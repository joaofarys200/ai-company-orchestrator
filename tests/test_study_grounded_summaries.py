import asyncio
import io
import json
import struct
import wave
import zipfile
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.websocket.handlers.study import StudyWebSocketHandler
from services.lecture_synthesizer import CornellNoteSynthesizer, LectureSession, LocalTranscriber
from services.study_ai_engine import (
    LEGACY_PREFABRICATED_MARKERS,
    is_prefabricated_artifact,
)
from services.study_service import StudyService


def _make_pcm_wav_bytes(duration_sec: float = 1.2, sample_rate: int = 16000, amplitude: int = 0) -> bytes:
    buf = io.BytesIO()
    n_samples = int(duration_sec * sample_rate)
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        if amplitude == 0:
            wf.writeframes(b"\x00\x00" * n_samples)
        else:
            frames = bytearray()
            for i in range(n_samples):
                val = amplitude if (i // 40) % 2 == 0 else -amplitude
                frames.extend(struct.pack("<h", val))
            wf.writeframes(bytes(frames))
    return buf.getvalue()


def _make_minimal_pptx_bytes() -> bytes:
    slide1_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
           xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
      <p:cSld><p:spTree>
        <p:sp><p:txBody><a:p><a:r><a:t>Ciclos Brayton Supercríticos com CO2</a:t></a:r></a:p></p:txBody></p:sp>
        <p:sp><p:txBody><a:p><a:r><a:t>O dióxido de carbono supercrítico opera acima de 31.1 graus Celsius e 7.38 MPa, reduzindo drasticamente o trabalho de compressão perto do ponto crítico.</a:t></a:r></a:p></p:txBody></p:sp>
      </p:spTree></p:cSld>
    </p:sld>"""
    slide2_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
           xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
      <p:cSld><p:spTree>
        <p:sp><p:txBody><a:p><a:r><a:t>Regeneração Térmica e Eficiência</a:t></a:r></a:p></p:txBody></p:sp>
        <p:sp><p:txBody><a:p><a:r><a:t>A configuração com recompressão evita o pinch-point nos permutadores recuperadores impressos por difusão, atingindo eficiências térmicas superiores a 48 por cento.</a:t></a:r></a:p></p:txBody></p:sp>
      </p:spTree></p:cSld>
    </p:sld>"""
    notes1_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <p:notes xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
             xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
      <p:cSld><p:spTree>
        <p:sp><p:txBody><a:p><a:r><a:t>Nota do docente: destacar comparação entre turbinas a gás hélio e ciclos sCO2 em centrais solares concentradas.</a:t></a:r></a:p></p:txBody></p:sp>
      </p:spTree></p:cSld>
    </p:notes>"""

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("ppt/slides/slide1.xml", slide1_xml)
        zf.writestr("ppt/slides/slide2.xml", slide2_xml)
        zf.writestr("ppt/notesSlides/notesSlide1.xml", notes1_xml)
    return buf.getvalue()


@pytest.fixture
def isolated_study_service(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    return StudyService(workspace_root=str(ws), vault_root=str(ws / "obsidian_vault"))


def _assert_zero_prefabricated_markers(payload) -> None:
    serialized = json.dumps(payload, ensure_ascii=False).lower()
    for marker in LEGACY_PREFABRICATED_MARKERS:
        assert marker not in serialized, f"Prefabricated marker found: {marker!r}"
    assert not is_prefabricated_artifact(payload)


def test_text_document_summaries_cornell_structure_and_multidoc_are_content_grounded(isolated_study_service):
    text_a = (
        "# Fotocatálise Heterogénea com Dióxido de Titânio\n\n"
        "A fotocatálise com nanopartículas de dióxido de titânio (TiO2) na fase anatase permite degradar "
        "poluentes orgânicos persistentes como a Rodamina B sob radiação ultravioleta de 365 nanómetros.\n\n"
        "# Metodologia Experimental e Cinética\n\n"
        "Foram sintetizados catalisadores dopados com azoto por sol-gel, avaliados num fotorreator anelar "
        "durante 120 minutos. A constante cinética de pseudo-primeira ordem atingiu 0.042 min^-1.\n\n"
        "# Resultados e Limitações\n\n"
        "Observou-se mineralização de 91% do carbono orgânico total após quatro ciclos de reutilização, "
        "embora a recombinação eletrão-lacuna limite o rendimento quântico em luz visível pura."
    )
    text_b = (
        "# Membranas de Grafeno Nanoporous na Dessalinização\n\n"
        "As membranas monocamada de grafeno com poros sub-nanométricos funcionalizados com grupos hidroxilo "
        "permitem rejeição de iões cloreto de sódio acima de 99.2% em processos de osmose inversa.\n\n"
        "# Simulação de Dinâmica Molecular e Permeabilidade\n\n"
        "Simulações LAMMPS demonstraram fluxos hidráulicos duas ordens de grandeza superiores às membranas "
        "poliméricas de poliamida tradicionais sob pressões transmembranares de 5 MPa."
    )

    doc_a = isolated_study_service.ingest_document(
        text_a.encode("utf-8"),
        "fotocatalise_tio2.md",
        subject="Engenharia Química",
    )
    doc_b = isolated_study_service.ingest_document(
        text_b.encode("utf-8"),
        "membranas_grafeno.md",
        subject="Engenharia de Materiais",
    )

    for doc, expected_terms in [
        (doc_a, ["tio2", "rodamina", "anatase", "fotocatálise"]),
        (doc_b, ["grafeno", "dessalinização", "osmose", "poliamida"]),
    ]:
        _assert_zero_prefabricated_markers(doc.to_dict())
        sums = doc.metadata.get("summaries")
        assert isinstance(sums, dict)
        assert isinstance(sums.get("quick"), list) and len(sums["quick"]) >= 2
        assert isinstance(sums.get("study"), list) and len(sums["study"]) >= 2
        assert isinstance(sums.get("detailed"), list) and len(sums["detailed"]) >= 1
        assert isinstance(sums.get("exam"), dict)
        assert len(sums["exam"].get("high_yield_concepts", [])) >= 1
        assert len(sums["exam"].get("likely_questions", [])) >= 1

        dump = json.dumps(sums, ensure_ascii=False).lower()
        assert any(term in dump for term in expected_terms), f"Expected domain terms {expected_terms} in {dump}"

        cornell = isolated_study_service.generate_cornell_from_document(doc.document_id)
        _assert_zero_prefabricated_markers(cornell)
        cornell_dump = json.dumps(cornell, ensure_ascii=False).lower()
        assert any(term in cornell_dump for term in expected_terms)

    # All 4 explicit generate_summary modes
    for mode in ("Quick", "Study", "Detailed", "Exam"):
        res = isolated_study_service.generate_summary(doc_a.document_id, mode=mode)
        _assert_zero_prefabricated_markers(res)
        assert res["mode"] == mode

    # Multi-doc synthesis
    multi = isolated_study_service.synthesize_documents([doc_a.document_id, doc_b.document_id])
    _assert_zero_prefabricated_markers(multi)
    multi_dump = json.dumps(multi, ensure_ascii=False).lower()
    assert any(t in multi_dump for t in ["tio2", "fotocatálise", "rodamina"])
    assert any(t in multi_dump for t in ["grafeno", "osmose", "poliamida"])

    # Vault export uses real concepts, zero hardcoded Transformer/Attention wikilinks
    vault_file = isolated_study_service.save_to_knowledge_vault(
        title="Revisão Fotocatálise",
        content="Síntese sobre degradação fotocatalítica com TiO2.",
        subject="Engenharia Química",
        source_document_ids=[doc_a.document_id],
    )
    saved_md = open(vault_file, encoding="utf-8").read()
    assert "Mecanismo de Atenção" not in saved_md
    assert "Arquitetura Transformer" not in saved_md


def test_pptx_ingestion_extracts_slides_and_speaker_notes(isolated_study_service):
    pptx_bytes = _make_minimal_pptx_bytes()
    doc = isolated_study_service.ingest_document(
        pptx_bytes,
        "ciclo_brayton_sco2.pptx",
        subject="Termodinâmica",
    )
    assert doc.source_type == "PPTX"
    assert doc.page_count == 2
    assert "Brayton" in doc.extracted_text
    assert "7.38 MPa" in doc.extracted_text
    assert "centrais solares concentradas" in doc.extracted_text
    _assert_zero_prefabricated_markers(doc.to_dict())

    sums_dump = json.dumps(doc.metadata.get("summaries"), ensure_ascii=False).lower()
    assert "brayton" in sums_dump or "supercrítico" in sums_dump or "compressão" in sums_dump


def test_silent_audio_never_fabricates_fake_classroom_transcript(isolated_study_service, tmp_path):
    silent_wav = _make_pcm_wav_bytes(duration_sec=1.0, amplitude=0)
    wav_file = tmp_path / "silent.wav"
    wav_file.write_bytes(silent_wav)

    transcriber = LocalTranscriber()
    transcript, segs = transcriber.transcribe(str(wav_file))
    assert transcript == ""
    assert segs == []
    assert "Transcrição de teste" not in transcript

    synth = CornellNoteSynthesizer(vault_root=str(tmp_path / "vault"))
    session = LectureSession(
        session_id="lec_silent_01",
        title="Aula Silenciosa",
        subject="Física",
        audio_path=str(wav_file),
    )
    notes = synth.generate_cornell_notes(session, "", [])
    _assert_zero_prefabricated_markers(notes)

    audio_doc = isolated_study_service.ingest_document(
        silent_wav,
        "gravacao_silenciosa.wav",
        subject="Física",
    )
    assert audio_doc.source_type == "AUDIO"
    _assert_zero_prefabricated_markers(audio_doc.to_dict())
    assert "Transcrição de teste" not in audio_doc.extracted_text


def test_speech_audio_ingestion_builds_grounded_timestamped_sections_and_summaries(
    isolated_study_service, monkeypatch
):
    fake_asr_output = (
        (
            "A equação de Michaelis-Menten descreve a velocidade inicial de reações catalisadas por enzimas "
            "em função da concentração de substrato. A constante Km corresponde à concentração de substrato "
            "na qual a velocidade de reação atinge metade da velocidade máxima Vmax. Inibidores competitivos "
            "aumentam o valor aparente de Km sem alterar Vmax."
        ),
        [
            {
                "id": 0,
                "start": 0.0,
                "end": 12.5,
                "text": "A equação de Michaelis-Menten descreve a velocidade inicial de reações catalisadas por enzimas em função da concentração de substrato.",
                "confidence": 0.96,
            },
            {
                "id": 1,
                "start": 12.5,
                "end": 26.0,
                "text": "A constante Km corresponde à concentração de substrato na qual a velocidade de reação atinge metade da velocidade máxima Vmax.",
                "confidence": 0.95,
            },
            {
                "id": 2,
                "start": 26.0,
                "end": 38.0,
                "text": "Inibidores competitivos aumentam o valor aparente de Km sem alterar Vmax.",
                "confidence": 0.97,
            },
        ],
        "TRANSCRIBED_WHISPER",
    )
    monkeypatch.setattr("services.study_service.transcribe_audio_real", lambda *_a, **_kw: fake_asr_output)

    wav_bytes = _make_pcm_wav_bytes(duration_sec=1.5, amplitude=4000)
    doc = isolated_study_service.ingest_document(
        wav_bytes,
        "cinetica_enzimatica.wav",
        subject="Bioquímica",
    )

    assert doc.source_type == "AUDIO"
    assert "Michaelis-Menten" in doc.extracted_text
    assert "Vmax" in doc.extracted_text
    _assert_zero_prefabricated_markers(doc.to_dict())

    sums_dump = json.dumps(doc.metadata.get("summaries"), ensure_ascii=False).lower()
    assert "michaelis" in sums_dump or "vmax" in sums_dump or "enzima" in sums_dump


def test_ingest_video_url_supports_v124_youtube_transcript_api_and_rejects_fake_fallback(
    isolated_study_service, monkeypatch
):
    class FakeFetchedSnippet:
        def __init__(self, text: str, start: float, duration: float):
            self.text = text
            self.start = start
            self.duration = duration

    class FakeYouTubeTranscriptApiSuccess:
        def fetch(self, video_id, languages=None):
            assert video_id == "dQw4w9WgXcQ"
            return [
                FakeFetchedSnippet(
                    "O teorema de Bayes atualiza probabilidades a priori à luz de nova evidência condicional.",
                    0.0,
                    8.0,
                ),
                FakeFetchedSnippet(
                    "Na inferência variacional aproximamos a distribuição posterior minimizando a divergência de Kullback-Leibler.",
                    8.0,
                    10.0,
                ),
            ]

    monkeypatch.setattr(
        "youtube_transcript_api.YouTubeTranscriptApi",
        FakeYouTubeTranscriptApiSuccess,
    )

    doc = isolated_study_service.ingest_video_url(
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        subject="Estatística Bayesiana",
        custom_title="Inferência Bayesiana e Variacional",
    )
    assert doc.source_type == "VIDEO"
    assert "Kullback-Leibler" in doc.extracted_text
    _assert_zero_prefabricated_markers(doc.to_dict())
    sums_dump = json.dumps(doc.metadata.get("summaries"), ensure_ascii=False).lower()
    assert "bayes" in sums_dump or "kullback" in sums_dump or "variacional" in sums_dump

    # Failure case: must raise honest ValueError instead of fabricating fake 3-line lecture transcript
    class FakeYouTubeTranscriptApiFail:
        def fetch(self, video_id, languages=None):
            raise RuntimeError("Subtitles disabled for this video")

        def list(self, video_id):
            raise RuntimeError("Subtitles disabled for this video")

    monkeypatch.setattr(
        "youtube_transcript_api.YouTubeTranscriptApi",
        FakeYouTubeTranscriptApiFail,
    )

    with pytest.raises(ValueError):
        isolated_study_service.ingest_video_url(
            "https://www.youtube.com/watch?v=00000000000",
            subject="Estatística",
        )


def test_websocket_study_handler_generate_summary_and_synthesize_echo_request_id(isolated_study_service):
    doc1 = isolated_study_service.ingest_document(
        (
            "# Protocolos QUIC sobre UDP\n\n"
            "O protocolo QUIC integra TLS 1.3 diretamente no handshake de transporte sobre UDP, "
            "eliminando o bloqueio head-of-line ao nível das streams multiplexadas no HTTP/3."
        ).encode("utf-8"),
        "quic_http3.md",
        subject="Redes de Computadores",
    )
    doc2 = isolated_study_service.ingest_document(
        (
            "# Controlo de Congestionamento BBR\n\n"
            "O algoritmo BBR estima continuamente a largura de banda de gargalo e o RTT mínimo de propagação "
            "para operar no ponto ótimo de Kleinrock sem encher filas intermédias."
        ).encode("utf-8"),
        "bbr_congestion.md",
        subject="Redes de Computadores",
    )

    connections = MagicMock()
    connections.send = AsyncMock()
    connections.broadcast = AsyncMock()

    handler = StudyWebSocketHandler(connections=connections, study_service=isolated_study_service)
    ws = object()
    session = SimpleNamespace()

    asyncio.run(
        handler.generate_summary(
            ws,
            {
                "type": "study_generate_summary",
                "document_id": doc1.document_id,
                "mode": "Exam",
                "force_regenerate": True,
                "request_id": "req_sum_123",
            },
            session,
        )
    )

    assert connections.broadcast.await_count == 1
    b_payload = connections.broadcast.await_args.args[0]
    assert b_payload["type"] == "study_document_ready"
    assert b_payload["document"]["document_id"] == doc1.document_id

    s_payload = connections.send.await_args.args[1]
    assert s_payload["type"] == "study_summary_ready"
    assert s_payload["request_id"] == "req_sum_123"
    assert s_payload["mode"] == "Exam"
    assert "quick" in s_payload["summaries"] and "study" in s_payload["summaries"]
    _assert_zero_prefabricated_markers(s_payload)

    connections.send.reset_mock()
    asyncio.run(
        handler.synthesize_documents(
            ws,
            {
                "type": "study_synthesize_documents",
                "document_ids": [doc1.document_id, doc2.document_id],
                "request_id": "req_synth_456",
            },
            session,
        )
    )
    synth_payload = connections.send.await_args.args[1]
    assert synth_payload["type"] == "study_synthesis_ready"
    assert synth_payload["request_id"] == "req_synth_456"
    _assert_zero_prefabricated_markers(synth_payload)
    synth_dump = json.dumps(synth_payload, ensure_ascii=False).lower()
    assert "quic" in synth_dump or "bbr" in synth_dump
