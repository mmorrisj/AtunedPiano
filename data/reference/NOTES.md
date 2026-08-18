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
| `C1.m4a`, `C1-2.m4a` | C1 | — | — | — | — | Both refused. See below. |
| `C2-2.m4a` | C2 | 1.598e-4 | 1.72 c | 20 | +10.19 c | |
| `C2-2string.m4a` | C2 | 1.501e-4 | 3.24 c | 19 | +10.65 c | Two strings, deliberate. Refused by the guard. |
| `C3.m4a` | C3 | 1.714e-4 | 1.95 c | 20 | +3.61 c | |
| `C4.m4a` | C4 | 3.3019e-4 | 0.99 c | 16 | +2.02 c | |
| `C4_2.m4a` | C4 | 3.2974e-4 | 0.99 c | 17 | +2.07 c | The original anchor. |
| `C4-3.m4a` | C4 | 3.3021e-4 | 0.41 c | 13 | +2.48 c | |
| `C5.m4a` | C5 | 7.404e-4 | 0.65 c | 10 | +5.50 c | |
| `C6.m4a` | C6 | 2.207e-3 | 0.79 c | 4 | +7.18 c | Needs `--start 3.5`; only 4 partials, treat as provisional. |
| `C7.m4a` | C7 | — | — | — | — | Refused. See below. |

### Repeatability: 0.15%

Three independent takes of C4 give **3.3019e-4, 3.2974e-4, 3.3021e-4** — a spread of
0.145%, standard deviation 0.081%. These are not near-copies of one measurement: the
segment search chose starts of 1.15, 0.86 and 4.15 s and fitted 16, 17 and 13 partials
respectively, so three different stretches of three different strikes agree to a part in
700.

This is the number that was missing. The per-fit standard error (±3.2e-6, about 0.1%)
turns out to be an honest estimate of real take-to-take reproducibility rather than an
optimistic one. **Practical consequence: a difference of more than about 0.3% between two
notes is a property of the piano, not of the measurement.** Everything below is read
against that threshold.

### The bass/treble break is visible

| | B | ratio to previous octave |
|---|---|---|
| C2 | 1.598e-4 | |
| C3 | 1.714e-4 | ×1.07 |
| C4 | 3.300e-4 | ×1.93 |
| C5 | 7.404e-4 | ×2.24 |
| C6 | 2.207e-3 | ×2.98 |

C2 to C3 is essentially flat — 7%, against a measurement floor of 0.3%, so real but small.
From C3 upward B roughly doubles per octave and the ratio keeps climbing. That is the
wound-bass to plain-wire transition: wound strings buy mass without stiffness, so B stays
low and flat across them, and once the plain steel section starts, stiffness climbs with
every semitone.

The break therefore sits between C3 and C4 on this piano. **A single smooth B-vs-key curve
fitted across that boundary will not work**, and the notes either side of it are the most
valuable ones still unrecorded — the exact semitone where the winding stops matters more
than another octave sample.

### Muting the unison costs 6% of B

The C2 pair is a controlled experiment: same note, same session, one string wedged versus
two.

| | B | residual | rejected partials |
|---|---|---|---|
| One string | 1.5983e-4 | 1.72 c | 0 |
| Two strings | 1.5008e-4 | 3.24 c | 1 |

B differs by 6.1% — forty times the 0.15% repeatability, so unambiguously real — and the
residual nearly doubles, pushing the two-string fit past the 3-cent guard where it is
refused outright. The protocol asserted that muting matters; this measures the cost of not
doing it.

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

## What the set could not measure, and why

Three failures, all correctly refused rather than reported as numbers. Two are estimator
gaps and one is the recording.

**C1, both takes — the fundamental is not there.** In the lowest octave the soundboard
barely radiates 32.7 Hz, so partial 1 arrives 54 dB below the loudest partial, which is
partial 9. The tracker starts at n=1 and takes what it finds within ±100 cents; with
nothing real there it locks onto noise, and every subsequent index inherits the error.
The result was B = 8.9e-3, about forty-five times too high, with residuals of ±20 cents.

The guard caught it, which is the system working. But the fix is clear: in the bass the
trajectory should be bootstrapped from the strongest partial and walked outward, not
started at n=1 on the assumption that the fundamental is present and findable.

**C6 and C7 — several strikes per file, and the analysis took the wrong one.** Both files
contain three or four separate strikes. Onset detection fires on the first block that rises
within 20 dB of the file's peak, which in C7 was a quiet strike at 3.5 s; the loudest is at
7.5 s. C6 analysed at its real strike (`--start 3.5`) gives a clean 0.79-cent fit.

The estimator assumes one note per file. Real recordings contain several attempts, which is
how anyone actually records: play it a few times, keep the file. Onset detection should find
*all* the strikes and analyse the best, using the residual as the criterion — the same
signal that is already trusted to refuse a bad fit.

**C7 is also the recording.** Even at its loudest strike, C7 yields one to three partials:
partial 3 sits 60 dB below partial 1. At 2093 Hz there are few strong partials to begin
with, the phone capsule rolls off above 5 kHz, and 128 kbps AAC is least generous exactly
where the content is quietest and highest. This is the case the protocol's lossless
recommendation was written for. The top octave needs a closer mic, a firmer strike, lossless
capture and 96 kHz — and even then it will be the hardest band on the keyboard.

## Interpreting a change

A shift in B on an unchanged file, after a change to the estimator, is a real signal. Before
accepting it, check in this order: did the partial count change, did the rejected list
change, did the residual RMS change. A B that moved while all three held steady means the
fit itself moved, which is worth understanding rather than absorbing.
