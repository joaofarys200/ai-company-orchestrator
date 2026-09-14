"""
JARVIS OS — Phase 50: Behavioral Contract Preservation & Migration Proof
Deterministic Runtime Trace Normalization and Secret Redaction.
"""

from __future__ import annotations

import copy
import re
from typing import Any, Dict, List, Set, Union


# Regex patterns for volatile or sensitive data
UUID_REGEX = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
ISO_TIMESTAMP_REGEX = re.compile(
    r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?$"
)
MEMORY_ADDR_REGEX = re.compile(r"0x[0-9a-fA-F]{6,16}")
BEARER_TOKEN_REGEX = re.compile(r"^Bearer\s+[A-Za-z0-9\-\._~\+\/]+=*$", re.IGNORECASE)

SENSITIVE_KEY_PATTERNS: Set[str] = {
    "password",
    "passphrase",
    "secret",
    "token",
    "api_key",
    "apikey",
    "auth_token",
    "access_token",
    "refresh_token",
    "private_key",
    "authorization",
    "credit_card",
    "card_number",
    "cvv",
    "ssn",
}

VOLATILE_ID_KEYS: Set[str] = {
    "request_id",
    "req_id",
    "trace_id",
    "span_id",
    "correlation_id",
    "session_id",
    "nonce",
}

VOLATILE_TIME_KEYS: Set[str] = {
    "timestamp",
    "created_at",
    "updated_at",
    "expires_at",
    "issued_at",
    "started_at",
    "completed_at",
    "time",
    "now",
}


class RuntimeTraceNormalizer:
    """
    Normalizes traces and payloads for deterministic behavioral comparison.
    Ensures zero leakage of credentials, tokens, or random system variables.
    """

    @classmethod
    def normalize_payload(cls, data: Any) -> Any:
        """Recursively normalizes dictionaries, lists, and primitives."""
        if data is None:
            return None

        if isinstance(data, dict):
            normalized_dict = {}
            for k, v in sorted(data.items(), key=lambda item: str(item[0])):
                key_lower = str(k).lower()

                # 1. Redact Secrets
                if any(sens in key_lower for sens in SENSITIVE_KEY_PATTERNS):
                    normalized_dict[k] = "<REDACTED_SECRET>"
                    continue

                # 2. Canonicalize Volatile IDs
                if any(vol_id == key_lower or vol_id in key_lower for vol_id in VOLATILE_ID_KEYS):
                    normalized_dict[k] = "<CANONICAL_ID>"
                    continue

                # 3. Canonicalize Volatile Timestamps
                if any(vol_time == key_lower for vol_time in VOLATILE_TIME_KEYS):
                    normalized_dict[k] = "<CANONICAL_TIMESTAMP>"
                    continue

                # 4. Recurse into values
                normalized_dict[k] = cls.normalize_payload(v)
            return normalized_dict

        elif isinstance(data, (list, tuple, set)):
            return [cls.normalize_payload(item) for item in data]

        elif isinstance(data, str):
            # Check string content for tokens, UUIDs, ISO timestamps, memory addresses
            if BEARER_TOKEN_REGEX.match(data.strip()):
                return "<REDACTED_BEARER_TOKEN>"
            if UUID_REGEX.match(data.strip()):
                return "<CANONICAL_UUID>"
            if ISO_TIMESTAMP_REGEX.match(data.strip()):
                return "<CANONICAL_TIMESTAMP>"
            if MEMORY_ADDR_REGEX.search(data):
                return MEMORY_ADDR_REGEX.sub("<CANONICAL_ADDR>", data)
            return data

        elif isinstance(data, float):
            # If large float looks like an epoch timestamp (> 1e9)
            if data > 1_000_000_000.0:
                return "<CANONICAL_TIMESTAMP>"
            return round(data, 4)

        return data

    @classmethod
    def normalize_trace(cls, trace_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalizes a full trace dictionary."""
        trace_copy = copy.deepcopy(trace_data)

        # Normalize payloads
        if "input_payload" in trace_copy:
            trace_copy["input_payload"] = cls.normalize_payload(trace_copy["input_payload"])
        if "output_payload" in trace_copy:
            trace_copy["output_payload"] = cls.normalize_payload(trace_copy["output_payload"])

        # Normalize side effects, events, and economic effects
        if "side_effects" in trace_copy and isinstance(trace_copy["side_effects"], list):
            trace_copy["side_effects"] = [cls.normalize_payload(se) for se in trace_copy["side_effects"]]
        if "events" in trace_copy and isinstance(trace_copy["events"], list):
            trace_copy["events"] = [cls.normalize_payload(ev) for ev in trace_copy["events"]]
        if "economic_effects" in trace_copy and isinstance(trace_copy["economic_effects"], list):
            trace_copy["economic_effects"] = [cls.normalize_payload(ee) for ee in trace_copy["economic_effects"]]
        if "authorization_state" in trace_copy and isinstance(trace_copy["authorization_state"], dict):
            trace_copy["authorization_state"] = cls.normalize_payload(trace_copy["authorization_state"])

        # Override volatile top-level metadata
        trace_copy["timestamp"] = "<CANONICAL_TIMESTAMP>"
        if "trace_id" in trace_copy:
            trace_copy["trace_id"] = "<CANONICAL_TRACE_ID>"
        if "parent_trace_hash" in trace_copy:
            trace_copy["parent_trace_hash"] = "<CANONICAL_PARENT_HASH>"

        return trace_copy
