"""
JARVIS OS — Phase 62: Continuous Verification & Autonomous Regression Governance
Module: change_detection.py
Deterministic ChangeSet Detection supporting Git, Runtime Missions, Repair Results,
Autonomous Modifications, and Workspace file changes.
"""

from __future__ import annotations

import ast
import hashlib
import os
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from .models import ChangeItem, ChangeSet, ChangeSource, ChangeType


class ChangeDetector:
    """
    Detects deterministic changes across multiple sources:
    - Git diffs
    - Runtime mission steps
    - Repair synthesis results
    - Autonomous agent actions
    - Workspace file snapshots
    """

    def __init__(self, workspace_root: Optional[str] = None) -> None:
        self.workspace_root = workspace_root or os.getcwd()
        self._logical_clock: int = 0

    def _next_logical_timestamp(self) -> int:
        self._logical_clock += 1
        return self._logical_clock

    def _hash_content(self, content: str) -> str:
        if not content:
            return ""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _extract_python_symbols(self, code: str) -> Dict[str, str]:
        """Extract top-level functions and classes with their hashed definitions."""
        symbols: Dict[str, str] = {}
        if not code:
            return symbols
        try:
            tree = ast.parse(code)
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    sym_code = ast.get_source_segment(code, node) or node.name
                    symbols[f"func:{node.name}"] = self._hash_content(sym_code)
                elif isinstance(node, ast.ClassDef):
                    sym_code = ast.get_source_segment(code, node) or node.name
                    symbols[f"class:{node.name}"] = self._hash_content(sym_code)
                    for item in node.body:
                        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            method_code = ast.get_source_segment(code, item) or item.name
                            symbols[f"class:{node.name}::{item.name}"] = self._hash_content(method_code)
        except Exception:
            # Fallback if unparsable
            pass
        return symbols

    def detect_from_file_pair(
        self,
        file_path: str,
        content_before: Optional[str],
        content_after: Optional[str],
        source: ChangeSource = ChangeSource.WORKSPACE_MODIFICATION,
        diff_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[ChangeItem]:
        """Generate fine-grained ChangeItems for a single file transition."""
        items: List[ChangeItem] = []
        meta = diff_metadata or {}
        l_ts = self._next_logical_timestamp()

        # Handle File Creation
        if content_before is None and content_after is not None:
            after_hash = self._hash_content(content_after)
            items.append(
                ChangeItem(
                    file_path=file_path,
                    symbol_id=None,
                    change_type=ChangeType.CREATED,
                    before_hash="",
                    after_hash=after_hash,
                    diff_metadata={**meta, "lines_added": len(content_after.splitlines())},
                    source=source,
                    logical_timestamp=l_ts,
                    confidence=1.0,
                )
            )
            # Symbol additions
            after_syms = self._extract_python_symbols(content_after)
            for sym, s_hash in after_syms.items():
                items.append(
                    ChangeItem(
                        file_path=file_path,
                        symbol_id=sym,
                        change_type=ChangeType.SYMBOL_ADDED,
                        before_hash="",
                        after_hash=s_hash,
                        diff_metadata={"symbol": sym},
                        source=source,
                        logical_timestamp=l_ts,
                        confidence=1.0,
                    )
                )
            return items

        # Handle File Deletion
        if content_before is not None and content_after is None:
            before_hash = self._hash_content(content_before)
            items.append(
                ChangeItem(
                    file_path=file_path,
                    symbol_id=None,
                    change_type=ChangeType.DELETED,
                    before_hash=before_hash,
                    after_hash="",
                    diff_metadata={**meta, "lines_deleted": len(content_before.splitlines())},
                    source=source,
                    logical_timestamp=l_ts,
                    confidence=1.0,
                )
            )
            before_syms = self._extract_python_symbols(content_before)
            for sym, s_hash in before_syms.items():
                items.append(
                    ChangeItem(
                        file_path=file_path,
                        symbol_id=sym,
                        change_type=ChangeType.SYMBOL_REMOVED,
                        before_hash=s_hash,
                        after_hash="",
                        diff_metadata={"symbol": sym},
                        source=source,
                        logical_timestamp=l_ts,
                        confidence=1.0,
                    )
                )
            return items

        # Both present: check modification
        before_hash = self._hash_content(content_before or "")
        after_hash = self._hash_content(content_after or "")

        if before_hash == after_hash:
            return items  # Identical content, no change

        # Determine primary file change type
        is_test_file = "test" in file_path.lower()
        primary_type = ChangeType.TEST_CHANGED if is_test_file else ChangeType.MODIFIED

        items.append(
            ChangeItem(
                file_path=file_path,
                symbol_id=None,
                change_type=primary_type,
                before_hash=before_hash,
                after_hash=after_hash,
                diff_metadata=meta,
                source=source,
                logical_timestamp=l_ts,
                confidence=1.0,
            )
        )

        # Symbol level analysis
        before_syms = self._extract_python_symbols(content_before or "")
        after_syms = self._extract_python_symbols(content_after or "")

        all_sym_names = set(before_syms.keys()) | set(after_syms.keys())
        for sym in all_sym_names:
            b_sh = before_syms.get(sym)
            a_sh = after_syms.get(sym)
            if b_sh is None and a_sh is not None:
                items.append(
                    ChangeItem(
                        file_path=file_path,
                        symbol_id=sym,
                        change_type=ChangeType.SYMBOL_ADDED,
                        before_hash="",
                        after_hash=a_sh,
                        diff_metadata={"symbol": sym},
                        source=source,
                        logical_timestamp=l_ts,
                        confidence=1.0,
                    )
                )
            elif b_sh is not None and a_sh is None:
                items.append(
                    ChangeItem(
                        file_path=file_path,
                        symbol_id=sym,
                        change_type=ChangeType.SYMBOL_REMOVED,
                        before_hash=b_sh,
                        after_hash="",
                        diff_metadata={"symbol": sym},
                        source=source,
                        logical_timestamp=l_ts,
                        confidence=1.0,
                    )
                )
            elif b_sh != a_sh:
                # Symbol modified
                items.append(
                    ChangeItem(
                        file_path=file_path,
                        symbol_id=sym,
                        change_type=ChangeType.SYMBOL_CHANGED,
                        before_hash=b_sh or "",
                        after_hash=a_sh or "",
                        diff_metadata={"symbol": sym},
                        source=source,
                        logical_timestamp=l_ts,
                        confidence=1.0,
                    )
                )

        return items

    def detect_from_workspace(
        self,
        files_before: Dict[str, Optional[str]],
        files_after: Dict[str, Optional[str]],
        source: ChangeSource = ChangeSource.WORKSPACE_MODIFICATION,
    ) -> ChangeSet:
        """Produce a ChangeSet from before/after dictionary snapshots."""
        all_paths = set(files_before.keys()) | set(files_after.keys())
        items: List[ChangeItem] = []
        for path in sorted(all_paths):
            cb = files_before.get(path)
            ca = files_after.get(path)
            detected = self.detect_from_file_pair(path, cb, ca, source=source)
            items.extend(detected)

        c_set = ChangeSet(
            id=f"cs_{int(time.time() * 1000)}",
            changes=items,
            timestamp=time.time(),
            source=source.value if hasattr(source, "value") else str(source),
        )
        return c_set

    def detect_from_items(self, items: List[ChangeItem], source: str = "custom") -> ChangeSet:
        """Wrap explicit ChangeItem list into a deterministic ChangeSet."""
        return ChangeSet(
            id=f"cs_{int(time.time() * 1000)}",
            changes=items,
            timestamp=time.time(),
            source=source,
        )

    def detect_from_git(self, diff_text: str, source: ChangeSource = ChangeSource.GIT) -> ChangeSet:
        """Parse git diff text into ChangeItems."""
        items: List[ChangeItem] = []
        current_file: Optional[str] = None
        current_b_hash = ""
        current_a_hash = ""
        lines_added = 0
        lines_removed = 0
        l_ts = self._next_logical_timestamp()

        for line in diff_text.splitlines():
            if line.startswith("diff --git"):
                if current_file:
                    items.append(
                        ChangeItem(
                            file_path=current_file,
                            change_type=ChangeType.MODIFIED,
                            before_hash=current_b_hash,
                            after_hash=current_a_hash,
                            diff_metadata={"lines_added": lines_added, "lines_removed": lines_removed},
                            source=source,
                            logical_timestamp=l_ts,
                        )
                    )
                parts = line.split()
                if len(parts) >= 4:
                    current_file = parts[3].lstrip("b/")
                current_b_hash = ""
                current_a_hash = ""
                lines_added = 0
                lines_removed = 0
            elif line.startswith("index "):
                idx_parts = line.split()[1].split("..")
                if len(idx_parts) == 2:
                    current_b_hash, current_a_hash = idx_parts[0], idx_parts[1]
            elif line.startswith("+") and not line.startswith("+++"):
                lines_added += 1
            elif line.startswith("-") and not line.startswith("---"):
                lines_removed += 1

        if current_file:
            items.append(
                ChangeItem(
                    file_path=current_file,
                    change_type=ChangeType.MODIFIED,
                    before_hash=current_b_hash,
                    after_hash=current_a_hash,
                    diff_metadata={"lines_added": lines_added, "lines_removed": lines_removed},
                    source=source,
                    logical_timestamp=l_ts,
                )
            )

        return ChangeSet(
            id=f"cs_git_{int(time.time() * 1000)}",
            changes=items,
            timestamp=time.time(),
            source=source.value if hasattr(source, "value") else str(source),
        )

    def detect_from_mission(
        self,
        mission_id: str,
        modifications: List[Dict[str, Any]],
    ) -> ChangeSet:
        """Ingest changes from autonomous mission execution."""
        items: List[ChangeItem] = []
        l_ts = self._next_logical_timestamp()
        for mod in modifications:
            f_path = mod.get("file_path", "unknown")
            b_content = mod.get("before_content")
            a_content = mod.get("after_content")
            detected = self.detect_from_file_pair(
                f_path, b_content, a_content, source=ChangeSource.RUNTIME_MISSION, diff_metadata={"mission_id": mission_id}
            )
            items.extend(detected)

        return ChangeSet(
            id=f"cs_mission_{mission_id}_{int(time.time() * 1000)}",
            changes=items,
            timestamp=time.time(),
            source=ChangeSource.RUNTIME_MISSION.value,
        )

    def detect_from_repair(
        self,
        repair_id: str,
        patches: List[Dict[str, Any]],
    ) -> ChangeSet:
        """Ingest changes from repair synthesis."""
        items: List[ChangeItem] = []
        for patch in patches:
            f_path = patch.get("file_path", "unknown")
            b_c = patch.get("original")
            a_c = patch.get("patched")
            detected = self.detect_from_file_pair(
                f_path, b_c, a_c, source=ChangeSource.REPAIR_RESULT, diff_metadata={"repair_id": repair_id}
            )
            items.extend(detected)

        return ChangeSet(
            id=f"cs_repair_{repair_id}_{int(time.time() * 1000)}",
            changes=items,
            timestamp=time.time(),
            source=ChangeSource.REPAIR_RESULT.value,
        )
