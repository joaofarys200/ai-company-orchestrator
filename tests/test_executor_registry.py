import unittest
from types import SimpleNamespace

from agents.executors import (
    CodingWorkPackageExecutor,
    DuplicateExecutorKindError,
    ExecutorDescriptor,
    ExecutorNotFoundError,
    ExecutorRegistry,
    ExecutorRegistryError,
    ProjectBuildWorkPackageExecutor,
    WorkPackageExecutionContext,
    WorkPackageExecutionResult,
    create_default_executor_registry,
)
from agents.mission_executor import MissionExecutorService


class StubExecutor:
    kind = "STUB"

    async def execute(self, _context):
        return WorkPackageExecutionResult(
            status="COMPLETED",
            phase="DONE",
        )


def descriptor(
    kind="STUB",
    *,
    supported=True,
    autonomous_allowed=True,
    executor_name="StubExecutor",
):
    return ExecutorDescriptor(
        kind=kind,
        executor_name=executor_name,
        supported=supported,
        requires_apply_approval=False,
        autonomous_allowed=autonomous_allowed,
        risk_level="LOW",
        description="Executor de teste.",
    )


class FakeGateway:
    def __init__(self):
        self.prepared = []
        self.applied = []
        self.builder_calls = []
        self.fail_coding = False
        self.execution = SimpleNamespace(version=2)

    def _load_execution(self, _project_id, _mission_id, _execution_id):
        return self.execution

    async def _prepare_coding_execution(self, project_id, _execution):
        if self.fail_coding:
            raise RuntimeError("coding unavailable")
        self.prepared.append(project_id)
        return self._snapshot(
            "RUNNING",
            "AWAITING_APPLY_APPROVAL",
            artifact_refs=["file:workspace/projects/p/app.js"],
        )

    @staticmethod
    def _execution_from_snapshot(_snapshot, _execution_id):
        return SimpleNamespace(version=3)

    def apply_execution(
        self,
        project_id,
        mission_id,
        execution_id,
        version,
        confirmed,
    ):
        self.applied.append(
            (project_id, mission_id, execution_id, version, confirmed)
        )
        return self._snapshot(
            "WAITING_FOR_REVIEW",
            "TECHNICAL_SUCCESS",
            artifact_refs=["file:workspace/projects/p/app.js"],
            evidence_refs=["evidence-1"],
            validation_refs=["validation:session"],
        )

    async def _run_project_builder(
        self,
        project_id,
        _execution,
        *,
        test_mode=False,
    ):
        self.builder_calls.append((project_id, test_mode))
        return self._snapshot(
            "WAITING_FOR_REVIEW",
            "TECHNICAL_SUCCESS",
            artifact_refs=["file:workspace/projects/built/index.html"],
            evidence_refs=["evidence-build"],
            validation_refs=["validation:build"],
        )

    @staticmethod
    def _snapshot(
        status,
        phase,
        artifact_refs=None,
        evidence_refs=None,
        validation_refs=None,
    ):
        return {
            "mission": {"mission_id": "m", "version": 1},
            "executions": [{
                "execution_id": "e",
                "status": status,
                "output_summary": {"phase": phase},
                "artifact_refs": artifact_refs or [],
                "evidence_refs": evidence_refs or [],
                "validation_refs": validation_refs or [],
            }],
        }


def context(
    gateway,
    *,
    kind="CODING",
    test_mode=False,
    autonomous=False,
    allow_apply=False,
):
    return WorkPackageExecutionContext(
        project_id="p",
        mission_id="m",
        execution_id="e",
        executor_kind=kind,
        mission={"mission_id": "m"},
        work_package={"work_package_id": "wp", "type": kind},
        execution_snapshot={"execution_id": "e"},
        input_snapshot={},
        test_mode=test_mode,
        autonomous=autonomous,
        allow_apply=allow_apply,
        service=gateway,
    )


class ExecutorRegistryTest(unittest.IsolatedAsyncioTestCase):
    def test_registers_valid_executor(self):
        registry = ExecutorRegistry()
        executor = StubExecutor()
        registry.register(executor, descriptor())
        self.assertIs(registry.get("stub"), executor)

    def test_rejects_duplicate_kind(self):
        registry = ExecutorRegistry()
        registry.register(StubExecutor(), descriptor())
        with self.assertRaises(DuplicateExecutorKindError):
            registry.register(StubExecutor(), descriptor())

    def test_rejects_unknown_executor(self):
        registry = ExecutorRegistry()
        with self.assertRaises(ExecutorNotFoundError):
            registry.get("UNKNOWN")

    def test_describe_preserves_legacy_fields_and_adds_policy(self):
        described = create_default_executor_registry().describe()
        self.assertTrue(described["CODING"]["supported"])
        self.assertEqual(described["CODING"]["executor"], "CodingSession")
        self.assertTrue(
            described["CODING"]["requires_apply_approval"]
        )
        self.assertTrue(described["CODING"]["autonomous_allowed"])
        self.assertIn("risk_level", described["CODING"])
        self.assertIn("description", described["CODING"])

    def test_available_for_autonomy_filters_descriptors(self):
        available = create_default_executor_registry().available_for_autonomy()
        self.assertEqual([item.kind for item in available], ["CODING"])

    def test_registry_can_be_injected_into_service(self):
        registry = create_default_executor_registry()
        service = MissionExecutorService(
            coding_service=object(),
            project_builder_runner=lambda _prompt: None,
            executor_registry=registry,
        )
        self.assertIs(service.executor_registry, registry)

    def test_rejects_incompatible_executor_descriptor(self):
        registry = ExecutorRegistry()
        with self.assertRaises(ExecutorRegistryError):
            registry.register(
                StubExecutor(),
                descriptor(kind="OTHER"),
            )
        with self.assertRaises(ExecutorRegistryError):
            registry.register(None, descriptor())
        with self.assertRaises(ExecutorRegistryError):
            registry.register(
                StubExecutor(),
                descriptor(
                    supported=False,
                    autonomous_allowed=False,
                    executor_name=None,
                ),
            )

    async def test_coding_adapter_delegates_without_auto_apply(self):
        gateway = FakeGateway()
        result = await CodingWorkPackageExecutor().execute(
            context(
                gateway,
                test_mode=True,
                autonomous=True,
                allow_apply=False,
            )
        )
        self.assertEqual(gateway.prepared, ["p"])
        self.assertEqual(gateway.applied, [])
        self.assertTrue(result.requires_review)
        self.assertEqual(result.phase, "AWAITING_APPLY_APPROVAL")

    async def test_coding_manual_test_mode_preserves_existing_apply_flow(self):
        gateway = FakeGateway()
        result = await CodingWorkPackageExecutor().execute(
            context(
                gateway,
                test_mode=True,
                autonomous=False,
                allow_apply=True,
            )
        )
        self.assertEqual(len(gateway.applied), 1)
        self.assertEqual(result.status, "WAITING_FOR_REVIEW")

    async def test_coding_preserves_artifacts_evidence_and_validations(self):
        gateway = FakeGateway()
        result = await CodingWorkPackageExecutor().execute(
            context(
                gateway,
                test_mode=True,
                allow_apply=True,
            )
        )
        self.assertEqual(
            result.artifact_refs,
            ["file:workspace/projects/p/app.js"],
        )
        self.assertEqual(result.evidence_refs, ["evidence-1"])
        self.assertEqual(
            result.validation_refs,
            ["validation:session"],
        )
        self.assertTrue(result.rollback_capable)

    async def test_project_build_adapter_delegates_and_propagates_test_mode(self):
        gateway = FakeGateway()
        result = await ProjectBuildWorkPackageExecutor().execute(
            context(
                gateway,
                kind="PROJECT_BUILD",
                test_mode=True,
            )
        )
        self.assertEqual(gateway.builder_calls, [("p", True)])
        self.assertEqual(result.status, "WAITING_FOR_REVIEW")
        self.assertEqual(result.evidence_refs, ["evidence-build"])

    async def test_adapter_normalizes_exception(self):
        gateway = FakeGateway()
        gateway.fail_coding = True
        result = await CodingWorkPackageExecutor().execute(context(gateway))
        self.assertEqual(result.status, "FAILED")
        self.assertEqual(result.error["type"], "RuntimeError")
        self.assertEqual(result.error["message"], "coding unavailable")
        self.assertIsInstance(result.exception, RuntimeError)


if __name__ == "__main__":
    unittest.main()
