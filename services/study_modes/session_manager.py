"""
JARVIS OS — Study Engine Phase 6: Study Session Manager
Sessões de estudo duráveis com suporte a pausa, retoma exata após interrupção
e preservação contínua de respostas parciais e histórico.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

from services.study_modes.contracts import (
    StudySessionMode,
    StudySessionState,
    StudySessionStatus,
)
from services.study_modes.persistence import StudyModePersistence


class StudySessionManager:
    """Gere o ciclo de vida persistente das sessões de estudo."""

    SESSIONS_FILE = "study_sessions.json"

    def __init__(self, persistence: StudyModePersistence) -> None:
        self.persistence = persistence

    def start_session(
        self,
        *,
        document_id: str,
        mode: str = StudySessionMode.FLASHCARD_REVIEW.value,
        title: str = "",
        item_ids: Optional[Sequence[str]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> StudySessionState:
        now = datetime.now().isoformat()
        sid = f"sess_{uuid.uuid4().hex[:10]}"
        session = StudySessionState(
            session_id=sid,
            document_id=document_id,
            mode=mode,
            status=StudySessionStatus.IN_PROGRESS.value,
            title=title or f"Sessão {mode}",
            item_ids=[str(x) for x in (item_ids or []) if str(x).strip()],
            current_index=0,
            config=dict(config or {}),
            started_at=now,
            last_activity_at=now,
        )

        def _mutate(cur: Any) -> Dict[str, Any]:
            store = dict(cur) if isinstance(cur, dict) else {}
            store[sid] = session.to_dict()
            return store

        self.persistence.update_state_file_atomic(self.SESSIONS_FILE, {}, _mutate)
        return session

    def get_session(self, session_id: str) -> Optional[StudySessionState]:
        raw = self.persistence.load_state_file(self.SESSIONS_FILE, {})
        if isinstance(raw, dict) and isinstance(raw.get(session_id), dict):
            return StudySessionState.from_dict(raw[session_id])
        return None

    def list_sessions(
        self,
        *,
        document_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[StudySessionState]:
        raw = self.persistence.load_state_file(self.SESSIONS_FILE, {})
        out: List[StudySessionState] = []
        if isinstance(raw, dict):
            for v in raw.values():
                if not isinstance(v, dict):
                    continue
                s = StudySessionState.from_dict(v)
                if document_id and s.document_id != document_id:
                    continue
                if status and s.status != status:
                    continue
                out.append(s)
        out.sort(key=lambda x: x.last_activity_at or x.started_at, reverse=True)
        return out

    def record_step(
        self,
        session_id: str,
        *,
        item_id: Optional[str] = None,
        partial_response: Any = None,
        outcome: Optional[Dict[str, Any]] = None,
        next_index: Optional[int] = None,
        mark_completed: bool = False,
    ) -> StudySessionState:
        holder: List[Optional[StudySessionState]] = [None]
        now = datetime.now().isoformat()

        def _mutate(cur: Any) -> Dict[str, Any]:
            store = dict(cur) if isinstance(cur, dict) else {}
            raw = store.get(session_id)
            if not isinstance(raw, dict):
                raise ValueError(f"Sessão de estudo '{session_id}' não encontrada.")
            sess = StudySessionState.from_dict(raw)
            sess.last_activity_at = now
            if item_id:
                if partial_response is not None:
                    sess.partial_responses[item_id] = partial_response
                if mark_completed and item_id not in sess.completed_item_ids:
                    sess.completed_item_ids.append(item_id)
            if outcome is not None:
                sess.item_outcomes.append(outcome)
            if next_index is not None:
                sess.current_index = max(0, int(next_index))
            elif mark_completed and sess.item_ids:
                sess.current_index = min(len(sess.item_ids) - 1, sess.current_index + 1)
            store[session_id] = sess.to_dict()
            holder[0] = sess
            return store

        self.persistence.update_state_file_atomic(self.SESSIONS_FILE, {}, _mutate)
        assert holder[0] is not None
        return holder[0]

    def pause_session(self, session_id: str) -> StudySessionState:
        holder: List[Optional[StudySessionState]] = [None]
        now = datetime.now().isoformat()

        def _mutate(cur: Any) -> Dict[str, Any]:
            store = dict(cur) if isinstance(cur, dict) else {}
            raw = store.get(session_id)
            if not isinstance(raw, dict):
                raise ValueError(f"Sessão '{session_id}' não encontrada.")
            sess = StudySessionState.from_dict(raw)
            if sess.status != StudySessionStatus.COMPLETED.value:
                sess.status = StudySessionStatus.PAUSED.value
                sess.paused_at = now
                sess.last_activity_at = now
            store[session_id] = sess.to_dict()
            holder[0] = sess
            return store

        self.persistence.update_state_file_atomic(self.SESSIONS_FILE, {}, _mutate)
        assert holder[0] is not None
        return holder[0]

    def resume_session(self, session_id: str) -> StudySessionState:
        holder: List[Optional[StudySessionState]] = [None]
        now = datetime.now().isoformat()

        def _mutate(cur: Any) -> Dict[str, Any]:
            store = dict(cur) if isinstance(cur, dict) else {}
            raw = store.get(session_id)
            if not isinstance(raw, dict):
                raise ValueError(f"Sessão '{session_id}' não encontrada.")
            sess = StudySessionState.from_dict(raw)
            if sess.status != StudySessionStatus.COMPLETED.value:
                sess.status = StudySessionStatus.IN_PROGRESS.value
                sess.paused_at = None
                sess.last_activity_at = now
            store[session_id] = sess.to_dict()
            holder[0] = sess
            return store

        self.persistence.update_state_file_atomic(self.SESSIONS_FILE, {}, _mutate)
        assert holder[0] is not None
        return holder[0]

    def complete_session(
        self,
        session_id: str,
        *,
        summary_stats: Optional[Dict[str, Any]] = None,
    ) -> StudySessionState:
        holder: List[Optional[StudySessionState]] = [None]
        now = datetime.now().isoformat()

        def _mutate(cur: Any) -> Dict[str, Any]:
            store = dict(cur) if isinstance(cur, dict) else {}
            raw = store.get(session_id)
            if not isinstance(raw, dict):
                raise ValueError(f"Sessão '{session_id}' não encontrada.")
            sess = StudySessionState.from_dict(raw)
            sess.status = StudySessionStatus.COMPLETED.value
            sess.completed_at = now
            sess.last_activity_at = now
            if summary_stats:
                sess.summary_stats.update(summary_stats)
            else:
                sess.summary_stats.setdefault("completed_items", len(sess.completed_item_ids))
                sess.summary_stats.setdefault("total_items", len(sess.item_ids))
            store[session_id] = sess.to_dict()
            holder[0] = sess
            return store

        self.persistence.update_state_file_atomic(self.SESSIONS_FILE, {}, _mutate)
        assert holder[0] is not None
        return holder[0]

