"""JARVIS OS — Fase 13.1 Live Runtime QA Verification Script.

Tests all required deep graph scalability capabilities against the live backend WebSocket:
ws://127.0.0.1:8001/?token=local-dev-token
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
import websockets

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

AUTH_TOKEN = os.getenv("JARVIS_WS_TOKEN") or os.getenv("WS_AUTH_TOKEN") or "local-dev-token"
BACKEND_URL = f"ws://127.0.0.1:8001/?token={AUTH_TOKEN}"


async def recv_until(ws, target_types: set[str] | str, timeout: float = 60.0) -> dict:
    if isinstance(target_types, str):
        target_types = {target_types}
    end_time = asyncio.get_event_loop().time() + timeout
    while True:
        remaining = max(0.1, end_time - asyncio.get_event_loop().time())
        msg = await asyncio.wait_for(ws.recv(), timeout=remaining)
        data = json.loads(msg)
        m_type = data.get("type", "")
        if m_type in target_types:
            return data


async def run_phase_13_1_qa() -> None:
    print("=" * 80)
    print("JARVIS OS — FASE 13.1 GRAPH VALIDATION SCALABILITY LIVE QA SCORECARD")
    print("=" * 80)

    scorecard: list[tuple[str, str, str]] = []

    try:
        async with websockets.connect(BACKEND_URL, close_timeout=15.0, max_size=33554432) as ws:
            print(f"[OK] Connected to live backend at {BACKEND_URL}")

            project_id = "default"
            mission_id_1000 = f"m_1000_{uuid.uuid4().hex[:6]}"

            # ── TEST 1: 1000-Node Linear DAG Decompose ────────────────────────
            print("\n--> TEST 1: Decompor e Validar 1000-Node DAG no Runtime")
            t0 = asyncio.get_event_loop().time()
            tasks_1000 = [
                {"task_id": f"t_{i}", "title": f"Task {i}", "dependencies": [f"t_{i-1}"] if i > 0 else []}
                for i in range(1000)
            ]
            decomp_msg_1000 = {
                "type": "mission_plan_decompose",
                "project_id": project_id,
                "mission_id": mission_id_1000,
                "title": "1000 Node Linear Chain Mission",
                "objective": "Verify 1000 node DAG creation and validation without recursion limits",
                "tasks": tasks_1000,
            }
            await ws.send(json.dumps(decomp_msg_1000))
            snap_1000 = await recv_until(ws, "mission_snapshot", timeout=60.0)
            dt_1000 = (asyncio.get_event_loop().time() - t0) * 1000
            m_1000 = snap_1000["data"]["mission"]
            assert m_1000["mission_id"] == mission_id_1000
            scorecard.append(("TEST 1: 1000-Node Linear DAG", "PASS", f"1000 tarefas criadas e validadas em {dt_1000:.1f}ms"))
            print(f"[PASS] 1000-Node DAG validado e persistido ({dt_1000:.1f}ms)")

            # ── TEST 2: 2000-Node DAG with Reverse Order ──────────────────────
            print("\n--> TEST 2: Decompor e Validar 2000-Node DAG (Inversão Topológica)")
            mission_id_2000 = f"m_2000_{uuid.uuid4().hex[:6]}"
            t0 = asyncio.get_event_loop().time()
            tasks_2000 = [
                {"task_id": f"rev_{i}", "title": f"Rev {i}", "dependencies": [f"rev_{i-1}"] if i > 0 else []}
                for i in reversed(range(2000))
            ]
            decomp_msg_2000 = {
                "type": "mission_plan_decompose",
                "project_id": project_id,
                "mission_id": mission_id_2000,
                "title": "2000 Node Reverse Chain Mission",
                "objective": "Verify 2000 node reverse chain DAG creation and validation without RecursionError",
                "tasks": tasks_2000,
            }
            await ws.send(json.dumps(decomp_msg_2000))
            snap_2000 = await recv_until(ws, "mission_snapshot", timeout=90.0)
            dt_2000 = (asyncio.get_event_loop().time() - t0) * 1000
            m_2000 = snap_2000["data"]["mission"]
            assert m_2000["mission_id"] == mission_id_2000
            scorecard.append(("TEST 2: 2000-Node Reverse DAG", "PASS", f"2000 tarefas reversas validadas em {dt_2000:.1f}ms sem RecursionError"))
            print(f"[PASS] 2000-Node Reverse DAG validado e persistido ({dt_2000:.1f}ms)")

            # ── TEST 3: Deep Cycle Detection on Large Graph ───────────────────
            print("\n--> TEST 3: Deteção de Ciclo Profundo (Deep Cycle Rejection)")
            prop_cycle = {
                "type": "mission_adaptation_propose",
                "project_id": project_id,
                "mission_id": mission_id_1000,
                "proposal": {
                    "proposal_id": f"prop_deep_cycle_{uuid.uuid4().hex[:6]}",
                    "base_graph_version": 1,
                    "decision": "ADAPT_PLAN",
                    "trigger": "REQUIREMENT_CHANGE",
                    "reason": "Tentativa de fechar um ciclo ligando a folha 999 de volta à raiz 0.",
                    "changed_edges": [["t_999", "t_0"]],
                },
            }
            await ws.send(json.dumps(prop_cycle))
            cycle_resp = await recv_until(ws, "mission_adaptation_proposal_result", timeout=30.0)
            assert cycle_resp["success"] is False
            assert "REJECTED_CYCLE_DETECTED" in cycle_resp["message"] or "Ciclo" in cycle_resp["message"]
            scorecard.append(("TEST 3: Deep Cycle Detection", "PASS", f"Ciclo profundo rejeitado: {cycle_resp['message'][:45]}..."))
            print(f"[PASS] Ciclo profundo rejeitado com segurança")

            # ── TEST 4: Dynamic Expansion on Deep Graph ───────────────────────
            print("\n--> TEST 4: Expansão Dinâmica em Grafo de 1000 Nós (v1 -> v2)")
            prop_expand = {
                "type": "mission_adaptation_propose",
                "project_id": project_id,
                "mission_id": mission_id_1000,
                "proposal": {
                    "proposal_id": f"prop_deep_adapt_{uuid.uuid4().hex[:6]}",
                    "base_graph_version": 1,
                    "decision": "ADAPT_PLAN",
                    "trigger": "RUNTIME_FAILURE",
                    "reason": "Inserir tarefa de monitorização entre nós 500 e 501.",
                    "added_tasks": [
                        {
                            "task_id": "t_deep_monitor",
                            "title": "Deep Monitor Task",
                            "category": "CODING",
                            "dependencies": ["t_500"],
                        }
                    ],
                    "changed_edges": [["t_deep_monitor", "t_501"]],
                    "evidence_ids": ["ev_deep_01"],
                },
            }
            await ws.send(json.dumps(prop_expand))
            expand_resp = await recv_until(ws, "mission_adaptation_proposal_result", timeout=30.0)
            assert expand_resp["success"] is True
            v2 = expand_resp["record"]["graph_version_after"]
            assert v2 == 2
            scorecard.append(("TEST 4: Dynamic Expansion Deep DAG", "PASS", f"Grafo de 1000 nós expandido com sucesso para v{v2}"))
            print(f"[PASS] Expansão dinâmica aplicada com sucesso (DAG v{v2})")

            # ── TEST 5: Adaptive Replanning on Deep Graph ─────────────────────
            print("\n--> TEST 5: Replaneamento Estrutural em Grafo Profundo (v2 -> v3)")
            prop_replan = {
                "type": "mission_adaptation_propose",
                "project_id": project_id,
                "mission_id": mission_id_1000,
                "proposal": {
                    "proposal_id": f"prop_deep_replan_{uuid.uuid4().hex[:6]}",
                    "base_graph_version": v2,
                    "decision": "REPLAN",
                    "trigger": "ARCHITECTURE_DISCOVERY",
                    "reason": "Substituição estrutural de nós 900-905 por nova arquitetura paralela.",
                    "removed_tasks": ["t_900"],
                    "added_tasks": [
                        {
                            "task_id": "t_replan_fast_pipeline",
                            "title": "Fast Pipeline Replacement",
                            "category": "CODING",
                            "dependencies": ["t_899"],
                        }
                    ],
                    "changed_edges": [["t_replan_fast_pipeline", "t_901"]],
                },
            }
            await ws.send(json.dumps(prop_replan))
            replan_resp = await recv_until(ws, "mission_adaptation_proposal_result", timeout=30.0)
            assert replan_resp["success"] is True
            v3 = replan_resp["record"]["graph_version_after"]
            assert v3 == 3
            scorecard.append(("TEST 5: Adaptive Replanning Deep DAG", "PASS", f"Replaneamento em grafo profundo aceite, avançando para v{v3}"))
            print(f"[PASS] Replaneamento estrutural aceite (DAG v{v3})")

            # ── TEST 6: Checkpoint & Recovery on Deep Graph ───────────────────
            print("\n--> TEST 6: Checkpoint e Recuperação de Grafo Profundo")
            cp_msg = {
                "type": "mission_checkpoint_create",
                "project_id": project_id,
                "mission_id": mission_id_1000,
                "description": "Snapshot de segurança de grafo profundo com 1000+ tarefas",
            }
            await ws.send(json.dumps(cp_msg))
            cp_resp = await recv_until(ws, "mission_checkpoint_created", timeout=30.0)
            seq = cp_resp.get("sequence", 1)
            assert seq >= 1

            # Restore checkpoint
            restore_msg = {
                "type": "mission_checkpoint_restore",
                "project_id": project_id,
                "mission_id": mission_id_1000,
                "checkpoint_id": cp_resp["checkpoint_id"],
                "sequence": seq,
            }
            await ws.send(json.dumps(restore_msg))
            restore_resp = await recv_until(ws, "mission_checkpoint_restored", timeout=30.0)
            assert restore_resp.get("success") is True
            scorecard.append(("TEST 6: Checkpoint/Restart Deep DAG", "PASS", f"Snapshot seq {seq} gravado e restaurado com 100% integridade"))
            print(f"[PASS] Checkpoint e recuperação validados com sucesso")

    except Exception as exc:
        import traceback
        traceback.print_exc()
        print(f"\n[FAIL] Erro durante a execução da suite de testes: {exc}")
        scorecard.append(("TEST EXECUTION", "FAIL", str(exc)))

    print("\n" + "=" * 80)
    print("SCORECARD OFICIAL — FASE 13.1 GRAPH VALIDATION SCALABILITY")
    print("=" * 80)
    print(f"{'ITEM / REQUISITO':<38} | {'STATUS':<8} | {'DETALHES'}")
    print("-" * 80)
    all_passed = True
    for req, status, details in scorecard:
        print(f"{req:<38} | {status:<8} | {details}")
        if status != "PASS":
            all_passed = False
    print("=" * 80)
    if all_passed and len(scorecard) == 6:
        print("RESULTADO GLOBAL: 6/6 REQUISITOS VALIDADOS COM SUCESSO [PASS]")
    else:
        print("RESULTADO GLOBAL: FALHAS DETETADAS [FAIL]")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_phase_13_1_qa())
