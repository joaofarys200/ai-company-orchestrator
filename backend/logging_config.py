from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime, timezone
from typing import Any


_SENSITIVE_PATTERNS = [
    (re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*([^\s,;]+)"), r"\1=[REDACTED]"),
    (re.compile(r"(?i)(Bearer\s+)[A-Za-z0-9._\-]+"), r"\1[REDACTED]"),
    (re.compile(r"[A-Za-z]:\\Users\\[^\\\s]+"), r"<user_home>"),
    (re.compile(r"/home/[^/\s]+"), r"/home/<user>"),
]


def sanitize_log_value(value: Any) -> Any:
    if isinstance(value, str):
        sanitized = value
        for pattern, replacement in _SENSITIVE_PATTERNS:
            sanitized = pattern.sub(replacement, sanitized)
        return sanitized
    if isinstance(value, dict):
        return {str(k): sanitize_log_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize_log_value(item) for item in value]
    return value


class StructuredLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        event = getattr(record, "event", record.getMessage())
        details = getattr(record, "details", {})
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "event": sanitize_log_value(event),
        }
        if details:
            payload["details"] = sanitize_log_value(details)
        if record.exc_info:
            payload["exception"] = sanitize_log_value(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False)


def configure_structured_logging() -> None:
    root_logger = logging.getLogger()
    if any(getattr(handler, "_jarvis_structured", False) for handler in root_logger.handlers):
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredLogFormatter())
    handler._jarvis_structured = True
    root_logger.handlers = [handler]
    root_logger.setLevel(logging.INFO)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def log_event(logger: logging.Logger, event: str, level: str = "info", **details: Any) -> None:
    levelno = getattr(logging, level.upper(), logging.INFO)
    logger.log(levelno, event, extra={"event": event, "details": details})
