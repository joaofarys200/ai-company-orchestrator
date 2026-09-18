"""
JARVIS OS — Phase 63: Cross-Project Engineering Learning & Verification Transfer
Module: provenance.py
ProvenanceTracker maintains immutable audit trails of knowledge origins and transformations.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional
from .models import KnowledgeProvenance


class ProvenanceTracker:
    """Records transformations, source origins, and validation receipts for all transferred items."""

    def __init__(self) -> None:
        self._ledger: List[Dict[str, Any]] = []

    def record_origin(
        self,
        knowledge_id: str,
        source_project_id: str,
        source_file: str = "",
        mission_id: str = "",
    ) -> KnowledgeProvenance:
        now = time.time()
        prov = KnowledgeProvenance(
            source_project_id=source_project_id,
            source_file=source_file,
            author_mission_id=mission_id,
            created_at=now,
        )
        self._ledger.append({
            "event": "ORIGIN_RECORDED",
            "knowledge_id": knowledge_id,
            "provenance": prov.to_dict(),
            "timestamp": now,
        })
        return prov

    def record_transformation(
        self,
        knowledge_id: str,
        provenance: KnowledgeProvenance,
        transformation_description: str,
    ) -> None:
        provenance.transformation_chain.append(transformation_description)
        self._ledger.append({
            "event": "TRANSFORMATION_APPLIED",
            "knowledge_id": knowledge_id,
            "transformation": transformation_description,
            "timestamp": time.time(),
        })

    def record_local_validation(
        self,
        knowledge_id: str,
        provenance: KnowledgeProvenance,
        validation_id: str,
        validation_hash: str,
    ) -> None:
        provenance.original_validation_hash = validation_hash
        self._ledger.append({
            "event": "LOCAL_VALIDATION_LINKED",
            "knowledge_id": knowledge_id,
            "validation_id": validation_id,
            "validation_hash": validation_hash,
            "timestamp": time.time(),
        })

    def get_ledger(self) -> List[Dict[str, Any]]:
        return list(self._ledger)
