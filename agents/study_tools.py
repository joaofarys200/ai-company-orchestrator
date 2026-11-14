"""
JARVIS OS — Study Engine Phase 7: Validated Agent Tool Contracts & Executor
Expõe capacidades selecionadas e seguras do Study Engine para os agentes e
orquestrador JARVIS através do StudyCapabilityRouter, validando argumentos e
limites de execução sem duplicar lógica de domínio.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, Optional

from services.study_integration.contracts import (
    StudyCapabilityRequest,
    StudyCapabilityType,
    VALID_DIFFICULTIES,
    normalize_chat_session_id,
)
from services.study_integration.router import StudyCapabilityRouter


STUDY_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "study_list_documents",
        "description": "Lista os documentos existentes na Biblioteca de Estudo e o respetivo estado de prontidão académica.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "study_get_document_status",
        "description": "Consulta o estado completo de processamento, Fases 2–5 e modos Fase 6 de um documento de estudo.",
        "input_schema": {
            "type": "object",
            "properties": {
                "document_id": {"type": "string", "description": "ID canónico do documento de estudo."},
            },
            "required": ["document_id"],
        },
    },
    {
        "name": "study_analyse_document",
        "description": "Executa ou reutiliza a análise académica (Fase 3: AcademicReasoningDossier) de um documento existente.",
        "input_schema": {
            "type": "object",
            "properties": {
                "document_id": {"type": "string", "description": "ID canónico do documento de estudo."},
                "force_recompute": {"type": "boolean", "description": "Se true, recalcula mesmo havendo cache."},
            },
            "required": ["document_id"],
        },
    },
    {
        "name": "study_explain_topic",
        "description": "Explica um capítulo, metodologia, passagem ou conceito de um documento de estudo com classificação epistémica rigorosa e citações.",
        "input_schema": {
            "type": "object",
            "properties": {
                "document_id": {"type": "string", "description": "ID canónico do documento de estudo."},
                "question": {"type": "string", "description": "Pergunta, pedido de explicação ou tema académico."},
                "chapter_ref": {"type": "string", "description": "Capítulo ou secção opcional (ex: 'capítulo 2', 'metodologia')."},
            },
            "required": ["document_id", "question"],
        },
    },
    {
        "name": "study_generate_study_document",
        "description": "Gera o plano editorial (Fase 4) e documento final de estudo PDF/DOCX (Fase 5) para um documento existente.",
        "input_schema": {
            "type": "object",
            "properties": {
                "document_id": {"type": "string", "description": "ID canónico do documento de estudo."},
                "force_recompute": {"type": "boolean", "description": "Força regeneração completa."},
            },
            "required": ["document_id"],
        },
    },
    {
        "name": "study_generate_flashcards",
        "description": "Gera ou recupera flashcards adaptativos (Fase 6 FlashcardEngine) fundamentados num documento.",
        "input_schema": {
            "type": "object",
            "properties": {
                "document_id": {"type": "string", "description": "ID canónico do documento de estudo."},
                "topic": {"type": "string", "description": "Capítulo ou tópico opcional para focar."},
                "card_count": {"type": "integer", "description": "Número alvo de cartões (1 a 50)."},
            },
            "required": ["document_id"],
        },
    },
    {
        "name": "study_generate_cornell_notes",
        "description": "Gera Cornell Notes estruturadas (Fase 6 CornellNotesEngine) com síntese e pistas de revisão.",
        "input_schema": {
            "type": "object",
            "properties": {
                "document_id": {"type": "string", "description": "ID canónico do documento de estudo."},
                "topic": {"type": "string", "description": "Foco opcional de capítulo ou secção."},
            },
            "required": ["document_id"],
        },
    },
    {
        "name": "study_create_assessment",
        "description": "Cria um teste interativo (Fase 6 AssessmentEngine) com foco, número de perguntas e dificuldade validados.",
        "input_schema": {
            "type": "object",
            "properties": {
                "document_id": {"type": "string", "description": "ID canónico do documento de estudo."},
                "topic": {"type": "string", "description": "Capítulo ou tópico opcional (ex: 'resultados', 'metodologia')."},
                "question_count": {"type": "integer", "description": "Número de perguntas (1 a 30)."},
                "difficulty": {"type": "string", "description": "EASY, MEDIUM ou HARD."},
            },
            "required": ["document_id"],
        },
    },
    {
        "name": "study_start_active_recall",
        "description": "Inicia ou recupera questões de Active Recall (Fase 6 ActiveRecallEngine) para testar compreensão.",
        "input_schema": {
            "type": "object",
            "properties": {
                "document_id": {"type": "string", "description": "ID canónico do documento de estudo."},
                "topic": {"type": "string", "description": "Tópico opcional."},
            },
            "required": ["document_id"],
        },
    },
    {
        "name": "study_start_daily_review",
        "description": "Calcula a fila de revisão diária SM-2/Active Recall e cria uma sessão persistente mista.",
        "input_schema": {
            "type": "object",
            "properties": {
                "document_id": {"type": "string", "description": "ID canónico do documento de estudo."},
            },
            "required": ["document_id"],
        },
    },
    {
        "name": "study_get_learning_progress",
        "description": "Devolve métricas reais de progresso, precisão e lacunas de conhecimento (Fase 6 LearningProgressEngine).",
        "input_schema": {
            "type": "object",
            "properties": {
                "document_id": {"type": "string", "description": "ID canónico do documento de estudo."},
            },
            "required": ["document_id"],
        },
    },
    {
        "name": "study_resume_session",
        "description": "Retoma uma sessão de estudo existente (Fase 6 SessionManager) preservando o índice e itens reais.",
        "input_schema": {
            "type": "object",
            "properties": {
                "study_session_id": {"type": "string", "description": "ID opcional da sessão de estudo a retomar."},
                "document_id": {"type": "string", "description": "ID opcional do documento associado à sessão."},
            },
        },
    },
]

STUDY_TOOL_NAMES = frozenset(t["name"] for t in STUDY_TOOL_DEFINITIONS)
STUDY_READ_TOOLS = frozenset({
    "study_list_documents",
    "study_get_document_status",
    "study_explain_topic",
    "study_get_learning_progress",
})
STUDY_WRITE_TOOLS = STUDY_TOOL_NAMES - STUDY_READ_TOOLS

_TOOL_TO_CAPABILITY: Dict[str, StudyCapabilityType] = {
    "study_list_documents": StudyCapabilityType.LIST_DOCUMENTS,
    "study_get_document_status": StudyCapabilityType.GET_DOCUMENT_STATUS,
    "study_analyse_document": StudyCapabilityType.ANALYSE_DOCUMENT,
    "study_explain_topic": StudyCapabilityType.EXPLAIN_CONCEPT_OR_CHAPTER,
    "study_generate_study_document": StudyCapabilityType.PREPARE_STUDY_MATERIAL,
    "study_generate_flashcards": StudyCapabilityType.GENERATE_FLASHCARDS,
    "study_generate_cornell_notes": StudyCapabilityType.GENERATE_CORNELL_NOTES,
    "study_create_assessment": StudyCapabilityType.CREATE_ASSESSMENT,
    "study_start_active_recall": StudyCapabilityType.START_ACTIVE_RECALL,
    "study_start_daily_review": StudyCapabilityType.START_DAILY_REVIEW,
    "study_get_learning_progress": StudyCapabilityType.GET_LEARNING_PROGRESS,
    "study_resume_session": StudyCapabilityType.MANAGE_STUDY_SESSION,
}

_SCHEMA_BY_NAME: Dict[str, Dict[str, Any]] = {
    t["name"]: t["input_schema"] for t in STUDY_TOOL_DEFINITIONS
}


def validate_study_tool_arguments(tool_name: str, tool_input: Any) -> Dict[str, Any]:
    """Valida estritamente nome da tool, chaves permitidas, tipos e limites."""
    if tool_name not in STUDY_TOOL_NAMES:
        raise ValueError(f"Tool de estudo desconhecida ou não registada: '{tool_name}'.")
    if tool_input is None:
        args: Dict[str, Any] = {}
    elif isinstance(tool_input, dict):
        args = dict(tool_input)
    else:
        raise ValueError("Os argumentos da tool de estudo devem ser um objeto JSON.")

    schema = _SCHEMA_BY_NAME[tool_name]
    allowed_props = schema.get("properties") or {}
    required = schema.get("required") or []

    unknown_keys = sorted(set(args.keys()) - set(allowed_props.keys()))
    if unknown_keys:
        raise ValueError(f"Argumentos não permitidos em '{tool_name}': {', '.join(unknown_keys)}.")

    for req_key in required:
        val = args.get(req_key)
        if not isinstance(val, str) or not val.strip():
            raise ValueError(f"'{tool_name}' exige '{req_key}' como texto não vazio.")

    for key, val in args.items():
        if val is None:
            continue
        expected_type = (allowed_props.get(key) or {}).get("type")
        if expected_type == "string":
            if not isinstance(val, str):
                raise ValueError(f"O argumento '{key}' deve ser texto.")
            if key == "document_id":
                from services.study_fs import safe_document_id
                try:
                    safe_document_id(val)
                except ValueError:
                    raise ValueError(f"O identificador '{key}' contém caracteres inválidos.")
                if any(bad in val for bad in (";", "|", "`")):
                    raise ValueError(f"O identificador '{key}' contém caracteres inválidos.")
        elif expected_type == "integer":
            if isinstance(val, bool) or not isinstance(val, int):
                raise ValueError(f"O argumento '{key}' deve ser um inteiro.")
        elif expected_type == "boolean":
            if not isinstance(val, bool):
                raise ValueError(f"O argumento '{key}' deve ser booleano.")

    if "question_count" in args and args["question_count"] is not None:
        if not (1 <= int(args["question_count"]) <= 30):
            raise ValueError("question_count deve estar entre 1 e 30.")
    if "card_count" in args and args["card_count"] is not None:
        if not (1 <= int(args["card_count"]) <= 50):
            raise ValueError("card_count deve estar entre 1 e 50.")
    if "difficulty" in args and args["difficulty"] is not None:
        if str(args["difficulty"]).strip().upper() not in VALID_DIFFICULTIES:
            raise ValueError(
                f"difficulty deve ser um de: {', '.join(sorted(VALID_DIFFICULTIES))}."
            )
    return args


def _resolve_shared_study_service(study_service: Any = None) -> Any:
    if study_service is not None:
        return study_service
    try:
        from backend.runtime_bridge import get_application_services

        app_services = get_application_services()
        if app_services and getattr(app_services, "study_service", None) is not None:
            return app_services.study_service
    except Exception:
        pass
    from services.study_service import StudyService

    return StudyService()


async def execute_study_tool(
    tool_name: str,
    tool_input: Any,
    *,
    study_service: Any = None,
    router: Optional[StudyCapabilityRouter] = None,
    chat_session_id: Optional[str] = None,
    require_chat_session: bool = False,
    timeout_seconds: float = 120.0,
) -> str:
    """Executa uma tool de estudo de forma segura e validada via StudyCapabilityRouter."""
    try:
        args = validate_study_tool_arguments(tool_name, tool_input)
        capability = _TOOL_TO_CAPABILITY[tool_name]
        normalized_sid = normalize_chat_session_id(chat_session_id)
        if require_chat_session and normalized_sid is None:
            return json.dumps(
                {
                    "status": "NEEDS_CLARIFICATION",
                    "capability": capability.value,
                    "error_code": "MISSING_CHAT_SESSION",
                    "error_message": (
                        "Identificador canónico de conversa em falta: "
                        "não é permitido executar ferramentas de estudo em contexto global partilhado."
                    ),
                    "summary_markdown": (
                        "Falta o identificador da conversa para executar esta ação de estudo "
                        "com isolamento de contexto."
                    ),
                },
                ensure_ascii=False,
            )
        svc = _resolve_shared_study_service(study_service)
        shared_coord = getattr(svc, "_study_coordinator", None)
        active_router = router or (shared_coord.router if shared_coord is not None else StudyCapabilityRouter(svc))
        req = StudyCapabilityRequest(
            capability=capability,
            chat_session_id=normalized_sid,
            document_id=args.get("document_id"),
            chapter_ref=args.get("chapter_ref"),
            topic=args.get("topic"),
            question=args.get("question"),
            question_count=args.get("question_count"),
            card_count=args.get("card_count"),
            difficulty=args.get("difficulty"),
            study_session_id=args.get("study_session_id"),
            session_action="resume" if tool_name == "study_resume_session" else None,
            force_recompute=bool(args.get("force_recompute", False)),
            raw_prompt=str(args.get("question") or args.get("topic") or tool_name),
        )
        res = await asyncio.wait_for(
            active_router.execute(req, allow_background=False),
            timeout=timeout_seconds,
        )
        return json.dumps(res.to_dict(), ensure_ascii=False)
    except asyncio.TimeoutError:
        return json.dumps(
            {
                "status": "FAILED",
                "error_code": "TOOL_TIMEOUT",
                "error_message": f"Tempo limite ({timeout_seconds}s) excedido ao executar '{tool_name}'.",
            },
            ensure_ascii=False,
        )
    except Exception as exc:
        return json.dumps(
            {
                "status": "FAILED",
                "error_code": "INVALID_TOOL_EXECUTION",
                "error_message": str(exc),
            },
            ensure_ascii=False,
        )
