"""Synthetic inharmonic piano tones with known (f0, B).

This module is the project's ground truth. Estimators are validated by generating a
signal whose inharmonicity coefficient is known exactly, running the estimator, and
checking that it recovers the value. Nothing here reads audio or estimates anything --
it only produces signals, so a test failure always points at the estimator.

The string model is the standard stiff-string relation

    f_n = n * f0 * sqrt(1 + B * n^2)

where ``f0`` is the ideal (stiffness-free) fundamental and ``B`` the inharmonicity
coefficient. Note that the *measured* first partial is ``f0 * sqrt(1 + B)``, which is
slightly sharp of ``f0``; the two are not interchangeable and the distinction matters at
treble values of B.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .notes import midi_to_hz

DEFAULT_SR = 48_000

# Plausible B across the keyboard, for generating test material only. Anchored on the
# shape reported in the literature (docs/research.md section 4): a minimum in the long
# bass strings, rising by more than two orders of magnitude into the treble. These are
# not measurements of any particular piano.
_B_PROFILE_MIDI = np.array([21, 36, 48, 60, 72, 84, 96, 108], dtype=float)
_B_PROFILE_VALUES = np.array(
    [2.0e-4, 8.0e-5, 1.4e-4, 4.0e-4, 1.2e-3, 4.0e-3, 1.4e-2, 4.0e-2], dtype=float
)


def typical_B(midi: float) -> float:
    """A plausible inharmonicity coefficient for a key, for building test signals.

    Log-linear interpolation over the profile above. Use this to sweep the keyboard with
    realistic magnitudes; never treat it as a measurement or as a prior in an estimator.
    """
    return float(
        np.exp(np.interp(midi, _B_PROFILE_MIDI, np.log(_B_PROFILE_VALUES)))
    )


def partial_frequencies(f0: float, B: float, n_partials: int) -> np.ndarray:
    """Frequencies of partials 1..``n_partials`` for the stiff-string model."""
    if f0 <= 0.0:
        raise ValueError(f"f0 must be positive, got {f0}")
    if B < 0.0:
        raise ValueError(f"B must be non-negative, got {B}")
    if n_partials < 1:
        raise ValueError(f"n_partials must be >= 1, got {n_partials}")
    n = np.arange(1, n_partials + 1, dtype=float)
    return n * f0 * np.sqrt(1.0 + B * n * n)


def first_partial(f0: float, B: float) -> float:
    """The measured first partial, ``f0 * sqrt(1 + B)``."""
    return float(f0 * np.sqrt(1.0 + B))


def f0_from_first_partial(f1: float, B: float) -> float:
    """Invert :func:`first_partial`: the ideal fundamental behind a measured partial 1."""
    return float(f1 / np.sqrt(1.0 + B))


@dataclass(frozen=True)
class SyntheticNote:
    """A generated tone together with the parameters that produced it."""

    signal: np.ndarray
    sample_rate: int
    f0: float
    B: float
    frequencies: np.ndarray
    amplitudes: np.ndarray

    @property
    def n_partials(self) -> int:
        return int(self.frequencies.size)

    @property
    def duration(self) -> float:
        return self.signal.size / self.sample_rate


def synth_note(
    f0: float,
    B: float,
    *,
    duration: float = 2.0,
    sample_rate: int = DEFAULT_SR,
    n_partials: int = 24,
    amplitude_rolloff: float = 1.0,
    amplitude_jitter_db: float = 0.0,
    decay_time: float | None = None,
    decay_exponent: float = 0.7,
    attack_time: float = 0.005,
    snr_db: float | None = None,
    seed: int | None = 0,
) -> SyntheticNote:
    """Generate an inharmonic tone with known ``f0`` and ``B``.

    Partials above 98% of Nyquist are dropped rather than aliased, so a treble note asked
    for 24 partials will come back with fewer; the returned :class:`SyntheticNote` always
    reports what was actually synthesised.

    Args:
        f0: Ideal fundamental in Hz (not the measured first partial).
        B: Inharmonicity coefficient.
        duration: Length of the signal in seconds.
        sample_rate: Samples per second.
        n_partials: Number of partials requested, before the Nyquist cut.
        amplitude_rolloff: Partial ``n`` gets amplitude ``n ** -amplitude_rolloff``.
        amplitude_jitter_db: Standard deviation of random per-partial gain, in dB. Real
            piano partials are far from a smooth roll-off; use this to check that an
            estimator does not lean on a tidy amplitude profile.
        decay_time: Exponential decay time constant of partial 1, in seconds. ``None``
            picks a frequency-dependent default (long in the bass, short in the treble).
        decay_exponent: Partial ``n`` decays with time constant
            ``decay_time * n ** -decay_exponent``, so upper partials die first.
        attack_time: Raised-cosine fade-in, to avoid a click at the onset.
        snr_db: Signal-to-noise ratio of added white Gaussian noise, in dB relative to
            signal RMS. ``None`` adds no noise.
        seed: Seed for phases, amplitude jitter and noise. Fixed by default so tests are
            deterministic; vary it to sample different realisations.
    """
    if duration <= 0.0:
        raise ValueError(f"duration must be positive, got {duration}")

    rng = np.random.default_rng(seed)
    nyquist = sample_rate / 2.0

    frequencies = partial_frequencies(f0, B, n_partials)
    keep = frequencies < 0.98 * nyquist
    if not keep.any():
        raise ValueError(
            f"no partials below Nyquist for f0={f0} Hz at {sample_rate} Hz sample rate"
        )
    frequencies = frequencies[keep]
    n = np.arange(1, frequencies.size + 1, dtype=float)

    amplitudes = n**-amplitude_rolloff
    if amplitude_jitter_db > 0.0:
        amplitudes = amplitudes * 10.0 ** (
            rng.normal(0.0, amplitude_jitter_db, size=amplitudes.size) / 20.0
        )

    if decay_time is None:
        decay_time = float(np.clip(200.0 / f0, 0.4, 6.0))
    taus = decay_time * n**-decay_exponent

    t = np.arange(int(round(duration * sample_rate)), dtype=float) / sample_rate
    phases = rng.uniform(0.0, 2.0 * np.pi, size=frequencies.size)

    # (n_partials, n_samples) outer products; fine for the sizes this harness uses.
    osc = np.sin(2.0 * np.pi * frequencies[:, None] * t[None, :] + phases[:, None])
    env = np.exp(-t[None, :] / taus[:, None])
    signal = np.sum(amplitudes[:, None] * osc * env, axis=0)

    if attack_time > 0.0:
        n_attack = min(int(round(attack_time * sample_rate)), signal.size)
        if n_attack > 1:
            ramp = 0.5 * (1.0 - np.cos(np.pi * np.arange(n_attack) / n_attack))
            signal[:n_attack] *= ramp

    if snr_db is not None:
        rms = float(np.sqrt(np.mean(signal**2)))
        noise_rms = rms * 10.0 ** (-snr_db / 20.0)
        signal = signal + rng.normal(0.0, noise_rms, size=signal.size)

    return SyntheticNote(
        signal=signal,
        sample_rate=sample_rate,
        f0=float(f0),
        B=float(B),
        frequencies=frequencies,
        amplitudes=amplitudes,
    )


def synth_key(
    midi: int,
    *,
    B: float | None = None,
    detune_cents: float = 0.0,
    **kwargs,
) -> SyntheticNote:
    """Generate a tone for a keyboard key, tuned so partial 1 lands on the target pitch.

    A real piano is tuned by ear or by meter to put the *measured* partial near the
    intended pitch, so this solves ``f0`` backwards from the first partial rather than
    setting ``f0`` to the equal-tempered frequency. ``detune_cents`` offsets that target,
    which is what a stretched tuning or an out-of-tune piano looks like to an estimator.
    """
    if B is None:
        B = typical_B(midi)
    target_f1 = midi_to_hz(midi) * 2.0 ** (detune_cents / 1200.0)
    return synth_note(f0_from_first_partial(target_f1, B), B, **kwargs)


def write_wav(path, note: SyntheticNote, *, peak: float = 0.7) -> None:
    """Write a synthetic note to a 32-bit float WAV, normalised to ``peak``."""
    from scipy.io import wavfile

    signal = np.asarray(note.signal, dtype=np.float32)
    largest = float(np.max(np.abs(signal))) or 1.0
    wavfile.write(str(path), note.sample_rate, (signal * (peak / largest)).astype(np.float32))
