"""
JARVIS OS — Phase 53: Universal Project Preflight & Runtime Failure Auto-Recovery
Safe Repair Planner: Generates surgical, non-destructive file patches with snapshotting
and reversible rollback lineage. Prohibits arbitrary code rewrites.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

from agents.project_preflight.confidence import RepairConfidenceEvaluator
from agents.project_preflight.models import (
    DiagnosticErrorClass,
    FilePatch,
    PreflightIssue,
    ProjectRuntimeProfile,
    RepairCategory,
    RepairConfidence,
    RepairPlan,
    RuntimeDiagnostic,
    compute_deterministic_hash,
)


class SafeRepairPlanner:
    """
    Creates surgical repair plans from diagnostics or preflight issues.
    Never overwrites files without an intact original snapshot.
    """

    def __init__(self) -> None:
        self.confidence_evaluator = RepairConfidenceEvaluator()

    def plan_repair(
        self,
        diagnostic: RuntimeDiagnostic,
        root_dir: str,
        profile: ProjectRuntimeProfile,
    ) -> Optional[RepairPlan]:
        if not diagnostic.file_path or not os.path.isfile(diagnostic.file_path):
            return None

        try:
            with open(diagnostic.file_path, "r", encoding="utf-8", errors="ignore") as f:
                original_content = f.read()
        except Exception:
            return None

        patches: List[FilePatch] = []
        rel_path = os.path.relpath(diagnostic.file_path, root_dir)
        category = RepairCategory.IMPORT_MISSING
        reason = ""
        expected = ""

        # Case 1: ReferenceError app
        if diagnostic.error_class == DiagnosticErrorClass.REFERENCE_ERROR and diagnostic.symbol == "app":
            category = RepairCategory.MIDDLEWARE_MISSING
            reason = "Instanciar aplicação Express e middlewares para resolver ReferenceError: app is not defined"
            expected = "Aplicação Express inicializada e rotas registadas sem ReferenceError"

            # Inject express setup at the top if not present
            header = (
                "const express = require('express');\n"
                "const app = express();\n"
                "const PORT = process.env.PORT || 3000;\n\n"
                "app.use(express.json());\n"
                "app.use(express.urlencoded({ extended: true }));\n"
            )
            footer = (
                "\n\n// Inicialização do servidor adicionada pelo JARVIS Safe Repair\n"
                "if (require.main === module) {\n"
                "    app.listen(PORT, () => console.log(`[JARVIS] Servidor ativo na porta ${PORT}`));\n"
                "}\n"
            )

            # Prepend header if not already containing express require
            patched = original_content
            if "require('express')" not in patched and 'require("express")' not in patched:
                patched = header + patched

            # Add footer if app.listen is missing
            if "app.listen" not in patched:
                patched = patched + footer

            patches.append(
                FilePatch(
                    relative_path=rel_path,
                    original_content=original_content,
                    patched_content=patched,
                    reason="Adição de imports do Express e inicialização do servidor",
                )
            )

        # Case 2: ReferenceError axios
        elif diagnostic.error_class == DiagnosticErrorClass.REFERENCE_ERROR and diagnostic.symbol == "axios":
            category = RepairCategory.IMPORT_MISSING
            reason = "Importar biblioteca axios para resolver ReferenceError: axios is not defined"
            expected = "Módulo axios disponível no escopo do arquivo"
            import_line = "const axios = require('axios');\n"
            patched = import_line + original_content
            patches.append(
                FilePatch(
                    relative_path=rel_path,
                    original_content=original_content,
                    patched_content=patched,
                    reason="Adição de importação do axios",
                )
            )

        # Case 3: Module not found (e.g. declare in package.json)
        elif diagnostic.error_class == DiagnosticErrorClass.MODULE_NOT_FOUND and diagnostic.symbol:
            category = RepairCategory.DEPENDENCY_MISSING
            reason = f"Declarar dependência '{diagnostic.symbol}' no package.json"
            expected = f"Dependência '{diagnostic.symbol}' registrada no manifesto"
            pkg_path = os.path.join(root_dir, "package.json")
            if os.path.isfile(pkg_path):
                try:
                    import json
                    with open(pkg_path, "r", encoding="utf-8") as pf:
                        pkg_json = json.load(pf)
                    deps = pkg_json.setdefault("dependencies", {})
                    deps[diagnostic.symbol] = "^1.0.0"
                    new_pkg_content = json.dumps(pkg_json, indent=2)
                    with open(pkg_path, "r", encoding="utf-8") as pf:
                        old_pkg_content = pf.read()
                    patches.append(
                        FilePatch(
                            relative_path="package.json",
                            original_content=old_pkg_content,
                            patched_content=new_pkg_content,
                            reason=f"Adição de '{diagnostic.symbol}' às dependências do package.json",
                        )
                    )
                except Exception:
                    pass

        # Case 4: Missing start script in package.json
        elif diagnostic.error_class == DiagnosticErrorClass.CONFIGURATION_ERROR:
            category = RepairCategory.START_SCRIPT_MISSING
            reason = "Adicionar script start ao package.json"
            expected = "npm run start funcional"
            pkg_path = os.path.join(root_dir, "package.json")
            if os.path.isfile(pkg_path):
                try:
                    import json
                    with open(pkg_path, "r", encoding="utf-8") as pf:
                        pkg_json = json.load(pf)
                    scripts = pkg_json.setdefault("scripts", {})
                    entry = profile.entrypoint or "app.js"
                    scripts["start"] = f"node {entry}"
                    new_pkg_content = json.dumps(pkg_json, indent=2)
                    with open(pkg_path, "r", encoding="utf-8") as pf:
                        old_pkg_content = pf.read()
                    patches.append(
                        FilePatch(
                            relative_path="package.json",
                            original_content=old_pkg_content,
                            patched_content=new_pkg_content,
                            reason="Adição do script start ao package.json",
                        )
                    )
                except Exception:
                    pass

        if not patches:
            return None

        # Evaluate Confidence
        is_known = diagnostic.symbol in ("app", "axios", "path", "fs", "express")
        confidence = self.confidence_evaluator.evaluate_confidence(
            diagnostic=diagnostic,
            category=category,
            has_deterministic_target=True,
            candidate_count=len(patches),
            is_known_symbol=is_known,
        )

        repair_id = compute_deterministic_hash(
            {"diag": diagnostic.diagnostic_id, "cat": category.value, "sym": diagnostic.symbol},
            prefix="rep_",
        )

        rollback_plan = {
            "strategy": "RESTORE_SNAPSHOT",
            "files": [p.relative_path for p in patches],
            "created_at": time.time(),
        }

        return RepairPlan(
            repair_id=repair_id,
            diagnostic_id=diagnostic.diagnostic_id,
            category=category,
            confidence=confidence,
            reason=reason,
            file_patches=patches,
            risk_score=0.10 if confidence == RepairConfidence.HIGH_CONFIDENCE else 0.40,
            rollback_plan=rollback_plan,
            expected_effect=expected,
        )

    def apply_repair(self, repair: RepairPlan, root_dir: str) -> bool:
        """Applies file patches atomically."""
        for patch in repair.file_patches:
            full_path = os.path.join(root_dir, patch.relative_path)
            try:
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(patch.patched_content)
            except Exception:
                # If any write fails, rollback immediately
                self.rollback_repair(repair, root_dir)
                return False
        return True

    def rollback_repair(self, repair: RepairPlan, root_dir: str) -> bool:
        """Reverts file patches to original content."""
        for patch in repair.file_patches:
            full_path = os.path.join(root_dir, patch.relative_path)
            try:
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(patch.original_content)
            except Exception:
                pass
        return True
