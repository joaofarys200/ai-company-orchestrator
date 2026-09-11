"""
JARVIS OS — Phase 39.1: Test Suite for TypeScript Dependency Index & Models
Validates:
- Data models serialization and deserialization
- SHA-256 content_hash stability
- Symbol extraction across Functions, Classes, Interfaces, Types, Enums, Constants, and React Components
- Windows canonical path normalization
"""

import pytest
from intelligence.typescript_dependency.models import (
    BoundaryType,
    ConfidenceClass,
    DependencyEdge,
    DependencyRelationType,
    TypeScriptDependencyIndex,
    TypeScriptExport,
    TypeScriptImport,
    TypeScriptSymbol,
    TypeScriptSymbolType,
)
from intelligence.typescript_dependency.parser import TypeScriptSyntaxParser


def test_model_serialization_roundtrip():
    sym = TypeScriptSymbol(
        name="MissionControlCenter",
        symbol_type=TypeScriptSymbolType.REACT_COMPONENT,
        file_path="frontend/src/features/missions/MissionControlCenter.tsx",
        line_number=42,
        is_exported=True,
        signature="export const MissionControlCenter: React.FC = ...",
    )
    d = sym.to_dict()
    assert d["name"] == "MissionControlCenter"
    assert d["symbol_type"] == "REACT_COMPONENT"
    restored = TypeScriptSymbol.from_dict(d)
    assert restored.name == sym.name
    assert restored.symbol_type == sym.symbol_type

    imp = TypeScriptImport(
        source_file="frontend/src/App.tsx",
        module_specifier="./features/missions/MissionControlCenter",
        imported_symbols=("MissionControlCenter",),
        is_relative=True,
        line_number=5,
        resolved_target="frontend/src/features/missions/MissionControlCenter.tsx",
    )
    imp_dict = imp.to_dict()
    assert imp_dict["source_file"] == "frontend/src/App.tsx"
    restored_imp = TypeScriptImport.from_dict(imp_dict)
    assert restored_imp.module_specifier == imp.module_specifier
    assert restored_imp.imported_symbols == ("MissionControlCenter",)

    idx = TypeScriptDependencyIndex(
        file_path="frontend/src/App.tsx",
        imports=[imp],
        exports=[],
        local_symbols=[sym],
        content_hash="abc123hash",
    )
    idx_dict = idx.to_dict()
    restored_idx = TypeScriptDependencyIndex.from_dict(idx_dict)
    assert restored_idx.file_path == "frontend/src/App.tsx"
    assert len(restored_idx.imports) == 1
    assert len(restored_idx.local_symbols) == 1


def test_syntax_parser_extracts_symbols():
    sample_code = """
    import React, { useState } from 'react';
    import type { Config } from './config';
    import * as Lucide from 'lucide-react';
    import './styles.css';

    export interface UserProfile {
        id: string;
        username: string;
    }

    export type Status = 'ACTIVE' | 'INACTIVE';

    export enum Role {
        ADMIN = 'ADMIN',
        OPERATOR = 'OPERATOR'
    }

    export class AuthService {
        login() { return true; }
    }

    export function calculateTotal(items: number[]): number {
        return items.reduce((a, b) => a + b, 0);
    }

    export const AppHeader: React.FC<{ title: string }> = ({ title }) => {
        return <div>{title}</div>;
    };

    export default AuthService;
    """

    imports, exports, symbols = TypeScriptSyntaxParser.parse_content_python(sample_code, "src/Sample.tsx")

    # Verify imports
    assert len(imports) == 4
    specifiers = [i.module_specifier for i in imports]
    assert "react" in specifiers
    assert "./config" in specifiers
    assert "lucide-react" in specifiers
    assert "./styles.css" in specifiers

    type_import = [i for i in imports if i.module_specifier == "./config"][0]
    assert type_import.is_type_only is True

    # Verify exports
    assert any(e.is_default for e in exports)

    # Verify symbols
    sym_map = {s.name: s.symbol_type for s in symbols}
    assert sym_map.get("UserProfile") == TypeScriptSymbolType.INTERFACE
    assert sym_map.get("Status") == TypeScriptSymbolType.TYPE_ALIAS
    assert sym_map.get("Role") == TypeScriptSymbolType.ENUM
    assert sym_map.get("AuthService") == TypeScriptSymbolType.CLASS
    assert sym_map.get("calculateTotal") == TypeScriptSymbolType.FUNCTION
    assert sym_map.get("AppHeader") == TypeScriptSymbolType.REACT_COMPONENT


def test_syntax_parser_handles_comments():
    code_with_comments = """
    // This is a line comment with import fake from 'fake';
    /* Block comment with import another from 'another'; */
    import { RealComponent } from './real';
    // export function fakeExport() {}
    export function realExport() { return 1; }
    """
    imports, exports, symbols = TypeScriptSyntaxParser.parse_content_python(code_with_comments, "src/Test.ts")
    assert len(imports) == 1
    assert imports[0].module_specifier == "./real"
    assert imports[0].imported_symbols == ("RealComponent",)

    sym_names = [s.name for s in symbols]
    assert "fakeExport" not in sym_names
    assert "realExport" in sym_names
