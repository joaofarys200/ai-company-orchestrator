from __future__ import annotations

import asyncio
import os
import re
import shutil
import subprocess
import unicodedata


LOCAL_APP_ACTION_WORDS = {
    "abre",
    "abrir",
    "abram",
    "inicia",
    "iniciar",
    "executa",
    "executar",
    "corre",
    "correr",
    "lanca",
    "lancar",
    "arranca",
    "arrancar",
    "open",
    "start",
    "run",
}
LOCAL_APP_OPEN_ACTION_WORDS = {
    "abre",
    "abrir",
    "abram",
    "inicia",
    "iniciar",
    "lanca",
    "lancar",
    "arranca",
    "arrancar",
    "open",
    "start",
}
LOCAL_APP_FILLER_WORDS = {
    "o",
    "a",
    "os",
    "as",
    "um",
    "uma",
    "uns",
    "umas",
    "de",
    "do",
    "da",
    "dos",
    "das",
    "no",
    "na",
    "nos",
    "nas",
    "por",
    "favor",
    "pf",
    "sff",
    "novamente",
    "outra",
    "vez",
    "app",
    "aplicacao",
    "programa",
}
LOCAL_APP_TARGETS = [
    {
        "id": "excel",
        "label": "Excel",
        "terms": [
            "excel",
            "microsoft excel",
            "folha de calculo",
            "folha calculo",
            "spreadsheet",
        ],
        "command": "Start-Process -FilePath excel.exe",
    },
    {
        "id": "word",
        "label": "Word",
        "terms": ["word", "microsoft word"],
        "command": "Start-Process -FilePath winword.exe",
    },
    {
        "id": "powerpoint",
        "label": "PowerPoint",
        "terms": [
            "powerpoint",
            "power point",
            "microsoft powerpoint",
        ],
        "command": "Start-Process -FilePath powerpnt.exe",
    },
    {
        "id": "outlook",
        "label": "Outlook",
        "terms": ["outlook", "microsoft outlook"],
        "command": "Start-Process -FilePath outlook.exe",
    },
    {
        "id": "notepad",
        "label": "Bloco de Notas",
        "terms": ["notepad", "bloco de notas", "bloco notas"],
        "command": "Start-Process -FilePath notepad.exe",
    },
    {
        "id": "calculator",
        "label": "Calculadora",
        "terms": ["calculadora", "calculator", "calc"],
        "command": "Start-Process -FilePath calc.exe",
    },
    {
        "id": "paint",
        "label": "Paint",
        "terms": ["paint", "mspaint"],
        "command": "Start-Process -FilePath mspaint.exe",
    },
    {
        "id": "explorer",
        "label": "Explorador de Ficheiros",
        "terms": [
            "explorador",
            "explorer",
            "ficheiros",
            "file explorer",
        ],
        "command": "Start-Process -FilePath explorer.exe",
    },
    {
        "id": "chrome",
        "label": "Chrome",
        "terms": ["chrome", "google chrome"],
        "command": "Start-Process -FilePath chrome.exe",
    },
    {
        "id": "edge",
        "label": "Edge",
        "terms": ["edge", "microsoft edge"],
        "command": "Start-Process -FilePath msedge.exe",
    },
    {
        "id": "powershell",
        "label": "PowerShell",
        "terms": ["powershell", "power shell"],
        "command": "Start-Process -FilePath powershell.exe",
    },
    {
        "id": "cmd",
        "label": "Command Prompt",
        "terms": [
            "cmd",
            "command prompt",
            "linha de comandos",
        ],
        "command": "Start-Process -FilePath cmd.exe",
    },
    {
        "id": "vscode",
        "label": "Visual Studio Code",
        "terms": ["visual studio code", "vs code", "vscode"],
        "command": "Start-Process -FilePath code",
    },
]


def normalize_voice_command_text(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text or "")
    without_accents = "".join(
        character
        for character in decomposed
        if unicodedata.category(character) != "Mn"
    )
    lowered = without_accents.lower()
    lowered = re.sub(r"[^a-z0-9\s]", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def normalized_phrase_in_text(text: str, phrase: str) -> bool:
    normalized_phrase = normalize_voice_command_text(phrase)
    if not normalized_phrase:
        return False
    return (
        f" {normalized_phrase} "
        in f" {text} "
    )


def extract_local_app_query(prompt: str) -> str:
    normalized = normalize_voice_command_text(prompt)
    if not normalized:
        return ""
    words = normalized.split()
    action_index = next(
        (
            index
            for index, word in enumerate(words)
            if word in LOCAL_APP_ACTION_WORDS
        ),
        -1,
    )
    if action_index < 0:
        return ""
    target_words = words[action_index + 1 :]
    while (
        target_words
        and target_words[0] in LOCAL_APP_FILLER_WORDS
    ):
        target_words.pop(0)
    while (
        target_words
        and target_words[-1] in LOCAL_APP_FILLER_WORDS
    ):
        target_words.pop()
    return " ".join(target_words).strip()


def local_app_start_menu_roots() -> list[str]:
    roots = []
    program_data = os.getenv("PROGRAMDATA")
    app_data = os.getenv("APPDATA")
    if program_data:
        roots.append(
            os.path.join(
                program_data,
                "Microsoft",
                "Windows",
                "Start Menu",
                "Programs",
            )
        )
    if app_data:
        roots.append(
            os.path.join(
                app_data,
                "Microsoft",
                "Windows",
                "Start Menu",
                "Programs",
            )
        )
    return roots


def find_start_menu_shortcut(query: str):
    normalized_query = normalize_voice_command_text(query)
    if not normalized_query:
        return None
    query_words = normalized_query.split()
    best_match = None
    best_score = 0
    for root in local_app_start_menu_roots():
        if not os.path.isdir(root):
            continue
        for current_root, _, filenames in os.walk(root):
            for filename in filenames:
                if not filename.lower().endswith(
                    (".lnk", ".url")
                ):
                    continue
                label = os.path.splitext(filename)[0]
                normalized_label = (
                    normalize_voice_command_text(label)
                )
                score = 0
                if normalized_label == normalized_query:
                    score = 100
                elif normalized_label.startswith(normalized_query):
                    score = 85
                elif normalized_phrase_in_text(
                    normalized_label,
                    normalized_query,
                ):
                    score = 75
                elif all(
                    word in normalized_label
                    for word in query_words
                ):
                    score = 60 + len(query_words)
                if score > best_score:
                    best_score = score
                    best_match = {
                        "label": label,
                        "path": os.path.join(
                            current_root,
                            filename,
                        ),
                    }
    if best_score < 60:
        return None
    return best_match


def find_path_executable(query: str):
    normalized_query = normalize_voice_command_text(
        query
    ).replace(" ", "")
    if not re.fullmatch(
        r"[a-z0-9_.-]{2,64}",
        normalized_query or "",
    ):
        return None
    for candidate in (
        normalized_query,
        f"{normalized_query}.exe",
        f"{normalized_query}.cmd",
    ):
        found = shutil.which(candidate)
        if found:
            return {"label": query.strip(), "path": found}
    return None


def quote_powershell_single(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def find_local_app_request(prompt: str):
    normalized = normalize_voice_command_text(prompt)
    if not normalized:
        return None
    words = normalized.split()
    action_words = {
        word
        for word in words
        if word in LOCAL_APP_ACTION_WORDS
    }
    if not action_words:
        return None
    for app in LOCAL_APP_TARGETS:
        if any(
            normalized_phrase_in_text(normalized, term)
            for term in app["terms"]
        ):
            return app
    query = extract_local_app_query(prompt)
    if not query:
        return None
    shortcut = find_start_menu_shortcut(query)
    if shortcut:
        return {
            "id": "start_menu_shortcut",
            "label": shortcut["label"],
            "path": shortcut["path"],
            "source": "start_menu",
        }
    if action_words & LOCAL_APP_OPEN_ACTION_WORDS:
        executable = find_path_executable(query)
        if executable:
            return {
                "id": "path_executable",
                "label": executable["label"],
                "path": executable["path"],
                "source": "path",
            }
    return None


async def open_local_application(
    app_request: dict,
    *,
    working_directory: str,
) -> tuple[bool, str]:
    if "command" in app_request:
        command = app_request["command"]
    elif "path" in app_request:
        command = (
            "Start-Process -FilePath "
            f"{quote_powershell_single(app_request['path'])}"
        )
    else:
        return False, "Aplicacao local nao resolvida."
    loop = asyncio.get_running_loop()

    def run_command() -> tuple[bool, str]:
        try:
            process = subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    command,
                ],
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=10,
                cwd=working_directory,
            )
            output = "\n".join(
                part
                for part in (process.stdout, process.stderr)
                if part
            ).strip()
            if process.returncode == 0:
                return True, output
            return (
                False,
                output
                or (
                    "PowerShell terminou com codigo "
                    f"{process.returncode}."
                ),
            )
        except subprocess.TimeoutExpired:
            return (
                False,
                "O comando excedeu o tempo limite ao tentar "
                "abrir a aplicacao.",
            )
        except Exception as command_error:
            return False, str(command_error)

    return await loop.run_in_executor(None, run_command)
