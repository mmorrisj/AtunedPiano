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
"""

from __future__ import annotations

from dataclasses import dataclass

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


def select_segment(
    signal: np.ndarray,
    sample_rate: int,
    f0_hint: float,
    *,
    attack_skip: float | None = None,
    duration: float | None = None,
) -> np.ndarray:
    """Cut a steady mid-decay segment: past the attack, before the note dies away.

    Falls back to whatever is available if the recording is shorter than the ideal window
    rather than failing, since a short note is still worth analysing -- just with coarser
    frequency resolution.
    """
    signal = np.asarray(signal, dtype=float)
    if signal.ndim != 1:
        raise ValueError(f"expected a mono signal, got shape {signal.shape}")

    if attack_skip is None:
        attack_skip = attack_skip_seconds(f0_hint)
    if duration is None:
        duration = window_seconds(f0_hint)

    start = int(round(attack_skip * sample_rate))
    length = int(round(duration * sample_rate))
    if start + length > signal.size:
        start = min(start, max(0, signal.size - length))
        length = min(length, signal.size - start)
    if length < 16:
        raise ValueError(
            f"signal too short to analyse: {signal.size} samples at {sample_rate} Hz"
        )
    return signal[start : start + length]


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
    attack_skip: float | None = None,
    duration: float | None = None,
    zero_pad: int = DEFAULT_ZERO_PAD,
) -> Spectrum:
    """Select a mid-decay segment sized for ``f0_hint`` and transform it."""
    segment = select_segment(
        signal, sample_rate, f0_hint, attack_skip=attack_skip, duration=duration
    )
    return compute_spectrum(segment, sample_rate, zero_pad=zero_pad)


def cents_error(measured_hz: float, expected_hz: float) -> float:
    """Convenience alias for reporting peak error in cents."""
    return cents(measured_hz, expected_hz)
