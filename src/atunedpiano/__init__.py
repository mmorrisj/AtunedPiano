"""AtunedPiano: inharmonicity measurement and piano tuning curves.

Stage 1 scope: per-note (B, f0) estimation from a single recorded note, validated
against synthetic signals with known B. See CLAUDE.md and docs/research.md.
"""

from .notes import cents, hz_to_midi, midi_to_hz, midi_to_note, note_to_hz, note_to_midi
from .synth import SyntheticNote, partial_frequencies, synth_key, synth_note, typical_B

__all__ = [
    "SyntheticNote",
    "cents",
    "hz_to_midi",
    "midi_to_hz",
    "midi_to_note",
    "note_to_hz",
    "note_to_midi",
    "partial_frequencies",
    "synth_key",
    "synth_note",
    "typical_B",
]
