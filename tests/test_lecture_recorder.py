import os
import time
import wave
try:
    import pytest
except ImportError:
    pytest = None
try:
    import numpy as np
except ImportError:
    np = None
from services.lecture_recorder import LectureRecorderService, LectureSession


def test_lecture_session_dataclass():
    session = LectureSession(
        session_id="lec_123",
        subject="Inteligência Artificial",
        title="Modelos Autoregressivos e RAG",
        professor="Prof. Silva",
        audio_path="temp_audio/lec_123.wav",
        status="IDLE",
    )
    data = session.to_dict()
    assert data["session_id"] == "lec_123"
    assert data["subject"] == "Inteligência Artificial"
    assert data["title"] == "Modelos Autoregressivos e RAG"
    assert data["status"] == "IDLE"


def test_recorder_start_and_stop(tmp_path):
    levels = []
    statuses = []

    recorder = LectureRecorderService(
        output_dir=str(tmp_path),
        on_audio_level=lambda lvl: levels.append(lvl),
        on_status_change=lambda sess: statuses.append(sess.status),
    )

    assert not recorder.is_recording
    status_initial = recorder.get_status()
    assert status_initial["is_recording"] is False
    assert status_initial["status"] == "IDLE"

    # Start
    session = recorder.start_recording(
        subject="Sistemas Distribuídos",
        title="Consenso Raft e Quorum",
        professor="Dra. Santos",
    )

    assert recorder.is_recording
    assert session.status == "RECORDING"
    assert os.path.exists(session.audio_path)
    assert len(statuses) >= 1
    assert statuses[-1] == "RECORDING"

    # Simulate audio frames via callback
    if np is not None:
        fake_audio = (np.sin(np.linspace(0, 100, 1600)) * 5000).astype(np.int16)
    else:
        fake_audio = b"\x00\x10" * 800
    recorder._audio_callback(fake_audio, 800, None, None)
    assert len(levels) > 0
    assert levels[-1] > 0.0

    status_running = recorder.get_status()
    assert status_running["is_recording"] is True
    assert status_running["status"] == "RECORDING"
    assert status_running["current_session"]["subject"] == "Sistemas Distribuídos"

    # Stop
    stopped_session = recorder.stop_recording()
    assert not recorder.is_recording
    assert stopped_session.status == "TRANSCRIBING"
    assert stopped_session.duration_seconds >= 0.0

    # History
    history = recorder.list_history()
    assert len(history) == 1
    assert history[0]["session_id"] == session.session_id


def test_recorder_prevents_double_start(tmp_path):
    recorder = LectureRecorderService(output_dir=str(tmp_path))
    recorder.start_recording("Matemática", "Cálculo")

    error_raised = False
    try:
        recorder.start_recording("Física", "Mecânica")
    except RuntimeError as e:
        error_raised = True
        assert "Já existe uma gravação" in str(e)

    assert error_raised, "Deveria ter lançado RuntimeError ao tentar iniciar segunda gravação."
    recorder.stop_recording()
