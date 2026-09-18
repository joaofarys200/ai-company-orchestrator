"""
JARVIS OS — Phase 66: Multi-Agent Engineering Coordination & Conflict Arbitration
Module: workspace.py
Manages isolated transaction workspaces for concurrent engineering intents, preventing shared dirty writes.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import time
from typing import Any, Dict, List, Optional, Set


class IsolatedWorkspace:
    """Represents a dedicated transactional workspace sandbox."""

    def __init__(
        self,
        workspace_id: str,
        agent_id: str,
        intent_id: str,
        transaction_id: str,
        snapshot_id: str,
        sandbox_path: str,
    ):
        self.workspace_id = workspace_id
        self.agent_id = agent_id
        self.intent_id = intent_id
        self.transaction_id = transaction_id
        self.snapshot_id = snapshot_id
        self.sandbox_path = sandbox_path
        self.isolated_path = sandbox_path
        self.created_at = time.time()
        self.is_active = True

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def __contains__(self, item: str) -> bool:
        return hasattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workspace_id": self.workspace_id,
            "agent_id": self.agent_id,
            "intent_id": self.intent_id,
            "transaction_id": self.transaction_id,
            "snapshot_id": self.snapshot_id,
            "sandbox_path": self.sandbox_path,
            "isolated_path": self.isolated_path,
            "created_at": self.created_at,
            "is_active": self.is_active,
        }


class WorkspaceIsolationManager:
    """Provisions and cleans up isolated filesystem sandboxes for concurrent agent executions."""

    def __init__(self, root_workspace: Optional[str] = None):
        self.root_workspace = root_workspace or os.getcwd()
        self.active_sandboxes: Dict[str, IsolatedWorkspace] = {}  # workspace_id -> info
        self.snapshots: Dict[str, Dict[str, str]] = {}  # snapshot_id or tx_id -> {rel_path: content}

    @property
    def workspaces(self) -> Dict[str, IsolatedWorkspace]:
        return self.active_sandboxes

    def create_isolated_workspace(
        self,
        agent_id: str,
        arg2: str = "",
        arg3: str = "",
        arg4: Optional[str] = None,
        transaction_id: str = "",
        snapshot_id: str = "",
        intent_id: str = "",
        **kwargs,
    ) -> IsolatedWorkspace:
        """Create a dedicated workspace directory for an agent's transactional changes."""
        tx_id = transaction_id or (arg3 if arg4 is not None else arg2) or f"tx_{agent_id}"
        snap_id = snapshot_id or (arg4 if arg4 is not None else arg3) or "snap_base_0"
        it_id = intent_id or (arg2 if arg4 is not None else f"intent_{agent_id}")

        workspace_id = f"ws_{agent_id}_{it_id}_{int(time.time() * 1000) % 100000}"
        sandbox_path = tempfile.mkdtemp(prefix=f"jarvis_coord_{agent_id}_")

        ws = IsolatedWorkspace(
            workspace_id=workspace_id,
            agent_id=agent_id,
            intent_id=it_id,
            transaction_id=tx_id,
            snapshot_id=snap_id,
            sandbox_path=sandbox_path,
        )
        self.active_sandboxes[workspace_id] = ws
        return ws

    def release_workspace(self, workspace_id: str, preserve_on_error: bool = False) -> bool:
        """Tear down an isolated workspace after merge or abort."""
        ws = self.active_sandboxes.get(workspace_id)
        if not ws:
            return False

        if not preserve_on_error:
            shutil.rmtree(ws.sandbox_path, ignore_errors=True)

        ws.is_active = False
        del self.active_sandboxes[workspace_id]
        return True

    def get_workspace_for_intent(self, intent_id: str) -> Optional[IsolatedWorkspace]:
        for ws in self.active_sandboxes.values():
            if ws.intent_id == intent_id and ws.is_active:
                return ws
        return None

    def get_workspace_for_transaction(self, transaction_id: str) -> Optional[IsolatedWorkspace]:
        for ws in self.active_sandboxes.values():
            if ws.transaction_id == transaction_id and ws.is_active:
                return ws
        return None

    def create_snapshot(self, target_id: str) -> Dict[str, str]:
        """Capture all files and contents in the target transaction workspace."""
        ws = self.get_workspace_for_transaction(target_id) or self.active_sandboxes.get(target_id)
        path = ws.sandbox_path if ws else self.root_workspace
        snap_data: Dict[str, str] = {}
        if os.path.exists(path):
            for root, _, files in os.walk(path):
                for f in files:
                    full_p = os.path.join(root, f)
                    rel_p = os.path.relpath(full_p, path)
                    try:
                        with open(full_p, "r", encoding="utf-8") as fl:
                            snap_data[rel_p] = fl.read()
                    except Exception:
                        pass
        self.snapshots[target_id] = snap_data
        return snap_data

    def rollback_to_snapshot(self, target_id: str, snapshot_data: Dict[str, str]) -> bool:
        """Atomically revert the target workspace files back to snapshot_data."""
        ws = self.get_workspace_for_transaction(target_id) or self.active_sandboxes.get(target_id)
        path = ws.sandbox_path if ws else self.root_workspace
        if not os.path.exists(path):
            return False

        # 1. Overwrite/restore files from snapshot
        for rel_p, content in snapshot_data.items():
            dest = os.path.join(path, rel_p)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "w", encoding="utf-8") as f:
                f.write(content)

        # 2. Clean files not present in snapshot
        for root, _, files in os.walk(path):
            for f in files:
                full_p = os.path.join(root, f)
                rel_p = os.path.relpath(full_p, path)
                if rel_p not in snapshot_data:
                    try:
                        os.remove(full_p)
                    except Exception:
                        pass
        return True
