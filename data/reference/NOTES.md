# Reference recordings

Real notes kept as the sanity anchor described in `docs/recording-protocol.md`. The audio
files are gitignored — they are large and specific to one piano — but this log is committed
so the numbers stay comparable.

Add one row per recording, and re-run after any change to the DSP:

```
python scripts/analyze_recording.py data/reference/<file>.wav --note <key>
```

## Reproducing the anchor from a clean clone

The compressed source is committed; the decoded WAV is not (see `.gitignore`). Decode it
first — the analyser reads WAV only:

```
ffmpeg -i data/C4_2.m4a -c:a pcm_s24le data/C4_2.wav
python scripts/analyze_recording.py data/C4_2.wav --note C4
```

Without ffmpeg, any libavcodec-backed decoder gives the same samples; `pip install av` in a
throwaway environment and dump the frames, or use your platform's converter. Do not decode
through anything that resamples, normalises or dithers.

You should get, exactly:

```
note onset at 0.41 s; analysed 0.25 s from 0.86 s (searched for a steady stretch)
B          3.297353e-04  +/- 3.2e-06
f0         261.8955 Hz
partial 1  261.9387 Hz  (+2.07 cents from nominal)
residuals  0.9894 cents rms, 3.2866 max, over 17 partials
```

Small differences in the last decimal are a decoder difference and not interesting. A
different partial count, a different segment start, or a residual that moves by more than a
tenth of a cent means something real changed — work through "Interpreting a change" below.

## The C-note set (2026-08-18)

Eleven recordings, all phone / AAC 128 kbps / 48 kHz mono, decoded with the command above.
Unison wedged except where noted.

| File | Key | B | resid | n | partial 1 vs nominal | Notes |
|---|---|---|---|---|---|---|
| `C1.m4a` | C1 | 3.656e-4 | 2.19 c | 19 | +2.92 c | Residuals trend with `n`; see below. |
| `C1-2.m4a` | C1 | 3.712e-4 | 2.88 c | 20 | +1.83 c | |
| `C2-2.m4a` | C2 | 1.598e-4 | 1.72 c | 20 | +10.19 c | |
| `C2-2string.m4a` | C2 | 1.580e-4 | 0.79 c | 19 | +10.47 c | Two strings, deliberate. |
| `C3.m4a` | C3 | 1.714e-4 | 1.95 c | 20 | +3.61 c | |
| `C4.m4a` | C4 | 3.3043e-4 | 0.93 c | 16 | +1.99 c | |
| `C4_2.m4a` | C4 | 3.2974e-4 | 0.99 c | 17 | +2.07 c | The original anchor. |
| `C4-3.m4a` | C4 | 3.2963e-4 | 0.43 c | 13 | +2.53 c | |
| `C5.m4a` | C5 | 7.404e-4 | 0.65 c | 10 | +5.50 c | |
| `C6.m4a` | C6 | 1.939e-3 | 0.20 c | 4 | +9.33 c | Only 4 partials; segment-dependent to about 15%. Provisional. |
| `C7.m4a` | C7 | — | — | — | — | Refused, and it is the recording. See below. |

### Repeatability: 0.24% at C4, 1.5% in the bass

Three independent takes of C4 give **3.3043e-4, 3.2974e-4, 3.2963e-4** — a spread of
0.24%. These are not near-copies of one measurement: the segment search chose different
starts and fitted 16, 17 and 13 partials respectively, so three different stretches of
three different strikes agree to a part in 400.

Repeatability is not uniform across the keyboard. C4 gives 0.24%; the two C1 takes differ
by 1.5% and the two C2 takes by 1.2%. The bass is harder to pin, as the synthetic sweep
predicted for a quite different reason — there B is small, so its whole signature spans only
a couple of cents.

This is the number that was missing. The per-fit standard error (±3.2e-6, about 0.1%)
turns out to be an honest estimate of real take-to-take reproducibility rather than an
optimistic one. **Practical consequence: in the midrange a difference above about 0.5% between two notes is
a property of the piano; in the bass the threshold is nearer 3%.** Everything below is read
against that.

### The B curve, including a bass minimum

| | B | ratio to previous octave |
|---|---|---|
| C1 | 3.656e-4 | |
| C2 | 1.598e-4 | ×0.44 |
| C3 | 1.714e-4 | ×1.07 |
| C4 | 3.299e-4 | ×1.93 |
| C5 | 7.404e-4 | ×2.24 |
| C6 | 1.939e-3 | ×2.62 |

Three features, and none of them is a smooth curve.

**B falls from C1 to C2 before it rises.** The lowest strings are short and heavily
overwound, which costs stiffness; a little further up the bass the strings get longer
faster than they get thicker, and B reaches a minimum. This is the expected shape, and the
factor of 2.3 is far outside the 1.5% bass repeatability, so it is real rather than noise.

**C2 to C3 is flat.** Seven percent, against a bass repeatability of about 1.5%: real, but
negligible next to what happens above it. Wound strings buy mass without stiffness, so B
barely moves across them.

**From C3 upward B roughly doubles per octave and the ratio keeps climbing.** That is the
plain steel section, where stiffness rises with every semitone.

The wound-to-plain break therefore sits between C3 and C4 on this piano. **A single smooth
B-vs-key curve fitted across that boundary will not work**, and it has a minimum below it as
well, so a monotonic model will not work either. The semitone where the winding stops is the
most valuable note still unrecorded — more valuable than another octave.

### What the muting comparison can and cannot show

The C2 pair was meant as a controlled experiment: same note, one string wedged versus two.

| | B | residual | rejected partials |
|---|---|---|---|
| One string | 1.5983e-4 | 1.72 c | 0 |
| Two strings | 1.5800e-4 | 0.79 c | 1 |

**They differ by 1.15%, which this data cannot distinguish from take-to-take variation.**
The two C1 takes — same string, same conditions, nothing deliberately changed — differ by
1.5%. So the muting difference is smaller than the noise it would have to beat.

An earlier version of this file reported the same comparison as a 6.1% effect and treated it
as decisive. That was wrong, and instructively so: at the time the two-string recording was
being fitted on a poorly chosen segment, so the 6% was mostly segment choice, not strings.
Once segment selection improved, the difference collapsed to 1.15%. **The number moved
because the estimator changed, which is exactly the situation "Interpreting a change" below
is for.** Settling this needs several takes of each condition, not one of each.

## Take 2 (2026-08-18) — cross-session agreement

A second full pass, C1 through C7, same phone and format, recorded louder (C6 peaks at 0.79
against 0.33 first time). Committed under `data/take2/`.

| Key | take 1 | take 2 | difference |
|---|---|---|---|
| C1 | 3.684e-4 | 3.683e-4 | −0.02% |
| C2 | 1.589e-4 | 1.611e-4 | +1.34% |
| C3 | 1.714e-4 | 1.748e-4 | +1.97% |
| C4 | 3.299e-4 | 3.198e-4 | **−3.08%** |
| C5 | 7.404e-4 | 7.278e-4 | −1.70% |
| C6 | 1.939e-3 | 2.318e-3 | +19.6% |
| C7 | refused | refused | — |

**Cross-session agreement is worse than within-session, and C4 is the warning.** Three takes
in one sitting agreed to 0.24%; the same note across two sittings differs by 3.08%, thirteen
times worse. B is a physical property of a steel wire — it does not drift in a few hours —
so the difference is measurement, not piano.

Scanning every segment of each recording shows where it comes from. The interquartile spread
of B across segments within one file is 0.8% and 1.0% for the first two take-1 C4 files, 7.2%
for the third, and **13.9%** for the take-2 file. The take-2 C4 recording is simply less
internally consistent, and its disagreement with take 1 is about the size of its own internal
scatter. The 0.24% from three consecutive takes was optimistic: takes recorded back to back
share whatever the session's mic placement, strike and wedge seating happened to be.

**Working figure: about 2% between sessions in the midrange and bass, and C6 is not
measurable to better than 20%.** Treat 0.24% as the floor of the method on a good recording,
not as the accuracy of any single number here.

The C1 agreement at −0.02% is luck at this sample size, not evidence that the bass is the
best-determined band; its two within-session takes differ by 1.5%.

### What take 2 did not change

C7 still refuses on both takes, despite the louder capture. Its partials above the third are
simply not in the file. Louder helped every other note and did not help this one, which
points at the capture chain rather than the strike: phone capsule roll-off above 5 kHz and
128 kbps AAC, exactly where C7's evidence lives.

## Recordings

| File | Key | Piano | Mic / room | Sample rate | Date | Notes |
|---|---|---|---|---|---|---|
| `C4_2.m4a` | C4 | — | phone | 48 kHz mono | 2026-08-17 | Recorded as AAC 128 kbps m4a, decoded to WAV. Unison muted with a rubber wedge. Note onset at 0.40 s; peak 0.995 (one sample at full scale, effectively unclipped). Envelope shows a 10 dB dip and recovery between 0.60 and 0.85 s — see below. |

## Measurements

Canonical run needs no arguments now: `analyze_recording.py <file> --note C4` detects the
onset and searches for a steady segment on its own. The values below are from the original
manual reading (`--start 1.20 --duration 2.0`); the automatic choice lands at 0.86 s and
gives B = 3.297e-4 with 0.99 cents RMS over 17 partials.

| Date | File | B | f0 (Hz) | partial 1 vs nominal | residual RMS | partials | Comment |
|---|---|---|---|---|---|---|---|
| 2026-08-17 | `C4_2.m4a` | 3.29e-4 ± 2e-6 | 261.90 | +1.5 cents (measured) | 0.32–0.53 c | 13–16 | Stable across window lengths 0.25–3.0 s and start times 0.55–1.8 s. Residuals unstructured; no growth with n. |

## What this recording established

**The stiff-string model fits a real string well.** Residuals are a third to a half of a
cent RMS over 13–16 partials with no systematic pattern — not growing with `n`, not alternating sign. B lands at
0.82x the typical value for C4, which is an ordinary piano-to-piano difference. This is the
result the anchor existed to check, and it passed.

**A lossy phone recording was good enough.** AAC at 128 kbps, 48 kHz mono, decoded to WAV.
Partials remained trackable down to −60 dB below the loudest. This does not license lossy
capture in general — a lower bitrate, or a phone applying noise suppression, would not have
survived — but the codec was not the limiting factor here.

**The muting worked — the extra spectral energy is not a second string.** Peaks near the
partials sit at inconsistent cents offsets from partial to partial (−12.9c at n=1, +6.3c at
n=2, +66.7c at n=3, −3.8c at n=4). A unison partner is a whole harmonic series offset by a
*constant* number of cents, so this is not one. Partial 1 does carry symmetric ±4.2 cent
sidebands at −28 dB, which is amplitude modulation at about 0.6 Hz rather than a second
string.

**Segment position matters more than window length.** The default segment lands a fixed
distance after the start of the file, with no notion of whether the envelope is steady
there. On this recording that put it across the 0.60–0.85 s dip-and-recovery, and rapid
amplitude change within a short window biases interpolated peak frequencies badly:

| 0.25 s window starting at | partial 1 residual | partial 2 residual | RMS |
|---|---|---|---|
| 0.55 s | +9.06 c | −9.16 c | 2.95 c |
| 0.70 s | −2.81 c | +2.55 c | 1.01 c |
| 1.00 s | −0.58 c | −0.33 c | 0.53 c |
| 1.20 s | −0.13 c | −0.15 c | 0.32 c |
| 1.80 s | −0.58 c | −0.14 c | 0.26 c |

The same 0.25 s window is fine from 1.0 s onward. Window *length* was never the issue — an
earlier reading of this file blamed length, and the position sweep above disproves it.

**Fixed.** `select_segment` now detects the note onset (this file has 0.41 s of lead-in, so
the old fixed offset was measured from the wrong place to begin with) and then searches for
a window whose log envelope is close to a straight line. On this recording it settles on
0.86 s. A fit whose partials disagree with the model by more than 3 cents RMS is now refused
outright rather than returned as a number.

**B survived a segment the residuals correctly rejected.** Across every window length
(0.25–3.0 s) and every start time up to 1.8 s, B stayed within 3.27–3.30e-4 — including the
bad 0.55 s segment where two partials were 9 cents out. The two errors were nearly
antisymmetric and cancelled in the fit. This is the residual diagnostic doing exactly its
job: B alone would have looked fine, and the residual column is what flagged the problem.

**The 10 dB dip is acoustic, not the phone — settled.** The envelope falls and recovers
about 10 dB between 0.65 and 0.85 s, which a single decaying string does not do. Gain
control and a beat null were both candidates; per-partial band envelopes separate them,
because AGC moves every partial in lockstep and beating does not:

| dB re. that partial at 0.45 s | n=1 | n=2 | n=3 | n=4 | n=5 | n=6 |
|---|---|---|---|---|---|---|
| 0.65 s | −13.1 | −25.5 | −12.8 | −5.3 | −5.6 | −4.7 |
| 0.90 s | −6.3 | −9.6 | −19.4 | −9.0 | −8.6 | −9.5 |

Partials 1 and 2 dip and then recover by 13–16 dB. Partials 4, 5 and 6 decay smoothly
straight through with no dip at all. Not gain control.

The mechanism shows in the sidebands: partial 1 carries symmetric ±4.2 cent sidebands at
−28 dB, which at 261.9 Hz is ±0.64 Hz — amplitude modulation at 0.64 Hz, period ~1.6 s,
giving exactly one null inside this window. Low partials only, with the unison wedged, is
the false-beat signature: twin partials from slight string asymmetry, which `research.md`
§9 lists and which affects low partials most. An imperfectly seated wedge letting a unison
partner ring through would look much the same.

Either way it is a property of the string, not of the capture, so it will recur on every
note and cannot be recorded away. This is what the steady-segment search exists to step
around — the design predates knowing the cause, and the cause vindicates it.

**The upload path did not alter the audio.** The m4a as committed to the repo is
byte-identical to the copy that arrived by upload (md5 8ae25ba1b3ab78b8772fa73f48c8d77d,
107494 bytes both). The AAC 128 kbps encoding came from the phone's recorder, not from
anything in between.

**Do not analyse the tail.** Windows starting past about 2 s on this recording return B values
between 0 and 2e-4 — the note has decayed far enough that the tracker follows noise peaks
rather than partials. These fits used to be returned as confident numbers; they are now
refused, on residuals of 5.5 cents and above against 0.2–0.5 for a live segment.

## The failures, and what fixing them taught

Of the three failures in the first pass, two are fixed and one is the recording. The route
to fixing them corrected a diagnosis, which is worth recording as carefully as the fix.

**C6 and C7 — several strikes per file.** Both hold three or four separate strikes. Onset
detection fired on the first event over threshold, which in C7 was a quiet strike at 3.5 s
when the loudest is at 7.5 s. Fixed: every strike is now found and fitted, and the best is
kept — most partials among those passing the residual guard, residual breaking ties. Most
partials rather than lowest residual, because fitting gets *easier* as a note dies and
fewer partials survive, so ranking on residual alone drifts toward the least informative
strike.

**C6 also needed the segment choice to escalate.** No window anywhere in that note is
steady by the usual standard, so the steadiness search fell back to the least-unsteady
candidate — a proxy with nothing behind it once its own precondition has failed — and
landed on an unfittable segment. Now, when the cheap choice fails, the alternatives are
fitted and judged by their results. C6 fits at 0.20 cents over 4 partials, though B still
varies by about 15% depending on the segment, so treat it as provisional.

**C1 — the diagnosis was wrong.** The first pass blamed the weak fundamental: partial 1
arrives 54 dB below the loudest partial, the tracker starts at n=1 and locks onto noise. A
fix was proposed on that basis. Testing the claim first showed it to be false — a synthetic
note with its fundamental buried 52 dB down is tracked correctly every time, and one with
its first two partials removed entirely is too. C1 was simply a bad segment, and the strike
and segment work above fixed it without touching the tracker.

What the test *did* find was narrower and real: with the first **three** partials absent the
walk died before it started, because the consecutive-miss counter was ending it during the
lead-in. The counter exists to stop the walk running off the top of the series, not to stop
it beginning. It now only applies once a partial has been found, and a note is measurable
with its first five partials missing.

The same test run also exposed a latent mis-indexing risk nobody had reported: the
pre-model search window was capped at a flat 340 cents, which is safe at n=1 where the
neighbouring partial is 1200 cents away but not at n=3 where it is 498. The cap is now
n-dependent.

C1 now fits at 3.66e-4 and 3.71e-4 across two takes. The residuals, though, trend
monotonically with `n` — about −3 cents at partial 3 rising to +3 at partial 11 — which is
structure, not scatter. The two-parameter stiff-string model does not fully describe a
heavily wound bass string. The fit is usable; it is not as trustworthy as C4's.

**C7 is the recording, not the estimator.** Even at its loudest strike it yields one to
three partials: partial 3 sits 60 dB below partial 1. At 2093 Hz there are few strong
partials to begin with, the phone capsule rolls off above 5 kHz, and 128 kbps AAC is least
generous exactly where the content is quietest and highest. The top octave needs a closer
mic, a firmer strike, lossless capture and 96 kHz.

## A low residual is not proof the fit is right

Scanning every segment of the C4 recordings turned up something worth keeping. A segment
inside the attack transient found four peaks — 248.57, 515.50, 824.46 and 1183.05 Hz, none
of them partials of C4, whose first four sit at 262, 524, 787 and 1050 — fitted them with
B = 2.88e-2, eighty-seven times too high, and produced a residual of 2.66 cents. Under the
flat 3-cent guard that was a pass, complete with a 2% standard error on B.

Two parameters fitted to four partials leave two degrees of freedom, and almost any four
peaks can be fitted by *some* stiff-string curve. The guard is now scaled by the evidence
behind the fit: the full 3 cents at eight partials or more, a third of that at four. Fewer
partials must fit better, not merely as well.

This does not affect any result in the tables above — the automatic segment choice never
picks that segment, and it was only reached by forcing `--start`. It matters because it is
a worked example of the failure this whole project is built to catch: a converged fit, a
plausible-looking number, a tight error bar, and nothing behind any of it. The residual
column is the check, and now the standard it is held to depends on how much there is to
check.

## Interpreting a change

A shift in B on an unchanged file, after a change to the estimator, is a real signal. Before
accepting it, check in this order: did the partial count change, did the rejected list
change, did the residual RMS change. A B that moved while all three held steady means the
fit itself moved, which is worth understanding rather than absorbing.
