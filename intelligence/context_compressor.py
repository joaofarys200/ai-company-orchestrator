from __future__ import annotations

import re
from typing import Any


class ContextCompressor:
    """Intelligently compresses long-running coding and mission context to preserve Qwen 3.5:9b accuracy."""

    @classmethod
    def compress_terminal_logs(cls, logs: str, max_chars: int = 1500) -> str:
        """Preserves top error summary and bottom traceback while compressing verbose middleware outputs."""
        if not logs or len(logs) <= max_chars:
            return logs

        half = max_chars // 2
        head = logs[:half]
        tail = logs[-half:]
        return f"{head}\n\n[... {len(logs) - max_chars} CARACTERES INTERMÉDIOS COMPRIMIDOS ...]\n\n{tail}"

    @classmethod
    def compress_diff_history(cls, applied_changes: list[dict[str, Any]], max_recent: int = 3) -> list[dict[str, Any]]:
        """Keeps only the most recent diffs and summarizes older changes into a compact changelog."""
        if len(applied_changes) <= max_recent:
            return applied_changes

        recent = applied_changes[-max_recent:]
        older_count = len(applied_changes) - max_recent
        summary_change = {
            "file": "CHANGELOG_SUMMARY",
            "summary": f"{older_count} alterações anteriores consolidadas com sucesso no repositório.",
            "status": "CONSOLIDATED",
        }
        return [summary_change] + recent

    @classmethod
    def assemble_compact_context(
        cls,
        objective: str,
        active_files: list[str],
        symbols: dict[str, Any] | None = None,
        recent_tool_outcomes: list[dict[str, Any]] | None = None,
        unresolved_errors: list[str] | None = None,
    ) -> dict[str, Any]:
        """Assembles a lightweight, token-efficient snapshot for prompt injection."""
        compact_symbols = {}
        if symbols:
            for f in active_files:
                if f in symbols:
                    compact_symbols[f] = symbols[f]

        return {
            "objective": objective,
            "active_files": active_files,
            "relevant_symbols": compact_symbols,
            "recent_tool_outcomes": (recent_tool_outcomes or [])[-3:],
            "unresolved_errors": [cls.compress_terminal_logs(e, max_chars=400) for e in (unresolved_errors or [])],
        }


__all__ = ["ContextCompressor"]
