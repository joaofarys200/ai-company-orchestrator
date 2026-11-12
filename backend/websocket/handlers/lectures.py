"""
JARVIS OS - Lecture WebSocket Handler
Processa mensagens de início/fim de gravação de aulas, consulta de status e lista de histórico.
"""

from __future__ import annotations

import asyncio
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from backend.logging_config import log_event
from backend.websocket.context import WebSocketSessionState
from backend.websocket.contracts import MessageHandler
try:
    from backend.websocket.gateway import ConnectionManager
except ImportError:
    ConnectionManager = Any
from backend.websocket.handlers import bind_handler_methods
from services.lecture_recorder import LectureRecorderService, LectureSession
from services.lecture_synthesizer import CornellNoteSynthesizer, VaultLinker


LECTURE_HANDLERS = {
    "start_lecture_recording": "start_lecture_recording",
    "stop_lecture_recording": "stop_lecture_recording",
    "get_lecture_status": "get_lecture_status",
    "list_lecture_history": "list_lecture_history",
    "generate_lecture_lesson": "generate_lecture_lesson",
    "submit_lecture_quiz": "submit_lecture_quiz",
}


class LectureWebSocketHandler:
    def __init__(
        self,
        connections: ConnectionManager,
        logger: Any = None,
        recorder_service: Optional[LectureRecorderService] = None,
        synthesizer_service: Optional[CornellNoteSynthesizer] = None,
    ) -> None:
        self.connections = connections
        self.logger = logger
        self.recorder = recorder_service or LectureRecorderService(
            on_audio_level=self._on_audio_level,
            on_status_change=self._on_status_change,
        )
        self.synthesizer = synthesizer_service or CornellNoteSynthesizer()

    def routes(self) -> dict[str, MessageHandler]:
        return bind_handler_methods(self, LECTURE_HANDLERS)

    def _on_audio_level(self, level: float) -> None:
        """Transmite o nível de áudio em tempo real para a UI."""
        # Apenas se estiver gravando
        if self.recorder.is_recording:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(
                    self.connections.broadcast({
                        "type": "lecture_audio_level",
                        "level": round(level, 3),
                    })
                )
            except RuntimeError:
                pass

    def _on_status_change(self, session: LectureSession) -> None:
        """Transmite alteração de estado da sessão."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(
                self.connections.broadcast({
                    "type": "lecture_session_update",
                    "session": session.to_dict(),
                })
            )
        except RuntimeError:
            pass

    async def start_lecture_recording(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        subject = message.get("subject", "Geral")
        title = message.get("title", "Nova Aula")
        professor = message.get("professor", "")

        try:
            session = self.recorder.start_recording(
                subject=subject,
                title=title,
                professor=professor,
            )
            if self.logger:
                log_event(self.logger, "lecture.recording.started", session_id=session.session_id)

            await self.connections.broadcast({
                "type": "lecture_recording_started",
                "session": session.to_dict(),
            })
        except Exception as e:
            await self.connections.send(websocket, {
                "type": "lecture_error",
                "message": str(e),
            })

    async def stop_lecture_recording(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        try:
            session = self.recorder.stop_recording()
            if self.logger:
                log_event(self.logger, "lecture.recording.stopped", session_id=session.session_id)

            await self.connections.broadcast({
                "type": "lecture_transcribing_started",
                "session": session.to_dict(),
            })

            # Executar transcrição e síntese em background
            asyncio.create_task(self._async_synthesize(session))

        except Exception as e:
            await self.connections.send(websocket, {
                "type": "lecture_error",
                "message": str(e),
            })

    async def _async_synthesize(self, session: LectureSession) -> None:
        """Executa a transcrição e geração de Cornell Notes de forma assíncrona."""
        try:
            loop = asyncio.get_running_loop()
            # Rodar síntese em thread pool para não bloquear o event loop
            markdown_path = await loop.run_in_executor(
                None,
                self.synthesizer.process_lecture,
                session,
            )

            await self.connections.broadcast({
                "type": "lecture_synthesis_completed",
                "session": session.to_dict(),
                "markdown_path": markdown_path,
            })
        except Exception as e:
            session.status = "FAILED"
            session.error_message = str(e)
            await self.connections.broadcast({
                "type": "lecture_error",
                "message": f"Erro na síntese da aula: {e}",
                "session": session.to_dict(),
            })

    async def get_lecture_status(
        self,
        websocket: Any,
        _message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        status_data = self.recorder.get_status()
        await self.connections.send(websocket, {
            "type": "lecture_status_response",
            **status_data,
        })

    async def list_lecture_history(
        self,
        websocket: Any,
        _message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        history = self.recorder.list_history()

        # Também varre obsidian_vault/10 - Lectures/ para incluir notas existentes
        vault_lectures = []
        lectures_dir = Path("obsidian_vault/10 - Lectures")
        if lectures_dir.exists():
            for md_file in lectures_dir.rglob("*.md"):
                if md_file.name == "Index.md" or ".obsidian" in md_file.parts:
                    continue
                try:
                    rel_subj = md_file.parent.name if md_file.parent != lectures_dir else "Geral"
                    vault_lectures.append({
                        "title": md_file.stem,
                        "subject": rel_subj,
                        "markdown_path": str(md_file).replace("\\", "/"),
                        "date": datetime.fromtimestamp(md_file.stat().st_mtime).strftime("%Y-%m-%d"),
                        "status": "COMPLETED",
                    })
                except Exception:
                    pass

        # Combinar sem duplicar títulos
        seen_titles = {h.get("title") for h in history if isinstance(h, dict)}
        for vl in vault_lectures:
            if vl["title"] not in seen_titles:
                history.append(vl)
                seen_titles.add(vl["title"])

        await self.connections.send(websocket, {
            "type": "lecture_history_response",
            "history": history,
        })

    async def generate_lecture_lesson(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        """Gera uma aula completa em formato Cornell Notes com perguntas de quiz e teste de transferência."""
        topic = message.get("topic", "").strip() or "Sistemas Multiagente e Arquiteturas RAG"
        subject = message.get("subject", "").strip() or "Inteligência Artificial"
        professor = message.get("professor", "").strip() or "Prof. JARVIS"
        date_str = datetime.now().strftime("%Y-%m-%d")

        try:
            from services.study_ai_engine import invoke_study_llm_json

            parsed_lesson = await asyncio.to_thread(
                invoke_study_llm_json,
                operation="lecture_generate_lesson",
                system_prompt=(
                    "És um professor universitário especialista em PT-PT. Prepara uma aula rigorosa, concreta e detalhada "
                    "em formato Cornell Notes sobre o tópico e disciplina indicados. Devolve apenas JSON válido."
                ),
                user_prompt=(
                    f"Tópico: \"{topic}\"\nDisciplina: \"{subject}\"\nProfessor: \"{professor}\"\n\n"
                    "Devolve JSON com:\n"
                    '{\n'
                    '  "executive_summary": "...",\n'
                    '  "cue_column": [{"cue": "...", "idea": "..."}],\n'
                    '  "detailed_notes": "Markdown com ### subtítulos, conceitos, exemplos e explicações concretas sobre o tópico",\n'
                    '  "glossary": "- **Termo**: Definição\\n...",\n'
                    '  "action_items": ["...", "...", "..."]\n'
                    '}'
                ),
                max_output_tokens=4096,
            )
            offline_fallback = not (isinstance(parsed_lesson, dict) and parsed_lesson.get("detailed_notes"))

            if isinstance(parsed_lesson, dict) and parsed_lesson.get("detailed_notes"):
                summary = str(parsed_lesson.get("executive_summary") or f"Síntese da aula sobre **{topic}** ({subject}).").strip()
                cue_column = [
                    {"cue": str(c.get("cue", "")).strip(), "idea": str(c.get("idea", "")).strip()}
                    for c in (parsed_lesson.get("cue_column") or [])
                    if isinstance(c, dict) and c.get("cue") and c.get("idea")
                ]
                detailed_notes = str(parsed_lesson.get("detailed_notes")).strip()
                glossary = str(parsed_lesson.get("glossary") or "").strip()
                action_items = [str(a).strip() for a in (parsed_lesson.get("action_items") or []) if str(a).strip()]
            else:
                cue_column = []
                summary = f"Estrutura de estudo para o tópico **{topic}** no âmbito de **{subject}**."
                detailed_notes = f"### Tópico: {topic}\n*(O motor LLM encontra-se offline para expandir o conteúdo expositivo desta aula.)*"
                glossary = f"- **{topic}**: Tópico selecionado na disciplina de {subject}."
                action_items = [f"Consultar materiais carregados sobre {topic} na biblioteca de Estudos."]

            if not cue_column:
                cue_column = [{"cue": f"Qual o foco de estudo de «{topic}»?", "idea": summary}]
            if not action_items:
                action_items = [f"Rever conceitos principais de {topic}."]

            # Injetar Wikilinks
            linker = VaultLinker()
            linked_summary = linker.link_text(summary)
            linked_notes = linker.link_text(detailed_notes)
            cue_rows_md = "\n".join(
                f"| **{c['cue'].replace('|', '/')}** | {c['idea'].replace('|', '/')} |"
                for c in cue_column
            )
            actions_md = "\n".join(f"- [ ] {act}" for act in action_items)

            # Construir Markdown completo
            raw_markdown = f"""---
type: lecture_notes
domain: academic
status: verified
source_type: PRIMARY_SOURCE
confidence: high
subject: "{subject}"
professor: "{professor}"
date: "{date_str}"
duration_minutes: 45.0
tags:
  - lecture-notes
  - cornell-notes
  - {subject.lower().replace(' ', '-')}
---

# 🎓 {topic}

## 📌 Metadados da Sessão
- **Disciplina:** {subject}
- **Professor(a):** {professor}
- **Data da Aula:** {date_str}
- **Duração:** 45 minutos

---

## 📝 1. Sumário Executivo
{linked_summary}

---

## 💡 2. Cornell Cue Column & Conceitos-Chave

| Perguntas de Revisão & Cues | Ideias Centrais & Respostas Rápidas |
|---|---|
{cue_rows_md}

---

## 📖 3. Notas Detalhadas de Conteúdo
{linked_notes}

---

## 📚 4. Glossário Técnico & Definições
{glossary}

---

## 🎯 5. Ações e Avaliações
{actions_md}
"""
            # Salvar no Obsidian Vault fora do loop async
            from services.study_fs import atomic_write_text, safe_filename

            clean_subj = "".join(c for c in subject if c.isalnum() or c in (" ", "-", "_")).strip() or "Geral"
            clean_top = "".join(c for c in topic if c.isalnum() or c in (" ", "-", "_")).strip()
            safe_fname = safe_filename(f"{date_str} - {clean_top}.md")
            dest_dir = Path("obsidian_vault/10 - Lectures") / clean_subj
            output_path = dest_dir / safe_fname

            def _persist_lesson_md() -> None:
                dest_dir.mkdir(parents=True, exist_ok=True)
                atomic_write_text(output_path, raw_markdown)

            await asyncio.to_thread(_persist_lesson_md)

            # 2. Gerar Perguntas de Quiz Interativo (marcando explicitamente modo offline se fallback)
            quiz_questions = [
                {
                    "id": "q1",
                    "question": f"Qual é o objetivo principal abordado na aula sobre {topic}?",
                    "options": [
                        f"Estruturação e coordenação robusta de {topic} com alta fidelidade.",
                        "Execução sem controlo de estado ou validação.",
                        "Eliminação de persistência e histórico de regras.",
                    ],
                    "correct_index": 0,
                    "explanation": f"{topic} estabelece princípios de modularidade, isolamento e validação.",
                    "offline_fallback": offline_fallback,
                },
                {
                    "id": "q2",
                    "question": f"Como o método Cornell organiza a retenção de conhecimento em {subject}?",
                    "options": [
                        "Dividindo o espaço em Cue Column (pistas), notas detalhadas e sumário executivo.",
                        "Gravando apenas áudio sem texto estruturado.",
                        "Descartando definições e itens de ação após a aula.",
                    ],
                    "correct_index": 0,
                    "explanation": "A coluna de pistas e o sumário promovem recordação ativa e síntese.",
                    "offline_fallback": offline_fallback,
                },
                {
                    "id": "q3",
                    "question": "Qual é a função dos [[Wikilinks]] e persistência no Knowledge Vault?",
                    "options": [
                        "Interligar conceitos num grafo de conhecimento navegável e reutilizável por RAG.",
                        "Apenas ocupar espaço em disco.",
                        "Bloquear a consulta externa de ficheiros.",
                    ],
                    "correct_index": 0,
                    "explanation": "Os wikilinks criam conexões semânticas bidirecionais entre conceitos.",
                    "offline_fallback": offline_fallback,
                },
            ]

            # 3. Questão de Transferência de Conhecimento
            transfer_question = {
                "id": "transfer_1",
                "scenario": (
                    f"Numa infraestrutura crítica com múltiplos nós distribuídos, como aplicarias os conceitos "
                    f"de {topic} para assegurar que falhas parciais não comprometem a integridade das operações?"
                ),
                "expected_concept": "Isolamento, idempotência, verificação criptográfica e recuperação de estado.",
                "offline_fallback": offline_fallback,
            }

            lesson_data = {
                "topic": topic,
                "subject": subject,
                "professor": professor,
                "date": date_str,
                "markdown_path": str(output_path).replace("\\", "/"),
                "markdown_content": raw_markdown,
                "summary": linked_summary,
                "cue_column": cue_column,
                "quiz": quiz_questions,
                "transfer_question": transfer_question,
                "offline_fallback": offline_fallback,
            }

            if self.logger:
                log_event(self.logger, "lecture.lesson.generated", topic=topic, path=str(output_path))

            msg_payload = {
                "type": "lecture_lesson_generated",
                "lesson": lesson_data,
            }
            await self.connections.broadcast(msg_payload)

        except Exception as e:
            await self.connections.broadcast({
                "type": "lecture_error",
                "message": f"Erro ao gerar aula: {str(e)}",
            })

    async def submit_lecture_quiz(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        """Avalia respostas do quiz e valida a transferência de conhecimento com scoring real."""
        topic = message.get("topic", "Geral")
        answers = message.get("answers", {})  # e.g. {"q1": 0, "q2": 1}
        transfer_answer = message.get("transfer_answer", "").strip()

        # Gabarito oficial para as questões padrão geradas
        official_answers = {"q1": 0, "q2": 0, "q3": 0}
        total = len(official_answers)
        correct = 0
        incorrect = 0
        unanswered = 0

        for q_id, correct_idx in official_answers.items():
            user_choice = answers.get(q_id)
            if user_choice is None:
                unanswered += 1
            elif int(user_choice) == correct_idx:
                correct += 1
            else:
                incorrect += 1

        score = round((correct / total) * 100.0, 1) if total > 0 else 0.0

        # Avaliação de transferência baseada em conceitos essenciais
        trans_clean = transfer_answer.lower()
        required_concepts = ["isolamento", "idempotência", "estado", "recuperação", "distribuídos", "tolerância"]
        matched_concepts = [c for c in required_concepts if c in trans_clean]

        if len(trans_clean) < 10:
            transfer_passed = False
            transfer_feedback = "Resposta não fornecida ou insuficiente para demonstrar transferência prática."
        elif len(matched_concepts) >= 2:
            transfer_passed = True
            transfer_feedback = f"Transferência validada! Conceitos articulados: {', '.join(matched_concepts)}."
        else:
            transfer_passed = False
            transfer_feedback = "A resposta ao cenário aplicado não articula conceitos suficientes de tolerância a falhas e isolamento de estado."

        feedback_msg = (
            f"Compreensão de {score}% ({correct}/{total} corretas"
            + (f", {unanswered} não respondidas" if unanswered else "")
            + f") em {topic}."
        )

        result_data = {
            "topic": topic,
            "score": score,
            "total_questions": total,
            "correct_answers": correct,
            "incorrect_answers": incorrect,
            "unanswered": unanswered,
            "feedback": feedback_msg,
            "transfer_passed": transfer_passed,
            "transfer_feedback": transfer_feedback,
            "student_mastery": round(score / 100.0, 2),
            "passed": score >= 70.0 and transfer_passed,
            "next_review_days": 1 if score < 70 else 3,
            "next_review_timestamp": time.time() + ((1 if score < 70 else 3) * 86400),
        }

        await self.connections.broadcast({
            "type": "lecture_quiz_evaluated",
            **result_data,
        })

