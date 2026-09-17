"""
JARVIS OS — Phase 54: Repair Candidate Generator
Generates competing candidate repair strategies for a verified root cause hypothesis.
"""

from __future__ import annotations

from typing import List

from agents.verified_repair.impact import PatchImpactAnalyzer
from agents.verified_repair.minimality import PatchMinimalityEvaluator
from agents.verified_repair.models import (
    RepairCandidate,
    RootCauseCategory,
    RootCauseHypothesis,
    compute_deterministic_hash,
)
from agents.verified_repair.synthesizer import RepairCodeSynthesizer


class RepairCandidateGenerator:
    """
    Generates multiple plausible repair candidates for a given root cause hypothesis.
    """

    def __init__(self) -> None:
        self.synthesizer = RepairCodeSynthesizer()
        self.impact_analyzer = PatchImpactAnalyzer()
        self.minimality_evaluator = PatchMinimalityEvaluator()

    def generate_candidates(
        self,
        hypothesis: RootCauseHypothesis,
        workspace_dir: str,
    ) -> List[RepairCandidate]:
        candidates: List[RepairCandidate] = []

        if hypothesis.category == RootCauseCategory.RUNTIME_SCOPE_ERROR:
            strategies = [
                ("DECLARATIVE_EXPRESS_BOILERPLATE", 0.95, 0.10, "Injetar instanciação e listener do framework Express"),
                ("MODULAR_APP_IMPORT", 0.75, 0.25, "Importar módulo de aplicação pré-existente"),
                ("ARCHITECTURAL_MOCK_STUB", 0.50, 0.65, "Substituir chamadas por mock global em memória"),
            ]
        elif hypothesis.category == RootCauseCategory.MISSING_IMPORT:
            strategies = [
                ("INJECT_CANONICAL_REQUIRE", 0.95, 0.05, "Injetar require canónico no cabeçalho do ficheiro"),
                ("DYNAMIC_LAZY_IMPORT", 0.70, 0.20, "Carregar biblioteca dinamicamente no momento do uso"),
            ]
        elif hypothesis.category == RootCauseCategory.PORT_CONFLICT:
            strategies = [
                ("DYNAMIC_PORT_FALLBACK", 0.95, 0.08, "Usar process.env.PORT com porta livre de fallback"),
            ]
        elif hypothesis.category == RootCauseCategory.MISSING_DEPENDENCY:
            strategies = [
                ("ADD_PACKAGE_DEPENDENCY", 0.90, 0.15, "Adicionar dependência ao package.json"),
            ]
        else:
            strategies = [
                ("GENERIC_SAFE_STUB", 0.50, 0.40, "Inserir stub de salvaguarda padrão"),
            ]

        for strat_name, conf, risk, effect in strategies:
            patches = self.synthesizer.synthesize_patches(hypothesis, workspace_dir, strat_name)
            files = [p.relative_path for p in patches]
            impact = self.impact_analyzer.analyze_patch_impact(patches, hypothesis.category.value, workspace_dir)
            minimality = self.minimality_evaluator.evaluate_minimality(patches)

            repair_id = compute_deterministic_hash(
                {"cause": hypothesis.cause_id, "strat": strat_name, "files": files},
                prefix="rep_cand_",
            )

            rollback_plan = {
                "snapshots": {p.relative_path: p.original_content for p in patches},
                "strategy": strat_name,
            }

            candidate = RepairCandidate(
                repair_id=repair_id,
                cause_id=hypothesis.cause_id,
                strategy_name=strat_name,
                files=files,
                patches=patches,
                expected_effect=effect,
                risk=risk,
                confidence=conf,
                predicted_impact=impact,
                rollback_plan=rollback_plan,
                provenance={"source_cause": hypothesis.cause_id, "strategy": strat_name},
                minimality=minimality,
            )
            candidates.append(candidate)

        return candidates
