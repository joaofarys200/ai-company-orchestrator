from __future__ import annotations

import hashlib
import re
from typing import Any


class DataIsolationEnvelope:
    """
    Enforces strict structural isolation for untrusted external data (web search,
    scraped pages, browser DOM, PDF text, external files, tool outputs) to prevent
    indirect prompt injection attacks.
    """

    TAG_NAME = "untrusted_external_data"

    @classmethod
    def wrap(cls, content: str | bytes, source: str = "external_source") -> str:
        """Wraps untrusted content within explicit boundary tags, escaping internal tag attempts."""
        if isinstance(content, bytes):
            text = content.decode("utf-8", errors="replace")
        else:
            text = str(content or "")

        # Compute SHA-256 fingerprint of the original raw data
        raw_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

        # Prevent tag injection / breakout attacks by escaping closing tag occurrences
        escaped_text = re.sub(
            rf"</\s*{cls.TAG_NAME}\s*>",
            f"[ESCAPED_CLOSING_TAG_{raw_hash}]",
            text,
            flags=re.IGNORECASE,
        )

        return (
            f"<{cls.TAG_NAME} source=\"{source}\" fingerprint=\"{raw_hash}\">\n"
            f"{escaped_text}\n"
            f"</{cls.TAG_NAME}>"
        )

    @classmethod
    def unwrap(cls, envelope_text: str) -> str:
        """Extracts content from envelope if present."""
        if not envelope_text:
            return ""
        pattern = rf"<{cls.TAG_NAME}[^>]*>([\s\S]*?)</{cls.TAG_NAME}>"
        match = re.search(pattern, envelope_text)
        if match:
            return match.group(1).strip()
        return envelope_text


__all__ = ["DataIsolationEnvelope"]
