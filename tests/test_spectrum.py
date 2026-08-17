"""Adaptive windowing and sub-bin peak location."""

from __future__ import annotations

import numpy as np
import pytest

from atunedpiano import notes, spectrum
from atunedpiano.synth import synth_note


def sine(frequency: float, duration: float, sample_rate: int = 48_000) -> np.ndarray:
    t = np.arange(int(duration * sample_rate)) / sample_rate
    return np.sin(2.0 * np.pi * frequency * t + 0.7)


class TestAdaptiveWindow:
    def test_bass_gets_a_longer_window_than_treble(self):
        assert spectrum.window_seconds(27.5) > spectrum.window_seconds(440.0)
        assert spectrum.window_seconds(440.0) >= spectrum.window_seconds(4186.0)

    def test_window_is_long_enough_to_separate_adjacent_partials(self):
        # A Hann main lobe is 4/T Hz wide; adjacent partials are about f0 apart. Every
        # note on the keyboard must clear that separation by a healthy margin, otherwise
        # partial tracking is resolving noise.
        for midi in notes.keyboard_midi_numbers():
            f0 = notes.midi_to_hz(midi)
            main_lobe_hz = 4.0 / spectrum.window_seconds(f0)
            assert main_lobe_hz < f0 / 2.0

    def test_window_is_clamped(self):
        assert spectrum.window_seconds(1.0) == spectrum.MAX_WINDOW_SECONDS
        assert spectrum.window_seconds(100_000.0) == spectrum.MIN_WINDOW_SECONDS

    def test_treble_window_fits_inside_a_short_decay(self):
        assert spectrum.window_seconds(4186.0) <= 0.3

    def test_attack_skip_is_longer_in_the_bass(self):
        assert spectrum.attack_skip_seconds(55.0) > spectrum.attack_skip_seconds(1760.0)

    def test_rejects_non_positive_hint(self):
        with pytest.raises(ValueError):
            spectrum.window_seconds(0.0)


class TestSegmentSelection:
    def test_skips_the_attack(self):
        signal = np.concatenate([np.zeros(4800), np.ones(96_000)])
        segment = spectrum.select_segment(signal, 48_000, 440.0, attack_skip=0.1)
        assert np.all(segment == 1.0)

    def test_falls_back_when_the_recording_is_short(self):
        signal = np.ones(12_000)  # 0.25 s, shorter than skip + ideal window
        segment = spectrum.select_segment(signal, 48_000, 55.0)
        assert 0 < segment.size <= signal.size

    def test_raises_on_a_signal_too_short_to_analyse(self):
        with pytest.raises(ValueError):
            spectrum.select_segment(np.ones(8), 48_000, 440.0)

    def test_rejects_stereo(self):
        with pytest.raises(ValueError):
            spectrum.select_segment(np.ones((2, 1000)), 48_000, 440.0)


class TestPeakRefinement:
    @pytest.mark.parametrize("frequency", [27.53, 220.7, 441.31, 1976.9, 4187.4])
    def test_parabolic_interpolation_is_sub_cent(self, frequency):
        signal = sine(frequency, 1.0)
        spec = spectrum.analyse(signal, 48_000, frequency, attack_skip=0.0)
        peak = spec.peak_near(frequency, 50.0)
        assert peak is not None
        assert abs(notes.cents(peak.frequency, frequency)) < 0.05

    def test_interpolation_beats_taking_the_raw_bin(self):
        # Deliberately off-centre in its bin, and with little zero-padding, so the raw bin
        # is visibly wrong and the interpolation has something to fix.
        frequency = 440.0 + 0.37
        segment = spectrum.select_segment(sine(frequency, 0.5), 48_000, 440.0, attack_skip=0.0)
        spec = spectrum.compute_spectrum(segment, 48_000, zero_pad=1)
        peak = spec.peak_near(frequency, 50.0)
        raw_bin_hz = spec.frequencies[peak.bin_index]
        assert abs(peak.frequency - frequency) < abs(raw_bin_hz - frequency)

    def test_returns_none_in_an_empty_band(self):
        spec = spectrum.analyse(sine(440.0, 1.0), 48_000, 440.0, attack_skip=0.0)
        floor = float(np.max(spec.magnitudes)) * 1e-3
        assert spec.peak_near(3000.0, 30.0, min_magnitude=floor) is None

    def test_does_not_latch_onto_a_neighbours_skirt(self):
        # One strong partial at 440; look for an absent one 700 cents up. The band should
        # contain no local maximum above the floor.
        spec = spectrum.analyse(sine(440.0, 1.0), 48_000, 440.0, attack_skip=0.0)
        floor = float(np.max(spec.magnitudes)) * 1e-2
        assert spec.peak_near(notes.shift_cents(440.0, 700.0), 60.0, min_magnitude=floor) is None

    def test_resolves_two_close_partials_separately(self):
        note = synth_note(110.0, 1e-4, duration=1.5, n_partials=6)
        spec = spectrum.analyse(note.signal, note.sample_rate, 110.0)
        for expected in note.frequencies[:6]:
            peak = spec.peak_near(expected, 30.0)
            assert peak is not None
            assert abs(notes.cents(peak.frequency, expected)) < 0.2


class TestSpectrumProperties:
    def test_removes_dc_offset(self):
        signal = sine(440.0, 0.5) + 3.0
        spec = spectrum.analyse(signal, 48_000, 440.0, attack_skip=0.0)
        assert spec.magnitudes[0] < 1e-6 * float(np.max(spec.magnitudes))

    def test_zero_padding_increases_resolution(self):
        segment = spectrum.select_segment(sine(440.0, 0.5), 48_000, 440.0, attack_skip=0.0)
        coarse = spectrum.compute_spectrum(segment, 48_000, zero_pad=1)
        fine = spectrum.compute_spectrum(segment, 48_000, zero_pad=8)
        assert fine.bin_width < coarse.bin_width
        assert fine.n_fft > coarse.n_fft

    def test_noise_floor_sits_far_below_a_partial(self):
        note = synth_note(440.0, 1e-4, duration=1.0, snr_db=30.0)
        spec = spectrum.analyse(note.signal, note.sample_rate, 440.0)
        assert spec.noise_floor < 1e-2 * float(np.max(spec.magnitudes))

    def test_rejects_invalid_zero_pad(self):
        with pytest.raises(ValueError):
            spectrum.compute_spectrum(np.ones(1024), 48_000, zero_pad=0)
