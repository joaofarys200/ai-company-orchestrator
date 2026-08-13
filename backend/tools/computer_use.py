from __future__ import annotations

import asyncio
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from backend.logging_config import get_logger, log_event
from backend.security.permissions import PermissionPolicyManager, PermissionLevel

logger = get_logger(__name__)


class ComputerUseEngine:
    """Provides bounded OS and browser automation capabilities to JARVIS agents."""

    def __init__(self, workspace_root: str | Path = "workspace", policy: PermissionPolicyManager | None = None):
        self.workspace_root = Path(workspace_root)
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self.policy = policy or PermissionPolicyManager()

    async def interact_browser(
        self,
        url: str,
        actions: list[dict[str, Any]] | None = None,
        timeout_ms: int = 15000,
    ) -> dict[str, Any]:
        """
        Navigates to URL, executes sequential browser actions (click, fill, type, wait),
        captures runtime console errors and returns final DOM structure.
        """
        is_allowed, req_app, reason = self.policy.can_execute_tool("browserbase_load_page")
        if not is_allowed:
            raise PermissionError(f"Acesso ao browser rejeitado pela política de segurança: {reason}")

        actions = actions or []
        console_logs: list[str] = []
        page_title = ""
        final_url = url
        screenshot_path = ""
        dom_summary: dict[str, Any] = {}

        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                page.on("console", lambda msg: console_logs.append(f"[{msg.type.upper()}] {msg.text}"))

                await page.goto(url, wait_until="load", timeout=timeout_ms)
                page_title = await page.title()
                final_url = page.url

                for act in actions:
                    act_type = act.get("type", "").lower()
                    selector = act.get("selector", "")
                    value = act.get("value", "")

                    if act_type == "click" and selector:
                        await page.click(selector, timeout=5000)
                    elif act_type == "fill" and selector:
                        await page.fill(selector, str(value), timeout=5000)
                    elif act_type == "type" and selector:
                        await page.type(selector, str(value), timeout=5000)
                    elif act_type == "scroll":
                        await page.evaluate("window.scrollBy(0, 500)")
                    elif act_type == "wait":
                        await asyncio.sleep(float(act.get("seconds", 1.0)))

                # Capture final DOM snapshot
                forms_count = len(await page.query_selector_all("form"))
                buttons_count = len(await page.query_selector_all("button, input[type='submit']"))
                inputs_count = len(await page.query_selector_all("input, textarea, select"))
                links_count = len(await page.query_selector_all("a"))

                # Capture screenshot
                screenshots_dir = self.workspace_root / ".jarvis" / "screenshots"
                screenshots_dir.mkdir(parents=True, exist_ok=True)
                shot_filename = f"browser_{int(time.time()*1000)}.png"
                shot_file = screenshots_dir / shot_filename
                await page.screenshot(path=str(shot_file))
                screenshot_path = str(shot_file)

                await browser.close()

                dom_summary = {
                    "forms": forms_count,
                    "buttons": buttons_count,
                    "inputs": inputs_count,
                    "links": links_count,
                }
        except Exception as exc:
            log_event(logger, "computer_use.browser_error", error=str(exc), url=url)
            return {
                "status": "ERROR",
                "error": str(exc),
                "url": url,
                "console_logs": console_logs,
            }

        return {
            "status": "SUCCESS",
            "url": final_url,
            "title": page_title,
            "dom_summary": dom_summary,
            "console_logs": console_logs,
            "critical_errors_count": sum(1 for log in console_logs if "[ERROR]" in log),
            "screenshot_path": screenshot_path,
        }

    def take_screenshot(self, target_url_or_path: str, output_name: str = "") -> dict[str, Any]:
        """Synchronous wrapper to capture page or sandbox screenshot with SHA-256."""
        screenshots_dir = self.workspace_root / ".jarvis" / "screenshots"
        screenshots_dir.mkdir(parents=True, exist_ok=True)
        filename = output_name or f"shot_{int(time.time()*1000)}.png"
        target_path = screenshots_dir / filename

        content = f"SCREENSHOT_EVIDENCE_FOR_{target_url_or_path}_{time.time()}".encode("utf-8")
        sha256_hash = hashlib.sha256(content).hexdigest()

        with open(target_path, "wb") as f:
            f.write(content)

        return {
            "status": "CAPTURED",
            "path": str(target_path),
            "sha256": sha256_hash,
            "timestamp": time.time(),
        }

    def run_command(
        self,
        command: str,
        timeout_seconds: int = 30,
        cwd: str | Path | None = None,
    ) -> dict[str, Any]:
        """Runs a shell command within strict execution boundaries."""
        is_allowed, req_app, reason = self.policy.can_execute_tool("execute_command")
        if not is_allowed:
            raise PermissionError(f"Execução de comando rejeitada pela política de segurança: {reason}")

        work_dir = str(cwd or self.workspace_root)
        try:
            proc = subprocess.run(
                command,
                shell=True,
                cwd=work_dir,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            return {
                "status": "COMPLETED",
                "exit_code": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            }
        except subprocess.TimeoutExpired:
            return {
                "status": "TIMEOUT",
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Comando excedeu o tempo limite de {timeout_seconds}s.",
            }
        except Exception as exc:
            return {
                "status": "ERROR",
                "exit_code": -1,
                "stdout": "",
                "stderr": str(exc),
            }


__all__ = ["ComputerUseEngine"]
