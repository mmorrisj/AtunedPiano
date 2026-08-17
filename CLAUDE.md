# AtunedPiano

A piano tuning tool: measure per-note inharmonicity (B) from recordings, fit a smooth
tuning curve, emit tuning targets in cents.

## Read this first

**`docs/research.md` is the authoritative context for this project.** It is a technical
review of the literature since Hinrichsen (2012) covering the paper citations, the
licensing constraint, the algorithm choices, and the known implementation gotchas. Read
it before designing anything in the DSP path. Do not re-derive its conclusions from
memory or from a web search — it is more specific than either.

## Hard constraints

These are not negotiable and do not expire. If a task appears to require breaking one,
stop and ask rather than working around it.

1. **Reimplement from the papers. Never port the Entropy Piano Tuner source.**
   EPT (gitlab.com/tp3/Entropy-Piano-Tuner and its mirrors) is **GPLv3**. Algorithms and
   math are not copyrightable, but a port or close translation of its C++ creates a
   derivative work and would relicense this project. Work from the primary sources:
   Hinrichsen arXiv:1203.5101 (CC-BY), Rigaud–David–Daudet 2013 (author PDF on HAL),
   Tuovinen et al. 2019 (open SMC PDF), Menrath 2021 (open KUG PDF), ENTROTUNER
   (IEEE Access, open access). Do not read EPT source while writing equivalent code.
   Also: do **not** reuse the TuneLab-copyright temperament file bundled in
   RobertBoganKang/piano_tuning. Verify the license of any repo before borrowing.

2. **The DSP core is numpy/scipy only.**
   `src/atunedpiano/` imports nothing beyond the standard library, numpy, and scipy.
   No librosa, no essentia, no torch, no tensorflow, no aubio. Application layers added
   later (API, storage, UI) may use other dependencies; the DSP must stay portable and
   auditable.

3. **No neural pitch estimation.**
   No CREPE, SPICE, Basic Pitch, or any learned f0/partial model. Their resolution
   (tens of cents) is coarser than tuning needs (sub-cent), and for isolated piano notes
   FFT peak-picking plus least-squares on the B-model is more accurate, faster, and
   interpretable. See `docs/research.md` §5 — even DDSP-piano falls back to classical
   signal-based extraction for exactly this sub-task. "AI tuning curve" vendor claims are
   marketing; treat them as such.

4. **Never quantize the optimization to 1 cent.**
   Decouple analysis resolution (sub-cent, via zero-padding and parabolic interpolation)
   from any optimization step size. Hinrichsen's 1-cent integer grid is a primary cause
   of the false plateaus and non-reproducible results the literature criticizes
   (`docs/research.md` §9).

5. **Do not use one FFT size for all 88 notes.**
   A0 is 27.5 Hz and C8 is 4186 Hz. Window length must scale with the note — long in the
   bass for partial separation, short in the treble to stay inside the decay. Analyze a
   steady mid-decay segment; skip the attack transient and the noisy tail.

## Ground truth

**Synthetic signals with known B are the only ground truth in this repo.** Every DSP
change must keep `tests/` green, and any new estimator must first be validated against
`atunedpiano.synth` before it is pointed at a real recording. The harness came first on
purpose — see `docs/validation.md`.

The synthetic tests can pass while the tuning still sounds wrong. Keep at least one real
recording of a note tuned by ear as a sanity anchor (`data/reference/`, protocol in
`docs/recording-protocol.md`) and check estimator output against it whenever the
estimator changes.

## Scope

**Current scope is Stage 1 only: per-note (B, f0) estimation for a single note,
validated on synthetic signals.**

Do not scaffold ahead of this. Specifically, do not add: audio capture, FastAPI
endpoints, Postgres/SQLAlchemy models, a worker queue, a UI, the keyboard-wide Rigaud
curve fit, the entropy or dissonance objective, or the treble 2:1 rule. Those are
Stages 1b–3 in `docs/research.md`; they get their own sessions, after the single-note
estimator is trusted. A large surface built at once hides the bugs that matter here.

## Layout

```
src/atunedpiano/
  notes.py           note names, MIDI, Hz, cents conversions
  synth.py           synthetic inharmonic tone generator (ground truth)
  spectrum.py        adaptive-window FFT, peak picking, parabolic interpolation
  inharmonicity.py   MAT-style partial tracking + least-squares (B, f0) fit
tests/               synthetic-recovery tests
scripts/             validation sweep, real-recording analysis
docs/research.md     literature review — the authoritative context
```

## Working commands

```
.venv/bin/pytest -q                              # test suite
.venv/bin/python scripts/validate_synthetic.py   # keyboard-wide recovery sweep
.venv/bin/python scripts/analyze_recording.py FILE.wav --note A4
```
