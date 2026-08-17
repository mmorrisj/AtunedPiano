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

Canonical run is `--attack-skip 1.20 --duration 2.0` — past the unsteady stretch near the
onset. See the segment-position note below.

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
`select_segment` should search for a stretch where the envelope is smoothly decaying instead
of trusting a fixed offset.

**B survived a segment the residuals correctly rejected.** Across every window length
(0.25–3.0 s) and every start time up to 1.8 s, B stayed within 3.27–3.30e-4 — including the
bad 0.55 s segment where two partials were 9 cents out. The two errors were nearly
antisymmetric and cancelled in the fit. This is the residual diagnostic doing exactly its
job: B alone would have looked fine, and the residual column is what flagged the problem.

**One thing this file cannot settle.** The envelope *rises* about 10 dB between 0.65 and
0.85 s. A single decaying string does not do that. It is either a beat null recovering or
the phone's automatic gain control pumping, and one recording cannot separate the two.
Disable gain control / "Enhance Recording" on the next capture; if the dip persists, it is
acoustic.

**Do not analyse the tail.** Windows starting past about 2 s on this file return B values
between 0 and 2e-4 — the note has decayed far enough that too few upper partials survive and
the fit degenerates. The estimator does not currently refuse these; it returns a confident
wrong number.

## Interpreting a change

A shift in B on an unchanged file, after a change to the estimator, is a real signal. Before
accepting it, check in this order: did the partial count change, did the rejected list
change, did the residual RMS change. A B that moved while all three held steady means the
fit itself moved, which is worth understanding rather than absorbing.
