import os
import wave
from pathlib import Path
try:
    import pytest
except ImportError:
    pytest = None
try:
    import numpy as np
except ImportError:
    np = None
from services.lecture_recorder import LectureSession
from services.lecture_synthesizer import (
    VaultLinker,
    CornellNoteSynthesizer,
    LocalTranscriber,
)


def test_vault_linker_auto_linking(tmp_path):
    vault = tmp_path / "obsidian_vault"
    vault.mkdir(parents=True, exist_ok=True)

    # Create dummy notes
    (vault / "Consensus and Raft Protocol.md").write_text("# Consensus and Raft Protocol", encoding="utf-8")
    (vault / "SQLite WAL Mode and Concurrency.md").write_text("# SQLite WAL Mode and Concurrency", encoding="utf-8")

    linker = VaultLinker(vault_root=str(vault))
    assert "consensus and raft protocol" in linker.known_concepts
    assert "sqlite wal mode and concurrency" in linker.known_concepts

    sample_text = (
        "Hoje estudamos o consensus and raft protocol em sistemas distribuídos e como "
        "o sqlite wal mode and concurrency garante leituras não-bloqueantes."
    )

    linked = linker.link_text(sample_text)
    assert "[[Consensus and Raft Protocol]]" in linked
    assert "[[SQLite WAL Mode and Concurrency]]" in linked


def test_cornell_note_generation(tmp_path):
    synthesizer = CornellNoteSynthesizer(vault_root=str(tmp_path))

    session = LectureSession(
        session_id="lec_test_01",
        subject="Engenharia de Software",
        title="Padrões de Arquitetura Limpa",
        professor="Prof. António",
        audio_path="temp_audio/test.wav",
        duration_seconds=3600.0,
    )

    segments = [
        {"start": 0.0, "end": 30.0, "timestamp": "00:00", "text": "Bem-vindos à aula de Engenharia de Software."},
        {"start": 30.0, "end": 60.0, "timestamp": "00:30", "text": "Hoje vamos discutir Clean Architecture e Hexagonal Ports."},
        {"start": 60.0, "end": 90.0, "timestamp": "01:00", "text": "A separação de responsabilidades é fundamental."},
    ]
    raw_transcript = "[00:00] Bem-vindos...\n[00:30] Hoje vamos discutir..."

    md = synthesizer.generate_cornell_notes(session, raw_transcript, segments)

    # Verify YAML Frontmatter
    assert "type: lecture_notes" in md
    assert 'subject: "Engenharia de Software"' in md
    assert 'professor: "Prof. António"' in md
    assert "duration_minutes: 60.0" in md

    # Verify Cornell Sections
    assert "# 🎓 Padrões de Arquitetura Limpa" in md
    assert "## 📝 1. Sumário Executivo (Executive Summary)" in md
    assert "## 💡 2. Cornell Cue Column & Conceitos-Chave" in md
    assert "## 📖 3. Notas Detalhadas de Conteúdo (Detailed Notes)" in md
    assert "## 📚 4. Glossário Técnico & Definições" in md
    assert "## 🎯 5. Ações, Prazos & Avaliações (Action Items & Exam Alerts)" in md
    assert "## 🎙️ 6. Transcrição com Marcas de Tempo" in md


def test_process_lecture_end_to_end(tmp_path):
    audio_dir = tmp_path / "temp_audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    wav_path = str(audio_dir / "test_lec.wav")

    # Create short silent wav file
    with wave.open(wav_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * 16000)

    vault_dir = tmp_path / "obsidian_vault"
    vault_dir.mkdir(parents=True, exist_ok=True)

    session = LectureSession(
        session_id="lec_e2e_01",
        subject="Compiladores",
        title="Análise Léxica e Autômatos",
        professor="Dra. Maria",
        audio_path=wav_path,
        duration_seconds=120.0,
    )

    synthesizer = CornellNoteSynthesizer(vault_root=str(vault_dir))
    output_md = synthesizer.process_lecture(session)

    assert os.path.exists(output_md)
    assert session.status == "COMPLETED"
    assert session.markdown_path == output_md

    content = Path(output_md).read_text(encoding="utf-8")
    assert "# 🎓 Análise Léxica e Autômatos" in content
    assert "type: lecture_notes" in content
