"""
JARVIS OS — Phase 56: Convergence Ledger Index
Unified index and discovery facade for convergence governance components and records.
"""

from __future__ import annotations

from typing import Dict, Any, List, Optional
from agents.repair_convergence_governance.models import (
    ConvergenceCertificate,
    ConvergenceState,
    GovernanceLedgerEntry,
)


class ConvergenceLedgerIndex:
    """Index maintaining queryable references to certificates, transactions, and state histories."""

    def __init__(self):
        self.certificates_by_id: Dict[str, ConvergenceCertificate] = {}
        self.certificates_by_transaction: Dict[str, ConvergenceCertificate] = {}
        self.states_by_transaction: Dict[str, List[ConvergenceState]] = {}

    def index_certificate(self, certificate: ConvergenceCertificate) -> None:
        self.certificates_by_id[certificate.certificate_id] = certificate
        self.certificates_by_transaction[certificate.transaction_id] = certificate

    def get_certificate_by_id(self, cert_id: str) -> Optional[ConvergenceCertificate]:
        return self.certificates_by_id.get(cert_id)

    def get_certificate_by_transaction(self, transaction_id: str) -> Optional[ConvergenceCertificate]:
        return self.certificates_by_transaction.get(transaction_id)

    def record_transaction_state(self, transaction_id: str, state: ConvergenceState) -> None:
        if transaction_id not in self.states_by_transaction:
            self.states_by_transaction[transaction_id] = []
        self.states_by_transaction[transaction_id].append(state)

    def get_transaction_states(self, transaction_id: str) -> List[ConvergenceState]:
        return list(self.states_by_transaction.get(transaction_id, []))
