"""
JARVIS OS — File Quarantine Executor (Fase S3)
Defensive isolation of suspicious files to secure quarantine vault with cryptographic integrity and full rollback.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from typing import Any, Dict, Optional, Tuple

from security.sentinel.contracts import ResponseActionType, SecurityResponseAction
from security.sentinel.response.executors.base import BaseActionExecutor


class FileQuarantineExecutor(BaseActionExecutor):
    """Executor defensivo para quarentena de ficheiros suspeitos sem destruição de dados."""

    def __init__(self, quarantine_dir: Optional[str] = None) -> None:
        super().__init__(ResponseActionType.QUARANTINE_FILE)
        if quarantine_dir is None:
            project_root = os.path.realpath(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
            self.quarantine_dir = os.path.join(project_root, "sentinel", "quarantine")
        else:
            self.quarantine_dir = quarantine_dir
        os.makedirs(self.quarantine_dir, exist_ok=True)

    def _sanitize_path(self, target: str) -> str:
        cleaned = target.replace("file:", "").replace("path:", "").strip()
        if not cleaned:
            raise ValueError("Caminho do ficheiro para quarentena não pode ser vazio")
        return os.path.normpath(os.path.abspath(cleaned))

    def _compute_sha256(self, file_path: str) -> str:
        if not file_path or not os.path.isfile(file_path):
            return ""
        hasher = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception:
            return ""

    def capture_pre_state(self, action: SecurityResponseAction) -> Dict[str, Any]:
        try:
            path = self._sanitize_path(action.target)
            exists = os.path.isfile(path)
            sha256 = self._compute_sha256(path) if exists else ""
            size = os.path.getsize(path) if exists else 0

            return {
                "original_path": path,
                "exists": exists,
                "sha256": sha256,
                "size_bytes": size,
                "captured_at": time.time(),
            }
        except Exception as e:
            return {"original_path": action.target, "error": str(e), "captured_at": time.time()}

    def pre_check(self, action: SecurityResponseAction) -> Tuple[bool, str]:
        try:
            path = self._sanitize_path(action.target)
        except ValueError as e:
            return False, str(e)

        # 1. Proteção estrita contra isolamento acidental de ficheiros do sistema operativo ou aplicações globais
        win_dir = os.environ.get("WINDIR", r"C:\Windows").lower()
        prog_files = os.environ.get("ProgramFiles", r"C:\Program Files").lower()
        prog_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)").lower()

        lower_path = path.lower()
        if (
            lower_path.startswith(win_dir)
            or lower_path.startswith(prog_files)
            or lower_path.startswith(prog_files_x86)
        ):
            return False, f"Bloqueado: Não é permitido colocar em quarentena ficheiros de sistema ou Program Files ('{path}')"

        if not os.path.exists(path):
            return False, f"Ficheiro alvo '{path}' não existe no disco"

        # Se o pre_state foi gravado previamente, valida integridade do ficheiro (prevenção de substituição)
        if action.pre_state and action.pre_state.get("sha256"):
            recorded_hash = action.pre_state.get("sha256")
            current_hash = self._compute_sha256(path)
            if recorded_hash != current_hash:
                return False, f"Alvo modificado: Hash atual ({current_hash[:8]}...) difere do hash registado ({recorded_hash[:8]}...)"

        return True, f"Ficheiro '{path}' validado para isolamento em quarentena"

    def execute(self, action: SecurityResponseAction) -> Dict[str, Any]:
        path = self._sanitize_path(action.target)
        sha256 = self._compute_sha256(path)
        timestamp = int(time.time() * 1000)

        quarantine_filename = f"{sha256[:16]}_{timestamp}.quarantine"
        quarantine_path = os.path.join(self.quarantine_dir, quarantine_filename)
        metadata_path = os.path.join(self.quarantine_dir, f"{sha256[:16]}_{timestamp}.json")

        # Registo de metadados de auditoria do ficheiro
        metadata = {
            "action_id": action.action_id,
            "incident_id": action.incident_id,
            "original_path": path,
            "sha256": sha256,
            "quarantined_at": time.time(),
            "quarantine_file": quarantine_path,
            "size_bytes": os.path.getsize(path),
        }

        # Move o ficheiro para quarentena
        shutil.move(path, quarantine_path)

        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        return {
            "original_path": path,
            "quarantine_path": quarantine_path,
            "metadata_path": metadata_path,
            "sha256": sha256,
            "quarantined_at": time.time(),
            "status": "QUARANTINED",
        }

    def verify(self, action: SecurityResponseAction) -> Tuple[bool, Dict[str, Any]]:
        path = self._sanitize_path(action.target)
        exec_res = action.execution_result
        quarantine_path = exec_res.get("quarantine_path", "")
        expected_hash = exec_res.get("sha256", "")

        # 1. Confirma que o original foi removido
        if os.path.exists(path):
            return False, {
                "verified": False,
                "reason": f"O ficheiro original '{path}' ainda permanece na localização de origem",
                "post_state": {"original_exists": True},
            }

        # 2. Confirma que o ficheiro de quarentena existe
        if not os.path.isfile(quarantine_path):
            return False, {
                "verified": False,
                "reason": f"Ficheiro de quarentena '{quarantine_path}' não foi encontrado",
                "post_state": {"quarantine_exists": False},
            }

        # 3. Confirma integridade criptográfica
        quarantined_hash = self._compute_sha256(quarantine_path)
        if quarantined_hash != expected_hash:
            return False, {
                "verified": False,
                "reason": f"Hash do ficheiro em quarentena ({quarantined_hash}) difere do esperado ({expected_hash})",
                "post_state": {"quarantined_hash": quarantined_hash},
            }

        return True, {
            "verified": True,
            "reason": "Ficheiro original isolado com sucesso; integridade SHA-256 preservada em quarentena",
            "post_state": {
                "original_exists": False,
                "quarantine_exists": True,
                "sha256": quarantined_hash,
            },
        }

    def rollback(self, action: SecurityResponseAction) -> Tuple[bool, Dict[str, Any]]:
        exec_res = action.execution_result
        original_path = exec_res.get("original_path") or self._sanitize_path(action.target)
        quarantine_path = exec_res.get("quarantine_path", "")
        metadata_path = exec_res.get("metadata_path", "")

        if not os.path.isfile(quarantine_path):
            return False, {
                "rollback_applied": False,
                "error": f"Ficheiro de quarentena '{quarantine_path}' não existe para efetuar rollback",
            }

        # Cria pasta pai se tiver sido apagada
        os.makedirs(os.path.dirname(original_path), exist_ok=True)

        # Move de volta
        shutil.move(quarantine_path, original_path)

        # Limpa ficheiro de metadados
        if metadata_path and os.path.isfile(metadata_path):
            try:
                os.remove(metadata_path)
            except Exception:
                pass

        # Verifica restauração
        restored_hash = self._compute_sha256(original_path)
        return True, {
            "rollback_applied": True,
            "message": f"Ficheiro restaurado para '{original_path}' com sucesso",
            "sha256": restored_hash,
        }
