"""
JARVIS OS — Real Repository Coding Trial Agent (Fase 10.2)
Agente de avaliação autónoma de repositórios reais sem fornecimento prévio da árvore de ficheiros (Zero Benchmark Leakage).
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
import json
import os
import re
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from intelligence.autonomous_repair_loop import AutonomousRepairLoop, AutonomousRepairReport
from intelligence.build_pipeline import DeterministicBuildPipeline, PipelineReport, StageStatus
from intelligence.repository_graph import BlastRadius, RepositoryGraph


@dataclass(slots=True)
class DiscoveredRepositoryModel:
    """Modelo completo descoberto autonomamente sobre a estrutura do repositório."""
    repository_path: str
    languages: List[str] = field(default_factory=list)
    frameworks: List[str] = field(default_factory=list)
    package_manager: str = "unknown"
    build_system: str = "none"
    test_system: str = "none"
    entrypoints: List[str] = field(default_factory=list)
    configs: List[str] = field(default_factory=list)
    is_monorepo: bool = False
    monorepo_packages: List[str] = field(default_factory=list)
    path_aliases: Dict[str, List[str]] = field(default_factory=dict)
    total_files: int = 0
    total_symbols: int = 0
    total_endpoints: int = 0
    total_tests: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TrialTaskPlan:
    """Plano de execução e decomposição autónoma da tarefa."""
    task_prompt: str
    criteria: List[str]
    detected_intent: str
    selected_files: List[str]
    selected_symbols: List[str]
    blast_radius: BlastRadius
    relevance_precision: float = 1.0
    relevance_recall: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TrialExecutionResult:
    """Resultado detalhado da execução de uma tarefa de teste real."""
    task_id: str
    repository_name: str
    discovery_model: DiscoveredRepositoryModel
    plan: TrialTaskPlan
    modified_files: List[str]
    pipeline_report: PipelineReport
    repair_report: Optional[AutonomousRepairReport] = None
    success: bool = False
    duration_seconds: float = 0.0
    relevance_precision: float = 1.0
    relevance_recall: float = 1.0
    wrong_file_rate: float = 0.0
    unrelated_change_rate: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class RealRepositoryCodingTrialAgent:
    """Agente executor de testes de programação sobre repositórios reais sem dicas externas."""

    def __init__(self, workspace_root: str) -> None:
        self.workspace_root = os.path.realpath(os.path.abspath(workspace_root))
        self.graph = RepositoryGraph(self.workspace_root)

    def discover_repository(self) -> DiscoveredRepositoryModel:
        """Descobre autonomamente a arquitetura, linguagens, frameworks e configurações do projeto."""
        self.graph.scan()

        languages: Set[str] = set()
        frameworks: Set[str] = set()
        pkg_manager = "unknown"
        build_sys = "none"
        test_sys = "none"

        for f in self.graph.files:
            lower = f.lower()
            if lower.endswith(".py"):
                languages.add("Python")
            elif lower.endswith((".ts", ".tsx")):
                languages.add("TypeScript")
            elif lower.endswith((".js", ".jsx")):
                languages.add("JavaScript")
            elif lower.endswith(".html"):
                languages.add("HTML")
            elif lower.endswith(".css"):
                languages.add("CSS")

            # Frameworks detection
            if "fastapi" in lower or lower.endswith("app.py") or lower.endswith("main.py"):
                if any(ep.framework == "fastapi" for ep in self.graph.endpoints):
                    frameworks.add("FastAPI")
            if "react" in lower or lower.endswith((".tsx", ".jsx")):
                frameworks.add("React")
            if "next" in lower or "app/api" in lower or "app/page" in lower or "pages/" in lower:
                frameworks.add("Next.js")
            if "tailwind" in lower:
                frameworks.add("TailwindCSS")
            if "zustand" in lower or "redux" in lower:
                frameworks.add("State Management")

            # Build and Test system detection
            if lower.endswith("pytest.ini") or "test" in lower and lower.endswith(".py"):
                test_sys = "pytest"
            if lower.endswith(("vitest.config.ts", "jest.config.js")):
                test_sys = "vitest" if "vitest" in lower else "jest"
            if lower.endswith("vite.config.ts"):
                build_sys = "vite"
            if lower.endswith("package.json"):
                pkg_manager = "npm"

        # Monorepo and Aliases
        is_monorepo = len(self.graph.monorepo_packages) > 0
        mono_pkgs = list(self.graph.monorepo_packages.keys())

        aliases: Dict[str, List[str]] = {}
        for ts_cfg in self.graph.tsconfigs.values():
            for k, v in ts_cfg.paths.items():
                aliases[k] = v

        total_symbols = sum(len(syms) for syms in self.graph.symbols.values())
        total_tests = len(self.graph.test_mappings)

        return DiscoveredRepositoryModel(
            repository_path=self.workspace_root,
            languages=sorted(languages),
            frameworks=sorted(frameworks),
            package_manager=pkg_manager,
            build_system=build_sys,
            test_system=test_sys,
            entrypoints=self.graph.entrypoints,
            configs=self.graph.configs,
            is_monorepo=is_monorepo,
            monorepo_packages=mono_pkgs,
            path_aliases=aliases,
            total_files=len(self.graph.files),
            total_symbols=total_symbols,
            total_endpoints=len(self.graph.endpoints),
            total_tests=total_tests,
        )

    def select_relevant_artifacts(
        self,
        task_prompt: str,
        criteria: List[str],
    ) -> Tuple[List[str], List[str]]:
        """Seleciona ficheiros e símbolos relevantes a partir da intenção da tarefa sem listas prévias."""
        combined_text = f"{task_prompt} {' '.join(criteria)}".lower()
        words = set(re.findall(r"[a-zA-Z0-9_]{3,}", combined_text))

        selected_files: Set[str] = set()
        selected_symbols: Set[str] = set()

        # 1. Correspondência em nomes de símbolos
        for sym_name, sym_defs in self.graph.symbols.items():
            sym_lower = sym_name.lower()
            if any(w in sym_lower or sym_lower in w for w in words):
                selected_symbols.add(sym_name)
                for d in sym_defs:
                    selected_files.add(d.file_path)

        # 2. Correspondência em nomes de ficheiros
        for f in self.graph.files:
            f_lower = f.lower()
            stem = os.path.splitext(os.path.basename(f_lower))[0]
            if any(w == stem or w in f_lower for w in words):
                selected_files.add(f)

        # 3. Se nenhum ficheiro for encontrado, adiciona entrypoints como ponto de partida
        if not selected_files and self.graph.entrypoints:
            selected_files.update(self.graph.entrypoints[:2])

        return sorted(selected_files), sorted(selected_symbols)

    def execute_trial_task(
        self,
        task_id: str,
        task_prompt: str,
        criteria: List[str],
        expected_files: Optional[List[str]] = None,
        apply_change_fn: Optional[Callable[[], List[str]]] = None,
    ) -> TrialExecutionResult:
        """Executa o ciclo completo de teste e mede métricas reais sem vazamento de benchmark."""
        t0 = time.time()
        repo_name = os.path.basename(self.workspace_root)

        # 1. Descoberta
        discovery_model = self.discover_repository()

        # 2. Seleção de Relevância
        sel_files, sel_symbols = self.select_relevant_artifacts(task_prompt, criteria)
        blast = self.graph.compute_blast_radius(sel_files)

        # 3. Classificação de Intenção
        intent = "FEATURE_ADD"
        p_lower = task_prompt.lower()
        if "bug" in p_lower or "corrig" in p_lower or "fix" in p_lower or "error" in p_lower:
            intent = "BUG_FIX"
        elif "refactor" in p_lower or "reorgani" in p_lower:
            intent = "REFACTOR"
        elif "cross" in p_lower or "integrat" in p_lower or "shared" in p_lower:
            intent = "CROSS_FILE"

        # Cálculo de Precisão e Recall de Relevância
        if expected_files:
            expected_set = set(expected_files)
            selected_set = set(sel_files)
            true_positives = len(selected_set & expected_set)
            precision = round(true_positives / max(len(selected_set), 1), 2)
            recall = round(true_positives / max(len(expected_set), 1), 2)
        else:
            precision = 1.0
            recall = 1.0

        plan = TrialTaskPlan(
            task_prompt=task_prompt,
            criteria=criteria,
            detected_intent=intent,
            selected_files=sel_files,
            selected_symbols=sel_symbols,
            blast_radius=blast,
            relevance_precision=precision,
            relevance_recall=recall,
        )

        # 4. Aplicação das Modificações
        modified_files: List[str] = []
        if apply_change_fn:
            modified_files = apply_change_fn()

        # 5. Execução do Pipeline de Validação
        pipeline = DeterministicBuildPipeline(self.workspace_root)
        report = pipeline.run_pipeline()

        # 6. Se houver falha, aciona o Autonomous Repair Loop
        repair_report = None
        if report.overall_status == StageStatus.FAILED.value:
            repair_loop = AutonomousRepairLoop(self.workspace_root)
            repair_report = repair_loop.run_repair_cycle()
            if repair_report.success and repair_report.final_pipeline_report:
                report = repair_report.final_pipeline_report

        success = report.overall_status == StageStatus.PASSED.value

        # Cálculo de taxa de ficheiros errados e alterações irrelevantes
        wrong_files = 0
        unrelated_changes = 0
        if expected_files and modified_files:
            for mf in modified_files:
                if mf not in expected_files:
                    wrong_files += 1
                    unrelated_changes += 1

        wrong_rate = round(wrong_files / max(len(modified_files), 1), 2)
        unrelated_rate = round(unrelated_changes / max(len(modified_files), 1), 2)

        return TrialExecutionResult(
            task_id=task_id,
            repository_name=repo_name,
            discovery_model=discovery_model,
            plan=plan,
            modified_files=modified_files,
            pipeline_report=report,
            repair_report=repair_report,
            success=success,
            duration_seconds=round(time.time() - t0, 3),
            relevance_precision=precision,
            relevance_recall=recall,
            wrong_file_rate=wrong_rate,
            unrelated_change_rate=unrelated_rate,
        )
