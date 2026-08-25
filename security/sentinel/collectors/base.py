"""
JARVIS OS — Security Sentinel Base Collector Interface
Defensive, fail-safe, read-only collection foundation.
"""

from __future__ import annotations

import abc
import hashlib
import os
import re
import time
from typing import Any, Dict, List, Optional

from security.sentinel.contracts import (
    EventCategory,
    PrivacyClassification,
    SecurityEvidence,
)


class BaseCollector(abc.ABC):
    """Classe base abstrata para todos os coletores de telemetria de segurança."""

    def __init__(self, name: str, category: EventCategory) -> None:
        self.name = name
        self.category = category

    @abc.abstractmethod
    def collect(self) -> List[SecurityEvidence]:
        """Executa a recolha de evidência de forma estritamente READ-ONLY."""
        pass

    def compute_sha256(self, file_path: str) -> str:
        """Calcula o hash SHA-256 de um ficheiro de forma segura e com leitura em chunks."""
        if not file_path or not os.path.isfile(file_path):
            return ""
        hasher = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except (PermissionError, FileNotFoundError, OSError):
            return ""

    def sanitize_cmdline(self, cmdline: str) -> str:
        """Mascara palavras-passe, chaves de API e tokens comuns em linhas de comando."""
        if not cmdline:
            return ""
        # Mascarar padrões como --password=XYZ, -p XYZ, --token=XYZ, --key=XYZ
        patterns = [
            (r"(--password[=\s]+)([^\s]+)", r"\1***REDACTED***"),
            (r"(--token[=\s]+)([^\s]+)", r"\1***REDACTED***"),
            (r"(--api[-_]?key[=\s]+)([^\s]+)", r"\1***REDACTED***"),
            (r"(-p\s+)([^\s]+)", r"\1***REDACTED***"),
            (r"(Bearer\s+)([a-zA-Z0-9_\-\.]+)", r"\1***REDACTED***"),
        ]
        sanitized = cmdline
        for pattern, replacement in patterns:
            sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)
        return sanitized

    def create_evidence(
        self,
        asset: str,
        observation: str,
        normalized_data: Dict[str, Any],
        raw_reference: str = "",
        confidence: float = 1.0,
        source: str = "host_telemetry",
        privacy_classification: str = PrivacyClassification.INTERNAL.value,
    ) -> SecurityEvidence:
        """Cria um objeto de evidência normalizado e com identificador único."""
        now = time.time()
        ev_id = f"EV-{self.name.upper()}-{int(now * 1000)}-{os.urandom(2).hex()}"
        serialized = str(normalized_data).encode("utf-8")
        data_hash = hashlib.sha256(serialized).hexdigest()

        return SecurityEvidence(
            evidence_id=ev_id,
            timestamp=now,
            collector=self.name,
            host=os.environ.get("COMPUTERNAME", "localhost"),
            asset=asset,
            observation=observation,
            raw_reference=raw_reference,
            normalized_data=normalized_data,
            sha256=data_hash,
            confidence=confidence,
            source=source,
            privacy_classification=privacy_classification,
        )
