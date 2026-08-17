#!/usr/bin/env python3
"""Sweep the keyboard on synthetic signals with known B and report recovery error.

The test suite asserts that error stays under a threshold. This reports the whole
distribution instead, which is what you want when the question is "how is it degrading?"
rather than "did it cross the line?". Run it after any change to the DSP and compare the
table to the one in docs/validation.md.

    python scripts/validate_synthetic.py
    python scripts/validate_synthetic.py --seeds 8 --stride 1
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from atunedpiano import notes  # noqa: E402
from atunedpiano.inharmonicity import InharmonicityError, estimate_key  # noqa: E402
from atunedpiano.synth import synth_key  # noqa: E402


@dataclass(frozen=True)
class Condition:
    label: str
    snr_db: float | None = None
    amplitude_jitter_db: float = 0.0
    detune_cents: float = 0.0


CONDITIONS = (
    Condition("clean"),
    Condition("40 dB SNR, 6 dB jitter", snr_db=40.0, amplitude_jitter_db=6.0),
    Condition("30 dB SNR, 6 dB jitter", snr_db=30.0, amplitude_jitter_db=6.0),
    Condition("20 dB SNR, 6 dB jitter", snr_db=20.0, amplitude_jitter_db=6.0),
    Condition("12 dB SNR, 6 dB jitter", snr_db=12.0, amplitude_jitter_db=6.0),
    Condition("30 dB SNR, -50 cents", snr_db=30.0, detune_cents=-50.0),
)

BANDS = (("bass A0-B2", 21, 47), ("mid C3-B5", 48, 83), ("treble C6-C8", 84, 108))


def band_of(midi: int) -> str:
    for label, low, high in BANDS:
        if low <= midi <= high:
            return label
    raise ValueError(f"midi {midi} is off the keyboard")


def run_condition(
    condition: Condition, *, seeds: int, stride: int, duration: float, sample_rate: int
) -> tuple[dict[str, list[tuple[float, float]]], list[str]]:
    """Return per-band (relative B error, |f0 error| in cents) and the notes that failed."""
    results: dict[str, list[tuple[float, float]]] = {label: [] for label, _, _ in BANDS}
    failures: list[str] = []

    for midi in notes.keyboard_midi_numbers()[::stride]:
        for seed in range(seeds):
            note = synth_key(
                midi,
                duration=duration,
                sample_rate=sample_rate,
                n_partials=24,
                snr_db=condition.snr_db,
                amplitude_jitter_db=condition.amplitude_jitter_db,
                detune_cents=condition.detune_cents,
                seed=seed,
            )
            try:
                estimate = estimate_key(note.signal, note.sample_rate, midi)
            except InharmonicityError:
                failures.append(f"{notes.midi_to_note(midi)}#{seed}")
                continue
            results[band_of(midi)].append(
                (
                    abs(estimate.B / note.B - 1.0),
                    abs(notes.cents(estimate.f0, note.f0)),
                )
            )
    return results, failures


def format_table(
    results: dict[str, list[tuple[float, float]]], failures: list[str]
) -> list[str]:
    lines = [
        f"  {'band':<14} {'n':>4}  {'B err med':>10} {'B err p95':>10} "
        f"{'B err max':>10}  {'f0 p95':>9} {'f0 max':>9}"
    ]
    for label, _, _ in BANDS:
        samples = results[label]
        if not samples:
            lines.append(f"  {label:<14} {0:>4}  {'-- all failed --':>54}")
            continue
        b_errors = np.array([b for b, _ in samples]) * 100.0
        f0_errors = np.array([f for _, f in samples])
        lines.append(
            f"  {label:<14} {len(samples):>4}  "
            f"{np.median(b_errors):>9.3f}% {np.percentile(b_errors, 95):>9.3f}% "
            f"{b_errors.max():>9.3f}%  "
            f"{np.percentile(f0_errors, 95):>8.4f}c {f0_errors.max():>8.4f}c"
        )
    if failures:
        shown = ", ".join(failures[:12]) + (" ..." if len(failures) > 12 else "")
        lines.append(f"  no fit: {len(failures)} ({shown})")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=3, help="realisations per note")
    parser.add_argument("--stride", type=int, default=1, help="test every Nth key")
    parser.add_argument("--duration", type=float, default=3.0, help="note length, seconds")
    parser.add_argument("--sample-rate", type=int, default=48_000)
    args = parser.parse_args(argv)

    print("Synthetic B recovery, 88 keys, stiff-string model f_n = n*f0*sqrt(1 + B*n^2)")
    print(
        f"{args.seeds} seed(s) per note, every {args.stride} key(s), "
        f"{args.duration:g} s at {args.sample_rate} Hz\n"
    )

    for condition in CONDITIONS:
        results, failures = run_condition(
            condition,
            seeds=args.seeds,
            stride=args.stride,
            duration=args.duration,
            sample_rate=args.sample_rate,
        )
        print(condition.label)
        print("\n".join(format_table(results, failures)))
        print()

    print(
        "B error is relative; f0 error is absolute, in cents. Extreme treble is limited by\n"
        "how many partials fall below Nyquist, not by the estimator -- C8 has four at 48 kHz."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
