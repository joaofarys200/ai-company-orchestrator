"""
JARVIS OS — AUTONOMOUS DECISION MODEL & EXECUTION TRUTH ENGINE
Implementa a separação rigorosa e formal entre as 6 dimensões de decisão:
A. INTENÇÃO (UserIntent)
B. VIABILIDADE (TaskFeasibility)
C. AUTORIZAÇÃO (TaskAuthorization)
D. POLÍTICA (PolicyAssessment)
E. EXECUÇÃO (ExecutionPlan)
F. ACEITAÇÃO (AcceptanceCriteria)

E a máquina de estados para Verdade de Execução (ExecutionTruthState).
"""

from __future__ import annotations

import enum
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


class UserIntentType(str, enum.Enum):
    """Dimensão A: O que o utilizador pediu efetivamente."""
    INFORMATION = "INFORMATION"                  # Questões gerais, explicações conceituais
    ANALYSIS = "ANALYSIS"                        # Diagnóstico, inspeção de logs, arquitetura
    IMPLEMENTATION = "IMPLEMENTATION"            # Criar ou alterar código, componentes, endpoints
    LOCAL_EXECUTION = "LOCAL_EXECUTION"          # Executar testes, comandos de build, dev servers
    FILE_OPERATION = "FILE_OPERATION"            # Ler ficheiro, entregar código integral ou anexo
    PROPOSAL = "PROPOSAL"                        # Pedido explícito de plano ou proposta prévia
    CONFIRMATION_CONTINUATION = "CONFIRMATION_CONTINUATION"  # "faz isso", "avança", "continua"


class TaskFeasibilityStatus(str, enum.Enum):
    """Dimensão B: Se a tarefa é realizável com as ferramentas e informação disponíveis."""
    FULLY_FEASIBLE = "FULLY_FEASIBLE"
    PARTIALLY_FEASIBLE = "PARTIALLY_FEASIBLE"
    BLOCKED_MISSING_DEPENDENCY = "BLOCKED_MISSING_DEPENDENCY"
    BLOCKED_MATERIAL_AMBIGUITY = "BLOCKED_MATERIAL_AMBIGUITY"
    BLOCKED_TECHNICAL_IMPOSSIBILITY = "BLOCKED_TECHNICAL_IMPOSSIBILITY"


class TaskAuthorizationStatus(str, enum.Enum):
    """Dimensão C: Se a ação está autorizada ou requer confirmação humana estrita."""
    AUTOMATICALLY_AUTHORIZED = "AUTOMATICALLY_AUTHORIZED"  # Edições e comandos rotineiros no workspace
    REQUIRES_USER_CONFIRMATION = "REQUIRES_USER_CONFIRMATION"  # Ações materialmente destrutivas/irreversíveis
    DENIED_UNAUTHORIZED = "DENIED_UNAUTHORIZED"            # Violações de segurança não autorizáveis


class PolicyStatus(str, enum.Enum):
    """Dimensão D: Restrições de segurança objetivas e aplicáveis."""
    ALLOWED = "ALLOWED"                                    # Legítimo, seguro para desenvolvimento
    RESTRICTED_LAB = "RESTRICTED_LAB"                      # Testes dual-use confinados a laboratório local
    BLOCKED_POLICY = "BLOCKED_POLICY"                      # Violação concreta e inegável de segurança


class ExecutionTruthState(str, enum.Enum):
    """Dimensão E/F: Fonte de verdade factual para o estado da operação."""
    REQUEST_RECEIVED = "REQUEST_RECEIVED"
    ANALYSIS_IN_PROGRESS = "ANALYSIS_IN_PROGRESS"
    EXECUTION_PLANNED = "EXECUTION_PLANNED"
    AWAITING_AUTHORIZATION = "AWAITING_AUTHORIZATION"
    EXECUTION_STARTED = "EXECUTION_STARTED"
    EXECUTION_IN_PROGRESS = "EXECUTION_IN_PROGRESS"
    EXECUTION_BLOCKED = "EXECUTION_BLOCKED"
    EXECUTION_FAILED = "EXECUTION_FAILED"
    EXECUTION_PARTIAL = "EXECUTION_PARTIAL"
    EXECUTION_COMPLETED = "EXECUTION_COMPLETED"
    RESULT_VALIDATED = "RESULT_VALIDATED"


@dataclass
class ExecutionStep:
    step_id: str
    description: str
    tool_name: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    is_completed: bool = False
    evidence_collected: Optional[str] = None


@dataclass
class DecisionAssessment:
    """Resultado da avaliação multi-dimensional formal."""
    raw_prompt: str
    intent: UserIntentType
    feasibility: TaskFeasibilityStatus
    authorization: TaskAuthorizationStatus
    policy: PolicyStatus
    execution_state: ExecutionTruthState
    target_project: Optional[str] = None
    target_files: List[str] = field(default_factory=list)
    executable_subdag: List[ExecutionStep] = field(default_factory=list)
    blocked_subdag: List[ExecutionStep] = field(default_factory=list)
    acceptance_criteria: List[str] = field(default_factory=list)
    reasoning: str = ""
    refusal_reason: str = ""
    partial_delivery_explanation: str = ""
    default_to_execution: bool = False
    requires_human_approval: bool = False
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_prompt": self.raw_prompt,
            "intent": self.intent.value,
            "feasibility": self.feasibility.value,
            "authorization": self.authorization.value,
            "policy": self.policy.value,
            "execution_state": self.execution_state.value,
            "target_project": self.target_project,
            "target_files": self.target_files,
            "executable_steps_count": len(self.executable_subdag),
            "blocked_steps_count": len(self.blocked_subdag),
            "acceptance_criteria": self.acceptance_criteria,
            "reasoning": self.reasoning,
            "refusal_reason": self.refusal_reason,
            "partial_delivery_explanation": self.partial_delivery_explanation,
            "default_to_execution": self.default_to_execution,
            "requires_human_approval": self.requires_human_approval,
            "created_at": self.created_at,
        }


class DecisionEngine:
    """
    Motor central que operacionaliza as 6 dimensões de decisão do JARVIS OS,
    garantindo que instruções executáveis não são degradadas em meras explicações.
    """

    # Verbos inequívocos de desenvolvimento e execução
    ACTION_VERBS = [
        "cria", "criar", "desenvolve", "desenvolver", "implementa", "implementar",
        "adiciona", "adicionar", "acrescenta", "acrescentar", "refatora", "refatorar",
        "corrige", "corrigir", "conserta", "consertar", "repara", "reparar",
        "muda", "mudar", "altera", "alterar", "ajusta", "ajustar",
        "configura", "configurar", "instala", "instalar", "remove", "remover",
        "aplica", "aplicar", "otimiza", "otimizar", "organiza", "organizar",
        "atualiza", "atualizar", "conecta", "conectar", "arranca", "arrancar",
        "inicia", "iniciar", "executa", "executar", "corre", "correr",
        "testa", "testar", "valida", "validar", "build", "compila", "compilar",
        "limpa", "limpar", "substitui", "substituir", "resolve", "resolver",
    ]

    # Expressões curtas de confirmação / continuação
    CONFIRMATION_PATTERNS = [
        r"^(ent[aã]o\s+)?(faz\s+isso|trata\s+disso|avan[cç]a(\s+com\s+isso)?|procede(\s+com\s+isso)?|for[cç]a(\s+nisso)?|come[cç]a|pode\s+ser|pode(s)?\s+avan[cç]ar|vamos\s+a\s+isso|executa(\s+isso)?|implementa(\s+isso)?|bora|trata\s+de\s+tudo)(\s+por\s+favor|\s+pf|\s+ent[aã]o)?$",
        r"^(ent[aã]o\s+)?faz(\s+por\s+favor|\s+pf|\s+ent[aã]o)?$",
        r"^(continua|segue|continua\s+a[ií]|continua\s+o\s+trabalho)$",
        r"^(experimenta\s+outra\s+abordagem|tenta\s+outra\s+coisa|resolve\s+o\s+problema)$",
    ]

    # Termos materialmente destrutivos que exigem autorização específica (não recusa)
    DESTRUCTIVE_TERMS = [
        r"\b(rm\s+-rf\s+/|format\s+[a-z]:|wipe\s+disk|drop\s+database\s+prod|delete\s+all\s+system\s+files)\b",
        r"\b(apaga\s+todo\s+o\s+disco|destroi\s+o\s+sistema)\b",
    ]

    # Padrões que são verdadeiras armas ofensivas sem qualquer utilidade defensiva/desenvolvimento
    EXPLICIT_MALWARE_PATTERNS = [
        r"\b(?:ransomware|keylogger|trojan|rootkit|credential\s+harvesting)\b",
        r"\b(?:exfiltrar|roubar|furtar)\s+(?:credenciais|senhas|passwords|chaves\s+privadas)\b",
    ]

    @classmethod
    def evaluate(
        cls,
        prompt: str,
        project_id: Optional[str] = None,
        history: Optional[List[Dict[str, Any]]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> DecisionAssessment:
        clean = (prompt or "").strip()
        clean_lower = clean.lower()

        # 1. Avaliação de Política (DIMENSÃO D)
        policy_status = PolicyStatus.ALLOWED
        refusal_reason = ""
        for pat in cls.EXPLICIT_MALWARE_PATTERNS:
            if re.search(pat, clean_lower):
                # Verificar se há enquadramento explícito de defesa/análise
                if not any(k in clean_lower for k in ["defesa", "mitiga", "proteger", "anti-", "análise de segurança"]):
                    policy_status = PolicyStatus.BLOCKED_POLICY
                    refusal_reason = "Operação classificada como criação de malware ou exfiltração não autorizada de credenciais."
                    break

        # Casos dual-use (ex: testes de flooding, rate limiting, scanners locais)
        if policy_status == PolicyStatus.ALLOWED:
            if any(k in clean_lower for k in ["ddos", "dos", "flooding", "stress test", "scan"]):
                policy_status = PolicyStatus.RESTRICTED_LAB  # Permitido com restrição de ambiente local

        # 2. Avaliação de Autorização (DIMENSÃO C)
        auth_status = TaskAuthorizationStatus.AUTOMATICALLY_AUTHORIZED
        for pat in cls.DESTRUCTIVE_TERMS:
            if re.search(pat, clean_lower):
                auth_status = TaskAuthorizationStatus.REQUIRES_USER_CONFIRMATION
                break

        if policy_status == PolicyStatus.BLOCKED_POLICY:
            auth_status = TaskAuthorizationStatus.DENIED_UNAUTHORIZED

        # 3. Avaliação de Intenção (DIMENSÃO A)
        intent = cls._classify_intent(clean, clean_lower, history)

        # Se for continuação contextual ("faz isso", "avança"), herdar o contexto anterior
        target_proj = project_id
        target_files = []
        inherited_objective = ""
        if intent == UserIntentType.CONFIRMATION_CONTINUATION:
            inherited_objective, target_proj, target_files = cls._resolve_continuation_context(
                clean, history, project_id
            )

        # 4. Avaliação de Viabilidade (DIMENSÃO B)
        feasibility, executable_steps, blocked_steps, partial_explanation = cls._evaluate_feasibility(
            clean, clean_lower, intent, target_proj, inherited_objective
        )

        # 5. Critérios de Aceitação (DIMENSÃO F)
        acceptance_criteria = cls._derive_acceptance_criteria(
            clean, intent, inherited_objective
        )

        # 6. Estado de Execução Inicial (DIMENSÃO E / VERDADE DE EXECUÇÃO)
        default_to_execution = (
            intent in {
                UserIntentType.IMPLEMENTATION,
                UserIntentType.LOCAL_EXECUTION,
                UserIntentType.CONFIRMATION_CONTINUATION,
            }
            and policy_status != PolicyStatus.BLOCKED_POLICY
            and auth_status == TaskAuthorizationStatus.AUTOMATICALLY_AUTHORIZED
            and feasibility in {TaskFeasibilityStatus.FULLY_FEASIBLE, TaskFeasibilityStatus.PARTIALLY_FEASIBLE}
        )

        if policy_status == PolicyStatus.BLOCKED_POLICY:
            exec_state = ExecutionTruthState.EXECUTION_BLOCKED
        elif auth_status == TaskAuthorizationStatus.REQUIRES_USER_CONFIRMATION:
            exec_state = ExecutionTruthState.AWAITING_AUTHORIZATION
        elif default_to_execution:
            exec_state = ExecutionTruthState.EXECUTION_PLANNED
        else:
            exec_state = ExecutionTruthState.REQUEST_RECEIVED

        reasoning = (
            f"Intenção: {intent.value} | Viabilidade: {feasibility.value} | "
            f"Autorização: {auth_status.value} | Política: {policy_status.value}."
        )

        return DecisionAssessment(
            raw_prompt=clean,
            intent=intent,
            feasibility=feasibility,
            authorization=auth_status,
            policy=policy_status,
            execution_state=exec_state,
            target_project=target_proj,
            target_files=target_files,
            executable_subdag=executable_steps,
            blocked_subdag=blocked_steps,
            acceptance_criteria=acceptance_criteria,
            reasoning=reasoning,
            refusal_reason=refusal_reason,
            partial_delivery_explanation=partial_explanation,
            default_to_execution=default_to_execution,
            requires_human_approval=(auth_status == TaskAuthorizationStatus.REQUIRES_USER_CONFIRMATION),
        )

    @classmethod
    def _classify_intent(
        cls, clean: str, clean_lower: str, history: Optional[List[Dict[str, Any]]]
    ) -> UserIntentType:
        # A. Continuação Contextual
        if any(re.search(pat, clean_lower) for pat in cls.CONFIRMATION_PATTERNS):
            return UserIntentType.CONFIRMATION_CONTINUATION

        # B. Pedido de Proposta Explícito
        if any(clean_lower.startswith(p) for p in ["propõe", "proposta para", "planeia", "faz uma proposta", "apresenta um plano"]):
            return UserIntentType.PROPOSAL

        # C. Operação de Ficheiros
        if any(clean_lower.startswith(p) for p in ["mostra o ficheiro", "conteúdo de", "anexa o ficheiro", "dá-me o ficheiro", "lê o ficheiro"]):
            return UserIntentType.FILE_OPERATION

        # D. Execução Local de Comandos/Testes
        if any(clean_lower.startswith(p) or p in clean_lower for p in [
            "executa os testes", "corre os testes", "corre o pytest", "npm test",
            "faz o build", "npm run build", "arranca o servidor", "inicia o preview"
        ]):
            return UserIntentType.LOCAL_EXECUTION

        # E. Análise / Diagnóstico
        if any(clean_lower.startswith(p) or p in clean_lower for p in [
            "diagnostica", "diagnosticar", "investiga", "investigar",
            "inspeciona os logs", "analisa o erro", "porque é que falhou", "qual é o problema"
        ]):
            return UserIntentType.ANALYSIS

        # F. Implementação de Código (Verbos de Ação)
        # Se contiver qualquer verbo de ação, é IMPLEMENTATION, a menos que seja puramente uma pergunta conceituada ("o que é X?")
        has_action_verb = any(
            re.search(r"\b" + re.escape(v) + r"\b", clean_lower)
            for v in cls.ACTION_VERBS
        )
        if has_action_verb:
            # Pergunta puramente conceitual: "O que é rate limiting?", "Para que serve express?"
            is_pure_concept = clean_lower.startswith(("o que é", "o que e", "para que serve", "qual a diferença entre")) and not any(k in clean_lower for k in ["no projeto", "em app.js", "aqui", "no código"])
            if not is_pure_concept:
                return UserIntentType.IMPLEMENTATION

        # G. Informação / Conversação Geral
        if clean.endswith("?") or any(clean_lower.startswith(w) for w in ["como", "o que", "porque", "qual", "quais", "onde", "quando"]):
            return UserIntentType.INFORMATION

        # H. Saudação
        if clean_lower in ["olá", "oi", "bom dia", "boa tarde", "boa noite", "tudo bem"]:
            return UserIntentType.INFORMATION

        # Se não for pergunta e tiver conteúdo substantivo, assume implementação por omissão
        if len(clean.split()) >= 2:
            return UserIntentType.IMPLEMENTATION

        return UserIntentType.INFORMATION

    @classmethod
    def _resolve_continuation_context(
        cls, clean: str, history: Optional[List[Dict[str, Any]]], project_id: Optional[str]
    ) -> Tuple[str, Optional[str], List[str]]:
        """Recupera o contexto técnico a partir do histórico para continuação ("faz isso", "avança")."""
        inherited_objective = ""
        target_proj = project_id
        target_files = []

        if not history:
            return inherited_objective, target_proj, target_files

        # Inspeciona mensagens anteriores de trás para a frente
        for msg in reversed(history):
            role = msg.get("role", "")
            content = str(msg.get("content") or "").strip()
            if not content:
                continue

            # Se a mensagem anterior for do utilizador (pedido técnico prévio)
            if role == "user" and not inherited_objective:
                if not any(re.search(pat, content.lower()) for pat in cls.CONFIRMATION_PATTERNS):
                    inherited_objective = content

            # Se a mensagem anterior for do assistente (proposta de solução técnica)
            elif role == "assistant" and not inherited_objective:
                # Extrai a recomendação técnica proposta pelo assistente
                if any(k in content.lower() for k in ["podemos", "sugiro", "recomendo", "solução", "correção", "implementar"]):
                    inherited_objective = content[:200]

            # Detectar menção a projeto
            if not target_proj or target_proj in {"default-project", "default"}:
                p_match = re.search(r"(?:ao\s+projeto|do\s+projeto|no\s+projeto|projeto|project)\s+[:=]?\s*([a-zA-Z0-9_\-]+)", content.lower())
                if p_match:
                    target_proj = p_match.group(1).strip()

            # Detectar menção a ficheiros
            f_matches = re.findall(r"\b([a-zA-Z0-9_\-\.\/]+\.(?:js|ts|py|html|css|json|md))\b", content)
            if f_matches:
                target_files.extend(f_matches)

            if inherited_objective and target_proj:
                break

        return inherited_objective, target_proj, list(dict.fromkeys(target_files))

    @classmethod
    def _evaluate_feasibility(
        cls,
        clean: str,
        clean_lower: str,
        intent: UserIntentType,
        project_id: Optional[str],
        inherited_objective: str,
    ) -> Tuple[TaskFeasibilityStatus, List[ExecutionStep], List[ExecutionStep], str]:
        """Avalia se a tarefa é totalmente ou parcialmente viável."""
        executable_steps: List[ExecutionStep] = []
        blocked_steps: List[ExecutionStep] = []
        partial_explanation = ""

        effective_goal = inherited_objective or clean

        # Impossibilidades teóricas/matemáticas (ex: halting problem, P=NP o(1))
        if any(k in clean_lower for k in ["resolve p=np em tempo polinomial", "determina o halting problem", "ordena em o(1) sem memoria"]):
            return (
                TaskFeasibilityStatus.BLOCKED_TECHNICAL_IMPOSSIBILITY,
                [],
                [ExecutionStep("impossible_01", "Execução de problema insolúvel", "none")],
                "O pedido viola limites computacionais e matemáticos teóricos fundamentais.",
            )

        # Cenário de dependência externa ausente (ex: nmap) com partes executáveis independentes
        if "nmap" in clean_lower or "ferramenta externa" in clean_lower:
            # Há partes locais viáveis: endpoints, cards de UI, parsing de IP
            executable_steps.append(ExecutionStep(
                step_id="step_code_01",
                description="Criar e atualizar endpoints e interfaces para deteção de dispositivos",
                tool_name="write_file",
            ))
            executable_steps.append(ExecutionStep(
                step_id="step_test_02",
                description="Executar validações funcionais de dados locais",
                tool_name="execute_command",
            ))
            blocked_steps.append(ExecutionStep(
                step_id="step_ext_03",
                description="Executar binário externo nmap a nível de sistema operativo",
                tool_name="execute_system_binary",
            ))
            partial_explanation = (
                "O código de integração e os componentes de interface são viáveis e foram preparados. "
                "Apenas a execução do binário externo nmap requer a presença da ferramenta no sistema."
            )
            return (
                TaskFeasibilityStatus.PARTIALLY_FEASIBLE,
                executable_steps,
                blocked_steps,
                partial_explanation,
            )

        # Se for uma instrução executável comum no workspace
        if intent in {UserIntentType.IMPLEMENTATION, UserIntentType.LOCAL_EXECUTION, UserIntentType.CONFIRMATION_CONTINUATION}:
            executable_steps.append(ExecutionStep(
                step_id="exec_inspect",
                description="Inspecionar contexto técnico do projeto",
                tool_name="read_file",
            ))
            executable_steps.append(ExecutionStep(
                step_id="exec_apply",
                description=f"Aplicar alterações para '{effective_goal[:60]}'",
                tool_name="write_file",
            ))
            executable_steps.append(ExecutionStep(
                step_id="exec_verify",
                description="Verificar integridade e validar entrega",
                tool_name="execute_command",
            ))
            return TaskFeasibilityStatus.FULLY_FEASIBLE, executable_steps, [], ""

        return TaskFeasibilityStatus.FULLY_FEASIBLE, [], [], ""

    @classmethod
    def _derive_acceptance_criteria(
        cls, clean: str, intent: UserIntentType, inherited_objective: str
    ) -> List[str]:
        criteria = []
        effective = inherited_objective or clean
        if intent == UserIntentType.IMPLEMENTATION:
            criteria.append(f"O código reflete a instrução: '{effective[:80]}'")
            criteria.append("Sem regressões nos testes sintáticos e de integridade do projeto")
            criteria.append("Ficheiros em disco atualizados com sucesso")
        elif intent == UserIntentType.LOCAL_EXECUTION:
            criteria.append("Comando executado com código de saída 0")
            criteria.append("Evidência de execução capturada nos logs")
        elif intent == UserIntentType.ANALYSIS:
            criteria.append("Diagnóstico específico fundamentado nos ficheiros e logs reais")
        else:
            criteria.append("Resposta e evidência correlacionadas com a solicitação")
        return criteria


class ExecutionTruthEnforcer:
    """
    Fiscaliza a verdade das mensagens do assistente e dos estados de execução.
    Garante que declarações factuais de sucesso exigem chamadas de ferramentas e provas em disco.
    """

    THEATER_CLAIM_PATTERNS = [
        r"\b(?:j[aá]\s+corrigi|j[aá]\s+est[aá]\s+feito|j[aá]\s+tratei|est[aá]\s+conclu[ií]do|alterei\s+o\s+c[oó]digo|implementei\s+a\s+solu[cç][aã]o)\b",
        r"\b(?:vou\s+tratar\s+disso|a\s+equipa\s+vai\s+tratar|estou\s+a\s+coordenar\s+a\s+equipa)\b",
    ]

    @classmethod
    def audit_response_truth(
        cls,
        assistant_text: str,
        tools_called_count: int,
        files_modified_count: int,
        execution_state: ExecutionTruthState,
    ) -> Tuple[bool, str]:
        """
        Verifica se a mensagem do assistente mente sobre ter executado alterações
        quando nenhuma ferramenta foi chamada ou nenhuma alteração ocorreu.
        Retorna (is_truthful: bool, corrected_or_audited_text: str).
        """
        text_lower = assistant_text.lower()
        has_claim = any(re.search(pat, text_lower) for pat in cls.THEATER_CLAIM_PATTERNS)

        if has_claim and tools_called_count == 0 and files_modified_count == 0:
            # Violação da verdade de execução: afirmação de ação sem evidência
            corrected = (
                "Aviso de Transparência: Nenhuma ferramenta foi executada e nenhum ficheiro foi "
                "modificado no disco nesta interação. Para aplicar estas alterações, confirme a instrução "
                "de execução direta no projeto ativo."
            )
            return False, corrected

        return True, assistant_text
