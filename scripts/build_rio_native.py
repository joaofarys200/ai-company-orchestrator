"""
JARVIS OS — Phase 23: Native RIO Extension Compiler
Invokes MSVC Build Tools to compile rio_native.c into rio_native.dll.
"""

import os
import subprocess
import sys

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
VCVARS_PATH = r"C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
RIO_DIR = os.path.join(WORKSPACE_ROOT, "agents", "native_rio_transport")
C_SOURCE = os.path.join(RIO_DIR, "rio_native.c")
DLL_OUTPUT = os.path.join(RIO_DIR, "rio_native.dll")


def build_rio_dll():
    print("=" * 80)
    print("JARVIS OS — COMPILING WINDOWS RIO NATIVE C EXTENSION (MSVC x64)")
    print("=" * 80)

    if not os.path.exists(VCVARS_PATH):
        print(f"[WARN] MSVC vcvars64.bat not found at: {VCVARS_PATH}")
        return False

    if not os.path.exists(C_SOURCE):
        print(f"[ERROR] Source file not found: {C_SOURCE}")
        return False

    cmd = f'call "{VCVARS_PATH}" && cl.exe /O2 /LD /D_CRT_SECURE_NO_WARNINGS /Fe:"{DLL_OUTPUT}" "{C_SOURCE}" ws2_32.lib'
    print(f"[BUILD] Executing: {cmd}")

    try:
        res = subprocess.run(
            ["cmd.exe", "/c", cmd],
            cwd=RIO_DIR,
            capture_output=True,
            text=True,
            check=False,
        )
        print(res.stdout)
        if res.returncode != 0:
            print(f"[ERROR] Compilation failed with returncode {res.returncode}:\n{res.stderr}")
            return False

        if os.path.exists(DLL_OUTPUT):
            dll_size_kb = round(os.path.getsize(DLL_OUTPUT) / 1024, 2)
            print(f"[SUCCESS] Native RIO DLL compiled successfully: {DLL_OUTPUT} ({dll_size_kb} KB)")
            return True
        else:
            print(f"[ERROR] DLL output file missing: {DLL_OUTPUT}")
            return False
    except Exception as ex:
        print(f"[ERROR] Exception during build: {ex}")
        return False


if __name__ == "__main__":
    success = build_rio_dll()
    if not success:
        sys.exit(1)
