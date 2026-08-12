from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class SafetyRule:
    category: str
    directive: str
    keywords: tuple[str, ...]


_DEFAULT_SAFETY_RULES = (
    SafetyRule(
        category="FILE_SYSTEM",
        directive="PROIBIDO sobrescrever ficheiros do sistema fora de sandbox_dir/ sem autorizacao. Preserva comentarios existentes.",
        keywords=("write_file", "salvar", "guardar", "ficheiro", "file", "alterar"),
    ),
    SafetyRule(
        category="DESKTOP_AUTOMATION",
        directive="Ao abrir aplicacoes locais (Google, Excel, Word), executa imediatamente o comando sem perguntar ou simular.",
        keywords=("abrir", "abre", "open", "lancar", "start", "executar"),
    ),
    SafetyRule(
        category="SECURITY",
        directive="NUNCA expor chaves de API reais, passwords ou tokens em ficheiros .example ou logs publicos.",
        keywords=("token", "api_key", "key", "password", "segurança", "auth", "secret"),
    ),
    SafetyRule(
        category="STRUCTURED_OUTPUT",
        directive="Chama apenas ferramentas permitidas pelo TaskProfile e envia argumentos compativeis com o JSON Schema.",
        keywords=("json", "tool", "ferramenta", "schema", "argumentos"),
    ),
)


class SHERuleBank:
    """Safety Harness Evolution (SHE) — 2026 Paper Implementation.

    Manages a dynamic Rule Bank that selectively injects context-relevant
    safety boundaries into the model's system prompt.
    """

    def __init__(self, custom_rules: Iterable[SafetyRule] | None = None):
        self.rules = tuple(custom_rules or _DEFAULT_SAFETY_RULES)

    def assemble_dynamic_rules(self, prompt_text: str, task_profile: str = "") -> str:
        """Analyzes task profile and prompt keywords to inject only active safety rules."""
        prompt_lower = (prompt_text or "").lower()
        active_directives: list[str] = []

        for rule in self.rules:
            # Active if any keyword is present in prompt or if relevant task profile
            if any(k in prompt_lower for k in rule.keywords) or task_profile in ("TOOL_SELECTION", "MISSION_PLANNING"):
                active_directives.append(f"- [{rule.category}]: {rule.directive}")

        if not active_directives:
            return ""

        return "\n### DIRECTIVAS E REGRAS DE SEGURANCA (SHE ENGINE)\n" + "\n".join(active_directives)


__all__ = ["SafetyRule", "SHERuleBank"]
