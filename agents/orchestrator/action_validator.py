from __future__ import annotations

import re

from agents.orchestrator.action_repair import is_safe_workspace_relative_path
from agents.orchestrator.implementation_plan import planned_file_paths
from agents.orchestrator.quality_gate import file_contributes_to_requirements, quality_gate_blocker
from agents.orchestrator.task_requirements import normalize_text, objective_tokens
from agents.orchestrator.task_state import CONTROLLED_STOP, INVALID_WITH_CORRECTION, VALID, TaskPlan, TaskState, ToolDecision

DIRECT_TOOLS = {"list_directory", "read_file", "write_file", "execute_command"}
EVALUATION_TOOLS = {"verificar_qualidade"}
STRATEGIC_TOOLS = {"criar_agente_especialista", "start_autonomous_plan", "chamar_swarm_dominio"}
EXTERNAL_TOOLS = {
    "obsidian_list_notes", "obsidian_read_note", "obsidian_write_note", "obsidian_search_notes",
    "firecrawl_scrape_url", "browserbase_load_page", "youtube_get_transcript",
    "apify_run_actor", "composio_execute_action", "frontend_ui_command",
    "list_active_windows", "capture_screen",
}
ENGINEERING_TOOLS = {
    "semantic_code_search", "refactor_move_symbol", "refactor_rename_symbol",
    "apply_code_patch", "registar_decisao_engenharia", "atualizar_memoria_arquitetura",
}
CODE_ARTIFACT_NOTE_RE = re.compile(
    r"\.(?:py|js|jsx|ts|tsx|css|html?|json|ya?ml|toml|sql|sh|bat|ps1|env)(?:\.md)?$",
    re.IGNORECASE,
)


def obsidian_path_looks_like_code_artifact(filename: str) -> bool:
    normalized = str(filename or "").strip().replace("\\", "/").lstrip("/")
    lowered = normalized.lower()
    if not lowered:
        return False
    if lowered.startswith(("sandbox_dir/", "sandbox/")):
        return True
    leaf = lowered.rsplit("/", 1)[-1]
    return bool(CODE_ARTIFACT_NOTE_RE.search(leaf))

def classify_tool(tool_name: str) -> str:
    if tool_name in DIRECT_TOOLS:
        return "direta"
    if tool_name in EVALUATION_TOOLS:
        return "avaliacao"
    if tool_name in STRATEGIC_TOOLS:
        return "estrategica"
    if tool_name in EXTERNAL_TOOLS:
        return "externa"
    if tool_name in ENGINEERING_TOOLS:
        return "engenharia"
    if tool_name == "declarar_objetivo":
        return "objetivo"
    return "outra"

def artifact_looks_relevant(prompt: str, state: TaskState, filename: str, content: str | None = None) -> bool:
    haystack = normalize_text(f"{filename} {content or ''}")
    tokens = objective_tokens(prompt, state.success_criteria)
    if not tokens:
        return True
    if any(token in haystack for token in tokens):
        return True
    # Very small generic files with no objective overlap are usually placeholders.
    if len(content or "") < 180:
        return False
    return True

def allowed_tools_for_current_step(task_plan: TaskPlan, available_tools: list[dict]) -> list[dict]:
    allowed = task_plan.allowed_tools()
    return [tool for tool in available_tools if tool.get("name") in allowed]

def validate_tool_for_plan(task_plan: TaskPlan, tool_name: str) -> ToolDecision:
    if tool_name in task_plan.allowed_tools():
        return ToolDecision(VALID)
    step = task_plan.current_step
    return ToolDecision(
        INVALID_WITH_CORRECTION,
        f"Tool `{tool_name}` nao contribui para a etapa atual `{step.id}`.",
        "contrato",
        step.required_evidence,
        f"Usa uma destas tools para a etapa atual: {', '.join(step.allowed_tools)}.",
    )

def validate_next_tool_decision(prompt: str, task_state: TaskState, tool_name: str, tool_input: dict | None) -> ToolDecision:
    tool_input = tool_input or {}
    if task_state.actions_without_progress >= 4:
        return ToolDecision(
            CONTROLLED_STOP,
            "Loop sem progresso real atingiu o limite operacional.",
            "LLM",
            task_state.missing_evidence(prompt),
            "Reformular a proxima acao para produzir um ficheiro, comando ou verificacao concreta.",
        )

    if not tool_name:
        if task_state.missing_evidence(prompt):
            return ToolDecision(
                INVALID_WITH_CORRECTION,
                "Resposta textual sem tool quando ainda ha trabalho obrigatorio.",
                "LLM",
                task_state.missing_evidence(prompt),
                "Emitir exatamente uma tool call que produza progresso verificavel.",
            )
        return ToolDecision(VALID)

    if not task_state.objective_declared and tool_name != "declarar_objetivo":
        return ToolDecision(
            INVALID_WITH_CORRECTION,
            "Objetivo ainda nao declarado; a primeira acao operacional deve definir criterios de sucesso.",
            "contrato",
            ["objetivo declarado"],
            "Chamar `declarar_objetivo` com criterios verificaveis antes de executar tools.",
        )

    if task_state.objective_declared and tool_name == "declarar_objetivo":
        return ToolDecision(
            INVALID_WITH_CORRECTION,
            "Objetivo ja foi declarado; repetir `declarar_objetivo` nao produz progresso.",
            "contrato",
            task_state.missing_evidence(prompt),
            "Avancar para uma tool executora ou avaliacao baseada no estado atual.",
        )

    if tool_name == "declarar_objetivo":
        objective_text = " ".join([
            str(tool_input.get("objetivo") or ""),
            *[str(item) for item in (tool_input.get("criterios_de_sucesso") or [])],
        ])
        prompt_tokens = objective_tokens(prompt)
        declared_text = normalize_text(objective_text)
        if not tool_input.get("objetivo") or not tool_input.get("criterios_de_sucesso"):
            return ToolDecision(
                INVALID_WITH_CORRECTION,
                "`declarar_objetivo` precisa de objetivo e criterios_de_sucesso verificaveis.",
                "contrato",
                ["objetivo declarado"],
                "Declarar o objetivo com criterios concretos derivados do pedido original.",
            )
        if prompt_tokens and not any(token in declared_text for token in prompt_tokens):
            return ToolDecision(
                INVALID_WITH_CORRECTION,
                "Objetivo declarado nao corresponde ao pedido original.",
                "contrato",
                ["objetivo alinhado com a prompt"],
                "Chamar `declarar_objetivo` novamente com objetivo e criterios ligados ao pedido do utilizador.",
            )

    if task_state.last_tool == tool_name and task_state.last_tool_input == tool_input:
        status = CONTROLLED_STOP if task_state.repeated_action_count >= 1 else INVALID_WITH_CORRECTION
        return ToolDecision(
            status,
            f"Repeticao da mesma tool sem novo progresso: {tool_name}.",
            "LLM",
            task_state.missing_evidence(prompt),
            "Escolher uma acao diferente ou usar novos parametros com evidencia clara.",
        )

    if tool_name in {"write_file", "read_file"}:
        filename = tool_input.get("filename")
        if not is_safe_workspace_relative_path(filename):
            return ToolDecision(
                CONTROLLED_STOP,
                f"Caminho fora do workspace/sandbox recusado: {filename}",
                "seguranca",
                [],
                "Usar um caminho relativo dentro do workspace, preferencialmente em sandbox_dir.",
            )

    if tool_name == "list_directory" and not is_safe_workspace_relative_path(tool_input.get("path")):
        return ToolDecision(
            CONTROLLED_STOP,
            f"Caminho fora do workspace/sandbox recusado: {tool_input.get('path')}",
            "seguranca",
            [],
            "Listar apenas diretorios relativos ao workspace.",
        )

    if tool_name == "write_file":
        filename = str(tool_input.get("filename") or "")
        content = str(tool_input.get("content") or "")
        if not filename or not content:
            return ToolDecision(
                INVALID_WITH_CORRECTION,
                "`write_file` precisa de `filename` e `content` nao vazios.",
                "contrato",
                task_state.missing_evidence(prompt),
                "Chamar `write_file` com caminho relativo e conteudo completo.",
            )
        planned_paths = planned_file_paths(task_state.implementation_plan)
        if planned_paths and filename.replace("\\", "/") not in planned_paths:
            justification = " ".join(str(tool_input.get(key) or "") for key in ["reason", "justification", "purpose"])
            if not file_contributes_to_requirements(filename, content + "\n" + justification, task_state):
                return ToolDecision(
                    INVALID_WITH_CORRECTION,
                    f"Ficheiro fora do ImplementationPlan e sem contribuicao clara para obrigacoes: {filename}",
                    "contrato",
                    task_state.missing_evidence(prompt),
                    "Usar um ficheiro previsto no ImplementationPlan ou justificar como cobre uma obrigacao concreta.",
                )
        if filename.replace("\\", "/") not in planned_paths and task_state.requires_creation(prompt) and not artifact_looks_relevant(prompt, task_state, filename, content):
            return ToolDecision(
                INVALID_WITH_CORRECTION,
                f"Ficheiro proposto parece placeholder ou irrelevante para o objetivo: {filename}",
                "contrato",
                task_state.missing_evidence(prompt),
                "Escrever um artefacto com conteudo ligado aos criterios do objetivo.",
            )

    if tool_name == "read_file" and not tool_input.get("filename"):
        return ToolDecision(
            INVALID_WITH_CORRECTION,
            "`read_file` precisa de `filename`.",
            "contrato",
            task_state.missing_evidence(prompt),
            "Chamar `read_file` com caminho relativo existente.",
        )

    if tool_name == "obsidian_write_note":
        filename = str(tool_input.get("filename") or "")
        content = tool_input.get("content")
        if not filename or content is None:
            return ToolDecision(
                INVALID_WITH_CORRECTION,
                "`obsidian_write_note` precisa de `filename` e `content`.",
                "contrato",
                task_state.missing_evidence(prompt),
                "Chamar `obsidian_write_note` apenas para notas Markdown do cofre.",
            )
        if obsidian_path_looks_like_code_artifact(filename):
            return ToolDecision(
                INVALID_WITH_CORRECTION,
                f"Obsidian nao deve criar artefactos de codigo/sandbox: {filename}",
                "contrato",
                task_state.missing_evidence(prompt),
                "Usar `write_file` para apps, frontend, backend e ficheiros em sandbox_dir.",
            )

    if tool_name == "verificar_qualidade" and tool_input.get("pronto_para_entrega", False):
        blocker = quality_gate_blocker(prompt, task_state, tool_input.get("ficheiros_criados", []))
        if blocker:
            return ToolDecision(
                INVALID_WITH_CORRECTION,
                blocker,
                "contrato",
                task_state.missing_evidence(prompt),
                "Continuar com tools diretas ate existir evidencia suficiente para o quality gate.",
            )

    if tool_name in STRATEGIC_TOOLS:
        context_blob = normalize_text(" ".join(str(value) for value in tool_input.values()))
        overlap = objective_tokens(prompt, task_state.success_criteria)
        has_context = len(context_blob) >= 30 and (not overlap or any(token in context_blob for token in overlap))
        if task_state.requires_creation(prompt) and not task_state.has_artifacts():
            return ToolDecision(
                INVALID_WITH_CORRECTION,
                "Tool estrategica chamada antes de qualquer execucao direta verificavel.",
                "contrato",
                task_state.missing_evidence(prompt),
                "Usar primeiro uma tool direta que produza evidencia, ou justificar a delegacao com contexto concreto.",
            )
        if not has_context:
            return ToolDecision(
                INVALID_WITH_CORRECTION,
                "Tool estrategica sem contexto suficiente ligado ao objetivo.",
                "contrato",
                task_state.missing_evidence(prompt),
                "Fornecer contexto objetivo e especifico, ou executar diretamente.",
            )

    return ToolDecision(VALID)

def validate_next_tool(prompt: str, task_state: TaskState, tool_name: str, tool_input: dict | None) -> str:
    return validate_next_tool_decision(prompt, task_state, tool_name, tool_input).status
