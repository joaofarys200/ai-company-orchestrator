"""
JARVIS OS — Study Engine Phase 7: Study Orchestration Coordinator
Interpreta pedidos naturais e follow-ups conversacionais sobre estudo utilizando
heurísticas determinísticas + inferência local Ollama (qwen3.5:9b) em JSON
estritamente validado, encaminhando a execução para StudyCapabilityRouter.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from typing import Any, Callable, Dict, List, Optional

from services.study_integration.context_manager import (
    StudyContextManager,
    normalize_match_text,
)
from services.study_integration.contracts import (
    StudyCapabilityRequest,
    StudyCapabilityResult,
    StudyCapabilityType,
)
from services.study_integration.explainer import (
    OllamaUnavailableError,
    StudyAcademicExplainer,
)
from services.study_integration.operation_manager import StudyOperationManager
from services.study_integration.router import StudyCapabilityRouter


class StudyOrchestrationCoordinator:
    """Coordenador central entre a camada conversacional JARVIS e StudyCapabilityRouter."""

    def __init__(
        self,
        study_service: Any,
        *,
        model_service: Any = None,
        intent_llm_caller: Optional[Callable[..., Any]] = None,
        explain_llm_caller: Optional[Callable[..., Any]] = None,
        router: Optional[StudyCapabilityRouter] = None,
    ) -> None:
        self.study_service = study_service
        self.model_service = model_service
        self.intent_llm_caller = intent_llm_caller
        storage_dir = getattr(study_service, "storage_dir", "data/study")
        self.context_manager = (
            router.context_manager if router else StudyContextManager(storage_dir=storage_dir)
        )
        self.operation_manager = (
            router.operation_manager if router else StudyOperationManager(storage_dir=storage_dir)
        )
        explainer = StudyAcademicExplainer(
            model_service=model_service,
            llm_caller=explain_llm_caller,
        )
        self.router = router or StudyCapabilityRouter(
            study_service,
            context_manager=self.context_manager,
            operation_manager=self.operation_manager,
            explainer=explainer,
        )

    async def handle_directive(
        self,
        *,
        prompt: str,
        chat_session_id: str = "global",
        correlation_id: str = "",
        ui_study_context: Optional[Dict[str, Any]] = None,
        history: Optional[List[Dict[str, Any]]] = None,
        on_status_event: Optional[Callable[[Any], Any]] = None,
        on_async_complete: Optional[Callable[[StudyCapabilityResult], Any]] = None,
        allow_background: bool = True,
    ) -> StudyCapabilityResult:
        ctx = self.context_manager.sync_ui_context(
            chat_session_id,
            self.study_service,
            ui_study_context,
        )

        # 1. Tentativa determinística rápida para comandos claros e follow-ups estruturais
        req = self._parse_deterministic_request(
            prompt=prompt,
            ctx=ctx,
            chat_session_id=chat_session_id,
            correlation_id=correlation_id,
        )

        # 2. Se ambíguo ou expressão livre complexa, usar qwen3.5:9b local para extração JSON estruturada
        if req is None:
            try:
                req = await self._extract_intent_with_local_llm(
                    prompt=prompt,
                    ctx=ctx,
                    history=history or [],
                    chat_session_id=chat_session_id,
                    correlation_id=correlation_id,
                )
            except OllamaUnavailableError as err:
                return StudyCapabilityResult(
                    operation_id=f"op_{correlation_id}" if correlation_id else "op_err",
                    capability="INTENT_RESOLUTION",
                    status="FAILED",
                    summary_markdown=(
                        f"Não foi possível interpretar este pedido livre com o modelo local (`qwen3.5:9b`): {err}"
                    ),
                    error_code="OLLAMA_UNAVAILABLE",
                    error_message=str(err),
                )
            except Exception as err:
                return StudyCapabilityResult(
                    operation_id=f"op_{correlation_id}" if correlation_id else "op_err",
                    capability="INTENT_RESOLUTION",
                    status="FAILED",
                    summary_markdown=(
                        f"Não consegui interpretar de forma segura que operação de estudo pretende: {err}"
                    ),
                    error_code="INTENT_EXTRACTION_FAILED",
                    error_message=str(err),
                )

        if req is None:
            return StudyCapabilityResult(
                operation_id=f"op_{correlation_id}" if correlation_id else "op_clarify",
                capability="CLARIFICATION",
                status="NEEDS_CLARIFICATION",
                summary_markdown=(
                    "Podes clarificar que ação de estudo queres executar (ex.: explicar um capítulo, "
                    "gerar flashcards, criar um teste, ver progresso ou continuar uma sessão)?"
                ),
                error_code="AMBIGUOUS_STUDY_INTENT",
            )

        return await self.router.execute(
            req,
            ui_context=ui_study_context,
            on_status_event=on_status_event,
            on_async_complete=on_async_complete,
            allow_background=allow_background,
        )

    def _parse_deterministic_request(
        self,
        *,
        prompt: str,
        ctx: Any,
        chat_session_id: str,
        correlation_id: str,
    ) -> Optional[StudyCapabilityRequest]:
        norm = normalize_match_text(prompt)
        q_count = self._extract_count(norm)
        difficulty = self._extract_difficulty(norm)
        doc_query = self._extract_explicit_doc_query(prompt, norm)
        topic_hint = self._extract_topic_hint(norm)

        # Follow-up: "Agora faz o mesmo, mas apenas sobre a metodologia"
        if any(p in norm for p in ("faz o mesmo", "o mesmo mas", "idem", "repete mas")) and ctx.last_operation_type:
            try:
                prev_cap = StudyCapabilityType(ctx.last_operation_type)
            except ValueError:
                prev_cap = StudyCapabilityType.GENERATE_FLASHCARDS
            return StudyCapabilityRequest(
                capability=prev_cap,
                correlation_id=correlation_id,
                chat_session_id=chat_session_id,
                document_id=ctx.active_document_id,
                chapter_ref=topic_hint,
                topic=topic_hint,
                question_count=q_count or ctx.last_question_count,
                difficulty=difficulty or ctx.last_difficulty,
                force_recompute=bool(topic_hint),
                raw_prompt=prompt,
            )

        # Follow-up: "Faz mais cinco perguntas" / "Quero algo mais difícil"
        if re.search(r"\bmais\s+(?:\d+|duas|tres|quatro|cinco|seis|sete|oito|nove|dez)\s+(?:perguntas|questoes)\b", norm) or (
            any(p in norm for p in ("mais dificil", "mais dificeis", "mais facil", "mais faceis", "aumenta a dificuldade"))
        ):
            return StudyCapabilityRequest(
                capability=StudyCapabilityType.CREATE_ASSESSMENT,
                correlation_id=correlation_id,
                chat_session_id=chat_session_id,
                document_id=ctx.active_document_id,
                chapter_id=ctx.active_chapter_id,
                topic=topic_hint or ctx.last_topic,
                difficulty=difficulty or ("HARD" if "difici" in norm else "EASY" if "fac" in norm else "HARD"),
                question_count=q_count or ctx.last_question_count or 5,
                force_recompute=True,
                raw_prompt=prompt,
            )

        # Follow-up: "Agora testa-me sobre isso" / "Testa se compreendi"
        if any(p in norm for p in ("testa-me", "testa me", "testar se realmente compreendi", "testar se compreendi", "active recall")):
            cap = (
                StudyCapabilityType.START_ACTIVE_RECALL
                if ("compreendi" in norm or "active recall" in norm)
                else StudyCapabilityType.CREATE_ASSESSMENT
            )
            return StudyCapabilityRequest(
                capability=cap,
                correlation_id=correlation_id,
                chat_session_id=chat_session_id,
                document_id=ctx.active_document_id,
                chapter_id=ctx.active_chapter_id,
                topic=topic_hint or ctx.last_topic,
                question_count=q_count or 5,
                difficulty=difficulty,
                raw_prompt=prompt,
            )

        # Follow-up: "Mostra-me a resposta"
        if any(p in norm for p in ("mostra-me a resposta", "mostra a resposta", "qual e a resposta", "ver resposta")) and (
            ctx.active_activity == "active_recall" or ctx.last_active_recall_prompt_id
        ):
            return StudyCapabilityRequest(
                capability=StudyCapabilityType.SUBMIT_ACTIVE_RECALL,
                correlation_id=correlation_id,
                chat_session_id=chat_session_id,
                document_id=ctx.active_document_id,
                prompt_id=ctx.last_active_recall_prompt_id,
                reveal_answer=True,
                raw_prompt=prompt,
            )

        # Follow-up: "Explica melhor essa parte"
        if any(p in norm for p in ("explica melhor", "nao percebi essa parte", "detalha essa parte", "esclarece essa passagem")) and ctx.active_document_id:
            return StudyCapabilityRequest(
                capability=StudyCapabilityType.EXPLAIN_CONCEPT_OR_CHAPTER,
                correlation_id=correlation_id,
                chat_session_id=chat_session_id,
                document_id=ctx.active_document_id,
                chapter_id=ctx.active_chapter_id,
                section_id=ctx.active_section_id,
                topic=ctx.last_topic,
                question=prompt,
                raw_prompt=prompt,
            )

        # Follow-up simples de sessão: "Continua" / "Continua a sessão de ontem" / "Pausa a sessão"
        if norm in {"continua", "continuar", "retoma", "retomar"} or any(
            p in norm
            for p in ("continua a sessao", "retoma a sessao", "sessao de ontem", "sessao que deixei", "pausa a sessao", "termina a sessao")
        ):
            action = "pause" if "pausa" in norm else ("complete" if ("termina" in norm or "conclui" in norm) else "resume")
            return StudyCapabilityRequest(
                capability=StudyCapabilityType.MANAGE_STUDY_SESSION,
                correlation_id=correlation_id,
                chat_session_id=chat_session_id,
                document_query=doc_query,
                session_action=action,
                raw_prompt=prompt,
            )

        # Cancelar operação
        if any(p in norm for p in ("cancela a geracao", "cancelar geracao", "parar geracao", "cancela o processamento")):
            return StudyCapabilityRequest(
                capability=StudyCapabilityType.CANCEL_STUDY_OPERATION,
                correlation_id=correlation_id,
                chat_session_id=chat_session_id,
                document_query=doc_query,
                raw_prompt=prompt,
            )

        # Listar documentos
        if any(p in norm for p in ("lista os documentos", "quais documentos", "que documentos tenho", "documentos de estudo", "biblioteca de estudo")):
            return StudyCapabilityRequest(
                capability=StudyCapabilityType.LIST_DOCUMENTS,
                correlation_id=correlation_id,
                chat_session_id=chat_session_id,
                raw_prompt=prompt,
            )

        # Estado / Quero estudar este documento / Quero estudar o documento X
        if any(p in norm for p in ("quero estudar", "estado deste documento", "estado do documento", "o que ja tenho para estudar")):
            return StudyCapabilityRequest(
                capability=StudyCapabilityType.GET_DOCUMENT_STATUS,
                correlation_id=correlation_id,
                chat_session_id=chat_session_id,
                document_query=doc_query,
                raw_prompt=prompt,
            )

        # Preparar material completo / analisar PDF e preparar material de estudo
        if (any(p in norm for p in ("analisa este", "analisa o pdf", "analisar o documento")) and any(
            p in norm for p in ("material de estudo", "prepara o material", "documento de estudo")
        )) or any(p in norm for p in ("gera o documento de estudo", "documento de estudo completo", "prepara o material de estudo")):
            return StudyCapabilityRequest(
                capability=StudyCapabilityType.PREPARE_STUDY_MATERIAL,
                correlation_id=correlation_id,
                chat_session_id=chat_session_id,
                document_query=doc_query,
                raw_prompt=prompt,
            )

        if any(p in norm for p in ("analisa este pdf", "analisa o documento", "raciocinio academico")):
            return StudyCapabilityRequest(
                capability=StudyCapabilityType.ANALYSE_DOCUMENT,
                correlation_id=correlation_id,
                chat_session_id=chat_session_id,
                document_query=doc_query,
                raw_prompt=prompt,
            )

        # Revisão diária / cartões pendentes
        if any(p in norm for p in ("cartoes que tenho pendentes", "rever os cartoes", "revisao diaria", "daily review", "cartoes pendentes")):
            return StudyCapabilityRequest(
                capability=StudyCapabilityType.START_DAILY_REVIEW,
                correlation_id=correlation_id,
                chat_session_id=chat_session_id,
                document_query=doc_query,
                raw_prompt=prompt,
            )

        # Progresso e lacunas
        if any(p in norm for p in ("mais dificuldades", "lacunas", "pontos fracos", "assuntos dificeis")):
            return StudyCapabilityRequest(
                capability=StudyCapabilityType.GET_KNOWLEDGE_GAPS,
                correlation_id=correlation_id,
                chat_session_id=chat_session_id,
                document_query=doc_query,
                raw_prompt=prompt,
            )
        if any(p in norm for p in ("meu progresso", "progresso de aprendizagem", "progresso de estudo")):
            return StudyCapabilityRequest(
                capability=StudyCapabilityType.GET_LEARNING_PROGRESS,
                correlation_id=correlation_id,
                chat_session_id=chat_session_id,
                document_query=doc_query,
                raw_prompt=prompt,
            )

        # Geração explícita Fase 6
        if "flashcard" in norm or "cartoes de estudo" in norm:
            return StudyCapabilityRequest(
                capability=StudyCapabilityType.GENERATE_FLASHCARDS,
                correlation_id=correlation_id,
                chat_session_id=chat_session_id,
                document_query=doc_query,
                chapter_ref=topic_hint,
                topic=topic_hint,
                card_count=q_count,
                raw_prompt=prompt,
            )
        if "cornell" in norm:
            return StudyCapabilityRequest(
                capability=StudyCapabilityType.GENERATE_CORNELL_NOTES,
                correlation_id=correlation_id,
                chat_session_id=chat_session_id,
                document_query=doc_query,
                chapter_ref=topic_hint,
                topic=topic_hint,
                raw_prompt=prompt,
            )
        if any(p in norm for p in ("faz-me um teste", "faz me um teste", "cria um teste", "criar quiz", "gera um quiz", "perguntas de avaliacao")):
            return StudyCapabilityRequest(
                capability=StudyCapabilityType.CREATE_ASSESSMENT,
                correlation_id=correlation_id,
                chat_session_id=chat_session_id,
                document_query=doc_query,
                chapter_ref=topic_hint,
                topic=topic_hint,
                difficulty=difficulty,
                question_count=q_count or 6,
                raw_prompt=prompt,
            )

        # Comparação explícita ou anafórica entre conceitos
        comp = re.search(r"diferenca\s+entre\s+(?:os?\s+|as?\s+)?(.+?)\s+e\s+(?:os?\s+|as?\s+)?(.+?)(?:\?|$|\.)", norm)
        if comp:
            ca = comp.group(1).strip(" .,?!")
            cb = comp.group(2).strip(" .,?!")
            return StudyCapabilityRequest(
                capability=StudyCapabilityType.COMPARE_CONCEPTS,
                correlation_id=correlation_id,
                chat_session_id=chat_session_id,
                document_query=doc_query,
                concept_a=ca,
                concept_b=cb,
                question=prompt,
                raw_prompt=prompt,
            )
        if any(p in norm for p in ("diferenca entre estes dois", "diferenca entre esses dois", "compara estes dois", "comparar estes dois")):
            return StudyCapabilityRequest(
                capability=StudyCapabilityType.COMPARE_CONCEPTS,
                correlation_id=correlation_id,
                chat_session_id=chat_session_id,
                document_id=ctx.active_document_id,
                document_query=doc_query,
                concept_a=ctx.recent_concepts[0] if len(ctx.recent_concepts) >= 1 else None,
                concept_b=ctx.recent_concepts[1] if len(ctx.recent_concepts) >= 2 else None,
                question=prompt,
                raw_prompt=prompt,
            )

        # Abrir vista explícita
        if re.match(r"^(?:abre|abrir|mostra)\s+(?:a\s+|o\s+)?(?:separador|leitor|progresso|biblioteca)\b", norm):
            tab = "reader" if "leitor" in norm else ("adaptive" if "progresso" in norm else "library")
            return StudyCapabilityRequest(
                capability=StudyCapabilityType.OPEN_STUDY_WORKSPACE,
                correlation_id=correlation_id,
                chat_session_id=chat_session_id,
                document_query=doc_query,
                target_tab=tab,
                raw_prompt=prompt,
            )

        # Explicações académicas diretas ("explica-me o segundo capítulo", "quais são os conceitos mais importantes...")
        if any(
            p in norm
            for p in (
                "explica-me", "explica me", "explica o ", "explica a ", "quais sao os conceitos",
                "conceitos mais importantes", "argumentos centrais", "quais os resultados",
                "metodologia deste", "capitulo ",
            )
        ):
            return StudyCapabilityRequest(
                capability=StudyCapabilityType.EXPLAIN_CONCEPT_OR_CHAPTER,
                correlation_id=correlation_id,
                chat_session_id=chat_session_id,
                document_query=doc_query,
                chapter_ref=topic_hint,
                topic=topic_hint,
                question=prompt,
                raw_prompt=prompt,
            )

        # Submissão direta de resposta a Active Recall em aberto
        if ctx.active_activity == "active_recall" and ctx.last_active_recall_prompt_id and len(prompt.split()) >= 6 and "?" not in prompt:
            return StudyCapabilityRequest(
                capability=StudyCapabilityType.SUBMIT_ACTIVE_RECALL,
                correlation_id=correlation_id,
                chat_session_id=chat_session_id,
                document_id=ctx.active_document_id,
                prompt_id=ctx.last_active_recall_prompt_id,
                answer_text=prompt,
                raw_prompt=prompt,
            )

        return None

    async def _extract_intent_with_local_llm(
        self,
        *,
        prompt: str,
        ctx: Any,
        history: List[Dict[str, Any]],
        chat_session_id: str,
        correlation_id: str,
    ) -> Optional[StudyCapabilityRequest]:
        docs = [
            {
                "document_id": d.document_id,
                "title": getattr(d, "title", d.document_id),
                "subject": getattr(d, "subject", "Geral"),
            }
            for d in (self.study_service.list_documents() or [])[:12]
        ]
        recent_hist = [
            {"role": m.get("role"), "content": str(m.get("content") or "")[:240]}
            for m in history[-4:]
            if isinstance(m, dict)
        ]
        caps_list = [c.value for c in StudyCapabilityType]

        system_prompt = (
            "És o analisador de intenções de estudo do JARVIS OS. Classifica o pedido do utilizador numa das capacidades "
            f"oficiais: {', '.join(caps_list)}.\n"
            "Devolve APENAS JSON válido com:\n"
            "{\n"
            '  "capability": "STUDY_CAPABILITY_ENUM",\n'
            '  "document_id": "id exato ou null",\n'
            '  "document_query": "nome/tema do doc se mencionado ou null",\n'
            '  "chapter_ref": "capitulo/seccao ou null",\n'
            '  "topic": "topico ou null",\n'
            '  "concept_a": "conceito 1 para COMPARE_CONCEPTS ou null",\n'
            '  "concept_b": "conceito 2 para COMPARE_CONCEPTS ou null",\n'
            '  "difficulty": "EASY|MEDIUM|HARD ou null",\n'
            '  "question_count": null,\n'
            '  "card_count": null,\n'
            '  "session_action": "start|resume|pause|complete|list ou null",\n'
            '  "target_tab": "library|reader|summary|notes|flashcards|active_recall|quiz|adaptive|knowledge ou null"\n'
            "}"
        )
        user_prompt = json.dumps(
            {
                "prompt": prompt,
                "active_context": ctx.to_dict(),
                "available_documents": docs,
                "recent_history": recent_hist,
            },
            ensure_ascii=False,
        )

        parsed = await self._invoke_local_json(system_prompt=system_prompt, user_prompt=user_prompt)
        if not isinstance(parsed, dict) or not parsed.get("capability"):
            return None

        cap_raw = str(parsed["capability"]).strip().upper()
        try:
            cap_enum = StudyCapabilityType(cap_raw)
        except ValueError as exc:
            raise ValueError(f"Capacidade devolvida pelo modelo não é válida: '{cap_raw}'") from exc

        return StudyCapabilityRequest(
            capability=cap_enum,
            correlation_id=correlation_id,
            chat_session_id=chat_session_id,
            document_id=parsed.get("document_id") or None,
            document_query=parsed.get("document_query") or None,
            chapter_ref=parsed.get("chapter_ref") or None,
            topic=parsed.get("topic") or None,
            concept_a=parsed.get("concept_a") or None,
            concept_b=parsed.get("concept_b") or None,
            difficulty=parsed.get("difficulty") or None,
            question_count=parsed.get("question_count"),
            card_count=parsed.get("card_count"),
            session_action=parsed.get("session_action") or None,
            target_tab=parsed.get("target_tab") or None,
            question=prompt,
            raw_prompt=prompt,
        )

    async def _invoke_local_json(self, *, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        if self.intent_llm_caller is not None:
            res = self.intent_llm_caller(
                operation="study_intent_resolution",
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                expect_json=True,
            )
            if asyncio.iscoroutine(res):
                res = await res
            if isinstance(res, dict):
                return res
            if isinstance(res, str):
                parsed = StudyAcademicExplainer._safe_parse_json(res)
                if parsed:
                    return parsed
            raise ValueError("JSON inválido devolvido na resolução de intenção.")

        if self.model_service is not None:
            from backend.model_harness.contracts import OutputFormat

            model_name = os.getenv("OLLAMA_STUDY_MODEL", os.getenv("OLLAMA_MODEL", "qwen3.5:9b"))
            try:
                resp = await self.model_service.execute(
                    provider="ollama",
                    model=model_name,
                    operation="study_intent_resolution",
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    output_format=OutputFormat.JSON,
                    temperature=0.0,
                    max_output_tokens=512,
                    timeout_seconds=30.0,
                )
            except Exception as exc:
                raise OllamaUnavailableError(str(exc)) from exc
            parsed = (
                resp.structured_output
                if isinstance(resp.structured_output, dict)
                else StudyAcademicExplainer._safe_parse_json(resp.raw_text)
            )
            if parsed:
                return parsed
            raise ValueError("Resposta JSON malformada do modelo local.")

        from services.study_ai_engine import invoke_study_llm_observable

        parsed, telemetry = await asyncio.to_thread(
            invoke_study_llm_observable,
            operation="study_intent_resolution",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            expect_json=True,
            temperature=0.0,
            max_output_tokens=512,
            timeout_seconds=30.0,
        )
        if isinstance(parsed, dict):
            return parsed
        raise OllamaUnavailableError(str(telemetry.get("error") or "Modelo Ollama indisponível."))

    @staticmethod
    def _extract_count(norm: str) -> Optional[int]:
        word_nums = {
            "um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4,
            "cinco": 5, "seis": 6, "sete": 7, "oito": 8, "nove": 9, "dez": 10,
            "doze": 12, "quinze": 15, "vinte": 20,
        }
        m = re.search(r"\b(\d{1,2})\s+(?:perguntas|questoes|cartoes|flashcards)\b", norm)
        if m:
            return int(m.group(1))
        for word, val in word_nums.items():
            if re.search(rf"\b{word}\s+(?:perguntas|questoes|cartoes|flashcards)\b", norm):
                return val
        return None

    @staticmethod
    def _extract_difficulty(norm: str) -> Optional[str]:
        if any(w in norm for w in ("dificil", "dificeis", "hard", "avancado", "avancada")):
            return "HARD"
        if any(w in norm for w in ("facil", "faceis", "basico", "basica", "easy")):
            return "EASY"
        if any(w in norm for w in ("medio", "media", "intermedio", "medium")):
            return "MEDIUM"
        return None

    @staticmethod
    def _extract_explicit_doc_query(prompt: str, norm: str) -> Optional[str]:
        q = re.search(r'["«]([^"»]{3,80})["»]', prompt or "")
        if q:
            return q.group(1).strip()
        m = re.search(
            r"(?:documento|artigo|paper|pdf|livro)\s+(?:sobre|de|do|da|chamado|intitulado)\s+([a-z0-9 \-_]{3,60})",
            norm,
        )
        if m:
            cand = m.group(1).strip()
            if cand.split()[0] not in {"este", "esta", "esse", "essa", "estudo", "atual"}:
                return cand
        return None

    @staticmethod
    def _extract_topic_hint(norm: str) -> Optional[str]:
        for kw in (
            "metodologia", "resultados", "conclusoes", "conclusao",
            "introducao", "arquitetura", "avaliacao", "experimentos",
        ):
            if kw in norm:
                return kw
        m = re.search(r"(?:apenas\s+)?sobre\s+(?:a|o|os|as)?\s*([a-z0-9 \-]{3,50})", norm)
        if m:
            cand = m.group(1).strip(" .,?!")
            if cand and cand.split()[0] not in {"este", "esta", "isso", "isto", "esse", "essa"}:
                return cand
        return None
