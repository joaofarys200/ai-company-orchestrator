"""
JARVIS OS — Phase 24 End-to-End Scenarios Validation Suite
Verifies the 5 Mandatory Scenarios defined in Phase 24 Section 10:
- Scenario A: Missing dependency, approval granted -> detected, requested, approved, installed in project, mission resumes to completion.
- Scenario B: Missing dependency, approval denied -> detected, requested, denied, no install, blocked step reported honestly.
- Scenario C: Dependency installation fails -> simulated failure reported honestly, no false success claim.
- Scenario D: Ordinary assisted modification -> no dependency required, normal mission execution lifecycle with file leases.
- Scenario E: Scope isolation -> approval granted for project A / operation A cannot be reused for project B or operation B.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
import pytest
from unittest.mock import AsyncMock

from agents.mission_state import MissionStateStore
from backend.services.chat_mission_bridge import ChatMissionBridge
from security.permission_gateway.project_dependency_manager import ProjectDependencyManager


def test_scenario_a_missing_dependency_approval_granted(tmp_path):
    """
    Scenario A:
    1. Submit task requiring missing dependency.
    2. Verify dependency is detected and approval requested.
    3. Verify no installation before approval.
    4. Approve request.
    5. Verify installation executes in project environment.
    6. Verify original development task resumes and completes.
    """
    async def _run():
        store = MissionStateStore(str(tmp_path))
        proj_dir = Path(store.projects_root) / "data-hub"
        proj_dir.mkdir(parents=True, exist_ok=True)
        (proj_dir / "main.py").write_text("# initial code", encoding="utf-8")

        mock_conn = AsyncMock()
        mock_conn.broadcast = AsyncMock()
        bridge = ChatMissionBridge(mission_state=store, connections=mock_conn)

        # 1. Submit development directive requiring 'pandas'
        res = await bridge.handle_directive(
            prompt="Adiciona geração de relatórios com o pacote pandas ao projeto data-hub",
            session_id=1,
            project_id="data-hub",
            correlation_id="corr_scen_a",
        )

        # 2 & 3. Verify waiting for approval and no installation occurred yet
        assert res["status"] == "WAITING_FOR_APPROVAL"
        assert res["package_name"] == "pandas"
        assert res["requires_approval"] is True
        req_id = res["request_id"]
        assert req_id in bridge._pending_dependency_requests
        assert not (proj_dir / "requirements.txt").exists()

        # Check mission state is BLOCKED pending approval
        m = store.load_mission("data-hub", f"m_corr_scen_a")
        assert m["mission"]["status"] == "BLOCKED"

        # Provide a safe mock runner for pip install
        def mock_installer(cmd, cwd, env):
            req_file = os.path.join(cwd, "requirements.txt")
            with open(req_file, "a", encoding="utf-8") as f:
                f.write("pandas>=2.0.0\n")
            return 0, "Successfully installed pandas-2.2.0", ""

        bridge._pending_dependency_requests[req_id]["mock_run_cmd"] = mock_installer

        # 4. User grants approval by responding 'aprovo'
        approval_res = await bridge.handle_directive(
            prompt="aprovo",
            session_id=1,
            project_id="data-hub",
            correlation_id="corr_scen_a_approval",
        )

        # 5 & 6. Verify installation succeeded and task resumed to completion
        assert approval_res["status"] == "COMPLETED"
        assert approval_res["dependency_installed"] == "pandas"
        assert (proj_dir / "requirements.txt").exists()
        assert "pandas>=2.0.0" in (proj_dir / "requirements.txt").read_text(encoding="utf-8")

        # Verify mission completed in state store
        updated_m = store.load_mission("data-hub", f"m_corr_scen_a")
        assert updated_m["mission"]["status"] == "COMPLETED"

    asyncio.run(_run())


def test_scenario_b_missing_dependency_approval_denied(tmp_path):
    """
    Scenario B:
    1. Submit task requiring missing dependency.
    2. Verify dependency detected and authorization requested.
    3. User denies request ('recuso').
    4. Verify no installation occurs.
    5. Verify JARVIS reports blocked step and explains consequence.
    """
    async def _run():
        store = MissionStateStore(str(tmp_path))
        proj_dir = Path(store.projects_root) / "web-miner"
        proj_dir.mkdir(parents=True, exist_ok=True)

        mock_conn = AsyncMock()
        mock_conn.broadcast = AsyncMock()
        bridge = ChatMissionBridge(mission_state=store, connections=mock_conn)

        # 1 & 2. Submit directive requiring 'beautifulsoup4'
        res = await bridge.handle_directive(
            prompt="Cria script de recolha web com beautifulsoup4 no projeto web-miner",
            session_id=1,
            project_id="web-miner",
            correlation_id="corr_scen_b",
        )

        assert res["status"] == "WAITING_FOR_APPROVAL"
        assert res["package_name"] == "beautifulsoup4"
        req_id = res["request_id"]

        # 3. User denies request
        denial_res = await bridge.handle_directive(
            prompt="recuso",
            session_id=1,
            project_id="web-miner",
            correlation_id="corr_scen_b_denial",
        )

        # 4 & 5. Verify no installation and blocked step reported
        assert denial_res["status"] == "BLOCKED"
        assert "recusada pelo utilizador" in denial_res["reason"].lower()
        assert not (proj_dir / "requirements.txt").exists()

        m = store.load_mission("web-miner", f"m_corr_scen_b")
        assert m["mission"]["status"] == "BLOCKED"

    asyncio.run(_run())


def test_scenario_c_dependency_installation_fails_honestly(tmp_path):
    """
    Scenario C:
    1. Simulate controlled installation failure.
    2. Verify JARVIS does not report false success.
    3. Verify failure is reported with affected environment details.
    """
    async def _run():
        store = MissionStateStore(str(tmp_path))
        proj_dir = Path(store.projects_root) / "broken-app"
        proj_dir.mkdir(parents=True, exist_ok=True)

        bridge = ChatMissionBridge(mission_state=store)

        res = await bridge.handle_directive(
            prompt="Instala o pacote non-existent-library-xyz no projeto broken-app",
            session_id=1,
            project_id="broken-app",
            correlation_id="corr_scen_c",
        )

        assert res["status"] == "WAITING_FOR_APPROVAL"
        req_id = res["request_id"]

        # Inject simulated failure
        def mock_failed_installer(cmd, cwd, env):
            return 1, "", "ERROR: No matching distribution found for non-existent-library-xyz"

        bridge._pending_dependency_requests[req_id]["mock_run_cmd"] = mock_failed_installer

        approval_res = await bridge.handle_directive(
            prompt="aprovo",
            session_id=1,
            project_id="broken-app",
            correlation_id="corr_scen_c_approval",
        )

        # Honest failure assertion
        assert approval_res["status"] == "FAILED"
        assert "no matching distribution" in approval_res["error"].lower()
        m = store.load_mission("broken-app", f"m_corr_scen_c")
        assert m["mission"]["status"] == "FAILED"

    asyncio.run(_run())


def test_scenario_d_ordinary_assisted_modification(tmp_path):
    """
    Scenario D:
    1. Submit development task that requires NO new dependency.
    2. Verify JARVIS does NOT request unnecessary approval.
    3. Verify file lease is acquired atomically and mission completes normally.
    """
    async def _run():
        store = MissionStateStore(str(tmp_path))
        proj_dir = Path(store.projects_root) / "math-core"
        proj_dir.mkdir(parents=True, exist_ok=True)
        main_file = proj_dir / "main.py"
        main_file.write_text("def add(a, b): return a + b\n", encoding="utf-8")

        bridge = ChatMissionBridge(mission_state=store)

        # Standard directive without third-party libraries
        res = await bridge.handle_directive(
            prompt="Refatora a função add em main.py no projeto math-core para adicionar docstring explicativa",
            session_id=1,
            project_id="math-core",
            correlation_id="corr_scen_d",
        )

        assert res["status"] == "COMPLETED"
        assert res.get("requires_approval") is not True

        # Check file lease was released
        from agents.file_lease_manager import get_file_lease_manager
        lease_mgr = get_file_lease_manager()
        assert not lease_mgr.is_file_locked(str(main_file))

        m = store.load_mission("math-core", f"m_corr_scen_d")
        assert m["mission"]["status"] == "COMPLETED"

    asyncio.run(_run())


def test_scenario_e_scope_isolation_cross_project_and_operation(tmp_path):
    """
    Scenario E:
    1. Create an approval for operation DEPENDENCY_INSTALL on proj-alpha.
    2. Attempt to use that authorization for proj-beta -> Rejected!
    3. Attempt to use that authorization for SHELL_EXEC -> Rejected!
    """
    mgr = ProjectDependencyManager()
    proj_a = tmp_path / "proj-alpha"
    proj_b = tmp_path / "proj-beta"
    proj_a.mkdir()
    proj_b.mkdir()

    req = mgr.prepare_authorization_request(
        project_root=str(proj_a),
        package_name="scipy",
        reason="Cálculos matemáticos para alpha",
        project_id="proj-alpha",
        mission_id="m_scen_e",
    )

    mgr.gateway.approve_request(req.request_id, decided_by="user_owner")

    # 1. Valid on proj-alpha
    assert mgr.can_execute(
        request_id=req.request_id,
        operation_type=f"install_package:scipy",
        target_project="proj-alpha",
    ) is True

    # 2. Reject cross-project hijacking on proj-beta
    assert mgr.can_execute(
        request_id=req.request_id,
        operation_type=f"install_package:scipy",
        target_project="proj-beta",
    ) is False

    assert mgr.can_execute(
        request_id=req.request_id,
        operation_type="SHELL_EXEC",
        target_project="proj-alpha",
    ) is False
