from __future__ import annotations

import re

def is_safe_workspace_relative_path(path_value: str | None) -> bool:
    value = str(path_value or "").strip().replace("\\", "/")
    if not value:
        return True
    if value.startswith("/") or re.match(r"^[a-zA-Z]:", value):
        return False
    parts = [part for part in value.split("/") if part]
    return ".." not in parts

def normalize_workspace_path_alias(path_value: str | None) -> str:
    value = str(path_value or "").strip().replace("\\", "/")
    aliases = {
        "/workspace": ".",
        "/sandbox": "sandbox_dir",
        "/sandbox_dir": "sandbox_dir",
        "/workspace/sandbox": "sandbox_dir",
        "/workspace/sandbox_dir": "sandbox_dir",
        "workspace/sandbox": "sandbox_dir",
        "workspace/sandbox_dir": "sandbox_dir",
    }
    if value in aliases:
        return aliases[value]
    if value.startswith("sandbox_dir/sandbox_dir/"):
        return "sandbox_dir/" + value[len("sandbox_dir/sandbox_dir/"):]
    for prefix, replacement in aliases.items():
        if value.startswith(prefix + "/"):
            return replacement + value[len(prefix):]
    return value

def extract_requested_file_paths(prompt: str) -> list[str]:
    text = str(prompt or "").replace("\\", "/")
    path_pattern = re.compile(
        r"(?:(?:/workspace/)?sandbox(?:_dir)?|workspace/sandbox(?:_dir)?|sandbox_dir)/[^\s,;:'\")]+",
        flags=re.IGNORECASE,
    )
    file_name_pattern = re.compile(
        r"\b[\w.-]+\.(?:html|css|js|jsx|tsx|py|json|md|txt|css|ts|sh|bat)\b",
        flags=re.IGNORECASE,
    )
    paths: list[str] = []
    directories: list[str] = []
    for match in path_pattern.findall(text):
        cleaned = normalize_workspace_path_alias(match.rstrip(".,;:!?)]}"))
        leaf = cleaned.rsplit("/", 1)[-1]
        if "." in leaf:
            paths.append(cleaned)
        else:
            directories.append(cleaned.rstrip("/"))

    explicit_leafs = {path.rsplit("/", 1)[-1].lower() for path in paths}
    if directories:
        base_dir = directories[-1]
        for filename in file_name_pattern.findall(text):
            if filename.lower() in explicit_leafs:
                continue
            paths.append(f"{base_dir}/{filename}")

    return list(dict.fromkeys(paths))

def normalize_execution_command(command: str) -> str:
    raw = str(command or "").strip()
    if not raw:
        return raw
    lowered = raw.lower()
    sandbox_probe = "Get-ChildItem -Force -LiteralPath sandbox_dir"
    if ("python -m http.server" in lowered or "http-server" in lowered) and any(alias in lowered for alias in ["/sandbox", "sandbox_dir"]):
        return sandbox_probe
    if re.search(r"\bls\s+-la\b", lowered):
        if any(alias in lowered for alias in ["/sandbox", "sandbox_dir"]):
            return sandbox_probe
        return "Get-ChildItem -Force"
    normalized = raw.replace("/workspace/sandbox_dir", "sandbox_dir")
    normalized = normalized.replace("/workspace/sandbox", "sandbox_dir")
    normalized = normalized.replace("/sandbox_dir", "sandbox_dir")
    normalized = normalized.replace("/sandbox", "sandbox_dir")
    normalized = normalized.replace("/workspace", ".")
    cd_match = re.match(r"^\s*cd\s+([^&;]+)\s*&&\s*(.+)$", normalized, flags=re.IGNORECASE)
    if cd_match:
        path_part = normalize_workspace_path_alias(cd_match.group(1).strip().strip("'\""))
        rest = cd_match.group(2).strip()
        return f"Set-Location -LiteralPath {path_part}; {rest}"
    return normalized

def normalize_tool_input_paths(tool_name: str, tool_input: dict | None) -> dict:
    normalized = dict(tool_input or {})
    if tool_name in {"write_file", "read_file"} and "filename" not in normalized and "path" in normalized:
        normalized["filename"] = normalized.get("path")
    if tool_name == "write_file" and "content" not in normalized:
        for alias in ("file_text", "text", "body", "html", "code"):
            if alias in normalized:
                normalized["content"] = normalized.get(alias)
                break
    if tool_name in {"write_file", "read_file"} and "filename" in normalized:
        normalized["filename"] = normalize_workspace_path_alias(normalized.get("filename"))
    if tool_name == "list_directory" and "path" in normalized:
        normalized["path"] = normalize_workspace_path_alias(normalized.get("path"))
    if tool_name == "execute_command" and "command" in normalized:
        normalized["command"] = normalize_execution_command(normalized.get("command"))
    return normalized
