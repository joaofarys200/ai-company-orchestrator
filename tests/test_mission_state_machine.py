from __future__ import annotations

import os
import pytest

from agents.mission_orchestrator import MissionLifecycleStatus
from agents.mission_state import MissionStateError, MissionStateStore
from agents.task_graph import TaskGraph, TaskNode, TaskStatus


def test_mission_state_transitions(tmp_path):
    store = MissionStateStore(str(tmp_path))
    os.makedirs(os.path.join(store.projects_root, "test-proj"), exist_ok=True)
    
    # 1. Create Mission (DRAFT)
    res = store.create_mission(
        project_id="test-proj",
        title="Test Mission",
        objective="Validate state machine",
        mission_id="m_sm_01",
    )
    loaded = store.load_mission("test-proj", "m_sm_01")
    assert loaded["mission"]["status"] == "DRAFT"

    # 2. DRAFT -> READY
    store.set_mission_status("test-proj", "m_sm_01", "READY", expected_version=loaded["mission"]["version"])
    loaded = store.load_mission("test-proj", "m_sm_01")
    assert loaded["mission"]["status"] == "READY"

    # 3. READY -> ACTIVE
    store.set_mission_status("test-proj", "m_sm_01", "ACTIVE", expected_version=loaded["mission"]["version"])
    loaded = store.load_mission("test-proj", "m_sm_01")
    assert loaded["mission"]["status"] == "ACTIVE"

    # 4. Invalid transition: ACTIVE cannot go directly to DRAFT
    with pytest.raises(MissionStateError):
        store.set_mission_status("test-proj", "m_sm_01", "DRAFT", expected_version=loaded["mission"]["version"])


def test_task_state_transitions():
    node = TaskNode(task_id="T1", title="Task 1")
    assert node.status == TaskStatus.PENDING

    # Transition to READY
    node.status = TaskStatus.READY
    assert node.status == TaskStatus.READY

    # Transition to RUNNING
    node.status = TaskStatus.RUNNING
    assert node.status == TaskStatus.RUNNING

    # Transition to COMPLETED
    node.status = TaskStatus.COMPLETED
    assert node.status == TaskStatus.COMPLETED
