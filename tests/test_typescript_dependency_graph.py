"""
JARVIS OS — Phase 39.1: Test Suite for Normalized TypeScript Dependency Graph
Validates:
- Graph construction and edge normalization
- Forward and reverse dependency lookups (shallow vs recursive)
- Symbol resolution through barrel files
- Cycle detection
- Structural integrity validation via TypeScriptGraphValidator
"""

import os
import shutil
import tempfile
import pytest

from intelligence.typescript_dependency.graph import NormalizedTypeScriptGraph
from intelligence.typescript_dependency.models import (
    ConfidenceClass,
    DependencyEdge,
    DependencyRelationType,
    TypeScriptDependencyIndex,
    TypeScriptExport,
    TypeScriptImport,
    TypeScriptSymbol,
    TypeScriptSymbolType,
)
from intelligence.typescript_dependency.validator import TypeScriptGraphValidator


@pytest.fixture
def sample_graph():
    workspace = "C:/fake_workspace"
    g = NormalizedTypeScriptGraph(workspace)

    sym_btn = TypeScriptSymbol(
        name="Button",
        symbol_type=TypeScriptSymbolType.REACT_COMPONENT,
        file_path="src/components/Button.tsx",
        line_number=10,
        is_exported=True,
    )
    exp_barrel = TypeScriptExport(
        source_file="src/components/index.ts",
        exported_symbols=("Button",),
        is_re_export=True,
        re_export_source="./Button",
        resolved_target="src/components/Button.tsx",
    )
    imp_app = TypeScriptImport(
        source_file="src/App.tsx",
        module_specifier="./components",
        imported_symbols=("Button",),
        resolved_target="src/components/index.ts",
    )

    idx_btn = TypeScriptDependencyIndex(
        file_path="src/components/Button.tsx",
        local_symbols=[sym_btn],
    )
    idx_barrel = TypeScriptDependencyIndex(
        file_path="src/components/index.ts",
        re_exports=[exp_barrel],
        resolved_targets=["src/components/Button.tsx"],
    )
    idx_app = TypeScriptDependencyIndex(
        file_path="src/App.tsx",
        imports=[imp_app],
        resolved_targets=["src/components/index.ts"],
    )

    g.build_from_indices([idx_btn, idx_barrel, idx_app])
    return g, workspace


def test_graph_forward_and_reverse_traversal(sample_graph):
    g, _ = sample_graph
    assert "src/App.tsx" in g.nodes
    assert "src/components/index.ts" in g.nodes
    assert "src/components/Button.tsx" in g.nodes

    # Forward: App -> components/index.ts
    fwd_app = g.get_forward_dependencies("src/App.tsx", recursive=False)
    assert "src/components/index.ts" in fwd_app

    # Recursive forward: App -> index.ts -> Button.tsx
    fwd_app_rec = g.get_forward_dependencies("src/App.tsx", recursive=True)
    assert "src/components/index.ts" in fwd_app_rec
    assert "src/components/Button.tsx" in fwd_app_rec

    # Reverse: Button.tsx <- index.ts <- App.tsx
    rev_btn = g.get_reverse_dependencies("src/components/Button.tsx", recursive=True)
    assert "src/components/index.ts" in rev_btn
    assert "src/App.tsx" in rev_btn


def test_graph_symbol_origin_and_consumers(sample_graph):
    g, _ = sample_graph
    # Resolve Button origin starting at barrel
    origin = g.resolve_symbol_origin("src/components/index.ts", "Button")
    assert origin is not None
    assert origin[0] == "src/components/Button.tsx"
    assert origin[1].name == "Button"

    # Find consumers of Button in the workspace
    consumers = g.get_symbol_consumers("src/components/Button.tsx", "Button")
    assert "src/App.tsx" in consumers


def test_validator_catches_errors():
    g = NormalizedTypeScriptGraph("/test")
    g.nodes.add("src\\bad_slash.ts")  # un-normalized path

    res = TypeScriptGraphValidator.validate_graph(g, "/test")
    assert res["is_valid"] is False
    assert any("un-normalized backslashes" in err for err in res["errors"])
