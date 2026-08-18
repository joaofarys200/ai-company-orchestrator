import os
import re
import asyncio
import json
import subprocess
import base64
import io
import yaml
import datetime
from dataclasses import asdict, dataclass, field
from pathlib import Path
from PIL import ImageGrab
from sandbox import SANDBOX_DIR
from backend.model_harness import (
    ExecutionConstraints,
    ExpectedOutput,
    ModelPreferences,
    ModelRequest,
    ModelResponseStatus,
    OutputFormat,
    get_model_harness,
)

try:
    from crewai import Agent, Task, Crew, LLM
    from crewai.tools import tool
except ImportError:
    Agent = Task = Crew = LLM = None
    def tool(*args, **kwargs):
        if len(args) == 1 and callable(args[0]) and not kwargs:
            return args[0]
        return lambda f: f

import agents.globals as glb
import agents.utils as utils
import agents.memory as memory
import agents.tools as ag_tools
import agents.obsidian_tools as obs_tools
import agents.swarm as swarm
import server

VALID = "VALID"
INVALID_WITH_CORRECTION = "INVALID_WITH_CORRECTION"
CONTROLLED_STOP = "CONTROLLED_STOP"

DIRECT_TOOLS = {"list_directory", "read_file", "write_file", "execute_command"}
EVALUATION_TOOLS = {"verificar_qualidade"}
STRATEGIC_TOOLS = {"criar_agente_especialista", "start_autonomous_plan", "chamar_swarm_dominio"}
EXTERNAL_TOOLS = {
    "obsidian_list_notes", "obsidian_read_note", "obsidian_write_note", "obsidian_search_notes",
    "firecrawl_scrape_url", "browserbase_load_page", "youtube_get_transcript",
    "apify_run_actor", "composio_execute_action", "frontend_ui_command",
    "list_active_windows", "capture_screen",
    "read_pdf", "search_arxiv",
}
ENGINEERING_TOOLS = {
    "semantic_code_search", "refactor_move_symbol", "refactor_rename_symbol",
    "apply_code_patch", "registar_decisao_engenharia", "atualizar_memoria_arquitetura",
}

from agents.orchestrator.task_requirements import (
    TaskRequirements,
    effective_requirements,
    evidence_contains,
    infer_task_requirements,
    is_code_generation_task,
    normalize_text,
    objective_tokens,
    task_requires_creation,
    task_requires_execution,
)
from agents.orchestrator.action_repair import (
    extract_requested_file_paths,
    is_safe_workspace_relative_path,
    normalize_execution_command,
    normalize_tool_input_paths,
    normalize_workspace_path_alias,
)
from agents.orchestrator.implementation_plan import (
    ImplementationPlan,
    PlannedArtifact,
    extract_json_object,
    fallback_plan_from_explicit_files,
    implementation_plan_context,
    parse_implementation_plan,
    plan_blob,
    planned_file_paths,
    validate_implementation_plan,
)
from agents.orchestrator.task_state import (
    ActionRepair,
    TaskPlan,
    TaskPlanStep,
    TaskState,
    ToolDecision,
    create_task_plan,
    format_operational_error,
    infer_success_criteria,
    update_task_state_after_tool,
)
from agents.orchestrator.debug_trace import OrchestrationTrace
from agents.orchestrator.quality_gate import (
    artifact_content_blob,
    artifacts_satisfy_minimum,
    deterministic_quality_ready,
    file_contributes_to_requirements,
    missing_requirement_evidence,
    quality_gate_blocker,
    should_finish_deterministically,
)
from agents.orchestrator.action_validator import (
    allowed_tools_for_current_step,
    artifact_looks_relevant,
    classify_tool,
    validate_next_tool,
    validate_next_tool_decision,
    validate_tool_for_plan,
)
def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int, minimum: int | None = None, maximum: int | None = None) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    if minimum is not None:
        parsed = max(minimum, parsed)
    if maximum is not None:
        parsed = min(maximum, parsed)
    return parsed


def prompt_allows_obsidian(prompt: str) -> bool:
    text = (prompt or "").lower()
    if any(word in text for word in ["obsidian", "vault", "cofre obsidian"]):
        return True
    return bool(re.search(r"\bnotas?\b", text))
























def deterministic_content_for_path(path_value: str, prompt: str) -> str:
    filename = path_value.rsplit("/", 1)[-1].lower()
    title = "Aplicacao"
    if filename.endswith(".html"):
        return (
            "<!doctype html>\n"
            "<html lang=\"pt\">\n"
            "<head>\n"
            "  <meta charset=\"utf-8\">\n"
            "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
            f"  <title>{title}</title>\n"
            "  <link rel=\"stylesheet\" href=\"style.css\">\n"
            "</head>\n"
            "<body>\n"
            "  <main id=\"app\">\n"
            "    <h1>Aplicacao</h1>\n"
            "  </main>\n"
            "  <script src=\"app.js\"></script>\n"
            "</body>\n"
            "</html>\n"
        )
    if filename.endswith(".css"):
        return "body { font-family: system-ui, sans-serif; margin: 2rem; }\nmain { max-width: 720px; }\n"
    if filename.endswith(".js"):
        return "const app = document.querySelector('#app');\nlocalStorage.setItem('app-ready', 'true');\n"
    if filename.endswith(".json"):
        return "{}\n"
    if filename.endswith(".py"):
        return "print('ok')\n"
    return f"{prompt.strip() or 'conteudo'}\n"


def deterministic_validation_command(prompt: str) -> str:
    text = normalize_text(prompt)
    if any(term in text for term in ["listar", "lista", "list", "diretorio", "directory"]) and "sandbox" in text:
        return "Get-ChildItem -LiteralPath sandbox_dir"
    if "preview" in text and "sandbox" in text:
        return "Get-ChildItem -Force -LiteralPath sandbox_dir"
    return ""

RECOVERABLE_COMPLETION_EVIDENCE = {"preview/sandbox validado", "validacao executada"}


def step_limit_completion_recovery_available(prompt: str, state: TaskState) -> bool:
    if not artifacts_satisfy_minimum(prompt, state, include_execution=False):
        return False
    missing_without_quality = set(missing_requirement_evidence(prompt, state, include_quality=False))
    return missing_without_quality.issubset(RECOVERABLE_COMPLETION_EVIDENCE)


def deterministic_validation_command_for_state(prompt: str, state: TaskState) -> str:
    for command in state.implementation_plan.validation_commands:
        allowed, _ = ag_tools.validate_local_command(command)
        if allowed:
            return command

    command = deterministic_validation_command(prompt)
    if command:
        return command

    if (
        step_limit_completion_recovery_available(prompt, state)
        and (state.requirements.requires_preview or state.requirements.requires_validation)
    ):
        return "Get-ChildItem -Force -LiteralPath sandbox_dir"
    return ""


















async def request_implementation_plan_from_ollama(model_name: str, prompt: str, requirements: TaskRequirements, previous_issues: list[str] | None = None) -> ImplementationPlan:
    issues_text = f"\nCorrige estes problemas do plano anterior: {previous_issues}" if previous_issues else ""
    plan_prompt = (
        "Cria um ImplementationPlan para executar a tarefa. "
        "Tu escolhes a arquitetura e os ficheiros; o orquestrador apenas vai validar coerencia. "
        "Nao escolhas ficheiros desnecessarios. Responde APENAS JSON valido com esta estrutura:\n"
        "{"
        "\"stack\":\"...\","
        "\"files\":[{\"path\":\"sandbox_dir/...\",\"purpose\":\"...\",\"obligations\":[\"frontend|backend|storage|auth|crud|search|dashboard|preview|validation|artifacts\"]}],"
        "\"validation_commands\":[\"...\"],"
        "\"completion_criteria\":[\"...\"],"
        "\"storage_strategy\":\"...\","
        "\"crud_map\":{\"create\":\"...\",\"read\":\"...\",\"update\":\"...\",\"delete\":\"...\"},"
        "\"preview_strategy\":\"...\""
        "}\n"
        f"Requisitos inferidos: {json.dumps(asdict(requirements), ensure_ascii=False)}\n"
        f"Tarefa: {prompt}\n"
        f"{issues_text}"
    )
    system = (
        "És um planeador operacional. Não escrevas prosa. Não uses markdown. "
        "Não inventes nomes fixos obrigatorios por template; escolhe ficheiros apenas se fizerem sentido para cumprir a tarefa."
    )
    res_json = await query_ollama_with_tools(
        model_name,
        [{"role": "user", "content": plan_prompt}],
        [],
        system,
    )
    content = (res_json.get("message", {}) or {}).get("content", "") or ""
    parsed = extract_json_object(content)
    return parse_implementation_plan(parsed)


async def request_planned_write_file_from_ollama(model_name: str, prompt: str, state: TaskState) -> dict | None:
    planned_paths = planned_file_paths(state.implementation_plan)
    created = {path.replace("\\", "/") for path in state.files_created}
    next_path = next((path for path in planned_paths if path not in created), "")
    if not next_path:
        return None
    artifact = next((item for item in state.implementation_plan.files if item.path == next_path), None)
    plan_summary = implementation_plan_context(state.implementation_plan, state.requirements)
    write_file_tool = next((tool for tool in ag_tools.JARVIS_TOOLS if tool.get("name") == "write_file"), None)
    content_prompt = (
        "Gera a proxima acao write_file para executar o ImplementationPlan. "
        "O ficheiro ja foi escolhido no plano pelo modelo; nao alteres o filename. "
        "Deves produzir o conteudo completo do ficheiro agora.\n"
        f"Filename obrigatorio: {next_path}\n"
        f"Objetivo: {prompt}\n"
        f"Proposito do ficheiro: {(artifact.purpose if artifact else '')}\n"
        f"Obrigacoes cobertas: {(artifact.obligations if artifact else [])}\n"
        f"{plan_summary}"
    )

    if write_file_tool:
        res_json = await query_ollama_with_tools(
            model_name,
            [{"role": "user", "content": content_prompt}],
            [write_file_tool],
            (
                "Chama exatamente uma tool: write_file. "
                f"O argumento filename tem de ser exatamente `{next_path}`. "
                "Nao respondas em prosa."
            ),
        )
        for idx, raw_call in enumerate((res_json.get("message", {}) or {}).get("tool_calls", []) or []):
            func = raw_call.get("function", {}) or {}
            if func.get("name") != "write_file":
                continue
            args = func.get("arguments", {}) or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {}
            args = normalize_tool_input_paths("write_file", args)
            filename = args.get("filename") or next_path
            content = args.get("content")
            if filename == next_path and isinstance(content, str) and content.strip():
                return {
                    "id": raw_call.get("id") or f"planned_write_{len(created)}_{idx}",
                    "name": "write_file",
                    "input": {
                        "filename": filename,
                        "content": content,
                        "reason": args.get("reason") or "Execucao do ImplementationPlan.",
                    },
                }

    json_prompt = (
        content_prompt
        + "\nA chamada de tool nao foi emitida. Responde APENAS JSON valido: "
        "{\"filename\":\"...\",\"content\":\"...\",\"reason\":\"...\"}."
    )
    res_json = await query_ollama_with_tools(
        model_name,
        [{"role": "user", "content": json_prompt}],
        [],
        "Responde apenas JSON valido, sem markdown e sem prosa.",
    )
    parsed = extract_json_object((res_json.get("message", {}) or {}).get("content", "") or "")
    filename = normalize_workspace_path_alias(parsed.get("filename") or next_path)
    content = parsed.get("content")
    if filename != next_path or not isinstance(content, str) or not content.strip():
        return None
    return {
        "id": f"planned_write_{len(created)}",
        "name": "write_file",
        "input": {
            "filename": filename,
            "content": content,
            "reason": parsed.get("reason") or "Execucao do ImplementationPlan.",
        },
    }














def repair_proposed_action(task_state: TaskState, task_plan: TaskPlan, proposed_tool: str, proposed_args: dict | None) -> ActionRepair:
    original_args = dict(proposed_args or {})
    repaired_args = normalize_tool_input_paths(proposed_tool, original_args)
    changed = repaired_args != original_args
    requested_paths = extract_requested_file_paths(task_state.objective)
    missing_requested_paths = [
        path for path in requested_paths
        if path not in {created.replace("\\", "/") for created in task_state.files_created}
    ]

    path_value = repaired_args.get("filename") if proposed_tool in {"write_file", "read_file"} else repaired_args.get("path")
    if proposed_tool in {"write_file", "read_file", "list_directory"} and not is_safe_workspace_relative_path(path_value):
        return ActionRepair(
            status=CONTROLLED_STOP,
            tool_name=proposed_tool,
            tool_input=repaired_args,
            original_tool=proposed_tool,
            original_input=original_args,
            changed=changed,
            reason=f"Caminho fora do workspace/sandbox recusado: {path_value}",
            decision=ToolDecision(
                CONTROLLED_STOP,
                f"Caminho fora do workspace/sandbox recusado: {path_value}",
                "seguranca",
                [],
                "Usar caminho relativo dentro do workspace/sandbox.",
            ),
        )

    if (
        task_plan.current_step.id == "criar_ficheiros"
        and proposed_tool in {"list_directory", "read_file"}
        and task_state.workspace_listed
        and missing_requested_paths
    ):
        next_path = missing_requested_paths[0]
        return ActionRepair(
            status=VALID,
            tool_name="write_file",
            tool_input={
                "filename": next_path,
                "content": deterministic_content_for_path(next_path, task_state.objective),
            },
            original_tool=proposed_tool,
            original_input=original_args,
            reason="acao de inspecao proposta durante criacao; recovery deterministico para o proximo ficheiro pedido explicitamente.",
            changed=True,
        )

    validation_command = deterministic_validation_command(task_state.objective)
    if (
        task_plan.current_step.id == "validar"
        and proposed_tool in {"list_directory", "read_file"}
        and not task_state.commands_executed
        and validation_command
    ):
        return ActionRepair(
            status=VALID,
            tool_name="execute_command",
            tool_input={"command": validation_command},
            original_tool=proposed_tool,
            original_input=original_args,
            reason="acao de inspecao proposta durante validacao; recovery deterministico para comando seguro de validacao.",
            changed=True,
        )

    if proposed_tool == "write_file" and missing_requested_paths:
        filename = str(repaired_args.get("filename") or "").replace("\\", "/")
        if filename and filename not in requested_paths:
            repaired_args["filename"] = missing_requested_paths[0]
            changed = True
            if not repaired_args.get("content"):
                repaired_args["content"] = deterministic_content_for_path(repaired_args["filename"], task_state.objective)
            return ActionRepair(
                status=VALID,
                tool_name="write_file",
                tool_input=repaired_args,
                original_tool=proposed_tool,
                original_input=original_args,
                reason="filename corrigido para o proximo ficheiro pedido explicitamente no objetivo.",
                changed=True,
            )

    if task_plan.current_step.id == "analisar_workspace" and proposed_tool == "write_file" and not task_state.workspace_listed:
        return ActionRepair(
            status=VALID,
            tool_name="write_file",
            tool_input=repaired_args,
            original_tool=proposed_tool,
            original_input=original_args,
            pre_actions=[{"tool_name": "list_directory", "tool_input": {"path": "sandbox_dir"}}],
            reason="write_file proposto antes de analisar workspace; executar list_directory deterministico primeiro.",
            changed=True,
        )

    return ActionRepair(
        status=VALID,
        tool_name=proposed_tool,
        tool_input=repaired_args,
        original_tool=proposed_tool,
        original_input=original_args,
        reason="acao sem reparacao necessaria" if not changed else "argumentos normalizados",
        changed=changed,
    )




















def parse_structured_action(response_text: str, allowed_tools: list[dict], step: int) -> list[dict]:
    allowed_names = {tool.get("name") for tool in allowed_tools}
    tool_aliases = {
        "create_file": "write_file",
        "create_or_update_file": "write_file",
        "save_file": "write_file",
    }
    candidates = re.findall(r"```(?:json)?\s*(.*?)```", response_text or "", flags=re.IGNORECASE | re.DOTALL)
    stripped = (response_text or "").strip()
    if stripped.startswith("{"):
        candidates.append(stripped)

    parsed_calls = []
    for raw in candidates:
        try:
            data = json.loads(raw.strip())
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        name = data.get("next_action") or data.get("name") or data.get("tool")
        name = tool_aliases.get(str(name or "").strip(), name)
        args = data.get("args") or data.get("arguments") or data.get("input") or {}
        if name in allowed_names and isinstance(args, dict):
            parsed_calls.append({
                "id": f"json_action_{step}",
                "name": name,
                "input": args,
            })
    return parsed_calls


async def request_structured_action_from_ollama(model_name: str, messages: list, allowed_tools: list[dict], reason: str) -> str:
    tool_names = [tool.get("name") for tool in allowed_tools]
    prompt = (
        "A tua ultima resposta nao foi uma tool_call executavel. "
        f"Motivo: {reason}. "
        "Responde APENAS com JSON valido neste formato: "
        "{\"next_action\":\"write_file\",\"args\":{},\"reason\":\"...\"}. "
        f"Escolhe uma next_action desta lista: {tool_names}. Nao uses markdown."
    )
    repair_messages = [*messages, {"role": "user", "content": prompt}]
    res_json = await query_ollama_with_tools(model_name, repair_messages, [], "Responde apenas JSON valido, sem texto extra.")
    return (res_json.get("message", {}) or {}).get("content", "") or ""


def tool_result_names(messages: list) -> list[str]:
    return [
        msg.get("tool_name", "")
        for msg in messages
        if msg.get("role") == "tool_result" and msg.get("tool_name")
    ]


def last_tool_result_name(messages: list) -> str:
    for msg in reversed(messages):
        if msg.get("role") == "tool_result" and msg.get("tool_name"):
            return msg.get("tool_name", "")
    return ""


def should_force_write_file_recovery(prompt: str, messages: list, already_attempted: bool) -> bool:
    if already_attempted or not is_code_generation_task(prompt):
        return False
    names = tool_result_names(messages)
    return (
        last_tool_result_name(messages) == "list_directory"
        and "list_directory" in names
        and "write_file" not in names
    )








async def run_start_autonomous_plan_safely(tool_input: dict | None = None) -> str:
    return (
        "Erro controlado: `start_autonomous_plan` esta temporariamente bloqueado dentro do loop async "
        "do orquestrador porque a implementacao atual chama execucao sincrona de agente e pode falhar "
        "com 'Agent execution was invoked synchronously from within a running event loop'. "
        "Usa tools diretas ou uma versao async segura desta tool."
    )


def build_tools_for_prompt(prompt: str, base_tools: list, swarm_enabled: bool = True) -> list:
    allow_obsidian = prompt_allows_obsidian(prompt)
    filtered_tools = []
    for tool in base_tools:
        name = tool.get("name", "")
        if name.startswith("obsidian_") and not allow_obsidian:
            continue
        if name == "chamar_swarm_dominio" and not swarm_enabled:
            continue
        filtered_tools.append(tool)
    return filtered_tools


def parse_text_tool_calls(response_text: str, allowed_tools: list, step: int) -> list:
    """Recover tool calls when a local model writes JSON instead of emitting tool_calls."""
    allowed_names = {tool.get("name") for tool in allowed_tools}
    candidates = re.findall(r"```(?:json)?\s*(.*?)```", response_text or "", flags=re.IGNORECASE | re.DOTALL)
    stripped = (response_text or "").strip()
    if stripped.startswith("{") or stripped.startswith("["):
        candidates.append(stripped)

    parsed_calls = []
    for raw in candidates:
        try:
            data = json.loads(raw.strip())
        except Exception:
            continue
        items = data if isinstance(data, list) else [data]
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            name = item.get("name") or item.get("tool") or item.get("tool_name")
            args = item.get("arguments") or item.get("args") or item.get("input") or {}
            if name not in allowed_names or not isinstance(args, dict):
                continue
            parsed_calls.append({
                "id": f"text_call_{step}_{idx}",
                "name": name,
                "input": args,
            })
    return parsed_calls


def remove_tools(tools: list, names_to_remove: set[str]) -> list:
    return [tool for tool in tools if tool.get("name") not in names_to_remove]


def keep_tools(tools: list, names_to_keep: set[str]) -> list:
    return [tool for tool in tools if tool.get("name") in names_to_keep]


# --- OPENCLAW_INSTINCTS ---
OPENCLAW_INSTINCTS = """
## Instincts (Reflexos AutomÃ¡ticos â€” aplicam-se SEMPRE, sem excepÃ§Ã£o)

1. **Instinct: Research-Before-Code**
   Antes de escrever qualquer ficheiro de cÃ³digo â†’ USA `list_directory` em "sandbox_dir" para ver o estado actual. Se existirem ficheiros relevantes â†’ lÃª-os com `read_file` antes de os sobrescrever.

2. **Instinct: Kanban Tracking**
   Quando um agente comeÃ§a uma tarefa â†’ reporta progresso. Quando termina â†’ confirma que estÃ¡ feito.

3. **Instinct: File Verification**
   ApÃ³s escrever qualquer ficheiro â†’ usa `list_directory` para confirmar que foi guardado.

4. **Instinct: Error Recovery**
   Se um `execute_command` ou `write_file` falhar â†’ tenta uma segunda vez com abordagem alternativa. Se falhar novamente â†’ reporta ao CEO com o erro exacto.

5. **Instinct: Scope Lock**
   Se o pedido do utilizador for ambÃ­guo â†’ clarifica com uma pergunta directa antes de delegar Ã  equipa.

6. **Instinct: Quality Gate**
   Antes de reportar "concluÃ­do" ao CEO â†’ usa a ferramenta `verificar_qualidade` para confirmar que o trabalho cumpre os critÃ©rios.

7. **Instinct: Specialist Peer Review**
   ApÃ³s receber a resposta de um agente especialista criado via `criar_agente_especialista` â†’ analisa os itens marcados com [VERIFICAR] na resposta. Se existirem â†’ testa-os, pesquisa-os, ou menciona-os ao CEO como pontos pendentes de validaÃ§Ã£o. NUNCA integres um [VERIFICAR] no trabalho final sem o validar primeiro.

8. **Instinct: Self-Correction and Knowledge Base Updates**
   Quando o utilizador corrigir uma regra de trabalho ou preferencia persistente, usa memoria apenas se a ferramenta adequada estiver disponivel neste pedido. NUNCA uses Obsidian para criar ficheiros de apps, websites, backend, frontend ou sandbox; para isso usa `write_file`.
"""


# --- RESEARCH_FIRST_RULE ---
RESEARCH_FIRST_RULE = """
## Research-First (OBRIGATÃ“RIO antes de qualquer acÃ§Ã£o de escrita)

Fluxo obrigatÃ³rio:
1. `list_directory` em "sandbox_dir" â†’ ver o que existe
2. `read_file` nos ficheiros relevantes â†’ perceber o estado actual
3. SÃ³ entÃ£o â†’ escrever, modificar ou delegar

NUNCA escrevas cÃ³digo sem primeiro perceber o que jÃ¡ existe na sandbox.
"""


# --- register_spawned_agent ---
def register_spawned_agent(nome: str, especialidade: str, tarefa: str, resultado_resumo: str):
    """Persists a spawned agent to disk for reuse and history tracking."""
    try:
        registry = {"agents": []}
        if _SPAWNED_AGENTS_PATH.exists():
            registry = json.loads(_SPAWNED_AGENTS_PATH.read_text(encoding="utf-8"))
        registry["agents"].append({
            "nome": nome,
            "especialidade": especialidade,
            "tarefa_original": tarefa[:120],
            "resultado_resumo": resultado_resumo[:200],
            "timestamp": datetime.datetime.now().isoformat()
        })
        # Keep last 30 spawned agents
        registry["agents"] = registry["agents"][-30:]
        _SPAWNED_AGENTS_PATH.write_text(
            json.dumps(registry, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except Exception as e:
        print(f"[Agent Spawning] Erro ao registar agente: {e}")


# --- list_spawned_agents_summary ---
def list_spawned_agents_summary() -> str:
    """Returns a summary of previously spawned specialist agents."""
    try:
        if not _SPAWNED_AGENTS_PATH.exists():
            return ""
        registry = json.loads(_SPAWNED_AGENTS_PATH.read_text(encoding="utf-8"))
        agents = registry.get("agents", [])
        if not agents:
            return ""
        lines = [f"## Agentes Especialistas Criados Anteriormente ({len(agents)})"]
        for a in agents[-5:]:  # Show last 5
            ts = a.get("timestamp", "")[:10]
            lines.append(f"- [{ts}] **{a['nome']}** ({a['especialidade']}): {a['resultado_resumo'][:80]}")
        return "\n".join(lines)
    except Exception:
        return ""


# --- spawn_specialist_agent ---
async def spawn_specialist_agent(
    nome: str,
    especialidade: str,
    backstory: str,
    tarefa: str,
    contexto_projeto: str,
    on_msg
) -> str:
    """
    Dynamic Agent Spawning â€” creates a specialist sub-agent on-the-fly.
    Now equipped with tool-calling for tool-based claim verification (anti-hallucination).
    """
    on_msg(nome, especialidade, f"*Agente especialista iniciado. A trabalhar em: {tarefa[:80]}...*")
    
    # Buscar notas relevantes no Obsidian com base na tarefa do especialista
    obsidian_context = obs_tools.buscar_contexto_obsidian(tarefa)
    if obsidian_context:
        on_msg(nome, especialidade, f"ðŸ“– *Injetado contexto relevante do Obsidian na base de conhecimento de {nome}.*")

    
    confidence_protocol = """
## Protocolo de ConfianÃ§a (OBRIGATÃ“RIO)

Em cada afirmaÃ§Ã£o que faÃ§as, usa um destes marcadores:
- **[CERTO]** â€” facto que conheces com certeza (ex: sintaxe de uma funÃ§Ã£o, comportamento documentado)
- **[ESTIMATIVA]** â€” raciocÃ­nio dedutivo sÃ³lido, mas nÃ£o testado neste contexto especÃ­fico
- **[VERIFICAR]** â€” algo que deves confirmar com a documentaÃ§Ã£o ou testes reais antes de usar em produÃ§Ã£o

No final da tua resposta, inclui SEMPRE:
```
## NÃ­vel de ConfianÃ§a Geral
AUTO-AVALIAÃ‡ÃƒO: [0-100%] â€” [justificaÃ§Ã£o em 1 frase]
ITENS A VERIFICAR: [lista dos pontos marcados com [VERIFICAR]]
```

SÃª honesto. Se nÃ£o tiveres a certeza de algo, diz-o. Uma resposta honesta com [VERIFICAR] Ã© mais Ãºtil do que uma resposta inventada com falsa confianÃ§a.
"""
    specialist_system = (
        f"Chamas-te {nome}. Ã‰s um especialista em {especialidade}.\n"
        f"{backstory}\n\n"
        f"## Contexto do Projecto\n{contexto_projeto}\n\n"
        "Tens acesso a ferramentas locais para investigar o workspace e validar as tuas propostas:\n"
        "- `execute_command`: Executa comandos PowerShell para correr testes, interpretadores (ex: python), comandos de banco de dados, etc.\n"
        "- `write_file`: Escreve/cria ficheiros no disco.\n"
        "- `read_file`: LÃª ficheiros no workspace.\n"
        "- `list_directory`: Lista ficheiros e diretÃ³rios.\n\n"
        "## OBRIGAÃ‡ÃƒO DE VALIDAÃ‡ÃƒO PRÃTICA (Anti-AlucinaÃ§Ã£o)\n"
        "Antes de dares a tua resposta final como concluÃ­da, deves usar a ferramenta `execute_command` (ou outras) "
        "para testar, validar ou provar as tuas afirmaÃ§Ãµes tÃ©cnicas (por exemplo, testar a query SQL sugerida, "
        "executar um pequeno script Python para validar lÃ³gica complexa, ou verificar se caminhos/ficheiros existem).\n"
        "SÃ³ deves dar a resposta como definitiva depois de veres o resultado do teste no terminal e garantires que funciona. "
        "No final do teu texto, inclui obrigatoriamente a secÃ§Ã£o '## ValidaÃ§Ã£o PrÃ¡tica Realizada' com a descriÃ§Ã£o e output dos testes que executaste.\n"
        "Responde sempre em portuguÃªs de Portugal. "
        "Foca-te exclusivamente na tarefa atribuÃ­da. "
        "Fornece uma resposta completa, detalhada e accionÃ¡vel. "
        "NÃ£o te apresentes, vai directamente ao trabalho.\n"
        f"{confidence_protocol}"
    )
    
    if obsidian_context:
        specialist_system += "\n" + obsidian_context

    # --- Project Intelligence & Runtime Awareness ---
    try:
        if os.path.exists("symbols_index.json"):
            with open("symbols_index.json", "r", encoding="utf-8") as f:
                idx_data = f.read()
                if len(idx_data) > 6000:
                    idx_data = idx_data[:6000] + "\n... [TRUNCADO PARA POUPAR TOKENS] ..."
                specialist_system += f"\n\n## Project Intelligence (AST & Symbol Graph)\nO mapa estrutural da aplicaÃ§Ã£o (classes, funÃ§Ãµes e imports):\n```json\n{idx_data}\n```"
    except Exception:
        pass
        
    try:
        from intelligence.runtime_observer import RuntimeObserver
        observer = RuntimeObserver()
        rt_state = observer.compile_runtime_state(websocket_connected=True, active_agents=1, frontend_connected=True)
        specialist_system += f"\n\n## Runtime Awareness (System Health)\nEstado da mÃ¡quina e base de dados em tempo real:\n```json\n{json.dumps(rt_state, indent=2)}\n```"
    except Exception:
        pass

    # Filter tools for the specialist (allow local commands, files, obsidian, and advanced APIs)
    specialist_tools = [
        t for t in ag_tools.JARVIS_TOOLS
        if t["name"] in [
            "execute_command", "write_file", "read_file", "list_directory",
            "obsidian_list_notes", "obsidian_read_note", "obsidian_write_note", "obsidian_search_notes",
            "firecrawl_scrape_url", "browserbase_load_page", "youtube_get_transcript",
            "apify_run_actor", "composio_execute_action"
        ]
    ]
    
    messages = [{"role": "user", "content": tarefa}]
    
    max_steps = env_int("ORCHESTRATOR_SPECIALIST_MAX_STEPS", 3, minimum=1, maximum=5)
    verbose_progress = env_bool("ORCHESTRATOR_VERBOSE_PROGRESS", False)
    step = 0
    final_response_text = ""
    
    try:
        while step < max_steps:
            response_text = ""
            tool_calls = []
            
            use_fallback = True

            if use_fallback:
                gemini_key = os.getenv("GEMINI_API_KEY")
                if gemini_key and glb.is_gemini_valid:
                    try:
                        res_json = await query_model_with_tools(
                            "gemini",
                            "gemini-2.5-flash",
                            messages,
                            specialist_tools,
                            specialist_system,
                            timeout_seconds=45.0,
                        )
                        resp_msg = res_json.get("message", {})
                        response_text = resp_msg.get("content") or ""
                        raw_tool_calls = resp_msg.get("tool_calls", [])
                        for idx, rtc in enumerate(raw_tool_calls):
                            func_info = rtc.get("function", {})
                            name = func_info.get("name")
                            args = func_info.get("arguments", {})
                            if not isinstance(args, dict):
                                args = {}
                            tool_calls.append({
                                "id": rtc.get("id") or f"call_{step}_{idx}",
                                "name": name,
                                "input": args,
                            })
                        assistant_message = {
                            "role": "assistant",
                            "content": response_text,
                        }
                        if raw_tool_calls:
                            assistant_message["tool_calls"] = raw_tool_calls
                        messages.append(assistant_message)
                        use_fallback = False
                    except Exception as e:
                        print(f"[{nome}] Gemini fallback exception: {e}. Trying Ollama.")
                        
                if use_fallback:
                    # Local Ollama fallback (when both Groq and Gemini fail/are missing)
                    model_name = os.getenv("OLLAMA_MODEL", "qwen3.5:9b")
                    res_json = await query_ollama_with_tools(model_name, messages, specialist_tools, specialist_system)
                    msg_out = res_json.get("message", {})
                    response_text = msg_out.get("content", "") or ""
                    
                    raw_tool_calls = msg_out.get("tool_calls", [])
                    for idx, rtc in enumerate(raw_tool_calls):
                        func_info = rtc.get("function", {})
                        name = func_info.get("name")
                        args = func_info.get("arguments", {})
                        
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except Exception:
                                args = {}
                                
                        call_id = rtc.get("id") or f"call_{step}_{idx}"
                        tool_calls.append({
                            "id": call_id,
                            "name": name,
                            "input": args
                        })
                        
                    messages.append({"role": "assistant", "content": response_text})
            
            # If the agent wrote text and didn't call tools, show it
            if response_text.strip() and not tool_calls:
                final_response_text = response_text
                
            # If no tools to call, we are done
            if not tool_calls:
                break
                
            # Execute tool calls
            for tc in tool_calls:
                tool_name = tc["name"]
                tool_input = tc["input"]
                tool_use_id = tc["id"]
                
                if verbose_progress:
                    on_msg(nome, especialidade, f"[ValidaÃ§Ã£o] A executar `{tool_name}`...")
                
                result_str = ""
                if tool_name == "execute_command":
                    cmd = tool_input.get("command")
                    result_str = await ag_tools.run_local_command(cmd)
                elif tool_name == "write_file":
                    fn = tool_input.get("filename")
                    content = tool_input.get("content")
                    result_str = await ag_tools.run_write_file(fn, content)
                elif tool_name == "read_file":
                    fn = tool_input.get("filename")
                    result_str = await ag_tools.run_read_file(fn)
                elif tool_name == "list_directory":
                    path = tool_input.get("path", ".")
                    result_str = await ag_tools.run_list_directory(path)
                elif tool_name == "frontend_ui_command":
                    import server
                    action_ui = tool_input.get("action")
                    await server.broadcast({"type": "ui_action", "action": action_ui})
                    result_str = f"Comando de UI '{action_ui}' emitido para o frontend."
                elif tool_name == "semantic_code_search":
                    from intelligence.semantic_index import SemanticCodeIndex
                    q = tool_input.get("query", "")
                    idx = SemanticCodeIndex()
                    idx.build_index() # Garante que o index estÃ¡ atualizado
                    result_str = idx.search(q)
                elif tool_name == "refactor_move_symbol":
                    from agents.refactor_engine import RefactorEngine
                    src = tool_input.get("source_file")
                    tgt = tool_input.get("target_file")
                    sym = tool_input.get("symbol_name")
                    refac_engine = RefactorEngine()
                    result_str = refac_engine.move_symbol(src, tgt, sym)
                elif tool_name == "refactor_rename_symbol":
                    from agents.refactor_engine import RefactorEngine
                    fp = tool_input.get("filepath")
                    old = tool_input.get("old_name")
                    new = tool_input.get("new_name")
                    refac_engine = RefactorEngine()
                    result_str = refac_engine.rename_symbol(fp, old, new)
                elif tool_name == "start_autonomous_plan":
                    result_str = await run_start_autonomous_plan_safely(tool_input)
                elif tool_name == "registar_decisao_engenharia":
                    import database
                    import server
                    decision = tool_input.get("decision")
                    reason = tool_input.get("reason")
                    impact = tool_input.get("impact", "")
                    database.add_engineering_decision(decision, reason, impact)
                    decisions = database.get_engineering_decisions()
                    await server.broadcast({"type": "decisions_updated", "decisions": decisions})
                    result_str = f"DecisÃ£o de engenharia registada com sucesso no SQLite: '{decision}'"
                elif tool_name == "atualizar_memoria_arquitetura":
                    import database
                    import server
                    module = tool_input.get("module")
                    purpose = tool_input.get("purpose")
                    dependencies = tool_input.get("dependencies", "")
                    constraints = tool_input.get("constraints", "")
                    database.add_architecture_memory(module, purpose, dependencies, constraints)
                    arch = database.get_architecture_memory()
                    await server.broadcast({"type": "architecture_updated", "architecture": arch})
                    result_str = f"MemÃ³ria de arquitetura atualizada com sucesso no SQLite para o mÃ³dulo: '{module}'"
                elif tool_name == "apply_code_patch":
                    from agents.patch_engine import PatchEngine
                    fp = tool_input.get("file_path")
                    sn = tool_input.get("symbol_name")
                    nc = tool_input.get("new_code")
                    pe = PatchEngine()
                    result_str = pe.apply_patch(fp, sn, nc)
                elif tool_name == "obsidian_list_notes":
                    result_str = await obs_tools.run_obsidian_list_notes()
                elif tool_name == "obsidian_read_note":
                    fn = tool_input.get("filename")
                    result_str = await obs_tools.run_obsidian_read_note(fn)
                elif tool_name == "obsidian_write_note":
                    fn = tool_input.get("filename")
                    content = tool_input.get("content")
                    result_str = await obs_tools.run_obsidian_write_note(fn, content)
                elif tool_name == "obsidian_search_notes":
                    q = tool_input.get("query")
                    result_str = await obs_tools.run_obsidian_search_notes(q)
                elif tool_name == "firecrawl_scrape_url":
                    url = tool_input.get("url")
                    result_str = await ag_tools.run_firecrawl_scrape(url)
                elif tool_name == "read_pdf":
                    fp = tool_input.get("file_path")
                    mp = tool_input.get("max_pages", 20)
                    result_str = await ag_tools.read_pdf(fp, max_pages=mp)
                elif tool_name == "search_arxiv":
                    q = tool_input.get("query")
                    mr = tool_input.get("max_results", 5)
                    result_str = await ag_tools.search_arxiv(q, max_results=mr)
                elif tool_name == "browserbase_load_page":
                    url = tool_input.get("url")
                    result_str = await ag_tools.run_browserbase_load(url)
                elif tool_name == "youtube_get_transcript":
                    video_id_or_url = tool_input.get("video_id_or_url")
                    result_str = await ag_tools.run_youtube_transcript(video_id_or_url)
                elif tool_name == "apify_run_actor":
                    actor_id = tool_input.get("actor_id")
                    input_data = tool_input.get("input_data", {})
                    result_str = await ag_tools.run_apify_actor(actor_id, input_data)
                elif tool_name == "composio_execute_action":
                    action_name = tool_input.get("action_name")
                    arguments = tool_input.get("arguments", {})
                    result_str = await ag_tools.run_composio_action(action_name, arguments)
                elif tool_name == "gravar_regra_compounding":
                    chave = tool_input.get("chave")
                    descricao = tool_input.get("descricao")
                    correcao = tool_input.get("correcao")
                    import database
                    database.add_compounding_rule(chave, descricao, correcao)
                    result_str = f"âœ… Regra de Compounding Memory '{chave}' gravada com sucesso no SQLite."
                else:
                    result_str = f"Erro: Ferramenta desconhecida '{tool_name}'"
                    
                result_str = utils.truncate_result(result_str)
                truncated_res = result_str
                if len(truncated_res) > 300:
                    truncated_res = truncated_res[:300] + "\n... [Restante output ocultado] ..."
                on_msg(nome, especialidade, f"[Resultado de {tool_name}]:\n```\n{truncated_res}\n```")
                
                messages.append({
                    "role": "tool_result",
                    "tool_name": tool_name,
                    "tool_use_id": tool_use_id,
                    "content": result_str
                })
                
            step += 1
            
        if not final_response_text:
            # Fallback to last assistant message if any
            for msg in reversed(messages):
                if msg["role"] == "assistant" and isinstance(msg.get("content"), str) and msg.get("content").strip():
                    final_response_text = msg["content"]
                    break
                    
        return final_response_text or "(sem resposta de texto)"
        
    except Exception as e:
        err = f"Erro ao executar agente especialista '{nome}': {str(e)}"
        on_msg(nome, especialidade, err)
        return err


# --- classify_task_complexity ---
async def classify_task_complexity(prompt: str) -> str:
    """Classifies task complexity: SIMPLE (command line/terminal/quick files) vs COMPLEX (swarms/apps)."""
    clean = prompt.lower().strip(" .?!,")
    # Immediate checks for command-like tasks
    simple_keywords = ["abre", "abrir", "run", "execute", "corre", "limpa", "screenshot", "ecrÃ£", "janela", "janelas", "nota", "escreve uma nota", "pesquisa", "procura"]
    if any(k in clean for k in simple_keywords) and not any(k in clean for k in ["website", "landing page", "pomodoro", "todo list", "app", "site"]):
        return "SIMPLE"
        
    mode = os.getenv("ORCHESTRATOR_MODE", "local").lower()
    system_instruction = (
        "Avalia a complexidade do pedido do utilizador. "
        "Se o utilizador pedir para criar um website, landing page, temporizador pomodoro, lista de tarefas, jogo, "
        "ou qualquer aplicaÃ§Ã£o web/cÃ³digo complexo de mÃºltiplos ficheiros, responde apenas 'COMPLEX'. "
        "Se for um pedido simples de comando de terminal, ler/escrever uma nota simples, abrir um programa local, "
        "tirar screenshot ou ver janelas, responde apenas 'SIMPLE'."
    )
    
    if env_bool("ORCHESTRATOR_COMPLEXITY_MODEL_ENABLED", False) and mode in {"local", "ollama"}:
        try:
            request = ModelRequest(
                task_profile="CODE_REASONING",
                system_prompt=system_instruction,
                user_prompt=prompt,
                expected_output=ExpectedOutput(
                    format=OutputFormat.TEXT
                ),
                temperature=0.0,
                max_output_tokens=10,
                metadata={
                    "consumer": "orchestrator",
                    "operation": "complexity_classification",
                },
                model_preferences=ModelPreferences(
                    providers=("ollama",),
                    models=(
                        os.getenv("OLLAMA_MODEL", "qwen3.5:9b"),
                    ),
                    mode="chat",
                ),
                execution_constraints=ExecutionConstraints(
                    max_attempts=1,
                    timeout_seconds=10.0,
                    streaming=False,
                    thinking=False,
                    allow_recovery=False,
                    stop_on_no_progress=False,
                ),
            )
            response = await get_model_harness().execute(request)
            if response.status == ModelResponseStatus.SUCCEEDED:
                val = response.raw_text.strip().upper()
                if "COMPLEX" in val:
                    return "COMPLEX"
                return "SIMPLE"
        except Exception:
            pass

    return "COMPLEX" if any(w in clean for w in ["website", "landing page", "pomodoro", "site", "app", "jogo", "game", "desenvolve"]) else "SIMPLE"


# --- shared model tool transport ---
async def query_model_with_tools(
    provider_name: str,
    model_name: str,
    messages: list,
    tools: list,
    system_prompt: str,
    *,
    timeout_seconds: float = 120.0,
) -> dict:
    tool_schemas = []
    for tool in tools:
        tool_schemas.append({
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["input_schema"]
            }
        })
        
    conversation_messages = []
    for msg in messages:
        role = msg["role"]
        content = msg["content"]
        
        # If assistant has complex tool use structure (Claude style), map to simple structure
        if role == "assistant" and isinstance(content, list):
            text_content = ""
            tool_calls = []
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        text_content += item.get("text", "")
                    elif item.get("type") == "tool_use":
                        tool_calls.append({
                            "type": "function",
                            "function": {
                                "name": item.get("name"),
                                "arguments": item.get("input", {})
                            }
                        })
            payload_msg = {"role": "assistant", "content": text_content}
            if tool_calls:
                payload_msg["tool_calls"] = tool_calls
            conversation_messages.append(payload_msg)
        elif role == "tool_result":
            conversation_messages.append({
                "role": "tool",
                "name": msg.get("tool_name", "tool"),
                "tool_call_id": msg.get("tool_use_id"),
                "content": (
                    content if isinstance(content, list) else str(content)
                )
            })
        else:
            conversation_messages.append({
                "role": role,
                "content": str(content),
            })

    allowed_tools = tuple(
        str(item.get("name") or "")
        for item in tools
        if str(item.get("name") or "")
    )
    output_format = (
        OutputFormat.TOOL_CALLS
        if allowed_tools
        else OutputFormat.JSON
    )
    user_prompt = next(
        (
            str(item.get("content") or "")
            for item in reversed(conversation_messages)
            if item.get("role") == "user"
        ),
        "Continua a tarefa atual.",
    )
    request = ModelRequest(
        task_profile=(
            "TOOL_SELECTION"
            if allowed_tools
            else "STRUCTURED_EXTRACTION"
        ),
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        allowed_tools=allowed_tools,
        expected_output=ExpectedOutput(format=output_format),
        temperature=0.0,
        max_context_tokens=None,
        max_output_tokens=None,
        metadata={
            "consumer": "orchestrator",
            "operation": "tool_decision",
            "conversation_messages": conversation_messages,
            "tool_schemas": tool_schemas,
            "top_p": 0.8,
        },
        model_preferences=ModelPreferences(
            providers=() if (os.getenv("GEMINI_FOR_COMPLEX", "").lower() in ("true", "1", "yes") and provider_name in ("local", "ollama")) else (provider_name,),
            models=() if (os.getenv("GEMINI_FOR_COMPLEX", "").lower() in ("true", "1", "yes") and provider_name in ("local", "ollama")) else (model_name,),
            mode="chat",
        ),
        execution_constraints=ExecutionConstraints(
            max_attempts=1,
            timeout_seconds=timeout_seconds,
            streaming=False,
            thinking=False,
            allow_recovery=False,
            stop_on_no_progress=False,
        ),
    )
    response = await get_model_harness().execute(request)
    if response.status == ModelResponseStatus.PROVIDER_FAILED:
        if response.provider_exception is not None:
            raise response.provider_exception
        raise RuntimeError(
            f"O provider {provider_name} falhou sem excecao."
        )
    return {
        "message": {
            "role": "assistant",
            "content": response.raw_text,
            "tool_calls": [
                {
                    "id": call.call_id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": dict(call.arguments),
                    },
                }
                for call in response.tool_calls
            ],
        },
        "model": response.model,
        "done": response.status == ModelResponseStatus.SUCCEEDED,
        "done_reason": response.status.value,
    }


async def query_ollama_with_tools(
    model_name: str,
    messages: list,
    tools: list,
    system_prompt: str,
) -> dict:
    return await query_model_with_tools(
        "ollama",
        model_name,
        messages,
        tools,
        system_prompt,
    )


# --- split_response_messages ---
def split_response_messages(text: str, agent_info: dict = None) -> list[tuple[str, str, str]]:
    """
    Splits the LLM response text into multiple messages based on agent tags.
    Returns a list of tuples: (sender, role, content)
    """
    if agent_info is None:
        agent_info = {
            "ALEX": ("Alex", "Gestor Produto"),
            "CLARA": ("Clara", "UI/UX Designer"),
            "DEVON": ("Devon", "Programador Core"),
            "QUINN": ("Quinn", "QA Engineer"),
            "JARVIS": ("OPENCLAW", "Orquestrador"),
            "OPENCLAW": ("OPENCLAW", "Orquestrador")
        }
    
    tags = list(agent_info.keys())
    if "JARVIS" not in tags:
        tags.append("JARVIS")
    if "OPENCLAW" not in tags:
        tags.append("OPENCLAW")
        
    pattern = re.compile(rf'\[({"|".join(tags)})\]', re.IGNORECASE)
    parts = pattern.split(text)
    if len(parts) == 1:
        return [("OPENCLAW", "Orquestrador", text.strip())]
        
    messages = []
    first_part = parts[0].strip()
    if first_part:
        messages.append(("OPENCLAW", "Orquestrador", first_part))
        
    for i in range(1, len(parts), 2):
        tag = parts[i].upper()
        content = parts[i+1].strip()
        if not content:
            continue
            
        sender, role = agent_info.get(tag, ("OPENCLAW", "Orquestrador") if tag in ["JARVIS", "OPENCLAW"] else (tag.capitalize(), "Especialista"))
        messages.append((sender, role, content))
        
    return messages


# --- run_jarvis_orchestration ---
async def run_jarvis_orchestration(prompt_text: str, session_id: int, on_msg, on_file, on_kanban, history: list = None, template_name: str = None, on_template_change = None):
    mode = os.getenv("ORCHESTRATOR_MODE", "local").lower()
    swarm_enabled = env_bool("ORCHESTRATOR_SWARM_ENABLED", False)
    verbose_progress = env_bool("ORCHESTRATOR_VERBOSE_PROGRESS", False)
    jarvis_tools = build_tools_for_prompt(prompt_text, ag_tools.JARVIS_TOOLS, swarm_enabled=swarm_enabled)
    jarvis_tool_names = ", ".join(tool["name"] for tool in jarvis_tools)
    
    if template_name is None:
        template_name = glb.active_template_name
    template = swarm.get_active_template(template_name)
    agents_cfg = template["agents"]
    
    # Load ECC Contexts
    skills_context = swarm.load_skills_for_template(template, prompt_text=prompt_text)
    session_context = memory.load_session_context()
    obsidian_context = obs_tools.buscar_contexto_obsidian(prompt_text)
    
    # Compile agent descriptions dynamically
    agents_desc = "\n".join([
        f"   - {name.capitalize()} ({cfg['role']}): {cfg['goal']}"
        for name, cfg in agents_cfg.items() if name != 'jarvis'
    ])
    
    # Compile tasks workflow description dynamically
    tasks_desc = "\n".join([
        f"   - {tid.upper()} (para o {tcfg.get('agent', '').capitalize()}): {tcfg['description']}"
        for tid, tcfg in template["tasks"].items()
    ])
    
    # Build agent_info mapping for parsing dialogue tags
    agent_info = {}
    for name, cfg in agents_cfg.items():
        agent_info[name.upper()] = (name.capitalize(), cfg["role"])
    agent_info["JARVIS"] = ("OPENCLAW", "Orquestrador")
    agent_info["OPENCLAW"] = ("OPENCLAW", "Orquestrador")
    
    # Compile dialogue tags rule text
    tag_rules = ""
    for name, cfg in agents_cfg.items():
        if name in ['jarvis', 'openclaw']:
            continue
        uname = name.upper()
        tag_rules += f"   - Para o {cfg['role']} ({name.capitalize()}) responder no chat: usa a tag `[{uname}]` seguida do texto da resposta dele (ex: `[{uname}] Entendido, OpenClaw. Estou a trabalhar na minha tarefa...`).\n"
    tag_rules += "   - Para tu (OpenClaw) reportares ao CEO: usa a tag `[OPENCLAW]` no inÃ­cio da tua resposta (ex: `[OPENCLAW] CEO, as tarefas foram concluÃ­das.`).\n"
    tag_rules += "   - REGRA DE OURO DE FERRAMENTAS: Se decidires chamar uma ferramenta (tool call) no teu passo atual, deves manter a resposta de texto totalmente vazia e limpa (content deve ser ''). NUNCA uses a tag como `[OPENCLAW]` ou qualquer outra palavra se fores chamar uma ferramenta, caso contrÃ¡rio o servidor rejeitarÃ¡ a mensagem com erro 400."
    
    if verbose_progress:
        on_msg("OPENCLAW", "Orquestrador", f"Processando pedido: '{prompt_text}'")
    
    # 3. Queen Routing (Roteamento de Complexidade)
    if verbose_progress:
        on_msg("OPENCLAW", "Orquestrador (Queen)", "ðŸ‘‘ *Analisando complexidade do pedido e determinando rota do Swarm...*")
    complexity = await classify_task_complexity(prompt_text)
    if verbose_progress:
        route_label = "pelo Swarm Completo" if complexity == "COMPLEX" else "diretamente com ferramentas rapidas"
        on_msg("OPENCLAW", "Orquestrador (Queen)", f"Rota determinada: {complexity} ({route_label}).")
    
    messages = []
    # Collect valid assistant tool_call IDs from history to match tool_results correctly
    _valid_tool_call_ids = set()
    if history:
        for msg in history[:-1]:
            role = msg["role"]
            content = msg["content"]
            
            # CRITICAL FIX: Skip any tool_result messages from prior sessions â€” they can carry
            # empty function_response.name fields that cause hard 400 errors on Groq and Gemini.
            # History is only used for user/assistant conversation context.
            if role == "tool_result":
                continue
            
            # Clean dialogue tags from previous sessions to prevent Groq API tool-call failures (400 Bad Request)
            if role == "assistant" and isinstance(content, str):
                # Also strip stored assistant messages that had tool_calls with no name
                if "tool_calls" in msg:
                    valid_tcs = [tc for tc in msg.get("tool_calls", []) if tc.get("function", {}).get("name")]
                    if not valid_tcs:
                        continue  # Skip this message entirely if all tool_calls are nameless
                    
                match = re.match(r"^\[([A-Z0-9_-]+)(?:\s*-\s*([^\]]+))?\]:\s*(.*)$", content, re.DOTALL | re.IGNORECASE)
                if match:
                    msg_sender = match.group(1).upper()
                    msg_content = match.group(3).strip()
                    
                    if msg_sender in ["OPENCLAW", "JARVIS"]:
                        # It is the orchestrator's own response, format clean
                        messages.append({"role": "assistant", "content": msg_content})
                    else:
                        # Another agent's output. For the orchestrator, this acts as a user instruction/status
                        messages.append({"role": "user", "content": f"[{msg_sender}] {msg_content}"})
                else:
                    messages.append({"role": "assistant", "content": content})
            else:
                messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": prompt_text})
    
    # Core identity of the Jarvis CEO
    core_identity = (
        "Ã‰s o OpenClaw, o orquestrador central de IA, COO e Agente Executivo Universal da agÃªncia. "
        "A tua missÃ£o Ã© um Sistema Operativo Cognitivo AutÃ³nomo orientado a objetivos. "
        "NÃ£o Ã©s um simples gerador de sites nem um copiloto de cÃ³digo. A tua funÃ§Ã£o Ã© atingir o objetivo definido pelo utilizador (CEO) utilizando a melhor combinaÃ§Ã£o possÃ­vel de raciocÃ­nio, swarms de domÃ­nio, ferramentas locais e gestÃ£o de recursos.\n"
        "Tens acesso a ferramentas locais e externas, mas em cada pedido so podes usar a lista dinamica de ferramentas disponiveis indicada mais abaixo.\n"
        "LOOP ENGINEERING: A tua primeira acÃ§Ã£o em QUALQUER pedido que envolva tarefas Ã© SEMPRE chamar `declarar_objetivo` "
        "para definir o Goal e os critÃ©rios de sucesso. SÃ³ depois executas as acÃ§Ãµes. "
        "O loop termina quando `verificar_qualidade(pronto_para_entrega=true)` for chamado com sucesso.\n"
        "ESTRATÃ‰GIA E EXECUÃ‡ÃƒO DE MEIOS (CRÃTICO):\n"
        "  - Como CEO cognitivo, tu analisas o objetivo e decides autonomamente quais as ferramentas ou swarms de domÃ­nio acionar.\n"
        "  - Podes chamar `chamar_swarm_dominio` para delegar trabalho complexo de domÃ­nios especÃ­ficos. Os domÃ­nios disponÃ­veis sÃ£o:\n"
        "    1. 'builder_swarm' (para criaÃ§Ã£o de cÃ³digo, websites, apps, APIs, scripts, bases de dados).\n"
        "    2. 'operator_swarm' (para organizar ficheiros, backups, lidar com docker/sandbox, comandos de SO).\n"
        "    3. 'creator_swarm' (para designs, ebooks, campanhas de copy, landing pages, infoprodutos).\n"
        "    4. 'growth_swarm' (para marketing, otimizaÃ§Ã£o de SEO, monetizaÃ§Ã£o, pesquisa de nichos, vendas).\n"
        "    5. 'research_swarm' (para recolha de informaÃ§Ã£o web, sumÃ¡rios, Obsidian e RAG).\n"
        "  - Podes encadear mÃºltiplos swarms em sequÃªncia se o objetivo do utilizador for complexo (ex: growth_swarm para pesquisar nichos, depois creator_swarm para redigir o produto, depois builder_swarm para codificar a landing page).\n"
        "  - Deves preferir aÃ§Ãµes concretas, prÃ¡ticas e verificÃ¡veis (escrever ficheiros, correr scripts de teste, arquivar notas no Obsidian) em vez de respostas teÃ³ricas ou ideias abstratas.\n"
        "DYNAMIC AGENT SPAWNING: Se precisares de competÃªncias ultra-especÃ­ficas que os swarms nÃ£o cobrem, usa `criar_agente_especialista` para spawnar um subagente focado.\n"
        "REGRAS DE CHAMADA DE FERRAMENTAS (CRÃTICO): Se decidires chamar uma ferramenta, o teu output deve conter UNICAMENTE a chamada da ferramenta. NÃ£o deves escrever qualquer texto conversacional, explicaÃ§Ãµes, saudaÃ§Ãµes, desculpas, nem tags como [OPENCLAW] nessa resposta. O conteÃºdo de texto (content) deve estar completamente vazio. Escrever texto ou tags ao mesmo tempo que chamas uma ferramenta causa um erro fatal de API 400. SÃ³ deves escrever texto ou usar tags quando NÃƒO estiveres a chamar nenhuma ferramenta.\n"
    )
    
    # Agent + task context (template-specific)
    team_context = (
        f"A tua equipa:\n{agents_desc}\n\n"
        f"Fluxo de tarefas:\n{tasks_desc}\n\n"
        f"Regras de tags para diÃ¡logo:\n{tag_rules}\n"
    )
    
    # Operational rules
    operational_rules = (
        "Regras operacionais (CRÃTICAS):\n"
        "- CONCISÃƒO ABSOLUTA: Nunca escrevas parÃ¡grafos longos a descrever o que a tua equipa faz ou planeia fazer, a menos que o CEO o peÃ§a explicitamente. NÃ£o faÃ§as resumos ou blÃ¡-blÃ¡-blÃ¡ desnecessÃ¡rio.\n"
        "- Quando o CEO te pede algo e precisas de chamar uma ferramenta, NÃƒO escrevas qualquer resposta conversacional (nada de 'Compreendido', 'Vou tratar disso' ou '[OPENCLAW]'). Chama a ferramenta imediatamente. SÃ³ podes falar com o CEO com a tag [OPENCLAW] apÃ³s obteres os resultados das ferramentas executadas, ou se precisares de lhe fazer uma pergunta direta para clarificaÃ§Ã£o.\n"
        "- REGRA ANTI-PROMESSA VAZIA (CRÃTICA): Ã‰ ESTRITAMENTE PROIBIDO responder com frases como 'Vou tratar disso', 'Vou comeÃ§ar' SEM chamar uma ferramenta no mesmo passo. Se o CEO pedir para avanÃ§ar ou confirmar algo, a tua ÃšNICA resposta vÃ¡lida Ã© chamar imediatamente a ferramenta relevante.\n"
        "- MEMÃ“RIA DO WORKSPACE: Deves criar e manter ativamente um ficheiro 'sandbox_dir/MEMORY.md' (ou ler 'MEMORY.md' se existir) que descreva o progresso das tarefas, decisÃµes chave tomadas e os prÃ³ximos passos. Atualiza este ficheiro sempre que concluÃ­res uma fase importante de desenvolvimento para garantir o alinhamento da equipa (Hive Mind).\n"
        "- Fala SEMPRE em portuguÃªs de Portugal (PT-PT)\n"
        "- Usa 'CEO' moderadamente, sem repetir em cada frase\n"
        "- Para abrir programas, sites ou navegadores (ex: Google, YouTube, Chrome, Word, Excel): chama `execute_command` (`Start-Process 'https://google.com'`) IMEDIATAMENTE. NUNCA respondas que ja esta aberto sem executar o comando.\n"
        "- Podes misturar mensagens no mesmo passo para conversaÃ§Ãµes dinÃ¢micas\n"
    )
    
    # Assemble full system prompt with ECC patterns
    system_prompt = core_identity + "\n" + team_context + "\n" + operational_rules
    system_prompt += (
        "\n\n[FERRAMENTAS DISPONIVEIS NESTE PEDIDO]\n"
        f"Usa apenas estas ferramentas: {jarvis_tool_names}.\n"
        "Se uma ferramenta nao estiver nesta lista, ela esta indisponivel para este pedido.\n"
    )
    if not prompt_allows_obsidian(prompt_text):
        system_prompt += (
            "Obsidian esta indisponivel neste pedido. Nunca uses `obsidian_write_note` para criar ficheiros de apps, websites, backend, frontend ou sandbox. "
            "Para ficheiros de projeto usa sempre `write_file`.\n"
        )
    if not swarm_enabled:
        system_prompt += (
            "\n\n[MODO EXECUTOR DISCIPLINADO]\n"
            "O swarm de dominio esta desativado nesta sessao. NUNCA chames `chamar_swarm_dominio`.\n"
            "Resolve a tarefa diretamente com ferramentas locais (`list_directory`, `read_file`, `write_file`, `execute_command`, `verificar_qualidade`).\n"
            "Nao simules debate de agentes, nao escrevas mensagens de progresso por cada micro-passo e so fala com o CEO em milestones ou quando precisares de uma decisao.\n"
        )

    system_prompt += (
        "\n\n[COORDENACAO OPERACIONAL POR ESTADO]\n"
        "Em cada passo escolhe exatamente UMA proxima acao operacional.\n"
        "Se ainda faltam evidencias no TASK_STATE, nao respondas em prosa: emite uma tool call.\n"
        "Nao chames planner, swarm ou agente especialista para substituir execucao direta quando ainda nao existe evidencia minima.\n"
        "So chama `verificar_qualidade(pronto_para_entrega=true)` quando o TASK_STATE mostrar ficheiros/comandos/evidencias suficientes para os criterios.\n"
        "Se uma tool estrategica for realmente necessaria, o input tem de conter contexto concreto ligado ao objetivo e ao estado atual.\n"
    )
    
    if complexity == "SIMPLE":
        system_prompt += (
            "\n\n[ROTA QUEEN: SIMPLES]\n"
            "Esta tarefa foi classificada como SIMPLES pela Queen Routing. NUNCA chames a ferramenta `chamar_swarm_dominio`.\n"
            "Deves resolver o pedido do utilizador diretamente utilizando as tuas ferramentas locais disponiveis neste pedido (ex: execute_command, write_file) neste loop.\n"
            "OBRIGATÃ“RIO: Chama uma ferramenta imediatamente neste passo. NÃ£o escrevas texto â€” age."
        )
    
    # ECC Pattern 3: Instincts â€” always-on reflexes
    system_prompt += "\n" + OPENCLAW_INSTINCTS
    
    # ECC Pattern 4: Research-First rule
    system_prompt += "\n" + RESEARCH_FIRST_RULE
    
    # ECC Pattern 1: Skills â€” agent skill definitions
    if skills_context:
        system_prompt += f"\n\n## Skills da Equipa (guias de trabalho para cada agente):{skills_context}"
    
    # ECC Pattern 2: Memory â€” inject previous session context
    if session_context:
        system_prompt += f"\n\n{session_context}"

    # Injetar contexto relevante do Obsidian (RAG)
    if obsidian_context:
        system_prompt += "\n" + obsidian_context
    
    # Track files created this session for memory persistence
    _session_files_created: list = []
    task_requirements = infer_task_requirements(prompt_text)
    implementation_plan = ImplementationPlan()
    if task_requirements.requires_artifacts:
        model_name_for_plan = os.getenv("OLLAMA_MODEL", "qwen3.5:9b")
        try:
            implementation_plan = await request_implementation_plan_from_ollama(
                model_name_for_plan,
                prompt_text,
                task_requirements,
            )
            implementation_plan = validate_implementation_plan(task_requirements, implementation_plan)
            if not implementation_plan.valid:
                corrected_plan = await request_implementation_plan_from_ollama(
                    model_name_for_plan,
                    prompt_text,
                    task_requirements,
                    implementation_plan.issues,
                )
                implementation_plan = validate_implementation_plan(task_requirements, corrected_plan)
        except Exception as e:
            implementation_plan = ImplementationPlan(issues=[f"falha ao obter ImplementationPlan: {e}"], valid=False)
        if not implementation_plan.valid:
            explicit_fallback = fallback_plan_from_explicit_files(prompt_text, task_requirements)
            if explicit_fallback.valid:
                implementation_plan = explicit_fallback

    task_state = TaskState(
        objective=prompt_text,
        objective_declared=True,
        requirements=task_requirements,
        implementation_plan=implementation_plan,
        success_criteria=infer_success_criteria(prompt_text),
    )
    task_plan = create_task_plan(prompt_text)
    trace = OrchestrationTrace(
        prompt=prompt_text,
        model=os.getenv("OLLAMA_MODEL", "qwen3.5:9b"),
        intent="TASK",
        enabled=env_bool("ORCHESTRATION_DEBUG", False),
        plan=asdict(task_plan),
    )
    trace.record("plan.created", plan=asdict(task_plan))
    trace.record(
        "implementation_plan.created",
        requirements=asdict(task_requirements),
        implementation_plan=asdict(implementation_plan),
    )
    # Loop Engineering: track declared goal and metrics
    _loop_goal: str = prompt_text
    _loop_success_criteria: list = []
    _loop_goal_achieved: bool = False
    _goal_declared: bool = True
    _loop_start_time: float = __import__('time').time()
    
    max_steps = env_int("ORCHESTRATOR_MAX_STEPS", 8, minimum=2, maximum=10)
    if task_state.implementation_plan.valid and planned_file_paths(task_state.implementation_plan):
        plan_step_budget = len(planned_file_paths(task_state.implementation_plan)) + 5
        if task_state.requirements.requires_validation or task_state.requirements.requires_preview:
            plan_step_budget += 1
        max_steps = max(max_steps, min(16, plan_step_budget))
    step = 0
    current_active_card = None
    tool_call_history = []
    repeated_tool_counts: dict[str, int] = {}
    blocked_repeat_signatures: set[str] = set()
    write_file_recovery_attempted = False
    force_write_file_next = False
    structured_action_recovery_attempted = False

    def finish_orchestration(result: str, success: bool = False, reason: str = "") -> str:
        trace.success = success
        trace.stop_reason = reason or result
        trace.record("orchestration.finished", success=success, reason=trace.stop_reason, task_state=asdict(task_state))
        trace.save(task_state)
        return result
    
    while step < max_steps:
        task_plan.advance_if_ready(task_state, prompt_text)
        if task_plan.current_step.id == "finalizar" and not task_state.quality_checks and deterministic_quality_ready(prompt_text, task_state):
            quality_result = "Quality Gate PASSOU por evidencia deterministica do TaskState."
            update_task_state_after_tool(
                task_state,
                "verificar_qualidade",
                {"pronto_para_entrega": True, "criterios_cumpridos": task_state.success_criteria},
                quality_result,
            )
            trace.record(
                "quality.deterministic_pass",
                step=step,
                task_state=asdict(task_state),
                reason=quality_result,
            )
            on_msg("OPENCLAW", "Orquestrador", "[OK] Quality Gate passou com evidencia no TaskState.")
            return finish_orchestration("[OK] Tarefa concluida com evidencia no TaskState.", success=True, reason="deterministic_quality_pass")
        trace.record(
            "step.started",
            step=step,
            plan_step=asdict(task_plan.current_step),
            task_state=asdict(task_state),
        )
        # Harness Layer context injection
        current_sandbox_state = memory.HarnessContext.get_current_sandbox_state()
        compounding_rules = memory.load_compounding_memory_rules()
        architecture_memory = memory.load_architecture_memory_summary()
        engineering_decisions = memory.load_engineering_decisions_summary()
        
        # --- Project Intelligence & Runtime Awareness ---
        project_intelligence = ""
        try:
            if os.path.exists("symbols_index.json"):
                with open("symbols_index.json", "r", encoding="utf-8") as f:
                    idx_data = f.read()
                    if len(idx_data) > 6000:
                        idx_data = idx_data[:6000] + "\n... [TRUNCADO PARA POUPAR TOKENS] ..."
                    project_intelligence = f"## Project Intelligence (AST & Symbol Graph)\nO mapa estrutural da aplicaÃ§Ã£o (classes, funÃ§Ãµes e imports):\n```json\n{idx_data}\n```"
        except Exception:
            pass
            
        runtime_awareness = ""
        try:
            from intelligence.runtime_observer import RuntimeObserver
            observer = RuntimeObserver()
            rt_state = observer.compile_runtime_state(websocket_connected=True, active_agents=len(agents_cfg), frontend_connected=True)
            runtime_awareness = f"## Runtime Awareness (System Health)\nEstado da mÃ¡quina e base de dados em tempo real:\n```json\n{json.dumps(rt_state, indent=2)}\n```"
        except Exception:
            pass
        
        dynamic_system_prompt = system_prompt
        if compounding_rules:
            dynamic_system_prompt += "\n\n" + compounding_rules
        if architecture_memory:
            dynamic_system_prompt += "\n\n" + architecture_memory
        if engineering_decisions:
            dynamic_system_prompt += "\n\n" + engineering_decisions
        if current_sandbox_state:
            dynamic_system_prompt += "\n\n" + current_sandbox_state
        if project_intelligence:
            dynamic_system_prompt += "\n\n" + project_intelligence
        if runtime_awareness:
            dynamic_system_prompt += "\n\n" + runtime_awareness
        dynamic_system_prompt += "\n\n" + task_plan.as_prompt_context()
        dynamic_system_prompt += "\n\n" + task_state.as_prompt_context(prompt_text)
        dynamic_system_prompt += "\n\n" + implementation_plan_context(task_state.implementation_plan, task_state.requirements)
        if step > 0 or any(msg.get("tool_name") == "declarar_objetivo" for msg in messages if msg.get("role") == "tool_result"):
            dynamic_system_prompt += (
                "\n\n[INSTRUCAO CRITICA]: O objetivo do loop ja foi declarado com sucesso. "
                "A ferramenta `declarar_objetivo` esta indisponivel a partir de agora. "
                "Deves avancar para execucao concreta: primeiro `list_directory` em `sandbox_dir`, depois `write_file` para criar/alterar ficheiros, "
                "depois `execute_command` para validar/arrancar, e no fim `verificar_qualidade`."
            )

        active_jarvis_tools = jarvis_tools
        if _goal_declared or any(msg.get("tool_name") == "declarar_objetivo" for msg in messages if msg.get("role") == "tool_result"):
            active_jarvis_tools = remove_tools(jarvis_tools, {"declarar_objetivo"})
        active_jarvis_tools = allowed_tools_for_current_step(task_plan, active_jarvis_tools)
        force_write_file_this_step = force_write_file_next
        force_write_file_next = False
        if force_write_file_this_step:
            active_jarvis_tools = keep_tools(active_jarvis_tools, {"write_file"})
            dynamic_system_prompt += (
                "\n\n[RECOVERY WRITE_FILE OBRIGATORIO]\n"
                "Modelo respondeu em texto apos `list_directory`; recovery ativo. "
                "Neste passo a unica acao valida e chamar `write_file` para criar ou atualizar um ficheiro do projeto dentro de `sandbox_dir`. "
                "Nao escrevas texto, nao chames outra ferramenta e nao expliques o plano.\n"
            )
        active_jarvis_tool_names = ", ".join(tool["name"] for tool in active_jarvis_tools)
        dynamic_system_prompt += (
            "\n\n[FERRAMENTAS ATIVAS NESTE PASSO]\n"
            f"Usa apenas estas ferramentas neste passo: {active_jarvis_tool_names}.\n"
        )
            
        response_text = ""
        tool_calls = []
        run_fallback = True
        used_local_fallback = False

        if run_fallback:

            # Try Gemini Cloud fallback first if GEMINI_API_KEY is configured and valid
            gemini_key = os.getenv("GEMINI_API_KEY")
            if gemini_key and glb.is_gemini_valid and mode != "local":
                on_msg("JARVIS", "Orquestrador", "Fallback cloud ativo: a utilizar Gemini 2.5 Pro via Google AI Studio...")
                
                gemini_models = ["gemini-2.5-pro", "gemini-2.5-flash"]
                gemini_success = False
                
                for g_model in gemini_models:
                    try:
                        res_json = await query_model_with_tools(
                            "gemini",
                            g_model,
                            messages,
                            active_jarvis_tools,
                            dynamic_system_prompt,
                            timeout_seconds=30.0,
                        )
                        resp_msg = res_json.get("message", {})
                        response_text = resp_msg.get("content") or ""
                        raw_tool_calls = resp_msg.get("tool_calls", [])
                        for idx, rtc in enumerate(raw_tool_calls):
                            func_info = rtc.get("function", {})
                            name = func_info.get("name")
                            if not name:
                                continue
                            args = func_info.get("arguments", {})
                            if not isinstance(args, dict):
                                args = {}
                            tool_calls.append({
                                "id": rtc.get("id") or f"call_{step}_{idx}",
                                "name": name,
                                "input": args,
                            })
                        assistant_message = {
                            "role": "assistant",
                            "content": response_text,
                        }
                        if raw_tool_calls:
                            assistant_message["tool_calls"] = raw_tool_calls
                        messages.append(assistant_message)
                        run_fallback = False
                        gemini_success = True
                        break
                    except Exception as e:
                        print(f"[Gemini Fallback] Error with {g_model}: {e}")
                
                if gemini_success:
                    run_fallback = False

        if run_fallback:
            # OLLAMA LOCAL (GRATUITO)
            used_local_fallback = True
            model_name = os.getenv("OLLAMA_MODEL", "qwen3.5:9b")
            if verbose_progress:
                on_msg("JARVIS", "Orquestrador", f"A utilizar modelo local {model_name} via Ollama...")
            # Inject a local-model specific delegation reinforcement into system prompt
            complex_action_rule = (
                "  - Para tarefas complexas por dominio: chama `chamar_swarm_dominio`\n"
                if swarm_enabled
                else "  - Para tarefas complexas: trabalha diretamente com `list_directory`, `read_file`, `write_file`, `execute_command` e `verificar_qualidade`\n"
            )
            obsidian_action_rule = (
                "  - Para guardar no Obsidian: chama `obsidian_write_note`\n"
                if prompt_allows_obsidian(prompt_text)
                else ""
            )
            goal_action_rule = (
                "  - Se ainda nao sabes o que fazer a seguir: chama `declarar_objetivo` para definir o plano de acao.\n"
                if "declarar_objetivo" in {tool["name"] for tool in active_jarvis_tools}
                else "  - Se o objetivo ja foi declarado: NUNCA chames `declarar_objetivo`; chama `list_directory`, `write_file`, `execute_command` ou `verificar_qualidade`.\n"
            )
            local_system_prompt = dynamic_system_prompt + (
                "\n\n[REFORÃ‡O CRÃTICO ABSOLUTO â€” MODELO LOCAL]:\n"
                "REGRA MÃXIMA: A tua resposta de texto (content) DEVE ESTAR COMPLETAMENTE VAZIA. NÃ£o escreves nada.\n"
                "A tua ÃšNICA saÃ­da permitida Ã© uma chamada de ferramenta (tool_call). SEM EXCEÃ‡Ã•ES.\n"
                "Ã‰ PROIBIDO: escrever planos, resumos, listas, explicaÃ§Ãµes, intenÃ§Ãµes, perguntas ou qualquer texto.\n"
                "Ã‰ PROIBIDO: dizer 'Vou fazer X', 'Vou criar Y', 'Vou tratar disso' â€” isso Ã© FALHA TOTAL.\n"
                "A ÃšNICA AÃ‡ÃƒO CORRETA Ã© chamar IMEDIATAMENTE uma das tuas ferramentas:\n"
                f"{complex_action_rule}"
                "  - Para criar ficheiros de texto/markdown: chama `write_file`\n"
                "  - Para executar comandos: chama `execute_command`\n"
                f"{obsidian_action_rule}"
                f"{goal_action_rule}"
                "NUNCA ESCREVAS PROSA. CHAMA UMA FERRAMENTA AGORA."
            )
            try:
                res_json = await query_ollama_with_tools(model_name, messages, active_jarvis_tools, local_system_prompt)
                msg_out = res_json.get("message", {})
                response_text = msg_out.get("content", "") or ""
                
                raw_tool_calls = msg_out.get("tool_calls", [])
                for idx, rtc in enumerate(raw_tool_calls):
                    func_info = rtc.get("function", {})
                    name = func_info.get("name")
                    if not name:  # CRITICAL: skip tool calls with empty/None name
                        continue
                    args = func_info.get("arguments", {})
                    
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except Exception:
                            args = {}
                            
                    call_id = rtc.get("id") or f"call_{step}_{idx}"
                    tool_calls.append({
                        "id": call_id,
                        "name": name,
                        "input": args
                    })
                    
                messages.append({"role": "assistant", "content": response_text})
                
            except Exception as e:
                err_msg = f"Erro no provider local: {str(e)}. Confirma que o serviÃ§o Ollama estÃ¡ ativo e que o modelo {model_name} estÃ¡ instalado."
                on_msg("JARVIS", "Orquestrador", err_msg)
                return finish_orchestration(err_msg, success=False, reason="ollama_error")

        if response_text.strip() and not tool_calls:
            recovered_tool_calls = parse_text_tool_calls(response_text, active_jarvis_tools, step)
            if recovered_tool_calls:
                tool_calls.extend(recovered_tool_calls)
                assistant_content = [
                    {
                        "type": "tool_use",
                        "id": tc["id"],
                        "name": tc["name"],
                        "input": tc["input"],
                    }
                    for tc in recovered_tool_calls
                ]
                if messages and messages[-1].get("role") == "assistant":
                    messages[-1]["content"] = assistant_content
                else:
                    messages.append({"role": "assistant", "content": assistant_content})
                response_text = ""
            elif task_plan.current_step.id == "criar_ficheiros" and task_state.implementation_plan.valid:
                planned_call = await request_planned_write_file_from_ollama(
                    os.getenv("OLLAMA_MODEL", "qwen3.5:9b"),
                    prompt_text,
                    task_state,
                )
                trace.record(
                    "tool_call.planned_write_recovery",
                    recovered=planned_call,
                    plan=asdict(task_state.implementation_plan),
                )
                if planned_call:
                    tool_calls.append(planned_call)
                    messages.append({
                        "role": "assistant",
                        "content": [
                            {
                                "type": "tool_use",
                                "id": planned_call["id"],
                                "name": planned_call["name"],
                                "input": planned_call["input"],
                            }
                        ],
                    })
                    response_text = ""
            elif not structured_action_recovery_attempted:
                structured_action_recovery_attempted = True
                model_name = os.getenv("OLLAMA_MODEL", "qwen3.5:9b")
                try:
                    json_action_text = await request_structured_action_from_ollama(
                        model_name,
                        messages,
                        active_jarvis_tools,
                        "resposta textual sem tool_call",
                    )
                    structured_tool_calls = parse_structured_action(json_action_text, jarvis_tools, step)
                    trace.record(
                        "tool_call.structured_recovery",
                        raw_response=json_action_text,
                        recovered=structured_tool_calls,
                    )
                    if structured_tool_calls:
                        tool_calls.extend(structured_tool_calls)
                        messages.append({
                            "role": "assistant",
                            "content": [
                                {
                                    "type": "tool_use",
                                    "id": tc["id"],
                                    "name": tc["name"],
                                    "input": tc["input"],
                                }
                                for tc in structured_tool_calls
                            ],
                        })
                        response_text = ""
                    else:
                        decision = ToolDecision(
                            CONTROLLED_STOP,
                            "O modelo nao conseguiu produzir uma acao executavel valida.",
                            "LLM",
                            task_plan.current_step.required_evidence,
                            "Trocar de modelo local ou simplificar a etapa atual.",
                        )
                        safe_msg = format_operational_error(task_plan.current_step.id, task_state, decision)
                        on_msg("JARVIS", "Orquestrador", safe_msg)
                        return finish_orchestration(safe_msg, success=False, reason="structured_action_failed")
                except Exception as e:
                    decision = ToolDecision(
                        CONTROLLED_STOP,
                        f"Falha ao pedir acao JSON estruturada ao modelo local: {e}",
                        "provider",
                        task_plan.current_step.required_evidence,
                        "Verificar Ollama/modelo local e repetir a tarefa.",
                    )
                    safe_msg = format_operational_error(task_plan.current_step.id, task_state, decision)
                    on_msg("JARVIS", "Orquestrador", safe_msg)
                    return finish_orchestration(safe_msg, success=False, reason="structured_action_exception")
                
        # Handle agent animations based on response text
        if response_text.strip() and tool_calls:
            parsed_msgs = split_response_messages(response_text, agent_info)
            for msg_sender, msg_role, msg_content in parsed_msgs:
                # Set kanban status based on who is speaking
                agent_key_lower = msg_sender.lower()
                assigned_task_id = None
                for task_id, t_cfg in template["tasks"].items():
                    if t_cfg.get("agent") == agent_key_lower:
                        assigned_task_id = task_id
                        break
                        
                if assigned_task_id:
                    if current_active_card and current_active_card != assigned_task_id:
                        on_kanban(current_active_card, "done")
                    on_kanban(assigned_task_id, "progress")
                    current_active_card = assigned_task_id
                
                on_msg(msg_sender, msg_role, msg_content)
            
        # Repetition / Loop Detection
        if tool_calls:
            current_call_sigs = [(tc["name"], json.dumps(tc["input"], sort_keys=True)) for tc in tool_calls]
            sig_key = json.dumps(current_call_sigs, sort_keys=True)
            if tool_call_history and tool_call_history[-1] == current_call_sigs:
                repeat_count = repeated_tool_counts.get(sig_key, 0) + 1
                repeated_tool_counts[sig_key] = repeat_count
                repeated_name = current_call_sigs[0][0] if current_call_sigs else "tool"
                repeated_args = current_call_sigs[0][1] if current_call_sigs else "{}"
                trace.record(
                    "loop.repeat_detected",
                    repeat_count=repeat_count,
                    tool=repeated_name,
                    args=repeated_args,
                )
                if repeat_count == 1:
                    messages.append({
                        "role": "user",
                        "content": (
                            f"Ja executaste `{repeated_name}` com estes argumentos. "
                            "Escolhe uma acao diferente que avance a etapa atual: ler ficheiro relevante, "
                            "criar ficheiro ou validar artefacto."
                        ),
                    })
                    step += 1
                    continue
                if repeat_count == 2:
                    blocked_repeat_signatures.add(sig_key)
                    messages.append({
                        "role": "user",
                        "content": (
                            f"A chamada repetida `{repeated_name}` com os mesmos argumentos esta bloqueada nesta etapa. "
                            f"Usa uma tool permitida para `{task_plan.current_step.id}` que produza nova evidencia."
                        ),
                    })
                    step += 1
                    continue
                print(f"[WARNING] Loop repetitivo detectado para: {current_call_sigs}.")
                decision = ToolDecision(
                    CONTROLLED_STOP,
                    f"Loop repetitivo confirmado para `{repeated_name}` com os mesmos argumentos.",
                    "LLM",
                    task_plan.current_step.required_evidence,
                    "Reformular a etapa atual com uma acao diferente.",
                )
                safe_msg = format_operational_error(task_plan.current_step.id, task_state, decision)
                on_msg("OPENCLAW", "Orquestrador", safe_msg)
                if current_active_card:
                    on_kanban(current_active_card, "done")
                return finish_orchestration(safe_msg, success=False, reason="loop_repetitivo")
            if sig_key in blocked_repeat_signatures:
                messages.append({
                    "role": "user",
                    "content": "Essa chamada repetida esta bloqueada. Escolhe uma acao diferente que avance o plano.",
                })
                step += 1
                continue
            tool_call_history.append(current_call_sigs)

        # If no tool calls â€” detect if model was idle (wrote prose instead of acting)
        if not tool_calls:
            if task_plan.current_step.id == "criar_ficheiros" and task_state.implementation_plan.valid:
                planned_call = await request_planned_write_file_from_ollama(
                    os.getenv("OLLAMA_MODEL", "qwen3.5:9b"),
                    prompt_text,
                    task_state,
                )
                trace.record(
                    "tool_call.planned_write_recovery_empty",
                    recovered=planned_call,
                    plan=asdict(task_state.implementation_plan),
                )
                if planned_call:
                    tool_calls.append(planned_call)
                    messages.append({
                        "role": "assistant",
                        "content": [
                            {
                                "type": "tool_use",
                                "id": planned_call["id"],
                                "name": planned_call["name"],
                                "input": planned_call["input"],
                            }
                        ],
                    })
                    response_text = ""
                else:
                    decision = ToolDecision(
                        INVALID_WITH_CORRECTION,
                        "Modelo sem tool e sem conteudo executavel para o proximo ficheiro do ImplementationPlan.",
                        "LLM",
                        task_state.missing_evidence(prompt_text),
                        "Emitir write_file para um ficheiro previsto no ImplementationPlan.",
                    )
                    messages.append({"role": "user", "content": format_operational_error(task_plan.current_step.id, task_state, decision)})
                    task_state.actions_without_progress += 1
                    step += 1
                    continue

            if not tool_calls and should_force_write_file_recovery(prompt_text, messages, write_file_recovery_attempted):
                write_file_recovery_attempted = True
                force_write_file_next = True
                recovery_msg = (
                    "Modelo respondeu em texto apos list_directory; recovery: forcing write_file for code generation task."
                )
                print(f"[OPENCLAW recovery] {recovery_msg}")
                messages.append({
                    "role": "user",
                    "content": (
                        f"[SISTEMA - RECOVERY]: {recovery_msg}\n"
                        "A tarefa e de geracao de codigo/projeto e ja listaste `sandbox_dir`. "
                        "No proximo passo tens exatamente uma ferramenta disponivel: `write_file`. "
                        "Chama `write_file` para criar ou atualizar o primeiro ficheiro necessario do projeto dentro de `sandbox_dir`. "
                        "Nao respondas em texto."
                    ),
                })
                step += 1
                continue

            if not tool_calls and (
                write_file_recovery_attempted
                and is_code_generation_task(prompt_text)
                and "write_file" not in tool_result_names(messages)
            ):
                safe_msg = (
                    "Recovery write_file falhou: o modelo local continuou sem emitir uma tool_call `write_file` valida "
                    "depois de `list_directory`. Orquestracao interrompida sem falso sucesso."
                )
                on_msg("JARVIS", "Orquestrador", safe_msg)
                return finish_orchestration(safe_msg, success=False, reason="write_file_recovery_failed")

            if not tool_calls:
                text_decision = validate_next_tool_decision(
                    prompt_text,
                    task_state,
                    "",
                    {"response_text": response_text},
                )
                if text_decision.status == CONTROLLED_STOP:
                    safe_msg = format_operational_error(task_state.last_stage, task_state, text_decision)
                    on_msg("JARVIS", "Orquestrador", safe_msg)
                    return finish_orchestration(safe_msg, success=False, reason="text_controlled_stop")
                if text_decision.status == INVALID_WITH_CORRECTION:
                    task_state.actions_without_progress += 1
                    task_state.controlled_errors.append(text_decision.reason)

                # Check if we're on step 0 with no tools called: this is an idle/promise response
                idle_threshold = env_int("ORCHESTRATOR_IDLE_RETRIES", 1, minimum=0, maximum=2)
                if not hasattr(run_jarvis_orchestration, '_idle_count'):
                    run_jarvis_orchestration._idle_count = {}
                # Count consecutive idle steps (text only, no tools)
                idle_count_key = session_id
                run_jarvis_orchestration._idle_count[idle_count_key] = run_jarvis_orchestration._idle_count.get(idle_count_key, 0) + 1
                current_idle = run_jarvis_orchestration._idle_count[idle_count_key]
                
                if text_decision.status == INVALID_WITH_CORRECTION and current_idle <= idle_threshold and step < max_steps - 1:
                    # Push a stern correction back into messages so next iteration acts
                    allowed_tool_hint = ", ".join(tool["name"] for tool in active_jarvis_tools)
                    correction_msg = (
                        "[SISTEMA â€” CORREÃ‡ÃƒO CRÃTICA]: A tua Ãºltima resposta foi APENAS TEXTO. Isso Ã© uma FALHA. "
                        "NÃ£o escreveste nenhuma chamada de ferramenta real. JSON em markdown tambem nao conta como tool_call. "
                        "AGORA, neste prÃ³ximo passo, chama OBRIGATORIAMENTE uma ferramenta. "
                        f"Motivo do contrato operacional: {text_decision.reason}. "
                        f"A tarefa atual e: {prompt_text}. Escolhe a ferramenta adequada para executar essa tarefa real "
                        f"usando apenas estas ferramentas disponiveis: {allowed_tool_hint}. "
                        "Para criar ficheiros na sandbox usa `write_file`; nao uses Obsidian para frontend/backend/apps. "
                        "NÃ£o escrevas mais texto â€” chama uma ferramenta agora."
                    )
                    messages.append({"role": "user", "content": correction_msg})
                    step += 1
                    continue  # Re-run the loop with the correction injected
                else:
                    # Too many idle responses â€” exit
                    run_jarvis_orchestration._idle_count[idle_count_key] = 0  # reset
                    if current_active_card:
                        on_kanban(current_active_card, "done")
                    if text_decision.status == INVALID_WITH_CORRECTION:
                        safe_msg = format_operational_error(task_state.last_stage, task_state, text_decision)
                        on_msg("JARVIS", "Orquestrador", safe_msg)
                        return finish_orchestration(safe_msg, success=False, reason="text_without_tool")
                    if used_local_fallback:
                        safe_msg = (
                            "Fallback local interrompido: o modelo Ollama respondeu em texto, mas nao emitiu uma tool call valida. "
                            "Para evitar acoes erradas, a orquestracao foi pausada. Divide a tarefa em passos menores ou ativa um provider cloud configurado."
                        )
                        on_msg("JARVIS", "Orquestrador", safe_msg)
                        return finish_orchestration(safe_msg, success=False, reason="local_fallback_interrupted")
                    if response_text.strip():
                        on_msg("OPENCLAW", "Orquestrador", "OrquestraÃ§Ã£o concluÃ­da!")
                    else:
                        on_msg("OPENCLAW", "Orquestrador", "[WARNING] Orquestracao encerrada sem acao. O modelo local nao chamou ferramentas. Tenta reformular o pedido.")
                    return finish_orchestration(response_text, success=False, reason="ended_without_tool")
            
        # Execute tool calls
        if current_active_card is None:
            on_kanban("start", "orchestration")
            first_task_id = list(template["tasks"].keys())[0] if template["tasks"] else "dev-code"
            current_active_card = first_task_id
            on_kanban(first_task_id, "progress")
            
        for tc in tool_calls:
            tool_name = tc["name"]
            tool_input = normalize_tool_input_paths(tool_name, tc["input"])
            tool_use_id = tc["id"]
            if (
                task_plan.current_step.id == "criar_ficheiros"
                and task_state.implementation_plan.valid
                and (
                    tool_name in {"list_directory", "read_file"}
                    or (tool_name == "write_file" and (not tool_input.get("filename") or not tool_input.get("content")))
                )
            ):
                planned_call = await request_planned_write_file_from_ollama(
                    os.getenv("OLLAMA_MODEL", "qwen3.5:9b"),
                    prompt_text,
                    task_state,
                )
                trace.record(
                    "tool_call.planned_write_repair",
                    original_tool=tool_name,
                    original_input=tool_input,
                    recovered=planned_call,
                )
                if planned_call:
                    tool_name = planned_call["name"]
                    tool_input = normalize_tool_input_paths(tool_name, planned_call["input"])
                    tool_use_id = planned_call["id"]
            repair = repair_proposed_action(task_state, task_plan, tool_name, tool_input)
            trace.record(
                "tool.repair_checked",
                step=step,
                plan_step=task_plan.current_step.id,
                original_tool=repair.original_tool,
                original_input=repair.original_input,
                repaired_tool=repair.tool_name,
                repaired_input=repair.tool_input,
                pre_actions=repair.pre_actions,
                changed=repair.changed,
                reason=repair.reason,
                decision=asdict(repair.decision) if repair.decision else None,
            )
            if repair.status == CONTROLLED_STOP:
                result_str = format_operational_error(
                    task_plan.current_step.id,
                    task_state,
                    repair.decision or ToolDecision(CONTROLLED_STOP, repair.reason, "seguranca"),
                )
                on_msg("JARVIS", "Orquestrador", result_str)
                return finish_orchestration(result_str, success=False, reason="repair_controlled_stop")

            for repair_index, pre_action in enumerate(repair.pre_actions):
                pre_tool_name = pre_action["tool_name"]
                pre_tool_input = normalize_tool_input_paths(pre_tool_name, pre_action.get("tool_input", {}))
                pre_result = ""
                if pre_tool_name == "list_directory":
                    pre_result = await ag_tools.run_list_directory(pre_tool_input.get("path", "sandbox_dir"))
                else:
                    pre_result = f"Erro controlado: reparador deterministico nao suporta pre-action `{pre_tool_name}`."
                pre_tool_id = f"repair_{step}_{repair_index}_{pre_tool_name}"
                messages.append({
                    "role": "tool_result",
                    "tool_use_id": pre_tool_id,
                    "tool_name": pre_tool_name,
                    "content": pre_result,
                })
                state_before = asdict(task_state)
                update_task_state_after_tool(task_state, pre_tool_name, pre_tool_input, pre_result)
                task_plan.advance_if_ready(task_state, prompt_text)
                trace.record(
                    "tool.repair_pre_action_executed",
                    step=step,
                    tool=pre_tool_name,
                    args=pre_tool_input,
                    result=str(pre_result)[:2000],
                    task_state_before=state_before,
                    task_state_after=asdict(task_state),
                    new_plan_step=asdict(task_plan.current_step),
                )

            if repair.changed:
                tool_name = repair.tool_name
                tool_input = repair.tool_input
            if repair.pre_actions:
                active_jarvis_tools = jarvis_tools
                if _goal_declared or any(msg.get("tool_name") == "declarar_objetivo" for msg in messages if msg.get("role") == "tool_result"):
                    active_jarvis_tools = remove_tools(jarvis_tools, {"declarar_objetivo"})
                active_jarvis_tools = allowed_tools_for_current_step(task_plan, active_jarvis_tools)
            allowed_tool_names = {tool["name"] for tool in active_jarvis_tools}
            if tool_name not in allowed_tool_names:
                plan_decision = validate_tool_for_plan(task_plan, tool_name)
                result_str = format_operational_error(task_plan.current_step.id, task_state, plan_decision)
                messages.append({
                    "role": "tool_result",
                    "tool_use_id": tool_use_id,
                    "tool_name": tool_name,
                    "content": result_str,
                })
                trace.record(
                    "tool.rejected_by_plan",
                    step=step,
                    plan_step=task_plan.current_step.id,
                    tool=tool_name,
                    args=tool_input,
                    decision=asdict(plan_decision),
                )
                messages.append({
                    "role": "user",
                    "content": (
                        "[SISTEMA - PLANO]: A tool proposta nao pertence a etapa atual. "
                        f"{plan_decision.correction}"
                    ),
                })
                continue

            decision = validate_next_tool_decision(prompt_text, task_state, tool_name, tool_input)
            trace.record(
                "tool.proposed",
                step=step,
                plan_step=task_plan.current_step.id,
                tool=tool_name,
                args=tool_input,
                decision=asdict(decision),
            )
            if decision.status != VALID:
                result_str = format_operational_error(task_state.last_stage, task_state, decision)
                messages.append({
                    "role": "tool_result",
                    "tool_use_id": tool_use_id,
                    "tool_name": tool_name,
                    "content": result_str,
                })
                update_task_state_after_tool(task_state, tool_name, tool_input, result_str)
                if decision.status == CONTROLLED_STOP:
                    on_msg("JARVIS", "Orquestrador", result_str)
                    if current_active_card:
                        on_kanban(current_active_card, "done")
                    return finish_orchestration(result_str, success=False, reason="validator_controlled_stop")
                messages.append({
                    "role": "user",
                    "content": (
                        "[SISTEMA - CONTRATO OPERACIONAL]: A tool call anterior foi recusada antes de executar. "
                        f"Motivo: {decision.reason}. "
                        f"Correcao: {decision.correction}. "
                        "Escolhe exatamente uma nova tool call que produza progresso verificavel."
                    ),
                })
                continue
            
            # Reset idle counter since a tool IS being called
            if hasattr(run_jarvis_orchestration, '_idle_count'):
                run_jarvis_orchestration._idle_count[session_id] = 0
            
            if verbose_progress:
                on_msg("OPENCLAW", "Orquestrador", f"A executar: {tool_name}...")
            
            result_str = ""
            try:
                if tool_name == "execute_command":
                    cmd = tool_input.get("command")
                    result_str = await ag_tools.run_local_command(cmd)
                elif tool_name == "chamar_swarm_dominio":
                    if not swarm_enabled:
                        result_str = (
                            "Swarm de dominio desativado por ORCHESTRATOR_SWARM_ENABLED=false. "
                            "Continua com ferramentas diretas: list_directory, read_file, write_file, execute_command e verificar_qualidade."
                        )
                    else:
                        dom = tool_input.get("dominio")
                        prompt_p = tool_input.get("prompt_projeto")
                        glb.active_template_name = dom
                        if on_template_change:
                            await on_template_change(dom)
                        result_str = await swarm.run_crew_orchestration(prompt_p, session_id, on_msg, on_file, on_kanban, template_name=dom)
                elif tool_name == "write_file":
                    fn = tool_input.get("filename")
                    content = tool_input.get("content")
                    result_str = await ag_tools.run_write_file(fn, content, on_file)
                    # ECC Memory: track files created this session
                    if fn and result_str and "sucesso" in result_str:
                        _session_files_created.append(fn)
                elif tool_name == "read_file":
                    fn = tool_input.get("filename")
                    result_str = await ag_tools.run_read_file(fn)
                elif tool_name == "list_directory":
                    path = tool_input.get("path", ".")
                    result_str = await ag_tools.run_list_directory(path)
                elif tool_name == "frontend_ui_command":
                    import server
                    action_ui = tool_input.get("action")
                    await server.broadcast({"type": "ui_action", "action": action_ui})
                    result_str = f"Comando de UI '{action_ui}' emitido para o frontend com sucesso."
                elif tool_name == "semantic_code_search":
                    from intelligence.semantic_index import SemanticCodeIndex
                    q = tool_input.get("query", "")
                    idx = SemanticCodeIndex()
                    idx.build_index()
                    result_str = idx.search(q)
                elif tool_name == "refactor_move_symbol":
                    from agents.refactor_engine import RefactorEngine
                    src = tool_input.get("source_file")
                    tgt = tool_input.get("target_file")
                    sym = tool_input.get("symbol_name")
                    refac_engine = RefactorEngine()
                    result_str = refac_engine.move_symbol(src, tgt, sym)
                elif tool_name == "refactor_rename_symbol":
                    from agents.refactor_engine import RefactorEngine
                    fp = tool_input.get("filepath")
                    old = tool_input.get("old_name")
                    new = tool_input.get("new_name")
                    refac_engine = RefactorEngine()
                    result_str = refac_engine.rename_symbol(fp, old, new)
                elif tool_name == "start_autonomous_plan":
                    result_str = await run_start_autonomous_plan_safely(tool_input)
                elif tool_name == "registar_decisao_engenharia":
                    import database
                    import server
                    decision = tool_input.get("decision")
                    reason = tool_input.get("reason")
                    impact = tool_input.get("impact", "")
                    database.add_engineering_decision(decision, reason, impact)
                    decisions = database.get_engineering_decisions()
                    await server.broadcast({"type": "decisions_updated", "decisions": decisions})
                    result_str = f"DecisÃ£o de engenharia registada com sucesso no SQLite: '{decision}'"
                elif tool_name == "atualizar_memoria_arquitetura":
                    import database
                    import server
                    module = tool_input.get("module")
                    purpose = tool_input.get("purpose")
                    dependencies = tool_input.get("dependencies", "")
                    constraints = tool_input.get("constraints", "")
                    database.add_architecture_memory(module, purpose, dependencies, constraints)
                    arch = database.get_architecture_memory()
                    await server.broadcast({"type": "architecture_updated", "architecture": arch})
                    result_str = f"MemÃ³ria de arquitetura atualizada com sucesso no SQLite para o mÃ³dulo: '{module}'"
                elif tool_name == "apply_code_patch":
                    from agents.patch_engine import PatchEngine
                    fp = tool_input.get("file_path")
                    sn = tool_input.get("symbol_name")
                    nc = tool_input.get("new_code")
                    pe = PatchEngine()
                    result_str = pe.apply_patch(fp, sn, nc)
                elif tool_name == "list_active_windows":
                    result_str = ag_tools.get_visible_windows_text()
                elif tool_name == "capture_screen":
                    path, b64 = await ag_tools.run_capture_screen()
                    if path:
                        windows = ag_tools.get_visible_windows_text()
                        result_str = f"Screenshot guardada com sucesso em '{path}'. Janelas abertas detetadas:\n{windows}"
                    else:
                        result_str = "Erro ao capturar ecrÃ£."
                # ECC Pattern 6: Verification Loop handler
                elif tool_name == "verificar_qualidade":
                    pronto = tool_input.get("pronto_para_entrega", False)
                    criterios = tool_input.get("criterios_cumpridos", [])
                    problemas = tool_input.get("problemas_encontrados", [])
                    ficheiros = tool_input.get("ficheiros_criados", [])
                    if ficheiros:
                        _session_files_created.extend(ficheiros)
                    quality_blocker = quality_gate_blocker(
                        prompt_text,
                        task_state,
                        _session_files_created,
                    )
                    if pronto and quality_blocker:
                        pronto = False
                        problemas = list(problemas) + [quality_blocker]
                    if pronto:
                        crit_str = "\n  - ".join(criterios) if criterios else "N/A"
                        result_str = f"âœ… Quality Gate PASSOU.\nCritÃ©rios cumpridos:\n  - {crit_str}\nTrabalho pronto para entrega ao CEO."
                        if current_active_card:
                            on_kanban(current_active_card, "done")
                        # ECC Memory: save session on successful delivery
                        memory.save_session_memory(
                            session_id=session_id,
                            goal=prompt_text,
                            files_created=list(set(_session_files_created)),
                            key_decisions=criterios
                        )
                        # Loop Engineering: mark goal as achieved
                        _loop_goal_achieved = True
                    else:
                        prob_str = "\n  - ".join(problemas) if problemas else "nÃ£o especificados"
                        result_str = f"âš ï¸ Quality Gate FALHOU. Problemas:\n  - {prob_str}\nContinuar a trabalhar antes de reportar ao CEO."
                # Loop Engineering: Goal Declaration handler
                elif tool_name == "declarar_objetivo":
                    if _goal_declared:
                        result_str = (
                            "Erro: O objetivo do loop jÃ¡ foi declarado anteriormente. "
                            "NÃ£o chames esta ferramenta de novo. Deves avanÃ§ar para a execuÃ§Ã£o usando outras ferramentas "
                            "(ex: write_file, execute_command) ou chamar 'verificar_qualidade' com pronto_para_entrega=True "
                            "se o trabalho estiver concluÃ­do ou se nÃ£o houver aÃ§Ãµes adicionais a realizar."
                        )
                    else:
                        _goal_declared = True
                        _loop_goal = tool_input.get("objetivo", prompt_text)
                        _loop_success_criteria = tool_input.get("criterios_de_sucesso", [])
                        complexidade = tool_input.get("complexidade_estimada", "mÃ©dia")
                        crit_str = "\n  - ".join(_loop_success_criteria) if _loop_success_criteria else "N/A"
                        result_str = (
                            "Objetivo registado. No proximo passo e proibido voltar a chamar `declarar_objetivo`. "
                            "Chama uma ferramenta de execucao concreta agora: para apps usa `list_directory` em `sandbox_dir`, "
                            "depois `write_file` para criar frontend/backend, depois `execute_command` para validar, e no fim `verificar_qualidade`."
                        )
                        on_msg("OPENCLAW", "Orquestrador", f"ðŸŽ¯ **Objetivo declarado:** {_loop_goal}")
                # Dynamic Agent Spawning handler
                elif tool_name == "criar_agente_especialista":
                    nome = tool_input.get("nome", "Especialista")
                    especialidade = tool_input.get("especialidade", "Especialista")
                    backstory = tool_input.get("backstory", "")
                    tarefa = tool_input.get("tarefa", "")
                    contexto = tool_input.get("contexto_projeto", "")
                    guardar = tool_input.get("guardar_agente", False)
                    
                    on_msg("OPENCLAW", "Orquestrador",
                        f"ðŸ§  **Spawning** agente especialista: **{nome}** ({especialidade})...")
                    
                    result_str = await spawn_specialist_agent(
                        nome=nome,
                        especialidade=especialidade,
                        backstory=backstory,
                        tarefa=tarefa,
                        contexto_projeto=contexto,
                        on_msg=on_msg
                    )
                    
                    if guardar:
                        register_spawned_agent(
                            nome=nome,
                            especialidade=especialidade,
                            tarefa=tarefa,
                            resultado_resumo=result_str[:200]
                        )
                        result_str += f"\n\nâœ… Agente **{nome}** guardado no registo para reutilizaÃ§Ã£o futura."
                elif tool_name == "obsidian_list_notes":
                    result_str = await obs_tools.run_obsidian_list_notes()
                elif tool_name == "obsidian_read_note":
                    fn = tool_input.get("filename")
                    result_str = await obs_tools.run_obsidian_read_note(fn)
                elif tool_name == "obsidian_write_note":
                    fn = tool_input.get("filename")
                    content = tool_input.get("content")
                    result_str = await obs_tools.run_obsidian_write_note(fn, content)
                elif tool_name == "obsidian_search_notes":
                    q = tool_input.get("query")
                    result_str = await obs_tools.run_obsidian_search_notes(q)
                elif tool_name == "firecrawl_scrape_url":
                    url = tool_input.get("url")
                    result_str = await ag_tools.run_firecrawl_scrape(url)
                elif tool_name == "read_pdf":
                    fp = tool_input.get("file_path")
                    mp = tool_input.get("max_pages", 20)
                    result_str = await ag_tools.read_pdf(fp, max_pages=mp)
                elif tool_name == "search_arxiv":
                    q = tool_input.get("query")
                    mr = tool_input.get("max_results", 5)
                    result_str = await ag_tools.search_arxiv(q, max_results=mr)
                elif tool_name == "browserbase_load_page":
                    url = tool_input.get("url")
                    result_str = await ag_tools.run_browserbase_load(url)
                elif tool_name == "youtube_get_transcript":
                    video_id_or_url = tool_input.get("video_id_or_url")
                    result_str = await ag_tools.run_youtube_transcript(video_id_or_url)
                elif tool_name == "apify_run_actor":
                    actor_id = tool_input.get("actor_id")
                    input_data = tool_input.get("input_data", {})
                    result_str = await ag_tools.run_apify_actor(actor_id, input_data)
                elif tool_name == "composio_execute_action":
                    action_name = tool_input.get("action_name")
                    arguments = tool_input.get("arguments", {})
                    result_str = await ag_tools.run_composio_action(action_name, arguments)
                elif tool_name == "gravar_regra_compounding":
                    chave = tool_input.get("chave")
                    descricao = tool_input.get("descricao")
                    correcao = tool_input.get("correcao")
                    import database
                    database.add_compounding_rule(chave, descricao, correcao)
                    result_str = f"âœ… Regra de Compounding Memory '{chave}' gravada com sucesso no SQLite."
                else:
                    result_str = f"Erro: Ferramenta desconhecida '{tool_name}'"
            except Exception as e:
                result_str = f"Erro ao processar a ferramenta: {str(e)}"
                
            result_str = utils.truncate_result(result_str)
            # Print tool result to host console for debugging/logging, avoiding Windows encoding crashes.
            safe_log_result = str(result_str[:400].strip()).encode("utf-8", errors="replace").decode("utf-8", errors="replace")
            try:
                print(f"[OPENCLAW tool_result] {tool_name}: {safe_log_result}...")
            except UnicodeEncodeError:
                print(f"[OPENCLAW tool_result] {tool_name}: {safe_log_result.encode('ascii', errors='replace').decode('ascii')}...")
            
            tool_res = {
                "role": "tool_result",
                "tool_name": tool_name,
                "tool_use_id": tool_use_id,
                "content": result_str
            }
            if tool_name == "capture_screen" and 'b64' in locals() and b64:
                tool_res["b64_data"] = b64
                
            messages.append(tool_res)
            state_before = asdict(task_state)
            update_task_state_after_tool(task_state, tool_name, tool_input, result_str)
            trace.record(
                "tool.executed",
                step=step,
                plan_step=task_plan.current_step.id,
                tool=tool_name,
                args=tool_input,
                result=str(result_str)[:2000],
                task_state_before=state_before,
                task_state_after=asdict(task_state),
            )
            
        step += 1
        
        # Loop Engineering: Goal-driven termination
        # Loop exits cleanly when goal is achieved via Quality Gate â€” not just on empty tool_calls
        if _loop_goal_achieved:
            duration = __import__('time').time() - _loop_start_time
            stats = memory.save_loop_metrics(
                success=True,
                steps_used=step,
                duration_secs=duration,
                goal=_loop_goal
            )
            metrics_str = memory.load_loop_metrics_summary()
            mins = int(duration // 60)
            secs = int(duration % 60)
            summary = f"[OK] Loop concluido com sucesso em {mins}m {secs}s ({step} passos)."
            if metrics_str:
                summary += f"\n{metrics_str}"
            on_msg("OPENCLAW", "Orquestrador", summary)
            return finish_orchestration(response_text or summary, success=True, reason="quality_gate_passed")

    if step_limit_completion_recovery_available(prompt_text, task_state):
        missing_without_quality = set(missing_requirement_evidence(prompt_text, task_state, include_quality=False))
        if missing_without_quality & RECOVERABLE_COMPLETION_EVIDENCE and not (task_state.commands_executed or task_state.sandbox_validated):
            validation_command = deterministic_validation_command_for_state(prompt_text, task_state)
            if validation_command:
                on_msg("OPENCLAW", "Orquestrador", "Limite atingido com artefactos prontos; a executar validacao deterministica final.")
                validation_result = await ag_tools.run_local_command(validation_command)
                validation_tool_id = f"step_limit_recovery_{step}_execute_command"
                messages.append({
                    "role": "tool_result",
                    "tool_name": "execute_command",
                    "tool_use_id": validation_tool_id,
                    "content": validation_result,
                })
                state_before = asdict(task_state)
                update_task_state_after_tool(task_state, "execute_command", {"command": validation_command}, validation_result)
                task_plan.advance_if_ready(task_state, prompt_text)
                trace.record(
                    "step_limit_recovery.validation_executed",
                    step=step,
                    command=validation_command,
                    result=str(validation_result)[:2000],
                    task_state_before=state_before,
                    task_state_after=asdict(task_state),
                )
                step += 1

        if deterministic_quality_ready(prompt_text, task_state):
            quality_input = {
                "pronto_para_entrega": True,
                "criterios_cumpridos": task_state.success_criteria,
                "problemas_encontrados": [],
                "ficheiros_criados": list(dict.fromkeys([*_session_files_created, *task_state.files_created])),
            }
            quality_result = "Quality Gate PASSOU por recuperacao deterministica no limite de passos."
            if not task_state.quality_checks:
                state_before = asdict(task_state)
                update_task_state_after_tool(task_state, "verificar_qualidade", quality_input, quality_result)
                trace.record(
                    "step_limit_recovery.quality_passed",
                    step=step,
                    quality_input=quality_input,
                    result=quality_result,
                    task_state_before=state_before,
                    task_state_after=asdict(task_state),
                )
                step += 1
            if current_active_card:
                on_kanban(current_active_card, "done")
            duration = __import__('time').time() - _loop_start_time
            memory.save_loop_metrics(
                success=True,
                steps_used=step,
                duration_secs=duration,
                goal=_loop_goal,
            )
            files_for_memory = list(dict.fromkeys([*_session_files_created, *task_state.files_created]))
            if files_for_memory:
                memory.save_session_memory(
                    session_id=session_id,
                    goal=prompt_text,
                    files_created=files_for_memory,
                    key_decisions=task_state.success_criteria or ["Validacao deterministica final"],
                )
            metrics_str = memory.load_loop_metrics_summary()
            mins = int(duration // 60)
            secs = int(duration % 60)
            summary = f"[OK] Loop concluido com recuperacao final em {mins}m {secs}s ({step} passos)."
            if metrics_str:
                summary += f"\n{metrics_str}"
            on_msg("OPENCLAW", "Orquestrador", summary)
            return finish_orchestration(summary, success=True, reason="step_limit_completion_recovery")

    if current_active_card:
        on_kanban(current_active_card, "done")
    
    # Loop Engineering: save metrics for failed/incomplete loops
    duration = __import__('time').time() - _loop_start_time
    memory.save_loop_metrics(
        success=False,
        steps_used=step,
        duration_secs=duration,
        goal=_loop_goal
    )
    metrics_str = memory.load_loop_metrics_summary()
    
    # ECC Memory: save session even if step limit was reached
    if _session_files_created:
        memory.save_session_memory(
            session_id=session_id,
            goal=prompt_text,
            files_created=list(set(_session_files_created)),
            key_decisions=["Limite de passos atingido"]
        )
    
    mins = int(duration // 60)
    secs = int(duration % 60)
    timeout_decision = ToolDecision(
        CONTROLLED_STOP,
        f"Limite de passos atingido ({step}/{max_steps}) sem evidencia suficiente para concluir.",
        "LLM",
        task_state.missing_evidence(prompt_text),
        "Continuar a partir do estado atual com uma tool direta que produza a evidencia em falta.",
    )
    timeout_msg = format_operational_error(task_state.last_stage, task_state, timeout_decision)
    timeout_msg += f"\nTempo: {mins}m {secs}s."
    if metrics_str:
        timeout_msg += f"\n{metrics_str}"
    on_msg("OPENCLAW", "Orquestrador", timeout_msg)
    return finish_orchestration(timeout_msg, success=False, reason="step_limit")
