"""
JARVIS OS — Phase 57: Predictive Mission Planner
Generates structured execution plans, performing pre-execution impact predictions
(files, symbols, contracts, consumers, risks, validations, repairs) and tracking prediction accuracy.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from .models import AutonomousMission, TaskUnderstandingResult


class MissionPlanner:
    """Predictive and adaptive mission planner."""

    @classmethod
    def generate_plan(
        cls,
        mission: AutonomousMission,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        plan_id = f"plan_{uuid.uuid4().hex[:8]}"
        domain = mission.provenance.get("domain", "general_engineering")
        
        # 1. Predictive Impact Estimation
        predicted_files = cls._predict_impacted_files(mission.objective, domain)
        predicted_symbols = cls._predict_symbols(mission.objective, domain)
        predicted_contracts = cls._predict_contracts(domain)
        predicted_consumers = cls._predict_consumers(domain)
        predicted_risks = cls._predict_risks(mission.risk, domain)
        predicted_validations = ["syntax", "type_check", "unit_test"]
        if domain in ("frontend", "fullstack", "browser_task"):
            predicted_validations.append("browser_e2e")
        if domain in ("backend", "contract_change"):
            predicted_validations.append("contract_schema_diff")
        
        predicted_repairs = ["import_path_fix", "schema_mismatch_adaptation"] if mission.risk > 0.3 else []

        # 2. Ordered Work Packages (DAG)
        tasks = []
        # Task 1: Environment & Preflight
        tasks.append({
            "task_id": "tsk_01_preflight",
            "title": "Verificação de Preflight e Ambiente",
            "action": "PREFLIGHT",
            "dependencies": [],
            "estimated_duration_ms": 150,
            "owner": "quinn_qa",
        })
        # Task 2: Implementation / Core Patch
        tasks.append({
            "task_id": "tsk_02_implementation",
            "title": f"Implementação de '{mission.objective[:40]}'",
            "action": "CODE_SYNTHESIS",
            "dependencies": ["tsk_01_preflight"],
            "target_files": predicted_files,
            "estimated_duration_ms": 800,
            "owner": "devon_coder",
        })
        # Task 3: Multi-Level Verification
        tasks.append({
            "task_id": "tsk_03_verification",
            "title": "Validação Multi-Nível (Compilação, Testes, Contratos)",
            "action": "VERIFICATION",
            "dependencies": ["tsk_02_implementation"],
            "validation_methods": predicted_validations,
            "estimated_duration_ms": 400,
            "owner": "quinn_qa",
        })
        # Task 4: Browser / UI validation if applicable
        if "browser_e2e" in predicted_validations:
            tasks.append({
                "task_id": "tsk_04_browser_validation",
                "title": "Validação de Browser e Renderização DOM",
                "action": "BROWSER_QA",
                "dependencies": ["tsk_03_verification"],
                "estimated_duration_ms": 600,
                "owner": "quinn_qa",
            })
        # Task 5: Formal Proof & Convergence
        last_dep = tasks[-1]["task_id"]
        tasks.append({
            "task_id": "tsk_05_completion_proof",
            "title": "Síntese de Prova Formal e Emissão de Certificado",
            "action": "PROVE_AND_CLOSE",
            "dependencies": [last_dep],
            "estimated_duration_ms": 200,
            "owner": "alex_architect",
        })

        plan = {
            "plan_id": plan_id,
            "mission_id": mission.mission_id,
            "created_at": time.time(),
            "tasks": tasks,
            "predictions": {
                "predicted_files": predicted_files,
                "predicted_symbols": predicted_symbols,
                "predicted_contracts": predicted_contracts,
                "predicted_consumers": predicted_consumers,
                "predicted_risks": predicted_risks,
                "predicted_validations": predicted_validations,
                "predicted_repairs": predicted_repairs,
            },
            "actuals": {
                "modified_files": [],
                "actual_repairs": [],
                "actual_validations": [],
            },
            "accuracy_score": 1.0,
        }

        mission.plan = plan
        return plan

    @classmethod
    def evaluate_prediction_accuracy(cls, mission: AutonomousMission) -> float:
        """Compares pre-execution predictions with actual execution outcomes."""
        plan = mission.plan
        if not plan or "predictions" not in plan:
            return 1.0

        preds = plan["predictions"]
        actuals = plan.get("actuals", {})

        pred_files = set(preds.get("predicted_files", []))
        act_files = set(actuals.get("modified_files", []))

        if not pred_files and not act_files:
            file_acc = 1.0
        elif not pred_files or not act_files:
            file_acc = 0.75  # Reasonable baseline
        else:
            intersection = len(pred_files.intersection(act_files))
            union = len(pred_files.union(act_files))
            file_acc = intersection / union if union > 0 else 1.0

        plan["accuracy_score"] = round(file_acc, 3)
        return plan["accuracy_score"]

    @staticmethod
    def _predict_impacted_files(objective: str, domain: str) -> list[str]:
        files = []
        if domain == "frontend":
            files.extend(["frontend/src/features/missions/components/MissionCard.tsx", "frontend/src/index.css"])
        elif domain == "backend":
            files.extend(["backend/routers/mission_api.py", "backend/models/mission_model.py"])
        elif domain == "fullstack":
            files.extend(["frontend/src/App.tsx", "backend/server.py", "backend/schemas.py"])
        elif domain == "contract_change":
            files.extend(["schemas/mission.schema.json", "backend/websocket/contracts.py"])
        else:
            files.append("agents/task_handler.py")
        return files

    @staticmethod
    def _predict_symbols(objective: str, domain: str) -> list[str]:
        return ["MissionController", "handle_request", "render_mission_ui"]

    @staticmethod
    def _predict_contracts(domain: str) -> list[str]:
        if domain in ("backend", "contract_change", "fullstack"):
            return ["mission_status_contract_v2", "websocket_event_schema"]
        return []

    @staticmethod
    def _predict_consumers(domain: str) -> list[str]:
        if domain in ("backend", "contract_change", "fullstack"):
            return ["frontend_mission_control_hud", "sentinel_audit_consumer"]
        return []

    @staticmethod
    def _predict_risks(risk_score: float, domain: str) -> list[str]:
        risks = []
        if risk_score > 0.5:
            risks.append("HIGH_REGRESSION_RISK")
        if domain in ("contract_change", "backend"):
            risks.append("CONSUMER_DRIFT_RISK")
        if not risks:
            risks.append("NOMINAL_RISK")
        return risks
