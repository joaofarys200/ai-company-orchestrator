import sys, os
sys.path.insert(0, os.path.abspath("."))

import unittest
from backend.models.economic_mission import EconomicMission, EconomicStage
from agents.economic_runner import EconomicMissionRunner
from backend.security.permissions import PermissionPolicyManager


class TestEconomicRunner(unittest.IsolatedAsyncioTestCase):
    def test_economic_mission_decomposition(self):
        mission = EconomicMission(
            objective="Criar micro-SaaS de análise de dados",
            target_niche="Fintech SaaS",
            budget_usd=100.0
        )
        runner = EconomicMissionRunner(mission)
        packages = runner.decompose_mission_into_work_packages()

        self.assertEqual(len(packages), 8)
        self.assertEqual(packages[0]["role"], "Researcher (Clara)")
        self.assertEqual(packages[1]["role"], "Analyst (Alex)")
        self.assertEqual(packages[2]["role"], "Builder (Devon)")
        self.assertEqual(packages[3]["role"], "QA (Quinn)")

    async def test_execute_step_allowed_tool(self):
        mission = EconomicMission(objective="Pesquisa de mercado")
        runner = EconomicMissionRunner(mission)
        packages = runner.decompose_mission_into_work_packages()

        # Step 1 uses 'web_search' which is allowed with no approval
        res = await runner.execute_step(packages[0])
        self.assertEqual(res["status"], "COMPLETED")
        self.assertEqual(packages[0]["status"], "COMPLETED")
        self.assertEqual(mission.current_stage, EconomicStage.DISCOVERING
)

    async def test_execute_step_high_risk_requires_approval(self):
        mission = EconomicMission(objective="Publicação financeira")
        runner = EconomicMissionRunner(mission)
        
        # High risk package with financial_transaction tool
        high_risk_wp = {
            "id": "high_risk_1",
            "role": "Finance Agent",
            "tool": "financial_transaction",
            "objective": "Efetuar pagamento de registo",
            "status": "PENDING"
        }
        res = await runner.execute_step(high_risk_wp)
        self.assertEqual(res["status"], "PENDING_APPROVAL")
        self.assertEqual(mission.current_stage, EconomicStage.PAUSED)


if __name__ == "__main__":
    unittest.main()
