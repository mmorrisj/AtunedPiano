"""Note-name, MIDI, frequency and cents conversions.

Equal temperament with A4 = 440 Hz by default. The piano keyboard spans MIDI 21
(A0, 27.5 Hz) to MIDI 108 (C8, 4186.0 Hz).
"""

from __future__ import annotations

import math
import re

A4_HZ = 440.0
A4_MIDI = 69

LOWEST_MIDI = 21  # A0
HIGHEST_MIDI = 108  # C8

_SHARP_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_SEMITONE_OF_LETTER = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_ACCIDENTAL_OFFSET = {"": 0, "#": 1, "♯": 1, "b": -1, "♭": -1, "x": 2, "##": 2, "bb": -2}

_NOTE_RE = re.compile(r"^\s*([A-Ga-g])\s*([#♯b♭x]{0,2})\s*(-?\d+)\s*$")


def midi_to_hz(midi: float, a4_hz: float = A4_HZ) -> float:
    """Equal-tempered frequency of a MIDI note number (fractional values allowed)."""
    return a4_hz * 2.0 ** ((midi - A4_MIDI) / 12.0)


def hz_to_midi(hz: float, a4_hz: float = A4_HZ) -> float:
    """Fractional MIDI note number of a frequency."""
    if hz <= 0.0:
        raise ValueError(f"frequency must be positive, got {hz}")
    return A4_MIDI + 12.0 * math.log2(hz / a4_hz)


def note_to_midi(name: str) -> int:
    """Parse a scientific-pitch note name (``A0``, ``C#4``, ``Bb3``) to MIDI number."""
    match = _NOTE_RE.match(name)
    if match is None:
        raise ValueError(f"unparseable note name: {name!r}")
    letter, accidental, octave = match.groups()
    try:
        offset = _ACCIDENTAL_OFFSET[accidental]
    except KeyError:  # pragma: no cover - regex restricts the character set
        raise ValueError(f"unparseable accidental in {name!r}") from None
    return 12 * (int(octave) + 1) + _SEMITONE_OF_LETTER[letter.upper()] + offset


def midi_to_note(midi: int) -> str:
    """Render a MIDI note number as a sharp-spelled scientific pitch name."""
    return f"{_SHARP_NAMES[midi % 12]}{midi // 12 - 1}"


def note_to_hz(name: str, a4_hz: float = A4_HZ) -> float:
    """Equal-tempered frequency of a note name."""
    return midi_to_hz(note_to_midi(name), a4_hz=a4_hz)


def cents(hz: float, reference_hz: float) -> float:
    """Interval from ``reference_hz`` to ``hz`` in cents (positive = sharp)."""
    if hz <= 0.0 or reference_hz <= 0.0:
        raise ValueError("frequencies must be positive")
    return 1200.0 * math.log2(hz / reference_hz)


def shift_cents(hz: float, delta_cents: float) -> float:
    """Frequency ``hz`` transposed by ``delta_cents``."""
    return hz * 2.0 ** (delta_cents / 1200.0)


def keyboard_midi_numbers() -> list[int]:
    """MIDI numbers of the 88 keys, A0 through C8."""
    return list(range(LOWEST_MIDI, HIGHEST_MIDI + 1))
