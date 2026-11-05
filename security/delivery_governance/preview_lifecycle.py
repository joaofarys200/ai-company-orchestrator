"""
JARVIS OS — Preview Lifecycle Governance
Garante o controlo de ciclo de vida seguro de instâncias de preview:
- Identifica processos em portas antes de qualquer ação.
- NUNCA termina processos de outras aplicações ou de projetos não-proprietários.
- Reinicia instâncias comprovadamente desatualizadas (STALE_RUNTIME) de forma controlada.
- Aguarda port readiness e confirma healthcheck e versão servida antes de aprovar.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from typing import Any, Dict, Optional, Tuple

from security.delivery_governance.runtime_identity import RuntimeIdentity, RuntimeTracker

logger = logging.getLogger("Jarvis.PreviewLifecycle")


class PreviewLifecycleManager:
    """Gestor de arranque, reinício e auditoria de processos de preview de projetos."""

    @classmethod
    def ensure_fresh_preview(
        cls,
        project_root: str,
        project_id: str,
        port: Optional[int] = None,
        start_command: Optional[str] = None,
        endpoint: Optional[str] = None,
        allow_foreign_kill: bool = False,
        wait_timeout: float = 12.0,
    ) -> Dict[str, Any]:
        """
        Método unificado de garantia de preview fresco e saudável.
        """
        ident = cls.ensure_valid_preview(
            project_root=project_root,
            project_id=project_id,
            start_command=start_command,
            port=port,
            wait_timeout=wait_timeout,
        )
        success = ident.is_running and not ident.is_stale and ident.is_owned
        return {
            "success": success,
            "identity": ident.to_dict(),
            "action": "VERIFIED_OR_RESTARTED",
            "port": ident.port or port,
            "error": "Preview falhou ou não é proprietário" if not success else None,
        }

    @classmethod
    def ensure_valid_preview(
        cls,
        project_root: str,
        project_id: str,
        start_command: Optional[str] = None,
        port: Optional[int] = None,
        wait_timeout: float = 12.0,
    ) -> RuntimeIdentity:
        """
        Garante que o projeto está a correr e a servir a versão exata do código em disco.
        Se estiver desatualizado (stale), reinicia-o de forma segura.
        Se a porta estiver ocupada por um processo de terceiros, recusa terminar e bloqueia.
        """
        norm_root = os.path.realpath(os.path.abspath(project_root))
        target_port = port or RuntimeTracker.detect_project_port(norm_root)

        # 1. Inspecionar estado atual
        initial_identity = RuntimeTracker.inspect_runtime(
            project_root=norm_root,
            project_id=project_id,
            port=target_port,
        )

        # 2. Conflito com processo de terceiros
        if initial_identity.process_status == "PORT_CONFLICT_UNOWNED" or (
            initial_identity.process_id and not initial_identity.is_owned
        ):
            logger.warning(
                f"[Lifecycle] Porta {target_port} ocupada por processo não pertencente ao projeto {project_id}. "
                f"PID: {initial_identity.process_id}."
            )
            initial_identity.verified = False
            return initial_identity

        # 3. Se já estiver a correr a versão atual e saudável, nada a fazer
        if (
            initial_identity.process_status == "RUNNING"
            and initial_identity.healthcheck_status == "HEALTHY"
            and not initial_identity.is_stale
            and initial_identity.is_owned
        ):
            logger.info(f"[Lifecycle] Preview do projeto {project_id} na porta {target_port} já está ativo e atualizado.")
            initial_identity.verified = True
            return initial_identity

        # 4. Se existir processo antigo/stale do projeto, efetua paragem controlada
        if initial_identity.process_id and initial_identity.is_owned:
            logger.info(
                f"[Lifecycle] Processo antigo do projeto {project_id} detetado (PID: {initial_identity.process_id}, Stale: {initial_identity.is_stale}). A reiniciar..."
            )
            stopped = cls.stop_owned_process(initial_identity.process_id, target_port)
            if not stopped:
                initial_identity.verified = False
                initial_identity.limitation = (
                    f"Não foi possível parar o processo antigo (PID: {initial_identity.process_id}) na porta {target_port}."
                )
                return initial_identity

        # 5. Determinar comando de arranque
        resolved_cmd = start_command or cls._infer_start_command(norm_root)
        if not resolved_cmd:
            initial_identity.verified = False
            initial_identity.process_status = "START_FAILED"
            initial_identity.limitation = f"Nenhum comando de arranque detetado para {project_id} (sem package.json ou app.js)."
            return initial_identity

        # 6. Iniciar processo em background de forma controlada
        logger.info(f"[Lifecycle] A iniciar preview para {project_id} com comando '{resolved_cmd}' na porta {target_port}...")
        proc = cls._spawn_server(resolved_cmd, norm_root)
        if not proc or proc.poll() is not None:
            initial_identity.verified = False
            initial_identity.process_status = "START_FAILED"
            initial_identity.limitation = f"Falha imediata ao executar '{resolved_cmd}' em {norm_root}."
            return initial_identity

        # 7. Aguardar disponibilidade da porta e healthcheck
        ready = cls._wait_for_port_and_health(
            port=target_port,
            timeout=wait_timeout,
        )

        if not ready:
            initial_identity.verified = False
            initial_identity.process_status = "START_FAILED"
            initial_identity.limitation = (
                f"O servidor do projeto {project_id} iniciou mas não ficou disponível na porta {target_port} "
                f"dentro do tempo limite ({wait_timeout}s)."
            )
            return initial_identity

        # 8. Re-inspecionar a identidade final do novo runtime
        final_identity = RuntimeTracker.inspect_runtime(
            project_root=norm_root,
            project_id=project_id,
            port=target_port,
        )

        if final_identity.is_stale or final_identity.process_status != "RUNNING":
            final_identity.verified = False
            final_identity.limitation = (
                f"O servidor na porta {target_port} foi iniciado mas ainda apresenta inconsistência de versão."
            )
            return final_identity

        final_identity.verified = True
        return final_identity

    @classmethod
    def stop_owned_process(cls, pid: int, port: int, timeout: float = 5.0) -> bool:
        """Termina exclusivamente um processo cuja propriedade foi confirmada."""
        try:
            if sys.platform == "win32":
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=timeout,
                )
            else:
                import signal
                os.kill(pid, signal.SIGKILL)
        except Exception as e:
            logger.debug(f"[Lifecycle] Erro ao matar PID {pid}: {e}")

        # Aguarda libertação da porta
        start_wait = time.time()
        while time.time() - start_wait < timeout:
            proc_check = RuntimeTracker.find_process_on_port(port)
            if not proc_check:
                return True
            time.sleep(0.3)

        return False

    @classmethod
    def _infer_start_command(cls, project_root: str) -> Optional[str]:
        pkg_json = os.path.join(project_root, "package.json")
        if os.path.isfile(pkg_json):
            import json
            try:
                data = json.loads(Path(pkg_json).read_text(encoding="utf-8"))
                scripts = data.get("scripts", {})
                if "start" in scripts:
                    return "npm start"
                if "dev" in scripts:
                    return "npm run dev"
                if "preview" in scripts:
                    return "npm run preview"
            except Exception:
                pass

        for entry in ("app.js", "server.js", "main.js", "index.js"):
            if os.path.isfile(os.path.join(project_root, entry)):
                return f"node {entry}"

        for py_entry in ("app.py", "main.py", "server.py"):
            if os.path.isfile(os.path.join(project_root, py_entry)):
                return f"python {py_entry}"

        return None

    @classmethod
    def _spawn_server(cls, command: str, cwd: str) -> Optional[subprocess.Popen]:
        """Arranca o processo desacoplado em background."""
        try:
            if sys.platform == "win32":
                return subprocess.Popen(
                    command,
                    cwd=cwd,
                    shell=True,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                return subprocess.Popen(
                    command,
                    cwd=cwd,
                    shell=True,
                    preexec_fn=os.setsid,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
        except Exception as e:
            logger.error(f"[Lifecycle] Falha ao arrancar servidor '{command}': {e}")
            return None

    @classmethod
    def _wait_for_port_and_health(cls, port: int, timeout: float = 10.0) -> bool:
        start_t = time.time()
        url = f"http://127.0.0.1:{port}/"
        import urllib.request
        while time.time() - start_t < timeout:
            proc = RuntimeTracker.find_process_on_port(port)
            if proc:
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": "Jarvis-HealthCheck/1.0"})
                    with urllib.request.urlopen(req, timeout=1.5) as resp:
                        if resp.status < 400:
                            return True
                except Exception:
                    pass
            time.sleep(0.4)
        return False
