"""Adaptive-window spectral analysis and sub-bin peak location.

Two constraints from docs/research.md drive the design here.

*One FFT size does not fit 88 notes.* A0 is 27.5 Hz and C8 is 4186 Hz. In the bass the
window must be long enough to separate partials spaced by the fundamental; in the treble a
long window mostly captures silence after a fast decay, and smears a spectrum that is
changing as the note dies. :func:`window_seconds` scales the window with the note.

*Analysis resolution is decoupled from any optimisation step.* Peak frequencies are
refined by parabolic interpolation on the log-magnitude spectrum, over a zero-padded FFT,
which puts the frequency error well below a cent. Nothing downstream is allowed to
re-quantise that to a 1-cent grid.

*Where the segment sits matters as much as how long it is.* This one came from a real
recording rather than the literature. Taking a fixed offset into the file assumes two
things a real note does not honour: that the file starts at the onset, and that the
envelope is well behaved wherever you happen to land. On the first reference recording
(``data/reference/NOTES.md``) a fixed offset put the segment across a 10 dB dip and
recovery, and rapid amplitude change within the window biased the interpolated frequencies
of partials 1 and 2 by nine cents. The same window length two-thirds of a second later was
clean. :func:`select_segment` therefore finds the onset first, then searches for a stretch
where the envelope decays smoothly.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
from scipy.signal import get_window

from .notes import cents, shift_cents

# Hann's main lobe is 4 bins wide, so a window of T seconds resolves peaks about 4/T Hz
# apart. Asking for MAIN_LOBES_PER_PARTIAL times that separation at spacing f0 gives the
# bass a long window and the treble a short one.
MAIN_LOBES_PER_PARTIAL = 8.0
MIN_WINDOW_SECONDS = 0.25
MAX_WINDOW_SECONDS = 1.5

# Zero-padding does not add information, but it moves the samples that parabolic
# interpolation sees closer to the true peak, which cuts the interpolation bias.
DEFAULT_ZERO_PAD = 8

# Envelope tracking, used to find the onset and to judge whether a candidate segment is
# steady. The block spans a few cycles of the note so the envelope of a low bass string is
# not modulated by its own waveform.
ENVELOPE_HOP_SECONDS = 0.01
ENVELOPE_CYCLES = 3.0

# A note is considered to have started once its short-time level first rises this far
# toward its peak.
ONSET_THRESHOLD_DB = -20.0

# A candidate segment is "steady" when its log envelope departs from a straight line by
# less than this. Straight in log terms means exponential decay, which is what a freely
# vibrating string does; a beat null, a double-decay knee or a compressor pumping all show
# up as curvature.
#
# Calibrated against the first reference recording, where the unsteady stretch scores
# 0.65-2.8 dB and everything past it scores 0.1-0.4 dB. Worth being clear about what this
# buys: on that file B came out at 3.20-3.32e-4 from *every* segment, steady or not, so
# this does not rescue a wrong answer. What it rescues is the residual column -- the one
# diagnostic that tells you whether to believe the answer -- which the unsteady segment
# inflated from 0.3 cents to 2.6.
STEADY_TOLERANCE_DB = 0.5

# Candidate segments quieter than this relative to the note's peak are a last resort: by
# then the upper partials have decayed into the noise and the fit has little to work with.
MIN_LEVEL_DB = -30.0

# How far apart to place candidate segment starts when searching.
CANDIDATE_HOP_SECONDS = 0.05


def window_seconds(
    f0_hint: float,
    *,
    minimum: float = MIN_WINDOW_SECONDS,
    maximum: float = MAX_WINDOW_SECONDS,
) -> float:
    """Analysis window length for a note near ``f0_hint``, in seconds."""
    if f0_hint <= 0.0:
        raise ValueError(f"f0_hint must be positive, got {f0_hint}")
    return float(np.clip(4.0 * MAIN_LOBES_PER_PARTIAL / f0_hint, minimum, maximum))


def attack_skip_seconds(f0_hint: float) -> float:
    """How much onset to discard before analysing, in seconds.

    The attack transient is broadband and its partial frequencies have not settled. Treble
    notes decay too fast to afford much; the bass can spare more and needs it, since the
    hammer noise lasts longer relative to the partial structure.
    """
    return 0.10 if f0_hint < 262.0 else 0.05


@dataclass(frozen=True)
class Peak:
    """A spectral peak refined to sub-bin resolution."""

    frequency: float
    amplitude: float
    bin_index: int


@dataclass(frozen=True)
class Spectrum:
    """Magnitude spectrum of one analysis window."""

    frequencies: np.ndarray
    magnitudes: np.ndarray
    sample_rate: int
    n_fft: int
    segment: "Segment | None" = None

    @property
    def bin_width(self) -> float:
        return self.sample_rate / self.n_fft

    @property
    def noise_floor(self) -> float:
        """Median magnitude, a robust stand-in for the broadband floor."""
        return float(np.median(self.magnitudes))

    def peak_near(
        self,
        target_hz: float,
        halfwidth_cents: float,
        *,
        min_magnitude: float = 0.0,
    ) -> Peak | None:
        """Strongest local maximum within ``halfwidth_cents`` of ``target_hz``.

        Returns ``None`` if the search band holds no local maximum above
        ``min_magnitude``. Requiring a genuine local maximum, rather than just the
        largest sample in the band, keeps the search from latching onto the skirt of a
        stronger neighbouring partial when the partial being sought is absent.
        """
        low = shift_cents(target_hz, -halfwidth_cents)
        high = shift_cents(target_hz, halfwidth_cents)
        lo_bin = max(1, int(np.floor(low / self.bin_width)))
        hi_bin = min(self.magnitudes.size - 2, int(np.ceil(high / self.bin_width)))
        if hi_bin <= lo_bin:
            return None

        band = self.magnitudes[lo_bin : hi_bin + 1]
        left = self.magnitudes[lo_bin - 1 : hi_bin]
        right = self.magnitudes[lo_bin + 1 : hi_bin + 2]
        is_maximum = (band >= left) & (band > right) & (band > min_magnitude)
        if not is_maximum.any():
            return None

        offsets = np.flatnonzero(is_maximum)
        best = int(offsets[np.argmax(band[offsets])]) + lo_bin
        return self.refine_peak(best)

    def refine_peak(self, bin_index: int) -> Peak:
        """Parabolic interpolation on the log-magnitude spectrum around ``bin_index``."""
        if bin_index <= 0 or bin_index >= self.magnitudes.size - 1:
            return Peak(
                frequency=float(self.frequencies[bin_index]),
                amplitude=float(self.magnitudes[bin_index]),
                bin_index=int(bin_index),
            )

        # Log magnitudes: a Gaussian-ish main lobe is close to a parabola in dB, which is
        # what makes three-point interpolation accurate here.
        a, b, c = np.log(
            np.maximum(self.magnitudes[bin_index - 1 : bin_index + 2], 1e-300)
        )
        denominator = a - 2.0 * b + c
        delta = 0.0 if denominator == 0.0 else 0.5 * (a - c) / denominator
        delta = float(np.clip(delta, -0.5, 0.5))
        return Peak(
            frequency=float((bin_index + delta) * self.bin_width),
            amplitude=float(np.exp(b - 0.25 * (a - c) * delta)),
            bin_index=int(bin_index),
        )


@dataclass(frozen=True)
class Segment:
    """A chosen slice of a recording, with the evidence for why it was chosen."""

    samples: np.ndarray
    start: float
    duration: float
    onset: float
    steadiness_db: float
    level_db: float
    searched: bool

    @property
    def is_steady(self) -> bool:
        return self.steadiness_db <= STEADY_TOLERANCE_DB

    def __len__(self) -> int:
        return int(self.samples.size)


def envelope(
    signal: np.ndarray, sample_rate: int, f0_hint: float
) -> tuple[np.ndarray, np.ndarray]:
    """Short-time level of ``signal`` in dB relative to its own peak.

    Returns the block start times and their levels. The block spans a few cycles of
    ``f0_hint`` so that a bass note's envelope reflects its decay rather than its waveform.
    """
    signal = np.asarray(signal, dtype=float)
    block = max(int(round(ENVELOPE_CYCLES / f0_hint * sample_rate)), 64)
    hop = max(int(round(ENVELOPE_HOP_SECONDS * sample_rate)), 1)
    if signal.size < block + hop:
        block = max(signal.size // 4, 1)

    cumulative = np.concatenate([[0.0], np.cumsum(signal**2)])
    starts = np.arange(0, signal.size - block + 1, hop)
    if starts.size == 0:
        starts = np.array([0])
        block = signal.size
        cumulative = np.concatenate([[0.0], np.cumsum(signal**2)])
    power = (cumulative[starts + block] - cumulative[starts]) / block
    peak = float(power.max())
    if peak <= 0.0:
        raise ValueError("signal is silent")
    return starts / sample_rate, 10.0 * np.log10(np.maximum(power, peak * 1e-12) / peak)


def find_onset(signal: np.ndarray, sample_rate: int, f0_hint: float) -> float:
    """Time at which the note starts, in seconds from the beginning of the file.

    A real recording has lead-in: room tone, the sound of reaching for the key, a moment of
    silence. Measuring the attack skip from the start of the file rather than from the note
    lands the analysis somewhere arbitrary, which is how the first reference recording came
    to be analysed across its own attack.
    """
    times, levels = envelope(signal, sample_rate, f0_hint)
    above = np.flatnonzero(levels > ONSET_THRESHOLD_DB)
    return float(times[above[0]]) if above.size else 0.0


def _score_window(
    times: np.ndarray, levels: np.ndarray, start: float, duration: float
) -> tuple[float, float]:
    """Return (steadiness, level) for the envelope inside one candidate window.

    Steadiness is the RMS departure of the log envelope from a straight line, in dB. A
    smooth exponential decay -- however steep -- scores near zero; a dip and recovery does
    not.
    """
    inside = (times >= start) & (times < start + duration)
    if inside.sum() < 4:
        return float("inf"), -np.inf
    t, level = times[inside], levels[inside]
    fit = np.polyval(np.polyfit(t, level, 1), t)
    return float(np.sqrt(np.mean((level - fit) ** 2))), float(np.mean(level))


def select_segment(
    signal: np.ndarray,
    sample_rate: int,
    f0_hint: float,
    *,
    start: float | None = None,
    attack_skip: float | None = None,
    duration: float | None = None,
    steady_tolerance_db: float = STEADY_TOLERANCE_DB,
    min_level_db: float = MIN_LEVEL_DB,
) -> Segment:
    """Choose a steady mid-decay slice of a recorded note.

    With ``start`` given, that slice is used as-is (seconds from the beginning of the file)
    and no search happens -- useful for reproducing a specific reading. Otherwise the onset
    is detected, ``attack_skip`` is measured from *there*, and the earliest window whose
    envelope decays smoothly is taken. Earliest matters twice over: the longer you wait, the
    fewer upper partials are still above the noise, and those are what determine B; and
    preferring the earliest is also what keeps trailing silence out of the result, since a
    note's own steady stretch always precedes the dead air after it. ``min_level_db`` is a
    backstop for the case where no candidate is steady, not the mechanism that excludes
    silence.

    Falls back to whatever is available on a recording too short for the ideal window, and
    to the steadiest candidate if none clears the tolerance, rather than refusing outright.
    A marginal segment analysed and reported is more useful than no answer; the caller can
    read :attr:`Segment.steadiness_db` and decide.
    """
    signal = np.asarray(signal, dtype=float)
    if signal.ndim != 1:
        raise ValueError(f"expected a mono signal, got shape {signal.shape}")
    if attack_skip is None:
        attack_skip = attack_skip_seconds(f0_hint)
    if duration is None:
        duration = window_seconds(f0_hint)

    length = int(round(duration * sample_rate))
    if length < 16 or signal.size < 16:
        raise ValueError(
            f"signal too short to analyse: {signal.size} samples at {sample_rate} Hz"
        )

    onset = 0.0 if start is not None else find_onset(signal, sample_rate, f0_hint)
    searched = start is None
    if searched:
        times, levels = envelope(signal, sample_rate, f0_hint)
        first = onset + attack_skip
        last = max(first, signal.size / sample_rate - duration)
        candidates = np.arange(first, last + 1e-9, CANDIDATE_HOP_SECONDS)
        if candidates.size == 0:
            candidates = np.array([first])

        scored = [(c, *_score_window(times, levels, c, duration)) for c in candidates]
        loud = [s for s in scored if s[2] >= min_level_db]
        pool = loud or scored
        steady = [s for s in pool if s[1] <= steady_tolerance_db]
        start, steadiness, level = steady[0] if steady else min(pool, key=lambda s: s[1])
    else:
        times, levels = envelope(signal, sample_rate, f0_hint)
        steadiness, level = _score_window(times, levels, start, duration)

    begin = int(round(start * sample_rate))
    if begin + length > signal.size:
        begin = min(begin, max(0, signal.size - length))
        length = min(length, signal.size - begin)
    if length < 16:
        raise ValueError(
            f"signal too short to analyse: {signal.size} samples at {sample_rate} Hz"
        )

    return Segment(
        samples=signal[begin : begin + length],
        start=begin / sample_rate,
        duration=length / sample_rate,
        onset=onset,
        steadiness_db=steadiness,
        level_db=level,
        searched=searched,
    )


def compute_spectrum(
    segment: np.ndarray,
    sample_rate: int,
    *,
    zero_pad: int = DEFAULT_ZERO_PAD,
    window: str = "hann",
) -> Spectrum:
    """Windowed, zero-padded magnitude spectrum of one segment."""
    segment = np.asarray(segment, dtype=float)
    if segment.size < 16:
        raise ValueError(f"segment too short: {segment.size} samples")
    if zero_pad < 1:
        raise ValueError(f"zero_pad must be >= 1, got {zero_pad}")

    segment = segment - float(np.mean(segment))  # drop DC offset from the capture chain
    taper = get_window(window, segment.size, fftbins=True)
    n_fft = int(2 ** np.ceil(np.log2(segment.size * zero_pad)))
    magnitudes = np.abs(np.fft.rfft(segment * taper, n=n_fft))
    return Spectrum(
        frequencies=np.fft.rfftfreq(n_fft, d=1.0 / sample_rate),
        magnitudes=magnitudes,
        sample_rate=int(sample_rate),
        n_fft=n_fft,
    )


def analyse(
    signal: np.ndarray,
    sample_rate: int,
    f0_hint: float,
    *,
    start: float | None = None,
    attack_skip: float | None = None,
    duration: float | None = None,
    zero_pad: int = DEFAULT_ZERO_PAD,
) -> Spectrum:
    """Select a steady segment sized for ``f0_hint`` and transform it.

    The chosen segment is kept on the returned :class:`Spectrum` so that whatever reports
    the result can say where the analysis actually looked, rather than reciting the
    defaults it would have used.
    """
    segment = select_segment(
        signal,
        sample_rate,
        f0_hint,
        start=start,
        attack_skip=attack_skip,
        duration=duration,
    )
    spectrum = compute_spectrum(segment.samples, sample_rate, zero_pad=zero_pad)
    return replace(spectrum, segment=segment)


def cents_error(measured_hz: float, expected_hz: float) -> float:
    """Convenience alias for reporting peak error in cents."""
    return cents(measured_hz, expected_hz)
