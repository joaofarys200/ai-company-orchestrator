from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable


@dataclass(frozen=True)
class AgentProfile:
    id: str
    role: str
    system_prompt: str
    allowed_tools: tuple[str, ...]
    task_profiles: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


class AgentProfileRegistry:
    def __init__(self, profiles: Iterable[AgentProfile]):
        self._profiles: dict[str, AgentProfile] = {}
        for profile in profiles:
            key = self._normalize(profile.id)
            if key in self._profiles:
                raise ValueError(f"AgentProfile duplicado: {key}.")
            if key != profile.id:
                raise ValueError(
                    "AgentProfile.id deve estar normalizado em minusculas."
                )
            self._profiles[key] = profile

    def get(self, profile_id: str) -> AgentProfile:
        key = self._normalize(profile_id)
        try:
            return self._profiles[key]
        except KeyError as exc:
            raise ValueError(
                f"AgentProfile desconhecido: {key}."
            ) from exc

    def resolve(
        self,
        executor_kind: str,
        metadata: dict | None = None,
    ) -> AgentProfile:
        metadata = metadata or {}
        explicit = str(
            metadata.get("agent_id")
            or metadata.get("assigned_agent")
            or ""
        ).strip()
        if explicit:
            return self.get(explicit)
        defaults = {
            "CODING": "devon",
            "PROJECT_BUILD": "devon",
            "RESEARCH": "alex",
            "DOCUMENT": "alex",
            "REVIEW": "quinn",
        }
        return self.get(defaults.get(str(executor_kind).upper(), "alex"))

    def describe(self) -> dict[str, dict]:
        return {
            key: profile.to_dict()
            for key, profile in self._profiles.items()
        }

    @staticmethod
    def _normalize(value: str) -> str:
        key = str(value or "").strip().lower()
        if not key:
            raise ValueError("AgentProfile.id e obrigatorio.")
        return key


def create_default_agent_profile_registry() -> AgentProfileRegistry:
    return AgentProfileRegistry((
        AgentProfile(
            id="alex",
            role="product_manager",
            system_prompt=(
                "Define objetivos, requisitos, prioridades e criterios "
                "de aceitacao verificaveis."
            ),
            allowed_tools=(
                "semantic_code_search",
                "read_file",
            ),
            task_profiles=("MISSION_PLANNING", "RESEARCH", "DOCUMENT"),
        ),
        AgentProfile(
            id="clara",
            role="product_designer",
            system_prompt=(
                "Define fluxos, interface e comportamento de utilizacao "
                "com base nos requisitos aprovados."
            ),
            allowed_tools=(
                "list_directory",
                "read_file",
                "semantic_code_search",
            ),
            task_profiles=("CODE_REASONING", "DOCUMENT_REVIEW"),
        ),
        AgentProfile(
            id="devon",
            role="software_engineer",
            system_prompt=(
                "Inspeciona o projeto, localiza simbolos e propoe a menor "
                "alteracao de codigo verificavel."
            ),
            allowed_tools=(
                "list_directory",
                "read_file",
                "semantic_code_search",
                "apply_code_patch",
                "execute_command",
            ),
            task_profiles=("CODE_REASONING", "STRUCTURED_EXTRACTION"),
        ),
        AgentProfile(
            id="quinn",
            role="quality_engineer",
            system_prompt=(
                "Valida alteracoes, testes, seguranca e criterios de "
                "aceitacao com evidencia reproduzivel."
            ),
            allowed_tools=(
                "list_directory",
                "read_file",
                "semantic_code_search",
                "execute_command",
            ),
            task_profiles=("CODE_REASONING", "DOCUMENT_REVIEW"),
        ),
    ))


__all__ = [
    "AgentProfile",
    "AgentProfileRegistry",
    "create_default_agent_profile_registry",
]
