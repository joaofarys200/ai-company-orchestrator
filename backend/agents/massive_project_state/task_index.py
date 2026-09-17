from __future__ import annotations

from typing import Dict, List, Optional, Set

from .index import BaseReverseIndex
from .models import TaskRecord


class TaskReverseIndex(BaseReverseIndex):
    """Reverse index linking tasks to affected files and contracts."""

    def __init__(self) -> None:
        super().__init__("TaskReverseIndex")
        self._tasks: Dict[str, TaskRecord] = {}
        self._file_tasks: Dict[str, Set[str]] = {}
        self._contract_tasks: Dict[str, Set[str]] = {}

    def add_task(self, task: TaskRecord) -> None:
        self._tasks[task.task_id] = task

        for f in task.affected_files:
            self._file_tasks.setdefault(f, set()).add(task.task_id)

        for c in task.contracts:
            self._contract_tasks.setdefault(c, set()).add(task.task_id)

        self.bump_revision()

    def remove_task(self, task_id: str) -> bool:
        task = self._tasks.pop(task_id, None)
        if not task:
            return False

        for f in task.affected_files:
            if f in self._file_tasks:
                self._file_tasks[f].discard(task_id)

        for c in task.contracts:
            if c in self._contract_tasks:
                self._contract_tasks[c].discard(task_id)

        self.bump_revision()
        return True

    def get_task(self, task_id: str) -> Optional[TaskRecord]:
        return self._tasks.get(task_id)

    def get_tasks_for_file(self, file_path: str) -> List[str]:
        return sorted(list(self._file_tasks.get(file_path, set())))

    def get_tasks_for_contract(self, contract_id: str) -> List[str]:
        return sorted(list(self._contract_tasks.get(contract_id, set())))

    def list_tasks(self) -> List[TaskRecord]:
        return list(self._tasks.values())

    def clear(self) -> None:
        self._tasks.clear()
        self._file_tasks.clear()
        self._contract_tasks.clear()
        self.bump_revision()

    def size(self) -> int:
        return len(self._tasks)
