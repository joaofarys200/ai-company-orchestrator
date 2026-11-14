"""Stages a self-contained portable Python runtime and JARVIS OS worker modules
into `src-tauri/py-runtime/runtime-bundle.zip` for Tauri MSI and NSIS installers.

The resulting archive allows `jarvis-os.exe` to spawn and supervise `ai`, `study`,
`mission`, and `voice` sidecar workers on a clean Windows installation without
requiring a user-installed Python interpreter or repository checkout.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import zipfile

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "src-tauri" / "py-runtime"
BUNDLE_ZIP_PATH = OUTPUT_DIR / "runtime-bundle.zip"
MANIFEST_PATH = OUTPUT_DIR / "manifest.json"

APP_PACKAGES: tuple[str, ...] = (
    "workers",
    "backend",
    "agents",
    "intelligence",
    "persistence",
    "security",
    "services",
    "schemas",
    "config",
)

APP_ROOT_MODULES: tuple[str, ...] = (
    "database.py",
    "gemini_live.py",
    "sandbox.py",
    "voice_service.py",
    "websocket_schema.py",
    "workspace_policy.py",
)

APP_SCRIPT_FILES: tuple[str, ...] = (
    "scripts/model_harness_benchmark.py",
    "scripts/model_harness_stateful_benchmark.py",
    "scripts/ts_ast_parser.js",
)

EXCLUDED_STDLIB_DIRS: frozenset[str] = frozenset(
    {
        "__pycache__",
        "site-packages",
        "test",
        "tests",
        "idlelib",
        "tkinter",
        "turtledemo",
        "ensurepip",
        "venv",
        "lib2to3",
    }
)

EXCLUDED_DLL_PREFIXES: tuple[str, ...] = (
    "_tkinter",
    "tcl8",
    "tk8",
    "_test",
)

ALLOWED_SITE_PACKAGE_PREFIXES: tuple[str, ...] = (
    "anyio",
    "attr",
    "attrs",
    "certifi",
    "cffi",
    "_cffi_backend",
    "charset_normalizer",
    "colorama",
    "cryptography",
    "docx",
    "python_docx",
    "dotenv",
    "python_dotenv",
    "fitz",
    "pymupdf",
    "h11",
    "httpcore",
    "httpx",
    "idna",
    "jsonschema",
    "jsonschema_specifications",
    "lxml",
    "networkx",
    "packaging",
    "pdfminer",
    "pdfplumber",
    "pil",
    "pillow",
    "psutil",
    "pycparser",
    "pygments",
    "referencing",
    "rpds",
    "sniffio",
    "tabulate",
    "typing_extensions",
    "websockets",
    "yaml",
    "_yaml",
    "pyyaml",
)


def _should_skip_app_path(rel_parts: tuple[str, ...], filename: str) -> bool:
    if any(
        part in ("__pycache__", ".checkpoints", ".pytest_cache", "node_modules")
        for part in rel_parts
    ):
        return True
    lower = filename.lower()
    if lower.endswith((".pyc", ".pyo", ".pdb", ".obj", ".exp", ".lib", ".db", ".db-wal", ".db-shm", ".bak")):
        return True
    return False


def _is_allowed_site_package_entry(entry_name: str) -> bool:
    lower = entry_name.lower()
    return any(
        lower == prefix
        or lower.startswith(prefix + ".")
        or lower.startswith(prefix + "-")
        or lower.startswith(prefix + "_")
        for prefix in ALLOWED_SITE_PACKAGE_PREFIXES
    )


def build_runtime_bundle() -> dict[str, object]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    base_prefix = Path(sys.base_prefix).resolve()
    active_prefix = Path(sys.prefix).resolve()

    site_packages_dirs: list[Path] = []
    for candidate in (
        active_prefix / "Lib" / "site-packages",
        base_prefix / "Lib" / "site-packages",
    ):
        if candidate.is_dir() and candidate not in site_packages_dirs:
            site_packages_dirs.append(candidate)

    app_files_count = 0
    python_files_count = 0
    site_packages_included: set[str] = set()

    tmp_zip_path = BUNDLE_ZIP_PATH.with_suffix(".zip.tmp")
    if tmp_zip_path.exists():
        tmp_zip_path.unlink()

    with zipfile.ZipFile(tmp_zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        # 1. Bundle JARVIS OS application Python packages and resources under `app/`
        for pkg in APP_PACKAGES:
            pkg_root = REPO_ROOT / pkg
            if not pkg_root.is_dir():
                continue
            for dirpath, dirnames, filenames in os.walk(pkg_root):
                rel_dir = Path(dirpath).relative_to(REPO_ROOT)
                dirnames[:] = [
                    d
                    for d in dirnames
                    if d not in ("__pycache__", ".checkpoints", ".pytest_cache", "node_modules")
                ]
                for fn in filenames:
                    if _should_skip_app_path(rel_dir.parts, fn):
                        continue
                    src_file = Path(dirpath) / fn
                    arcname = f"app/{(rel_dir / fn).as_posix()}"
                    zf.write(src_file, arcname)
                    app_files_count += 1

        for mod_name in APP_ROOT_MODULES:
            src_mod = REPO_ROOT / mod_name
            if src_mod.is_file():
                zf.write(src_mod, f"app/{mod_name}")
                app_files_count += 1

        zf.writestr("app/scripts/__init__.py", "")
        app_files_count += 1
        for script_rel in APP_SCRIPT_FILES:
            src_script = REPO_ROOT / script_rel
            if src_script.is_file():
                zf.write(src_script, f"app/{script_rel}")
                app_files_count += 1

        # 2. Bundle portable CPython interpreter & base DLLs under `python/`
        for root_file in base_prefix.iterdir():
            if not root_file.is_file():
                continue
            lower = root_file.name.lower()
            if (
                lower in ("python.exe", "pythonw.exe", "LICENSE.txt".lower())
                or (lower.startswith("python3") and lower.endswith(".dll"))
                or (lower.startswith("vcruntime") and lower.endswith(".dll"))
                or (lower.startswith("msvcp") and lower.endswith(".dll"))
            ):
                zf.write(root_file, f"python/{root_file.name}")
                python_files_count += 1

        dlls_dir = base_prefix / "DLLs"
        if dlls_dir.is_dir():
            for dll_file in dlls_dir.rglob("*"):
                if not dll_file.is_file():
                    continue
                lower = dll_file.name.lower()
                if lower.endswith(".pdb") or any(lower.startswith(p) for p in EXCLUDED_DLL_PREFIXES):
                    continue
                if lower.endswith((".pyd", ".dll")):
                    rel = dll_file.relative_to(dlls_dir).as_posix()
                    zf.write(dll_file, f"python/DLLs/{rel}")
                    python_files_count += 1

        # 3. Bundle standard library under `python/Lib/`
        stdlib_dir = base_prefix / "Lib"
        if stdlib_dir.is_dir():
            for dirpath, dirnames, filenames in os.walk(stdlib_dir):
                rel_dir = Path(dirpath).relative_to(stdlib_dir)
                dirnames[:] = [d for d in dirnames if d not in EXCLUDED_STDLIB_DIRS]
                if any(part in EXCLUDED_STDLIB_DIRS for part in rel_dir.parts):
                    continue
                for fn in filenames:
                    if fn.endswith((".pyc", ".pyo", ".pdb")):
                        continue
                    src_file = Path(dirpath) / fn
                    rel_posix = (rel_dir / fn).as_posix() if rel_dir.parts else fn
                    zf.write(src_file, f"python/Lib/{rel_posix}")
                    python_files_count += 1

        # 4. Bundle allowlisted runtime site-packages under `python/Lib/site-packages/`
        seen_site_arcs: set[str] = set()
        for sp_dir in site_packages_dirs:
            for entry in sp_dir.iterdir():
                if not _is_allowed_site_package_entry(entry.name):
                    continue
                site_packages_included.add(entry.name)
                if entry.is_file():
                    arc = f"python/Lib/site-packages/{entry.name}"
                    if arc not in seen_site_arcs:
                        seen_site_arcs.add(arc)
                        zf.write(entry, arc)
                        python_files_count += 1
                elif entry.is_dir():
                    for dp, dn, fns in os.walk(entry):
                        dn[:] = [d for d in dn if d not in ("__pycache__", "tests", "test")]
                        for fn in fns:
                            if fn.endswith((".pyc", ".pyo", ".pdb")):
                                continue
                            src_f = Path(dp) / fn
                            rel_sp = src_f.relative_to(sp_dir).as_posix()
                            arc = f"python/Lib/site-packages/{rel_sp}"
                            if arc not in seen_site_arcs:
                                seen_site_arcs.add(arc)
                                zf.write(src_f, arc)
                                python_files_count += 1

    os.replace(tmp_zip_path, BUNDLE_ZIP_PATH)

    sha256_hash = hashlib.sha256(BUNDLE_ZIP_PATH.read_bytes()).hexdigest()
    bundle_size_bytes = BUNDLE_ZIP_PATH.stat().st_size

    manifest = {
        "schema_version": 1,
        "bundle_filename": "runtime-bundle.zip",
        "bundle_sha256": sha256_hash,
        "bundle_size_bytes": bundle_size_bytes,
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "python_rel_path": "python/python.exe",
        "app_rel_path": "app",
        "worker_boot_rel_path": "app/workers/worker_boot.py",
        "app_packages": list(APP_PACKAGES),
        "app_root_modules": list(APP_ROOT_MODULES),
        "app_files_count": app_files_count,
        "python_files_count": python_files_count,
        "site_packages_count": len(site_packages_included),
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    result = build_runtime_bundle()
    print(json.dumps(result, indent=2))
