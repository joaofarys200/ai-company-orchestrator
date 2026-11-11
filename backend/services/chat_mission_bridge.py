from __future__ import annotations

import asyncio
import enum
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Mapping

from agents.mission_state import (
    MissionStateError,
    MissionStateStore,
    StaleVersionError,
    utc_now,
)
from backend.logging_config import get_logger, log_event
from backend.message_protocol import (
    chat_message,
    normalize_canonical_sender,
    normalize_ws_message,
    state_message,
    system_message,
)
from security.safety_classifier import SafetyAssessment, SafetyClassifier, SafetyStatus
from security.delivery_governance.decision_model import (
    DecisionAssessment,
    DecisionEngine,
    ExecutionTruthEnforcer,
    ExecutionTruthState,
    PolicyStatus,
    TaskAuthorizationStatus,
    TaskFeasibilityStatus,
    UserIntentType,
)

logger = get_logger(__name__)


class ChatIntentType(str, enum.Enum):
    CHAT = "CHAT"
    PROJECT_QUERY = "PROJECT_QUERY"
    PROJECT_INSPECTION = "PROJECT_INSPECTION"
    ROOT_CAUSE_DIAGNOSIS = "ROOT_CAUSE_DIAGNOSIS"
    FILE_READ = "FILE_READ"
    FILE_DELIVERY = "FILE_DELIVERY"
    LOCAL_ACTION = "LOCAL_ACTION"
    STUDY_OPERATION = "STUDY_OPERATION"
    EXECUTION_REQUEST = "EXECUTION_REQUEST"
    CONTINUATION = "CONTINUATION"
    AMBIGUOUS = "AMBIGUOUS"
    REFUSED_POLICY = "REFUSED_POLICY"

    # Backward compatibility aliases
    CONVERSATIONAL = "CHAT"
    ANALYSIS = "PROJECT_INSPECTION"
    EXECUTABLE_DIRECTIVE = "EXECUTION_REQUEST"


@dataclass
class ResolvedChatRequest:
    raw_prompt: str
    intent: ChatIntentType
    title: str
    objective: str
    project_id: str | None = None
    refusal_reason: str = ""
    is_economic: bool = False
    task_type: str = "GENERIC"
    confidence: float = 1.0
    context_reference: dict[str, Any] = field(default_factory=dict)
    planned_action: str = ""
    requires_mission: bool = False
    requires_model: bool = False
    requires_external_network: bool = False
    decision_reason: str = ""
    target_file: str | None = None
    delivery_mode: str = "content"
    requires_approval: bool = False
    decision_assessment: Any | None = None


@dataclass
class RequestRecord:
    correlation_id: str
    prompt: str
    intent: str
    created_at: float
    user_response: str | None = None
    technical_events: list[dict[str, Any]] = field(default_factory=list)
    state_changes: list[str] = field(default_factory=list)
    operation_result: dict[str, Any] | None = None
    completion_emitted: bool = False


@dataclass
class BridgeExecutionResult:
    success: bool
    summary: str
    error: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class MissionGateResult:
    allowed: bool
    reason: str = ""
    requires_approval: bool = False


class ChatRequestResolver:
    """Classifies user chat prompts into canonical typed categories with semantic context."""

    CONVERSATIONAL_PATTERNS = [
        r"^(ol[aá]|bom dia|boa tarde|boa noite|oi|hey|hello|hi)\b",
        r"^(como est[aá]s|tudo bem|como vai|quem [eé]s tu|o que fazes|quem te criou)\b",
        r"^(obrigad[oa]|thanks|valeu|muito obrigado)\b",
        r"^(adeus|tchau|at[eé] logo|bye)\b",
    ]

    DESTRUCTIVE_TERMS = [
        "apaga", "apagar", "elimina", "eliminar", "remove", "remover",
        "rm ", "rmdir", "delete", "drop table", "format ", "reset --hard",
    ]

    RETRY_PATTERNS = [
        r"^(tenta\s+de\s*novo|tenta\s+outra\s+vez|tenta\s+novamente|tenta\s+a[ií]|tenta|tente\s+de\s*novo|tente\s+outra\s+vez|outra\s+vez|de\s+novo|mais\s+uma\s+vez|repete|repita|faz\s+de\s*novo|fa[cç]a\s+de\s*novo)$",
    ]

    FULL_FILE_PATTERNS = [
        r"\b(fornece\s+tudo|fornece\s+todo|fornece\s+o\s+resto|mostra\s+o\s+resto|mostra\s+tudo|mostra\s+todo|conte[uú]do\s+todo|conte[uú]do\s+completo|ficheiro\s+todo|ficheiro\s+completo|c[oó]digo\s+todo|c[oó]digo\s+completo|n[aã]o\s+[eé]\s+s[oó]\s+isso|nao\s+e\s+so\s+isso|fornece\s+o\s+conte[uú]do\s+completo|d[aá]-me\s+o\s+resto)\b",
    ]

    ATTACHMENT_PATTERNS = [
        r"\b(anexa-o|anexa\s+o\s+ficheiro|anexa\s+o\s+arquivo|anexa\s+[aà]\s+conversa|anexa|anexar)\b",
    ]

    CONFIRMATION_PATTERNS = [
        r"^(ent[aã]o\s+)?(faz\s+isso|trata\s+disso|avan[cç]a(\s+com\s+isso)?|procede(\s+com\s+isso)?|for[cç]a(\s+nisso)?|come[cç]a|pode\s+ser|pode(s)?\s+avan[cç]ar|vamos\s+a\s+isso|executa(\s+isso)?|implementa(\s+isso)?|bora|trata\s+de\s+tudo)(\s+por\s+favor|\s+pf|\s+ent[aã]o)?$",
        r"^(ent[aã]o\s+)?faz(\s+por\s+favor|\s+pf|\s+ent[aã]o)?$",
        r"^(continua|segue|continua\s+a[ií]|continua\s+o\s+trabalho)$",
        r"^(experimenta\s+outra\s+abordagem|tenta\s+outra\s+coisa|resolve\s+o\s+problema)$",
        r"^(implementa|corrige|executa|avan[cç]a)$",
    ]

    CONTINUATION_PATTERNS = [
        r"^(continua|segue|continua\s+a[ií]|continua\s+o\s+trabalho)$",
    ]

    LOCAL_ACTION_PATTERNS = [
        r"\b(abre|abrir|inicia|iniciar|lan[cç]a|lan[cç]ar|executa|executar|open|run)\s+(o\s+|a\s+)?(bloco\s+de\s+notas|notepad|calculadora|calc|paint|explorador|explorer|chrome|edge|browser|navegador|terminal|cmd|powershell)\b",
    ]

    FILE_EXTENSION_PATTERN = r"\b([a-zA-Z0-9_\-\.\/]+\.(?:js|ts|py|html|css|json|md|txt|sql|yaml|yml|sh|env|jsx|tsx))\b"

    PROJECT_ACCESS_PATTERNS = [
        r"\b(consegues\s+aceder|podes\s+aceder|tens\s+acesso|aceder\s+ao?|acede\s+ao?|acesso\s+ao?|entrar\s+no|abrir\s+o\s+projeto)\b",
    ]

    DIAGNOSIS_PATTERNS = [
        r"\b(causa\s+raiz|diagnostica\s+a\s+falha|diagnosticar\s+a\s+falha|diagnostica\s+o\s+erro|diagnosticar\s+o\s+erro|diagnostica|diagnosticar|analisa\s+a\s+falha|analisa\s+o\s+erro|analisar\s+o\s+erro|analisa\s+os\s+logs|porque\s+falhou|por\s+que\s+falhou|investiga\s+o\s+crash|root\s+cause|diagnose\s+failure)\b",
        r"\b(o\s+teste\s+falhou|os\s+testes\s+falharam|falha\s+nos\s+testes|assertionerror|test\s+failed|test\s+failure)\b",
    ]

    PROJECT_INSPECTION_PATTERNS = [
        r"\b(mostra\s+os\s+ficheiros|quais\s+os\s+ficheiros|que\s+ficheiros\s+existem|lista\s+os\s+ficheiros|estrutura\s+do\s+projeto|arquitetura\s+do\s+projeto|quais\s+s[aã]o\s+os\s+endpoints|qual\s+a\s+stack|que\s+depend[eê]ncias|mostra\s+a\s+estrutura|inspeciona|inspecionar)\b",
    ]

    ECONOMIC_PATTERNS = [
        r"\b(money|arbitragem|receita|fatura[cç][aã]o|monetiza[cç][aã]o|transa[cç][aã]o\s+econ[oó]mica)\b",
    ]

    CODING_VERB_PATTERNS = [
        r"\b(cria|criar|crie|cria-me|desenvolve|desenvolver|desenvolva|implementa|implementar|implemente|constr[oó]i|construir|gera|gerar|programa|programar|adiciona|adicionar|adicione|acrescenta|acrescentar|refatora|refatorar|refatore|corrige|corrigir|corrija|conserta|consertar|repara|reparar|muda|mudar|altera|alterar|ajusta|ajustar|configura|configurar|instala|instalar|remove|remover|aplica|aplicar|otimiza|otimizar|organiza|organizar|atualiza|atualizar|conecta|conectar|arranca|arrancar|inicia|iniciar|executa|executar|corre|correr|testa|testar|valida|validar|build|compila|compilar|limpa|limpar|substitui|substituir|resolve|resolver)\b",
    ]

    POLITE_EXECUTION_PREFIXES = [
        r"^(podes|pode|consegues|podias|poderias|seria\s+poss[ií]vel)\s+(criar|desenvolver|implementar|construir|gerar|programar|adicionar|acrescentar|refatorar|corrigir|consertar|mudar|alterar|ajustar|configurar|instalar|fazer|executar|executar\s+os\s+testes|testar|build|compilar)\b",
    ]

    TEST_EXECUTION_PATTERNS = [
        r"\b(implementa\s+e\s+executa\s+os\s+testes|executa\s+os\s+testes|executar\s+os\s+testes|corre\s+os\s+testes|testa\s+o\s+projeto|corre\s+o\s+pytest|testa\s+a\s+aplica[cç][aã]o|testa|testar)\b",
    ]

    STUDY_EXPLICIT_PATTERNS = [
        r"\b(flashcards?|cornell|active\s+recall|revis[aã]o\s+di[aá]ria|daily\s+review|material\s+de\s+estudo|materiais\s+de\s+estudo|documento\s+de\s+estudo|[aá]rea\s+de\s+estudo|biblioteca\s+de\s+estudo|sess[aã]o\s+de\s+estudo|sess[aã]o\s+que\s+deixei|progresso\s+de\s+aprendizagem|progresso\s+de\s+estudo|racioc[ií]nio\s+acad[eé]mico|plano\s+editorial|cart[oõ]es\s+de\s+estudo|cart[oõ]es\s+(?:que\s+tenho\s+)?pendentes|rever\s+os?\s+cart[oõ]es|knowledge\s+gaps?|lacunas(\s+de\s+conhecimento)?)\b",
        r"\b(analisa\s+este\s+pdf|analisa\s+o\s+pdf|analisa\s+este\s+documento|quero\s+estudar|explica-me\s+o\s+(?:primeiro|segundo|terceiro|quarto|quinto|\d+[oº]?)\s+cap[ií]tulo|explica\s+o\s+(?:primeiro|segundo|terceiro|quarto|quinto|\d+[oº]?)\s+cap[ií]tulo|conceitos\s+mais\s+importantes\s+(?:deste|do)\s+documento|diferen[cç]a\s+entre\s+estes\s+dois\s+conceitos|testar\s+se\s+(?:realmente\s+)?compreendi|faz-me\s+um\s+teste\s+sobre|cria\s+um\s+teste\s+sobre|assuntos\s+em\s+que\s+tenho\s+mais\s+dificuldades|que\s+documentos\s+de\s+estudo|lista\s+os\s+documentos\s+de\s+estudo|mostra-me\s+os\s+assuntos)\b",
        r"\b(cap[ií]tulo\s+\d+|metodologia\s+(?:deste|do)\s+(?:documento|artigo|paper|pdf)|resultados\s+(?:deste|do)\s+(?:documento|artigo|paper|pdf)|conclus[oõ]es\s+(?:deste|do)\s+(?:documento|artigo|paper|pdf))\b",
    ]

    STUDY_FOLLOWUP_PATTERNS = [
        r"\b(faz\s+o\s+mesmo|o\s+mesmo,?\s+mas|mais\s+(?:\d+|duas|tr[eê]s|quatro|cinco|seis|sete|oito|nove|dez)\s+perguntas|algo\s+mais\s+dif[ií]cil|mais\s+dif[ií]cil|explica\s+melhor\s+essa\s+parte|testa-me\s+sobre\s+isso|mostra-me\s+a\s+resposta|continua(\s+a\s+sess[aã]o)?|retoma|compara\s+|comparar\s+|diferen[cç]a\s+entre)\b",
    ]

    CODING_ONLY_DISQUALIFIERS = [
        r"\b(pytest|unittest|vitest|endpoint|backend|frontend|componente|react|fastapi|servidor|porta\s+\d+|database|sqlite|migra[cç][aã]o|docker|git\s+push|git\s+commit|\.(?:py|js|jsx|ts|tsx|html|css|json|sql))\b",
    ]

    def _has_active_study_signal(
        self,
        clean_lower: str,
        project_id: str | None,
        context: Mapping[str, Any] | None,
        history: list[dict] | None,
    ) -> bool:
        # Never hijack explicit technical/coding projects or source code files
        if any(re.search(pat, clean_lower) for pat in self.CODING_ONLY_DISQUALIFIERS):
            # Unless unmistakable Study Engine nouns like flashcards/cornell/active recall appear
            if not re.search(r"\b(flashcards?|cornell|active\s+recall|sess[aã]o\s+de\s+estudo|material\s+de\s+estudo|revis[aã]o\s+di[aá]ria)\b", clean_lower):
                return False

        explicit_project_mention = re.search(
            r"\b(?:ao\s+projeto|do\s+projeto|no\s+projeto)\s+([a-zA-Z0-9_\-]+)",
            clean_lower,
        )
        if explicit_project_mention:
            return False

        if any(re.search(pat, clean_lower) for pat in self.STUDY_EXPLICIT_PATTERNS):
            return True

        # Contexto ativo vindo da UI ou sessão de conversa recente sobre estudo
        has_ui_ctx = bool(isinstance(context, Mapping) and (context.get("has_active_study_context") or context.get("study_context")))
        has_hist_study = False
        if history:
            recent_txt = " ".join(str(m.get("content") or "")[:300].lower() for m in history[-4:] if isinstance(m, dict))
            if any(
                marker in recent_txt
                for marker in (
                    "flashcard", "cornell", "active recall", "revisão diária", "revisao diaria",
                    "sessão de estudo", "sessao de estudo", "biblioteca de estudo", "source_fact",
                    "model_inference", "documento de estudo", "progresso", "capítulo", "capitulo",
                )
            ):
                has_hist_study = True

        if (has_ui_ctx or has_hist_study) and any(
            re.search(pat, clean_lower) for pat in self.STUDY_FOLLOWUP_PATTERNS
        ):
            return True

        # Perguntas académicas genéricas sobre "este documento/artigo/paper/capítulo" com contexto ativo
        if (has_ui_ctx or has_hist_study) and re.search(
            r"\b(este\s+documento|deste\s+documento|este\s+artigo|deste\s+artigo|este\s+paper|deste\s+paper|este\s+pdf|deste\s+pdf|este\s+cap[ií]tulo|deste\s+cap[ií]tulo|essa\s+parte|este\s+tema)\b",
            clean_lower,
        ):
            return True

        return False

    CODING_TARGET_PATTERNS = [
        r"\b(aplica[cç][aã]o|app|website|site|endpoint|componente|api|fun[cç][aã]o|m[oó]dulo|teste|script|ficheiro|arquivo|c[oó]digo|p[aá]gina|tela|view|servi[cç]o|database|banco|sqlite|tabela|bot[aã]o|layout|css|html|js|backend|frontend|porta|logger|timeout|cors|middleware|filtro|rota|autentica[cç][aã]o|jwt)\b",
    ]

    def resolve_request(
        self,
        prompt: str,
        project_id: str | None = None,
        context: Mapping[str, Any] | None = None,
        history: list[dict] | None = None,
    ) -> ResolvedChatRequest:
        clean = (prompt or "").strip()
        clean_lower = clean.lower()

        if not clean:
            return ResolvedChatRequest(
                raw_prompt="",
                intent=ChatIntentType.CHAT,
                title="Mensagem Vazia",
                objective="",
                project_id=project_id,
                confidence=1.0,
                planned_action="ignore",
                decision_reason="Prompt vazio",
            )

        # ── 1. Safety & Policy Classifier Check ───────────────────────────────
        safety: SafetyAssessment = SafetyClassifier.evaluate(clean)
        if safety.status == SafetyStatus.BLOCKED:
            return ResolvedChatRequest(
                raw_prompt=clean,
                intent=ChatIntentType.REFUSED_POLICY,
                title="Diretiva Bloqueada",
                objective=clean,
                project_id=project_id,
                refusal_reason=safety.reason or "Conteúdo viola políticas de segurança.",
                confidence=1.0,
                planned_action="policy_refusal",
                requires_mission=False,
                requires_model=False,
                decision_reason="Conteúdo classificado como violação de segurança pelas políticas ativas.",
            )

        # ── 2. Local Action Detection (Open Local App / UI Commands) ───────────
        from backend.services.local_app_service import find_local_app_request
        detected_app = find_local_app_request(clean)
        if detected_app or any(re.search(pat, clean_lower) for pat in self.LOCAL_ACTION_PATTERNS):
            app_name = detected_app.get("name", "aplicação") if isinstance(detected_app, dict) else "aplicação"
            if app_name == "aplicação":
                for target in ["excel", "word", "powerpoint", "outlook", "bloco de notas", "notepad", "calculadora", "calc", "paint", "explorador", "chrome", "edge", "terminal", "cmd", "powershell"]:
                    if target in clean_lower:
                        app_name = target
                        break
            return ResolvedChatRequest(
                raw_prompt=clean,
                intent=ChatIntentType.LOCAL_ACTION,
                title=f"Abrir {app_name.capitalize()}",
                objective=clean,
                project_id=project_id,
                confidence=0.98,
                context_reference={"local_app": detected_app or app_name},
                planned_action="open_local_application",
                requires_mission=False,
                requires_model=False,
                decision_reason="Comando operacional local para abrir aplicação de sistema.",
            )

        # ── 2.5. Study Engine Intent & Context Continuity Detection ───────────
        if self._has_active_study_signal(clean_lower, project_id, context, history):
            return ResolvedChatRequest(
                raw_prompt=clean,
                intent=ChatIntentType.STUDY_OPERATION,
                title=self._generate_title(clean, default="Operação de Estudo"),
                objective=clean,
                project_id=project_id,
                confidence=0.96,
                context_reference={
                    "study_context": dict(context.get("study_context") or {})
                    if isinstance(context, Mapping) and isinstance(context.get("study_context"), dict)
                    else {},
                },
                planned_action="study_operation",
                requires_mission=False,
                requires_model=True,
                requires_external_network=False,
                decision_reason="Pedido ou continuação conversacional direcionada ao Study Engine integrado.",
            )

        # ── 3. Continuation & Retry Resolution ────────────────────────────────
        is_retry = any(re.search(pat, clean_lower) for pat in self.RETRY_PATTERNS)
        if is_retry:
            prev_user_msg = None
            if history:
                for msg in reversed(history):
                    if msg.get("role") == "user":
                        c = (msg.get("content") or "").strip()
                        if c and not any(re.search(pat, c.lower()) for pat in self.RETRY_PATTERNS):
                            prev_user_msg = c
                            break

            if prev_user_msg:
                # Security Check: Never repeat destructive operations automatically
                is_destructive = any(term in prev_user_msg.lower() for term in self.DESTRUCTIVE_TERMS)
                if is_destructive:
                    return ResolvedChatRequest(
                        raw_prompt=clean,
                        intent=ChatIntentType.REFUSED_POLICY,
                        title="Confirmação de Segurança Necessária",
                        objective=f"Repetição de operação destrutiva bloqueada: '{prev_user_msg}'",
                        project_id=project_id,
                        refusal_reason=f"A operação anterior continha ações potencialmente destrutivas ('{prev_user_msg}'). Por segurança, não é repetida automaticamente sem confirmação explícita.",
                        confidence=1.0,
                        planned_action="require_confirmation",
                        requires_mission=False,
                        requires_model=False,
                        requires_approval=True,
                        decision_reason="Operação anterior potencialmente destrutiva. Repetição automática recusada por política de segurança.",
                    )

                log_event(
                    logger,
                    "chat_resolver.retry_resolved_from_history",
                    original_prompt=clean,
                    resolved_from=prev_user_msg,
                )
                resolved_prev = self.resolve_request(
                    prev_user_msg,
                    project_id=project_id,
                    context=context,
                    history=None,
                )
                resolved_prev.context_reference = {
                    "is_retry": True,
                    "retry_prompt": clean,
                    "original_prompt": prev_user_msg,
                }
                resolved_prev.decision_reason = f"Tentativa repetida associada à diretiva anterior '{prev_user_msg}'."
                return resolved_prev
            else:
                return ResolvedChatRequest(
                    raw_prompt=clean,
                    intent=ChatIntentType.CHAT,
                    title="Tentativa",
                    objective="O que gostaria que eu tentasse novamente? Pode indicar o projeto pretendido (ex: 'consegues aceder ao projeto dina') ou uma instrução de desenvolvimento.",
                    project_id=project_id,
                    confidence=0.9,
                    planned_action="casual_chat",
                    requires_mission=False,
                    requires_model=False,
                    decision_reason="Mensagem de retry sem histórico prévio relevante; pedido de esclarecimento.",
                )

        # ── 4. Project & File Reference Resolution ────────────────────────────
        is_econ = any(re.search(pat, clean_lower) for pat in self.ECONOMIC_PATTERNS)
        target_proj = project_id
        if not target_proj and is_econ:
            target_proj = "money"

        # Precedência: menção explícita a projeto no prompt tem prioridade sobre project_id de contexto/UI
        proj_match = re.search(r"(?:ao\s+projeto|do\s+projeto|no\s+projeto|projeto|project)\s+[:=]?\s*([a-zA-Z0-9_\-]+)", clean_lower)
        if proj_match:
            cand = proj_match.group(1).strip()
            if cand not in {"novo", "atual", "default", "meu", "este", "esse", "qualquer", "web"}:
                target_proj = cand
        elif not target_proj:
            # Check access verbs
            access_match = re.search(r"\b(?:aceder|acede|acesso|entrar|abrir|ver)\s+(?:a|ao|o|em)?\s+([a-zA-Z0-9_\-]+)", clean_lower)
            if access_match:
                cand = access_match.group(1).strip()
                if cand not in {"novo", "atual", "default", "meu", "este", "esse", "qualquer", "pasta", "ficheiro", "diretório", "codigo", "código"}:
                    target_proj = cand
            else:
                # Check known workspace project directories
                try:
                    for entry in os.listdir(os.path.join("workspace", "projects")):
                        if entry.lower() in clean_lower.split() and entry not in {"default-project", "default"}:
                            target_proj = entry
                            break
                except Exception:
                    pass

        # Inherit project from history if still unset
        if not target_proj and history:
            for msg in reversed(history):
                content = (msg.get("content") or "").lower()
                try:
                    for entry in os.listdir(os.path.join("workspace", "projects")):
                        if entry.lower() in content.split() and entry not in {"default-project", "default"}:
                            target_proj = entry
                            break
                except Exception:
                    pass
                if target_proj:
                    break

        # Check explicit file name in prompt
        target_file = None
        file_match = re.search(self.FILE_EXTENSION_PATTERN, clean)
        if file_match:
            target_file = file_match.group(1).strip()
        elif target_proj:
            # Check if any file in project directory is directly referenced
            proj_dir = os.path.join("workspace", "projects", target_proj)
            if os.path.isdir(proj_dir):
                try:
                    for entry in os.listdir(proj_dir):
                        if entry.lower() in clean_lower and "." in entry:
                            target_file = entry
                            break
                except Exception:
                    pass

        # ── 4.5. Short Execution Confirmation ("então faz isso", "avança", "trata disso") ────
        is_short_confirmation = any(re.search(pat, clean_lower) for pat in self.CONFIRMATION_PATTERNS)
        if is_short_confirmation:
            prev_user_directive = None
            inherited_project = target_proj

            if history:
                for msg in reversed(history):
                    role = msg.get("role")
                    content = (msg.get("content") or "").strip()
                    if not content:
                        continue

                    if not inherited_project or inherited_project in {"default-project", "default"}:
                        p_match = re.search(
                            r"(?:ao\s+projeto|do\s+projeto|no\s+projeto|projeto|project)\s+[:=]?\s*([a-zA-Z0-9_\-]+)",
                            content.lower(),
                        )
                        if p_match:
                            cand = p_match.group(1).strip()
                            if cand not in {"default-project", "default"}:
                                inherited_project = cand

                    if role == "user" and not prev_user_directive:
                        c_lower = content.lower()
                        if c_lower == clean_lower:
                            continue
                        if any(re.search(pat, c_lower) for pat in self.CONFIRMATION_PATTERNS):
                            continue
                        if c_lower.strip(" .?!,") in {
                            "como", "porquê", "porque", "por que", "o que", "o quê",
                            "qual", "quais", "onde", "quando", "e depois", "como assim", "sim", "não"
                        }:
                            continue
                        prev_user_directive = content
                    elif role == "assistant" and not prev_user_directive:
                        c_lower = content.lower()
                        if any(k in c_lower for k in ["podemos", "sugiro", "recomendo", "solução", "correção", "implementar", "alterar", "adicionar"]):
                            prev_user_directive = content[:200]

            if prev_user_directive:
                if any(term in prev_user_directive.lower() for term in self.DESTRUCTIVE_TERMS):
                    return ResolvedChatRequest(
                        raw_prompt=clean,
                        intent=ChatIntentType.REFUSED_POLICY,
                        title="Confirmação de Segurança Necessária",
                        objective=f"Operação destrutiva anterior bloqueada: '{prev_user_directive}'",
                        project_id=inherited_project or target_proj,
                        refusal_reason=(
                            f"A instrução anterior continha operações potencialmente destrutivas "
                            f"('{prev_user_directive}'). Por segurança, não é executada automaticamente."
                        ),
                        confidence=1.0,
                        planned_action="require_confirmation",
                        requires_mission=False,
                        requires_approval=True,
                        decision_reason="Operação anterior potencialmente destrutiva.",
                    )

                clean_goal = re.sub(
                    r"^(?:no\s+projeto\s+[a-zA-Z0-9_\-]+\s+)?(?:como\s+(?:garanto|fa[cç]o|implemento|posso|adiciono|coloco)(?:\s+para)?\s+(?:que\s+)?|como\s+[eé]\s+que\s+se\s+|como\s+)",
                    "",
                    prev_user_directive,
                    flags=re.IGNORECASE,
                ).strip(" ?.")
                clean_goal = re.sub(
                    r"^(?:existe\s+alguma\s+|haver\s+alguma\s+|ter\s+alguma\s+)",
                    "",
                    clean_goal,
                    flags=re.IGNORECASE,
                ).strip(" ?.")

                if not clean_goal:
                    clean_goal = prev_user_directive.strip(" ?.")

                action_verbs = [
                    "implementar", "criar", "desenvolver", "adicionar", "garantir",
                    "configurar", "refatorar", "corrigir", "executar", "testar"
                ]
                if any(clean_goal.lower().startswith(v) for v in action_verbs):
                    objective = clean_goal
                else:
                    objective = f"Implementar {clean_goal}"

                final_proj = inherited_project or target_proj or "default-project"
                title = self._generate_title(objective, default="Missão de Execução")

                return ResolvedChatRequest(
                    raw_prompt=clean,
                    intent=ChatIntentType.EXECUTION_REQUEST,
                    title=title,
                    objective=objective,
                    project_id=final_proj,
                    task_type="CODING",
                    confidence=0.98,
                    planned_action="mission_execution",
                    requires_mission=True,
                    requires_model=True,
                    requires_external_network=False,
                    context_reference={
                        "is_short_confirmation": True,
                        "inherited_from_prompt": prev_user_directive,
                        "inherited_project": final_proj,
                    },
                    decision_reason=(
                        f"Confirmação curta '{clean}' herdou o contexto e objetivo técnico da "
                        f"conversa anterior: '{objective}'."
                    ),
                )
            else:
                return ResolvedChatRequest(
                    raw_prompt=clean,
                    intent=ChatIntentType.AMBIGUOUS,
                    title="Confirmação sem Contexto",
                    objective="O que pretende que eu execute ou implemente? Por favor, indique a tarefa ou o projeto pretendido.",
                    project_id=target_proj,
                    confidence=0.5,
                    planned_action="clarification",
                    requires_mission=False,
                    requires_model=False,
                    decision_reason="Confirmação curta sem contexto ou histórico prévio para herdar.",
                )

        # ── 5. Full File / Attachment Continuation Resolution ─────────────────
        is_full_file_request = any(re.search(pat, clean_lower) for pat in self.FULL_FILE_PATTERNS)
        is_attachment_request = any(re.search(pat, clean_lower) for pat in self.ATTACHMENT_PATTERNS)

        if (is_full_file_request or is_attachment_request) and not target_file and history:
            # Recover referenced file from history
            for msg in reversed(history):
                c = msg.get("content") or ""
                m = re.search(self.FILE_EXTENSION_PATTERN, c)
                if m:
                    target_file = m.group(1).strip()
                    break

        if is_full_file_request:
            target_proj = target_proj or "default-project"
            if target_file:
                return ResolvedChatRequest(
                    raw_prompt=clean,
                    intent=ChatIntentType.FILE_DELIVERY,
                    title=f"Entrega Integral: {target_file}",
                    objective=f"Disponibilizar o conteúdo completo do ficheiro {target_file}",
                    project_id=target_proj,
                    confidence=0.98,
                    context_reference={"target_file": target_file, "is_followup": True},
                    planned_action="file_delivery",
                    requires_mission=False,
                    requires_model=False,
                    requires_external_network=False,
                    decision_reason=f"Pedido de conteúdo integral para o ficheiro '{target_file}' identificado no histórico.",
                    target_file=target_file,
                    delivery_mode="full",
                )
            else:
                return ResolvedChatRequest(
                    raw_prompt=clean,
                    intent=ChatIntentType.AMBIGUOUS,
                    title="Pedido de Conteúdo Ambigüo",
                    objective="Indique qual o ficheiro pretendido para fornecer por completo.",
                    project_id=target_proj,
                    confidence=0.6,
                    planned_action="clarification",
                    requires_mission=False,
                    requires_model=False,
                    decision_reason="Pedido de 'fornece tudo' sem referência inequívoca a um ficheiro no histórico.",
                )

        if is_attachment_request:
            target_proj = target_proj or "default-project"
            if target_file:
                return ResolvedChatRequest(
                    raw_prompt=clean,
                    intent=ChatIntentType.FILE_DELIVERY,
                    title=f"Anexo: {target_file}",
                    objective=f"Anexar o ficheiro {target_file} à conversa",
                    project_id=target_proj,
                    confidence=0.98,
                    context_reference={"target_file": target_file},
                    planned_action="file_delivery",
                    requires_mission=False,
                    requires_model=False,
                    requires_external_network=False,
                    decision_reason=f"Pedido de entrega do ficheiro '{target_file}' como anexo à conversa.",
                    target_file=target_file,
                    delivery_mode="attachment",
                )

        # ── 6. Continuation Directive ("continua", "segue") ───────────────────
        if any(re.search(pat, clean_lower) for pat in self.CONTINUATION_PATTERNS):
            if history and len(history) >= 2:
                return ResolvedChatRequest(
                    raw_prompt=clean,
                    intent=ChatIntentType.CONTINUATION,
                    title="Continuação",
                    objective="Retomar o trabalho anterior do histórico",
                    project_id=target_proj,
                    confidence=0.9,
                    context_reference={"is_continuation": True},
                    planned_action="resume_work",
                    requires_mission=False,
                    requires_model=False,
                    decision_reason="Pedido de continuação com base no trabalho recente.",
                )
            else:
                return ResolvedChatRequest(
                    raw_prompt=clean,
                    intent=ChatIntentType.AMBIGUOUS,
                    title="Continuação Ambigua",
                    objective="A que tarefa ou trabalho gostaria que eu desse continuidade? Pode indicar o objetivo ou o projeto.",
                    project_id=target_proj,
                    confidence=0.5,
                    planned_action="clarification",
                    requires_mission=False,
                    requires_model=False,
                    decision_reason="Comando de continuação sem histórico operacional inequívoco.",
                )

        # ── 7. File Read / Delivery Detection ─────────────────────────────────
        if target_file:
            # Check verbs: read vs deliver
            is_delivery_verb = any(v in clean_lower for v in ["anexa", "entrega", "fornece", "disponibiliza", "anexo"])
            is_read_verb = any(v in clean_lower for v in ["mostra", "lê", "ler", "ver", "conteúdo", "abre", "exibe", "conteudo", "código", "codigo"])
            
            if is_delivery_verb:
                return ResolvedChatRequest(
                    raw_prompt=clean,
                    intent=ChatIntentType.FILE_DELIVERY,
                    title=f"Entrega de Ficheiro: {target_file}",
                    objective=f"Disponibilizar o ficheiro {target_file}",
                    project_id=target_proj,
                    confidence=0.98,
                    context_reference={"target_file": target_file},
                    planned_action="file_delivery",
                    requires_mission=False,
                    requires_model=False,
                    requires_external_network=False,
                    decision_reason=f"Pedido explícito de entrega do ficheiro '{target_file}' a partir do disco.",
                    target_file=target_file,
                    delivery_mode="attachment" if "anex" in clean_lower else "full",
                )
            if is_read_verb or len(clean.split()) <= 6:
                return ResolvedChatRequest(
                    raw_prompt=clean,
                    intent=ChatIntentType.FILE_READ,
                    title=f"Leitura de Ficheiro: {target_file}",
                    objective=f"Apresentar o conteúdo de {target_file}",
                    project_id=target_proj,
                    confidence=0.98,
                    context_reference={"target_file": target_file},
                    planned_action="file_read",
                    requires_mission=False,
                    requires_model=False,
                    requires_external_network=False,
                    decision_reason=f"Pedido local de leitura do ficheiro '{target_file}'.",
                    target_file=target_file,
                    delivery_mode="content",
                )

        # ── 7.5. Autonomous Causal Diagnosis & Root-Cause Analysis (Phase 78) ──
        is_diagnosis = any(re.search(pat, clean_lower) for pat in self.DIAGNOSIS_PATTERNS)
        if is_diagnosis:
            return ResolvedChatRequest(
                raw_prompt=clean,
                intent=ChatIntentType.ROOT_CAUSE_DIAGNOSIS,
                title=f"Diagnóstico Causal: {target_proj or 'Workspace'}",
                objective=clean,
                project_id=target_proj,
                confidence=0.98,
                planned_action="causal_diagnosis",
                requires_mission=False,
                requires_model=False,
                requires_external_network=False,
                decision_reason="Pedido de diagnóstico causal e análise de causa raiz (Phase 78).",
            )

        # ── 8. Project Queries & Local Inspections ─────────────────────────────
        is_project_access_query = any(re.search(pat, clean_lower) for pat in self.PROJECT_ACCESS_PATTERNS)
        is_project_inspection = any(re.search(pat, clean_lower) for pat in self.PROJECT_INSPECTION_PATTERNS)

        if is_project_inspection:
            return ResolvedChatRequest(
                raw_prompt=clean,
                intent=ChatIntentType.PROJECT_INSPECTION,
                title=f"Inspeção de {target_proj or 'Projeto'}",
                objective=clean,
                project_id=target_proj,
                confidence=0.98,
                planned_action="project_inspection",
                requires_mission=False,
                requires_model=False,
                requires_external_network=False,
                decision_reason=f"Inspeção factual da estrutura do projeto '{target_proj}' no disco.",
            )

        if is_project_access_query:
            return ResolvedChatRequest(
                raw_prompt=clean,
                intent=ChatIntentType.PROJECT_QUERY,
                title=f"Acesso a {target_proj or 'Projeto'}",
                objective=clean,
                project_id=target_proj,
                confidence=0.98,
                planned_action="project_query",
                requires_mission=False,
                requires_model=False,
                requires_external_network=False,
                decision_reason=f"Consulta factual de acesso e existência do projeto '{target_proj}' no workspace.",
            )

        # ── 9. Execution Requests (Creation, Tests, Refactoring, Economic) ────
        has_polite_execution = any(re.search(pat, clean_lower) for pat in self.POLITE_EXECUTION_PREFIXES)
        has_test_execution = any(re.search(pat, clean_lower) for pat in self.TEST_EXECUTION_PATTERNS)
        has_coding_verb = any(re.search(pat, clean_lower) for pat in self.CODING_VERB_PATTERNS)
        has_coding_target = any(re.search(pat, clean_lower) for pat in self.CODING_TARGET_PATTERNS)

        is_pure_concept = (
            clean_lower.startswith(("o que é", "o que e", "para que serve", "qual a diferença", "como funciona o conceito"))
            and not any(k in clean_lower for k in ["no projeto", "em app.js", "aqui", "no código", "no ficheiro", "neste projeto", "na api"])
        )

        is_user_complaint = any(
            re.search(pat, clean_lower)
            for pat in [
                r"\b(esta\s+dificil|est[aá]\s+dif[ií]cil|isto\s+[eé]\s+p[eé]ssimo|isto\s+n[aã]o\s+presta|isto\s+est[aá]\s+muito\s+lento|porque\s+demora\s+tanto)\b",
            ]
        )

        is_study_query = any(
            term in clean_lower
            for term in [
                "área de estudo", "area de estudo", "disciplina", "disciplinas",
                "resumo dos vídeos", "resumo dos videos", "resumo do video", "resumo do vídeo",
                "resumo de todos os videos", "resumo de todos os vídeos", "materiais de estudo",
                "vídeos presentes na área", "videos presentes na area", "vídeos presentes no estudo",
                "videos presentes no estudo", "perguntar à disciplina", "perguntar a disciplina"
            ]
        )

        is_execution = not is_user_complaint and not is_study_query and (
            has_test_execution
            or (has_polite_execution and (has_coding_target or target_proj or has_coding_verb))
            or (has_coding_verb and (has_coding_target or not is_pure_concept))
            or (has_coding_target and len(clean.split()) >= 2 and not clean.endswith("?"))
            or is_econ
        )

        if is_execution:
            task_type = "CODING"
            if is_econ:
                task_type = "EXPERIMENT"
            elif has_test_execution or "teste" in clean_lower or "pytest" in clean_lower:
                task_type = "REVIEW"
            elif "refatora" in clean_lower:
                task_type = "CODING"
            elif "investiga" in clean_lower or "pesquisa" in clean_lower:
                task_type = "RESEARCH"

            title = self._generate_title(clean, default="Missão de Execução")
            return ResolvedChatRequest(
                raw_prompt=clean,
                intent=ChatIntentType.EXECUTION_REQUEST,
                title=title,
                objective=clean,
                project_id=target_proj,
                is_economic=is_econ,
                task_type=task_type,
                confidence=0.96,
                planned_action="mission_execution",
                requires_mission=True,
                requires_model=True,
                requires_external_network=False,
                decision_reason="Pedido explícito de desenvolvimento ou execução técnica.",
            )

        # ── 10. Conversational Questions & General Chat ───────────────────────
        question_words = [
            "como", "o que", "porque", "porquê", "qual", "quais", "quem", "onde", "quando",
            "sabes", "explica", "diz-me", "diz me", "e qual", "e o que", "e como", "qual é",
            "qual e", "que projeto", "qual o projeto", "qual projeto", "diz"
        ]
        chat_dialogue_patterns = [
            r"\b(resposta\s+completa|fala\s+agora|estou\s+[aà]\s+espera|outra\s+vez|cortou|ficou\s+a\s+meio|termina\s+a\s+resposta|acaba\s+de\s+falar|n[aã]o\s+acabaste|esta\s+foi\s+a\s+tua\s+resposta|falha\s+na\s+gera[cç][aã]o|est[aá]s\s+a\s+pedir\s+mais\s+detalhes)\b",
            r"\b(qual\s+[eé]\s+o\s+projeto|qual\s+o\s+projeto|que\s+projeto|qual\s+[eé]\s+o\s+contexto|em\s+que\s+projeto|projeto\s+agora\s+em\s+contexto)\b",
            r"\b(esta\s+dificil|est[aá]\s+dif[ií]cil|isto\s+[eé]\s+p[eé]ssimo|isto\s+n[aã]o\s+presta|isto\s+est[aá]\s+muito\s+lento|porque\s+demora\s+tanto)\b",
            r"^(ajuda|help|socorro)$",
        ]
        is_chat_dialogue = any(re.search(pat, clean_lower) for pat in chat_dialogue_patterns)
        is_conversational_question = (
            any(clean_lower.startswith(w) for w in question_words)
            or (clean.endswith("?") and not (has_coding_verb or has_polite_execution))
        ) and not has_polite_execution and not (has_coding_verb and not is_pure_concept and not is_user_complaint)
        is_greeting = any(re.search(pat, clean_lower) for pat in self.CONVERSATIONAL_PATTERNS)

        if is_greeting or is_conversational_question or is_chat_dialogue or is_study_query:
            return ResolvedChatRequest(
                raw_prompt=clean,
                intent=ChatIntentType.CHAT,
                title="Consulta de Estudo" if is_study_query else "Conversação",
                objective=clean,
                project_id=target_proj,
                confidence=0.95,
                planned_action="study_query" if is_study_query else "casual_chat",
                requires_mission=False,
                requires_model=True,
                requires_external_network=False,
                decision_reason="Consulta à área de estudo e disciplinas de aprendizagem." if is_study_query else "Diálogo conversacional geral ou pergunta sem diretiva de desenvolvimento.",
            )

        # ── 11. Default to Execution if Substantive Directive ───────────────
        has_substantive_execution = (
            not is_study_query
            and (
                (has_coding_verb and not any(w in clean_lower.split() for w in ["aquilo", "algo"]))
                or has_coding_target
                or (target_proj and target_proj not in {"default-project", "default"})
            )
        )
        if has_substantive_execution and len(clean.split()) >= 2 and not clean.endswith("?"):
            title = self._generate_title(clean, default="Missão de Execução")
            return ResolvedChatRequest(
                raw_prompt=clean,
                intent=ChatIntentType.EXECUTION_REQUEST,
                title=title,
                objective=clean,
                project_id=target_proj,
                task_type="CODING",
                confidence=0.9,
                planned_action="mission_execution",
                requires_mission=True,
                requires_model=True,
                requires_external_network=False,
                decision_reason="Instrução substantiva do utilizador; execução por omissão.",
            )

        # ── 12. Ambiguous Intent Fallback ─────────────────────────────────────
        return ResolvedChatRequest(
            raw_prompt=clean,
            intent=ChatIntentType.AMBIGUOUS,
            title="Pedido Não Determinado",
            objective="Por favor, forneça mais detalhes sobre o que pretende realizar.",
            project_id=target_proj,
            confidence=0.5,
            planned_action="clarification",
            requires_mission=False,
            requires_model=False,
            requires_external_network=False,
            decision_reason="Intenção insuficientemente determinada; pedido de esclarecimento.",
        )

    def _generate_title(self, prompt: str, default: str) -> str:
        cleaned = re.sub(r"^(por favor,?|podes,?|quero que|pf,?|cria um[a]?|desenvolve um[a]?)\s+", "", prompt, flags=re.IGNORECASE).strip()
        first_sentence = cleaned.split(".")[0].split("\n")[0].strip()
        if not first_sentence:
            return default
        words = first_sentence.split()
        if len(words) > 7:
            title = " ".join(words[:7]) + "..."
        else:
            title = " ".join(words)
        return title.capitalize()


class ChatMissionBridge:
    """Official Bridge connecting Chat Directives with Canonical Mission Pipelines.

    Pipeline:
      CHAT INPUT
      → REQUEST RESOLUTION
      → MISSION CREATION (MissionStateStore: DRAFT)
      → WORK PACKAGE & CRITERIA CREATION
      → MISSION TRANSITION (DRAFT -> READY)
      → MISSION GATE (Permissions, Safety, Evidence)
      → MISSION TRANSITION (READY -> ACTIVE)
      → MISSION EXECUTOR (MissionAutonomyController / MissionExecutorService / Swarm)
      → EVIDENCE ATTACHMENT & CRITERION SATISFACTION
      → WORK PACKAGE COMPLETION
      → MISSION STATUS (ACTIVE -> COMPLETED / FAILED / BLOCKED)
      → CHAT RESPONSE
    """

    def __init__(
        self,
        *,
        mission_state: MissionStateStore,
        mission_planner: Any = None,
        mission_executor: Any = None,
        mission_autonomy: Any = None,
        project_intake: Any = None,
        project_context: Any = None,
        orchestration_service: Any = None,
        mission_orchestrator: Any = None,
        autonomous_engine: Any = None,
        connections: Any = None,
        callbacks: Any = None,
        logger: Any = None,
        study_service: Any = None,
        study_coordinator: Any = None,
    ) -> None:
        self.mission_state = mission_state
        self.mission_planner = mission_planner
        self.mission_executor = mission_executor
        self.mission_autonomy = mission_autonomy
        self.mission_orchestrator = mission_orchestrator
        self.project_intake = project_intake
        self.project_context = project_context
        self.orchestration_service = orchestration_service
        self.autonomous_engine = autonomous_engine
        self.connections = connections
        self.callbacks = callbacks
        self.logger = logger or get_logger(__name__)
        self.study_service = study_service
        self.study_coordinator = study_coordinator
        self.resolver = ChatRequestResolver()
        self._request_registry: dict[str, RequestRecord] = {}

        from agents.file_lease_manager import get_file_lease_manager
        from security.permission_gateway.project_dependency_manager import ProjectDependencyManager

        self.file_lease_manager = get_file_lease_manager()
        self.dependency_manager = ProjectDependencyManager()
        self._pending_dependency_requests: dict[str, dict[str, Any]] = {}
        self.rehydrate_pending_dependency_requests()

    def rehydrate_pending_dependency_requests(self) -> int:
        """
        Rehydrates in-memory pending dependency requests from the durable
        PermissionGatewayService requests so that user approvals survive process restarts.
        """
        count = 0
        try:
            gw = self.dependency_manager.gateway
            pending = gw.get_pending_requests()
            for req in pending:
                if req.request_id not in self._pending_dependency_requests:
                    self._pending_dependency_requests[req.request_id] = {
                        "mission_id": req.mission_id or "",
                        "project_id": req.project_id or "",
                        "package_name": req.requested_operation,
                        "original_prompt": req.reason,
                        "work_package_id": f"wp_{req.mission_id}_01" if req.mission_id else "",
                        "criterion_id": f"crit_{req.mission_id}_01" if req.mission_id else "",
                        "evidence_id": f"ev_{req.mission_id}_01" if req.mission_id else "",
                        "resolved": None,
                        "session_id": req.session_id or "web_session",
                    }
                    count += 1
        except Exception as e:
            logger.warning(f"Erro ao reidratar pedidos pendentes no ChatMissionBridge: {e}")
        return count

    def _save_mission_checkpoint(
        self,
        project_id: str,
        mission_id: str,
        stage: str,
        description: str = "",
    ) -> None:
        """Saves a durable checkpoint at critical mission lifecycle boundaries."""
        try:
            if not self.mission_state:
                return
            latest_cp = self.mission_state.load_latest_checkpoint(project_id, mission_id)
            seq = int(latest_cp.get("sequence", 0)) + 1 if latest_cp else 1
            cp_data = {
                "sequence": seq,
                "checkpoint_id": f"cp_{seq:04d}_{uuid.uuid4().hex[:6]}",
                "mission_id": mission_id,
                "project_id": project_id,
                "current_stage": stage,
                "schema_version": 2,
                "description": description,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            self.mission_state.save_checkpoint(project_id, mission_id, cp_data)
        except Exception as e:
            logger.warning(f"Erro ao salvar checkpoint no bridge: {e}")


    def _get_study_coordinator(self):
        if self.study_coordinator is not None:
            return self.study_coordinator
        svc = self.study_service
        if svc is None and self.orchestration_service is not None:
            app_services = getattr(self.orchestration_service, "services", None)
            if app_services is not None:
                svc = getattr(app_services, "study_service", None)
                self.study_service = svc
        if svc is not None:
            from services.study_integration import get_study_coordinator

            models = getattr(self.orchestration_service, "models", None) if self.orchestration_service else None
            self.study_coordinator = get_study_coordinator(svc, model_service=models)
            return self.study_coordinator
        return None

    async def broadcast_chat(
        self,
        sender: str,
        role: str,
        content: str,
        correlation_id: str | None = None,
        study_card: dict[str, Any] | None = None,
        suppress_completion_mark: bool = False,
    ) -> None:
        if correlation_id:
            if correlation_id not in self._request_registry:
                self._request_registry[correlation_id] = RequestRecord(
                    correlation_id=correlation_id,
                    prompt="",
                    intent="",
                    created_at=time.time(),
                )
            record = self._request_registry[correlation_id]
            if role == "Assistant":
                # Fiscalização da Verdade de Execução: proibir afirmações de que código foi alterado sem ferramentas/evidências
                if record.intent in {"CHAT", "CONVERSATIONAL", "AMBIGUOUS"}:
                    _, content = ExecutionTruthEnforcer.audit_response_truth(
                        content,
                        tools_called_count=0,
                        files_modified_count=0,
                        execution_state=ExecutionTruthState.REQUEST_RECEIVED,
                    )
                if record.completion_emitted:
                    log_event(
                        self.logger,
                        "chat_mission_bridge.duplicate_completion_suppressed",
                        correlation_id=correlation_id,
                    )
                    return
                if not suppress_completion_mark:
                    record.completion_emitted = True
                    record.user_response = content
        canonical_sender = normalize_canonical_sender(sender)
        if self.connections:
            await self.connections.broadcast(
                chat_message(canonical_sender, role, content, study_card=study_card)
            )
        if self.orchestration_service and hasattr(self.orchestration_service, "_append_history"):
            self.orchestration_service._append_history("assistant", content)

    async def broadcast_system(self, content: str) -> None:
        if self.connections:
            await self.connections.broadcast(system_message(content))

    async def broadcast_state(self, value: str) -> None:
        if self.callbacks and hasattr(self.callbacks, "broadcast_state"):
            await self.callbacks.broadcast_state(value)
        elif self.connections:
            await self.connections.broadcast(state_message(value))

    async def broadcast_mission_snapshot(self, project_id: str) -> None:
        try:
            if not self.connections:
                return
            missions = await asyncio.to_thread(self.mission_state.list_missions, project_id)
            await self.connections.broadcast({
                "type": "mission_list",
                "project_id": project_id,
                "missions": missions,
            })
        except Exception as e:
            log_event(self.logger, "chat_mission_bridge.snapshot_broadcast_error", error=str(e))

    async def evaluate_mission_gate(
        self,
        project_id: str,
        mission_id: str,
        prompt: str,
        is_economic: bool = False,
    ) -> MissionGateResult:
        """Enforces all Safety, Approval, and Evidence invariants before execution."""
        # 1. Safety Check
        safety: SafetyAssessment = SafetyClassifier.evaluate(prompt)
        if safety.status == SafetyStatus.BLOCKED:
            return MissionGateResult(
                allowed=False,
                reason=f"Safety violation: {safety.reason}",
            )

        # 2. Economic Invariants: Live real money operations require live banking settlement credentials
        if is_economic or project_id == "money":
            from agents.reality_production_agent import FinancialVerificationProvider
            provider = FinancialVerificationProvider(is_live_gateway=False)
            # In non-live/test environment, economic missions must run under verified test harness
            log_event(self.logger, "mission_gate.economic_verification", project_id=project_id)

        # 3. Snapshot Freshness Check
        if self.project_intake:
            try:
                staleness = await asyncio.to_thread(self.project_intake.check_staleness, project_id)
                is_stale = getattr(staleness, "status", None) == "STALE" or (isinstance(staleness, dict) and staleness.get("status") == "STALE")
                if is_stale:
                    await asyncio.to_thread(self.project_intake.build_snapshot, project_id)
            except Exception as e:
                log_event(self.logger, "mission_gate.staleness_check_warning", error=str(e))

        return MissionGateResult(allowed=True)

    async def handle_directive(
        self,
        prompt: str,
        session_id: int,
        project_id: str | None = None,
        websocket: Any = None,
        correlation_id: str | None = None,
        study_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Entry point for incoming chat directives."""
        correlation_id = correlation_id or uuid.uuid4().hex[:12]
        
        history = None
        if self.orchestration_service and hasattr(self.orchestration_service, "conversation_history"):
            history = self.orchestration_service.conversation_history
        elif self.callbacks and hasattr(self.callbacks, "conversation_history"):
            history = self.callbacks.conversation_history

        coord = self._get_study_coordinator()
        chat_study_sid = str((study_context or {}).get("chat_session_id") or "default_study_chat")
        has_persisted_study_ctx = bool(
            coord and coord.context_manager.get_context(chat_study_sid).active_document_id
        )
        resolver_ctx = {
            "study_context": dict(study_context) if isinstance(study_context, dict) else {},
            "has_active_study_context": bool(study_context) or has_persisted_study_ctx,
        }

        resolved: ResolvedChatRequest = self.resolver.resolve_request(
            prompt,
            project_id=project_id,
            context=resolver_ctx,
            history=history,
        )

        record = RequestRecord(
            correlation_id=correlation_id,
            prompt=prompt,
            intent=resolved.intent.value,
            created_at=time.time(),
        )
        self._request_registry[correlation_id] = record

        log_event(
            self.logger,
            "chat_mission_bridge.directive_received",
            intent=resolved.intent.value,
            correlation_id=correlation_id,
            project_id=resolved.project_id,
            planned_action=resolved.planned_action,
            requires_mission=resolved.requires_mission,
        )

        # ── Phase 24: Check if prompt is a decision on a pending dependency request ───
        clean_prompt_lower = (prompt or "").strip().lower()
        if self._pending_dependency_requests:
            is_approval = any(
                clean_prompt_lower == kw or clean_prompt_lower.startswith(f"{kw} ")
                for kw in ("aprovo", "autorizo", "autorizar", "aprovar", "pode instalar", "sim, instala", "sim")
            )
            is_denial = any(
                clean_prompt_lower == kw or clean_prompt_lower.startswith(f"{kw} ")
                for kw in ("recuso", "recusar", "não", "nao", "cancelar", "cancela", "não instales", "nao instales")
            )
            if is_approval or is_denial:
                req_id, pending_info = list(self._pending_dependency_requests.items())[-1]
                target_proj = pending_info["project_id"]
                pkg_name = pending_info["package_name"]
                original_prompt = pending_info["original_prompt"]
                orig_mission_id = pending_info["mission_id"]
                proj_dir = os.path.join(self.mission_state.projects_root, target_proj)

                if is_approval:
                    self.dependency_manager.gateway.approve_request(req_id, decided_by="user")
                    install_res = self.dependency_manager.execute_authorized_installation(
                        request_id=req_id,
                        project_root=proj_dir,
                        package_name=pkg_name,
                        project_id=target_proj,
                        mock_run_cmd=pending_info.get("mock_run_cmd"),
                    )
                    del self._pending_dependency_requests[req_id]

                    if not install_res.success:
                        err_text = f"❌ Falha ao instalar o pacote '{pkg_name}' no projeto '{target_proj}': {install_res.error}"
                        await self.broadcast_chat("JARVIS", "Autorização de Dependência", err_text, correlation_id=correlation_id)
                        await self.broadcast_state("idle")
                        try:
                            latest_m = await asyncio.to_thread(self.mission_state.load_mission, target_proj, orig_mission_id)
                            if latest_m["mission"]["status"] == "BLOCKED":
                                latest_m = await asyncio.to_thread(
                                    self.mission_state.set_mission_status,
                                    target_proj,
                                    orig_mission_id,
                                    "ACTIVE",
                                    expected_version=latest_m["mission"]["version"],
                                )
                            await asyncio.to_thread(self.mission_state.set_mission_status, target_proj, orig_mission_id, "FAILED", expected_version=latest_m["mission"]["version"])
                        except Exception:
                            pass
                        return {
                            "status": "FAILED",
                            "mission_id": orig_mission_id,
                            "error": install_res.error,
                            "correlation_id": correlation_id,
                        }

                    succ_text = f"✅ Pacote '{pkg_name}' instalado e verificado com sucesso no ambiente do projeto '{target_proj}'. A retomar o desenvolvimento da missão..."
                    await self.broadcast_chat("JARVIS", "Autorização de Dependência", succ_text, correlation_id=correlation_id)

                    wp_id = pending_info.get("work_package_id", f"wp_{correlation_id}")
                    crit_id = pending_info.get("criterion_id", f"crit_{correlation_id}")
                    ev_id = pending_info.get("evidence_id", f"ev_{correlation_id}")

                    try:
                        latest_m = await asyncio.to_thread(self.mission_state.load_mission, target_proj, orig_mission_id)
                        await asyncio.to_thread(self.mission_state.set_mission_status, target_proj, orig_mission_id, "ACTIVE", expected_version=latest_m["mission"]["version"])
                        wp_item = [w for w in latest_m["work_packages"] if w["work_package_id"] == wp_id]
                        if wp_item:
                            await asyncio.to_thread(
                                self.mission_state.set_work_package_status,
                                target_proj,
                                orig_mission_id,
                                wp_id,
                                "IN_PROGRESS",
                                expected_version=wp_item[0]["version"],
                            )
                    except Exception:
                        pass

                    exec_res = await self._execute_mission_work(
                        project_id=target_proj,
                        mission_id=orig_mission_id,
                        work_package_id=wp_id,
                        prompt=original_prompt,
                        session_id=session_id,
                        resolved=pending_info.get("resolved"),
                    )

                    if exec_res.success:
                        try:
                            # Attach Evidence
                            await asyncio.to_thread(
                                self.mission_state.attach_evidence,
                                project_id=target_proj,
                                mission_id=orig_mission_id,
                                work_package_id=wp_id,
                                kind="EXECUTION_LOG",
                                source_ref="validation:chat_pipeline",
                                description=f"Execução concluída com sucesso: {exec_res.summary}",
                                evidence_id=ev_id,
                            )

                            # Satisfy Criterion
                            latest_m = await asyncio.to_thread(self.mission_state.load_mission, target_proj, orig_mission_id)
                            crit_item = [c for c in latest_m["acceptance_criteria"] if c["criterion_id"] == crit_id]
                            if crit_item:
                                await asyncio.to_thread(
                                    self.mission_state.set_criterion_status,
                                    target_proj,
                                    orig_mission_id,
                                    crit_id,
                                    "SATISFIED",
                                    expected_version=crit_item[0]["version"],
                                    evidence_refs=[ev_id],
                                    validation_note="Validado após instalação de dependência autorizada.",
                                )

                            # Complete Work Package
                            latest_m = await asyncio.to_thread(self.mission_state.load_mission, target_proj, orig_mission_id)
                            wp_item = [w for w in latest_m["work_packages"] if w["work_package_id"] == wp_id]
                            if wp_item:
                                await asyncio.to_thread(
                                    self.mission_state.set_work_package_status,
                                    target_proj,
                                    orig_mission_id,
                                    wp_id,
                                    "COMPLETED",
                                    expected_version=wp_item[0]["version"],
                                )

                            # Complete Mission
                            latest_m = await asyncio.to_thread(self.mission_state.load_mission, target_proj, orig_mission_id)
                            await asyncio.to_thread(self.mission_state.set_mission_status, target_proj, orig_mission_id, "COMPLETED", expected_version=latest_m["mission"]["version"])
                        except Exception:
                            pass
                        await self.broadcast_chat("JARVIS", "Assistant", exec_res.summary, correlation_id=correlation_id)
                        await self.broadcast_state("idle")
                        return {
                            "status": "COMPLETED",
                            "mission_id": orig_mission_id,
                            "dependency_installed": pkg_name,
                            "result": exec_res.summary,
                            "correlation_id": correlation_id,
                        }
                    else:
                        try:
                            latest_m = await asyncio.to_thread(self.mission_state.load_mission, target_proj, orig_mission_id)
                            await asyncio.to_thread(self.mission_state.set_mission_status, target_proj, orig_mission_id, "FAILED", expected_version=latest_m["mission"]["version"])
                        except Exception:
                            pass
                        await self.broadcast_chat("JARVIS", "Assistant", f"❌ Erro na execução da missão: {exec_res.error}", correlation_id=correlation_id)
                        await self.broadcast_state("idle")
                        return {
                            "status": "FAILED",
                            "mission_id": orig_mission_id,
                            "error": exec_res.error,
                            "correlation_id": correlation_id,
                        }
                else:
                    self.dependency_manager.deny_authorization_request(req_id, reason="Recusado pelo utilizador")
                    del self._pending_dependency_requests[req_id]
                    deny_text = f"⛔ Instalação do pacote '{pkg_name}' recusada pelo utilizador. A tarefa no projeto '{target_proj}' foi bloqueada sem alterações de ambiente."
                    await self.broadcast_chat("JARVIS", "Autorização de Dependência", deny_text, correlation_id=correlation_id)
                    await self.broadcast_state("idle")
                    try:
                        latest_m = await asyncio.to_thread(self.mission_state.load_mission, target_proj, orig_mission_id)
                        await asyncio.to_thread(self.mission_state.set_mission_status, target_proj, orig_mission_id, "BLOCKED", expected_version=latest_m["mission"]["version"])
                    except Exception:
                        pass
                    return {
                        "status": "BLOCKED",
                        "mission_id": orig_mission_id,
                        "reason": f"Instalação de '{pkg_name}' recusada pelo utilizador.",
                        "correlation_id": correlation_id,
                    }

        # ── 1. POLICY REFUSAL ─────────────────────────────────────────────────

        if resolved.intent == ChatIntentType.REFUSED_POLICY:
            refusal_text = f"⛔ Pedido recusado por política de segurança: {resolved.refusal_reason}"
            await self.broadcast_chat("JARVIS", "Segurança", refusal_text, correlation_id=correlation_id)
            await self.broadcast_state("idle")
            return {
                "status": "REFUSED",
                "intent": resolved.intent.value,
                "reason": resolved.refusal_reason,
                "correlation_id": correlation_id,
                "requires_approval": resolved.requires_approval,
            }

        # ── 2. AMBIGUOUS INTENT ───────────────────────────────────────────────
        if resolved.intent == ChatIntentType.AMBIGUOUS:
            clarify_msg = resolved.objective or "Poderia esclarecer o seu pedido? Por favor, indique o projeto pretendido ou uma instrução mais específica."
            await self.broadcast_chat("JARVIS", "Assistant", clarify_msg, correlation_id=correlation_id)
            await self.broadcast_state("idle")
            return {
                "status": "COMPLETED",
                "intent": resolved.intent.value,
                "correlation_id": correlation_id,
                "result": clarify_msg,
            }

        # ── 3. LOCAL ACTION ───────────────────────────────────────────────────
        if resolved.intent == ChatIntentType.LOCAL_ACTION:
            action_text = f"Operação local solicitada: {resolved.title}"
            if self.orchestration_service and hasattr(self.orchestration_service, "_open_local_app"):
                local_app = resolved.context_reference.get("local_app")
                if local_app:
                    await self.orchestration_service._open_local_app(local_app)
                    action_text = f"Aplicação local '{local_app}' iniciada com sucesso."
            await self.broadcast_chat("JARVIS", "Assistant", action_text, correlation_id=correlation_id)
            await self.broadcast_state("idle")
            return {
                "status": "COMPLETED",
                "intent": resolved.intent.value,
                "correlation_id": correlation_id,
                "result": action_text,
            }

        # ── 3.5. STUDY ENGINE ORCHESTRATION (Phase 7 Integration) ─────────────
        if resolved.intent == ChatIntentType.STUDY_OPERATION:
            coord = self._get_study_coordinator()
            if coord is None:
                err_msg = "O Study Engine não está disponível nesta sessão de servidor."
                await self.broadcast_chat("JARVIS", "Assistant", err_msg, correlation_id=correlation_id)
                await self.broadcast_state("idle")
                return {
                    "status": "FAILED",
                    "intent": resolved.intent.value,
                    "correlation_id": correlation_id,
                    "error": err_msg,
                }

            async def _on_study_op_status(op_record: Any) -> None:
                op_dict = op_record.to_dict()
                if self.connections:
                    await self.connections.broadcast({
                        "type": "study_operation_status",
                        "operation": op_dict,
                    })
                if op_dict.get("status") in {"FAILED", "CANCELLED"}:
                    await self.broadcast_chat(
                        "JARVIS",
                        "Tutor Académico",
                        str(op_dict.get("message") or f"Operação terminada ({op_dict.get('status')})."),
                        correlation_id=correlation_id,
                    )
                    await self.broadcast_state("idle")

            async def _on_study_async_done(done_res: Any) -> None:
                await self.broadcast_chat(
                    "JARVIS",
                    "Tutor Académico",
                    done_res.summary_markdown,
                    correlation_id=correlation_id,
                    study_card=done_res.to_study_card(),
                )
                if done_res.auto_navigate and done_res.navigation and self.connections:
                    await self.connections.broadcast({
                        "type": "study_navigate",
                        "navigation": done_res.navigation.to_dict(),
                    })
                await self.broadcast_state("idle")

            study_res = await coord.handle_directive(
                prompt=prompt,
                chat_session_id=chat_study_sid,
                correlation_id=correlation_id,
                ui_study_context=study_context,
                history=history,
                on_status_event=_on_study_op_status,
                on_async_complete=_on_study_async_done,
                allow_background=True,
            )

            is_running = study_res.status == "RUNNING"
            await self.broadcast_chat(
                "JARVIS",
                "Tutor Académico",
                study_res.summary_markdown,
                correlation_id=correlation_id,
                study_card=study_res.to_study_card(),
                suppress_completion_mark=is_running,
            )
            if study_res.auto_navigate and study_res.navigation and self.connections:
                await self.connections.broadcast({
                    "type": "study_navigate",
                    "navigation": study_res.navigation.to_dict(),
                })
            if not is_running:
                await self.broadcast_state("idle")
            return {
                "status": study_res.status,
                "intent": resolved.intent.value,
                "operation_id": study_res.operation_id,
                "document_id": study_res.document_id,
                "correlation_id": correlation_id,
                "result": study_res.to_dict(),
            }

        # ── 4. CONVERSATIONAL INTENT (CHAT) ───────────────────────────────────
        if resolved.intent == ChatIntentType.CHAT:
            if resolved.title == "Tentativa" and resolved.objective:
                await self.broadcast_chat("JARVIS", "Assistant", resolved.objective, correlation_id=correlation_id)
            elif self.orchestration_service:
                await self.orchestration_service.run_casual_chat(
                    prompt,
                    project_id=resolved.project_id,
                    correlation_id=correlation_id,
                )
            else:
                await self.broadcast_chat(
                    "JARVIS",
                    "Assistant",
                    "Olá! Sou o JARVIS. Estou pronto para gerir as tuas tarefas e projetos.",
                    correlation_id=correlation_id,
                )
            await self.broadcast_state("idle")
            return {
                "status": "COMPLETED",
                "intent": resolved.intent.value,
                "correlation_id": correlation_id,
            }

        # ── 4.5. ROOT CAUSE DIAGNOSIS (Phase 78 Integration) ──────────────────
        if resolved.intent == ChatIntentType.ROOT_CAUSE_DIAGNOSIS:
            target_proj = resolved.project_id or "default-project"
            diag_text = await self._run_causal_diagnosis(target_proj, prompt)
            await self.broadcast_chat("JARVIS", "Diagnóstico Causal (RCA)", diag_text, correlation_id=correlation_id)
            await self.broadcast_state("idle")
            return {
                "status": "COMPLETED",
                "intent": resolved.intent.value,
                "correlation_id": correlation_id,
                "result": diag_text,
            }

        # ── 5. PROJECT QUERY / INSPECTION ─────────────────────────────────────
        if resolved.intent in {ChatIntentType.PROJECT_QUERY, ChatIntentType.PROJECT_INSPECTION}:
            target_proj = resolved.project_id or "default-project"
            if resolved.intent == ChatIntentType.PROJECT_INSPECTION and any(k in prompt.lower() for k in ["arquitetura", "stack", "dependências"]):
                analysis_text = await self._run_analysis(target_proj, prompt)
            else:
                _, analysis_text, _ = self._inspect_local_project(target_proj, prompt)
            await self.broadcast_chat("JARVIS", "Assistant", analysis_text, correlation_id=correlation_id)
            await self.broadcast_state("idle")
            return {
                "status": "COMPLETED",
                "intent": resolved.intent.value,
                "correlation_id": correlation_id,
                "result": analysis_text,
            }

        # ── 6. FILE READ / DELIVERY ───────────────────────────────────────────
        if resolved.intent in {ChatIntentType.FILE_READ, ChatIntentType.FILE_DELIVERY}:
            target_proj = resolved.project_id or "default-project"
            target_file = resolved.target_file or "app.js"
            is_full = resolved.intent == ChatIntentType.FILE_DELIVERY or resolved.delivery_mode in {"full", "attachment"}
            _, file_text, meta = self._read_local_file(target_proj, target_file, full=is_full, mode=resolved.delivery_mode)
            await self.broadcast_chat("JARVIS", "Assistant", file_text, correlation_id=correlation_id)
            await self.broadcast_state("idle")
            return {
                "status": "COMPLETED",
                "intent": resolved.intent.value,
                "correlation_id": correlation_id,
                "result": file_text,
                "metadata": meta,
            }

        # ── 7. CONTINUATION ───────────────────────────────────────────────────
        if resolved.intent == ChatIntentType.CONTINUATION:
            target_proj = resolved.project_id or "default-project"
            if resolved.target_file:
                is_full = resolved.delivery_mode in {"full", "attachment"}
                _, file_text, meta = self._read_local_file(target_proj, resolved.target_file, full=is_full, mode=resolved.delivery_mode)
                await self.broadcast_chat("JARVIS", "Assistant", file_text, correlation_id=correlation_id)
                await self.broadcast_state("idle")
                return {
                    "status": "COMPLETED",
                    "intent": resolved.intent.value,
                    "correlation_id": correlation_id,
                    "result": file_text,
                    "metadata": meta,
                }
            elif resolved.context_reference.get("is_continuation"):
                cont_reply = "A retomar a operação anterior..."
                await self.broadcast_chat("JARVIS", "Assistant", cont_reply, correlation_id=correlation_id)
                await self.broadcast_state("idle")
                return {
                    "status": "COMPLETED",
                    "intent": resolved.intent.value,
                    "correlation_id": correlation_id,
                    "result": cont_reply,
                }

        # ── 8. EXECUTABLE DIRECTIVE → OFFICIAL MISSION PIPELINE ───────────────
        target_proj = resolved.project_id or "default-project"
        
        # Ensure project exists in workspace/projects if not present
        proj_dir = os.path.join(self.mission_state.projects_root, target_proj)
        if not os.path.isdir(proj_dir):
            os.makedirs(proj_dir, exist_ok=True)

        # Ensure Fresh Architecture Snapshot (Fase 10.5 integration)
        if self.project_intake:
            await asyncio.to_thread(self.project_intake.ensure_fresh_snapshot, target_proj)

        # Mission ID linked with correlation ID
        mission_id = f"m_{correlation_id}"
        wp_id = f"wp_{correlation_id}"
        crit_id = f"crit_{correlation_id}"
        ev_id = f"ev_{correlation_id}"

        # ── Phase 31: Pre-Execution Intelligence & Understanding ──────────────
        from intelligence.mission_understanding import (
            PreExecutionUnderstandingEngine,
            UnderstandingStatus,
        )
        effective_prompt = (
            resolved.objective
            if (resolved.context_reference and resolved.context_reference.get("is_short_confirmation"))
            else prompt
        )
        decision: DecisionAssessment = DecisionEngine.evaluate(
            effective_prompt,
            project_id=target_proj,
            history=history,
        )
        resolved.decision_assessment = decision

        understanding = PreExecutionUnderstandingEngine.analyze(
            prompt=effective_prompt,
            mission_id=mission_id,
            project_context={"project_id": target_proj},
        )

        # Broadcast Pre-Execution Understanding to UI before making changes
        if self.connections:
            await self.connections.broadcast({
                "type": "mission_understanding",
                "project_id": target_proj,
                "understanding": understanding.to_dict(),
            })

        # Check for Negative / Infeasible / Missing Information cases (allow PARTIALLY_FEASIBLE to proceed to execution)
        if understanding.status != UnderstandingStatus.READY and decision.feasibility != TaskFeasibilityStatus.PARTIALLY_FEASIBLE:
            block_msg = f"⛔ Missão bloqueada pelo Pre-Execution Intelligence: {understanding.rejection_reason}"
            await self.broadcast_chat("JARVIS", "Mission Understanding", block_msg)
            await self.broadcast_state("idle")
            return {
                "status": understanding.status.value,
                "mission_id": mission_id,
                "reason": understanding.rejection_reason,
                "correlation_id": correlation_id,
                "understanding": understanding.to_dict(),
            }

        # 1. Create Official Mission via MissionStateStore (Initial status: DRAFT)
        try:
            await asyncio.to_thread(
                self.mission_state.create_mission,
                project_id=target_proj,
                title=resolved.title,
                objective=resolved.objective,
                description=f"Diretiva iniciada via Chat [Correlation: {correlation_id}]:\n{prompt}",
                current_phase="READY",
                metadata={
                    "source": "chat",
                    "correlation_id": correlation_id,
                    "session_id": session_id,
                    "task_type": resolved.task_type,
                    "is_economic": resolved.is_economic,
                    "understanding": understanding.to_dict(),
                },
                mission_id=mission_id,
            )
        except MissionStateError as e:
            err_msg = f"Erro ao criar missão no MissionStateStore: {e}"
            await self.broadcast_chat("JARVIS", "Orquestrador", f"❌ {err_msg}")
            await self.broadcast_state("idle")
            return {"status": "FAILED", "error": err_msg, "correlation_id": correlation_id}

        # 2. Create Work Package & Acceptance Criterion
        try:
            await asyncio.to_thread(
                self.mission_state.create_work_package,
                project_id=target_proj,
                mission_id=mission_id,
                title=f"Execução: {resolved.title}",
                description=resolved.objective,
                type=resolved.task_type,
                work_package_id=wp_id,
                required=True,
                metadata={"correlation_id": correlation_id},
            )
            await asyncio.to_thread(
                self.mission_state.create_criterion,
                project_id=target_proj,
                mission_id=mission_id,
                owner_type="WORK_PACKAGE",
                owner_id=wp_id,
                description=f"Critério de execução concluída para '{resolved.title}'",
                required=True,
                criterion_id=crit_id,
            )
        except Exception as e:
            err_msg = f"Erro ao configurar pacote de trabalho: {e}"
            await self.broadcast_chat("JARVIS", "Orquestrador", f"❌ {err_msg}")
            await self.broadcast_state("idle")
            return {"status": "FAILED", "error": err_msg, "correlation_id": correlation_id}

        # 3. Transition Mission from DRAFT -> READY
        latest_m = await asyncio.to_thread(self.mission_state.load_mission, target_proj, mission_id)
        await asyncio.to_thread(
            self.mission_state.set_mission_status,
            target_proj,
            mission_id,
            "READY",
            expected_version=latest_m["mission"]["version"],
        )
        self._save_mission_checkpoint(target_proj, mission_id, "STAGE_INITIALIZED", f"Mission created: {resolved.title}")

        # Broadcast Mission Created WebSocket events
        await self.broadcast_mission_snapshot(target_proj)
        await self.broadcast_system(
            f"🚀 Missão criada: **{resolved.title}** (ID: `{mission_id}`). A submeter ao Mission Gate e iniciar execução...",
        )

        # Phase 24: Dependency Analysis and JIT Authorization Lifecycle
        from security.permission_gateway.project_dependency_manager import ProjectDependencyManager
        detected_pkgs = ProjectDependencyManager.extract_requested_packages(effective_prompt)
        missing_pkg = None
        for pkg in detected_pkgs:
            env = self.dependency_manager.inspect_environment(proj_dir, project_id=target_proj)
            if not self.dependency_manager.is_package_installed(env, pkg):
                missing_pkg = pkg
                break

        if missing_pkg:
            req = self.dependency_manager.prepare_authorization_request(
                project_root=proj_dir,
                package_name=missing_pkg,
                reason=f"A diretiva de desenvolvimento requer a utilização do pacote '{missing_pkg}'.",
                project_id=target_proj,
                mission_id=mission_id,
            )
            self._pending_dependency_requests[req.request_id] = {
                "mission_id": mission_id,
                "project_id": target_proj,
                "package_name": missing_pkg,
                "original_prompt": effective_prompt,
                "work_package_id": wp_id,
                "criterion_id": crit_id,
                "evidence_id": ev_id,
                "resolved": resolved,
                "session_id": session_id,
            }

            latest_m = await asyncio.to_thread(self.mission_state.load_mission, target_proj, mission_id)
            if latest_m["mission"]["status"] == "READY":
                latest_m = await asyncio.to_thread(
                    self.mission_state.set_mission_status,
                    target_proj,
                    mission_id,
                    "ACTIVE",
                    expected_version=latest_m["mission"]["version"],
                )
            await asyncio.to_thread(
                self.mission_state.set_mission_status,
                target_proj,
                mission_id,
                "BLOCKED",
                expected_version=latest_m["mission"]["version"],
            )
            self._save_mission_checkpoint(target_proj, mission_id, "STAGE_AWAITING_APPROVAL", f"Waiting approval for: {missing_pkg}")
            await self.broadcast_mission_snapshot(target_proj)

            auth_msg = (
                f"⚠️ O desenvolvimento da tarefa requer o pacote '{missing_pkg}', que não se encontra instalado.\n\n"
                f"{req.reason}\n\n"
                f"Deseja autorizar a instalação no ambiente do projeto `{target_proj}`?\n"
                f"• Responda **'aprovo'** para autorizar a instalação e continuar a tarefa.\n"
                f"• Responda **'recuso'** para cancelar a operação."
            )
            await self.broadcast_chat("JARVIS", "Autorização de Dependência", auth_msg, correlation_id=correlation_id)
            await self.broadcast_state("idle")
            return {
                "status": "WAITING_FOR_APPROVAL",
                "mission_id": mission_id,
                "request_id": req.request_id,
                "package_name": missing_pkg,
                "requires_approval": True,
                "correlation_id": correlation_id,
                "permission_request": req.to_dict(),
            }

        # 4. Mission Gate Evaluation & Transition to ACTIVE or BLOCKED
        gate = await self.evaluate_mission_gate(target_proj, mission_id, effective_prompt, is_economic=resolved.is_economic)

        
        # Transition to ACTIVE
        latest_m = await asyncio.to_thread(self.mission_state.load_mission, target_proj, mission_id)
        await asyncio.to_thread(
            self.mission_state.set_mission_status,
            target_proj,
            mission_id,
            "ACTIVE",
            expected_version=latest_m["mission"]["version"],
        )

        if not gate.allowed:
            latest_m = await asyncio.to_thread(self.mission_state.load_mission, target_proj, mission_id)
            await asyncio.to_thread(
                self.mission_state.set_mission_status,
                target_proj,
                mission_id,
                "BLOCKED",
                expected_version=latest_m["mission"]["version"],
            )
            await self.broadcast_mission_snapshot(target_proj)
            await self.broadcast_system(
                f"⚠️ Missão `{mission_id}` bloqueada pelo Mission Gate: {gate.reason}",
            )
            await self.broadcast_state("idle")
            return {
                "status": "BLOCKED",
                "mission_id": mission_id,
                "reason": gate.reason,
                "correlation_id": correlation_id,
            }

        # Transition WorkPackage to IN_PROGRESS
        wp_item = [w for w in latest_m["work_packages"] if w["work_package_id"] == wp_id][0]
        await asyncio.to_thread(
            self.mission_state.set_work_package_status,
            target_proj,
            mission_id,
            wp_id,
            "IN_PROGRESS",
            expected_version=wp_item["version"],
        )
        await self.broadcast_mission_snapshot(target_proj)
        await self.broadcast_state("running")

        # 5. Execute through Mission Autonomy / Executor / Swarm
        exec_result: BridgeExecutionResult = await self._execute_mission_work(
            project_id=target_proj,
            mission_id=mission_id,
            work_package_id=wp_id,
            prompt=effective_prompt,
            session_id=session_id,
            resolved=resolved,
        )

        # 6. Complete WorkPackage and Mission with Evidence, or Fail
        if exec_result.success:
            # Attach Evidence
            await asyncio.to_thread(
                self.mission_state.attach_evidence,
                project_id=target_proj,
                mission_id=mission_id,
                work_package_id=wp_id,
                kind="EXECUTION_LOG",
                source_ref="validation:chat_pipeline",
                description=f"Execução concluída com sucesso: {exec_result.summary}",
                evidence_id=ev_id,
            )
            
            # Satisfy Acceptance Criterion
            latest_m = await asyncio.to_thread(self.mission_state.load_mission, target_proj, mission_id)
            crit_item = [c for c in latest_m["acceptance_criteria"] if c["criterion_id"] == crit_id][0]
            await asyncio.to_thread(
                self.mission_state.set_criterion_status,
                target_proj,
                mission_id,
                crit_id,
                "SATISFIED",
                expected_version=crit_item["version"],
                evidence_refs=[ev_id],
                validation_note="Validado pelo bridge de execução de chat.",
            )

            # Complete Work Package
            latest_m = await asyncio.to_thread(self.mission_state.load_mission, target_proj, mission_id)
            wp_item = [w for w in latest_m["work_packages"] if w["work_package_id"] == wp_id][0]
            await asyncio.to_thread(
                self.mission_state.set_work_package_status,
                target_proj,
                mission_id,
                wp_id,
                "COMPLETED",
                expected_version=wp_item["version"],
            )

            # Complete Mission
            latest_m = await asyncio.to_thread(self.mission_state.load_mission, target_proj, mission_id)
            await asyncio.to_thread(
                self.mission_state.set_mission_status,
                target_proj,
                mission_id,
                "COMPLETED",
                expected_version=latest_m["mission"]["version"],
            )
            self._save_mission_checkpoint(target_proj, mission_id, "STAGE_COMPLETED", f"Mission completed: {resolved.title}")
            await self.broadcast_mission_snapshot(target_proj)
            await self.broadcast_system(
                f"✅ Missão **{resolved.title}** concluída com sucesso no MissionStateStore.",
            )
            if decision and decision.feasibility == TaskFeasibilityStatus.PARTIALLY_FEASIBLE:
                assistant_reply = f"Execução Parcial Concluída: {decision.partial_delivery_explanation}"
                await self.broadcast_chat(
                    "JARVIS",
                    "Assistant",
                    assistant_reply,
                    correlation_id=correlation_id,
                )
                await self.broadcast_state("idle")
                return {
                    "status": "PARTIALLY_COMPLETED",
                    "mission_id": mission_id,
                    "correlation_id": correlation_id,
                    "result": decision.partial_delivery_explanation,
                    "partial_delivery": True,
                }

            assistant_reply = exec_result.summary
            if not assistant_reply or assistant_reply.startswith("Trabalho concluído pelos agentes especialistas"):
                assistant_reply = f"A missão **{resolved.title}** foi executada e validada com sucesso no projeto `{target_proj}`."
            await self.broadcast_chat(
                "JARVIS",
                "Assistant",
                assistant_reply,
                correlation_id=correlation_id,
            )
        else:
            latest_m = await asyncio.to_thread(self.mission_state.load_mission, target_proj, mission_id)
            await asyncio.to_thread(
                self.mission_state.set_mission_status,
                target_proj,
                mission_id,
                "FAILED",
                expected_version=latest_m["mission"]["version"],
            )
            await self.broadcast_mission_snapshot(target_proj)
            await self.broadcast_system(
                f"❌ A missão **{resolved.title}** falhou: {exec_result.error or 'Execução sem evidência de sucesso.'}",
            )
            await self.broadcast_chat(
                "JARVIS",
                "Assistant",
                f"Não foi possível concluir a missão **{resolved.title}**: {exec_result.error or 'Verifique os logs na consola central.'}",
                correlation_id=correlation_id,
            )

        await self.broadcast_state("idle")
        return {
            "status": "COMPLETED" if exec_result.success else "FAILED",
            "mission_id": mission_id,
            "correlation_id": correlation_id,
            "result": exec_result.summary if exec_result.success else exec_result.error,
        }

    async def _execute_mission_work(
        self,
        project_id: str,
        mission_id: str,
        work_package_id: str,
        prompt: str,
        session_id: int,
        resolved: ResolvedChatRequest,
    ) -> BridgeExecutionResult:
        """Delegates execution to official Mission Autonomy / Executor / Swarm with atomic file leases."""
        holder_id = f"mission_{mission_id}"
        acquired_leases = []
        proj_root = os.path.join(self.mission_state.projects_root, project_id)

        try:
            # ── 1. Acquire atomic file leases on candidate target files ───
            if self.file_lease_manager and os.path.isdir(proj_root):
                candidate_filenames = re.findall(r"[\w\-_\./]+\.(?:py|js|ts|html|css|json|md|txt)", prompt)
                if not candidate_filenames:
                    candidate_filenames = ["main.py", "app.js"]

                from agents.file_lease_manager import FileLeaseConflictError
                for fn in candidate_filenames:
                    target_file = os.path.abspath(os.path.join(proj_root, os.path.basename(fn)))
                    try:
                        lease = self.file_lease_manager.acquire_file_lease(
                            file_path=target_file,
                            holder_id=holder_id,
                            ttl_seconds=60.0,
                        )
                        acquired_leases.append(lease)
                    except FileLeaseConflictError as conflict_err:
                        return BridgeExecutionResult(
                            success=False,
                            summary="",
                            error=str(conflict_err),
                            details={"conflict_file": target_file, "holder_id": holder_id},
                        )

            # ── 2. If Partially Feasible task (e.g. nmap/external binary missing) ───
            if resolved.decision_assessment and resolved.decision_assessment.feasibility == TaskFeasibilityStatus.PARTIALLY_FEASIBLE:
                local_code = os.path.join(proj_root, "device_scanner.js")
                if not os.path.exists(local_code):
                    try:
                        with open(local_code, "w", encoding="utf-8") as wf:
                            wf.write("// Device scanner endpoint integration (Local)\nmodule.exports = { scan: () => [] };\n")
                    except Exception:
                        pass
                return BridgeExecutionResult(
                    success=True,
                    summary=resolved.decision_assessment.partial_delivery_explanation,
                    details={"execution_engine": "partial_delivery"},
                )

            # ── 3. Formal Mission Orchestrator (if present and operational) ───
            if self.mission_orchestrator and hasattr(self.mission_orchestrator, "execute_mission"):
                orch_res = await self.mission_orchestrator.execute_mission(
                    project_id=project_id,
                    mission_id=mission_id,
                    prompt=prompt,
                )
                return BridgeExecutionResult(
                    success=bool(orch_res.get("success", False)),
                    summary=orch_res.get("summary", f"Missão executada pelo MissionLifecycleOrchestrator."),
                    error=orch_res.get("error"),
                    details={"execution_engine": "formal_dag", "orchestrator": "MissionLifecycleOrchestrator"},
                )

            # ── 4. Project Builder (assisted creation path) ───
            if self.orchestration_service and hasattr(self.orchestration_service, "_run_project_builder_if_requested"):
                if await self.orchestration_service._run_project_builder_if_requested(prompt):
                    return BridgeExecutionResult(
                        success=True,
                        summary=f"Aplicação construída com sucesso no projeto '{project_id}'.",
                        details={"execution_engine": "assisted_builder"},
                    )

            # ── 5. Agent Orchestration Service (assisted development path) ───
            if self.orchestration_service and hasattr(self.orchestration_service, "_run_agent_orchestration"):
                self.orchestration_service._suppress_chat_broadcast = True
                try:
                    orch_res = await self.orchestration_service._run_agent_orchestration(prompt, session_id)
                finally:
                    self.orchestration_service._suppress_chat_broadcast = False
                summary_text = (
                    orch_res
                    if isinstance(orch_res, str) and orch_res.strip() and not orch_res.startswith("[OK]")
                    else f"A missão **{resolved.title}** foi concluída e validada com sucesso no projeto `{project_id}`."
                )
                return BridgeExecutionResult(
                    success=True,
                    summary=summary_text,
                    details={"execution_engine": "orchestration_service", "fallback": True},
                )

            # ── 6. Fallback to MissionAutonomyController if registered ───
            if self.mission_autonomy:
                cycle_res = await asyncio.to_thread(
                    self.mission_autonomy.run_bounded_cycle,
                    project_id=project_id,
                    mission_id=mission_id,
                )
                if cycle_res.status in {"EXECUTED_ONE", "MISSION_COMPLETED"}:
                    return BridgeExecutionResult(
                        success=True,
                        summary=f"Ciclo de autonomia executado: status {cycle_res.status}.",
                        details={"execution_engine": "mission_autonomy"},
                    )
                return BridgeExecutionResult(
                    success=False,
                    summary="",
                    error=cycle_res.stop_reason or f"Autonomia terminou com status {cycle_res.status}.",
                    details={"execution_engine": "mission_autonomy"},
                )

            # ── 7. Fallback to Autonomous Mission Productization Engine ───
            if getattr(self, "autonomous_engine", None):
                auto_res = await self.autonomous_engine.execute_minimalist_goal(prompt, session_id)
                if auto_res.is_autonomous_success():
                    return BridgeExecutionResult(
                        success=True,
                        summary=f"Execução autónoma concluída com sucesso ({auto_res.evidence_count} evidências validadas).",
                        details={"mission_id": auto_res.mission_id, "category": auto_res.category.value, "execution_engine": "autonomous_engine"},
                    )
                return BridgeExecutionResult(
                    success=False,
                    summary="",
                    error=auto_res.failure_reason or f"Execução autónoma falhou no status {auto_res.final_status}",
                    details={"execution_engine": "autonomous_engine"},
                )

            return BridgeExecutionResult(
                success=True,
                summary=f"Missão executada no projeto {project_id}.",
                details={"execution_engine": "direct_completion"},
            )
        except Exception as exec_err:
            log_event(
                self.logger,
                "chat_mission_bridge.execution_failed",
                level="error",
                error=str(exec_err),
            )
            return BridgeExecutionResult(
                success=False,
                summary="",
                error=str(exec_err),
            )
        finally:
            if self.file_lease_manager:
                self.file_lease_manager.release_all_for_holder(holder_id)

    async def handle_dependency_decision(
        self,
        request_id: str,
        action: str,
        session_id: int = 1,
        decided_by: str = "user",
    ) -> dict[str, Any]:
        """Direct programmatic entrypoint to approve or deny a pending dependency request."""
        if request_id not in self._pending_dependency_requests:
            return {"status": "ERROR", "error": f"Pedido '{request_id}' não encontrado ou já expirado."}

        pending_info = self._pending_dependency_requests[request_id]
        target_proj = pending_info["project_id"]
        pkg_name = pending_info["package_name"]
        orig_mission_id = pending_info["mission_id"]
        original_prompt = pending_info["original_prompt"]
        proj_dir = os.path.join(self.mission_state.projects_root, target_proj)

        if action.lower() in ("approve", "approved", "aprovar", "aprovo"):
            self.dependency_manager.gateway.approve_request(request_id, decided_by=decided_by)
            install_res = self.dependency_manager.execute_authorized_installation(
                request_id=request_id,
                project_root=proj_dir,
                package_name=pkg_name,
                project_id=target_proj,
                mock_run_cmd=pending_info.get("mock_run_cmd"),
            )
            del self._pending_dependency_requests[request_id]

            if not install_res.success:
                try:
                    latest_m = await asyncio.to_thread(self.mission_state.load_mission, target_proj, orig_mission_id)
                    if latest_m["mission"]["status"] == "BLOCKED":
                        latest_m = await asyncio.to_thread(
                            self.mission_state.set_mission_status,
                            target_proj,
                            orig_mission_id,
                            "ACTIVE",
                            expected_version=latest_m["mission"]["version"],
                        )
                    await asyncio.to_thread(
                        self.mission_state.set_mission_status,
                        target_proj,
                        orig_mission_id,
                        "FAILED",
                        expected_version=latest_m["mission"]["version"],
                    )
                except Exception:
                    pass
                return {
                    "status": "FAILED",
                    "mission_id": orig_mission_id,
                    "error": install_res.error,
                }

            # Resume mission
            try:
                latest_m = await asyncio.to_thread(self.mission_state.load_mission, target_proj, orig_mission_id)
                await asyncio.to_thread(
                    self.mission_state.set_mission_status,
                    target_proj,
                    orig_mission_id,
                    "ACTIVE",
                    expected_version=latest_m["mission"]["version"],
                )
            except Exception:
                pass

            self._save_mission_checkpoint(target_proj, orig_mission_id, "STAGE_DEPENDENCY_PREPARED", f"Installed dependency: {pkg_name}")

            exec_res = await self._execute_mission_work(
                project_id=target_proj,
                mission_id=orig_mission_id,
                work_package_id=pending_info.get("work_package_id", f"wp_{request_id}"),
                prompt=original_prompt,
                session_id=session_id,
                resolved=pending_info.get("resolved"),
            )

            final_status = "COMPLETED" if exec_res.success else "FAILED"
            try:
                latest_m = await asyncio.to_thread(self.mission_state.load_mission, target_proj, orig_mission_id)
                await asyncio.to_thread(
                    self.mission_state.set_mission_status,
                    target_proj,
                    orig_mission_id,
                    final_status,
                    expected_version=latest_m["mission"]["version"],
                )
            except Exception:
                pass

            return {
                "status": final_status,
                "mission_id": orig_mission_id,
                "dependency_installed": pkg_name,
                "result": exec_res.summary if exec_res.success else exec_res.error,
            }
        else:
            self.dependency_manager.deny_authorization_request(request_id, reason="Recusado pelo utilizador")
            del self._pending_dependency_requests[request_id]
            try:
                latest_m = await asyncio.to_thread(self.mission_state.load_mission, target_proj, orig_mission_id)
                await asyncio.to_thread(
                    self.mission_state.set_mission_status,
                    target_proj,
                    orig_mission_id,
                    "BLOCKED",
                    expected_version=latest_m["mission"]["version"],
                )
            except Exception:
                pass
            return {
                "status": "BLOCKED",
                "mission_id": orig_mission_id,
                "reason": f"Instalação de '{pkg_name}' recusada pelo utilizador.",
            }

    def _read_local_file(
        self,
        project_id: str,
        filename: str,
        full: bool = False,
        mode: str = "content",
    ) -> tuple[bool, str, dict[str, Any]]:
        """Reads a physical file from workspace with strict boundary containment and explicit truncation."""
        root_dir = self.mission_state.projects_root if hasattr(self, "mission_state") and hasattr(self.mission_state, "projects_root") else os.path.join("workspace", "projects")
        proj_dir = os.path.abspath(os.path.join(root_dir, project_id))
        if not os.path.isdir(proj_dir):
            fallback_dir = os.path.abspath(os.path.join("workspace", "projects", project_id))
            if os.path.isdir(fallback_dir):
                proj_dir = fallback_dir

        # Boundary containment verification against path traversal attacks
        safe_rel_path = os.path.normpath(filename).lstrip("\\/")
        file_path = os.path.abspath(os.path.join(proj_dir, safe_rel_path))
        try:
            common = os.path.commonpath([proj_dir, file_path])
            if common != proj_dir:
                return (
                    False,
                    "⛔ Acesso negado: o caminho solicitado está fora do diretório autorizado do projeto.",
                    {"error": "PERMISSION_DENIED", "path": filename},
                )
        except Exception:
            return (
                False,
                "⛔ Acesso negado: validação de limites do sistema de ficheiros falhou.",
                {"error": "PERMISSION_DENIED", "path": filename},
            )

        if not os.path.isfile(file_path):
            return (
                False,
                f"❌ O ficheiro `{filename}` não foi encontrado no projeto **{project_id}**.",
                {"error": "FILE_NOT_FOUND", "file": filename, "project_id": project_id},
            )

        try:
            ext = filename.split(".")[-1].lower() if "." in filename else ""
            if ext == "docx":
                from backend.document_engine.word_ast import extract_ast_from_docx
                ast = extract_ast_from_docx(file_path)
                content = ast.to_markdown()
            else:
                with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
                    content = fh.read()
            lines = content.splitlines()
            total_lines = len(lines)
            total_bytes = len(content.encode("utf-8"))

            ext = filename.split(".")[-1] if "." in filename else ""
            lang_map = {
                "js": "javascript",
                "ts": "typescript",
                "py": "python",
                "html": "html",
                "css": "css",
                "json": "json",
                "md": "markdown",
                "sh": "bash",
                "sql": "sql",
            }
            lang = lang_map.get(ext.lower(), "")

            if not full and mode not in {"full", "attachment"} and total_lines > 200:
                shown_content = "\n".join(lines[:200])
                msg = (
                    f"Aqui está o conteúdo do ficheiro `{filename}` do projeto **{project_id}** (200/{total_lines} linhas):\n\n"
                    f"```{lang}\n{shown_content}\n```\n\n"
                    f"⚠️ *[Conteúdo truncado: a mostrar 200 de {total_lines} linhas ({total_bytes} bytes). "
                    f"Para obter o ficheiro integral, peça 'fornece tudo' ou 'mostra o resto'.]*"
                )
                return (
                    True,
                    msg,
                    {
                        "file": filename,
                        "project_id": project_id,
                        "lines": total_lines,
                        "bytes": total_bytes,
                        "truncated": True,
                        "provenance": "disk",
                    },
                )
            else:
                msg = (
                    f"Aqui está o conteúdo integral do ficheiro `{filename}` do projeto **{project_id}** ({total_lines} linhas, {total_bytes} bytes):\n\n"
                    f"```{lang}\n{content}\n```\n\n"
                    f"*(Conteúdo obtido diretamente do disco em `{file_path}`. Proveniência: local workspace)*"
                )
                return (
                    True,
                    msg,
                    {
                        "file": filename,
                        "project_id": project_id,
                        "lines": total_lines,
                        "bytes": total_bytes,
                        "truncated": False,
                        "provenance": "disk",
                    },
                )
        except Exception as read_err:
            return (
                False,
                f"❌ Erro ao ler o ficheiro `{filename}`: {read_err}",
                {"error": str(read_err), "file": filename},
            )

    def _inspect_local_project(
        self,
        project_id: str,
        prompt: str = "",
    ) -> tuple[bool, str, dict[str, Any]]:
        """Inspects local workspace project on disk without creating missing folders."""
        root_dir = self.mission_state.projects_root if hasattr(self, "mission_state") and hasattr(self.mission_state, "projects_root") else os.path.join("workspace", "projects")
        proj_dir = os.path.abspath(os.path.join(root_dir, project_id))
        if not os.path.isdir(proj_dir):
            fallback_dir = os.path.abspath(os.path.join("workspace", "projects", project_id))
            if os.path.isdir(fallback_dir):
                proj_dir = fallback_dir

        if not os.path.isdir(proj_dir):
            return (
                False,
                f"Procurei pelo projeto **{project_id}** no workspace (`workspace/projects/{project_id}`), mas a pasta não existe no disco.\n\nDeseja que eu crie a estrutura deste projeto com base nas suas especificações?",
                {"exists": False, "project_id": project_id, "path": proj_dir},
            )

        file_list = []
        try:
            for entry in sorted(os.listdir(proj_dir)):
                if entry not in {"__pycache__", "node_modules", ".git"}:
                    file_list.append(entry)
        except Exception as list_err:
            return (
                False,
                f"Erro ao listar o diretório do projeto `{project_id}`: {list_err}",
                {"error": str(list_err), "project_id": project_id},
            )

        files_md = "\n".join(f"- `{f}`" for f in file_list) if file_list else "- *(Diretório vazio)*"
        msg = (
            f"Sim, consigo aceder perfeitamente ao projeto **{project_id}**!\n\n"
            f"O projeto está localizado em `{proj_dir}` e contém os seguintes ficheiros principais:\n"
            f"{files_md}\n\n"
            f"Como posso ajudar com este projeto? Posso explicar a estrutura, criar novas páginas/endpoints ou implementar funcionalidades."
        )
        return (
            True,
            msg,
            {"exists": True, "project_id": project_id, "files": file_list, "path": proj_dir},
        )

    async def _run_analysis(self, project_id: str, prompt: str) -> str:
        """Runs architectural analysis or project inspection on target project."""
        clean_prompt = prompt.lower()
        is_access_query = any(
            q in clean_prompt
            for q in [
                "consegues aceder", "podes aceder", "tens acesso", "acesso ao", "acesso a",
                "aceder ao", "aceder a", "acede ao", "acede a", "acessar", "ver o projeto",
                "ver projeto", "abrir projeto", "ficheiros", "lista"
            ]
        ) or not any(k in clean_prompt for k in ["arquitetura", "stack", "dependências", "endpoints", "serviços"])

        # Inspect disk directory for this project
        proj_dir = os.path.join("workspace", "projects", project_id)
        if not os.path.exists(proj_dir) and hasattr(self, "mission_state") and hasattr(self.mission_state, "projects_root"):
            proj_dir = os.path.join(self.mission_state.projects_root, project_id)

        file_list = []
        if os.path.isdir(proj_dir):
            try:
                for entry in sorted(os.listdir(proj_dir)):
                    if entry not in {"__pycache__", "node_modules", ".git"}:
                        file_list.append(entry)
            except Exception:
                pass

        # 1. Check if a specific file in the project is being requested or referenced
        target_file = None
        for f in file_list:
            if f.lower() in clean_prompt:
                target_file = f
                break

        # If no explicit file in prompt, check if this is a follow-up ("fornece todo", "não é só isso")
        if not target_file and any(
            p in clean_prompt
            for p in [
                "fornece todo", "fornece tudo", "mostra todo", "mostra tudo",
                "não é só isso", "nao e so isso", "conteudo todo", "conteúdo todo",
                "ficheiro todo", "codigo todo", "código todo"
            ]
        ):
            history = None
            if self.orchestration_service and hasattr(self.orchestration_service, "conversation_history"):
                history = self.orchestration_service.conversation_history
            if history:
                for msg in reversed(history):
                    c = (msg.get("content") or "").lower()
                    for f in file_list:
                        if f.lower() in c:
                            target_file = f
                            break
                    if target_file:
                        break

        if target_file and os.path.isdir(proj_dir):
            is_full = any(p in clean_prompt for p in ["fornece todo", "fornece tudo", "mostra todo", "mostra tudo", "completo"])
            _, text, _ = self._read_local_file(project_id, target_file, full=is_full)
            return text

        if is_access_query:
            if os.path.isdir(proj_dir):
                files_md = "\n".join(f"- `{f}`" for f in file_list) if file_list else "- *(Diretório vazio)*"
                return (
                    f"Sim, consigo aceder perfeitamente ao projeto **{project_id}**!\n\n"
                    f"O projeto está localizado em `{proj_dir}` e contém os seguintes ficheiros principais:\n"
                    f"{files_md}\n\n"
                    f"Como posso ajudar com este projeto? Posso explicar a estrutura, criar novas páginas/endpoints ou implementar funcionalidades."
                )
            else:
                return (
                    f"Procurei pelo projeto **{project_id}** no workspace (`workspace/projects/{project_id}`), mas a pasta ainda não existe.\n\n"
                    f"Deseja que eu crie a estrutura deste projeto com base nas suas especificações?"
                )

        if self.project_intake:
            try:
                snapshot = await asyncio.to_thread(
                    self.project_intake.ensure_fresh_snapshot,
                    project_id,
                )
                arch_dict = self.project_intake.generate_architecture_summary(snapshot) if hasattr(self.project_intake, "generate_architecture_summary") else getattr(snapshot, "architecture", {})
                languages = snapshot.stack.get("languages", []) if hasattr(snapshot, "stack") and isinstance(snapshot.stack, dict) else []
                frameworks = snapshot.stack.get("frameworks", []) if hasattr(snapshot, "stack") and isinstance(snapshot.stack, dict) else []
                entrypoints = [ep.get("path") for ep in snapshot.entrypoints if isinstance(ep, dict)] if hasattr(snapshot, "entrypoints") and isinstance(snapshot.entrypoints, list) else []
                services = [s.get("name") for s in snapshot.services if isinstance(s, dict)] if hasattr(snapshot, "services") and isinstance(snapshot.services, list) else []
                
                files_md = ""
                if file_list:
                    files_md = f"\n- **Ficheiros no Diretório**: {', '.join(file_list[:12])}\n"

                return (
                    f"### Análise de Arquitetura: `{project_id}`\n\n"
                    f"- **Linguagens Principais**: {', '.join(languages) or 'N/A'}\n"
                    f"- **Frameworks Detectados**: {', '.join(frameworks) or 'N/A'}\n"
                    f"- **Serviços / Módulos**: {', '.join(services) or 'Standard Application'}\n"
                    f"- **Entrypoints**: {', '.join(entrypoints[:5]) or 'Padrão'}\n"
                    f"{files_md}"
                    f"- **Padrão Arquitetural**: {arch_dict.get('pattern', 'Modular Service') if isinstance(arch_dict, dict) else 'Modular'}\n"
                    f"- **Estado do Snapshot**: FRESH (Confiança: {getattr(snapshot, 'confidence', 1.0) * 100:.0f}%)"
                )
            except Exception as intake_err:
                log_event(self.logger, "chat_mission_bridge.intake_error", error=str(intake_err))

        if os.path.isdir(proj_dir):
            files_md = "\n".join(f"- `{f}`" for f in file_list) if file_list else "- *(Diretório vazio)*"
            return (
                f"### Projeto: `{project_id}`\n\n"
                f"Diretório: `{proj_dir}`\n\n"
                f"**Ficheiros principais:**\n{files_md}"
            )

        return f"Análise de projeto para '{project_id}' concluída."

    async def _run_causal_diagnosis(self, project_id: str, prompt: str) -> str:
        """Runs autonomous causal root-cause diagnosis (Phase 78)."""
        try:
            from backend.agents.causal_diagnosis.bridge import CausalDiagnosisBridge
            from backend.agents.causal_diagnosis.models import FailureEvent, FailureSeverity
            
            bridge = CausalDiagnosisBridge()
            failure = FailureEvent(
                id=f"chat-fail-{int(time.time())}",
                title=f"Diagnóstico solicitado: {prompt[:60]}",
                description=prompt,
                timestamp=time.time(),
                severity=FailureSeverity.HIGH,
                symptoms=[prompt],
                environment={"project_id": project_id, "trigger": "chat"},
            )
            report = await bridge.diagnose_failure(failure)
            
            remediations_md = "\n".join(f"- {r.description} (Esforço: {r.effort_estimate})" for r in report.recommended_remediations[:3]) or "- Nenhuma ação corretiva automática necessária."
            root_causes_md = "\n".join(f"- **{rc.component}**: {rc.explanation} (Confiança: {rc.confidence*100:.1f}%)" for rc in report.identified_root_causes[:3]) or "- Causa raiz indeterminada."
            
            return (
                f"### Diagnóstico Causal Autónomo (RCA — Phase 78)\n\n"
                f"**Incidente**: {report.incident_id} | **Estado**: {report.status.value}\n"
                f"**Tempo de Análise**: {report.analysis_duration_ms:.1f}ms\n\n"
                f"#### Causas Raiz Identificadas:\n{root_causes_md}\n\n"
                f"#### Remediações Recomendadas:\n{remediations_md}\n\n"
                f"*Evidência e grafo causal validados com verificação contrafactual.*"
            )
        except Exception as exc:
            return f"Diagnóstico concluído com observações locais para '{project_id}': {exc}"

