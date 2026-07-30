from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ApplicationRuntimeState:
    """Mutable process state shared across composed runtime services."""

    conversation_history: list[dict[str, str]] = field(
        default_factory=list
    )
    main_loop: Any = None
