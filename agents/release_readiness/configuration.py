"""
Configuration Readiness Module
Phase 70 — Autonomous Release Readiness & Production Governance

Verifies environment parameters, safe defaults, and secret references.
Crucial invariant: Never logs or prints plaintext secret values. UNSAFE -> BLOCKED.
"""

from __future__ import annotations
from typing import Dict, Any, List
from .models import ConfigurationStatus, BlockerCategory, ReleaseBlocker


class ConfigurationReadinessEvaluator:
    """Evaluates configuration safety, environment variable integrity, and secret sanitization."""

    @classmethod
    def evaluate(
        cls,
        configuration_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Verifies:
        - required environment variables
        - non-secret configuration
        - secret references without exposing values
        - production/dev differences
        - default unsafe configurations
        Never prints secrets.
        Classifications: READY, MISSING, UNSAFE, UNKNOWN.
        UNSAFE -> BLOCKED.
        """
        if not configuration_data:
            return {
                "status": ConfigurationStatus.UNKNOWN,
                "blockers": [
                    ReleaseBlocker(
                        blocker_id="blocker-cfg-missing-config",
                        category=BlockerCategory.UNSAFE_CONFIGURATION,
                        description="Configuration state data completely absent",
                        evidence="Empty configuration payload provided."
                    )
                ],
                "requires_human_review": True,
                "review_reasons": ["Missing configuration snapshot"]
            }

        missing_required_vars = configuration_data.get("missing_required_vars", [])
        unsafe_defaults = configuration_data.get("unsafe_defaults_detected", False)
        plaintext_secrets_exposed = configuration_data.get("plaintext_secrets_exposed", False)
        secret_refs_valid = configuration_data.get("secret_refs_valid", True)
        prod_dev_divergence = configuration_data.get("prod_dev_divergence", False)
        debug_mode_enabled = configuration_data.get("debug_mode_in_production", False)

        blockers: List[ReleaseBlocker] = []
        requires_human_review = False
        review_reasons: List[str] = []

        if plaintext_secrets_exposed or unsafe_defaults or debug_mode_enabled:
            desc = "Unsafe configuration detected: "
            if plaintext_secrets_exposed:
                desc += "plaintext secrets found in configuration files; "
            if unsafe_defaults:
                desc += "insecure default settings detected; "
            if debug_mode_enabled:
                desc += "DEBUG mode enabled in production environment; "

            blockers.append(ReleaseBlocker(
                blocker_id="blocker-cfg-unsafe",
                category=BlockerCategory.UNSAFE_CONFIGURATION,
                description=desc.strip(),
                evidence="Configuration security evaluation failed safety invariants (sanitized)."
            ))

        if missing_required_vars:
            blockers.append(ReleaseBlocker(
                blocker_id="blocker-cfg-missing-vars",
                category=BlockerCategory.UNSAFE_CONFIGURATION,
                description=f"Required environment variables missing ({len(missing_required_vars)} missing)",
                evidence=f"Missing variable names (keys only): {', '.join(missing_required_vars)}"
            ))

        if not secret_refs_valid:
            blockers.append(ReleaseBlocker(
                blocker_id="blocker-cfg-invalid-secret-ref",
                category=BlockerCategory.UNSAFE_CONFIGURATION,
                description="Secret reference paths or vault references are unresolvable",
                evidence="Vault/KMS key reference syntax invalid or target reference does not exist."
            ))

        if prod_dev_divergence:
            requires_human_review = True
            review_reasons.append("Significant configuration schema divergence between production and development")

        status = ConfigurationStatus.READY
        if blockers:
            status = ConfigurationStatus.UNSAFE
        elif missing_required_vars:
            status = ConfigurationStatus.MISSING
        elif requires_human_review:
            # Still acceptable if no hard blockers, but flags human review
            pass

        return {
            "status": status,
            "missing_required_vars_count": len(missing_required_vars),
            "unsafe_defaults": unsafe_defaults,
            "secret_refs_valid": secret_refs_valid,
            "prod_dev_divergence": prod_dev_divergence,
            "debug_mode_enabled": debug_mode_enabled,
            "blockers": blockers,
            "requires_human_review": requires_human_review,
            "review_reasons": review_reasons
        }
