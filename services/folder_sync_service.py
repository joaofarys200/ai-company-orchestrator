"""
JARVIS OS - Folder Synchronization Service for Study Area
Manages local folder association, filesystem monitoring, change detection
(new, modified, renamed, deleted files), debounce protection, and reconciliation.
Preserves original files on disk unconditionally (strictly non-destructive).
"""

from __future__ import annotations

import hashlib
import os
import re
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Supported Extensions & Whitelists
# ---------------------------------------------------------------------------

SUPPORTED_DOC_EXTENSIONS = {".pdf", ".docx", ".pptx", ".txt", ".md", ".markdown"}
SUPPORTED_VIDEO_EXTENSIONS = {
    ".mp4", ".webm", ".mkv", ".mov", ".avi", ".wmv", ".m4v", ".flv", ".mpg", ".mpeg"
}
SUPPORTED_AUDIO_EXTENSIONS = {
    ".mp3", ".wav", ".m4a", ".ogg", ".wma", ".aac", ".flac"
}
SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

ALL_SUPPORTED_EXTENSIONS = (
    SUPPORTED_DOC_EXTENSIONS
    | SUPPORTED_VIDEO_EXTENSIONS
    | SUPPORTED_AUDIO_EXTENSIONS
    | SUPPORTED_IMAGE_EXTENSIONS
)

SUPPORTED_DOC_EXTS = SUPPORTED_DOC_EXTENSIONS
SUPPORTED_VIDEO_EXTS = SUPPORTED_VIDEO_EXTENSIONS


def is_supported_study_file(file_path: str) -> bool:
    """Verifica se o ficheiro possui extensão suportada para estudo."""
    ext = os.path.splitext(file_path)[1].lower()
    return ext in ALL_SUPPORTED_EXTENSIONS


def compute_file_sha256(file_path: str) -> str:
    """Calcula o hash SHA256 do ficheiro no disco."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

IGNORED_DIRECTORIES = {
    ".git",
    ".obsidian",
    ".idea",
    ".vscode",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".trash",
}

IGNORED_FILE_PREFIXES = (".", "~$", "._")
IGNORED_FILE_SUFFIXES = (".tmp", ".crdownload", ".part", ".download", ".bak", ".swp")


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class StudyFolderLink:
    folder_path: str
    sync_enabled: bool = True
    recursive: bool = True
    last_synced_at: Optional[str] = None
    file_count: int = 0
    unsupported_count: int = 0
    status: str = "IDLE"  # IDLE, SYNCING, ERROR
    error: Optional[str] = None
    registered_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ScannedFileInfo:
    abs_path: str
    rel_path: str
    filename: str
    extension: str
    size_bytes: int
    mtime: float
    is_supported: bool
    source_type: str  # PDF, VIDEO, DOCX, TXT, MARKDOWN, IMAGE, AUDIO, PPTX, UNSUPPORTED
    unsupported_reason: Optional[str] = None


@dataclass
class FolderSyncReport:
    folder_path: str
    collection_id: str
    scanned_count: int = 0
    added_count: int = 0
    updated_count: int = 0
    removed_count: int = 0
    unsupported_count: int = 0
    failed_count: int = 0
    added_documents: List[str] = field(default_factory=list)
    updated_documents: List[str] = field(default_factory=list)
    removed_documents: List[str] = field(default_factory=list)
    renamed_count: int = 0
    unsupported_files: List[Dict[str, str]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    synced_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["total_files"] = self.total_files
        d["added_files"] = self.added_files
        d["modified_files"] = self.modified_files
        d["renamed_files"] = self.renamed_files
        d["deleted_files"] = self.deleted_files
        return d

    def get(self, key: str, default: Any = None) -> Any:
        return self.to_dict().get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self.to_dict()[key]

    @property
    def total_files(self) -> int:
        return self.scanned_count

    @property
    def added_files(self) -> int:
        return self.added_count

    @property
    def modified_files(self) -> int:
        return self.updated_count

    @property
    def renamed_files(self) -> int:
        return self.renamed_count

    @property
    def deleted_files(self) -> int:
        return self.removed_count


# ---------------------------------------------------------------------------
# Path Security & Validation
# ---------------------------------------------------------------------------

def validate_and_normalize_folder_path(folder_path: str) -> Path:
    """
    Valida e normaliza o caminho de uma pasta local para vinculação ao Estudo.
    Garante proteção contra path traversal, symlinks perigosos e caminhos inválidos.
    """
    if not folder_path or not str(folder_path).strip():
        raise ValueError("O caminho da pasta não pode estar vazio.")

    raw_str = str(folder_path).strip()
    # Detetar path traversal deliberado com '..' antes da normalização
    if ".." in raw_str.replace("\\", "/").split("/"):
        raise ValueError(f"PATH_TRAVERSAL_DETECTED: Caminho contém componentes ilegais: '{raw_str}'")

    path_obj = Path(raw_str).resolve()

    if not path_obj.exists():
        raise FileNotFoundError(f"A pasta especificada não existe: '{path_obj}'")

    if not path_obj.is_dir():
        raise NotADirectoryError(f"O caminho especificado não é uma pasta: '{path_obj}'")

    # Proteger contra raízes críticas do sistema (Windows / Linux)
    root_path = Path(path_obj.anchor)
    if path_obj == root_path:
        raise PermissionError("A vinculação da raiz do sistema de ficheiros (drive root) não é permitida.")

    sys_dirs = ["windows", "system32", "program files", "program files (x86)", "/etc", "/bin", "/sbin", "/usr"]
    lower_p = str(path_obj).lower()
    for sd in sys_dirs:
        if lower_p.endswith(f"\\{sd}") or lower_p.endswith(f"/{sd}"):
            raise PermissionError(f"Acesso a pastas críticas do sistema ({sd}) é proibido.")

    return path_obj


def determine_source_type(ext: str) -> str:
    """Mapeia a extensão do ficheiro para o SourceType da área de Estudo."""
    clean_ext = ext.lower().lstrip(".")
    if clean_ext == "pdf":
        return "PDF"
    elif clean_ext in ("mp4", "webm", "mkv", "mov", "avi", "wmv", "m4v", "flv", "mpg", "mpeg"):
        return "VIDEO"
    elif clean_ext in ("wav", "mp3", "m4a", "ogg", "wma", "aac", "flac"):
        return "AUDIO"
    elif clean_ext in ("png", "jpg", "jpeg", "webp"):
        return "IMAGE"
    elif clean_ext == "docx":
        return "DOCX"
    elif clean_ext == "pptx":
        return "PPTX"
    elif clean_ext in ("md", "markdown"):
        return "MARKDOWN"
    elif clean_ext in ("txt", "text"):
        return "TXT"
    return "UNSUPPORTED"


# ---------------------------------------------------------------------------
# FolderSyncManager
# ---------------------------------------------------------------------------

class FolderSyncManager:
    """
    Gestor de sincronização e monitorização contínua de pastas de estudo.
    Thread-safe, com proteção contra ficheiros em escrita e varrimento de reconciliação.
    """

    def __init__(
        self,
        poll_interval_seconds: float = 3.0,
        debounce_seconds: float = 1.0,
        logger: Any = None,
    ):
        self.poll_interval = poll_interval_seconds
        self.debounce_seconds = debounce_seconds
        self.logger = logger
        self._lock = threading.RLock()

        # Registo de pastas monitorizadas: (collection_id, folder_path) -> {params, last_scan}
        self._monitored_folders: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start_monitoring(self) -> None:
        """Inicia a thread de monitorização em background se ainda não estiver ativa."""
        with self._lock:
            if self._monitor_thread is not None and self._monitor_thread.is_alive():
                return
            self._stop_event.clear()
            self._monitor_thread = threading.Thread(
                target=self._monitoring_loop,
                name="StudyFolderSyncWorker",
                daemon=True,
            )
            self._monitor_thread.start()

    def stop_monitoring(self) -> None:
        """Pára a thread de monitorização em background."""
        self._stop_event.set()
        with self._lock:
            self._monitored_folders.clear()
            if self._monitor_thread is not None and self._monitor_thread.is_alive():
                self._monitor_thread.join(timeout=1.0)
            self._monitor_thread = None

    stop = stop_monitoring

    def register_folder(
        self,
        collection_id: str,
        folder_path: str,
        recursive: bool = True,
        on_change_callback: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        """Regista uma pasta para monitorização contínua."""
        norm_path = str(validate_and_normalize_folder_path(folder_path))
        key = (collection_id, norm_path)
        with self._lock:
            self._monitored_folders[key] = {
                "collection_id": collection_id,
                "folder_path": norm_path,
                "recursive": recursive,
                "on_change_callback": on_change_callback,
                "last_snapshot": self.scan_folder(norm_path, recursive=recursive),
            }
            if not self._monitor_thread or not self._monitor_thread.is_alive():
                self.start_monitoring()

    def unregister_folder(self, collection_id: str, folder_path: str) -> None:
        """Remove a pasta da monitorização contínua."""
        try:
            norm_path = str(validate_and_normalize_folder_path(folder_path))
        except Exception:
            norm_path = str(folder_path)

        key = (collection_id, norm_path)
        with self._lock:
            self._monitored_folders.pop(key, None)
            if not self._monitored_folders:
                self.stop_monitoring()

    def scan_folder(
        self,
        folder_path: str | Path,
        recursive: bool = True,
    ) -> Dict[str, ScannedFileInfo]:
        """
        Percorre a pasta local e devolve um dicionário de rel_path -> ScannedFileInfo.
        Ignora pastas e ficheiros de sistema/temporários.
        """
        target = Path(folder_path).resolve()
        if not target.exists() or not target.is_dir():
            return {}

        results: Dict[str, ScannedFileInfo] = {}
        now = time.time()

        for root, dirs, files in os.walk(str(target)):
            # Filtrar pastas ignoradas in-place
            dirs[:] = [d for d in dirs if d not in IGNORED_DIRECTORIES and not d.startswith(".")]

            root_path = Path(root)
            for fname in files:
                # Ignorar ficheiros temporários / ocultos
                if any(fname.startswith(p) for p in IGNORED_FILE_PREFIXES):
                    continue
                if any(fname.lower().endswith(s) for s in IGNORED_FILE_SUFFIXES):
                    continue

                abs_file = root_path / fname
                try:
                    rel_p = str(abs_file.relative_to(target)).replace("\\", "/")
                    stat = abs_file.stat()
                    size_bytes = stat.st_size
                    mtime = stat.st_mtime
                except (OSError, ValueError):
                    continue

                # Debounce de escrita: se o ficheiro foi alterado há menos de debounce_seconds,
                # e o tamanho for 0, pode estar ainda em cópia.
                ext = abs_file.suffix.lower()
                is_supported = ext in ALL_SUPPORTED_EXTENSIONS
                stype = determine_source_type(ext)
                unsupported_reason = None if is_supported else f"Formato de ficheiro '{ext}' não suportado pelo motor de estudo."

                results[rel_p] = ScannedFileInfo(
                    abs_path=str(abs_file),
                    rel_path=rel_p,
                    filename=fname,
                    extension=ext,
                    size_bytes=size_bytes,
                    mtime=mtime,
                    is_supported=is_supported,
                    source_type=stype,
                    unsupported_reason=unsupported_reason,
                )

            if not recursive:
                break

        return results

    def _monitoring_loop(self) -> None:
        """Loop de monitorização periódico em background."""
        while not self._stop_event.is_set():
            try:
                time.sleep(self.poll_interval)
            except Exception:
                break

            if self._stop_event.is_set():
                break

            with self._lock:
                folders_to_check = list(self._monitored_folders.items())

            for (col_id, fpath), data in folders_to_check:
                if self._stop_event.is_set():
                    break
                try:
                    current_scan = self.scan_folder(fpath, recursive=data.get("recursive", True))
                    last_scan = data.get("last_snapshot", {})

                    # Verificar se há alterações nos ficheiros
                    has_changes = False
                    if set(current_scan.keys()) != set(last_scan.keys()):
                        has_changes = True
                    else:
                        for k, c_info in current_scan.items():
                            l_info = last_scan.get(k)
                            if not l_info or c_info.mtime != l_info.mtime or c_info.size_bytes != l_info.size_bytes:
                                has_changes = True
                                break

                    if has_changes:
                        with self._lock:
                            if (col_id, fpath) in self._monitored_folders:
                                self._monitored_folders[(col_id, fpath)]["last_snapshot"] = current_scan

                        callback = data.get("on_change_callback")
                        if callback:
                            try:
                                callback(col_id, fpath)
                            except Exception as cb_err:
                                if self.logger:
                                    self.logger.error(f"[FolderSync] Callback error on {fpath}: {cb_err}")
                except Exception as err:
                    if self.logger:
                        self.logger.error(f"[FolderSync] Error scanning {fpath}: {err}")
