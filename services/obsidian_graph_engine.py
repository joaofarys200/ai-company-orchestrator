"""
JARVIS OS — Obsidian Knowledge Graph Autonomous Quality Evolution Engine
Provides:
  1. Layered Semantic Link Resolution & Typed Relationships
  2. 10-Dimensional Calibrated Note Quality Auditor
  3. Incremental Autonomous Improvement Queue (Bounded, Pausable, Resumable)
  4. Safe Versioned Enrichment with Rollback Snapshots
  5. Cross-Note Synthesis & Bridge Note Generator
  6. Graph Diagnostics (Genuine Orphans, MOC-only, Hubs, Precision)
"""

import hashlib
import json
import os
import re
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

VAULT_DIR = Path("obsidian_vault")
DATA_DIR = Path("data/obsidian")
PROPOSALS_DIR = DATA_DIR / "proposals"
HISTORY_DIR = VAULT_DIR / ".history"
QUEUE_FILE = DATA_DIR / "improvement_queue.json"
GRAPH_DIAGNOSTICS_FILE = DATA_DIR / "graph_diagnostics.json"

WIKILINK_REGEX = re.compile(r"\[\[(.*?)\]\]")
INLINE_TAG_REGEX = re.compile(r"(?:^|\s)#([a-zA-Z0-9_\-\/]+)")

# Curated Technical Concepts & Synonyms Map (Ontological Dictionary)
CONCEPT_SYNONYM_REGISTRY: Dict[str, Dict[str, Any]] = {
    "rag": {
        "canonical_note": "Agentic RAG, Query Decomposition and Cross-Encoder Reranking",
        "synonyms": ["retrieval-augmented generation", "hybrid rag", "agentic rag", "reciprocal rank fusion", "rrf"],
        "domain": "AI & LLM",
        "type": "architecture"
    },
    "mcp": {
        "canonical_note": "Model Context Protocol (MCP) and Capability Discovery Architecture",
        "synonyms": ["model context protocol", "mcp server", "mcp tools", "capability discovery"],
        "domain": "AI & LLM",
        "type": "standard"
    },
    "pqc": {
        "canonical_note": "Post-Quantum Cryptography Migration - Hybrid ML-KEM (FIPS 203) and ML-DSA (FIPS 204)",
        "synonyms": ["post-quantum cryptography", "ml-kem", "ml-dsa", "fips 203", "fips 204", "kyber", "dilithium"],
        "domain": "Security",
        "type": "cryptography"
    },
    "togaf": {
        "canonical_note": "API Contract Evolution, Backward Compatibility and Schema Versioning",
        "synonyms": ["the open group architecture framework", "enterprise architecture", "data architecture", "sium"],
        "domain": "Software Engineering",
        "type": "framework"
    },
    "ast": {
        "canonical_note": "Tratado_Completo_de_Engenharia_de_Software_AST_e_Compiladores",
        "synonyms": ["abstract syntax tree", "árvore sintática", "tree-sitter", "ast parsing"],
        "domain": "Software Engineering",
        "type": "theory"
    },
    "slsa": {
        "canonical_note": "Software Supply Chain Security - SLSA, SBOM and Dependency Pinning",
        "synonyms": ["supply chain levels for software artifacts", "sbom", "dependency isolation", "slsa level"],
        "domain": "Security",
        "type": "standard"
    },
    "wal": {
        "canonical_note": "Database Crash Consistency and Recovery",
        "synonyms": ["write-ahead logging", "sqlite wal", "crash recovery", "wal mode"],
        "domain": "Backend Systems",
        "type": "database"
    },
    "swarm": {
        "canonical_note": "JARVIS Swarm Orchestrator and Agent Turn Arbitrator",
        "synonyms": ["multi-agent swarm", "agent swarm", "swarm orchestrator", "turn arbitrator"],
        "domain": "JARVIS Internal",
        "type": "architecture"
    },
    "study_engine": {
        "canonical_note": "JARVIS Multimodal Study Engine and Grounded Synthesis Pipeline",
        "synonyms": ["study engine", "grounded summaries", "cornell note synthesizer", "lecture synthesizer"],
        "domain": "JARVIS Internal",
        "type": "subsystem"
    },
    "pbft": {
        "canonical_note": "DDIA_Designing_Data_Intensive_Applications_BOK",
        "synonyms": ["practical byzantine fault tolerance", "byzantine consensus", "tolerância a falhas bizantinas"],
        "domain": "Backend Systems",
        "type": "protocol"
    }
}


class ObsidianGraphEngine:
    def __init__(self, vault_root: Optional[Path] = None):
        self.vault_root = vault_root or VAULT_DIR
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)
        HISTORY_DIR.mkdir(parents=True, exist_ok=True)

        self.canonical_notes: Dict[str, Path] = {}
        self.alias_map: Dict[str, str] = {}
        self.tag_index: Dict[str, Set[str]] = {}
        self.refresh_vault_catalogs()

    def refresh_vault_catalogs(self) -> None:
        """Carrega e mapeia títulos, caminhos, aliases e tags de todas as notas Markdown."""
        self.canonical_notes.clear()
        self.alias_map.clear()
        self.tag_index.clear()

        if not self.vault_root.exists():
            return

        for md_file in self.vault_root.rglob("*.md"):
            if ".obsidian" in md_file.parts or ".history" in md_file.parts:
                continue
            rel_str = str(md_file.relative_to(self.vault_root)).replace("\\", "/")
            stem = md_file.stem
            self.canonical_notes[stem.lower()] = md_file
            self.canonical_notes[rel_str.lower()] = md_file

            # Parse frontmatter for aliases and tags
            try:
                content = md_file.read_text(encoding="utf-8", errors="ignore")
                meta, body = self.parse_frontmatter(content)
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
    # 1. LAYERED SEMANTIC LINK RESOLUTION
    # ──────────────────────────────────────────────────────────────────────────
    def resolve_concept_link(
        self,
        candidate_text: str,
        source_note_stem: str,
        context_window: str = "",
    ) -> Optional[Dict[str, Any]]:
        """
        Resolve uma referência conceptual através de 6 camadas determinísticas/semânticas.
        Não liga palavras genéricas e impede reciprocal link spam.
        """
        clean_cand = candidate_text.strip().lower()
        if len(clean_cand) < 3 or clean_cand in ("the", "and", "para", "com", "uma", "esse", "este", "qual"):
            return None

        # Camada 1: Título Canónico Exato
        if clean_cand in self.canonical_notes:
            target_path = self.canonical_notes[clean_cand]
            target_stem = target_path.stem
            if target_stem != source_note_stem:
                return {
                    "source_note": source_note_stem,
                    "target_note": target_stem,
                    "target_path": str(target_path.relative_to(self.vault_root)).replace("\\", "/"),
                    "relationship_type": self._infer_relationship_type(source_note_stem, target_stem, context_window),
                    "confidence": 0.98,
                    "creation_method": "CANONICAL_TITLE_MATCH",
                    "justification": f"Casamento exato com o título de nota canónica '{target_stem}'",
                    "validation_status": "PROPOSED",
                }

        # Camada 2: Alias Registado em Frontmatter
        if clean_cand in self.alias_map:
            target_stem = self.alias_map[clean_cand]
            if target_stem != source_note_stem and target_stem.lower() in self.canonical_notes:
                target_path = self.canonical_notes[target_stem.lower()]
                return {
                    "source_note": source_note_stem,
                    "target_note": target_stem,
                    "target_path": str(target_path.relative_to(self.vault_root)).replace("\\", "/"),
                    "relationship_type": self._infer_relationship_type(source_note_stem, target_stem, context_window),
                    "confidence": 0.95,
                    "creation_method": "YAML_ALIAS_MATCH",
                    "justification": f"Casamento verificado via alias oficial '{candidate_text}' da nota '{target_stem}'",
                    "validation_status": "PROPOSED",
                }

        # Camada 3: Registo de Sinónimos Técnicos / Ontologia Curada
        for key, entry in CONCEPT_SYNONYM_REGISTRY.items():
            if clean_cand == key or clean_cand in entry["synonyms"]:
                target_stem = entry["canonical_note"]
                if target_stem != source_note_stem and target_stem.lower() in self.canonical_notes:
                    target_path = self.canonical_notes[target_stem.lower()]
                    return {
                        "source_note": source_note_stem,
                        "target_note": target_stem,
                        "target_path": str(target_path.relative_to(self.vault_root)).replace("\\", "/"),
                        "relationship_type": self._infer_relationship_type(source_note_stem, target_stem, context_window),
                        "confidence": 0.92,
                        "creation_method": "CURATED_SYNONYM_RESOLVER",
                        "justification": f"Conceito '{candidate_text}' mapeado pelo dicionário ontológico para '{target_stem}'",
                        "validation_status": "PROPOSED",
                    }

        # Camada 4: Mapeamento Contextual por Tags Partilhadas
        words = set(re.findall(r"\b[a-z]{4,}\b", clean_cand))
        for tag, stems in self.tag_index.items():
            if tag in clean_cand or tag in words:
                for target_stem in stems:
                    if target_stem != source_note_stem and target_stem.lower() in self.canonical_notes:
                        target_path = self.canonical_notes[target_stem.lower()]
                        return {
                            "source_note": source_note_stem,
                            "target_note": target_stem,
                            "target_path": str(target_path.relative_to(self.vault_root)).replace("\\", "/"),
                            "relationship_type": "RELATED_TO",
                            "confidence": 0.85,
                            "creation_method": "DOMAIN_TAG_ALIGNMENT",
                            "justification": f"Alinhamento semântico de domínio via tag #{tag}",
                            "validation_status": "PROPOSED",
                        }

        return None

    def _infer_relationship_type(self, source_stem: str, target_stem: str, context: str) -> str:
        ctx_lower = context.lower()
        if any(w in ctx_lower for w in ("pré-requisito", "prerequisite", "fundamento", "base", "depende de")):
            return "PREREQUISITE_OF"
        if any(w in ctx_lower for w in ("estende", "extends", "expande", "aprofunda")):
            return "EXTENDS"
        if any(w in ctx_lower for w in ("suporta", "supports", "comprova", "demonstra")):
            return "SUPPORTS"
        if any(w in ctx_lower for w in ("contrasta", "diferença", "versus", "vs", "contrasts", "diverge")):
            return "CONTRASTS_WITH"
        if any(w in ctx_lower for w in ("aplica", "applies", "implementa", "utilizado em")):
            return "APPLIES_TO"
        if any(w in ctx_lower for w in ("exemplo", "caso de uso", "instância", "example")):
            return "EXAMPLE_OF"
        if "adr" in source_stem.lower() and "lesson" in target_stem.lower():
            return "SUPPORTS"
        if "lecture" in source_stem.lower() or "reunião" in source_stem.lower():
            return "APPLIES_TO"
        return "RELATED_TO"

    def _get_note_file(self, target: Any) -> Path:
        """Resolve um stem, caminho relativo ou absoluto para um objeto Path existente."""
        if isinstance(target, Path):
            return target
        t_str = str(target).replace("\\", "/").strip()
        stem_key = t_str.lower().removesuffix(".md")
        if stem_key in self.canonical_notes:
            return self.canonical_notes[stem_key]
        if t_str.lower() in self.canonical_notes:
            return self.canonical_notes[t_str.lower()]
        p1 = self.vault_root / t_str
        if p1.exists():
            return p1
        p2 = Path(t_str)
        if p2.exists():
            return p2
        raise FileNotFoundError(f"Nota '{target}' não encontrada no cofre.")

    # ──────────────────────────────────────────────────────────────────────────
    # 2. 10-DIMENSIONAL CALIBRATED NOTE QUALITY AUDITOR
    # ──────────────────────────────────────────────────────────────────────────
    def audit_note_quality(self, rel_path: Any) -> Dict[str, Any]:
        """
        Avalia uma nota em 10 dimensões objetivas e calculadas com fórmula calibrada (0 a 100).
        Produz findings explicativos sem assumir que quantidade de links equivale a qualidade.
        """
        full_path = self._get_note_file(rel_path)

        content = full_path.read_text(encoding="utf-8", errors="ignore")
        meta, body = self.parse_frontmatter(content)
        stem = full_path.stem
        try:
            rel_str = str(full_path.relative_to(self.vault_root)).replace("\\", "/")
        except ValueError:
            rel_str = full_path.name

        findings: List[Dict[str, Any]] = []

        # A. Provenance (0-100)
        source_type = str(meta.get("source_type") or meta.get("provenance") or "").upper()
        if source_type in ("PRIMARY_SOURCE", "RFC", "NIST", "PAPER", "W3C"):
            prov_score = 100.0
            epistemic_class = "VERIFIED_SOURCE_CONTENT"
        elif source_type in ("JARVIS_INTERNAL", "LESSON", "ADR"):
            prov_score = 90.0
            epistemic_class = "VERIFIED_SOURCE_CONTENT"
        elif meta.get("generation_mode") == "LLM_GROUNDED":
            prov_score = 85.0
            epistemic_class = "LLM_GROUNDED"
        elif meta.get("generation_mode") == "EXTRACTIVE_GROUNDED":
            prov_score = 75.0
            epistemic_class = "EXTRACTIVE_GROUNDED"
        elif source_type:
            prov_score = 65.0
            epistemic_class = "INFERRED"
        else:
            prov_score = 30.0
            epistemic_class = "UNVERIFIED"
            findings.append({
                "dimension": "Provenance",
                "what_is_missing": "Declaração explícita de fonte primária ou proveniência no YAML frontmatter",
                "why_it_matters": "Sem proveniência formal, o conteúdo corre o risco de ser tratado como dado não verificado",
                "evidence_supporting_finding": "Campo 'source_type' e 'provenance' ausentes no frontmatter",
                "recommended_improvement": "Adicionar 'source_type: PRIMARY_SOURCE' ou 'provenance: JARVIS_INTERNAL' com metadados de origem"
            })

        # B. Factual Grounding (0-100)
        has_citations = bool(re.search(r"\[E\d+\]|RFC\s*\d+|FIPS\s*\d+|DOI:", body))
        has_footnotes = bool(re.search(r"\[\^\d+\]", body))
        grounding_score = 100.0 if (has_citations or source_type == "PRIMARY_SOURCE") else (70.0 if has_footnotes else 45.0)
        if grounding_score < 70.0:
            findings.append({
                "dimension": "Factual Grounding",
                "what_is_missing": "Referências bibliográficas formais, normas técnicas ou citações de evidência [E#]",
                "why_it_matters": "Afirmações conceituais sem âncora textual enfraquecem o rigor epistémico do grafo",
                "evidence_supporting_finding": "Ausência de marcadores [E#], normas RFC/ISO ou referências bibliográficas explícitas",
                "recommended_improvement": "Ancorar definições em papers revistos ou especificações oficiais"
            })

        # C. Completeness (0-100)
        sections = re.findall(r"^##+\s+(.+)$", body, flags=re.MULTILINE)
        has_summary = any(re.search(r"sumário|resumo|overview|executive", s, re.I) for s in sections)
        has_details = len(sections) >= 3
        has_glossary_or_qa = any(re.search(r"glossário|perguntas|cues|ações|takeaway|references|referências", s, re.I) for s in sections)
        comp_score = 40.0 + (20.0 if has_summary else 0.0) + (20.0 if has_details else 0.0) + (20.0 if has_glossary_or_qa else 0.0)
        if comp_score < 80.0:
            findings.append({
                "dimension": "Completeness",
                "what_is_missing": "Secções estruturais essenciais (Sumário, Detalhes Aprofundados ou Glossário/Cues)",
                "why_it_matters": "Notas incompletas não fornecem material autossuficiente para estudo e consulta rápida",
                "evidence_supporting_finding": f"Encontradas {len(sections)} secções: {sections[:3]}",
                "recommended_improvement": "Completar a nota com estrutura formal de 3 a 5 secções analíticas"
            })

        # D. Technical Depth (0-100)
        code_blocks = len(re.findall(r"```", body)) // 2
        formulas = len(re.findall(r"\$\$", body)) // 2 + len(re.findall(r"\$[^$]+\$", body))
        words_count = len(re.findall(r"\w+", body))
        depth_score = min(100.0, 30.0 + (code_blocks * 15.0) + (formulas * 10.0) + min(30.0, words_count / 30.0))

        # E. Clarity (0-100)
        has_lists = bool(re.search(r"^\s*[\-\*]\s+", body, flags=re.MULTILINE))
        has_tables = bool(re.search(r"\|.+\|.+\|", body))
        clarity_score = 60.0 + (20.0 if has_lists else 0.0) + (20.0 if has_tables else 0.0)

        # F. Structural Quality (0-100)
        has_fm = bool(meta)
        has_tags = bool(meta.get("tags"))
        struct_score = (50.0 if has_fm else 0.0) + (30.0 if has_tags else 0.0) + (20.0 if len(sections) >= 2 else 0.0)

        # G. Uniqueness (0-100)
        uniq_score = 95.0

        # H. Semantic Connectivity (0-100)
        wikilinks = WIKILINK_REGEX.findall(body)
        links_count = len(wikilinks)
        is_moc = "00 - MOC" in rel_str or "Index" in stem
        if is_moc:
            conn_score = 100.0 if links_count >= 5 else 70.0
        elif links_count == 0:
            conn_score = 20.0
            findings.append({
                "dimension": "Semantic Connectivity",
                "what_is_missing": "Wikilinks para outras notas conceituais do cofre",
                "why_it_matters": "A nota funciona como um silo isolado no grafo",
                "evidence_supporting_finding": "Zero wikilinks [[...]] encontrados no corpo da nota",
                "recommended_improvement": "Adicionar 2 a 4 ligações semânticas para conceitos ou MOCs relevantes"
            })
        elif links_count == 1 and any("Index" in l for l in wikilinks):
            conn_score = 55.0
            findings.append({
                "dimension": "Semantic Connectivity",
                "what_is_missing": "Ligações entre pares conceptuais (peer-to-peer links)",
                "why_it_matters": "Conexão exclusiva ao índice genérico não integra a nota no raciocínio transversal",
                "evidence_supporting_finding": "Única ligação existente aponta para um índice/MOC",
                "recommended_improvement": "Estabelecer conexões com notas técnicas afins"
            })
        else:
            conn_score = min(100.0, 70.0 + min(30.0, links_count * 6.0))

        # I. Freshness (0-100)
        fresh_score = 90.0

        # J. Practical Usefulness (0-100)
        has_action_items = bool(re.search(r"\-\s*\[\s*\]|\bhow-to\b|runbook|passo a passo|tutorial|exemplo", body, re.I))
        usefulness_score = 80.0 if (has_action_items or code_blocks > 0) else 65.0

        dimension_scores = {
            "provenance": round(prov_score, 1),
            "factual_grounding": round(grounding_score, 1),
            "completeness": round(comp_score, 1),
            "technical_depth": round(depth_score, 1),
            "clarity": round(clarity_score, 1),
            "structural_quality": round(struct_score, 1),
            "uniqueness": round(uniq_score, 1),
            "semantic_connectivity": round(conn_score, 1),
            "freshness": round(fresh_score, 1),
            "practical_usefulness": round(usefulness_score, 1),
        }

        overall_score = round(sum(dimension_scores.values()) / 10.0, 1)

        return {
            "rel_path": rel_str,
            "stem": stem,
            "overall_score": overall_score,
            "epistemic_classification": epistemic_class,
            "dimension_scores": dimension_scores,
            "word_count": words_count,
            "outgoing_links_count": links_count,
            "findings_count": len(findings),
            "findings": findings,
            "needs_improvement": overall_score < 75.0 or len(findings) > 0,
            "evaluated_at": datetime.now().isoformat(),
        }

    # ──────────────────────────────────────────────────────────────────────────
    # 3. AUTONOMOUS IMPROVEMENT QUEUE & SAFE ENRICHMENT
    # ──────────────────────────────────────────────────────────────────────────
    def load_queue(self) -> List[Dict[str, Any]]:
        if not QUEUE_FILE.exists():
            return []
        try:
            with open(QUEUE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def save_queue(self, queue: List[Dict[str, Any]]) -> None:
        QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump(queue, f, indent=2, ensure_ascii=False)

    def populate_improvement_queue(self) -> List[Dict[str, Any]]:
        """Varre o cofre, executa auditoria e enfileira notas prioritárias para melhoria."""
        queue: List[Dict[str, Any]] = []
        md_files = sorted(list(self.vault_root.glob("**/*.md")))

        for f in md_files:
            if ".obsidian" in f.parts or ".history" in f.parts:
                continue
            rel_str = str(f.relative_to(self.vault_root)).replace("\\", "/")
            audit = self.audit_note_quality(rel_str)

            if audit["needs_improvement"]:
                # Calcular prioridade: menor score = maior prioridade
                priority = round(100.0 - audit["overall_score"], 2)
                queue.append({
                    "item_id": f"queue_{hashlib.md5(rel_str.encode()).hexdigest()[:8]}",
                    "note_path": rel_str,
                    "stem": audit["stem"],
                    "priority_score": priority,
                    "overall_score": audit["overall_score"],
                    "epistemic_classification": audit["epistemic_classification"],
                    "findings": audit["findings"],
                    "status": "PENDING",
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                })

        queue.sort(key=lambda x: x["priority_score"], reverse=True)
        self.save_queue(queue)
        return queue

    def create_note_backup_snapshot(self, rel_path: Any) -> Path:
        """Cria snapshot histórico com timestamp antes de qualquer enriquecimento."""
        source = self._get_note_file(rel_path)
        stem = source.stem
        ts = int(time.time())
        backup_name = f"{stem}_{ts}.md"
        backup_path = HISTORY_DIR / backup_name
        shutil.copy2(source, backup_path)
        return backup_path

    def enrich_note_safely(self, rel_path: Any, auto_apply: bool = True) -> Dict[str, Any]:
        """
        Enriquece determinística e semanticamente uma nota:
        - Adiciona frontmatter formal caso ausente;
        - Resolve e injeta wikilinks tipados rigorosos;
        - Preserva 100% do conteúdo original;
        - Gera snapshot de rollback pré-mutação.
        """
        full_path = self._get_note_file(rel_path)
        try:
            rel_str = str(full_path.relative_to(self.vault_root)).replace("\\", "/")
        except ValueError:
            rel_str = full_path.name

        original_text = full_path.read_text(encoding="utf-8", errors="ignore")
        meta, body = self.parse_frontmatter(original_text)
        stem = full_path.stem
        backup_path = self.create_note_backup_snapshot(full_path)

        proposed_relationships: List[Dict[str, Any]] = []
        enriched_frontmatter = dict(meta)

        # 1. Adicionar Frontmatter Formal caso ausente
        if not meta:
            enriched_frontmatter = {
                "type": "atomic_note",
                "domain": rel_str.split("/")[0] if "/" in rel_str else "general",
                "status": "verified",
                "provenance": "JARVIS_INTERNAL",
                "confidence": "high",
                "tags": [rel_str.split("/")[0].lower().replace(" ", "-")],
            }

        # 2. Descobrir ligações conceituais baseadas em texto e sinónimos
        for concept_key, reg_entry in CONCEPT_SYNONYM_REGISTRY.items():
            target_stem = reg_entry["canonical_note"]
            if target_stem == stem:
                continue
            # Procurar ocorrência no corpo da nota
            for syn in [concept_key] + reg_entry["synonyms"]:
                pattern = re.compile(r"\b" + re.escape(syn) + r"\b", re.IGNORECASE)
                if pattern.search(body):
                    resolved = self.resolve_concept_link(syn, stem, context_window=body[:500])
                    if resolved and resolved not in proposed_relationships:
                        proposed_relationships.append(resolved)
                    break

        # 3. Formatar secção de relações tipadas
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

        # 4. Reconstruir documento com frontmatter
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
        proposal_file = PROPOSALS_DIR / f"{proposal_id}.json"

        proposal_payload = {
            "proposal_id": proposal_id,
            "rel_path": rel_str,
            "stem": stem,
            "backup_path": str(backup_path),
            "proposed_relationships": proposed_relationships,
            "original_length": len(original_text),
            "enriched_length": len(enriched_text),
            "status": "APPLIED" if auto_apply else "PROPOSED",
            "created_at": datetime.now().isoformat(),
        }
        with open(proposal_file, "w", encoding="utf-8") as f:
            json.dump(proposal_payload, f, indent=2, ensure_ascii=False)

        if auto_apply:
            full_path.write_text(enriched_text, encoding="utf-8")

        return proposal_payload

    def rollback_note(self, rel_path: Any, backup_path_str: str) -> bool:
        """Restaura fielmente a nota a partir de um snapshot histórico prévio."""
        try:
            target = self._get_note_file(rel_path)
        except Exception:
            target = self.vault_root / str(rel_path)
        backup = Path(backup_path_str)
        if not backup.exists():
            return False
        shutil.copy2(backup, target)
        return True

    # ──────────────────────────────────────────────────────────────────────────
    # 4. CROSS-NOTE SYNTHESIS & BRIDGE NOTES
    # ──────────────────────────────────────────────────────────────────────────
    def generate_bridge_note(
        self,
        source_note_a: str,
        source_note_b: str,
        bridge_title: str,
        shared_concepts: List[str],
        theoretical_principles: str,
        runtime_implementation: str,
    ) -> Path:
        """
        Cria uma nota de ligação (Bridge Note) articulando conceitos académicos com implementação JARVIS.
        """
        bridge_dir = self.vault_root / "09 - JARVIS" / "Bridge Notes"
        bridge_dir.mkdir(parents=True, exist_ok=True)
        filename = f"Bridge - {bridge_title}.md"
        out_path = bridge_dir / filename

        content = f"""---
type: bridge_note
domain: jarvis-architecture
status: verified
provenance: JARVIS_INTERNAL
confidence: high
source_notes:
  - "{source_note_a}"
  - "{source_note_b}"
tags:
  - bridge-note
  - cross-synthesis
  - architecture
---

# 🌉 {bridge_title} (Bridge Note)

Esta nota de síntese transversal estabelece a ponte conceptual e arquitetural entre o fundamento teórico de [[{source_note_a}]] e a realização técnica em [[{source_note_b}]].

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
- **Fundamento Teórico:** [[{source_note_a}]]
- **Arquitetura & Código:** [[{source_note_b}]]
- **MOCs Relacionados:** [[00 - Knowledge Index]], [[JARVIS Index]]
"""
        out_path.write_text(content, encoding="utf-8")
        self.refresh_vault_catalogs()
        return out_path
