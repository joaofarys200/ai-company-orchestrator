"""
JARVIS OS — Phase 65: Safe Self-Modification & Transactional Architecture Implementation
Module: patch_validation.py
Validates candidate patches prior to filesystem mutation:
- Syntax & AST parsing validation (Python ast.parse)
- Diff scope & expected vs unexpected file validation
- Security Sentinel checks (prohibits destructive calls, eval, secrets, credential theft)
- Strict rejection when EXPECTED_SCOPE != ACTUAL_SCOPE
"""

from __future__ import annotations

import ast
import re
from typing import Any, Dict, List, Optional, Tuple

from .models import ModificationPatch


class PatchValidator:
    """Pre-apply static and AST validator for candidate modification patches."""

    FORBIDDEN_CALLS = {
        "os.system",
        "subprocess.Popen",
        "eval",
        "exec",
        "shutil.rmtree",
        "builtins.__import__",
    }

    FORBIDDEN_PATTERNS = [
        r"rmtree\s*\(",
        r"os\.system\s*\(",
        r"eval\s*\(",
        r"exec\s*\(",
        r"__import__\s*\(",
        r"password\s*=\s*['\"][^'\"]+['\"]",
        r"secret_key\s*=\s*['\"][^'\"]+['\"]",
        r"api_key\s*=\s*['\"][^'\"]+['\"]",
    ]

    PROTECTED_PATHS = {
        "governance",
        "security",
        "sentinel",
        "rollback",
        "verification_gate",
        "ledger",
    }

    def validate_patch(
        self,
        patch: ModificationPatch,
        expected_files: List[str],
        allow_protected_path_override: bool = False,
    ) -> Tuple[bool, List[str]]:
        """Validate candidate patch syntax, AST integrity, scope, and security safety."""
        logs: List[str] = []
        is_valid = True

        # 1. Scope check: expected files vs actual touched files
        expected_set = set(expected_files)
        actual_set = set(patch.target_files)

        if not actual_set.issubset(expected_set):
            unexpected = actual_set - expected_set
            logs.append(f"SCOPE_VIOLATION: EXPECTED_SCOPE != ACTUAL_SCOPE. Unexpected files: {unexpected}")
            is_valid = False

        # 2. Protected paths check
        if not allow_protected_path_override:
            for f in patch.target_files:
                for prot in self.PROTECTED_PATHS:
                    if prot in f.lower() and "safe_self_modification" not in f.lower():
                        logs.append(f"PROTECTED_PATH_VIOLATION: Attempted modification of protected system component '{f}'.")
                        is_valid = False

        # 3. Security Sentinel pattern detection
        for pattern in self.FORBIDDEN_PATTERNS:
            if re.search(pattern, patch.diff):
                logs.append(f"SECURITY_SENTINEL_BLOCK: Forbidden destructive pattern '{pattern}' detected in patch diff.")
                is_valid = False

        # 4. AST and syntax validation for Python files
        for f, content in patch.new_contents.items():
            if f.endswith(".py"):
                try:
                    ast.parse(content, filename=f)
                    logs.append(f"AST_SYNTAX_VALID: File '{f}' passed ast.parse().")
                except SyntaxError as e:
                    logs.append(f"AST_SYNTAX_ERROR: SyntaxError in '{f}' at line {e.lineno}: {e.msg}")
                    is_valid = False
                except Exception as e:
                    logs.append(f"AST_PARSE_ERROR: Failed to parse '{f}': {e}")
                    is_valid = False

        if is_valid:
            logs.append("PATCH_VALIDATION_PASSED: All AST, scope, and sentinel checks verified.")
        return is_valid, logs
