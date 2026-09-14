"""
JARVIS OS — Phase 44: Semantic Task Translator
Translates abstract intent / tasks into language-specific tasks with formal cross-language dependencies.

Principles:
- Producer tasks precede Consumer tasks (API task precedes Frontend integration task).
- Causal justification & contractual evidence are mandatory.
- If contracts are absent, translation is marked UNCERTAIN. Never guess.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import uuid
from typing import Any, Dict, List, Optional, Set

from agents.semantic_graph.adapters import SemanticAdapterRegistry
from agents.semantic_graph.contracts import ContractRegistry
from agents.semantic_graph.graph import CrossLanguageSemanticGraph
from agents.semantic_graph.models import (
    ConfidenceClass,
    SemanticNode,
    SemanticNodeType,
    SemanticRelationType,
    TranslatedTask,
    ValidationStatus,
)


class SemanticTaskTranslator:
    """Translates abstract, language-neutral tasks or features into cross-language execution DAGs."""

    def __init__(
        self,
        graph: CrossLanguageSemanticGraph,
        contracts: ContractRegistry,
        adapters: SemanticAdapterRegistry | None = None,
    ) -> None:
        self.graph = graph
        self.contracts = contracts
        self.adapters = adapters or SemanticAdapterRegistry()

    def translate_feature_intent(
        self,
        intent_description: str,
        target_architecture_node_id: str,
    ) -> list[TranslatedTask]:
        """Translates a high-level intent tied to an architecture node into coordinated cross-language tasks.
        
        Example:
        Search Capability ->
          1. Persistence task: Create database query & model index
          2. Backend task: Implement FastAPI search endpoint (depends on Persistence task)
          3. API contract task: Define /users/search OpenAPI schema
          4. Frontend task: Implement React Search Component (depends on API contract & Backend task)
          5. Test task: Unit & Integration tests for API
          6. Browser task: Playwright browser verification
        """
        arch_node = self.graph.get_node(target_architecture_node_id)
        if not arch_node:
            # Fallback: create an uncertain task
            return [
                TranslatedTask(
                    task_id=f"tsk_trans_{uuid.uuid4().hex[:8]}",
                    source_task=intent_description,
                    target_domain="general",
                    affected_nodes=[],
                    dependencies=[],
                    translation_reason=f"Target architecture node '{target_architecture_node_id}' not found in semantic graph.",
                    evidence=[],
                    confidence_class=ConfidenceClass.UNCERTAIN,
                )
            ]

        # Find downstream implementation nodes
        downstream_ids = self.graph.get_downstream_nodes(target_architecture_node_id)
        downstream_nodes = [self.graph.get_node(nid) for nid in downstream_ids if self.graph.get_node(nid) is not None]

        tasks: list[TranslatedTask] = []
        task_id_by_domain: dict[str, str] = {}

        # 1. Persistence Tasks
        persistence_nodes = [n for n in downstream_nodes if n.node_type in (SemanticNodeType.PERSISTENCE_OPERATION, SemanticNodeType.DATA_MODEL)]
        if persistence_nodes:
            t_id = f"tsk_db_{uuid.uuid4().hex[:6]}"
            task_id_by_domain["persistence"] = t_id
            tasks.append(
                TranslatedTask(
                    task_id=t_id,
                    source_task=intent_description,
                    target_domain="persistence",
                    affected_nodes=[n.node_id for n in persistence_nodes],
                    dependencies=[],
                    translation_reason="Configure persistence models and schema queries for capability.",
                    evidence=[f"Architecture implements node {n.node_id}" for n in persistence_nodes],
                    confidence_class=ConfidenceClass.CONTRACTUAL,
                )
            )

        # 2. Backend Service Tasks
        backend_nodes = [n for n in downstream_nodes if n.node_type == SemanticNodeType.BACKEND_SERVICE]
        if backend_nodes:
            t_id = f"tsk_backend_{uuid.uuid4().hex[:6]}"
            task_id_by_domain["backend"] = t_id
            deps = [task_id_by_domain["persistence"]] if "persistence" in task_id_by_domain else []
            tasks.append(
                TranslatedTask(
                    task_id=t_id,
                    source_task=intent_description,
                    target_domain="backend",
                    affected_nodes=[n.node_id for n in backend_nodes],
                    dependencies=deps,
                    translation_reason="Implement backend business logic and service handlers.",
                    evidence=[f"Backend service {n.node_id} ({n.ecosystem})" for n in backend_nodes],
                    confidence_class=ConfidenceClass.CONTRACTUAL,
                )
            )

        # 3. API Contract Tasks
        api_nodes = [n for n in downstream_nodes if n.node_type in (SemanticNodeType.API_CONTRACT, SemanticNodeType.API_ENDPOINT)]
        if api_nodes:
            t_id = f"tsk_api_{uuid.uuid4().hex[:6]}"
            task_id_by_domain["api"] = t_id
            deps = [task_id_by_domain["backend"]] if "backend" in task_id_by_domain else []
            tasks.append(
                TranslatedTask(
                    task_id=t_id,
                    source_task=intent_description,
                    target_domain="api",
                    affected_nodes=[n.node_id for n in api_nodes],
                    dependencies=deps,
                    translation_reason="Expose and validate formal OpenAPI contract for consumers.",
                    evidence=[f"Contract {n.node_id}" for n in api_nodes],
                    confidence_class=ConfidenceClass.CONTRACTUAL,
                )
            )

        # 4. Frontend Component Tasks
        frontend_nodes = [n for n in downstream_nodes if n.node_type == SemanticNodeType.FRONTEND_COMPONENT]
        if frontend_nodes:
            t_id = f"tsk_frontend_{uuid.uuid4().hex[:6]}"
            task_id_by_domain["frontend"] = t_id
            # Frontend strictly depends on API contract
            deps = []
            if "api" in task_id_by_domain:
                deps.append(task_id_by_domain["api"])
            elif "backend" in task_id_by_domain:
                deps.append(task_id_by_domain["backend"])

            # Verify if contract exists for frontend
            has_contract = any(
                len([e for e in self.graph.get_out_edges(fn.node_id) if e.relation_type == SemanticRelationType.CONSUMES]) > 0
                for fn in frontend_nodes
            )
            confidence = ConfidenceClass.CONTRACTUAL if has_contract else ConfidenceClass.UNCERTAIN

            tasks.append(
                TranslatedTask(
                    task_id=t_id,
                    source_task=intent_description,
                    target_domain="frontend",
                    affected_nodes=[n.node_id for n in frontend_nodes],
                    dependencies=deps,
                    translation_reason="Build user-facing UI component consuming typed API contracts.",
                    evidence=[f"Frontend component {n.node_id} ({n.ecosystem})" for n in frontend_nodes],
                    confidence_class=confidence,
                )
            )

        # 5. Testing Tasks
        test_nodes = [n for n in downstream_nodes if n.node_type == SemanticNodeType.TEST]
        if test_nodes:
            t_id = f"tsk_test_{uuid.uuid4().hex[:6]}"
            task_id_by_domain["testing"] = t_id
            deps = []
            if "backend" in task_id_by_domain:
                deps.append(task_id_by_domain["backend"])
            if "frontend" in task_id_by_domain:
                deps.append(task_id_by_domain["frontend"])

            tasks.append(
                TranslatedTask(
                    task_id=t_id,
                    source_task=intent_description,
                    target_domain="testing",
                    affected_nodes=[n.node_id for n in test_nodes],
                    dependencies=deps,
                    translation_reason="Execute unit and integration test assertions across components.",
                    evidence=[f"Test suite {n.node_id}" for n in test_nodes],
                    confidence_class=ConfidenceClass.CONTRACTUAL,
                )
            )

        # 6. Browser Verification Tasks
        browser_nodes = [n for n in downstream_nodes if n.node_type == SemanticNodeType.BROWSER_SCENARIO]
        if browser_nodes:
            t_id = f"tsk_browser_{uuid.uuid4().hex[:6]}"
            task_id_by_domain["browser"] = t_id
            deps = []
            if "frontend" in task_id_by_domain:
                deps.append(task_id_by_domain["frontend"])
            if "testing" in task_id_by_domain:
                deps.append(task_id_by_domain["testing"])

            tasks.append(
                TranslatedTask(
                    task_id=t_id,
                    source_task=intent_description,
                    target_domain="browser",
                    affected_nodes=[n.node_id for n in browser_nodes],
                    dependencies=deps,
                    translation_reason="Perform live end-to-end browser verification on Microsoft Edge.",
                    evidence=[f"Browser scenario {n.node_id}" for n in browser_nodes],
                    confidence_class=ConfidenceClass.CONTRACTUAL,
                )
            )

        return tasks

    def translate_task_dependency(
        self,
        frontend_task: TranslatedTask,
        api_task: TranslatedTask,
    ) -> tuple[bool, str]:
        """Enforces that frontend task depends on API task, never the reverse."""
        if frontend_task.target_domain == "frontend" and api_task.target_domain in ("api", "backend"):
            if api_task.task_id not in frontend_task.dependencies:
                frontend_task.dependencies.append(api_task.task_id)
            return True, f"Frontend task '{frontend_task.task_id}' correctly depends on API task '{api_task.task_id}'."

        if frontend_task.target_domain in ("api", "backend") and api_task.target_domain == "frontend":
            return False, "INVALID DEPENDENCY DIRECTION: API/Backend cannot depend on downstream Frontend task."

        return True, "Valid dependency configuration."
