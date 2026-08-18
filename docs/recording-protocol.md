# Recording protocol for the sanity anchor

The point of this file is one recording, kept indefinitely, of a note you have tuned by
ear on a real piano. Synthetic tests establish that the estimator recovers a B that was put
there by a formula. They cannot tell you whether the answer is right about a real string,
because a real string has false beats, double decay, phantom partials, a soundboard, and
neighbours. The anchor is the check on that, and it only works if the recording stays
constant, so the protocol is worth following once, carefully.

Store the audio in `data/reference/` and log what you did in `data/reference/NOTES.md`.
The audio itself is gitignored — it is large and specific to one piano — but the notes file
is committed, so the numbers stay comparable across machines.

## What to record

**One note, one string.** Mute the other strings of the unison with a rubber wedge or felt
strip. Two- and three-string unisons beat against each other and show double decay, which
corrupts both partial amplitudes and the frequency estimate. Using the una corda pedal is a
rougher substitute on a grand — it shifts the hammer rather than silencing the strings, so
it helps but does not isolate.

You do **not** need to mute the rest of the piano. Jaatinen & Pätynen (2022) measured this
directly on a Steinway D and found the covibrating strings of other keys had no meaningful
effect on the measured inharmonicity of a single string (`docs/research.md` §6). Damper up,
other keys undamped, is fine. Elaborate muting buys nothing for B.

**Pick a note in the midrange first.** A4 or C4. The bass is where B is hardest to pin
(few clean high partials) and the extreme treble is limited by how many partials fall below
Nyquist. Establish the anchor somewhere the estimator is on solid ground, then add a bass
and a treble note as separate files once the midrange one agrees with your ear.

**Mezzo-forte, not fortissimo.** Loud blows excite more partials but push the string into
nonlinear behaviour and risk clipping the input. A clean mf note is worth more than a loud
distorted one.

## Capture settings

| Setting | Value | Why |
|---|---|---|
| Sample rate | 48 kHz; **96 kHz above C6** | The top octave runs out of partials below Nyquist. C8 has four at 48 kHz, which is the bare minimum for a two-parameter fit. |
| Bit depth | 24-bit, or 32-bit float | Headroom, so you can record conservatively without losing the quiet upper partials. |
| Format | WAV, uncompressed | Lossy codecs discard the low-level high-frequency content B depends on. In practice the first reference recording survived AAC at 128 kbps with partials trackable to −60 dB, so this is a preference rather than an absolute — but the margin is unknown and a lower bitrate has no reason to be safe. Record lossless when the app lets you. |
| Level | peak around −12 dBFS | `analyze_recording.py` warns about clipping; do not analyse a file it warns about. |
| Length | 3–5 seconds | Longer than the analysis window with room to spare. The script uses a mid-decay segment, not the whole file. |
| Channels | mono, or a stereo pair that gets averaged | Either works; the script averages channels. |
| Processing | none | No noise reduction, no EQ, no normalisation, no compressor, and **no automatic gain control**. Every one of them moves partial amplitudes; noise reduction eats the quiet upper partials, and AGC pumps the envelope in a way the analysis has to work around. On a phone this usually means turning off "Voice Isolation" or "Enhance Recording". |

Lead-in silence is fine — the analysis detects the note onset and measures from there, so
you do not need to trim the file. Let it run a second before you play.

Mic roughly a metre from the strings, off to one side rather than directly over the hammer
line, in as quiet a room as you can manage. A phone or a cheap USB mic is genuinely fine:
this estimator reads B from the lower partials, so the >5 kHz roll-off that afflicts cheap
capsules does not bias the result. What matters far more is a quiet room and no processing.

Note the mic, the position, the room and the date in `NOTES.md`. If a future run disagrees
with the anchor, the first question is always whether something about the capture changed.

## Using the anchor

```
python scripts/analyze_recording.py data/reference/A4-single-string.wav --note A4
```

Record the resulting B, f0, partial-1 offset from nominal, and residual RMS in
`data/reference/NOTES.md`. After any change to the DSP, run it again and compare.

What to look at, in order:

1. **The residual column.** On a clean single string it should be small and unstructured. A
   systematic pattern — residuals growing with `n`, or alternating sign — means the
   stiff-string model is not describing this string, and the B value is a fitted number
   rather than a measurement. Above 3 cents RMS the fit is refused outright.
2. **The segment line.** The report says where it looked and how steady the envelope was
   there. A steadiness warning means no part of the note decayed smoothly — usually gain
   control, sometimes a heavy beat — and partial frequencies may be biased.
3. **Rejected partials.** One or two is ordinary. Several suggests unison beating, in which
   case the muting was not doing its job.
4. **B against the typical value** the script prints for that key. An order of magnitude out
   almost always means mis-indexed partials rather than an unusual piano.
5. **Partial 1 against your ear.** You tuned this note. If the script says it is 15 cents
   flat and you tuned it to a fork, something upstream is wrong — the sample rate metadata,
   the note argument, or the concert pitch (`--a4`).

A change in the anchor's B that the synthetic tests did not predict is the single most
valuable signal this project has. Do not explain it away.
