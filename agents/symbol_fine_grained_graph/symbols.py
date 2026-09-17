from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional

from .models import SymbolKind, SymbolNode


class SymbolManager:
    """Manages creation, canonical naming, and state hashing for atomic symbols."""

    @staticmethod
    def create_symbol_id(file_id: str, qualified_name: str) -> str:
        """Returns standard format file_id::qualified_name."""
        clean_file = file_id.replace("\\", "/").strip("/")
        clean_name = qualified_name.strip()
        return f"{clean_file}::{clean_name}"

    @staticmethod
    def compute_signature_hash(name: str, kind: Any = "", signature_text: str = "") -> str:
        kind_val = kind.value if hasattr(kind, "value") else str(kind)
        raw = f"{name}:{kind_val}:{signature_text}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    @staticmethod
    def compute_body_hash(body_text: str) -> str:
        return hashlib.sha256(body_text.encode()).hexdigest()[:16]

    @staticmethod
    def compute_state_hash(symbol: SymbolNode) -> str:
        kind_val = symbol.kind.value if hasattr(symbol.kind, "value") else str(symbol.kind)
        raw = (
            f"{symbol.symbol_id}:{kind_val}:{symbol.signature_hash}:"
            f"{symbol.body_hash}:{symbol.exported}:{symbol.visibility}"
        )
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    @classmethod
    def build_symbol(
        cls,
        file_id: str,
        *args: Any,
        name: Optional[str] = None,
        kind: Optional[Any] = None,
        qualified_name: Optional[str] = None,
        module_id: Optional[str] = None,
        language: str = "python",
        exported: bool = False,
        imported: bool = False,
        line: int = 1,
        column: int = 1,
        visibility: str = "public",
        signature_text: str = "",
        body_text: str = "",
        provenance: Optional[Dict[str, Any]] = None,
        signature_hash: Optional[str] = None,
        body_hash: Optional[str] = None,
        **kwargs: Any,
    ) -> SymbolNode:
        if len(args) == 1:
            actual_name = name or str(args[0])
            actual_kind = kind or SymbolKind.FUNCTION
            actual_qname = qualified_name or actual_name
        elif len(args) == 2:
            actual_name = name or str(args[0])
            actual_kind = kind or args[1]
            actual_qname = qualified_name or actual_name
        elif len(args) >= 3:
            if isinstance(args[2], (SymbolKind, str)) and (isinstance(args[2], SymbolKind) or args[2] in SymbolKind.__members__):
                actual_qname = str(args[0])
                actual_name = str(args[1])
                actual_kind = args[2]
            else:
                actual_name = str(args[0])
                actual_qname = str(args[1])
                actual_kind = args[2]
        else:
            actual_name = name or kwargs.get("name", "unnamed")
            actual_kind = kind or kwargs.get("kind", SymbolKind.FUNCTION)
            actual_qname = qualified_name or kwargs.get("qualified_name") or actual_name

        if isinstance(actual_kind, str):
            if actual_kind in SymbolKind.__members__:
                actual_kind = SymbolKind(actual_kind)
            else:
                actual_kind = SymbolKind.FUNCTION

        clean_file = file_id.replace("\\", "/")
        sym_id = cls.create_symbol_id(clean_file, actual_qname)
        mod_id = module_id or clean_file.split(".")[0].replace("/", ".")
        sig_hash = signature_hash or cls.compute_signature_hash(actual_name, actual_kind, signature_text)
        b_hash = body_hash if body_hash is not None else cls.compute_body_hash(body_text)

        node = SymbolNode(
            symbol_id=sym_id,
            file_id=clean_file,
            module_id=mod_id,
            name=actual_name,
            qualified_name=actual_qname,
            language=language,
            kind=actual_kind,
            exported=exported,
            imported=imported,
            line=line,
            column=column,
            visibility=visibility,
            signature_hash=sig_hash,
            body_hash=b_hash,
            provenance=provenance or {},
        )
        node.state_hash = cls.compute_state_hash(node)
        return node
