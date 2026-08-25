"""
JARVIS OS — Security Sentinel Contracts & Evidence Data Models (Fase S2)
Defensive, explainable, fail-safe cybersecurity data structures with schema versioning.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional
import hashlib
import json
import time


SENTINEL_SCHEMA_VERSION = 1


class SecurityClassification(str, Enum):
    """Níveis rigorosos de classificação defensiva."""
    BENIGN = "BENIGN"
    SUSPICIOUS = "SUSPICIOUS"
    HIGH_RISK = "HIGH_RISK"
    CONFIRMED_MALICIOUS = "CONFIRMED_MALICIOUS"
    UNKNOWN = "UNKNOWN"


class SentinelLifecycleState(str, Enum):
    """Estados explícitos do ciclo de vida e arranque do Sentinel."""
    STARTING = "STARTING"
    BASELINE_RUNNING = "BASELINE_RUNNING"
    READY = "READY"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"


class SentinelShadowModeState(str, Enum):
    """Estados explícitos do Shadow Mode operacional (100% Read-Only)."""
    STARTING = "STARTING"
    COLLECTING = "COLLECTING"
    ANALYZING = "ANALYZING"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"
    DEGRADED = "DEGRADED"


class SecurityPosture(str, Enum):
    """Postura geral calculada do sistema."""
    GOOD = "GOOD"
    MONITORING = "MONITORING"
    ATTENTION = "ATTENTION"
    HIGH_RISK = "HIGH_RISK"
    DEGRADED = "DEGRADED"
    UNKNOWN = "UNKNOWN"


class EventCategory(str, Enum):
    """Categorias formais de eventos de segurança."""
    PROCESS = "PROCESS"
    NETWORK = "NETWORK"
    PERSISTENCE = "PERSISTENCE"
    BROWSER = "BROWSER"
    HOSTS = "HOSTS"
    AUTHENTICATION = "AUTHENTICATION"
    PRIVILEGE = "PRIVILEGE"
    FILE_SYSTEM = "FILE_SYSTEM"
    SERVICE = "SERVICE"
    TASK_SCHEDULER = "TASK_SCHEDULER"
    REGISTRY = "REGISTRY"
    DEFENDER = "DEFENDER"
    SYSTEM = "SYSTEM"


class IncidentStatus(str, Enum):
    """Ciclo de vida de um incidente de segurança."""
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    CONTAINED = "CONTAINED"
    RESOLVED = "RESOLVED"
    FALSE_POSITIVE = "FALSE_POSITIVE"
    UNKNOWN = "UNKNOWN"


class PrivacyClassification(str, Enum):
    """Classificação de privacidade para proteção de dados do utilizador."""
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    RESTRICTED = "RESTRICTED"
    CONFIDENTIAL = "CONFIDENTIAL"


@dataclass(slots=True)
class KnownGoodItem:
    """Registo de alteração explicitamente aprovada como benigna pelo utilizador."""
    item_key: str
    category: str
    accepted_by: str
    accepted_at: float
    reason: str
    previous_state: Dict[str, Any]
    current_state: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SecurityEvidence:
    """Registo imutável de evidência observada."""
    evidence_id: str
    timestamp: float
    collector: str
    host: str
    asset: str
    observation: str
    raw_reference: str
    normalized_data: Dict[str, Any]
    sha256: str
    confidence: float
    source: str
    retention: str = "30d"
    privacy_classification: str = PrivacyClassification.INTERNAL.value
    schema_version: int = SENTINEL_SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class HumanIncidentReview:
    """Registo canónico de revisão humana sobre um evento de segurança."""
    review_id: str
    event_id: str
    operator: str
    timestamp: float
    reason: str
    evidence_ids: List[str]
    previous_classification: str
    final_classification: str
    is_false_positive: bool = False
    schema_version: int = SENTINEL_SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SecurityEvent:
    """Evento correlacionado de segurança com fingerprint e deduplicação."""
    event_id: str
    fingerprint: str
    timestamp: float
    first_seen: float
    last_seen: float
    occurrence_count: int
    category: str
    severity: str
    confidence: float
    evidence_ids: List[str]
    rationale: str
    recommended_action: str
    affected_process: Optional[Dict[str, Any]] = None
    affected_user: Optional[str] = None
    affected_network_endpoint: Optional[Dict[str, Any]] = None
    approval_required: bool = True
    status: str = "OPEN"
    is_known_good: bool = False
    observation_timeline: List[Dict[str, Any]] = field(default_factory=list)
    model_classification: Optional[str] = None
    human_review: Optional[Dict[str, Any]] = None
    schema_version: int = SENTINEL_SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ProcessItem:
    """Metadados normalizados de um processo em execução."""
    pid: int
    ppid: int
    name: str
    exe_path: str
    cmdline: str
    username: str
    create_time: float
    status: str
    sha256: str = ""
    is_signed: Optional[bool] = None
    signer: Optional[str] = None
    is_temp_dir: bool = False
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class NetworkItem:
    """Metadados de uma conexão de rede ou porta em escuta."""
    protocol: str  # TCP / UDP
    local_address: str
    local_port: int
    remote_address: Optional[str]
    remote_port: Optional[int]
    status: str  # LISTEN, ESTABLISHED, TIME_WAIT, etc.
    pid: Optional[int]
    process_name: Optional[str] = None
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PersistenceItem:
    """Entrada de persistência no sistema (Registry, Startup, Tasks, Services)."""
    kind: str  # REGISTRY_RUN, STARTUP_FOLDER, SCHEDULED_TASK, SERVICE
    name: str
    target_path: str
    arguments: str = ""
    location: str = ""
    sha256: str = ""
    is_active: bool = True
    owner: str = ""
    status_label: str = "KNOWN_GOOD"  # KNOWN_GOOD, NEW, CHANGED, REMOVED, UNKNOWN
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class HostsInfo:
    """Estado e integridade do ficheiro hosts."""
    path: str
    sha256: str
    exists: bool
    line_count: int
    custom_entries: List[Dict[str, str]]
    raw_content: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class BrowserExtensionItem:
    """Extensão de browser inventariada."""
    browser: str  # CHROME / EDGE / FIREFOX
    extension_id: str
    name: str
    version: str
    description: str
    permissions: List[str]
    install_path: str
    install_source: str = "web_store"
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class WindowsSecurityStatus:
    """Estado do subsistema de segurança do Windows."""
    defender_realtime_enabled: Optional[bool] = None
    defender_antivirus_enabled: Optional[bool] = None
    firewall_domain_enabled: Optional[bool] = None
    firewall_private_enabled: Optional[bool] = None
    firewall_public_enabled: Optional[bool] = None
    recent_security_events_count: int = 0
    recent_events_summary: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SystemBaseline:
    """Snapshot formal do estado do sistema com gestão de Known Good."""
    baseline_id: str
    timestamp: float
    integrity_hash: str
    host_info: Dict[str, Any]
    processes: List[Dict[str, Any]]
    network: List[Dict[str, Any]]
    persistence: List[Dict[str, Any]]
    hosts_info: Dict[str, Any]
    browser_extensions: List[Dict[str, Any]]
    windows_security: Dict[str, Any]
    collector_metrics: Dict[str, Any]
    known_goods: List[Dict[str, Any]] = field(default_factory=list)
    schema_version: int = SENTINEL_SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def compute_hash(cls, data_dict: Dict[str, Any]) -> str:
        """Gera hash criptográfico SHA-256 determinístico sobre o snapshot."""
        # Remove campos variáveis antes de hashear para estabilidade canónica
        filtered = {k: v for k, v in data_dict.items() if k != "integrity_hash"}
        serialized = json.dumps(filtered, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


@dataclass(slots=True)
class BaselineDiff:
    """Comparação determinística entre dois baselines."""
    base_id: str
    target_id: str
    timestamp: float
    new_processes: List[Dict[str, Any]] = field(default_factory=list)
    removed_processes: List[Dict[str, Any]] = field(default_factory=list)
    new_listening_ports: List[Dict[str, Any]] = field(default_factory=list)
    removed_listening_ports: List[Dict[str, Any]] = field(default_factory=list)
    new_persistence: List[Dict[str, Any]] = field(default_factory=list)
    removed_persistence: List[Dict[str, Any]] = field(default_factory=list)
    hosts_changed: bool = False
    hosts_diff: Optional[Dict[str, Any]] = None
    new_browser_extensions: List[Dict[str, Any]] = field(default_factory=list)
    removed_browser_extensions: List[Dict[str, Any]] = field(default_factory=list)
    security_status_changed: bool = False
    schema_version: int = SENTINEL_SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ResponseActionType(str, Enum):
    """Tipos de ações de resposta defensiva suportadas na Fase S3."""
    TERMINATE_PROCESS = "TERMINATE_PROCESS"
    DISABLE_SCHEDULED_TASK = "DISABLE_SCHEDULED_TASK"
    BLOCK_NETWORK_ENDPOINT = "BLOCK_NETWORK_ENDPOINT"
    QUARANTINE_FILE = "QUARANTINE_FILE"
    MARK_KNOWN_GOOD = "MARK_KNOWN_GOOD"


class ResponseActionStatus(str, Enum):
    """Estados do ciclo de vida de uma ação de resposta."""
    PROPOSED = "PROPOSED"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    APPROVED = "APPROVED"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"
    REJECTED = "REJECTED"


class PermissionLevel(str, Enum):
    """Níveis formais de permissão para mutações no sistema."""
    READ_ONLY = "READ_ONLY"
    LOW_RISK_MUTATION = "LOW_RISK_MUTATION"
    HIGH_RISK_MUTATION = "HIGH_RISK_MUTATION"
    CRITICAL_MUTATION = "CRITICAL_MUTATION"


@dataclass(slots=True)
class SecurityResponseAction:
    """Registo canónico de ação de resposta defensiva com aprovação humana e verificação."""
    action_id: str
    incident_id: str
    action_type: str
    target: str
    rationale: str
    evidence_ids: List[str]
    permission_level: str = PermissionLevel.LOW_RISK_MUTATION.value
    requested_by: str = "sentinel_correlation_engine"
    approval_required: bool = True
    approved_by: Optional[str] = None
    approval_session_id: Optional[str] = None
    approval_timestamp: Optional[float] = None
    pre_state: Dict[str, Any] = field(default_factory=dict)
    execution_result: Dict[str, Any] = field(default_factory=dict)
    post_state: Dict[str, Any] = field(default_factory=dict)
    verification_result: Dict[str, Any] = field(default_factory=dict)
    rollback_available: bool = False
    rollback_plan: str = ""
    rollback_result: Optional[Dict[str, Any]] = None
    status: str = ResponseActionStatus.PROPOSED.value
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    error_message: Optional[str] = None
    schema_version: int = SENTINEL_SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

