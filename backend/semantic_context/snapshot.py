from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Mapping

from backend.semantic_context.contracts import (
    SEMANTIC_CONTEXT_VERSION,
    BuilderConfiguration,
    CapabilityContext,
    CompressionResult,
    ContextItem,
    DocumentContext,
    MissionContext,
    RankingScore,
    SemanticSnapshot,
    WorkspaceContext,
    sha256_json,
)
from backend.semantic_context.serializer import SemanticContextSerializer


class SemanticSnapshotFactory:
    def create(
        self,
        *,
        generated_at: str,
        configuration: BuilderConfiguration,
        mission: MissionContext,
        workspace: WorkspaceContext,
        capabilities: CapabilityContext,
        documents: DocumentContext,
        items: tuple[ContextItem, ...],
        ranking: tuple[RankingScore, ...],
        compression: CompressionResult,
        source_hashes: Mapping[str, str],
        statistics: Mapping[str, Any],
    ) -> SemanticSnapshot:
        seed = semantic_snapshot_seed(
            generated_at=generated_at,
            configuration=configuration,
            items=items,
            ranking=ranking,
            compression=compression,
            source_hashes=source_hashes,
        )
        snapshot = SemanticSnapshot(
            builder_version=SEMANTIC_CONTEXT_VERSION,
            snapshot_version=(
                f"{SEMANTIC_CONTEXT_VERSION}-{seed[:16]}"
            ),
            generated_at=generated_at,
            configuration=configuration,
            mission=mission,
            workspace=workspace,
            capabilities=capabilities,
            documents=documents,
            items=items,
            ranking=ranking,
            compression=compression,
            source_hashes=source_hashes,
            statistics=statistics,
            content_sha256="0" * 64,
        )
        return replace(
            snapshot,
            content_sha256=snapshot.computed_content_sha256(),
        )


def semantic_snapshot_seed(
    *,
    generated_at: str,
    configuration: BuilderConfiguration,
    items: tuple[ContextItem, ...],
    ranking: tuple[RankingScore, ...],
    compression: CompressionResult,
    source_hashes: Mapping[str, str],
) -> str:
    return sha256_json({
        "builder_version": SEMANTIC_CONTEXT_VERSION,
        "generated_at": generated_at,
        "configuration": configuration,
        "source_hashes": source_hashes,
        "item_hashes": tuple(
            (item.item_id, item.content_sha256, item.references)
            for item in items
        ),
        "ranking": ranking,
        "compression": compression,
    })


@dataclass(frozen=True)
class SnapshotExportResult:
    path: str
    size_bytes: int
    sha256: str


class SemanticSnapshotExporter:
    """Explicit atomic export. Building a context never invokes this writer."""

    def __init__(
        self,
        serializer: SemanticContextSerializer | None = None,
    ):
        self.serializer = serializer or SemanticContextSerializer()

    def export(
        self,
        snapshot: SemanticSnapshot,
        destination: str | Path,
    ) -> SnapshotExportResult:
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = (self.serializer.serialize(snapshot, pretty=True) + "\n").encode(
            "utf-8"
        )
        temporary_path = ""
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
                temporary_path = stream.name
            os.replace(temporary_path, path)
        finally:
            if temporary_path and os.path.exists(temporary_path):
                os.unlink(temporary_path)
        return SnapshotExportResult(
            path=str(path),
            size_bytes=len(payload),
            sha256=hashlib.sha256(payload).hexdigest(),
        )
