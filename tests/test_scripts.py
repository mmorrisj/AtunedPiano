"""Smoke tests for the command-line entry points.

They exist so the scripts do not quietly rot as the library changes. They check that the
tools run end to end and report the right answer on a file whose B is known, not that the
output is formatted any particular way.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from atunedpiano.synth import synth_key, write_wav

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def analyze():
    return load_script("analyze_recording")


@pytest.fixture(scope="module")
def validate():
    return load_script("validate_synthetic")


class TestAnalyzeRecording:
    @pytest.fixture
    def wav(self, tmp_path):
        note = synth_key(
            69, duration=3.0, n_partials=24, snr_db=32.0, detune_cents=-7.0, seed=4
        )
        path = tmp_path / "A4.wav"
        write_wav(path, note)
        return path, note

    def test_recovers_the_known_parameters_of_a_written_file(self, analyze, wav, capsys):
        path, note = wav
        assert analyze.main([str(path), "--note", "A4"]) == 0

        output = capsys.readouterr().out
        reported_B = float(re.search(r"B\s+([\d.]+e[-+]\d+)", output).group(1))
        assert abs(reported_B / note.B - 1.0) < 0.01
        assert "-7.00 cents from nominal" in output
        assert "plausible" in output

    def test_round_trips_through_the_wav_writer(self, analyze, wav):
        path, note = wav
        signal, sample_rate = analyze.read_wav(path)
        assert sample_rate == note.sample_rate
        assert signal.ndim == 1
        assert signal.size == note.signal.size

    def test_reports_a_missing_file(self, analyze, tmp_path, capsys):
        assert analyze.main([str(tmp_path / "absent.wav"), "--note", "A4"]) == 2

    def test_reports_a_note_that_is_not_there(self, analyze, wav, capsys):
        path, _ = wav
        assert analyze.main([str(path), "--note", "C2"]) == 1
        assert "could not fit" in capsys.readouterr().err

    def test_flags_a_clipped_recording(self, analyze, tmp_path, capsys):
        note = synth_key(69, duration=3.0, n_partials=24)
        driven = note.signal / (0.3 * np.max(np.abs(note.signal)))
        path = tmp_path / "clipped.wav"
        write_wav(path, replace(note, signal=np.clip(driven, -1.0, 1.0)), peak=1.0)

        analyze.main([str(path), "--note", "A4"])
        assert "likely clipped" in capsys.readouterr().out


class TestValidateSweep:
    def test_runs_and_reports_every_band(self, validate, capsys):
        assert validate.main(["--seeds", "1", "--stride", "24", "--duration", "1.5"]) == 0
        output = capsys.readouterr().out
        for label, _, _ in validate.BANDS:
            assert label in output
        for condition in validate.CONDITIONS:
            assert condition.label in output

    def test_bands_cover_the_whole_keyboard(self, validate):
        from atunedpiano import notes

        for midi in notes.keyboard_midi_numbers():
            assert validate.band_of(midi) in {label for label, _, _ in validate.BANDS}
