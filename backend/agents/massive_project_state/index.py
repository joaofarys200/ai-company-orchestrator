from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set


class BaseReverseIndex(ABC):
    """Abstract base class for high-performance reverse indexes."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.revision = 1
        self.last_updated = time.time()

    def bump_revision(self) -> int:
        self.revision += 1
        self.last_updated = time.time()
        return self.revision

    @abstractmethod
    def clear(self) -> None:
        pass

    @abstractmethod
    def size(self) -> int:
        pass
