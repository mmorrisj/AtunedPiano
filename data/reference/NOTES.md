# Reference recordings

Real notes, tuned by ear, kept as the sanity anchor described in
`docs/recording-protocol.md`. The audio files are gitignored — they are large and specific
to one piano — but this log is committed so the numbers stay comparable.

Add one row per recording, and re-run after any change to the DSP:

```
python scripts/analyze_recording.py data/reference/<file>.wav --note <key>
```

## Recordings

| File | Key | Piano | Mic / room | Sample rate | Date | Notes |
|---|---|---|---|---|---|---|
| _(none yet)_ | | | | | | |

## Measurements

| Date | File | B | f0 (Hz) | partial 1 vs nominal | residual RMS | partials | Comment |
|---|---|---|---|---|---|---|---|
| _(none yet)_ | | | | | | | |

## Interpreting a change

A shift in B on an unchanged file, after a change to the estimator, is a real signal. Before
accepting it, check in this order: did the partial count change, did the rejected list
change, did the residual RMS change. A B that moved while all three held steady means the
fit itself moved, which is worth understanding rather than absorbing.
