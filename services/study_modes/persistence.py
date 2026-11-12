"""
JARVIS OS — Study Engine Phase 6: Atomic Persistence Layer
Persistência atómica com escrita temporária + fsync + os.replace()
para materiais de estudo por documento e progresso global do estudante.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

from services.study_fs import (
    atomic_write_json,
    read_json_safe,
    resolve_confined_path,
    safe_document_id,
    safe_filename,
)


class StudyModePersistence:
    """Gere leitura/escrita atómica dos artefactos da Fase 6 sem corromper fases anteriores."""

    def __init__(self, storage_dir: Path | str) -> None:
        self.storage_dir = Path(storage_dir)
        self.docs_dir = self.storage_dir / "documents"
        self.state_dir = self.storage_dir / "study_modes_state"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self._io_lock = threading.RLock()

    def document_dir(self, document_id: str) -> Path:
        clean_id = safe_document_id(document_id)
        return resolve_confined_path(self.docs_dir, clean_id)

    def study_modes_dir(self, document_id: str) -> Path:
        d = resolve_confined_path(self.document_dir(document_id), "study_modes")
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _atomic_write_json(self, target_path: Path, payload: Any) -> None:
        atomic_write_json(target_path, payload, indent=2)

    def _read_json(
        self,
        path: Path,
        default: Any = None,
        *,
        backup_on_corrupt: bool = True,
    ) -> Tuple[Any, bool]:
        if not path.exists():
            return default, False
        data, corrupted = read_json_safe(path, default=default, backup_on_corrupt=backup_on_corrupt)
        if corrupted:
            return default, False
        return data, True

    # ------------------------------------------------------------------
    # Artefactos das Fases 2–5 (apenas leitura para Fase 6)
    # ------------------------------------------------------------------

    def load_upstream_artifacts(self, document_id: str) -> Dict[str, Any]:
        doc_dir = self.document_dir(document_id)
        ast_data, _ = self._read_json(doc_dir / "ast.json", None, backup_on_corrupt=False)
        dossier_data, _ = self._read_json(doc_dir / "reasoning_dossier.json", None, backup_on_corrupt=False)
        plan_data, _ = self._read_json(doc_dir / "editorial_study_plan.json", None, backup_on_corrupt=False)
        dev_content_data, has_dev = self._read_json(doc_dir / "developed_study_content.json", None, backup_on_corrupt=False)
        if not has_dev:
            dev_content_data, has_dev = self._read_json(doc_dir / "developed_content.json", None, backup_on_corrupt=False)
        if not has_dev:
            alt_dev = doc_dir / "developed_content_v1.json"
            dev_content_data, has_dev = self._read_json(alt_dev, None, backup_on_corrupt=False)
        doc_gen_data, _ = self._read_json(doc_dir / "document_generation_result.json", None, backup_on_corrupt=False)
        return {
            "ast_data": ast_data if isinstance(ast_data, dict) else None,
            "dossier_data": dossier_data if isinstance(dossier_data, dict) else None,
            "plan_data": plan_data if isinstance(plan_data, dict) else None,
            "developed_content_data": dev_content_data if isinstance(dev_content_data, dict) else None,
            "docgen_result_data": doc_gen_data if isinstance(doc_gen_data, dict) else None,
        }

    # ------------------------------------------------------------------
    # Artefactos por documento (Flashcards, Cornell, Avaliações, Recall)
    # ------------------------------------------------------------------

    def load_json_doc_artifact(self, document_id: str, filename: str, default: Any = None) -> Optional[Any]:
        with self._io_lock:
            clean_name = safe_filename(filename)
            p = resolve_confined_path(self.document_dir(document_id), "study_modes", clean_name)
            data, ok = self._read_json(p, default)
            return data if ok else default

    def save_json_doc_artifact(self, document_id: str, filename: str, payload: Any) -> Path:
        with self._io_lock:
            clean_name = safe_filename(filename)
            p = resolve_confined_path(self.study_modes_dir(document_id), clean_name)
            self._atomic_write_json(p, payload)
            return p

    # ------------------------------------------------------------------
    # Estado global do estudante (SRS, Histórico, Sessões, Progresso)
    # ------------------------------------------------------------------

    def load_state_file(self, filename: str, default: Any) -> Any:
        with self._io_lock:
            clean_name = safe_filename(filename)
            p = resolve_confined_path(self.state_dir, clean_name)
            data, ok = self._read_json(p, default)
            return data if ok else default

    def save_state_file(self, filename: str, payload: Any) -> Path:
        with self._io_lock:
            clean_name = safe_filename(filename)
            p = resolve_confined_path(self.state_dir, clean_name)
            self._atomic_write_json(p, payload)
            return p

    def update_state_file_atomic(
        self,
        filename: str,
        default: Any,
        mutator: Callable[[Any], Any],
    ) -> Any:
        """Executa leitura-modificação-escrita atómica sob lock partilhado."""
        with self._io_lock:
            current = self.load_state_file(filename, default)
            updated = mutator(current)
            self.save_state_file(filename, updated)
            return updated

