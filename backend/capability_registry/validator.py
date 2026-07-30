from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime
from pathlib import PurePosixPath

from backend.capability_registry.contracts import (
    CapabilityDefinition,
    CapabilityId,
    CapabilityRegistrySnapshot,
    CompatibilityRule,
    ModelCapabilityProfile,
    RegistryValidationIssue,
    RegistryValidationResult,
    ValidationSeverity,
)
from backend.capability_registry.exceptions import (
    CapabilityRegistryValidationError,
)


class CapabilityRegistryValidator:
    def validate(
        self,
        *,
        catalog: Mapping[CapabilityId, CapabilityDefinition],
        profiles: Iterable[ModelCapabilityProfile],
        rules: Iterable[CompatibilityRule],
        snapshot: CapabilityRegistrySnapshot | None = None,
    ) -> RegistryValidationResult:
        issues: list[RegistryValidationIssue] = []
        profile_values = tuple(profiles)
        rule_values = tuple(rules)
        self._validate_catalog(catalog, issues)
        self._validate_profiles(catalog, profile_values, issues)
        self._validate_rules(catalog, rule_values, issues)
        if snapshot is not None:
            self._validate_snapshot(snapshot, issues)
        return RegistryValidationResult(
            valid=not any(
                item.severity is ValidationSeverity.ERROR
                for item in issues
            ),
            issues=tuple(issues),
        )

    def validate_or_raise(self, **values) -> RegistryValidationResult:
        result = self.validate(**values)
        if not result.valid:
            details = "; ".join(
                f"{item.code}@{item.location}: {item.message}"
                for item in result.issues
                if item.severity is ValidationSeverity.ERROR
            )
            raise CapabilityRegistryValidationError(details)
        return result

    def _validate_catalog(
        self,
        catalog: Mapping[CapabilityId, CapabilityDefinition],
        issues: list[RegistryValidationIssue],
    ) -> None:
        missing = set(CapabilityId) - set(catalog)
        for capability_id in sorted(missing, key=lambda item: item.value):
            self._error(
                issues,
                "CATALOG_CAPABILITY_MISSING",
                f"Capability sem definicao: {capability_id.value}.",
                f"catalog.{capability_id.value}",
            )
        for capability_id, definition in catalog.items():
            if definition.id is not capability_id:
                self._error(
                    issues,
                    "CATALOG_ID_MISMATCH",
                    "A chave e o id da definicao nao coincidem.",
                    f"catalog.{capability_id.value}",
                )

    def _validate_profiles(
        self,
        catalog: Mapping[CapabilityId, CapabilityDefinition],
        profiles: tuple[ModelCapabilityProfile, ...],
        issues: list[RegistryValidationIssue],
    ) -> None:
        names = [profile.model_name for profile in profiles]
        if len(names) != len(set(names)):
            self._error(
                issues,
                "DUPLICATE_MODEL_PROFILE",
                "Existem perfis duplicados para o mesmo modelo.",
                "models",
            )
        for profile in profiles:
            location = f"models.{profile.model_name}"
            self._timestamp(profile.last_validation, location, issues)
            capability_ids = [item.id for item in profile.capabilities]
            if len(capability_ids) != len(set(capability_ids)):
                self._error(
                    issues,
                    "DUPLICATE_MODEL_CAPABILITY",
                    "O perfil contem capabilities duplicadas.",
                    f"{location}.capabilities",
                )
            for capability in profile.capabilities:
                cap_location = (
                    f"{location}.capabilities.{capability.id.value}"
                )
                if capability.id not in catalog:
                    self._error(
                        issues,
                        "UNKNOWN_PROFILE_CAPABILITY",
                        "Capability nao existe no catalogo.",
                        cap_location,
                    )
                if not capability.evidence:
                    self._error(
                        issues,
                        "CAPABILITY_WITHOUT_EVIDENCE",
                        "Capability de modelo nao tem benchmark evidence.",
                        cap_location,
                    )
                    continue
                latest = max(
                    capability.evidence,
                    key=lambda item: (
                        item.benchmark.timestamp,
                        item.benchmark.artifact,
                    ),
                )
                if capability.status is not latest.status:
                    self._error(
                        issues,
                        "CAPABILITY_STATUS_NOT_LATEST",
                        "Status nao corresponde a evidencia mais recente.",
                        cap_location,
                    )
                if capability.last_verified != latest.benchmark.timestamp:
                    self._error(
                        issues,
                        "CAPABILITY_TIMESTAMP_NOT_LATEST",
                        "last_verified nao corresponde a evidencia mais recente.",
                        cap_location,
                    )
                configuration_hashes = {
                    item.configuration_hash
                    for item in capability.configurations
                }
                for index, evidence in enumerate(capability.evidence):
                    evidence_location = f"{cap_location}.evidence.{index}"
                    if evidence.capability_id is not capability.id:
                        self._error(
                            issues,
                            "CAPABILITY_EVIDENCE_ID_MISMATCH",
                            "Evidence pertence a outra capability.",
                            evidence_location,
                        )
                    benchmark = evidence.benchmark
                    if (
                        benchmark.configuration_hash
                        not in configuration_hashes
                    ):
                        self._error(
                            issues,
                            "EVIDENCE_CONFIGURATION_MISSING",
                            "Configuracao da evidencia nao esta no perfil.",
                            evidence_location,
                        )
                    self._artifact_path(
                        benchmark.artifact,
                        evidence_location,
                        issues,
                    )
                    if benchmark.report_artifact:
                        self._artifact_path(
                            benchmark.report_artifact,
                            evidence_location,
                            issues,
                        )
                    for artifact in benchmark.artifact_hashes:
                        self._artifact_path(
                            artifact,
                            evidence_location,
                            issues,
                        )
                    self._timestamp(
                        benchmark.timestamp,
                        evidence_location,
                        issues,
                    )

    def _validate_rules(
        self,
        catalog: Mapping[CapabilityId, CapabilityDefinition],
        rules: tuple[CompatibilityRule, ...],
        issues: list[RegistryValidationIssue],
    ) -> None:
        targets = [rule.target for rule in rules]
        if len(targets) != len(set(targets)):
            self._error(
                issues,
                "DUPLICATE_COMPATIBILITY_RULE",
                "Existem regras duplicadas para o mesmo target.",
                "compatibility_rules",
            )
        for rule in rules:
            for requirement in rule.requirements:
                if requirement.capability_id not in catalog:
                    self._error(
                        issues,
                        "RULE_CAPABILITY_UNKNOWN",
                        "Regra referencia capability fora do catalogo.",
                        f"compatibility_rules.{rule.target.value}",
                    )

    def _validate_snapshot(
        self,
        snapshot: CapabilityRegistrySnapshot,
        issues: list[RegistryValidationIssue],
    ) -> None:
        if snapshot.computed_content_sha256() != snapshot.content_sha256:
            self._error(
                issues,
                "SNAPSHOT_HASH_MISMATCH",
                "content_sha256 nao corresponde ao snapshot.",
                "snapshot.content_sha256",
            )
        self._timestamp(snapshot.generated_at, "snapshot.generated_at", issues)

    def _artifact_path(
        self,
        value: str,
        location: str,
        issues: list[RegistryValidationIssue],
    ) -> None:
        path = PurePosixPath(str(value))
        if path.is_absolute() or ".." in path.parts:
            self._error(
                issues,
                "UNSAFE_EVIDENCE_ARTIFACT_PATH",
                "Artifact path deve ser relativo e sem traversal.",
                location,
            )

    def _timestamp(
        self,
        value: str,
        location: str,
        issues: list[RegistryValidationIssue],
    ) -> None:
        try:
            parsed = datetime.fromisoformat(
                str(value).replace("Z", "+00:00")
            )
        except ValueError:
            self._error(
                issues,
                "INVALID_TIMESTAMP",
                f"Timestamp invalido: {value!r}.",
                location,
            )
            return
        if parsed.utcoffset() is None:
            self._error(
                issues,
                "TIMESTAMP_WITHOUT_TIMEZONE",
                f"Timestamp sem timezone: {value!r}.",
                location,
            )

    @staticmethod
    def _error(
        issues: list[RegistryValidationIssue],
        code: str,
        message: str,
        location: str,
    ) -> None:
        issues.append(
            RegistryValidationIssue(
                code=code,
                message=message,
                severity=ValidationSeverity.ERROR,
                location=location,
            )
        )
