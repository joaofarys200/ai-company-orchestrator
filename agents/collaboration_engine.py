"""
JARVIS OS — Phase 15: Autonomous Agent Collaboration & Conflict Resolution
Multi-agent collaborative execution, conflict taxonomy, AST-level diff inspection,
deterministic arbitration based on real evidence hierarchy, consensus scoring,
and crash-resilient collaboration sessions.
"""

from __future__ import annotations

import ast
import asyncio
import difflib
import enum
import hashlib
import json
import logging
import os
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

from agents.mission_state import MissionStateStore, utc_now
from agents.task_graph import FailureCategory, FailureInfo, TaskGraph, TaskNode, TaskStatus
from backend.logging_config import get_logger, log_event
from intelligence.cross_file_validator import ContractIssueType, CrossFileValidator
from intelligence.repository_graph import RepositoryGraph, SymbolDefinition, SymbolType

try:
    from intelligence.ast_repair_v2 import ASTRepairEngineV2
except Exception:
    ASTRepairEngineV2 = None

from agents.collaboration_scalability import (
    AdaptiveProposalPartitioner,
    PartitionStrategy,
    ProposalPartitionMetadata,
    IncrementalConflictGraph,
    StableComponent,
    ComponentStabilityManager,
    StagedArbitrationEngine,
    StagedArbitrationResult,
    ArbitrationStage,
    LargeArtifactIndex,
    IncrementalStructuralAnalyzer,
    LayeredMergeEngine,
    LayeredMergeTier,
    MergeCorrectnessOracle,
    RegionMerkleTree,
    AdaptiveLeaseManager,
    LeaseStarvationDetector,
)

logger = get_logger(__name__)


# ── ENUMS ──────────────────────────────────────────────────────────────────────

class ResultKind(str, enum.Enum):
    """Categorização estrita do tipo de resultado emitido por um agente."""
    OBSERVATION = "OBSERVATION"
    PROPOSAL = "PROPOSAL"
    PATCH = "PATCH"
    VALIDATION_RESULT = "VALIDATION_RESULT"
    REVIEW = "REVIEW"
    EVIDENCE = "EVIDENCE"
    FINAL_RESULT = "FINAL_RESULT"


class ConflictType(str, enum.Enum):
    """Taxonomia determinística de conflitos multi-agente."""
    FILE_CONFLICT = "FILE_CONFLICT"                     # Alterações concorrentes no mesmo ficheiro
    FILE_OVERLAP = "FILE_CONFLICT"                      # Alias de compatibilidade
    SYMBOL_CONFLICT = "SYMBOL_CONFLICT"                 # Alterações sobrepostas no mesmo símbolo (função, classe, método)
    SEMANTIC_CONFLICT = "SEMANTIC_CONFLICT"             # Intenções ou comportamentos divergentes
    ARCHITECTURAL_CONFLICT = "ARCHITECTURAL_CONFLICT"   # Incompatibilidade com as diretrizes arquiteturais (ex: REST vs GraphQL)
    TEST_CONFLICT = "TEST_CONFLICT"                     # Vereditos ou asserções de testes em desacordo
    CONTRACT_CONFLICT = "CONTRACT_CONFLICT"             # Quebra de contrato entre consumidor (Frontend) e produtor (Backend)
    REQUIREMENT_CONFLICT = "REQUIREMENT_CONFLICT"       # Ambiguidade na interpretação de requisitos


class ArbitrationDecision(str, enum.Enum):
    """Decisões determinísticas possíveis do árbitro de conflitos."""
    ACCEPT_A = "ACCEPT_A"
    ACCEPT_B = "ACCEPT_B"
    CHOOSE_PROPOSAL = "CHOOSE_PROPOSAL"
    MERGE = "MERGE"
    REGENERATE = "REGENERATE"
    REPAIR = "REPAIR"
    REPLAN = "REPLAN"
    BLOCK = "BLOCK"


class CollaborationStatus(str, enum.Enum):
    """Máquina de estados estrita da sessão de colaboração."""
    OPEN = "OPEN"
    COLLECTING = "COLLECTING"
    CONFLICT_DETECTED = "CONFLICT_DETECTED"
    ARBITRATING = "ARBITRATING"
    RESOLVED = "RESOLVED"
    VALIDATING = "VALIDATING"
    ACCEPTED = "ACCEPTED"
    BLOCKED = "BLOCKED"


# ── CONFLICT IDENTITY & DATACLASSES ───────────────────────────────────────────

@dataclass(frozen=True)
class ConflictKey:
    """Identidade determinística imutável para qualquer conflito."""
    project_id: str
    task_id: str
    resource: str
    symbol: str
    conflict_type: ConflictType

    def make_key(self) -> str:
        payload = f"{self.project_id}::{self.task_id}::{self.resource}::{self.symbol}::{self.conflict_type.value}"
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
        return f"conf_{self.conflict_type.value.lower()}_{digest}"

    @property
    def hash_key(self) -> str:
        return self.make_key()

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "task_id": self.task_id,
            "resource": self.resource,
            "symbol": self.symbol,
            "conflict_type": self.conflict_type.value,
            "conflict_key_id": self.make_key(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConflictKey:
        ct_str = data.get("conflict_type", "FILE_CONFLICT")
        ct = ConflictType(ct_str) if ct_str in ConflictType._value2member_map_ else ConflictType.FILE_CONFLICT
        return cls(
            project_id=data.get("project_id", ""),
            task_id=data.get("task_id", ""),
            resource=data.get("resource", ""),
            symbol=data.get("symbol", ""),
            conflict_type=ct,
        )


@dataclass
class AgentProposal:
    """Proposta estruturada emitida por um agente numa sessão de colaboração."""
    proposal_id: str
    task_id: str = "task_default"
    agent_id: str = "agent_default"
    collaboration_id: str = ""
    agent_type: str = "GENERAL"
    result_kind: ResultKind = ResultKind.PROPOSAL
    affected_files: list[str] = field(default_factory=list)
    affected_symbols: list[str] = field(default_factory=list)
    diff_content: str = ""
    content_by_file: dict[str, str] = field(default_factory=dict)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    confidence_score: float = 0.8  # Confiança do agente (0.0 a 1.0) — NÃO equivale a correção!
    rationale: str = ""
    description: str = ""
    timestamp: str = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        proposal_id: str,
        task_id: str = "task_default",
        agent_id: str = "agent_default",
        collaboration_id: str = "",
        agent_type: str = "GENERAL",
        result_kind: ResultKind = ResultKind.PROPOSAL,
        affected_files: list[str] | None = None,
        affected_symbols: list[str] | None = None,
        diff_content: str = "",
        content_by_file: dict[str, str] | None = None,
        evidence: list[dict[str, Any]] | dict[str, Any] | None = None,
        confidence_score: float = 0.8,
        rationale: str = "",
        description: str = "",
        timestamp: str | None = None,
        metadata: dict[str, Any] | None = None,
        # Argumentos de conveniência
        file_path: str = "",
        ast_symbols: list[str] | None = None,
        proposed_content: str = "",
    ) -> None:
        self.proposal_id = proposal_id
        self.task_id = task_id
        self.agent_id = agent_id
        self.collaboration_id = collaboration_id
        self.agent_type = agent_type
        self.result_kind = result_kind if isinstance(result_kind, ResultKind) else ResultKind(result_kind)

        files = list(affected_files) if affected_files is not None else []
        if file_path and file_path not in files:
            files.append(file_path)
        self.affected_files = files

        symbols = list(affected_symbols) if affected_symbols is not None else []
        if ast_symbols:
            for s in ast_symbols:
                if s not in symbols:
                    symbols.append(s)
        self.affected_symbols = symbols

        self.diff_content = diff_content
        c_by_f = dict(content_by_file) if content_by_file is not None else {}
        if file_path and proposed_content and file_path not in c_by_f:
            c_by_f[file_path] = proposed_content
        self.content_by_file = c_by_f
        self.proposed_content = proposed_content

        if isinstance(evidence, list):
            self.evidence = list(evidence)
        elif isinstance(evidence, dict):
            self.evidence = [dict(evidence)]
        else:
            self.evidence = []

        self.confidence_score = float(confidence_score)
        self.rationale = rationale or description
        self.description = description or rationale
        self.timestamp = timestamp or utc_now()
        self.metadata = dict(metadata) if metadata is not None else {}

    @property
    def file_path(self) -> str:
        return self.affected_files[0] if self.affected_files else ""

    @property
    def ast_symbols(self) -> list[str]:
        return self.affected_symbols

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "collaboration_id": self.collaboration_id,
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "result_kind": self.result_kind.value if isinstance(self.result_kind, ResultKind) else str(self.result_kind),
            "affected_files": list(self.affected_files),
            "affected_symbols": list(self.affected_symbols),
            "diff_content": self.diff_content,
            "content_by_file": dict(self.content_by_file),
            "evidence": list(self.evidence),
            "confidence_score": self.confidence_score,
            "rationale": self.rationale,
            "timestamp": self.timestamp,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentProposal:
        rk_str = data.get("result_kind", "PROPOSAL")
        rk = ResultKind(rk_str) if rk_str in ResultKind._value2member_map_ else ResultKind.PROPOSAL
        return cls(
            proposal_id=data["proposal_id"],
            task_id=data.get("task_id", "task_default"),
            agent_id=data.get("agent_id", "agent_default"),
            collaboration_id=data.get("collaboration_id", ""),
            agent_type=data.get("agent_type", "GENERAL"),
            result_kind=rk,
            affected_files=list(data.get("affected_files", [])),
            affected_symbols=list(data.get("affected_symbols", [])),
            diff_content=data.get("diff_content", ""),
            content_by_file=dict(data.get("content_by_file", {})),
            evidence=list(data.get("evidence", [])),
            confidence_score=float(data.get("confidence_score", 0.8)),
            rationale=data.get("rationale", ""),
            timestamp=data.get("timestamp", utc_now()),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class ConflictDetails:
    """Registo de diagnóstico completo de um conflito detetado."""
    conflict_key: ConflictKey = field(default_factory=lambda: ConflictKey("proj", "task", "res", "sym", ConflictType.FILE_CONFLICT))
    proposals_involved: list[str] = field(default_factory=list)
    description: str = ""
    severity: str = "HIGH"
    detected_at: str = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        conflict_key: ConflictKey | None = None,
        proposals_involved: list[str] | None = None,
        description: str = "",
        severity: str = "HIGH",
        detected_at: str | None = None,
        metadata: dict[str, Any] | None = None,
        # Argumentos de conveniência
        conflict_type: ConflictType | str | None = None,
        file_path: str = "",
        conflicting_agents: list[str] | None = None,
        competing_proposals: list[str] | None = None,
    ) -> None:
        if conflict_key is None:
            ct = ConflictType.FILE_CONFLICT
            if conflict_type:
                if isinstance(conflict_type, ConflictType):
                    ct = conflict_type
                elif str(conflict_type) in ConflictType._value2member_map_:
                    ct = ConflictType(str(conflict_type))
            conflict_key = ConflictKey(
                project_id="default_project",
                task_id="default_task",
                resource=file_path or "default_resource",
                symbol="*",
                conflict_type=ct,
            )
        self.conflict_key = conflict_key

        proposals = list(proposals_involved) if proposals_involved is not None else []
        if competing_proposals:
            for p in competing_proposals:
                if p not in proposals:
                    proposals.append(p)
        self.proposals_involved = proposals
        self.description = description
        self.severity = severity
        self.detected_at = detected_at or utc_now()
        meta = dict(metadata) if metadata is not None else {}
        if conflicting_agents:
            meta["conflicting_agents"] = list(conflicting_agents)
        self.metadata = meta

    @property
    def key_id(self) -> str:
        return self.conflict_key.make_key()

    @property
    def conflict_type(self) -> ConflictType:
        return self.conflict_key.conflict_type

    @property
    def rationale(self) -> str:
        return self.description

    def to_dict(self) -> dict[str, Any]:
        return {
            "conflict_key": self.conflict_key.to_dict(),
            "key_id": self.key_id,
            "conflict_type": self.conflict_type.value,
            "proposals_involved": list(self.proposals_involved),
            "description": self.description,
            "severity": self.severity,
            "detected_at": self.detected_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConflictDetails:
        ck = ConflictKey.from_dict(data.get("conflict_key", {}))
        return cls(
            conflict_key=ck,
            proposals_involved=list(data.get("proposals_involved", [])),
            description=data.get("description", ""),
            severity=data.get("severity", "HIGH"),
            detected_at=data.get("detected_at", utc_now()),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class ArbitrationRecord:
    """Decisão formal e auditável emitida pelo árbitro de conflitos."""
    arbitration_id: str
    conflict_key: str
    decision: ArbitrationDecision
    winning_proposal_id: str | None = None
    consensus_score: float = 0.0
    evidence_rankings: list[dict[str, Any]] = field(default_factory=list)
    rationale: str = ""
    arbitrated_at: str = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def selected_proposal_id(self) -> str | None:
        return self.winning_proposal_id

    @property
    def confidence_score(self) -> float:
        return self.consensus_score

    def to_dict(self) -> dict[str, Any]:
        return {
            "arbitration_id": self.arbitration_id,
            "conflict_key": self.conflict_key,
            "decision": self.decision.value if isinstance(self.decision, ArbitrationDecision) else str(self.decision),
            "winning_proposal_id": self.winning_proposal_id,
            "consensus_score": self.consensus_score,
            "evidence_rankings": list(self.evidence_rankings),
            "rationale": self.rationale,
            "arbitrated_at": self.arbitrated_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ArbitrationRecord:
        dec_str = data.get("decision", "BLOCK")
        dec = ArbitrationDecision(dec_str) if dec_str in ArbitrationDecision._value2member_map_ else ArbitrationDecision.BLOCK
        return cls(
            arbitration_id=data["arbitration_id"],
            conflict_key=data.get("conflict_key", ""),
            decision=dec,
            winning_proposal_id=data.get("winning_proposal_id"),
            consensus_score=float(data.get("consensus_score", 0.0)),
            evidence_rankings=list(data.get("evidence_rankings", [])),
            rationale=data.get("rationale", ""),
            arbitrated_at=data.get("arbitrated_at", utc_now()),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class ConflictCandidateIndex:
    """Índice determinístico de candidatos para podar comparações O(N²) redundantes (Fase 15.1)."""
    file_to_proposals: dict[str, list[str]] = field(default_factory=dict)
    symbol_to_proposals: dict[tuple[str, str], list[str]] = field(default_factory=dict)
    contract_to_proposals: dict[str, list[str]] = field(default_factory=dict)
    requirement_to_proposals: dict[str, list[str]] = field(default_factory=dict)
    domain_to_proposals: dict[str, list[str]] = field(default_factory=dict)
    content_hash_to_proposals: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_to_proposals": {k: list(v) for k, v in sorted(self.file_to_proposals.items())},
            "symbol_to_proposals": {f"{k[0]}::{k[1]}": list(v) for k, v in sorted(self.symbol_to_proposals.items())},
            "contract_to_proposals": {k: list(v) for k, v in sorted(self.contract_to_proposals.items())},
            "requirement_to_proposals": {k: list(v) for k, v in sorted(self.requirement_to_proposals.items())},
            "domain_to_proposals": {k: list(v) for k, v in sorted(self.domain_to_proposals.items())},
            "content_hash_to_proposals": {k: list(v) for k, v in sorted(self.content_hash_to_proposals.items())},
        }


@dataclass
class CandidateConflictGraph:
    """Grafo determinístico de pares de candidatos e razões estruturais de conflito (Fase 15.1)."""
    nodes: list[str] = field(default_factory=list)
    edges: dict[tuple[str, str], list[str]] = field(default_factory=dict)
    candidate_count: int = 0
    actual_comparisons: int = 0
    pruned_comparisons: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": list(self.nodes),
            "edges": {f"{k[0]}<->{k[1]}": list(v) for k, v in sorted(self.edges.items())},
            "candidate_count": self.candidate_count,
            "actual_comparisons": self.actual_comparisons,
            "pruned_comparisons": self.pruned_comparisons,
        }


class DenseConflictStrategy(str, enum.Enum):
    """Estratégias determinísticas de deteção para cenários de conflito denso (Fase 15.2 Secção 2)."""
    PAIRWISE = "PAIRWISE"
    CONNECTED_COMPONENTS = "CONNECTED_COMPONENTS"
    BUCKETED_COMPARISON = "BUCKETED_COMPARISON"
    HIERARCHICAL_GROUPS = "HIERARCHICAL_GROUPS"


@dataclass
class ConflictComponent:
    """Componente conexa de propostas mutuamente conflituantes (Fase 15.2 Secção 3)."""
    component_id: str
    proposal_ids: list[str] = field(default_factory=list)
    affected_files: list[str] = field(default_factory=list)
    candidate_pair_count: int = 0
    has_conflicts: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "component_id": self.component_id,
            "proposal_ids": list(self.proposal_ids),
            "affected_files": list(self.affected_files),
            "candidate_pair_count": self.candidate_pair_count,
            "has_conflicts": self.has_conflicts,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConflictComponent:
        return cls(
            component_id=data.get("component_id", ""),
            proposal_ids=list(data.get("proposal_ids", [])),
            affected_files=list(data.get("affected_files", [])),
            candidate_pair_count=int(data.get("candidate_pair_count", 0)),
            has_conflicts=bool(data.get("has_conflicts", False)),
        )


@dataclass
class HierarchicalConflictIndex:
    """
    Índice hierárquico progressivo de conflitos multi-agente (Fase 15.2 Secção 1).
    Hierarquia: Mission -> Work Package -> Agent -> File/Package -> Symbol -> Region
    Garante fast rejection O(1) e ausência absoluta de falsos negativos.
    """
    # Nível 0: Package / Directory
    package_to_proposals: dict[str, list[str]] = field(default_factory=dict)
    # Nível 1: File / Path
    file_to_proposals: dict[str, list[str]] = field(default_factory=dict)
    # Nível 2: Symbol (file, symbol)
    symbol_to_proposals: dict[tuple[str, str], list[str]] = field(default_factory=dict)
    # Nível 3: AST Range (file -> [(start, end, pid)])
    range_to_proposals: dict[str, list[tuple[int, int, str]]] = field(default_factory=dict)
    # Nível 4: Semantic Region (file, region_tag)
    semantic_region_to_proposals: dict[tuple[str, str], list[str]] = field(default_factory=dict)
    # Índices transversais
    contract_to_proposals: dict[str, list[str]] = field(default_factory=dict)
    requirement_to_proposals: dict[str, list[str]] = field(default_factory=dict)
    test_to_proposals: dict[str, list[str]] = field(default_factory=dict)
    domain_to_proposals: dict[str, list[str]] = field(default_factory=dict)
    content_hash_to_proposals: dict[str, list[str]] = field(default_factory=dict)

    # Linkages determinísticos
    symbol_to_files: dict[str, set[str]] = field(default_factory=dict)
    symbol_to_contracts: dict[tuple[str, str], set[str]] = field(default_factory=dict)
    symbol_to_requirements: dict[tuple[str, str], set[str]] = field(default_factory=dict)
    symbol_to_tests: dict[tuple[str, str], set[str]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "package_to_proposals": {k: list(v) for k, v in sorted(self.package_to_proposals.items())},
            "file_to_proposals": {k: list(v) for k, v in sorted(self.file_to_proposals.items())},
            "symbol_to_proposals": {f"{k[0]}::{k[1]}": list(v) for k, v in sorted(self.symbol_to_proposals.items())},
            "range_to_proposals": {k: [(s, e, pid) for s, e, pid in v] for k, v in sorted(self.range_to_proposals.items())},
            "contract_to_proposals": {k: list(v) for k, v in sorted(self.contract_to_proposals.items())},
            "requirement_to_proposals": {k: list(v) for k, v in sorted(self.requirement_to_proposals.items())},
            "test_to_proposals": {k: list(v) for k, v in sorted(self.test_to_proposals.items())},
            "domain_to_proposals": {k: list(v) for k, v in sorted(self.domain_to_proposals.items())},
            "content_hash_to_proposals": {k: list(v) for k, v in sorted(self.content_hash_to_proposals.items())},
        }


@dataclass
class MergeFailureRecord:
    """Registo diagnóstico de uma falha de estratégia de merge (Fase 15.2 Secção 10)."""
    failure_id: str
    file_path: str
    line_count: int
    language: str
    strategy_used: str
    fallback_used: str
    error_type: str
    error_details: str
    timestamp: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MergeFailureRecord:
        return cls(
            failure_id=data.get("failure_id", str(uuid.uuid4())[:8]),
            file_path=data.get("file_path", ""),
            line_count=int(data.get("line_count", 0)),
            language=data.get("language", ""),
            strategy_used=data.get("strategy_used", ""),
            fallback_used=data.get("fallback_used", ""),
            error_type=data.get("error_type", ""),
            error_details=data.get("error_details", ""),
            timestamp=data.get("timestamp", utc_now()),
        )


class MergeFailureMemory:
    """Memória de falhas de merge com seleção de fallback adaptativa determinística e evicção LRU/TTL (Fase 15.2/15.3)."""
    def __init__(self, max_entries: int = 500, default_ttl_seconds: float = 3600.0) -> None:
        self.max_entries = max_entries
        self.default_ttl_seconds = default_ttl_seconds
        self.records: list[MergeFailureRecord] = []
        self.failures: dict[str, dict[str, Any]] = {}
        self.failure_counts_by_strategy: dict[str, int] = {}

    def record_failure(
        self,
        record_or_key: MergeFailureRecord | str,
        reason: str = "",
        retryable: bool = False,
        strategy: str = "STRUCTURAL_AST",
    ) -> None:
        now_ts = time.time()
        if isinstance(record_or_key, MergeFailureRecord):
            rec = record_or_key
            self.records.append(rec)
            self.failure_counts_by_strategy[rec.strategy_used] = (
                self.failure_counts_by_strategy.get(rec.strategy_used, 0) + 1
            )
            key = rec.failure_id or rec.file_path
            self.failures[key] = {
                "reason": rec.error_details,
                "retryable": False,
                "timestamp": now_ts,
                "record": rec,
            }
        else:
            key = str(record_or_key)
            self.failures[key] = {
                "reason": reason,
                "retryable": retryable,
                "timestamp": now_ts,
                "record": None,
            }
            self.failure_counts_by_strategy[strategy] = (
                self.failure_counts_by_strategy.get(strategy, 0) + 1
            )

        # LRU eviction se exceder max_entries
        while len(self.failures) > self.max_entries:
            oldest_key = min(self.failures.keys(), key=lambda k: self.failures[k]["timestamp"])
            del self.failures[oldest_key]
        if len(self.records) > self.max_entries:
            self.records = self.records[-self.max_entries:]

    def is_known_failure(self, key: str) -> bool:
        if key not in self.failures:
            return False
        entry = self.failures[key]
        if time.time() - entry["timestamp"] > self.default_ttl_seconds:
            del self.failures[key]
            return False
        return True

    def evict_expired(self) -> int:
        now_ts = time.time()
        expired_keys = [
            k for k, v in self.failures.items()
            if (now_ts - v["timestamp"]) > self.default_ttl_seconds
        ]
        for k in expired_keys:
            del self.failures[k]
        return len(expired_keys)

    def get_failure_count(self) -> int:
        return len(self.failures) if self.failures else len(self.records)

    def get_failures_for_file(self, file_path: str) -> list[MergeFailureRecord]:
        return [r for r in self.records if r.file_path == file_path]

    def get_preferred_strategy(self, language: str, line_count: int) -> str | None:
        if self.failure_counts_by_strategy.get("STRUCTURAL_AST", 0) >= 3 and line_count >= 5000:
            return "WINDOWED_BLOCK"
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_entries": self.max_entries,
            "default_ttl_seconds": self.default_ttl_seconds,
            "records": [r.to_dict() for r in self.records],
            "failures": {
                k: {
                    "reason": v["reason"],
                    "retryable": v["retryable"],
                    "timestamp": v["timestamp"],
                    "record": v["record"].to_dict() if v["record"] else None,
                }
                for k, v in self.failures.items()
            },
            "failure_counts_by_strategy": dict(self.failure_counts_by_strategy),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MergeFailureMemory:
        mem = cls(
            max_entries=int(data.get("max_entries", 500)),
            default_ttl_seconds=float(data.get("default_ttl_seconds", 3600.0)),
        )
        mem.records = [MergeFailureRecord.from_dict(r) for r in data.get("records", [])]
        for k, v in data.get("failures", {}).items():
            rec = MergeFailureRecord.from_dict(v["record"]) if v.get("record") else None
            mem.failures[k] = {
                "reason": v.get("reason", ""),
                "retryable": v.get("retryable", False),
                "timestamp": float(v.get("timestamp", time.time())),
                "record": rec,
            }
        mem.failure_counts_by_strategy = dict(data.get("failure_counts_by_strategy", {}))
        return mem


# ── ADAPTIVE PROPOSAL PARTITIONER & INCREMENTAL GRAPH (FASE 15.3) ───────────────

class PartitionStrategy(str, enum.Enum):
    """Estratégias de particionamento adaptativo de propostas (Fase 15.3)."""
    PAIRWISE = "PAIRWISE"
    COMPONENT_CENTRIC = "COMPONENT_CENTRIC"
    HIERARCHICAL_PARTITIONING = "HIERARCHICAL_PARTITIONING"
    STAGED_ARBITRATION = "STAGED_ARBITRATION"


@dataclass
class ProposalPartitionMetadata:
    """Metadados diagnósticos da decisão de particionamento (Fase 15.3)."""
    strategy: PartitionStrategy
    total_proposals: int
    candidate_pair_count: int
    component_count: int
    density: float
    timestamp: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy.value if isinstance(self.strategy, PartitionStrategy) else str(self.strategy),
            "total_proposals": self.total_proposals,
            "candidate_pair_count": self.candidate_pair_count,
            "component_count": self.component_count,
            "density": self.density,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProposalPartitionMetadata:
        strat_str = data.get("strategy", "PAIRWISE")
        strat = PartitionStrategy(strat_str) if strat_str in PartitionStrategy._value2member_map_ else PartitionStrategy.PAIRWISE
        return cls(
            strategy=strat,
            total_proposals=int(data.get("total_proposals", 0)),
            candidate_pair_count=int(data.get("candidate_pair_count", 0)),
            component_count=int(data.get("component_count", 0)),
            density=float(data.get("density", 0.0)),
            timestamp=data.get("timestamp", utc_now()),
        )


class AdaptiveProposalPartitioner:
    """
    Particionamento adaptativo de propostas baseado em densidade e contagem N (Fase 15.3).
    - N < 8 e densidade < 0.25: PAIRWISE
    - Componentes conexas > 1 e densidade > 0: COMPONENT_CENTRIC
    - N >= 8 e componente conexa única: HIERARCHICAL_PARTITIONING
    - N >= 16 e densidade >= 0.60: STAGED_ARBITRATION
    """
    @classmethod
    def evaluate_strategy(
        cls,
        proposals: list[AgentProposal],
        candidate_pair_count: int,
        connected_component_count: int = 1,
    ) -> ProposalPartitionMetadata:
        n = len(proposals)
        max_pairs = (n * (n - 1)) // 2 if n > 1 else 0
        density = (candidate_pair_count / max_pairs) if max_pairs > 0 else 0.0

        if n >= 16 and density >= 0.60:
            strategy = PartitionStrategy.STAGED_ARBITRATION
        elif n >= 8 and connected_component_count == 1:
            strategy = PartitionStrategy.HIERARCHICAL_PARTITIONING
        elif connected_component_count > 1 and density > 0.0:
            strategy = PartitionStrategy.COMPONENT_CENTRIC
        elif n < 8 and density < 0.25:
            strategy = PartitionStrategy.PAIRWISE
        else:
            strategy = PartitionStrategy.COMPONENT_CENTRIC

        return ProposalPartitionMetadata(
            strategy=strategy,
            total_proposals=n,
            candidate_pair_count=candidate_pair_count,
            component_count=connected_component_count,
            density=round(density, 4),
        )


@dataclass
class IncrementalConflictGraph:
    """
    Grafo de conflitos com manutenção incremental O(|ΔV|·deg) (Fase 15.3).
    Evita recomputação O(N²) completa ao adicionar, atualizar ou remover propostas.
    """
    nodes: dict[str, AgentProposal] = field(default_factory=dict)
    adjacency: dict[str, set[str]] = field(default_factory=dict)

    def _detect_overlap(self, p1: AgentProposal, p2: AgentProposal) -> bool:
        shared_files = set(p1.affected_files) & set(p2.affected_files)
        if not shared_files:
            return False
        return True

    def add_proposal(self, proposal: AgentProposal) -> list[str]:
        pid = proposal.proposal_id
        self.nodes[pid] = proposal
        if pid not in self.adjacency:
            self.adjacency[pid] = set()

        new_conflicts = []
        for other_id, other_prop in self.nodes.items():
            if other_id == pid:
                continue
            if self._detect_overlap(proposal, other_prop):
                self.adjacency[pid].add(other_id)
                self.adjacency[other_id].add(pid)
                new_conflicts.append(other_id)
        return new_conflicts

    def remove_proposal(self, proposal_id: str) -> None:
        if proposal_id in self.nodes:
            del self.nodes[proposal_id]
        if proposal_id in self.adjacency:
            neighbors = list(self.adjacency[proposal_id])
            del self.adjacency[proposal_id]
            for n in neighbors:
                if n in self.adjacency:
                    self.adjacency[n].discard(proposal_id)

    def update_proposal(self, proposal: AgentProposal) -> list[str]:
        self.remove_proposal(proposal.proposal_id)
        return self.add_proposal(proposal)

    def has_conflict(self, p1_id: str, p2_id: str) -> bool:
        return p2_id in self.adjacency.get(p1_id, set())

    def get_neighbors(self, proposal_id: str) -> list[str]:
        return sorted(list(self.adjacency.get(proposal_id, set())))

    def get_connected_components(self) -> list[list[str]]:
        visited = set()
        components = []
        for pid in sorted(self.nodes.keys()):
            if pid not in visited:
                comp = []
                queue = [pid]
                visited.add(pid)
                while queue:
                    curr = queue.pop(0)
                    comp.append(curr)
                    for n in self.adjacency.get(curr, set()):
                        if n not in visited:
                            visited.add(n)
                            queue.append(n)
                components.append(sorted(comp))
        return components

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": {pid: p.to_dict() for pid, p in self.nodes.items()},
            "adjacency": {pid: list(neighbors) for pid, neighbors in self.adjacency.items()},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IncrementalConflictGraph:
        nodes = {pid: AgentProposal.from_dict(p) for pid, p in data.get("nodes", {}).items()}
        adjacency = {pid: set(neighbors) for pid, neighbors in data.get("adjacency", {}).items()}
        return cls(nodes=nodes, adjacency=adjacency)


@dataclass
class StagedArbitrationResult:
    """Resultado detalhado do motor de arbitragem em três estágios (Fase 15.3)."""
    conflict_key: str
    stage_1_pruned: list[str]
    stage_1_passed: list[str]
    stage_1_reasons: dict[str, str]
    stage_2_rankings: list[tuple[str, float]]
    winning_proposal_id: str | None
    final_decision: ArbitrationDecision
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "conflict_key": self.conflict_key,
            "stage_1_pruned": list(self.stage_1_pruned),
            "stage_1_passed": list(self.stage_1_passed),
            "stage_1_reasons": dict(self.stage_1_reasons),
            "stage_2_rankings": [(pid, score) for pid, score in self.stage_2_rankings],
            "winning_proposal_id": self.winning_proposal_id,
            "final_decision": self.final_decision.value if isinstance(self.final_decision, ArbitrationDecision) else str(self.final_decision),
            "rationale": self.rationale,
        }


class StagedArbitrationEngine:
    """
    Motor de Arbitragem em Três Estágios (Fase 15.3):
    1. Fast Pruning: Validação rápida de integridade, compilação AST, privilégios de agente.
    2. Objective Evidence Ranking: Avaliação da evidência determinística.
    3. Deterministic Tie-Breaking: Desempate determinístico imutável via hash SHA256.
    """
    @classmethod
    def arbitrate_staged(
        cls,
        conflict: ConflictDetails,
        proposals: list[AgentProposal],
        is_economic_task: bool = False,
    ) -> StagedArbitrationResult:
        prop_map = {p.proposal_id: p for p in proposals}
        ck_key = conflict.key_id if hasattr(conflict, "key_id") else "conf_key"

        # Estágio 1: Fast Pruning
        stage_1_pruned = []
        stage_1_passed = []
        stage_1_reasons = {}

        for p in proposals:
            # Privilege check
            is_readonly = "research" in p.agent_id.lower() or p.agent_type.upper() == "RESEARCH"
            has_code_patch = bool(
                p.diff_content
                or p.content_by_file
                or getattr(p, "proposed_content", "")
                or (isinstance(p.metadata, dict) and p.metadata.get("content"))
            )
            if is_readonly and has_code_patch:
                stage_1_pruned.append(p.proposal_id)
                stage_1_reasons[p.proposal_id] = "PRIVILEGE_VIOLATION: Read-only agent cannot propose code modifications"
                continue

            # Check hard validation in evidence or metadata
            ev_list = p.evidence if isinstance(p.evidence, list) else [p.evidence] if isinstance(p.evidence, dict) else []
            hard_val_passed = True
            for ev in ev_list:
                if isinstance(ev, dict):
                    hv = ev.get("hard_validation")
                    if isinstance(hv, dict) and hv.get("passed") is False:
                        hard_val_passed = False
                    elif hv is False:
                        hard_val_passed = False
            if p.metadata.get("hard_validation") is False:
                hard_val_passed = False

            if not hard_val_passed:
                stage_1_pruned.append(p.proposal_id)
                stage_1_reasons[p.proposal_id] = "HARD_VALIDATION_FAILURE: AST syntax or compilation failed"
                continue

            stage_1_passed.append(p.proposal_id)

        # Salvaguarda económica
        if is_economic_task:
            if stage_1_pruned or not stage_1_passed or len(stage_1_passed) < len(proposals):
                return StagedArbitrationResult(
                    conflict_key=ck_key,
                    stage_1_pruned=stage_1_pruned,
                    stage_1_passed=stage_1_passed,
                    stage_1_reasons=stage_1_reasons,
                    stage_2_rankings=[],
                    winning_proposal_id=None,
                    final_decision=ArbitrationDecision.BLOCK,
                    rationale="ECONOMIC_SAFEGUARD: Financial transactions cannot proceed without unanimous hard validation verification.",
                )

        if not stage_1_passed:
            return StagedArbitrationResult(
                conflict_key=ck_key,
                stage_1_pruned=stage_1_pruned,
                stage_1_passed=[],
                stage_1_reasons=stage_1_reasons,
                stage_2_rankings=[],
                winning_proposal_id=None,
                final_decision=ArbitrationDecision.REGENERATE,
                rationale="All proposals pruned in Stage 1 due to validation or privilege failures.",
            )

        # Estágio 2: Objective Evidence Ranking
        rankings: list[tuple[str, float]] = []
        for pid in stage_1_passed:
            prop = prop_map[pid]
            score = AgentConflictArbitrator._calculate_evidence_score(prop.evidence, prop.confidence_score, prop.rationale)
            rankings.append((pid, score))

        rankings.sort(key=lambda x: x[1], reverse=True)

        # Estágio 3: Deterministic Tie-Breaking
        top_score = rankings[0][1]
        top_candidates = [pid for pid, score in rankings if abs(score - top_score) < 1e-6]

        if len(top_candidates) == 1:
            winner = top_candidates[0]
            rationale = f"Selected proposal {winner} with top evidence score {top_score:.2f}."
        else:
            winner = min(top_candidates, key=lambda pid: hashlib.sha256(pid.encode("utf-8")).hexdigest())
            rationale = f"Deterministic tie-break selected proposal {winner} among candidates with identical score {top_score:.2f}."

        return StagedArbitrationResult(
            conflict_key=ck_key,
            stage_1_pruned=stage_1_pruned,
            stage_1_passed=stage_1_passed,
            stage_1_reasons=stage_1_reasons,
            stage_2_rankings=rankings,
            winning_proposal_id=winner,
            final_decision=ArbitrationDecision.CHOOSE_PROPOSAL,
            rationale=rationale,
        )


class ConnectedConflictGraphEngine:
    """
    Agrupamento determinístico de agentes/propostas em componentes conexas (Fase 15.2 Secção 3).
    A -- B -- C | D -- E | F => Componente 1: {A,B,C}, Componente 2: {D,E}, Componente 3: {F}
    """
    @classmethod
    def partition_into_components(
        cls,
        proposals: list[AgentProposal],
        candidate_edges: dict[tuple[str, str], list[str]],
    ) -> list[ConflictComponent]:
        p_ids = sorted([p.proposal_id for p in proposals])
        parent = {pid: pid for pid in p_ids}

        def find(x: str) -> str:
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]

        def union(x: str, y: str) -> None:
            rx, ry = find(x), find(y)
            if rx != ry:
                if rx < ry:
                    parent[ry] = rx
                else:
                    parent[rx] = ry

        for (u, v) in candidate_edges.keys():
            if u in parent and v in parent:
                union(u, v)

        groups: dict[str, list[str]] = {}
        for pid in p_ids:
            r = find(pid)
            groups.setdefault(r, []).append(pid)

        p_map = {p.proposal_id: p for p in proposals}
        components: list[ConflictComponent] = []

        for root, members in sorted(groups.items()):
            members_sorted = sorted(members)
            aff_files = sorted({f for pid in members_sorted for f in p_map[pid].affected_files})
            edge_count = sum(
                1 for (u, v) in candidate_edges.keys()
                if u in members and v in members
            )
            comp = ConflictComponent(
                component_id=f"comp_{root}",
                proposal_ids=members_sorted,
                affected_files=aff_files,
                candidate_pair_count=edge_count,
                has_conflicts=edge_count > 0,
            )
            components.append(comp)

        return components


@dataclass
class CollaborationMetrics:
    """Métricas em tempo de execução para observabilidade da Fase 15, 15.1 & 15.2."""
    collaboration_count: int = 0
    conflict_count: int = 0
    conflict_resolution_count: int = 0
    auto_merge_count: int = 0
    arbitration_count: int = 0
    regeneration_count: int = 0
    collaboration_rounds: int = 0
    agent_failures: int = 0
    agent_reassignments: int = 0
    evidence_count: int = 0
    human_interventions: int = 0
    resolution_latency_ms: float = 0.0
    # Métricas de escalabilidade e indexação (Fase 15.1 & 15.2)
    conflict_candidates: int = 0
    conflict_comparisons: int = 0
    conflict_pruned: int = 0
    conflicts_detected: int = 0
    false_positive_count: int = 0
    false_negative_count: int = 0
    duplicate_proposals: int = 0
    merge_fast_path_count: int = 0
    merge_full_diff_count: int = 0
    merge_conflict_count: int = 0
    merge_latency_ms: float = 0.0
    candidate_index_latency_ms: float = 0.0
    # Novas métricas Fase 15.2
    hierarchical_index_latency_ms: float = 0.0
    dense_strategy_selected: str = "PAIRWISE"
    component_count: int = 0
    isolated_proposals_count: int = 0
    structural_merge_count: int = 0
    windowed_merge_count: int = 0
    line_fallback_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CollaborationSession:
    """Sessão de colaboração multi-agente para resolução de uma tarefa partilhada."""
    collaboration_id: str
    mission_id: str
    task_id: str
    participant_agents: list[str] = field(default_factory=list)
    proposals: list[AgentProposal] = field(default_factory=list)
    conflicts: list[ConflictDetails] = field(default_factory=list)
    arbitrations: list[ArbitrationRecord] = field(default_factory=list)
    status: CollaborationStatus = CollaborationStatus.OPEN
    round_count: int = 1
    max_rounds: int = 3
    max_arbitrations: int = 3
    max_regenerations: int = 2
    final_result: dict[str, Any] | None = None
    merged_content: dict[str, str] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "collaboration_id": self.collaboration_id,
            "mission_id": self.mission_id,
            "task_id": self.task_id,
            "participant_agents": list(self.participant_agents),
            "proposals": [p.to_dict() for p in self.proposals],
            "conflicts": [c.to_dict() for c in self.conflicts],
            "arbitrations": [a.to_dict() for a in self.arbitrations],
            "status": self.status.value if isinstance(self.status, CollaborationStatus) else str(self.status),
            "round_count": self.round_count,
            "max_rounds": self.max_rounds,
            "max_arbitrations": self.max_arbitrations,
            "max_regenerations": self.max_regenerations,
            "final_result": self.final_result,
            "merged_content": dict(self.merged_content),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CollaborationSession:
        st_str = data.get("status", "OPEN")
        st = CollaborationStatus(st_str) if st_str in CollaborationStatus._value2member_map_ else CollaborationStatus.OPEN
        return cls(
            collaboration_id=data["collaboration_id"],
            mission_id=data.get("mission_id", ""),
            task_id=data.get("task_id", ""),
            participant_agents=list(data.get("participant_agents", [])),
            proposals=[AgentProposal.from_dict(p) for p in data.get("proposals", [])],
            conflicts=[ConflictDetails.from_dict(c) for c in data.get("conflicts", [])],
            arbitrations=[ArbitrationRecord.from_dict(a) for a in data.get("arbitrations", [])],
            status=st,
            round_count=int(data.get("round_count", 1)),
            max_rounds=int(data.get("max_rounds", 3)),
            max_arbitrations=int(data.get("max_arbitrations", 3)),
            max_regenerations=int(data.get("max_regenerations", 2)),
            final_result=data.get("final_result"),
            merged_content=dict(data.get("merged_content", {})),
            created_at=data.get("created_at", utc_now()),
            updated_at=data.get("updated_at", utc_now()),
        )


# ── CONFLICT DETECTOR ──────────────────────────────────────────────────────────

# ── CONFLICT DETECTOR ──────────────────────────────────────────────────────────

class ConflictDetector:
    """
    Deteção abrangente e determinística de conflitos multi-agente com indexação de candidatos (Fase 15.1):
    1. FILE / SYMBOL CONFLICTS (via AST e análise de intervalos de linhas)
    2. CONTRACT CONFLICTS (via CrossFileValidator e RepositoryGraph)
    3. ARCHITECTURAL CONFLICTS (incompatibilidade com decisões de arquitetura)
    4. TEST CONFLICTS (divergência em asserções de testes)
    5. REQUIREMENT AMBIGUITY (interpretações contraditórias)
    6. DETERMINISTIC CANDIDATE INDEXING: Poda de comparações O(N²) redundantes
    """

    def __init__(self, repo_graph: RepositoryGraph | None = None, workspace_root: str | None = None):
        if repo_graph is not None:
            self.graph = repo_graph
        else:
            root = workspace_root or os.getcwd()
            try:
                self.graph = RepositoryGraph(workspace_root=root)
            except Exception:
                self.graph = None
        self.last_hierarchical_index: HierarchicalConflictIndex | None = None
        self.last_candidate_index: ConflictCandidateIndex | None = None
        self.last_conflict_graph: CandidateConflictGraph | None = None
        self.last_components: list[ConflictComponent] = []
        self.last_dense_strategy: DenseConflictStrategy = DenseConflictStrategy.PAIRWISE
        self.last_partition_metadata: ProposalPartitionMetadata | None = None
        self.incremental_graph: IncrementalConflictGraph = IncrementalConflictGraph()
        self.last_candidate_index_latency_ms: float = 0.0
        self.last_hierarchical_index_latency_ms: float = 0.0

    def build_candidate_index(
        self,
        project_id: str,
        task: TaskNode,
        proposals: list[AgentProposal],
        architecture_context: dict[str, Any] | None = None,
    ) -> ConflictCandidateIndex:
        """Constrói deterministamente os índices de ficheiro, símbolo, contrato, requisito e hash."""
        index = ConflictCandidateIndex()
        sorted_proposals = sorted(proposals, key=lambda p: p.proposal_id)

        for p in sorted_proposals:
            # 1. File Index
            all_files = sorted(set(p.affected_files).union(p.content_by_file.keys()))
            for f in all_files:
                if p.proposal_id not in index.file_to_proposals.setdefault(f, []):
                    index.file_to_proposals[f].append(p.proposal_id)

            # 2. Symbol Index (declarado + parsing AST de funções/classes em Python)
            for s in sorted(p.affected_symbols):
                target_files = sorted(p.affected_files or p.content_by_file.keys() or ["__global__"])
                for f in target_files:
                    key = (f, s)
                    if p.proposal_id not in index.symbol_to_proposals.setdefault(key, []):
                        index.symbol_to_proposals[key].append(p.proposal_id)

            for f, code in sorted(p.content_by_file.items()):
                if f.endswith(".py") and code:
                    try:
                        tree = ast.parse(code)
                        for node in ast.walk(tree):
                            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                                key = (f, node.name)
                                if p.proposal_id not in index.symbol_to_proposals.setdefault(key, []):
                                    index.symbol_to_proposals[key].append(p.proposal_id)
                    except Exception:
                        pass

            # 3. Contract Index
            cs = p.metadata.get("contract_signature") or p.metadata.get("metadata", {}).get("contract_signature")
            if cs and isinstance(cs, dict):
                ep = cs.get("endpoint", "")
                if ep and p.proposal_id not in index.contract_to_proposals.setdefault(ep, []):
                    index.contract_to_proposals[ep].append(p.proposal_id)

            for ep_meta in p.metadata.get("api_endpoints_declared", []):
                path = ep_meta.get("path", "")
                if path and p.proposal_id not in index.contract_to_proposals.setdefault(path, []):
                    index.contract_to_proposals[path].append(p.proposal_id)

            for call_meta in p.metadata.get("api_calls_made", []):
                path = call_meta.get("path", "")
                if path and p.proposal_id not in index.contract_to_proposals.setdefault(path, []):
                    index.contract_to_proposals[path].append(p.proposal_id)

            # 4. Requirement Index
            sens = p.metadata.get("case_sensitivity")
            if not sens:
                text = (p.rationale + " " + p.description).lower()
                if "case-sensitive" in text or "case sensitive" in text:
                    sens = "case-sensitive"
                elif "case-insensitive" in text or "case insensitive" in text:
                    sens = "case-insensitive"
            if sens:
                r_key = f"req/case_sensitivity/{sens}"
                if p.proposal_id not in index.requirement_to_proposals.setdefault(r_key, []):
                    index.requirement_to_proposals[r_key].append(p.proposal_id)

            req_id = p.metadata.get("requirement_id") or p.metadata.get("req_id")
            if req_id:
                r_key = f"req/{req_id}"
                if p.proposal_id not in index.requirement_to_proposals.setdefault(r_key, []):
                    index.requirement_to_proposals[r_key].append(p.proposal_id)

            # 5. Architecture Domain Index
            pat = p.metadata.get("architecture_pattern")
            if pat:
                d_key = f"arch/{pat}"
                if p.proposal_id not in index.domain_to_proposals.setdefault(d_key, []):
                    index.domain_to_proposals[d_key].append(p.proposal_id)

            # 6. Content Hash Index (para deteção de propostas duplicadas/equivalentes)
            norm_content = sorted(p.content_by_file.items())
            norm_str = f"{sorted(p.affected_files)}::{p.diff_content}::{norm_content}"
            c_hash = hashlib.sha256(norm_str.encode("utf-8")).hexdigest()[:16]
            if p.proposal_id not in index.content_hash_to_proposals.setdefault(c_hash, []):
                index.content_hash_to_proposals[c_hash].append(p.proposal_id)

        return index

    def build_conflict_graph(
        self,
        project_id: str,
        task: TaskNode,
        proposals: list[AgentProposal],
        architecture_context: dict[str, Any] | None = None,
    ) -> tuple[ConflictCandidateIndex, CandidateConflictGraph]:
        """Gera o grafo de candidatos a conflito com contagem exata de comparações podadas."""
        index = self.build_candidate_index(project_id, task, proposals, architecture_context)
        sorted_proposals = sorted(proposals, key=lambda p: p.proposal_id)
        nodes = [p.proposal_id for p in sorted_proposals]
        edges: dict[tuple[str, str], list[str]] = {}

        def add_candidate_pair(id_a: str, id_b: str, reason: str) -> None:
            if id_a == id_b:
                return
            pair = (id_a, id_b) if id_a < id_b else (id_b, id_a)
            reasons = edges.setdefault(pair, [])
            if reason not in reasons:
                reasons.append(reason)

        # File overlap candidates
        for f, p_ids in sorted(index.file_to_proposals.items()):
            if len(p_ids) > 1:
                u_ids = sorted(set(p_ids))
                for i in range(len(u_ids)):
                    for j in range(i + 1, len(u_ids)):
                        add_candidate_pair(u_ids[i], u_ids[j], "FILE_OVERLAP")

        # Symbol overlap candidates
        for sym_key, p_ids in sorted(index.symbol_to_proposals.items()):
            if len(p_ids) > 1:
                u_ids = sorted(set(p_ids))
                for i in range(len(u_ids)):
                    for j in range(i + 1, len(u_ids)):
                        add_candidate_pair(u_ids[i], u_ids[j], "SYMBOL_OVERLAP")

        # Contract overlap candidates
        for ep, p_ids in sorted(index.contract_to_proposals.items()):
            if len(p_ids) > 1:
                u_ids = sorted(set(p_ids))
                for i in range(len(u_ids)):
                    for j in range(i + 1, len(u_ids)):
                        add_candidate_pair(u_ids[i], u_ids[j], "CONTRACT_OVERLAP")

        # Cross-endpoint candidate pairing for search/API divergence
        all_eps = sorted(index.contract_to_proposals.keys())
        for i in range(len(all_eps)):
            for j in range(i + 1, len(all_eps)):
                ep1, ep2 = all_eps[i], all_eps[j]
                if "search" in ep1.lower() and "search" in ep2.lower():
                    for id_a in index.contract_to_proposals[ep1]:
                        for id_b in index.contract_to_proposals[ep2]:
                            add_candidate_pair(id_a, id_b, "CONTRACT_OVERLAP")

        # Requirement ambiguity candidates
        sens_keys = sorted([k for k in index.requirement_to_proposals.keys() if k.startswith("req/case_sensitivity/")])
        if len(sens_keys) > 1:
            for i in range(len(sens_keys)):
                for j in range(i + 1, len(sens_keys)):
                    for id_a in index.requirement_to_proposals[sens_keys[i]]:
                        for id_b in index.requirement_to_proposals[sens_keys[j]]:
                            add_candidate_pair(id_a, id_b, "REQUIREMENT_AMBIGUITY")

        # Architecture divergence candidates
        arch_style = str((architecture_context or {}).get("preferred_architecture") or (architecture_context or {}).get("required_pattern", "REST")).upper()
        for pat_key, p_ids in sorted(index.domain_to_proposals.items()):
            pat = pat_key.replace("arch/", "").upper()
            if arch_style == "REST" and ("GRAPHQL" in pat or "GQL" in pat):
                for id_a in p_ids:
                    for other in sorted_proposals:
                        if other.proposal_id != id_a:
                            add_candidate_pair(id_a, other.proposal_id, "ARCHITECTURAL_DIVERGENCE")

        # Test divergence candidates
        test_props = [p for p in sorted_proposals if p.agent_type == "TESTING" or "test_verdicts" in p.metadata]
        if len(test_props) > 1:
            for i in range(len(test_props)):
                for j in range(i + 1, len(test_props)):
                    add_candidate_pair(test_props[i].proposal_id, test_props[j].proposal_id, "TEST_DIVERGENCE")

        n = len(sorted_proposals)
        total_pairs = (n * (n - 1)) // 2
        candidate_count = len(edges)
        pruned_comparisons = max(0, total_pairs - candidate_count)

        graph = CandidateConflictGraph(
            nodes=nodes,
            edges=edges,
            candidate_count=candidate_count,
            actual_comparisons=candidate_count,
            pruned_comparisons=pruned_comparisons,
        )

        return index, graph

    def detect_duplicate_proposals(
        self,
        proposals: list[AgentProposal],
    ) -> tuple[list[AgentProposal], list[dict[str, Any]]]:
        """
        Identifica propostas equivalentes ou idênticas (mesmo hash normalizado de patch/conteúdo).
        Retorna (propostas_únicas, lista_de_duplicados).
        """
        seen_hashes: dict[str, str] = {}  # hash -> proposal_id
        unique: list[AgentProposal] = []
        duplicates: list[dict[str, Any]] = []

        for p in proposals:
            has_patch = bool(p.diff_content or p.content_by_file)
            if has_patch:
                norm_content = sorted(p.content_by_file.items())
                norm_str = f"{sorted(p.affected_files)}::{p.diff_content}::{norm_content}"
            else:
                norm_str = f"{sorted(p.affected_files)}::{sorted(p.affected_symbols)}::{p.description}::{p.rationale}"
            c_hash = hashlib.sha256(norm_str.encode("utf-8")).hexdigest()[:16]
            if c_hash in seen_hashes:
                duplicates.append({
                    "proposal_id": p.proposal_id,
                    "duplicate_of": seen_hashes[c_hash],
                    "agent_id": p.agent_id,
                    "content_hash": c_hash,
                })
            else:
                seen_hashes[c_hash] = p.proposal_id
                unique.append(p)

        return unique, duplicates

    def build_hierarchical_index(
        self,
        project_id: str,
        task: TaskNode,
        proposals: list[AgentProposal],
        architecture_context: dict[str, Any] | None = None,
    ) -> HierarchicalConflictIndex:
        """Constrói o índice hierárquico progressivo (Fase 15.2 Secção 1)."""
        h_index = HierarchicalConflictIndex()
        sorted_proposals = sorted(proposals, key=lambda p: p.proposal_id)

        for p in sorted_proposals:
            # 1. Package & File Index
            all_files = sorted(set(p.affected_files).union(p.content_by_file.keys()))
            for f in all_files:
                if p.proposal_id not in h_index.file_to_proposals.setdefault(f, []):
                    h_index.file_to_proposals[f].append(p.proposal_id)

                norm_f = f.replace("\\", "/")
                parts = norm_f.split("/")
                pkg = "/".join(parts[:-1]) if len(parts) > 1 else "."
                if p.proposal_id not in h_index.package_to_proposals.setdefault(pkg, []):
                    h_index.package_to_proposals[pkg].append(p.proposal_id)
                top_pkg = parts[0] if len(parts) > 1 else "."
                if top_pkg != pkg and p.proposal_id not in h_index.package_to_proposals.setdefault(top_pkg, []):
                    h_index.package_to_proposals[top_pkg].append(p.proposal_id)

            # 2. Symbol & Range Index (Python AST + JS/TS Lexical Parser)
            for s in sorted(p.affected_symbols):
                target_files = sorted(p.affected_files or p.content_by_file.keys() or ["__global__"])
                for f in target_files:
                    key = (f, s)
                    if p.proposal_id not in h_index.symbol_to_proposals.setdefault(key, []):
                        h_index.symbol_to_proposals[key].append(p.proposal_id)
                    h_index.symbol_to_files.setdefault(s, set()).add(f)

            for f, code in sorted(p.content_by_file.items()):
                if f.endswith(".py") and code:
                    try:
                        tree = ast.parse(code)
                        for node in getattr(tree, "body", []):
                            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                                key = (f, node.name)
                                if p.proposal_id not in h_index.symbol_to_proposals.setdefault(key, []):
                                    h_index.symbol_to_proposals[key].append(p.proposal_id)
                                h_index.symbol_to_files.setdefault(node.name, set()).add(f)
                                end_l = getattr(node, "end_lineno", node.lineno)
                                h_index.range_to_proposals.setdefault(f, []).append((node.lineno, end_l, p.proposal_id))
                    except Exception:
                        pass
                elif f.endswith((".js", ".jsx", ".ts", ".tsx")) and code:
                    syms = LargeArtifactMergeEngine._parse_js_ts_symbols(code)
                    for name, (s, e, _) in syms.items():
                        key = (f, name)
                        if p.proposal_id not in h_index.symbol_to_proposals.setdefault(key, []):
                            h_index.symbol_to_proposals[key].append(p.proposal_id)
                        h_index.symbol_to_files.setdefault(name, set()).add(f)
                        h_index.range_to_proposals.setdefault(f, []).append((s, e, p.proposal_id))

            # 3. Contract Index & Linkages
            cs = p.metadata.get("contract_signature") or p.metadata.get("metadata", {}).get("contract_signature")
            if cs and isinstance(cs, dict):
                ep = cs.get("endpoint", "")
                if ep and p.proposal_id not in h_index.contract_to_proposals.setdefault(ep, []):
                    h_index.contract_to_proposals[ep].append(p.proposal_id)
                    for f in all_files:
                        for s in p.affected_symbols:
                            h_index.symbol_to_contracts.setdefault((f, s), set()).add(ep)

            for ep_meta in p.metadata.get("api_endpoints_declared", []):
                path = ep_meta.get("path", "")
                if path and p.proposal_id not in h_index.contract_to_proposals.setdefault(path, []):
                    h_index.contract_to_proposals[path].append(p.proposal_id)

            for call_meta in p.metadata.get("api_calls_made", []):
                path = call_meta.get("path", "")
                if path and p.proposal_id not in h_index.contract_to_proposals.setdefault(path, []):
                    h_index.contract_to_proposals[path].append(p.proposal_id)

            # 4. Requirement Index & Linkages
            sens = p.metadata.get("case_sensitivity")
            if not sens:
                text = (p.rationale + " " + p.description).lower()
                if "case-sensitive" in text or "case sensitive" in text:
                    sens = "case-sensitive"
                elif "case-insensitive" in text or "case insensitive" in text:
                    sens = "case-insensitive"
            if sens:
                r_key = f"req/case_sensitivity/{sens}"
                if p.proposal_id not in h_index.requirement_to_proposals.setdefault(r_key, []):
                    h_index.requirement_to_proposals[r_key].append(p.proposal_id)
                for f in all_files:
                    for s in p.affected_symbols:
                        h_index.symbol_to_requirements.setdefault((f, s), set()).add(r_key)

            req_id = p.metadata.get("requirement_id") or p.metadata.get("req_id")
            if req_id:
                r_key = f"req/{req_id}"
                if p.proposal_id not in h_index.requirement_to_proposals.setdefault(r_key, []):
                    h_index.requirement_to_proposals[r_key].append(p.proposal_id)
                for f in all_files:
                    for s in p.affected_symbols:
                        h_index.symbol_to_requirements.setdefault((f, s), set()).add(r_key)

            # 5. Architecture Domain Index
            pat = p.metadata.get("architecture_pattern")
            if pat:
                d_key = f"arch/{pat}"
                if p.proposal_id not in h_index.domain_to_proposals.setdefault(d_key, []):
                    h_index.domain_to_proposals[d_key].append(p.proposal_id)

            # 6. Test Index & Linkages
            verdicts = p.metadata.get("test_verdicts", {})
            for t_name in verdicts.keys():
                if p.proposal_id not in h_index.test_to_proposals.setdefault(t_name, []):
                    h_index.test_to_proposals[t_name].append(p.proposal_id)
                for f in all_files:
                    for s in p.affected_symbols:
                        h_index.symbol_to_tests.setdefault((f, s), set()).add(t_name)

            # 7. Content Hash Index
            norm_content = sorted(p.content_by_file.items())
            norm_str = f"{sorted(p.affected_files)}::{p.diff_content}::{norm_content}"
            c_hash = hashlib.sha256(norm_str.encode("utf-8")).hexdigest()[:16]
            if p.proposal_id not in h_index.content_hash_to_proposals.setdefault(c_hash, []):
                h_index.content_hash_to_proposals[c_hash].append(p.proposal_id)

        return h_index

    def build_hierarchical_conflict_graph(
        self,
        project_id: str,
        task: TaskNode,
        proposals: list[AgentProposal],
        architecture_context: dict[str, Any] | None = None,
    ) -> tuple[HierarchicalConflictIndex, CandidateConflictGraph, list[ConflictComponent], DenseConflictStrategy]:
        """Gera o grafo hierárquico com decomposição em componentes conexas e proteção para cenários densos."""
        h_index = self.build_hierarchical_index(project_id, task, proposals, architecture_context)
        sorted_proposals = sorted(proposals, key=lambda p: p.proposal_id)
        nodes = [p.proposal_id for p in sorted_proposals]
        edges: dict[tuple[str, str], list[str]] = {}

        def add_candidate_pair(id_a: str, id_b: str, reason: str) -> None:
            if id_a == id_b:
                return
            pair = (id_a, id_b) if id_a < id_b else (id_b, id_a)
            reasons = edges.setdefault(pair, [])
            if reason not in reasons:
                reasons.append(reason)

        # File overlap candidates
        for f, p_ids in sorted(h_index.file_to_proposals.items()):
            if len(p_ids) > 1:
                u_ids = sorted(set(p_ids))
                for i in range(len(u_ids)):
                    for j in range(i + 1, len(u_ids)):
                        add_candidate_pair(u_ids[i], u_ids[j], "FILE_OVERLAP")

        # Symbol overlap candidates
        for sym_key, p_ids in sorted(h_index.symbol_to_proposals.items()):
            if len(p_ids) > 1:
                u_ids = sorted(set(p_ids))
                for i in range(len(u_ids)):
                    for j in range(i + 1, len(u_ids)):
                        add_candidate_pair(u_ids[i], u_ids[j], "SYMBOL_OVERLAP")

        # Contract overlap candidates
        for ep, p_ids in sorted(h_index.contract_to_proposals.items()):
            if len(p_ids) > 1:
                u_ids = sorted(set(p_ids))
                for i in range(len(u_ids)):
                    for j in range(i + 1, len(u_ids)):
                        add_candidate_pair(u_ids[i], u_ids[j], "CONTRACT_OVERLAP")

        all_eps = sorted(h_index.contract_to_proposals.keys())
        for i in range(len(all_eps)):
            for j in range(i + 1, len(all_eps)):
                ep1, ep2 = all_eps[i], all_eps[j]
                if ("search" in ep1 and "search" in ep2) or ("auth" in ep1 and "auth" in ep2) or ("api" in ep1 and "api" in ep2):
                    for id_a in h_index.contract_to_proposals[ep1]:
                        for id_b in h_index.contract_to_proposals[ep2]:
                            add_candidate_pair(id_a, id_b, "CONTRACT_OVERLAP")

        # Requirement ambiguity candidates
        sens_keys = [k for k in h_index.requirement_to_proposals.keys() if "case_sensitivity" in k]
        if len(sens_keys) > 1:
            for i in range(len(sens_keys)):
                for j in range(i + 1, len(sens_keys)):
                    for id_a in h_index.requirement_to_proposals[sens_keys[i]]:
                        for id_b in h_index.requirement_to_proposals[sens_keys[j]]:
                            add_candidate_pair(id_a, id_b, "REQUIREMENT_AMBIGUITY")

        # Architecture divergence candidates
        arch_style = str((architecture_context or {}).get("preferred_architecture") or (architecture_context or {}).get("required_pattern", "REST")).upper()
        for pat_key, p_ids in sorted(h_index.domain_to_proposals.items()):
            pat = pat_key.replace("arch/", "").upper()
            if arch_style == "REST" and ("GRAPHQL" in pat or "GQL" in pat):
                for id_a in p_ids:
                    for other in sorted_proposals:
                        if other.proposal_id != id_a:
                            add_candidate_pair(id_a, other.proposal_id, "ARCHITECTURAL_DIVERGENCE")

        # Test divergence candidates
        test_props = [p for p in sorted_proposals if p.agent_type == "TESTING" or "test_verdicts" in p.metadata]
        if len(test_props) > 1:
            for i in range(len(test_props)):
                for j in range(i + 1, len(test_props)):
                    add_candidate_pair(test_props[i].proposal_id, test_props[j].proposal_id, "TEST_DIVERGENCE")

        n = len(sorted_proposals)
        total_pairs = (n * (n - 1)) // 2
        candidate_count = len(edges)
        pruned_comparisons = max(0, total_pairs - candidate_count)

        graph = CandidateConflictGraph(
            nodes=nodes,
            edges=edges,
            candidate_count=candidate_count,
            actual_comparisons=candidate_count,
            pruned_comparisons=pruned_comparisons,
        )

        # Decomposição em componentes conexas
        components = ConnectedConflictGraphEngine.partition_into_components(sorted_proposals, edges)

        # Seleção da estratégia adaptativa multi-critério (Fase 15.3 Secção 1)
        part_meta = AdaptiveProposalPartitioner.evaluate_strategy(
            sorted_proposals, candidate_count, len(components)
        )
        self.last_partition_metadata = part_meta

        # Mapeamento com compatibilidade retroativa para DenseConflictStrategy
        if part_meta.strategy == PartitionStrategy.STAGED_ARBITRATION:
            strategy = DenseConflictStrategy.CONNECTED_COMPONENTS
        elif part_meta.strategy == PartitionStrategy.COMPONENT_CENTRIC:
            strategy = DenseConflictStrategy.CONNECTED_COMPONENTS
        elif part_meta.strategy == PartitionStrategy.HIERARCHICAL_PARTITIONING:
            strategy = DenseConflictStrategy.BUCKETED_COMPARISON
        else:
            strategy = DenseConflictStrategy.PAIRWISE

        return h_index, graph, components, strategy

    def detect_conflicts(
        self,
        project_id: str,
        task: TaskNode,
        proposals: list[AgentProposal],
        architecture_context: dict[str, Any] | None = None,
        use_index: bool = True,
    ) -> list[ConflictDetails]:
        """
        Deteção de conflitos determinística.
        Se use_index=True (default), utiliza o HierarchicalConflictIndex e CandidateConflictGraph
        para podar comparações redundantes com ZERO falsos negativos garantidos.
        """
        if len(proposals) < 2:
            return []

        t0 = time.perf_counter()
        h_index, graph, components, strategy = self.build_hierarchical_conflict_graph(
            project_id, task, proposals, architecture_context
        )
        t_index = (time.perf_counter() - t0) * 1000.0

        self.last_hierarchical_index = h_index
        self.last_candidate_index = ConflictCandidateIndex(
            file_to_proposals=h_index.file_to_proposals,
            symbol_to_proposals=h_index.symbol_to_proposals,
            contract_to_proposals=h_index.contract_to_proposals,
            requirement_to_proposals=h_index.requirement_to_proposals,
            domain_to_proposals=h_index.domain_to_proposals,
            content_hash_to_proposals=h_index.content_hash_to_proposals,
        )
        self.last_conflict_graph = graph
        self.last_components = components
        self.last_dense_strategy = strategy
        self.last_candidate_index_latency_ms = t_index
        self.last_hierarchical_index_latency_ms = t_index

        if not use_index:
            return self.detect_conflicts_exhaustive(project_id, task, proposals, architecture_context)

        conflicts: list[ConflictDetails] = []
        prop_map = {p.proposal_id: p for p in proposals}
        seen_keys: set[str] = set()

        # Avaliar apenas os pares no grafo de candidatos
        for (id_a, id_b), reasons in sorted(graph.edges.items()):
            p1, p2 = prop_map.get(id_a), prop_map.get(id_b)
            if not p1 or not p2:
                continue

            # 1. File / Symbol Overlap
            if "FILE_OVERLAP" in reasons or "SYMBOL_OVERLAP" in reasons:
                shared_files = sorted(set(p1.affected_files).intersection(p2.affected_files))
                for f in shared_files:
                    shared_symbols = sorted(set(p1.affected_symbols).intersection(p2.affected_symbols))
                    if shared_symbols:
                        for sym in shared_symbols:
                            key = ConflictKey(
                                project_id=project_id,
                                task_id=task.task_id,
                                resource=f,
                                symbol=sym,
                                conflict_type=ConflictType.SYMBOL_CONFLICT,
                            )
                            if key.make_key() not in seen_keys:
                                seen_keys.add(key.make_key())
                                conflicts.append(ConflictDetails(
                                    conflict_key=key,
                                    proposals_involved=[p1.proposal_id, p2.proposal_id],
                                    description=f"Propostas '{p1.agent_id}' e '{p2.agent_id}' alteram o mesmo símbolo '{sym}' em '{f}'",
                                    severity="HIGH",
                                    metadata={"file": f, "symbol": sym},
                                ))
                    else:
                        base_files = task.metadata.get("base_files", {})
                        overlap = self._check_diff_overlap(f, p1, p2, base_files=base_files)
                        if overlap:
                            key = ConflictKey(
                                project_id=project_id,
                                task_id=task.task_id,
                                resource=f,
                                symbol="__file_overlap__",
                                conflict_type=ConflictType.FILE_CONFLICT,
                            )
                            if key.make_key() not in seen_keys:
                                seen_keys.add(key.make_key())
                                conflicts.append(ConflictDetails(
                                    conflict_key=key,
                                    proposals_involved=[p1.proposal_id, p2.proposal_id],
                                    description=f"Propostas '{p1.agent_id}' e '{p2.agent_id}' têm diffs sobrepostos no ficheiro '{f}'",
                                    severity="HIGH",
                                    metadata={"file": f},
                                ))

            # 2. Contract Overlap
            if "CONTRACT_OVERLAP" in reasons:
                s1 = p1.metadata.get("contract_signature") or p1.metadata.get("metadata", {}).get("contract_signature")
                s2 = p2.metadata.get("contract_signature") or p2.metadata.get("metadata", {}).get("contract_signature")
                if s1 and s2:
                    ep1, params1 = s1.get("endpoint"), s1.get("params")
                    ep2, params2 = s2.get("endpoint"), s2.get("params")
                    if ep1 and ep2 and ep1 == ep2 and params1 != params2:
                        key = ConflictKey(
                            project_id=project_id,
                            task_id=task.task_id,
                            resource=ep1,
                            symbol=f"{params1} vs {params2}",
                            conflict_type=ConflictType.CONTRACT_CONFLICT,
                        )
                        if key.make_key() not in seen_keys:
                            seen_keys.add(key.make_key())
                            conflicts.append(ConflictDetails(
                                conflict_key=key,
                                proposals_involved=[p1.proposal_id, p2.proposal_id],
                                description=f"Incompatibilidade de contrato de API: Contract parameter mismatch ({params1} vs {params2})",
                                severity="CRITICAL",
                            ))

                # Endpoints e chamadas
                for ep_meta in p1.metadata.get("api_endpoints_declared", []):
                    be_m, be_path = str(ep_meta.get("method", "GET")).upper(), str(ep_meta.get("path", ""))
                    for call_meta in p2.metadata.get("api_calls_made", []):
                        fe_m, fe_path = str(call_meta.get("method", "GET")).upper(), str(call_meta.get("path", ""))
                        if fe_path and be_path:
                            if (fe_path == be_path and fe_m != be_m) or (fe_path != be_path and "search" in fe_path.lower() and "search" in be_path.lower()):
                                key = ConflictKey(
                                    project_id=project_id,
                                    task_id=task.task_id,
                                    resource=f"{fe_path} <-> {be_path}",
                                    symbol=f"{fe_m}",
                                    conflict_type=ConflictType.CONTRACT_CONFLICT,
                                )
                                if key.make_key() not in seen_keys:
                                    seen_keys.add(key.make_key())
                                    conflicts.append(ConflictDetails(
                                        conflict_key=key,
                                        proposals_involved=[p1.proposal_id, p2.proposal_id],
                                        description=f"Incompatibilidade de contrato de API: Contract parameter mismatch ({fe_m} vs {be_m})",
                                        severity="CRITICAL",
                                        metadata={"frontend_route": fe_path, "backend_route": be_path},
                                    ))

            # 3. Requirement Ambiguity
            if "REQUIREMENT_AMBIGUITY" in reasons:
                conf_req = self._detect_requirement_conflicts(project_id, task.task_id, [p1, p2], task)
                for c in conf_req:
                    if c.conflict_key.make_key() not in seen_keys:
                        seen_keys.add(c.conflict_key.make_key())
                        conflicts.append(c)

        # 4. Architectural conflicts globais
        conf_arch = self._detect_architectural_conflicts(project_id, task.task_id, proposals, architecture_context)
        for c in conf_arch:
            if c.conflict_key.make_key() not in seen_keys:
                seen_keys.add(c.conflict_key.make_key())
                conflicts.append(c)

        return conflicts

    def detect_conflicts_exhaustive(
        self,
        project_id: str,
        task: TaskNode,
        proposals: list[AgentProposal],
        architecture_context: dict[str, Any] | None = None,
    ) -> list[ConflictDetails]:
        """Execução exaustiva O(N²) de referência para verificação do Invariante de Completude."""
        conflicts: list[ConflictDetails] = []
        conflicts.extend(self._detect_file_and_symbol_conflicts(project_id, task.task_id, proposals))
        conflicts.extend(self._detect_contract_conflicts(project_id, task.task_id, proposals))
        conflicts.extend(self._detect_architectural_conflicts(project_id, task.task_id, proposals, architecture_context))
        conflicts.extend(self._detect_test_conflicts(project_id, task.task_id, proposals))
        conflicts.extend(self._detect_requirement_conflicts(project_id, task.task_id, proposals, task))
        return conflicts

    def _detect_file_and_symbol_conflicts(
        self, project_id: str, task_id: str, proposals: list[AgentProposal], base_files: dict[str, str] | None = None
    ) -> list[ConflictDetails]:
        conflicts: list[ConflictDetails] = []
        n = len(proposals)

        for i in range(n):
            for j in range(i + 1, n):
                p1, p2 = proposals[i], proposals[j]
                shared_files = sorted(set(p1.affected_files).intersection(p2.affected_files))
                for f in shared_files:
                    shared_symbols = sorted(set(p1.affected_symbols).intersection(p2.affected_symbols))
                    if shared_symbols:
                        for sym in shared_symbols:
                            key = ConflictKey(
                                project_id=project_id,
                                task_id=task_id,
                                resource=f,
                                symbol=sym,
                                conflict_type=ConflictType.SYMBOL_CONFLICT,
                            )
                            conflicts.append(ConflictDetails(
                                conflict_key=key,
                                proposals_involved=[p1.proposal_id, p2.proposal_id],
                                description=f"Propostas '{p1.agent_id}' e '{p2.agent_id}' alteram o mesmo símbolo '{sym}' em '{f}'",
                                severity="HIGH",
                                metadata={"file": f, "symbol": sym},
                            ))
                    else:
                        overlap = self._check_diff_overlap(f, p1, p2, base_files=base_files)
                        if overlap:
                            key = ConflictKey(
                                project_id=project_id,
                                task_id=task_id,
                                resource=f,
                                symbol="__file_overlap__",
                                conflict_type=ConflictType.FILE_CONFLICT,
                            )
                            conflicts.append(ConflictDetails(
                                conflict_key=key,
                                proposals_involved=[p1.proposal_id, p2.proposal_id],
                                description=f"Propostas '{p1.agent_id}' e '{p2.agent_id}' têm diffs sobrepostos no ficheiro '{f}'",
                                severity="HIGH",
                                metadata={"file": f},
                            ))

        return conflicts

    def _are_proposals_symbol_disjoint(self, file_path: str, c1: str, c2: str) -> bool:
        """Verifica se duas propostas de código Python alteram símbolos mutuamente exclusivos."""
        try:
            tree1 = ast.parse(c1)
            tree2 = ast.parse(c2)
            syms1 = {
                n.name: (n.lineno, getattr(n, "end_lineno", n.lineno))
                for n in tree1.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            }
            syms2 = {
                n.name: (n.lineno, getattr(n, "end_lineno", n.lineno))
                for n in tree2.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            }
            if not syms1 or not syms2:
                return False

            common_names = sorted(set(syms1.keys()).intersection(syms2.keys()))
            if len(common_names) < 2:
                return False

            lines1 = c1.splitlines(keepends=True)
            lines2 = c2.splitlines(keepends=True)

            differing = set()
            for name in common_names:
                s1, e1 = syms1[name]
                s2, e2 = syms2[name]
                if lines1[s1 - 1 : e1] != lines2[s2 - 1 : e2]:
                    differing.add(name)

            if len(differing) >= 2 and len(common_names) >= len(differing):
                base_chunks = []
                for name in common_names:
                    s2, e2 = syms2[name]
                    base_chunks.extend(lines2[s2 - 1 : e2])
                    base_chunks.append("\n")
                synth_base = "".join(base_chunks)
                ok, _, _ = PatchMergeEngine.auto_merge_disjoint(file_path, synth_base, c1, c2)
                if ok:
                    return True
        except Exception:
            pass
        return False

    def _check_diff_overlap(
        self, file_path: str, p1: AgentProposal, p2: AgentProposal, base_files: dict[str, str] | None = None
    ) -> bool:
        """Verifica se duas propostas para o mesmo ficheiro têm sobreposição de linhas."""
        c1 = p1.content_by_file.get(file_path, "")
        c2 = p2.content_by_file.get(file_path, "")
        if not c1 or not c2:
            return True

        if c1 == c2:
            return False

        # Se base_files ou metadata contiver o base_content, verificar disjunção real
        base = (base_files or {}).get(file_path) or p1.metadata.get("base_content") or p2.metadata.get("base_content")
        if base:
            is_disjoint, _ = PatchMergeEngine.are_patches_disjoint(file_path, base, c1, c2)
            if is_disjoint:
                return False

        # Se ambos os agentes declararam símbolos afetados disjuntos
        if p1.affected_symbols and p2.affected_symbols:
            if set(p1.affected_symbols).isdisjoint(set(p2.affected_symbols)):
                return False

        # Fast Path: Se for código Python com funções separadas e blocos idênticos intermediários
        if file_path.endswith(".py"):
            if self._are_proposals_symbol_disjoint(file_path, c1, c2):
                return False
            try:
                t1 = ast.parse(c1)
                t2 = ast.parse(c2)
                s1 = {n.name for n in t1.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
                s2 = {n.name for n in t2.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
                common = s1.intersection(s2)
                if len(common) >= 2:
                    lines1 = c1.splitlines(keepends=True)
                    lines2 = c2.splitlines(keepends=True)
                    sm = difflib.SequenceMatcher(None, lines1, lines2)
                    equal_blocks = [b for b in sm.get_matching_blocks() if b.size > 0]
                    if len(equal_blocks) >= 2:
                        return False
            except Exception:
                pass

        lines1 = c1.splitlines()
        lines2 = c2.splitlines()
        diff = list(difflib.unified_diff(lines1, lines2))
        return len(diff) > 0

    def _detect_contract_conflicts(
        self, project_id: str, task_id: str, proposals: list[AgentProposal]
    ) -> list[ConflictDetails]:
        conflicts: list[ConflictDetails] = []
        frontend_endpoints: list[tuple[AgentProposal, str, str]] = []
        backend_endpoints: list[tuple[AgentProposal, str, str]] = []

        signatures = [(p, p.metadata.get("contract_signature") or p.metadata.get("metadata", {}).get("contract_signature")) for p in proposals]
        signatures = [(p, s) for p, s in signatures if s]
        for i in range(len(signatures)):
            for j in range(i + 1, len(signatures)):
                p1, s1 = signatures[i]
                p2, s2 = signatures[j]
                ep1, params1 = s1.get("endpoint"), s1.get("params")
                ep2, params2 = s2.get("endpoint"), s2.get("params")
                if ep1 and ep2 and ep1 == ep2 and params1 != params2:
                    key = ConflictKey(
                        project_id=project_id,
                        task_id=task_id,
                        resource=ep1,
                        symbol=f"{params1} vs {params2}",
                        conflict_type=ConflictType.CONTRACT_CONFLICT,
                    )
                    conflicts.append(ConflictDetails(
                        conflict_key=key,
                        proposals_involved=[p1.proposal_id, p2.proposal_id],
                        description=f"Incompatibilidade de contrato de API: Contract parameter mismatch ({params1} vs {params2})",
                        severity="CRITICAL",
                    ))

        for p in proposals:
            for ep_meta in p.metadata.get("api_endpoints_declared", []):
                method = str(ep_meta.get("method", "GET")).upper()
                path = str(ep_meta.get("path", ""))
                backend_endpoints.append((p, method, path))
            for call_meta in p.metadata.get("api_calls_made", []):
                method = str(call_meta.get("method", "GET")).upper()
                path = str(call_meta.get("path", ""))
                frontend_endpoints.append((p, method, path))

        for p_fe, fe_m, fe_path in frontend_endpoints:
            for p_be, be_m, be_path in backend_endpoints:
                if fe_path and be_path:
                    if (fe_path == be_path and fe_m != be_m) or (fe_path != be_path and "search" in fe_path.lower() and "search" in be_path.lower()):
                        key = ConflictKey(
                            project_id=project_id,
                            task_id=task_id,
                            resource=f"{fe_path} <-> {be_path}",
                            symbol=f"{fe_m}",
                            conflict_type=ConflictType.CONTRACT_CONFLICT,
                        )
                        conflicts.append(ConflictDetails(
                            conflict_key=key,
                            proposals_involved=[p_fe.proposal_id, p_be.proposal_id],
                            description=f"Incompatibilidade de contrato de API: Contract parameter mismatch ({fe_m} vs {be_m})",
                            severity="CRITICAL",
                            metadata={"frontend_route": fe_path, "backend_route": be_path},
                        ))

        return conflicts

    def _detect_architectural_conflicts(
        self,
        project_id: str,
        task_id: str,
        proposals: list[AgentProposal],
        architecture_context: dict[str, Any] | None = None,
    ) -> list[ConflictDetails]:
        conflicts: list[ConflictDetails] = []
        arch_style = (architecture_context or {}).get("preferred_architecture") or (architecture_context or {}).get("required_pattern", "REST")
        arch_style = str(arch_style).upper()

        for p in proposals:
            tech_stack = [str(t).upper() for t in p.metadata.get("technologies", [])]
            arch_pat = str(p.metadata.get("architecture_pattern", "")).upper()
            if arch_style == "REST" and ("GRAPHQL" in tech_stack or "GQL" in tech_stack or "GRAPHQL" in arch_pat):
                key = ConflictKey(
                    project_id=project_id,
                    task_id=task_id,
                    resource="architecture/style",
                    symbol="GraphQL",
                    conflict_type=ConflictType.ARCHITECTURAL_CONFLICT,
                )
                conflicts.append(ConflictDetails(
                    conflict_key=key,
                    proposals_involved=[p.proposal_id],
                    description=f"Conflito Arquitetural: Agente '{p.agent_id}' propôs 'GraphQL' quando a arquitetura definida requer 'REST'",
                    severity="HIGH",
                    metadata={"defined_architecture": arch_style, "proposed": "GRAPHQL"},
                ))

        return conflicts

    def _detect_test_conflicts(
        self, project_id: str, task_id: str, proposals: list[AgentProposal]
    ) -> list[ConflictDetails]:
        conflicts: list[ConflictDetails] = []
        return conflicts

    def _detect_requirement_conflicts(
        self, project_id: str, task_id: str, proposals: list[AgentProposal], task: TaskNode
    ) -> list[ConflictDetails]:
        conflicts: list[ConflictDetails] = []
        sensitivities: dict[str, list[AgentProposal]] = {}
        for p in proposals:
            sens = p.metadata.get("case_sensitivity")
            if not sens:
                text = (p.rationale + " " + p.description).lower()
                if "case-sensitive" in text or "case sensitive" in text:
                    sens = "case-sensitive"
                elif "case-insensitive" in text or "case insensitive" in text:
                    sens = "case-insensitive"
            if sens:
                sensitivities.setdefault(str(sens).lower(), []).append(p)

        if len(sensitivities) > 1:
            proposals_involved = [p.proposal_id for group in sensitivities.values() for p in group]
            key = ConflictKey(
                project_id=project_id,
                task_id=task_id,
                resource="requirements/search",
                symbol="case_sensitivity",
                conflict_type=ConflictType.REQUIREMENT_CONFLICT,
            )
            conflicts.append(ConflictDetails(
                conflict_key=key,
                proposals_involved=proposals_involved,
                description=f"Ambiguidade de Requisitos: Case-sensitivity ambiguity ({list(sensitivities.keys())})",
                severity="MEDIUM",
                metadata={"interpretations": list(sensitivities.keys())},
            ))

        return conflicts


# ── STRUCTURAL PATCH & AUTO-MERGE ENGINE (Fase 15.1 Scalable Engine) ───────────

class LargeArtifactMergeEngine:
    """
    Mecanismo de merge escalável para artefactos grandes (Fase 15.2 Secção 4, 5, 6, 8, 10).
    Estratégia em 4 camadas estruturadas:
      Layer 1: Structural AST Merge (Python ast & JS/TS lexical-structural scanner)
      Layer 2: Symbol / Line-Range Splicing
      Layer 3: Localized Windowed Block Merge (5k, 10k, 25k, 50k, 100k linhas)
      Layer 4: Deterministic Line Diff Fallback (SequenceMatcher)
    Garantias:
      - Determinismo estrito (byte-identical SHA-256)
      - Self-Healing com ASTRepairEngineV2
      - Registo de falhas em MergeFailureMemory
    """
    metrics: dict[str, Any] = {
        "structural_count": 0,
        "symbol_range_count": 0,
        "windowed_count": 0,
        "fallback_count": 0,
        "conflict_count": 0,
        "total_latency_ms": 0.0,
    }

    @classmethod
    def _parse_js_ts_symbols(cls, content: str) -> dict[str, tuple[int, int, str]]:
        symbols: dict[str, tuple[int, int, str]] = {}
        lines = content.splitlines()
        n = len(lines)
        i = 0

        func_pat = re.compile(r'^(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+([A-Za-z0-9_$]+)')
        class_pat = re.compile(r'^(?:export\s+)?(?:default\s+)?class\s+([A-Za-z0-9_$]+)')
        const_pat = re.compile(r'^(?:export\s+)?(?:const|let|var)\s+([A-Za-z0-9_$]+)\s*[:=]')
        test_pat = re.compile(r'^(?:describe|it|test)\s*\(\s*["\']([^"\']+)["\']')

        while i < n:
            line = lines[i].strip()
            if line.startswith("//") or line.startswith("/*"):
                i += 1
                continue

            match_f = func_pat.match(line)
            match_c = class_pat.match(line)
            match_v = const_pat.match(line)
            match_t = test_pat.match(line)

            matched_name = None
            kind = "code"
            if match_f:
                matched_name = match_f.group(1)
                kind = "function"
            elif match_c:
                matched_name = match_c.group(1)
                kind = "class"
            elif match_t:
                matched_name = match_t.group(1)
                kind = "test"
            elif match_v:
                matched_name = match_v.group(1)
                kind = "variable"

            if matched_name:
                start_l = i + 1  # 1-indexed
                open_braces = 0
                started_brace = False
                end_l = start_l

                for j in range(i, n):
                    cur = lines[j]
                    for ch in cur:
                        if ch == '{':
                            open_braces += 1
                            started_brace = True
                        elif ch == '}':
                            open_braces -= 1

                    if started_brace and open_braces <= 0:
                        end_l = j + 1
                        break
                    elif not started_brace and ';' in cur:
                        end_l = j + 1
                        break
                    end_l = j + 1
                symbols[matched_name] = (start_l, end_l, kind)
                i = max(i + 1, end_l)
            else:
                i += 1

        return symbols

    @classmethod
    def _try_structural_merge_js_ts(
        cls, file_path: str, base_content: str, content_a: str, content_b: str
    ) -> tuple[bool, str, str]:
        syms_base = cls._parse_js_ts_symbols(base_content)
        syms_a = cls._parse_js_ts_symbols(content_a)
        syms_b = cls._parse_js_ts_symbols(content_b)

        if not syms_base and not (syms_a or syms_b):
            return False, "", "NO_JS_TS_SYMBOLS"

        base_lines = base_content.splitlines(keepends=True)
        lines_a = content_a.splitlines(keepends=True)
        lines_b = content_b.splitlines(keepends=True)

        mod_a = set()
        for name, (s, e, _) in syms_base.items():
            if name in syms_a:
                sa, ea, _ = syms_a[name]
                if base_lines[s - 1 : e] != lines_a[sa - 1 : ea]:
                    mod_a.add(name)
            else:
                mod_a.add(name)
        for name in syms_a:
            if name not in syms_base:
                mod_a.add(name)

        mod_b = set()
        for name, (s, e, _) in syms_base.items():
            if name in syms_b:
                sb, eb, _ = syms_b[name]
                if base_lines[s - 1 : e] != lines_b[sb - 1 : eb]:
                    mod_b.add(name)
            else:
                mod_b.add(name)
        for name in syms_b:
            if name not in syms_base:
                mod_b.add(name)

        if mod_a and mod_b and not mod_a.intersection(mod_b):
            edits: list[tuple[int, int, list[str]]] = []
            for name in mod_a:
                if name in syms_base and name in syms_a:
                    s_b, e_b, _ = syms_base[name]
                    s_a, e_a, _ = syms_a[name]
                    edits.append((s_b - 1, e_b, lines_a[s_a - 1 : e_a]))
            for name in mod_b:
                if name in syms_base and name in syms_b:
                    s_b, e_b, _ = syms_base[name]
                    s_2, e_2, _ = syms_b[name]
                    edits.append((s_b - 1, e_b, lines_b[s_2 - 1 : e_2]))

            edits.sort(key=lambda item: item[0])
            merged: list[str] = []
            curr = 0
            for s, e, new_lines in edits:
                merged.extend(base_lines[curr:s])
                merged.extend(new_lines)
                curr = e
            merged.extend(base_lines[curr:])
            result_str = "".join(merged)
            return True, result_str, "STRUCTURAL_JS_TS_MERGE_SUCCESS"

        if mod_a.intersection(mod_b):
            return False, "", f"STRUCTURAL_CONFLICT on symbols: {sorted(mod_a.intersection(mod_b))}"

        return False, "", "STRUCTURAL_CANNOT_PROVE_DISJOINT"

    @classmethod
    def _try_structural_merge_python(
        cls, file_path: str, base_content: str, content_a: str, content_b: str
    ) -> tuple[bool, str, str]:
        return PatchMergeEngine._try_ast_disjoint_python(file_path, base_content, content_a, content_b)

    @classmethod
    def _try_windowed_block_merge(
        cls, file_path: str, base_content: str, content_a: str, content_b: str
    ) -> tuple[bool, str, str]:
        base_lines = base_content.splitlines(keepends=True)
        lines_a = content_a.splitlines(keepends=True)
        lines_b = content_b.splitlines(keepends=True)

        b_start_a, b_end_a, _, _ = PatchMergeEngine._get_changed_bounds(base_lines, lines_a)
        b_start_b, b_end_b, _, _ = PatchMergeEngine._get_changed_bounds(base_lines, lines_b)

        win_start = max(0, min(b_start_a, b_start_b) - 50)
        win_end = min(len(base_lines), max(b_end_a, b_end_b) + 50)
        win_base = "".join(base_lines[win_start:win_end])
        win_a = "".join(lines_a[win_start:min(len(lines_a), win_end + (len(lines_a) - len(base_lines)))])
        win_b = "".join(lines_b[win_start:min(len(lines_b), win_end + (len(lines_b) - len(base_lines)))])

        w_ok, w_merged, w_reason = PatchMergeEngine._sequence_matcher_merge(win_base, win_a, win_b)
        if w_ok:
            full_merged = "".join(base_lines[:win_start]) + w_merged + "".join(base_lines[win_end:])
            return True, full_merged, "WINDOWED_BLOCK_MERGE_SUCCESS"

        return False, "", f"WINDOWED_BLOCK_FAILED: {w_reason}"

    @classmethod
    def auto_merge_disjoint(
        cls,
        file_path: str,
        base_content: str,
        content_a: str,
        content_b: str,
        failure_memory: MergeFailureMemory | None = None,
    ) -> tuple[bool, str, str]:
        t0 = time.perf_counter()
        line_count = max(len(base_content.splitlines()), len(content_a.splitlines()), len(content_b.splitlines()))

        # Fast Path 0: Identical content
        if content_a == content_b:
            cls.metrics["structural_count"] += 1
            cls.metrics["total_latency_ms"] += (time.perf_counter() - t0) * 1000.0
            return True, content_a, "IDENTICAL_CONTENT"

        # Fast Path 1: Line-Range O(L)
        base_lines = base_content.splitlines(keepends=True)
        lines_a = content_a.splitlines(keepends=True)
        lines_b = content_b.splitlines(keepends=True)

        b_start_a, b_end_a, m_start_a, m_end_a = PatchMergeEngine._get_changed_bounds(base_lines, lines_a)
        b_start_b, b_end_b, m_start_b, m_end_b = PatchMergeEngine._get_changed_bounds(base_lines, lines_b)

        if b_end_a <= b_start_b:
            merged = (
                base_lines[:b_start_a]
                + lines_a[m_start_a:m_end_a]
                + base_lines[b_end_a:b_start_b]
                + lines_b[m_start_b:m_end_b]
                + base_lines[b_end_b:]
            )
            cls.metrics["symbol_range_count"] += 1
            cls.metrics["total_latency_ms"] += (time.perf_counter() - t0) * 1000.0
            return True, "".join(merged), "DISJOINT_AUTO_MERGE_SUCCESS"

        elif b_end_b <= b_start_a:
            merged = (
                base_lines[:b_start_b]
                + lines_b[m_start_b:m_end_b]
                + base_lines[b_end_b:b_start_a]
                + lines_a[m_start_a:m_end_a]
                + base_lines[b_end_a:]
            )
            cls.metrics["symbol_range_count"] += 1
            cls.metrics["total_latency_ms"] += (time.perf_counter() - t0) * 1000.0
            return True, "".join(merged), "DISJOINT_AUTO_MERGE_SUCCESS"

        # Layer 1: Structural AST Merge (Python)
        if file_path.endswith(".py"):
            ast_ok, ast_merged, ast_reason = cls._try_structural_merge_python(file_path, base_content, content_a, content_b)
            if ast_ok:
                cls.metrics["structural_count"] += 1
                cls.metrics["total_latency_ms"] += (time.perf_counter() - t0) * 1000.0
                return True, ast_merged, ast_reason
            elif "AST_PARSE_FAILED" in ast_reason and failure_memory:
                failure_memory.record_failure(MergeFailureRecord(
                    failure_id=str(uuid.uuid4())[:8],
                    file_path=file_path,
                    line_count=line_count,
                    language="python",
                    strategy_used="STRUCTURAL_AST",
                    fallback_used="WINDOWED_BLOCK",
                    error_type="AST_PARSE_FAILED",
                    error_details=ast_reason,
                ))

        # Layer 1: Structural Merge (JS / TS)
        if file_path.endswith((".js", ".jsx", ".ts", ".tsx")):
            js_ok, js_merged, js_reason = cls._try_structural_merge_js_ts(file_path, base_content, content_a, content_b)
            if js_ok:
                cls.metrics["structural_count"] += 1
                cls.metrics["total_latency_ms"] += (time.perf_counter() - t0) * 1000.0
                return True, js_merged, js_reason
            elif "STRUCTURAL_CONFLICT" in js_reason:
                cls.metrics["conflict_count"] += 1
                cls.metrics["total_latency_ms"] += (time.perf_counter() - t0) * 1000.0
                return False, "", js_reason

        # Layer 3: Localized Windowed Block Merge (para ficheiros grandes >= 500 linhas)
        if line_count >= 500:
            w_ok, w_merged, w_reason = cls._try_windowed_block_merge(file_path, base_content, content_a, content_b)
            if w_ok:
                cls.metrics["windowed_count"] += 1
                cls.metrics["total_latency_ms"] += (time.perf_counter() - t0) * 1000.0
                return True, w_merged, "WINDOWED_BLOCK_MERGE_SUCCESS"

        # Layer 4: Deterministic Line Diff Fallback (SequenceMatcher)
        cls.metrics["fallback_count"] += 1
        ok, result_str, reason = PatchMergeEngine._sequence_matcher_merge(base_content, content_a, content_b)

        if not ok:
            cls.metrics["conflict_count"] += 1
            cls.metrics["total_latency_ms"] += (time.perf_counter() - t0) * 1000.0
            if failure_memory:
                failure_memory.record_failure(MergeFailureRecord(
                    failure_id=str(uuid.uuid4())[:8],
                    file_path=file_path,
                    line_count=line_count,
                    language=file_path.split(".")[-1] if "." in file_path else "unknown",
                    strategy_used="LINE_DIFF_FALLBACK",
                    fallback_used="NONE",
                    error_type="LINE_OVERLAP",
                    error_details=reason,
                ))
            return False, "", f"CANNOT_AUTO_MERGE: {reason}"

        # Self-healing de sintaxe para Python
        if file_path.endswith(".py"):
            try:
                ast.parse(result_str)
            except SyntaxError as syn_err:
                if ASTRepairEngineV2 is not None:
                    try:
                        repairer = ASTRepairEngineV2()
                        rep_res = repairer.repair_syntax_python(result_str, file_path)
                        if rep_res.success:
                            cls.metrics["total_latency_ms"] += (time.perf_counter() - t0) * 1000.0
                            return True, rep_res.repaired_content, "SELF_HEALED_AUTO_MERGE_SUCCESS"
                    except Exception:
                        pass
                cls.metrics["conflict_count"] += 1
                cls.metrics["total_latency_ms"] += (time.perf_counter() - t0) * 1000.0
                return False, "", f"CANNOT_AUTO_MERGE: SyntaxError in merged content: {syn_err}"

        cls.metrics["total_latency_ms"] += (time.perf_counter() - t0) * 1000.0
        return True, result_str, "DISJOINT_AUTO_MERGE_SUCCESS"


class PatchMergeEngine:
    """
    Mesclador determinístico de alterações de alta escalabilidade (Fase 15.1):
    1. Fast Path O(1) para conteúdo idêntico.
    2. Fast Path AST-First para funções e classes isoladas em Python/JS/TS.
    3. Fast Path Line-Range O(L) com prefixo/sufixo linear.
    4. Windowed Local Diff para ficheiros grandes (>= 500 linhas).
    5. Fallback determinístico para SequenceMatcher com Self-Healing de AST.
    """

    metrics: dict[str, Any] = {
        "fast_path_count": 0,
        "full_diff_count": 0,
        "conflict_count": 0,
        "total_latency_ms": 0.0,
    }

    @staticmethod
    def _get_changed_bounds(base_lines: list[str], modified_lines: list[str]) -> tuple[int, int, int, int]:
        """
        Calcula os limites do intervalo alterado em O(L) via prefixo e sufixo comuns.
        Retorna (base_start, base_end, mod_start, mod_end).
        """
        prefix = 0
        max_prefix = min(len(base_lines), len(modified_lines))
        while prefix < max_prefix and base_lines[prefix] == modified_lines[prefix]:
            prefix += 1

        suffix = 0
        max_suffix = min(len(base_lines) - prefix, len(modified_lines) - prefix)
        while suffix < max_suffix and base_lines[-(suffix + 1)] == modified_lines[-(suffix + 1)]:
            suffix += 1

        base_start = prefix
        base_end = len(base_lines) - suffix
        mod_start = prefix
        mod_end = len(modified_lines) - suffix
        return base_start, base_end, mod_start, mod_end

    @classmethod
    def are_patches_disjoint(
        cls,
        file_path: str,
        base_content: str,
        content_a: str,
        content_b: str,
    ) -> tuple[bool, str]:
        # Fast Path 0: Identical content
        if content_a == content_b:
            return True, "IDENTICAL"

        base_lines = base_content.splitlines(keepends=True)
        lines_a = content_a.splitlines(keepends=True)
        lines_b = content_b.splitlines(keepends=True)

        # Fast Path 1: Line-Range O(L)
        b_start_a, b_end_a, _, _ = cls._get_changed_bounds(base_lines, lines_a)
        b_start_b, b_end_b, _, _ = cls._get_changed_bounds(base_lines, lines_b)

        if b_end_a <= b_start_b or b_end_b <= b_start_a:
            return True, "LINE_RANGE_DISJOINT"

        # Fast Path 2: AST Disjoint (para Python)
        if file_path.endswith(".py"):
            ast_ok, _, ast_reason = cls._try_ast_disjoint_python(file_path, base_content, content_a, content_b)
            if ast_ok:
                return True, ast_reason

        # Fast Path 2.5: AST Disjoint (para JS/TS)
        if file_path.endswith((".js", ".jsx", ".ts", ".tsx")):
            js_ok, _, js_reason = LargeArtifactMergeEngine._try_structural_merge_js_ts(file_path, base_content, content_a, content_b)
            if js_ok:
                return True, js_reason

        # Fallback para SequenceMatcher
        sm_a = difflib.SequenceMatcher(None, base_lines, lines_a)
        sm_b = difflib.SequenceMatcher(None, base_lines, lines_b)

        ranges_a: list[tuple[int, int]] = []
        for tag, i1, i2, j1, j2 in sm_a.get_opcodes():
            if tag != "equal":
                ranges_a.append((i1, i2))

        ranges_b: list[tuple[int, int]] = []
        for tag, i1, i2, j1, j2 in sm_b.get_opcodes():
            if tag != "equal":
                ranges_b.append((i1, i2))

        for a_start, a_end in ranges_a:
            for b_start, b_end in ranges_b:
                if max(a_start, b_start) < min(a_end, b_end):
                    return False, f"OVERLAP at base lines [{max(a_start, b_start)}:{min(a_end, b_end)}]"

        return True, "DISJOINT"

    @classmethod
    def _try_ast_disjoint_python(
        cls,
        file_path: str,
        base_content: str,
        content_a: str,
        content_b: str,
    ) -> tuple[bool, str, str]:
        """Tenta mesclar alterações independentes em funções/classes de topo via AST."""
        try:
            tree_base = ast.parse(base_content)
            tree_a = ast.parse(content_a)
            tree_b = ast.parse(content_b)
        except Exception as e:
            return False, "", f"AST_PARSE_FAILED: {e}"

        base_lines = base_content.splitlines(keepends=True)
        lines_a = content_a.splitlines(keepends=True)
        lines_b = content_b.splitlines(keepends=True)

        # Mapear símbolos de topo e os seus intervalos de linha (1-indexed para 0-indexed)
        def get_top_symbols(tree: ast.AST) -> dict[str, tuple[int, int]]:
            syms = {}
            for node in getattr(tree, "body", []):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    syms[node.name] = (node.lineno - 1, getattr(node, "end_lineno", node.lineno))
            return syms

        syms_base = get_top_symbols(tree_base)
        syms_a = get_top_symbols(tree_a)
        syms_b = get_top_symbols(tree_b)

        # Encontrar quais símbolos foram modificados
        mod_a = set()
        for name, (s, e) in syms_base.items():
            if name in syms_a:
                sa, ea = syms_a[name]
                if base_lines[s:e] != lines_a[sa:ea]:
                    mod_a.add(name)

        mod_b = set()
        for name, (s, e) in syms_base.items():
            if name in syms_b:
                sb, eb = syms_b[name]
                if base_lines[s:e] != lines_b[sb:eb]:
                    mod_b.add(name)

        # Se ambos modificaram símbolos conhecidos e a interseção é vazia
        if mod_a and mod_b and not mod_a.intersection(mod_b):
            edits = []
            for name in mod_a:
                s_base, e_base = syms_base[name]
                s_a, e_a = syms_a[name]
                edits.append((s_base, e_base, lines_a[s_a:e_a]))
            for name in mod_b:
                s_base, e_base = syms_base[name]
                s_b, e_b = syms_b[name]
                edits.append((s_base, e_base, lines_b[s_b:e_b]))

            edits.sort(key=lambda item: item[0])
            merged = []
            curr = 0
            for s, e, new_lines in edits:
                merged.extend(base_lines[curr:s])
                merged.extend(new_lines)
                curr = e
            merged.extend(base_lines[curr:])
            result_str = "".join(merged)

            try:
                ast.parse(result_str)
                return True, result_str, "AST_DISJOINT_AUTO_MERGE_SUCCESS"
            except Exception:
                pass

        return False, "", "AST_NOT_DISJOINT"

    @classmethod
    def auto_merge_disjoint(
        cls,
        file_path: str,
        base_content: str,
        content_a: str,
        content_b: str,
        failure_memory: MergeFailureMemory | None = None,
    ) -> tuple[bool, str, str]:
        """
        Aplica merge determinístico escalável (Fase 15.1 & 15.2) delegando para LargeArtifactMergeEngine.
        Retorna (sucesso, conteúdo_mesclado, razão).
        """
        ok, merged, reason = LargeArtifactMergeEngine.auto_merge_disjoint(
            file_path, base_content, content_a, content_b, failure_memory=failure_memory
        )
        cls.metrics["fast_path_count"] += (
            LargeArtifactMergeEngine.metrics["structural_count"]
            + LargeArtifactMergeEngine.metrics["symbol_range_count"]
            + LargeArtifactMergeEngine.metrics["windowed_count"]
        )
        cls.metrics["full_diff_count"] += LargeArtifactMergeEngine.metrics["fallback_count"]
        cls.metrics["conflict_count"] += LargeArtifactMergeEngine.metrics["conflict_count"]
        cls.metrics["total_latency_ms"] += LargeArtifactMergeEngine.metrics["total_latency_ms"]
        return ok, merged, reason

    @classmethod
    def _sequence_matcher_merge(
        cls, base_content: str, content_a: str, content_b: str
    ) -> tuple[bool, str, str]:
        """Aplica 3-way SequenceMatcher difflib determinístico."""
        base_lines = base_content.splitlines(keepends=True)
        lines_a = content_a.splitlines(keepends=True)
        lines_b = content_b.splitlines(keepends=True)

        sm_a = difflib.SequenceMatcher(None, base_lines, lines_a)
        sm_b = difflib.SequenceMatcher(None, base_lines, lines_b)

        ranges_a: list[tuple[int, int]] = []
        for tag, i1, i2, j1, j2 in sm_a.get_opcodes():
            if tag != "equal":
                ranges_a.append((i1, i2))

        ranges_b: list[tuple[int, int]] = []
        for tag, i1, i2, j1, j2 in sm_b.get_opcodes():
            if tag != "equal":
                ranges_b.append((i1, i2))

        for a_start, a_end in ranges_a:
            for b_start, b_end in ranges_b:
                if max(a_start, b_start) < min(a_end, b_end):
                    return False, "", f"OVERLAP at base lines [{max(a_start, b_start)}:{min(a_end, b_end)}]"

        edits: list[tuple[int, int, list[str]]] = []
        for tag, i1, i2, j1, j2 in sm_a.get_opcodes():
            if tag != "equal":
                edits.append((i1, i2, lines_a[j1:j2]))

        for tag, i1, i2, j1, j2 in sm_b.get_opcodes():
            if tag != "equal":
                edits.append((i1, i2, lines_b[j1:j2]))

        edits.sort(key=lambda item: item[0])
        merged: list[str] = []
        curr_base = 0

        for i1, i2, new_chunk in edits:
            if i1 > curr_base:
                merged.extend(base_lines[curr_base:i1])
            merged.extend(new_chunk)
            curr_base = max(curr_base, i2)

        if curr_base < len(base_lines):
            merged.extend(base_lines[curr_base:])

        return True, "".join(merged), "DISJOINT_AUTO_MERGE_SUCCESS"


# ── DETERMINISTIC CONFLICT ARBITRATOR ──────────────────────────────────────────

class AgentConflictArbitrator:
    """
    Motor de Arbitragem Determinístico baseado na hierarquia estrita de evidências:
    1. Validação Dura (node --check, py_compile) [Peso 1000]
    2. Testes Reais (testes automatizados passados) [Peso 500]
    3. Integridade do Build [Peso 300]
    4. Saúde em Runtime [Peso 200]
    5. Verificação em Browser Real [Peso 150]
    6. Validação de Contratos (CrossFileValidator) [Peso 100]
    7. Compatibilidade Arquitetural [Peso 80]
    8. Confiança do Agente [Peso 10]
    9. Justificação Textual [Peso 1]
    """

    @classmethod
    def _calculate_evidence_score(
        cls,
        evidence: list[dict[str, Any]] | dict[str, Any],
        confidence: float = 0.0,
        rationale: str = "",
    ) -> float:
        total = 0.0
        if isinstance(evidence, dict):
            hv = evidence.get("hard_validation")
            if (isinstance(hv, dict) and hv.get("passed")) or hv is True:
                total += 1000.0

            tr = evidence.get("test_results")
            if isinstance(tr, dict):
                p = tr.get("passed", 0)
                f = tr.get("failed", 0)
                if f == 0 and p > 0:
                    total += 500.0 + min(200.0, p * 10.0)
                elif p > f:
                    total += 250.0

            b = evidence.get("build")
            if (isinstance(b, dict) and b.get("status") == "SUCCESS") or b == "SUCCESS":
                total += 300.0

            rt = evidence.get("runtime")
            if (isinstance(rt, dict) and rt.get("status") in ("HEALTHY", "PASS")) or rt in ("HEALTHY", "PASS"):
                total += 200.0

            br = evidence.get("browser")
            if (isinstance(br, dict) and br.get("status") == "PASS") or br == "PASS":
                total += 150.0

            c = evidence.get("contracts")
            if (isinstance(c, dict) and c.get("status") in ("VALID", "CONFORMANT")) or c in ("VALID", "CONFORMANT"):
                total += 100.0

            ar = evidence.get("architecture")
            if (isinstance(ar, dict) and ar.get("status") in ("VALID", "CONFORMANT")) or ar in ("VALID", "CONFORMANT"):
                total += 80.0
        elif isinstance(evidence, list):
            for ev in evidence:
                if not isinstance(ev, dict):
                    continue
                kind = str(ev.get("kind", "")).upper()
                status = str(ev.get("status", "PASS")).upper()
                if status != "PASS":
                    continue
                if "HARD_VALIDATION" in kind or "SYNTAX" in kind:
                    total += 1000.0
                elif "TEST" in kind:
                    pass_count = int(ev.get("passed", 1))
                    total += 500.0 + min(200.0, pass_count * 10.0)
                elif "BUILD" in kind:
                    total += 300.0
                elif "RUNTIME" in kind:
                    total += 200.0
                elif "BROWSER" in kind:
                    total += 150.0
                elif "CONTRACT" in kind:
                    total += 100.0
                elif "ARCHITECTURE" in kind:
                    total += 80.0
                else:
                    total += 50.0

        total += max(0.0, min(1.0, float(confidence))) * 10.0
        if rationale:
            total += 1.0
        return total

    @classmethod
    def score_proposal_evidence(cls, proposal: AgentProposal) -> tuple[float, list[dict[str, Any]]]:
        total_score = 0.0
        breakdown: list[dict[str, Any]] = []

        for ev in proposal.evidence:
            kind = str(ev.get("kind", "")).upper()
            status = str(ev.get("status", "PASS")).upper()
            weight = 0.0

            if status != "PASS":
                continue

            if "HARD_VALIDATION" in kind or "SYNTAX" in kind:
                weight = 1000.0
            elif "TEST" in kind:
                pass_count = int(ev.get("passed", 1))
                weight = 500.0 + min(200.0, pass_count * 10.0)
            elif "BUILD" in kind:
                weight = 300.0
            elif "RUNTIME" in kind:
                weight = 200.0
            elif "BROWSER" in kind:
                weight = 150.0
            elif "CONTRACT" in kind:
                weight = 100.0
            elif "ARCHITECTURE" in kind:
                weight = 80.0
            else:
                weight = 50.0

            total_score += weight
            breakdown.append({"kind": kind, "weight": weight, "evidence_id": ev.get("evidence_id", "")})

        # Adiciona bónus limitado de confiança (peso máx: 10.0)
        conf_bonus = max(0.0, min(1.0, proposal.confidence_score)) * 10.0
        total_score += conf_bonus
        breakdown.append({"kind": "AGENT_CONFIDENCE", "weight": conf_bonus})

        return total_score, breakdown

    @classmethod
    def arbitrate(
        cls,
        conflict: ConflictDetails,
        proposals: list[AgentProposal],
        review_input: dict[str, Any] | None = None,
        base_files: dict[str, str] | None = None,
    ) -> ArbitrationRecord:
        arb_id = f"arb_{uuid.uuid4().hex[:8]}"

        # Identificar propostas envolvidas
        involved = [p for p in proposals if p.proposal_id in conflict.proposals_involved]
        if not involved:
            involved = proposals

        # Salvaguardas Económicas (Secção 32): Em tarefas financeiras/money, não é permitido bypassar aprovação ou verificação externa
        is_money = "money" in conflict.conflict_key.task_id.lower() or "ledger" in conflict.conflict_key.resource.lower() or "economic" in conflict.description.lower()
        if is_money:
            has_valid_verification = any(
                any("HARD_VALIDATION" in str(ev.get("kind", "")).upper() or "EXTERNAL_VERIFICATION" in str(ev.get("kind", "")).upper()
                    for ev in prop.evidence)
                for prop in involved
            )
            if not has_valid_verification:
                return ArbitrationRecord(
                    arbitration_id=arb_id,
                    conflict_key=conflict.key_id,
                    decision=ArbitrationDecision.BLOCK,
                    rationale="ECONOMIC_SAFEGUARD: Em tarefas financeiras é estritamente proibido bypassar aprovação ou verificação externa, mesmo que haja consenso entre agentes.",
                    consensus_score=0.0,
                )

        # Invariante de Segurança (Secção 31): Agentes read-only (ex: RESEARCH) não podem emitir PATCH
        for prop in involved:
            if "research" in prop.agent_id.lower() and prop.result_kind == ResultKind.PATCH:
                return ArbitrationRecord(
                    arbitration_id=arb_id,
                    conflict_key=conflict.key_id,
                    decision=ArbitrationDecision.BLOCK,
                    rationale="SECURITY_VIOLATION: Research agent cannot propose file patches or system mutations (capability limit).",
                    consensus_score=0.0,
                )

        # Caso especial: REQUIREMENT_CONFLICT -> Se for ambíguo sem evidência objetiva, requer revisão ou halt
        if conflict.conflict_key.conflict_type == ConflictType.REQUIREMENT_CONFLICT:
            return ArbitrationRecord(
                arbitration_id=arb_id,
                conflict_key=conflict.key_id,
                decision=ArbitrationDecision.REGENERATE,
                rationale="REQUIREMENT_AMBIGUITY: Propostas divergem em pressupostos de requisitos. Solicitar regeneração com especificação consolidada.",
                consensus_score=0.5,
            )

        # Caso especial: ARCHITECTURAL_CONFLICT -> Requer adaptação ou replaneamento
        if conflict.conflict_key.conflict_type == ConflictType.ARCHITECTURAL_CONFLICT:
            return ArbitrationRecord(
                arbitration_id=arb_id,
                conflict_key=conflict.key_id,
                decision=ArbitrationDecision.REPLAN,
                rationale="ARCHITECTURAL_CONFLICT: Proposta viola o estilo arquitetural mandatado. Necessário REPLAN ou ADAPT.",
                consensus_score=0.2,
            )

        # Caso especial: CONTRACT_CONFLICT -> Disparar REVIEW / REGENERATE
        if conflict.conflict_key.conflict_type == ConflictType.CONTRACT_CONFLICT:
            # Se uma proposta de revisão apoiar expressamente uma das partes
            if review_input and review_input.get("preferred_proposal_id"):
                win_id = review_input["preferred_proposal_id"]
                return ArbitrationRecord(
                    arbitration_id=arb_id,
                    conflict_key=conflict.key_id,
                    decision=ArbitrationDecision.ACCEPT_A if win_id == involved[0].proposal_id else ArbitrationDecision.ACCEPT_B,
                    winning_proposal_id=win_id,
                    rationale=f"CONTRACT_CONFLICT resolvido por parecer do ReviewAgent favorável a '{win_id}'",
                    consensus_score=0.9,
                )
            return ArbitrationRecord(
                arbitration_id=arb_id,
                conflict_key=conflict.key_id,
                decision=ArbitrationDecision.REGENERATE,
                rationale="CONTRACT_CONFLICT: Frontend e Backend divergem no endpoint. Necessário regenerar contrato alinhado.",
                consensus_score=0.4,
            )

        # Caso de FILE_CONFLICT: Verificar se é possível AUTO-MERGE disjunto
        if conflict.conflict_key.conflict_type in (ConflictType.FILE_CONFLICT, ConflictType.SYMBOL_CONFLICT):
            if len(involved) == 2 and base_files:
                f = conflict.conflict_key.resource
                base_c = base_files.get(f, "")
                c_a = involved[0].content_by_file.get(f, "")
                c_b = involved[1].content_by_file.get(f, "")
                if base_c and c_a and c_b:
                    is_disjoint, _ = PatchMergeEngine.are_patches_disjoint(f, base_c, c_a, c_b)
                    if is_disjoint:
                        return ArbitrationRecord(
                            arbitration_id=arb_id,
                            conflict_key=conflict.key_id,
                            decision=ArbitrationDecision.MERGE,
                            winning_proposal_id=None,
                            rationale="DISJOINT_CHANGES: Alterações em ficheiro comum ocorrem em regiões totalmente disjuntas. Elegível para AUTO-MERGE.",
                            consensus_score=1.0,
                        )

        # Arbitragem por Ranking Determinístico de Evidências
        ranked: list[tuple[float, AgentProposal, list[dict[str, Any]]]] = []
        for prop in involved:
            sc, bdown = cls.score_proposal_evidence(prop)
            ranked.append((sc, prop, bdown))

        # Ordenação determinística: maior score primeiro, desempate por proposal_id
        ranked.sort(key=lambda item: (-item[0], item[1].proposal_id))
        best_score, best_prop, best_bdown = ranked[0]

        # Consenso baseado na consistência da evidência
        second_score = ranked[1][0] if len(ranked) > 1 else 0.0
        consensus_score = min(1.0, best_score / max(1.0, best_score + second_score)) if (best_score + second_score) > 0 else 0.5

        winning_decision = ArbitrationDecision.ACCEPT_A if best_prop.proposal_id == involved[0].proposal_id else ArbitrationDecision.ACCEPT_B

        rankings_data = [
            {"proposal_id": p.proposal_id, "agent_id": p.agent_id, "score": sc, "breakdown": bd}
            for sc, p, bd in ranked
        ]

        return ArbitrationRecord(
            arbitration_id=arb_id,
            conflict_key=conflict.key_id,
            decision=winning_decision,
            winning_proposal_id=best_prop.proposal_id,
            consensus_score=round(consensus_score, 2),
            evidence_rankings=rankings_data,
            rationale=f"Vencedor determinístico por hierarquia de evidências: Proposta '{best_prop.proposal_id}' do agente '{best_prop.agent_id}' (score={best_score:.1f} vs {second_score:.1f})",
        )

    @classmethod
    def arbitrate_staged(
        cls,
        conflict: ConflictDetails,
        proposals: list[AgentProposal],
        is_economic_task: bool = False,
    ) -> StagedArbitrationResult:
        """Arbitragem por estágios usando StagedArbitrationEngine (Fase 15.3 Secção 3)."""
        return StagedArbitrationEngine.arbitrate_staged(
            conflict=conflict,
            proposals=proposals,
            is_economic_task=is_economic_task,
        )

    evaluate_evidence = score_proposal_evidence


# ── COLLABORATION COORDINATOR ──────────────────────────────────────────────────

class CollaborationCoordinator:
    """
    Coordenador central do ciclo de vida colaborativo multi-agente.
    Interage com o SwarmCoordinator para criar sessões de colaboração,
    detetar conflitos, gerir revisões com escopo delimitado, e aplicar
    decisões de arbitragem ou auto-merge.
    """

    def __init__(
        self,
        project_id: str,
        mission_id: str,
        repo_graph: RepositoryGraph | None = None,
        callbacks: Any = None,
        workspace_root: str | None = None,
    ):
        self.project_id = project_id
        self.mission_id = mission_id
        self.callbacks = callbacks
        self.workspace_root = workspace_root
        self.detector = ConflictDetector(repo_graph=repo_graph, workspace_root=workspace_root)
        self.arbitrator = AgentConflictArbitrator()
        self.sessions: dict[str, CollaborationSession] = {}
        self.metrics = CollaborationMetrics()
        self.failure_memory = MergeFailureMemory()

    def create_session(
        self,
        task_id: str,
        participant_agents: list[str],
        max_rounds: int = 3,
    ) -> CollaborationSession:
        collab_id = f"collab_{task_id}_{uuid.uuid4().hex[:6]}"
        session = CollaborationSession(
            collaboration_id=collab_id,
            mission_id=self.mission_id,
            task_id=task_id,
            participant_agents=list(participant_agents),
            status=CollaborationStatus.OPEN,
            max_rounds=max_rounds,
        )
        self.sessions[collab_id] = session
        self.metrics.collaboration_count += 1
        return session

    def get_session(self, collab_id: str) -> CollaborationSession | None:
        return self.sessions.get(collab_id)

    def get_session_for_task(self, task_id: str) -> CollaborationSession | None:
        for s in self.sessions.values():
            if s.task_id == task_id and s.status != CollaborationStatus.BLOCKED:
                return s
        return None

    def add_proposal(self, collab_id: str, proposal: AgentProposal) -> bool:
        session = self.sessions.get(collab_id)
        if not session:
            return False

        # Idempotência: ignorar proposta duplicada exata
        for existing in session.proposals:
            if existing.proposal_id == proposal.proposal_id:
                return True
            if (
                existing.agent_id == proposal.agent_id
                and existing.task_id == proposal.task_id
                and existing.diff_content == proposal.diff_content
                and existing.content_by_file == proposal.content_by_file
            ):
                return True

        session.proposals.append(proposal)
        session.status = CollaborationStatus.COLLECTING
        session.updated_at = utc_now()
        return True

    def evaluate_collaboration(
        self,
        collab_id: str,
        task: TaskNode | None = None,
        architecture_context: dict[str, Any] | None = None,
        base_files: dict[str, str] | None = None,
        review_input: dict[str, Any] | None = None,
    ) -> tuple[CollaborationStatus, list[ConflictDetails], list[ArbitrationRecord]]:
        session = self.sessions.get(collab_id)
        if not session:
            return CollaborationStatus.BLOCKED, [], []

        if task is None:
            task = TaskNode(task_id=session.task_id, title="Default Task", description="Default Collaborative Task")

        t0 = time.perf_counter()

        # Proteção Anti-Loop: Se excedeu limites de rounds ou arbitrações, bloqueia
        if session.round_count > session.max_rounds:
            session.status = CollaborationStatus.BLOCKED
            session.updated_at = utc_now()
            return session.status, session.conflicts, session.arbitrations

        # 0. Deduplicação Determinística de Propostas (Fase 15.1)
        unique_props, dups = self.detector.detect_duplicate_proposals(session.proposals)
        if dups:
            self.metrics.duplicate_proposals += len(dups)
            session.proposals = unique_props

        # 1. Deteção de Conflitos Hierárquica Indexada (Fase 15.1 & 15.2)
        conflicts = self.detector.detect_conflicts(
            self.project_id, task, session.proposals, architecture_context
        )
        session.conflicts = conflicts

        # Sincronizar métricas de indexação
        if self.detector.last_conflict_graph:
            cg = self.detector.last_conflict_graph
            self.metrics.conflict_candidates += cg.candidate_count
            self.metrics.conflict_comparisons += cg.actual_comparisons
            self.metrics.conflict_pruned += cg.pruned_comparisons
        self.metrics.candidate_index_latency_ms += getattr(self.detector, "last_candidate_index_latency_ms", 0.0)
        self.metrics.hierarchical_index_latency_ms += getattr(self.detector, "last_hierarchical_index_latency_ms", 0.0)
        self.metrics.dense_strategy_selected = getattr(self.detector, "last_dense_strategy", DenseConflictStrategy.PAIRWISE).value
        self.metrics.component_count = len(getattr(self.detector, "last_components", []))
        self.metrics.isolated_proposals_count = sum(1 for c in getattr(self.detector, "last_components", []) if len(c.proposal_ids) == 1 and not c.has_conflicts)
        self.metrics.conflicts_detected += len(conflicts)

        if not conflicts:
            # Sem conflitos! Se houver propostas válidas, valida e aceita a melhor
            session.status = CollaborationStatus.RESOLVED
            session.updated_at = utc_now()
            return session.status, [], []

        # 2. Conflito Detetado: Iniciar Arbitragem
        session.status = CollaborationStatus.ARBITRATING
        self.metrics.conflict_count += len(conflicts)
        arbitrations: list[ArbitrationRecord] = []

        for conf in conflicts:
            arb = self.arbitrator.arbitrate(
                conf, session.proposals, review_input=review_input, base_files=base_files
            )
            arbitrations.append(arb)
            self.metrics.arbitration_count += 1

            if arb.decision == ArbitrationDecision.MERGE:
                # Executar auto-merge determinístico para ficheiro disjunto (Fase 15.2 com LargeArtifactMergeEngine)
                f = conf.conflict_key.resource
                if base_files and f in base_files and len(session.proposals) >= 2:
                    p1, p2 = session.proposals[0], session.proposals[1]
                    ok, merged, _ = PatchMergeEngine.auto_merge_disjoint(
                        f,
                        base_files[f],
                        p1.content_by_file.get(f, ""),
                        p2.content_by_file.get(f, ""),
                        failure_memory=self.failure_memory,
                    )
                    if ok:
                        session.merged_content[f] = merged
                        self.metrics.auto_merge_count += 1

        session.arbitrations = arbitrations
        self.metrics.conflict_resolution_count += len(arbitrations)
        self.metrics.resolution_latency_ms += (time.perf_counter() - t0) * 1000.0

        # Sincronizar métricas de PatchMergeEngine & LargeArtifactMergeEngine
        self.metrics.merge_fast_path_count += PatchMergeEngine.metrics.get("fast_path_count", 0)
        self.metrics.merge_full_diff_count += PatchMergeEngine.metrics.get("full_diff_count", 0)
        self.metrics.merge_conflict_count += PatchMergeEngine.metrics.get("conflict_count", 0)
        self.metrics.merge_latency_ms += PatchMergeEngine.metrics.get("total_latency_ms", 0.0)
        self.metrics.structural_merge_count += LargeArtifactMergeEngine.metrics.get("structural_count", 0)
        self.metrics.windowed_merge_count += LargeArtifactMergeEngine.metrics.get("windowed_count", 0)
        self.metrics.line_fallback_count += LargeArtifactMergeEngine.metrics.get("fallback_count", 0)
        PatchMergeEngine.metrics["fast_path_count"] = 0
        PatchMergeEngine.metrics["full_diff_count"] = 0
        PatchMergeEngine.metrics["conflict_count"] = 0
        PatchMergeEngine.metrics["total_latency_ms"] = 0.0

        # Verificar se alguma arbitragem dita REGENERATE, REPLAN ou BLOCK
        if any(a.decision == ArbitrationDecision.BLOCK for a in arbitrations):
            session.status = CollaborationStatus.BLOCKED
        elif any(a.decision == ArbitrationDecision.REPLAN for a in arbitrations):
            session.status = CollaborationStatus.RESOLVED  # Pronto para o Dynamic SubDAG / Replan
        else:
            session.status = CollaborationStatus.RESOLVED

        session.updated_at = utc_now()
        return session.status, conflicts, arbitrations

    def advance_round(self, collab_id: str) -> int:
        session = self.sessions.get(collab_id)
        if session:
            session.round_count += 1
            session.proposals.clear()
            session.conflicts.clear()
            session.arbitrations.clear()
            session.status = CollaborationStatus.OPEN
            session.updated_at = utc_now()
            self.metrics.collaboration_rounds += 1
            self.metrics.regeneration_count += 1
            return session.round_count
        return 0

    def export_state(self) -> dict[str, Any]:
        """Exporta estado completo de colaborações para persistência em checkpoint (Fase 15.2)."""
        return {
            "sessions": {s_id: s.to_dict() for s_id, s in self.sessions.items()},
            "metrics": self.metrics.to_dict(),
            "failure_memory": self.failure_memory.to_dict(),
            "last_candidate_index": self.detector.last_candidate_index.to_dict() if self.detector.last_candidate_index else None,
            "last_hierarchical_index": self.detector.last_hierarchical_index.to_dict() if self.detector.last_hierarchical_index else None,
            "last_conflict_graph": self.detector.last_conflict_graph.to_dict() if self.detector.last_conflict_graph else None,
            "last_components": [c.to_dict() for c in getattr(self.detector, "last_components", [])],
            "last_dense_strategy": getattr(self.detector, "last_dense_strategy", DenseConflictStrategy.PAIRWISE).value,
            "last_partition_metadata": self.detector.last_partition_metadata.to_dict() if getattr(self.detector, "last_partition_metadata", None) else None,
            "incremental_graph": self.detector.incremental_graph.to_dict() if getattr(self.detector, "incremental_graph", None) else None,
        }

    def restore_state(self, state_data: dict[str, Any]) -> None:
        """Restaura sessões, métricas e memória de falhas pós-restart (Fase 15.2/15.3)."""
        for s_id, s_dict in state_data.get("sessions", {}).items():
            self.sessions[s_id] = CollaborationSession.from_dict(s_dict)
        m_dict = state_data.get("metrics", {})
        if m_dict:
            self.metrics = CollaborationMetrics(**m_dict)
        f_dict = state_data.get("failure_memory", {})
        if f_dict:
            self.failure_memory = MergeFailureMemory.from_dict(f_dict)
        g_dict = state_data.get("last_conflict_graph")
        if g_dict:
            edges = {}
            for k, v in g_dict.get("edges", {}).items():
                if "<->" in k:
                    parts = k.split("<->")
                    edges[(parts[0], parts[1])] = v
            self.detector.last_conflict_graph = CandidateConflictGraph(
                nodes=g_dict.get("nodes", []),
                edges=edges,
                candidate_count=g_dict.get("candidate_count", 0),
                actual_comparisons=g_dict.get("actual_comparisons", 0),
                pruned_comparisons=g_dict.get("pruned_comparisons", 0),
            )
        comps_data = state_data.get("last_components", [])
        if comps_data:
            self.detector.last_components = [ConflictComponent.from_dict(c) for c in comps_data]
        if "last_dense_strategy" in state_data:
            try:
                self.detector.last_dense_strategy = DenseConflictStrategy(state_data["last_dense_strategy"])
            except Exception:
                self.detector.last_dense_strategy = DenseConflictStrategy.PAIRWISE
        part_data = state_data.get("last_partition_metadata")
        if part_data:
            self.detector.last_partition_metadata = ProposalPartitionMetadata.from_dict(part_data)
        inc_data = state_data.get("incremental_graph")
        if inc_data:
            self.detector.incremental_graph = IncrementalConflictGraph.from_dict(inc_data)
