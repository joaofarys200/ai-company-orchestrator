import re


_REDACTIONS = [
    (re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*([^\s,;]+)"), r"\1=[REDACTED]"),
    (re.compile(r"(?i)(Bearer\s+)[A-Za-z0-9._\-]+"), r"\1[REDACTED]"),
    (re.compile(r"[A-Za-z]:\\Users\\[^\\\s]+"), r"<user_home>"),
    (re.compile(r"/home/[^/\s]+"), r"/home/<user>"),
]


def sanitize_error_text(error: object) -> str:
    text = str(error or "").strip()
    for pattern, replacement in _REDACTIONS:
        text = pattern.sub(replacement, text)
    return text


def safe_user_error(prefix: str, error: object) -> str:
    sanitized = sanitize_error_text(error)
    if not sanitized:
        return f"{prefix}: erro interno sem detalhes disponiveis."
    return f"{prefix}: {sanitized}"
