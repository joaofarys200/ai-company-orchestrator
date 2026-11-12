"""
JARVIS OS — Study Engine Phase 7: Long-Running Operation Manager
Gere operações assíncronas do Study Engine com ID de operação, correlação,
desduplicação, reporte honesto de progresso, cancelamento cooperativo real e
recuperação/relato de operações interrompidas após reinício.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import threading
from typing import Any, Callable, Coroutine, Dict, List, Optional, Tuple
import uuid

from services.study_integration.contracts import (
    StudyOperationRecord,
    StudyOperationState,
    _utc_now_iso,
)


class StudyOperationManager:
    """Rastreia, desduplica e coordena execução assíncrona de operações de estudo."""

    def __init__(self, storage_dir: Path | str = Path("data/study")) -> None:
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.ops_path = self.storage_dir / "study_operations.json"
        self._lock = threading.Lock()
        self._operations: Dict[str, StudyOperationRecord] = {}
        self._cancel_events: Dict[str, threading.Event] = {}
        self._tasks: Dict[str, asyncio.Task] = {}
        self._load_and_mark_interrupted()

    def _load_and_mark_interrupted(self) -> None:
        if not self.ops_path.exists():
            return
        from services.study_fs import read_json_safe
        raw, corrupt = read_json_safe(
            self.ops_path, default=[], expected_type=list, backup_on_corrupt=True
        )
        if corrupt or not isinstance(raw, list):
            self._operations = {}
            return
        try:
            changed = False
            for item in raw[-150:]:
                if not isinstance(item, dict):
                    continue
                rec = StudyOperationRecord.from_dict(item)
                if rec.status in {
                    StudyOperationState.RUNNING.value,
                    StudyOperationState.QUEUED.value,
                }:
                    rec.status = StudyOperationState.INTERRUPTED.value
                    rec.stage = "INTERRUPTED"
                    rec.message = (
                        "Operação interrompida devido a reinício anterior do servidor; pode retomá-la."
                    )
                    rec.updated_at = _utc_now_iso()
                    changed = True
                self._operations[rec.operation_id] = rec
            if changed:
                self._save_operations()
        except Exception:
            self._operations = {}

    def _save_operations(self) -> None:
        from services.study_fs import atomic_write_json
        items = [op.to_dict() for op in list(self._operations.values())[-150:]]
        atomic_write_json(self.ops_path, items, indent=2)

    def get_operation(self, operation_id: str) -> Optional[StudyOperationRecord]:
        with self._lock:
            op = self._operations.get(operation_id)
            return StudyOperationRecord.from_dict(op.to_dict()) if op else None

    def list_operations(
        self,
        *,
        document_id: Optional[str] = None,
        chat_session_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        with self._lock:
            ops = list(self._operations.values())
        if document_id:
            ops = [op for op in ops if op.document_id == document_id]
        if chat_session_id:
            ops = [op for op in ops if op.chat_session_id == chat_session_id]
        ops.sort(key=lambda o: o.started_at, reverse=True)
        return [o.to_dict() for o in ops[:40]]

    def find_active_by_dedup_key(self, dedup_key: str) -> Optional[StudyOperationRecord]:
        if not dedup_key:
            return None
        with self._lock:
            for op in self._operations.values():
                if (
                    op.dedup_key == dedup_key
                    and op.status in {StudyOperationState.QUEUED.value, StudyOperationState.RUNNING.value}
                ):
                    return StudyOperationRecord.from_dict(op.to_dict())
        return None

    async def submit_operation(
        self,
        *,
        capability: str,
        document_id: Optional[str],
        chat_session_id: str,
        correlation_id: str,
        dedup_key: str,
        worker_fn: Callable[[Callable[[str, Optional[float], str], None], threading.Event], Dict[str, Any]],
        on_status_event: Optional[Callable[[StudyOperationRecord], Coroutine[Any, Any, None]]] = None,
        on_complete_callback: Optional[Callable[[StudyOperationRecord, Dict[str, Any]], Coroutine[Any, Any, None]]] = None,
    ) -> Tuple[StudyOperationRecord, bool]:
        """
        Regista e inicia uma operação assíncrona em background.
        Devolve (record, deduplicated). Se já houver uma operação ativa com o mesmo dedup_key,
        devolve a existente sem iniciar processamento duplicado.
        """
        existing = self.find_active_by_dedup_key(dedup_key)
        if existing is not None:
            return existing, True

        op_id = f"studyop_{uuid.uuid4().hex[:12]}"
        cancel_ev = threading.Event()
        rec = StudyOperationRecord(
            operation_id=op_id,
            correlation_id=correlation_id or op_id,
            chat_session_id=chat_session_id,
            capability=capability,
            document_id=document_id,
            status=StudyOperationState.RUNNING.value,
            stage="STARTED",
            progress_percent=None,
            message="Operação iniciada.",
            dedup_key=dedup_key,
        )
        with self._lock:
            self._operations[op_id] = rec
            self._cancel_events[op_id] = cancel_ev
            self._save_operations()
        if document_id:
            from services.study_ai_engine import register_study_generation_start

            register_study_generation_start(document_id, op_id)

        loop = asyncio.get_running_loop()

        def emit_progress(stage: str, pct: Optional[float], message: str) -> None:
            # Nunca fabricar percentagem se o motor subjacente não reportar float válido
            clean_pct: Optional[float]
            if isinstance(pct, (int, float)) and not isinstance(pct, bool):
                val = float(pct)
                clean_pct = round(val * 100.0 if 0.0 <= val <= 1.0 else max(0.0, min(100.0, val)), 1)
            else:
                clean_pct = None
            with self._lock:
                cur = self._operations.get(op_id)
                if cur is None or cur.status in {
                    StudyOperationState.COMPLETED.value,
                    StudyOperationState.FAILED.value,
                    StudyOperationState.CANCELLED.value,
                }:
                    return
                cur.stage = str(stage or cur.stage)
                cur.progress_percent = clean_pct
                cur.message = str(message or cur.message)
                cur.updated_at = _utc_now_iso()
                snapshot = StudyOperationRecord.from_dict(cur.to_dict())
                self._save_operations()
            if on_status_event is not None:
                try:
                    asyncio.run_coroutine_threadsafe(on_status_event(snapshot), loop)
                except Exception:
                    pass

        async def _runner() -> None:
            try:
                if on_status_event is not None:
                    await on_status_event(StudyOperationRecord.from_dict(rec.to_dict()))
                outcome = await asyncio.to_thread(worker_fn, emit_progress, cancel_ev)
                if cancel_ev.is_set() or (isinstance(outcome, dict) and outcome.get("cancelled")):
                    with self._lock:
                        cur = self._operations[op_id]
                        cur.status = StudyOperationState.CANCELLED.value
                        cur.stage = "CANCELLED"
                        cur.message = "Operação cancelada a pedido do utilizador."
                        cur.updated_at = _utc_now_iso()
                        final_rec = StudyOperationRecord.from_dict(cur.to_dict())
                        self._save_operations()
                    if on_status_event is not None:
                        await on_status_event(final_rec)
                    return

                with self._lock:
                    cur = self._operations[op_id]
                    cur.status = StudyOperationState.COMPLETED.value
                    cur.stage = "COMPLETED"
                    cur.progress_percent = 100.0
                    cur.message = str((outcome or {}).get("summary_markdown") or "Concluído com sucesso.")[:300]
                    cur.result_summary = dict((outcome or {}).get("result_ref") or {})
                    cur.updated_at = _utc_now_iso()
                    final_rec = StudyOperationRecord.from_dict(cur.to_dict())
                    self._save_operations()
                if on_status_event is not None:
                    await on_status_event(final_rec)
                if on_complete_callback is not None:
                    await on_complete_callback(final_rec, outcome or {})
            except asyncio.CancelledError:
                cancel_ev.set()
                with self._lock:
                    cur = self._operations[op_id]
                    cur.status = StudyOperationState.CANCELLED.value
                    cur.stage = "CANCELLED"
                    cur.message = "Tarefa cancelada."
                    cur.updated_at = _utc_now_iso()
                    final_rec = StudyOperationRecord.from_dict(cur.to_dict())
                    self._save_operations()
                if on_status_event is not None:
                    try:
                        await on_status_event(final_rec)
                    except Exception:
                        pass
                raise
            except Exception as exc:
                err_txt = str(exc)
                was_cancelled = cancel_ev.is_set() or "cancel" in err_txt.lower()
                with self._lock:
                    cur = self._operations[op_id]
                    if was_cancelled:
                        cur.status = StudyOperationState.CANCELLED.value
                        cur.stage = "CANCELLED"
                        cur.message = "Operação cancelada."
                    else:
                        cur.status = StudyOperationState.FAILED.value
                        cur.stage = "FAILED"
                        cur.error = err_txt
                        cur.message = f"Erro na operação: {err_txt}"
                    cur.updated_at = _utc_now_iso()
                    final_rec = StudyOperationRecord.from_dict(cur.to_dict())
                    self._save_operations()
                if on_status_event is not None:
                    await on_status_event(final_rec)
            finally:
                with self._lock:
                    self._tasks.pop(op_id, None)
                    self._cancel_events.pop(op_id, None)
                    still_active = bool(
                        document_id
                        and any(
                            o.document_id == document_id
                            and o.status in {StudyOperationState.RUNNING.value, StudyOperationState.QUEUED.value}
                            for o in self._operations.values()
                        )
                    )
                if document_id and not still_active:
                    from services.study_ai_engine import register_study_generation_start

                    register_study_generation_start(document_id, op_id)

        task = asyncio.create_task(_runner())
        with self._lock:
            self._tasks[op_id] = task
        return StudyOperationRecord.from_dict(rec.to_dict()), False

    def request_cancel(
        self,
        *,
        operation_id: Optional[str] = None,
        document_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Solicita cancelamento cooperativo honesto. Não marca como CANCELLED enquanto
        a tarefa em execução não interromper/confirmar; se já estava concluída/inativa, informa claramente.
        """
        target_ops: List[StudyOperationRecord] = []
        with self._lock:
            if operation_id and operation_id in self._operations:
                target_ops.append(self._operations[operation_id])
            elif document_id:
                for op in self._operations.values():
                    if op.document_id == document_id and op.status in {
                        StudyOperationState.RUNNING.value,
                        StudyOperationState.QUEUED.value,
                    }:
                        target_ops.append(op)

            if not target_ops:
                return {
                    "found": False,
                    "cancellation_requested": False,
                    "status": "NOT_FOUND",
                    "message": "Nenhuma operação de estudo ativa encontrada para cancelar.",
                }

            requested_ids: List[str] = []
            already_finished: List[str] = []
            for op in target_ops:
                if op.status not in {StudyOperationState.RUNNING.value, StudyOperationState.QUEUED.value}:
                    already_finished.append(op.operation_id)
                    continue
                ev = self._cancel_events.get(op.operation_id)
                if ev is not None:
                    ev.set()
                op.stage = "CANCELLING"
                op.message = "Cancelamento solicitado; a aguardar paragem segura da tarefa."
                op.updated_at = _utc_now_iso()
                requested_ids.append(op.operation_id)
                if op.document_id:
                    from services.study_ai_engine import cancel_study_generation

                    cancel_study_generation(op.document_id)
            if requested_ids:
                self._save_operations()

        if requested_ids:
            return {
                "found": True,
                "cancellation_requested": True,
                "operation_ids": requested_ids,
                "status": "CANCELLING",
                "message": "Cancelamento solicitado. O estado mudará para CANCELLED assim que a tarefa parar.",
            }
        return {
            "found": True,
            "cancellation_requested": False,
            "operation_ids": already_finished,
            "status": target_ops[0].status,
            "message": f"A operação já terminou com estado {target_ops[0].status}.",
        }
