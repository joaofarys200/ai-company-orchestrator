from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.model_harness.benchmarking.provider_diagnostic_synthesis import (  # noqa: E402
    assemble_final_diagnostic,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Assemble the clean matrix, exact stream probe, historical "
            "failure, and contaminated-run evidence without new model calls."
        )
    )
    parser.add_argument("--clean-run", type=Path, required=True)
    parser.add_argument("--partial-run", type=Path, required=True)
    parser.add_argument("--stream-run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--ollama-log",
        type=Path,
        default=(
            Path(os.environ.get("LOCALAPPDATA") or "")
            / "Ollama"
            / "server.log"
        ),
    )
    parser.add_argument(
        "--validation-results",
        type=Path,
        help="Optional JSON produced by the offline validation step.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    validation = {}
    if args.validation_results:
        validation = json.loads(
            args.validation_results.read_text(encoding="utf-8")
        )
    summary = assemble_final_diagnostic(
        clean_run=args.clean_run.resolve(),
        partial_run=args.partial_run.resolve(),
        stream_run=args.stream_run.resolve(),
        output_dir=args.output.resolve(),
        ollama_log=args.ollama_log.resolve(),
        validation_results=validation,
    )
    print(json.dumps({
        "output": str(args.output.resolve()),
        "decision": summary["decision"],
        "integrity_unchanged": summary["integrity_unchanged"],
        "production_fix_implemented": (
            summary["production_fix_implemented"]
        ),
    }, ensure_ascii=False, indent=2))
    return 0 if summary["integrity_unchanged"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
