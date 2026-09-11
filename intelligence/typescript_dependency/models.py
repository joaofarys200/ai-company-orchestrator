"""
JARVIS OS — Phase 39.1: TypeScript Dependency Models
Defines immutable data models, enums, and structured containers for TypeScript & React
dependency intelligence, export graph, and symbol resolution.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple


class DependencyRelationType(str, Enum):
    IMPORTS = "IMPORTS"
    RE_EXPORTS = "RE_EXPORTS"
    REFERENCES = "REFERENCES"
    PACKAGE_DEPENDS = "PACKAGE_DEPENDS"
    ALIAS_RESOLVES = "ALIAS_RESOLVES"
    DYNAMIC_UNRESOLVED = "DYNAMIC_UNRESOLVED"


class ConfidenceClass(str, Enum):
    DETERMINISTIC = "DETERMINISTIC"
    INFERRED = "INFERRED"
    UNCERTAIN = "UNCERTAIN"


class BoundaryType(str, Enum):
    INTRA_PACKAGE = "INTRA_PACKAGE"
    INTER_PACKAGE = "INTER_PACKAGE"
    EXTERNAL_PACKAGE = "EXTERNAL_PACKAGE"


class SymbolResolutionStatus(str, Enum):
    SYMBOL_RESOLVED = "SYMBOL_RESOLVED"
    SYMBOL_UNRESOLVED = "SYMBOL_UNRESOLVED"


class TypeScriptSymbolType(str, Enum):
    FUNCTION = "FUNCTION"
    CLASS = "CLASS"
    INTERFACE = "INTERFACE"
    TYPE_ALIAS = "TYPE_ALIAS"
    ENUM = "ENUM"
    CONSTANT = "CONSTANT"
    REACT_COMPONENT = "REACT_COMPONENT"
    MODULE = "MODULE"
    UNKNOWN = "UNKNOWN"


@dataclass(slots=True, frozen=True)
class TypeScriptSymbol:
    """Represents a declaration or export of a symbol within a TypeScript/TSX file."""
    name: str
    symbol_type: TypeScriptSymbolType
    file_path: str
    line_number: int
    is_exported: bool = False
    signature: str = ""
    is_default: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "symbol_type": self.symbol_type.value if isinstance(self.symbol_type, TypeScriptSymbolType) else str(self.symbol_type),
            "file_path": self.file_path,
            "line_number": self.line_number,
            "is_exported": self.is_exported,
            "signature": self.signature,
            "is_default": self.is_default,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> TypeScriptSymbol:
        st = d.get("symbol_type", "UNKNOWN")
        try:
            sym_enum = TypeScriptSymbolType(st)
        except ValueError:
            sym_enum = TypeScriptSymbolType.UNKNOWN
        return cls(
            name=d["name"],
            symbol_type=sym_enum,
            file_path=d["file_path"],
            line_number=d.get("line_number", 1),
            is_exported=d.get("is_exported", False),
            signature=d.get("signature", ""),
            is_default=d.get("is_default", False),
        )


@dataclass(slots=True, frozen=True)
class TypeScriptImport:
    """Represents an import statement in a TypeScript/TSX file."""
    source_file: str
    module_specifier: str
    imported_symbols: Tuple[str, ...] = field(default_factory=tuple)  # e.g. ('Button', 'Header')
    default_import: Optional[str] = None  # e.g. 'React'
    namespace_import: Optional[str] = None  # e.g. '* as path'
    is_type_only: bool = False
    is_relative: bool = False
    is_dynamic: bool = False  # import('./lazy') or require(...)
    line_number: int = 1
    resolved_target: Optional[str] = None
    confidence: ConfidenceClass = ConfidenceClass.DETERMINISTIC
    boundary: BoundaryType = BoundaryType.INTRA_PACKAGE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_file": self.source_file,
            "module_specifier": self.module_specifier,
            "imported_symbols": list(self.imported_symbols),
            "default_import": self.default_import,
            "namespace_import": self.namespace_import,
            "is_type_only": self.is_type_only,
            "is_relative": self.is_relative,
            "is_dynamic": self.is_dynamic,
            "line_number": self.line_number,
            "resolved_target": self.resolved_target,
            "confidence": self.confidence.value,
            "boundary": self.boundary.value,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> TypeScriptImport:
        return cls(
            source_file=d["source_file"],
            module_specifier=d["module_specifier"],
            imported_symbols=tuple(d.get("imported_symbols", [])),
            default_import=d.get("default_import"),
            namespace_import=d.get("namespace_import"),
            is_type_only=d.get("is_type_only", False),
            is_relative=d.get("is_relative", False),
            is_dynamic=d.get("is_dynamic", False),
            line_number=d.get("line_number", 1),
            resolved_target=d.get("resolved_target"),
            confidence=ConfidenceClass(d.get("confidence", ConfidenceClass.DETERMINISTIC.value)),
            boundary=BoundaryType(d.get("boundary", BoundaryType.INTRA_PACKAGE.value)),
        )


@dataclass(slots=True, frozen=True)
class TypeScriptExport:
    """Represents an export or re-export declaration in a TypeScript/TSX file."""
    source_file: str
    exported_symbols: Tuple[str, ...] = field(default_factory=tuple)  # e.g. ('foo', 'bar')
    is_default: bool = False
    is_re_export: bool = False
    re_export_source: Optional[str] = None  # e.g. './components'
    is_star_export: bool = False  # export * from './X'
    star_namespace: Optional[str] = None  # export * as utils from './utils'
    is_type_only: bool = False
    line_number: int = 1
    resolved_target: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_file": self.source_file,
            "exported_symbols": list(self.exported_symbols),
            "is_default": self.is_default,
            "is_re_export": self.is_re_export,
            "re_export_source": self.re_export_source,
            "is_star_export": self.is_star_export,
            "star_namespace": self.star_namespace,
            "is_type_only": self.is_type_only,
            "line_number": self.line_number,
            "resolved_target": self.resolved_target,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> TypeScriptExport:
        return cls(
            source_file=d["source_file"],
            exported_symbols=tuple(d.get("exported_symbols", [])),
            is_default=d.get("is_default", False),
            is_re_export=d.get("is_re_export", False),
            re_export_source=d.get("re_export_source"),
            is_star_export=d.get("is_star_export", False),
            star_namespace=d.get("star_namespace"),
            is_type_only=d.get("is_type_only", False),
            line_number=d.get("line_number", 1),
            resolved_target=d.get("resolved_target"),
        )


@dataclass(slots=True)
class DependencyEdge:
    """Normalized directed dependency edge between source and target."""
    source: str
    target: str
    relation_type: DependencyRelationType
    confidence_class: ConfidenceClass
    origin: str  # e.g. "import", "re-export", "alias"
    resolved: bool = True
    symbol: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "relation_type": self.relation_type.value,
            "confidence_class": self.confidence_class.value,
            "origin": self.origin,
            "resolved": self.resolved,
            "symbol": self.symbol,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> DependencyEdge:
        return cls(
            source=d["source"],
            target=d["target"],
            relation_type=DependencyRelationType(d["relation_type"]),
            confidence_class=ConfidenceClass(d["confidence_class"]),
            origin=d.get("origin", "import"),
            resolved=d.get("resolved", True),
            symbol=d.get("symbol"),
            metadata=d.get("metadata", {}),
        )


@dataclass(slots=True)
class TypeScriptDependencyIndex:
    """Complete, normalized dependency index for a single TypeScript/TSX file."""
    file_path: str
    imports: List[TypeScriptImport] = field(default_factory=list)
    exports: List[TypeScriptExport] = field(default_factory=list)
    local_symbols: List[TypeScriptSymbol] = field(default_factory=list)
    imported_symbols: List[str] = field(default_factory=list)
    re_exports: List[TypeScriptExport] = field(default_factory=list)
    resolved_targets: List[str] = field(default_factory=list)
    unresolved_imports: List[str] = field(default_factory=list)
    aliases_used: List[Dict[str, str]] = field(default_factory=list)
    package_name: str = "frontend"
    module_boundary: BoundaryType = BoundaryType.INTRA_PACKAGE
    parser_version: str = "39.1.0"
    content_hash: str = ""
    parsed_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "imports": [i.to_dict() for i in self.imports],
            "exports": [e.to_dict() for e in self.exports],
            "local_symbols": [s.to_dict() for s in self.local_symbols],
            "imported_symbols": self.imported_symbols,
            "re_exports": [r.to_dict() for r in self.re_exports],
            "resolved_targets": self.resolved_targets,
            "unresolved_imports": self.unresolved_imports,
            "aliases_used": self.aliases_used,
            "package_name": self.package_name,
            "module_boundary": self.module_boundary.value,
            "parser_version": self.parser_version,
            "content_hash": self.content_hash,
            "parsed_at": self.parsed_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> TypeScriptDependencyIndex:
        return cls(
            file_path=d["file_path"],
            imports=[TypeScriptImport.from_dict(i) for i in d.get("imports", [])],
            exports=[TypeScriptExport.from_dict(e) for e in d.get("exports", [])],
            local_symbols=[TypeScriptSymbol.from_dict(s) for s in d.get("local_symbols", [])],
            imported_symbols=d.get("imported_symbols", []),
            re_exports=[TypeScriptExport.from_dict(r) for r in d.get("re_exports", [])],
            resolved_targets=d.get("resolved_targets", []),
            unresolved_imports=d.get("unresolved_imports", []),
            aliases_used=d.get("aliases_used", []),
            package_name=d.get("package_name", "frontend"),
            module_boundary=BoundaryType(d.get("module_boundary", BoundaryType.INTRA_PACKAGE.value)),
            parser_version=d.get("parser_version", "39.1.0"),
            content_hash=d.get("content_hash", ""),
            parsed_at=d.get("parsed_at", 0.0),
        )
