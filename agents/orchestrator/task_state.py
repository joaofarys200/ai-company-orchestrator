from __future__ import annotations

import re
from dataclasses import dataclass, field

from agents.orchestrator.implementation_plan import ImplementationPlan
from agents.orchestrator.task_requirements import TaskRequirements, normalize_text, task_requires_creation, task_requires_execution

VALID = "VALID"
INVALID_WITH_CORRECTION = "INVALID_WITH_CORRECTION"
CONTROLLED_STOP = "CONTROLLED_STOP"

STRATEGIC_TOOLS = {"criar_agente_especialista", "start_autonomous_plan", "chamar_swarm_dominio"}

@dataclass
class TaskState:
    objective: str = ""
    objective_declared: bool = False
    requirements: TaskRequirements = field(default_factory=TaskRequirements)
    implementation_plan: ImplementationPlan = field(default_factory=ImplementationPlan)
    workspace_listed: bool = False
    files_created: list[str] = field(default_factory=list)
    artifact_contents: dict[str, str] = field(default_factory=dict)
    files_read: list[str] = field(default_factory=list)
    commands_executed: list[str] = field(default_factory=list)
    quality_checks: list[dict] = field(default_factory=list)
    last_tool: str = ""
    last_tool_input: dict = field(default_factory=dict)
    repeated_action_count: int = 0
    actions_without_progress: int = 0
    controlled_errors: list[str] = field(default_factory=list)
    success_criteria: list[str] = field(default_factory=list)
    sandbox_validated: bool = False
    last_stage: str = "inicio"

    def has_artifacts(self) -> bool:
        return bool(self.files_created or self.commands_executed)

    def requires_creation(self, prompt: str) -> bool:
        return task_requires_creation(prompt, self.success_criteria)

    def requires_execution(self, prompt: str) -> bool:
        return task_requires_execution(prompt, self.success_criteria)

    def missing_evidence(self, prompt: str) -> list[str]:
        from agents.orchestrator.quality_gate import missing_requirement_evidence

        return missing_requirement_evidence(prompt, self)

    def as_prompt_context(self, prompt: str) -> str:
        missing = self.missing_evidence(prompt)
        return (
            "[TASK_STATE]\n"
            f"- objetivo_declarado: {self.objective_declared}\n"
            f"- workspace_listado: {self.workspace_listed}\n"
            f"- ficheiros_criados: {self.files_created}\n"
            f"- ficheiros_lidos: {self.files_read}\n"
            f"- comandos_executados: {self.commands_executed}\n"
            f"- quality_checks: {len(self.quality_checks)}\n"
            f"- ultima_tool: {self.last_tool or 'nenhuma'}\n"
            f"- acoes_sem_progresso: {self.actions_without_progress}\n"
            f"- criterios_sucesso: {self.success_criteria}\n"
            f"- evidencia_em_falta: {missing or []}\n"
            "[/TASK_STATE]"
        )

@dataclass
class ToolDecision:
    status: str
    reason: str = ""
    category: str = "contrato"
    missing_evidence: list[str] = field(default_factory=list)
    correction: str = ""

@dataclass
class ActionRepair:
    status: str
    tool_name: str
    tool_input: dict
    original_tool: str
    original_input: dict
    pre_actions: list[dict] = field(default_factory=list)
    reason: str = ""
    changed: bool = False
    decision: ToolDecision | None = None

@dataclass
class TaskPlanStep:
    id: str
    title: str
    allowed_tools: list[str]
    required_evidence: list[str] = field(default_factory=list)
    completed: bool = False

@dataclass
class TaskPlan:
    steps: list[TaskPlanStep]
    current_index: int = 0

    @property
    def current_step(self) -> TaskPlanStep:
        if not self.steps:
            return TaskPlanStep("execucao", "Executar tarefa", ["declarar_objetivo"])
        return self.steps[min(self.current_index, len(self.steps) - 1)]

    def allowed_tools(self) -> set[str]:
        return set(self.current_step.allowed_tools)

    def advance_if_ready(self, state: TaskState, prompt: str) -> None:
        from agents.orchestrator.quality_gate import artifacts_satisfy_minimum

        while self.current_index < len(self.steps) - 1:
            step = self.current_step
            enough_created = artifacts_satisfy_minimum(prompt, state, include_execution=False)
            if step.id == "objetivo" and state.objective_declared:
                step.completed = True
            elif step.id == "analisar_workspace" and state.workspace_listed:
                step.completed = True
            elif step.id == "criar_ficheiros" and (not task_requires_creation(prompt, state.success_criteria) or enough_created):
                step.completed = True
            elif step.id == "validar" and (not task_requires_execution(prompt, state.success_criteria) or state.commands_executed or state.sandbox_validated):
                step.completed = True
            elif step.id == "finalizar" and state.quality_checks:
                step.completed = True

            if step.completed:
                self.current_index += 1
                continue
            break

    def as_prompt_context(self) -> str:
        lines = ["[TASK_PLAN]"]
        for idx, step in enumerate(self.steps):
            marker = "atual" if idx == self.current_index else ("feito" if step.completed else "pendente")
            lines.append(
                f"- {step.id}: {step.title} | estado={marker} | tools={step.allowed_tools} | evidencia={step.required_evidence}"
            )
        lines.append("[/TASK_PLAN]")
        return "\n".join(lines)

def create_task_plan(prompt: str) -> TaskPlan:
    requires_creation = task_requires_creation(prompt)
    requires_execution = task_requires_execution(prompt)
    steps = [
        TaskPlanStep(
            id="objetivo",
            title="Declarar objetivo e criterios verificaveis",
            allowed_tools=["declarar_objetivo"],
            required_evidence=["objetivo declarado", "criterios de sucesso"],
        ),
        TaskPlanStep(
            id="analisar_workspace",
            title="Analisar workspace/sandbox antes de alterar ficheiros",
            allowed_tools=["list_directory", "read_file"],
            required_evidence=["workspace listado"],
        ),
    ]
    if requires_creation:
        steps.append(TaskPlanStep(
            id="criar_ficheiros",
            title="Criar ou editar artefactos relevantes",
            allowed_tools=["write_file", "read_file", "list_directory"],
            required_evidence=["ficheiros criados"],
        ))
    if requires_execution:
        steps.append(TaskPlanStep(
            id="validar",
            title="Executar validacao, build ou preview",
            allowed_tools=["execute_command", "read_file", "list_directory"],
            required_evidence=["comando executado ou sandbox validada"],
        ))
    steps.append(TaskPlanStep(
        id="finalizar",
        title="Verificar qualidade e entregar apenas com evidencia",
        allowed_tools=["verificar_qualidade", "read_file", "list_directory"],
        required_evidence=["quality gate"],
    ))
    return TaskPlan(steps=steps)

def infer_success_criteria(prompt: str) -> list[str]:
    criteria = []
    if task_requires_creation(prompt):
        criteria.append("artefactos criados no workspace/sandbox")
    if task_requires_execution(prompt):
        criteria.append("execucao, validacao ou preview realizado")
    criteria.append("quality gate final baseado em evidencia")
    return criteria

def format_operational_error(stage: str, state: TaskState, decision: ToolDecision) -> str:
    missing = ", ".join(decision.missing_evidence or state.missing_evidence("")) or "nao especificada"
    correction = decision.correction or "Escolher uma ferramenta que produza evidencia verificavel antes de continuar."
    return (
        "Erro controlado de contrato operacional.\n"
        f"Etapa: {stage}.\n"
        f"Ultima tool: {state.last_tool or 'nenhuma'}.\n"
        f"Motivo: {decision.reason or 'acao invalida'}.\n"
        f"Evidencia em falta: {missing}.\n"
        f"Proxima correcao sugerida: {correction}.\n"
        f"Categoria da falha: {decision.category}."
    )

def update_task_state_after_tool(task_state: TaskState, tool_name: str, tool_input: dict | None, result: str) -> None:
    tool_input = tool_input or {}
    result_text = normalize_text(str(result or ""))
    failed = any(
        marker in result_text
        for marker in ["erro", "error", "falhou", "failed", "failure", "bloqueado", "indisponivel", "recusado"]
    ) or bool(re.search(r"codigo\s+(?!0\b)\d+", result_text))
    progressed = False

    if task_state.last_tool == tool_name and task_state.last_tool_input == tool_input:
        task_state.repeated_action_count += 1
    else:
        task_state.repeated_action_count = 0

    if tool_name == "declarar_objetivo" and not failed:
        task_state.objective_declared = True
        criteria = tool_input.get("criterios_de_sucesso") or []
        if isinstance(criteria, list):
            task_state.success_criteria = [str(item) for item in criteria if str(item).strip()]
        progressed = True
        task_state.last_stage = "objetivo"
    elif tool_name == "list_directory" and not failed:
        task_state.workspace_listed = True
        progressed = True
        task_state.last_stage = "inspecao"
    elif tool_name == "write_file" and not failed:
        filename = str(tool_input.get("filename") or "")
        if filename and filename not in task_state.files_created:
            task_state.files_created.append(filename)
        if filename:
            task_state.artifact_contents[filename] = str(tool_input.get("content") or "")[:12000]
        progressed = bool(filename)
        task_state.last_stage = "geracao_ficheiros"
    elif tool_name == "read_file" and not failed:
        filename = str(tool_input.get("filename") or "")
        if filename and filename not in task_state.files_read:
            task_state.files_read.append(filename)
        progressed = bool(filename)
        task_state.last_stage = "inspecao"
    elif tool_name == "execute_command" and not failed:
        command = str(tool_input.get("command") or "")
        if command:
            task_state.commands_executed.append(command)
        task_state.sandbox_validated = True
        progressed = bool(command)
        task_state.last_stage = "execucao"
    elif tool_name == "verificar_qualidade":
        task_state.quality_checks.append({
            "pronto": bool(tool_input.get("pronto_para_entrega", False)),
            "result": str(result or "")[:500],
        })
        progressed = not failed
        task_state.last_stage = "quality_gate"
    elif tool_name in STRATEGIC_TOOLS and not failed:
        progressed = True
        task_state.last_stage = "estrategia"

    if failed:
        task_state.controlled_errors.append(str(result or "")[:500])
        task_state.actions_without_progress += 1
    elif progressed:
        task_state.actions_without_progress = 0
    else:
        task_state.actions_without_progress += 1

    task_state.last_tool = tool_name
    task_state.last_tool_input = dict(tool_input)
