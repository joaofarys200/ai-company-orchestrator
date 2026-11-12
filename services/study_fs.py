"""
Utilitários Partilhados de Segurança de Ficheiros, Identificadores e Persistência Atómica (Study Engine).

Fornece:
- Validação estrita de document_id, nomes de ficheiro e caminhos confinados (anti path traversal / symlink escape).
- Escrita atómica durável via ficheiro temporário único (`mkstemp`), `fsync` e `os.replace`.
- Leitura segura de JSON com preservação forense de ficheiros corrompidos (`.corrupt.<ts>.bak`).
"""

from __future__ import annotations

import copy
import json
import os
import re
import shutil
import tempfile
import time
import urllib.parse
from pathlib import Path
from typing import Any, Optional, Tuple, Type

from backend.logging_config import get_logger

logger = get_logger(__name__)

_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9._-]{0,127}$")
_WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}


def validate_safe_identifier(value: Any, *, label: str = "document_id") -> str:
    """
    Valida que um identificador (e.g. `document_id`, `session_id`) é seguro para uso
    em nomes de pastas ou ficheiros sem risco de path traversal.
    """
    if not isinstance(value, str):
        raise ValueError(f"SECURITY_VIOLATION: {label} inválido (tipo não suportado).")
    cleaned = value.strip()
    if (
        not cleaned
        or "\x00" in cleaned
        or "/" in cleaned
        or "\\" in cleaned
        or ":" in cleaned
        or ".." in cleaned
        or cleaned in (".", "..")
        or not _SAFE_ID_RE.fullmatch(cleaned)
    ):
        raise ValueError(f"SECURITY_VIOLATION: {label} inválido '{value}'.")
    return cleaned


def safe_document_id(document_id: Any) -> str:
    """Valida estritamente um `document_id`."""
    return validate_safe_identifier(document_id, label="document_id")


def safe_filename(filename: Any) -> str:
    """
    Valida um nome de ficheiro isolado (sem componentes de diretório, traversal, null bytes
    ou nomes reservados do sistema). Preserva espaços e acentuação legítimos.
    """
    if not isinstance(filename, str):
        raise ValueError("SECURITY_VIOLATION: Nome de ficheiro inválido.")
    cleaned = filename.strip()
    if (
        not cleaned
        or cleaned in (".", "..")
        or cleaned.startswith(".")
        or "\x00" in cleaned
        or "/" in cleaned
        or "\\" in cleaned
        or ":" in cleaned
        or ".." in cleaned
        or any(ord(ch) < 32 for ch in cleaned)
    ):
        raise ValueError(f"SECURITY_VIOLATION: Nome de ficheiro ilegal '{filename}'.")

    stem = Path(cleaned).stem.upper()
    if stem in _WINDOWS_RESERVED_NAMES:
        raise ValueError(f"SECURITY_VIOLATION: Nome de ficheiro reservado pelo sistema '{filename}'.")
    return cleaned


def resolve_confined_path(
    base_dir: Path | str,
    *parts: str | Path,
    reject_symlinks: bool = True,
) -> Path:
    """
    Resolve um caminho garantindo confinamento estrito dentro de `base_dir`
    e rejeitando componentes absolutos, '..' e symlinks que apontem para dentro/fora.
    """
    base_resolved = Path(base_dir).resolve(strict=False)
    current = base_resolved

    for raw_part in parts:
        part_str = str(raw_part)
        if not part_str or "\x00" in part_str or ":" in part_str:
            raise ValueError(f"SECURITY_VIOLATION: Componente de caminho inválido '{raw_part}'.")
        part_path = Path(part_str)
        if part_path.is_absolute():
            raise ValueError(f"SECURITY_VIOLATION: Caminho absoluto proibido dentro de base confinada: '{raw_part}'.")
        for seg in part_path.parts:
            if not seg or seg in (".", "..", "/", "\\") or ".." in seg:
                raise ValueError(f"SECURITY_VIOLATION: Path traversal detetado em '{raw_part}'.")
            current = current / seg
            if reject_symlinks and current.is_symlink():
                raise ValueError(f"SECURITY_VIOLATION: Symlink bloqueado no caminho '{current}'.")

    resolved = current.resolve(strict=False)
    if resolved != base_resolved and not resolved.is_relative_to(base_resolved):
        raise ValueError(f"SECURITY_VIOLATION: Caminho '{resolved}' escapa da diretoria confinada '{base_resolved}'.")
    if reject_symlinks and resolved.is_symlink():
        raise ValueError(f"SECURITY_VIOLATION: Symlink bloqueado no destino '{resolved}'.")
    return resolved


def resolve_confined_subpath(
    base_dir: Path | str,
    raw_subpath: str,
    *,
    reject_symlinks: bool = True,
) -> Path:
    """
    Decodifica URL de forma segura e resolve um subcaminho relativo dentro de `base_dir`,
    rejeitando path traversal (incluindo `%2e%2e`, barras invertidas, drives ou symlinks).
    """
    if not isinstance(raw_subpath, str):
        raise ValueError("SECURITY_VIOLATION: Subcaminho inválido.")
    decoded = urllib.parse.unquote(urllib.parse.unquote(raw_subpath))
    if "\x00" in decoded or ":" in decoded:
        raise ValueError("SECURITY_VIOLATION: Caracteres ilegais no subcaminho.")
    normalized = decoded.replace("\\", "/")
    if not normalized or normalized.startswith("/"):
        raise ValueError("SECURITY_VIOLATION: Caminho absoluto proibido no subcaminho.")
    segments = [seg for seg in normalized.split("/") if seg != ""]
    if not segments or any(seg in (".", "..") or ".." in seg for seg in segments):
        raise ValueError("SECURITY_VIOLATION: Traversal detetado no subcaminho.")
    return resolve_confined_path(base_dir, *segments, reject_symlinks=reject_symlinks)


def is_path_within_roots(candidate: Path | str, roots: Tuple[Path | str, ...] | list[Path | str]) -> bool:
    """Verifica de forma canónica se `candidate` reside dentro de alguma das raízes permitidas (sem symlinks)."""
    try:
        cand_path = Path(candidate)
        if cand_path.is_symlink():
            return False
        resolved_cand = cand_path.resolve(strict=False)
        for root in roots:
            if not root:
                continue
            resolved_root = Path(root).resolve(strict=False)
            if resolved_cand == resolved_root or resolved_cand.is_relative_to(resolved_root):
                return True
    except Exception:
        return False
    return False


def _run_with_sharing_retry(fn: Any, *, attempts: int = 10, base_delay: float = 0.004) -> Any:
    """Repete brevemente operações sujeitas a lock transitório WinError 5/32 no Windows."""
    for attempt in range(attempts):
        try:
            return fn()
        except PermissionError:
            if os.name != "nt" or attempt + 1 >= attempts:
                raise
            time.sleep(base_delay * (attempt + 1))


def atomic_write_bytes(path: Path | str, data: bytes) -> None:
    """Escreve bytes atomicamente com ficheiro temporário único, `flush`, `fsync` e `os.replace`."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(target.parent),
        prefix=f".{target.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            try:
                os.fsync(handle.fileno())
            except OSError:
                pass
        _run_with_sharing_retry(lambda: os.replace(tmp_name, target))
    except Exception:
        try:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
        except OSError:
            pass
        raise


def atomic_write_text(path: Path | str, content: str, *, encoding: str = "utf-8") -> None:
    """Escreve texto atomicamente."""
    atomic_write_bytes(path, content.encode(encoding))


def atomic_write_json(path: Path | str, payload: Any, *, indent: int = 2) -> None:
    """Serializa e persiste JSON atomicamente com `fsync` e `os.replace`."""
    serialized = json.dumps(payload, indent=indent, ensure_ascii=False)
    atomic_write_text(path, serialized, encoding="utf-8")


def backup_corrupt_file(path: Path | str) -> Optional[Path]:
    """
    Preserva um ficheiro corrompido movendo-o para `<nome>.corrupt.<timestamp>.bak`
    antes de qualquer fallback ou reescrita.
    """
    src = Path(path)
    if not src.exists():
        return None
    ts = int(time.time())
    suffix_idx = 0
    while True:
        extra = f".{suffix_idx}" if suffix_idx else ""
        bak = src.with_name(f"{src.name}.corrupt.{ts}.{os.getpid()}{extra}.bak")
        if not bak.exists():
            break
        suffix_idx += 1

    try:
        _run_with_sharing_retry(lambda: os.replace(src, bak))
    except OSError:
        try:
            shutil.copy2(src, bak)
        except OSError as exc:
            logger.error(f"[StudyFS] Falha ao preservar cópia de segurança de {src}: {exc}")
            return None

    logger.error(
        f"[StudyFS] Ficheiro corrompido preservado em {bak} para evitar perda silenciosa de dados ({src})."
    )
    return bak


def read_json_safe(
    path: Path | str,
    *,
    default: Any = None,
    expected_type: Optional[Type[Any]] = None,
    backup_on_corrupt: bool = True,
) -> Tuple[Any, bool]:
    """
    Lê e valida um ficheiro JSON.
    Retorna `(dados, estava_corrompido)`. Em caso de JSON inválido ou tipo inesperado,
    preserva o ficheiro original via `.corrupt.*.bak` se `backup_on_corrupt=True`.
    """
    target = Path(path)
    if not target.exists():
        return (copy.deepcopy(default), False)

    try:
        raw_text = _run_with_sharing_retry(lambda: target.read_text(encoding="utf-8"))
        if not raw_text.strip():
            raise ValueError("Ficheiro JSON vazio")
        parsed = json.loads(raw_text)
        if expected_type is not None and not isinstance(parsed, expected_type):
            raise TypeError(f"Esperado {expected_type.__name__}, recebido {type(parsed).__name__}")
        return (parsed, False)
    except Exception as exc:
        logger.error(f"[StudyFS] Erro ao ler JSON em {target}: {exc}")
        if backup_on_corrupt:
            backup_corrupt_file(target)
        return (copy.deepcopy(default), True)

