from __future__ import annotations

import re
from collections import Counter
from pathlib import PurePosixPath

from backend.semantic_context.contracts import (
    SEMANTIC_CONTEXT_VERSION,
    ContextSource,
    SemanticSnapshot,
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
    sha256_json,
    sha256_text,
)
from backend.semantic_context.snapshot import semantic_snapshot_seed


REFERENCE_PATTERN = re.compile(r"^([a-z_]+):(.+)$")
PATH_REFERENCE_SCHEMES = {
    "benchmark",
    "coding_session",
    "experiment",
    "file",
    "obsidian",
    "project_context",
    "source",
    "validation",
}
IDENTIFIER_REFERENCE_SCHEMES = {
    "capability",
    "criterion",
    "deliverable",
    "evidence",
    "mission",
    "task_profile",
    "work_package",
}


class SemanticContextValidationError(Exception):
    pass


class SemanticContextValidator:
    def validate(self, snapshot: SemanticSnapshot) -> ValidationResult:
        issues: list[ValidationIssue] = []
        self._identity(snapshot, issues)
        self._limits(snapshot, issues)
        self._items(snapshot, issues)
        self._ranking(snapshot, issues)
        self._sources(snapshot, issues)
        self._integrity(snapshot, issues)
        return ValidationResult(
            valid=not any(
                issue.severity is ValidationSeverity.ERROR
                for issue in issues
            ),
            issues=tuple(issues),
        )

    def validate_or_raise(
        self,
        snapshot: SemanticSnapshot,
    ) -> ValidationResult:
        result = self.validate(snapshot)
        if not result.valid:
            details = "; ".join(
                f"{item.code}@{item.location}: {item.message}"
                for item in result.issues
                if item.severity is ValidationSeverity.ERROR
            )
            raise SemanticContextValidationError(details)
        return result

    def _identity(
        self,
        snapshot: SemanticSnapshot,
        issues: list[ValidationIssue],
    ) -> None:
        if snapshot.builder_version != SEMANTIC_CONTEXT_VERSION:
            self._error(
                issues,
                "BUILDER_VERSION_INVALID",
                "Snapshot builder version is not supported.",
                "builder_version",
            )
        expected_version = (
            f"{SEMANTIC_CONTEXT_VERSION}-"
            f"{semantic_snapshot_seed(
                generated_at=snapshot.generated_at,
                configuration=snapshot.configuration,
                items=snapshot.items,
                ranking=snapshot.ranking,
                compression=snapshot.compression,
                source_hashes=snapshot.source_hashes,
            )[:16]}"
        )
        if snapshot.snapshot_version != expected_version:
            self._error(
                issues,
                "SNAPSHOT_VERSION_INVALID",
                "Snapshot version does not match its deterministic inputs.",
                "snapshot_version",
            )
        identities = {
            snapshot.configuration.project_id,
            snapshot.mission.project_id,
            snapshot.workspace.project_id,
        }
        if len(identities) != 1:
            self._error(
                issues,
                "PROJECT_ID_MISMATCH",
                "Configuration, mission and workspace project ids differ.",
                "project_id",
            )
        if (
            snapshot.configuration.mission_id
            != snapshot.mission.mission_id
        ):
            self._error(
                issues,
                "MISSION_ID_MISMATCH",
                "Configuration and mission ids differ.",
                "mission_id",
            )
        if (
            snapshot.configuration.model_name
            != snapshot.capabilities.model_name
        ):
            self._error(
                issues,
                "MODEL_ID_MISMATCH",
                "Configuration and capability model names differ.",
                "model_name",
            )

    def _limits(
        self,
        snapshot: SemanticSnapshot,
        issues: list[ValidationIssue],
    ) -> None:
        configuration = snapshot.configuration
        if len(snapshot.items) > configuration.max_items:
            self._error(
                issues,
                "ITEM_LIMIT_EXCEEDED",
                "Context package exceeds max_items.",
                "items",
            )
        chars = sum(len(item.content) for item in snapshot.items)
        if chars > configuration.max_chars:
            self._error(
                issues,
                "CHAR_LIMIT_EXCEEDED",
                "Context package exceeds max_chars.",
                "items",
            )
        for item in snapshot.items:
            if len(item.content) > configuration.max_item_chars:
                self._error(
                    issues,
                    "ITEM_CHAR_LIMIT_EXCEEDED",
                    "Context item exceeds max_item_chars.",
                    f"items.{item.item_id}",
                )
        if snapshot.compression.final_chars != chars:
            self._error(
                issues,
                "COMPRESSION_SIZE_MISMATCH",
                "Compression final_chars does not match selected content.",
                "compression.final_chars",
            )

    def _items(
        self,
        snapshot: SemanticSnapshot,
        issues: list[ValidationIssue],
    ) -> None:
        ids = [item.item_id for item in snapshot.items]
        hashes = [item.content_sha256 for item in snapshot.items]
        for value, count in Counter(ids).items():
            if count > 1:
                self._error(
                    issues,
                    "DUPLICATE_ITEM_ID",
                    "Context item id is duplicated.",
                    f"items.{value}",
                )
        for value, count in Counter(hashes).items():
            if count > 1:
                self._error(
                    issues,
                    "DUPLICATE_CONTENT",
                    "Duplicate content survived compression.",
                    f"items.{value}",
                )
        for item in snapshot.items:
            if sha256_text(item.content) != item.content_sha256:
                self._error(
                    issues,
                    "ITEM_HASH_MISMATCH",
                    "Context item content hash is invalid.",
                    f"items.{item.item_id}.content_sha256",
                )
            for reference in item.references:
                if not self._valid_reference(reference):
                    self._error(
                        issues,
                        "REFERENCE_INVALID",
                        f"Invalid context reference: {reference}",
                        f"items.{item.item_id}.references",
                    )

    def _ranking(
        self,
        snapshot: SemanticSnapshot,
        issues: list[ValidationIssue],
    ) -> None:
        item_ids = tuple(item.item_id for item in snapshot.items)
        ranking_ids = tuple(item.item_id for item in snapshot.ranking)
        if item_ids != ranking_ids:
            self._error(
                issues,
                "RANKING_ITEM_ORDER_MISMATCH",
                "Items and ranking order differ.",
                "ranking",
            )
        if ranking_ids != snapshot.compression.selected_item_ids:
            self._error(
                issues,
                "COMPRESSION_ITEM_ORDER_MISMATCH",
                "Compression selected ids and item order differ.",
                "compression.selected_item_ids",
            )
        expected_ranks = tuple(range(1, len(snapshot.ranking) + 1))
        actual_ranks = tuple(item.rank for item in snapshot.ranking)
        if actual_ranks != expected_ranks:
            self._error(
                issues,
                "RANK_SEQUENCE_INVALID",
                "Ranking sequence must be contiguous and one-based.",
                "ranking",
            )
        totals = tuple(item.total for item in snapshot.ranking)
        if totals != tuple(sorted(totals, reverse=True)):
            self._error(
                issues,
                "RANK_ORDER_INVALID",
                "Ranking totals are not descending.",
                "ranking",
            )

    def _sources(
        self,
        snapshot: SemanticSnapshot,
        issues: list[ValidationIssue],
    ) -> None:
        task_profile_items = tuple(
            item
            for item in snapshot.items
            if item.source is ContextSource.TASK_PROFILE
        )
        expected = {
            "mission_state": snapshot.mission.source_sha256,
            "workspace": snapshot.workspace.source_sha256,
            "documents": snapshot.documents.source_sha256,
            "capability_registry": snapshot.capabilities.source_sha256,
            "task_profile": (
                sha256_text(task_profile_items[0].content)
                if len(task_profile_items) == 1
                else ""
            ),
            "benchmark_configuration": sha256_json(
                snapshot.configuration.benchmark_configuration
            ),
        }
        if len(task_profile_items) != 1:
            self._error(
                issues,
                "TASK_PROFILE_CONTEXT_INVALID",
                "Exactly one TaskProfile context item is required.",
                "items",
            )
        for name in expected:
            if name not in snapshot.source_hashes:
                self._error(
                    issues,
                    "SOURCE_HASH_MISSING",
                    f"Required source hash is missing: {name}",
                    f"source_hashes.{name}",
                )
        for name in (
            "mission_state",
            "workspace",
            "documents",
            "capability_registry",
            "task_profile",
            "benchmark_configuration",
        ):
            if (
                name in snapshot.source_hashes
                and snapshot.source_hashes[name] != expected[name]
            ):
                self._error(
                    issues,
                    "SOURCE_HASH_MISMATCH",
                    f"Source hash does not match context: {name}",
                    f"source_hashes.{name}",
                )

    def _integrity(
        self,
        snapshot: SemanticSnapshot,
        issues: list[ValidationIssue],
    ) -> None:
        if snapshot.computed_content_sha256() != snapshot.content_sha256:
            self._error(
                issues,
                "SNAPSHOT_HASH_MISMATCH",
                "Snapshot content hash is invalid.",
                "content_sha256",
            )

    @staticmethod
    def _valid_reference(value: str) -> bool:
        match = REFERENCE_PATTERN.fullmatch(str(value or ""))
        if match is None:
            return False
        scheme, target = match.groups()
        if scheme in IDENTIFIER_REFERENCE_SCHEMES:
            return bool(target.strip()) and "\x00" not in target
        if scheme not in PATH_REFERENCE_SCHEMES:
            return False
        normalized = target.replace("\\", "/")
        path = PurePosixPath(normalized)
        return (
            bool(normalized)
            and not path.is_absolute()
            and ".." not in path.parts
            and "\x00" not in normalized
            and not re.match(r"^[A-Za-z]:/", normalized)
        )

    @staticmethod
    def _error(
        issues: list[ValidationIssue],
        code: str,
        message: str,
        location: str,
    ) -> None:
        issues.append(
            ValidationIssue(
                code=code,
                message=message,
                severity=ValidationSeverity.ERROR,
                location=location,
            )
        )
