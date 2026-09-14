"""
JARVIS OS — Phase 42: Experience Normalization & Signature Extraction
Maps heterogeneous natural language intents, technical contexts, and failure states
into canonical, structured ExperienceSignatures for cross-mission indexing.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from agents.experience_memory.models import ExperienceSignature


class IntentNormalizer:
    """Normalizes natural language intent formulations into deterministic semantic categories."""

    INTENT_MAP = [
        (
            re.compile(r"\b(pesquis|search|filtr|procur|busc|find|localiz|lookup)\w*", re.IGNORECASE),
            "SEARCH_AND_FILTER",
            ("ui", "filtering", "search"),
        ),
        (
            re.compile(r"\b(autentic|auth|login|jwt|token|sess|credenci|seguran|passkey|fido2)\w*", re.IGNORECASE),
            "AUTHENTICATION_AND_AUTH",
            ("security", "auth", "tokens"),
        ),
        (
            re.compile(r"\b(despes|gast|financ|receit|totais|contag|balan|ledger)\w*", re.IGNORECASE),
            "FINANCIAL_LEDGER",
            ("financial", "accounting", "ledger"),
        ),
        (
            re.compile(r"\b(oscila|loop|repeti|altern|fingerprint|trava)\w*", re.IGNORECASE),
            "OSCILLATION_DEFENSE",
            ("stability", "loop_control", "oscillation"),
        ),
        (
            re.compile(r"\b(repar|cura|fix|patch|compil|ast|sintaxe|erro|crash|deadlock)\w*", re.IGNORECASE),
            "CODE_REPAIR",
            ("healing", "repair", "compilation"),
        ),
        (
            re.compile(r"\b(previs|impact|predi|simula|estimat)\w*", re.IGNORECASE),
            "IMPACT_PREDICTION",
            ("prediction", "impact", "simulation"),
        ),
        (
            re.compile(r"\b(evid|comprov|valid|gate|finish|test|browser|fuzz)\w*", re.IGNORECASE),
            "EVIDENCE_VALIDATION",
            ("validation", "evidence", "finish_gate"),
        ),
        (
            re.compile(r"\b(replan|adapt|subdag|grafa|failover|alternat)\w*", re.IGNORECASE),
            "DYNAMIC_ADAPTATION",
            ("adaptation", "planning", "dag"),
        ),
        (
            re.compile(r"\b(endpoint|rest|crud|api|rotas?|servidor|backend|post|get|sse|stream|grpc|rpc)\w*", re.IGNORECASE),
            "BACKEND_API",
            ("backend", "api", "routing"),
        ),
        (
            re.compile(r"\b(persist|sqlite|db|banco|storage|tabela|salv|snapshot|wal)\w*", re.IGNORECASE),
            "PERSISTENCE",
            ("persistence", "database", "storage"),
        ),
        (
            re.compile(r"\b(dashboard|painel|kpi|métrica|grafic|telemetr|kanban|toast|ui|theme)\w*", re.IGNORECASE),
            "DASHBOARD_AND_METRICS",
            ("dashboard", "frontend", "ui"),
        ),
        (
            re.compile(r"\b(depend|pacote|pip|npm|versão|conflit|drift|poetry)\w*", re.IGNORECASE),
            "DEPENDENCY_MANAGEMENT",
            ("dependency", "package", "version"),
        ),
    ]

    @classmethod
    def normalize_intent(cls, text: str) -> tuple[str, list[str]]:
        """Returns canonical category and standard semantic tags."""
        if not text:
            return "GENERAL_EXECUTION", ["generic"]

        cleaned = re.sub(r"^(query|task|miss[aã]o|cen[aá]rio)\s*\d*\s*:\s*", "", text.strip(), flags=re.IGNORECASE)
        for pattern, category, cat_tags in cls.INTENT_MAP:
            if pattern.search(cleaned):
                return category, list(cat_tags)

        # Fallback category based on length / structure
        return "GENERAL_FEATURE", ["feature", "execution"]


class ExperienceSignatureExtractor:
    """Extracts a structured ExperienceSignature from runtime contexts."""

    @classmethod
    def extract_signature(
        cls,
        intent_text: str,
        requirements: list[dict[str, Any]],
        tasks: list[dict[str, Any]],
        observation: dict[str, Any],
        decision: str,
        technology: list[str],
        environment: str = "LOCAL",
        affected_architecture: Optional[list[str]] = None,
    ) -> ExperienceSignature:
        intent_cat, _ = IntentNormalizer.normalize_intent(intent_text)

        # Extract requirement types
        req_types = []
        for r in requirements:
            source = r.get("source", "USER_REQUIREMENT")
            req_types.append(source)
        if not req_types:
            req_types = ["USER_REQUIREMENT"]

        # Extract task categories
        task_cats = set()
        for t in tasks:
            action = t.get("action", t.get("type", "EXECUTE"))
            task_cats.add(str(action))
        if not task_cats:
            task_cats.add("CODE_MODIFICATION")

        # Failure diagnosis
        failure = observation.get("failure_class", observation.get("error_type", "NONE"))
        if not failure or failure == "":
            failure = "NONE"

        scope = "CROSS_MODULE" if len(tasks) > 3 or len(technology) > 2 else "MODULE"

        arch = affected_architecture or ["frontend", "backend"]

        return ExperienceSignature(
            intent_category=intent_cat,
            requirement_types=tuple(sorted(set(req_types))),
            affected_architecture=tuple(sorted(set(arch))),
            task_categories=tuple(sorted(task_cats)),
            observed_failure=str(failure),
            decision=str(decision),
            environment=environment,
            technology=tuple(sorted(set(technology))),
            scope=scope,
        )
