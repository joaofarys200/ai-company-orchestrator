from __future__ import annotations

import ast
import hashlib
import re
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
    """Selects caller-supplied context and provides AST structural outline fallback when budget is exceeded."""

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

            # Check if full content exceeds budget
            if reason is None and used + len(candidate.content) > request.max_chars:
                # Attempt AST structural outline fallback
                outline = self._extract_structural_outline(candidate)
                if outline and used + len(outline) <= request.max_chars:
                    inclusion_reason = f"ast_outline_budget_fallback (original_size={len(candidate.content)})"
                    selected.append(
                        ContextItem(
                            source=candidate.source,
                            kind="structural_outline",
                            content=outline,
                            inclusion_reason=inclusion_reason,
                            relevance_score=float(candidate.relevance_score),
                            metadata={
                                **dict(candidate.metadata),
                                "fallback": "ast_outline",
                                "original_chars": len(candidate.content),
                            },
                        )
                    )
                    used += len(outline)
                    decisions.append(self._decision(candidate, True, inclusion_reason))
                    continue
                else:
                    reason = "character_budget_exceeded"

            if reason is not None:
                decisions.append(self._decision(candidate, False, reason))
                continue

            inclusion_reason = (
                "explicitly_requested"
                if candidate.explicitly_requested
                else f"relevance_score={candidate.relevance_score:.3f}"
            )
            selected.append(
                ContextItem(
                    source=candidate.source,
                    kind=candidate.kind,
                    content=candidate.content,
                    inclusion_reason=inclusion_reason,
                    relevance_score=float(candidate.relevance_score),
                    metadata=dict(candidate.metadata),
                )
            )
            used += len(candidate.content)
            decisions.append(self._decision(candidate, True, inclusion_reason))

        return TaskContext(
            items=tuple(selected),
            decisions=tuple(decisions),
            total_chars=used,
        )

    @classmethod
    def _extract_structural_outline(cls, candidate: ContextCandidate) -> str:
        """Extracts AST outline for Python or regex symbols for JS/TS/MD/HTML."""
        src = candidate.source.lower()
        content = candidate.content

        # 1. Python AST Outline
        if src.endswith(".py") or "python" in candidate.kind.lower():
            try:
                tree = ast.parse(content)
                lines = [f"# [AST OUTLINE] Source: {candidate.source} (Large File Fallback)", ""]
                
                # Imports
                imports = []
                for node in ast.iter_child_nodes(tree):
                    if isinstance(node, ast.Import):
                        imports.append(f"import {', '.join(alias.name for alias in node.names)}")
                    elif isinstance(node, ast.ImportFrom):
                        module = node.module or ""
                        names = ", ".join(alias.name for alias in node.names)
                        imports.append(f"from {module} import {names}")
                
                if imports:
                    lines.append("## Imports:")
                    lines.extend(imports[:15])
                    lines.append("")

                # Classes & Methods
                classes = []
                for node in ast.iter_child_nodes(tree):
                    if isinstance(node, ast.ClassDef):
                        bases = ", ".join(ast.unparse(b) for b in node.bases) if node.bases else ""
                        bases_str = f"({bases})" if bases else ""
                        doc = ast.get_docstring(node)
                        doc_str = f"  # {doc.splitlines()[0]}" if doc else ""
                        classes.append(f"class {node.name}{bases_str}:{doc_str}")
                        
                        for item in node.body:
                            if isinstance(item, ast.FunctionDef) or isinstance(item, ast.AsyncFunctionDef):
                                prefix = "async def" if isinstance(item, ast.AsyncFunctionDef) else "def"
                                args = [a.arg for a in item.args.args]
                                classes.append(f"    {prefix} {item.name}({', '.join(args)}): ...")

                if classes:
                    lines.append("## Classes & Methods:")
                    lines.extend(classes)
                    lines.append("")

                # Standalone Functions
                funcs = []
                for node in ast.iter_child_nodes(tree):
                    if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                        prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
                        args = [a.arg for a in node.args.args]
                        funcs.append(f"{prefix} {node.name}({', '.join(args)}): ...")

                if funcs:
                    lines.append("## Functions:")
                    lines.extend(funcs)
                    lines.append("")

                return "\n".join(lines).strip()
            except Exception:
                pass

        # 2. JS / TS Outline
        if src.endswith((".js", ".ts", ".jsx", ".tsx")):
            lines = [f"// [SYMBOL OUTLINE] Source: {candidate.source} (Large File Fallback)", ""]
            for raw_line in content.splitlines():
                l = raw_line.strip()
                if l.startswith(("import ", "export ", "function ", "class ", "interface ", "type ", "const ")):
                    lines.append(l)
            if len(lines) > 2:
                return "\n".join(lines[:60]).strip()

        # 3. Markdown / Document Outline
        if src.endswith(".md") or "doc" in candidate.kind.lower():
            lines = [f"# [DOCUMENT OUTLINE] Source: {candidate.source} (Large File Fallback)", ""]
            for raw_line in content.splitlines():
                if raw_line.startswith(("#", "##", "###", "####")):
                    lines.append(raw_line)
            if len(lines) > 2:
                return "\n".join(lines[:40]).strip()

        # 4. Fallback line slice (first 25 lines + summary)
        content_lines = content.splitlines()
        preview = "\n".join(content_lines[:25])
        return f"# [TRUNCATED PREVIEW: {candidate.source} (Total Lines: {len(content_lines)})]\n{preview}\n# ... [Remaining content omitted for character budget]"

    @staticmethod
    def from_candidates(
        task_summary: str,
        candidates: Iterable[ContextCandidate],
        **kwargs,
    ) -> TaskContext:
        return ContextBuilder().build(
            ContextBuildRequest(
                task_summary=task_summary,
                candidates=tuple(candidates),
                **kwargs,
            )
        )

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


__all__ = ["ContextCandidate", "ContextBuildRequest", "ContextBuilder", "AUTO_EXCLUDED_CONTEXT_KINDS"]
