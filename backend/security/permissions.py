from __future__ import annotations

from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Any, Callable


class PermissionLevel(Enum):
    READ_ONLY = auto()
    LOCAL_WRITE = auto()
    CODE_EXECUTION = auto()
    NETWORK_READ = auto()
    NETWORK_WRITE = auto()
    EXTERNAL_ACCOUNT = auto()
    FINANCIAL_ACTION = auto()
    IRREVERSIBLE_ACTION = auto()


class AutonomyLevel(str, Enum):
    LEVEL_0_ASSISTED = "LEVEL_0_ASSISTED"
    LEVEL_1_SUPERVISED = "LEVEL_1_SUPERVISED"
    LEVEL_2_BOUNDED = "LEVEL_2_BOUNDED"


@dataclass(frozen=True)
class ToolPermissionSpec:
    tool_name: str
    level: PermissionLevel
    requires_human_approval: bool = False
    description: str = ""


TOOL_PERMISSIONS: dict[str, ToolPermissionSpec] = {
    "read_file": ToolPermissionSpec("read_file", PermissionLevel.READ_ONLY, False, "Lê ficheiros locais"),
    "list_directory": ToolPermissionSpec("list_directory", PermissionLevel.READ_ONLY, False, "Lista diretorias"),
    "obsidian_list_notes": ToolPermissionSpec("obsidian_list_notes", PermissionLevel.READ_ONLY, False, "Lista notas RAG"),
    "obsidian_read_note": ToolPermissionSpec("obsidian_read_note", PermissionLevel.READ_ONLY, False, "Lê notas RAG"),
    "obsidian_search_notes": ToolPermissionSpec("obsidian_search_notes", PermissionLevel.READ_ONLY, False, "Pesquisa notas RAG"),
    "semantic_code_search": ToolPermissionSpec("semantic_code_search", PermissionLevel.READ_ONLY, False, "Pesquisa código"),
    "web_search": ToolPermissionSpec("web_search", PermissionLevel.NETWORK_READ, False, "Pesquisa na web"),
    "firecrawl_scrape_url": ToolPermissionSpec("firecrawl_scrape_url", PermissionLevel.NETWORK_READ, False, "Extrai página web"),
    "browserbase_load_page": ToolPermissionSpec("browserbase_load_page", PermissionLevel.NETWORK_READ, False, "Carrega página web"),
    "youtube_get_transcript": ToolPermissionSpec("youtube_get_transcript", PermissionLevel.NETWORK_READ, False, "Obtém transcrição de vídeo"),
    "write_file": ToolPermissionSpec("write_file", PermissionLevel.LOCAL_WRITE, False, "Escreve ficheiro local"),
    "apply_code_patch": ToolPermissionSpec("apply_code_patch", PermissionLevel.LOCAL_WRITE, False, "Aplica patch AST"),
    "refactor_move_symbol": ToolPermissionSpec("refactor_move_symbol", PermissionLevel.LOCAL_WRITE, False, "Move símbolo AST"),
    "refactor_rename_symbol": ToolPermissionSpec("refactor_rename_symbol", PermissionLevel.LOCAL_WRITE, False, "Renomeia símbolo AST"),
    "obsidian_write_note": ToolPermissionSpec("obsidian_write_note", PermissionLevel.LOCAL_WRITE, False, "Escreve nota RAG"),
    "execute_command": ToolPermissionSpec("execute_command", PermissionLevel.CODE_EXECUTION, False, "Executa comando shell"),
    "run_unit_tests": ToolPermissionSpec("run_unit_tests", PermissionLevel.CODE_EXECUTION, False, "Executa testes unitários"),
    "capture_screen": ToolPermissionSpec("capture_screen", PermissionLevel.READ_ONLY, False, "Tira screenshot do ecrã"),
    "external_account_create": ToolPermissionSpec("external_account_create", PermissionLevel.EXTERNAL_ACCOUNT, True, "Cria conta externa"),
    "publish_digital_asset": ToolPermissionSpec("publish_digital_asset", PermissionLevel.IRREVERSIBLE_ACTION, True, "Publica produto/asset"),
    "financial_transaction": ToolPermissionSpec("financial_transaction", PermissionLevel.FINANCIAL_ACTION, True, "Ação financeira com custo real"),
}


class PermissionPolicyManager:
    """Manages execution permissions, autonomy levels, and human approval gates for agent tool calls."""

    def __init__(
        self,
        allowed_levels: set[PermissionLevel] | None = None,
        autonomy_level: AutonomyLevel = AutonomyLevel.LEVEL_1_SUPERVISED,
    ):
        self.autonomy_level = autonomy_level
        if allowed_levels is None:
            self.allowed_levels = {
                PermissionLevel.READ_ONLY,
                PermissionLevel.LOCAL_WRITE,
                PermissionLevel.CODE_EXECUTION,
                PermissionLevel.NETWORK_READ,
                PermissionLevel.NETWORK_WRITE,
            }
        else:
            self.allowed_levels = allowed_levels

    def can_execute_tool(self, tool_name: str) -> tuple[bool, bool, str]:
        """
        Returns (is_allowed, requires_approval, reason).
        """
        spec = TOOL_PERMISSIONS.get(tool_name)
        if not spec:
            return True, False, f"Ferramenta '{tool_name}' sem especificação explícita de risco."

        # LEVEL 0 ASSISTED: Every external tool requires approval
        if self.autonomy_level == AutonomyLevel.LEVEL_0_ASSISTED:
            if spec.level in {PermissionLevel.NETWORK_READ, PermissionLevel.NETWORK_WRITE, PermissionLevel.EXTERNAL_ACCOUNT, PermissionLevel.FINANCIAL_ACTION, PermissionLevel.IRREVERSIBLE_ACTION}:
                return True, True, f"Modo ASSISTED (Level 0): ação externa '{tool_name}' requer confirmação humana."

        # High risk actions ALWAYS require approval regardless of autonomy level
        if spec.requires_human_approval or spec.level in {PermissionLevel.FINANCIAL_ACTION, PermissionLevel.EXTERNAL_ACCOUNT, PermissionLevel.IRREVERSIBLE_ACTION}:
            return True, True, f"Ação de alto risco '{tool_name}' ({spec.level.name}) requer aprovação humana explícita."

        if spec.level not in self.allowed_levels:
            return False, False, f"Nível de permissão '{spec.level.name}' desativado pela política atual."

        return True, False, "Permissão concedida."


__all__ = [
    "PermissionLevel",
    "AutonomyLevel",
    "ToolPermissionSpec",
    "TOOL_PERMISSIONS",
    "PermissionPolicyManager",
]
