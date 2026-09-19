"""
Phase 71 — Local Runtime Controller & Environmental Grounding
Detects physical cloud/Kubernetes deployment availability.
Emits DEPLOYMENT_NOT_AVAILABLE honestly and governs real local runtime operations.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple
from .models import OperationalState, RuntimeTarget


class InfrastructureDetector:
    """
    Detects physical presence of container and cloud execution targets.
    """

    @staticmethod
    def detect() -> Dict[str, bool]:
        """Checks for real existence of external tools in local system PATH."""
        docker_ok = shutil.which("docker") is not None
        kubectl_ok = shutil.which("kubectl") is not None
        # Check cloud CLI runners
        aws_ok = shutil.which("aws") is not None
        gcloud_ok = shutil.which("gcloud") is not None
        az_ok = shutil.which("az") is not None
        cloud_runner_ok = aws_ok or gcloud_ok or az_ok

        return {
            "docker_available": docker_ok,
            "kubectl_available": kubectl_ok,
            "cloud_runner_available": cloud_runner_ok,
            "physical_infrastructure_present": docker_ok or kubectl_ok or cloud_runner_ok,
        }

    @staticmethod
    def get_environment_classification() -> Tuple[RuntimeTarget, Optional[OperationalState]]:
        """
        Classifies runtime target.
        If physical cloud infrastructure is absent, returns (LOCAL_RUNTIME, DEPLOYMENT_NOT_AVAILABLE).
        """
        detection = InfrastructureDetector.detect()
        if not detection["physical_infrastructure_present"]:
            return RuntimeTarget.LOCAL_RUNTIME, OperationalState.DEPLOYMENT_NOT_AVAILABLE
        return RuntimeTarget.DEPLOYMENT_TARGET, None


class LocalRuntimeController:
    """
    Executes and monitors strictly local processes safely, without pretending to be a cloud cluster.
    """

    def __init__(self, service_id: str):
        self.service_id = service_id
        self._managed_processes: Dict[str, subprocess.Popen] = {}
        self._process_logs: Dict[str, List[str]] = {}

    def check_port_open(self, host: str = "127.0.0.1", port: int = 8000, timeout: float = 0.5) -> bool:
        """Verifies if a local port is actively bound and listening."""
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            return False

    def start_local_process(
        self,
        name: str,
        cmd: List[str],
        cwd: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """Spawns a monitored local subprocess safely."""
        if name in self._managed_processes and self._managed_processes[name].poll() is None:
            return True, f"Process '{name}' is already running with PID {self._managed_processes[name].pid}."

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self._managed_processes[name] = proc
            self._process_logs[name] = [f"Started with PID {proc.pid} at {time.time()}"]
            return True, f"Started local process '{name}' (PID: {proc.pid})."
        except Exception as exc:
            return False, f"Failed to start local process '{name}': {str(exc)}"

    def terminate_process(self, name: str) -> Tuple[bool, str]:
        """Gracefully terminates a local subprocess."""
        if name not in self._managed_processes:
            return False, f"Process '{name}' is not tracked."

        proc = self._managed_processes[name]
        if proc.poll() is not None:
            return True, f"Process '{name}' was already terminated (exit code: {proc.returncode})."

        try:
            proc.terminate()
            try:
                proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=1.0)
            return True, f"Process '{name}' terminated successfully."
        except Exception as exc:
            return False, f"Failed terminating '{name}': {str(exc)}"

    def restart_process(
        self,
        name: str,
        cmd: List[str],
        cwd: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """Restarts a managed local process cleanly."""
        self.terminate_process(name)
        time.sleep(0.1)
        return self.start_local_process(name, cmd, cwd)

    def is_process_alive(self, name: str) -> bool:
        if name not in self._managed_processes:
            return False
        return self._managed_processes[name].poll() is None

    def get_logs(self, name: str) -> List[str]:
        return list(self._process_logs.get(name, []))
