"""
JARVIS OS — Phase 15.3: Independent Correctness Oracle (ReferenceConflictEngine & ReferenceMergeEngine)

Provides unoptimized, simple, deterministic ground truth implementations of conflict detection,
arbitration, and code merging for multi-agent collaboration (Fase 15.3 Secções 3, 4, 10).

Guarantees:
- O(N^2) exhaustive pairwise comparison without indexes or pruning caches.
- false_negatives == 0 invariant verification against optimized engines.
- Strict security & economic safeguards enforcement.
"""

from __future__ import annotations

import ast
import difflib
import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Sequence

from backend.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class ReferenceConflict:
    conflict_type: str
    proposal_ids: list[str]
    file_path: str
    details: str
    severity: str = "HIGH"


@dataclass
class ReferenceConflictResult:
    conflicts: list[ReferenceConflict] = field(default_factory=list)
    conflict_types: set[str] = field(default_factory=set)
    affected_proposals: set[str] = field(default_factory=set)
    accepted_proposals: list[str] = field(default_factory=list)
    rejected_proposals: list[str] = field(default_factory=list)
    arbitration_winner: str | None = None
    rationale: str = ""


@dataclass
class ReferenceMergeResult:
    success: bool
    merged_content: str
    merged_files: list[str] = field(default_factory=list)
    conflict_reason: str = ""
    structural_validity: bool = True


class ReferenceConflictEngine:
    """
    Independent reference implementation for multi-agent conflict detection and arbitration.
    Characteristics:
    - Simple
    - Slow
    - Deterministic
    - No optimizations
    - No index reuse
    Exclusively used as an independent ground truth oracle to ensure zero false negatives.
    """

    @classmethod
    def extract_symbols_full(cls, code: str, ext: str = ".py") -> set[str]:
        """Extracts symbols using exhaustive unoptimized parsing."""
        symbols: set[str] = set()
        if not code.strip():
            return symbols

        if ext == ".py":
            try:
                tree = ast.parse(code)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        symbols.add(node.name)
            except Exception:
                pass
        else:
            # JS / TS regex extraction
            for match in re.finditer(r"(?:function|class|const|let|var)\s+([A-Za-z0-9_$]+)", code):
                symbols.add(match.group(1))
        return symbols

    @classmethod
    def evaluate_proposals(
        cls,
        proposals: list[Any],
        architecture_context: dict[str, Any] | None = None,
        is_financial_task: bool = False,
    ) -> ReferenceConflictResult:
        """
        Performs exhaustive unoptimized pairwise conflict evaluation across all proposals.
        """
        conflicts: list[ReferenceConflict] = []
        affected: set[str] = set()
        conflict_types: set[str] = set()

        n = len(proposals)
        for i in range(n):
            p1 = proposals[i]
            id1 = getattr(p1, "proposal_id", f"p_{i}")
            files1 = set(getattr(p1, "affected_files", []) or [])
            if hasattr(p1, "file_path") and p1.file_path:
                files1.add(p1.file_path)
            content_map1 = getattr(p1, "content_by_file", {}) or {}
            files1.update(content_map1.keys())

            syms1 = set(getattr(p1, "ast_symbols", []) or getattr(p1, "affected_symbols", []) or [])
            desc1 = str(getattr(p1, "description", "") or getattr(p1, "rationale", "")).lower()
            meta1 = getattr(p1, "metadata", {}) or {}
            ev1 = getattr(p1, "evidence", {}) or {}

            for j in range(i + 1, n):
                p2 = proposals[j]
                id2 = getattr(p2, "proposal_id", f"p_{j}")
                files2 = set(getattr(p2, "affected_files", []) or [])
                if hasattr(p2, "file_path") and p2.file_path:
                    files2.add(p2.file_path)
                content_map2 = getattr(p2, "content_by_file", {}) or {}
                files2.update(content_map2.keys())

                syms2 = set(getattr(p2, "ast_symbols", []) or getattr(p2, "affected_symbols", []) or [])
                desc2 = str(getattr(p2, "description", "") or getattr(p2, "rationale", "")).lower()
                meta2 = getattr(p2, "metadata", {}) or {}
                ev2 = getattr(p2, "evidence", {}) or {}

                common_files = files1.intersection(files2)
                for f in common_files:
                    # 1. File & Symbol overlap
                    # If symbols are not explicitly annotated, exhaustively extract them from content
                    c1 = content_map1.get(f, getattr(p1, "proposed_content", ""))
                    c2 = content_map2.get(f, getattr(p2, "proposed_content", ""))
                    ext = os.path.splitext(f)[1].lower() or ".py"

                    s1 = syms1.union(cls.extract_symbols_full(c1, ext))
                    s2 = syms2.union(cls.extract_symbols_full(c2, ext))
                    common_syms = s1.intersection(s2)

                    if common_syms:
                        conf = ReferenceConflict(
                            conflict_type="AST_SYMBOL_OVERLAP",
                            proposal_ids=[id1, id2],
                            file_path=f,
                            details=f"Symbol overlap on {sorted(common_syms)} in {f}",
                        )
                        conflicts.append(conf)
                        affected.update([id1, id2])
                        conflict_types.add("AST_SYMBOL_OVERLAP")
                    elif c1 != c2 and (c1 and c2):
                        conf = ReferenceConflict(
                            conflict_type="FILE_OVERLAP",
                            proposal_ids=[id1, id2],
                            file_path=f,
                            details=f"Conflicting content modification on file {f}",
                        )
                        conflicts.append(conf)
                        affected.update([id1, id2])
                        conflict_types.add("FILE_OVERLAP")

                # 2. Contract conflict (routes / parameters)
                routes1 = meta1.get("routes", meta1.get("endpoints", []))
                routes2 = meta2.get("routes", meta2.get("endpoints", []))
                params1 = meta1.get("parameters", meta1.get("query_params", {}))
                params2 = meta2.get("parameters", meta2.get("query_params", {}))

                if routes1 and routes2:
                    if set(routes1) != set(routes2) or (params1 and params2 and params1 != params2):
                        conf = ReferenceConflict(
                            conflict_type="CONTRACT_CONFLICT",
                            proposal_ids=[id1, id2],
                            file_path="api/contract",
                            details=f"Divergent endpoints/parameters: {routes1} vs {routes2}",
                        )
                        conflicts.append(conf)
                        affected.update([id1, id2])
                        conflict_types.add("CONTRACT_CONFLICT")

                # 3. Architectural conflict (e.g. REST vs GraphQL)
                arch1 = meta1.get("architecture", meta1.get("pattern", ""))
                arch2 = meta2.get("architecture", meta2.get("pattern", ""))
                if arch1 and arch2 and arch1.lower() != arch2.lower():
                    conf = ReferenceConflict(
                        conflict_type="ARCHITECTURAL_MISMATCH",
                        proposal_ids=[id1, id2],
                        file_path="architecture",
                        details=f"Architectural pattern divergence: {arch1} vs {arch2}",
                    )
                    conflicts.append(conf)
                    affected.update([id1, id2])
                    conflict_types.add("ARCHITECTURAL_MISMATCH")

                # 4. Test conflict
                t1 = ev1.get("test_results", {})
                t2 = ev2.get("test_results", {})
                if t1 and t2:
                    t1_passed = t1.get("passed", 0) > 0 and t1.get("failed", 0) == 0
                    t2_passed = t2.get("passed", 0) > 0 and t2.get("failed", 0) == 0
                    if t1_passed != t2_passed:
                        conf = ReferenceConflict(
                            conflict_type="TEST_VERDICT_DIVERGENCE",
                            proposal_ids=[id1, id2],
                            file_path="tests",
                            details="Contradictory test execution outcomes",
                        )
                        conflicts.append(conf)
                        affected.update([id1, id2])
                        conflict_types.add("TEST_VERDICT_DIVERGENCE")

                # 5. Semantic / Security conflict
                sec1 = any(k in desc1 for k in ("security", "sandbox", "root", "unconfined"))
                sec2 = any(k in desc2 for k in ("security", "sandbox", "root", "unconfined"))
                if sec1 and sec2 and ("unconfined" in desc1 or "root" in desc1) != ("unconfined" in desc2 or "root" in desc2):
                    conf = ReferenceConflict(
                        conflict_type="SEMANTIC_CONFLICT",
                        proposal_ids=[id1, id2],
                        file_path="security",
                        details="Conflicting security boundary definitions",
                    )
                    conflicts.append(conf)
                    affected.update([id1, id2])
                    conflict_types.add("SEMANTIC_CONFLICT")

                # 6. Requirement ambiguity
                req1 = meta1.get("requirement_interpretation", "")
                req2 = meta2.get("requirement_interpretation", "")
                if req1 and req2 and req1.lower() != req2.lower():
                    conf = ReferenceConflict(
                        conflict_type="REQUIREMENT_AMBIGUITY",
                        proposal_ids=[id1, id2],
                        file_path="requirements",
                        details=f"Divergent requirement interpretations: {req1} vs {req2}",
                    )
                    conflicts.append(conf)
                    affected.update([id1, id2])
                    conflict_types.add("REQUIREMENT_AMBIGUITY")

        # Deterministic Arbitration in Reference Engine
        scored: list[tuple[float, str, Any]] = []
        for p in proposals:
            pid = getattr(p, "proposal_id", "")
            agent_id = getattr(p, "agent_id", "").upper()
            role = getattr(p, "role", "").upper()
            desc = str(getattr(p, "description", "") or getattr(p, "rationale", "")).lower()

            # Security invariant: non-coding / untrusted cannot mutate code
            if ("RESEARCH" in agent_id or "RESEARCH" in role) and hasattr(p, "proposed_content") and p.proposed_content:
                score = -1000000.0  # blocked by security gate
                scored.append((score, pid, p))
                continue

            # Economic safeguard invariant: financial tasks cannot bypass verification
            if is_financial_task and ("skip verification" in desc or "bypass approval" in desc):
                score = -1000000.0  # blocked by economic gate
                scored.append((score, pid, p))
                continue

            ev = getattr(p, "evidence", {}) or {}
            score = 0.0
            if ev.get("hard_validation", {}).get("passed", False):
                score += 1000.0
            tr = ev.get("test_results", {})
            if tr.get("passed", 0) > 0 and tr.get("failed", 0) == 0:
                score += 500.0 + tr.get("passed", 0) * 10.0
            if ev.get("build_status", {}).get("success", False):
                score += 300.0
            if ev.get("runtime_logs", {}).get("clean", False):
                score += 200.0
            if ev.get("browser_validation", {}).get("verified", False):
                score += 150.0
            if ev.get("contract_validation", {}).get("compatible", False):
                score += 100.0
            if ev.get("architectural_check", {}).get("aligned", False):
                score += 80.0

            conf = float(getattr(p, "confidence_score", 0.5) or 0.5)
            score += conf * 10.0
            score += min(len(str(getattr(p, "rationale", "") or "")), 100) * 0.01

            scored.append((score, pid, p))

        # Sort descending by score, ascending by pid for deterministic tie-breaking
        scored.sort(key=lambda item: (-item[0], item[1]))

        winner_id = scored[0][1] if scored and scored[0][0] > -500000.0 else None
        accepted = [winner_id] if winner_id else []
        rejected = [item[1] for item in scored if item[1] != winner_id]

        return ReferenceConflictResult(
            conflicts=conflicts,
            conflict_types=conflict_types,
            affected_proposals=affected,
            accepted_proposals=accepted,
            rejected_proposals=rejected,
            arbitration_winner=winner_id,
            rationale=f"Reference arbitration selected {winner_id} with score {scored[0][0] if scored else 0.0}",
        )


class ReferenceMergeEngine:
    """
    Independent reference implementation for code merge correctness validation.
    Characteristics:
    - Simple
    - Slow
    - Deterministic
    - No optimizations
    - No index reuse
    Performs unoptimized character/line range overlap checks and standard 3-way sequence merging.
    """

    @classmethod
    def extract_line_ranges(cls, base_text: str, modified_text: str) -> list[tuple[int, int]]:
        """Extracts modified line ranges [start_line, end_line] relative to base_text."""
        base_lines = base_text.splitlines(keepends=True)
        mod_lines = modified_text.splitlines(keepends=True)

        matcher = difflib.SequenceMatcher(None, base_lines, mod_lines)
        modified_ranges: list[tuple[int, int]] = []
        for tag, alo, ahi, blo, bhi in matcher.get_opcodes():
            if tag in ("replace", "delete", "insert"):
                modified_ranges.append((alo, ahi))
        return modified_ranges

    @classmethod
    def merge_patches(
        cls,
        file_path: str,
        base_content: str,
        content_a: str,
        content_b: str,
    ) -> ReferenceMergeResult:
        """
        Unoptimized reference 3-way merge:
        1. Checks line range overlaps between A and B.
        2. If ranges overlap -> returns conflict immediately (no blind merge).
        3. If disjoint -> merges non-overlapping blocks in order.
        4. Validates structural syntax of final output.
        """
        if content_a == base_content:
            return ReferenceMergeResult(
                success=True,
                merged_content=content_b,
                merged_files=[file_path],
                structural_validity=cls._validate_syntax(file_path, content_b),
            )
        if content_b == base_content:
            return ReferenceMergeResult(
                success=True,
                merged_content=content_a,
                merged_files=[file_path],
                structural_validity=cls._validate_syntax(file_path, content_a),
            )
        if content_a == content_b:
            return ReferenceMergeResult(
                success=True,
                merged_content=content_a,
                merged_files=[file_path],
                structural_validity=cls._validate_syntax(file_path, content_a),
            )

        ranges_a = cls.extract_line_ranges(base_content, content_a)
        ranges_b = cls.extract_line_ranges(base_content, content_b)

        # Check overlap
        for s_a, e_a in ranges_a:
            for s_b, e_b in ranges_b:
                if max(s_a, s_b) < min(e_a, e_b) or (s_a == s_b and e_a == e_b):
                    return ReferenceMergeResult(
                        success=False,
                        merged_content="",
                        merged_files=[],
                        conflict_reason=f"OVERLAPPING_EDIT_CONFLICT in range [{s_a}:{e_a}] vs [{s_b}:{e_b}]",
                        structural_validity=False,
                    )

        # Disjoint edits: perform standard 3-way line merge
        base_lines = base_content.splitlines(keepends=True)
        lines_a = content_a.splitlines(keepends=True)
        lines_b = content_b.splitlines(keepends=True)

        matcher_a = difflib.SequenceMatcher(None, base_lines, lines_a)
        matcher_b = difflib.SequenceMatcher(None, base_lines, lines_b)

        ops_a = [op for op in matcher_a.get_opcodes() if op[0] != "equal"]
        ops_b = [op for op in matcher_b.get_opcodes() if op[0] != "equal"]

        all_ops: list[tuple[int, int, str, list[str]]] = []
        for tag, alo, ahi, blo, bhi in ops_a:
            all_ops.append((alo, ahi, "A", lines_a[blo:bhi]))
        for tag, alo, ahi, blo, bhi in ops_b:
            all_ops.append((alo, ahi, "B", lines_b[blo:bhi]))

        all_ops.sort(key=lambda op: op[0])

        merged_lines: list[str] = []
        curr = 0
        for alo, ahi, origin, new_chunk in all_ops:
            if alo > curr:
                merged_lines.extend(base_lines[curr:alo])
            merged_lines.extend(new_chunk)
            curr = max(curr, ahi)
        if curr < len(base_lines):
            merged_lines.extend(base_lines[curr:])

        merged_text = "".join(merged_lines)
        valid = cls._validate_syntax(file_path, merged_text)

        return ReferenceMergeResult(
            success=valid,
            merged_content=merged_text if valid else "",
            merged_files=[file_path] if valid else [],
            conflict_reason="" if valid else "SYNTAX_ERROR_IN_REFERENCE_MERGE",
            structural_validity=valid,
        )

    @classmethod
    def _validate_syntax(cls, file_path: str, code: str) -> bool:
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".py":
            try:
                ast.parse(code)
                return True
            except SyntaxError:
                return False
        # JS / TS basic delimiter balance check
        open_b = code.count("{")
        close_b = code.count("}")
        return open_b == close_b


class MergeCorrectnessComparator:
    """
    Compares Optimized Engine vs Reference Engine outputs (Fase 15.3 Secção 4).
    Enforces false_negatives == 0 invariant.
    """

    @classmethod
    def verify_no_false_negatives(
        cls,
        reference_conflicts: ReferenceConflictResult,
        optimized_conflicts: Any,
    ) -> tuple[bool, str]:
        """
        Verifies that optimized engine did NOT miss any conflict detected by reference engine.
        """
        ref_affected = reference_conflicts.affected_proposals

        opt_conflicts_list = getattr(optimized_conflicts, "conflicts", [])
        if isinstance(optimized_conflicts, list):
            opt_conflicts_list = optimized_conflicts

        opt_affected: set[str] = set()
        for c in opt_conflicts_list:
            if hasattr(c, "proposals_involved"):
                opt_affected.update(c.proposals_involved)
            elif hasattr(c, "proposal_ids"):
                opt_affected.update(c.proposal_ids)
            elif isinstance(c, dict):
                opt_affected.update(c.get("proposals_involved", c.get("proposal_ids", [])))

        # Check false negatives
        missed = ref_affected.difference(opt_affected)
        if missed:
            return False, f"FALSE_NEGATIVE_DETECTED: Optimized engine missed conflicts on proposals {sorted(missed)}"

        return True, "ZERO_FALSE_NEGATIVES_VERIFIED"
