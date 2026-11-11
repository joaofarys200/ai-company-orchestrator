"""
JARVIS OS — Study Engine Phase 6: Atomic Persistence Layer
Persistência atómica com escrita temporária + fsync + os.replace()
para materiais de estudo por documento e progresso global do estudante.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


class StudyModePersistence:
    """Gere leitura/escrita atómica dos artefactos da Fase 6 sem corromper fases anteriores."""

    def __init__(self, storage_dir: Path | str) -> None:
        self.storage_dir = Path(storage_dir)
        self.docs_dir = self.storage_dir / "documents"
        self.state_dir = self.storage_dir / "study_modes_state"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self._io_lock = threading.RLock()

    def document_dir(self, document_id: str) -> Path:
        return self.docs_dir / document_id

    def study_modes_dir(self, document_id: str) -> Path:
        d = self.document_dir(document_id) / "study_modes"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _atomic_write_json(self, target_path: Path, payload: Any) -> None:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(payload, indent=2, ensure_ascii=False)
        raw_bytes = serialized.encode("utf-8")
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{target_path.stem}_",
            suffix=".tmp",
            dir=str(target_path.parent),
        )
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(raw_bytes)
                handle.flush()
                os.fsync(handle.fileno())
            if not tmp_path.exists() or tmp_path.stat().st_size != len(raw_bytes):
                raise IOError(f"Falha na verificação de escrita atómica para {target_path.name}.")
            os.replace(tmp_path, target_path)
        except Exception:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass
            raise

    def _read_json(self, path: Path, default: Any = None) -> Tuple[Any, bool]:
        if not path.exists():
            return default, False
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data, True
        except Exception:
            return default, False

    # ------------------------------------------------------------------
    # Artefactos das Fases 2–5 (apenas leitura para Fase 6)
    # ------------------------------------------------------------------

    def load_upstream_artifacts(self, document_id: str) -> Dict[str, Any]:
        doc_dir = self.document_dir(document_id)
        ast_data, has_ast = self._read_json(doc_dir / "ast.json", None)
        dossier_data, has_dossier = self._read_json(doc_dir / "reasoning_dossier.json", None)
        plan_data, has_plan = self._read_json(doc_dir / "editorial_study_plan.json", None)
        dev_content_data, has_dev = self._read_json(doc_dir / "developed_content.json", None)
        if not has_dev:
            # Fase 5 também persiste por vezes em generated_content/developed_content.json ou similar
            alt_dev = doc_dir / "developed_content_v1.json"
            dev_content_data, has_dev = self._read_json(alt_dev, None)
        doc_gen_data, has_docgen = self._read_json(doc_dir / "document_generation_result.json", None)
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
            p = self.document_dir(document_id) / "study_modes" / filename
            data, ok = self._read_json(p, default)
            return data if ok else default

    def save_json_doc_artifact(self, document_id: str, filename: str, payload: Any) -> Path:
        with self._io_lock:
            p = self.study_modes_dir(document_id) / filename
            self._atomic_write_json(p, payload)
            return p

    # ------------------------------------------------------------------
    # Estado global do estudante (SRS, Histórico, Sessões, Progresso)
    # ------------------------------------------------------------------

    def load_state_file(self, filename: str, default: Any) -> Any:
        with self._io_lock:
            p = self.state_dir / filename
            data, ok = self._read_json(p, default)
            return data if ok else default

    def save_state_file(self, filename: str, payload: Any) -> Path:
        with self._io_lock:
            p = self.state_dir / filename
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

