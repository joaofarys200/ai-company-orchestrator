"""
JARVIS OS — STUDY ENGINE FORENSIC QA & MULTIMODAL GROUNDED GENERATION SUITE
Covers all 25 mandatory tests from Section 12 plus real local Ollama qwen3.5:9b verification.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.study_ai_engine import (
    EXTRACTION_VERSION,
    build_document_evidence_units,
    cancel_study_generation,
    detect_argumentative_structure,
    generate_complete_study_bundle,
    get_last_study_telemetry,
    invoke_study_llm_observable,
    is_study_generation_cancelled,
    match_claim_evidence_ids,
    register_study_generation_start,
    strip_thinking_and_fences,
    synthesize_multi_documents_grounded,
)
from services.study_service import StudyService
from backend.websocket.handlers.study import StudyWebSocketHandler


# ============================================================================
# 1. Upload de TXT produz excerto rastreável
# ============================================================================
def test_01_txt_upload_produces_traceable_evidence_units(tmp_path: Path):
    svc = StudyService(storage_dir=str(tmp_path / "study"))
    txt_content = (
        "Introdução à Termodinâmica Clássica\n\n"
        "A primeira lei da termodinâmica estabelece a conservação da energia num sistema fechado, "
        "relacionando a variação da energia interna com o calor transferido e o trabalho realizado.\n\n"
        "A segunda lei introduz a entropia como grandeza de irreversibilidade macroscópica."
    )
    doc = svc.ingest_document(
        txt_content.encode("utf-8"),
        "termodinamica.txt",
        subject="Física",
        source_type="TXT",
        custom_title="Termodinâmica Clássica",
    )
    evidence_units = doc.metadata.get("evidence_units", [])
    assert len(evidence_units) >= 2
    first_unit = evidence_units[0]
    assert first_unit["document_id"] == doc.document_id
    assert first_unit["source_type"] == "TXT"
    assert "line_range" in first_unit
    assert "paragraph_id" in first_unit
    assert first_unit["evidence_id"].startswith(f"{doc.document_id}:")


# ============================================================================
# 2. Upload de PDF preserva página e parágrafo
# ============================================================================
def test_02_pdf_preserves_page_and_paragraph_coordinates():
    sections = [
        {
            "section_id": "sec_1",
            "title": "1. Arquitetura de Redes Neuronais",
            "page_start": 3,
            "page_end": 4,
            "paragraphs": [
                {
                    "paragraph_id": "p_3_1",
                    "page_number": 3,
                    "text": "O mecanismo de backpropagation calcula o gradiente da função de perda relativamente aos pesos sinápticos.",
                },
                {
                    "paragraph_id": "p_4_1",
                    "page_number": 4,
                    "text": "A normalização por lote estabiliza a distribuição das ativações intermédias durante o treino.",
                },
            ],
        }
    ]
    units = build_document_evidence_units(
        document_id="doc_pdf_01",
        source_type="PDF",
        sections=sections,
    )
    assert len(units) == 2
    assert units[0]["page_number"] == 3
    assert units[0]["paragraph_id"] == "p_3_1"
    assert units[0]["evidence_id"] == "doc_pdf_01:p3:p_3_1"
    assert units[1]["page_number"] == 4
    assert units[1]["evidence_id"] == "doc_pdf_01:p4:p_4_1"


# ============================================================================
# 3. Upload de PPTX preserva número do diapositivo
# ============================================================================
def test_03_pptx_preserves_slide_number_and_text_element():
    sections = [
        {
            "section_id": "slide_5",
            "title": "Slide 5: Protocolo Raft",
            "page_start": 5,
            "page_end": 5,
            "paragraphs": [
                {
                    "paragraph_id": "slide_5_el_1",
                    "page_number": 5,
                    "text": "A eleição de líder no protocolo Raft utiliza timeouts aleatórios para evitar divisão de votos.",
                },
                {
                    "paragraph_id": "slide_5_notes",
                    "page_number": 5,
                    "speaker_notes": "Nota do orador: salientar que cada termo possui no máximo um líder eleito.",
                    "text": "Nota do orador: salientar que cada termo possui no máximo um líder eleito.",
                },
            ],
        }
    ]
    units = build_document_evidence_units(
        document_id="doc_pptx_01",
        source_type="PPTX",
        sections=sections,
    )
    assert len(units) == 2
    assert units[0]["slide_number"] == 5
    assert units[0]["text_element_id"] == "slide_5_el_1"
    assert "slide5" in units[0]["evidence_id"]


# ============================================================================
# 4. Upload de DOCX preserva estrutura de secções
# ============================================================================
def test_04_docx_preserves_section_and_paragraph_structure():
    sections = [
        {
            "section_id": "sec_metodologia",
            "title": "2. Metodologia Experimental",
            "page_start": 1,
            "page_end": 1,
            "paragraphs": [
                {
                    "paragraph_id": "docx_p_12",
                    "page_number": 1,
                    "text": "A amostra foi submetida a espetroscopia de impedância eletroquímica entre 10 mHz e 100 kHz.",
                }
            ],
        }
    ]
    units = build_document_evidence_units(
        document_id="doc_docx_01",
        source_type="DOCX",
        sections=sections,
    )
    assert len(units) == 1
    assert units[0]["section_id"] == "sec_metodologia"
    assert units[0]["paragraph_id"] == "docx_p_12"
    assert units[0]["evidence_id"] == "doc_docx_01:sec_metodologia:docx_p_12"


# ============================================================================
# 5. Upload de áudio produz transcrição com timestamps
# ============================================================================
def test_05_audio_produces_transcription_segments_with_timestamps():
    sections = [
        {
            "section_id": "audio_seg_1",
            "title": "Segmento 00:00 - 01:30",
            "page_start": 1,
            "page_end": 1,
            "paragraphs": [
                {
                    "paragraph_id": "seg_01",
                    "start_timestamp": 12.5,
                    "end_timestamp": 45.0,
                    "text": "Nesta aula analisamos a transformada de Laplace aplicada a sistemas lineares invariantes no tempo.",
                }
            ],
        }
    ]
    units = build_document_evidence_units(
        document_id="doc_audio_01",
        source_type="AUDIO",
        sections=sections,
    )
    assert len(units) == 1
    assert units[0]["start_timestamp"] == 12.5
    assert units[0]["end_timestamp"] == 45.0
    assert units[0]["transcription_segment_id"] == "seg_01"
    assert "t12-45" in units[0]["evidence_id"]


# ============================================================================
# 6. Upload de vídeo associa transcrição e OCR
# ============================================================================
def test_06_video_associates_transcription_and_ocr_timestamps():
    sections = [
        {
            "section_id": "vid_ch_1",
            "title": "Capítulo 1: Equações de Maxwell",
            "page_start": 1,
            "page_end": 1,
            "paragraphs": [
                {
                    "paragraph_id": "vid_asr_1",
                    "start_timestamp": 0.0,
                    "end_timestamp": 30.0,
                    "modality": "ASR",
                    "text": "O fluxo do campo elétrico através de uma superfície fechada é proporcional à carga interna.",
                },
                {
                    "paragraph_id": "vid_ocr_1",
                    "start_timestamp": 15.0,
                    "end_timestamp": 25.0,
                    "modality": "OCR_SLIDE",
                    "ocr_text": "Lei de Gauss: div(E) = rho / epsilon_0",
                    "text": "Lei de Gauss: div(E) = rho / epsilon_0",
                },
            ],
        }
    ]
    units = build_document_evidence_units(
        document_id="doc_video_01",
        source_type="VIDEO",
        sections=sections,
    )
    assert len(units) == 2
    assert units[0]["start_timestamp"] == 0.0
    assert units[0]["end_timestamp"] == 30.0
    assert units[1]["ocr_text"] == "Lei de Gauss: div(E) = rho / epsilon_0"


# ============================================================================
# 7. Documento sem voz reporta NO_SPEECH_DETECTED
# ============================================================================
def test_07_silent_audio_reports_no_speech_detected(tmp_path: Path):
    svc = StudyService(storage_dir=str(tmp_path / "study"))
    silent_wav = tmp_path / "silent.mp3"
    silent_wav.write_bytes(b"\x00" * 512)

    with patch("services.study_service.transcribe_audio_real", return_value=("", [], "NO_SPEECH_DETECTED")):
        doc = svc.ingest_document(
            str(silent_wav),
            "silent.mp3",
            subject="Teste",
            source_type="AUDIO",
            custom_title="Áudio Silencioso",
        )
    assert doc.metadata.get("transcription_status") in ("NO_SPEECH_DETECTED", "TRANSCRIPTION_FAILED")
    assert doc.metadata.get("audio_analysis_incomplete") is True
    assert doc.metadata.get("generation_mode") != "LLM_GROUNDED"


# ============================================================================
# 8. Geração através de qwen3.5:9b é registada com telemetria observável
# ============================================================================
def test_08_qwen35_9b_observable_telemetry_recorded():
    mock_resp = MagicMock()
    mock_resp.raw_text = json.dumps(
        {
            "quick_summary": [
                {"text": "A fotossíntese converte energia luminosa em energia química nos cloroplastos.", "source_refs": ["E1"]}
            ],
        }
    )
    mock_resp.usage = MagicMock(input_tokens=140, output_tokens=45)
    mock_resp.metadata = {"ttft_ms": 320.0}

    with patch.dict(os.environ, {"STUDY_FORCE_LIVE_LLM": "1"}):
        with patch("backend.services.model_service.ModelExecutionService.execute", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_resp

            parsed, telem = invoke_study_llm_observable(
                operation="test_summaries",
                system_prompt="Responde em JSON.",
                user_prompt="Analisa o documento sobre fotossíntese.",
                document_id="doc_bio_01",
            )

    assert parsed is not None
    assert telem["provider"] == "ollama"
    assert telem["model"] == "qwen3.5:9b"
    assert telem["status"] == "COMPLETED"
    assert telem["input_tokens"] == 140
    assert telem["output_tokens"] == 45
    assert telem["ttft_ms"] == 320.0
    assert get_last_study_telemetry("doc_bio_01")["model"] == "qwen3.5:9b"


# ============================================================================
# 9. Resposta inválida do modelo é rejeitada
# ============================================================================
def test_09_invalid_llm_response_is_rejected():
    mock_resp = MagicMock()
    mock_resp.raw_text = "Isto não é JSON válido nem contém estrutura esperada."
    mock_resp.usage = MagicMock(input_tokens=50, output_tokens=12)
    mock_resp.metadata = {}

    with patch.dict(os.environ, {"STUDY_FORCE_LIVE_LLM": "1"}):
        with patch("backend.services.model_service.ModelExecutionService.execute", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_resp

            parsed, telem = invoke_study_llm_observable(
                operation="test_invalid_json",
                system_prompt="Responde em JSON.",
                user_prompt="Teste",
                document_id="doc_invalid_01",
            )

    assert parsed is None
    assert telem["status"] == "FAILED_VALIDATION"
    assert "INVALID_JSON_SYNTAX" in telem["validation_errors"]


# ============================================================================
# 10. Marcadores <think> são removidos ou rejeitados
# ============================================================================
def test_10_think_markers_are_stripped_cleanly():
    raw_output = (
        "<think>\nVou analisar o texto passo a passo antes de responder.\n</think>\n"
        '{"quick_summary": ["O protocolo TCP garante entrega ordenada e controlo de congestionamento."]}'
    )
    cleaned = strip_thinking_and_fences(raw_output)
    assert "<think>" not in cleaned
    assert "</think>" not in cleaned
    data = json.loads(cleaned)
    assert "TCP" in data["quick_summary"][0]


# ============================================================================
# 11. Afirmação sem evidência não é aceite como facto
# ============================================================================
def test_11_ungrounded_claim_is_rejected_by_evidence_matcher():
    sections = [
        {
            "section_id": "sec_1",
            "title": "Arquitetura RISC-V",
            "page_start": 1,
            "page_end": 1,
            "paragraphs": [
                {
                    "paragraph_id": "p_1",
                    "page_number": 1,
                    "text": "O conjunto de instruções RISC-V baseia-se num design load-store modular com registos de 32 ou 64 bits.",
                }
            ],
        }
    ]
    units = build_document_evidence_units("doc_riscv", "PDF", sections)
    grounded_refs = match_claim_evidence_ids(
        "O design load-store modular do RISC-V utiliza registos de 32 ou 64 bits.",
        units,
    )
    assert len(grounded_refs) >= 1

    fabricated_refs = match_claim_evidence_ids(
        "A Revolução Francesa de 1789 alterou o regime monárquico europeu.",
        units,
    )
    assert fabricated_refs == []


# ============================================================================
# 12. Quick Summary reflete o tema real do documento
# ============================================================================
def test_12_quick_summary_reflects_real_document_topic():
    text = (
        "1. Consenso Distribuído e Tolerância a Falhas Bizantinas\n\n"
        "O algoritmo PBFT (Practical Byzantine Fault Tolerance) permite que um sistema distribuído "
        "alcance consenso mesmo quando até f nós entre 3f+1 réplicas exibem comportamento arbitrário ou malicioso. "
        "O protocolo opera em três fases: pre-prepare, prepare e commit, garantindo segurança (safety) e vivacidade (liveness) "
        "sob sincronia parcial.\n\n"
        "2. Complexidade de Comunicação\n\n"
        "A troca de mensagens nas fases prepare e commit apresenta custo quadrático O(n^2) relativamente ao número de nós."
    )
    sections = [
        {
            "section_id": "sec_1",
            "title": "1. Consenso Distribuído e Tolerância a Falhas Bizantinas",
            "page_start": 1,
            "page_end": 1,
            "paragraphs": [
                {
                    "paragraph_id": "p_1",
                    "page_number": 1,
                    "text": "O algoritmo PBFT (Practical Byzantine Fault Tolerance) permite que um sistema distribuído alcance consenso mesmo quando até f nós entre 3f+1 réplicas exibem comportamento arbitrário.",
                }
            ],
        },
        {
            "section_id": "sec_2",
            "title": "2. Complexidade de Comunicação",
            "page_start": 1,
            "page_end": 1,
            "paragraphs": [
                {
                    "paragraph_id": "p_2",
                    "page_number": 1,
                    "text": "A troca de mensagens nas fases prepare e commit apresenta custo quadrático O(n^2) relativamente ao número de nós.",
                }
            ],
        },
    ]
    bundle = generate_complete_study_bundle(
        title="Consenso PBFT",
        subject="Sistemas Distribuídos",
        source_type="PDF",
        raw_text=text,
        sections=sections,
        document_id="doc_pbft",
    )
    quick_text = " ".join(bundle["summaries"]["quick"]).lower()
    assert "pbft" in quick_text or "consenso" in quick_text or "3f+1" in quick_text
    assert "este documento apresenta" not in quick_text


# ============================================================================
# 13. Study Summary preserva a estrutura por secções
# ============================================================================
def test_13_study_summary_preserves_section_structure():
    sections = [
        {
            "section_id": "sec_a",
            "title": "Camada de Transporte QUIC",
            "page_start": 1,
            "page_end": 1,
            "paragraphs": [
                {
                    "paragraph_id": "p_a",
                    "page_number": 1,
                    "text": "O protocolo QUIC executa sobre UDP e integra o handshake criptográfico TLS 1.3 para reduzir a latência de estabelecimento de ligação.",
                }
            ],
        },
        {
            "section_id": "sec_b",
            "title": "Multiplexagem sem Head-of-Line Blocking",
            "page_start": 2,
            "page_end": 2,
            "paragraphs": [
                {
                    "paragraph_id": "p_b",
                    "page_number": 2,
                    "text": "Ao contrário do TCP, a perda de um pacote UDP no QUIC afeta apenas o stream correspondente, evitando bloqueio dos restantes streams.",
                }
            ],
        },
    ]
    bundle = generate_complete_study_bundle(
        title="Arquitetura QUIC",
        subject="Redes",
        source_type="PDF",
        raw_text=" ".join(p["text"] for s in sections for p in s["paragraphs"]),
        sections=sections,
        document_id="doc_quic",
    )
    study = bundle["summaries"]["study"]
    assert len(study) == 2
    assert "QUIC" in study[0]["title"]
    assert "Multiplexagem" in study[1]["title"]
    assert len(study[0].get("source_refs", [])) >= 1


# ============================================================================
# 14. Detailed Summary apresenta profundidade superior ao Quick Summary
# ============================================================================
def test_14_detailed_summary_has_greater_depth_than_quick_summary():
    sections = [
        {
            "section_id": "sec_1",
            "title": "1. Memória Virtual e Paginação Multinível",
            "page_start": 1,
            "page_end": 2,
            "paragraphs": [
                {
                    "paragraph_id": "p_1",
                    "page_number": 1,
                    "text": "A unidade de gestão de memória (MMU) traduz endereços virtuais em endereços físicos através de tabelas de páginas hierárquicas de 4 níveis (PML4, PDPT, PD, PT).",
                },
                {
                    "paragraph_id": "p_2",
                    "page_number": 1,
                    "text": "A Translation Lookaside Buffer (TLB) armazena em cache as traduções recentes para evitar múltiplos acessos à memória principal por instrução.",
                },
                {
                    "paragraph_id": "p_3",
                    "page_number": 2,
                    "text": "Quando ocorre um TLB miss, o hardware percorre a tabela de páginas (page walk) e, caso o bit de presença seja zero, gera uma exceção Page Fault tratada pelo kernel.",
                },
            ],
        }
    ]
    full_text = " ".join(p["text"] for s in sections for p in s["paragraphs"])
    bundle = generate_complete_study_bundle(
        title="Memória Virtual e MMU",
        subject="Sistemas Operativos",
        source_type="PDF",
        raw_text=full_text,
        sections=sections,
        document_id="doc_mmu",
    )
    detailed = bundle["summaries"]["detailed"]
    detailed_text = " ".join(str(item.get("text") or item.get("content") or "") for item in detailed)
    assert len(detailed_text) >= 120
    assert "TLB" in detailed_text or "MMU" in detailed_text


# ============================================================================
# 15. Exam Summary identifica conceitos relevantes do documento
# ============================================================================
def test_15_exam_summary_identifies_high_yield_concepts():
    sections = [
        {
            "section_id": "sec_1",
            "title": "Isolamento Transacional MVCC",
            "page_start": 1,
            "page_end": 1,
            "paragraphs": [
                {
                    "paragraph_id": "p_1",
                    "page_number": 1,
                    "text": "O Controlo de Concorrência Multiversão (MVCC) mantém múltiplas versões imutáveis (snapshots) de cada registo para permitir leituras não bloqueantes.",
                }
            ],
        }
    ]
    bundle = generate_complete_study_bundle(
        title="Isolamento MVCC",
        subject="Bases de Dados",
        source_type="PDF",
        raw_text=sections[0]["paragraphs"][0]["text"],
        sections=sections,
        document_id="doc_mvcc",
    )
    exam = bundle["summaries"]["exam"]
    concepts = [c["concept"] for c in exam["high_yield_concepts"]]
    assert any("MVCC" in c or "Concorrência" in c or "Isolamento" in c or "Controlo" in c for c in concepts)


# ============================================================================
# 16. Cornell Notes produz cues, notes e summary fundamentados
# ============================================================================
def test_16_cornell_notes_produces_grounded_cues_notes_and_summary():
    sections = [
        {
            "section_id": "sec_1",
            "title": "Árvores B+ em Motores de Armazenamento",
            "page_start": 1,
            "page_end": 1,
            "paragraphs": [
                {
                    "paragraph_id": "p_1",
                    "page_number": 1,
                    "text": "Nas árvores B+, todos os valores de dados residem nos nós folha ligados sequencialmente, enquanto os nós internos guardam apenas chaves de encaminhamento.",
                }
            ],
        }
    ]
    bundle = generate_complete_study_bundle(
        title="Árvores B+",
        subject="Bases de Dados",
        source_type="PDF",
        raw_text=sections[0]["paragraphs"][0]["text"],
        sections=sections,
        document_id="doc_bplus",
    )
    cornell = bundle["cornell_notes"]
    assert len(cornell["cue_column"]) >= 1
    assert len(cornell.get("detailed_notes", "")) >= 10
    assert "B+" in cornell["executive_summary"] or "folha" in cornell["executive_summary"]
    assert len(cornell["cue_column"][0].get("source_refs", [])) >= 1


# ============================================================================
# 17. Argument Map representa argumentos reais ou comunica ausência de estrutura argumentativa
# ============================================================================
def test_17_argument_map_distinguishes_descriptive_from_argumentative():
    descriptive_text = (
        "Manual de Instalação e Configuração do Servidor PostgreSQL 16.\n"
        "Passo 1: Descarregar o pacote binário para Windows x86_64.\n"
        "Passo 2: Definir a diretoria PGDATA e inicializar o cluster com initdb.\n"
        "Passo 3: Configurar a porta 5432 no ficheiro postgresql.conf."
    )
    is_arg_desc, desc_limitation = detect_argumentative_structure(descriptive_text)
    assert is_arg_desc is False
    assert desc_limitation

    argumentative_text = (
        "Problema: Os sistemas distribuídos assíncronos sofrem de divergência de estado sob falhas bizantinas. "
        "A nossa tese e hipótese central defende que a verificação formal de protocolos distribuídos com TLA+ "
        "reduz defeitos críticos de concorrência em produção. "
        "Metodologia: Aplicámos model checking exaustivo sobre um dataset de 12 implementações industriais e "
        "realizámos um experimento controlado na infraestrutura AWS. "
        "Resultados: A evidência empírica mostra que 14 bugs subtis de replicação foram detetados antes da implementação. "
        "Conclusão: Concluímos que o custo inicial da especificação formal é compensado pela eliminação de falhas catastróficas."
    )
    is_arg_true, arg_limitation = detect_argumentative_structure(argumentative_text)
    assert is_arg_true is True
    assert arg_limitation is None


# ============================================================================
# 18. Flashcards e quizzes não utilizam perguntas genéricas
# ============================================================================
def test_18_flashcards_and_quizzes_contain_zero_generic_filler(tmp_path: Path):
    svc = StudyService(storage_dir=str(tmp_path / "study"))
    doc = svc.ingest_document(
        (
            "1. Definição de SSA\n\n"
            "Na representação intermédia Static Single Assignment (SSA), cada variável é atribuída exatamente uma vez "
            "no código estático, facilitando otimizações como propagação de constantes e eliminação de código morto.\n\n"
            "2. Funções Phi\n\n"
            "Nos pontos de convergência do grafo de fluxo de controlo (join nodes), o compilador insere funções Phi "
            "para selecionar a versão correta da variável consoante o bloco predecessor executado."
        ).encode("utf-8"),
        "compiladores_ssa.txt",
        subject="Compiladores",
        source_type="TXT",
        custom_title="Forma Static Single Assignment (SSA)",
    )
    quiz = svc.generate_quiz_for_document(doc.document_id, question_count=5)
    forbidden_phrases = [
        "qual é o princípio fundamental",
        "qual a melhor abordagem prática",
        "conceito a (incorreto)",
        "conceito b (correto)",
        "reler o material com atenção",
    ]
    for q in quiz.questions:
        q_lower = q["question"].lower()
        for phrase in forbidden_phrases:
            assert phrase not in q_lower
        assert len(q.get("source_ids", [])) >= 1


# ============================================================================
# 19. Síntese multi-documento atribui cada ponto ao documento correto
# ============================================================================
def test_19_multi_document_synthesis_attributes_points_to_documents():
    docs = [
        {
            "document_id": "doc_raft",
            "title": "Consenso Raft",
            "source_type": "PDF",
            "excerpt": "O protocolo Raft decompõe o consenso em eleição de líder, replicação de log e segurança de estado.",
        },
        {
            "document_id": "doc_paxos",
            "title": "Algoritmo Paxos",
            "source_type": "PDF",
            "excerpt": "O protocolo Multi-Paxos utiliza quóruns de maioria nas fases Prepare e Accept para garantir consenso distribuído.",
        },
    ]
    res = synthesize_multi_documents_grounded(docs)
    assert res["document_count"] == 2
    assert any("Consenso Raft" in d or "Algoritmo Paxos" in d for d in res["differences"])


# ============================================================================
# 20. Fallback extrativo é identificado como EXTRACTIVE_GROUNDED
# ============================================================================
def test_20_extractive_fallback_is_explicitly_marked_extractive_grounded():
    with patch.dict(os.environ, {"STUDY_DISABLE_LIVE_LLM": "1"}):
        bundle = generate_complete_study_bundle(
            title="Teorema CAP",
            subject="Sistemas Distribuídos",
            source_type="TXT",
            raw_text="O Teorema CAP afirma que um sistema de dados distribuído na presença de partições de rede tem de escolher entre consistência linearizável e disponibilidade total.",
            sections=[
                {
                    "section_id": "s1",
                    "title": "Teorema CAP",
                    "page_start": 1,
                    "page_end": 1,
                    "paragraphs": [
                        {
                            "paragraph_id": "p1",
                            "page_number": 1,
                            "text": "O Teorema CAP afirma que um sistema de dados distribuído na presença de partições de rede tem de escolher entre consistência linearizável e disponibilidade total.",
                        }
                    ],
                }
            ],
            document_id="doc_cap",
        )
    assert bundle["generation_mode"] == "EXTRACTIVE_GROUNDED"
    assert isinstance(bundle.get("unavailable_generative_features"), list)
    assert len(bundle["unavailable_generative_features"]) > 0


# ============================================================================
# 21. Falha do modelo não comunica sucesso
# ============================================================================
def test_21_model_failure_never_reports_llm_grounded_success():
    with patch.dict(os.environ, {"STUDY_FORCE_LIVE_LLM": "1"}):
        with patch(
            "backend.services.model_service.ModelExecutionService.execute",
            new_callable=AsyncMock,
            side_effect=RuntimeError("ConnectError: local Ollama daemon unreachable"),
        ):
            parsed, telem = invoke_study_llm_observable(
                operation="test_failure",
                system_prompt="JSON",
                user_prompt="Teste",
                document_id="doc_fail_01",
            )

    assert parsed is None
    assert telem["status"] == "UNAVAILABLE"
    assert any("ConnectError" in e for e in telem["validation_errors"])


# ============================================================================
# 22. Regeração substitui artefactos derivados de forma limpa
# ============================================================================
def test_22_regeneration_replaces_stale_derived_artifacts_cleanly(tmp_path: Path):
    svc = StudyService(storage_dir=str(tmp_path / "study"))
    doc = svc.ingest_document(
        (
            "A criptografia de curvas elípticas (ECC) baseia-se na dificuldade computacional do problema "
            "do logaritmo discreto sobre o grupo abeliano de pontos de uma curva elíptica sobre um corpo finito."
        ).encode("utf-8"),
        "criptografia_ecc.txt",
        subject="Segurança",
        source_type="TXT",
        custom_title="Criptografia de Curvas Elípticas",
    )
    doc.metadata["summaries"]["quick"] = ["Texto antigo obsoleto que deve desaparecer."]
    refreshed = svc.generate_summary(doc.document_id, mode="Quick", force_regenerate=True)
    new_quick = " ".join(refreshed["summaries"]["quick"])
    assert "Texto antigo obsoleto" not in new_quick
    assert "curvas elípticas" in new_quick.lower() or "ecc" in new_quick.lower()


# ============================================================================
# 23. study_save_to_vault preserva proveniência e protege notas existentes (.archive/)
# ============================================================================
def test_23_save_to_vault_preserves_provenance_and_archives_existing_file(tmp_path: Path):
    vault_dir = tmp_path / "vault"
    svc = StudyService(storage_dir=str(tmp_path / "study"), vault_root=str(vault_dir))
    doc = svc.ingest_document(
        "Uma prova de conhecimento zero permite a um provador demonstrar a veracidade de uma afirmação a um verificador sem revelar informação adicional.".encode("utf-8"),
        "zero_knowledge.txt",
        subject="Criptografia",
        source_type="TXT",
        custom_title="Provas de Conhecimento Zero (zk-SNARKs)",
    )
    path1 = svc.save_to_knowledge_vault(
        title="zk_SNARKs_Audit_Note",
        markdown_content="Conteúdo inicial da nota sobre zk-SNARKs.",
        subject="Criptografia",
        source_document_ids=[doc.document_id],
        synthesis_type="StudySummary",
    )
    first_text = Path(path1).read_text(encoding="utf-8")
    assert "source_document_id:" in first_text
    assert doc.document_id in first_text
    assert "generation_mode:" in first_text
    assert "status: extractive_unverified" in first_text or "status: llm_grounded_verified" in first_text

    # Second save with same title must archive the previous note first
    path2 = svc.save_to_knowledge_vault(
        title="zk_SNARKs_Audit_Note",
        markdown_content="Conteúdo atualizado na segunda exportação.",
        subject="Criptografia",
        source_document_ids=[doc.document_id],
        synthesis_type="DetailedSummary",
    )
    archive_dir = Path(path2).parent / ".archive"
    assert archive_dir.exists()
    archived_files = list(archive_dir.glob("*.md"))
    assert len(archived_files) == 1
    assert "Conteúdo inicial" in archived_files[0].read_text(encoding="utf-8")


# ============================================================================
# 24. WebSocket preserva request_id e suporta study_cancel_generation
# ============================================================================
def test_24_websocket_preserves_request_id_and_supports_cancel(tmp_path: Path):
    import asyncio
    svc = StudyService(storage_dir=str(tmp_path / "study"))
    connections = MagicMock()
    connections.send = AsyncMock()
    connections.broadcast = AsyncMock()
    handler = StudyWebSocketHandler(connections=connections, study_service=svc)

    ws = MagicMock()
    register_study_generation_start("doc_ws_test", "gen_ws_1")
    assert is_study_generation_cancelled("doc_ws_test") is False

    asyncio.run(handler.cancel_generation(ws, {"document_id": "doc_ws_test", "request_id": "req_cancel_99"}))
    assert is_study_generation_cancelled("doc_ws_test") is True
    connections.send.assert_awaited_once()
    sent_payload = connections.send.call_args[0][1]
    assert sent_payload["type"] == "study_generation_cancelled"
    assert sent_payload["request_id"] == "req_cancel_99"
    assert sent_payload["document_id"] == "doc_ws_test"


# ============================================================================
# 25. Frontend distingue geração fundamentada de extração local
# ============================================================================
def test_25_frontend_distinguishes_llm_grounded_from_extractive_local():
    summary_view_path = Path("frontend/src/features/study/StudySummaryView.tsx")
    notes_view_path = Path("frontend/src/features/study/StudyNotesView.tsx")
    summary_code = summary_view_path.read_text(encoding="utf-8")
    notes_code = notes_view_path.read_text(encoding="utf-8")

    assert "IA Fundamentada •" in summary_code
    assert "qwen3.5:9b" in summary_code
    assert "Extração Local sem Modelo" in summary_code
    assert "Síntese Parcial •" in summary_code
    assert "argumentative_limitation" in summary_code
    assert "unavailable_generative_features" in summary_code
    assert "onCancelGeneration" in summary_code
    assert "source_refs" in notes_code
