from __future__ import annotations

import re
from datetime import datetime

from backend.model_harness.profiles import TaskProfile
from backend.semantic_context.contracts import (
    ContextItem,
    ContextKind,
    ContextSource,
    MissionContext,
    RankingScore,
)


TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]{3,}")
WEIGHTS = {
    "recency": 0.12,
    "proximity": 0.16,
    "relevance": 0.24,
    "type_score": 0.14,
    "priority": 0.12,
    "task_profile": 0.12,
    "mission": 0.10,
}
TYPE_SCORES = {
    ContextKind.MISSION: 1.0,
    ContextKind.WORK_PACKAGE: 0.95,
    ContextKind.ACCEPTANCE_CRITERION: 0.90,
    ContextKind.EVIDENCE: 0.88,
    ContextKind.DELIVERABLE: 0.86,
    ContextKind.SOURCE_FILE: 0.84,
    ContextKind.TEST_FILE: 0.82,
    ContextKind.CONFIGURATION: 0.78,
    ContextKind.DOCUMENT: 0.76,
    ContextKind.CAPABILITY: 0.72,
    ContextKind.COMPATIBILITY: 0.70,
    ContextKind.TASK_PROFILE: 0.68,
    ContextKind.WORKSPACE_METADATA: 0.66,
    ContextKind.BENCHMARK_CONFIGURATION: 0.62,
}
PROFILE_KIND_SCORES = {
    "CODE_REASONING": {
        ContextKind.SOURCE_FILE: 1.0,
        ContextKind.TEST_FILE: 0.95,
        ContextKind.CONFIGURATION: 0.85,
        ContextKind.WORKSPACE_METADATA: 0.75,
    },
    "RESEARCH": {
        ContextKind.DOCUMENT: 1.0,
        ContextKind.EVIDENCE: 0.95,
        ContextKind.WORK_PACKAGE: 0.85,
    },
    "DOCUMENT": {
        ContextKind.DOCUMENT: 1.0,
        ContextKind.DELIVERABLE: 0.95,
        ContextKind.EVIDENCE: 0.90,
    },
    "DOCUMENT_REVIEW": {
        ContextKind.DOCUMENT: 1.0,
        ContextKind.ACCEPTANCE_CRITERION: 0.95,
        ContextKind.EVIDENCE: 0.90,
    },
    "MISSION_PLANNING": {
        ContextKind.MISSION: 1.0,
        ContextKind.WORK_PACKAGE: 0.98,
        ContextKind.DELIVERABLE: 0.90,
        ContextKind.ACCEPTANCE_CRITERION: 0.88,
    },
    "STRUCTURED_EXTRACTION": {
        ContextKind.CONFIGURATION: 0.95,
        ContextKind.DOCUMENT: 0.85,
        ContextKind.SOURCE_FILE: 0.80,
    },
}


class DeterministicContextRanker:
    def rank(
        self,
        items: tuple[ContextItem, ...],
        *,
        mission: MissionContext,
        task_profile: TaskProfile,
        relevant_paths: tuple[str, ...] = (),
    ) -> tuple[RankingScore, ...]:
        query_tokens = self._mission_tokens(mission)
        timestamps = {
            item.item_id: _timestamp_value(item.observed_at)
            for item in items
        }
        valid_timestamps = [
            value for value in timestamps.values() if value is not None
        ]
        oldest = min(valid_timestamps) if valid_timestamps else None
        newest = max(valid_timestamps) if valid_timestamps else None
        provisional: list[tuple[ContextItem, dict[str, float]]] = []
        for item in items:
            values = {
                "recency": _recency(
                    timestamps[item.item_id],
                    oldest,
                    newest,
                ),
                "proximity": self._proximity(item, relevant_paths),
                "relevance": self._relevance(item, query_tokens),
                "type_score": TYPE_SCORES.get(item.kind, 0.5),
                "priority": _clamp((item.priority + 100) / 200),
                "task_profile": self._profile_score(
                    item,
                    task_profile.name,
                ),
                "mission": self._mission_score(item, query_tokens),
            }
            values["total"] = round(
                sum(values[name] * WEIGHTS[name] for name in WEIGHTS),
                8,
            )
            provisional.append((item, values))
        provisional.sort(
            key=lambda pair: (
                -pair[1]["total"],
                pair[0].source.value,
                pair[0].kind.value,
                pair[0].item_id,
                pair[0].content_sha256,
            )
        )
        return tuple(
            RankingScore(
                item_id=item.item_id,
                recency=values["recency"],
                proximity=values["proximity"],
                relevance=values["relevance"],
                type_score=values["type_score"],
                priority=values["priority"],
                task_profile=values["task_profile"],
                mission=values["mission"],
                total=values["total"],
                rank=index,
            )
            for index, (item, values) in enumerate(provisional, start=1)
        )

    @staticmethod
    def _mission_tokens(mission: MissionContext) -> set[str]:
        values = [
            mission.title,
            mission.objective,
            mission.description,
            mission.current_phase,
        ]
        values.extend(
            str(item.get(field) or "")
            for item in mission.work_packages
            for field in ("title", "description", "type")
        )
        return {
            token.lower()
            for value in values
            for token in TOKEN_PATTERN.findall(value)
        }

    @staticmethod
    def _proximity(
        item: ContextItem,
        relevant_paths: tuple[str, ...],
    ) -> float:
        if not relevant_paths:
            return 0.55 if item.source is ContextSource.MISSION_STATE else 0.25
        if item.source_path in relevant_paths:
            return 1.0
        file_references = {
            value.split(":", 1)[1]
            for value in item.references
            if value.startswith("file:") and ":" in value
        }
        if file_references.intersection(relevant_paths):
            return 0.95
        for candidate in relevant_paths:
            if (
                item.source_path.startswith(f"{candidate}/")
                or candidate.startswith(f"{item.source_path}/")
            ):
                return 0.75
        return 0.2

    @staticmethod
    def _relevance(item: ContextItem, query_tokens: set[str]) -> float:
        if not query_tokens:
            return 0.0
        item_tokens = {
            token.lower()
            for token in TOKEN_PATTERN.findall(
                f"{item.title}\n{item.source_path}\n{item.content}"
            )
        }
        overlap = len(item_tokens.intersection(query_tokens))
        return round(_clamp(overlap / min(12, len(query_tokens))), 8)

    @staticmethod
    def _profile_score(item: ContextItem, profile_name: str) -> float:
        mapping = PROFILE_KIND_SCORES.get(profile_name, {})
        if item.kind in mapping:
            return mapping[item.kind]
        if item.kind is ContextKind.TASK_PROFILE:
            return 1.0
        return 0.45

    @staticmethod
    def _mission_score(
        item: ContextItem,
        query_tokens: set[str],
    ) -> float:
        if item.source is ContextSource.MISSION_STATE:
            return 1.0
        title_tokens = {
            token.lower()
            for token in TOKEN_PATTERN.findall(
                f"{item.title} {item.source_path}"
            )
        }
        if not query_tokens:
            return 0.0
        return round(
            _clamp(
                len(title_tokens.intersection(query_tokens))
                / min(5, len(query_tokens))
            ),
            8,
        )


def _timestamp_value(value: str) -> float | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except (AttributeError, OverflowError, TypeError, ValueError):
        return None


def _recency(
    value: float | None,
    oldest: float | None,
    newest: float | None,
) -> float:
    if value is None or oldest is None or newest is None:
        return 0.0
    if newest == oldest:
        return 1.0
    return round(_clamp((value - oldest) / (newest - oldest)), 8)


def _clamp(value: float) -> float:
    return min(1.0, max(0.0, float(value)))
