"""
JARVIS OS — Real Browser QA Integration Validator
Invoca e orquestra a execução de testes no navegador real (Microsoft Edge / Playwright)
e reconcilia com a governança de aceitação de produto.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional

logger = logging.getLogger("Jarvis.RealBrowserQA")


class RealBrowserQAValidator:
    """Valida o preview real através de testes de browser de ponta a ponta."""

    RUNNER_SCRIPT = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "scripts",
        "run_real_browser_qa.cjs",
    )

    ARTIFACTS_DIR = "C:/Users/joaor/.gemini/antigravity-ide/brain/b312d351-2732-4aea-a0a9-e218fa8e1fba"

    @classmethod
    def execute_browser_qa(
        cls,
        preview_url: str,
        mission_id: str = "qa_mission",
        evidence_dir: Optional[str] = None,
        timeout_seconds: float = 25.0,
        actions: Optional[List[Dict[str, Any]]] = None,
        project_id: str = "",
        timeout_ms: Optional[float] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Executa o script de Browser QA real via Node.js e Playwright/Edge.
        """
        if timeout_ms:
            timeout_seconds = timeout_ms / 1000.0

        resolved_evidence_dir = evidence_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "evidence",
            "product_delivery",
        )
        os.makedirs(resolved_evidence_dir, exist_ok=True)

        if not os.path.isfile(cls.RUNNER_SCRIPT):
            return {
                "available": False,
                "valid": False,
                "status": "INSUFFICIENT_EVIDENCE",
                "violations": [f"Runner script ausente: {cls.RUNNER_SCRIPT}"],
                "screenshots": [],
                "evidence_screenshots": [],
            }

        cmd = [
            "node",
            cls.RUNNER_SCRIPT,
            preview_url,
            mission_id,
            resolved_evidence_dir,
        ]

        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            raw_stdout = res.stdout.strip()
            # Encontrar JSON no stdout
            for line in reversed(raw_stdout.splitlines()):
                line = line.strip()
                if line.startswith("{") and line.endswith("}"):
                    try:
                        data = json.loads(line)
                        screenshots = data.get("evidence_screenshots", [])
                        data["screenshots"] = screenshots
                        # Copia screenshots para artifacts dir se existir
                        cls._copy_evidence_to_artifacts(screenshots)
                        return data
                    except Exception:
                        continue

            return {
                "available": True,
                "valid": False,
                "status": "FAIL",
                "violations": [f"Saída inesperada do Browser QA runner: {raw_stdout[:200]} {res.stderr[:200]}"],
                "evidence_screenshots": [],
            }
        except subprocess.TimeoutExpired:
            return {
                "available": True,
                "valid": False,
                "status": "FAIL",
                "violations": [f"Browser QA excedeu o tempo limite de {timeout_seconds}s contra {preview_url}."],
                "evidence_screenshots": [],
            }
        except Exception as exc:
            return {
                "available": False,
                "valid": False,
                "status": "INSUFFICIENT_EVIDENCE",
                "violations": [f"Erro ao executar runner do browser: {exc}"],
                "evidence_screenshots": [],
            }

    @classmethod
    def _copy_evidence_to_artifacts(cls, screenshots: List[str]) -> None:
        if not os.path.isdir(cls.ARTIFACTS_DIR):
            return
        for s in screenshots:
            if os.path.isfile(s):
                try:
                    dest = os.path.join(cls.ARTIFACTS_DIR, os.path.basename(s))
                    shutil.copy2(s, dest)
                except Exception:
                    pass
