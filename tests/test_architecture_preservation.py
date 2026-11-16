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
        "ARCHITECTURE.md",
        "docs/PROJECT_MAP.md",
        "docs/decisions/ADR-001-hybrid-dual-model-harness.md",
        "docs/decisions/ADR-002-websocket-protocol-multiplexing.md",
        "docs/decisions/ADR-003-host-security-sentinel-watchdog.md",
        "docs/decisions/ADR-004-deterministic-ast-patch-engine.md",
        "docs/decisions/ADR-005-sqlite-and-json-state-persistence.md",
        "docs/decisions/ADR-006-four-tier-economic-evidence-taxonomy.md",
    ]
    for d in required_docs:
        assert os.path.isfile(d), f"Document {d} must exist"
        with open(d, "r", encoding="utf-8") as f:
            content = f.read()
            assert content.strip(), f"Document {d} must not be empty"

    manifest_path = "src-tauri/py-runtime/manifest.json"
    assert os.path.isfile(manifest_path), f"Document {manifest_path} must exist"
    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        assert data is not None and data.get("bundle_sha256"), "Runtime manifest must be valid JSON"


def test_frontend_typecheck_and_build():
    """Valida se o build do frontend compila sem erros TypeScript."""
    res = subprocess.run(
        ["npm", "--prefix", "frontend", "run", "build"],
        capture_output=True,
        text=True,
        shell=True,
    )
    assert res.returncode == 0, f"npm run build failed:\n{res.stderr}\n{res.stdout}"
