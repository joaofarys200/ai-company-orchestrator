"""
JARVIS OS — Security Sentinel Response Engine (Fase S3)
Central orchestrator for human-approved response actions, verification, replay prevention, and rollback.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from security.sentinel.contracts import (
    PermissionLevel,
    ResponseActionStatus,
    ResponseActionType,
    SecurityResponseAction,
)
from security.sentinel.response.executors.base import BaseActionExecutor
from security.sentinel.response.executors.known_good import MarkKnownGoodExecutor
from security.sentinel.response.executors.network import FirewallBlockExecutor
from security.sentinel.response.executors.process import ProcessTerminationExecutor
from security.sentinel.response.executors.quarantine import FileQuarantineExecutor
from security.sentinel.response.executors.task import ScheduledTaskDisableExecutor


class ResponseEngine:
    """Motor central de gestão de ações de resposta defensiva do Sentinel."""

    def __init__(self, storage_dir: Optional[str] = None) -> None:
        if storage_dir is None:
            project_root = os.path.realpath(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
            self.storage_dir = os.path.join(project_root, "sentinel")
        else:
            self.storage_dir = storage_dir

        os.makedirs(self.storage_dir, exist_ok=True)
        self.history_file = os.path.join(self.storage_dir, "response_history.json")

        self._actions: Dict[str, SecurityResponseAction] = {}
        self._lock = asyncio.Lock()

        # Inicialização dos executores especializados
        self._executors: Dict[ResponseActionType, BaseActionExecutor] = {
            ResponseActionType.TERMINATE_PROCESS: ProcessTerminationExecutor(),
            ResponseActionType.DISABLE_SCHEDULED_TASK: ScheduledTaskDisableExecutor(),
            ResponseActionType.BLOCK_NETWORK_ENDPOINT: FirewallBlockExecutor(),
            ResponseActionType.QUARANTINE_FILE: FileQuarantineExecutor(
                quarantine_dir=os.path.join(self.storage_dir, "quarantine")
            ),
            ResponseActionType.MARK_KNOWN_GOOD: MarkKnownGoodExecutor(),
        }

        self._load_history()

    def _load_history(self) -> None:
        if os.path.isfile(self.history_file):
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    items = data if isinstance(data, list) else list(data.values())
                    for item in items:
                        if isinstance(item, dict):
                            action = SecurityResponseAction(**item)
                            self._actions[action.action_id] = action
            except Exception:
                pass

    def _save_history(self) -> None:
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump([a.to_dict() for a in self._actions.values()], f, indent=2)
        except Exception:
            pass

    def get_actions(self) -> List[SecurityResponseAction]:
        return list(self._actions.values())

    def get_action(self, action_id: str) -> Optional[SecurityResponseAction]:
        return self._actions.get(action_id)

    def propose_action(
        self,
        incident_id: str,
        action_type: ResponseActionType,
        target: str,
        rationale: str,
        evidence_ids: List[str],
        permission_level: PermissionLevel = PermissionLevel.LOW_RISK_MUTATION,
        requested_by: str = "sentinel_correlation_engine",
    ) -> SecurityResponseAction:
        """Propõe uma ação de resposta defensiva sem executar qualquer mutação."""
        # 1. Validação estrita de evidências
        if not evidence_ids or len(evidence_ids) == 0:
            raise ValueError("Proposta de ação de resposta rejeitada: Requer pelo menos 1 ID de evidência válido e imutável")

        # 2. Validação de nível de permissão (Fase S3 permite apenas LOW_RISK_MUTATION e READ_ONLY)
        if permission_level in (PermissionLevel.HIGH_RISK_MUTATION, PermissionLevel.CRITICAL_MUTATION):
            raise PermissionError(
                f"Nível de permissão '{permission_level.value}' está estritamente bloqueado na Fase S3 do Sentinel"
            )

        # 3. Validação do executor
        executor = self._executors.get(action_type)
        if not executor:
            raise ValueError(f"Tipo de ação de resposta não suportado: '{action_type}'")

        action_id = f"ACT-{action_type.value[:4]}-{int(time.time() * 1000)}-{uuid.uuid4().hex[:6]}"

        action = SecurityResponseAction(
            action_id=action_id,
            incident_id=incident_id,
            action_type=action_type.value,
            target=target,
            rationale=rationale,
            evidence_ids=evidence_ids,
            permission_level=permission_level.value,
            requested_by=requested_by,
            approval_required=True,
            status=ResponseActionStatus.PROPOSED.value,
            rollback_available=(action_type != ResponseActionType.TERMINATE_PROCESS),
            rollback_plan=f"Reverter a ação {action_type.value} no alvo {target}",
        )

        # Captura o estado do alvo antes de qualquer ação
        action.pre_state = executor.capture_pre_state(action)
        action.status = ResponseActionStatus.WAITING_APPROVAL.value
        action.updated_at = time.time()

        self._actions[action_id] = action
        self._save_history()

        return action

    async def approve_and_execute(
        self,
        action_id: str,
        user: str,
        session_id: str,
        incident_id: Optional[str] = None,
        timestamp: Optional[float] = None,
    ) -> Tuple[bool, SecurityResponseAction, str]:
        """Aprova formalmente e executa uma ação de resposta com verificação e proteção contra replay."""
        async with self._lock:
            action = self._actions.get(action_id)
            if not action:
                return False, None, f"Ação '{action_id}' não encontrada"

            # 1. Validação de autenticação e contexto
            if not user or len(user.strip()) < 2:
                return False, action, "Aprovação rejeitada: Identificador de utilizador ausente ou inválido"

            if not session_id or len(session_id.strip()) < 4:
                return False, action, "Aprovação rejeitada: Contexto de sessão/token ausente ou inválido"

            if incident_id and action.incident_id != incident_id:
                return False, action, f"Aprovação rejeitada: incident_id incompatível ('{incident_id}' != '{action.incident_id}')"

            # 2. Proteção contra Ataques de Replay
            if action.status not in (ResponseActionStatus.PROPOSED.value, ResponseActionStatus.WAITING_APPROVAL.value):
                return False, action, f"Aprovação rejeitada: Ação já se encontra no estado '{action.status}' (replay bloqueado)"

            # 3. Transição para APPROVED
            now = timestamp or time.time()
            action.approved_by = user.strip()
            action.approval_session_id = session_id.strip()
            action.approval_timestamp = now
            action.status = ResponseActionStatus.APPROVED.value
            action.updated_at = now

            executor = self._executors.get(ResponseActionType(action.action_type))
            if not executor:
                action.status = ResponseActionStatus.FAILED.value
                action.error_message = "Executor indisponível para o tipo de ação"
                self._save_history()
                return False, action, action.error_message

            # 4. Pré-verificação de integridade do alvo (Target Integrity Check)
            try:
                is_valid, check_msg = await asyncio.to_thread(executor.pre_check, action)
            except Exception as e:
                action.status = ResponseActionStatus.FAILED.value
                action.error_message = f"Falha na pré-verificação: {str(e)}"
                action.updated_at = time.time()
                self._save_history()
                return False, action, action.error_message

            if not is_valid:
                action.status = ResponseActionStatus.FAILED.value
                action.error_message = f"Pré-verificação falhou: {check_msg}"
                action.updated_at = time.time()
                self._save_history()
                return False, action, action.error_message

            # 5. Execução
            action.status = ResponseActionStatus.EXECUTING.value
            action.updated_at = time.time()
            try:
                exec_result = await asyncio.to_thread(executor.execute, action)
                action.execution_result = exec_result
            except Exception as e:
                action.status = ResponseActionStatus.FAILED.value
                action.error_message = f"Falha na execução: {str(e)}"
                action.updated_at = time.time()
                self._save_history()
                return False, action, action.error_message

            # 6. Verificação de Pós-Estado (Post-State Empirical Verification)
            action.status = ResponseActionStatus.VERIFYING.value
            action.updated_at = time.time()
            try:
                verified, verify_result = await asyncio.to_thread(executor.verify, action)
                action.verification_result = verify_result
                action.post_state = verify_result.get("post_state", {})

                if not verified:
                    action.status = ResponseActionStatus.FAILED.value
                    action.error_message = f"Verificação empírica falhou: {verify_result.get('reason', 'Pós-estado inconsistente')}"
                    action.updated_at = time.time()
                    self._save_history()
                    return False, action, action.error_message

                action.status = ResponseActionStatus.COMPLETED.value
                action.updated_at = time.time()
                self._save_history()
                return True, action, "Ação executada e verificada com sucesso"

            except Exception as e:
                action.status = ResponseActionStatus.FAILED.value
                action.error_message = f"Erro na verificação: {str(e)}"
                action.updated_at = time.time()
                self._save_history()
                return False, action, action.error_message

    async def rollback(
        self,
        action_id: str,
        user: str,
        session_id: str,
    ) -> Tuple[bool, SecurityResponseAction, str]:
        """Reverte uma ação previamente concluída para o seu estado original."""
        async with self._lock:
            action = self._actions.get(action_id)
            if not action:
                return False, None, f"Ação '{action_id}' não encontrada"

            if not action.rollback_available:
                return False, action, f"Rollback não suportado para o tipo de ação '{action.action_type}'"

            if action.status != ResponseActionStatus.COMPLETED.value:
                return False, action, f"Rollback só pode ser aplicado a ações concluídas (estado atual: {action.status})"

            executor = self._executors.get(ResponseActionType(action.action_type))
            if not executor:
                return False, action, "Executor indisponível para efetuar rollback"

            try:
                success, rollback_res = await asyncio.to_thread(executor.rollback, action)
                action.rollback_result = rollback_res
                if success:
                    action.status = ResponseActionStatus.ROLLED_BACK.value
                    action.updated_at = time.time()
                    self._save_history()
                    return True, action, "Rollback aplicado com sucesso"
                else:
                    action.error_message = f"Falha no rollback: {rollback_res.get('error', 'Inconsistência na reversão')}"
                    self._save_history()
                    return False, action, action.error_message
            except Exception as e:
                action.error_message = f"Erro durante execução do rollback: {str(e)}"
                self._save_history()
                return False, action, action.error_message

    def reject(
        self,
        action_id: str,
        user: str,
        reason: str,
    ) -> Tuple[bool, SecurityResponseAction, str]:
        """Rejeita formalmente uma proposta de ação de resposta."""
        action = self._actions.get(action_id)
        if not action:
            return False, None, f"Ação '{action_id}' não encontrada"

        if action.status not in (ResponseActionStatus.PROPOSED.value, ResponseActionStatus.WAITING_APPROVAL.value):
            return False, action, f"Ação não pode ser rejeitada no estado '{action.status}'"

        action.status = ResponseActionStatus.REJECTED.value
        action.error_message = f"Rejeitado por {user}: {reason}"
        action.updated_at = time.time()
        self._save_history()
        return True, action, "Ação rejeitada pelo utilizador"

    reject_action = reject

