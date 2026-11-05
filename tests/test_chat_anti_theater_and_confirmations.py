"""
Tests for Anti-Theater System Prompt, Direct Technical Answers with Project Context,
and Short Confirmation Execution Upgrades.
"""

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.mission_state import MissionStateStore
from backend.services.chat_mission_bridge import (
    ChatIntentType,
    ChatMissionBridge,
    ChatRequestResolver,
)
from backend.services.orchestration_runtime import (
    CASUAL_CHAT_SYSTEM_PROMPT,
    OrchestrationCallbacks,
    OrchestrationService,
)


def _setup_dina_project(root_path):
    dina_dir = root_path / "projects" / "dina"
    dina_dir.mkdir(parents=True, exist_ok=True)
    app_js = dina_dir / "app.js"
    app_js.write_text(
        """const express = require('express');
const app = express();
app.get('/scan-local-ips', (req, res) => {
    // executes arp -a and ping
    res.json({ ips: ['192.168.1.50'] });
});
module.exports = app;
""",
        encoding="utf-8",
    )
    pkg_json = dina_dir / "package.json"
    pkg_json.write_text('{"name": "dina", "version": "1.0.0"}', encoding="utf-8")
    return dina_dir


# ─────────────────────────────────────────────────────────────────────────────
# 1. Matar o Teatro no Prompt
# ─────────────────────────────────────────────────────────────────────────────

def test_prompt_anti_theater_prohibitions():
    """1. Garante que o prompt elimina encenação de cargos e proíbe promessas vazias."""
    # Eliminação total das diretrizes antigas de fingimento
    assert "coordenas a tua equipa" not in CASUAL_CHAT_SYSTEM_PROMPT.lower()
    assert "diz apenas que vais tratar do assunto" not in CASUAL_CHAT_SYSTEM_PROMPT.lower()

    # Nenhuma referência a subordinados imaginários no chat casual
    assert "Alex - Produto" not in CASUAL_CHAT_SYSTEM_PROMPT
    assert "Clara - Designer" not in CASUAL_CHAT_SYSTEM_PROMPT
    assert "Devon - Programador" not in CASUAL_CHAT_SYSTEM_PROMPT
    assert "Quinn - QA" not in CASUAL_CHAT_SYSTEM_PROMPT

    # Diretivas anti-teatro e respostas técnicas explícitas
    assert "NUNCA FAÇAS TEATRO" in CASUAL_CHAT_SYSTEM_PROMPT
    assert "NUNCA digas 'vou coordenar a equipa'" in CASUAL_CHAT_SYSTEM_PROMPT
    assert "RESPOSTAS TÉCNICAS DIRETAS E CONCRETAS" in CASUAL_CHAT_SYSTEM_PROMPT
    assert "FUNDAMENTAÇÃO NO PROJETO" in CASUAL_CHAT_SYSTEM_PROMPT

    # Diretivas anti-teatro e respostas técnicas explícitas
    assert "NUNCA FAÇAS TEATRO" in CASUAL_CHAT_SYSTEM_PROMPT
    assert "RESPOSTAS TÉCNICAS DIRETAS E CONCRETAS" in CASUAL_CHAT_SYSTEM_PROMPT
    assert "FUNDAMENTAÇÃO NO PROJETO" in CASUAL_CHAT_SYSTEM_PROMPT


# ─────────────────────────────────────────────────────────────────────────────
# 2. Respostas Técnicas Diretas com Contexto Real do Projeto
# ─────────────────────────────────────────────────────────────────────────────

def test_run_casual_chat_injects_real_project_context(tmp_path):
    """2. Consultas sobre um projeto injetam o contexto e ficheiros reais do projeto no modelo."""
    async def _run():
        _setup_dina_project(tmp_path)

        mock_models = MagicMock()
        mock_models.execute_local = AsyncMock()
        mock_models.execute_local.return_value = MagicMock(
            raw_text="No projeto Dina, podes adicionar lookup de MAC vendor no endpoint /scan-local-ips em app.js."
        )

        mock_connections = AsyncMock()
        mock_services = MagicMock()
        mock_services.mission_planner = MagicMock()
        mock_services.mission_planner.mission_state.projects_root = str(tmp_path / "projects")

        mock_callbacks = OrchestrationCallbacks(
            broadcast_state=AsyncMock(),
            open_local_application=AsyncMock(),
            run_in_main_loop=AsyncMock(),
            on_agent_message=AsyncMock(),
            on_file_update=AsyncMock(),
            on_kanban_update=AsyncMock(),
            build_template_payload=lambda x: {},
        )

        orch = OrchestrationService(
            services=mock_services,
            models=mock_models,
            connections=mock_connections,
            callbacks=mock_callbacks,
            conversation_history=[],
            logger=MagicMock(),
        )

        await orch.run_casual_chat(
            prompt="no projeto dina como garanto que existe alguma identificação de onde são os ips encontrados?",
            project_id="dina",
            correlation_id="corr_test_tech_answer",
        )

        assert mock_models.execute_local.called
        call_kwargs = mock_models.execute_local.call_args.kwargs
        sys_prompt = call_kwargs["system_prompt"]

        # Verifica se o contexto técnico real de Dina foi injetado no system prompt
        assert "[Contexto Técnico Real do Projeto 'dina']" in sys_prompt
        assert "app.js" in sys_prompt
        assert "scan-local-ips" in sys_prompt
        assert "DIRETIVAS ANTI-TEATRO" in sys_prompt

    asyncio.run(_run())


# ─────────────────────────────────────────────────────────────────────────────
# 3. Promover Confirmações Curtas para Execução Real
# ─────────────────────────────────────────────────────────────────────────────

def test_short_confirmation_inherits_context_and_triggers_execution(tmp_path):
    """3. 'então faz isso' com histórico herda o projeto/objetivo e aciona o pipeline de missão."""
    async def _run():
        _setup_dina_project(tmp_path)
        store = MissionStateStore(str(tmp_path / "projects"))
        mock_connections = AsyncMock()
        mock_connections.broadcast = AsyncMock()

        mock_orch = MagicMock()
        mock_orch._run_project_builder_if_requested = AsyncMock(return_value=False)
        mock_orch._run_agent_orchestration = AsyncMock(return_value="[OK] Funcionalidade integrada com sucesso.")
        mock_orch._suppress_chat_broadcast = False
        mock_orch.conversation_history = [
            {
                "role": "user",
                "content": "no projeto dina como garanto que existe alguma identificação de onde são os ips encontrados?",
            },
            {
                "role": "assistant",
                "content": "No projeto Dina, podes usar reverse DNS e prefixos MAC OUI no endpoint /scan-local-ips.",
            },
        ]

        bridge = ChatMissionBridge(
            mission_state=store,
            connections=mock_connections,
            orchestration_service=mock_orch,
        )

        # 1. Resolução isolada do router
        resolver = ChatRequestResolver()
        resolved = resolver.resolve_request("então faz isso", history=mock_orch.conversation_history)

        assert resolved.intent == ChatIntentType.EXECUTION_REQUEST
        assert resolved.project_id == "dina"
        assert resolved.requires_mission is True
        assert "identificação de onde são os ips encontrados" in resolved.objective.lower()
        assert resolved.context_reference.get("is_short_confirmation") is True

        # 2. Execução real pela bridge
        res = await bridge.handle_directive(
            prompt="então faz isso",
            session_id=1,
            correlation_id="corr_entao_faz_isso",
        )

        assert res["status"] == "COMPLETED"
        # Garante que uma missão real foi criada no MissionStateStore para o projeto dina
        missions = store.list_missions("dina")
        assert len(missions) == 1
        m = missions[0]
        assert "identificação de onde são os ips" in m["objective"].lower()
        assert m["status"] in {"ACTIVE", "COMPLETED"}

    asyncio.run(_run())


def test_short_confirmations_variants_avanca_trata_disso():
    """4. Variações como 'avança', 'trata disso', 'faz isso' herdam contexto sem cair em CHAT."""
    resolver = ChatRequestResolver()
    history = [
        {"role": "user", "content": "no projeto dina como implemento autenticação jwt?"},
        {"role": "assistant", "content": "Podes usar o pacote jsonwebtoken no app.js."},
    ]

    for variant in ["avança", "trata disso", "faz isso", "avança com isso", "procede", "pode ser", "força"]:
        res = resolver.resolve_request(variant, history=history)
        assert res.intent == ChatIntentType.EXECUTION_REQUEST, f"Falhou para variante '{variant}'"
        assert res.project_id == "dina"
        assert res.requires_mission is True
        assert "autenticação jwt" in res.objective.lower()


def test_short_confirmation_handles_intermediate_clarifications():
    """5. Perguntas monossilábicas intermediárias ('como?') não quebram a herança da diretiva raiz."""
    resolver = ChatRequestResolver()
    history = [
        {
            "role": "user",
            "content": "no projeto dina como garanto que existe alguma identificação de onde são os ips encontrados?",
        },
        {"role": "assistant", "content": "Podes usar reverse DNS e lookup de vendor MAC."},
        {"role": "user", "content": "como?"},
        {"role": "assistant", "content": "Instalando a biblioteca mac-lookup e chamando lookup(mac)."},
    ]

    # Utilizador confirma após diálogo com 'como?' no meio
    res = resolver.resolve_request("então faz isso", history=history)
    assert res.intent == ChatIntentType.EXECUTION_REQUEST
    assert res.project_id == "dina"
    assert res.requires_mission is True
    assert "identificação de onde são os ips" in res.objective.lower()


def test_short_confirmation_without_history_is_ambiguous():
    """6. Confirmação sem histórico prévio resulta em AMBIGUOUS com pedido de esclarecimento."""
    resolver = ChatRequestResolver()
    res = resolver.resolve_request("então faz isso", history=[])
    assert res.intent == ChatIntentType.AMBIGUOUS
    assert res.requires_mission is False
    assert "pretende que eu execute" in res.objective or "tarefa" in res.objective


def test_short_confirmation_safety_blocks_destructive_history():
    """7. Confirmação curta após diretiva destrutiva é bloqueada por REFUSED_POLICY."""
    resolver = ChatRequestResolver()
    history = [
        {"role": "user", "content": "apaga todos os ficheiros do projeto dina"},
        {"role": "assistant", "content": "Operação de eliminação pendente."},
    ]
    res = resolver.resolve_request("faz isso", history=history)
    assert res.intent == ChatIntentType.REFUSED_POLICY
    assert res.requires_approval is True
    assert "destrutiv" in res.refusal_reason.lower()
