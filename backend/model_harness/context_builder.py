from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from backend.model_harness.contracts import (
    ContextDecision,
    ContextItem,
    TaskContext,
)


AUTO_EXCLUDED_CONTEXT_KINDS = {
    "full_history",
    "full_mission",
    "full_project",
    "full_vector_store",
    "full_workspace",
}


@dataclass(frozen=True)
class ContextCandidate:
    source: str
    kind: str
    content: str
    relevance_score: float = 0.0
    explicitly_requested: bool = False
    sensitive: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def content_sha256(self) -> str:
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ContextBuildRequest:
    task_summary: str
    candidates: tuple[ContextCandidate, ...] = ()
    allowed_kinds: tuple[str, ...] = ()
    max_items: int = 12
    max_chars: int = 60_000
    include_sensitive: bool = False

    def __post_init__(self) -> None:
        if self.max_items < 0 or self.max_chars < 0:
            raise ValueError("Limites de contexto nao podem ser negativos.")


class ContextBuilder:
    """Selects only caller-supplied context and records every decision."""

    def build(self, request: ContextBuildRequest) -> TaskContext:
        allowed = set(request.allowed_kinds)
        ordered = sorted(
            request.candidates,
            key=lambda item: (
                not item.explicitly_requested,
                -float(item.relevance_score),
                item.kind,
                item.source,
                item.content_sha256,
            ),
        )
        selected: list[ContextItem] = []
        decisions: list[ContextDecision] = []
        used = 0
        for candidate in ordered:
            reason = self._exclusion_reason(candidate, request, allowed)
            if reason is None and len(selected) >= request.max_items:
                reason = "item_limit_reached"
            if reason is None and used + len(candidate.content) > request.max_chars:
                reason = "character_budget_exceeded"
            if reason is not None:
                decisions.append(self._decision(candidate, False, reason))
                continue
            inclusion_reason = (
                "explicitly_requested"
                if candidate.explicitly_requested
                else f"relevance_score={candidate.relevance_score:.3f}"
            )
            selected.append(ContextItem(
                source=candidate.source,
                kind=candidate.kind,
                content=candidate.content,
                inclusion_reason=inclusion_reason,
                relevance_score=float(candidate.relevance_score),
                metadata=dict(candidate.metadata),
            ))
            used += len(candidate.content)
            decisions.append(
                self._decision(candidate, True, inclusion_reason)
            )
        return TaskContext(
            items=tuple(selected),
            decisions=tuple(decisions),
            total_chars=used,
        )

    @staticmethod
    def from_candidates(
        task_summary: str,
        candidates: Iterable[ContextCandidate],
        **kwargs,
    ) -> TaskContext:
        return ContextBuilder().build(ContextBuildRequest(
            task_summary=task_summary,
            candidates=tuple(candidates),
            **kwargs,
        ))

    @staticmethod
    def _exclusion_reason(
        candidate: ContextCandidate,
        request: ContextBuildRequest,
        allowed: set[str],
    ) -> str | None:
        if not candidate.content:
            return "empty_content"
        if candidate.sensitive and not request.include_sensitive:
            return "sensitive_context_not_authorized"
        if allowed and candidate.kind not in allowed:
            return "context_kind_not_allowed"
        if (
            candidate.kind in AUTO_EXCLUDED_CONTEXT_KINDS
            and not candidate.explicitly_requested
        ):
            return "bulk_context_requires_explicit_request"
        return None

    @staticmethod
    def _decision(
        candidate: ContextCandidate,
        included: bool,
        reason: str,
    ) -> ContextDecision:
        return ContextDecision(
            source=candidate.source,
            kind=candidate.kind,
            included=included,
            reason=reason,
            content_sha256=candidate.content_sha256,
            size_chars=len(candidate.content),
        )
