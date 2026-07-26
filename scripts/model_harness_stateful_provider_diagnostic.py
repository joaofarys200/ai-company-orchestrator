from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.model_harness.benchmarking.provider_diagnostic import (  # noqa: E402
    DEFAULT_SCENARIO,
    DIAGNOSTIC_ROOT,
    DiagnosticConfig,
    StatefulProviderDiagnostic,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Diagnose the isolated provider path of the first stateful "
            "ModelHarness request without executing tools."
        )
    )
    parser.add_argument("--scenario", default=DEFAULT_SCENARIO)
    parser.add_argument("--model", default="qwen3.5:9b")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:11434",
    )
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--output")
    parser.add_argument(
        "--mode",
        choices=("exact", "matrix", "compare"),
        default="exact",
    )
    parser.add_argument("--keep-alive", default="15m")
    parser.add_argument("--debug-payload", action="store_true")
    parser.add_argument("--capture-ollama-logs", action="store_true")
    parser.add_argument("--compare-v1", action="store_true")
    parser.add_argument("--direct-ollama", action="store_true")
    parser.add_argument(
        "--reset-model-between-variants",
        action="store_true",
        help=(
            "Explicitly unload the selected model after each live matrix "
            "variant so a stuck runner cannot contaminate the next one."
        ),
    )
    parser.add_argument(
        "--stream-probe-only",
        action="store_true",
        help=(
            "In exact mode, run only the exact payload with stream=true "
            "to observe first byte, chunk, and token timing."
        ),
    )
    return parser


def config_from_args(args: argparse.Namespace) -> DiagnosticConfig:
    output = Path(args.output) if args.output else (
        DIAGNOSTIC_ROOT
        / (
            datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            + f"-{args.mode}"
        )
    )
    return DiagnosticConfig(
        scenario=args.scenario,
        model=args.model,
        base_url=args.base_url,
        timeout_seconds=args.timeout,
        output_dir=output,
        mode=args.mode,
        keep_alive=args.keep_alive,
        debug_payload=args.debug_payload,
        capture_ollama_logs=args.capture_ollama_logs,
        compare_v1=args.compare_v1,
        direct_ollama=args.direct_ollama,
        reset_model_between_variants=(
            args.reset_model_between_variants
        ),
        stream_probe_only=args.stream_probe_only,
    )


async def async_main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = config_from_args(args)
    diagnostic = StatefulProviderDiagnostic(config)
    summary = await diagnostic.run()
    print(json.dumps({
        "output": str(config.output_dir.resolve()),
        "scenario": summary["scenario"],
        "mode": summary["mode"],
        "decision": summary["decision"],
        "integrity_unchanged": summary["integrity_unchanged"],
        "production_fix_implemented": (
            summary["production_fix_implemented"]
        ),
    }, ensure_ascii=False, indent=2))
    return 0 if summary["integrity_unchanged"] else 1


def main() -> int:
    return asyncio.run(async_main())


if __name__ == "__main__":
    raise SystemExit(main())
