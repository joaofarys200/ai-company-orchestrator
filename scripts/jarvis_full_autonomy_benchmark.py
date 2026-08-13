import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.abspath("."))

from agents.autonomous_orchestrator import AutonomousOrchestrator


async def main():
    print("================================================================================")
    print("           JARVIS OS — FULL AUTONOMOUS EXECUTION BENCHMARK")
    print("================================================================================")
    print("Iniciando ciclo autónomo unassisted a partir de objetivo de alto nível...")
    print("Objetivo: 'Descobrir oportunidade de micro-SaaS, validar no mercado, construir MVP, publicar no sandbox, testar interatividade com browser e avaliar ROI.'\n")

    orchestrator = AutonomousOrchestrator()
    mission, telemetry = await orchestrator.execute_autonomous_mission(
        "Descobrir oportunidade de micro-SaaS, validar no mercado, construir MVP, publicar no sandbox, testar interatividade com browser e avaliar ROI."
    )

    print("\n" + "=" * 80)
    print("                       MATRIZ DE TELEMETRIA DE AUTONOMIA")
    print("=" * 80)
    print(f"{'Métrica':<35} | {'Valor Registado'}")
    print("-" * 80)
    print(f"{'Decisões Autónomas':<35} | {telemetry.autonomous_decisions}")
    print(f"{'Chamadas ao Qwen 3.5:9b':<35} | {telemetry.qwen_model_calls}")
    print(f"{'Ferramentas Executadas':<35} | {telemetry.tools_executed}")
    print(f"{'Erros Encontrados':<35} | {telemetry.errors_encountered}")
    print(f"{'Recuperações com Sucesso':<35} | {telemetry.recoveries_succeeded}")
    print(f"{'Ficheiros Alterados':<35} | {telemetry.files_modified}")
    print(f"{'Ciclos Completos de Execução':<35} | {telemetry.cycles_completed}")
    print(f"{'Oportunidades Avaliadas':<35} | 1")
    print(f"{'MVPs Construídos':<35} | {telemetry.mvps_built}")
    print(f"{'Deployments Verificados':<35} | {telemetry.deployments}")
    print(f"{'Leads / Utilizadores Obtidos':<35} | {telemetry.verified_leads}")
    print(f"{'Receita Verificada (USD)':<35} | ${telemetry.verified_revenue_usd:.2f}")
    print(f"{'Receita Sintética / Teste (USD)':<35} | ${telemetry.synthetic_revenue_usd:.2f}")
    print(f"{'Custo Computacional Estimado (USD)':<35} | ${telemetry.total_compute_cost_usd:.2f}")
    print(f"{'Decisões Corretas':<35} | {telemetry.correct_decisions}")
    print(f"{'Tempo Total de Execução':<35} | {telemetry.elapsed_seconds}s")
    print(f"{'Estado Final da Missão':<35} | {mission.current_stage.value}")
    print("=" * 80)
    print(">>> JARVIS FULL AUTONOMY BENCHMARK CONCLUÍDO COM SUCESSO <<<")


if __name__ == "__main__":
    asyncio.run(main())
