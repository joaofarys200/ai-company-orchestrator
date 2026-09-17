from __future__ import annotations

from typing import Any, Dict, List, Optional

from .models import SymbolEdge, SymbolEdgeType


class SymbolEdgeBuilder:
    """Constructs and validates typed edges between symbols with confidence scoring."""

    @classmethod
    def build_edge(
        cls,
        source_symbol: str,
        target_symbol: str,
        edge_type: SymbolEdgeType,
        provenance: Optional[Dict[str, Any]] = None,
        confidence: float = 1.0,
        source_location: Optional[Dict[str, Any]] = None,
    ) -> SymbolEdge:
        # Calibrate confidence based on edge type
        if edge_type == SymbolEdgeType.DYNAMIC:
            confidence = min(confidence, 0.4)
        elif edge_type == SymbolEdgeType.UNKNOWN:
            confidence = min(confidence, 0.2)

        return SymbolEdge(
            source_symbol=source_symbol,
            target_symbol=target_symbol,
            edge_type=edge_type,
            provenance=provenance or {},
            confidence=round(confidence, 3),
            source_location=source_location or {},
        )

    @classmethod
    def build_calls_edge(
        cls, source_symbol: str, target_symbol: str, provenance: Optional[Dict[str, Any]] = None, confidence: float = 1.0
    ) -> SymbolEdge:
        return cls.build_edge(source_symbol, target_symbol, SymbolEdgeType.CALLS, provenance, confidence)

    @classmethod
    def build_type_uses_edge(
        cls, source_symbol: str, target_symbol: str, provenance: Optional[Dict[str, Any]] = None, confidence: float = 1.0
    ) -> SymbolEdge:
        return cls.build_edge(source_symbol, target_symbol, SymbolEdgeType.TYPE_USES, provenance, confidence)

    @classmethod
    def build_reexports_edge(
        cls, source_symbol: str, target_symbol: str, provenance: Optional[Dict[str, Any]] = None, confidence: float = 1.0
    ) -> SymbolEdge:
        return cls.build_edge(source_symbol, target_symbol, SymbolEdgeType.REEXPORTS, provenance, confidence)

    @classmethod
    def build_extends_edge(
        cls, source_symbol: str, target_symbol: str, provenance: Optional[Dict[str, Any]] = None, confidence: float = 1.0
    ) -> SymbolEdge:
        return cls.build_edge(source_symbol, target_symbol, SymbolEdgeType.EXTENDS, provenance, confidence)

    @classmethod
    def build_dynamic_edge(
        cls, source_symbol: str, target_symbol: str, provenance: Optional[Dict[str, Any]] = None
    ) -> SymbolEdge:
        return cls.build_edge(source_symbol, target_symbol, SymbolEdgeType.DYNAMIC, provenance, 0.4)

    @staticmethod
    def is_type_only(edge: SymbolEdge) -> bool:
        return edge.edge_type in (
            SymbolEdgeType.TYPE_USES,
            SymbolEdgeType.IMPLEMENTS,
        )

    @staticmethod
    def is_value_use(edge: SymbolEdge) -> bool:
        return edge.edge_type in (
            SymbolEdgeType.CALLS,
            SymbolEdgeType.CONSTRUCTS,
            SymbolEdgeType.VALUE_USES,
            SymbolEdgeType.READS,
            SymbolEdgeType.WRITES,
        )

    @staticmethod
    def is_reexport(edge: SymbolEdge) -> bool:
        return edge.edge_type == SymbolEdgeType.REEXPORTS
