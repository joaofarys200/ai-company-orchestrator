"""
JARVIS OS — File Lease Manager
Provides atomic, exclusive file leases to prevent concurrent modification conflicts
during multi-agent and mission development operations.
"""

from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Generator, List, Optional

logger = logging.getLogger("Jarvis.FileLeaseManager")


class FileLeaseConflictError(Exception):
    """Lançado quando um ficheiro já se encontra bloqueado exclusivamente por outro titular."""
    pass


class FileLeaseExpiredError(Exception):
    """Lançado quando a lease do ficheiro expirou."""
    pass


@dataclass
class FileLease:
    """Registo canónico de lease exclusiva sobre um ficheiro do workspace."""
    lease_id: str
    file_path: str
    holder_id: str
    acquired_at: float
    expires_at: float
    ttl_seconds: float = 30.0

    def is_valid(self, now: Optional[float] = None) -> bool:
        curr = now if now is not None else time.time()
        return curr <= self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class FileLeaseManager:
    """
    Gestor atómico e thread-safe de bloqueios (leases) exclusivos sobre ficheiros.
    Impede que dois agentes, workers ou sessões modifiquem o mesmo ficheiro concorrentemente.
    """

    def __init__(self, default_ttl_seconds: float = 30.0) -> None:
        self.default_ttl_seconds = default_ttl_seconds
        self._lock = threading.RLock()
        self._leases_by_path: Dict[str, FileLease] = {}
        self._leases_by_id: Dict[str, FileLease] = {}

    def _normalize_path(self, file_path: str) -> str:
        return os.path.normcase(os.path.abspath(file_path))

    def acquire_file_lease(
        self,
        file_path: str,
        holder_id: str,
        ttl_seconds: Optional[float] = None,
        now: Optional[float] = None,
    ) -> FileLease:
        """
        Adquire lease exclusiva para o ficheiro.
        Se já existir lease válida de outro titular, levanta FileLeaseConflictError.
        Se o mesmo titular já tiver a lease, renova-a.
        """
        norm_path = self._normalize_path(file_path)
        curr = now if now is not None else time.time()
        effective_ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl_seconds

        with self._lock:
            existing = self._leases_by_path.get(norm_path)
            if existing and existing.is_valid(curr):
                if existing.holder_id != holder_id:
                    remaining = existing.expires_at - curr
                    raise FileLeaseConflictError(
                        f"Conflito de modificação: o ficheiro '{os.path.basename(norm_path)}' "
                        f"está bloqueado exclusivamente por '{existing.holder_id}' "
                        f"(expira em {remaining:.1f}s, lease_id: {existing.lease_id})."
                    )
                # Mesmo titular: renova a lease existente
                existing.expires_at = curr + effective_ttl
                existing.ttl_seconds = effective_ttl
                return existing

            # Cria nova lease
            lease_id = f"flease_{uuid.uuid4().hex[:10]}"
            lease = FileLease(
                lease_id=lease_id,
                file_path=norm_path,
                holder_id=holder_id,
                acquired_at=curr,
                expires_at=curr + effective_ttl,
                ttl_seconds=effective_ttl,
            )
            self._leases_by_path[norm_path] = lease
            self._leases_by_id[lease_id] = lease
            return lease

    def release_file_lease(self, lease_id: str, holder_id: str) -> bool:
        """Liberta a lease exclusiva especificada se pertencer ao titular."""
        with self._lock:
            lease = self._leases_by_id.get(lease_id)
            if not lease:
                return False
            if lease.holder_id != holder_id:
                logger.warning(
                    f"Tentativa não autorizada de libertar lease '{lease_id}': "
                    f"titular '{lease.holder_id}' != '{holder_id}'."
                )
                return False

            if lease.file_path in self._leases_by_path:
                del self._leases_by_path[lease.file_path]
            del self._leases_by_id[lease_id]
            return True

    def release_all_for_holder(self, holder_id: str) -> int:
        """Liberta todas as leases ativas detidas pelo titular (ex: ao concluir uma missão)."""
        released = 0
        with self._lock:
            to_remove = [
                lid for lid, l in self._leases_by_id.items()
                if l.holder_id == holder_id
            ]
            for lid in to_remove:
                l = self._leases_by_id[lid]
                if l.file_path in self._leases_by_path:
                    del self._leases_by_path[l.file_path]
                del self._leases_by_id[lid]
                released += 1
        return released

    def is_file_locked(self, file_path: str, now: Optional[float] = None) -> bool:
        """Verifica se o ficheiro possui uma lease ativa e não expirada."""
        norm_path = self._normalize_path(file_path)
        curr = now if now is not None else time.time()
        with self._lock:
            existing = self._leases_by_path.get(norm_path)
            return bool(existing and existing.is_valid(curr))

    def get_lease_holder(self, file_path: str, now: Optional[float] = None) -> Optional[str]:
        norm_path = self._normalize_path(file_path)
        curr = now if now is not None else time.time()
        with self._lock:
            existing = self._leases_by_path.get(norm_path)
            if existing and existing.is_valid(curr):
                return existing.holder_id
            return None

    @contextmanager
    def file_lock(
        self,
        file_path: str,
        holder_id: str,
        ttl_seconds: Optional[float] = None,
    ) -> Generator[FileLease, None, None]:
        """Context manager seguro para adquirir e libertar leases automaticamente."""
        lease = self.acquire_file_lease(file_path, holder_id, ttl_seconds=ttl_seconds)
        try:
            yield lease
        finally:
            self.release_file_lease(lease.lease_id, holder_id)


# Instância global singleton partilhada
_GLOBAL_FILE_LEASE_MANAGER: Optional[FileLeaseManager] = None
_GLOBAL_LOCK = threading.RLock()


def get_file_lease_manager() -> FileLeaseManager:
    global _GLOBAL_FILE_LEASE_MANAGER
    with _GLOBAL_LOCK:
        if _GLOBAL_FILE_LEASE_MANAGER is None:
            _GLOBAL_FILE_LEASE_MANAGER = FileLeaseManager()
        return _GLOBAL_FILE_LEASE_MANAGER


def reset_file_lease_manager() -> None:
    global _GLOBAL_FILE_LEASE_MANAGER
    with _GLOBAL_LOCK:
        _GLOBAL_FILE_LEASE_MANAGER = None
