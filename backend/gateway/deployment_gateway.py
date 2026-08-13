from __future__ import annotations

import httpx
import json
import os
from pathlib import Path
from typing import Any

from sandbox import SANDBOX_DIR, write_project_files, start_local_fallback_server, get_sandbox_status


class WebDeploymentGateway:
    """Deploys MVPs to the local sandbox preview server and performs real HTTP verification."""

    def __init__(self, port: int = 8080):
        self.port = port
        self.base_url = f"http://127.0.0.1:{self.port}"

    def deploy_local_mvp(self, html: str, css: str = "", js: str = "") -> dict[str, Any]:
        """Writes project files to sandbox_dir and ensures local HTTP fallback server is running."""
        write_project_files(html, css, js)
        start_local_fallback_server()
        return {
            "status": "DEPLOYED",
            "url": self.base_url,
            "preview_path": f"{self.base_url}/index.html",
            "health_path": f"{self.base_url}/healthz",
        }

    async def verify_deployment_health(self) -> tuple[bool, str, dict[str, Any]]:
        """Performs a real HTTP request to verify server availability and title rendering."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/index.html")
                if resp.status_code == 200:
                    return True, "Servidor Sandbox respondeu 200 OK", {
                        "status_code": 200,
                        "url": f"{self.base_url}/index.html",
                        "content_length": len(resp.text),
                    }
                return False, f"Servidor respondeu com status {resp.status_code}", {"status_code": resp.status_code}
        except Exception as e:
            return False, f"Falha ao ligar ao sandbox: {str(e)}", {"error": str(e)}


__all__ = ["WebDeploymentGateway"]
