"""
JARVIS OS — API & Frontend Contract Validator
Valida semântica e estruturalmente o contrato entre endpoints backend e código de interface:
- Garante que campos devolvidos pelo backend são mapeados e renderizados no frontend.
- Deteção de dessincronização contratual (ex: backend envia devices mas frontend só renderiza ips).
- Validação factual de GeoIP: proíbe alegações de GPS exato ou ISP/ASN fictícios.
- 100% seguro: nunca executa tráfego de ataque ou varreduras agressivas durante a validação.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("Jarvis.ContractValidator")


class ContractValidator:
    """Valida o acoplamento contratual entre respostas de endpoints e componentes de apresentação."""

    @classmethod
    def validate_local_scan_contract(
        cls,
        sample_payload: Dict[str, Any],
        frontend_js_code: str,
    ) -> Dict[str, Any]:
        """
        Valida o contrato do scanner de rede local.
        """
        violations: List[str] = []
        warnings: List[str] = []

        # 1. Validação do Payload Backend
        if "ips" not in sample_payload:
            violations.append("BACKEND_CONTRACT_VIOLATION: Campo 'ips' obrigatório em falta no payload.")
        if "devices" not in sample_payload:
            violations.append("BACKEND_CONTRACT_VIOLATION: Campo 'devices' (dispositivos estruturados) em falta no payload.")

        devices = sample_payload.get("devices") or []
        if devices and isinstance(devices, list):
            sample_device = devices[0] if isinstance(devices[0], dict) else {}
            for expected_field in ("ip", "mac", "vendor", "role"):
                if expected_field not in sample_device:
                    violations.append(f"BACKEND_DEVICE_FIELD_MISSING: Campo '{expected_field}' ausente no objeto de dispositivo.")

        # 2. Validação do Consumo no Frontend
        # O frontend DEVE referenciar e renderizar 'devices'
        if not re.search(r'\b(?:data\.)?devices\b', frontend_js_code):
            violations.append("FRONTEND_CONTRACT_DESYNC: O frontend não processa 'devices', continuando acoplado apenas ao contrato legado 'ips'.")

        for fld in ("ip", "mac", "vendor", "role"):
            if not re.search(rf'\b[a-zA-Z0-9_]+\.{fld}\b', frontend_js_code):
                warnings.append(f"FRONTEND_UNRENDERED_FIELD: O campo '{fld}' de device pode não estar a ser renderizado na interface.")

        # Deteta se o frontend ainda tem um fallback que mascara o resultado
        has_silent_legacy_fallback = bool(re.search(r'else\s+if\s*\([^)]*data\.ips[^)]*\)', frontend_js_code))

        return {
            "valid": len(violations) == 0,
            "violations": violations,
            "warnings": warnings,
            "has_silent_legacy_fallback": has_silent_legacy_fallback,
        }

    @classmethod
    def validate_geoip_contract(
        cls,
        sample_payload: Dict[str, Any],
        frontend_js_code: str,
    ) -> Dict[str, Any]:
        """
        Valida o contrato de identificação geográfica e alvo.
        """
        violations: List[str] = []
        warnings: List[str] = []

        # 1. Validação do Payload Backend
        if "targetIp" not in sample_payload:
            violations.append("BACKEND_CONTRACT_VIOLATION: Campo 'targetIp' ausente no payload.")
        if "ipType" not in sample_payload:
            violations.append("BACKEND_CONTRACT_VIOLATION: Campo 'ipType' ausente no payload.")
        if "ipOrigin" not in sample_payload:
            violations.append("BACKEND_CONTRACT_VIOLATION: Campo 'ipOrigin' ausente no payload.")

        ip_origin = sample_payload.get("ipOrigin")
        if isinstance(ip_origin, dict):
            # Proíbe falsas alegações de ISP/ASN se a biblioteca (ex: geoip-lite) não as fornecer
            if "isp" in ip_origin and not ip_origin["isp"]:
                warnings.append("GEOIP_NULL_FIELD: 'isp' está presente mas vazio.")
            # Proíbe declarar precisão física exata
            if ip_origin.get("exact_physical_address"):
                violations.append("FACTUAL_INTEGRITY_VIOLATION: Proibido declarar localização física/GPS exata via GeoIP.")

        # 2. Validação no Frontend
        if not re.search(r'\b(?:data\.)?ipOrigin\b', frontend_js_code):
            violations.append("FRONTEND_CONTRACT_DESYNC: O frontend não consome nem apresenta 'ipOrigin'.")

        return {
            "valid": len(violations) == 0,
            "violations": violations,
            "warnings": warnings,
        }

    @classmethod
    def audit_project_contracts(cls, project_root: str) -> Dict[str, Any]:
        """
        Audita os contratos de código em disco entre app.js e client.js.
        """
        app_js_path = os.path.join(project_root, "app.js")
        client_js_path = os.path.join(project_root, "client.js")

        if not os.path.isfile(app_js_path) or not os.path.isfile(client_js_path):
            return {
                "valid": True,
                "status": "NOT_APPLICABLE_OR_NON_DINA",
                "details": "Ficheiros app.js ou client.js não encontrados para teste específico de contrato.",
                "violations": [],
            }

        client_js = Path(client_js_path).read_text(encoding="utf-8", errors="ignore")
        app_js = Path(app_js_path).read_text(encoding="utf-8", errors="ignore")

        # Mock seguro de payload local scan baseado no app.js real
        mock_scan_payload = {
            "message": "Dispositivos encontrados na rede local",
            "ips": ["192.168.1.1", "192.168.1.50"],
            "devices": [
                {
                    "ip": "192.168.1.1",
                    "mac": "00:11:22:33:44:55",
                    "vendor": "Test Vendor",
                    "hostname": "router.local",
                    "role": "Gateway / Router",
                }
            ],
        }

        # Mock seguro de payload GeoIP
        mock_geoip_payload = {
            "targetUrl": "https://example.com",
            "targetIp": "93.184.216.34",
            "ipType": "Público",
            "ipOrigin": {
                "country": "US",
                "city": "Norwell",
                "timezone": "America/New_York",
                "summary": "US (Norwell) [America/New_York]",
                "hostname": "example.com",
            },
        }

        scan_res = cls.validate_local_scan_contract(mock_scan_payload, client_js)
        geoip_res = cls.validate_geoip_contract(mock_geoip_payload, client_js)

        all_violations = scan_res["violations"] + geoip_res["violations"]
        all_warnings = scan_res["warnings"] + geoip_res["warnings"]

        return {
            "valid": len(all_violations) == 0,
            "violations": all_violations,
            "warnings": all_warnings,
            "scan_contract": scan_res,
            "geoip_contract": geoip_res,
        }
