"""
JARVIS OS — Phase 57: Autonomous Task Completion Benchmark
Evaluates scalability, throughput, and completion metrics across synthetic and real-user-like
mission workloads at scales: 10, 25, 50, 100 missions across 10 categories.
Emits docs/phase57_performance.json.
"""

from __future__ import annotations

import json
import os
import sys
import time

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from backend.agents.autonomous_task_completion import (
    AutonomousMissionExecutor,
    CompletionDecision,
    MissionState,
)

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DOCS_DIR = os.path.join(WORKSPACE_ROOT, "docs")
PERF_FILE = os.path.join(DOCS_DIR, "phase57_performance.json")

BENCHMARK_INTENTS = [
    # 1. Frontend
    "Criar componente de navegação responsiva com abas e animação de transição",
    # 2. Backend
    "Desenvolver endpoint REST em FastAPI para gestão de tarefas com SQLite",
    # 3. Fullstack
    "Criar aplicação completa de gestão de notas com frontend React e backend API",
    # 4. Bugfix
    "Corrigir erro de parsing no interpretador de tipos e garantir zero regressões",
    # 5. Contract Change
    "Atualizar esquema de contrato da entidade missão adicionando campos de auditoria",
    # 6. Refactor
    "Modularizar subsistema monolítico de telemetria em submódulos desacoplados",
    # 7. Integration
    "Integrar serviço de mensageria com webhook assíncrono e retry exponencial",
    # 8. Browser Task
    "Validar fluxo crítico de utilizador no navegador com screenshots e asserções DOM",
    # 9. Data Task
    "Executar migração de esquema de banco de dados e recalcular índices de busca",
    # 10. Security Task
    "Implementar sandbox rigoroso com auditoria Sentinel para comandos de shell",
]


def run_benchmark_scale(scale: int) -> dict:
    start_time = time.perf_counter()
    completed = 0
    blocked = 0
    human_reviews = 0
    total_repairs = 0
    total_evidences = 0
    false_completions = 0

    for i in range(scale):
        intent = BENCHMARK_INTENTS[i % len(BENCHMARK_INTENTS)]
        mission = AutonomousMissionExecutor.run_mission(
            raw_intent=f"{intent} [Iter {i+1}]",
            mission_id=f"bm_p57_{scale}_{i+1}",
        )

        if mission.state == MissionState.COMPLETED:
            completed += 1
        elif mission.state == MissionState.BLOCKED:
            blocked += 1
        elif mission.state == MissionState.HUMAN_REVIEW_REQUIRED:
            human_reviews += 1

        total_repairs += len(mission.repairs)
        total_evidences += len(mission.evidence_set.evidences)

        # Verification: False completion check
        if mission.state == MissionState.COMPLETED and mission.final_decision != CompletionDecision.MISSION_PROVEN_COMPLETE:
            false_completions += 1

    total_duration = time.perf_counter() - start_time
    avg_duration_ms = (total_duration / scale) * 1000.0
    throughput = scale / total_duration if total_duration > 0 else 0.0

    return {
        "scale": scale,
        "total_missions": scale,
        "completed_proven": completed,
        "blocked": blocked,
        "human_reviews": human_reviews,
        "total_repairs": total_repairs,
        "total_evidences": total_evidences,
        "false_completions": false_completions,
        "total_duration_seconds": round(total_duration, 4),
        "avg_duration_ms_per_mission": round(avg_duration_ms, 3),
        "throughput_missions_per_sec": round(throughput, 2),
        "sla_target_ms": 500.0,
        "sla_met": avg_duration_ms < 500.0,
    }


def main():
    print("=================================================================")
    print("JARVIS OS — Phase 57: Autonomous Task Completion Benchmark")
    print("=================================================================")

    os.makedirs(DOCS_DIR, exist_ok=True)
    scales = [10, 25, 50, 100]
    results = []

    for scale in scales:
        print(f"[*] Executing benchmark scale: {scale} missions...")
        res = run_benchmark_scale(scale)
        results.append(res)
        print(
            f"    -> Scale {scale}: {res['completed_proven']}/{scale} proven ({res['avg_duration_ms_per_mission']} ms/mission, "
            f"{res['throughput_missions_per_sec']} missions/sec, SLA: {'PASS' if res['sla_met'] else 'FAIL'})"
        )

    output = {
        "benchmark": "Phase 57 Autonomous Task Completion Scalability",
        "timestamp": time.time(),
        "categories_covered": 10,
        "scales_evaluated": scales,
        "results": results,
    }

    with open(PERF_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"\n[+] Benchmark complete. Saved to: {PERF_FILE}")


if __name__ == "__main__":
    main()
