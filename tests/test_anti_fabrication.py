import sys, os
sys.path.insert(0, os.path.abspath("."))

import hashlib
import hmac
import json
import unittest

from backend.gateway import (
    EconomicExecutionGateway,
    EvidenceLevel,
    ExternalVerificationGate,
    FabricationAttemptError,
    LeadCaptureGateway,
    MonetizationGateway,
)
from backend.models.economic_mission import EconomicMission, EconomicStage
from agents.economic_runner import EconomicMissionRunner


class TestAntiFabrication(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.secret = "whsec_test_secret_anti_fabrication"
        self.verification_gate = ExternalVerificationGate(default_webhook_secret=self.secret)
        self.monetization = MonetizationGateway(
            webhook_secret=self.secret,
            verification_gate=self.verification_gate,
        )
        self.leads = LeadCaptureGateway(verification_gate=self.verification_gate)
        self.gateway = EconomicExecutionGateway(
            verification_gate=self.verification_gate,
            monetization_gateway=self.monetization,
            lead_gateway=self.leads,
        )

    def test_direct_synthetic_payment_cannot_grant_monetized_success(self):
        """Proves that a local synthetic payment fixture cannot grant official economic SUCCESS."""
        mission = EconomicMission(objective="Teste Anti-Fabricação")
        runner = EconomicMissionRunner(mission, gateway=self.gateway)

        # Record a synthetic payment
        self.gateway.monetization.record_synthetic_payment(
            mission_id=mission.mission_id,
            transaction_id=f"tx_fake_{int(os.getpid())}_{id(self)}",
            amount_usd=500.0,
        )

        # Verified revenue must be strictly 0.0
        verified_rev = self.gateway.monetization.get_verified_revenue(mission.mission_id)
        self.assertEqual(verified_rev, 0.0)

    async def test_synthetic_mission_reaches_benchmark_passed_not_success(self):
        """Proves that a mission with synthetic revenue ends in BENCHMARK_PASSED instead of SUCCESS."""
        mission = EconomicMission(objective="Teste de Classificação Honesta")
        runner = EconomicMissionRunner(mission, gateway=self.gateway)
        packages = runner.decompose_mission_into_work_packages()

        self.gateway.monetization.record_synthetic_payment(
            mission_id=mission.mission_id,
            transaction_id=f"tx_synth_{int(os.getpid())}_{id(self)}",
            amount_usd=200.0,
        )

        for pkg in packages:
            await runner.execute_step(pkg)

        # Must NOT be SUCCESS, must be BENCHMARK_PASSED
        self.assertEqual(mission.current_stage, EconomicStage.BENCHMARK_PASSED)
        self.assertEqual(mission.metrics["verified_revenue_usd"], 0.0)
        self.assertEqual(mission.metrics["synthetic_revenue_usd"], 200.0)

    def test_invalid_hmac_webhook_signature_rejected(self):
        """Proves that spoofed or forged webhook payloads are rejected."""
        payload = json.dumps({"event": "charge.succeeded", "amount": 100.0})
        fake_sig = "a1b2c3d4e5f6spoofed_signature"

        is_valid, level, reason, _ = self.verification_gate.verify_payment_webhook(
            raw_payload=payload,
            signature_header=fake_sig,
            webhook_secret=self.secret,
        )
        self.assertFalse(is_valid)
        self.assertEqual(level, EvidenceLevel.EXTERNAL_UNVERIFIED)
        self.assertIn("spoofing detected", reason)

    def test_valid_hmac_webhook_accepted_as_external_verified(self):
        """Proves that genuine HMAC-signed payloads earn EXTERNAL_VERIFIED status."""
        payload = json.dumps({"event": "charge.succeeded", "amount": 150.0})
        valid_sig = hmac.new(self.secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()

        is_valid, level, reason, data = self.verification_gate.verify_payment_webhook(
            raw_payload=payload,
            signature_header=valid_sig,
            webhook_secret=self.secret,
        )
        self.assertTrue(is_valid)
        self.assertEqual(level, EvidenceLevel.EXTERNAL_VERIFIED)
        self.assertEqual(data["amount"], 150.0)

    async def test_genuine_external_verified_revenue_enables_success(self):
        """Proves that authentic EXTERNAL_VERIFIED revenue is required to reach real SUCCESS."""
        mission = EconomicMission(objective="Teste de Sucesso Real Verificado")
        runner = EconomicMissionRunner(mission, gateway=self.gateway)
        packages = runner.decompose_mission_into_work_packages()

        payload = json.dumps({"event": "charge.succeeded", "amount": 300.0})
        valid_sig = hmac.new(self.secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()

        self.gateway.monetization.process_webhook_payment(
            mission_id=mission.mission_id,
            transaction_id=f"tx_real_{int(os.getpid())}_{id(self)}",
            amount_usd=300.0,
            raw_payload=payload,
            signature_header=valid_sig,
        )

        for pkg in packages:
            await runner.execute_step(pkg)

        self.assertEqual(mission.current_stage, EconomicStage.SUCCESS)
        self.assertEqual(mission.metrics["verified_revenue_usd"], 300.0)
        self.assertGreater(mission.metrics["roi_pct"], 0.0)

    def test_certify_evidence_blocks_forged_external_verified(self):
        """Proves that certify_evidence raises FabricationAttemptError without valid signature."""
        with self.assertRaises(FabricationAttemptError):
            self.verification_gate.certify_evidence(
                evidence_level=EvidenceLevel.EXTERNAL_VERIFIED,
                data={"fake": "proof"},
                signature="",  # Missing signature
            )

    def test_illegal_state_jump_blocked(self):
        """Proves that jumping directly from CREATED to SUCCESS or MONETIZED is blocked."""
        mission = EconomicMission(objective="Teste de Salto Ilegal")
        with self.assertRaises(ValueError):
            mission.transition_to_stage(EconomicStage.SUCCESS)


if __name__ == "__main__":
    unittest.main()
