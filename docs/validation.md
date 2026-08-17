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

## Measured recovery

`scripts/validate_synthetic.py`, all 88 keys, 3 seeds each, 3 s notes at 48 kHz. B error is
relative; f0 error is absolute in cents. "Jitter" is the standard deviation of random
per-partial gain, which stops the estimator leaning on a tidy amplitude roll-off.

| Condition | Band | B err median | B err p95 | f0 err p95 |
|---|---|---|---|---|
| clean | bass A0–B2 | 0.000% | 0.001% | 0.0001c |
| | mid C3–B5 | 0.000% | 0.000% | 0.0001c |
| | treble C6–C8 | 0.000% | 0.000% | 0.0000c |
| 30 dB SNR, 6 dB jitter | bass A0–B2 | 0.020% | 0.084% | 0.0108c |
| | mid C3–B5 | 0.007% | 0.048% | 0.0088c |
| | treble C6–C8 | 0.000% | 0.001% | 0.0019c |
| 20 dB SNR, 6 dB jitter | bass A0–B2 | 0.064% | 0.274% | 0.0340c |
| | mid C3–B5 | 0.019% | 0.140% | 0.0261c |
| | treble C6–C8 | 0.001% | 0.004% | 0.0041c |
| 12 dB SNR, 6 dB jitter | bass A0–B2 | 0.144% | 0.628% | 0.0834c |
| | mid C3–B5 | 0.041% | 0.415% | 0.0588c |
| | treble C6–C8 | 0.002% | 0.011% | 0.0100c |

The estimator also finds a piano detuned by ±90 cents from nominal without loss of
accuracy, which is what a pitch-raise candidate looks like.

Three things in this table are worth reading rather than skimming:

**The bass is the weak band, not the treble.** This is the opposite of what the raw B
values suggest, and it is the expected result. Bass B is small — around 1e-4 — so the whole
inharmonic signature across the available partials amounts to a couple of cents, and noise
of a few tenths of a cent per peak eats a real fraction of it. The treble has the opposite
problem in a form that does not show up as error: enormous B, unmistakable in the spectrum,
but very few partials below Nyquist to fit it with.

**Accuracy collapses below about 12 dB SNR, in the bass specifically.** Individual bass
notes at 6 dB SNR have been seen 33% out on B while reporting a standard error of 6% — the
uncertainty estimate is not reliable that far down, because with five surviving partials the
residual-based variance is itself barely determined. Do not trust a bass fit from a noisy
recording, and do not trust its error bar either. The fix is a better recording, not a better
optimizer.

**Extreme treble is limited by Nyquist, not by the estimator.** C8 with treble-scale B has
four partials below 24 kHz, which is the bare minimum for a two-parameter fit. Recording the
top octave at 96 kHz is the reason `docs/recording-protocol.md` asks for it.

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
