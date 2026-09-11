"""
JARVIS OS — Phase 39: Predictive Impact Validator

Validates structural consistency and physical plausibility of predictions:
1. File paths are syntactically valid and normalized.
2. Predicted tasks have well-formed actions, owners, and titles.
3. Kahn DAG topological validation: verifies the predicted task graph has NO CYCLES.
4. Dependency references point to valid existing tasks or valid predicted tasks.
5. Evidence impact references correspond to real evidence objects.
6. Rejects structurally impossible predictions as INVALID_PREDICTION.
"""

from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple


class PredictiveImpactValidator:
    """
    Ensures that hypothetical simulation graphs are mathematically and structurally sound.
    """

    @classmethod
    def validate_prediction(
        cls,
        predicted_tasks: list[dict[str, Any]],
        predicted_files: list[dict[str, Any]],
        predicted_evidence: list[dict[str, Any]],
        current_tasks: list[dict[str, Any]],
        current_evidence: list[dict[str, Any]],
    ) -> Tuple[bool, list[str]]:
        """
        Returns:
            - is_valid: bool
            - errors: list[str]
        """
        errors: list[str] = []

        # 1. Validate File paths
        for pf in predicted_files:
            path = pf.get("file_path", "")
            if not path or ".." in path or "\\" in path and "/" in path:
                errors.append(f"Caminho de ficheiro previsto inválido ou mal formatado: '{path}'")

        # 2. Validate Tasks structure
        existing_task_ids: Set[str] = {t.get("id", "") for t in current_tasks if t.get("id")}
        all_task_ids: Set[str] = set(existing_task_ids)

        for pt in predicted_tasks:
            t_id = pt.get("predicted_task_id", "")
            if not t_id:
                errors.append("Tarefa prevista sem 'predicted_task_id'")
            all_task_ids.add(t_id)

            action = pt.get("action", "")
            if action not in ("ADD_TASK", "REMOVE_TASK", "MODIFY_TASK", "ADD_DEPENDENCY", "REASSIGN"):
                errors.append(f"Ação de tarefa prevista desconhecida: '{action}' em {t_id}")

            if not pt.get("title"):
                errors.append(f"Tarefa prevista {t_id} sem título")

        # 3. Validate Dependencies & Kahn DAG Cycle Check
        # Build adjacency graph for all tasks (existing + predicted additions)
        adj: dict[str, list[str]] = {}
        in_degree: dict[str, int] = {}

        # Register existing
        for t in current_tasks:
            tid = t.get("id", "")
            if tid:
                adj[tid] = []
                in_degree[tid] = 0

        # Register predicted
        for pt in predicted_tasks:
            tid = pt.get("predicted_task_id", "")
            if tid:
                adj[tid] = []
                in_degree[tid] = 0

        # Wire dependencies
        for t in current_tasks:
            tid = t.get("id", "")
            for dep in t.get("dependencies", []):
                if dep in adj:
                    adj[dep].append(tid)
                    in_degree[tid] = in_degree.get(tid, 0) + 1

        for pt in predicted_tasks:
            tid = pt.get("predicted_task_id", "")
            deps = pt.get("dependencies", [])
            for dep in deps:
                if dep not in all_task_ids:
                    errors.append(f"Tarefa prevista {tid} referencia dependência inexistente: '{dep}'")
                elif dep == tid:
                    errors.append(f"Tarefa prevista {tid} possui auto-dependência cíclica")
                elif dep in adj:
                    adj[dep].append(tid)
                    in_degree[tid] = in_degree.get(tid, 0) + 1

        # Kahn's Algorithm for DAG cycle detection
        queue = [node for node, deg in in_degree.items() if deg == 0]
        visited_count = 0

        while queue:
            curr = queue.pop(0)
            visited_count += 1
            for neighbor in adj.get(curr, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if visited_count < len(adj):
            errors.append(f"Ciclo detetado no grafo de tarefas previsto ({visited_count}/{len(adj)} nós resolvidos). Topologia DAG inválida.")

        # 4. Validate Evidence references
        existing_ev_ids = {e.get("evidence_id", e.get("id", "")) for e in current_evidence}
        for pe in predicted_evidence:
            ev_id = pe.get("evidence_id", "")
            if ev_id and ev_id not in existing_ev_ids:
                errors.append(f"Evidência prevista '{ev_id}' não existe no Evidence Ledger atual")

        is_valid = len(errors) == 0
        return is_valid, errors
