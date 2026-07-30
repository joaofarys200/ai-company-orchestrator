from __future__ import annotations

import json
import os
import re
from typing import Any

from backend.logging_config import log_event
from backend.websocket_gateway import resolve_under_base


AVAILABLE_TEMPLATE_NAMES = {
    "builder_swarm",
    "operator_swarm",
    "creator_swarm",
    "growth_swarm",
    "research_swarm",
}
AGENT_ICON_MAP = {
    "dev_lead": "briefcase",
    "sys_admin": "briefcase",
    "market_analyst": "briefcase",
    "designer": "palette",
    "ops_specialist": "palette",
    "coder": "code",
    "copywriter": "code",
    "growth_lead": "code",
    "researcher": "code",
    "knowledge_manager": "code",
}


def env_bool(
    name: str,
    default: bool = False,
) -> bool:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def env_int(
    name: str,
    default: int,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
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


def is_orchestration_result_error(
    result: str | None,
) -> bool:
    text = (result or "").lower()
    markers = [
        "fallback local interrompido",
        "limite de passos atingido",
        "erro:",
        "interrompido",
        "falhou",
        "falha",
        "recovery write_file falhou",
        "orquestracao interrompida",
        "orquestração interrompida",
        "erro controlado",
        "contrato operacional",
        "quality gate falhou",
    ]
    return any(marker in text for marker in markers)


def normalize_persistent_plan(plan_data: Any):
    if not isinstance(plan_data, dict):
        return None
    status = str(plan_data.get("status") or "").upper()
    goal = str(plan_data.get("goal") or "").strip()
    steps = plan_data.get("steps")
    has_steps = isinstance(steps, list) and len(steps) > 0
    if status in {"NONE", "DONE", "COMPLETED"}:
        return None
    if not goal and not has_steps:
        return None
    return plan_data


def read_persistent_plan_state(
    path: str,
    *,
    logger: Any,
):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as plan_file:
            return normalize_persistent_plan(
                json.load(plan_file)
            )
    except Exception as read_error:
        log_event(
            logger,
            "planner_state.read_error",
            level="error",
            error=str(read_error),
        )
        return None


def parse_file_context(
    prompt: str,
    *,
    project_root: str,
    sandbox_root: str,
    logger: Any,
) -> str:
    mentions = re.findall(r"@([\w.\-/]+)", prompt)
    if not mentions:
        return prompt
    extra_context = []
    for filename in dict.fromkeys(mentions):
        found = False
        for directory in (project_root, sandbox_root):
            if not directory:
                continue
            candidate = resolve_under_base(directory, filename)
            if not candidate:
                log_event(
                    logger,
                    "file_context.path_blocked",
                    level="warning",
                    filename=filename,
                )
                continue
            if not os.path.isfile(candidate):
                continue
            try:
                with open(
                    candidate,
                    "r",
                    encoding="utf-8",
                    errors="replace",
                ) as source_file:
                    content = source_file.read()
                if len(content) > 8000:
                    content = (
                        content[:8000]
                        + "\n... [truncado para 8000 "
                        "caracteres] ..."
                    )
                extra_context.append(
                    "\n\n--- ConteÃºdo do ficheiro "
                    f"@{filename} ---\n```\n{content}\n```"
                )
                log_event(
                    logger,
                    "file_context.injected",
                    filename=filename,
                    content_length=len(content),
                )
                found = True
                break
            except Exception as read_error:
                log_event(
                    logger,
                    "file_context.read_error",
                    level="error",
                    filename=filename,
                    error=str(read_error),
                )
        if not found:
            log_event(
                logger,
                "file_context.not_found",
                level="warning",
                filename=filename,
            )
    if extra_context:
        return prompt + "".join(extra_context)
    return prompt


def get_template_suggestions(template_name: str) -> list:
    suggestions = {
        "builder_swarm": [
            {
                "prompt": (
                    "Criar Landing Page de PortefÃ³lio Moderno"
                ),
                "label": "Landing Page PortefÃ³lio",
                "icon": "layout",
            },
            {
                "prompt": (
                    "Desenvolver API FastAPI para Tarefas "
                    "com SQLite"
                ),
                "label": "API FastAPI SQLite",
                "icon": "database",
            },
            {
                "prompt": (
                    "Escrever Script Python para Renomear "
                    "Ficheiros em Massa"
                ),
                "label": "Script Renomear",
                "icon": "file-code",
            },
        ],
        "operator_swarm": [
            {
                "prompt": (
                    "Configurar CÃ³pia de SeguranÃ§a do "
                    "Obsidian Vault"
                ),
                "label": "Backup Obsidian",
                "icon": "archive",
            },
            {
                "prompt": (
                    "Verificar Estado dos Contentores Docker "
                    "no Windows"
                ),
                "label": "Estado Docker",
                "icon": "server",
            },
            {
                "prompt": (
                    "Organizar Ficheiros da Sandbox por "
                    "ExtensÃ£o"
                ),
                "label": "Organizar Sandbox",
                "icon": "folder-plus",
            },
        ],
        "creator_swarm": [
            {
                "prompt": (
                    "Escrever Ebook de IntroduÃ§Ã£o a Agentes "
                    "de IA em PDF"
                ),
                "label": "Ebook Agentes IA",
                "icon": "book-open",
            },
            {
                "prompt": (
                    "Criar GuiÃ£o e Copy para LanÃ§amento de "
                    "Curso Online"
                ),
                "label": "Copy LanÃ§amento",
                "icon": "video",
            },
            {
                "prompt": (
                    "Projetar Mockup de Interface de "
                    "Utilizador para App"
                ),
                "label": "Mockup App",
                "icon": "palette",
            },
        ],
        "growth_swarm": [
            {
                "prompt": (
                    "Pesquisa de Nichos de MonetizaÃ§Ã£o com "
                    "IA para 500â‚¬/mÃªs"
                ),
                "label": "Nicho 500â‚¬/mÃªs",
                "icon": "dollar-sign",
            },
            {
                "prompt": (
                    "Delinear EstratÃ©gia de SEO para Blog de "
                    "Tecnologia"
                ),
                "label": "EstratÃ©gia SEO",
                "icon": "trending-up",
            },
            {
                "prompt": (
                    "Criar Plano de LanÃ§amento de Produto "
                    "Digital"
                ),
                "label": "Plano LanÃ§amento",
                "icon": "shopping-cart",
            },
        ],
        "research_swarm": [
            {
                "prompt": (
                    "Investigar TendÃªncias de Agentes "
                    "Inteligentes em 2026"
                ),
                "label": "TendÃªncias IA 2026",
                "icon": "search",
            },
            {
                "prompt": (
                    "Organizar Notas do Obsidian e Atualizar "
                    "SOPs"
                ),
                "label": "Organizar Vault",
                "icon": "book",
            },
            {
                "prompt": (
                    "Fazer SumÃ¡rio de DocumentaÃ§Ã£o sobre "
                    "FastAPI"
                ),
                "label": "SumÃ¡rio FastAPI",
                "icon": "align-left",
            },
        ],
    }
    return suggestions.get(
        template_name,
        suggestions["builder_swarm"],
    )


def normalize_template_name(template_name: str) -> str:
    if template_name in AVAILABLE_TEMPLATE_NAMES:
        return template_name
    return "builder_swarm"


def build_template_payload(
    template_name: str,
    *,
    agents_module: Any,
) -> dict:
    normalized_name = normalize_template_name(template_name)
    template_info = agents_module.get_active_template(
        normalized_name
    )
    agents_config = template_info.get("agents", {})
    tasks_config = template_info.get("tasks", {})
    return {
        "type": "template_changed",
        "template_name": normalized_name,
        "name": template_info.get("name", "Builder Swarm"),
        "description": template_info.get("description", ""),
        "agents": [
            {
                "id": name,
                "name": name.replace("_", " ").title(),
                "role": config.get("role", "Agente"),
                "icon": AGENT_ICON_MAP.get(
                    name,
                    "shield-check",
                ),
            }
            for name, config in agents_config.items()
            if name != "jarvis"
        ],
        "tasks": [
            {
                "id": task_id,
                "title": config.get(
                    "title",
                    task_id.replace("task_", "")
                    .replace("_", " ")
                    .capitalize(),
                ),
                "agent": config.get("agent"),
            }
            for task_id, config in tasks_config.items()
        ],
        "suggestions": get_template_suggestions(
            normalized_name
        ),
    }


def markdown_to_html(text: str) -> str:
    lines = text.split("\n")
    html_lines = []
    in_list = False
    in_table = False
    in_code = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            if in_code:
                html_lines.append("</code></pre>")
                in_code = False
            else:
                html_lines.append("<pre><code>")
                in_code = True
            continue
        if in_code:
            html_lines.append(line)
            continue
        if not stripped:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            if in_table:
                html_lines.append("</table>")
                in_table = False
            continue
        if stripped.startswith("# "):
            html_lines.append(f"<h1>{stripped[2:]}</h1>")
        elif stripped.startswith("## "):
            html_lines.append(f"<h2>{stripped[3:]}</h2>")
        elif stripped.startswith("### "):
            html_lines.append(f"<h3>{stripped[4:]}</h3>")
        elif stripped.startswith(("- ", "* ")):
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            content = re.sub(
                r"\*\*(.*?)\*\*",
                r"<strong>\1</strong>",
                stripped[2:],
            )
            html_lines.append(f"<li>{content}</li>")
        elif stripped.startswith("|"):
            if not in_table:
                html_lines.append("<table>")
                in_table = True
            parts = [
                part.strip()
                for part in stripped.split("|")[1:-1]
            ]
            if parts and all(
                re.match(r"^:?-+:?$", part)
                for part in parts
            ):
                continue
            row_type = (
                "th"
                if html_lines[-1] == "<table>"
                else "td"
            )
            row = "<tr>" + "".join(
                f"<{row_type}>{part}</{row_type}>"
                for part in parts
            ) + "</tr>"
            html_lines.append(row)
        else:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            if in_table:
                html_lines.append("</table>")
                in_table = False
            content = re.sub(
                r"\*\*(.*?)\*\*",
                r"<strong>\1</strong>",
                stripped,
            )
            html_lines.append(f"<p>{content}</p>")
    if in_list:
        html_lines.append("</ul>")
    if in_table:
        html_lines.append("</table>")
    if in_code:
        html_lines.append("</code></pre>")
    return "\n".join(html_lines)
