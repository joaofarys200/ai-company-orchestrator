from __future__ import annotations

import asyncio
import pytest

from agents.mission_state import MissionStateStore
from backend.services.chat_mission_bridge import ChatMissionBridge


class DummyFailingExecutionBridge(ChatMissionBridge):
    async def _execute_mission_work(self, *args, **kwargs):
        from backend.services.chat_mission_bridge import BridgeExecutionResult
        return BridgeExecutionResult(
            success=False,
            summary="",
            error="Erro controlado no teste: compilação falhou.",
        )


def test_mission_state_transitions_to_completed_on_success(tmp_path):
    async def _run():
        store = MissionStateStore(str(tmp_path))
        bridge = ChatMissionBridge(mission_state=store)
        
        res = await bridge.handle_directive(
            prompt="Adiciona testes unitários para a função de cálculo de impostos.",
            session_id=1,
            project_id="tax-service",
            correlation_id="tax_001",
        )
        
        assert res["status"] == "COMPLETED"
        mission_data = store.load_mission("tax-service", "m_tax_001")
        assert mission_data["mission"]["status"] == "COMPLETED"

    asyncio.run(_run())


def test_mission_state_transitions_to_failed_on_failure(tmp_path):
    async def _run():
        store = MissionStateStore(str(tmp_path))
        bridge = DummyFailingExecutionBridge(mission_state=store)
        
        res = await bridge.handle_directive(
            prompt="Refatora o módulo de autenticação.",
            session_id=1,
            project_id="auth-service",
            correlation_id="auth_fail_01",
        )
        
        assert res["status"] == "FAILED"
        assert "compilação falhou" in res["result"]
        mission_data = store.load_mission("auth-service", "m_auth_fail_01")
        assert mission_data["mission"]["status"] == "FAILED"

    asyncio.run(_run())
