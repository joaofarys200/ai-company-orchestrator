from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import websockets

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


async def run_adaptive_planning_websocket_e2e() -> bool:
    print("=" * 70)
    print("JARVIS OS — ADAPTIVE PLANNING (FASE 13) LIVE WEBSOCKET E2E TEST")
    print("=" * 70)

    async with websockets.connect(BACKEND_URL, close_timeout=5.0) as ws:
        print("[OK] Connected to live backend at", BACKEND_URL)
        await asyncio.sleep(0.1)

        project_id = "default"
        mission_id = f"m_ap_{uuid.uuid4().hex[:8]}"

        # STEP 1: Decompose a structured mission into DAG
        print("\n--> STEP 1: Criar Missão com DAG Inicial (v1)")
        decomp_msg = {
            "type": "mission_plan_decompose",
            "project_id": project_id,
            "mission_id": mission_id,
            "title": "Missão E2E Adaptive Planning",
            "objective": "Validar ciclo Observation -> Proposal -> Validation -> Atomic Apply",
            "tasks": [
                {"title": "Configuração Base", "category": "SETUP", "task_id": "T_SETUP"},
                {"title": "Serviço de Processamento", "category": "CODING", "dependencies": ["T_SETUP"], "task_id": "T_PROC"},
                {"title": "Testes de Integração", "category": "TEST", "dependencies": ["T_PROC"], "task_id": "T_TEST"},
            ],
        }
        await ws.send(json.dumps(decomp_msg))
        snapshot_resp = await recv_until(ws, "mission_snapshot", timeout=6.0)
        assert snapshot_resp["data"]["mission"]["mission_id"] == mission_id
        meta = snapshot_resp["data"]["mission"].get("metadata", {})
        graph_version = meta.get("graph_version", 1)
        print(f"[OK] Missão criada: {mission_id}, DAG v{graph_version}")

        # STEP 2: Evaluate plan with observations
        print("\n--> STEP 2: Enviar mission_plan_evaluate com Observação Estruturada")
        eval_msg = {
            "type": "mission_plan_evaluate",
            "project_id": project_id,
            "mission_id": mission_id,
            "observations": [
                {
                    "source": "RUNTIME",
                    "event": "Serviço de Processamento excedeu limite de memória (OOMKilled)",
                    "task_id": "T_PROC",
                    "severity": "HIGH",
                    "evidence_id": "ev_oom_01",
                }
            ],
        }
        await ws.send(json.dumps(eval_msg))
        eval_resp = await recv_until(ws, "mission_plan_evaluation_result", timeout=6.0)
        eval_res = eval_resp.get("result", {})
        decision = eval_res.get("decision")
        print(f"[OK] Avaliação do Plano recebida: Decisão = {decision}, Motivo = {eval_res.get('reason')}")
        assert decision in {"ADAPT_PLAN", "REPLAN"}

        # STEP 3: Propose adaptation (insert memory tuning task)
        print("\n--> STEP 3: Propor Adaptação Válida (mission_adaptation_propose)")
        prop_id = f"prop_{uuid.uuid4().hex[:8]}"
        proposal_msg = {
            "type": "mission_adaptation_propose",
            "project_id": project_id,
            "mission_id": mission_id,
            "proposal": {
                "proposal_id": prop_id,
                "base_graph_version": graph_version,
                "decision": "ADAPT_PLAN",
                "trigger": "RUNTIME_FAILURE",
                "reason": "Aumentar alocação de memória e adicionar batch streaming no processamento.",
                "added_tasks": [
                    {
                        "task_id": "T_MEM_TUNE",
                        "title": "Ajuste de Buffer e Streaming",
                        "category": "CODING",
                        "dependencies": ["T_SETUP"],
                    }
                ],
                "changed_edges": [["T_MEM_TUNE", "T_PROC"]],
                "evidence_ids": ["ev_oom_01"],
            },
        }
        await ws.send(json.dumps(proposal_msg))
        prop_resp = await recv_until(ws, "mission_adaptation_proposal_result", timeout=6.0)
        assert prop_resp["proposal_id"] == prop_id
        assert prop_resp["success"] is True
        new_v = prop_resp["record"]["graph_version_after"]
        print(f"[OK] Adaptação aplicada com sucesso! Grafo avançou de v{graph_version} para v{new_v}")
        assert new_v == graph_version + 1

        # STEP 4: Query adaptation history
        print("\n--> STEP 4: Consultar Histórico de Adaptações (mission_adaptation_get_history)")
        hist_msg = {
            "type": "mission_adaptation_get_history",
            "project_id": project_id,
            "mission_id": mission_id,
        }
        await ws.send(json.dumps(hist_msg))
        hist_resp = await recv_until(ws, "mission_adaptation_history", timeout=6.0)
        history = hist_resp.get("history", [])
        assert len(history) >= 1
        assert any(r.get("proposal_id") == prop_id for r in history)
        print(f"[OK] Histórico verificado: {len(history)} registo(s) de adaptação.")

        # STEP 5: Rejection of invalid cycle proposal
        print("\n--> STEP 5: Testar Rejeição de Proposta com Ciclo (REJECTED_CYCLE_DETECTED)")
        cycle_prop_id = f"prop_cycle_{uuid.uuid4().hex[:8]}"
        cycle_msg = {
            "type": "mission_adaptation_propose",
            "project_id": project_id,
            "mission_id": mission_id,
            "proposal": {
                "proposal_id": cycle_prop_id,
                "base_graph_version": new_v,
                "decision": "ADAPT_PLAN",
                "trigger": "RUNTIME_FAILURE",
                "reason": "Tentativa deliberada de introduzir dependência circular no grafo.",
                "changed_edges": [["T_PROC", "T_SETUP"]],  # T_SETUP -> T_PROC -> T_SETUP = CYCLE!
                "evidence_ids": ["ev_oom_01"],
            },
        }
        await ws.send(json.dumps(cycle_msg))
        cycle_resp = await recv_until(ws, "mission_adaptation_proposal_result", timeout=6.0)
        assert cycle_resp["success"] is False
        assert "REJECTED_CYCLE_DETECTED" in cycle_resp["message"] or "Ciclo" in cycle_resp["message"]
        print(f"[OK] Ciclo rejeitado determinísticamente: {cycle_resp['message']}")

        print("\n" + "=" * 70)
        print("FASE 13 WEBSOCKET E2E VERIFICATION: ALL 5 STEPS PASSED [SUCCESS]")
        print("=" * 70)
        return True


if __name__ == "__main__":
    success = asyncio.run(run_adaptive_planning_websocket_e2e())
    sys.exit(0 if success else 1)
