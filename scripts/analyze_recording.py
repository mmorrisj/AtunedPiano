#!/usr/bin/env python3
"""Fit (B, f0) to a real recorded note and print the evidence behind the fit.

This is the sanity anchor. Synthetic tests can all pass while the result is still wrong on
a real piano, so keep a recording of a note you have tuned by ear (see
docs/recording-protocol.md) and run this against it whenever the estimator changes. What
matters is not just the B it prints but the partial table: the residuals tell you whether
the model actually describes the string, and a low residual with an implausible B usually
means partials were mis-indexed.

    python scripts/analyze_recording.py data/reference/A4-single-string.wav --note A4
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from atunedpiano import notes  # noqa: E402
from atunedpiano.inharmonicity import (  # noqa: E402
    InharmonicityError,
    InharmonicityEstimate,
    estimate_key,
)
from atunedpiano.spectrum import STEADY_TOLERANCE_DB  # noqa: E402
from atunedpiano.synth import typical_B  # noqa: E402


def read_wav(path: Path) -> tuple[np.ndarray, int]:
    """Read a WAV as mono float. Integer formats are scaled to +/-1."""
    from scipy.io import wavfile

    sample_rate, data = wavfile.read(str(path))
    data = np.asarray(data)
    if data.dtype.kind in "iu":
        data = data.astype(float) / float(np.iinfo(data.dtype).max)
    else:
        data = data.astype(float)
    if data.ndim > 1:
        data = data.mean(axis=1)
    return data, int(sample_rate)


def clipping_fraction(signal: np.ndarray) -> float:
    peak = float(np.max(np.abs(signal)))
    if peak == 0.0:
        return 0.0
    return float(np.mean(np.abs(signal) >= 0.999 * peak))


def report(
    estimate: InharmonicityEstimate,
    *,
    key: str,
    nominal_hz: float,
    signal: np.ndarray,
    sample_rate: int,
    path: Path,
) -> None:
    print(f"{path.name}: {signal.size / sample_rate:.2f} s at {sample_rate} Hz")

    segment = estimate.spectrum.segment
    how = "searched for a steady stretch" if segment.searched else "start given"
    print(
        f"note onset at {segment.onset:.2f} s; analysed {segment.duration:.2f} s "
        f"from {segment.start:.2f} s ({how})"
    )
    print(
        f"segment envelope departs from a smooth decay by {segment.steadiness_db:.2f} dB, "
        f"at {segment.level_db:.1f} dB relative to the note's peak"
    )
    if not segment.is_steady:
        print(
            f"WARNING: no segment scored under {STEADY_TOLERANCE_DB:.2f} dB -- the envelope "
            "is unsteady throughout, so partial frequencies may be biased"
        )
    print(f"peak sample {float(np.max(np.abs(signal))):.3f}")
    clipped = clipping_fraction(signal)
    if clipped > 1e-4:
        print(f"WARNING: {clipped * 100:.2f}% of samples at full scale -- likely clipped")
    print()

    print(f"key {key}  nominal {nominal_hz:.3f} Hz")
    print(f"  B          {estimate.B:.6e}  +/- {estimate.B_stderr:.1e}")
    print(f"  f0         {estimate.f0:.4f} Hz  +/- {estimate.f0_stderr_cents:.4f} cents")
    print(
        f"  partial 1  {estimate.first_partial:.4f} Hz  "
        f"({notes.cents(estimate.first_partial, nominal_hz):+.2f} cents from nominal)"
    )
    print(
        f"  residuals  {estimate.residual_cents_rms:.4f} cents rms, "
        f"{estimate.max_residual_cents:.4f} max, over {estimate.n_partials} partials"
    )
    if estimate.rejected:
        dropped = ", ".join(str(p.index) for p in estimate.rejected)
        print(f"  rejected   partials {dropped} (residual above tolerance)")

    expected = typical_B(notes.note_to_midi(key))
    ratio = estimate.B / expected
    verdict = "plausible" if 0.2 <= ratio <= 5.0 else "OUTSIDE the usual range"
    print(f"  vs typical {expected:.3e} for this key: {ratio:.2f}x, {verdict}")
    print()

    print(f"  {'n':>3} {'measured Hz':>13} {'model Hz':>13} {'resid c':>9} {'level dB':>9}")
    loudest = max(p.amplitude for p in estimate.partials)
    for partial in estimate.partials:
        print(
            f"  {partial.index:>3} {partial.frequency:>13.4f} "
            f"{estimate.predicted_frequency(partial.index):>13.4f} "
            f"{partial.residual_cents:>+9.3f} "
            f"{20 * np.log10(partial.amplitude / loudest):>9.1f}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="WAV file containing one note")
    parser.add_argument("--note", required=True, help="key that was played, e.g. A4 or C#2")
    parser.add_argument("--a4", type=float, default=440.0, help="concert pitch reference")
    parser.add_argument("--max-partials", type=int, default=20)
    parser.add_argument("--min-partials", type=int, default=4)
    parser.add_argument(
        "--hint-cents",
        type=float,
        default=100.0,
        help="how far from nominal partial 1 may sit; raise for a badly flat piano",
    )
    parser.add_argument(
        "--attack-skip",
        type=float,
        default=None,
        help="seconds to discard after the detected note onset (not after the file start)",
    )
    parser.add_argument(
        "--start",
        type=float,
        default=None,
        help="analyse from this many seconds into the file, skipping the steady-segment "
        "search; use to reproduce a specific reading",
    )
    parser.add_argument(
        "--duration", type=float, default=None, help="analysis window, seconds"
    )
    args = parser.parse_args(argv)

    if not args.path.exists():
        print(f"no such file: {args.path}", file=sys.stderr)
        return 2

    signal, sample_rate = read_wav(args.path)
    nominal_hz = notes.note_to_hz(args.note, a4_hz=args.a4)

    try:
        estimate = estimate_key(
            signal,
            sample_rate,
            args.note,
            a4_hz=args.a4,
            max_partials=args.max_partials,
            min_partials=args.min_partials,
            hint_cents=args.hint_cents,
            start=args.start,
            attack_skip=args.attack_skip,
            duration=args.duration,
        )
    except InharmonicityError as error:
        print(f"could not fit {args.note} in {args.path.name}: {error}", file=sys.stderr)
        print(
            "Check that the note argument matches what was played, that the recording is\n"
            "long enough, and that the piano is within --hint-cents of nominal. A residual\n"
            "complaint usually means the segment analysed had decayed too far -- try an\n"
            "earlier --start, or record a louder note.",
            file=sys.stderr,
        )
        return 1

    report(
        estimate,
        key=args.note,
        nominal_hz=nominal_hz,
        signal=signal,
        sample_rate=sample_rate,
        path=args.path,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
