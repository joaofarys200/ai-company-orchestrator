"""
JARVIS OS — Permission Gateway Service
Core orchestrator for Just-In-Time Human-in-the-Loop authorization.
Manages request lifecycle, policy validation, user decisions,
capability checks, audit trails, and idempotency.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple

from security.permission_gateway.capability_checker import CapabilityChecker
from security.permission_gateway.models import (
    AuditLogEntry,
    CapabilityStatus,
    DependencyRequirement,
    PermissionRequest,
    PermissionRequestStatus,
    PermissionRiskLevel,
    RollbackRecord,
)
from security.permission_gateway.policy_engine import PermissionPolicyEngine
from security.permission_gateway.supply_chain import SupplyChainValidator

logger = logging.getLogger("permission_gateway")


class PermissionGatewayError(Exception):
    """Exceção base do Gateway de Permissões."""
    pass


class PermissionNotFoundError(PermissionGatewayError):
    pass


class PermissionExpiredError(PermissionGatewayError):
    pass


class PermissionBlockedByPolicyError(PermissionGatewayError):
    pass


class CrossProjectApprovalError(PermissionGatewayError):
    pass


class InvalidApprovalStateError(PermissionGatewayError):
    pass


class PermissionGatewayService:
    """
    Serviço central de mediação de autorizações e capacidades externas.
    Totalmente thread-safe e seguro contra manipulações do cliente.
    """

    def __init__(self, default_ttl_seconds: float = 300.0) -> None:
        self.default_ttl_seconds = default_ttl_seconds
        self._lock = threading.RLock()
        self._requests: Dict[str, PermissionRequest] = {}
        self._dedup_index: Dict[str, str] = {}  # key -> request_id
        self._audit_log: List[AuditLogEntry] = []
        self._rollbacks: Dict[str, RollbackRecord] = {}
        self._broadcast_callbacks: List[Callable[[str, Dict[str, Any]], Any]] = []

    def register_broadcast_callback(self, cb: Callable[[str, Dict[str, Any]], Any]) -> None:
        with self._lock:
            self._broadcast_callbacks.append(cb)

    def _notify_listeners(self, event_type: str, payload: Dict[str, Any]) -> None:
        for cb in list(self._broadcast_callbacks):
            try:
                cb(event_type, payload)
            except Exception as e:
                logger.warning(f"Erro ao emitir evento {event_type}: {e}")

    def _dedup_key(
        self,
        mission_id: Optional[str],
        project_id: Optional[str],
        execution_id: Optional[str],
        tool_name: str,
        requested_operation: str,
    ) -> str:
        return f"{project_id or '*'}:{mission_id or '*'}:{execution_id or '*'}:{tool_name.lower().strip()}:{requested_operation.lower().strip()}"

    def _log_audit(
        self,
        request_id: str,
        event_type: str,
        risk_level: str,
        tool_name: str,
        mission_id: Optional[str] = None,
        project_id: Optional[str] = None,
        execution_id: Optional[str] = None,
        user_decision: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditLogEntry:
        entry = AuditLogEntry(
            audit_id=f"audit-{uuid.uuid4().hex[:10]}",
            request_id=request_id,
            event_type=event_type,
            timestamp=time.time(),
            user_decision=user_decision,
            risk_level=risk_level,
            tool_name=tool_name,
            mission_id=mission_id,
            project_id=project_id,
            execution_id=execution_id,
            details=details or {},
        )
        self._audit_log.append(entry)
        return entry

    def create_request(
        self,
        tool_name: str,
        requested_operation: str,
        reason: str,
        risk_level: str,
        required_privileges: str,
        affected_resources: List[str],
        mission_id: Optional[str] = None,
        project_id: Optional[str] = None,
        execution_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        tool_type: str = "binary",
        installation_required: bool = False,
        installer_source: Optional[str] = None,
        installer_version: Optional[str] = None,
        installer_checksum: Optional[str] = None,
        alternative_available: bool = False,
        fallback_description: Optional[str] = None,
        rollback_available: bool = False,
        rollback_plan: Optional[str] = None,
        ttl_seconds: Optional[float] = None,
    ) -> PermissionRequest:
        with self._lock:
            # 1. Deduplicação: se já existe um pedido ativo idêntico, reutiliza-o
            dedup_key = self._dedup_key(mission_id, project_id, execution_id, tool_name, requested_operation)
            existing_id = self._dedup_index.get(dedup_key)
            if existing_id and existing_id in self._requests:
                existing = self._requests[existing_id]
                # Se ainda estiver pendente e não expirou, devolve o existente
                if existing.status in {
                    PermissionRequestStatus.WAITING_FOR_USER.value,
                    PermissionRequestStatus.REQUESTED.value,
                    PermissionRequestStatus.CAPABILITY_CHECKING.value,
                } and time.time() < existing.expires_at:
                    return existing

            # 2. Validação de Supply Chain se houver pacote/fonte
            if installer_source:
                valid_source, msg = SupplyChainValidator.validate_installer_source(installer_source)
                if not valid_source:
                    req = PermissionRequest.create(
                        tool_name=tool_name,
                        requested_operation=requested_operation,
                        reason=reason,
                        risk_level=risk_level,
                        required_privileges=required_privileges,
                        affected_resources=affected_resources,
                        mission_id=mission_id,
                        project_id=project_id,
                        execution_id=execution_id,
                        agent_id=agent_id,
                        tool_type=tool_type,
                        installation_required=installation_required,
                        installer_source=installer_source,
                        installer_version=installer_version,
                        installer_checksum=installer_checksum,
                        alternative_available=alternative_available,
                        fallback_description=fallback_description,
                    )
                    req.status = PermissionRequestStatus.BLOCKED_BY_POLICY.value
                    req.policy_reason = f"Violação de Supply Chain: {msg}"
                    self._requests[req.request_id] = req
                    self._log_audit(
                        req.request_id, "blocked", risk_level, tool_name,
                        mission_id, project_id, execution_id, details={"reason": req.policy_reason}
                    )
                    return req

            # 3. Cria a instância canónica do pedido
            effective_ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl_seconds
            req = PermissionRequest.create(
                tool_name=tool_name,
                requested_operation=requested_operation,
                reason=reason,
                risk_level=risk_level,
                required_privileges=required_privileges,
                affected_resources=affected_resources,
                mission_id=mission_id,
                project_id=project_id,
                execution_id=execution_id,
                agent_id=agent_id,
                tool_type=tool_type,
                installation_required=installation_required,
                installer_source=installer_source,
                installer_version=installer_version,
                installer_checksum=installer_checksum,
                alternative_available=alternative_available,
                fallback_description=fallback_description,
                ttl_seconds=effective_ttl,
                rollback_available=rollback_available,
                rollback_plan=rollback_plan,
            )

            # 4. Avaliação estrita da Política Sentinel / Workspace
            decision = PermissionPolicyEngine.evaluate(req)
            req.status = decision.initial_status.value
            req.policy_reason = decision.reason
            req.decision_evidence["policy_evaluation"] = decision.to_dict()

            self._requests[req.request_id] = req
            self._dedup_index[dedup_key] = req.request_id

            # 5. Registo no log de auditoria
            if decision.is_blocked_by_policy:
                self._log_audit(
                    req.request_id, "blocked", risk_level, tool_name,
                    mission_id, project_id, execution_id, details={"reason": decision.reason}
                )
            else:
                self._log_audit(
                    req.request_id, "request_created", risk_level, tool_name,
                    mission_id, project_id, execution_id, details={"reason": reason}
                )
                self._log_audit(
                    req.request_id, "shown_to_user", risk_level, tool_name,
                    mission_id, project_id, execution_id
                )

            # 6. Notificação via WebSocket
            self._notify_listeners("permission_request_created", {"request": req.to_dict()})
            # Reutiliza também action_confirm_request para compatibilidade com o protocolo
            self._notify_listeners("action_confirm_request", {
                "request_id": req.request_id,
                "tool_name": req.tool_name,
                "reason": req.reason,
                "risk_level": req.risk_level,
                "required_privileges": req.required_privileges,
                "affected_resources": req.affected_resources,
                "installation_required": req.installation_required,
                "fallback": req.fallback_description,
                "expiry": req.expires_at,
                "reversible": req.rollback_available,
                "rollback": req.rollback_plan,
            })

            return req

    def approve_request(
        self,
        request_id: str,
        user: str = "human_operator",
        session_id: str = "web_session",
        mission_id: Optional[str] = None,
        project_id: Optional[str] = None,
        mock_installed_tools: Optional[Dict[str, str]] = None,
        mock_is_admin: Optional[bool] = None,
    ) -> PermissionRequest:
        with self._lock:
            if request_id not in self._requests:
                raise PermissionNotFoundError(f"Pedido de permissão '{request_id}' não encontrado.")

            req = self._requests[request_id]

            # Proteção contra aprovação forjada se já estiver bloqueado por política
            if req.status == PermissionRequestStatus.BLOCKED_BY_POLICY.value:
                raise PermissionBlockedByPolicyError("Operações bloqueadas por política não podem ser aprovadas.")

            # Proteção contra isolamento entre projetos (Cross-Project Approval)
            if project_id and req.project_id and project_id != req.project_id:
                raise CrossProjectApprovalError("Aprovação rejeitada: project_id não corresponde ao pedido original.")
            if mission_id and req.mission_id and mission_id != req.mission_id:
                raise CrossProjectApprovalError("Aprovação rejeitada: mission_id não corresponde ao pedido original.")

            # Idempotência: se já foi aprovado e processado, retorna o registo sem duplicar ações
            if req.status in {
                PermissionRequestStatus.APPROVED.value,
                PermissionRequestStatus.AVAILABLE.value,
                PermissionRequestStatus.ADMIN_PRIVILEGE_REQUIRED.value,
                PermissionRequestStatus.INSTALLATION_REQUIRED.value,
                PermissionRequestStatus.EXECUTION_READY.value,
                PermissionRequestStatus.EXECUTED.value,
            }:
                return req

            # Verificação estrita de Expiração (TTL)
            now = time.time()
            if now > req.expires_at:
                req.status = PermissionRequestStatus.EXPIRED.value
                self._log_audit(
                    req.request_id, "expired", req.risk_level, req.tool_name,
                    req.mission_id, req.project_id, req.execution_id,
                    details={"expired_at": req.expires_at, "attempted_at": now}
                )
                self._notify_listeners("permission_request_expired", {"request_id": req.request_id})
                raise PermissionExpiredError("O pedido de autorização expirou e não pode ser aprovado.")

            # Apenas pedidos em WAITING_FOR_USER ou REQUESTED podem ser aprovados
            if req.status not in {
                PermissionRequestStatus.WAITING_FOR_USER.value,
                PermissionRequestStatus.REQUESTED.value,
            }:
                raise InvalidApprovalStateError(f"Pedido em estado inválido para aprovação: '{req.status}'.")

            # 1. Registo de Aprovação Humana
            req.user_decision = "USER_APPROVED"
            req.decided_by = user
            req.session_id = session_id
            req.decided_at = now
            req.status = PermissionRequestStatus.APPROVED.value

            self._log_audit(
                req.request_id, "approved", req.risk_level, req.tool_name,
                req.mission_id, req.project_id, req.execution_id,
                user_decision="USER_APPROVED",
                details={"user": user, "session_id": session_id}
            )
            self._notify_listeners("permission_request_approved", {
                "request_id": req.request_id,
                "mission_id": req.mission_id,
                "project_id": req.project_id,
                "execution_id": req.execution_id,
                "user": user,
            })

            # 2. CAPABILITY CHECK (Nunca salta diretamente para EXECUTED!)
            req.status = PermissionRequestStatus.CAPABILITY_CHECKING.value
            cap_status, cap_details = CapabilityChecker.check_capability(
                req,
                mock_installed_tools=mock_installed_tools,
                mock_is_admin=mock_is_admin,
            )
            req.capability_result = cap_details
            req.decision_evidence["capability_check"] = cap_details

            # 3. Transição após verificação de capacidade
            if cap_status == CapabilityStatus.AVAILABLE:
                req.status = PermissionRequestStatus.EXECUTION_READY.value
            elif cap_status == CapabilityStatus.ADMIN_PRIVILEGE_REQUIRED:
                req.status = PermissionRequestStatus.ADMIN_PRIVILEGE_REQUIRED.value
            elif cap_status == CapabilityStatus.INSTALLATION_REQUIRED:
                req.status = PermissionRequestStatus.INSTALLATION_REQUIRED.value
            elif cap_status == CapabilityStatus.UNSUPPORTED:
                req.status = PermissionRequestStatus.UNSUPPORTED.value
            elif cap_status == CapabilityStatus.BLOCKED:
                req.status = PermissionRequestStatus.BLOCKED_BY_POLICY.value

            self._log_audit(
                req.request_id, "capability_checked", req.risk_level, req.tool_name,
                req.mission_id, req.project_id, req.execution_id,
                details={"capability_status": cap_status.value, **cap_details}
            )
            self._notify_listeners("permission_capability_result", {
                "request_id": req.request_id,
                "mission_id": req.mission_id,
                "project_id": req.project_id,
                "execution_id": req.execution_id,
                "status": req.status,
                "capability": cap_details,
            })

            return req

    def deny_request(
        self,
        request_id: str,
        user: str = "human_operator",
        session_id: str = "web_session",
        reason: str = "Recusado pelo utilizador",
        mission_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> PermissionRequest:
        with self._lock:
            if request_id not in self._requests:
                raise PermissionNotFoundError(f"Pedido de permissão '{request_id}' não encontrado.")

            req = self._requests[request_id]

            if project_id and req.project_id and project_id != req.project_id:
                raise CrossProjectApprovalError("Rejeição falhou: project_id não corresponde.")
            if mission_id and req.mission_id and mission_id != req.mission_id:
                raise CrossProjectApprovalError("Rejeição falhou: mission_id não corresponde.")

            # Idempotência
            if req.status == PermissionRequestStatus.DENIED.value:
                return req

            now = time.time()
            req.user_decision = "USER_DENIED"
            req.decided_by = user
            req.session_id = session_id
            req.decided_at = now
            req.status = PermissionRequestStatus.DENIED.value
            req.decision_evidence["deny_reason"] = reason

            self._log_audit(
                req.request_id, "denied", req.risk_level, req.tool_name,
                req.mission_id, req.project_id, req.execution_id,
                user_decision="USER_DENIED",
                details={"reason": reason, "user": user}
            )

            self._notify_listeners("permission_request_denied", {
                "request_id": req.request_id,
                "mission_id": req.mission_id,
                "project_id": req.project_id,
                "execution_id": req.execution_id,
                "user": user,
                "reason": reason,
                "fallback_available": req.alternative_available,
                "fallback_description": req.fallback_description,
            })

            return req

    def execute_approved_request(
        self,
        request_id: str,
        executor_func: Optional[Callable[[], Any]] = None,
    ) -> PermissionRequest:
        """
        Executa a operação aprovada. Garante a invariante:
        NUNCA saltar diretamente de REQUESTED para EXECUTED.
        """
        with self._lock:
            if request_id not in self._requests:
                raise PermissionNotFoundError(f"Pedido '{request_id}' não encontrado.")

            req = self._requests[request_id]

            # Invariante de Segurança: Só executa se tiver sido aprovado e estiver pronto
            if req.status not in {
                PermissionRequestStatus.EXECUTION_READY.value,
                PermissionRequestStatus.AVAILABLE.value,
            }:
                raise InvalidApprovalStateError(
                    f"Execução bloqueada: pedido não está pronto para execução (estado atual: '{req.status}')."
                )

            self._log_audit(
                req.request_id, "execution_started", req.risk_level, req.tool_name,
                req.mission_id, req.project_id, req.execution_id
            )

            try:
                result = executor_func() if executor_func else {"executed": True, "tool": req.tool_name}
                req.status = PermissionRequestStatus.EXECUTED.value
                req.execution_result = {"status": "SUCCESS", "result": result}

                self._log_audit(
                    req.request_id, "execution_completed", req.risk_level, req.tool_name,
                    req.mission_id, req.project_id, req.execution_id,
                    details=req.execution_result
                )
                self._notify_listeners("permission_execution_result", {
                    "request_id": req.request_id,
                    "mission_id": req.mission_id,
                    "project_id": req.project_id,
                    "execution_id": req.execution_id,
                    "status": "EXECUTED",
                    "result": req.execution_result,
                })
            except Exception as exc:
                req.status = PermissionRequestStatus.FAILED.value
                req.execution_result = {"status": "FAILED", "error": str(exc)}
                self._log_audit(
                    req.request_id, "failed", req.risk_level, req.tool_name,
                    req.mission_id, req.project_id, req.execution_id,
                    details={"error": str(exc)}
                )
                self._notify_listeners("permission_execution_result", {
                    "request_id": req.request_id,
                    "mission_id": req.mission_id,
                    "project_id": req.project_id,
                    "execution_id": req.execution_id,
                    "status": "FAILED",
                    "error": str(exc),
                })
                raise

            return req

    def rollback_request(
        self,
        request_id: str,
        user: str = "human_operator",
        rollback_func: Optional[Callable[[], Any]] = None,
    ) -> RollbackRecord:
        with self._lock:
            if request_id not in self._requests:
                raise PermissionNotFoundError(f"Pedido '{request_id}' não encontrado.")

            req = self._requests[request_id]
            if not req.rollback_available:
                raise PermissionGatewayError(f"A ferramenta '{req.tool_name}' não suporta reversão automática.")

            rec = RollbackRecord(
                rollback_id=f"roll-{uuid.uuid4().hex[:10]}",
                request_id=request_id,
                tool_name=req.tool_name,
                installer=req.installer_source,
                version=req.installer_version,
                checksum=req.installer_checksum,
                is_reversible=True,
            )

            if rollback_func:
                rec.result = rollback_func()
            rec.executed = True
            self._rollbacks[request_id] = rec

            self._log_audit(
                request_id, "rolled_back", req.risk_level, req.tool_name,
                req.mission_id, req.project_id, req.execution_id,
                details={"user": user, "rollback_id": rec.rollback_id}
            )

            return rec

    def check_and_expire_requests(self) -> List[str]:
        with self._lock:
            now = time.time()
            expired_ids = []
            for r in self._requests.values():
                if r.status in {
                    PermissionRequestStatus.WAITING_FOR_USER.value,
                    PermissionRequestStatus.REQUESTED.value,
                } and now > r.expires_at:
                    r.status = PermissionRequestStatus.EXPIRED.value
                    expired_ids.append(r.request_id)
                    self._log_audit(
                        r.request_id, "expired", r.risk_level, r.tool_name,
                        r.mission_id, r.project_id, r.execution_id,
                        details={"expired_at": r.expires_at, "checked_at": now}
                    )
                    self._notify_listeners("permission_request_expired", {"request_id": r.request_id})
            return expired_ids

    def register_rollback(
        self,
        request_id: str,
        installer: Optional[str] = None,
        version: Optional[str] = None,
        checksum: Optional[str] = None,
        pre_install_state: Optional[Dict[str, Any]] = None,
        post_install_state: Optional[Dict[str, Any]] = None,
    ) -> RollbackRecord:
        with self._lock:
            req = self._requests.get(request_id)
            tool_name = req.tool_name if req else "unknown"
            rec = RollbackRecord(
                rollback_id=f"roll-{uuid.uuid4().hex[:10]}",
                request_id=request_id,
                tool_name=tool_name,
                installer=installer,
                version=version,
                checksum=checksum,
                pre_install_state=pre_install_state or {},
                post_install_state=post_install_state or {},
                is_reversible=True,
            )
            self._rollbacks[request_id] = rec
            return rec

    def get_rollbacks(self) -> Dict[str, RollbackRecord]:
        with self._lock:
            return dict(self._rollbacks)

    def get_pending_requests(self) -> List[PermissionRequest]:
        with self._lock:
            now = time.time()
            pending = []
            for r in self._requests.values():
                if r.status in {
                    PermissionRequestStatus.WAITING_FOR_USER.value,
                    PermissionRequestStatus.REQUESTED.value,
                }:
                    if now <= r.expires_at:
                        pending.append(r)
                    else:
                        r.status = PermissionRequestStatus.EXPIRED.value
            return pending

    def get_request(self, request_id: str) -> Optional[PermissionRequest]:
        with self._lock:
            return self._requests.get(request_id)

    def get_audit_log(self, request_id: Optional[str] = None) -> List[AuditLogEntry]:
        with self._lock:
            if request_id:
                return [entry for entry in self._audit_log if entry.request_id == request_id]
            return list(self._audit_log)


_GLOBAL_PERMISSION_GATEWAY: Optional[PermissionGatewayService] = None
_GLOBAL_GATEWAY_LOCK = threading.Lock()


def get_permission_gateway_service() -> PermissionGatewayService:
    global _GLOBAL_PERMISSION_GATEWAY
    with _GLOBAL_GATEWAY_LOCK:
        if _GLOBAL_PERMISSION_GATEWAY is None:
            _GLOBAL_PERMISSION_GATEWAY = PermissionGatewayService()
        return _GLOBAL_PERMISSION_GATEWAY


def reset_permission_gateway_service() -> None:
    global _GLOBAL_PERMISSION_GATEWAY
    with _GLOBAL_GATEWAY_LOCK:
        _GLOBAL_PERMISSION_GATEWAY = None
