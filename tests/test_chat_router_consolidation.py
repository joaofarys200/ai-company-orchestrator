from __future__ import annotations

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from agents.mission_state import MissionStateStore
from backend.services.chat_mission_bridge import (
    ChatIntentType,
    ChatMissionBridge,
    ChatRequestResolver,
    ResolvedChatRequest,
)
from backend.services.model_service import ModelExecutionService


# ─────────────────────────────────────────────────────────────────────────────
# 16 REGRESSION SCENARIOS — CONSOLIDAÇÃO DO CHAT ROUTER
# ─────────────────────────────────────────────────────────────────────────────

def _setup_dina(tmp_path):
    dina_dir = os.path.join(tmp_path, "workspace", "projects", "dina")
    os.makedirs(dina_dir, exist_ok=True)
    content = (
        "const express = require('express');\n"
        "const app = express();\n"
        "// arp -a /scan-local-ips\n"
        "app.get('/scan-local-ips', (req, res) => {\n"
        "    res.json({ ips: ['192.168.1.50'] });\n"
        "});\n"
        "module.exports = app;\n"
    )
    with open(os.path.join(dina_dir, "app.js"), "w", encoding="utf-8") as wf:
        wf.write(content)


def test_scenario_01_saudacao_simples():
    """1. Saudação simples ('Olá') -> CHAT, 0 missões, 0 chamadas de código."""
    resolver = ChatRequestResolver()
    res = resolver.resolve_request("Olá")
    assert res.intent in {ChatIntentType.CHAT, ChatIntentType.CONVERSATIONAL}
    assert res.requires_mission is False
    assert res.requires_model is True
    assert res.requires_external_network is False


def test_scenario_02_pergunta_sobre_sistema():
    """2. Pergunta sobre o sistema ('O que consegues fazer?') -> CHAT, 0 missões."""
    resolver = ChatRequestResolver()
    res = resolver.resolve_request("O que consegues fazer?")
    assert res.intent in {ChatIntentType.CHAT, ChatIntentType.CONVERSATIONAL}
    assert res.requires_mission is False


def test_scenario_03_pergunta_educada_criar_app():
    """3. Pergunta educada para criar app ('Podes criar uma app para gerir tarefas?') -> EXECUTION_REQUEST.
    CRÍTICO: Perguntas com ? contendo verbos executivos de programação NUNCA podem ser classificadas como CHAT casual.
    """
    resolver = ChatRequestResolver()
    res = resolver.resolve_request("Podes criar uma app para gerir tarefas?")
    assert res.intent in {ChatIntentType.EXECUTION_REQUEST, ChatIntentType.EXECUTABLE_DIRECTIVE}
    assert res.requires_mission is True
    assert "tarefas" in res.title.lower() or "app" in res.title.lower()


def test_scenario_04_consulta_projeto_existente(tmp_path):
    """4. Consulta de projeto existente ('Consegues aceder ao projeto dina?') -> PROJECT_QUERY / INSPECTION.
    Garante que não cria missão e obtém ficheiros físicos do disco.
    """
    async def _run():
        _setup_dina(tmp_path)
        store = MissionStateStore(str(tmp_path))
        mock_connections = AsyncMock()
        bridge = ChatMissionBridge(mission_state=store, connections=mock_connections)

        res = await bridge.handle_directive(
            prompt="Consegues aceder ao projeto dina?",
            session_id=1,
            correlation_id="corr_scen_04",
        )
        assert res["status"] == "COMPLETED"
        assert res["intent"] in {"PROJECT_QUERY", "ANALYSIS"}
        # Deve encontrar app.js do projeto real
        assert "app.js" in res["result"]
        # 0 missões no store
        assert len(store.list_missions("dina")) == 0

    asyncio.run(_run())


def test_scenario_05_consulta_projeto_inexistente(tmp_path):
    """5. Consulta de projeto inexistente -> Resposta factual informando ausência sem inventar ficheiros nem criar diretório fantasma."""
    async def _run():
        store = MissionStateStore(str(tmp_path))
        mock_connections = AsyncMock()
        bridge = ChatMissionBridge(mission_state=store, connections=mock_connections)

        non_existent_proj = "projeto-inexistente-xyz-123"
        res = await bridge.handle_directive(
            prompt=f"Consegues aceder ao projeto {non_existent_proj}?",
            session_id=1,
            correlation_id="corr_scen_05",
        )
        assert res["status"] == "COMPLETED"
        assert "não existe no disco" in res["result"] or "Procurei pelo projeto" in res["result"]
        # Não deve criar a pasta no disco
        target_dir = os.path.join("workspace", "projects", non_existent_proj)
        assert not os.path.exists(target_dir)
        # 0 missões criadas no store
        assert not os.path.exists(os.path.join(tmp_path, "workspace", ".jarvis", "projects", non_existent_proj))

    asyncio.run(_run())


def test_scenario_06_leitura_ficheiro_especifico(tmp_path):
    """6. Consulta de ficheiro específico ('Mostra o ficheiro app.js do projeto dina') -> FILE_READ com proveniência de disco."""
    async def _run():
        _setup_dina(tmp_path)
        store = MissionStateStore(str(tmp_path))
        mock_connections = AsyncMock()
        bridge = ChatMissionBridge(mission_state=store, connections=mock_connections)

        res = await bridge.handle_directive(
            prompt="Mostra o ficheiro app.js do projeto dina",
            session_id=1,
            correlation_id="corr_scen_06",
        )
        assert res["status"] == "COMPLETED"
        assert res["intent"] in {"FILE_READ", "ANALYSIS"}
        assert "app.js" in res["result"]
        assert "arp -a" in res["result"]
        assert res.get("metadata", {}).get("provenance") == "disk"
        assert len(store.list_missions("dina")) == 0

    asyncio.run(_run())


def test_scenario_07_entrega_ficheiro_anexo(tmp_path):
    """7. Entrega de ficheiro ('Anexa o app.js') com projeto no histórico -> FILE_DELIVERY."""
    async def _run():
        _setup_dina(tmp_path)
        store = MissionStateStore(str(tmp_path))
        mock_connections = AsyncMock()
        mock_orch = MagicMock()
        mock_orch.conversation_history = [
            {"role": "user", "content": "consegues aceder ao projeto dina?"},
            {"role": "assistant", "content": "Sim, contém app.js"},
        ]
        bridge = ChatMissionBridge(mission_state=store, connections=mock_connections, orchestration_service=mock_orch)

        res = await bridge.handle_directive(
            prompt="Anexa o app.js",
            session_id=1,
            correlation_id="corr_scen_07",
        )
        assert res["status"] == "COMPLETED"
        assert res["intent"] in {"FILE_DELIVERY", "ANALYSIS"}
        assert "app.js" in res["result"]
        assert len(store.list_missions("dina")) == 0

    asyncio.run(_run())


def test_scenario_08_pedido_ficheiro_integral_apos_resumo(tmp_path):
    """8. Pedido de ficheiro integral após resumo ('Fornece tudo') -> Continuação e entrega integral sem truncagem."""
    async def _run():
        _setup_dina(tmp_path)
        store = MissionStateStore(str(tmp_path))
        mock_connections = AsyncMock()
        mock_orch = MagicMock()
        mock_orch.conversation_history = [
            {"role": "user", "content": "mostra o ficheiro app.js do projeto dina"},
            {"role": "assistant", "content": "Aqui está o app.js [Conteúdo truncado: a mostrar 200 de 300 linhas...]"},
        ]
        bridge = ChatMissionBridge(mission_state=store, connections=mock_connections, orchestration_service=mock_orch)

        res = await bridge.handle_directive(
            prompt="fornece tudo",
            session_id=1,
            correlation_id="corr_scen_08",
        )
        assert res["status"] == "COMPLETED"
        assert "conteúdo integral" in res["result"] or "app.js" in res["result"]
        assert res.get("metadata", {}).get("truncated") is False
        assert len(store.list_missions("dina")) == 0

    asyncio.run(_run())


def test_scenario_09_desabafo_queixa_utilizador():
    """9. Desabafo / queixa do utilizador ('Isto está muito lento') -> CHAT (sem criar missão)."""
    resolver = ChatRequestResolver()
    res = resolver.resolve_request("Isto está muito lento, porque demora tanto?")
    assert res.intent in {ChatIntentType.CHAT, ChatIntentType.CONVERSATIONAL}
    assert res.requires_mission is False


def test_scenario_10_tentativa_contextual_com_historico(tmp_path):
    """10. Tentativa contextual após resposta ('Tenta de novo') -> Resolução pelo contexto anterior."""
    async def _run():
        _setup_dina(tmp_path)
        store = MissionStateStore(str(tmp_path))
        mock_connections = AsyncMock()
        mock_orch = MagicMock()
        mock_orch.conversation_history = [
            {"role": "user", "content": "consegues aceder ao projeto dina?"},
            {"role": "assistant", "content": "Sim, consigo aceder perfeitamente."},
        ]
        bridge = ChatMissionBridge(mission_state=store, connections=mock_connections, orchestration_service=mock_orch)

        res = await bridge.handle_directive(
            prompt="tenta de novo",
            session_id=1,
            correlation_id="corr_scen_10",
        )
        assert res["status"] == "COMPLETED"
        assert res["intent"] in {"PROJECT_QUERY", "ANALYSIS"}
        assert "dina" in res["result"]
        assert len(store.list_missions("dina")) == 0

    asyncio.run(_run())


def test_scenario_11_tentativa_sem_contexto_anterior():
    """11. Tentativa sem contexto anterior -> Pedido de esclarecimento sem erro e sem missão."""
    resolver = ChatRequestResolver()
    res = resolver.resolve_request("tenta de novo", history=[])
    assert res.intent in {ChatIntentType.CHAT, ChatIntentType.CONVERSATIONAL, ChatIntentType.AMBIGUOUS}
    assert res.requires_mission is False
    assert "novamente" in res.objective or "esclarecer" in res.objective


def test_scenario_12_tentativa_apos_operacao_destrutiva():
    """12. Tentativa após operação destrutiva -> Bloqueio por política de segurança (REFUSED_POLICY).
    Garante que comandos perigosos não são re-executados inadvertidamente com 'tenta de novo'.
    """
    resolver = ChatRequestResolver()
    destructive_history = [
        {"role": "user", "content": "apaga todos os ficheiros da base de dados e faz drop table"},
        {"role": "assistant", "content": "Operação bloqueada por política de segurança."},
    ]
    res = resolver.resolve_request("tenta de novo", history=destructive_history)
    assert res.intent == ChatIntentType.REFUSED_POLICY
    assert res.requires_approval is True
    assert "destrutiv" in res.refusal_reason.lower()


def test_scenario_13_input_ambiguo():
    """13. Input ambíguo ('Faz aquilo') -> AMBIGUOUS com pedido de esclarecimento."""
    resolver = ChatRequestResolver()
    res = resolver.resolve_request("faz aquilo agora")
    # Não possui alvo nem verbo explícito de código -> AMBIGUOUS
    assert res.intent in {ChatIntentType.AMBIGUOUS, ChatIntentType.CHAT}
    assert res.requires_mission is False


def test_scenario_14_queda_modelo_local_sem_fallback_autorizado():
    """14. Queda de modelo local sem fallback autorizado -> Mensagem explícita de erro sem leak de credenciais ou chamada Gemini."""
    async def _run():
        service = ModelExecutionService()
        service.execute = AsyncMock(side_effect=Exception("ConnectionRefusedError: Ollama offline"))
        
        with patch.dict(os.environ, {"ORCHESTRATOR_MODE": "local", "ALLOW_EXTERNAL_FALLBACK": "false", "GEMINI_API_KEY": "fake_secret_key"}):
            with pytest.raises(RuntimeError) as exc_info:
                await service.execute_local(
                    operation="test_local",
                    system_prompt="sys",
                    user_prompt="user",
                    timeout_seconds=1.0,
                )
            
            # Garante que service.execute foi chamado apenas para ollama e NUNCA para gemini
            assert service.execute.call_count == 1
            call_kwargs = service.execute.call_args.kwargs
            assert call_kwargs.get("provider") == "ollama"
            # Garante que o erro explica explicitamente a recusa de fallback externo
            assert "fallback para fornecedores externos está bloqueado" in str(exc_info.value).lower()
            # Garante que a chave fake nunca vazou no texto do erro
            assert "fake_secret_key" not in str(exc_info.value)

    asyncio.run(_run())


def test_scenario_15_resposta_unica_garantida(tmp_path):
    """15. Resposta única garantida -> Nenhuma duplicação de mensagens para o mesmo correlation_id."""
    async def _run():
        store = MissionStateStore(str(tmp_path))
        mock_connections = AsyncMock()
        mock_connections.broadcast = AsyncMock()
        bridge = ChatMissionBridge(mission_state=store, connections=mock_connections)

        corr_id = "corr_unique_resp_test"
        # 1. Primeira emissão
        await bridge.broadcast_chat("JARVIS", "Assistant", "Resposta inicial legítima.", correlation_id=corr_id)
        # 2. Tentativa duplicada com o mesmo correlation_id
        await bridge.broadcast_chat("JARVIS", "Assistant", "Segunda resposta duplicada.", correlation_id=corr_id)

        # Inspeciona broadcasts
        calls = [c.args[0] for c in mock_connections.broadcast.call_args_list]
        assistant_msgs = [c for c in calls if c.get("type") == "chat" and c.get("role") == "Assistant"]
        
        # Exatamente UMA resposta permitida!
        assert len(assistant_msgs) == 1
        assert assistant_msgs[0]["content"] == "Resposta inicial legítima."

    asyncio.run(_run())


def test_scenario_16_acesso_fora_dos_limites_bloqueado(tmp_path):
    """16. Acesso a ficheiro fora dos limites do projeto ('../../etc/passwd' ou path traversal) -> Bloqueado com erro explícito de segurança."""
    async def _run():
        store = MissionStateStore(str(tmp_path))
        mock_connections = AsyncMock()
        bridge = ChatMissionBridge(mission_state=store, connections=mock_connections)

        # Tentativa de ler ficheiro fora dos limites
        success, reply, meta = bridge._read_local_file(
            project_id="dina",
            filename="../../secret_credentials.env",
        )
        assert success is False
        assert "fora do diretório autorizado" in reply or "Acesso negado" in reply
        assert meta.get("error") == "PERMISSION_DENIED"

    asyncio.run(_run())
