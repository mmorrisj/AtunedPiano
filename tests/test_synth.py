"""Tests for the ground-truth harness itself.

If these fail, every other test in the project is meaningless: they check that the
generated signal really contains the partials it claims to, at the frequencies the
stiff-string model predicts. The frequency check here uses a direct DFT at the candidate
bin rather than anything from ``atunedpiano.spectrum``, so the harness is verified
independently of the code it is used to test.
"""

from __future__ import annotations

import numpy as np
import pytest

from atunedpiano import notes
from atunedpiano.synth import (
    first_partial,
    f0_from_first_partial,
    partial_frequencies,
    synth_key,
    synth_note,
    typical_B,
)


def dft_magnitude(signal: np.ndarray, sample_rate: int, frequency: float) -> float:
    """Magnitude of a single DFT bin at an arbitrary (non-integer) frequency."""
    t = np.arange(signal.size, dtype=float) / sample_rate
    window = np.hanning(signal.size)
    return float(np.abs(np.sum(signal * window * np.exp(-2j * np.pi * frequency * t))))


class TestPartialModel:
    def test_matches_stiff_string_formula(self):
        f0, B = 261.6255653, 4.0e-4
        freqs = partial_frequencies(f0, B, 8)
        for n in range(1, 9):
            expected = n * f0 * np.sqrt(1.0 + B * n**2)
            assert freqs[n - 1] == pytest.approx(expected, rel=1e-12)

    def test_zero_B_gives_exact_harmonics(self):
        freqs = partial_frequencies(100.0, 0.0, 5)
        assert freqs == pytest.approx([100.0, 200.0, 300.0, 400.0, 500.0])

    def test_partials_are_progressively_sharp(self):
        f0, B = 220.0, 1.0e-3
        freqs = partial_frequencies(f0, B, 10)
        deviations = [
            notes.cents(freqs[n - 1], n * f0) for n in range(1, 11)
        ]
        # Inharmonicity pushes every partial sharp, and increasingly so.
        assert all(d > 0.0 for d in deviations)
        assert np.all(np.diff(deviations) > 0.0)

    def test_first_partial_roundtrip(self):
        B = 1.0e-2
        f0 = 2093.0
        f1 = first_partial(f0, B)
        assert f1 > f0  # stiffness sharpens partial 1 relative to the ideal f0
        assert f0_from_first_partial(f1, B) == pytest.approx(f0, rel=1e-12)

    @pytest.mark.parametrize("bad", [(0.0, 1e-4, 4), (100.0, -1e-4, 4), (100.0, 1e-4, 0)])
    def test_rejects_invalid_arguments(self, bad):
        with pytest.raises(ValueError):
            partial_frequencies(*bad)


class TestTypicalB:
    def test_spans_the_documented_range(self):
        values = [typical_B(m) for m in notes.keyboard_midi_numbers()]
        assert min(values) > 1e-5
        assert max(values) < 1e-1
        # Treble inharmonicity is orders of magnitude above the bass minimum.
        assert max(values) / min(values) > 100.0

    def test_rises_through_the_treble(self):
        for midi in range(48, 108):
            assert typical_B(midi + 1) > typical_B(midi)


class TestSynthNote:
    def test_energy_sits_at_the_claimed_partial_frequencies(self):
        note = synth_note(220.0, 5.0e-4, duration=1.0, n_partials=10)
        segment = note.signal[: note.sample_rate // 2]
        for freq in note.frequencies[:8]:
            at_partial = dft_magnitude(segment, note.sample_rate, freq)
            off_flat = dft_magnitude(segment, note.sample_rate, freq / 1.0)
            assert at_partial == off_flat  # sanity: same call, same answer
            for offset_cents in (-40.0, 40.0):
                off = dft_magnitude(
                    segment, note.sample_rate, notes.shift_cents(freq, offset_cents)
                )
                assert at_partial > 5.0 * off

    def test_inharmonic_signal_is_distinguishable_from_a_harmonic_one(self):
        B = 2.0e-3
        note = synth_note(440.0, B, duration=1.0, n_partials=8)
        segment = note.signal[: note.sample_rate // 2]
        n = 8
        inharmonic = note.frequencies[n - 1]
        harmonic = n * note.f0
        assert dft_magnitude(segment, note.sample_rate, inharmonic) > 5.0 * dft_magnitude(
            segment, note.sample_rate, harmonic
        )

    def test_drops_partials_above_nyquist_instead_of_aliasing(self):
        note = synth_note(2093.0, 1.4e-2, sample_rate=44_100, n_partials=24, duration=0.5)
        assert note.n_partials < 24
        assert np.all(note.frequencies < 0.98 * note.sample_rate / 2)
        # Nothing folded back below the lowest partial.
        below = dft_magnitude(note.signal, note.sample_rate, note.frequencies[0] / 2.0)
        at_partial = dft_magnitude(note.signal, note.sample_rate, note.frequencies[0])
        assert below < 0.01 * at_partial

    def test_raises_when_every_partial_is_above_nyquist(self):
        with pytest.raises(ValueError):
            synth_note(30_000.0, 0.0, sample_rate=44_100, duration=0.1)

    def test_upper_partials_decay_faster(self):
        note = synth_note(440.0, 1e-4, duration=3.0, n_partials=6, decay_time=2.0)
        early = note.signal[: note.sample_rate // 2]
        late = note.signal[-note.sample_rate // 2 :]
        ratio_1 = dft_magnitude(late, note.sample_rate, note.frequencies[0]) / dft_magnitude(
            early, note.sample_rate, note.frequencies[0]
        )
        ratio_6 = dft_magnitude(late, note.sample_rate, note.frequencies[5]) / dft_magnitude(
            early, note.sample_rate, note.frequencies[5]
        )
        assert ratio_6 < ratio_1

    def test_is_deterministic_for_a_fixed_seed(self):
        a = synth_note(440.0, 1e-4, duration=0.3, seed=7)
        b = synth_note(440.0, 1e-4, duration=0.3, seed=7)
        c = synth_note(440.0, 1e-4, duration=0.3, seed=8)
        assert np.array_equal(a.signal, b.signal)
        assert not np.array_equal(a.signal, c.signal)

    @pytest.mark.parametrize("snr_db", [40.0, 20.0, 6.0])
    def test_added_noise_hits_the_requested_snr(self, snr_db):
        clean = synth_note(440.0, 1e-4, duration=1.0, seed=3)
        noisy = synth_note(440.0, 1e-4, duration=1.0, seed=3, snr_db=snr_db)
        noise = noisy.signal - clean.signal
        measured = 20.0 * np.log10(
            np.sqrt(np.mean(clean.signal**2)) / np.sqrt(np.mean(noise**2))
        )
        assert measured == pytest.approx(snr_db, abs=0.5)

    def test_amplitude_jitter_perturbs_the_rolloff(self):
        plain = synth_note(440.0, 1e-4, duration=0.3, n_partials=8, seed=5)
        jittered = synth_note(
            440.0, 1e-4, duration=0.3, n_partials=8, seed=5, amplitude_jitter_db=6.0
        )
        assert not np.allclose(plain.amplitudes, jittered.amplitudes)
        assert np.array_equal(plain.frequencies, jittered.frequencies)

    def test_attack_ramp_avoids_an_onset_click(self):
        note = synth_note(440.0, 1e-4, duration=0.3, attack_time=0.005)
        assert abs(note.signal[0]) < 1e-6

    def test_reports_its_own_parameters(self):
        note = synth_note(440.0, 3e-4, duration=1.5, sample_rate=44_100, n_partials=12)
        assert note.f0 == 440.0
        assert note.B == 3e-4
        assert note.n_partials == 12
        assert note.duration == pytest.approx(1.5, abs=1e-3)


class TestSynthKey:
    @pytest.mark.parametrize("name", ["A0", "C2", "A4", "C7", "C8"])
    def test_first_partial_lands_on_the_equal_tempered_pitch(self, name):
        midi = notes.note_to_midi(name)
        note = synth_key(midi, duration=0.5)
        measured_f1 = note.frequencies[0]
        assert notes.cents(measured_f1, notes.midi_to_hz(midi)) == pytest.approx(
            0.0, abs=1e-6
        )
        # The ideal f0 sits flat of partial 1 by an amount set by B.
        assert note.f0 < measured_f1

    def test_detune_offsets_the_target(self):
        midi = notes.note_to_midi("A4")
        note = synth_key(midi, detune_cents=-12.5, duration=0.5)
        assert notes.cents(note.frequencies[0], 440.0) == pytest.approx(-12.5, abs=1e-6)

    def test_uses_the_keyboard_B_profile_by_default(self):
        midi = notes.note_to_midi("C7")
        assert synth_key(midi, duration=0.2).B == pytest.approx(typical_B(midi))
        assert synth_key(midi, B=1e-3, duration=0.2).B == pytest.approx(1e-3)
