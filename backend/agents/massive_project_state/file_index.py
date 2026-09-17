from __future__ import annotations

from typing import Dict, List, Optional, Set

from .index import BaseReverseIndex
from .models import FileRecord


class FileReverseIndex(BaseReverseIndex):
    """Reverse index mapping files to symbols, shards, and imports."""

    def __init__(self) -> None:
        super().__init__("FileReverseIndex")
        self._files: Dict[str, FileRecord] = {}
        self._shard_files: Dict[str, Set[str]] = {}
        self._symbol_to_file: Dict[str, str] = {}

    def add_file(self, file_rec: FileRecord) -> None:
        self._files[file_rec.file_path] = file_rec
        self._shard_files.setdefault(file_rec.shard_id, set()).add(file_rec.file_path)

        for sym in file_rec.symbols:
            self._symbol_to_file[sym] = file_rec.file_path

        self.bump_revision()

    def remove_file(self, file_path: str) -> bool:
        file_rec = self._files.pop(file_path, None)
        if not file_rec:
            return False

        if file_rec.shard_id in self._shard_files:
            self._shard_files[file_rec.shard_id].discard(file_path)

        for sym in file_rec.symbols:
            if self._symbol_to_file.get(sym) == file_path:
                del self._symbol_to_file[sym]

        self.bump_revision()
        return True

    def get_file(self, file_path: str) -> Optional[FileRecord]:
        return self._files.get(file_path)

    def get_files_by_shard(self, shard_id: str) -> List[str]:
        return sorted(list(self._shard_files.get(shard_id, set())))

    def get_file_for_symbol(self, symbol_id: str) -> Optional[str]:
        return self._symbol_to_file.get(symbol_id)

    def clear(self) -> None:
        self._files.clear()
        self._shard_files.clear()
        self._symbol_to_file.clear()
        self.bump_revision()

    def size(self) -> int:
        return len(self._files)
