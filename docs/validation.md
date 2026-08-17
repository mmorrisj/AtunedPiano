# Validation strategy

## Why the harness came first

The synthetic-signal harness (`src/atunedpiano/synth.py`) is the first commit in this
repository, before any estimator, any audio I/O, and any application layer. That ordering
is deliberate.

Inharmonicity estimation has a failure mode that is easy to miss: an estimator can run
without error, return a plausible B, and produce a smooth, professional-looking tuning
curve while being quietly wrong. Nothing about the output announces the mistake. The only
way to catch it is to feed the estimator a signal whose B you already know exactly and
check the number that comes back.

Building the generator first means every later change is checkable from the moment it is
written. Building the capture path or the API first would have produced a lot of working
plumbing and no way to tell whether the math underneath it was right.

This mirrors how the literature validates: Rauhala (PFD) and Rigaud (NMF) both establish
estimator accuracy on synthetic signals with known B before touching recordings. See
`docs/research.md` §10.

## The three levels

**1. Synthetic, known B — the ground truth.**
`atunedpiano.synth` generates a stiff-string tone, `f_n = n·f0·√(1 + B·n²)`, with
controllable partial count, amplitude roll-off and jitter, per-partial decay, and additive
noise at a specified SNR. Everything is seeded, so failures reproduce exactly.

`tests/test_synth.py` verifies the harness itself: that the signal really contains energy
at the frequencies the model predicts, using a direct single-bin DFT rather than anything
from the project's own spectrum code. The harness is not allowed to depend on the code it
validates.

`tests/test_inharmonicity.py` is the actual estimator gate. It sweeps the keyboard —
bass through extreme treble — at realistic B values, with noise and with irregular partial
amplitudes, and asserts recovery within a stated tolerance. Any change to the DSP must
keep it green.

`scripts/validate_synthetic.py` runs the same sweep as a report rather than an assertion,
which is the right tool when you want to see *how* accuracy degrades rather than whether
it crossed a line.

**2. Reference datasets — not yet in scope.**
RWC (3 grands), MAPS (upright + grand), Iowa MIS, and the Kawai K18 sample library used by
Szwajcowski. Rigaud's supplementary material publishes per-note (B, f0) for five pianos and
is the closest thing to a benchmark the field has. This is Stage 1b work.

**3. A real recording tuned by ear — the sanity anchor.**
Synthetic tests can all pass and the result can still not *sound* right. A real note,
tuned by ear on a real piano, recorded with the protocol in
`docs/recording-protocol.md`, is the check on that. Keep at least one in `data/reference/`
and run `scripts/analyze_recording.py` against it whenever the estimator changes. A jump in
the fitted B or in the residuals on that file is a signal even when the test suite is
silent.

## Tolerances and what they mean

Estimator accuracy is asserted on two quantities:

- **B, relative error.** Tolerance is looser than for f0 because B is what the tuning curve
  is built from, and its effect is a smooth function across the keyboard — a few percent of
  B moves the curve by a fraction of a cent in the midrange. It matters much more in the
  treble, where B is large, which is why the treble tolerance is the tighter constraint in
  practice.
- **f0, absolute error in cents.** Sub-cent, because this is the quantity a tuner acts on
  directly. Note that cents, not Hz, is the metric throughout; a fixed Hz tolerance would be
  meaninglessly tight in the bass and meaninglessly loose in the treble.

The residual RMS in cents reported by the estimator is the in-band health check: on a clean
synthetic signal it should sit far below the tolerance, and on a real recording it is the
first thing to look at when a fit seems wrong. A low residual with a wrong B usually means
partials were mis-indexed — the model fits a consistent but wrong trajectory.

## What does not count as validation

- **The Railsback curve.** A tuning that produces a plausible Railsback shape is not
  thereby correct. Many audibly different tunings share similar smooth curves, and the
  averaged curve hides exactly the per-note detail that matters. Use it as a smell test,
  never as proof (`docs/research.md` §10).
- **"The plot looks right."** See above; this is the failure mode the harness exists to
  catch.
- **Agreement with another tuning program.** It inherits that program's choices and its
  bugs, and in the case of EPT it would also mean reading GPLv3 source, which this project
  does not do (CLAUDE.md, constraint 1).

Blind listening tests (ITU-R BS.1116 or MUSHRA via webMUSHRA) are the real validator for a
finished tuning, but they validate the curve, not the estimator, and they belong to Stage 3.
