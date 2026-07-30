from __future__ import annotations

import hashlib
import json
from typing import Any

from backend.semantic_context.contracts import (
    SemanticSnapshot,
    to_jsonable,
)


class SemanticContextSerializer:
    def to_package(self, snapshot: SemanticSnapshot) -> dict[str, Any]:
        return {
            "version": snapshot.builder_version,
            "snapshot_version": snapshot.snapshot_version,
            "generated_at": snapshot.generated_at,
            "mission": to_jsonable(snapshot.mission),
            "workspace": to_jsonable(snapshot.workspace),
            "capabilities": to_jsonable(snapshot.capabilities),
            "documents": to_jsonable(snapshot.documents),
            "context_items": to_jsonable(snapshot.items),
            "metadata": {
                "configuration": to_jsonable(snapshot.configuration),
            },
            "ranking": to_jsonable(snapshot.ranking),
            "compression": to_jsonable(snapshot.compression),
            "statistics": to_jsonable(snapshot.statistics),
            "hashes": {
                "sources": to_jsonable(snapshot.source_hashes),
                "content_sha256": snapshot.content_sha256,
            },
        }

    def serialize(
        self,
        snapshot: SemanticSnapshot,
        *,
        pretty: bool = False,
    ) -> str:
        options: dict[str, Any] = {
            "ensure_ascii": False,
            "sort_keys": True,
        }
        if pretty:
            options["indent"] = 2
        else:
            options["separators"] = (",", ":")
        return json.dumps(self.to_package(snapshot), **options)

    def serialized_sha256(self, snapshot: SemanticSnapshot) -> str:
        return hashlib.sha256(
            self.serialize(snapshot).encode("utf-8")
        ).hexdigest()
