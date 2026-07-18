import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agents.mission_state import MissionStateError, MissionStateStore, StaleVersionError
from agents.planner_engine import PersistentPlanner


class MissionStateTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = self.temp.name
        for project_id in ("fraud-project", "other-project"):
            Path(self.root, "workspace", "projects", project_id).mkdir(parents=True)
        self.store = MissionStateStore(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def create_mission(self, project_id="fraud-project"):
        return self.store.create_mission(
            project_id,
            "Projeto universitario de detecao de fraude",
            "Investigar e validar um baseline de detecao de fraude",
            mission_id="fraud-mission",
        )

    @staticmethod
    def mission(snapshot):
        return snapshot["mission"]

    @staticmethod
    def work_package(snapshot, item_id):
        return next(item for item in snapshot["work_packages"] if item["work_package_id"] == item_id)

    @staticmethod
    def deliverable(snapshot, item_id):
        return next(item for item in snapshot["deliverables"] if item["deliverable_id"] == item_id)

    @staticmethod
    def criterion(snapshot, item_id):
        return next(item for item in snapshot["acceptance_criteria"] if item["criterion_id"] == item_id)

    def satisfy_work_package(self, snapshot, mission_id, work_package_id, suffix):
        criterion_id = f"criterion-{suffix}"
        evidence_id = f"evidence-{suffix}"
        snapshot = self.store.create_criterion(
            "fraud-project", mission_id, "WORK_PACKAGE", work_package_id,
            "Evidencia verificada", ["VALIDATION"], criterion_id=criterion_id,
        )
        snapshot = self.store.attach_evidence(
            "fraud-project", mission_id, work_package_id, "VALIDATION",
            f"validation:{suffix}", evidence_id=evidence_id,
        )
        return self.store.set_criterion_status(
            "fraud-project", mission_id, criterion_id, "SATISFIED",
            self.criterion(snapshot, criterion_id)["version"], [evidence_id],
        )

    def test_mission_crud_persistence_and_atomic_write(self):
        snapshot = self.create_mission()
        self.assertEqual(self.mission(snapshot)["status"], "DRAFT")
        self.assertEqual(len(self.store.list_missions("fraud-project")), 1)

        updated = self.store.update_mission(
            "fraud-project",
            "fraud-mission",
            self.mission(snapshot)["version"],
            {"description": "Descricao revista", "metadata": {"course": "Data Science"}},
        )
        self.assertEqual(self.mission(updated)["description"], "Descricao revista")
        self.assertEqual(self.mission(updated)["metadata"]["course"], "Data Science")

        reloaded = MissionStateStore(self.root).load_mission("fraud-project", "fraud-mission")
        self.assertEqual(self.mission(reloaded), self.mission(updated))
        mission_dir = Path(self.root, "workspace", ".jarvis", "projects", "fraud-project", "missions", "fraud-mission")
        self.assertFalse(list(mission_dir.rglob("*.tmp")))
        json.loads((mission_dir / "mission.json").read_text(encoding="utf-8"))

    def test_failed_atomic_replace_keeps_previous_state(self):
        snapshot = self.create_mission()
        mission_path = Path(self.root, "workspace", ".jarvis", "projects", "fraud-project", "missions", "fraud-mission", "mission.json")
        before = mission_path.read_bytes()
        with patch("agents.mission_state.os.replace", side_effect=OSError("replace failed")):
            with self.assertRaises(OSError):
                self.store.update_mission(
                    "fraud-project", "fraud-mission", self.mission(snapshot)["version"], {"description": "nao persistir"}
                )
        self.assertEqual(mission_path.read_bytes(), before)
        self.assertFalse(list(mission_path.parent.glob("*.tmp")))

    def test_work_package_crud_dag_and_ready_derivation(self):
        snapshot = self.create_mission()
        snapshot = self.store.create_work_package(
            "fraud-project", "fraud-mission", "Preparar dataset", type="RESEARCH", work_package_id="wp1"
        )
        snapshot = self.store.create_work_package(
            "fraud-project", "fraud-mission", "Baseline", type="CODING", dependencies=["wp1"], work_package_id="wp2"
        )
        self.assertEqual(self.work_package(snapshot, "wp1")["status"], "READY")
        self.assertEqual(self.work_package(snapshot, "wp2")["status"], "PENDING")
        self.assertEqual(snapshot["eligible_work_packages"], ["wp1"])

        with self.assertRaisesRegex(MissionStateError, "dependencias"):
            self.store.set_work_package_status(
                "fraud-project", "fraud-mission", "wp2", "IN_PROGRESS", self.work_package(snapshot, "wp2")["version"]
            )

        snapshot = self.store.update_work_package(
            "fraud-project", "fraud-mission", "wp1", self.work_package(snapshot, "wp1")["version"], {"priority": 10}
        )
        self.assertEqual(self.work_package(snapshot, "wp1")["priority"], 10)
        snapshot = self.store.set_work_package_status(
            "fraud-project", "fraud-mission", "wp1", "IN_PROGRESS", self.work_package(snapshot, "wp1")["version"]
        )
        snapshot = self.satisfy_work_package(snapshot, "fraud-mission", "wp1", "wp1")
        snapshot = self.store.set_work_package_status(
            "fraud-project", "fraud-mission", "wp1", "COMPLETED", self.work_package(snapshot, "wp1")["version"]
        )
        self.assertEqual(self.work_package(snapshot, "wp2")["status"], "READY")
        self.assertIn("wp2", snapshot["eligible_work_packages"])

    def test_dependency_validation_rejects_missing_self_direct_and_indirect_cycles(self):
        snapshot = self.create_mission()
        snapshot = self.store.create_work_package("fraud-project", "fraud-mission", "A", work_package_id="a")
        snapshot = self.store.create_work_package("fraud-project", "fraud-mission", "B", dependencies=["a"], work_package_id="b")
        snapshot = self.store.create_work_package("fraud-project", "fraud-mission", "C", dependencies=["b"], work_package_id="c")

        with self.assertRaisesRegex(MissionStateError, "inexistente"):
            self.store.add_dependency("fraud-project", "fraud-mission", "a", "missing", self.work_package(snapshot, "a")["version"])
        with self.assertRaisesRegex(MissionStateError, "si proprio"):
            self.store.add_dependency("fraud-project", "fraud-mission", "a", "a", self.work_package(snapshot, "a")["version"])
        with self.assertRaisesRegex(MissionStateError, "ciclo"):
            self.store.add_dependency("fraud-project", "fraud-mission", "a", "b", self.work_package(snapshot, "a")["version"])
        with self.assertRaisesRegex(MissionStateError, "ciclo"):
            self.store.add_dependency("fraud-project", "fraud-mission", "a", "c", self.work_package(snapshot, "a")["version"])

    def test_cancelled_dependency_derives_blocked_status(self):
        self.create_mission()
        snapshot = self.store.create_work_package("fraud-project", "fraud-mission", "Origem", work_package_id="origin")
        snapshot = self.store.create_work_package(
            "fraud-project", "fraud-mission", "Dependente", dependencies=["origin"], work_package_id="dependent"
        )
        snapshot = self.store.set_work_package_status(
            "fraud-project", "fraud-mission", "origin", "CANCELLED", self.work_package(snapshot, "origin")["version"]
        )
        self.assertEqual(self.work_package(snapshot, "dependent")["status"], "BLOCKED")
        self.assertNotIn("dependent", snapshot["eligible_work_packages"])

    def test_deliverable_criterion_evidence_and_completion_rules(self):
        snapshot = self.create_mission()
        snapshot = self.store.create_work_package(
            "fraud-project", "fraud-mission", "Relatorio", type="DOCUMENT", work_package_id="wp-report"
        )
        snapshot = self.store.create_deliverable(
            "fraud-project",
            "fraud-mission",
            "wp-report",
            "Relatorio final",
            kind="REPORT",
            required=True,
            deliverable_id="report",
        )
        snapshot = self.store.create_criterion(
            "fraud-project",
            "fraud-mission",
            "WORK_PACKAGE",
            "wp-report",
            "Resultados reproduzidos",
            required_evidence_kinds=["VALIDATION"],
            criterion_id="criterion-report",
        )
        snapshot = self.store.set_work_package_status(
            "fraud-project", "fraud-mission", "wp-report", "IN_PROGRESS", self.work_package(snapshot, "wp-report")["version"]
        )
        with self.assertRaisesRegex(MissionStateError, "Deliverables"):
            self.store.set_work_package_status(
                "fraud-project", "fraud-mission", "wp-report", "COMPLETED", self.work_package(snapshot, "wp-report")["version"]
            )
        with self.assertRaisesRegex(MissionStateError, "Evidence"):
            self.store.set_criterion_status(
                "fraud-project", "fraud-mission", "criterion-report", "SATISFIED",
                self.criterion(snapshot, "criterion-report")["version"], []
            )
        with self.assertRaisesRegex(MissionStateError, "inexistente"):
            self.store.set_criterion_status(
                "fraud-project", "fraud-mission", "criterion-report", "SATISFIED",
                self.criterion(snapshot, "criterion-report")["version"], ["missing"]
            )

        proof = Path(self.root, "workspace", "projects", "fraud-project", "proof.txt")
        proof.write_text("pytest passed", encoding="utf-8")
        snapshot = self.store.attach_evidence(
            "fraud-project",
            "fraud-mission",
            "wp-report",
            "VALIDATION",
            "file:workspace/projects/fraud-project/proof.txt",
            deliverable_id="report",
            evidence_id="evidence-report",
        )
        evidence = next(item for item in snapshot["evidence"] if item["evidence_id"] == "evidence-report")
        self.assertRegex(evidence["content_hash"], r"^[a-f0-9]{64}$")
        snapshot = self.store.set_criterion_status(
            "fraud-project", "fraud-mission", "criterion-report", "SATISFIED",
            self.criterion(snapshot, "criterion-report")["version"], ["evidence-report"]
        )
        snapshot = self.store.set_deliverable_status(
            "fraud-project", "fraud-mission", "report", "ACCEPTED", self.deliverable(snapshot, "report")["version"]
        )
        snapshot = self.store.set_work_package_status(
            "fraud-project", "fraud-mission", "wp-report", "COMPLETED", self.work_package(snapshot, "wp-report")["version"]
        )
        self.assertEqual(self.work_package(snapshot, "wp-report")["status"], "COMPLETED")

    def test_mission_transitions_and_premature_completion(self):
        snapshot = self.create_mission()
        with self.assertRaisesRegex(MissionStateError, "invalida"):
            self.store.set_mission_status(
                "fraud-project", "fraud-mission", "ACTIVE", self.mission(snapshot)["version"]
            )
        snapshot = self.store.create_work_package("fraud-project", "fraud-mission", "Obrigatorio", work_package_id="wp")
        snapshot = self.store.set_mission_status(
            "fraud-project", "fraud-mission", "READY", self.mission(snapshot)["version"]
        )
        snapshot = self.store.set_mission_status(
            "fraud-project", "fraud-mission", "ACTIVE", self.mission(snapshot)["version"]
        )
        with self.assertRaisesRegex(MissionStateError, "nao concluidos"):
            self.store.set_mission_status(
                "fraud-project", "fraud-mission", "COMPLETED", self.mission(snapshot)["version"]
            )
        snapshot = self.store.set_work_package_status(
            "fraud-project", "fraud-mission", "wp", "IN_PROGRESS", self.work_package(snapshot, "wp")["version"]
        )
        with self.assertRaisesRegex(MissionStateError, "AcceptanceCriterion"):
            self.store.set_work_package_status(
                "fraud-project", "fraud-mission", "wp", "COMPLETED", self.work_package(snapshot, "wp")["version"]
            )
        snapshot = self.satisfy_work_package(snapshot, "fraud-mission", "wp", "mission-wp")
        snapshot = self.store.set_work_package_status(
            "fraud-project", "fraud-mission", "wp", "COMPLETED", self.work_package(snapshot, "wp")["version"]
        )
        snapshot = self.store.set_mission_status(
            "fraud-project", "fraud-mission", "COMPLETED", self.mission(snapshot)["version"]
        )
        self.assertEqual(self.mission(snapshot)["status"], "COMPLETED")
        self.assertEqual(self.mission(snapshot)["progress"], 100.0)

    def test_optimistic_locking_event_log_restart_and_isolation(self):
        snapshot = self.create_mission()
        original_version = self.mission(snapshot)["version"]
        snapshot = self.store.update_mission(
            "fraud-project", "fraud-mission", original_version, {"current_phase": "Pesquisa"}
        )
        with self.assertRaises(StaleVersionError):
            self.store.update_mission(
                "fraud-project", "fraud-mission", original_version, {"current_phase": "stale"}
            )
        self.store.create_mission("other-project", "Outra", "Isolada", mission_id="fraud-mission")
        self.assertEqual(len(self.store.list_missions("fraud-project")), 1)
        self.assertEqual(len(self.store.list_missions("other-project")), 1)

        reloaded = MissionStateStore(self.root).load_mission("fraud-project", "fraud-mission")
        self.assertEqual(self.mission(reloaded)["current_phase"], "Pesquisa")
        self.assertGreaterEqual(len(reloaded["recent_events"]), 2)
        self.assertTrue(all(event["mission_id"] == "fraud-mission" for event in reloaded["recent_events"]))
        self.assertTrue(reloaded["read_only_execution"])

    def test_path_escape_and_legacy_preview(self):
        snapshot = self.create_mission()
        snapshot = self.store.create_work_package("fraud-project", "fraud-mission", "Pesquisa", work_package_id="wp")
        with self.assertRaisesRegex(MissionStateError, "relativa"):
            self.store.attach_evidence(
                "fraud-project", "fraud-mission", "wp", "SOURCE", "file:../secret.txt"
            )
        with self.assertRaises(MissionStateError):
            self.store.create_mission("../escape", "X", "Y")

        legacy = Path(self.root, ".jarvis_plan.json")
        legacy.write_text(json.dumps({
            "goal": "Plano antigo",
            "status": "PENDING",
            "steps": [{"id": 1, "action": "Pesquisar", "status": "DONE"}],
        }), encoding="utf-8")
        before = legacy.read_bytes()
        preview = self.store.legacy_plan_to_mission_preview()
        self.assertTrue(preview["read_only"])
        self.assertFalse(preview["migration_performed"])
        self.assertEqual(preview["work_packages"][0]["status"], "COMPLETED")
        self.assertEqual(legacy.read_bytes(), before)

    def test_persistent_planner_uses_mission_state_and_keeps_legacy_read_only(self):
        legacy = Path(self.root, ".jarvis_plan.json")
        legacy.write_text(json.dumps({"goal": "Antigo", "steps": [], "status": "PENDING"}), encoding="utf-8")
        planner = PersistentPlanner(self.root)
        self.assertEqual(planner.load_plan()["goal"], "Antigo")
        with self.assertRaisesRegex(RuntimeError, "apenas de leitura"):
            planner.create_plan("Novo plano global")
        with self.assertRaisesRegex(RuntimeError, "execucao autonoma"):
            planner.execute_next_step()
        snapshot = planner.create_mission("fraud-project", "Nova", "Mission State", mission_id="planner-mission")
        self.assertEqual(snapshot["mission"]["mission_id"], "planner-mission")


if __name__ == "__main__":
    unittest.main()
