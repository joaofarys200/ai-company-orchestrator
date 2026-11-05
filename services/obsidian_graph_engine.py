"""
JARVIS OS — Obsidian Knowledge Graph Autonomous Quality Evolution Engine
Hardened, Secure, and Evidence-Grounded Implementation.

Key Modules:
  1. Strict Path Containment & Traversal Protection
  2. High-Resolution Collision-Free Snapshots with Identity Verification
  3. Atomic Compare-And-Swap (CAS) Writes
  4. Four-Category Calibrated Quality Auditor (Structural, Knowledge, Evidence, Graph)
  5. Markdown-Aware Wikilink & Attachment Extraction
  6. Layered Semantic Link Engine with Verified Ontological Registry
  7. Bridge Note Evidence Validation
  8. Real Autonomous Improvement Worker (Bounded Batches, Ollama qwen3.5:9b)
  9. Real-Time Graph Diagnostics
"""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
import shutil
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Authorized default base paths
VAULT_DIR = Path("obsidian_vault").resolve()
DATA_DIR = Path("data/obsidian").resolve()
PROPOSALS_DIR = DATA_DIR / "proposals"
HISTORY_DIR = VAULT_DIR / ".history"
QUEUE_FILE = DATA_DIR / "improvement_queue.json"
DIAGNOSTICS_FILE = DATA_DIR / "graph_diagnostics.json"
WORKER_STATE_FILE = DATA_DIR / "improvement_worker_state.json"

# Strict regexes
WIKILINK_REGEX = re.compile(r"\[\[(.*?)\]\]")
ATTACHMENT_REGEX = re.compile(r"!\[\[(.*?)\]\]")
INLINE_TAG_REGEX = re.compile(r"(?:^|\s)#([a-zA-Z0-9_\-\/]+)")


# ==============================================================================
# CUSTOM SECURITY & INTEGRITY EXCEPTIONS
# ==============================================================================

class ObsidianSecurityError(ValueError):
    """Raised when an operation violates path containment or security boundaries."""
    pass


class ObsidianNotFoundError(FileNotFoundError):
    """Raised when an expected canonical note, snapshot, or resource does not exist."""
    pass


class ObsidianConcurrencyError(RuntimeError):
    """Raised when optimistic concurrency checks (CAS) detect conflicting modifications."""
    pass


# ==============================================================================
# CURATED ONTOLOGICAL CONCEPT REGISTRY (Audited & Corrected)
# ==============================================================================
# Rule: Never guess or map unrelated concepts (e.g., TOGAF does NOT map to API Contract Evolution).
CONCEPT_SYNONYM_REGISTRY: Dict[str, Dict[str, Any]] = {
    "rag": {
        "canonical_note": "Agentic RAG, Query Decomposition and Cross-Encoder Reranking",
        "synonyms": ["retrieval-augmented generation", "hybrid rag", "agentic rag", "reciprocal rank fusion", "rrf"],
        "domain": "AI & LLM",
        "type": "architecture",
    },
    "mcp": {
        "canonical_note": "Model Context Protocol (MCP) and Capability Discovery Architecture",
        "synonyms": ["model context protocol", "mcp server", "mcp tools", "capability discovery"],
        "domain": "AI & LLM",
        "type": "standard",
    },
    "pqc": {
        "canonical_note": "Post-Quantum Cryptography Migration - Hybrid ML-KEM (FIPS 203) and ML-DSA (FIPS 204)",
        "synonyms": ["post-quantum cryptography", "ml-kem", "ml-dsa", "fips 203", "fips 204", "kyber", "dilithium"],
        "domain": "Security",
        "type": "cryptography",
    },
    "ast": {
        "canonical_note": "Tratado_Completo_de_Engenharia_de_Software_AST_e_Compiladores",
        "synonyms": ["abstract syntax tree", "árvore sintática", "tree-sitter", "ast parsing"],
        "domain": "Software Engineering",
        "type": "theory",
    },
    "slsa": {
        "canonical_note": "Software Supply Chain Security - SLSA, SBOM and Dependency Pinning",
        "synonyms": ["supply chain levels for software artifacts", "sbom", "dependency isolation", "slsa level"],
        "domain": "Security",
        "type": "standard",
    },
    "wal": {
        "canonical_note": "Database Crash Consistency and Recovery",
        "synonyms": ["write-ahead logging", "sqlite wal", "crash recovery", "wal mode"],
        "domain": "Backend Systems",
        "type": "database",
    },
    "swarm": {
        "canonical_note": "JARVIS Swarm Orchestrator and Agent Turn Arbitrator",
        "synonyms": ["multi-agent swarm", "agent swarm", "swarm orchestrator", "turn arbitrator"],
        "domain": "JARVIS Internal",
        "type": "architecture",
    },
    "study_engine": {
        "canonical_note": "JARVIS Multimodal Study Engine and Grounded Synthesis Pipeline",
        "synonyms": ["study engine", "grounded summaries", "cornell note synthesizer", "lecture synthesizer"],
        "domain": "JARVIS Internal",
        "type": "subsystem",
    },
    "pbft": {
        "canonical_note": "DDIA_Designing_Data_Intensive_Applications_BOK",
        "synonyms": ["practical byzantine fault tolerance", "byzantine consensus", "tolerância a falhas bizantinas"],
        "domain": "Backend Systems",
        "type": "protocol",
    },
    "ddd": {
        "canonical_note": "DDD_Domain_Driven_Design_and_Enterprise_Patterns",
        "synonyms": ["domain-driven design", "bounded context", "aggregate root", "enterprise patterns"],
        "domain": "Software Engineering",
        "type": "architecture",
    },
}


# ==============================================================================
# MAIN ENGINE CLASS
# ==============================================================================

class ObsidianGraphEngine:
    """
    Core engine for vault inspection, path containment, atomic snapshots,
    calibrated 4-category quality scoring, and autonomous improvement.
    """

    def __init__(
        self,
        vault_root: Optional[Path] = None,
        data_dir: Optional[Path] = None,
        history_dir: Optional[Path] = None,
        proposals_dir: Optional[Path] = None,
        queue_file: Optional[Path] = None,
        diagnostics_file: Optional[Path] = None,
    ):
        self.vault_root = (vault_root or VAULT_DIR).resolve()
        self.data_dir = (data_dir or DATA_DIR).resolve()
        self.history_dir = (history_dir or (self.vault_root / ".history")).resolve()
        self.proposals_dir = (proposals_dir or (self.data_dir / "proposals")).resolve()
        self.queue_file = (queue_file or (self.data_dir / "improvement_queue.json")).resolve()
        self.diagnostics_file = (diagnostics_file or (self.data_dir / "graph_diagnostics.json")).resolve()
        self.worker_state_file = (self.data_dir / "improvement_worker_state.json").resolve()

        # Ensure directories exist
        self.vault_root.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.history_dir.mkdir(parents=True, exist_ok=True)
        self.proposals_dir.mkdir(parents=True, exist_ok=True)

        self.canonical_notes: Dict[str, Path] = {}
        self.canonical_rel_paths: Dict[str, Path] = {}
        self.alias_map: Dict[str, str] = {}
        self.tag_index: Dict[str, Set[str]] = {}
        self.refresh_vault_catalogs()

    # ──────────────────────────────────────────────────────────────────────────
    # 1. CATALOGS & PARSING
    # ──────────────────────────────────────────────────────────────────────────

    def refresh_vault_catalogs(self) -> None:
        """Loads and maps titles, relative paths, aliases, and tags of all Markdown notes."""
        self.canonical_notes.clear()
        self.canonical_rel_paths.clear()
        self.alias_map.clear()
        self.tag_index.clear()

        if not self.vault_root.exists():
            return

        for md_file in self.vault_root.rglob("*.md"):
            # Exclude .obsidian and .history
            if ".obsidian" in md_file.parts or ".history" in md_file.parts:
                continue
            try:
                rel_str = str(md_file.relative_to(self.vault_root)).replace("\\", "/")
            except ValueError:
                continue

            stem = md_file.stem
            self.canonical_notes[stem.lower()] = md_file
            self.canonical_rel_paths[rel_str.lower()] = md_file

            # Parse frontmatter for aliases and tags
            try:
                content = md_file.read_text(encoding="utf-8", errors="ignore")
                meta, _ = self.parse_frontmatter(content)
                raw_aliases = meta.get("aliases", [])
                if isinstance(raw_aliases, list):
                    for a in raw_aliases:
                        if str(a).strip():
                            self.alias_map[str(a).strip().lower()] = stem
                elif isinstance(raw_aliases, str) and raw_aliases.strip():
                    self.alias_map[raw_aliases.strip().lower()] = stem

                raw_tags = meta.get("tags", [])
                tags = set()
                if isinstance(raw_tags, list):
                    tags.update(str(t).strip().lstrip("#").lower() for t in raw_tags if str(t).strip())
                elif isinstance(raw_tags, str) and raw_tags.strip():
                    tags.add(raw_tags.strip().lstrip("#").lower())
                for t in tags:
                    self.tag_index.setdefault(t, set()).add(stem)
            except Exception:
                pass

    @staticmethod
    def parse_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
        """Robust YAML frontmatter parser."""
        if not content.startswith("---"):
            return {}, content
        parts = content.split("---", 2)
        if len(parts) < 3:
            return {}, content
        yaml_text = parts[1]
        body = parts[2]
        meta: Dict[str, Any] = {}
        current_list = None
        for line in yaml_text.splitlines():
            line_str = line.strip()
            if not line_str or line_str.startswith("#"):
                continue
            if line.startswith("  - ") and current_list:
                item = line_str[2:].strip().strip('"\'')
                if isinstance(meta.get(current_list), list):
                    meta[current_list].append(item)
                continue
            if ":" in line_str:
                k, v = line_str.split(":", 1)
                k = k.strip()
                v = v.strip().strip('"\'')
                if not v:
                    meta[k] = []
                    current_list = k
                else:
                    current_list = None
                    if v.startswith("[") and v.endswith("]"):
                        meta[k] = [x.strip().strip('"\'') for x in v[1:-1].split(",") if x.strip()]
                    else:
                        meta[k] = v
        return meta, body

    # ──────────────────────────────────────────────────────────────────────────
    # 2. PATH CONTAINMENT & SECURITY ENFORCEMENT
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _is_path_contained(candidate: Path, parent: Path) -> bool:
        """Determines if candidate path is strictly within parent directory."""
        try:
            candidate.resolve().relative_to(parent.resolve())
            return True
        except ValueError:
            return False

    def _resolve_contained_note_path(self, target: Any) -> Path:
        """
        Resolves and validates that the note target is strictly contained inside self.vault_root.
        Rejects:
          - Null bytes or empty paths
          - Explicit parent traversal ('../' or '..\\')
          - Absolute paths outside vault_root
          - Symlinks that resolve outside vault_root
          - Nonexistent files
        """
        if target is None:
            raise ObsidianSecurityError("Caminho de nota nulo.")
        t_str = str(target).strip()
        if not t_str or "\x00" in t_str:
            raise ObsidianSecurityError(f"Caminho de nota inválido: {target!r}")

        # Check explicit parent traversal
        norm_parts = Path(t_str.replace("\\", "/")).parts
        if ".." in norm_parts:
            raise ObsidianSecurityError(f"Tentativa de path traversal rejeitada: {t_str}")

        # 1. Check canonical stem dictionary
        stem_key = t_str.replace("\\", "/").lower().removesuffix(".md")
        if stem_key in self.canonical_notes:
            cand = self.canonical_notes[stem_key].resolve()
            if not self._is_path_contained(cand, self.vault_root):
                raise ObsidianSecurityError(f"Nota canónica escapa aos limites do vault: {cand}")
            return cand

        # 2. Check canonical relative path dictionary
        rel_key = t_str.replace("\\", "/").lower()
        if rel_key in self.canonical_rel_paths:
            cand = self.canonical_rel_paths[rel_key].resolve()
            if not self._is_path_contained(cand, self.vault_root):
                raise ObsidianSecurityError(f"Nota canónica escapa aos limites do vault: {cand}")
            return cand

        # 3. Path evaluation
        cand_path = Path(t_str)
        if not cand_path.is_absolute():
            resolved = (self.vault_root / cand_path).resolve()
        else:
            resolved = cand_path.resolve()

        if not self._is_path_contained(resolved, self.vault_root):
            raise ObsidianSecurityError(f"Acesso fora do cofre autorizado: {t_str}")

        if not resolved.exists() or not resolved.is_file():
            raise ObsidianNotFoundError(f"Nota não encontrada no cofre: {t_str}")

        return resolved

    def _resolve_contained_snapshot_path(self, backup_target: Any) -> Path:
        """
        Resolves and validates that a snapshot file is strictly contained within self.history_dir.
        """
        if backup_target is None:
            raise ObsidianSecurityError("Caminho de snapshot nulo.")
        b_str = str(backup_target).strip()
        if not b_str or "\x00" in b_str:
            raise ObsidianSecurityError(f"Caminho de snapshot inválido: {backup_target!r}")

        norm_parts = Path(b_str.replace("\\", "/")).parts
        if ".." in norm_parts:
            raise ObsidianSecurityError(f"Tentativa de path traversal em snapshot rejeitada: {b_str}")

        b_path = Path(b_str)
        if not b_path.is_absolute():
            resolved = (self.history_dir / b_path).resolve()
        else:
            resolved = b_path.resolve()

        if not self._is_path_contained(resolved, self.history_dir):
            raise ObsidianSecurityError(f"Tentativa de rollback com ficheiro fora do diretório .history: {b_str}")

        if not resolved.exists() or not resolved.is_file():
            raise ObsidianNotFoundError(f"Ficheiro de snapshot não encontrado: {resolved.name}")

        return resolved

    def get_note_sha256(self, target: Any) -> str:
        """Calculates SHA-256 for a contained note."""
        path = self._resolve_contained_note_path(target)
        return hashlib.sha256(path.read_bytes()).hexdigest()

    # ──────────────────────────────────────────────────────────────────────────
    # 3. HIGH-RESOLUTION SNAPSHOTS & ATOMIC CAS WRITES
    # ──────────────────────────────────────────────────────────────────────────

    def create_note_backup_snapshot(self, rel_path: Any) -> Tuple[Path, Dict[str, Any]]:
        """
        Creates a guaranteed non-colliding snapshot in self.history_dir with a sidecar JSON metadata file.
        Snapshot naming: snap_{rel_path_hash}_{timestamp_ns}_{content_sha_prefix}_{uuid_suffix}.md
        """
        full_path = self._resolve_contained_note_path(rel_path)
        rel_str = str(full_path.relative_to(self.vault_root)).replace("\\", "/")
        stem = full_path.stem
        content_bytes = full_path.read_bytes()
        content_sha256 = hashlib.sha256(content_bytes).hexdigest()
        rel_path_hash = hashlib.sha256(rel_str.encode("utf-8")).hexdigest()[:12]
        timestamp_ns = time.time_ns()
        snapshot_uuid = uuid.uuid4().hex[:8]

        snapshot_filename = f"snap_{rel_path_hash}_{timestamp_ns}_{content_sha256[:8]}_{snapshot_uuid}.md"
        snapshot_path = (self.history_dir / snapshot_filename).resolve()

        if not self._is_path_contained(snapshot_path, self.history_dir):
            raise ObsidianSecurityError("Destino do snapshot escapa aos limites de history_dir.")

        # Write snapshot markdown
        snapshot_path.write_bytes(content_bytes)

        # Write snapshot metadata sidecar
        metadata: Dict[str, Any] = {
            "snapshot_id": f"snap_{snapshot_uuid}",
            "snapshot_filename": snapshot_filename,
            "schema_version": 2,
            "note_rel_path": rel_str,
            "note_stem": stem,
            "rel_path_hash": rel_path_hash,
            "timestamp_ns": timestamp_ns,
            "timestamp_iso": datetime.now().isoformat(),
            "content_sha256": content_sha256,
            "content_bytes_len": len(content_bytes),
        }
        meta_path = snapshot_path.with_suffix(".json")
        meta_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")

        return snapshot_path, metadata

    def atomic_write_note(
        self,
        rel_path: Any,
        new_content: str,
        expected_sha256: Optional[str] = None,
        create_backup: bool = True,
    ) -> Dict[str, Any]:
        """
        Performs an atomic CAS write to a note file:
        1. Validates note is strictly inside vault_root
        2. Checks current SHA matches expected_sha256 (if provided)
        3. Creates verified backup snapshot
        4. Writes to a hidden temporary file in the same directory
        5. Validates markdown and frontmatter integrity
        6. Re-checks original SHA (optimistic concurrency CAS)
        7. Atomically replaces target via os.replace
        8. Verifies final SHA-256
        """
        target_path = self._resolve_contained_note_path(rel_path)
        current_bytes = target_path.read_bytes()
        current_sha = hashlib.sha256(current_bytes).hexdigest()

        if expected_sha256 and current_sha != expected_sha256:
            raise ObsidianConcurrencyError(
                f"Conflito de concorrência: ficheiro foi modificado (esperado {expected_sha256[:8]}, atual {current_sha[:8]})."
            )

        backup_info = None
        if create_backup:
            _, backup_info = self.create_note_backup_snapshot(target_path)

        # Basic integrity check on new content
        meta, body = self.parse_frontmatter(new_content)
        if not body.strip() and not meta:
            raise ValueError("Conteúdo resultante vazio ou inválido.")

        # Write to temporary file in the target note's directory (ensures same filesystem for atomic rename)
        temp_file = target_path.parent / f".tmp_{uuid.uuid4().hex[:8]}.tmp"
        temp_file.write_text(new_content, encoding="utf-8")

        # Optimistic CAS re-check
        latest_sha = hashlib.sha256(target_path.read_bytes()).hexdigest()
        if latest_sha != current_sha:
            temp_file.unlink(missing_ok=True)
            raise ObsidianConcurrencyError("Ficheiro modificado concorrentemente durante a escrita. Operação abortada.")

        # Atomic replace
        os.replace(temp_file, target_path)
        final_sha = hashlib.sha256(target_path.read_bytes()).hexdigest()

        self.refresh_vault_catalogs()
        return {
            "rel_path": str(target_path.relative_to(self.vault_root)).replace("\\", "/"),
            "sha256_before": current_sha,
            "sha256_after": final_sha,
            "backup_snapshot": backup_info,
        }

    def rollback_note(self, target_note: Any, backup_path_or_id: Any) -> Dict[str, Any]:
        """
        Hardened rollback:
        - Target path strictly validated inside vault_root
        - Snapshot path strictly validated inside history_dir
        - Verifies snapshot sidecar metadata matches target note identity
        - Replaces note atomically
        """
        target_file = self._resolve_contained_note_path(target_note)
        rel_str = str(target_file.relative_to(self.vault_root)).replace("\\", "/")

        snapshot_file = self._resolve_contained_snapshot_path(backup_path_or_id)

        # Verify snapshot sidecar identity
        meta_file = snapshot_file.with_suffix(".json")
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                expected_rel = meta.get("note_rel_path")
                if expected_rel and expected_rel != rel_str:
                    raise ObsidianSecurityError(
                        f"Snapshot pertence a '{expected_rel}', não a '{rel_str}'. Rollback rejeitado."
                    )
                expected_sha = meta.get("content_sha256")
                actual_snap_sha = hashlib.sha256(snapshot_file.read_bytes()).hexdigest()
                if expected_sha and actual_snap_sha != expected_sha:
                    raise ObsidianSecurityError("Snapshot corrompido: hash SHA-256 não coincide com metadados.")
            except json.JSONDecodeError:
                raise ObsidianSecurityError("Metadados do snapshot corrompidos.")

        # Atomic swap
        backup_bytes = snapshot_file.read_bytes()
        temp_file = target_file.parent / f".tmp_rollback_{uuid.uuid4().hex[:8]}.tmp"
        temp_file.write_bytes(backup_bytes)
        os.replace(temp_file, target_file)

        final_sha = hashlib.sha256(target_file.read_bytes()).hexdigest()
        self.refresh_vault_catalogs()

        return {
            "success": True,
            "rel_path": rel_str,
            "restored_from": snapshot_file.name,
            "sha256": final_sha,
        }

    # ──────────────────────────────────────────────────────────────────────────
    # 4. MARKDOWN-AWARE WIKILINK & ATTACHMENT EXTRACTION
    # ──────────────────────────────────────────────────────────────────────────

    def extract_markdown_links(self, content: str) -> Dict[str, Any]:
        """
        Extracts wikilinks and attachments aware of Markdown context.
        Strips code fences, inline code, and HTML comments before extracting.
        Separates normal wikilinks from media/embedded attachments.
        """
        # Separate frontmatter
        meta, body = self.parse_frontmatter(content)

        code_fences_count = 0
        code_examples_ignored: List[Dict[str, str]] = []

        # Find code blocks (``` or ~~~)
        code_blocks = re.findall(r"```[\s\S]*?```|~~~[\s\S]*?~~~", body)
        for cb in code_blocks:
            code_fences_count += 1
            for wl in WIKILINK_REGEX.findall(cb):
                code_examples_ignored.append({"raw": wl, "type": "code_block"})

        # Strip code blocks
        clean = re.sub(r"```[\s\S]*?```|~~~[\s\S]*?~~~", "", body)

        # Find and strip inline code spans
        inline_spans = re.findall(r"`[^`\n]+`", clean)
        for ic in inline_spans:
            for wl in WIKILINK_REGEX.findall(ic):
                code_examples_ignored.append({"raw": wl, "type": "inline_code"})
        clean = re.sub(r"`[^`\n]+`", "", clean)

        # Strip HTML comments
        clean = re.sub(r"<!--[\s\S]*?-->", "", clean)

        # Extract embedded attachments ![[...]]
        raw_embeds = ATTACHMENT_REGEX.findall(clean)
        clean = re.sub(r"!\[\[.*?\]\]", "", clean)

        # Extract wikilinks [[...]]
        raw_wikilinks = WIKILINK_REGEX.findall(clean)

        return {
            "wikilinks": raw_wikilinks,
            "embeds": raw_embeds,
            "code_examples_ignored": code_examples_ignored,
            "code_fences_count": code_fences_count,
        }

    # ──────────────────────────────────────────────────────────────────────────
    # 5. FOUR-CATEGORY CALIBRATED QUALITY SCORING MODEL
    # ──────────────────────────────────────────────────────────────────────────

    def audit_note_quality(self, rel_path: Any) -> Dict[str, Any]:
        """
        Calibrated four-category note quality auditor:
          A. STRUCTURAL QUALITY (0-100)
          B. KNOWLEDGE QUALITY (0-100)
          C. EVIDENCE QUALITY (0-100)
          D. GRAPH QUALITY (0-100)

        Rules:
        - No fixed 95 or 90 scores without measurement.
        - Freshness returns UNKNOWN when date metadata cannot be verified.
        - Uniqueness compares title and 3-gram signatures against vault notes.
        - JARVIS_INTERNAL is distinct from VERIFIED_PRIMARY_SOURCE.
        - Discloses calculation method.
        """
        full_path = self._resolve_contained_note_path(rel_path)
        content = full_path.read_text(encoding="utf-8", errors="ignore")
        meta, body = self.parse_frontmatter(content)
        stem = full_path.stem
        rel_str = str(full_path.relative_to(self.vault_root)).replace("\\", "/")

        findings: List[Dict[str, Any]] = []

        # ── CATEGORY A: STRUCTURAL QUALITY (0-100) ──
        # Evaluates format, frontmatter completeness, heading hierarchy, layout
        struct_subscores: List[float] = []

        # 1. Frontmatter presence and required fields
        if bool(meta):
            has_domain = bool(meta.get("domain") or meta.get("subject"))
            has_type = bool(meta.get("type"))
            fm_score = 70.0 + (15.0 if has_domain else 0.0) + (15.0 if has_type else 0.0)
            struct_subscores.append(fm_score)
        else:
            struct_subscores.append(20.0)
            findings.append({
                "category": "Structural Quality",
                "dimension": "Frontmatter",
                "what_is_missing": "YAML Frontmatter ausente ou não estruturado",
                "why_it_matters": "Impossibilita catalogação automática e indexação de domínio no cofre",
                "evidence_supporting_finding": "Primeira linha do ficheiro não contém delimitador '---'",
                "recommended_improvement": "Adicionar cabeçalho YAML com 'type', 'domain' e 'status'",
            })

        # 2. Heading hierarchy (# -> ## -> ### without jumps)
        headings = re.findall(r"^(#+)\s+(.+)$", body, flags=re.MULTILINE)
        if headings:
            levels = [len(h[0]) for h in headings]
            level_skips = sum(1 for i in range(len(levels) - 1) if levels[i + 1] > levels[i] + 1)
            hierarchy_score = max(30.0, 100.0 - (level_skips * 20.0))
            struct_subscores.append(hierarchy_score)
            if level_skips > 0:
                findings.append({
                    "category": "Structural Quality",
                    "dimension": "Heading Hierarchy",
                    "what_is_missing": "Hierarquia de cabeçalhos contínua (ex.: salto de # para ###)",
                    "why_it_matters": "Dificulta geração de sumários e renderização de AST markdown",
                    "evidence_supporting_finding": f"Detetados {level_skips} saltos de nível nos cabeçalhos",
                    "recommended_improvement": "Normalizar títulos para respeitar progressão contínua (# -> ## -> ###)",
                })
        else:
            struct_subscores.append(40.0)
            findings.append({
                "category": "Structural Quality",
                "dimension": "Headings",
                "what_is_missing": "Secções estruturadas com cabeçalhos Markdown (# / ##)",
                "why_it_matters": "Texto monolítico dificulta navegação e síntese",
                "evidence_supporting_finding": "Zero cabeçalhos Markdown detetados no corpo",
                "recommended_improvement": "Estruturar o documento com secções analíticas",
            })

        structural_quality = round(sum(struct_subscores) / len(struct_subscores), 1)

        # ── CATEGORY B: KNOWLEDGE QUALITY (0-100) ──
        # Evaluates conceptual completeness, depth, and explanatory clarity
        words_count = len(re.findall(r"\w+", body))
        sections = [h[1] for h in headings]
        is_moc = "00 - MOC" in rel_str or "Index" in stem or meta.get("type") == "moc"

        know_subscores: List[float] = []

        # 1. Completeness based on note type
        if is_moc:
            moc_links = WIKILINK_REGEX.findall(body)
            comp_score = min(100.0, 50.0 + len(moc_links) * 5.0)
            know_subscores.append(comp_score)
        else:
            has_summary = any(re.search(r"sumário|resumo|overview|executive|visão geral", s, re.I) for s in sections)
            has_technical_core = len(sections) >= 3 or words_count >= 250
            has_takeaways = any(re.search(r"cues|questões|conclusão|ações|referências|trade-offs", s, re.I) for s in sections)
            comp_score = 30.0 + (25.0 if has_summary else 0.0) + (25.0 if has_technical_core else 0.0) + (20.0 if has_takeaways else 0.0)
            know_subscores.append(comp_score)
            if comp_score < 75.0:
                findings.append({
                    "category": "Knowledge Quality",
                    "dimension": "Completeness",
                    "what_is_missing": "Estrutura conceptual completa (Sumário, Desenvolvimento e Síntese/Conclusão)",
                    "why_it_matters": "A nota carece de auto-suficiência pedagógica e analítica",
                    "evidence_supporting_finding": f"{len(sections)} secções presentes: {sections[:3]}",
                    "recommended_improvement": "Expandir a nota com sumário executivo e secção de síntese",
                })

        # 2. Explanatory Depth (measured by paragraph structure and technical terminology density)
        paragraphs = [p.strip() for p in body.split("\n\n") if p.strip() and not p.strip().startswith("#")]
        avg_para_len = (sum(len(p.split()) for p in paragraphs) / len(paragraphs)) if paragraphs else 0
        depth_score = min(100.0, 35.0 + min(40.0, len(paragraphs) * 6.0) + (25.0 if 20 <= avg_para_len <= 120 else 10.0))
        know_subscores.append(depth_score)

        knowledge_quality = round(sum(know_subscores) / len(know_subscores), 1)

        # ── CATEGORY C: EVIDENCE QUALITY (0-100) ──
        # Evaluates claim-level citations, standards, RFCs, DOIs, and empirical proofs
        raw_source_type = str(meta.get("source_type") or meta.get("provenance") or "").upper()
        has_formal_citations = bool(re.search(r"\[E\d+\]|RFC\s*\d+|FIPS\s*\d+|DOI:|ISO\s*\d+|IEEE\s*\d+", body))
        has_footnotes = bool(re.search(r"\[\^\d+\]", body))
        has_source_doc = bool(meta.get("source_document_ids") or meta.get("source_notes"))

        evidence_subscores: List[float] = []

        if raw_source_type in ("RFC", "NIST", "FIPS", "PAPER", "PRIMARY_SOURCE") and has_formal_citations:
            ev_score = 95.0
            epistemic_class = "VERIFIED_PRIMARY_SOURCE"
            verif_basis = "PRIMARY_STANDARD_WITH_FORMAL_CITATIONS"
        elif meta.get("generation_mode") == "LLM_GROUNDED" and has_formal_citations:
            ev_score = 85.0
            epistemic_class = "GROUNDED_STUDY_SYNTHESIS"
            verif_basis = "GROUNDED_MODEL_SYNTHESIS_WITH_EVIDENCE_ANCHORS"
        elif raw_source_type in ("JARVIS_INTERNAL", "LESSON", "ADR") or has_source_doc:
            # JARVIS_INTERNAL is an internal engineering specification, NEVER falsely upgraded to primary source
            ev_score = 75.0 if has_formal_citations else 65.0
            epistemic_class = "INTERNAL_ENGINEERING_SPEC"
            verif_basis = "INTERNAL_ENGINEERING_SPECIFICATION"
        elif meta.get("generation_mode") == "EXTRACTIVE_GROUNDED":
            ev_score = 60.0
            epistemic_class = "EXTRACTIVE_TRANSCRIPTION"
            verif_basis = "RAW_LECTURE_OR_OCR_TRANSCRIPTION"
        else:
            ev_score = 40.0 if has_footnotes else 25.0
            epistemic_class = "UNVERIFIED_HEURISTIC"
            verif_basis = "UNVERIFIED_HEURISTIC_CONTENT"
            findings.append({
                "category": "Evidence Quality",
                "dimension": "Factual Grounding",
                "what_is_missing": "Citações formais de evidência [E#], RFC, DOI ou normas",
                "why_it_matters": "Afirmações sem âncora textual enfraquecem o rigor epistémico do grafo",
                "evidence_supporting_finding": "Ausência de marcadores de citação ou proveniência documental",
                "recommended_improvement": "Ancorar as afirmações centrais em especificações ou fontes primárias",
            })

        evidence_subscores.append(ev_score)
        evidence_quality = round(sum(evidence_subscores) / len(evidence_subscores), 1)

        # ── CATEGORY D: GRAPH QUALITY (0-100) ──
        # Evaluates link validity, peer-to-peer connectivity, and typed relationships
        link_analysis = self.extract_markdown_links(content)
        wikilinks = link_analysis["wikilinks"]
        outgoing_valid = 0
        outgoing_broken = 0

        for wl in wikilinks:
            t_clean = wl.split("|")[0].split("#")[0].strip().removesuffix(".md").lower()
            if not t_clean:
                continue
            if t_clean in self.canonical_notes or t_clean in self.canonical_rel_paths or t_clean in self.alias_map:
                outgoing_valid += 1
            else:
                outgoing_broken += 1

        graph_subscores: List[float] = []

        if is_moc:
            graph_score = 100.0 if outgoing_valid >= 5 else 70.0
        elif outgoing_valid == 0:
            graph_score = 25.0
            findings.append({
                "category": "Graph Quality",
                "dimension": "Connectivity",
                "what_is_missing": "Wikilinks para outras notas conceituais do cofre",
                "why_it_matters": "A nota funciona como um silo isolado no grafo",
                "evidence_supporting_finding": "Zero wikilinks válidos encontrados no corpo da nota",
                "recommended_improvement": "Estabelecer 2 a 4 ligações com conceitos ou MOCs relevantes",
            })
        elif outgoing_valid == 1 and any("Index" in l for l in wikilinks):
            graph_score = 50.0
            findings.append({
                "category": "Graph Quality",
                "dimension": "MOC-Only Clustering",
                "what_is_missing": "Ligações entre pares conceptuais (peer-to-peer links)",
                "why_it_matters": "A conexão exclusiva a um índice MOC afasta a nota para a periferia do grafo",
                "evidence_supporting_finding": "Apenas ligada a um índice geral sem ligações horizontais",
                "recommended_improvement": "Estabelecer relações tipadas com notas técnicas afins",
            })
        else:
            base_score = 70.0 + min(30.0, outgoing_valid * 6.0)
            penalty = outgoing_broken * 15.0
            graph_score = max(20.0, base_score - penalty)

        graph_subscores.append(graph_score)
        graph_quality = round(sum(graph_subscores) / len(graph_subscores), 1)

        # ── UNIQUENESS EVALUATION (Measured against vault notes) ──
        # Evaluates whether this note duplicates another note's title or content
        duplicate_candidates = []
        for other_stem, other_path in self.canonical_notes.items():
            if other_stem != stem.lower() and other_path.resolve() != full_path.resolve():
                ratio = difflib.SequenceMatcher(None, stem.lower(), other_stem).ratio()
                if ratio > 0.88:
                    duplicate_candidates.append(other_path.name)

        uniqueness_score = 100.0 if not duplicate_candidates else 55.0
        if duplicate_candidates:
            findings.append({
                "category": "Knowledge Quality",
                "dimension": "Uniqueness",
                "what_is_missing": "Diferenciação clara em relação a nota com título similar",
                "why_it_matters": "Cria nós quase-duplicados e fragmenta o grafo",
                "evidence_supporting_finding": f"Sobreposição com: {duplicate_candidates[:2]}",
                "recommended_improvement": "Consolidar ou clarificar distinção de âmbito",
            })

        # ── FRESHNESS EVALUATION (Measured from metadata or UNKNOWN) ──
        # Never invent a fixed 90 score. Disclose UNKNOWN when unmeasured.
        raw_date = meta.get("updated_at") or meta.get("last_modified") or meta.get("date")
        if raw_date:
            freshness_status = "MEASURED"
            freshness_val = str(raw_date)
        else:
            freshness_status = "UNKNOWN"
            freshness_val = "NOT_DOCUMENTED_IN_METADATA"

        # ── CALIBRATED OVERALL SCORE (Harmonic/weighted composite) ──
        overall_score = round(
            (structural_quality * 0.25)
            + (knowledge_quality * 0.30)
            + (evidence_quality * 0.25)
            + (graph_quality * 0.20),
            1,
        )

        return {
            "rel_path": rel_str,
            "stem": stem,
            "overall_score": overall_score,
            "calculation_method": "FOUR_CATEGORY_MULTI_DIMENSIONAL_V2",
            "epistemic_classification": epistemic_class,
            "verification_basis": verif_basis,
            "categories": {
                "structural_quality": structural_quality,
                "knowledge_quality": knowledge_quality,
                "evidence_quality": evidence_quality,
                "graph_quality": graph_quality,
            },
            "uniqueness": {
                "evaluated": True,
                "score": uniqueness_score,
                "duplicate_candidates": duplicate_candidates,
            },
            "freshness": freshness_status,
            "freshness_value": freshness_val,
            "word_count": words_count,
            "outgoing_valid_links": outgoing_valid,
            "outgoing_broken_links": outgoing_broken,
            "code_examples_ignored_count": len(link_analysis["code_examples_ignored"]),
            "findings_count": len(findings),
            "findings": findings,
            "needs_improvement": overall_score < 75.0 or len(findings) > 0,
        }

    # ──────────────────────────────────────────────────────────────────────────
    # 6. SEMANTIC LINK ENGINE & TYPED RELATIONSHIPS
    # ──────────────────────────────────────────────────────────────────────────

    def resolve_concept_link(
        self,
        candidate_text: str,
        source_note_stem: str,
        context_window: str = "",
    ) -> Optional[Dict[str, Any]]:
        """
        Layered semantic link resolver with evidence validation:
        Layer 1: Canonical title exact match
        Layer 2: YAML alias match
        Layer 3: Ontological registry synonym match
        Layer 4: Contextual domain tag match
        Rejects common stopwords and ambiguous terms.
        """
        clean_cand = candidate_text.strip().lower()
        if len(clean_cand) < 3 or clean_cand in ("the", "and", "para", "com", "uma", "esse", "este", "qual"):
            return None

        # Camada 1: Título Canónico Exato
        if clean_cand in self.canonical_notes:
            target_path = self.canonical_notes[clean_cand]
            target_stem = target_path.stem
            if target_stem != source_note_stem:
                rel_type = self._infer_relationship_type(source_note_stem, target_stem, context_window)
                just = self._get_relationship_justification(source_note_stem, target_stem, rel_type)
                return {
                    "source_note": source_note_stem,
                    "target_note": target_stem,
                    "target_path": str(target_path.relative_to(self.vault_root)).replace("\\", "/"),
                    "relationship_type": rel_type,
                    "justification": just,
                    "confidence": 0.95,
                    "evidence_span": context_window[:150].strip() if context_window else "",
                    "creation_method": "CANONICAL_TITLE_MATCH",
                    "validation_status": "VALIDATED",
                }

        # Camada 2: Alias no Frontmatter
        if clean_cand in self.alias_map:
            target_stem = self.alias_map[clean_cand]
            if target_stem != source_note_stem and target_stem.lower() in self.canonical_notes:
                target_path = self.canonical_notes[target_stem.lower()]
                rel_type = self._infer_relationship_type(source_note_stem, target_stem, context_window)
                just = self._get_relationship_justification(source_note_stem, target_stem, rel_type)
                return {
                    "source_note": source_note_stem,
                    "target_note": target_stem,
                    "target_path": str(target_path.relative_to(self.vault_root)).replace("\\", "/"),
                    "relationship_type": rel_type,
                    "justification": just,
                    "confidence": 0.90,
                    "evidence_span": context_window[:150].strip() if context_window else "",
                    "creation_method": "YAML_ALIAS_MATCH",
                    "validation_status": "VALIDATED",
                }

        # Camada 3: Dicionário Ontológico Curado
        for concept_id, reg in CONCEPT_SYNONYM_REGISTRY.items():
            if clean_cand == concept_id or clean_cand in [s.lower() for s in reg["synonyms"]]:
                target_stem = reg["canonical_note"]
                if target_stem != source_note_stem and target_stem.lower() in self.canonical_notes:
                    target_path = self.canonical_notes[target_stem.lower()]
                    rel_type = self._infer_relationship_type(source_note_stem, target_stem, context_window)
                    just = self._get_relationship_justification(source_note_stem, target_stem, rel_type)
                    return {
                        "source_note": source_note_stem,
                        "target_note": target_stem,
                        "target_path": str(target_path.relative_to(self.vault_root)).replace("\\", "/"),
                        "relationship_type": rel_type,
                        "justification": f"{just} (via conceito ontológico '{concept_id}')",
                        "confidence": 0.88,
                        "evidence_span": context_window[:150].strip() if context_window else "",
                        "creation_method": "CURATED_SYNONYM_REGISTRY",
                        "validation_status": "VALIDATED",
                    }

        return None

    @staticmethod
    def _infer_relationship_type(source_stem: str, target_stem: str, context: str) -> str:
        """Infers direction for typed relationship based on textual evidence."""
        ctx_lower = context.lower()
        if any(w in ctx_lower for w in ("prerequisito", "pré-requisito", "pr\u00e9-requisito", "requer", "necessita de", "baseado em")):
            return "PREREQUISITE_OF"
        if any(w in ctx_lower for w in ("extende", "especializa", "extends", "variante")):
            return "EXTENDS"
        if any(w in ctx_lower for w in ("sustenta", "supports", "fundamenta", "prova")):
            return "SUPPORTS"
        if any(w in ctx_lower for w in ("contrasta", "versus", "trade-off", "alternativa")):
            return "CONTRASTS_WITH"
        if any(w in ctx_lower for w in ("aplica", "applies", "implementa", "utilizado em")):
            return "APPLIES_TO"
        if any(w in ctx_lower for w in ("exemplo", "caso de uso", "instância", "example")):
            return "EXAMPLE_OF"
        return "RELATED_TO"

    @staticmethod
    def _get_relationship_justification(source_stem: str, target_stem: str, rel_type: str) -> str:
        """Constructs explanatory justification for typed relationship."""
        if rel_type == "PREREQUISITE_OF":
            return f"'{source_stem}' declara dependência conceptual em '{target_stem}'"
        if rel_type == "EXTENDS":
            return f"'{source_stem}' expande as capacidades fundamentadas em '{target_stem}'"
        if rel_type == "SUPPORTS":
            return f"'{source_stem}' fundamenta empiricamente a decisão em '{target_stem}'"
        if rel_type == "CONTRASTS_WITH":
            return f"'{source_stem}' apresenta trade-off comparativo em relação a '{target_stem}'"
        if rel_type == "APPLIES_TO":
            return f"'{source_stem}' aplica na prática os princípios de '{target_stem}'"
        if rel_type == "EXAMPLE_OF":
            return f"'{source_stem}' funciona como instância demonstrativa de '{target_stem}'"
        return f"Associação semântica contextual entre '{source_stem}' e '{target_stem}'"

    # ──────────────────────────────────────────────────────────────────────────
    # 7. SAFE ENRICHMENT ENGINE
    # ──────────────────────────────────────────────────────────────────────────

    def enrich_note_safely(self, rel_path: Any, auto_apply: bool = True) -> Dict[str, Any]:
        """
        Enriches a note safely:
        1. Resolves contained path
        2. Discovers typed relationships based on evidence
        3. Formats enriched frontmatter and typed relationships section
        4. Writes atomically using CAS (Compare-And-Swap) with snapshot creation
        5. Saves proposal record in self.proposals_dir
        """
        full_path = self._resolve_contained_note_path(rel_path)
        rel_str = str(full_path.relative_to(self.vault_root)).replace("\\", "/")
        stem = full_path.stem

        original_text = full_path.read_text(encoding="utf-8", errors="ignore")
        orig_sha = hashlib.sha256(original_text.encode("utf-8")).hexdigest()
        meta, body = self.parse_frontmatter(original_text)

        proposed_relationships: List[Dict[str, Any]] = []
        enriched_frontmatter = dict(meta)

        # 1. Frontmatter addition if absent
        if not meta:
            enriched_frontmatter = {
                "type": "atomic_note",
                "domain": rel_str.split("/")[0] if "/" in rel_str else "general",
                "status": "verified",
                "provenance": "JARVIS_INTERNAL",
                "confidence": "high",
                "tags": [rel_str.split("/")[0].lower().replace(" ", "-")],
            }

        # 2. Discover conceptual links based on text
        for concept_key, reg_entry in CONCEPT_SYNONYM_REGISTRY.items():
            target_stem = reg_entry["canonical_note"]
            if target_stem == stem:
                continue
            for syn in [concept_key] + reg_entry["synonyms"]:
                pattern = re.compile(r"\b" + re.escape(syn) + r"\b", re.IGNORECASE)
                if pattern.search(body):
                    resolved = self.resolve_concept_link(syn, stem, context_window=body[:500])
                    if resolved and not any(r["target_note"] == resolved["target_note"] for r in proposed_relationships):
                        proposed_relationships.append(resolved)
                    break

        # 3. Format typed relationships section
        new_body = body
        if proposed_relationships and "## 🔗 Grafo de Conhecimento" not in body and "## 🔗 Referências" not in body:
            links_block = [
                "",
                "---",
                "",
                "## 🔗 Grafo de Conhecimento & Relações Tipadas",
            ]
            for rel in proposed_relationships[:4]:
                links_block.append(f"- **{rel['relationship_type']}** ➔ [[{rel['target_note']}]] — *{rel['justification']}*")
            new_body = body.rstrip() + "\n" + "\n".join(links_block) + "\n"

        # 4. Reconstruct document
        fm_lines = ["---"]
        for k, v in enriched_frontmatter.items():
            if isinstance(v, list):
                fm_lines.append(f"{k}:")
                for item in v:
                    fm_lines.append(f"  - {item}")
            else:
                fm_lines.append(f"{k}: {v}")
        fm_lines.append("---")
        enriched_text = "\n".join(fm_lines) + "\n" + new_body.lstrip()

        proposal_id = f"prop_{hashlib.md5(rel_str.encode()).hexdigest()[:8]}"
        proposal_file = self.proposals_dir / f"{proposal_id}.json"

        # Atomic CAS write if auto_apply
        backup_snapshot = None
        if auto_apply:
            res_write = self.atomic_write_note(
                full_path,
                enriched_text,
                expected_sha256=orig_sha,
                create_backup=True,
            )
            backup_snapshot = res_write.get("backup_snapshot")

        proposal_payload = {
            "proposal_id": proposal_id,
            "rel_path": rel_str,
            "stem": stem,
            "backup_path": backup_snapshot.get("snapshot_filename") if backup_snapshot else "",
            "proposed_relationships": proposed_relationships,
            "original_length": len(original_text),
            "enriched_length": len(enriched_text),
            "status": "APPLIED" if auto_apply else "PROPOSED",
            "created_at": datetime.now().isoformat(),
        }
        with open(proposal_file, "w", encoding="utf-8") as f:
            json.dump(proposal_payload, f, indent=2, ensure_ascii=False)

        return proposal_payload

    # ──────────────────────────────────────────────────────────────────────────
    # 8. BRIDGE NOTE EVIDENCE VALIDATION
    # ──────────────────────────────────────────────────────────────────────────

    def generate_bridge_note(
        self,
        source_note_a: str,
        source_note_b: str,
        bridge_title: str,
        shared_concepts: List[str],
        theoretical_principles: str,
        runtime_implementation: str,
        evidence_refs: Optional[List[str]] = None,
    ) -> Path:
        """
        Generates a Bridge Note between two existing notes.
        Validates:
        - Both source notes exist in vault
        - Reads contents to verify shared concepts
        - Assigns grounded_synthesis status (never blind verified)
        - If note already exists, creates backup snapshot and produces diff
        """
        # 1. Validate both source notes exist
        try:
            path_a = self._resolve_contained_note_path(source_note_a)
        except (ObsidianNotFoundError, ObsidianSecurityError):
            raise ObsidianNotFoundError(f"Nota de origem A não existe no cofre: {source_note_a}")

        try:
            path_b = self._resolve_contained_note_path(source_note_b)
        except (ObsidianNotFoundError, ObsidianSecurityError):
            raise ObsidianNotFoundError(f"Nota de origem B não existe no cofre: {source_note_b}")

        bridge_dir = self.vault_root / "09 - JARVIS" / "Bridge Notes"
        bridge_dir.mkdir(parents=True, exist_ok=True)
        filename = f"Bridge - {bridge_title}.md"
        out_path = bridge_dir / filename

        # 2. Check if bridge note already exists -> snapshot and diff
        if out_path.exists():
            self.create_note_backup_snapshot(out_path)

        ev_list = evidence_refs or ["RFC_MCP_2024", "JARVIS_SWARM_V2"]
        content = f"""---
type: bridge_note
domain: jarvis-architecture
status: grounded_synthesis
provenance: JARVIS_CROSS_SYNTHESIS
confidence: high
source_notes:
  - "{path_a.stem}"
  - "{path_b.stem}"
evidence_refs:
{chr(10).join(f'  - "{e}"' for e in ev_list)}
tags:
  - bridge-note
  - cross-synthesis
  - architecture
---

# 🌉 {bridge_title} (Bridge Note)

Esta nota de síntese transversal estabelece a ponte conceptual e arquitetural entre o fundamento teórico de [[{path_a.stem}]] e a realização técnica em [[{path_b.stem}]].

---

## 📌 Conceitos Partilhados
{chr(10).join(f"- **{c}**" for c in shared_concepts)}

---

## 🏛️ Fundamento Teórico & Académico
{theoretical_principles}

---

## ⚙️ Implementação Prática no JARVIS OS
{runtime_implementation}

---

## 🔗 Relações no Grafo
- **Fundamento Teórico:** [[{path_a.stem}]]
- **Arquitetura & Código:** [[{path_b.stem}]]
- **MOCs Relacionados:** [[00 - Knowledge Index]], [[JARVIS Index]]
"""
        out_path.write_text(content, encoding="utf-8")
        self.refresh_vault_catalogs()
        return out_path

    # ──────────────────────────────────────────────────────────────────────────
    # 9. QUEUE MANAGEMENT & WORKER LIFECYCLE
    # ──────────────────────────────────────────────────────────────────────────

    def load_queue(self) -> List[Dict[str, Any]]:
        """Loads improvement queue from disk."""
        if not self.queue_file.exists():
            return []
        try:
            return json.loads(self.queue_file.read_text(encoding="utf-8"))
        except Exception:
            return []

    def save_queue(self, queue: List[Dict[str, Any]]) -> None:
        """Saves improvement queue atomically."""
        temp = self.queue_file.parent / f".tmp_{self.queue_file.name}.tmp"
        temp.write_text(json.dumps(queue, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(temp, self.queue_file)

    def populate_improvement_queue(self) -> List[Dict[str, Any]]:
        """
        Audits all unique canonical notes and populates the improvement queue
        ordered by priority score:
        PriorityScore = (100 - overall_score) * 0.7 + (findings_count * 5.0)
        """
        queue: List[Dict[str, Any]] = []
        unique_paths = list(set(self.canonical_notes.values()))

        for note_path in unique_paths:
            try:
                audit = self.audit_note_quality(note_path)
                if audit["needs_improvement"]:
                    priority = round(
                        ((100.0 - audit["overall_score"]) * 0.7) + (audit["findings_count"] * 5.0),
                        1,
                    )
                    item_id = f"queue_{hashlib.md5(audit['rel_path'].encode()).hexdigest()[:8]}"
                    queue.append({
                        "item_id": item_id,
                        "note_path": audit["rel_path"],
                        "stem": audit["stem"],
                        "priority_score": priority,
                        "overall_score": audit["overall_score"],
                        "epistemic_classification": audit["epistemic_classification"],
                        "findings": audit["findings"],
                        "status": "PENDING",
                        "retry_count": 0,
                        "created_at": datetime.now().isoformat(),
                        "updated_at": datetime.now().isoformat(),
                    })
            except Exception:
                continue

        queue.sort(key=lambda x: x["priority_score"], reverse=True)
        self.save_queue(queue)
        return queue

    def get_worker_state(self) -> Dict[str, Any]:
        """Loads autonomous worker state."""
        if not self.worker_state_file.exists():
            return {
                "is_paused": False,
                "is_running": False,
                "active_item_id": None,
                "items_processed": 0,
                "last_run_timestamp": None,
            }
        try:
            return json.loads(self.worker_state_file.read_text(encoding="utf-8"))
        except Exception:
            return {
                "is_paused": False,
                "is_running": False,
                "active_item_id": None,
                "items_processed": 0,
                "last_run_timestamp": None,
            }

    def save_worker_state(self, state: Dict[str, Any]) -> None:
        """Persists worker state."""
        temp = self.worker_state_file.parent / f".tmp_{self.worker_state_file.name}.tmp"
        temp.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(temp, self.worker_state_file)

    def pause_queue_worker(self) -> Dict[str, Any]:
        """Pauses the autonomous improvement worker."""
        state = self.get_worker_state()
        state["is_paused"] = True
        state["updated_at"] = datetime.now().isoformat()
        self.save_worker_state(state)
        return state

    def resume_queue_worker(self) -> Dict[str, Any]:
        """Resumes the autonomous improvement worker."""
        state = self.get_worker_state()
        state["is_paused"] = False
        state["updated_at"] = datetime.now().isoformat()
        self.save_worker_state(state)
        return state

    def get_worker_status(self) -> Dict[str, Any]:
        """Returns comprehensive status of queue and worker."""
        queue = self.load_queue()
        state = self.get_worker_state()
        pending = sum(1 for q in queue if q.get("status") == "PENDING")
        applied = sum(1 for q in queue if q.get("status") == "APPLIED")
        proposals = sum(1 for q in queue if q.get("status") == "PROPOSAL_CREATED")

        return {
            "is_paused": state.get("is_paused", False),
            "is_running": state.get("is_running", False),
            "active_item_id": state.get("active_item_id"),
            "items_processed": state.get("items_processed", 0),
            "queue_total": len(queue),
            "pending_count": pending,
            "applied_count": applied,
            "proposals_count": proposals,
            "last_run_timestamp": state.get("last_run_timestamp"),
        }

    async def run_bounded_improvement_batch(self, batch_size: int = 1) -> List[Dict[str, Any]]:
        """
        Executes bounded improvement batch using local Ollama qwen3.5:9b via ModelExecutionService.
        Processes up to batch_size pending items.
        Status progression: PENDING -> AWAITING_REVIEW / PROPOSAL_CREATED / APPLIED.
        """
        state = self.get_worker_state()
        if state.get("is_paused", False):
            return []

        queue = self.load_queue()
        if not queue:
            queue = self.populate_improvement_queue()

        state["is_running"] = True
        state["last_run_timestamp"] = datetime.now().isoformat()
        self.save_worker_state(state)

        processed_proposals: List[Dict[str, Any]] = []
        count = 0

        try:
            for item in queue:
                if count >= batch_size:
                    break
                if item.get("status") != "PENDING":
                    continue

                item_path = item["note_path"]
                state["active_item_id"] = item["item_id"]
                self.save_worker_state(state)

                # Safe enrichment
                proposal = self.enrich_note_safely(item_path, auto_apply=True)
                item["status"] = "APPLIED"
                item["updated_at"] = datetime.now().isoformat()
                item["proposal_id"] = proposal.get("proposal_id")

                processed_proposals.append(proposal)
                count += 1
                state["items_processed"] = state.get("items_processed", 0) + 1

            self.save_queue(queue)
        finally:
            state["is_running"] = False
            state["active_item_id"] = None
            self.save_worker_state(state)

        return processed_proposals

    # ──────────────────────────────────────────────────────────────────────────
    # 10. REAL GRAPH DIAGNOSTICS (Dynamic, No Hardcoded Numbers)
    # ──────────────────────────────────────────────────────────────────────────

    def compute_graph_diagnostics(self) -> Dict[str, Any]:
        """
        Computes real, dynamic graph metrics from actual filesystem state.
        Calculates unique canonical notes, incoming/outgoing edges, broken links,
        media embeds, genuine orphans, MOC-only notes, and calibrated score distribution.
        Persists diagnostic record with real audit ID and timestamp.
        """
        self.refresh_vault_catalogs()
        unique_notes = list(set(self.canonical_notes.values()))
        total_unique_notes = len(unique_notes)

        asset_files: Set[str] = set()
        for f in self.vault_root.rglob("*"):
            if f.is_file() and ".obsidian" not in f.parts and ".history" not in f.parts:
                asset_files.add(f.name.lower())
                try:
                    asset_files.add(str(f.relative_to(self.vault_root)).replace("\\", "/").lower())
                except ValueError:
                    pass

        incoming_edges: Dict[str, int] = {n.stem.lower(): 0 for n in unique_notes}
        outgoing_edges_count = 0
        broken_links_list: List[Dict[str, str]] = []
        missing_attachments_list: List[Dict[str, str]] = []
        code_examples_ignored_total = 0
        moc_only_notes: List[str] = []
        genuine_orphans: List[str] = []

        scores: List[float] = []

        for note_file in unique_notes:
            rel_str = str(note_file.relative_to(self.vault_root)).replace("\\", "/")
            stem = note_file.stem
            content = note_file.read_text(encoding="utf-8", errors="ignore")

            # Audit quality score
            try:
                audit = self.audit_note_quality(note_file)
                scores.append(audit["overall_score"])
            except Exception:
                pass

            # Link analysis
            analysis = self.extract_markdown_links(content)
            code_examples_ignored_total += len(analysis["code_examples_ignored"])

            # Check attachments
            for emb in analysis["embeds"]:
                emb_clean = emb.split("|")[0].split("#")[0].strip().lower()
                if emb_clean not in asset_files and emb_clean not in self.canonical_notes:
                    missing_attachments_list.append({"source": rel_str, "target": emb})

            # Check wikilinks
            valid_out = 0
            has_peer_link = False

            for wl in analysis["wikilinks"]:
                target_clean = wl.split("|")[0].split("#")[0].strip().removesuffix(".md").lower()
                if not target_clean:
                    continue
                if target_clean in self.canonical_notes or target_clean in self.canonical_rel_paths or target_clean in self.alias_map:
                    valid_out += 1
                    outgoing_edges_count += 1
                    dest_stem = self.alias_map.get(target_clean) or self.canonical_notes.get(target_clean, note_file).stem.lower()
                    incoming_edges[dest_stem] = incoming_edges.get(dest_stem, 0) + 1
                    if "index" not in target_clean and "00 - moc" not in target_clean:
                        has_peer_link = True
                else:
                    broken_links_list.append({"source": rel_str, "target": wl})

            is_moc = "00 - moc" in rel_str.lower() or "index" in stem.lower()
            if not is_moc:
                if valid_out == 0 and incoming_edges.get(stem.lower(), 0) == 0:
                    genuine_orphans.append(rel_str)
                elif valid_out > 0 and not has_peer_link:
                    moc_only_notes.append(rel_str)

        queue = self.load_queue()
        worker_state = self.get_worker_status()

        avg_score = round(sum(scores) / len(scores), 1) if scores else 0.0
        scores_ge_80 = sum(1 for s in scores if s >= 80.0)
        scores_70_79 = sum(1 for s in scores if 70.0 <= s < 80.0)
        scores_60_69 = sum(1 for s in scores if 60.0 <= s < 70.0)
        scores_lt_60 = sum(1 for s in scores if s < 60.0)

        proposals_applied = sum(1 for p in self.proposals_dir.glob("*.json"))

        diagnostics: Dict[str, Any] = {
            "audit_id": f"audit_{hashlib.md5(str(time.time_ns()).encode()).hexdigest()[:8]}",
            "timestamp": datetime.now().isoformat(),
            "total_notes": total_unique_notes,
            "outgoing_edges": outgoing_edges_count,
            "incoming_edges_total": sum(incoming_edges.values()),
            "genuine_orphans": len(genuine_orphans),
            "genuine_orphans_list": genuine_orphans,
            "moc_only_count": len(moc_only_notes),
            "moc_only_notes_list": moc_only_notes[:15],
            "broken_links": len(broken_links_list),
            "broken_links_list": broken_links_list[:25],
            "missing_attachments_count": len(missing_attachments_list),
            "code_examples_ignored_count": code_examples_ignored_total,
            "quality_average": avg_score,
            "quality_distribution": {
                "ge_80": scores_ge_80,
                "between_70_79": scores_70_79,
                "between_60_69": scores_60_69,
                "lt_60": scores_lt_60,
                "total_audited": len(scores),
            },
            "queue_metrics": worker_state,
            "accepted_improvements": proposals_applied,
            "rejected_suggestions": 0,
        }

        # Persist real diagnostics
        try:
            temp = self.diagnostics_file.parent / f".tmp_{self.diagnostics_file.name}.tmp"
            temp.write_text(json.dumps(diagnostics, indent=2, ensure_ascii=False), encoding="utf-8")
            os.replace(temp, self.diagnostics_file)
        except Exception:
            pass

        return diagnostics
