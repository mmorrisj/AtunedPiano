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
    MAX_RESIDUAL_CENTS,
    InharmonicityError,
    estimate_inharmonicity,
    estimate_key,
    fit_linear,
    track_partials,
)
from atunedpiano.spectrum import analyse, select_segment
from atunedpiano.synth import (
    f0_from_first_partial,
    partial_frequencies,
    synth_key,
    synth_note,
    typical_B,
)

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


class TestResidualGuard:
    """A converged fit is not the same as a correct one."""

    def test_refuses_a_fit_the_model_cannot_explain(self):
        # Noise shaped to have peaks near the harmonics of C4, so the tracker finds
        # "partials" and the fit converges -- on nothing. Without the guard this returns a
        # confident B, which is how a decayed tail gets reported as a measurement.
        rng = np.random.default_rng(3)
        sample_rate, f0 = 48_000, notes.note_to_hz("C4")
        t = np.arange(3 * sample_rate) / sample_rate
        signal = sum(
            np.sin(2 * np.pi * notes.shift_cents(n * f0, rng.uniform(-60, 60)) * t)
            / n
            for n in range(1, 15)
        )
        with pytest.raises(InharmonicityError, match="residual"):
            estimate_inharmonicity(signal, sample_rate, f0, start=0.1)

    def test_a_clean_note_passes_the_guard_with_room_to_spare(self):
        note = synth_key(notes.note_to_midi("C4"), duration=3.0, n_partials=20, snr_db=30.0)
        estimate = estimate_key(note.signal, note.sample_rate, "C4")
        assert estimate.residual_cents_rms < MAX_RESIDUAL_CENTS / 10.0

    def test_the_threshold_can_be_relaxed_for_inspection(self):
        rng = np.random.default_rng(3)
        sample_rate, f0 = 48_000, notes.note_to_hz("C4")
        t = np.arange(3 * sample_rate) / sample_rate
        signal = sum(
            np.sin(2 * np.pi * notes.shift_cents(n * f0, rng.uniform(-60, 60)) * t)
            / n
            for n in range(1, 15)
        )
        loose = estimate_inharmonicity(
            signal, sample_rate, f0, start=0.1, max_residual_cents=1e9
        )
        assert loose.residual_cents_rms > MAX_RESIDUAL_CENTS


class TestSegmentChoice:
    """The estimator should not need to be told where to look."""

    def test_finds_the_note_behind_lead_in_silence(self):
        note = synth_key(notes.note_to_midi("C4"), duration=3.0, n_partials=20)
        signal = np.concatenate([np.zeros(int(0.8 * note.sample_rate)), note.signal])
        estimate = estimate_key(signal, note.sample_rate, "C4")
        assert relative_B_error(estimate.B, note.B) < 0.01
        assert estimate.spectrum.segment.onset == pytest.approx(0.8, abs=0.05)

    @pytest.mark.parametrize(
        "lead,trail", [(0.0, 0.0), (0.371, 0.0), (2.0, 0.0), (0.0, 20.0), (1.234, 8.0)]
    )
    def test_silence_around_the_note_does_not_move_the_answer(self, lead, trail):
        # Recordings have dead air at both ends: reaching for the key, and letting it ring
        # out before stopping the recorder. Neither should reach the measurement. Leading
        # room tone is skipped by onset detection. Trailing silence is excluded by the
        # search taking the *earliest* steady candidate -- the note's own steady stretch
        # always precedes the silence, so silence is never reached. The level floor and the
        # residual guard sit behind that as backstops for a recording with no steady stretch
        # at all; neither is what does the work here.
        note = synth_key(notes.note_to_midi("C4"), duration=3.0, n_partials=20, snr_db=40.0)
        rng = np.random.default_rng(0)
        room = float(np.sqrt(np.mean(note.signal**2))) * 1e-3
        padded = np.concatenate(
            [
                rng.normal(0.0, room, int(lead * note.sample_rate)),
                note.signal,
                rng.normal(0.0, room, int(trail * note.sample_rate)),
            ]
        )
        reference = estimate_key(note.signal, note.sample_rate, "C4")
        padded_estimate = estimate_key(padded, note.sample_rate, "C4")

        assert padded_estimate.B == pytest.approx(reference.B, rel=0.005)
        assert padded_estimate.n_partials == reference.n_partials
        assert padded_estimate.spectrum.segment.onset == pytest.approx(lead, abs=0.05)

    def test_avoids_a_segment_that_would_bias_the_low_partials(self):
        # Reproduces the failure found on the first real recording: a dip and recovery in
        # the envelope, and a short window sitting across it, biases the interpolated
        # frequencies of the low partials by several cents.
        note = synth_key(notes.note_to_midi("C4"), duration=3.0, n_partials=20)
        t = np.arange(note.signal.size) / note.sample_rate
        signal = note.signal * (1.0 - 0.9 * np.exp(-(((t - 0.25) / 0.06) ** 2)))

        across = estimate_inharmonicity(
            signal, note.sample_rate, notes.note_to_hz("C4"), start=0.15, duration=0.25,
            max_residual_cents=1e9,
        )
        chosen = estimate_key(signal, note.sample_rate, "C4")
        assert chosen.spectrum.segment.start >= 0.25  # moved past the dip
        assert chosen.residual_cents_rms < across.residual_cents_rms
        assert relative_B_error(chosen.B, note.B) < 0.01


class TestMissingLowPartials:
    """A bass string can radiate nothing at all at its first few partials."""

    def without_low_partials(self, midi, B, drop, *, sample_rate=48_000, snr_db=30.0, seed=0):
        rng = np.random.default_rng(seed)
        f0 = f0_from_first_partial(notes.midi_to_hz(midi), B)
        freqs = partial_frequencies(f0, B, 24)
        freqs = freqs[freqs < 0.98 * sample_rate / 2]
        n = np.arange(1, freqs.size + 1, dtype=float)
        amplitudes = np.exp(-((n - 5.0) ** 2) / 50.0)
        amplitudes[:drop] = 0.0
        t = np.arange(int(4.0 * sample_rate)) / sample_rate
        envelope = np.exp(-t[None, :] / (4.0 * n[:, None] ** -0.7))
        phases = rng.uniform(0.0, 2 * np.pi, (n.size, 1))
        signal = (
            amplitudes[:, None]
            * np.sin(2 * np.pi * freqs[:, None] * t[None, :] + phases)
            * envelope
        ).sum(axis=0)
        noise = np.sqrt(np.mean(signal**2)) * 10 ** (-snr_db / 20)
        return signal + rng.normal(0.0, noise, signal.size), sample_rate

    @pytest.mark.parametrize("drop", [1, 2, 3, 4, 5])
    def test_recovers_B_with_the_lowest_partials_absent(self, drop):
        # The miss counter is there to stop the walk running off the top of the series, not
        # to stop it starting. With the first five partials gone the note is still perfectly
        # measurable from partial six upward.
        B = 3.6e-4
        signal, sr = self.without_low_partials(24, B, drop)
        estimate = estimate_key(signal, sr, 24)
        assert relative_B_error(estimate.B, B) < 0.02
        assert estimate.partials[0].index == drop + 1

    def test_a_buried_fundamental_is_still_found(self):
        # Buried is not absent: at -50 dB partial 1 is still a real peak and still tracked.
        B = 3.6e-4
        signal, sr = self.without_low_partials(24, B, 0)
        estimate = estimate_key(signal, sr, 24)
        assert estimate.partials[0].index == 1
        assert relative_B_error(estimate.B, B) < 0.02


class TestSearchWindow:
    def test_never_reaches_the_neighbouring_partial(self):
        # A window wider than half the gap to the next partial can grab the wrong one. The
        # gap shrinks fast with n -- 1200 cents at n=1, 702 at n=2, 498 at n=3 -- so a fixed
        # cap safe at the bottom is not safe a few partials up.
        from atunedpiano.inharmonicity import _search_halfwidth_cents

        for n in range(1, 12):
            gap_to_neighbour = 1200.0 * np.log2((n + 1.0) / n)
            for fitted in (0, 1, 2, 3):
                halfwidth = _search_halfwidth_cents(
                    n, fitted, search_cents=40.0, hint_cents=100.0
                )
                assert halfwidth < gap_to_neighbour / 2.0


class TestMultipleStrikesEndToEnd:
    def test_picks_the_usable_strike_over_an_earlier_poor_one(self):
        # A quiet, short first strike followed by a full one -- the shape of the real C6 and
        # C7 recordings, where the analysis used to lock onto whichever came first.
        good = synth_key(60, duration=3.0, n_partials=20, seed=1)
        weak = synth_key(60, duration=0.25, n_partials=3, seed=2)
        sr = good.sample_rate
        signal = np.zeros(int(8.0 * sr))
        signal[int(0.5 * sr) : int(0.5 * sr) + weak.signal.size] += 0.05 * weak.signal
        signal[int(3.0 * sr) : int(3.0 * sr) + good.signal.size] += good.signal

        estimate = estimate_key(signal, sr, 60)
        assert relative_B_error(estimate.B, good.B) < 0.01
        assert estimate.spectrum.segment.start > 2.5


class TestSegmentEscalation:
    """When the cheap segment choice is wrong, fit the alternatives instead of guessing."""

    def never_steady(self, midi=84, seed=0):
        """A note that is erratic while it sounds and flat once it is gone -- the C6 shape.

        Heavy amplitude modulation means no window containing the note passes the steadiness
        test, while the noise floor after it decays is perfectly flat and so scores as the
        steadiest thing in the file. select_segment therefore falls back to a stretch with
        no note in it. The steadiness proxy has no standing once its own precondition has
        failed, and on the real C6 it picked an unfittable segment in exactly this way.
        """
        note = synth_key(midi, duration=1.2, n_partials=20, decay_time=0.35, seed=seed)
        rng = np.random.default_rng(seed)
        sr = note.sample_rate
        signal = np.concatenate([note.signal, np.zeros(int(2.5 * sr))])
        t = np.arange(signal.size) / sr
        signal = signal * (
            1.0 + 0.85 * np.sin(2 * np.pi * 3.1 * t) * np.sin(2 * np.pi * 1.7 * t + 0.4)
        )
        floor = float(np.sqrt(np.mean(note.signal**2))) * 0.05
        return signal + rng.normal(0.0, floor, signal.size), sr, note.B

    def test_no_segment_of_this_note_is_steady(self):
        # Establishes the precondition the escalation exists for; without it the test below
        # would pass for the wrong reason.
        signal, sr, _ = self.never_steady()
        chosen = select_segment(signal, sr, notes.midi_to_hz(84))
        assert not chosen.is_steady

    def test_recovers_B_anyway(self):
        signal, sr, B = self.never_steady()
        estimate = estimate_key(signal, sr, 84)
        assert relative_B_error(estimate.B, B) < 0.05

    def test_an_explicit_start_is_never_second_guessed(self):
        # Escalation would defeat the purpose of --start, which exists to reproduce one
        # specific reading.
        signal, sr, _ = self.never_steady()
        with pytest.raises(InharmonicityError):
            estimate_key(signal, sr, 84, start=len(signal) / sr - 0.26)


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
