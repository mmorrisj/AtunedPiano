# AtunedPiano

Measuring piano inharmonicity from recordings, as the foundation for a computed tuning
curve.

Piano strings are stiff, so their partials are not exact harmonics — partial `n` sits sharp
by a factor that grows with `n²`:

```
f_n = n · f0 · √(1 + B·n²)
```

`B` is the inharmonicity coefficient, and it varies across the keyboard by more than two
orders of magnitude. It is why octaves on a piano are stretched, why the Railsback curve
exists, and why a piano tuned to exact equal temperament sounds wrong. Everything a tuning
program does downstream depends on measuring it accurately first.

## Current state

**Stage 1: per-note (B, f0) estimation from a single recorded note.** This is the whole of
what works today, and it is validated rather than merely written.

- `atunedpiano.synth` — synthetic tones with known B, the project's ground truth
- `atunedpiano.spectrum` — note-adaptive windowing, sub-cent peak location
- `atunedpiano.inharmonicity` — MAT-style partial tracking and least-squares fit

Recovery across all 88 keys: B within 0.001% on clean signals, within 0.1% at 30 dB SNR
with irregular partial amplitudes, f0 within 0.02 cents, and robust to a piano detuned by
±90 cents. Full numbers in [docs/validation.md](docs/validation.md).

Not yet built, deliberately: the keyboard-wide tuning curve, the entropy or dissonance
refinement, audio capture, and any API or storage layer. See `CLAUDE.md` for why the scope
is held here.

## Usage

```python
from atunedpiano.inharmonicity import estimate_key

estimate = estimate_key(signal, sample_rate, "A4")
estimate.B                    # 9.117e-04
estimate.f0                   # ideal fundamental, Hz
estimate.first_partial        # f0 * sqrt(1 + B) -- the pitch you hear
estimate.residual_cents_rms   # how well the model fits; read this, not just B
```

Command line:

```
python scripts/analyze_recording.py recording.wav --note A4   # fit a real note
python scripts/validate_synthetic.py                          # keyboard-wide sweep
```

## Development

```
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/pytest -q
```

The DSP core depends on numpy and scipy only. Read `CLAUDE.md` before changing anything in
`src/atunedpiano/` — it carries the licensing and architectural constraints — and
`docs/research.md` for the literature the implementation is drawn from.

## Documentation

- [`docs/research.md`](docs/research.md) — technical review of the field since
  Hinrichsen (2012); the authoritative context for every design decision here
- [`docs/validation.md`](docs/validation.md) — how accuracy is established, and measured
- [`docs/recording-protocol.md`](docs/recording-protocol.md) — capturing a real note worth
  trusting

## Licensing

Implemented from the published papers. No code is derived from the Entropy Piano Tuner,
which is GPLv3; see constraint 1 in `CLAUDE.md`.
