"""Conversions between note names, MIDI numbers, frequencies and cents."""

from __future__ import annotations

import pytest

from atunedpiano import notes


class TestNoteNames:
    @pytest.mark.parametrize(
        "name,midi",
        [("A0", 21), ("C1", 24), ("C4", 60), ("A4", 69), ("C8", 108), ("A#3", 58)],
    )
    def test_parses_scientific_pitch(self, name, midi):
        assert notes.note_to_midi(name) == midi

    @pytest.mark.parametrize("sharp,flat", [("A#3", "Bb3"), ("C#4", "Db4"), ("F#2", "Gb2")])
    def test_enharmonics_agree(self, sharp, flat):
        assert notes.note_to_midi(sharp) == notes.note_to_midi(flat)

    def test_renders_back_with_sharp_spelling(self):
        for midi in notes.keyboard_midi_numbers():
            assert notes.note_to_midi(notes.midi_to_note(midi)) == midi

    @pytest.mark.parametrize("bad", ["H4", "A", "4A", "", "A#-"])
    def test_rejects_unparseable_names(self, bad):
        with pytest.raises(ValueError):
            notes.note_to_midi(bad)


class TestFrequencies:
    @pytest.mark.parametrize(
        "name,hz", [("A4", 440.0), ("A0", 27.5), ("A5", 880.0), ("C8", 4186.009)]
    )
    def test_equal_tempered_frequencies(self, name, hz):
        assert notes.note_to_hz(name) == pytest.approx(hz, rel=1e-6)

    def test_midi_hz_roundtrip(self):
        for midi in notes.keyboard_midi_numbers():
            assert notes.hz_to_midi(notes.midi_to_hz(midi)) == pytest.approx(midi)

    def test_alternative_concert_pitch(self):
        assert notes.note_to_hz("A4", a4_hz=442.0) == pytest.approx(442.0)
        assert notes.note_to_hz("A3", a4_hz=442.0) == pytest.approx(221.0)

    def test_keyboard_has_88_keys(self):
        assert len(notes.keyboard_midi_numbers()) == 88


class TestCents:
    def test_octave_is_1200_cents(self):
        assert notes.cents(880.0, 440.0) == pytest.approx(1200.0)
        assert notes.cents(220.0, 440.0) == pytest.approx(-1200.0)

    def test_semitone_is_100_cents(self):
        assert notes.cents(notes.midi_to_hz(61), notes.midi_to_hz(60)) == pytest.approx(100.0)

    def test_shift_roundtrip(self):
        assert notes.cents(notes.shift_cents(440.0, 3.7), 440.0) == pytest.approx(3.7)

    @pytest.mark.parametrize("bad", [(0.0, 440.0), (440.0, 0.0), (-1.0, 440.0)])
    def test_rejects_non_positive_frequencies(self, bad):
        with pytest.raises(ValueError):
            notes.cents(*bad)
