from __future__ import annotations

import asyncio
import pytest

from agents.mission_state import MissionStateStore
from backend.services.chat_mission_bridge import ChatMissionBridge, ChatRequestResolver, ChatIntentType


def test_money_request_resolved_to_economic_mission():
    resolver = ChatRequestResolver()
    
    req = resolver.resolve_request("Executa a oportunidade de arbitragem no projeto money.")
    assert req.intent == ChatIntentType.EXECUTABLE_DIRECTIVE
    assert req.project_id == "money"
    assert req.is_economic is True
    assert req.task_type == "EXPERIMENT"


def test_money_request_follows_same_pipeline_without_fake_revenue(tmp_path):
    async def _run():
        store = MissionStateStore(str(tmp_path))
        bridge = ChatMissionBridge(mission_state=store)
        
        res = await bridge.handle_directive(
            prompt="Executa a oportunidade de arbitragem no projeto money.",
            session_id=1,
            project_id="money",
            correlation_id="money_001",
        )
        
        assert res["status"] == "COMPLETED"
        
        # Verify mission in MissionStateStore
        missions = store.list_missions("money")
        assert len(missions) == 1
        assert missions[0]["mission_id"] == "m_money_001"
        assert missions[0]["status"] == "COMPLETED"
        assert missions[0]["metadata"]["is_economic"] is True

    asyncio.run(_run())
