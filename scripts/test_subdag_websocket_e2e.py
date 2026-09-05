from __future__ import annotations

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import websockets

AUTH_TOKEN = os.getenv("JARVIS_WS_TOKEN") or os.getenv("WS_AUTH_TOKEN") or "local-dev-token"
BACKEND_URL = f"ws://127.0.0.1:8001/?token={AUTH_TOKEN}"

async def recv_until(ws, target_types: set[str] | str, timeout: float = 6.0) -> dict:
    if isinstance(target_types, str):
        target_types = {target_types}
    end_time = asyncio.get_event_loop().time() + timeout
    while True:
        remaining = max(0.1, end_time - asyncio.get_event_loop().time())
        msg = await asyncio.wait_for(ws.recv(), timeout=remaining)
        data = json.loads(msg)
        if data.get("type") in target_types:
            return data

async def run_subdag_websocket_e2e():
    print("=" * 70)
    print("JARVIS OS - SUB-DAG EXPANSION (FASE 12) LIVE WEBSOCKET E2E TEST")
    print("=" * 70)

    async with websockets.connect(BACKEND_URL, close_timeout=5.0) as ws:
        print("[OK] Connected to live backend at", BACKEND_URL)
        await asyncio.sleep(0.1)

        # STEP 1: Decompose a structured mission into DAG
        print("\n--> STEP 1: Criar Missão com DAG Inicial")
        decomp_msg = {
            "type": "mission_plan_decompose",
            "project_id": "task-app",
            "title": "Missão E2E Teste Expansão Dinâmica",
            "objective": "Validar expansão declarativa de Sub-DAGs no runtime determinístico",
            "tasks": [
                {"title": "Setup Inicial", "category": "RESEARCH", "task_id": "TASK_INIT"},
                {"title": "Módulo Core", "category": "CODING", "dependencies": ["TASK_INIT"], "task_id": "TASK_CORE"},
                {"title": "Testes e Validação", "category": "REVIEW", "dependencies": ["TASK_CORE"], "task_id": "TASK_VERIFY"},
            ],
        }
        await ws.send(json.dumps(decomp_msg))
        snapshot_resp = await recv_until(ws, "mission_snapshot", timeout=6.0)
        mission_id = snapshot_resp["data"]["mission"]["mission_id"]
        mission_title = snapshot_resp["data"]["mission"]["title"]
        metadata = snapshot_resp["data"]["mission"].get("metadata", {})
        graph_version = metadata.get("graph_version", 1)
        print(f"[OK] Missão criada: {mission_title} ({mission_id}), DAG v{graph_version}")

        # STEP 2: Propor expansão dinâmica válida de Sub-DAG para TASK_CORE
        print("\n--> STEP 2: Propor expansão dinâmica de Sub-DAG (Gatilho: REQUIREMENT_DISCOVERY)")
        dynamic_task_id = "TASK_CORE_SUB_1"
        subdag_proposal = {
            "type": "mission_subdag_propose",
            "project_id": "task-app",
            "mission_id": mission_id,
            "parent_task_id": "TASK_CORE",
            "base_graph_version": graph_version,
            "trigger": "REQUIREMENT_DISCOVERY",
            "reason": "Descoberta de novos requisitos de segurança e sanitização de dados no Core",
            "tasks": [
                {
                    "task_id": dynamic_task_id,
                    "title": "Sanitização de Entradas no Módulo Core",
                    "description": "Implementar validações de limites de entrada e sanitização HTML/SQL",
                    "type": "CODING",
                    "required": True,
                    "estimated_complexity": "LOW"
                },
                {
                    "task_id": "TASK_CORE_SUB_2",
                    "title": "Testes Unitários de Sanitização",
                    "description": "Validar regressão de payloads adversariais",
                    "type": "CODING",
                    "required": True,
                    "estimated_complexity": "LOW"
                }
            ],
            "dependencies": [
                ["TASK_CORE_SUB_1", "TASK_CORE_SUB_2"]
            ],
            "acceptance_criteria": [
                {
                    "criterion_id": "CRIT_SANITIZATION_PASS",
                    "description": "100% dos testes de sanitização executados com sucesso",
                    "verification_method": "AUTOMATED_TEST",
                    "threshold": "100% PASS"
                }
            ]
        }
        await ws.send(json.dumps(subdag_proposal))

        # We expect a proposal result followed by (or accompanied by) updated snapshot
        result_msg = await recv_until(ws, "mission_subdag_proposal_result", timeout=6.0)
        print(f"[OK] Resultado da Proposta: success={result_msg.get('success')}, message='{result_msg.get('message')}'")
        assert result_msg.get("success") is True, f"Proposta falhou: {result_msg}"

        # Fetch fresh snapshot
        await ws.send(json.dumps({
            "type": "mission_resume_snapshot",
            "project_id": "task-app",
            "mission_id": mission_id
        }))
        updated_snapshot = await recv_until(ws, "mission_snapshot", timeout=6.0)
        new_graph_version = updated_snapshot["data"]["mission"].get("metadata", {}).get("graph_version")
        print(f"[OK] Versão da DAG atualizada transacionalmente: v{graph_version} -> v{new_graph_version}")
        assert new_graph_version == graph_version + 1, f"Expected graph_version {graph_version + 1}, got {new_graph_version}"

        # Verify added tasks and their parent links
        wps = updated_snapshot["data"]["work_packages"]
        sub1 = next((w for w in wps if w["work_package_id"] == "TASK_CORE_SUB_1"), None)
        sub2 = next((w for w in wps if w["work_package_id"] == "TASK_CORE_SUB_2"), None)
        assert sub1 is not None, "TASK_CORE_SUB_1 not found in snapshot"
        assert sub2 is not None, "TASK_CORE_SUB_2 not found in snapshot"
        print(f"[OK] Sub-tarefa 1 encontrada: {sub1['title']} (parent_task_id={sub1.get('parent_task_id')}, depth={sub1.get('expansion_depth')})")
        print(f"[OK] Sub-tarefa 2 encontrada: {sub2['title']} (parent_task_id={sub2.get('parent_task_id')}, depth={sub2.get('expansion_depth')})")
        assert sub1.get("parent_task_id") == "TASK_CORE"
        assert sub1.get("expansion_depth") == 1

        # STEP 3: Consultar histórico de expansões dinâmicas via mission_subdag_get_history
        print("\n--> STEP 3: Consultar histórico de expansões dinâmicas")
        await ws.send(json.dumps({
            "type": "mission_subdag_get_history",
            "project_id": "task-app",
            "mission_id": mission_id
        }))
        history_msg = await recv_until(ws, "mission_subdag_history", timeout=6.0)
        history = history_msg.get("history", [])
        print(f"[OK] Histórico recebido com {len(history)} registo(s):")
        assert len(history) >= 1, "Histórico deve conter pelo menos 1 expansão"
        latest = history[-1]
        print(f"     SubDAG: {latest.get('subdag_id')} | Trigger: {latest.get('trigger')} | Motivo: {latest.get('reason')}")
        print(f"     Transição: v{latest.get('graph_version_before')} -> v{latest.get('graph_version_after')}")
        print(f"     Tarefas adicionadas: {latest.get('tasks_added')}")
        print(f"     Arestas adicionadas: {latest.get('edges_added')}")
        assert latest.get("graph_version_before") == 1
        assert latest.get("graph_version_after") == 2
        assert "TASK_CORE_SUB_1" in latest.get("tasks_added", [])
        assert "TASK_CORE_SUB_2" in latest.get("tasks_added", [])

        # STEP 4: Testar rejeição determinística por versão obsoleta (Stale Base Graph Version)
        print("\n--> STEP 4: Testar rejeição de concorrência / versão obsoleta (Stale Version)")
        stale_proposal = {
            "type": "mission_subdag_propose",
            "project_id": "task-app",
            "mission_id": mission_id,
            "parent_task_id": "TASK_CORE",
            "base_graph_version": 1,  # Stale! Current is 2
            "trigger": "VALIDATION_FAILURE",
            "reason": "Tentativa de expansão concorrente com versão desatualizada",
            "tasks": [
                {
                    "task_id": dynamic_task_id,
                    "title": "Sanitização de Entradas no Módulo Core",
                    "type": "CODING"
                }
            ]
        }
        await ws.send(json.dumps(stale_proposal))
        stale_result = await recv_until(ws, "mission_subdag_proposal_result", timeout=6.0)
        print(f"[OK] Resultado recebido: success={stale_result.get('success')}, message='{stale_result.get('message')}'")
        assert stale_result.get("success") is False, "Proposta obsoleta devia ter sido rejeitada!"
        assert "stale" in stale_result.get("message", "").lower() or "version" in stale_result.get("message", "").lower()

        # STEP 5: Testar rejeição determinística por tarefa pai inexistente
        print("\n--> STEP 5: Testar rejeição de parent_task_id inexistente")
        invalid_parent_proposal = {
            "type": "mission_subdag_propose",
            "project_id": "task-app",
            "mission_id": mission_id,
            "parent_task_id": "TASK_DOES_NOT_EXIST",
            "base_graph_version": 2,
            "trigger": "REQUIREMENT_DISCOVERY",
            "reason": "Tentativa de expansão para tarefa inexistente",
            "tasks": [
                {"task_id": "TASK_ORPHAN", "title": "Orphan", "type": "CODING"}
            ]
        }
        await ws.send(json.dumps(invalid_parent_proposal))
        invalid_parent_result = await recv_until(ws, "mission_subdag_proposal_result", timeout=6.0)
        print(f"[OK] Resultado recebido: success={invalid_parent_result.get('success')}, message='{invalid_parent_result.get('message')}'")
        assert invalid_parent_result.get("success") is False, "Parent inexistente devia ter sido rejeitado!"

        print("\n" + "=" * 70)
        print("TODOS OS TESTES E2E WEBSOCKET DA FASE 12 FORAM CONCLUÍDOS COM 100% SUCESSO!")
        print("=" * 70)

if __name__ == "__main__":
    asyncio.run(run_subdag_websocket_e2e())
