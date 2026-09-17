from __future__ import annotations

from typing import Dict, List, Optional, Set

from .index import BaseReverseIndex
from .models import ContractRecord


class ContractReverseIndex(BaseReverseIndex):
    """Reverse index connecting contracts to consumers, providers, and endpoints."""

    def __init__(self) -> None:
        super().__init__("ContractReverseIndex")
        self._contracts: Dict[str, ContractRecord] = {}
        self._contract_consumers: Dict[str, Set[str]] = {}
        self._consumer_contracts: Dict[str, Set[str]] = {}
        self._shard_contracts: Dict[str, Set[str]] = {}

    def add_contract(self, contract: ContractRecord) -> None:
        self._contracts[contract.contract_id] = contract
        self._shard_contracts.setdefault(contract.shard_id, set()).add(contract.contract_id)

        self._contract_consumers[contract.contract_id] = set(contract.consumers)
        for consumer in contract.consumers:
            self._consumer_contracts.setdefault(consumer, set()).add(contract.contract_id)

        self.bump_revision()

    def remove_contract(self, contract_id: str) -> bool:
        contract = self._contracts.pop(contract_id, None)
        if not contract:
            return False

        if contract.shard_id in self._shard_contracts:
            self._shard_contracts[contract.shard_id].discard(contract_id)

        consumers = self._contract_consumers.pop(contract_id, set())
        for c in consumers:
            if c in self._consumer_contracts:
                self._consumer_contracts[c].discard(contract_id)

        self.bump_revision()
        return True

    def get_contract(self, contract_id: str) -> Optional[ContractRecord]:
        return self._contracts.get(contract_id)

    def get_consumers(self, contract_id: str) -> List[str]:
        return sorted(list(self._contract_consumers.get(contract_id, set())))

    def get_contracts_for_consumer(self, consumer_id: str) -> List[str]:
        return sorted(list(self._consumer_contracts.get(consumer_id, set())))

    def get_contracts_by_shard(self, shard_id: str) -> List[ContractRecord]:
        cids = self._shard_contracts.get(shard_id, set())
        return [self._contracts[cid] for cid in cids if cid in self._contracts]

    def clear(self) -> None:
        self._contracts.clear()
        self._contract_consumers.clear()
        self._consumer_contracts.clear()
        self._shard_contracts.clear()
        self.bump_revision()

    def size(self) -> int:
        return len(self._contracts)
