"""
Regressão Stage 6 — Pipeline de Vídeo: OCR WinRT em lotes resilientes, diagnóstico ASR e cache MP4 para .wmv.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from services import lecture_synthesizer, study_ai_engine, video_intelligence_service


def test_batched_winrt_ocr_preserves_succeeded_batches_when_one_batch_fails(tmp_path):
    frames = []
    for idx in range(8):
        fp = tmp_path / f"frame_{idx:03d}.jpg"
        fp.write_bytes(b"fake-jpg")
        frames.append(str(fp.resolve()))

    def fake_ps_batch(batch_paths, timeout_sec=28):
        if len(batch_paths) > 1 and frames[6] in batch_paths:
            return None, "TIMEOUT"
        return {p: f"Slide content from {Path(p).name}" for p in batch_paths}, "OK"

    with patch("services.study_ai_engine.os.name", "nt"), patch(
        "services.study_ai_engine._run_winrt_ocr_ps_batch", side_effect=fake_ps_batch
    ):
        ocr_map, status = study_ai_engine.extract_keyframes_ocr_windows_with_status(
            frames, batch_size=6
        )

    assert len(ocr_map) == 8
    assert status == "OCR_PARTIAL"


def test_local_transcriber_reports_whisper_not_installed_explicitly(tmp_path):
    wav = tmp_path / "dummy.wav"
    wav.write_bytes(b"RIFF\x24\x00\x00\x00WAVEfmt ")

    transcriber = lecture_synthesizer.LocalTranscriber()
    with patch.object(lecture_synthesizer, "WhisperModel", None), patch(
        "services.lecture_synthesizer.transcribe_audio_real",
        return_value=("", [], "TRANSCRIPTION_FAILED"),
    ):
        text, segments = transcriber.transcribe(str(wav))

    assert text == ""
    assert segments == []
    assert transcriber.last_status == "TRANSCRIPTION_FAILED"
    assert transcriber.asr_unavailable_reason == "WHISPER_NOT_INSTALLED"


def test_ensure_browser_playable_video_transcodes_wmv_and_caches(tmp_path):
    src_wmv = tmp_path / "lecture.wmv"
    src_wmv.write_bytes(b"wmv3-dummy-bytes")
    cache_dir = tmp_path / "videos_cache"

    calls = []

    def fake_run(cmd, capture_output=True, text=True, timeout=300):
        calls.append(cmd)
        out_path = Path(cmd[-1])
        out_path.write_bytes(b"\x00\x00\x00\x18ftypmp42")

        class _Res:
            returncode = 0
            stderr = ""

        return _Res()

    with patch("services.video_intelligence_service.get_ffmpeg_binary", return_value="ffmpeg"), patch(
        "services.video_intelligence_service.subprocess.run", side_effect=fake_run
    ):
        path1, mime1 = video_intelligence_service.ensure_browser_playable_video(
            str(src_wmv), "doc_vid_abc12345", cache_dir=cache_dir
        )
        path2, mime2 = video_intelligence_service.ensure_browser_playable_video(
            str(src_wmv), "doc_vid_abc12345", cache_dir=cache_dir
        )

    assert mime1 == "video/mp4"
    assert mime2 == "video/mp4"
    assert path1 == path2
    assert Path(path1).exists()
    assert len(calls) == 1

    with pytest.raises(ValueError, match="SECURITY_VIOLATION"):
        video_intelligence_service.ensure_browser_playable_video(
            str(src_wmv), "../../evil", cache_dir=cache_dir
        )

