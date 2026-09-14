"""
Tests for Autonomous Loop Crash Recovery and Idempotent Resumption.
"""

import os
import shutil
import tempfile
import pytest
from agents.autonomous_loop.controller import AutonomousLoopController
from agents.autonomous_loop.models import LoopDecisionType, LoopStage
from agents.autonomous_loop.state import AutonomousLoopStateManager


def test_checkpoint_persistence_and_restore():
    temp_dir = tempfile.mkdtemp()
    mission_id = "m_crash_01"

    try:
        # 1. Run cycle with controller using temp checkpoint dir
        ctrl1 = AutonomousLoopController(
            mission_id=mission_id,
            user_intent="Criar microsserviço resiliente",
            initial_requirements=[{"id": "REQ_RES_1", "title": "Heartbeat"}],
            initial_tasks=[{"id": "task_hb", "status": "PENDING", "files": ["hb.py"]}],
            checkpoint_dir=temp_dir,
        )

        state1, dec1 = ctrl1.step_cycle()
        assert state1.cycle_id == "cycle_1"
        assert state1.plan_version == 1
        assert len(ctrl1.state_mgr.checkpoints) == 1

        # Verify checkpoint file on disk
        files = os.listdir(temp_dir)
        chk_files = [f for f in files if f.startswith(f"checkpoint_{mission_id}_")]
        assert len(chk_files) == 1

        # 2. Simulate complete worker process crash (fresh manager instance)
        state_mgr2 = AutonomousLoopStateManager(mission_id=mission_id, checkpoint_dir=temp_dir)
        restored_data = state_mgr2.restore_latest_checkpoint()

        assert restored_data is not None
        assert restored_data["mission_id"] == mission_id
        assert restored_data["cycle_id"] == "cycle_1"
        assert restored_data["plan_version"] == 1
        assert state_mgr2.state.mission_id == mission_id
        assert state_mgr2.state.cycle_id == "cycle_1"
        assert state_mgr2.state.plan_version == 1

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_idempotent_continuation_after_recovery():
    temp_dir = tempfile.mkdtemp()
    mission_id = "m_crash_02"

    try:
        # Step 1
        ctrl1 = AutonomousLoopController(
            mission_id=mission_id,
            user_intent="Testar idempotência de recuperação",
            initial_requirements=[{"id": "REQ_IDEMP_1", "title": "Idempotência"}],
            initial_tasks=[{"id": "task_idemp", "status": "PENDING", "files": ["idemp.py"]}],
            checkpoint_dir=temp_dir,
        )
        ctrl1.step_cycle()

        # Step 2: Simulate restart by loading checkpoint into new controller
        state_mgr = AutonomousLoopStateManager(mission_id=mission_id, checkpoint_dir=temp_dir)
        restored = state_mgr.restore_latest_checkpoint()
        assert restored is not None

        ctrl2 = AutonomousLoopController(
            mission_id=mission_id,
            user_intent="Testar idempotência de recuperação",
            initial_requirements=[{"id": "REQ_IDEMP_1", "title": "Idempotência"}],
            initial_tasks=ctrl1.tasks,
            checkpoint_dir=temp_dir,
        )
        # Restore versions
        ctrl2.cycle_counter = ctrl1.cycle_counter
        ctrl2.state_mgr.state = state_mgr.state

        # Execute cycle 2
        state2, dec2 = ctrl2.step_cycle()
        assert state2.cycle_id == "cycle_2"
        # Verify tasks not duplicated
        task_ids = [t["id"] for t in ctrl2.tasks]
        assert len(task_ids) == len(set(task_ids))

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
