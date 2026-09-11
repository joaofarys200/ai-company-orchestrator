"""
JARVIS OS — Test Suite: Architecture Preservation & Zero Regression (Fase 38)
"""

import json
import os
import subprocess
import pytest
from intelligence.repository_graph import RepositoryGraph


def test_public_api_surface_preservation():
    mcc_path = "frontend/src/features/missions/MissionControlCenter.tsx"
    with open(mcc_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Public exports must remain identical
    assert "export default MissionControlCenter;" in content
    assert "export const MissionControlCenter" in content
    assert "export interface MissionControlCenterProps" in content
    assert "export type ScenarioKey" in content
    assert "export const SCENARIOS" in content


def test_zero_circular_dependencies_in_repository():
    graph = RepositoryGraph(".")
    graph.scan()
    cycles = graph.detect_circular_dependencies()
    # No circular dependency should involve the new decomposed components
    decomposed_cycles = [
        c for c in cycles if any("features/missions" in node for node in c)
    ]
    assert len(decomposed_cycles) == 0, f"Circular dependencies detected in decomposed components: {decomposed_cycles}"


def test_docs_ledger_and_diffs_exist():
    required_docs = [
        "docs/phase38_super_file_audit.json",
        "docs/super_file_audit.json",
        "docs/phase38_decomposition_plan.json",
        "docs/phase38_architecture_before.json",
        "docs/phase38_architecture_after.json",
        "docs/phase38_api_diff.json",
        "docs/phase38_dependency_diff.json",
    ]

    for d in required_docs:
        assert os.path.isfile(d), f"Document {d} must exist"
        with open(d, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert data is not None, f"Document {d} must contain valid JSON"


def test_frontend_typecheck_and_build():
    """Valida se o build do frontend compila sem erros TypeScript."""
    res = subprocess.run(
        ["npm", "--prefix", "frontend", "run", "build"],
        capture_output=True,
        text=True,
        shell=True,
    )
    assert res.returncode == 0, f"npm run build failed:\n{res.stderr}\n{res.stdout}"
