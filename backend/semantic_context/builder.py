from __future__ import annotations

import os
import time
from collections import Counter
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from agents.mission_state import MissionStateStore
from backend.capability_registry import CapabilityRegistry
from backend.model_harness.profiles import (
    TaskProfile,
    TaskProfileRegistry,
    create_default_task_profile_registry,
)
from backend.semantic_context.capabilities import CapabilityContextReader
from backend.semantic_context.compression import (
    DeterministicContextCompressor,
)
from backend.semantic_context.contracts import (
    EPOCH_TIMESTAMP,
    BuilderConfiguration,
    CapabilityContext,
    ContextItem,
    ContextKind,
    ContextSource,
    MissionContext,
    SemanticSnapshot,
    canonical_json,
    sha256_json,
    sha256_text,
    to_jsonable,
)
from backend.semantic_context.mission import MissionContextReader
from backend.semantic_context.ranking import DeterministicContextRanker
from backend.semantic_context.serializer import SemanticContextSerializer
from backend.semantic_context.snapshot import SemanticSnapshotFactory
from backend.semantic_context.telemetry import SemanticContextTelemetry
from backend.semantic_context.validator import SemanticContextValidator
from backend.semantic_context.workspace import (
    WorkspaceInspection,
    WorkspaceInspector,
)


class SemanticContextBuilder:
    """Construct context only. It never invokes models, tools or executors."""

    def __init__(
        self,
        capability_registry: CapabilityRegistry,
        *,
        mission_store: MissionStateStore | None = None,
        task_profiles: TaskProfileRegistry | None = None,
        workspace_inspector: WorkspaceInspector | None = None,
        ranker: DeterministicContextRanker | None = None,
        compressor: DeterministicContextCompressor | None = None,
        snapshot_factory: SemanticSnapshotFactory | None = None,
        validator: SemanticContextValidator | None = None,
        serializer: SemanticContextSerializer | None = None,
        telemetry: SemanticContextTelemetry | None = None,
    ):
        self.capability_registry = capability_registry
        self.mission_store = mission_store
        self.task_profiles = (
            task_profiles or create_default_task_profile_registry()
        )
        self.workspace_inspector = workspace_inspector or WorkspaceInspector()
        self.ranker = ranker or DeterministicContextRanker()
        self.compressor = compressor or DeterministicContextCompressor()
        self.snapshot_factory = snapshot_factory or SemanticSnapshotFactory()
        self.validator = validator or SemanticContextValidator()
        self.serializer = serializer or SemanticContextSerializer()
        self.telemetry = telemetry or SemanticContextTelemetry()

    def build(
        self,
        configuration: BuilderConfiguration,
    ) -> SemanticSnapshot:
        started = time.perf_counter()
        mission_store = self._mission_store(configuration)
        mission = MissionContextReader(mission_store).read(configuration)
        task_profile = self.task_profiles.get(
            configuration.task_profile_name
        )
        workspace = self.workspace_inspector.inspect(
            configuration,
            mission_terms=self._mission_terms(mission),
        )
        capabilities = CapabilityContextReader(
            self.capability_registry
        ).read(configuration)
        items, task_profile_hash = self._context_items(
            mission=mission,
            workspace=workspace,
            capabilities=capabilities,
            task_profile=task_profile,
            benchmark_configuration=(
                configuration.benchmark_configuration
            ),
        )
        ranking = self.ranker.rank(
            items,
            mission=mission,
            task_profile=task_profile,
            relevant_paths=configuration.relevant_paths,
        )
        compressed = self.compressor.compress(
            items,
            ranking,
            configuration,
        )
        source_hashes = {
            "mission_state": mission.source_sha256,
            "workspace": workspace.workspace.source_sha256,
            "documents": workspace.documents.source_sha256,
            "capability_registry": capabilities.source_sha256,
            "task_profile": task_profile_hash,
            "benchmark_configuration": sha256_json(
                configuration.benchmark_configuration
            ),
        }
        source_counts = Counter(
            item.source.value for item in compressed.items
        )
        statistics = {
            "candidate_items": len(items),
            "selected_items": len(compressed.items),
            "rejected_items": len(compressed.result.rejected),
            "duplicate_items": compressed.result.duplicate_items,
            "original_chars": compressed.result.original_chars,
            "final_chars": compressed.result.final_chars,
            "workspace_files_considered": (
                workspace.workspace.files_considered
            ),
            "workspace_files_rejected": (
                workspace.workspace.files_rejected
            ),
            "workspace_traversal_truncated": (
                workspace.workspace.traversal_truncated
            ),
            "source_counts": dict(sorted(source_counts.items())),
        }
        snapshot = self.snapshot_factory.create(
            generated_at=self._generated_at(
                mission,
                workspace,
                capabilities,
            ),
            configuration=configuration,
            mission=mission,
            workspace=workspace.workspace,
            capabilities=capabilities,
            documents=workspace.documents,
            items=compressed.items,
            ranking=compressed.ranking,
            compression=compressed.result,
            source_hashes=source_hashes,
            statistics=statistics,
        )
        self.validator.validate_or_raise(snapshot)
        serialized = self.serializer.serialize(snapshot)
        self.telemetry.record_build(
            duration_ms=(time.perf_counter() - started) * 1000,
            items_considered=len(items),
            items_rejected=len(compressed.result.rejected),
            duplicate_items=compressed.result.duplicate_items,
            ranked_items=len(compressed.ranking),
            source_counts=dict(source_counts),
            final_chars=compressed.result.final_chars,
            final_bytes=len(serialized.encode("utf-8")),
            snapshot_version=snapshot.snapshot_version,
        )
        return snapshot

    def _mission_store(
        self,
        configuration: BuilderConfiguration,
    ) -> MissionStateStore:
        if self.mission_store is None:
            return MissionStateStore(configuration.workspace_root)
        expected = os.path.realpath(
            os.path.abspath(configuration.workspace_root)
        )
        actual = os.path.realpath(
            os.path.abspath(self.mission_store.workspace_root)
        )
        if expected != actual:
            raise ValueError(
                "MissionStateStore workspace_root does not match configuration."
            )
        return self.mission_store

    def _context_items(
        self,
        *,
        mission: MissionContext,
        workspace: WorkspaceInspection,
        capabilities: CapabilityContext,
        task_profile: TaskProfile,
        benchmark_configuration: Mapping[str, Any],
    ) -> tuple[tuple[ContextItem, ...], str]:
        items: list[ContextItem] = []
        mission_payload = {
            "project_id": mission.project_id,
            "mission_id": mission.mission_id,
            "title": mission.title,
            "objective": mission.objective,
            "description": mission.description,
            "status": mission.status,
            "current_phase": mission.current_phase,
            "progress": mission.progress,
            "eligible_work_packages": mission.eligible_work_packages,
        }
        items.append(
            self._item(
                source=ContextSource.MISSION_STATE,
                kind=ContextKind.MISSION,
                title=mission.title or mission.mission_id,
                content=canonical_json(mission_payload),
                source_path=f"mission/{mission.mission_id}",
                references=(f"mission:{mission.mission_id}",),
                observed_at=mission.updated_at or EPOCH_TIMESTAMP,
                priority=100,
            )
        )
        for value in mission.work_packages:
            work_package_id = str(value.get("work_package_id") or "")
            references = [f"work_package:{work_package_id}"]
            references.extend(
                f"work_package:{item}"
                for item in value.get("dependencies") or ()
            )
            items.append(
                self._item(
                    source=ContextSource.MISSION_STATE,
                    kind=ContextKind.WORK_PACKAGE,
                    title=str(value.get("title") or work_package_id),
                    content=canonical_json(value),
                    source_path=(
                        f"mission/work_packages/{work_package_id}"
                    ),
                    references=tuple(references),
                    observed_at=str(
                        value.get("updated_at")
                        or value.get("created_at")
                        or EPOCH_TIMESTAMP
                    ),
                    priority=_bounded_priority(value.get("priority"), 80),
                )
            )
        for value in mission.deliverables:
            deliverable_id = str(value.get("deliverable_id") or "")
            references = [
                f"deliverable:{deliverable_id}",
                f"work_package:{value.get('work_package_id')}",
            ]
            references.extend(
                str(item)
                for item in value.get("artifact_refs") or ()
            )
            items.append(
                self._item(
                    source=ContextSource.MISSION_STATE,
                    kind=ContextKind.DELIVERABLE,
                    title=str(value.get("name") or deliverable_id),
                    content=canonical_json(value),
                    source_path=(
                        f"mission/deliverables/{deliverable_id}"
                    ),
                    references=tuple(references),
                    observed_at=str(
                        value.get("updated_at")
                        or value.get("created_at")
                        or EPOCH_TIMESTAMP
                    ),
                    priority=75,
                )
            )
        for value in mission.evidence:
            evidence_id = str(value.get("evidence_id") or "")
            references = [
                f"evidence:{evidence_id}",
                f"work_package:{value.get('work_package_id')}",
            ]
            if value.get("deliverable_id"):
                references.append(
                    f"deliverable:{value.get('deliverable_id')}"
                )
            if value.get("source_ref"):
                references.append(str(value.get("source_ref")))
            items.append(
                self._item(
                    source=ContextSource.MISSION_STATE,
                    kind=ContextKind.EVIDENCE,
                    title=str(
                        value.get("description")
                        or value.get("kind")
                        or evidence_id
                    ),
                    content=canonical_json(value),
                    source_path=f"mission/evidence/{evidence_id}",
                    references=tuple(references),
                    observed_at=str(
                        value.get("created_at") or EPOCH_TIMESTAMP
                    ),
                    priority=78,
                )
            )
        for value in mission.acceptance_criteria:
            criterion_id = str(value.get("criterion_id") or "")
            references = [f"criterion:{criterion_id}"]
            references.extend(
                f"evidence:{item}"
                for item in value.get("evidence_refs") or ()
            )
            items.append(
                self._item(
                    source=ContextSource.MISSION_STATE,
                    kind=ContextKind.ACCEPTANCE_CRITERION,
                    title=str(
                        value.get("description") or criterion_id
                    ),
                    content=canonical_json(value),
                    source_path=(
                        f"mission/criteria/{criterion_id}"
                    ),
                    references=tuple(references),
                    observed_at=str(
                        value.get("updated_at")
                        or value.get("created_at")
                        or EPOCH_TIMESTAMP
                    ),
                    priority=85 if value.get("required", True) else 60,
                )
            )

        workspace_payload = {
            "project_id": workspace.workspace.project_id,
            "project_name": workspace.workspace.project_name,
            "root_path": workspace.workspace.root_path,
            "stack": workspace.workspace.stack,
            "frameworks": workspace.workspace.frameworks,
            "package_managers": workspace.workspace.package_managers,
            "entrypoints": workspace.workspace.entrypoints,
            "source_roots": workspace.workspace.source_roots,
            "languages": workspace.workspace.languages,
            "dependencies": workspace.workspace.dependencies,
            "configurations": workspace.workspace.configurations,
            "tests": workspace.workspace.tests,
            "latest_changes": workspace.workspace.latest_changes,
        }
        items.append(
            self._item(
                source=ContextSource.WORKSPACE,
                kind=ContextKind.WORKSPACE_METADATA,
                title=workspace.workspace.project_name,
                content=canonical_json(workspace_payload),
                source_path=workspace.workspace.root_path,
                references=tuple(
                    f"file:{item}"
                    for item in workspace.workspace.entrypoints
                ),
                observed_at=workspace.workspace.observed_at,
                priority=72,
            )
        )
        for value in workspace.contents:
            kind = {
                "configuration": ContextKind.CONFIGURATION,
                "document": ContextKind.DOCUMENT,
                "test": ContextKind.TEST_FILE,
            }.get(value.category, ContextKind.SOURCE_FILE)
            items.append(
                self._item(
                    source=ContextSource.WORKSPACE,
                    kind=kind,
                    title=value.path,
                    content=value.content,
                    source_path=value.path,
                    references=(f"file:{value.path}",),
                    observed_at=value.observed_at,
                    priority=value.priority,
                    content_sha256=value.content_sha256,
                )
            )

        capability_overview = {
            "registry_version": capabilities.registry_version,
            "registry_snapshot_version": (
                capabilities.registry_snapshot_version
            ),
            "model_name": capabilities.model_name,
            "configuration_hash": capabilities.configuration_hash,
            "limitations": capabilities.limitations,
            "last_validation": capabilities.last_validation,
        }
        items.append(
            self._item(
                source=ContextSource.CAPABILITY_REGISTRY,
                kind=ContextKind.CAPABILITY,
                title=f"Capabilities for {capabilities.model_name}",
                content=canonical_json(capability_overview),
                source_path="capability_registry/model_profile",
                references=(),
                observed_at=(
                    capabilities.last_validation or EPOCH_TIMESTAMP
                ),
                priority=58,
            )
        )
        for value in capabilities.capabilities:
            items.append(
                self._item(
                    source=ContextSource.CAPABILITY_REGISTRY,
                    kind=ContextKind.CAPABILITY,
                    title=value.capability_id,
                    content=canonical_json(value),
                    source_path=(
                        f"capability_registry/{value.capability_id}"
                    ),
                    references=(
                        f"capability:{value.capability_id}",
                        *value.evidence_references,
                    ),
                    observed_at=value.last_verified or EPOCH_TIMESTAMP,
                    priority=55,
                )
            )
        for value in capabilities.compatibility:
            items.append(
                self._item(
                    source=ContextSource.CAPABILITY_REGISTRY,
                    kind=ContextKind.COMPATIBILITY,
                    title=value.target,
                    content=canonical_json(value),
                    source_path=(
                        f"capability_registry/compatibility/{value.target}"
                    ),
                    references=tuple(
                        f"capability:{item}"
                        for item in value.requirements
                    ),
                    observed_at=(
                        capabilities.last_validation or EPOCH_TIMESTAMP
                    ),
                    priority=52,
                )
            )

        task_profile_content = canonical_json(task_profile.to_dict())
        items.append(
            self._item(
                source=ContextSource.TASK_PROFILE,
                kind=ContextKind.TASK_PROFILE,
                title=task_profile.name,
                content=task_profile_content,
                source_path=f"task_profiles/{task_profile.name}",
                references=(f"task_profile:{task_profile.name}",),
                observed_at=EPOCH_TIMESTAMP,
                priority=65,
            )
        )
        benchmark_content = canonical_json(benchmark_configuration)
        items.append(
            self._item(
                source=ContextSource.BENCHMARK_CONFIGURATION,
                kind=ContextKind.BENCHMARK_CONFIGURATION,
                title="Benchmark configuration",
                content=benchmark_content,
                source_path="benchmark/configuration",
                references=(),
                observed_at=EPOCH_TIMESTAMP,
                priority=40,
            )
        )
        return tuple(items), sha256_text(task_profile_content)

    @staticmethod
    def _item(
        *,
        source: ContextSource,
        kind: ContextKind,
        title: str,
        content: str,
        source_path: str,
        references: tuple[str, ...],
        observed_at: str,
        priority: int,
        content_sha256: str = "",
    ) -> ContextItem:
        seed = sha256_json({
            "source": source.value,
            "kind": kind.value,
            "source_path": source_path,
            "title": title,
            "content_sha256": content_sha256 or sha256_text(content),
        })
        return ContextItem(
            item_id=f"ctx:{seed[:24]}",
            source=source,
            kind=kind,
            title=title,
            content=content,
            source_path=source_path,
            references=references,
            observed_at=observed_at or EPOCH_TIMESTAMP,
            priority=priority,
            content_sha256=content_sha256,
        )

    @staticmethod
    def _mission_terms(mission: MissionContext) -> tuple[str, ...]:
        values = [
            mission.title,
            mission.objective,
            mission.description,
            mission.current_phase,
        ]
        values.extend(
            str(item.get("title") or "")
            for item in mission.work_packages
        )
        return tuple(value for value in values if value)

    @staticmethod
    def _generated_at(
        mission: MissionContext,
        workspace: WorkspaceInspection,
        capabilities: CapabilityContext,
    ) -> str:
        values = (
            mission.updated_at,
            workspace.workspace.observed_at,
            capabilities.last_validation,
        )
        parsed: list[datetime] = []
        for value in values:
            try:
                parsed.append(
                    datetime.fromisoformat(
                        str(value).replace("Z", "+00:00")
                    )
                )
            except (TypeError, ValueError):
                continue
        if not parsed:
            return EPOCH_TIMESTAMP
        latest = max(
            (
                item
                if item.tzinfo is not None
                else item.replace(tzinfo=timezone.utc)
            )
            for item in parsed
        )
        return latest.astimezone(timezone.utc).isoformat()


def _bounded_priority(value: Any, default: int) -> int:
    try:
        return max(-100, min(100, int(value)))
    except (TypeError, ValueError):
        return default
