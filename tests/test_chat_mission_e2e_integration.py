from __future__ import annotations

import asyncio
import sqlite3
import pytest

from agents.mission_state import MissionStateStore
from backend.services.chat_mission_bridge import ChatMissionBridge
from backend.websocket.gateway import ConnectionManager
from database import get_connection, init_db


class RecordingConnectionManager(ConnectionManager):
    def __init__(self):
        super().__init__()
        self.sent_messages = []

    async def broadcast(self, message: dict) -> None:
        self.sent_messages.append(message)


def test_full_chat_to_mission_e2e(tmp_path, monkeypatch):
    async def _run():
        test_db = str(tmp_path / "test_e2e.db")
        
        def fake_get_connection():
            return sqlite3.connect(test_db)
            
        monkeypatch.setattr("database.get_connection", fake_get_connection)
        init_db()
        
        store = MissionStateStore(str(tmp_path))
        conn_mgr = RecordingConnectionManager()
        
        bridge = ChatMissionBridge(
            mission_state=store,
            connections=conn_mgr,
        )
        
        prompt = "Cria uma aplicação simples para gerir tarefas. Guardar os dados localmente. Mostrar criação, edição e eliminação."
        
        res = await bridge.handle_directive(
            prompt=prompt,
            session_id=1,
            project_id="task-manager-app",
            correlation_id="e2e_task_01",
        )
        
        # 1. Check Execution Result
        assert res["status"] == "COMPLETED"
        assert res["mission_id"] == "m_e2e_task_01"
        
        # 2. Check Mission Persistence in MissionStateStore
        missions = store.list_missions("task-manager-app")
        assert len(missions) == 1
        assert missions[0]["mission_id"] == "m_e2e_task_01"
        assert missions[0]["status"] == "COMPLETED"
        
        # 3. Check WebSocket Messages Streamed to Client
        msg_types = [m.get("type") for m in conn_mgr.sent_messages]
        assert "mission_list" in msg_types
        assert "chat" in msg_types
        
        # Verify sender in chat messages is canonical JARVIS
        chat_msgs = [m for m in conn_mgr.sent_messages if m.get("type") == "chat"]
        for cm in chat_msgs:
            assert cm.get("sender") == "JARVIS"
            assert "OPENCLAW" not in cm.get("sender", "").upper()
            # Ensure no mojibake
            assert "ðŸ" not in cm.get("content", "")
            assert "Ã" not in cm.get("content", "")

    asyncio.run(_run())
