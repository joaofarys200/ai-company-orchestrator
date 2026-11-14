//! Obsidian Knowledge Graph Engine in native Rust.
//!
//! Ported from `services/obsidian_graph_engine.py`:
//! 1. Strict path containment & traversal/symlink rejection
//! 2. Collision-free 2-stage snapshots with sidecar v2 JSON integrity metadata
//! 3. Atomic Compare-And-Swap (CAS) note writes & cross-note-safe rollback
//! 4. Four-category calibrated heuristic quality scoring (`audit_note_quality`)
//! 5. Markdown-aware wikilink & attachment extraction (ignoring code fences/inline code)
//! 6. Deterministic semantic enrichment via curated synonym ontology
//! 7. Improvement queue & bounded batch execution (Ollama qwen probe + deterministic fallback)
//! 8. Two-pass graph diagnostics (`compute_graph_diagnostics`)

use std::collections::{BTreeMap, HashMap, HashSet};
use std::fmt;
use std::fs;
use std::path::{Component, Path, PathBuf};
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use chrono::{Local, NaiveDate, NaiveDateTime};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::net::TcpStream;
use tokio::time::timeout;
use uuid::Uuid;

use crate::knowledge::vault::resolve_vault_root;
use crate::storage::atomic_fs::{atomic_write_bytes, atomic_write_string};

#[derive(Debug, Clone)]
pub enum KnowledgeError {
    SecurityViolation(String),
    NotFound(String),
    ConcurrencyConflict(String),
    Internal(String),
}

impl KnowledgeError {
    pub fn code(&self) -> &'static str {
        match self {
            Self::SecurityViolation(_) => "SECURITY_VIOLATION",
            Self::NotFound(_) => "NOT_FOUND",
            Self::ConcurrencyConflict(_) => "CONCURRENCY_CONFLICT",
            Self::Internal(_) => "INTERNAL_ERROR",
        }
    }
}

impl fmt::Display for KnowledgeError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::SecurityViolation(m)
            | Self::NotFound(m)
            | Self::ConcurrencyConflict(m)
            | Self::Internal(m) => f.write_str(m),
        }
    }
}

struct ConceptRegistryEntry {
    key: &'static str,
    canonical_note: &'static str,
    synonyms: &'static [&'static str],
    concept_type: &'static str,
}

const CONCEPT_SYNONYM_REGISTRY: &[ConceptRegistryEntry] = &[
    ConceptRegistryEntry {
        key: "rag",
        canonical_note: "Agentic RAG, Query Decomposition and Cross-Encoder Reranking",
        synonyms: &[
            "retrieval-augmented generation",
            "hybrid rag",
            "agentic rag",
            "reciprocal rank fusion",
            "rrf",
        ],
        concept_type: "architecture",
    },
    ConceptRegistryEntry {
        key: "mcp",
        canonical_note: "Model Context Protocol (MCP) and Capability Discovery Architecture",
        synonyms: &[
            "model context protocol",
            "mcp server",
            "mcp tools",
            "capability discovery",
        ],
        concept_type: "standard",
    },
    ConceptRegistryEntry {
        key: "pqc",
        canonical_note: "Post-Quantum Cryptography Migration - Hybrid ML-KEM (FIPS 203) and ML-DSA (FIPS 204)",
        synonyms: &[
            "post-quantum cryptography",
            "ml-kem",
            "ml-dsa",
            "fips 203",
            "fips 204",
            "kyber",
            "dilithium",
        ],
        concept_type: "cryptography",
    },
    ConceptRegistryEntry {
        key: "ast",
        canonical_note: "Tratado_Completo_de_Engenharia_de_Software_AST_e_Compiladores",
        synonyms: &[
            "abstract syntax tree",
            "árvore sintática",
            "tree-sitter",
            "ast parsing",
        ],
        concept_type: "theory",
    },
    ConceptRegistryEntry {
        key: "slsa",
        canonical_note: "Software Supply Chain Security - SLSA, SBOM and Dependency Pinning",
        synonyms: &[
            "supply chain levels for software artifacts",
            "sbom",
            "dependency isolation",
            "slsa level",
        ],
        concept_type: "standard",
    },
    ConceptRegistryEntry {
        key: "wal",
        canonical_note: "Database Crash Consistency and Recovery",
        synonyms: &[
            "write-ahead logging",
            "sqlite wal",
            "crash recovery",
            "wal mode",
        ],
        concept_type: "database",
    },
    ConceptRegistryEntry {
        key: "swarm",
        canonical_note: "JARVIS Swarm Orchestrator and Agent Turn Arbitrator",
        synonyms: &[
            "multi-agent swarm",
            "agent swarm",
            "swarm orchestrator",
            "turn arbitrator",
        ],
        concept_type: "architecture",
    },
    ConceptRegistryEntry {
        key: "study_engine",
        canonical_note: "JARVIS Multimodal Study Engine and Grounded Synthesis Pipeline",
        synonyms: &[
            "study engine",
            "grounded summaries",
            "cornell note synthesizer",
            "lecture synthesizer",
        ],
        concept_type: "subsystem",
    },
    ConceptRegistryEntry {
        key: "pbft",
        canonical_note: "DDIA_Designing_Data_Intensive_Applications_BOK",
        synonyms: &[
            "practical byzantine fault tolerance",
            "byzantine consensus",
            "tolerância a falhas bizantinas",
        ],
        concept_type: "protocol",
    },
    ConceptRegistryEntry {
        key: "ddd",
        canonical_note: "DDD_Domain_Driven_Design_and_Enterprise_Patterns",
        synonyms: &[
            "domain-driven design",
            "bounded context",
            "aggregate root",
            "enterprise patterns",
        ],
        concept_type: "architecture",
    },
];

fn round1(v: f64) -> f64 {
    (v * 10.0).round() / 10.0
}

fn sha256_hex(bytes: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(bytes);
    hex::encode(hasher.finalize())
}

fn now_iso_local() -> String {
    Local::now().format("%Y-%m-%dT%H:%M:%S%.6f").to_string()
}

fn now_unix_nanos() -> u128 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_nanos())
        .unwrap_or(0)
}

fn is_word_char(ch: char) -> bool {
    ch.is_alphanumeric() || ch == '_'
}

fn count_words(text: &str) -> usize {
    let mut count = 0usize;
    let mut in_word = false;
    for ch in text.chars() {
        if is_word_char(ch) {
            if !in_word {
                count += 1;
                in_word = true;
            }
        } else {
            in_word = false;
        }
    }
    count
}

fn contains_word_ci(haystack: &str, needle: &str) -> bool {
    let h_lower = haystack.to_lowercase();
    let n_lower = needle.to_lowercase();
    if n_lower.is_empty() {
        return false;
    }
    let mut start = 0usize;
    while let Some(pos) = h_lower[start..].find(&n_lower) {
        let abs = start + pos;
        let end = abs + n_lower.len();
        let before_ok = h_lower[..abs]
            .chars()
            .next_back()
            .map(|c| !is_word_char(c))
            .unwrap_or(true);
        let after_ok = h_lower[end..]
            .chars()
            .next()
            .map(|c| !is_word_char(c))
            .unwrap_or(true);
        if before_ok && after_ok {
            return true;
        }
        start = abs + n_lower.len().max(1);
    }
    false
}

fn find_longest_common_match(
    a: &[char],
    b: &[char],
    alo: usize,
    ahi: usize,
    blo: usize,
    bhi: usize,
) -> (usize, usize, usize) {
    let mut besti = alo;
    let mut bestj = blo;
    let mut bestsize = 0usize;
    let mut j2len: HashMap<usize, usize> = HashMap::new();
    for (i_off, &ch_a) in a[alo..ahi].iter().enumerate() {
        let i = alo + i_off;
        let mut newj2len: HashMap<usize, usize> = HashMap::new();
        for (j_off, &ch_b) in b[blo..bhi].iter().enumerate() {
            if ch_a != ch_b {
                continue;
            }
            let j = blo + j_off;
            let prev = j
                .checked_sub(1)
                .and_then(|p| j2len.get(&p).copied())
                .unwrap_or(0);
            let k = prev + 1;
            newj2len.insert(j, k);
            if k > bestsize {
                besti = i + 1 - k;
                bestj = j + 1 - k;
                bestsize = k;
            }
        }
        j2len = newj2len;
    }
    (besti, bestj, bestsize)
}

/// Ratcliff/Obershelp character sequence similarity matching Python `difflib.SequenceMatcher.ratio()`.
fn sequence_similarity(a_str: &str, b_str: &str) -> f64 {
    let a: Vec<char> = a_str.chars().collect();
    let b: Vec<char> = b_str.chars().collect();
    if a.is_empty() && b.is_empty() {
        return 1.0;
    }
    if a.is_empty() || b.is_empty() {
        return 0.0;
    }
    let mut queue = vec![(0usize, a.len(), 0usize, b.len())];
    let mut matched = 0usize;
    while let Some((alo, ahi, blo, bhi)) = queue.pop() {
        let (i, j, k) = find_longest_common_match(&a, &b, alo, ahi, blo, bhi);
        if k > 0 {
            matched += k;
            if alo < i && blo < j {
                queue.push((alo, i, blo, j));
            }
            if i + k < ahi && j + k < bhi {
                queue.push((i + k, ahi, j + k, bhi));
            }
        }
    }
    (2.0 * matched as f64) / ((a.len() + b.len()) as f64)
}

fn path_stem_str(path: &Path) -> String {
    path.file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or("")
        .to_string()
}

fn strip_md_suffix_ci(s: &str) -> &str {
    if s.len() >= 3 && s[s.len() - 3..].eq_ignore_ascii_case(".md") {
        &s[..s.len() - 3]
    } else {
        s
    }
}

fn extract_bracket_tokens(text: &str, open: &str, close: &str) -> (Vec<String>, String) {
    let mut items = Vec::new();
    let mut cleaned = String::with_capacity(text.len());
    let mut rest = text;
    while let Some(start) = rest.find(open) {
        cleaned.push_str(&rest[..start]);
        let after_open = &rest[start + open.len()..];
        if let Some(end) = after_open.find(close) {
            let inner = &after_open[..end];
            if !inner.contains('\n') {
                items.push(inner.to_string());
                rest = &after_open[end + close.len()..];
            } else {
                cleaned.push_str(open);
                rest = after_open;
            }
        } else {
            cleaned.push_str(open);
            rest = after_open;
        }
    }
    cleaned.push_str(rest);
    (items, cleaned)
}

fn strip_fenced_code_blocks(body: &str) -> (String, Vec<String>, usize) {
    let mut clean = String::with_capacity(body.len());
    let mut blocks = Vec::new();
    let mut pos = 0usize;
    let bytes = body.as_bytes();
    while pos < bytes.len() {
        let rem = &body[pos..];
        let next_bt = rem.find("```");
        let next_tilde = rem.find("~~~");
        let next_rel = match (next_bt, next_tilde) {
            (Some(a), Some(b)) => Some(if a <= b { (a, "```") } else { (b, "~~~") }),
            (Some(a), None) => Some((a, "```")),
            (None, Some(b)) => Some((b, "~~~")),
            (None, None) => None,
        };
        let Some((rel_idx, delim)) = next_rel else {
            clean.push_str(rem);
            break;
        };
        clean.push_str(&rem[..rel_idx]);
        let block_start = pos + rel_idx;
        let after_open = &body[block_start + delim.len()..];
        if let Some(close_rel) = after_open.find(delim) {
            let block_end = block_start + delim.len() + close_rel + delim.len();
            blocks.push(body[block_start..block_end].to_string());
            pos = block_end;
        } else {
            clean.push_str(delim);
            pos = block_start + delim.len();
        }
    }
    let count = blocks.len();
    (clean, blocks, count)
}

fn strip_inline_code_spans(text: &str) -> (String, Vec<String>) {
    let mut clean = String::with_capacity(text.len());
    let mut spans = Vec::new();
    let mut rest = text;
    while let Some(start) = rest.find('`') {
        let after_open = &rest[start + 1..];
        if let Some(end) = after_open.find('`') {
            let inner = &after_open[..end];
            if !inner.contains('\n') {
                clean.push_str(&rest[..start]);
                spans.push(rest[start..start + 1 + end + 1].to_string());
                rest = &after_open[end + 1..];
                continue;
            }
        }
        clean.push_str(&rest[..start + 1]);
        rest = after_open;
    }
    clean.push_str(rest);
    (clean, spans)
}

fn strip_html_comments(text: &str) -> String {
    let mut clean = String::with_capacity(text.len());
    let mut rest = text;
    while let Some(start) = rest.find("<!--") {
        clean.push_str(&rest[..start]);
        let after = &rest[start + 4..];
        if let Some(end) = after.find("-->") {
            rest = &after[end + 3..];
        } else {
            clean.push_str("<!--");
            rest = after;
        }
    }
    clean.push_str(rest);
    clean
}

/// Parses optional leading YAML `--- ... ---` frontmatter into ordered key-value pairs and body.
pub fn parse_frontmatter(content: &str) -> (BTreeMap<String, Value>, String) {
    if !content.starts_with("---") {
        return (BTreeMap::new(), content.to_string());
    }
    let after = &content[3..];
    let Some((yaml_text, body)) = after.split_once("---") else {
        return (BTreeMap::new(), content.to_string());
    };
    let mut meta: BTreeMap<String, Value> = BTreeMap::new();
    let mut current_list: Option<String> = None;

    for raw_line in yaml_text.lines() {
        let line_str = raw_line.trim();
        if line_str.is_empty() || line_str.starts_with('#') {
            continue;
        }
        if raw_line.starts_with("  - ") {
            if let Some(ref key) = current_list {
                let item = line_str
                    .strip_prefix('-')
                    .unwrap_or(line_str)
                    .trim()
                    .trim_matches(|c| c == '"' || c == '\'')
                    .to_string();
                if let Some(Value::Array(arr)) = meta.get_mut(key) {
                    arr.push(Value::String(item));
                }
                continue;
            }
        }
        if let Some((k_raw, v_raw)) = line_str.split_once(':') {
            let k = k_raw.trim().to_string();
            let v = v_raw.trim().trim_matches(|c| c == '"' || c == '\'');
            if v.is_empty() {
                meta.insert(k.clone(), Value::Array(Vec::new()));
                current_list = Some(k);
            } else {
                current_list = None;
                if v.starts_with('[') && v.ends_with(']') {
                    let items: Vec<Value> = v[1..v.len() - 1]
                        .split(',')
                        .map(|s| s.trim().trim_matches(|c| c == '"' || c == '\'').to_string())
                        .filter(|s| !s.is_empty())
                        .map(Value::String)
                        .collect();
                    meta.insert(k, Value::Array(items));
                } else {
                    meta.insert(k, Value::String(v.to_string()));
                }
            }
        }
    }
    (meta, body.to_string())
}

fn format_frontmatter_and_body(meta: &BTreeMap<String, Value>, body: &str) -> String {
    let mut fm_lines = vec!["---".to_string()];
    for (k, v) in meta {
        match v {
            Value::Array(arr) => {
                fm_lines.push(format!("{k}:"));
                for item in arr {
                    let text = item
                        .as_str()
                        .map(String::from)
                        .unwrap_or_else(|| item.to_string());
                    fm_lines.push(format!("  - {text}"));
                }
            }
            Value::String(s) => fm_lines.push(format!("{k}: {s}")),
            other => fm_lines.push(format!("{k}: {other}")),
        }
    }
    fm_lines.push("---".to_string());
    format!("{}\n{}", fm_lines.join("\n"), body.trim_start())
}

#[derive(Debug, Clone)]
pub struct ExtractedLinks {
    pub wikilinks: Vec<String>,
    pub embeds: Vec<String>,
    pub code_examples_ignored: Vec<Value>,
    pub code_fences_count: usize,
}

/// Extracts wikilinks and embedded attachments while ignoring fenced code, inline code, and HTML comments.
pub fn extract_markdown_links(content: &str) -> ExtractedLinks {
    let (_, body) = parse_frontmatter(content);
    let mut ignored = Vec::new();
    let (clean_after_blocks, code_blocks, code_fences_count) = strip_fenced_code_blocks(&body);
    for cb in &code_blocks {
        let (wls, _) = extract_bracket_tokens(cb, "[[", "]]");
        for wl in wls {
            ignored.push(json!({ "raw": wl, "type": "code_block" }));
        }
    }
    let (clean_after_inline, inline_spans) = strip_inline_code_spans(&clean_after_blocks);
    for ic in &inline_spans {
        let (wls, _) = extract_bracket_tokens(ic, "[[", "]]");
        for wl in wls {
            ignored.push(json!({ "raw": wl, "type": "inline_code" }));
        }
    }
    let clean = strip_html_comments(&clean_after_inline);
    let (embeds, clean_after_embeds) = extract_bracket_tokens(&clean, "![[", "]]");
    let (wikilinks, _) = extract_bracket_tokens(&clean_after_embeds, "[[", "]]");
    ExtractedLinks {
        wikilinks,
        embeds,
        code_examples_ignored: ignored,
        code_fences_count,
    }
}

fn has_formal_citations(body: &str) -> bool {
    let bytes = body.as_bytes();
    for i in 0..bytes.len() {
        if bytes[i] == b'[' && i + 3 < bytes.len() && (bytes[i + 1] == b'E' || bytes[i + 1] == b'e')
        {
            let mut j = i + 2;
            while j < bytes.len() && bytes[j].is_ascii_digit() {
                j += 1;
            }
            if j > i + 2 && j < bytes.len() && bytes[j] == b']' {
                return true;
            }
        }
    }
    ["rfc", "fips", "doi", "iso", "ieee"]
        .iter()
        .any(|kw| contains_word_ci(body, kw))
}

fn has_footnotes(body: &str) -> bool {
    let bytes = body.as_bytes();
    for i in 0..bytes.len() {
        if bytes[i] == b'[' && i + 3 < bytes.len() && bytes[i + 1] == b'^' {
            let mut j = i + 2;
            while j < bytes.len() && bytes[j].is_ascii_digit() {
                j += 1;
            }
            if j > i + 2 && j < bytes.len() && bytes[j] == b']' {
                return true;
            }
        }
    }
    false
}

fn parse_freshness_date(raw: &str) -> Option<NaiveDateTime> {
    let cleaned = raw.trim().trim_matches(|c| c == '"' || c == '\'');
    let prefix: String = cleaned.chars().take(19).collect();
    if let Ok(dt) = NaiveDateTime::parse_from_str(&prefix, "%Y-%m-%dT%H:%M:%S") {
        return Some(dt);
    }
    if let Ok(dt) = NaiveDateTime::parse_from_str(&prefix, "%Y-%m-%d %H:%M:%S") {
        return Some(dt);
    }
    let date_prefix: String = cleaned.chars().take(10).collect();
    if let Ok(d) = NaiveDate::parse_from_str(&date_prefix, "%Y-%m-%d") {
        return d.and_hms_opt(0, 0, 0);
    }
    None
}

fn is_moc_note(rel_str: &str, stem: &str, meta: &BTreeMap<String, Value>) -> bool {
    rel_str.to_lowercase().contains("00 - moc")
        || stem.to_lowercase().contains("index")
        || meta.get("type").and_then(Value::as_str) == Some("moc")
}

fn extract_meta_str<'a>(meta: &'a BTreeMap<String, Value>, keys: &[&str]) -> Option<&'a str> {
    for k in keys {
        if let Some(v) = meta.get(*k) {
            if let Some(s) = v.as_str().map(str::trim).filter(|s| !s.is_empty()) {
                return Some(s);
            }
        }
    }
    None
}

fn meta_has_truthy(meta: &BTreeMap<String, Value>, keys: &[&str]) -> bool {
    for k in keys {
        if let Some(v) = meta.get(*k) {
            match v {
                Value::Null => {}
                Value::Bool(false) => {}
                Value::String(s) if s.trim().is_empty() => {}
                Value::Array(a) if a.is_empty() => {}
                Value::Object(m) if m.is_empty() => {}
                _ => return true,
            }
        }
    }
    false
}

/// Core native Obsidian graph quality, safety, queue, and diagnostics engine.
pub struct ObsidianGraphEngine {
    pub vault_root: PathBuf,
    pub data_dir: PathBuf,
    pub history_dir: PathBuf,
    pub proposals_dir: PathBuf,
    pub queue_file: PathBuf,
    pub diagnostics_file: PathBuf,
    pub worker_state_file: PathBuf,
    pub locks_dir: PathBuf,
    canonical_notes: HashMap<String, PathBuf>,
    canonical_rel_paths: HashMap<String, PathBuf>,
    alias_map: HashMap<String, String>,
    tag_index: HashMap<String, HashSet<String>>,
}

impl ObsidianGraphEngine {
    /// Opens an engine using workspace-relative `obsidian_vault` (or `OBSIDIAN_VAULT_PATH`) and `data/obsidian`.
    pub fn open_default(project_root: &Path) -> Result<Self, KnowledgeError> {
        let vault = resolve_vault_root(project_root)
            .map_err(|e| KnowledgeError::Internal(e.message))?;
        let data = project_root.join("data").join("obsidian");
        Self::with_paths(vault, data)
    }

    /// Opens an engine bound to explicit `vault_root` and `data_dir` roots.
    pub fn with_paths(vault_root: PathBuf, data_dir: PathBuf) -> Result<Self, KnowledgeError> {
        for dir in [&vault_root, &data_dir] {
            fs::create_dir_all(dir)
                .map_err(|e| KnowledgeError::Internal(format!("Failed creating dir: {e}")))?;
        }
        let canon_vault = dunce::canonicalize(&vault_root)
            .map_err(|e| KnowledgeError::Internal(format!("Failed canonicalizing vault: {e}")))?;
        let canon_data = dunce::canonicalize(&data_dir)
            .map_err(|e| KnowledgeError::Internal(format!("Failed canonicalizing data dir: {e}")))?;

        let history_dir = canon_vault.join(".history");
        let proposals_dir = canon_data.join("proposals");
        let locks_dir = canon_data.join(".locks");
        for dir in [&history_dir, &proposals_dir, &locks_dir] {
            fs::create_dir_all(dir)
                .map_err(|e| KnowledgeError::Internal(format!("Failed creating subdir: {e}")))?;
        }

        let mut engine = Self {
            vault_root: canon_vault,
            data_dir: canon_data.clone(),
            history_dir: dunce::canonicalize(&history_dir).unwrap_or(history_dir),
            proposals_dir: dunce::canonicalize(&proposals_dir).unwrap_or(proposals_dir),
            queue_file: canon_data.join("improvement_queue.json"),
            diagnostics_file: canon_data.join("graph_diagnostics.json"),
            worker_state_file: canon_data.join("improvement_worker_state.json"),
            locks_dir: dunce::canonicalize(&locks_dir).unwrap_or(locks_dir),
            canonical_notes: HashMap::new(),
            canonical_rel_paths: HashMap::new(),
            alias_map: HashMap::new(),
            tag_index: HashMap::new(),
        };
        engine.refresh_vault_catalogs();
        Ok(engine)
    }

    /// Re-scans `vault_root` (excluding `.obsidian` and `.history`) and rebuilds note, alias, and tag indexes.
    pub fn refresh_vault_catalogs(&mut self) {
        self.canonical_notes.clear();
        self.canonical_rel_paths.clear();
        self.alias_map.clear();
        self.tag_index.clear();

        if !self.vault_root.exists() {
            return;
        }

        let mut stack = vec![self.vault_root.clone()];
        while let Some(dir) = stack.pop() {
            let Ok(entries) = fs::read_dir(&dir) else {
                continue;
            };
            for entry in entries.flatten() {
                let path = entry.path();
                let Ok(meta_fs) = fs::symlink_metadata(&path) else {
                    continue;
                };
                if meta_fs.file_type().is_symlink() {
                    continue;
                }
                let name = entry.file_name().to_string_lossy().to_string();
                if meta_fs.is_dir() {
                    if name == ".obsidian" || name == ".history" {
                        continue;
                    }
                    stack.push(path);
                } else if meta_fs.is_file() && name.to_ascii_lowercase().ends_with(".md") {
                    let Ok(canon) = dunce::canonicalize(&path) else {
                        continue;
                    };
                    if !canon.starts_with(&self.vault_root) {
                        continue;
                    }
                    let Ok(rel) = canon.strip_prefix(&self.vault_root) else {
                        continue;
                    };
                    let rel_str = rel.to_string_lossy().replace('\\', "/");
                    let stem = path_stem_str(&canon);
                    self.canonical_notes.insert(stem.to_lowercase(), canon.clone());
                    self.canonical_rel_paths
                        .insert(rel_str.to_lowercase(), canon.clone());

                    if let Ok(content) = fs::read_to_string(&canon) {
                        let (meta, _) = parse_frontmatter(&content);
                        if let Some(aliases_val) = meta.get("aliases") {
                            match aliases_val {
                                Value::Array(arr) => {
                                    for a in arr {
                                        let s = a.as_str().unwrap_or("").trim();
                                        if !s.is_empty() {
                                            self.alias_map
                                                .insert(s.to_lowercase(), stem.clone());
                                        }
                                    }
                                }
                                Value::String(s) if !s.trim().is_empty() => {
                                    self.alias_map
                                        .insert(s.trim().to_lowercase(), stem.clone());
                                }
                                _ => {}
                            }
                        }
                        if let Some(tags_val) = meta.get("tags") {
                            let mut tags = Vec::new();
                            match tags_val {
                                Value::Array(arr) => {
                                    for t in arr {
                                        let s = t.as_str().unwrap_or("").trim().trim_start_matches('#');
                                        if !s.is_empty() {
                                            tags.push(s.to_lowercase());
                                        }
                                    }
                                }
                                Value::String(s) => {
                                    let t = s.trim().trim_start_matches('#');
                                    if !t.is_empty() {
                                        tags.push(t.to_lowercase());
                                    }
                                }
                                _ => {}
                            }
                            for t in tags {
                                self.tag_index.entry(t).or_default().insert(stem.clone());
                            }
                        }
                    }
                }
            }
        }
    }

    fn validate_raw_target(raw: &str) -> Result<String, KnowledgeError> {
        let trimmed = raw.trim();
        if trimmed.is_empty() || trimmed.contains('\0') {
            return Err(KnowledgeError::SecurityViolation(format!(
                "Caminho de nota inválido: '{raw}'"
            )));
        }
        let slash_norm = trimmed.replace('\\', "/");
        for comp in Path::new(&slash_norm).components() {
            if matches!(comp, Component::ParentDir) {
                return Err(KnowledgeError::SecurityViolation(format!(
                    "Tentativa de path traversal rejeitada: {trimmed}"
                )));
            }
        }
        Ok(trimmed.to_string())
    }

    /// Resolves and validates an existing note strictly confined inside `self.vault_root`.
    pub fn resolve_contained_note_path(&self, target: &str) -> Result<PathBuf, KnowledgeError> {
        let cleaned = Self::validate_raw_target(target)?;
        let slash_lower = cleaned.replace('\\', "/").to_lowercase();
        let stem_key = strip_md_suffix_ci(&slash_lower).to_string();

        if let Some(candidate) = self.canonical_notes.get(&stem_key) {
            return self.verify_contained_file(candidate, &cleaned);
        }
        if let Some(candidate) = self.canonical_rel_paths.get(&slash_lower) {
            return self.verify_contained_file(candidate, &cleaned);
        }

        let cand_path = Path::new(&cleaned);
        let joined = if cand_path.is_absolute() {
            cand_path.to_path_buf()
        } else {
            self.vault_root.join(cand_path)
        };
        self.verify_contained_file(&joined, &cleaned)
    }

    fn verify_contained_file(&self, candidate: &Path, display: &str) -> Result<PathBuf, KnowledgeError> {
        if !candidate.exists() {
            // Check parent containment even when missing so traversal/outside paths fail with SecurityViolation.
            if candidate.is_absolute() {
                if let Some(parent) = candidate.parent() {
                    if let Ok(cp) = dunce::canonicalize(parent) {
                        if !cp.starts_with(&self.vault_root) {
                            return Err(KnowledgeError::SecurityViolation(format!(
                                "Caminho fora dos limites do Obsidian Vault rejeitado: {display}"
                            )));
                        }
                    } else if !candidate.starts_with(&self.vault_root) {
                        return Err(KnowledgeError::SecurityViolation(format!(
                            "Caminho fora dos limites do Obsidian Vault rejeitado: {display}"
                        )));
                    }
                }
            }
            return Err(KnowledgeError::NotFound(format!(
                "Nota não encontrada no cofre: {display}"
            )));
        }
        if let Ok(meta) = fs::symlink_metadata(candidate) {
            if meta.file_type().is_symlink() {
                let canon = dunce::canonicalize(candidate).map_err(|e| {
                    KnowledgeError::SecurityViolation(format!("Symlink inválido bloqueado: {e}"))
                })?;
                if !canon.starts_with(&self.vault_root) {
                    return Err(KnowledgeError::SecurityViolation(format!(
                        "Symlink fora dos limites do vault rejeitado: {display}"
                    )));
                }
            }
        }
        let canon = dunce::canonicalize(candidate).map_err(|e| {
            KnowledgeError::SecurityViolation(format!("Falha ao resolver nota: {e}"))
        })?;
        if !canon.starts_with(&self.vault_root) {
            return Err(KnowledgeError::SecurityViolation(format!(
                "Caminho fora dos limites do Obsidian Vault rejeitado: {display}"
            )));
        }
        if !canon.is_file() {
            return Err(KnowledgeError::NotFound(format!(
                "Alvo não é um ficheiro regular: {display}"
            )));
        }
        Ok(canon)
    }

    fn resolve_contained_snapshot_path(&self, backup_target: &str) -> Result<PathBuf, KnowledgeError> {
        let cleaned = Self::validate_raw_target(backup_target)?;
        let candidate = Path::new(&cleaned);
        let joined = if candidate.is_absolute() {
            candidate.to_path_buf()
        } else {
            self.history_dir.join(candidate)
        };
        if let Ok(meta) = fs::symlink_metadata(&joined) {
            if meta.file_type().is_symlink() {
                return Err(KnowledgeError::SecurityViolation(format!(
                    "Snapshot simbólico rejeitado: {cleaned}"
                )));
            }
        }
        let canon = match dunce::canonicalize(&joined) {
            Ok(c) => c,
            Err(_) => {
                if candidate.is_absolute() && !joined.starts_with(&self.history_dir) {
                    return Err(KnowledgeError::SecurityViolation(format!(
                        "Snapshot fora dos limites do history_dir rejeitado: {cleaned}"
                    )));
                }
                return Err(KnowledgeError::NotFound(format!(
                    "Snapshot de backup não encontrado: {cleaned}"
                )));
            }
        };
        if !canon.starts_with(&self.history_dir) {
            return Err(KnowledgeError::SecurityViolation(format!(
                "Snapshot fora dos limites do history_dir rejeitado: {cleaned}"
            )));
        }
        if !canon.is_file() {
            return Err(KnowledgeError::NotFound(format!(
                "Snapshot de backup não encontrado: {cleaned}"
            )));
        }
        Ok(canon)
    }

    fn rel_str_for(&self, canon_path: &Path) -> Result<String, KnowledgeError> {
        canon_path
            .strip_prefix(&self.vault_root)
            .map(|p| p.to_string_lossy().replace('\\', "/"))
            .map_err(|_| {
                KnowledgeError::SecurityViolation(
                    "Nota escapa aos limites de vault_root.".to_string(),
                )
            })
    }

    /// Creates a collision-free backup snapshot in `history_dir` + validated sidecar JSON (`schema_version = 2`).
    pub fn create_note_backup_snapshot(
        &self,
        target: &str,
        reason: &str,
    ) -> Result<(PathBuf, Value), KnowledgeError> {
        let full_path = self.resolve_contained_note_path(target)?;
        let rel_str = self.rel_str_for(&full_path)?;
        let stem = path_stem_str(&full_path);
        let content_bytes = fs::read(&full_path)
            .map_err(|e| KnowledgeError::Internal(format!("Falha ao ler nota para backup: {e}")))?;
        let content_sha256 = sha256_hex(&content_bytes);
        let rel_path_hash = sha256_hex(rel_str.as_bytes())[..12].to_string();
        let timestamp_ns = now_unix_nanos();
        let snap_uuid = Uuid::new_v4().simple().to_string()[..8].to_string();

        let snapshot_filename = format!(
            "snap_{}_{}_{}_{}.md",
            rel_path_hash,
            timestamp_ns,
            &content_sha256[..8],
            snap_uuid
        );
        let snapshot_path = self.history_dir.join(&snapshot_filename);
        let written_snap = atomic_write_bytes(&self.history_dir, &snapshot_path, &content_bytes)
            .map_err(|e| KnowledgeError::Internal(e.message))?;

        let verified_bytes = fs::read(&written_snap).map_err(|e| {
            KnowledgeError::Internal(format!("Falha ao verificar snapshot gravado: {e}"))
        })?;
        if sha256_hex(&verified_bytes) != content_sha256 || verified_bytes.len() != content_bytes.len()
        {
            let _ = fs::remove_file(&written_snap);
            return Err(KnowledgeError::Internal(
                "Falha de integridade ao verificar snapshot.".to_string(),
            ));
        }

        let metadata = json!({
            "snapshot_id": format!("snap_{snap_uuid}"),
            "snapshot_filename": snapshot_filename,
            "snapshot_path": written_snap.to_string_lossy().to_string(),
            "schema_version": 2,
            "note_rel_path": rel_str,
            "note_stem": stem,
            "rel_path_hash": rel_path_hash,
            "timestamp_ns": timestamp_ns as u64,
            "timestamp_iso": now_iso_local(),
            "content_sha256": content_sha256,
            "content_bytes_len": content_bytes.len(),
            "reason": reason,
        });
        let meta_filename = format!(
            "{}.json",
            snapshot_filename
                .strip_suffix(".md")
                .unwrap_or(&snapshot_filename)
        );
        let meta_path = self.history_dir.join(&meta_filename);
        let serialized_meta = serde_json::to_string_pretty(&metadata)
            .map_err(|e| KnowledgeError::Internal(format!("Serialize snapshot metadata failed: {e}")))?;
        atomic_write_string(&self.history_dir, &meta_path, &serialized_meta).map_err(|e| {
            let _ = fs::remove_file(&written_snap);
            KnowledgeError::Internal(e.message)
        })?;

        Ok((written_snap, metadata))
    }

    /// Performs an atomic CAS write to an existing vault note, optionally creating a snapshot first.
    pub fn atomic_write_note(
        &mut self,
        target: &str,
        new_content: &str,
        expected_sha256: Option<&str>,
        create_backup: bool,
    ) -> Result<Value, KnowledgeError> {
        let full_path = self.resolve_contained_note_path(target)?;
        let current_bytes = fs::read(&full_path)
            .map_err(|e| KnowledgeError::Internal(format!("Falha ao ler nota: {e}")))?;
        let current_sha = sha256_hex(&current_bytes);
        if let Some(exp) = expected_sha256 {
            if !exp.is_empty() && current_sha != exp {
                return Err(KnowledgeError::ConcurrencyConflict(format!(
                    "Conflito de concorrência (CAS): hash atual da nota ({}) difere do esperado ({}).",
                    &current_sha[..8.min(current_sha.len())],
                    &exp[..8.min(exp.len())]
                )));
            }
        }

        let backup_meta = if create_backup {
            Some(self.create_note_backup_snapshot(target, "pre_enrichment")?.1)
        } else {
            None
        };

        let written = atomic_write_string(&self.vault_root, &full_path, new_content)
            .map_err(|e| KnowledgeError::Internal(e.message))?;
        let new_bytes = fs::read(&written)
            .map_err(|e| KnowledgeError::Internal(format!("Falha ao verificar escrita: {e}")))?;
        let new_sha = sha256_hex(&new_bytes);

        let rel_str = self.rel_str_for(&written)?;
        self.refresh_vault_catalogs();

        Ok(json!({
            "success": true,
            "rel_path": rel_str,
            "previous_sha256": current_sha,
            "new_sha256": new_sha,
            "backup_snapshot": backup_meta,
        }))
    }

    /// Rolls back a vault note strictly from a verified snapshot inside `history_dir` with matching metadata.
    pub fn rollback_note(
        &mut self,
        target_note: &str,
        backup_path_or_id: &str,
        expected_current_hash: Option<&str>,
    ) -> Result<bool, KnowledgeError> {
        let target_file = self.resolve_contained_note_path(target_note)?;
        let rel_str = self.rel_str_for(&target_file)?;
        let current_bytes = fs::read(&target_file)
            .map_err(|e| KnowledgeError::Internal(format!("Falha ao ler nota alvo: {e}")))?;
        let current_sha = sha256_hex(&current_bytes);
        if let Some(exp) = expected_current_hash {
            if !exp.is_empty() && current_sha != exp {
                return Err(KnowledgeError::ConcurrencyConflict(format!(
                    "Rollback abortado: hash atual da nota ({}) difere do esperado ({}).",
                    &current_sha[..8.min(current_sha.len())],
                    &exp[..8.min(exp.len())]
                )));
            }
        }

        let snapshot_file = self.resolve_contained_snapshot_path(backup_path_or_id)?;
        let meta_file = snapshot_file.with_extension("json");
        if !meta_file.exists() || !meta_file.is_file() {
            return Err(KnowledgeError::SecurityViolation(format!(
                "Rollback rejeitado: metadados sidecar JSON não encontrados para o snapshot '{}'.",
                snapshot_file
                    .file_name()
                    .and_then(|s| s.to_str())
                    .unwrap_or("")
            )));
        }

        let meta_raw = fs::read_to_string(&meta_file).map_err(|e| {
            KnowledgeError::SecurityViolation(format!("Metadados do snapshot ilegíveis: {e}"))
        })?;
        let meta: Value = serde_json::from_str(&meta_raw).map_err(|e| {
            KnowledgeError::SecurityViolation(format!(
                "Metadados do snapshot corrompidos ou mal formatados: {e}"
            ))
        })?;

        if meta.get("schema_version").and_then(Value::as_i64) != Some(2) {
            return Err(KnowledgeError::SecurityViolation(
                "Versão de esquema do snapshot não suportada (esperado 2).".to_string(),
            ));
        }

        let expected_rel = meta.get("note_rel_path").and_then(Value::as_str).unwrap_or("");
        if expected_rel.is_empty() || expected_rel != rel_str {
            return Err(KnowledgeError::SecurityViolation(format!(
                "Snapshot pertence a '{expected_rel}', não a '{rel_str}'. Rollback cross-note rejeitado."
            )));
        }

        if let Some(meta_fname) = meta.get("snapshot_filename").and_then(Value::as_str) {
            let actual_fname = snapshot_file
                .file_name()
                .and_then(|s| s.to_str())
                .unwrap_or("");
            if !meta_fname.is_empty() && meta_fname != actual_fname {
                return Err(KnowledgeError::SecurityViolation(format!(
                    "Nome de ficheiro do snapshot ({actual_fname}) não coincide com metadados ({meta_fname})."
                )));
            }
        }

        let snapshot_bytes = fs::read(&snapshot_file)
            .map_err(|e| KnowledgeError::Internal(format!("Falha ao ler snapshot: {e}")))?;
        if let Some(exp_len) = meta.get("content_bytes_len").and_then(Value::as_u64) {
            if snapshot_bytes.len() as u64 != exp_len {
                return Err(KnowledgeError::SecurityViolation(format!(
                    "Comprimento de bytes do snapshot ({}) difere dos metadados ({}).",
                    snapshot_bytes.len(),
                    exp_len
                )));
            }
        }

        let expected_sha = meta.get("content_sha256").and_then(Value::as_str).unwrap_or("");
        let actual_snap_sha = sha256_hex(&snapshot_bytes);
        if expected_sha.is_empty() || actual_snap_sha != expected_sha {
            return Err(KnowledgeError::SecurityViolation(format!(
                "Snapshot corrompido: hash SHA-256 ({}) não coincide com metadados.",
                &actual_snap_sha[..8.min(actual_snap_sha.len())]
            )));
        }

        let _ = self.create_note_backup_snapshot(&rel_str, "pre_rollback")?;
        atomic_write_bytes(&self.vault_root, &target_file, &snapshot_bytes)
            .map_err(|e| KnowledgeError::Internal(e.message))?;

        let final_sha = sha256_hex(
            &fs::read(&target_file)
                .map_err(|e| KnowledgeError::Internal(format!("Falha pós-rollback: {e}")))?,
        );
        if final_sha != actual_snap_sha {
            return Err(KnowledgeError::Internal(
                "Falha crítica no rollback: hash do ficheiro restaurado difere do snapshot."
                    .to_string(),
            ));
        }

        self.refresh_vault_catalogs();
        Ok(true)
    }

    /// Audited 4-category calibrated note quality score (`HEURISTIC`).
    pub fn audit_note_quality(&self, rel_path: &str) -> Result<Value, KnowledgeError> {
        let full_path = self.resolve_contained_note_path(rel_path)?;
        let content = fs::read_to_string(&full_path)
            .map_err(|e| KnowledgeError::Internal(format!("Falha ao ler nota: {e}")))?;
        let (meta, body) = parse_frontmatter(&content);
        let stem = path_stem_str(&full_path);
        let rel_str = self.rel_str_for(&full_path)?;

        let mut findings: Vec<Value> = Vec::new();
        let (clean_prose, _, _) = strip_fenced_code_blocks(&body);
        let words_count = count_words(&clean_prose);
        let normalized_prose = clean_prose.replace("\r\n", "\n");
        let paragraphs: Vec<&str> = normalized_prose
            .split("\n\n")
            .map(str::trim)
            .filter(|p| !p.is_empty() && !p.starts_with('#'))
            .collect();

        // A. STRUCTURAL QUALITY
        let mut struct_subscores: Vec<f64> = Vec::new();
        if !meta.is_empty() {
            let has_domain = meta_has_truthy(&meta, &["domain", "subject", "tags"]);
            let has_type = meta_has_truthy(&meta, &["type", "source_type"]);
            struct_subscores.push(
                70.0 + if has_domain { 15.0 } else { 0.0 } + if has_type { 15.0 } else { 0.0 },
            );
        } else {
            struct_subscores.push(20.0);
            findings.push(json!({
                "category": "Structural Quality",
                "dimension": "Frontmatter",
                "what_is_missing": "YAML Frontmatter ausente ou não estruturado",
                "why_it_matters": "Impossibilita catalogação automática e indexação de domínio no cofre",
                "evidence_supporting_finding": "Primeira linha do ficheiro não contém delimitador '---'",
                "recommended_improvement": "Adicionar cabeçalho YAML com 'type', 'domain' e 'status'",
            }));
        }

        let mut headings: Vec<(usize, String)> = Vec::new();
        for line in body.lines() {
            let trimmed = line.trim_end_matches('\r');
            let hashes = trimmed.bytes().take_while(|&b| b == b'#').count();
            if hashes > 0 {
                let after = &trimmed[hashes..];
                if after.starts_with(char::is_whitespace) {
                    let title = after.trim();
                    if !title.is_empty() {
                        headings.push((hashes, title.to_string()));
                    }
                }
            }
        }
        if !headings.is_empty() {
            let mut level_skips = 0usize;
            for i in 0..headings.len().saturating_sub(1) {
                if headings[i + 1].0 > headings[i].0 + 1 {
                    level_skips += 1;
                }
            }
            struct_subscores.push((100.0 - (level_skips as f64 * 20.0)).max(30.0));
            if level_skips > 0 {
                findings.push(json!({
                    "category": "Structural Quality",
                    "dimension": "Heading Hierarchy",
                    "what_is_missing": "Hierarquia de cabeçalhos contínua (ex.: salto de # para ###)",
                    "why_it_matters": "Dificulta geração de sumários e renderização de AST markdown",
                    "evidence_supporting_finding": format!("Detetados {level_skips} saltos de nível nos cabeçalhos"),
                    "recommended_improvement": "Normalizar títulos para respeitar progressão contínua (# -> ## -> ###)",
                }));
            }
        } else {
            struct_subscores.push(40.0);
            findings.push(json!({
                "category": "Structural Quality",
                "dimension": "Headings",
                "what_is_missing": "Secções estruturadas com cabeçalhos Markdown (# / ##)",
                "why_it_matters": "Texto monolítico dificulta navegação e síntese",
                "evidence_supporting_finding": "Zero cabeçalhos Markdown detetados no corpo",
                "recommended_improvement": "Estruturar o documento com secções analíticas",
            }));
        }
        let structural_quality =
            round1(struct_subscores.iter().sum::<f64>() / struct_subscores.len() as f64);

        // B. KNOWLEDGE QUALITY
        let sections: Vec<&str> = headings.iter().map(|(_, s)| s.as_str()).collect();
        let is_moc = is_moc_note(&rel_str, &stem, &meta);
        let mut know_subscores: Vec<f64> = Vec::new();
        if is_moc {
            let (moc_links, _) = extract_bracket_tokens(&body, "[[", "]]");
            know_subscores.push((50.0 + moc_links.len() as f64 * 5.0).min(100.0));
        } else {
            let has_summary = sections.iter().any(|s| {
                let l = s.to_lowercase();
                ["sumário", "sumario", "resumo", "overview", "executive", "visão geral", "visao geral"]
                    .iter()
                    .any(|kw| l.contains(kw))
            });
            let has_technical_core = sections.len() >= 3 || words_count >= 250;
            let has_takeaways = sections.iter().any(|s| {
                let l = s.to_lowercase();
                [
                    "takeaway",
                    "glossário",
                    "glossario",
                    "cues",
                    "questões",
                    "questoes",
                    "conclusão",
                    "conclusao",
                    "ações",
                    "acoes",
                    "referências",
                    "referencias",
                    "trade-offs",
                ]
                .iter()
                .any(|kw| l.contains(kw))
            });
            let comp_score = 30.0
                + if has_summary { 25.0 } else { 0.0 }
                + if has_technical_core { 25.0 } else { 0.0 }
                + if has_takeaways { 20.0 } else { 0.0 };
            know_subscores.push(comp_score);
            if comp_score < 75.0 {
                let sample: Vec<&str> = sections.iter().copied().take(3).collect();
                findings.push(json!({
                    "category": "Knowledge Quality",
                    "dimension": "Completeness",
                    "what_is_missing": "Estrutura conceptual completa (Sumário, Desenvolvimento e Síntese/Conclusão)",
                    "why_it_matters": "A nota carece de auto-suficiência pedagógica e analítica",
                    "evidence_supporting_finding": format!("{} secções presentes: {:?}", sections.len(), sample),
                    "recommended_improvement": "Expandir a nota com sumário executivo e secção de síntese",
                }));
            }
        }
        let avg_para_len = if paragraphs.is_empty() {
            0.0
        } else {
            paragraphs
                .iter()
                .map(|p| p.split_whitespace().count() as f64)
                .sum::<f64>()
                / paragraphs.len() as f64
        };
        let depth_score = (35.0
            + (paragraphs.len() as f64 * 6.0).min(40.0)
            + if (20.0..=120.0).contains(&avg_para_len) {
                25.0
            } else {
                10.0
            })
        .min(100.0);
        know_subscores.push(depth_score);
        let knowledge_quality =
            round1(know_subscores.iter().sum::<f64>() / know_subscores.len() as f64);

        // C. EVIDENCE QUALITY
        let raw_source_type = extract_meta_str(&meta, &["source_type", "provenance"])
            .unwrap_or("")
            .to_ascii_uppercase();
        let citations_present = has_formal_citations(&body);
        let footnotes_present = has_footnotes(&body);
        let has_source_doc = meta_has_truthy(&meta, &["source_document_ids", "source_notes"]);
        let gen_mode = meta.get("generation_mode").and_then(Value::as_str);

        let (ev_score, epistemic_class, verif_basis) =
            if matches!(raw_source_type.as_str(), "RFC" | "NIST" | "FIPS" | "PAPER" | "PRIMARY_SOURCE") {
                if citations_present {
                    (95.0, "VERIFIED_PRIMARY_SOURCE", "PRIMARY_STANDARD_WITH_FORMAL_CITATIONS")
                } else {
                    (80.0, "VERIFIED_PRIMARY_SOURCE", "PRIMARY_STANDARD_DECLARATION")
                }
            } else if gen_mode == Some("LLM_GROUNDED") && citations_present {
                (85.0, "GROUNDED_STUDY_SYNTHESIS", "GROUNDED_MODEL_SYNTHESIS_WITH_EVIDENCE_ANCHORS")
            } else if matches!(raw_source_type.as_str(), "JARVIS_INTERNAL" | "LESSON" | "ADR")
                || has_source_doc
            {
                (
                    if citations_present { 75.0 } else { 65.0 },
                    "INTERNAL_ENGINEERING_SPEC",
                    "INTERNAL_ENGINEERING_SPECIFICATION",
                )
            } else if gen_mode == Some("EXTRACTIVE_GROUNDED") {
                (60.0, "EXTRACTIVE_TRANSCRIPTION", "RAW_LECTURE_OR_OCR_TRANSCRIPTION")
            } else {
                if raw_source_type.is_empty() {
                    findings.push(json!({
                        "category": "Evidence Quality",
                        "dimension": "Provenance",
                        "what_is_missing": "Proveniência de fonte não identificada nos metadados",
                        "why_it_matters": "Não é possível rastrear a origem do conteúdo",
                        "evidence_supporting_finding": "Frontmatter não declara 'source_type' nem 'provenance'",
                        "recommended_improvement": "Adicionar proveniência ou ligar a documento fonte",
                    }));
                }
                findings.push(json!({
                    "category": "Evidence Quality",
                    "dimension": "Factual Grounding",
                    "what_is_missing": "Citações formais de evidência [E#], RFC, DOI ou normas",
                    "why_it_matters": "Afirmações sem âncora textual enfraquecem o rigor epistémico do grafo",
                    "evidence_supporting_finding": "Ausência de marcadores de citação ou proveniência documental",
                    "recommended_improvement": "Ancorar as afirmações centrais em especificações ou fontes primárias",
                }));
                (
                    if footnotes_present { 40.0 } else { 25.0 },
                    "UNVERIFIED_HEURISTIC",
                    "UNVERIFIED_HEURISTIC_CONTENT",
                )
            };
        let evidence_quality = round1(ev_score);

        // D. GRAPH QUALITY
        let link_analysis = extract_markdown_links(&content);
        let mut outgoing_valid = 0usize;
        let mut outgoing_broken = 0usize;
        for wl in &link_analysis.wikilinks {
            let head = wl
                .split('|')
                .next()
                .unwrap_or("")
                .split('#')
                .next()
                .unwrap_or("")
                .trim();
            let t_clean = strip_md_suffix_ci(head).to_lowercase();
            if t_clean.is_empty() {
                continue;
            }
            let md_rel = format!("{t_clean}.md");
            if self.canonical_notes.contains_key(&t_clean)
                || self.canonical_rel_paths.contains_key(&t_clean)
                || self.canonical_rel_paths.contains_key(&md_rel)
                || self.alias_map.contains_key(&t_clean)
            {
                outgoing_valid += 1;
            } else {
                outgoing_broken += 1;
            }
        }

        let graph_score = if is_moc {
            if outgoing_valid >= 5 { 100.0 } else { 70.0 }
        } else if outgoing_valid == 0 {
            findings.push(json!({
                "category": "Graph Quality",
                "dimension": "Connectivity",
                "what_is_missing": "Wikilinks para outras notas conceituais do cofre",
                "why_it_matters": "A nota funciona como um silo isolado no grafo",
                "evidence_supporting_finding": "Zero wikilinks válidos encontrados no corpo da nota",
                "recommended_improvement": "Estabelecer 2 a 4 ligações com conceitos ou MOCs relevantes",
            }));
            25.0
        } else if outgoing_valid == 1
            && link_analysis.wikilinks.iter().any(|l| l.contains("Index"))
        {
            findings.push(json!({
                "category": "Graph Quality",
                "dimension": "MOC-Only Clustering",
                "what_is_missing": "Ligações entre pares conceptuais (peer-to-peer links)",
                "why_it_matters": "A conexão exclusiva a um índice MOC afasta a nota para a periferia do grafo",
                "evidence_supporting_finding": "Apenas ligada a um índice geral sem ligações horizontais",
                "recommended_improvement": "Estabelecer relações tipadas com notas técnicas afins",
            }));
            50.0
        } else {
            let base = 70.0 + (outgoing_valid as f64 * 6.0).min(30.0);
            let penalty = outgoing_broken as f64 * 15.0;
            (base - penalty).max(20.0)
        };
        let graph_quality = round1(graph_score);

        // UNIQUENESS
        let stem_lower = stem.to_lowercase();
        let mut duplicate_candidates = Vec::new();
        for (other_stem, other_path) in &self.canonical_notes {
            if other_stem != &stem_lower && other_path != &full_path {
                let ratio = sequence_similarity(&stem_lower, other_stem);
                if ratio > 0.88 {
                    if let Some(name) = other_path.file_name().and_then(|s| s.to_str()) {
                        duplicate_candidates.push(name.to_string());
                    }
                }
            }
        }
        let uniqueness_score = if duplicate_candidates.is_empty() { 100.0 } else { 55.0 };
        if !duplicate_candidates.is_empty() {
            let preview: Vec<String> = duplicate_candidates.iter().take(2).cloned().collect();
            findings.push(json!({
                "category": "Knowledge Quality",
                "dimension": "Uniqueness",
                "what_is_missing": "Diferenciação clara em relação a nota com título similar",
                "why_it_matters": "Cria nós quase-duplicados e fragmenta o grafo",
                "evidence_supporting_finding": format!("Sobreposição com: {preview:?}"),
                "recommended_improvement": "Consolidar ou clarificar distinção de âmbito",
            }));
        }

        // FRESHNESS
        let raw_date = extract_meta_str(&meta, &["updated_at", "last_modified", "date"]);
        let mut freshness_status = "UNKNOWN";
        let mut freshness_val = "NOT_DOCUMENTED_IN_METADATA".to_string();
        if let Some(date_str) = raw_date {
            if let Some(parsed_dt) = parse_freshness_date(date_str) {
                freshness_status = "MEASURED";
                let days_since = Local::now()
                    .naive_local()
                    .signed_duration_since(parsed_dt)
                    .num_days()
                    .max(0);
                freshness_val = format!("{date_str} ({days_since} dias atrás)");
            } else {
                freshness_val = format!("UNPARSEABLE_DATE_FORMAT: {date_str}");
            }
        }

        let overall_score = round1(
            (structural_quality * 0.25)
                + (knowledge_quality * 0.30)
                + (evidence_quality * 0.25)
                + (graph_quality * 0.20),
        );

        Ok(json!({
            "rel_path": rel_str,
            "stem": stem,
            "overall_score": overall_score,
            "score_type": "HEURISTIC",
            "calculation_method": "FOUR_CATEGORY_MULTI_DIMENSIONAL_V2",
            "scoring_formula": "structural_quality * 0.25 + knowledge_quality * 0.30 + evidence_quality * 0.25 + graph_quality * 0.20",
            "epistemic_classification": epistemic_class,
            "verification_basis": verif_basis,
            "categories": {
                "structural_quality": structural_quality,
                "knowledge_quality": knowledge_quality,
                "evidence_quality": evidence_quality,
                "graph_quality": graph_quality,
            },
            "dimension_scores": {
                "provenance": evidence_quality,
                "factual_grounding": evidence_quality,
                "completeness": knowledge_quality,
                "technical_depth": knowledge_quality,
                "structural_quality": structural_quality,
                "graph_quality": graph_quality,
            },
            "uniqueness": {
                "evaluated": true,
                "score": uniqueness_score,
                "duplicate_candidates": duplicate_candidates,
            },
            "freshness": freshness_status,
            "freshness_value": freshness_val,
            "word_count": words_count,
            "outgoing_valid_links": outgoing_valid,
            "outgoing_broken_links": outgoing_broken,
            "code_examples_ignored_count": link_analysis.code_examples_ignored.len(),
            "findings_count": findings.len(),
            "findings": findings,
            "needs_improvement": overall_score < 75.0 || !findings.is_empty(),
        }))
    }

    fn infer_relationship_type(
        &self,
        source_or_type: &str,
        target_or_context: &str,
        context_window: &str,
    ) -> &'static str {
        let combined =
            format!("{source_or_type} {target_or_context} {context_window}").to_lowercase();
        if ["prerequisito", "pré-requisito", "prerequisite", "depende de", "baseia-se em"]
            .iter()
            .any(|w| combined.contains(w))
        {
            return "PREREQUISITE_OF";
        }
        if ["estende", "expansão", "adiciona", "extends"]
            .iter()
            .any(|w| combined.contains(w))
        {
            return "EXTENDS";
        }
        if ["evidência", "comprova", "suporta", "fundamenta", "supports"]
            .iter()
            .any(|w| combined.contains(w))
        {
            return "SUPPORTS";
        }
        if ["versus", "em contraste", "contrasta com", "contrasts", "trade-off"]
            .iter()
            .any(|w| combined.contains(w))
        {
            return "CONTRASTS_WITH";
        }
        if ["aplica-se a", "utilizado em", "implementado em", "applies"]
            .iter()
            .any(|w| combined.contains(w))
        {
            return "APPLIES_TO";
        }
        if ["exemplo", "caso de estudo", "instância", "example"]
            .iter()
            .any(|w| combined.contains(w))
        {
            return "EXAMPLE_OF";
        }

        match source_or_type.to_lowercase().as_str() {
            "standard" | "protocol" | "cryptography" => "SUPPORTS",
            "architecture" | "database" => "APPLIES_TO",
            "theory" => "PREREQUISITE_OF",
            "subsystem" => "EXTENDS",
            _ => "RELATED_TO",
        }
    }

    fn generate_justification(source_stem: &str, target_stem: &str, rel_type: &str) -> String {
        match rel_type {
            "PREREQUISITE_OF" => format!(
                "'{source_stem}' constitui pré-requisito teórico ou fundação conceptual para '{target_stem}'"
            ),
            "EXTENDS" => {
                format!("'{source_stem}' expande as capacidades fundamentadas em '{target_stem}'")
            }
            "SUPPORTS" => format!(
                "'{source_stem}' fundamenta empiricamente a decisão em '{target_stem}'"
            ),
            "CONTRASTS_WITH" => format!(
                "'{source_stem}' apresenta trade-off comparativo em relação a '{target_stem}'"
            ),
            "APPLIES_TO" => {
                format!("'{source_stem}' aplica na prática os princípios de '{target_stem}'")
            }
            "EXAMPLE_OF" => {
                format!("'{source_stem}' funciona como instância demonstrativa de '{target_stem}'")
            }
            _ => format!("Associação semântica contextual entre '{source_stem}' e '{target_stem}'"),
        }
    }

    /// Resolves a concept string to a curated typed relationship when eligible.
    pub fn resolve_concept_link(
        &self,
        concept: &str,
        source_stem: &str,
        context_window: &str,
    ) -> Option<Value> {
        let c_norm = concept.trim().to_lowercase();
        if c_norm.is_empty()
            || matches!(
                c_norm.as_str(),
                "para" | "com" | "de" | "por" | "em" | "um" | "uma" | "o" | "a" | "os" | "as"
            )
        {
            return None;
        }

        if let Some(target_path) = self.canonical_notes.get(&c_norm) {
            let target_stem = path_stem_str(target_path);
            if target_stem != source_stem {
                let rel_type =
                    self.infer_relationship_type(source_stem, &target_stem, context_window);
                let justification =
                    Self::generate_justification(source_stem, &target_stem, rel_type);
                return Some(json!({
                    "source_note": source_stem,
                    "target_note": target_stem,
                    "relationship_type": rel_type,
                    "justification": justification,
                    "confidence": 0.95,
                    "creation_method": "CANONICAL_TITLE_MATCH",
                    "validation_status": "VALIDATED",
                }));
            }
        }

        if let Some(alias_stem) = self.alias_map.get(&c_norm) {
            if alias_stem != source_stem {
                let rel_type =
                    self.infer_relationship_type(source_stem, alias_stem, context_window);
                let justification =
                    Self::generate_justification(source_stem, alias_stem, rel_type);
                return Some(json!({
                    "source_note": source_stem,
                    "target_note": alias_stem,
                    "relationship_type": rel_type,
                    "justification": justification,
                    "confidence": 0.90,
                    "creation_method": "YAML_ALIAS_MATCH",
                    "validation_status": "VALIDATED",
                }));
            }
        }

        for entry in CONCEPT_SYNONYM_REGISTRY {
            if c_norm == entry.key || entry.synonyms.iter().any(|s| *s == c_norm) {
                let target_stem = entry.canonical_note;
                if target_stem != source_stem {
                    let rel_type = self.infer_relationship_type(
                        entry.concept_type,
                        target_stem,
                        context_window,
                    );
                    let justification =
                        Self::generate_justification(source_stem, target_stem, rel_type);
                    return Some(json!({
                        "source_note": source_stem,
                        "target_note": target_stem,
                        "relationship_type": rel_type,
                        "justification": justification,
                        "confidence": 0.95,
                        "creation_method": "DETERMINISTIC_CURATED_SYNONYM",
                        "validation_status": "VALIDATED",
                    }));
                }
            }
        }
        None
    }

    fn save_proposal_file(&self, proposal_id: &str, payload: &Value) -> Result<(), KnowledgeError> {
        let filename = format!("{proposal_id}.json");
        let serialized = serde_json::to_string_pretty(payload)
            .map_err(|e| KnowledgeError::Internal(format!("Serialize proposal failed: {e}")))?;
        atomic_write_string(&self.proposals_dir, &self.proposals_dir.join(&filename), &serialized)
            .map_err(|e| KnowledgeError::Internal(e.message))?;
        Ok(())
    }

    /// Deterministically enriches a vault note with conservative frontmatter & typed ontology links.
    pub fn enrich_note_safely(
        &mut self,
        rel_path: &str,
        auto_apply: bool,
    ) -> Result<Value, KnowledgeError> {
        let full_path = self.resolve_contained_note_path(rel_path)?;
        let rel_str = self.rel_str_for(&full_path)?;
        let stem = path_stem_str(&full_path);
        let rel_path_hash = sha256_hex(rel_str.as_bytes())[..8].to_string();

        let original_bytes = fs::read(&full_path)
            .map_err(|e| KnowledgeError::Internal(format!("Falha ao ler nota: {e}")))?;
        let orig_sha = sha256_hex(&original_bytes);
        let original_text = String::from_utf8_lossy(&original_bytes).into_owned();
        let (meta, body) = parse_frontmatter(&original_text);

        let mut proposed_relationships: Vec<Value> = Vec::new();
        let enriched_frontmatter = if meta.is_empty() {
            let domain = rel_str
                .split('/')
                .next()
                .filter(|_| rel_str.contains('/'))
                .unwrap_or("general")
                .to_string();
            let tag = domain.to_lowercase().replace(' ', "-");
            let mut fm = BTreeMap::new();
            fm.insert("confidence".to_string(), json!("unknown"));
            fm.insert("domain".to_string(), json!(domain));
            fm.insert("provenance".to_string(), json!("UNDECLARED"));
            fm.insert("status".to_string(), json!("needs_review"));
            fm.insert("tags".to_string(), json!([tag]));
            fm.insert("type".to_string(), json!("atomic_note"));
            fm
        } else {
            meta
        };

        let ctx_preview: String = body.chars().take(500).collect();
        for entry in CONCEPT_SYNONYM_REGISTRY {
            if entry.canonical_note == stem {
                continue;
            }
            for &syn in std::iter::once(&entry.key).chain(entry.synonyms.iter()) {
                if contains_word_ci(&body, syn) {
                    if let Some(resolved) =
                        self.resolve_concept_link(syn, &stem, &ctx_preview)
                    {
                        let target_name = resolved
                            .get("target_note")
                            .and_then(Value::as_str)
                            .unwrap_or("");
                        if !proposed_relationships.iter().any(|r| {
                            r.get("target_note").and_then(Value::as_str) == Some(target_name)
                        }) {
                            proposed_relationships.push(resolved);
                        }
                    }
                    break;
                }
            }
        }

        let new_body = if !proposed_relationships.is_empty()
            && !body.contains("## 🔗 Grafo de Conhecimento")
            && !body.contains("## 🔗 Referências")
        {
            let mut links_block = vec![
                String::new(),
                "---".to_string(),
                String::new(),
                "## 🔗 Grafo de Conhecimento & Relações Tipadas".to_string(),
            ];
            for rel in proposed_relationships.iter().take(4) {
                let r_type = rel.get("relationship_type").and_then(Value::as_str).unwrap_or("RELATED_TO");
                let r_target = rel.get("target_note").and_then(Value::as_str).unwrap_or("");
                let r_just = rel.get("justification").and_then(Value::as_str).unwrap_or("");
                links_block.push(format!("- **{r_type}** ➔ [[{r_target}]] — *{r_just}*"));
            }
            format!("{}\n{}\n", body.trim_end(), links_block.join("\n"))
        } else {
            body
        };

        let enriched_text = format_frontmatter_and_body(&enriched_frontmatter, &new_body);
        let proposal_id = format!(
            "prop_{}_{}_{}",
            rel_path_hash,
            now_unix_nanos(),
            &Uuid::new_v4().simple().to_string()[..6]
        );

        let backup_path = if auto_apply {
            let write_res =
                self.atomic_write_note(&rel_str, &enriched_text, Some(&orig_sha), true)?;
            write_res["backup_snapshot"]["snapshot_path"]
                .as_str()
                .unwrap_or("")
                .to_string()
        } else {
            String::new()
        };

        let proposal_payload = json!({
            "proposal_id": proposal_id,
            "rel_path": rel_str,
            "stem": stem,
            "model_provider": "deterministic",
            "model_name": "synonym_registry_v2",
            "backup_path": backup_path,
            "proposed_relationships": proposed_relationships,
            "original_length": original_text.len(),
            "enriched_length": enriched_text.len(),
            "status": if auto_apply { "APPLIED" } else { "PROPOSED" },
            "created_at": now_iso_local(),
        });
        self.save_proposal_file(&proposal_id, &proposal_payload)?;
        Ok(proposal_payload)
    }

    pub fn load_queue(&self) -> Vec<Value> {
        let Ok(raw) = fs::read_to_string(&self.queue_file) else {
            return Vec::new();
        };
        serde_json::from_str::<Vec<Value>>(&raw).unwrap_or_default()
    }

    pub fn save_queue(&self, queue: &[Value]) -> Result<(), KnowledgeError> {
        let serialized = serde_json::to_string_pretty(queue)
            .map_err(|e| KnowledgeError::Internal(format!("Serialize queue failed: {e}")))?;
        atomic_write_string(&self.data_dir, &self.queue_file, &serialized)
            .map_err(|e| KnowledgeError::Internal(e.message))?;
        Ok(())
    }

    pub fn populate_improvement_queue(&mut self) -> Result<Vec<Value>, KnowledgeError> {
        self.refresh_vault_catalogs();
        let unique_paths: Vec<PathBuf> = self
            .canonical_notes
            .values()
            .cloned()
            .collect::<HashSet<_>>()
            .into_iter()
            .collect();
        let mut queue: Vec<Value> = Vec::new();
        for note_path in unique_paths {
            let Ok(rel_str) = self.rel_str_for(&note_path) else {
                continue;
            };
            let Ok(audit) = self.audit_note_quality(&rel_str) else {
                continue;
            };
            if audit["needs_improvement"].as_bool() == Some(true) {
                let overall = audit["overall_score"].as_f64().unwrap_or(0.0);
                let fcount = audit["findings_count"].as_u64().unwrap_or(0) as f64;
                let priority = round1(((100.0 - overall) * 0.7) + (fcount * 5.0));
                let rel_hash = sha256_hex(rel_str.as_bytes())[..8].to_string();
                let ts = now_iso_local();
                queue.push(json!({
                    "item_id": format!("queue_{rel_hash}"),
                    "note_path": rel_str,
                    "stem": audit["stem"],
                    "priority_score": priority,
                    "overall_score": overall,
                    "epistemic_classification": audit["epistemic_classification"],
                    "findings": audit["findings"],
                    "status": "PENDING",
                    "retry_count": 0,
                    "created_at": ts,
                    "updated_at": ts,
                }));
            }
        }
        queue.sort_by(|a, b| {
            let pa = a["priority_score"].as_f64().unwrap_or(0.0);
            let pb = b["priority_score"].as_f64().unwrap_or(0.0);
            pb.partial_cmp(&pa).unwrap_or(std::cmp::Ordering::Equal)
        });
        self.save_queue(&queue)?;
        Ok(queue)
    }

    pub fn get_worker_state(&self) -> Value {
        let mut state = json!({
            "is_paused": false,
            "is_running": false,
            "active_item_id": Value::Null,
            "items_processed": 0,
            "auto_mode_enabled": false,
            "last_model_used": Value::Null,
            "last_batch_result": Value::Null,
            "last_run_timestamp": Value::Null,
        });
        if let Ok(raw) = fs::read_to_string(&self.worker_state_file) {
            if let Ok(Value::Object(parsed)) = serde_json::from_str::<Value>(&raw) {
                if let Some(obj) = state.as_object_mut() {
                    for (k, v) in parsed {
                        obj.insert(k, v);
                    }
                }
            }
        }
        state
    }

    pub fn save_worker_state(&self, state: &Value) -> Result<(), KnowledgeError> {
        let serialized = serde_json::to_string_pretty(state)
            .map_err(|e| KnowledgeError::Internal(format!("Serialize worker state failed: {e}")))?;
        atomic_write_string(&self.data_dir, &self.worker_state_file, &serialized)
            .map_err(|e| KnowledgeError::Internal(e.message))?;
        Ok(())
    }

    pub fn pause_queue_worker(&self) -> Result<Value, KnowledgeError> {
        let mut state = self.get_worker_state();
        if let Some(obj) = state.as_object_mut() {
            obj.insert("is_paused".to_string(), json!(true));
            obj.insert("updated_at".to_string(), json!(now_iso_local()));
        }
        self.save_worker_state(&state)?;
        Ok(state)
    }

    pub fn resume_queue_worker(&self) -> Result<Value, KnowledgeError> {
        let mut state = self.get_worker_state();
        if let Some(obj) = state.as_object_mut() {
            obj.insert("is_paused".to_string(), json!(false));
            obj.insert("updated_at".to_string(), json!(now_iso_local()));
        }
        self.save_worker_state(&state)?;
        Ok(state)
    }

    pub fn get_worker_status(&self) -> Value {
        let queue = self.load_queue();
        let state = self.get_worker_state();
        let count_status = |targets: &[&str]| -> usize {
            queue
                .iter()
                .filter(|q| {
                    q.get("status")
                        .and_then(Value::as_str)
                        .map(|s| targets.contains(&s))
                        .unwrap_or(false)
                })
                .count()
        };
        json!({
            "is_paused": state.get("is_paused").and_then(Value::as_bool).unwrap_or(false),
            "is_running": state.get("is_running").and_then(Value::as_bool).unwrap_or(false),
            "active_item_id": state.get("active_item_id").cloned().unwrap_or(Value::Null),
            "items_processed": state.get("items_processed").and_then(Value::as_u64).unwrap_or(0),
            "auto_mode_enabled": state.get("auto_mode_enabled").and_then(Value::as_bool).unwrap_or(false),
            "last_model_used": state.get("last_model_used").cloned().unwrap_or(Value::Null),
            "last_batch_result": state.get("last_batch_result").cloned().unwrap_or(Value::Null),
            "queue_total": queue.len(),
            "pending_count": count_status(&["PENDING"]),
            "applied_count": count_status(&["APPLIED"]),
            "proposals_count": count_status(&["PROPOSAL_CREATED", "AWAITING_REVIEW"]),
            "blocked_count": count_status(&["BLOCKED_BY_ENVIRONMENT"]),
            "reconciliation_count": count_status(&["RECONCILIATION_REQUIRED"]),
            "last_run_timestamp": state.get("last_run_timestamp").cloned().unwrap_or(Value::Null),
        })
    }

    pub fn reconcile_interrupted_queue(&self) -> usize {
        let mut queue = self.load_queue();
        let mut reconciled = 0usize;
        for item in &mut queue {
            if item.get("status").and_then(Value::as_str) == Some("IN_PROGRESS") {
                if let Some(obj) = item.as_object_mut() {
                    obj.insert("status".to_string(), json!("RECONCILIATION_REQUIRED"));
                    obj.insert(
                        "reconciliation_reason".to_string(),
                        json!("Processo interrompido durante execução anterior detetado no arranque."),
                    );
                    obj.insert("updated_at".to_string(), json!(now_iso_local()));
                }
                reconciled += 1;
            }
        }
        if reconciled > 0 {
            let _ = self.save_queue(&queue);
        }
        reconciled
    }

    async fn check_ollama_qwen_available(&self) -> bool {
        if matches!(
            std::env::var("JARVIS_SKIP_OLLAMA_PROBE").ok().as_deref(),
            Some("1") | Some("true")
        ) {
            return false;
        }
        let Ok(Ok(mut stream)) = timeout(
            Duration::from_millis(400),
            TcpStream::connect("127.0.0.1:11434"),
        )
        .await
        else {
            return false;
        };
        let req = "GET /api/tags HTTP/1.1\r\nHost: 127.0.0.1:11434\r\nConnection: close\r\n\r\n";
        if stream.write_all(req.as_bytes()).await.is_err() {
            return false;
        }
        let mut buf = Vec::with_capacity(8192);
        let Ok(Ok(_)) = timeout(Duration::from_millis(600), stream.read_to_end(&mut buf)).await
        else {
            return false;
        };
        let raw = String::from_utf8_lossy(&buf);
        let Some((_, body)) = raw.split_once("\r\n\r\n") else {
            return false;
        };
        let Ok(parsed) = serde_json::from_str::<Value>(body) else {
            return false;
        };
        parsed
            .get("models")
            .and_then(Value::as_array)
            .map(|models| {
                models.iter().any(|m| {
                    m.get("name")
                        .and_then(Value::as_str)
                        .map(|n| n.to_ascii_lowercase().starts_with("qwen"))
                        .unwrap_or(false)
                })
            })
            .unwrap_or(false)
    }

    async fn execute_qwen_knowledge_improvement(&self, rel_path: &str) -> Result<Value, KnowledgeError> {
        let full_path = self.resolve_contained_note_path(rel_path)?;
        let rel_str = self.rel_str_for(&full_path)?;
        let stem = path_stem_str(&full_path);
        let rel_path_hash = sha256_hex(rel_str.as_bytes())[..8].to_string();
        let bytes = fs::read(&full_path)
            .map_err(|e| KnowledgeError::Internal(format!("Falha ao ler nota: {e}")))?;
        let orig_sha = sha256_hex(&bytes);
        let content_text = String::from_utf8_lossy(&bytes).into_owned();

        let body_snippet: String = content_text.chars().take(3000).collect();
        let sys_prompt = "És o motor de melhoria conceptual de notas do JARVIS OS. Responde EXCLUSIVAMENTE em JSON com 'substantive_addition', 'mechanisms_and_tradeoffs', 'evidence_anchors', 'jarvis_linkage' e 'suggested_typed_relationships'.";
        let user_prompt = format!("Nota: '{stem}' ({rel_str})\n<note_content>\n{body_snippet}\n</note_content>");

        let chat_body = json!({
            "model": "qwen3.5:9b",
            "stream": false,
            "format": "json",
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt},
            ],
        })
        .to_string();

        let http_req = format!(
            "POST /api/chat HTTP/1.1\r\nHost: 127.0.0.1:11434\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}",
            chat_body.len(),
            chat_body
        );

        let mut stream = timeout(Duration::from_secs(2), TcpStream::connect("127.0.0.1:11434"))
            .await
            .map_err(|_| KnowledgeError::Internal("Timeout connecting to Ollama".to_string()))?
            .map_err(|e| KnowledgeError::Internal(format!("Ollama connect failed: {e}")))?;

        stream
            .write_all(http_req.as_bytes())
            .await
            .map_err(|e| KnowledgeError::Internal(format!("Ollama write failed: {e}")))?;

        let mut resp_buf = Vec::with_capacity(32768);
        timeout(Duration::from_secs(30), stream.read_to_end(&mut resp_buf))
            .await
            .map_err(|_| KnowledgeError::Internal("Ollama response timeout".to_string()))?
            .map_err(|e| KnowledgeError::Internal(format!("Ollama read failed: {e}")))?;

        let raw = String::from_utf8_lossy(&resp_buf);
        let (_, http_body) = raw
            .split_once("\r\n\r\n")
            .ok_or_else(|| KnowledgeError::Internal("Invalid HTTP response from Ollama".to_string()))?;
        let resp_json: Value = serde_json::from_str(http_body)
            .map_err(|e| KnowledgeError::Internal(format!("Ollama JSON parse failed: {e}")))?;
        let msg_content = resp_json["message"]["content"]
            .as_str()
            .unwrap_or("{}")
            .trim()
            .to_string();
        let parsed: Value = serde_json::from_str(&msg_content).unwrap_or_else(|_| json!({}));

        let addition = parsed["substantive_addition"].as_str().unwrap_or("").trim().to_string();
        let mechanisms: Vec<String> = parsed["mechanisms_and_tradeoffs"]
            .as_array()
            .map(|a| a.iter().filter_map(|v| v.as_str().map(String::from)).collect())
            .unwrap_or_default();
        let anchors = parsed["evidence_anchors"].as_array().cloned().unwrap_or_default();
        let linkage = parsed["jarvis_linkage"].as_str().unwrap_or("").to_string();
        let suggested_rels = parsed["suggested_typed_relationships"]
            .as_array()
            .cloned()
            .unwrap_or_default();

        let (meta, body) = parse_frontmatter(&content_text);
        let enriched_frontmatter = if meta.is_empty() {
            let domain = rel_str
                .split('/')
                .next()
                .filter(|_| rel_str.contains('/'))
                .unwrap_or("general")
                .to_string();
            let mut fm = BTreeMap::new();
            fm.insert("confidence".to_string(), json!("unknown"));
            fm.insert("domain".to_string(), json!(domain));
            fm.insert("provenance".to_string(), json!("UNDECLARED"));
            fm.insert("status".to_string(), json!("needs_review"));
            fm.insert("tags".to_string(), json!([domain.to_lowercase().replace(' ', "-")]));
            fm.insert("type".to_string(), json!("atomic_note"));
            fm
        } else {
            meta
        };

        let mut substantive = vec![
            String::new(),
            "---".to_string(),
            String::new(),
            "## 🧠 Aprofundamento Conceptual & Mecanismos (qwen3.5:9b)".to_string(),
            if addition.is_empty() {
                "Síntese analítica.".to_string()
            } else {
                addition.clone()
            },
        ];
        if !mechanisms.is_empty() {
            substantive.push("\n### ⚖️ Trade-offs & Compromissos de Engenharia".to_string());
            for m in &mechanisms {
                substantive.push(format!("- {m}"));
            }
        }
        if !linkage.is_empty() {
            substantive.push(format!("\n### ⚙️ Alinhamento JARVIS OS\n{linkage}"));
        }
        let new_body = format!("{}\n{}\n", body.trim_end(), substantive.join("\n"));
        let enriched_text = format_frontmatter_and_body(&enriched_frontmatter, &new_body);

        let proposal_id = format!(
            "prop_{}_{}_{}",
            rel_path_hash,
            now_unix_nanos(),
            &Uuid::new_v4().simple().to_string()[..6]
        );
        let evidence_refs: Vec<Value> = anchors
            .iter()
            .filter_map(|a| a.get("source").cloned())
            .collect();
        let has_inference = anchors
            .iter()
            .any(|a| a.get("status").and_then(Value::as_str) == Some("INFERRED"));

        let payload = json!({
            "proposal_id": proposal_id,
            "rel_path": rel_str,
            "stem": stem,
            "original_sha256": orig_sha,
            "proposed_sha256": sha256_hex(enriched_text.as_bytes()),
            "generation_id": format!("gen_qwen_{}", &Uuid::new_v4().simple().to_string()[..8]),
            "model_provider": "ollama",
            "model_name": "qwen3.5:9b",
            "prompt_version": "v2_grounded_qwen",
            "evidence_refs": evidence_refs,
            "proposed_changes": {
                "substantive_addition": addition,
                "mechanisms_and_tradeoffs": mechanisms,
                "evidence_anchors": anchors,
                "jarvis_linkage": linkage,
                "relationships": suggested_rels,
            },
            "validation_results": {
                "claims_evaluated": anchors.len(),
                "has_inference": has_inference,
            },
            "enriched_text": enriched_text,
            "status": "AWAITING_REVIEW",
            "created_at": now_iso_local(),
        });
        self.save_proposal_file(&proposal_id, &payload)?;
        Ok(payload)
    }

    /// Runs a bounded improvement batch `[1..=5]` with pause respect & deterministic fallback.
    pub async fn run_bounded_improvement_batch(
        &mut self,
        batch_size: i64,
    ) -> Result<Vec<Value>, KnowledgeError> {
        let clamped = batch_size.clamp(1, 5) as usize;
        let mut state = self.get_worker_state();
        if state.get("is_paused").and_then(Value::as_bool) == Some(true) {
            return Ok(Vec::new());
        }

        let _ = self.reconcile_interrupted_queue();
        let mut queue = self.load_queue();
        if queue.is_empty() {
            queue = self.populate_improvement_queue()?;
        }

        if let Some(obj) = state.as_object_mut() {
            obj.insert("is_running".to_string(), json!(true));
            obj.insert("last_run_timestamp".to_string(), json!(now_iso_local()));
        }
        self.save_worker_state(&state)?;

        let mut processed_proposals = Vec::new();
        let mut count = 0usize;
        let mut model_used = "deterministic";

        for idx in 0..queue.len() {
            if count >= clamped {
                break;
            }
            if queue[idx].get("status").and_then(Value::as_str) != Some("PENDING") {
                continue;
            }
            if self
                .get_worker_state()
                .get("is_paused")
                .and_then(Value::as_bool)
                == Some(true)
            {
                break;
            }
            let item_path = queue[idx]
                .get("note_path")
                .and_then(Value::as_str)
                .unwrap_or("")
                .to_string();
            let item_id = queue[idx]
                .get("item_id")
                .and_then(Value::as_str)
                .unwrap_or("")
                .to_string();
            if item_path.is_empty() {
                continue;
            }

            if let Some(obj) = queue[idx].as_object_mut() {
                obj.insert("status".to_string(), json!("IN_PROGRESS"));
                obj.insert("updated_at".to_string(), json!(now_iso_local()));
            }
            if let Some(obj) = state.as_object_mut() {
                obj.insert("active_item_id".to_string(), json!(item_id));
            }
            let _ = self.save_queue(&queue);
            let _ = self.save_worker_state(&state);

            let ollama_ok = self.check_ollama_qwen_available().await;
            if ollama_ok {
                match self.execute_qwen_knowledge_improvement(&item_path).await {
                    Ok(proposal) => {
                        let status = proposal["status"]
                            .as_str()
                            .unwrap_or("AWAITING_REVIEW")
                            .to_string();
                        let pid = proposal["proposal_id"].clone();
                        if let Some(obj) = queue[idx].as_object_mut() {
                            obj.insert("status".to_string(), json!(status));
                            obj.insert("proposal_id".to_string(), pid);
                            obj.insert("updated_at".to_string(), json!(now_iso_local()));
                        }
                        processed_proposals.push(proposal);
                        model_used = "qwen3.5:9b";
                    }
                    Err(err) => {
                        if let Some(obj) = queue[idx].as_object_mut() {
                            obj.insert("status".to_string(), json!("FAILED_VALIDATION"));
                            obj.insert("error".to_string(), json!(err.to_string()));
                            obj.insert("updated_at".to_string(), json!(now_iso_local()));
                        }
                        processed_proposals.push(json!({
                            "status": "FAILED_VALIDATION",
                            "item_id": item_id,
                            "note_path": item_path,
                            "error": err.to_string(),
                            "model_provider": "ollama",
                            "model_name": "qwen3.5:9b",
                        }));
                    }
                }
            } else {
                let proposal = self.enrich_note_safely(&item_path, true)?;
                let pid = proposal["proposal_id"].clone();
                if let Some(obj) = queue[idx].as_object_mut() {
                    obj.insert("status".to_string(), json!("APPLIED"));
                    obj.insert("proposal_id".to_string(), pid);
                    obj.insert("updated_at".to_string(), json!(now_iso_local()));
                }
                processed_proposals.push(proposal);
                model_used = "deterministic_fallback";
            }

            count += 1;
            let prev = state
                .get("items_processed")
                .and_then(Value::as_u64)
                .unwrap_or(0);
            if let Some(obj) = state.as_object_mut() {
                obj.insert("items_processed".to_string(), json!(prev + 1));
            }
        }

        let _ = self.save_queue(&queue);
        if let Some(obj) = state.as_object_mut() {
            obj.insert("is_running".to_string(), json!(false));
            obj.insert("active_item_id".to_string(), Value::Null);
            obj.insert("last_model_used".to_string(), json!(model_used));
            obj.insert(
                "last_batch_result".to_string(),
                json!({
                    "count": count,
                    "model": model_used,
                    "timestamp": now_iso_local(),
                }),
            );
        }
        self.save_worker_state(&state)?;
        Ok(processed_proposals)
    }

    fn collect_all_vault_assets(&self) -> HashSet<String> {
        let mut assets = HashSet::new();
        let mut stack = vec![self.vault_root.clone()];
        while let Some(dir) = stack.pop() {
            let Ok(entries) = fs::read_dir(&dir) else {
                continue;
            };
            for entry in entries.flatten() {
                let path = entry.path();
                let Ok(meta) = fs::symlink_metadata(&path) else {
                    continue;
                };
                if meta.file_type().is_symlink() {
                    continue;
                }
                let name = entry.file_name().to_string_lossy().to_string();
                if meta.is_dir() {
                    if name == ".obsidian" || name == ".history" {
                        continue;
                    }
                    stack.push(path);
                } else if meta.is_file() {
                    assets.insert(name.to_lowercase());
                    if let Ok(rel) = path.strip_prefix(&self.vault_root) {
                        assets.insert(rel.to_string_lossy().replace('\\', "/").to_lowercase());
                    }
                }
            }
        }
        assets
    }

    /// Computes two-pass real filesystem graph diagnostics & persists `graph_diagnostics.json`.
    pub fn compute_graph_diagnostics(&mut self) -> Result<Value, KnowledgeError> {
        self.refresh_vault_catalogs();

        let unique_notes: Vec<PathBuf> = self
            .canonical_notes
            .values()
            .cloned()
            .collect::<HashSet<_>>()
            .into_iter()
            .collect();

        let mut outgoing_map: HashMap<String, Vec<String>> = HashMap::new();
        let mut incoming_map: HashMap<String, Vec<String>> = HashMap::new();
        let mut stem_to_rel: HashMap<String, String> = HashMap::new();
        let mut lower_rel_to_rel: HashMap<String, String> = HashMap::new();

        for p in &unique_notes {
            let Ok(rel) = self.rel_str_for(p) else {
                continue;
            };
            outgoing_map.insert(rel.clone(), Vec::new());
            incoming_map.insert(rel.clone(), Vec::new());
            stem_to_rel.insert(path_stem_str(p).to_lowercase(), rel.clone());
            lower_rel_to_rel.insert(rel.to_lowercase(), rel.clone());
        }

        let asset_files = self.collect_all_vault_assets();
        let mut broken_links_list: Vec<Value> = Vec::new();
        let mut missing_attachments_list: Vec<Value> = Vec::new();
        let mut scores: Vec<f64> = Vec::new();
        let mut score_map: HashMap<String, f64> = HashMap::new();
        let mut code_examples_ignored_total = 0usize;

        for note_file in &unique_notes {
            let Ok(rel_str) = self.rel_str_for(note_file) else {
                continue;
            };
            let content = fs::read_to_string(note_file).unwrap_or_default();

            if let Ok(audit) = self.audit_note_quality(&rel_str) {
                if let Some(sc) = audit["overall_score"].as_f64() {
                    scores.push(sc);
                    score_map.insert(rel_str.clone(), sc);
                }
            }

            let analysis = extract_markdown_links(&content);
            code_examples_ignored_total += analysis.code_examples_ignored.len();

            for emb in &analysis.embeds {
                let emb_clean = emb
                    .split('|')
                    .next()
                    .unwrap_or("")
                    .split('#')
                    .next()
                    .unwrap_or("")
                    .trim()
                    .to_lowercase();
                if !asset_files.contains(&emb_clean) && !self.canonical_notes.contains_key(&emb_clean)
                {
                    missing_attachments_list.push(json!({ "source": rel_str, "target": emb }));
                }
            }

            for wl in &analysis.wikilinks {
                let head = wl
                    .split('|')
                    .next()
                    .unwrap_or("")
                    .split('#')
                    .next()
                    .unwrap_or("")
                    .trim();
                let target_clean = strip_md_suffix_ci(head).to_lowercase();
                if target_clean.is_empty() {
                    continue;
                }
                let md_candidate = format!("{target_clean}.md");
                let dest_rel = lower_rel_to_rel
                    .get(&target_clean)
                    .or_else(|| lower_rel_to_rel.get(&md_candidate))
                    .or_else(|| {
                        self.alias_map
                            .get(&target_clean)
                            .and_then(|st| stem_to_rel.get(&st.to_lowercase()))
                    })
                    .or_else(|| stem_to_rel.get(&target_clean))
                    .cloned();

                if let Some(dest) = dest_rel {
                    if let Some(out) = outgoing_map.get_mut(&rel_str) {
                        out.push(dest.clone());
                    }
                    if let Some(inc) = incoming_map.get_mut(&dest) {
                        inc.push(rel_str.clone());
                    }
                } else {
                    broken_links_list.push(json!({ "source": rel_str, "target": wl }));
                }
            }
        }

        // Pass 2
        let mut genuine_orphans = Vec::new();
        let mut moc_only_notes = Vec::new();
        let mut hubs = Vec::new();
        let total_outgoing: usize = outgoing_map.values().map(Vec::len).sum();
        let total_incoming: usize = incoming_map.values().map(Vec::len).sum();

        for (rel_str, out_edges) in &outgoing_map {
            let empty = Vec::new();
            let in_edges = incoming_map.get(rel_str).unwrap_or(&empty);
            let degree = out_edges.len() + in_edges.len();
            if degree >= 15 {
                hubs.push(rel_str.clone());
            }

            let rel_lower = rel_str.to_lowercase();
            let stem_lower = path_stem_str(Path::new(rel_str)).to_lowercase();
            let is_moc = rel_lower.contains("00 - moc") || stem_lower.contains("index");
            if !is_moc {
                if out_edges.is_empty() && in_edges.is_empty() {
                    genuine_orphans.push(rel_str.clone());
                } else {
                    let all_connected_moc = out_edges
                        .iter()
                        .chain(in_edges.iter())
                        .all(|c| {
                            c.to_lowercase().contains("00 - moc")
                                || path_stem_str(Path::new(c))
                                    .to_lowercase()
                                    .contains("index")
                        });
                    if all_connected_moc {
                        moc_only_notes.push(rel_str.clone());
                    }
                }
            }
        }

        let mut proposals_applied = 0usize;
        let mut proposals_rejected = 0usize;
        let mut proposals_awaiting_review = 0usize;
        if let Ok(entries) = fs::read_dir(&self.proposals_dir) {
            for entry in entries.flatten() {
                let p = entry.path();
                if p.extension().and_then(|s| s.to_str()) != Some("json") {
                    continue;
                }
                if let Ok(raw) = fs::read_to_string(&p) {
                    if let Ok(val) = serde_json::from_str::<Value>(&raw) {
                        match val.get("status").and_then(Value::as_str) {
                            Some("APPLIED") => proposals_applied += 1,
                            Some("REJECTED") => proposals_rejected += 1,
                            Some("AWAITING_REVIEW")
                            | Some("PROPOSAL_CREATED")
                            | Some("PENDING") => proposals_awaiting_review += 1,
                            _ => {}
                        }
                    }
                }
            }
        }

        let avg_score = if scores.is_empty() {
            0.0
        } else {
            round1(scores.iter().sum::<f64>() / scores.len() as f64)
        };
        let scores_ge_80 = scores.iter().filter(|&&s| s >= 80.0).count();
        let scores_70_79 = scores.iter().filter(|&&s| (70.0..80.0).contains(&s)).count();
        let scores_60_69 = scores.iter().filter(|&&s| (60.0..70.0).contains(&s)).count();
        let scores_lt_60 = scores.iter().filter(|&&s| s < 60.0).count();

        let orphan_set: HashSet<String> = genuine_orphans.iter().cloned().collect();
        let hub_set: HashSet<String> = hubs.iter().cloned().collect();
        let mut sorted_rels: Vec<String> = outgoing_map.keys().cloned().collect();
        sorted_rels.sort_by(|a, b| {
            let deg_a = outgoing_map[a].len() + incoming_map[a].len();
            let deg_b = outgoing_map[b].len() + incoming_map[b].len();
            deg_b
                .cmp(&deg_a)
                .then_with(|| a.to_lowercase().cmp(&b.to_lowercase()))
        });
        sorted_rels.truncate(300);
        let included_set: HashSet<String> = sorted_rels.iter().cloned().collect();

        let graph_nodes: Vec<Value> = sorted_rels
            .iter()
            .map(|rel| {
                let in_deg = incoming_map[rel].len();
                let out_deg = outgoing_map[rel].len();
                let folder = rel
                    .rsplit_once('/')
                    .map(|(f, _)| f)
                    .unwrap_or("");
                json!({
                    "id": rel,
                    "label": path_stem_str(Path::new(rel)),
                    "folder": folder,
                    "in_degree": in_deg,
                    "out_degree": out_deg,
                    "degree": in_deg + out_deg,
                    "score": score_map.get(rel).copied().map(round1),
                    "is_orphan": orphan_set.contains(rel),
                    "is_hub": hub_set.contains(rel),
                })
            })
            .collect();

        let mut seen_edges: HashSet<(String, String)> = HashSet::new();
        let mut graph_edges: Vec<Value> = Vec::new();
        'edge_loop: for src in &sorted_rels {
            for dst in &outgoing_map[src] {
                if included_set.contains(dst)
                    && src != dst
                    && seen_edges.insert((src.clone(), dst.clone()))
                {
                    graph_edges.push(json!({ "source": src, "target": dst }));
                    if graph_edges.len() >= 800 {
                        break 'edge_loop;
                    }
                }
            }
        }

        let audit_seed = now_unix_nanos().to_string();
        let audit_id = format!("audit_{}", &sha256_hex(audit_seed.as_bytes())[..8]);
        let diagnostics = json!({
            "audit_id": audit_id,
            "timestamp": now_iso_local(),
            "total_notes": unique_notes.len(),
            "outgoing_edges": total_outgoing,
            "incoming_edges_total": total_incoming,
            "genuine_orphans": genuine_orphans.len(),
            "genuine_orphans_list": genuine_orphans,
            "moc_only_count": moc_only_notes.len(),
            "moc_only_notes_list": &moc_only_notes[..moc_only_notes.len().min(25)],
            "hubs_count": hubs.len(),
            "hubs_list": &hubs[..hubs.len().min(15)],
            "broken_links": broken_links_list.len(),
            "broken_links_list": &broken_links_list[..broken_links_list.len().min(25)],
            "missing_attachments_count": missing_attachments_list.len(),
            "code_examples_ignored_count": code_examples_ignored_total,
            "quality_average": avg_score,
            "quality_distribution": {
                "ge_80": scores_ge_80,
                "between_70_79": scores_70_79,
                "between_60_69": scores_60_69,
                "lt_60": scores_lt_60,
                "total_audited": scores.len(),
            },
            "queue_metrics": self.get_worker_status(),
            "accepted_improvements": proposals_applied,
            "rejected_suggestions": proposals_rejected,
            "proposals_awaiting_review": proposals_awaiting_review,
            "graph_nodes": graph_nodes,
            "graph_edges": graph_edges,
        });

        if let Ok(serialized) = serde_json::to_string_pretty(&diagnostics) {
            let _ = atomic_write_string(&self.data_dir, &self.diagnostics_file, &serialized);
        }
        Ok(diagnostics)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn extract_links_ignores_code_fences_inline_code_and_html_comments() {
        let md = "---\ntags: [architecture]\n---\n# Title\n```md\n[[IgnoredInFence]]\n```\nInline `[[IgnoredInline]]` <!-- [[IgnoredHtml]] -->\n![[diagram.png]]\nReal [[Valid Target]]!\n";
        let extracted = extract_markdown_links(md);
        assert_eq!(extracted.code_fences_count, 1);
        assert_eq!(extracted.code_examples_ignored.len(), 2);
        assert_eq!(extracted.embeds, vec!["diagram.png".to_string()]);
        assert_eq!(extracted.wikilinks, vec!["Valid Target".to_string()]);
    }

    #[test]
    fn containment_cas_snapshot_and_cross_note_rollback_guards() {
        let dir = tempdir().unwrap();
        let vault = dir.path().join("obsidian_vault");
        let data = dir.path().join("data").join("obsidian");
        fs::create_dir_all(&vault).unwrap();
        fs::write(vault.join("Alpha Note.md"), "Alpha original content").unwrap();
        fs::write(vault.join("Beta Note.md"), "Beta content").unwrap();
        fs::write(dir.path().join("outside.md"), "Outside secret").unwrap();

        let mut engine = ObsidianGraphEngine::with_paths(vault.clone(), data).unwrap();

        // 1. Traversal & outside containment rejected
        assert!(matches!(
            engine.resolve_contained_note_path("../outside.md"),
            Err(KnowledgeError::SecurityViolation(_))
        ));
        assert!(matches!(
            engine.rollback_note("Alpha Note.md", "../outside.md", None),
            Err(KnowledgeError::SecurityViolation(_))
        ));

        // 2. CAS write creates v2 snapshot and enforces hash check
        let orig_sha = sha256_hex(b"Alpha original content");
        assert!(matches!(
            engine.atomic_write_note("Alpha Note.md", "Conflict", Some("bad_hash"), true),
            Err(KnowledgeError::ConcurrencyConflict(_))
        ));

        let res = engine
            .atomic_write_note("Alpha Note.md", "Alpha updated content", Some(&orig_sha), true)
            .unwrap();
        let snap_path = res["backup_snapshot"]["snapshot_path"].as_str().unwrap();

        // 3. Cross-note rollback attempt must fail with SecurityViolation
        assert!(matches!(
            engine.rollback_note("Beta Note.md", snap_path, None),
            Err(KnowledgeError::SecurityViolation(_))
        ));

        // 4. Same-note rollback restores original bytes cleanly
        assert!(engine.rollback_note("Alpha Note.md", snap_path, None).unwrap());
        assert_eq!(
            fs::read_to_string(vault.join("Alpha Note.md")).unwrap(),
            "Alpha original content"
        );
    }

    #[tokio::test]
    async fn quality_audit_enrichment_queue_batch_and_diagnostics_flow() {
        let dir = tempdir().unwrap();
        let vault = dir.path().join("obsidian_vault");
        let data = dir.path().join("data").join("obsidian");
        fs::create_dir_all(vault.join("00 - MOC")).unwrap();
        fs::write(
            vault.join("00 - MOC/00 - Knowledge Index.md"),
            "---\ntype: moc\ndomain: Index\n---\n# Master Index\n- [[Topic One]]\n- [[Topic Two]]\n- [[Topic Three]]\n- [[Topic Four]]\n- [[Topic Five]]\n",
        )
        .unwrap();
        fs::write(
            vault.join("Topic One.md"),
            "Write-ahead logging and hybrid RAG with [[Missing Note]]",
        )
        .unwrap();
        fs::write(vault.join("Orphan Topic.md"), "# Isolated\nMinimal body.").unwrap();

        let mut engine = ObsidianGraphEngine::with_paths(vault.clone(), data).unwrap();
        let diag = engine.compute_graph_diagnostics().unwrap();
        assert_eq!(diag["total_notes"], 3);
        assert_eq!(diag["genuine_orphans"], 1);
        assert_eq!(diag["broken_links"], 6); // Topic Two..Five + Missing Note

        let audit = engine.audit_note_quality("Topic One.md").unwrap();
        assert_eq!(audit["score_type"], "HEURISTIC");
        assert_eq!(audit["freshness"], "UNKNOWN");
        assert_eq!(audit["needs_improvement"], true);

        // Populate queue, pause blocks batch, resume runs deterministic enrichment fallback
        let queue = engine.populate_improvement_queue().unwrap();
        assert!(!queue.is_empty());
        engine.pause_queue_worker().unwrap();
        std::env::set_var("JARVIS_SKIP_OLLAMA_PROBE", "1");
        let paused_res = engine.run_bounded_improvement_batch(2).await.unwrap();
        assert!(paused_res.is_empty());

        engine.resume_queue_worker().unwrap();
        let batch_res = engine.run_bounded_improvement_batch(1).await.unwrap();
        assert_eq!(batch_res.len(), 1);
        assert_eq!(batch_res[0]["model_provider"], "deterministic");

        let status = engine.get_worker_status();
        assert_eq!(status["applied_count"], 1);
    }
}
