"""
JARVIS OS — Test Suite: Super-File Decomposition Validation (Fase 38)
"""

import os
import pytest


def test_mission_control_components_exist():
    base_dir = "frontend/src/features/missions/components"
    assert os.path.isdir(base_dir), f"Directory {base_dir} must exist"

    expected_files = [
        "MissionHeader.tsx",
        "MissionControlActions.tsx",
        "CancelConfirmModal.tsx",
        "IntentPreviewModal.tsx",
        "MissionOverviewPanel.tsx",
        "MissionTaskGraphPanel.tsx",
        "MissionRequirementsDiffPanel.tsx",
        "MissionPlanDiffPanel.tsx",
        "MissionEvidenceImpactPanel.tsx",
        "MissionWhyCausalPanel.tsx",
        "MissionRepairPanel.tsx",
        "MissionEvidenceLedgerPanel.tsx",
        "MissionAppPreviewPanel.tsx",
        "index.ts",
    ]

    for fname in expected_files:
        fpath = os.path.join(base_dir, fname)
        assert os.path.isfile(fpath), f"Component {fname} must exist in {base_dir}"
        assert os.path.getsize(fpath) > 100, f"Component {fname} must have non-trivial content"


def test_mission_control_center_size_reduction():
    mcc_path = "frontend/src/features/missions/MissionControlCenter.tsx"
    assert os.path.isfile(mcc_path)

    with open(mcc_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # The original file was 2519 lines. The decomposed composer must be < 800 lines.
    assert len(lines) < 800, f"MissionControlCenter.tsx has {len(lines)} lines, should be < 800"
    assert len(lines) > 200, "MissionControlCenter.tsx must remain a complete functional orchestrator"


def test_barrel_exports_integrity():
    barrel_path = "frontend/src/features/missions/components/index.ts"
    with open(barrel_path, "r", encoding="utf-8") as f:
        content = f.read()

    expected_exports = [
        "MissionHeader",
        "MissionControlActions",
        "CancelConfirmModal",
        "IntentPreviewModal",
        "MissionOverviewPanel",
        "MissionTaskGraphPanel",
        "MissionRequirementsDiffPanel",
        "MissionPlanDiffPanel",
        "MissionEvidenceImpactPanel",
        "MissionWhyCausalPanel",
        "MissionRepairPanel",
        "MissionEvidenceLedgerPanel",
        "MissionAppPreviewPanel",
    ]

    for exp in expected_exports:
        assert f"export {{ {exp} }}" in content, f"Barrel index.ts must export {exp}"


def test_critical_qa_selectors_preserved():
    """Garante que nenhum ID ou seletor essencial para o Browser QA ou testes foi perdido."""
    mcc_path = "frontend/src/features/missions/MissionControlCenter.tsx"
    with open(mcc_path, "r", encoding="utf-8") as f:
        mcc_content = f.read()

    # Check that components are imported and rendered
    assert "MissionHeader" in mcc_content
    assert "MissionControlActions" in mcc_content
    assert "IntentPreviewModal" in mcc_content
    assert "CancelConfirmModal" in mcc_content
    assert "MissionOverviewPanel" in mcc_content
    assert "MissionTaskGraphPanel" in mcc_content
    assert "MissionRequirementsDiffPanel" in mcc_content
    assert "MissionPlanDiffPanel" in mcc_content
    assert "MissionEvidenceImpactPanel" in mcc_content
    assert "MissionWhyCausalPanel" in mcc_content
    assert "MissionRepairPanel" in mcc_content
    assert "MissionEvidenceLedgerPanel" in mcc_content
    assert "MissionAppPreviewPanel" in mcc_content

    # Check component files contain the critical IDs
    header_path = "frontend/src/features/missions/components/MissionHeader.tsx"
    with open(header_path, "r", encoding="utf-8") as f:
        h_content = f.read()
    assert 'id="mission-status-badge"' in h_content
    assert 'id="mission-version-badge"' in h_content
    assert 'id="mission-intent-version-badge"' in h_content
    assert 'id="mission-plan-version-badge"' in h_content

    actions_path = "frontend/src/features/missions/components/MissionControlActions.tsx"
    with open(actions_path, "r", encoding="utf-8") as f:
        a_content = f.read()
    assert 'id="mission-cmd-pause"' in a_content
    assert 'id="mission-cmd-resume"' in a_content
    assert 'id="mission-cmd-cancel"' in a_content
    assert 'id="mission-cmd-edit-goal"' in a_content

    modal_path = "frontend/src/features/missions/components/IntentPreviewModal.tsx"
    with open(modal_path, "r", encoding="utf-8") as f:
        mod_content = f.read()
    assert 'id="intent-preview-modal"' in mod_content
    assert 'id="btn-analyze-intent"' in mod_content
    assert 'id="btn-apply-intent"' in mod_content
    assert 'id="btn-cancel-intent"' in mod_content
    assert 'id="preview-impact-badge"' in mod_content
