from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Mapping

from backend.model_harness.contracts import ProgressCondition


@dataclass(frozen=True)
class ProgressEvent:
    kind: str
    signature: str
    outcome: str
    sequence: int


@dataclass(frozen=True)
class ProgressSnapshot:
    event_count: int
    distinct_inputs: int
    distinct_outputs: int
    conditions: tuple[ProgressCondition, ...]
    latest_outcome: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["conditions"] = [
            item.value for item in self.conditions
        ]
        return payload


class ProgressTracker:
    """Stores hashes and outcomes, never prompts or generated content."""

    def __init__(self, repeated_threshold: int = 2):
        if repeated_threshold < 2:
            raise ValueError("repeated_threshold deve ser pelo menos 2.")
        self.repeated_threshold = repeated_threshold
        self.events: list[ProgressEvent] = []

    def record_input(self, fingerprint: str) -> ProgressSnapshot:
        return self._record("input", fingerprint, "OBSERVED")

    def record_output(self, raw_text: str) -> ProgressSnapshot:
        return self._record(
            "output",
            self._hash(raw_text),
            "PRODUCED",
        )

    def record_tool_call(
        self,
        name: str,
        arguments: Mapping[str, Any],
    ) -> ProgressSnapshot:
        signature = self._hash(json.dumps(
            {"name": name, "arguments": dict(arguments)},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ))
        return self._record("tool_call", signature, "CALLED")

    def record_failure(self, code: str) -> ProgressSnapshot:
        return self._record("failure", self._hash(code), "FAILED")

    def record_action(self, action: str, outcome: str) -> ProgressSnapshot:
        return self._record(
            "action",
            self._hash(action),
            str(outcome or "OBSERVED"),
        )

    def snapshot(self) -> ProgressSnapshot:
        conditions: list[ProgressCondition] = []
        if self._has_repeated("output"):
            conditions.append(ProgressCondition.REPEATED_REASONING)
        if self._has_repeated("tool_call"):
            conditions.append(ProgressCondition.REPEATED_TOOL_CALLS)
        if self._has_repeated("failure"):
            conditions.append(ProgressCondition.REPEATED_FAILURES)
        input_events = [
            item for item in self.events if item.kind == "input"
        ]
        output_events = [
            item for item in self.events if item.kind == "output"
        ]
        if (
            len(input_events) >= self.repeated_threshold
            and len({item.signature for item in input_events}) == 1
            and len({item.signature for item in output_events})
            <= 1
        ):
            conditions.append(ProgressCondition.NO_PROGRESS)
        return ProgressSnapshot(
            event_count=len(self.events),
            distinct_inputs=len({
                item.signature
                for item in input_events
            }),
            distinct_outputs=len({
                item.signature
                for item in output_events
            }),
            conditions=tuple(dict.fromkeys(conditions)),
            latest_outcome=(
                self.events[-1].outcome if self.events else ""
            ),
        )

    def _record(
        self,
        kind: str,
        signature: str,
        outcome: str,
    ) -> ProgressSnapshot:
        self.events.append(ProgressEvent(
            kind=kind,
            signature=signature,
            outcome=outcome,
            sequence=len(self.events) + 1,
        ))
        return self.snapshot()

    def _has_repeated(self, kind: str) -> bool:
        values = [
            item.signature for item in self.events if item.kind == kind
        ]
        if len(values) < self.repeated_threshold:
            return False
        return any(
            values.count(signature) >= self.repeated_threshold
            for signature in set(values)
        )

    @staticmethod
    def _hash(value: str) -> str:
        return hashlib.sha256(
            str(value or "").encode("utf-8")
        ).hexdigest()
