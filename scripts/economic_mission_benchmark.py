import asyncio
import os
import sys
import time
from typing import Any

sys.path.insert(0, os.path.abspath("."))

from backend.models.economic_mission import (
    BoundedAutonomyPolicy,
    EconomicMission,
    EconomicStage,
    EvidenceArtifact,
)
from backend.security.permissions import AutonomyLevel, PermissionPolicyManager
from agents.economic_runner import EconomicMissionRunner
from workspace.financial_analytics.analyzer import FinancialAnalyzer


async def run_e01_opportunity_discovery() -> dict[str, Any]:
    mission = EconomicMission(objective="Identificar nicho de micro-SaaS para developers")
    runner = EconomicMissionRunner(mission)
    packages = runner.decompose_mission_into_work_packages()
    res = await runner.execute_step(packages[0])
    assert res["status"] == "COMPLETED"
    assert mission.current_stage == EconomicStage.DISCOVERING
    assert len(mission.evidence) >= 1
    return {"scenario": "E01_OPPORTUNITY_DISCOVERY", "status": "PASS", "evidence_count": len(mission.evidence)}


async def run_e02_market_research() -> dict[str, Any]:
    mission = EconomicMission(objective="Pesquisa aprofundada de mercado em automação de logs", target_niche="DevOps")
    runner = EconomicMissionRunner(mission)
    packages = runner.decompose_mission_into_work_packages()
    res = await runner.execute_step(packages[0])
    assert res["status"] == "COMPLETED"
    return {"scenario": "E02_MARKET_RESEARCH", "status": "PASS", "stage": mission.current_stage.value}


async def run_e03_competitor_analysis() -> dict[str, Any]:
    mission = EconomicMission(objective="Análise de concorrentes SaaS", target_niche="Fintech")
    runner = EconomicMissionRunner(mission)
    packages = runner.decompose_mission_into_work_packages()
    res = await runner.execute_step(packages[0])
    assert res["status"] == "COMPLETED"
    return {"scenario": "E03_COMPETITOR_ANALYSIS", "status": "PASS", "stage": mission.current_stage.value}


async def run_e04_opportunity_scoring() -> dict[str, Any]:
    mission = EconomicMission(objective="Scoring de viabilidade económica")
    runner = EconomicMissionRunner(mission)
    packages = runner.decompose_mission_into_work_packages()
    await runner.execute_step(packages[0])
    res = await runner.execute_step(packages[1])
    assert res["status"] == "COMPLETED"
    assert mission.expected_value_usd > 0
    assert mission.confidence_score >= 0.8
    assert mission.current_stage == EconomicStage.VALIDATING
    return {"scenario": "E04_OPPORTUNITY_SCORING", "status": "PASS", "expected_value": mission.expected_value_usd, "confidence": mission.confidence_score}


async def run_e05_mvp_construction() -> dict[str, Any]:
    mission = EconomicMission(objective="Construção de MVP")
    runner = EconomicMissionRunner(mission)
    packages = runner.decompose_mission_into_work_packages()
    res = await runner.execute_step(packages[2])
    assert res["status"] == "COMPLETED"
    assert mission.current_stage == EconomicStage.BUILDING
    assert mission.metrics["total_cost_usd"] > 0
    return {"scenario": "E05_MVP_CONSTRUCTION", "status": "PASS", "stage": mission.current_stage.value, "cost": mission.metrics["total_cost_usd"]}


async def run_e06_landing_page_creation() -> dict[str, Any]:
    mission = EconomicMission(objective="Criação de Landing Page com CTA")
    runner = EconomicMissionRunner(mission)
    packages = runner.decompose_mission_into_work_packages()
    res = await runner.execute_step(packages[2])
    assert res["status"] == "COMPLETED"
    return {"scenario": "E06_LANDING_PAGE_CREATION", "status": "PASS", "stage": mission.current_stage.value}


async def run_e07_publishing_local_sandbox() -> dict[str, Any]:
    mission = EconomicMission(objective="Publicação e Health Check no Sandbox Local")
    runner = EconomicMissionRunner(mission)
    packages = runner.decompose_mission_into_work_packages()
    res = await runner.execute_step(packages[4])
    assert res["status"] == "COMPLETED"
    assert mission.current_stage == EconomicStage.PUBLISHED
    return {"scenario": "E07_PUBLISHING_SANDBOX", "status": "PASS", "stage": mission.current_stage.value}


async def run_e08_lead_acquisition() -> dict[str, Any]:
    mission = EconomicMission(objective="Aquisição de Leads e Conversões")
    runner = EconomicMissionRunner(mission)
    packages = runner.decompose_mission_into_work_packages()
    res = await runner.execute_step(packages[5])
    assert res["status"] == "COMPLETED"
    assert mission.current_stage == EconomicStage.ACQUIRING
    assert mission.metrics["leads_generated"] > 0
    assert mission.metrics["conversions"] > 0
    return {"scenario": "E08_LEAD_ACQUISITION", "status": "PASS", "leads": mission.metrics["leads_generated"], "conversions": mission.metrics["conversions"]}


async def run_e09_metrics_analysis() -> dict[str, Any]:
    mission = EconomicMission(objective="Análise de Métricas Financeiras e ROI")
    runner = EconomicMissionRunner(mission)
    packages = runner.decompose_mission_into_work_packages()
    await runner.execute_step(packages[2])  # build cost
    await runner.execute_step(packages[5])  # leads cost
    res = await runner.execute_step(packages[6])  # measuring revenue
    assert res["status"] == "COMPLETED"
    assert mission.current_stage == EconomicStage.MEASURING
    assert mission.metrics["revenue_usd"] > 0
    assert mission.metrics["roi_pct"] > 0
    return {
        "scenario": "E09_METRICS_ANALYSIS",
        "status": "PASS",
        "revenue": mission.metrics["revenue_usd"],
        "cost": mission.metrics["total_cost_usd"],
        "roi_pct": mission.metrics["roi_pct"],
        "cac": mission.metrics["cac_usd"],
    }


async def run_e10_autonomous_iteration() -> dict[str, Any]:
    mission = EconomicMission(objective="Ciclo Completo End-to-End com Iteração Autónoma")
    runner = EconomicMissionRunner(mission)
    packages = runner.decompose_mission_into_work_packages()
    for pkg in packages:
        res = await runner.execute_step(pkg)
        assert res["status"] == "COMPLETED"

    assert mission.current_stage == EconomicStage.SUCCESS
    assert mission.metrics["roi_pct"] > 0
    assert len(mission.evidence) == len(packages)
    return {
        "scenario": "E10_AUTONOMOUS_ITERATION",
        "status": "PASS",
        "final_stage": mission.current_stage.value,
        "evidence_verified": len(mission.evidence),
        "roi_pct": mission.metrics["roi_pct"],
    }


async def main():
    print("================================================================================")
    print("             JARVIS OS — ECONOMIC MISSION BENCHMARK (E01 - E10)")
    print("================================================================================")
    start_total = time.time()
    scenarios = [
        run_e01_opportunity_discovery,
        run_e02_market_research,
        run_e03_competitor_analysis,
        run_e04_opportunity_scoring,
        run_e05_mvp_construction,
        run_e06_landing_page_creation,
        run_e07_publishing_local_sandbox,
        run_e08_lead_acquisition,
        run_e09_metrics_analysis,
        run_e10_autonomous_iteration,
    ]

    results = []
    for sc_func in scenarios:
        t0 = time.time()
        res = await sc_func()
        res["elapsed_s"] = round(time.time() - t0, 4)
        results.append(res)
        print(f"[{res['scenario']}] -> STATUS: {res['status']} ({res['elapsed_s']}s)")

    print("\n================================================================================")
    print("                             BENCHMARK SUMMARY")
    print("================================================================================")
    passed = sum(1 for r in results if r["status"] == "PASS")
    print(f"Total Scenarios : {len(results)}")
    print(f"Passed          : {passed} / {len(results)} (100%)")
    print(f"Total Time      : {round(time.time() - start_total, 3)}s")
    print("\n>>> ECONOMIC BENCHMARK COMPLETED WITH 100% PASS RATE <<<")


if __name__ == "__main__":
    asyncio.run(main())
