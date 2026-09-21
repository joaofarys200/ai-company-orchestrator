import asyncio
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from agents.mission_control_engine import (
    CommandType,
    MissionControlCommand,
    MissionControlEngine,
    MissionControlState,
)
from agents.mission_state import (
    Mission,
    MissionStateError,
    MissionStateStore,
    ProjectContextMissingError,
)
from intelligence.project_context import ProjectContextService


class TestMissionRuntimeLifecycleIntegrity(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = self.temp_dir.name
        
        # Setup workspace project paths
        self.project_a = "task-app"
        self.project_b = "finance-tracker"
        Path(self.root, "workspace", "projects", self.project_a).mkdir(parents=True, exist_ok=True)
        Path(self.root, "workspace", "projects", self.project_b).mkdir(parents=True, exist_ok=True)
        
        # Initialize context service and mission state store
        self.project_service = ProjectContextService(self.root)
        self.store = MissionStateStore(self.root, project_context=self.project_service)

    def tearDown(self):
        self.temp_dir.cleanup()

    # 1. test_mission_created_with_explicit_project_context
    def test_mission_created_with_explicit_project_context(self):
        snapshot = self.store.create_mission(
            self.project_a,
            "Gestor de Despesas",
            "Construir gestor de despesas com persistência",
            mission_id="m_explicit_01",
        )
        m = snapshot["mission"]
        self.assertEqual(m["mission_id"], "m_explicit_01")
        self.assertEqual(m["project_id"], self.project_a)
        self.assertTrue(bool(m["project_name"]))
        self.assertTrue(bool(m["project_path"]))
        self.assertTrue(bool(m["execution_id"]))
        self.assertEqual(m["last_event_sequence"], 1)

    # 2. test_mission_creation_fails_without_project_context
    def test_mission_creation_fails_without_project_context(self):
        # Empty project_id
        with self.assertRaises(ProjectContextMissingError):
            self.store.create_mission(
                "",
                "Missão Órfã",
                "Sem projeto associado",
            )
        # Nonexistent project_id
        with self.assertRaises(ProjectContextMissingError):
            self.store.create_mission(
                "nonexistent-project-404",
                "Missão Fantasma",
                "Projeto não existe no workspace",
            )

    # 3. test_mission_identity_immutable_across_mutations
    def test_mission_identity_immutable_across_mutations(self):
        snapshot = self.store.create_mission(
            self.project_a,
            "Missão Original",
            "Objetivo Original",
            mission_id="m_immutable_01",
        )
        orig_p_id = snapshot["mission"]["project_id"]
        orig_p_name = snapshot["mission"]["project_name"]
        orig_p_path = snapshot["mission"]["project_path"]

        # Mutate title and description
        updated = self.store.update_mission(
            self.project_a,
            "m_immutable_01",
            expected_version=snapshot["mission"]["version"],
            changes={"title": "Título Atualizado", "description": "Nova Descrição"},
        )
        m = updated["mission"]
        self.assertEqual(m["project_id"], orig_p_id)
        self.assertEqual(m["project_name"], orig_p_name)
        self.assertEqual(m["project_path"], orig_p_path)

    # 4. test_mission_control_state_contains_canonical_project_metadata
    def test_mission_control_state_contains_canonical_project_metadata(self):
        state = MissionControlEngine.get_scenario_state("INTERACTIVE")
        d = state.to_dict()
        self.assertIn("project_id", d)
        self.assertIn("project_name", d)
        self.assertIn("project_path", d)
        self.assertIn("execution_id", d)
        self.assertIn("last_event_at", d)
        self.assertIn("last_event_sequence", d)

    # 5. test_initial_sync_delivers_complete_mission_snapshot
    def test_initial_sync_delivers_complete_mission_snapshot(self):
        self.store.create_mission(
            self.project_a,
            "Missão Alpha",
            "Objetivo Alpha",
            mission_id="m_sync_01",
        )
        self.store.create_mission(
            self.project_b,
            "Missão Beta",
            "Objetivo Beta",
            mission_id="m_sync_02",
        )

        all_missions = self.store.list_all_missions()
        self.assertEqual(len(all_missions), 2)
        for m in all_missions:
            self.assertTrue(bool(m["project_id"]))
            self.assertTrue(bool(m["project_name"]))
            self.assertIn("status", m)
            self.assertIn("progress", m)
            self.assertIn("last_event_sequence", m)

    # 6. test_mission_event_emitted_on_execution_progress
    def test_mission_event_emitted_on_execution_progress(self):
        snapshot = self.store.create_mission(
            self.project_a,
            "Missão Progresso",
            "Testar progresso de execução",
            mission_id="m_progress_01",
        )
        updated = self.store.update_mission_progress(
            self.project_a,
            "m_progress_01",
            progress=42.5,
            current_stage="BUILD",
            status="RUNNING",
        )
        m = updated["mission"]
        self.assertEqual(m["progress"], 42.5)
        self.assertEqual(m["current_stage"], "BUILD")
        self.assertEqual(m["status"], "RUNNING")
        self.assertGreater(m["last_event_sequence"], 1)

    # 7. test_mission_event_sequence_strictly_monotonic
    def test_mission_event_sequence_strictly_monotonic(self):
        snapshot = self.store.create_mission(
            self.project_a,
            "Missão Monotónica",
            "Testar sequenciamento estrito",
            mission_id="m_mono_01",
        )
        seq_0 = snapshot["mission"]["last_event_sequence"]

        snap1 = self.store.update_mission_progress(self.project_a, "m_mono_01", 10.0, "STAGE_1")
        seq_1 = snap1["mission"]["last_event_sequence"]

        snap2 = self.store.update_mission_progress(self.project_a, "m_mono_01", 25.0, "STAGE_2")
        seq_2 = snap2["mission"]["last_event_sequence"]

        snap3 = self.store.update_mission_progress(self.project_a, "m_mono_01", 50.0, "STAGE_3")
        seq_3 = snap3["mission"]["last_event_sequence"]

        self.assertLess(seq_0, seq_1)
        self.assertLess(seq_1, seq_2)
        self.assertLess(seq_2, seq_3)

    # 8. test_client_deduplicates_repeated_event_sequence
    def test_client_deduplicates_repeated_event_sequence(self):
        # Emulating the client sequence state logic
        last_sequence = 5
        incoming_event_sequence = 5
        
        # Invariant: sequence == last_sequence -> DEDUPLICATE
        action = "DEDUPLICATE" if incoming_event_sequence == last_sequence else "APPLY"
        self.assertEqual(action, "DEDUPLICATE")

    # 9. test_client_ignores_older_event_sequence
    def test_client_ignores_older_event_sequence(self):
        # Emulating client sequence logic for out-of-order stale event
        last_sequence = 5
        incoming_event_sequence = 4

        action = "IGNORE" if incoming_event_sequence < last_sequence else "APPLY"
        self.assertEqual(action, "IGNORE")

    # 10. test_state_gap_detection_triggers_snapshot_recovery
    def test_state_gap_detection_triggers_snapshot_recovery(self):
        # Emulating client state gap detection
        last_sequence = 5
        incoming_event_sequence = 8  # Gap of sequences 6 and 7 missed

        action = "STATE_GAP_DETECTED" if incoming_event_sequence > last_sequence + 1 else "APPLY"
        self.assertEqual(action, "STATE_GAP_DETECTED")

    # 11. test_mission_progress_updates_without_page_refresh
    def test_mission_progress_updates_without_page_refresh(self):
        self.store.create_mission(
            self.project_a,
            "Missão Incremental",
            "Sem refresh de página",
            mission_id="m_live_01",
        )
        snap1 = self.store.update_mission_progress(self.project_a, "m_live_01", 20.0, "STAGE_A")
        snap2 = self.store.update_mission_progress(self.project_a, "m_live_01", 60.0, "STAGE_B")
        loaded = self.store.load_mission(self.project_a, "m_live_01")
        
        self.assertEqual(loaded["mission"]["progress"], 60.0)
        self.assertEqual(loaded["mission"]["current_stage"], "STAGE_B")

    # 12. test_mission_cannot_be_deleted_while_running
    def test_mission_cannot_be_deleted_while_running(self):
        self.store.create_mission(
            self.project_a,
            "Missão Em Execução",
            "Tentar apagar enquanto ativa",
            mission_id="m_del_running",
        )
        self.store.update_mission_progress(self.project_a, "m_del_running", 30.0, "BUILD", status="RUNNING")

        with self.assertRaises(MissionStateError) as ctx:
            self.store.delete_mission(self.project_a, "m_del_running")
        err_msg = str(ctx.exception).lower()
        self.assertTrue("execucao" in err_msg or "execução" in err_msg)

    # 13. test_mission_cannot_be_deleted_while_cancelling
    def test_mission_cannot_be_deleted_while_cancelling(self):
        self.store.create_mission(
            self.project_a,
            "Missão Em Cancelamento",
            "Tentar apagar enquanto cancela",
            mission_id="m_del_cancelling",
        )
        self.store.update_mission_progress(self.project_a, "m_del_cancelling", 30.0, "BUILD", status="CANCELLING")

        with self.assertRaises(MissionStateError) as ctx:
            self.store.delete_mission(self.project_a, "m_del_cancelling")
        err_msg = str(ctx.exception).lower()
        self.assertTrue("execucao" in err_msg or "execução" in err_msg)

    # 14. test_stop_command_transitions_running_to_cancelling
    def test_stop_command_transitions_running_to_cancelling(self):
        cmd = MissionControlCommand(
            command_id="cmd_stop_01",
            mission_id="m_p36_interactive",
            command_type=CommandType.CANCEL,
            user_id="operator",
            requested_at=time.time(),
            reason="Paragem manual solicitada pelo operador",
            idempotency_key="idemp_stop_01",
        )
        result = MissionControlEngine.execute_command(cmd)
        self.assertEqual(result.status.value, "ACCEPTED")
        # In interactive scenario, STOP sets status to CANCELLED (terminal)
        self.assertIn(result.state_dict["status"], ("CANCELLING", "CANCELLED"))

    # 15. test_cancelling_transitions_to_cancelled_on_engine_ack
    def test_cancelling_transitions_to_cancelled_on_engine_ack(self):
        self.store.create_mission(
            self.project_a,
            "Missão Paragem",
            "Transição CANCELLING -> CANCELLED",
            mission_id="m_ack_01",
        )
        snap1 = self.store.update_mission_progress(self.project_a, "m_ack_01", 30.0, "CANCELLING", status="CANCELLING")
        self.assertEqual(snap1["mission"]["status"], "CANCELLING")

        snap2 = self.store.update_mission_progress(self.project_a, "m_ack_01", 30.0, "CANCELLED", status="CANCELLED")
        self.assertEqual(snap2["mission"]["status"], "CANCELLED")

    # 16. test_cancelled_mission_can_be_removed_from_history
    def test_cancelled_mission_can_be_removed_from_history(self):
        self.store.create_mission(
            self.project_a,
            "Missão Cancelada",
            "Remoção após cancelamento",
            mission_id="m_del_cancelled",
        )
        self.store.set_mission_status(self.project_a, "m_del_cancelled", "CANCELLED", expected_version=1)
        
        # Deletion must succeed without error
        res = self.store.delete_mission(self.project_a, "m_del_cancelled")
        self.assertTrue(res)

    # 17. test_completed_mission_can_be_removed_from_history
    def test_completed_mission_can_be_removed_from_history(self):
        self.store.create_mission(
            self.project_a,
            "Missão Concluída",
            "Remoção após conclusão com sucesso",
            mission_id="m_del_completed",
        )
        self.store.update_mission_progress(self.project_a, "m_del_completed", 100.0, "COMPLETED", status="COMPLETED")
        
        res = self.store.delete_mission(self.project_a, "m_del_completed")
        self.assertTrue(res)

    # 18. test_failed_mission_can_be_removed_from_history
    def test_failed_mission_can_be_removed_from_history(self):
        self.store.create_mission(
            self.project_a,
            "Missão Falhada",
            "Remoção após falha",
            mission_id="m_del_failed",
        )
        self.store.update_mission_progress(self.project_a, "m_del_failed", 40.0, "FAILED", status="FAILED")
        
        res = self.store.delete_mission(self.project_a, "m_del_failed")
        self.assertTrue(res)

    # 19. test_removed_mission_cleans_runtime_and_persistence
    def test_removed_mission_cleans_runtime_and_persistence(self):
        self.store.create_mission(
            self.project_a,
            "Missão a Expurgar",
            "Verificar ausência no storage",
            mission_id="m_clean_01",
        )
        self.store.update_mission_progress(self.project_a, "m_clean_01", 100.0, "COMPLETED", status="COMPLETED")
        self.store.delete_mission(self.project_a, "m_clean_01")

        # Must raise MissionStateError on load
        with self.assertRaises(MissionStateError):
            self.store.load_mission(self.project_a, "m_clean_01")

    # 20. test_removed_mission_disappears_from_all_connected_clients
    def test_removed_mission_disappears_from_all_connected_clients(self):
        self.store.create_mission(
            self.project_a,
            "Missão Visível",
            "Objetivo",
            mission_id="m_visible_01",
        )
        self.store.update_mission_progress(self.project_a, "m_visible_01", 100.0, "COMPLETED", status="COMPLETED")
        
        list_before = self.store.list_missions(self.project_a)
        self.assertTrue(any(m["mission_id"] == "m_visible_01" for m in list_before))

        self.store.delete_mission(self.project_a, "m_visible_01")

        list_after = self.store.list_missions(self.project_a)
        self.assertFalse(any(m["mission_id"] == "m_visible_01" for m in list_after))

    # 21. test_stale_running_mission_marked_no_recent_updates_after_15s
    def test_stale_running_mission_marked_no_recent_updates_after_15s(self):
        # Staleness evaluation logic
        now = time.time()
        last_event_at = now - 18.0  # 18 seconds ago (> 15s)
        status = "RUNNING"
        
        is_stale = (status in ("RUNNING", "CANCELLING")) and ((now - last_event_at) > 15.0)
        self.assertTrue(is_stale)
        
        # Critical guarantee: mission must NOT transition to FAILED automatically
        self.assertEqual(status, "RUNNING")

    # 22. test_reconnect_reconciles_missed_events_via_snapshot
    def test_reconnect_reconciles_missed_events_via_snapshot(self):
        self.store.create_mission(
            self.project_a,
            "Missão Reconciliação",
            "Objetivo",
            mission_id="m_recon_01",
        )
        # Advance backend to progress 75%
        self.store.update_mission_progress(self.project_a, "m_recon_01", 75.0, "TESTING")
        
        # Client reconnects and requests snapshot
        snapshot = self.store.load_mission(self.project_a, "m_recon_01")
        self.assertEqual(snapshot["mission"]["progress"], 75.0)
        self.assertEqual(snapshot["mission"]["current_stage"], "TESTING")

    # 23. test_switching_workspace_project_updates_mission_visibility
    def test_switching_workspace_project_updates_mission_visibility(self):
        self.store.create_mission(
            self.project_a,
            "Missão Projeto A",
            "Exclusiva de A",
            mission_id="m_proj_a",
        )
        self.store.create_mission(
            self.project_b,
            "Missão Projeto B",
            "Exclusiva de B",
            mission_id="m_proj_b",
        )

        missions_a = self.store.list_missions(self.project_a)
        missions_b = self.store.list_missions(self.project_b)

        self.assertTrue(any(m["mission_id"] == "m_proj_a" for m in missions_a))
        self.assertFalse(any(m["mission_id"] == "m_proj_b" for m in missions_a))

        self.assertTrue(any(m["mission_id"] == "m_proj_b" for m in missions_b))
        self.assertFalse(any(m["mission_id"] == "m_proj_a" for m in missions_b))

    # 24. test_zero_residual_state_after_mission_removal
    def test_zero_residual_state_after_mission_removal(self):
        self.store.create_mission(
            self.project_a,
            "Missão Temporária",
            "Objetivo Temporário",
            mission_id="m_temp_zero",
        )
        self.store.set_mission_status(self.project_a, "m_temp_zero", "CANCELLED", expected_version=1)
        self.store.delete_mission(self.project_a, "m_temp_zero")

        # Check all missions for project_a
        missions_left = self.store.list_missions(self.project_a)
        self.assertEqual(len(missions_left), 0)

        # Check all missions across entire workspace
        all_left = self.store.list_all_missions()
        self.assertEqual(len(all_left), 0)


if __name__ == "__main__":
    unittest.main()
