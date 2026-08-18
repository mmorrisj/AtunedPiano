# Reference recordings

Real notes kept as the sanity anchor described in `docs/recording-protocol.md`. The audio
files are gitignored — they are large and specific to one piano — but this log is committed
so the numbers stay comparable.

Add one row per recording, and re-run after any change to the DSP:

```
python scripts/analyze_recording.py data/reference/<file>.wav --note <key>
```

## Recordings

| File | Key | Piano | Mic / room | Sample rate | Date | Notes |
|---|---|---|---|---|---|---|
| `C4-phone.wav` | C4 | — | phone | 48 kHz mono | 2026-08-17 | Recorded as AAC 128 kbps m4a, decoded to WAV. Unison muted with a rubber wedge. Note onset at 0.40 s; peak 0.995 (one sample at full scale, effectively unclipped). Envelope shows a 10 dB dip and recovery between 0.60 and 0.85 s — see below. |

## Measurements

Canonical run needs no arguments now: `analyze_recording.py <file> --note C4` detects the
onset and searches for a steady segment on its own. The values below are from the original
manual reading (`--start 1.20 --duration 2.0`); the automatic choice lands at 0.86 s and
gives B = 3.297e-4 with 0.99 cents RMS over 17 partials.

| Date | File | B | f0 (Hz) | partial 1 vs nominal | residual RMS | partials | Comment |
|---|---|---|---|---|---|---|---|
| 2026-08-17 | `C4-phone.wav` | 3.29e-4 ± 2e-6 | 261.90 | +1.5 cents (measured) | 0.32–0.53 c | 13–16 | Stable across window lengths 0.25–3.0 s and start times 0.55–1.8 s. Residuals unstructured; no growth with n. |

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

**Do not analyse the tail.** Windows starting past about 2 s on this file return B values
between 0 and 2e-4 — the note has decayed far enough that the tracker follows noise peaks
rather than partials. These fits used to be returned as confident numbers; they are now
refused, on residuals of 5.5 cents and above against 0.2–0.5 for a live segment.

## Interpreting a change

A shift in B on an unchanged file, after a change to the estimator, is a real signal. Before
accepting it, check in this order: did the partial count change, did the rejected list
change, did the residual RMS change. A B that moved while all three held steady means the
fit itself moved, which is worth understanding rather than absorbing.
