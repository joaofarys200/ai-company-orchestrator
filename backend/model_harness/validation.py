from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from typing import Any

from jsonschema import Draft202012Validator

from backend.model_harness.contracts import (
    ExpectedOutput,
    ModelRequest,
    ModelRoute,
    OutputFormat,
    ProviderResult,
    ValidationIssue,
    ValidationResult,
    ValidationStage,
    ValidationStatus,
)


ValidationCallback = Callable[
    [Any, ModelRequest, ModelRoute],
    bool | tuple[bool, str] | ValidationIssue,
]


@dataclass(frozen=True)
class ValidationRule:
    stage: ValidationStage
    code: str
    callback: ValidationCallback
    location: str = "$"
    recoverable: bool = True


class ModelValidationPipeline:
    def __init__(self, rules: Iterable[ValidationRule] | None = None):
        self.rules = tuple(rules or ())

    def validate(
        self,
        request: ModelRequest,
        route: ModelRoute,
        provider_result: ProviderResult,
        stages: tuple[str, ...],
        expected_output: ExpectedOutput,
    ) -> ValidationResult:
        if expected_output.defer_validation:
            return ValidationResult(
                status=ValidationStatus.DEFERRED,
                structured_output=None,
                delegated_to=expected_output.validation_owner,
            )
        configured = self._configured_stages(stages)
        completed: list[ValidationStage] = []
        issues: list[ValidationIssue] = []
        parsed: Any = provider_result.raw_text

        if ValidationStage.PARSING in configured:
            parsed, parsing_issues = self._parse(
                expected_output,
                provider_result,
            )
            completed.append(ValidationStage.PARSING)
            issues.extend(parsing_issues)
            if parsing_issues:
                return self._result(issues, parsed, completed)

        for stage in configured:
            if stage == ValidationStage.PARSING:
                continue
            stage_issues: list[ValidationIssue] = []
            if stage == ValidationStage.SCHEMA:
                stage_issues.extend(self._validate_schema(
                    parsed,
                    expected_output,
                ))
            elif stage == ValidationStage.ENUMS:
                stage_issues.extend(self._validate_enums(
                    parsed,
                    expected_output,
                ))
            elif stage == ValidationStage.REFERENCES:
                stage_issues.extend(self._validate_references(
                    parsed,
                    expected_output,
                ))
            elif stage == ValidationStage.COMPATIBILITY:
                stage_issues.extend(self._validate_compatibility(
                    request,
                    provider_result,
                    expected_output,
                ))
            stage_issues.extend(
                self._run_rules(stage, parsed, request, route)
            )
            completed.append(stage)
            issues.extend(stage_issues)
            if stage_issues:
                break
        return self._result(issues, parsed, completed)

    @staticmethod
    def _configured_stages(
        stages: tuple[str, ...],
    ) -> tuple[ValidationStage, ...]:
        result: list[ValidationStage] = []
        for item in stages:
            stage = ValidationStage(str(item).strip().upper())
            if stage not in result:
                result.append(stage)
        return tuple(result)

    @staticmethod
    def _parse(
        expected: ExpectedOutput,
        provider_result: ProviderResult,
    ) -> tuple[Any, list[ValidationIssue]]:
        if expected.format == OutputFormat.TEXT:
            return provider_result.raw_text, []
        if (
            expected.format == OutputFormat.TOOL_CALLS
            and provider_result.tool_calls
        ):
            return [asdict(item) for item in provider_result.tool_calls], []
        try:
            return json.loads(provider_result.raw_text), []
        except (TypeError, json.JSONDecodeError) as exc:
            return None, [ValidationIssue(
                stage=ValidationStage.PARSING,
                code="JSON_PARSE_FAILED",
                location="$",
                message=f"Output JSON invalido: {exc.msg if hasattr(exc, 'msg') else type(exc).__name__}.",
                recoverable=True,
            )]

    @staticmethod
    def _validate_schema(
        parsed: Any,
        expected: ExpectedOutput,
    ) -> list[ValidationIssue]:
        if expected.schema is None:
            return []
        validator = Draft202012Validator(dict(expected.schema))
        return [
            ValidationIssue(
                stage=ValidationStage.SCHEMA,
                code="JSON_SCHEMA_FAILED",
                location=(
                    "$"
                    + "".join(
                        f"[{part}]" if isinstance(part, int) else f".{part}"
                        for part in error.absolute_path
                    )
                ),
                message=error.message,
                recoverable=True,
            )
            for error in sorted(
                validator.iter_errors(parsed),
                key=lambda item: tuple(
                    str(part) for part in item.absolute_path
                ),
            )
        ]

    def _validate_enums(
        self,
        parsed: Any,
        expected: ExpectedOutput,
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        for constraint in expected.enum_constraints:
            found, value = self._resolve_path(
                parsed,
                constraint.field_path,
            )
            if not found or value not in constraint.allowed_values:
                issues.append(ValidationIssue(
                    stage=ValidationStage.ENUMS,
                    code="ENUM_VALUE_INVALID",
                    location=constraint.field_path,
                    message=(
                        "Valor ausente ou fora do enum permitido."
                    ),
                    recoverable=True,
                    details={
                        "allowed_values": list(
                            constraint.allowed_values
                        ),
                    },
                ))
        return issues

    def _validate_references(
        self,
        parsed: Any,
        expected: ExpectedOutput,
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        for constraint in expected.reference_constraints:
            found, value = self._resolve_path(
                parsed,
                constraint.field_path,
            )
            values = value if isinstance(value, list) else [value]
            empty_allowed = (
                constraint.allow_empty
                and value in ("", None, [])
            )
            valid = found and (
                empty_allowed
                or (
                    bool(value)
                    and all(
                        isinstance(item, str)
                        and item in constraint.allowed_references
                        for item in values
                    )
                )
            )
            if not valid:
                issues.append(ValidationIssue(
                    stage=ValidationStage.REFERENCES,
                    code="REFERENCE_INVALID",
                    location=constraint.field_path,
                    message="Referencia ausente ou nao autorizada.",
                    recoverable=True,
                    details={
                        "allowed_reference_count": len(
                            constraint.allowed_references
                        ),
                    },
                ))
        return issues

    @staticmethod
    def _validate_compatibility(
        request: ModelRequest,
        provider_result: ProviderResult,
        expected: ExpectedOutput,
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        if (
            expected.format == OutputFormat.TEXT
            and not provider_result.raw_text.strip()
        ):
            issues.append(ValidationIssue(
                stage=ValidationStage.COMPATIBILITY,
                code="EMPTY_MODEL_OUTPUT",
                location="$",
                message="O provider devolveu texto vazio.",
                recoverable=True,
            ))
        if expected.format == OutputFormat.TOOL_CALLS:
            allowed = set(request.allowed_tools)
            for index, call in enumerate(provider_result.tool_calls):
                if call.name not in allowed:
                    issues.append(ValidationIssue(
                        stage=ValidationStage.COMPATIBILITY,
                        code="TOOL_NOT_ALLOWED",
                        location=f"tool_calls[{index}].name",
                        message="O modelo selecionou uma tool nao autorizada.",
                        recoverable=False,
                    ))
        return issues

    def _run_rules(
        self,
        stage: ValidationStage,
        parsed: Any,
        request: ModelRequest,
        route: ModelRoute,
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        for rule in self.rules:
            if rule.stage != stage:
                continue
            result = rule.callback(parsed, request, route)
            if isinstance(result, ValidationIssue):
                if result.stage != stage:
                    raise ValueError(
                        "ValidationRule devolveu issue para outra fase."
                    )
                issues.append(result)
                continue
            if isinstance(result, tuple):
                passed, message = result
            else:
                passed, message = bool(result), "Regra nao satisfeita."
            if not passed:
                issues.append(ValidationIssue(
                    stage=stage,
                    code=rule.code,
                    location=rule.location,
                    message=str(message),
                    recoverable=rule.recoverable,
                ))
        return issues

    @staticmethod
    def _resolve_path(data: Any, field_path: str) -> tuple[bool, Any]:
        clean = str(field_path or "").strip()
        if clean in {"", "$"}:
            return True, data
        clean = clean.removeprefix("$.").removeprefix("$")
        parts = []
        for name, index in re.findall(
            r"(?:^|\.)([^.\[\]]+)|\[(\d+)\]",
            clean,
        ):
            parts.append(int(index) if index else name)
        current = data
        for part in parts:
            if isinstance(part, int):
                if not isinstance(current, list) or part >= len(current):
                    return False, None
                current = current[part]
            else:
                if not isinstance(current, dict) or part not in current:
                    return False, None
                current = current[part]
        return True, current

    @staticmethod
    def _result(
        issues: list[ValidationIssue],
        parsed: Any,
        completed: list[ValidationStage],
    ) -> ValidationResult:
        return ValidationResult(
            status=(
                ValidationStatus.FAILED
                if issues
                else ValidationStatus.PASSED
            ),
            issues=tuple(issues),
            structured_output=parsed,
            completed_stages=tuple(completed),
        )
