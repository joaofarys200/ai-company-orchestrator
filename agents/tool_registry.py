from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


@dataclass(frozen=True)
class ToolMetadata:
    name: str
    description: str
    input_schema: dict[str, Any]
    permissions: tuple[str, ...] = field(default_factory=tuple)
    enabled: bool = True

    def as_llm_tool(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


class ToolRegistry:
    def __init__(self, tools: Iterable[dict[str, Any]] | None = None):
        self._tools: dict[str, ToolMetadata] = {}
        if tools:
            for tool in tools:
                self.register(tool)

    def register(self, tool: dict[str, Any], permissions: Iterable[str] | None = None) -> None:
        metadata = self._metadata_from_tool(tool, permissions)
        if metadata.name in self._tools:
            raise ValueError(f"Ferramenta duplicada no registry: {metadata.name}")
        self._tools[metadata.name] = metadata

    def get(self, name: str) -> ToolMetadata | None:
        return self._tools.get(name)

    def list(self) -> list[ToolMetadata]:
        return list(self._tools.values())

    def names(self) -> list[str]:
        return list(self._tools.keys())

    def validate(self) -> list[str]:
        errors: list[str] = []
        for tool in self._tools.values():
            if not tool.name:
                errors.append("Ferramenta sem nome.")
            if not tool.description:
                errors.append(f"Ferramenta sem descricao: {tool.name}")
            if tool.input_schema.get("type") != "object":
                errors.append(f"Schema invalido para ferramenta: {tool.name}")
        return errors

    def to_llm_tools(self) -> list[dict[str, Any]]:
        return [tool.as_llm_tool() for tool in self._tools.values() if tool.enabled]

    def documentation(self) -> str:
        lines = ["# Tool Registry", ""]
        for tool in self._tools.values():
            permissions = ", ".join(tool.permissions) if tool.permissions else "none"
            lines.append(f"- `{tool.name}`: {tool.description} Permissions: {permissions}.")
        return "\n".join(lines)

    @staticmethod
    def _metadata_from_tool(tool: dict[str, Any], permissions: Iterable[str] | None) -> ToolMetadata:
        name = str(tool.get("name", ""))
        description = str(tool.get("description", ""))
        input_schema = tool.get("input_schema") if isinstance(tool.get("input_schema"), dict) else {}
        inferred_permissions = tuple(permissions or infer_permissions(name))
        return ToolMetadata(
            name=name,
            description=description,
            input_schema=input_schema,
            permissions=inferred_permissions,
        )


def infer_permissions(tool_name: str) -> tuple[str, ...]:
    if tool_name == "execute_command":
        return ("command", "workspace")
    if tool_name in {"write_file", "read_file", "list_directory"}:
        return ("filesystem", "workspace")
    if tool_name in {"capture_screen", "list_active_windows", "frontend_ui_command"}:
        return ("desktop",)
    if tool_name.startswith("obsidian_") or tool_name in {
        "gravar_regra_compounding",
        "consultar_memoria_arquitetura",
        "atualizar_memoria_arquitetura",
        "registar_decisao_engenharia",
    }:
        return ("memory",)
    if tool_name in {
        "firecrawl_scrape_url",
        "browserbase_load_page",
        "youtube_get_transcript",
        "apify_run_actor",
        "composio_execute_action",
    }:
        return ("network", "external")
    if tool_name in {"chamar_swarm_dominio", "criar_agente_especialista"}:
        return ("orchestration",)
    return ()


def build_registry(tool_definitions: Iterable[dict[str, Any]]) -> ToolRegistry:
    registry = ToolRegistry(tool_definitions)
    errors = registry.validate()
    if errors:
        raise ValueError("; ".join(errors))
    return registry


def discover_default_registry() -> ToolRegistry:
    from agents.tools import JARVIS_TOOLS

    return build_registry(JARVIS_TOOLS)
