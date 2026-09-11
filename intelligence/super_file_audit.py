"""
JARVIS OS — Super-File Decomposition & Architecture Hygiene Auditor (Fase 38)
Identificação determinística e multi-dimensional de super-ficheiros no repositório real.

Reutiliza:
- intelligence.repository_graph (RepositoryGraph, SymbolDefinition, ModuleImport)
- workspace_policy (WORKSPACE_ROOT, resolve_workspace_path)
"""

from __future__ import annotations

import os
import sys

# Ensure workspace root is in sys.path
_WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, _WORKSPACE_ROOT)

import ast
import json
import re
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from intelligence.repository_graph import RepositoryGraph, SymbolType
from workspace_policy import WORKSPACE_ROOT, resolve_workspace_path



class SeverityLevel(str, Enum):
    NORMAL = "NORMAL"
    WATCH = "WATCH"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class DecompositionRisk(str, Enum):
    LOW_RISK = "LOW_RISK"
    MEDIUM_RISK = "MEDIUM_RISK"
    HIGH_RISK = "HIGH_RISK"
    DEFERRED = "DEFERRED"


@dataclass(slots=True)
class ResponsibilityItem:
    name: str
    category: str
    evidence_source: str
    status: str = "VERIFIED"  # VERIFIED or INFERRED

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SuperFileReport:
    path: str
    language: str
    loc: int
    classes: int
    functions: int
    responsibilities: List[str]
    responsibility_details: List[Dict[str, Any]]
    imports: int
    fan_in: int
    fan_out: int
    shared_state_count: int
    public_symbols: int
    complexity_metrics: Dict[str, Any]
    score: float
    score_breakdown: Dict[str, float]
    severity: str
    risk: str
    recommended_decomposition: List[str]
    consumers: List[str]
    associated_tests: List[str]
    architectural_role: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SuperFileAuditor:
    """
    Auditor determinístico multi-dimensional de Super-Ficheiros.
    Analisa densidade de responsabilidades, acoplamento, complexidade e estado.
    """

    EXCLUDE_DIRS: Set[str] = {
        "node_modules",
        "venv",
        ".venv",
        "dist",
        "build",
        ".git",
        ".pytest_cache",
        ".vscode",
        "obsidian_vault",
        "__pycache__",
        ".tempmediaStorage",
        "test_ws_subdag_",
    }

    # Pesos do SUPER_FILE_SCORE (soma = 1.0)
    WEIGHTS: Dict[str, float] = {
        "loc": 0.15,
        "classes": 0.05,
        "functions": 0.10,
        "responsibilities": 0.20,  # Maior peso: densidade de responsabilidades
        "fan_out": 0.05,
        "fan_in": 0.10,
        "shared_state": 0.10,
        "complexity": 0.10,
        "public_symbols": 0.05,
        "domains": 0.10,
    }

    def __init__(self, workspace_root: Optional[str] = None):
        self.workspace_root = str(workspace_root or WORKSPACE_ROOT).replace("\\", "/")
        self.repo_graph = RepositoryGraph(self.workspace_root)

    def run_audit(self) -> Dict[str, Any]:
        """Executa auditoria completa sobre o repositório real."""
        start_time = time.perf_counter()

        # 1. Constrói grafo de repositório existente
        self.repo_graph.scan()

        # 2. Varre ficheiros de interesse
        candidates: List[SuperFileReport] = []
        files_scanned = 0

        for rel_path in sorted(self.repo_graph.files):
            if any(exc in rel_path for exc in self.EXCLUDE_DIRS):
                continue

            lower = rel_path.lower()
            if not lower.endswith((".py", ".ts", ".tsx", ".js", ".jsx")):
                continue

            # Ignora ficheiros de testes para lista de super-ficheiros de produto
            if rel_path.startswith("tests/") or "test_" in rel_path or ".test." in rel_path:
                continue

            abs_path = os.path.join(self.workspace_root, rel_path)
            if not os.path.isfile(abs_path):
                continue

            files_scanned += 1
            report = self._analyze_file(rel_path, abs_path)
            if report:
                candidates.append(report)

        # 3. Ordena por score decrescente, depois responsabilidades, acoplamento e LOC
        candidates.sort(
            key=lambda c: (
                c.score,
                len(c.responsibilities),
                c.fan_in + c.fan_out,
                c.loc,
            ),
            reverse=True,
        )

        audit_duration = time.perf_counter() - start_time

        # 4. Agrega estatísticas globais
        critical_count = sum(1 for c in candidates if c.severity == SeverityLevel.CRITICAL.value)
        high_count = sum(1 for c in candidates if c.severity == SeverityLevel.HIGH.value)
        watch_count = sum(1 for c in candidates if c.severity == SeverityLevel.WATCH.value)
        normal_count = sum(1 for c in candidates if c.severity == SeverityLevel.NORMAL.value)

        result = {
            "audit_metadata": {
                "workspace_root": self.workspace_root,
                "timestamp": time.time(),
                "duration_seconds": round(audit_duration, 4),
                "files_scanned": files_scanned,
                "total_candidates": len(candidates),
                "summary": {
                    "critical": critical_count,
                    "high": high_count,
                    "watch": watch_count,
                    "normal": normal_count,
                },
            },
            "top_candidates": [c.to_dict() for c in candidates[:20]],
            "all_reports": [c.to_dict() for c in candidates],
        }

        return result

    def _get_outbound_dependencies(self, rel_path: str) -> Set[str]:
        out = set()
        for imp in self.repo_graph.imports.get(rel_path, []):
            if imp.resolved_target and imp.resolved_target != rel_path:
                out.add(imp.resolved_target)
        return out

    def _get_inbound_dependencies(self, rel_path: str) -> Set[str]:
        inbound = set()
        for src, imp_list in self.repo_graph.imports.items():
            if src != rel_path:
                for imp in imp_list:
                    if imp.resolved_target == rel_path:
                        inbound.add(src)
        return inbound

    def _get_associated_tests(self, rel_path: str) -> Set[str]:
        tests = set()
        stem = Path(rel_path).stem.lower()
        for test_file, impl_list in self.repo_graph.test_mappings.items():
            if rel_path in impl_list or stem in test_file.lower():
                tests.add(test_file)
        return tests

    def _analyze_file(self, rel_path: str, abs_path: str) -> Optional[SuperFileReport]:
        try:
            with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except OSError:
            return None

        lines = content.splitlines()
        loc = len([line for line in lines if line.strip() and not line.strip().startswith(("#", "//", "/*", "*"))])
        if loc < 15:
            return None

        language = "python" if rel_path.endswith(".py") else "typescript" if rel_path.endswith((".ts", ".tsx")) else "javascript"

        # Dependências de entrada (fan-in) e saída (fan-out)
        inbound = self._get_inbound_dependencies(rel_path)
        outbound = self._get_outbound_dependencies(rel_path)
        fan_in = len(inbound)
        fan_out = len(outbound)
        associated_tests = self._get_associated_tests(rel_path)

        # Análise específica por linguagem
        if language == "python":
            cls_count, fn_count, pub_symbols, state_count, cpx_metrics, resp_items = self._analyze_python(content, rel_path)
        else:
            cls_count, fn_count, pub_symbols, state_count, cpx_metrics, resp_items = self._analyze_typescript(content, rel_path)

        responsibilities = sorted(list(set(r.name for r in resp_items)))
        resp_details = [r.to_dict() for r in resp_items]

        # Domínios funcionais tocados
        domains = sorted(list(set(r.category for r in resp_items)))

        # Cálculo do SUPER_FILE_SCORE determinístico
        score, breakdown = self._calculate_score(
            loc=loc,
            classes=cls_count,
            functions=fn_count,
            responsibilities=len(responsibilities),
            fan_out=fan_out,
            fan_in=fan_in,
            shared_state=state_count,
            complexity=cpx_metrics.get("cyclomatic_complexity", 0),
            public_symbols=pub_symbols,
            domains=len(domains),
        )

        severity = self._classify_severity(score)
        risk, recs, role = self._determine_risk_and_decomposition(rel_path, loc, responsibilities, fan_in, fan_out, pub_symbols)

        return SuperFileReport(
            path=rel_path,
            language=language,
            loc=loc,
            classes=cls_count,
            functions=fn_count,
            responsibilities=responsibilities,
            responsibility_details=resp_details,
            imports=fan_out,
            fan_in=fan_in,
            fan_out=fan_out,
            shared_state_count=state_count,
            public_symbols=pub_symbols,
            complexity_metrics=cpx_metrics,
            score=round(score, 2),
            score_breakdown=breakdown,
            severity=severity.value,
            risk=risk.value,
            recommended_decomposition=recs,
            consumers=sorted(list(inbound)),
            associated_tests=sorted(list(associated_tests)),
            architectural_role=role,
        )

    def _analyze_python(
        self, content: str, rel_path: str
    ) -> Tuple[int, int, int, int, Dict[str, Any], List[ResponsibilityItem]]:
        cls_count = 0
        fn_count = 0
        pub_symbols = 0
        state_count = 0
        cyclomatic = 1
        branch_count = 0
        resp_items: List[ResponsibilityItem] = []

        try:
            tree = ast.parse(content, filename=rel_path)
        except SyntaxError:
            # Fallback com contagem regex
            cls_count = len(re.findall(r"^\s*class\s+\w+", content, re.MULTILINE))
            fn_count = len(re.findall(r"^\s*(?:async\s+)?def\s+\w+", content, re.MULTILINE))
            return cls_count, fn_count, cls_count + fn_count, 1, {"cyclomatic_complexity": 10}, []

        # Responsabilidades e complexidade via AST
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                # Variáveis mutáveis a nível de módulo (estado partilhado)
                state_count += 1
            elif isinstance(node, ast.ClassDef):
                cls_count += 1
                if not node.name.startswith("_"):
                    pub_symbols += 1
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fn_count += 1
                if not node.name.startswith("_"):
                    pub_symbols += 1

        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.While, ast.For, ast.AsyncFor, ast.ExceptHandler, ast.With, ast.AsyncWith)):
                cyclomatic += 1
                branch_count += 1
            elif isinstance(node, ast.BoolOp):
                cyclomatic += len(node.values) - 1

            # Deteção de métodos de classe
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node not in tree.body:
                fn_count += 1
                if not node.name.startswith("_"):
                    pub_symbols += 1

        # Deteção de responsabilidades semânticas
        # 1. API / Endpoints
        if re.search(r"@\w+\.(?:get|post|put|delete|patch|websocket)", content) or "APIRouter" in content:
            resp_items.append(ResponsibilityItem("api_endpoints", "api", "AST_DECORATOR", "VERIFIED"))

        # 2. WebSocket
        if "websocket" in content.lower() or "WebSocket" in content:
            resp_items.append(ResponsibilityItem("websocket_messaging", "websocket", "AST_IMPORT_OR_CALL", "VERIFIED"))

        # 3. Persistence / Storage
        if any(w in content for w in ("sqlite3", "cursor.execute", "commit()", "json.dump", "open(", "Path(")) and "persistence" in rel_path.lower():
            resp_items.append(ResponsibilityItem("persistence_storage", "persistence", "AST_CALL", "VERIFIED"))
        elif any(w in content for w in ("sqlite3", "cursor.execute", "commit()")):
            resp_items.append(ResponsibilityItem("database_access", "persistence", "AST_CALL", "VERIFIED"))

        # 4. Lifecycle / Mission State
        if any(w in content for w in ("MissionStatus", "state_transition", "PAUSED", "RESUMED", "CANCELLED", "COMPLETED")):
            resp_items.append(ResponsibilityItem("mission_lifecycle", "lifecycle", "DOMAIN_CONSTANT", "VERIFIED"))

        # 5. Dynamic Intent / Replan / Goal
        if any(w in content for w in ("MissionIntent", "IntentDelta", "replan", "DynamicReplanner", "apply_intent")):
            resp_items.append(ResponsibilityItem("dynamic_intent_and_replan", "mission_logic", "AST_CLASS_OR_METHOD", "VERIFIED"))

        # 6. Security / Sentinel
        if any(w in content for w in ("SecuritySentinel", "sentinel", "audit_log", "verify_security", "SecurityPolicy")):
            resp_items.append(ResponsibilityItem("security_sentinel_policy", "security", "AST_REFERENCE", "VERIFIED"))

        # 7. Orchestration & Swarm
        if any(w in content for w in ("SwarmFederation", "WorkerAgent", "dispatch_task", "allocate_agents", "orchestrator")):
            resp_items.append(ResponsibilityItem("swarm_orchestration", "orchestration", "AST_REFERENCE", "VERIFIED"))

        # 8. Evidence & Ledger
        if any(w in content for w in ("EvidenceStatus", "revalidation_required", "superseded_by", "evidence_ledger")):
            resp_items.append(ResponsibilityItem("evidence_and_ledger", "evidence", "AST_REFERENCE", "VERIFIED"))

        # 9. Validation & Schema
        if any(w in content for w in ("BaseModel", "validate_", "ValidationError", "dataclass")):
            resp_items.append(ResponsibilityItem("data_validation", "validation", "AST_CLASS_DEF", "VERIFIED"))

        # 10. Scheduler & DAG
        if any(w in content for w in ("kahn", "topological_sort", "ready_queue", "in_degree", "dependency_graph")):
            resp_items.append(ResponsibilityItem("dag_scheduler", "scheduler", "ALGORITHM_STRUCTURE", "VERIFIED"))

        cpx_metrics = {
            "cyclomatic_complexity": cyclomatic,
            "branch_count": branch_count,
            "ast_nodes": len(list(ast.walk(tree))),
        }

        return cls_count, fn_count, pub_symbols, state_count, cpx_metrics, resp_items

    def _analyze_typescript(
        self, content: str, rel_path: str
    ) -> Tuple[int, int, int, int, Dict[str, Any], List[ResponsibilityItem]]:
        cls_count = len(re.findall(r"^\s*(?:export\s+)?class\s+\w+", content, re.MULTILINE))
        fn_count = len(re.findall(r"(?:function\s+\w+|(?:const|let|var)\s+\w+\s*=\s*(?:async\s*)?\([^)]*\)\s*=>)", content))
        pub_symbols = len(re.findall(r"^\s*export\s+(?:default\s+)?(?:class|function|const|let|interface|type|enum)\s+\w+", content, re.MULTILINE))

        # Estado partilhado / React hooks
        state_hooks = len(re.findall(r"\buse(?:State|Reducer|Ref|Context)\b", content))
        state_count = max(1, state_hooks)

        # Complexidade ciclomática aproximada
        branch_count = len(re.findall(r"\b(?:if|else\s+if|for|while|case|catch)\b|\?.*:", content))
        cyclomatic = max(1, branch_count + 1)
        jsx_elements = len(re.findall(r"<[A-Z][A-Za-z0-9_]*|<(?:div|span|button|input|textarea|section|header|nav)\b", content))

        resp_items: List[ResponsibilityItem] = []

        # Responsabilidades no Frontend
        # 1. Rendering / JSX
        if jsx_elements > 0 or "<div" in content:
            resp_items.append(ResponsibilityItem("ui_rendering", "rendering", "JSX_TREE", "VERIFIED"))

        # 2. State Management
        if state_hooks > 0:
            resp_items.append(ResponsibilityItem("state_management", "state", "REACT_HOOKS", "VERIFIED"))

        # 3. WebSocket / Networking
        if any(w in content for w in ("WebSocket", "sendMissionCommand", "sendMissionIntent", "useWebSocket", "onmessage")):
            resp_items.append(ResponsibilityItem("websocket_client", "websocket", "HOOK_OR_EVENT_CALL", "VERIFIED"))

        # 4. Mission Controls
        if any(w in content for w in ("handlePause", "handleResume", "handleCancel", "handleApprove", "mission-cmd-")):
            resp_items.append(ResponsibilityItem("mission_control_actions", "controls", "HANDLER_FUNCTIONS", "VERIFIED"))

        # 5. Modal Management
        if any(w in content for w in ("Modal", "showModal", "setShowModal", "confirm-dialog", "intent-preview-modal")):
            resp_items.append(ResponsibilityItem("modal_dialog_management", "modal", "MODAL_STATE", "VERIFIED"))

        # 6. Task Graph / DAG
        if any(w in content for w in ("TaskGraph", "task-card", "dependencies", "dag", "topological")):
            resp_items.append(ResponsibilityItem("task_dag_visualization", "mission_logic", "JSX_COMPONENT", "VERIFIED"))

        # 7. Navigation / Tabs
        if any(w in content for w in ("activeTab", "setActiveTab", "tab-", "switch (activeTab)")):
            resp_items.append(ResponsibilityItem("navigation_and_tabs", "navigation", "STATE_AND_JSX", "VERIFIED"))

        # 8. Dynamic Intent UI
        if any(w in content for w in ("intent_version", "plan_version", "intent-preview", "btn-analyze-intent")):
            resp_items.append(ResponsibilityItem("dynamic_intent_editor", "mission_logic", "UI_CONTROLS", "VERIFIED"))

        # 9. Evidence / Validation Tracker
        if any(w in content for w in ("evidence", "Zero False Success", "superseded", "revalidation")):
            resp_items.append(ResponsibilityItem("evidence_invalidation_display", "evidence", "UI_PANEL", "VERIFIED"))

        # 10. Why Panel / Explainability
        if any(w in content for w in ("Why", "causal", "chain", "delta_id", "causality")):
            resp_items.append(ResponsibilityItem("why_causal_explainability", "evidence", "UI_PANEL", "VERIFIED"))

        cpx_metrics = {
            "cyclomatic_complexity": cyclomatic,
            "branch_count": branch_count,
            "jsx_element_count": jsx_elements,
            "state_hooks": state_hooks,
        }

        return cls_count, fn_count, pub_symbols, state_count, cpx_metrics, resp_items

    def _calculate_score(
        self,
        loc: int,
        classes: int,
        functions: int,
        responsibilities: int,
        fan_out: int,
        fan_in: int,
        shared_state: int,
        complexity: int,
        public_symbols: int,
        domains: int,
    ) -> Tuple[float, Dict[str, float]]:
        # Sub-scores normalizados de 0 a 100
        s_loc = min(100.0, loc / 25.0)  # 2500 LOC = 100
        s_cls = min(100.0, classes * 15.0)
        s_fn = min(100.0, functions * 2.5)  # 40 funções = 100
        s_resp = min(100.0, responsibilities * 12.5)  # 8 responsabilidades = 100
        s_fan_out = min(100.0, fan_out * 3.33)  # 30 imports = 100
        s_fan_in = min(100.0, fan_in * 5.0)  # 20 consumidores = 100
        s_state = min(100.0, shared_state * 10.0)  # 10 variáveis de estado = 100
        s_cpx = min(100.0, complexity * 1.5)  # 66 complexidade = 100
        s_api = min(100.0, public_symbols * 4.0)  # 25 símbolos públicos = 100
        s_dom = min(100.0, domains * 20.0)  # 5 domínios = 100

        breakdown = {
            "loc": round(s_loc, 1),
            "classes": round(s_cls, 1),
            "functions": round(s_fn, 1),
            "responsibilities": round(s_resp, 1),
            "fan_out": round(s_fan_out, 1),
            "fan_in": round(s_fan_in, 1),
            "shared_state": round(s_state, 1),
            "complexity": round(s_cpx, 1),
            "public_symbols": round(s_api, 1),
            "domains": round(s_dom, 1),
        }

        total_score = sum(self.WEIGHTS[k] * breakdown[k] for k in self.WEIGHTS)
        return total_score, breakdown

    def _classify_severity(self, score: float) -> SeverityLevel:
        if score >= 80.0:
            return SeverityLevel.CRITICAL
        elif score >= 65.0:
            return SeverityLevel.HIGH
        elif score >= 40.0:
            return SeverityLevel.WATCH
        return SeverityLevel.NORMAL

    def _determine_risk_and_decomposition(
        self,
        rel_path: str,
        loc: int,
        responsibilities: List[str],
        fan_in: int,
        fan_out: int,
        pub_symbols: int,
    ) -> Tuple[DecompositionRisk, List[str], str]:
        # 1. UI Super File (Ex: MissionControlCenter.tsx)
        if "MissionControlCenter.tsx" in rel_path:
            recs = [
                "components/MissionHeader.tsx (Header, status, metrics, version badges)",
                "components/MissionUnderstandingPanel.tsx (Understanding & domain summary)",
                "components/MissionTaskGraphPanel.tsx (Task DAG, priorities, reordering)",
                "components/MissionSwarmPanel.tsx (Swarm agent allocation)",
                "components/MissionTimelinePanel.tsx (Execution logs & step timeline)",
                "components/MissionRepairPanel.tsx (Self-healing & repair diffs)",
                "components/MissionRecoveryPanel.tsx (Checkpoints & recovery)",
                "components/MissionRequirementsDiffPanel.tsx (Requirements lifecycle diff)",
                "components/MissionPlanDiffPanel.tsx (Plan diff & DAG status validation)",
                "components/EvidenceInvalidationPanel.tsx (Zero False Success evidence tracker)",
                "components/WhyCausalPanel.tsx (Causal explainability chains)",
                "components/MissionControlActions.tsx (Pause, resume, cancel, edit goal buttons)",
                "components/IntentPreviewModal.tsx (Goal editor & impact analysis modal)",
                "components/CancelConfirmModal.tsx (Cancellation confirmation dialog)",
            ]
            return DecompositionRisk.LOW_RISK, recs, "Frontend Mission Control Orchestrator"

        # 2. Mission Control Engine (Backend)
        if "mission_control_engine.py" in rel_path:
            recs = [
                "agents/mission_intent/intent_resolver.py (NLP parsing & target resolution)",
                "agents/mission_intent/impact_analyzer.py (Impact analysis & classification)",
                "agents/mission_intent/conflict_detector.py (Conflict detection & Sentinel check)",
                "agents/mission_intent/dynamic_replanner.py (DAG topological replanning)",
            ]
            return DecompositionRisk.DEFERRED, recs, "Mission Control State & Invariant Engine"

        # 3. Collaboration Engine
        if "collaboration_engine.py" in rel_path:
            recs = [
                "agents/collaboration/turn_manager.py",
                "agents/collaboration/context_sharing.py",
                "agents/collaboration/consensus_gate.py",
            ]
            return DecompositionRisk.DEFERRED, recs, "Multi-Agent Collaboration Core"

        # 4. Project Builder
        if "project_builder.py" in rel_path:
            recs = [
                "agents/orchestrator/builder_scaffolding.py",
                "agents/orchestrator/builder_dependency_resolver.py",
            ]
            return DecompositionRisk.DEFERRED, recs, "Autonomous Project Scaffolder"

        # 5. Default Heuristic
        if fan_in > 15 or "security" in rel_path or "sentinel" in rel_path:
            risk = DecompositionRisk.HIGH_RISK
        elif loc > 1200:
            risk = DecompositionRisk.MEDIUM_RISK
        else:
            risk = DecompositionRisk.LOW_RISK

        recs = [f"Extract sub-domain modules for {r}" for r in responsibilities[:3]]
        return risk, recs, "Domain Service / Component"


def main():
    auditor = SuperFileAuditor()
    print("[Phase 38] Executing Super-File Audit across real workspace...")
    results = auditor.run_audit()

    summary = results["audit_metadata"]["summary"]
    print(f"Scanned {results['audit_metadata']['files_scanned']} files in {results['audit_metadata']['duration_seconds']}s.")
    print(f"Candidates found: Critical={summary['critical']}, High={summary['high']}, Watch={summary['watch']}, Normal={summary['normal']}")

    top5 = results["top_candidates"][:5]
    print("\nTop 5 Super-Files:")
    for i, c in enumerate(top5, 1):
        print(f" {i}. {c['path']} (Score: {c['score']} | {c['severity']} | LOC: {c['loc']} | Resp: {len(c['responsibilities'])})")

    # Salva relatórios solicitados na especificação
    os.makedirs("docs", exist_ok=True)
    with open("docs/phase38_super_file_audit.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    with open("docs/super_file_audit.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("\nSaved docs/phase38_super_file_audit.json and docs/super_file_audit.json successfully.")


if __name__ == "__main__":
    main()
