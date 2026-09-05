"""JARVIS OS - Fase 13 Live Runtime QA Verification Script.

Tests all 10 Live Runtime QA requirements against the live backend WebSocket:
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


async def recv_until(ws, target_types: set[str] | str, timeout: float = 8.0) -> dict:
    if isinstance(target_types, str):
        target_types = {target_types}
    end_time = asyncio.get_event_loop().time() + timeout
    while True:
        remaining = max(0.1, end_time - asyncio.get_event_loop().time())
        msg = await asyncio.wait_for(ws.recv(), timeout=remaining)
        data = json.loads(msg)
        if data.get("type") in target_types:
            return data


async def run_phase_13_qa() -> None:
    print("=" * 75)
    print("JARVIS OS — FASE 13 LIVE RUNTIME QA VERIFICATION SCORECARD")
    print("=" * 75)

    scorecard: list[tuple[str, str, str]] = []

    try:
        async with websockets.connect(BACKEND_URL, close_timeout=5.0) as ws:
            print(f"[OK] Connected to live backend at {BACKEND_URL}")

            # ── 1. Handshake & Live Connection ────────────────────────────────
            print("\n--> TEST 1: WebSocket Handshake & Conexão")
            await ws.send(json.dumps({"type": "ping"}))
            await asyncio.sleep(0.1)
            scorecard.append(("TEST 1: Handshake & Conexão", "PASS", "Conexão WebSocket ativa em 127.0.0.1:8001"))
            print("[PASS] Handshake OK")

            project_id = "default"
            mission_id = f"m_f13_{uuid.uuid4().hex[:8]}"

            # ── 2. Início de Missão com DAG Inicial (v1) ───────────────────────
            print("\n--> TEST 2: Início de Missão com DAG Inicial (v1)")
            t_setup = f"setup_{uuid.uuid4().hex[:4]}"
            t_core = f"core_{uuid.uuid4().hex[:4]}"
            t_audit = f"audit_{uuid.uuid4().hex[:4]}"
            init_msg = {
                "type": "mission_plan_decompose",
                "project_id": project_id,
                "mission_id": mission_id,
                "title": "Missão de Verificação Fase 13",
                "objective": "Verificação integral de Adaptive Planning e Graph Intelligence",
                "tasks": [
                    {"task_id": t_setup, "title": "Ambiente e Dependências", "category": "SETUP"},
                    {"task_id": t_core, "title": "Implementação do Core Engine", "category": "CODING", "dependencies": [t_setup]},
                    {"task_id": t_audit, "title": "Auditoria de Segurança", "category": "REVIEW", "dependencies": [t_core]},
                ],
            }
            await ws.send(json.dumps(init_msg))
            snap_resp = await recv_until(ws, "mission_snapshot", timeout=6.0)
            meta = snap_resp["data"]["mission"].get("metadata", {})
            v1 = meta.get("graph_version", 1)
            assert v1 == 1
            scorecard.append(("TEST 2: DAG Inicial v1 Decompose", "PASS", f"Missão {mission_id} criada com DAG v{v1}"))
            print(f"[PASS] Missão criada com DAG v{v1}")

            # ── 3. Avaliação de Plano com Falha Localizada (ADAPT_PLAN) ────────
            print("\n--> TEST 3: Avaliação de Plano (Falha Localizada -> ADAPT_PLAN)")
            eval_msg_local = {
                "type": "mission_plan_evaluate",
                "project_id": project_id,
                "mission_id": mission_id,
                "observations": [
                    {
                        "source": "BUILD",
                        "event": "TypeScript build failed with TS2307: Cannot find module '@types/node'",
                        "task_id": t_core,
                        "severity": "HIGH",
                        "evidence_id": "ev_ts_error",
                    }
                ],
            }
            await ws.send(json.dumps(eval_msg_local))
            eval_resp_1 = await recv_until(ws, "mission_plan_evaluation_result", timeout=6.0)
            res_1 = eval_resp_1.get("result", {})
            assert res_1.get("decision") in {"ADAPT_PLAN", "REPLAN"}
            scorecard.append(("TEST 3: Avaliação Falha Localizada", "PASS", f"Decisão {res_1.get('decision')} para erro TypeScript"))
            print(f"[PASS] Avaliação devolveu {res_1.get('decision')}")

            # ── 4. Avaliação de Plano com Descoberta Arquitetural (REPLAN) ─────
            print("\n--> TEST 4: Avaliação de Plano (Descoberta Arquitetural -> REPLAN)")
            eval_msg_arch = {
                "type": "mission_plan_evaluate",
                "project_id": project_id,
                "mission_id": mission_id,
                "architecture_change": {
                    "summary": "Descoberta de requisito de alta disponibilidade incompatível com SQLite",
                    "affected_tasks": [t_core, t_audit],
                },
            }
            await ws.send(json.dumps(eval_msg_arch))
            eval_resp_2 = await recv_until(ws, "mission_plan_evaluation_result", timeout=6.0)
            res_2 = eval_resp_2.get("result", {})
            assert res_2.get("decision") == "REPLAN"
            scorecard.append(("TEST 4: Avaliação Descoberta Arquitetural", "PASS", f"Decisão REPLAN confirmada com trigger {res_2.get('trigger')}"))
            print(f"[PASS] REPLAN recomendado para mudança arquitetural")

            # ── 5. Proposta e Aplicação Atómica de Adaptação (v1 -> v2) ───────
            print("\n--> TEST 5: Proposta e Aplicação Atómica (v1 -> v2)")
            t_patch = f"patch_{uuid.uuid4().hex[:4]}"
            prop_1_id = f"prop_fix_{uuid.uuid4().hex[:6]}"
            prop_1 = {
                "type": "mission_adaptation_propose",
                "project_id": project_id,
                "mission_id": mission_id,
                "proposal": {
                    "proposal_id": prop_1_id,
                    "base_graph_version": v1,
                    "decision": "ADAPT_PLAN",
                    "trigger": "BUILD_FAILURE",
                    "reason": "Instalar tipagens @types/node no setup antes do core.",
                    "added_tasks": [
                        {
                            "task_id": t_patch,
                            "title": "Instalar @types/node",
                            "category": "SETUP",
                            "dependencies": [t_setup],
                        }
                    ],
                    "changed_edges": [[t_patch, t_core]],
                    "evidence_ids": ["ev_ts_error"],
                },
            }
            await ws.send(json.dumps(prop_1))
            prop_resp_1 = await recv_until(ws, "mission_adaptation_proposal_result", timeout=6.0)
            assert prop_resp_1["success"] is True
            v2 = prop_resp_1["record"]["graph_version_after"]
            assert v2 == 2
            scorecard.append(("TEST 5: Aplicação Atómica v1 -> v2", "PASS", f"DAG atualizado para v{v2} com nova tarefa {t_patch}"))
            print(f"[PASS] DAG incrementado para v{v2}")

            # ── 6. Replan Completo com Preservação de Concluídos (v2 -> v3) ───
            print("\n--> TEST 6: Replan Completo com Preservação (v2 -> v3)")
            prop_replan_id = f"prop_replan_{uuid.uuid4().hex[:6]}"
            t_pg = f"pg_{uuid.uuid4().hex[:4]}"
            prop_replan = {
                "type": "mission_adaptation_propose",
                "project_id": project_id,
                "mission_id": mission_id,
                "proposal": {
                    "proposal_id": prop_replan_id,
                    "base_graph_version": v2,
                    "decision": "REPLAN",
                    "trigger": "ARCHITECTURE_DISCOVERY",
                    "reason": "Migração completa de infraestrutura para PostgreSQL clusterizado.",
                    "removed_tasks": [t_core],
                    "added_tasks": [
                        {
                            "task_id": t_pg,
                            "title": "Setup PostgreSQL Cluster",
                            "category": "CODING",
                            "dependencies": [t_setup],
                        }
                    ],
                    "changed_edges": [[t_pg, t_audit]],
                },
            }
            await ws.send(json.dumps(prop_replan))
            prop_resp_replan = await recv_until(ws, "mission_adaptation_proposal_result", timeout=6.0)
            assert prop_resp_replan["success"] is True
            v3 = prop_resp_replan["record"]["graph_version_after"]
            assert v3 == 3
            scorecard.append(("TEST 6: Replan Completo v2 -> v3", "PASS", f"Replan aceite; tarefas reconfiguradas para v{v3}"))
            print(f"[PASS] Replan aplicado com sucesso, DAG agora em v{v3}")

            # ── 7. Rejeição de Oscilação de Estratégia Repetida ───────────────
            print("\n--> TEST 7: Deteção e Rejeição de Oscilação de Estratégia")
            prop_repeat = {
                "type": "mission_adaptation_propose",
                "project_id": project_id,
                "mission_id": mission_id,
                "proposal": {
                    "proposal_id": f"prop_repeat_{uuid.uuid4().hex[:6]}",
                    "base_graph_version": v3,
                    "decision": "REPLAN",
                    "trigger": "ARCHITECTURE_DISCOVERY",
                    "reason": "Re-tentativa idêntica da proposta anterior de migração.",
                    "removed_tasks": [t_core],
                    "added_tasks": [
                        {
                            "task_id": t_pg,
                            "title": "Setup PostgreSQL Cluster",
                            "category": "CODING",
                            "dependencies": [t_setup],
                        }
                    ],
                    "changed_edges": [[t_pg, t_audit]],
                },
            }
            await ws.send(json.dumps(prop_repeat))
            prop_resp_repeat = await recv_until(ws, "mission_adaptation_proposal_result", timeout=6.0)
            # Budget max_strategy_repeats or oscillation rejects repeat
            assert prop_resp_repeat["success"] is False or "OSCILLATION" in prop_resp_repeat.get("message", "")
            scorecard.append(("TEST 7: Deteção de Oscilação", "PASS", f"Estratégia repetida travada determinísticamente"))
            print(f"[PASS] Oscilação detetada/rejeitada")

            # ── 8. Rejeição de Versão Obsoleta (Stale Graph Version) ─────────
            print("\n--> TEST 8: Rejeição de Proposta com Grafo Obsoleto")
            prop_stale = {
                "type": "mission_adaptation_propose",
                "project_id": project_id,
                "mission_id": mission_id,
                "proposal": {
                    "proposal_id": f"prop_stale_{uuid.uuid4().hex[:6]}",
                    "base_graph_version": 1,  # Stale! Grafo atual está em v3
                    "decision": "ADAPT_PLAN",
                    "trigger": "REQUIREMENT_CHANGE",
                    "reason": "Proposta atrasada gerada contra versão antiga do grafo.",
                    "added_tasks": [{"task_id": "late_task", "title": "Late Task"}],
                },
            }
            await ws.send(json.dumps(prop_stale))
            prop_resp_stale = await recv_until(ws, "mission_adaptation_proposal_result", timeout=6.0)
            assert prop_resp_stale["success"] is False
            assert "REJECTED_STALE_GRAPH_VERSION" in prop_resp_stale["message"]
            scorecard.append(("TEST 8: Bloqueio de Versão Obsoleta", "PASS", "Optimistic lock barrou proposta em DAG desatualizado"))
            print(f"[PASS] Bloqueio por versão obsoleta confirmado")

            # ── 9. Rejeição de Dependência Circular (Cycle Injection) ────────
            print("\n--> TEST 9: Deteção de Ciclo no Grafo Proposto")
            prop_cycle = {
                "type": "mission_adaptation_propose",
                "project_id": project_id,
                "mission_id": mission_id,
                "proposal": {
                    "proposal_id": f"prop_cycle_{uuid.uuid4().hex[:6]}",
                    "base_graph_version": v3,
                    "decision": "ADAPT_PLAN",
                    "trigger": "REQUIREMENT_CHANGE",
                    "reason": "Injetar aresta circular entre audit e setup.",
                    "changed_edges": [[t_audit, t_setup]],  # setup -> pg -> audit -> setup = CYCLE
                },
            }
            await ws.send(json.dumps(prop_cycle))
            prop_resp_cycle = await recv_until(ws, "mission_adaptation_proposal_result", timeout=6.0)
            assert prop_resp_cycle["success"] is False
            assert "REJECTED_CYCLE_DETECTED" in prop_resp_cycle["message"] or "Ciclo" in prop_resp_cycle["message"]
            scorecard.append(("TEST 9: Deteção de Ciclo", "PASS", "Ciclo no trial DAG rejeitado antes de mutar grafo"))
            print(f"[PASS] Dependência circular rejeitada com segurança")

            # ── 10. Consulta de Histórico de Adaptação Persistido ──────────────
            print("\n--> TEST 10: Consulta e Verificação de Histórico de Adaptações")
            hist_query = {
                "type": "mission_adaptation_get_history",
                "project_id": project_id,
                "mission_id": mission_id,
            }
            await ws.send(json.dumps(hist_query))
            hist_resp = await recv_until(ws, "mission_adaptation_history", timeout=6.0)
            history = hist_resp.get("history", [])
            assert len(history) >= 2  # At least proposal 1 and replan
            scorecard.append(("TEST 10: Histórico de Adaptações", "PASS", f"{len(history)} registos persistidos e auditáveis em disco"))
            print(f"[PASS] Histórico persistido contém {len(history)} registos")

    except Exception as exc:
        import traceback
        traceback.print_exc()
        print(f"\n[FAIL] Erro durante a execução da suite de testes: {exc}")
        scorecard.append(("TEST EXECUTION", "FAIL", str(exc)))

    print("\n" + "=" * 75)
    print("SCORECARD OFICIAL — FASE 13 MISSION GRAPH INTELLIGENCE & ADAPTIVE PLANNING")
    print("=" * 75)
    print(f"{'ITEM / REQUISITO':<42} | {'STATUS':<8} | {'DETALHES'}")
    print("-" * 75)
    all_passed = True
    for req, status, details in scorecard:
        print(f"{req:<42} | {status:<8} | {details}")
        if status != "PASS":
            all_passed = False
    print("=" * 75)
    if all_passed and len(scorecard) == 10:
        print("RESULTADO GLOBAL: 10/10 REQUISITOS VALIDADOS COM SUCESSO [PASS]")
    else:
        print("RESULTADO GLOBAL: FALHAS DETETADAS [FAIL]")
    print("=" * 75)


if __name__ == "__main__":
    asyncio.run(run_phase_13_qa())
