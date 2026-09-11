"""
JARVIS OS — Phase 39.1: TypeScript Dependency Intelligence Package
Provides deterministic TypeScript/React import resolution, AST parsing,
symbol tracking, export-import graph traversal, and incremental caching.
"""

from intelligence.typescript_dependency.models import (
    BoundaryType,
    ConfidenceClass,
    DependencyEdge,
    DependencyRelationType,
    SymbolResolutionStatus,
    TypeScriptDependencyIndex,
    TypeScriptExport,
    TypeScriptImport,
    TypeScriptSymbol,
    TypeScriptSymbolType,
)
from intelligence.typescript_dependency.parser import TypeScriptSyntaxParser
from intelligence.typescript_dependency.resolver import TypeScriptImportResolver
from intelligence.typescript_dependency.cache import TypeScriptDependencyCache
from intelligence.typescript_dependency.graph import NormalizedTypeScriptGraph
from intelligence.typescript_dependency.validator import TypeScriptGraphValidator
from intelligence.typescript_dependency.index import TypeScriptDependencyService

__all__ = [
    "BoundaryType",
    "ConfidenceClass",
    "DependencyEdge",
    "DependencyRelationType",
    "NormalizedTypeScriptGraph",
    "SymbolResolutionStatus",
    "TypeScriptDependencyCache",
    "TypeScriptDependencyIndex",
    "TypeScriptDependencyService",
    "TypeScriptExport",
    "TypeScriptGraphValidator",
    "TypeScriptImport",
    "TypeScriptImportResolver",
    "TypeScriptSymbol",
    "TypeScriptSymbolType",
    "TypeScriptSyntaxParser",
]
