from __future__ import annotations

from dataclasses import dataclass, replace

from backend.semantic_context.contracts import (
    BuilderConfiguration,
    CompressionResult,
    ContextItem,
    ContextRejection,
    RankingScore,
)


@dataclass(frozen=True)
class CompressedSelection:
    items: tuple[ContextItem, ...]
    ranking: tuple[RankingScore, ...]
    result: CompressionResult


class DeterministicContextCompressor:
    """Exact deduplication and budgets only; no semantic rewriting."""

    def compress(
        self,
        items: tuple[ContextItem, ...],
        ranking: tuple[RankingScore, ...],
        configuration: BuilderConfiguration,
    ) -> CompressedSelection:
        by_id = {item.item_id: item for item in items}
        selected: list[ContextItem] = []
        selected_scores: list[RankingScore] = []
        selected_by_hash: dict[str, int] = {}
        rejected: list[ContextRejection] = []
        total_chars = 0
        duplicate_count = 0

        for score in ranking:
            item = by_id[score.item_id]
            if not item.content.strip():
                rejected.append(
                    ContextRejection(
                        item_id=item.item_id,
                        reason="empty_content",
                    )
                )
                continue
            duplicate_index = selected_by_hash.get(item.content_sha256)
            if duplicate_index is not None:
                existing = selected[duplicate_index]
                selected[duplicate_index] = replace(
                    existing,
                    references=tuple(
                        sorted(set(existing.references + item.references))
                    ),
                )
                duplicate_count += 1
                rejected.append(
                    ContextRejection(
                        item_id=item.item_id,
                        reason="duplicate_content",
                        duplicate_of=existing.item_id,
                    )
                )
                continue
            if len(item.content) > configuration.max_item_chars:
                rejected.append(
                    ContextRejection(
                        item_id=item.item_id,
                        reason="item_char_limit",
                    )
                )
                continue
            if len(selected) >= configuration.max_items:
                rejected.append(
                    ContextRejection(
                        item_id=item.item_id,
                        reason="item_count_limit",
                    )
                )
                continue
            if total_chars + len(item.content) > configuration.max_chars:
                rejected.append(
                    ContextRejection(
                        item_id=item.item_id,
                        reason="total_char_limit",
                    )
                )
                continue
            selected_by_hash[item.content_sha256] = len(selected)
            selected.append(item)
            selected_scores.append(score)
            total_chars += len(item.content)

        ranked = tuple(
            replace(score, rank=index)
            for index, score in enumerate(selected_scores, start=1)
        )
        result = CompressionResult(
            selected_item_ids=tuple(item.item_id for item in selected),
            rejected=tuple(rejected),
            considered_items=len(items),
            duplicate_items=duplicate_count,
            original_chars=sum(len(item.content) for item in items),
            final_chars=total_chars,
            max_items=configuration.max_items,
            max_chars=configuration.max_chars,
        )
        return CompressedSelection(
            items=tuple(selected),
            ranking=ranked,
            result=result,
        )
