"""The estimator gate: does it recover a B we already know?

This is the file that matters. Everything else in the suite supports it. A change to the
DSP that leaves these green is probably fine; one that breaks them is wrong until proven
otherwise, and "the curve still looks right" is not a proof (see docs/validation.md).

Tolerances are stated per recording condition rather than as one global number, because
the honest answer varies: on a clean signal the estimator is essentially exact, and it
degrades gracefully with noise. The numbers here are set roughly 5x looser than the
observed error from scripts/validate_synthetic.py, so ordinary numerical drift does not
trip them but a real regression does.
"""

from __future__ import annotations

import numpy as np
import pytest

from atunedpiano import notes
from atunedpiano.inharmonicity import (
    B_MAX,
    InharmonicityError,
    estimate_inharmonicity,
    estimate_key,
    fit_linear,
    track_partials,
)
from atunedpiano.spectrum import analyse
from atunedpiano.synth import partial_frequencies, synth_key, synth_note, typical_B

KEYBOARD_SAMPLE = ["A0", "C1", "C2", "C3", "C4", "A4", "C5", "C6", "C7", "C8"]


def relative_B_error(estimated: float, true: float) -> float:
    return abs(estimated / true - 1.0)


class TestLinearFit:
    def test_recovers_parameters_from_exact_partials(self):
        f0, B = 261.6, 4.0e-4
        frequencies = partial_frequencies(f0, B, 12)
        fitted_f0, fitted_B = fit_linear(np.arange(1, 13), frequencies)
        assert fitted_f0 == pytest.approx(f0, rel=1e-9)
        assert fitted_B == pytest.approx(B, rel=1e-6)

    def test_two_partials_give_an_exact_solve(self):
        f0, B = 110.0, 2.0e-4
        frequencies = partial_frequencies(f0, B, 8)
        fitted_f0, fitted_B = fit_linear(np.array([1.0, 7.0]), frequencies[[0, 6]])
        assert fitted_f0 == pytest.approx(f0, rel=1e-9)
        assert fitted_B == pytest.approx(B, rel=1e-6)

    def test_handles_a_perfectly_harmonic_series(self):
        fitted_f0, fitted_B = fit_linear(np.arange(1, 9), np.arange(1, 9) * 200.0)
        assert fitted_f0 == pytest.approx(200.0, rel=1e-9)
        assert fitted_B == pytest.approx(0.0, abs=1e-9)

    def test_clamps_a_physically_impossible_negative_B(self):
        # Partials bending flat: no real string does this, so B is pinned at zero rather
        # than propagating a negative value into the tuning curve.
        frequencies = np.arange(1, 9) * 200.0 * (1.0 - 0.001 * np.arange(1, 9))
        _, fitted_B = fit_linear(np.arange(1, 9), frequencies)
        assert fitted_B == 0.0

    def test_requires_two_partials(self):
        with pytest.raises(InharmonicityError):
            fit_linear(np.array([1.0]), np.array([440.0]))


class TestPartialTracking:
    def test_a_fixed_harmonic_template_would_lose_the_treble_trajectory(self):
        # Justifies the adjustive trajectory. At treble B, partial 8 sits hundreds of
        # cents above n*f0, far outside any sane fixed search window, so a B=0 template
        # cannot find it and everything above it is lost too.
        f0, B = 2093.0, typical_B(notes.note_to_midi("C7"))
        f8 = partial_frequencies(f0, B, 8)[-1]
        assert notes.cents(f8, 8.0 * f0) > 200.0

    @pytest.mark.parametrize("name", KEYBOARD_SAMPLE)
    def test_partials_are_indexed_correctly(self, name):
        # A mis-indexed partial can still produce a low-residual, self-consistent, wrong
        # fit -- the exact silent failure this suite exists to catch. Check every tracked
        # partial against the frequency the generator actually put there.
        note = synth_key(notes.note_to_midi(name), duration=3.0, n_partials=24)
        spec = analyse(note.signal, note.sample_rate, notes.note_to_hz(name))
        tracked = track_partials(spec, notes.note_to_hz(name))
        assert len(tracked) >= 4
        for partial in tracked:
            true_frequency = note.frequencies[partial.index - 1]
            assert abs(notes.cents(partial.frequency, true_frequency)) < 1.0

    def test_tracking_stops_at_nyquist_rather_than_wrapping(self):
        note = synth_key(notes.note_to_midi("C8"), duration=1.0, sample_rate=48_000)
        spec = analyse(note.signal, note.sample_rate, notes.note_to_hz("C8"))
        tracked = track_partials(spec, notes.note_to_hz("C8"))
        assert all(p.frequency < note.sample_rate / 2 for p in tracked)


class TestCleanRecovery:
    @pytest.mark.parametrize("name", KEYBOARD_SAMPLE)
    def test_recovers_B_and_f0_across_the_keyboard(self, name):
        note = synth_key(notes.note_to_midi(name), duration=3.0, n_partials=24)
        estimate = estimate_key(note.signal, note.sample_rate, name)
        assert relative_B_error(estimate.B, note.B) < 0.001
        assert abs(notes.cents(estimate.f0, note.f0)) < 0.01
        assert estimate.residual_cents_rms < 0.01

    @pytest.mark.parametrize("B", [1e-5, 1e-4, 1e-3, 1e-2, 3e-2])
    def test_recovers_B_over_five_orders_of_magnitude(self, B):
        note = synth_note(440.0, B, duration=3.0, n_partials=24)
        estimate = estimate_inharmonicity(note.signal, note.sample_rate, 440.0)
        assert relative_B_error(estimate.B, B) < 0.01

    def test_recovers_a_perfectly_harmonic_tone_as_near_zero_B(self):
        note = synth_note(440.0, 0.0, duration=3.0, n_partials=20)
        estimate = estimate_inharmonicity(note.signal, note.sample_rate, 440.0)
        assert estimate.B < 1e-6

    def test_first_partial_is_sharp_of_the_ideal_f0(self):
        note = synth_key(notes.note_to_midi("C7"), duration=2.0)
        estimate = estimate_key(note.signal, note.sample_rate, "C7")
        assert estimate.first_partial > estimate.f0
        assert notes.cents(estimate.first_partial, note.frequencies[0]) == pytest.approx(
            0.0, abs=0.05
        )

    def test_inharmonicity_grows_with_partial_number(self):
        note = synth_key(notes.note_to_midi("C6"), duration=2.0)
        estimate = estimate_key(note.signal, note.sample_rate, "C6")
        deviations = [estimate.inharmonicity_cents(n) for n in range(1, 9)]
        assert all(d > 0.0 for d in deviations)
        assert np.all(np.diff(deviations) > 0.0)


class TestNoisyRecovery:
    @pytest.mark.parametrize("name", KEYBOARD_SAMPLE)
    def test_survives_a_realistic_room_recording(self, name):
        # 30 dB SNR with irregular partial amplitudes: a decent phone or USB mic in a
        # quiet room, which is the target condition for this tool.
        note = synth_key(
            notes.note_to_midi(name),
            duration=3.0,
            n_partials=24,
            snr_db=30.0,
            amplitude_jitter_db=6.0,
            seed=1,
        )
        estimate = estimate_key(note.signal, note.sample_rate, name)
        assert relative_B_error(estimate.B, note.B) < 0.01
        assert abs(notes.cents(estimate.f0, note.f0)) < 0.1

    @pytest.mark.parametrize("seed", range(4))
    def test_survives_a_noisy_room_recording(self, seed):
        note = synth_key(
            notes.note_to_midi("C4"),
            duration=3.0,
            n_partials=24,
            snr_db=20.0,
            amplitude_jitter_db=6.0,
            seed=seed,
        )
        estimate = estimate_key(note.signal, note.sample_rate, "C4")
        assert relative_B_error(estimate.B, note.B) < 0.02
        assert abs(notes.cents(estimate.f0, note.f0)) < 0.2

    @pytest.mark.parametrize("detune_cents", [-90.0, -45.0, 45.0, 90.0])
    def test_finds_a_piano_that_has_drifted_out_of_tune(self, detune_cents):
        # The hint is the nominal pitch; the piano is not there. Pitch-raise territory.
        note = synth_key(
            notes.note_to_midi("C4"),
            duration=3.0,
            n_partials=24,
            detune_cents=detune_cents,
            snr_db=30.0,
        )
        estimate = estimate_key(note.signal, note.sample_rate, "C4")
        assert relative_B_error(estimate.B, note.B) < 0.01
        assert notes.cents(estimate.first_partial, notes.note_to_hz("C4")) == pytest.approx(
            detune_cents, abs=0.1
        )


class TestOutlierHandling:
    def test_rejects_a_spurious_peak_near_a_partial(self):
        # A strong interloper 25 cents off partial 7 -- what a false beat, a phantom
        # partial or a neighbouring string can look like. It should not move B.
        note = synth_key(notes.note_to_midi("C4"), duration=3.0, n_partials=20)
        t = np.arange(note.signal.size) / note.sample_rate
        intruder = notes.shift_cents(note.frequencies[6], 25.0)
        contaminated = note.signal + 0.6 * np.sin(2.0 * np.pi * intruder * t)

        estimate = estimate_inharmonicity(
            contaminated, note.sample_rate, notes.note_to_hz("C4")
        )
        assert relative_B_error(estimate.B, note.B) < 0.01
        # The interloper is louder than the real partial 7, so the search finds it; the
        # residual then exposes it and the fit drops it rather than bending B to suit.
        assert 7 in [p.index for p in estimate.rejected]
        assert 7 not in [p.index for p in estimate.partials]

    def test_reports_what_it_threw_away(self):
        note = synth_key(notes.note_to_midi("C4"), duration=3.0, n_partials=20)
        estimate = estimate_key(note.signal, note.sample_rate, "C4")
        assert estimate.rejected == ()
        assert estimate.n_partials == len(estimate.partials)


class TestFailureModes:
    def test_refuses_to_fit_noise(self):
        rng = np.random.default_rng(0)
        with pytest.raises(InharmonicityError):
            estimate_inharmonicity(rng.normal(size=96_000), 48_000, 440.0)

    def test_refuses_when_too_few_partials_survive(self):
        note = synth_note(440.0, 1e-4, duration=2.0, n_partials=3)
        with pytest.raises(InharmonicityError):
            estimate_inharmonicity(note.signal, note.sample_rate, 440.0, min_partials=8)

    def test_extreme_treble_is_partial_starved_at_48k(self):
        # C8 with treble-scale B has only a handful of partials below Nyquist. This is a
        # property of the note, not a bug -- it is why the recording protocol asks for a
        # higher sample rate in the top octave.
        at_48k = estimate_key(
            *_signal_and_rate(synth_key(108, duration=1.0, sample_rate=48_000)), "C8"
        )
        at_96k = estimate_key(
            *_signal_and_rate(synth_key(108, duration=1.0, sample_rate=96_000)), "C8"
        )
        assert at_96k.n_partials > at_48k.n_partials

    def test_B_is_bounded(self):
        note = synth_key(notes.note_to_midi("C8"), duration=1.0)
        estimate = estimate_key(note.signal, note.sample_rate, "C8")
        assert 0.0 <= estimate.B <= B_MAX


class TestReportedUncertainty:
    def test_standard_errors_are_finite_when_there_are_spare_partials(self):
        note = synth_key(
            notes.note_to_midi("C4"), duration=3.0, n_partials=20, snr_db=30.0
        )
        estimate = estimate_key(note.signal, note.sample_rate, "C4")
        assert np.isfinite(estimate.B_stderr)
        assert np.isfinite(estimate.f0_stderr_cents)
        assert estimate.B_stderr > 0.0

    def test_noise_widens_the_reported_uncertainty(self):
        quiet = estimate_key(
            *_signal_and_rate(
                synth_key(60, duration=3.0, n_partials=20, snr_db=40.0, seed=2)
            ),
            "C4",
        )
        loud = estimate_key(
            *_signal_and_rate(
                synth_key(60, duration=3.0, n_partials=20, snr_db=15.0, seed=2)
            ),
            "C4",
        )
        assert loud.B_stderr > quiet.B_stderr
        assert loud.residual_cents_rms > quiet.residual_cents_rms


class TestKeyLookup:
    def test_accepts_a_note_name_or_a_midi_number(self):
        note = synth_key(69, duration=2.0)
        by_name = estimate_key(note.signal, note.sample_rate, "A4")
        by_midi = estimate_key(note.signal, note.sample_rate, 69)
        assert by_name.B == pytest.approx(by_midi.B)

    def test_honours_an_alternative_concert_pitch(self):
        note = synth_key(69, duration=2.0)
        estimate = estimate_key(note.signal, note.sample_rate, "A4", a4_hz=442.0)
        assert relative_B_error(estimate.B, note.B) < 0.01


def _signal_and_rate(note):
    return note.signal, note.sample_rate
