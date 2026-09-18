"""
JARVIS OS — Phase 67: Long-Horizon Autonomous Engineering Missions
Long-Horizon Mission Bridge (Central Singleton Coordinator).
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid

from backend.agents.long_horizon_missions.adaptation import AdaptiveReplanner
from backend.agents.long_horizon_missions.architecture import ArchitectureConsistencyGovernor
from backend.agents.long_horizon_missions.behavior import BehaviorConsistencyGovernor
from backend.agents.long_horizon_missions.budget import BudgetTracker
from backend.agents.long_horizon_missions.cache import MissionStateCache
from backend.agents.long_horizon_missions.checkpoint import CheckpointManager
from backend.agents.long_horizon_missions.completion import CompletionEvaluator
from backend.agents.long_horizon_missions.constraints import ConstraintValidator
from backend.agents.long_horizon_missions.contracts import ContractConsistencyGovernor
from backend.agents.long_horizon_missions.coordination import MissionCoordinationManager
from backend.agents.long_horizon_missions.evidence import EvidenceLedger
from backend.agents.long_horizon_missions.execution import MissionExecutionEngine
from backend.agents.long_horizon_missions.metrics import MissionMetricsTracker
from backend.agents.long_horizon_missions.milestones import MilestoneManager
from backend.agents.long_horizon_missions.mission_state import MissionStateMachine
from backend.agents.long_horizon_missions.models import (
    CheckpointType,
    LongHorizonMission,
    Milestone,
    MissionBudget,
    MissionObjective,
    MissionPlan,
    MissionState,
    ObjectiveCategory,
    ObjectiveState,
)
from backend.agents.long_horizon_missions.objectives import ObjectiveTracker
from backend.agents.long_horizon_missions.persistence import MissionPersistenceStore
from backend.agents.long_horizon_missions.planning import MissionPlanner
from backend.agents.long_horizon_missions.policy import get_policy
from backend.agents.long_horizon_missions.provenance import ProvenanceTracker
from backend.agents.long_horizon_missions.recovery import CrashRecoveryEngine
from backend.agents.long_horizon_missions.risk import RiskGovernor, RiskSeverity
from backend.agents.long_horizon_missions.security import MissionSecuritySentinel
from backend.agents.long_horizon_missions.validator import MissionValidator
from backend.agents.long_horizon_missions.verification import MissionVerifier


class LongHorizonMissionBridge:
    """
    Central coordinator bridging execution, planning, recovery, governance, and WebSocket handlers.
    """

    _instance: Optional[LongHorizonMissionBridge] = None

    def __init__(self, db_path: str = ":memory:"):
        self.persistence = MissionPersistenceStore(db_path)
        self.cache = MissionStateCache()
        self.missions: Dict[str, LongHorizonMission] = {}
        self.engines: Dict[str, MissionExecutionEngine] = {}
        self.trackers: Dict[str, ObjectiveTracker] = {}
        self.planners: Dict[str, MissionPlanner] = {}
        self.checkpoint_managers: Dict[str, CheckpointManager] = {}
        self.recovery_engines: Dict[str, CrashRecoveryEngine] = {}
        self.metrics_trackers: Dict[str, MissionMetricsTracker] = {}

    @classmethod
    def get_instance(cls, db_path: str = ":memory:") -> LongHorizonMissionBridge:
        if cls._instance is None:
            cls._instance = cls(db_path)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    def create_mission(
        self,
        objective: str,
        success_criteria: Optional[List[str]] = None,
        primary_objectives: Optional[List[MissionObjective]] = None,
        constraints: Optional[List[str]] = None,
        budget_limits: Optional[Dict[str, Any]] = None,
        policy_name: str = "GOVERNED",
        milestone_count: int = 10,
        mission_id: Optional[str] = None,
    ) -> LongHorizonMission:
        """
        Creates and registers a new LongHorizonMission.
        """
        mid = mission_id or f"lhm_{uuid.uuid4().hex[:8]}"
        criteria = success_criteria or ["All primary objectives verified", "Zero critical regressions"]
        policy = get_policy(policy_name)

        budget = MissionBudget.from_dict({"limits": budget_limits or {}})
        mission = LongHorizonMission(
            mission_id=mid,
            objective=objective,
            success_criteria=criteria,
            constraints=constraints or [],
            risk_policy=policy_name,
            verification_policy="CONTINUOUS_F62",
            security_policy="SANDBOXED_F65",
            budget=budget,
            created_at=time.time(),
            updated_at=time.time(),
        )

        # Setup objectives
        objs = primary_objectives or [
            MissionObjective(
                objective_id=f"OBJ_{mid}_01",
                description=objective,
                category=ObjectiveCategory.PRIMARY_OBJECTIVES,
                measurable_conditions=["tests_pass >= 1"],
                evidence_requirements=["CONTINUOUS_VERIFICATION"],
                priority=1,
            )
        ]
        obj_tracker = ObjectiveTracker(objs)
        self.trackers[mid] = obj_tracker

        # Setup planner and generate initial DAG
        planner = MissionPlanner()
        plan = planner.generate_scalable_dag(
            mid,
            node_count=milestone_count,
            objective_ids=[o.objective_id for o in objs],
        )
        mission.plan = plan
        self.planners[mid] = planner

        # Sub-engines
        m_mgr = MilestoneManager(plan.milestones)
        b_tracker = BudgetTracker(budget)
        cp_mgr = CheckpointManager()
        ev_ledger = EvidenceLedger()
        verifier = MissionVerifier()
        coord_mgr = MissionCoordinationManager()
        replanner = AdaptiveReplanner()
        risk_gov = RiskGovernor()
        sec_sentinel = MissionSecuritySentinel()
        comp_eval = CompletionEvaluator()

        exec_engine = MissionExecutionEngine(
            mission=mission,
            objective_tracker=obj_tracker,
            planner=planner,
            milestone_manager=m_mgr,
            budget_tracker=b_tracker,
            checkpoint_manager=cp_mgr,
            evidence_ledger=ev_ledger,
            verifier=verifier,
            coordination_manager=coord_mgr,
            replanner=replanner,
            risk_governor=risk_gov,
            security_sentinel=sec_sentinel,
            completion_evaluator=comp_eval,
        )

        self.missions[mid] = mission
        self.engines[mid] = exec_engine
        self.checkpoint_managers[mid] = cp_mgr
        self.recovery_engines[mid] = CrashRecoveryEngine()
        self.metrics_trackers[mid] = MissionMetricsTracker()

        self.persistence.save_mission(mission)
        return mission

    def execute_step(self, mission_id: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        engine = self.engines.get(mission_id)
        if not engine:
            raise KeyError(f"Mission {mission_id} not found")

        t0 = time.time()
        res = engine.execute_step(context)
        dt_ms = (time.time() - t0) * 1000.0

        metrics = self.metrics_trackers.get(mission_id)
        if metrics:
            metrics.add_timing("execution_ms", dt_ms)

        self.persistence.save_mission(engine.mission)
        return res

    def run_bounded(self, mission_id: str, max_steps: int = 500, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Runs bounded execution until completion, pause, failure, or max_steps.
        """
        engine = self.engines.get(mission_id)
        if not engine:
            raise KeyError(f"Mission {mission_id} not found")

        steps_run = 0
        last_step = {}
        terminal_states = {
            MissionState.COMPLETED,
            MissionState.FAILED,
            MissionState.BLOCKED,
            MissionState.CANCELLED,
            MissionState.ROLLED_BACK,
            MissionState.INCONCLUSIVE,
            MissionState.HUMAN_REVIEW,
        }

        while steps_run < max_steps:
            if engine.mission.current_state in terminal_states:
                break
            last_step = engine.execute_step(context)
            steps_run += 1

        return {
            "mission_id": mission_id,
            "steps_run": steps_run,
            "final_state": engine.mission.current_state.value,
            "last_step": last_step,
            "proof": engine.mission.completion_proof.to_dict() if engine.mission.completion_proof else None,
        }

    def get_mission(self, mission_id: str) -> Optional[LongHorizonMission]:
        return self.missions.get(mission_id)
