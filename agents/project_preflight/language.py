"""
JARVIS OS — Phase 53: Universal Project Preflight & Runtime Failure Auto-Recovery
Language, Runtime Constants, and Global Symbol Registries.
"""

from __future__ import annotations

from typing import Dict, List, Set

from agents.project_preflight.models import LanguageType, RuntimeType

# Node.js built-in globals and modules that are legitimate without import
NODE_LEGITIMATE_GLOBALS: Set[str] = {
    "require", "module", "exports", "__dirname", "__filename", "process",
    "global", "console", "setTimeout", "clearTimeout", "setInterval", "clearInterval",
    "setImmediate", "clearImmediate", "Buffer", "URL", "URLSearchParams",
    "TextEncoder", "TextDecoder", "AbortController", "AbortSignal", "fetch",
    "Promise", "Object", "Array", "String", "Number", "Boolean", "Function",
    "Symbol", "BigInt", "Math", "Date", "RegExp", "Error", "TypeError",
    "RangeError", "SyntaxError", "ReferenceError", "JSON", "Map", "Set",
    "WeakMap", "WeakSet", "ArrayBuffer", "DataView",
}

# Browser standard globals for frontend / static projects
BROWSER_LEGITIMATE_GLOBALS: Set[str] = {
    "window", "document", "navigator", "location", "history", "localStorage",
    "sessionStorage", "alert", "prompt", "confirm", "addEventListener",
    "removeEventListener", "HTMLElement", "Element", "Node", "Event",
    "CustomEvent", "MouseEvent", "KeyboardEvent", "XMLHttpRequest", "fetch",
    "FormData", "Blob", "File", "FileReader", "Image", "Audio",
}

# Python built-in functions and constants
PYTHON_LEGITIMATE_BUILTINS: Set[str] = {
    "abs", "all", "any", "ascii", "bin", "bool", "breakpoint", "bytearray",
    "bytes", "callable", "chr", "classmethod", "compile", "complex", "delattr",
    "dict", "dir", "divmod", "enumerate", "eval", "exec", "filter", "float",
    "format", "frozenset", "getattr", "globals", "hasattr", "hash", "help",
    "hex", "id", "input", "int", "isinstance", "issubclass", "iter", "len",
    "list", "locals", "map", "max", "memoryview", "min", "next", "object",
    "oct", "open", "ord", "pow", "print", "property", "range", "repr",
    "reversed", "round", "set", "setattr", "slice", "sorted", "staticmethod",
    "str", "sum", "super", "tuple", "type", "vars", "zip", "__import__",
    "True", "False", "None", "Exception", "ValueError", "TypeError",
    "KeyError", "IndexError", "FileNotFoundError", "RuntimeError",
}

# Supported vs Planned languages
SUPPORTED_LANGUAGES: Dict[str, bool] = {
    LanguageType.JAVASCRIPT.value: True,
    LanguageType.TYPESCRIPT.value: True,
    LanguageType.PYTHON.value: True,
    LanguageType.HTML_JS.value: True,
    "GO": False,      # Architecture ready, execution disabled
    "RUST": False,    # Architecture ready, execution disabled
    "JAVA": False,    # Architecture ready, execution disabled
}


def is_supported_language(lang: str) -> bool:
    return SUPPORTED_LANGUAGES.get(lang.upper(), False)
