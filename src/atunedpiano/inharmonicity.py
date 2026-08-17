"""Per-note (B, f0) estimation from a single recorded note.

The estimator follows the Median-Adjustive-Trajectories idea (Hodgkinson et al. 2009,
described in docs/research.md section 4): walk up the partials one at a time, and after
each one re-fit the stiff-string model so the *next* partial is predicted by everything
found so far rather than by a fixed harmonic template. Because inharmonicity pushes
partial ``n`` sharp by a factor that grows like ``n^2``, a fixed template loses the
trajectory within a few partials in the treble; an adjustive one does not.

Two fits are used. The first is linear and closed-form, which is what makes it safe to run
inside the tracking loop:

    (f_n / n)^2 = f0^2 + f0^2 * B * n^2

is a straight line in ``n^2``, so ``f0`` and ``B`` come from an ordinary least-squares
intercept and slope. The second, after outlier rejection, is a nonlinear fit that minimises
residuals **in cents**, which is the metric that matters perceptually and the one that
weights the whole keyboard evenly.

Partials are weighted equally rather than by amplitude. Amplitude weighting is tempting --
loud partials have better-conditioned frequency estimates -- but the upper partials that
carry nearly all the information about B are exactly the quiet ones, so it would suppress
the signal being measured.

This is a from-scratch implementation of the published mathematics. No code was taken from
the GPLv3 Entropy Piano Tuner; see CLAUDE.md, constraint 1.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import least_squares

from .notes import cents, midi_to_hz, note_to_hz
from .spectrum import DEFAULT_ZERO_PAD, Spectrum, analyse

# Above this the stiff-string model stops describing a piano string, so a fit that wants a
# larger B has almost certainly mis-indexed a partial.
B_MAX = 0.06


class InharmonicityError(RuntimeError):
    """Raised when a note yields too little usable spectral structure to fit."""


@dataclass(frozen=True)
class Partial:
    """One tracked partial and its disagreement with the fitted model."""

    index: int
    frequency: float
    amplitude: float
    residual_cents: float = float("nan")


@dataclass(frozen=True)
class InharmonicityEstimate:
    """Fitted stiff-string parameters for one note."""

    f0: float
    B: float
    partials: tuple[Partial, ...]
    rejected: tuple[Partial, ...] = ()
    B_stderr: float = float("nan")
    f0_stderr_cents: float = float("nan")
    spectrum: Spectrum | None = field(default=None, repr=False, compare=False)

    @property
    def n_partials(self) -> int:
        return len(self.partials)

    @property
    def first_partial(self) -> float:
        """Model frequency of partial 1, ``f0 * sqrt(1 + B)`` -- the pitch a tuner hears."""
        return self.predicted_frequency(1)

    @property
    def residual_cents_rms(self) -> float:
        if not self.partials:
            return float("nan")
        return float(np.sqrt(np.mean([p.residual_cents**2 for p in self.partials])))

    @property
    def max_residual_cents(self) -> float:
        if not self.partials:
            return float("nan")
        return float(np.max(np.abs([p.residual_cents for p in self.partials])))

    def predicted_frequency(self, n: int) -> float:
        """Model frequency of partial ``n``."""
        return float(n * self.f0 * np.sqrt(1.0 + self.B * n * n))

    def inharmonicity_cents(self, n: int) -> float:
        """How sharp partial ``n`` sits relative to a pure harmonic of ``f0``."""
        return cents(self.predicted_frequency(n), n * self.f0)


def fit_linear(indices: np.ndarray, frequencies: np.ndarray) -> tuple[float, float]:
    """Closed-form (f0, B) from partial frequencies, via the ``n^2`` linearisation.

    Two partials give an exact solve, more give least squares. B is clamped to a physically
    plausible range; a negative slope means the measured partials bend flat, which no real
    string does and which signals a mis-indexed partial rather than a small negative B.
    """
    indices = np.asarray(indices, dtype=float)
    frequencies = np.asarray(frequencies, dtype=float)
    if indices.size < 2:
        raise InharmonicityError("need at least two partials for a linear fit")

    x = indices**2
    y = (frequencies / indices) ** 2
    slope, intercept = np.polyfit(x, y, 1)
    if intercept <= 0.0:
        raise InharmonicityError("degenerate fit: non-positive f0^2 intercept")

    f0 = float(np.sqrt(intercept))
    B = float(np.clip(slope / intercept, 0.0, B_MAX))
    return f0, B


def _residual_cents(f0: float, B: float, indices: np.ndarray, frequencies: np.ndarray):
    predicted = indices * f0 * np.sqrt(1.0 + B * indices**2)
    return 1200.0 * np.log2(frequencies / predicted)


def fit_nonlinear(
    indices: np.ndarray,
    frequencies: np.ndarray,
    initial: tuple[float, float],
) -> tuple[float, float, float, float]:
    """Refine (f0, B) by least squares on cent residuals.

    Returns ``(f0, B, B_stderr, f0_stderr_cents)``. The standard errors come from the
    Jacobian at the solution and are ``nan`` when there are no degrees of freedom left.
    They are worth reading: in the bass, where few clean high partials survive, a fit can
    look tidy and still pin B only to within a factor of two.
    """
    indices = np.asarray(indices, dtype=float)
    frequencies = np.asarray(frequencies, dtype=float)
    f0_init, B_init = initial

    result = least_squares(
        lambda p: _residual_cents(p[0], p[1], indices, frequencies),
        x0=[f0_init, max(B_init, 1e-9)],
        bounds=([f0_init * 0.5, 0.0], [f0_init * 2.0, B_MAX]),
        xtol=1e-14,
        ftol=1e-14,
        gtol=1e-14,
    )
    f0, B = float(result.x[0]), float(result.x[1])

    dof = indices.size - 2
    B_stderr = f0_stderr_cents = float("nan")
    if dof > 0:
        variance = float(np.sum(result.fun**2)) / dof
        try:
            covariance = np.linalg.inv(result.jac.T @ result.jac) * variance
        except np.linalg.LinAlgError:
            covariance = None
        if covariance is not None and np.all(np.diag(covariance) >= 0.0):
            f0_stderr_hz = float(np.sqrt(covariance[0, 0]))
            B_stderr = float(np.sqrt(covariance[1, 1]))
            f0_stderr_cents = 1200.0 * float(np.log2(1.0 + f0_stderr_hz / f0))
    return f0, B, B_stderr, f0_stderr_cents


def _search_halfwidth_cents(
    n: int, n_fitted: int, *, search_cents: float, hint_cents: float
) -> float:
    """How far from the predicted position to look for partial ``n``.

    With three or more partials fitted the model is trustworthy and the window is tight.
    Before that, B is unknown, and assuming B=0 misplaces partial ``n`` by an amount that
    grows with ``n^2`` -- so the window has to cover the whole plausible B range. It is
    capped short of half the distance to the neighbouring partial, which is what stops the
    search from ever grabbing the wrong one.
    """
    if n_fitted >= 3:
        return search_cents
    if n_fitted == 2:
        return 2.0 * search_cents
    span = 600.0 * np.log2((1.0 + B_MAX * n * n) / (1.0 + B_MAX))
    return float(min(hint_cents + span, 340.0))


def track_partials(
    spectrum: Spectrum,
    f0_hint: float,
    *,
    max_partials: int = 20,
    search_cents: float = 40.0,
    hint_cents: float = 100.0,
    max_consecutive_misses: int = 3,
    prominence_ratio: float = 6.0,
    floor_db: float = 70.0,
) -> list[Partial]:
    """Walk up the partial series, re-fitting the model after each new partial.

    ``f0_hint`` is the nominal pitch of the note -- roughly where partial 1 should be, not
    the ideal stiffness-free ``f0``. A piano that has drifted or been deliberately stretched
    is still found, as long as it is inside ``hint_cents`` of nominal.
    """
    if max_partials < 2:
        raise ValueError(f"max_partials must be >= 2, got {max_partials}")

    nyquist = spectrum.sample_rate / 2.0
    min_magnitude = max(
        spectrum.noise_floor * prominence_ratio,
        float(np.max(spectrum.magnitudes)) * 10.0 ** (-floor_db / 20.0),
    )

    found: list[Partial] = []
    f0_model, B_model = f0_hint, 0.0
    misses = 0

    for n in range(1, max_partials + 1):
        predicted = n * f0_model * np.sqrt(1.0 + B_model * n * n)
        if predicted > 0.95 * nyquist:
            break

        halfwidth = _search_halfwidth_cents(
            n, len(found), search_cents=search_cents, hint_cents=hint_cents
        )
        peak = spectrum.peak_near(predicted, halfwidth, min_magnitude=min_magnitude)
        if peak is None:
            misses += 1
            if misses >= max_consecutive_misses:
                break
            continue

        misses = 0
        found.append(Partial(index=n, frequency=peak.frequency, amplitude=peak.amplitude))
        if len(found) >= 2:
            try:
                f0_model, B_model = fit_linear(
                    np.array([p.index for p in found]),
                    np.array([p.frequency for p in found]),
                )
            except InharmonicityError:
                # Keep the previous model and let the next partial arbitrate.
                pass

    return found


def _reject_outliers(
    partials: list[Partial], outlier_cents: float, min_partials: int
) -> tuple[list[Partial], list[Partial], tuple[float, float]]:
    """Iteratively drop partials the model cannot explain, refitting each round.

    Real recordings contain false beats, phantom partials and neighbouring-string energy,
    any of which can put a peak where the model does not expect one. The threshold is the
    looser of a fixed cent tolerance and a median-absolute-deviation band, so a uniformly
    noisy fit is not stripped down to nothing.
    """
    kept = list(partials)
    rejected: list[Partial] = []

    for _ in range(3):
        indices = np.array([p.index for p in kept], dtype=float)
        frequencies = np.array([p.frequency for p in kept], dtype=float)
        f0, B = fit_linear(indices, frequencies)
        residuals = _residual_cents(f0, B, indices, frequencies)

        mad = float(np.median(np.abs(residuals - np.median(residuals))))
        threshold = max(outlier_cents, 6.0 * mad)
        bad = np.abs(residuals) > threshold
        if not bad.any() or len(kept) - int(bad.sum()) < min_partials:
            return kept, rejected, (f0, B)

        rejected.extend(p for p, is_bad in zip(kept, bad) if is_bad)
        kept = [p for p, is_bad in zip(kept, bad) if not is_bad]

    indices = np.array([p.index for p in kept], dtype=float)
    frequencies = np.array([p.frequency for p in kept], dtype=float)
    return kept, rejected, fit_linear(indices, frequencies)


def estimate_inharmonicity(
    signal: np.ndarray,
    sample_rate: int,
    f0_hint: float,
    *,
    max_partials: int = 20,
    min_partials: int = 4,
    search_cents: float = 40.0,
    hint_cents: float = 100.0,
    outlier_cents: float = 20.0,
    attack_skip: float | None = None,
    duration: float | None = None,
    zero_pad: int = DEFAULT_ZERO_PAD,
) -> InharmonicityEstimate:
    """Estimate (B, f0) for a single recorded note.

    Args:
        signal: Mono samples of one note.
        sample_rate: Samples per second.
        f0_hint: Nominal pitch of the note in Hz (where partial 1 is expected).
        max_partials: Highest partial to look for. Partials above Nyquist stop the walk.
        min_partials: Fewest partials that may be fitted; below this the fit is refused
            rather than returned with a number nobody should trust.
        search_cents: Half-width of the search window once the model is established.
        hint_cents: How far partial 1 may sit from ``f0_hint`` -- i.e. how out of tune the
            piano is allowed to be.
        outlier_cents: Residual above which a partial is dropped and the fit repeated.
        attack_skip: Seconds of onset to discard. ``None`` scales it with the note.
        duration: Analysis window in seconds. ``None`` scales it with the note.
        zero_pad: FFT zero-padding factor, for sub-bin peak location.

    Raises:
        InharmonicityError: if fewer than ``min_partials`` usable partials are found.
    """
    spectrum = analyse(
        signal,
        sample_rate,
        f0_hint,
        attack_skip=attack_skip,
        duration=duration,
        zero_pad=zero_pad,
    )
    tracked = track_partials(
        spectrum,
        f0_hint,
        max_partials=max_partials,
        search_cents=search_cents,
        hint_cents=hint_cents,
    )
    if len(tracked) < min_partials:
        raise InharmonicityError(
            f"found {len(tracked)} partials near {f0_hint:.2f} Hz, need {min_partials}"
        )

    kept, rejected, linear = _reject_outliers(tracked, outlier_cents, min_partials)
    indices = np.array([p.index for p in kept], dtype=float)
    frequencies = np.array([p.frequency for p in kept], dtype=float)
    f0, B, B_stderr, f0_stderr_cents = fit_nonlinear(indices, frequencies, linear)

    residuals = _residual_cents(f0, B, indices, frequencies)
    partials = tuple(
        Partial(p.index, p.frequency, p.amplitude, float(r))
        for p, r in zip(kept, residuals)
    )
    return InharmonicityEstimate(
        f0=f0,
        B=B,
        partials=partials,
        rejected=tuple(rejected),
        B_stderr=B_stderr,
        f0_stderr_cents=f0_stderr_cents,
        spectrum=spectrum,
    )


def estimate_key(
    signal: np.ndarray,
    sample_rate: int,
    key: int | str,
    *,
    a4_hz: float = 440.0,
    **kwargs,
) -> InharmonicityEstimate:
    """Estimate (B, f0) for a named key (``"A4"``) or MIDI number, using it as the hint."""
    f0_hint = note_to_hz(key, a4_hz=a4_hz) if isinstance(key, str) else midi_to_hz(key, a4_hz)
    return estimate_inharmonicity(signal, sample_rate, f0_hint, **kwargs)
