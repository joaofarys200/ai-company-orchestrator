from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional, Set

from .index_manager import IndexManager
from .models import ChangePlan, ImpactScope, TargetedSubgraph
from .subgraph import TargetedSubgraphExtractor


class RepositoryChangePlanner:
    """Plans repository-wide changes causally across services and layers using targeted subgraphs."""

    def __init__(self, index_manager: IndexManager, extractor: TargetedSubgraphExtractor) -> None:
        self.indexes = index_manager
        self.extractor = extractor

    def plan_change(
        self,
        objective: str,
        changed_files: List[str],
        changed_contracts: Optional[List[str]] = None,
        risk: str = "LOW",
    ) -> ChangePlan:
        plan_id = f"plan_{uuid.uuid4().hex[:8]}"

        # Step 1: Identify root symbols from changed files
        root_symbols: List[str] = []
        for fp in changed_files:
            file_rec = self.indexes.files.get_file(fp)
            if file_rec:
                root_symbols.extend(file_rec.symbols)

        if not root_symbols and changed_files:
            # Fallback symbol names if files are not yet fully indexed
            for fp in changed_files:
                base = fp.split("/")[-1].split(".")[0]
                root_symbols.append(f"sym_{base}")

        # Step 2: Extract targeted subgraph
        subgraph: TargetedSubgraph = self.extractor.extract_subgraph(
            root_symbols=root_symbols,
            max_depth=3,
            max_nodes=150,
        )

        all_contracts = sorted(list(set((changed_contracts or []) + subgraph.contracts)))
        all_affected_symbols = sorted(list(set(root_symbols + subgraph.downstream_symbols)))

        # Step 3: Identify affected services
        affected_services = set()
        for fp in changed_files:
            f = self.indexes.files.get_file(fp)
            if f:
                affected_services.add(f.shard_id)
        for sid in all_affected_symbols:
            sym = self.indexes.symbols.get_symbol(sid)
            if sym:
                affected_services.add(sym.shard_id)

        # Step 4: Classify blast radius
        if len(affected_services) > 3 or "shared" in affected_services:
            scope = ImpactScope.REPOSITORY_WIDE
        elif len(affected_services) > 1:
            scope = ImpactScope.CROSS_SERVICE
        elif len(all_affected_symbols) > 5 or len(changed_files) > 2:
            scope = ImpactScope.REGIONAL
        else:
            scope = ImpactScope.LOCAL

        # Step 5: Construct causal test and validation requirements
        required_tests: List[str] = []
        required_validation: List[str] = [
            "validate_code_syntax",
            "validate_contract_compatibility",
        ]

        for s in affected_services:
            required_tests.append(f"test_service_{s}")

        if all_contracts:
            required_validation.append("validate_contract_drift")
            required_tests.append("test_contract_conformance")

        browser_scenarios = list(subgraph.browser_scenarios)
        if "frontend" in affected_services and not browser_scenarios:
            browser_scenarios.append("qa_user_interface_flow")

        if browser_scenarios:
            required_validation.append("validate_browser_scenarios")

        # Step 6: Map affected tasks
        affected_tasks: Set[str] = set(subgraph.tasks)
        for fp in changed_files:
            affected_tasks.update(self.indexes.tasks.get_tasks_for_file(fp))

        return ChangePlan(
            plan_id=plan_id,
            objective=objective,
            scope=scope,
            changed_files=changed_files,
            affected_symbols=all_affected_symbols,
            affected_tasks=sorted(list(affected_tasks)),
            affected_contracts=all_contracts,
            affected_consumers=subgraph.direct_consumers,
            affected_services=sorted(list(affected_services)),
            required_tests=required_tests,
            browser_scenarios=browser_scenarios,
            predicted_risk=risk if scope in (ImpactScope.LOCAL, ImpactScope.REGIONAL) else "HIGH",
            required_validation=required_validation,
            subgraph_id=subgraph.subgraph_id,
            provenance={
                "subgraph_extraction_ms": round(subgraph.extraction_time_ms, 2),
                "nodes_count": len(subgraph.nodes),
                "edges_count": len(subgraph.edges),
            },
        )
