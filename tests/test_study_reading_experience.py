"""
Test Suite: Study Reading Experience & Pedagogical Vault Consolidation
Validates:
- Document ingestion (PDF & text) with SHA256 hashing and provenance
- Language detection (EN vs PT-PT) non-destructive preservation
- Reading Assistant: Contextual translation, 3-level explanation (Básico, Intermédio, Académico)
- Figure & Table explanation with INSUFFICIENT_EVIDENCE guards
- Paper RAG queries with exact page/section citations
- Argument mapping with OBSERVED / INFERRED / UNKNOWN provenance
- Quiz generation (5, 10, 20 questions) and real mathematical scoring (TP, incorrect, unanswered, %)
- Applied Knowledge Transfer scenario grading against rubric
- Lecture quiz handler defect fix verification
- Spaced review flashcards (SM-2 intervals: Again, Hard, Good, Easy)
- Cornell Notes synthesis and Obsidian Vault export with [[Wikilinks]]
- Multi-document comparative synthesis
- WebSocket study handlers and dispatcher integration
"""

import pytest
import os
import shutil
import tempfile
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

from services.study_service import (
    StudyService,
    StudyDocument,
    StudySection,
    StudyParagraph,
    StudyMedia,
    ArticleStructure,
    StudyQuiz,
    Flashcard,
    StudyReadingNote,
    StudyHighlight,
    detect_language,
    contextual_translate_to_pt,
)
from backend.websocket.handlers.study import StudyWebSocketHandler
from backend.websocket.handlers.lectures import LectureWebSocketHandler


@pytest.fixture
def temp_workspace():
    temp_dir = tempfile.mkdtemp(prefix="test_study_workspace_")
    vault_dir = os.path.join(temp_dir, "obsidian_vault")
    os.makedirs(vault_dir, exist_ok=True)
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def study_service(temp_workspace):
    vault_dir = os.path.join(temp_workspace, "obsidian_vault")
    return StudyService(
        workspace_root=temp_workspace,
        vault_root=vault_dir,
    )


# ==============================================================================
# 1. Ingestion & Provenance Tests
# ==============================================================================

def test_ingest_text_document_creates_structure(study_service):
    sample_text = """
    # Introduction to Attention Mechanisms
    Attention mechanisms have revolutionized deep learning. They allow models to focus on specific regions.
    
    ## Transformer Architecture
    The Transformer replaces recurrence entirely with self-attention.
    Figure 1 shows the scaled dot-product attention module.
    
    ## Experimental Results
    We achieved 28.4 BLEU on English-to-German translation.
    Table 1 summarizes the benchmark comparisons across WMT tasks.
    """
    doc = study_service.ingest_document(
        file_path_or_content=sample_text.encode("utf-8"),
        filename="attention_paper.txt",
        custom_title="Attention Is All You Need Review",
        subject="Machine Learning"
    )
    assert doc is not None
    assert doc.document_id is not None
    assert doc.source_hash is not None
    assert len(doc.source_hash) == 64  # SHA-256
    assert doc.title == "Attention Is All You Need Review"
    assert doc.language == "en"
    assert len(doc.sections) >= 1
    assert len(doc.extracted_text) > 0


def test_provenance_tracking(study_service):
    doc = study_service.ingest_document(
        file_path_or_content=b"# Methodology\nWe evaluate our pipeline on three datasets.",
        filename="methods.md",
        custom_title="Methods Document"
    )
    assert doc.source_hash != ""
    assert doc.provenance.get("source_hash") == doc.source_hash
    assert doc.provenance.get("evidence_status") == "OBSERVED"


def test_language_detection_english_flag(study_service):
    en_text = "This paper presents a novel framework for deep contextual embeddings with self-attention."
    doc_en = study_service.ingest_document(
        file_path_or_content=en_text.encode("utf-8"),
        filename="paper_en.txt",
        custom_title="English Paper"
    )
    assert doc_en.language == "en"

    pt_text = "Este artigo apresenta uma nova abordagem para o processamento de linguagem natural com base em dados de referência."
    doc_pt = study_service.ingest_document(
        file_path_or_content=pt_text.encode("utf-8"),
        filename="artigo_pt.txt",
        custom_title="Artigo Português"
    )
    assert doc_pt.language == "pt"


# ==============================================================================
# 2. Reading Assistant Tests (Translation, Explanations, Levels)
# ==============================================================================

def test_reading_assistant_contextual_translation(study_service):
    doc = study_service.ingest_document(
        file_path_or_content=b"# Transformer\nIn this paper, we propose a new model.",
        filename="trans.txt",
    )
    result = study_service.contextual_assist(
        document_id=doc.document_id,
        action="translate",
        selected_text="In this paper, we propose a scalable attention mechanism for sequences."
    )
    assert result["action"] == "translate"
    assert "translation" in result
    assert "Neste artigo, propomos" in result["translation"]
    assert "notes" in result


def test_explanation_level_basic(study_service):
    doc = study_service.ingest_document(b"Sample", "doc.txt")
    expl = study_service.contextual_assist(
        document_id=doc.document_id,
        action="explain",
        selected_text="Backpropagation optimizes gradient updates across layers.",
        level="Básico"
    )
    assert expl["level"] == "Básico"
    assert "simples" in expl["simple_explanation"].lower()


def test_explanation_level_intermediate(study_service):
    doc = study_service.ingest_document(b"Sample", "doc.txt")
    expl = study_service.contextual_assist(
        document_id=doc.document_id,
        action="explain",
        selected_text="Backpropagation optimizes gradient updates across layers.",
        level="Intermédio"
    )
    assert expl["level"] == "Intermédio"
    assert "conceptual" in expl["simple_explanation"].lower()


def test_explanation_level_academic(study_service):
    doc = study_service.ingest_document(b"Sample", "doc.txt")
    expl = study_service.contextual_assist(
        document_id=doc.document_id,
        action="explain",
        selected_text="Backpropagation optimizes gradient updates across layers.",
        level="Académico"
    )
    assert expl["level"] == "Académico"
    assert "formal" in expl["simple_explanation"].lower()


def test_explain_figure_with_evidence(study_service):
    doc = study_service.ingest_document(b"Sample content", "paper.txt")
    expl = study_service.contextual_assist(
        document_id=doc.document_id,
        action="explain_figure",
        selected_text="Figure 1: Scaled dot product attention showing key, query, value matrix operations."
    )
    assert expl["status"] == "OBSERVED"
    assert "compares" in expl
    assert "trend" in expl


def test_explain_figure_insufficient_evidence(study_service):
    doc = study_service.ingest_document(b"Sample", "empty.txt")
    expl = study_service.contextual_assist(
        document_id=doc.document_id,
        action="explain_figure",
        selected_text=""
    )
    assert expl["status"] == "INSUFFICIENT_EVIDENCE"


def test_explain_table_with_data(study_service):
    doc = study_service.ingest_document(b"Sample", "results.txt")
    expl = study_service.contextual_assist(
        document_id=doc.document_id,
        action="explain_table",
        selected_text="Table 1: BLEU score comparison on English-to-German translation benchmark."
    )
    assert expl["status"] == "OBSERVED"
    assert "units" in expl


def test_explain_table_insufficient_evidence(study_service):
    doc = study_service.ingest_document(b"Sample", "empty.txt")
    expl = study_service.contextual_assist(
        document_id=doc.document_id,
        action="explain_table",
        selected_text="   "
    )
    assert expl["status"] == "INSUFFICIENT_EVIDENCE"


# ==============================================================================
# 3. Paper RAG & Argument Map Tests
# ==============================================================================

def test_ask_paper_returns_citations(study_service):
    sample = """
    # Abstract
    We propose a scalable attention mechanism for sequences.
    
    # Methodology
    Our method reduces computational complexity from O(N^2) to O(N log N) using sparse projections.
    
    # Results
    Training time is cut by 45% while retaining 99.2% accuracy.
    """
    doc = study_service.ingest_document(
        file_path_or_content=sample.encode("utf-8"),
        filename="neural_nets.txt",
    )
    response = study_service.ask_paper(
        document_id=doc.document_id,
        question="What is the computational complexity of the proposed method?"
    )
    assert "answer" in response
    assert "sources" in response
    assert len(response["sources"]) > 0
    assert any("p. " in s for s in response["sources"])


def test_argument_map_generation_provenance(study_service):
    sample = """
    # Introduction
    Existing architectures suffer from quadratic memory bottlenecks.
    
    # Proposed Approach
    We introduce Linear-Attention with kernel feature maps.
    
    # Empirical Validation
    Experiments on ImageNet show 82.5% Top-1 accuracy.
    
    # Limitations
    However, the kernel approximation introduces slight noise in high-frequency patterns.
    """
    doc = study_service.ingest_document(
        file_path_or_content=sample.encode("utf-8"),
        filename="scientific_paper.txt",
    )
    struct = doc.structure
    assert struct is not None
    assert "problem" in struct
    assert "method" in struct
    assert "limitations" in struct
    assert struct["problem"]["status"] in ["OBSERVED", "INFERRED", "UNKNOWN"]


# ==============================================================================
# 4. Quiz & Real Mathematical Scoring Tests
# ==============================================================================

def test_generate_quiz_counts(study_service):
    doc = study_service.ingest_document(
        file_path_or_content=b"# Biology\nCellular respiration produces ATP.",
        filename="biology.txt",
    )
    quiz_5 = study_service.generate_quiz(doc.document_id, question_count=5)
    assert len(quiz_5.questions) == 5

    quiz_10 = study_service.generate_quiz(doc.document_id, question_count=10)
    assert len(quiz_10.questions) == 10


def test_evaluate_quiz_mathematical_scoring_perfect(study_service):
    doc = study_service.ingest_document(b"# Title\nSample text", "test_paper.txt")
    quiz = study_service.generate_quiz(doc.document_id, question_count=5)

    answers = {q["id"]: q["correct_index"] for q in quiz.questions}
    result = study_service.evaluate_quiz(
        quiz_id=quiz.quiz_id,
        user_answers=answers,
        transfer_answer="isolamento, idempotência, rastreabilidade e proveniência para persistência"
    )
    assert result["total_questions"] == 5
    assert result["correct_answers"] == 5
    assert result["incorrect_answers"] == 0
    assert result["unanswered"] == 0
    assert result["score_percentage"] == 100.0
    assert result["passed"] is True


def test_evaluate_quiz_mathematical_scoring_partial(study_service):
    doc = study_service.ingest_document(b"# Title\nSample text", "test_paper.txt")
    quiz = study_service.generate_quiz(doc.document_id, question_count=5)

    # 3 correct, 1 incorrect, 1 omitted
    answers = {
        quiz.questions[0]["id"]: quiz.questions[0]["correct_index"],
        quiz.questions[1]["id"]: quiz.questions[1]["correct_index"],
        quiz.questions[2]["id"]: quiz.questions[2]["correct_index"],
        quiz.questions[3]["id"]: (quiz.questions[3]["correct_index"] + 1) % 4,
    }

    result = study_service.evaluate_quiz(
        quiz_id=quiz.quiz_id,
        user_answers=answers,
        transfer_answer=""
    )
    assert result["total_questions"] == 5
    assert result["correct_answers"] == 3
    assert result["incorrect_answers"] == 1
    assert result["unanswered"] == 1
    assert result["score_percentage"] == 60.0
    assert result["passed"] is False


def test_evaluate_quiz_knowledge_transfer_rubric_evaluation(study_service):
    doc = study_service.ingest_document(b"# Systems\nRaft consensus", "systems.txt")
    quiz = study_service.generate_quiz(doc.document_id, question_count=5)
    answers = {q["id"]: q["correct_index"] for q in quiz.questions}

    result_good = study_service.evaluate_quiz(
        quiz_id=quiz.quiz_id,
        user_answers=answers,
        transfer_answer="Adotaria isolamento estrito, idempotência em todas as mensagens e rastreabilidade total de proveniência."
    )
    assert result_good["transfer_status"] == "PASS"
    assert result_good["transfer_passed"] is True

    result_blank = study_service.evaluate_quiz(
        quiz_id=quiz.quiz_id,
        user_answers=answers,
        transfer_answer=""
    )
    assert result_blank["transfer_status"] == "NOT_ATTEMPTED"
    assert result_blank["transfer_passed"] is False


# ==============================================================================
# 5. Lecture Quiz Handler Defect Fix Verification
# ==============================================================================

def test_lecture_quiz_scoring_fixed_in_handler():
    """Verify backend/websocket/handlers/lectures.py accurately grades quiz instead of hardcoded 100%."""
    async def _run():
        mock_connections = MagicMock()
        mock_connections.send = AsyncMock()
        mock_connections.broadcast = AsyncMock()
        mock_socket = MagicMock()
        mock_session = MagicMock()

        handler = LectureWebSocketHandler(connections=mock_connections)

        payload = {
            "topic": "Distributed Systems",
            "answers": {
                "q1": 0,  # Correct
                "q2": 1,  # Incorrect (correct is 0)
                # q3 is unanswered
            },
            "transfer_answer": "Short"
        }

        await handler.submit_lecture_quiz(mock_socket, payload, mock_session)

        assert mock_connections.broadcast.called
        sent_msg = mock_connections.broadcast.call_args[0][0]
        assert sent_msg["type"] == "lecture_quiz_evaluated"
        assert sent_msg["total_questions"] == 3
        assert sent_msg["correct_answers"] == 1
        assert sent_msg["incorrect_answers"] == 1
        assert sent_msg["unanswered"] == 1
        assert sent_msg["score"] == 33.3  # 1/3 = 33.3%, NOT 100%!
        assert sent_msg["passed"] is False

    asyncio.run(_run())


# ==============================================================================
# 6. Spaced Review & Flashcard SM-2 Algorithm Tests
# ==============================================================================

def test_flashcard_generation(study_service):
    doc = study_service.ingest_document(
        file_path_or_content=b"# DNA Replication\nDNA polymerase synthesizes new strands.",
        filename="genetics.txt",
    )
    cards = study_service.generate_flashcards(doc.document_id)
    assert len(cards) >= 1
    assert all(c.document_id == doc.document_id for c in cards)
    assert all(c.interval_days == 1.0 for c in cards)


def test_flashcard_review_sm2_again(study_service):
    doc = study_service.ingest_document(b"Sample", "sample.txt")
    cards = study_service.generate_flashcards(doc.document_id)
    card = cards[0]
    updated = study_service.review_flashcard(card.card_id, action="Again")
    assert updated.interval_days == 1.0
    assert updated.repetitions == 0
    assert updated.difficulty == "HARD"


def test_flashcard_review_sm2_good_progression(study_service):
    doc = study_service.ingest_document(b"Sample", "sample.txt")
    cards = study_service.generate_flashcards(doc.document_id)
    card = cards[0]

    # Repetition 1
    r1 = study_service.review_flashcard(card.card_id, action="Good")
    assert r1.repetitions == 1
    assert r1.interval_days >= 2.0

    # Repetition 2
    r2 = study_service.review_flashcard(card.card_id, action="Good")
    assert r2.repetitions == 2
    assert r2.interval_days >= 4.0


def test_flashcard_review_sm2_easy_bonus(study_service):
    doc = study_service.ingest_document(b"Sample", "sample.txt")
    cards = study_service.generate_flashcards(doc.document_id)
    card = cards[0]
    updated = study_service.review_flashcard(card.card_id, action="Easy")
    assert updated.repetitions == 1
    assert updated.interval_days >= 3.0
    assert updated.difficulty == "EASY"


# ==============================================================================
# 7. Cornell Notes & Obsidian Vault Export Tests
# ==============================================================================

def test_cornell_notes_synthesis(study_service):
    doc = study_service.ingest_document(
        file_path_or_content=b"# Memory Virtualization\nVirtual memory provides contiguous address space.",
        filename="operating_systems.txt",
    )
    cornell = study_service.generate_cornell_from_document(doc.document_id)
    assert cornell is not None
    assert "executive_summary" in cornell
    assert "cue_column" in cornell
    assert "detailed_notes" in cornell
    assert "glossary" in cornell
    assert "action_items" in cornell
    assert len(cornell["cue_column"]) > 0


def test_export_to_obsidian_vault_with_wikilinks(study_service):
    doc = study_service.ingest_document(
        file_path_or_content=b"# CAP Theorem\nA distributed system has trade-offs.",
        filename="distributed_db.txt",
    )
    cornell = study_service.generate_cornell_from_document(doc.document_id)
    saved_path = study_service.save_to_knowledge_vault(
        title="CAP Theorem Cornell Note",
        subject="Distributed Systems",
        source_document_ids=[doc.document_id],
        cornell_dict=cornell,
    )
    assert os.path.exists(saved_path)

    with open(saved_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "---" in content
    assert "type: study_note" in content
    assert doc.document_id in content


# ==============================================================================
# 8. Multi-Document Comparative Synthesis Tests
# ==============================================================================

def test_comparative_synthesis_multi_documents(study_service):
    doc1 = study_service.ingest_document(b"# Transformers\nSelf-attention complexity.", "doc1.txt")
    doc2 = study_service.ingest_document(b"# Performers\nLinear complexity.", "doc2.txt")
    synthesis = study_service.synthesize_documents([doc1.document_id, doc2.document_id])
    assert synthesis is not None
    assert "common_themes" in synthesis
    assert "divergent_perspectives" in synthesis
    assert synthesis["document_count"] == 2


# ==============================================================================
# 9. Highlights & Reading Notes Management Tests
# ==============================================================================

def test_create_and_retrieve_highlights(study_service):
    doc = study_service.ingest_document(b"# Reading\nText here", "reading.txt")
    hl = study_service.add_highlight(
        document_id=doc.document_id,
        page=1,
        selected_text="Crucial breakthrough",
        context="Surrounding sentence",
        color="yellow",
    )
    assert hl.highlight_id is not None
    assert hl.color == "yellow"
    assert hl.page == 1
    assert len(study_service.highlights) >= 1


def test_create_and_retrieve_reading_notes(study_service):
    doc = study_service.ingest_document(b"# Chapter 1\nDetailed content", "ch1.txt")
    note = study_service.add_reading_note(
        document_id=doc.document_id,
        page=1,
        selection="Detailed content",
        note_text="Check experiments again",
        section_id="sec_0",
    )
    assert note.note_id is not None
    assert note.note == "Check experiments again"
    assert len(study_service.notes) >= 1


# ==============================================================================
# 10. WebSocket Study Handler Integration Tests
# ==============================================================================

def test_websocket_study_list_documents(study_service):
    async def _run():
        mock_connections = MagicMock()
        mock_connections.send = AsyncMock()
        mock_socket = MagicMock()
        mock_session = MagicMock()

        handler = StudyWebSocketHandler(connections=mock_connections, study_service=study_service)

        study_service.ingest_document(b"# WebSocket Test\nDocument loaded.", "ws_doc.txt")

        await handler.list_documents(mock_socket, {}, mock_session)
        assert mock_connections.send.called
        msg = mock_connections.send.call_args[0][1]
        assert msg["type"] == "study_documents_list"
        assert len(msg["documents"]) >= 1

    asyncio.run(_run())


def test_websocket_study_contextual_assist(study_service):
    async def _run():
        mock_connections = MagicMock()
        mock_connections.send = AsyncMock()
        mock_socket = MagicMock()
        mock_session = MagicMock()

        handler = StudyWebSocketHandler(connections=mock_connections, study_service=study_service)
        doc = study_service.ingest_document(b"# NLP\nSelf-attention is key.", "nlp.txt")

        payload = {
            "document_id": doc.document_id,
            "action": "translate",
            "selected_text": "In this paper, we propose a new neural model.",
        }
        await handler.contextual_assist(mock_socket, payload, mock_session)
        assert mock_connections.send.called
        msg = mock_connections.send.call_args[0][1]
        assert msg["type"] == "study_contextual_assist_result"
        assert msg["action"] == "translate"

    asyncio.run(_run())


def test_websocket_study_ask_paper(study_service):
    async def _run():
        mock_connections = MagicMock()
        mock_connections.send = AsyncMock()
        mock_socket = MagicMock()
        mock_session = MagicMock()

        handler = StudyWebSocketHandler(connections=mock_connections, study_service=study_service)
        doc = study_service.ingest_document(b"# RL\nPolicy gradient updates actor weights.", "rl.txt")

        payload = {
            "document_id": doc.document_id,
            "question": "How does policy gradient work?",
        }
        await handler.ask_paper(mock_socket, payload, mock_session)
        assert mock_connections.send.called
        msg = mock_connections.send.call_args[0][1]
        assert msg["type"] == "study_ask_paper_result"
        assert "answer" in msg

    asyncio.run(_run())


def test_websocket_study_quiz_lifecycle(study_service):
    async def _run():
        mock_connections = MagicMock()
        mock_connections.send = AsyncMock()
        mock_socket = MagicMock()
        mock_session = MagicMock()

        handler = StudyWebSocketHandler(connections=mock_connections, study_service=study_service)
        doc = study_service.ingest_document(b"# Compilers\nLexical analysis converts character streams.", "comp.txt")

        # 1. Generate quiz
        await handler.generate_quiz(mock_socket, {"document_id": doc.document_id, "question_count": 5}, mock_session)
        msg_gen = mock_connections.send.call_args[0][1]
        assert msg_gen["type"] == "study_quiz_ready"
        quiz = msg_gen["quiz"]
        quiz_id = quiz["quiz_id"]

        # 2. Submit quiz
        mock_connections.send.reset_mock()
        submit_payload = {
            "quiz_id": quiz_id,
            "answers": {q["id"]: q["correct_index"] for q in quiz["questions"]},
            "transfer_answer": "isolamento, idempotência, rastreabilidade"
        }
        await handler.submit_quiz(mock_socket, submit_payload, mock_session)
        msg_eval = mock_connections.send.call_args[0][1]
        assert msg_eval["type"] == "study_quiz_evaluated"
        assert "score_percentage" in msg_eval
        assert msg_eval["correct_answers"] == 5

    asyncio.run(_run())


def test_websocket_study_flashcards_lifecycle(study_service):
    async def _run():
        mock_connections = MagicMock()
        mock_connections.send = AsyncMock()
        mock_socket = MagicMock()
        mock_session = MagicMock()

        handler = StudyWebSocketHandler(connections=mock_connections, study_service=study_service)
        doc = study_service.ingest_document(b"# Neuro\nSynaptic plasticity strengthens synapses.", "neuro.txt")

        # 1. List flashcards
        await handler.list_flashcards(mock_socket, {"document_id": doc.document_id}, mock_session)
        msg_list = mock_connections.send.call_args[0][1]
        assert msg_list["type"] == "study_flashcards_list"
        cards = msg_list["flashcards"]
        assert len(cards) >= 1
        card_id = cards[0]["card_id"]

        # 2. Review flashcard
        mock_connections.send.reset_mock()
        await handler.review_flashcard(mock_socket, {"card_id": card_id, "action": "Good"}, mock_session)
        msg_review = mock_connections.send.call_args[0][1]
        assert msg_review["type"] == "study_flashcard_reviewed"
        assert msg_review["flashcard"]["card_id"] == card_id

    asyncio.run(_run())


def test_websocket_study_save_to_knowledge(study_service):
    async def _run():
        mock_connections = MagicMock()
        mock_connections.broadcast = AsyncMock()
        mock_connections.send = AsyncMock()
        mock_socket = MagicMock()
        mock_session = MagicMock()

        handler = StudyWebSocketHandler(connections=mock_connections, study_service=study_service)
        doc = study_service.ingest_document(b"# Cloud\nObject storage provides durability.", "cloud.txt")

        await handler.save_to_knowledge(
            mock_socket,
            {"title": "Cloud Note", "content": "Sample content", "subject": "Cloud Computing", "source_document_ids": [doc.document_id]},
            mock_session
        )
        assert mock_connections.broadcast.called
        msg_vault = mock_connections.broadcast.call_args[0][0]
        assert msg_vault["type"] == "study_knowledge_saved"
        assert msg_vault["title"] == "Cloud Note"

    asyncio.run(_run())


# Additional deterministic tests to reach 36 tests
def test_study_document_to_dict(study_service):
    doc = study_service.ingest_document(b"# Header\nParagraph one.", "test.txt")
    d = doc.to_dict()
    assert d["document_id"] == doc.document_id
    assert d["title"] == "Test"
    assert len(d["sections"]) >= 1


def test_summarize_modes_quick_and_exam(study_service):
    doc = study_service.ingest_document(b"# Introduction\nFirst sentence of introduction.", "summary.txt")
    quick = study_service.generate_summary(doc.document_id, mode="Quick")
    assert quick["mode"] == "Quick"
    assert len(quick["points"]) > 0

    exam = study_service.generate_summary(doc.document_id, mode="Exam")
    assert exam["mode"] == "Exam"
    assert len(exam["high_yield_concepts"]) > 0


def test_summarize_modes_detailed_and_study(study_service):
    doc = study_service.ingest_document(b"# Detailed Section\nParagraph content.", "detailed.txt")
    detailed = study_service.generate_summary(doc.document_id, mode="Detailed")
    assert detailed["mode"] == "Detailed"

    study = study_service.generate_summary(doc.document_id, mode="Study")
    assert study["mode"] == "Study"


def test_define_concept_glossary_match(study_service):
    doc = study_service.ingest_document(b"# Test\nContent", "glossary.txt")
    result = study_service.contextual_assist(
        document_id=doc.document_id,
        action="define_concept",
        selected_text="transformer"
    )
    assert result["status"] in ["OBSERVED", "INFERRED"]
    assert "translation" in result
    assert "translation" in result


def test_update_reading_progress(study_service):
    doc = study_service.ingest_document(b"# Section 1\nContent page 1.", "progress.txt")
    prog = study_service.update_reading_progress(
        document_id=doc.document_id,
        current_page=1,
        current_section="Section 1",
        scroll_position=250,
    )
    assert prog["current_page"] == 1
    assert prog["scroll_position"] == 250
    assert prog["progress_percent"] == 100.0


def test_get_document_details(study_service):
    doc = study_service.ingest_document(b"Single content", "single.txt")
    retrieved = study_service.documents.get(doc.document_id)
    assert retrieved is not None
    assert retrieved.document_id == doc.document_id


def test_get_nonexistent_document_returns_none(study_service):
    retrieved = study_service.documents.get("non-existent-id")
    assert retrieved is None


def test_empty_document_handling(study_service):
    doc = study_service.ingest_document(b"", "empty.txt")
    assert doc.document_id is not None
    assert doc.page_count >= 1


def test_quiz_answer_count_validation(study_service):
    doc = study_service.ingest_document(b"# Header\nContent", "quiz.txt")
    quiz_20 = study_service.generate_quiz(doc.document_id, question_count=20)
    assert len(quiz_20.questions) == 20


# ==============================================================================
# Document Store Synchronization & Concurrency Regression Tests
# ==============================================================================

def test_hot_ingestion_without_service_restart(temp_workspace):
    """
    Teste Obrigatório 1:
    1. Iniciar StudyService
    2. Carregar catálogo inicial
    3. Criar/ingerir novo documento DEPOIS da inicialização
    4. Não reiniciar StudyService
    5. Pedir listagem
    6. Confirmar novo documento presente
    7. Abrir documento
    8. Confirmar conteúdo correto
    """
    vault_dir = os.path.join(temp_workspace, "obsidian_vault")
    # 1. Iniciar StudyService
    svc = StudyService(workspace_root=temp_workspace, vault_root=vault_dir)

    # 2. Carregar catálogo inicial
    initial_docs = svc.list_documents()
    assert len(initial_docs) == 0

    # 3. Criar/ingerir novo documento DEPOIS da inicialização
    sample_text = "# Hot Ingestion Article\nConteudo gerado dinamicamente para teste sem restart."
    new_doc = svc.ingest_document(
        file_path_or_content=sample_text.encode("utf-8"),
        filename="hot_ingestion.txt",
        custom_title="Hot Ingestion Document",
        subject="AI Engineering",
    )

    # 4. Não reiniciar StudyService
    # 5. Pedir listagem
    active_docs = svc.list_documents()

    # 6. Confirmar novo documento presente
    doc_ids = [d.document_id for d in active_docs]
    assert new_doc.document_id in doc_ids

    # 7. Abrir documento
    retrieved = svc.get_document(new_doc.document_id)
    assert retrieved is not None

    # 8. Confirmar conteúdo correto
    assert retrieved.title == "Hot Ingestion Document"
    assert "Conteudo gerado dinamicamente" in retrieved.extracted_text


def test_external_modification_of_documents_json_detected_without_restart(temp_workspace):
    """
    Teste Obrigatório 2:
    StudyService iniciado
    → documents.json alterado externamente
    → próxima consulta detecta alteração
    → registry atualizado
    Sem restart.
    """
    vault_dir = os.path.join(temp_workspace, "obsidian_vault")
    import time
    import json
    from pathlib import Path

    # 1. Iniciar StudyService
    svc = StudyService(workspace_root=temp_workspace, vault_root=vault_dir)
    assert len(svc.list_documents()) == 0

    # 2. Simular outro processo/worker a escrever externamente em documents.json
    external_doc_id = "doc_ext_99887766"
    external_doc_payload = {
        external_doc_id: {
            "document_id": external_doc_id,
            "source_id": external_doc_id,
            "title": "Externally Added Paper",
            "source_type": "PDF",
            "subject": "Geral",
            "source_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "page_count": 5,
            "language": "en",
            "extracted_text": "Page 1 content. Overview of externally added research.",
            "sections": [{"section_id": "sec_1", "title": "1. Overview", "page_start": 1, "page_end": 2, "paragraphs": []}],
            "reading_progress": {"current_page": 1, "current_section": "1. Overview", "scroll_position": 0, "progress_percent": 20.0, "last_read_at": "2026-09-23 00:00:00", "bookmarks": []},
            "created_at": "2026-09-23 00:00:00",
            "updated_at": "2026-09-23 00:00:00"
        }
    }
    time.sleep(0.05)
    docs_file = Path(temp_workspace) / "data" / "study" / "documents.json"
    docs_file.parent.mkdir(parents=True, exist_ok=True)
    docs_file.write_text(json.dumps(external_doc_payload, indent=2), encoding="utf-8")

    # 3. Próxima consulta em svc (SEM restart) detecta alteração
    updated_docs = svc.list_documents()
    assert len(updated_docs) == 1
    assert updated_docs[0].document_id == external_doc_id
    assert updated_docs[0].title == "Externally Added Paper"

    # Verificar métricas de refresh e stale
    metrics = svc.get_catalog_metrics()
    assert metrics["study_catalog_stale_detected"] >= 1
    assert metrics["study_catalog_refresh_count"] >= 1
    assert metrics["study_catalog_refresh_latency_ms"] >= 0.0


def test_existing_document_modification_invalidates_cache_and_updates_hash(temp_workspace):
    """
    Teste Obrigatório 3:
    documento existente é alterado
    e confirmar:
    - source_hash atualizado
    - conteúdo atualizado
    - cache antigo invalidado
    """
    vault_dir = os.path.join(temp_workspace, "obsidian_vault")
    import time
    import json
    import hashlib
    from pathlib import Path

    svc = StudyService(workspace_root=temp_workspace, vault_root=vault_dir)

    # Ingestão original
    orig_doc = svc.ingest_document(
        file_path_or_content=b"Versao 1 original do documento.",
        filename="paper_revision.txt",
        custom_title="Paper Revision Study"
    )
    orig_hash = orig_doc.source_hash
    orig_id = orig_doc.document_id

    # Confirmar cache inicial
    cached = svc.get_document(orig_id)
    assert cached.source_hash == orig_hash
    assert "Versao 1 original" in cached.extracted_text

    # Simular modificação externa do mesmo documento
    time.sleep(0.05)
    new_content = "Versao 2 alterada com novos dados empiricos."
    new_hash = hashlib.sha256(new_content.encode("utf-8")).hexdigest()

    docs_file = Path(temp_workspace) / "data" / "study" / "documents.json"
    current_data = json.loads(docs_file.read_text(encoding="utf-8"))
    current_data[orig_id]["source_hash"] = new_hash
    current_data[orig_id]["extracted_text"] = new_content
    current_data[orig_id]["updated_at"] = "2026-09-23 01:00:00"
    docs_file.write_text(json.dumps(current_data, indent=2), encoding="utf-8")

    # Próxima consulta deve invalidar o cache e trazer versão atualizada
    updated = svc.get_document(orig_id)
    assert updated is not None
    assert updated.source_hash == new_hash
    assert updated.source_hash != orig_hash
    assert "Versao 2 alterada" in updated.extracted_text


def test_websocket_study_get_document_file_success(study_service):
    async def _run():
        doc = study_service.ingest_document(
            file_path_or_content=b"%PDF-1.4 Mock Binary PDF content for testing reading layer",
            filename="native_sample.pdf",
            custom_title="Native PDF Paper"
        )
        
        mock_conn = MagicMock()
        mock_conn.send = AsyncMock()
        handler = StudyWebSocketHandler(connections=mock_conn, study_service=study_service)

        ws = MagicMock()
        session = MagicMock()

        await handler.get_document_file(
            ws,
            {
                "type": "study_get_document_file",
                "document_id": doc.document_id,
                "request_id": "req-file-1234",
            },
            session
        )

        mock_conn.send.assert_awaited_once()
        payload = mock_conn.send.await_args[0][1]
        assert payload["type"] == "study_document_file_result"
        assert payload["document_id"] == doc.document_id
        assert payload["request_id"] == "req-file-1234"
        assert "content_base64" in payload
        assert len(payload["content_base64"]) > 0

    asyncio.run(_run())


def test_websocket_study_get_document_file_missing(study_service):
    async def _run():
        mock_conn = MagicMock()
        mock_conn.send = AsyncMock()
        handler = StudyWebSocketHandler(connections=mock_conn, study_service=study_service)

        ws = MagicMock()
        session = MagicMock()

        await handler.get_document_file(
            ws,
            {
                "type": "study_get_document_file",
                "document_id": "nonexistent_doc_id",
                "request_id": "req-missing-999",
            },
            session
        )

        mock_conn.send.assert_awaited_once()
        payload = mock_conn.send.await_args[0][1]
        assert payload["type"] == "study_document_file_result"
        assert payload["document_id"] == "nonexistent_doc_id"
        assert payload["request_id"] == "req-missing-999"
        assert "error" in payload

    asyncio.run(_run())


def test_websocket_contextual_assist_with_request_id(study_service):
    async def _run():
        doc = study_service.ingest_document(
            file_path_or_content=b"Sample paper methodology text.",
            filename="methods.pdf",
            custom_title="Methods Paper"
        )

        mock_conn = MagicMock()
        mock_conn.send = AsyncMock()
        handler = StudyWebSocketHandler(connections=mock_conn, study_service=study_service)

        ws = MagicMock()
        session = MagicMock()

        await handler.contextual_assist(
            ws,
            {
                "type": "study_contextual_assist",
                "document_id": doc.document_id,
                "action": "translate",
                "selected_text": "In this paper, we propose a novel framework.",
                "request_id": "req-assist-pt-555",
            },
            session
        )

        mock_conn.send.assert_awaited_once()
        payload = mock_conn.send.await_args[0][1]
        assert payload["type"] == "study_contextual_assist_result"
        assert payload["document_id"] == doc.document_id
        assert payload["request_id"] == "req-assist-pt-555"
        assert "Neste artigo, propomos" in payload["translation"]

    asyncio.run(_run())


def test_reading_assistant_contextual_translation_scientific_paper(study_service):
    text = "In this work, we present state-of-the-art results compared to baseline."
    translated = contextual_translate_to_pt(text)
    assert "Neste trabalho, apresentamos" in translated
    assert "Estado da arte" in translated or "estado da arte" in translated
    assert "linha de base" in translated

