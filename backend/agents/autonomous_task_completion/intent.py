"""
JARVIS OS — Phase 57: Intent Understanding Engine
Parses and normalizes raw user intent, extracts core objectives, constraints,
and categorizes domain targets (frontend, backend, fullstack, bugfix, security, etc.).
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from .models import (
    AmbiguityItem,
    RequirementCategory,
    RequirementItem,
    TaskUnderstandingResult,
)


class IntentUnderstandingEngine:
    """Understands raw user intentions and converts them into structured task understanding."""

    DOMAIN_KEYWORDS = {
        "frontend": ["frontend", "react", "component", "css", "page", "modal", "button", "view", "interface visual"],
        "backend": ["backend", "api", "endpoint", "fastapi", "server", "database", "sqlite", "route", "microserviço", "microservice", "python"],
        "fullstack": ["fullstack", "full-stack", "end-to-end", "sistema completo", "com frontend"],
        "bugfix": ["fix", "corrigir", "erro", "bug", "falha", "repair", "broken", "crash"],
        "contract_change": ["contract", "schema", "drift", "polymorphic", "interface", "mudança contratual"],
        "refactor": ["refactor", "refatorar", "clean", "decompose", "hygiene", "modularizar"],
        "integration": ["integration", "integrar", "bridge", "webhook", "service", "sync"],
        "browser_task": ["browser", "navegador", "edge", "e2e", "dom", "screenshot", "click", "interação"],
        "data_task": ["data", "etl", "migration", "query", "sql", "dataset", "persist"],
        "security_task": ["security", "auth", "jwt", "sentinel", "quarantine", "sandbox", "token", "segurança"],
    }

    @classmethod
    def analyze_intent(cls, raw_intent: str, task_id: str | None = None) -> TaskUnderstandingResult:
        tid = task_id or f"task_{uuid.uuid4().hex[:8]}"
        normalized = cls._normalize_text(raw_intent)
        domain = cls._infer_domain(normalized)
        
        objective = cls._extract_objective(normalized)
        constraints = cls._extract_constraints(normalized)
        required_outputs = cls._extract_required_outputs(normalized, domain)
        ambiguities = cls._detect_ambiguities(normalized)
        missing_info = [a.description for a in ambiguities if a.risk_level in ("HIGH", "CRITICAL")]
        
        risk_level = "LOW"
        if any(w in normalized for w in ["auth", "security", "token", "password", "delete", "drop", "purge"]):
            risk_level = "HIGH"
        elif any(w in normalized for w in ["database", "contract", "schema", "payment", "economic"]):
            risk_level = "MEDIUM"

        confidence = 0.95 if not missing_info else 0.70

        return TaskUnderstandingResult(
            task_id=tid,
            raw_intent=raw_intent,
            normalized_intent=normalized,
            objective=objective,
            constraints=constraints,
            required_outputs=required_outputs,
            risk_level=risk_level,
            ambiguities=ambiguities,
            missing_information=missing_info,
            confidence=confidence,
            provenance={
                "engine": "IntentUnderstandingEngine",
                "domain": domain,
                "detected_keywords": [k for k, v in cls.DOMAIN_KEYWORDS.items() if any(kw in normalized for kw in v)],
            },
        )

    @staticmethod
    def _normalize_text(text: str) -> str:
        text = text.strip()
        text = re.sub(r"\s+", " ", text)
        return text

    @classmethod
    def _infer_domain(cls, text: str) -> str:
        lower = text.lower()
        for domain, keywords in cls.DOMAIN_KEYWORDS.items():
            if any(kw in lower for kw in keywords):
                return domain
        return "general_engineering"

    @staticmethod
    def _extract_objective(text: str) -> str:
        first_line = text.splitlines()[0] if text else "Autonomous Engineering Mission"
        first_line = re.sub(r"^(implementa|criar|desenvolver|fazer|build|create|fix)\s+", "", first_line, flags=re.IGNORECASE)
        return first_line[:120].strip() or "Execute autonomous task"

    @staticmethod
    def _extract_constraints(text: str) -> list[str]:
        constraints: list[str] = []
        lower = text.lower()
        if "sem quebrar" in lower or "no regressions" in lower:
            constraints.append("zero_regression")
        if "rápido" in lower or "fast" in lower or "latência" in lower:
            constraints.append("performance_bounded")
        if "typescript" in lower:
            constraints.append("strict_typescript")
        if "seguro" in lower or "security" in lower:
            constraints.append("sentinel_supervised")
        if not constraints:
            constraints.append("standard_jarvis_invariants")
        return constraints

    @staticmethod
    def _extract_required_outputs(text: str, domain: str) -> list[str]:
        outputs = ["execution_log", "verification_evidence"]
        if domain in ("frontend", "fullstack", "browser_task"):
            outputs.extend(["ui_components", "browser_screenshot"])
        if domain in ("backend", "fullstack", "contract_change"):
            outputs.extend(["api_endpoint", "contract_schema"])
        if domain == "bugfix":
            outputs.extend(["repaired_code", "regression_proof"])
        if domain == "security_task":
            outputs.extend(["security_audit_log", "sentinel_clearance"])
        return outputs

    @staticmethod
    def _detect_ambiguities(text: str) -> list[AmbiguityItem]:
        ambiguities: list[AmbiguityItem] = []
        lower = text.lower()
        # High-risk ambiguity: Auth without specifying JWT vs Session
        if "autentica" in lower or "auth" in lower or "login" in lower:
            if not ("jwt" in lower or "session" in lower or "oauth" in lower):
                ambiguities.append(
                    AmbiguityItem(
                        ambiguity_id=f"amb_{uuid.uuid4().hex[:6]}",
                        description="Mecanismo de autenticação não especificado (JWT vs Session vs OAuth)",
                        risk_level="HIGH",
                        resolution_strategy="REQUIRE_HUMAN",
                        chosen_resolution=None,
                    )
                )
        # Low-risk ambiguity: Database persistence engine
        if "persist" in lower or "armazenar" in lower or "guardar" in lower:
            if not ("sqlite" in lower or "postgres" in lower or "json" in lower):
                ambiguities.append(
                    AmbiguityItem(
                        ambiguity_id=f"amb_{uuid.uuid4().hex[:6]}",
                        description="Engine de persistência não explicitada",
                        risk_level="LOW",
                        resolution_strategy="DEFAULT_POLICY",
                        chosen_resolution="Usar SQLite padrão do JARVIS OS",
                    )
                )
        # Ambiguity: Styling framework
        if (re.search(r"\bui\b", lower) or "frontend" in lower) and not ("tailwind" in lower or "vanilla" in lower or "css" in lower):
            ambiguities.append(
                AmbiguityItem(
                    ambiguity_id=f"amb_{uuid.uuid4().hex[:6]}",
                    description="Framework de estilos não especificado",
                    risk_level="LOW",
                    resolution_strategy="DEFAULT_POLICY",
                    chosen_resolution="Vanilla CSS com Tailwind pré-instalado",
                )
            )
        return ambiguities
