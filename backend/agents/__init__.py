"""Backward-compatible namespace alias mapping `backend.agents.*` to canonical `agents.*`."""

from __future__ import annotations

import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import sys
import types
from pathlib import Path
from typing import Sequence

_CANONICAL_AGENTS_DIR = Path(__file__).resolve().parent.parent.parent / "agents"
__path__ = [str(_CANONICAL_AGENTS_DIR)]


class _BackendAgentsAliasLoader(importlib.abc.Loader):
    def __init__(self, canonical_name: str, canonical_spec: importlib.machinery.ModuleSpec) -> None:
        self._canonical_name = canonical_name
        self._canonical_spec = canonical_spec

    def create_module(self, spec: importlib.machinery.ModuleSpec) -> types.ModuleType:
        module = importlib.import_module(self._canonical_name)
        sys.modules[spec.name] = module
        return module

    def exec_module(self, module: types.ModuleType) -> None:
        # Restore canonical ModuleSpec so `__package__ == __spec__.parent` on relative imports.
        module.__spec__ = self._canonical_spec
        return None


class _BackendAgentsAliasFinder(importlib.abc.MetaPathFinder):
    _PREFIX = "backend.agents."

    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None,
        target: types.ModuleType | None = None,
    ) -> importlib.machinery.ModuleSpec | None:
        if not fullname.startswith(self._PREFIX):
            return None
        canonical_name = "agents." + fullname[len(self._PREFIX) :]
        canonical_spec = importlib.util.find_spec(canonical_name)
        if canonical_spec is None:
            return None
        is_pkg = canonical_spec.submodule_search_locations is not None
        spec = importlib.machinery.ModuleSpec(
            name=fullname,
            loader=_BackendAgentsAliasLoader(canonical_name, canonical_spec),
            origin=canonical_spec.origin,
            is_package=is_pkg,
        )
        if is_pkg:
            spec.submodule_search_locations = list(
                canonical_spec.submodule_search_locations or []
            )
        return spec


if not any(isinstance(f, _BackendAgentsAliasFinder) for f in sys.meta_path):
    sys.meta_path.insert(0, _BackendAgentsAliasFinder())


def __getattr__(name: str) -> object:
    return importlib.import_module(f"agents.{name}")
