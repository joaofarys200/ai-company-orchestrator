"""
JARVIS OS — Security Sentinel Event Correlation & Deduplication Engine
Correlaciona múltiplos sinais independentes e faz deduplicação determinística com linha do tempo.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any, Dict, List, Optional, Set

from security.sentinel.contracts import (
    BaselineDiff,
    EventCategory,
    HumanIncidentReview,
    KnownGoodItem,
    SecurityClassification,
    SecurityEvent,
    SecurityEvidence,
    SystemBaseline,
)


class EventCorrelationEngine:
    """Motor de correlação de telemetria e deduplicação de eventos de segurança."""

    def __init__(self) -> None:
        # Tabela em memória de eventos ativos indexados por fingerprint determinístico
        self.active_events: Dict[str, SecurityEvent] = {}
        self.event_history: List[SecurityEvent] = []
        self.known_goods: Dict[str, KnownGoodItem] = {}

    def compute_fingerprint(self, category: str, asset: str, anomaly_type: str) -> str:
        """Gera um fingerprint determinístico para deduplicação entre ciclos de scan."""
        raw = f"{category.upper()}:{asset.strip().lower()}:{anomaly_type.upper()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def register_known_good(self, known_good: KnownGoodItem) -> None:
        """Regista um item como Known Good aprovado pelo utilizador."""
        self.known_goods[known_good.item_key] = known_good
        # Se existir evento ativo com esta chave, marca como resolvido/known_good
        for ev in self.active_events.values():
            if ev.fingerprint == known_good.item_key or known_good.item_key in ev.evidence_ids:
                ev.is_known_good = True
                ev.status = "RESOLVED"

    def is_known_good(self, item_key: str) -> bool:
        """Verifica se um item foi aprovado pelo utilizador."""
        return item_key in self.known_goods

    def correlate_diff(
        self,
        diff: BaselineDiff,
        current_baseline: Optional[SystemBaseline] = None,
        evidences: Optional[List[SecurityEvidence]] = None,
    ) -> List[SecurityEvent]:
        """Correlaciona as alterações do diff com evidências e emite eventos deduplicados."""
        now = time.time()
        new_events: List[SecurityEvent] = []
        evidence_map = {ev.asset: ev for ev in (evidences or [])}

        # 1. Regra Crítica: Degradação do Windows Defender / Firewall
        sec = current_baseline.windows_security if current_baseline else {}
        if sec:
            if sec.get("defender_realtime_enabled") is False:
                fp = self.compute_fingerprint(EventCategory.DEFENDER.value, "system:defender", "REALTIME_DISABLED")
                ev = self._record_or_update_event(
                    fingerprint=fp,
                    category=EventCategory.DEFENDER.value,
                    severity=SecurityClassification.HIGH_RISK.value,
                    confidence=1.0,
                    evidence_ids=["system:windows_security_subsystem"],
                    rationale="A proteção em tempo real do Windows Defender foi desativada no sistema.",
                    recommended_action="Reativar a proteção em tempo real do Windows Defender nas Definições de Segurança.",
                    now=now,
                )
                if ev:
                    new_events.append(ev)

            if (
                sec.get("firewall_domain_enabled") is False
                or sec.get("firewall_private_enabled") is False
                or sec.get("firewall_public_enabled") is False
            ):
                fp = self.compute_fingerprint(EventCategory.DEFENDER.value, "system:firewall", "FIREWALL_DISABLED")
                ev = self._record_or_update_event(
                    fingerprint=fp,
                    category=EventCategory.DEFENDER.value,
                    severity=SecurityClassification.SUSPICIOUS.value,
                    confidence=1.0,
                    evidence_ids=["system:windows_security_subsystem"],
                    rationale="Um ou mais perfis da Firewall do Windows encontram-se desativados.",
                    recommended_action="Verificar o estado dos perfis da Firewall do Windows.",
                    now=now,
                )
                if ev:
                    new_events.append(ev)

        # 2. Regra: Ficheiro Hosts Alterado
        if diff.hosts_changed:
            fp = self.compute_fingerprint(EventCategory.HOSTS.value, "file:hosts", "HOSTS_MODIFIED")
            h_diff = diff.hosts_diff or {}
            diff_desc = f"Hash anterior: {str(h_diff.get('base_sha256'))[:10]}... -> Novo Hash: {str(h_diff.get('current_sha256'))[:10]}..."
            ev = self._record_or_update_event(
                fingerprint=fp,
                category=EventCategory.HOSTS.value,
                severity=SecurityClassification.SUSPICIOUS.value,
                confidence=0.95,
                evidence_ids=["file:hosts"],
                rationale=f"O ficheiro hosts do Windows foi alterado desde o último baseline. ({diff_desc})",
                recommended_action="Inspecionar os novos mapeamentos de IP no ficheiro hosts para descartar pharming.",
                now=now,
            )
            if ev:
                new_events.append(ev)

        # 3. Correlação Multi-Sinal: Novos Processos & Persistência & Rede
        new_proc_names = {p.get("name", "").lower(): p for p in diff.new_processes}
        new_persist_names = {p.get("name", "").lower(): p for p in diff.new_persistence}

        for proc in diff.new_processes:
            p_name = proc.get("name", "unknown")
            p_pid = proc.get("pid", 0)
            p_exe = proc.get("exe_path", "")
            is_temp = proc.get("is_temp_dir", False)
            asset_key = f"process:{p_pid}:{p_name}"

            # Verificar se há persistência correlacionada
            has_persistence = any(
                p_name.lower() in str(persist.get("target_path", "")).lower()
                or p_name.lower() == str(persist.get("name", "")).lower()
                for persist in diff.new_persistence
            )

            # Verificar se há conexão de rede correlacionada
            has_network = any(
                n.get("pid") == p_pid for n in (current_baseline.network if current_baseline else []) if n.get("status") != "LISTEN"
            )

            # Matriz de Correlação
            if is_temp and has_persistence and has_network:
                # SINAL TRIPLO: Processo em %TEMP% + Chave de Arranque + Conexão TCP Ativa
                fp = self.compute_fingerprint(EventCategory.PROCESS.value, asset_key, "CORRELATED_TEMP_EXEC_PERSISTENCE")
                ev = self._record_or_update_event(
                    fingerprint=fp,
                    category=EventCategory.PROCESS.value,
                    severity=SecurityClassification.HIGH_RISK.value,
                    confidence=0.88,
                    evidence_ids=[f"process:{p_pid}"],
                    rationale=(
                        f"Processo anómalo '{p_name}' a executar de pasta temporária ({p_exe}), "
                        f"com persistência no arranque e conexão de rede ativa observada."
                    ),
                    recommended_action="Inspecionar o processo e a respetiva entrada de persistência.",
                    affected_process=proc,
                    now=now,
                )
                if ev:
                    new_events.append(ev)

            elif is_temp:
                # Processo em pasta temporária
                fp = self.compute_fingerprint(EventCategory.PROCESS.value, asset_key, "TEMP_DIR_EXECUTION")
                ev = self._record_or_update_event(
                    fingerprint=fp,
                    category=EventCategory.PROCESS.value,
                    severity=SecurityClassification.SUSPICIOUS.value,
                    confidence=0.75,
                    evidence_ids=[f"process:{p_pid}"],
                    rationale=f"Novo processo '{p_name}' detetado a executar a partir de diretório temporário: {p_exe}",
                    recommended_action="Verificar a proveniência do executável.",
                    affected_process=proc,
                    now=now,
                )
                if ev:
                    new_events.append(ev)

            else:
                # Processo novo benigno/desconhecido (baixo risco, não-alarme)
                fp = self.compute_fingerprint(EventCategory.PROCESS.value, asset_key, "NEW_PROCESS_OBSERVED")
                ev = self._record_or_update_event(
                    fingerprint=fp,
                    category=EventCategory.PROCESS.value,
                    severity=SecurityClassification.BENIGN.value,
                    confidence=0.50,
                    evidence_ids=[f"process:{p_pid}"],
                    rationale=f"Novo processo '{p_name}' observado no sistema em {p_exe}",
                    recommended_action="Nenhuma ação necessária para processos legítimos.",
                    affected_process=proc,
                    now=now,
                )
                if ev:
                    new_events.append(ev)

        # 4. Regra: Nova Entrada de Persistência Isolada
        for persist in diff.new_persistence:
            p_kind = persist.get("kind", "UNKNOWN")
            p_name = persist.get("name", "unknown")
            p_target = persist.get("target_path", "")
            asset_key = f"persistence:{p_kind.lower()}:{p_name}"

            fp = self.compute_fingerprint(EventCategory.PERSISTENCE.value, asset_key, "NEW_PERSISTENCE_ENTRY")
            ev = self._record_or_update_event(
                fingerprint=fp,
                category=EventCategory.PERSISTENCE.value,
                severity=SecurityClassification.SUSPICIOUS.value,
                confidence=0.70,
                evidence_ids=[asset_key],
                rationale=f"Nova entrada de persistência criada ({p_kind}): '{p_name}' -> {p_target}",
                recommended_action="Confirmar se esta entrada de arranque foi criada por um programa legítimo.",
                now=now,
            )
            if ev:
                new_events.append(ev)

        # 5. Regra: Novas Extensões de Navegador
        for ext in diff.new_browser_extensions:
            b_name = ext.get("browser", "BROWSER")
            e_id = ext.get("extension_id", "unknown")
            e_name = ext.get("name", "Unknown Extension")
            perms = ext.get("permissions", [])
            asset_key = f"extension:{b_name.lower()}:{e_id}"

            has_sensitive_perms = any(p in perms for p in ["cookies", "webRequest", "webRequestBlocking", "<all_urls>", "*://*/*"])
            severity = SecurityClassification.SUSPICIOUS.value if has_sensitive_perms else SecurityClassification.BENIGN.value

            fp = self.compute_fingerprint(EventCategory.BROWSER.value, asset_key, "NEW_EXTENSION_INSTALLED")
            ev = self._record_or_update_event(
                fingerprint=fp,
                category=EventCategory.BROWSER.value,
                severity=severity,
                confidence=0.80,
                evidence_ids=[asset_key],
                rationale=f"Nova extensão detetada no {b_name}: '{e_name}' (ID: {e_id}, Permissões: {len(perms)})",
                recommended_action="Validar a utilidade e permissões da extensão.",
                now=now,
            )
            if ev:
                new_events.append(ev)

        return new_events

    def _record_or_update_event(
        self,
        fingerprint: str,
        category: str,
        severity: str,
        confidence: float,
        evidence_ids: List[str],
        rationale: str,
        recommended_action: str,
        now: Optional[float] = None,
        affected_process: Optional[Dict[str, Any]] = None,
        affected_network_endpoint: Optional[Dict[str, Any]] = None,
    ) -> Optional[SecurityEvent]:
        """Regista um novo evento ou atualiza a cronologia do evento existente (Deduplicação)."""
        now = now if now is not None else time.time()
        is_known = self.is_known_good(fingerprint)

        if fingerprint in self.active_events:
            # Evento existente: DEDUPLICAÇÃO ativa, atualiza contadores e cronologia
            existing = self.active_events[fingerprint]
            existing.last_seen = now
            existing.occurrence_count += 1
            existing.observation_timeline.append({
                "timestamp": now,
                "note": f"Reobservado no ciclo de scan #{existing.occurrence_count}",
            })
            if is_known:
                existing.is_known_good = True
                existing.status = "RESOLVED"
            return None  # Não emite novo evento redundante

        # Novo evento
        event_id = f"SEC-EV-{int(now * 1000)}-{fingerprint[:6]}"
        event = SecurityEvent(
            event_id=event_id,
            fingerprint=fingerprint,
            timestamp=now,
            first_seen=now,
            last_seen=now,
            occurrence_count=1,
            category=category,
            severity=severity,
            confidence=confidence,
            evidence_ids=evidence_ids,
            rationale=rationale,
            recommended_action=recommended_action,
            affected_process=affected_process,
            affected_network_endpoint=affected_network_endpoint,
            status="RESOLVED" if is_known else "OPEN",
            is_known_good=is_known,
            observation_timeline=[{
                "timestamp": now,
                "note": "Primeira deteção durante ciclo de auditoria",
            }],
            model_classification=severity,
        )

        self.active_events[fingerprint] = event
        self.event_history.append(event)
        return event

    def get_open_events(self) -> List[SecurityEvent]:
        """Devolve todos os eventos de segurança em estado aberto ou não resolvido."""
        return [ev for ev in self.active_events.values() if ev.status != "RESOLVED"]

    def get_high_risk_events(self) -> List[SecurityEvent]:
        """Devolve apenas os eventos classificados como HIGH_RISK ou SUSPICIOUS."""
        return [
            ev for ev in self.active_events.values()
            if ev.severity in (SecurityClassification.HIGH_RISK.value, SecurityClassification.SUSPICIOUS.value)
            and not ev.is_known_good
        ]

    def get_event_by_id(self, event_id: str) -> Optional[SecurityEvent]:
        """Localiza um evento por event_id."""
        for ev in self.event_history:
            if ev.event_id == event_id:
                return ev
        for ev in self.active_events.values():
            if ev.event_id == event_id:
                return ev
        return None

    def submit_human_review(
        self,
        event_id: str,
        operator: str,
        final_classification: str,
        reason: str,
    ) -> Optional[HumanIncidentReview]:
        """Aplica revisão humana a um incidente, registando operador, motivo e separando da classificação do modelo."""
        event = self.get_event_by_id(event_id)
        if not event:
            return None

        now = time.time()
        prev_class = event.severity
        is_fp = (
            prev_class in (SecurityClassification.HIGH_RISK.value, SecurityClassification.SUSPICIOUS.value)
            and final_classification in (SecurityClassification.BENIGN.value, "KNOWN_GOOD")
        )

        review = HumanIncidentReview(
            review_id=f"REV-{int(now * 1000)}",
            event_id=event_id,
            operator=operator,
            timestamp=now,
            reason=reason,
            evidence_ids=list(event.evidence_ids),
            previous_classification=prev_class,
            final_classification=final_classification,
            is_false_positive=is_fp,
        )

        event.human_review = review.to_dict()
        event.observation_timeline.append({
            "timestamp": now,
            "note": f"Revisão Humana ({operator}): {final_classification} — {reason}",
        })

        if final_classification in (SecurityClassification.BENIGN.value, "KNOWN_GOOD"):
            event.is_known_good = True
            event.status = "RESOLVED"
            # Registar no cache de known goods por fingerprint
            self.known_goods[event.fingerprint] = KnownGoodItem(
                item_key=event.fingerprint,
                category=event.category,
                accepted_by=operator,
                accepted_at=now,
                reason=reason,
                previous_state={"model_classification": prev_class},
                current_state={"final_classification": final_classification},
            )

        return review
