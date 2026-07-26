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

from backend.model_harness.benchmarking import (  # noqa: E402
    BENCHMARK_VERSION,
    BenchmarkConfig,
    BenchmarkMode,
)
from backend.model_harness.benchmarking.runner import (  # noqa: E402
    StatefulBenchmarkRunner,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the isolated ModelHarness stateful read-only benchmark."
        )
    )
    parser.add_argument(
        "--mode",
        choices=[item.value for item in BenchmarkMode],
        default=BenchmarkMode.SMOKE.value,
    )
    parser.add_argument("--model", default="qwen3.5:9b")
    parser.add_argument("--output")
    parser.add_argument("--repetitions", type=int)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--context-tokens", type=int, default=8_192)
    parser.add_argument("--max-steps", type=int, default=6)
    parser.add_argument("--keep-alive", default="15m")
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument(
        "--fault-injection",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--debug-prompts",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:11434",
    )
    return parser


def config_from_args(args: argparse.Namespace) -> BenchmarkConfig:
    mode = BenchmarkMode(args.mode)
    repetitions = args.repetitions
    if repetitions is None:
        repetitions = 1 if mode == BenchmarkMode.SMOKE else 2
    if mode != BenchmarkMode.SMOKE:
        repetitions = max(2, repetitions)
    output = args.output or str(
        Path(
            "diagnostics",
            "model_harness_benchmark",
            (
                datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
                + f"-stateful-{mode.value}"
            ),
        )
    )
    return BenchmarkConfig(
        mode=mode,
        model=args.model,
        output_dir=output,
        repetitions=repetitions,
        seed=args.seed,
        context_tokens=args.context_tokens,
        max_steps=args.max_steps,
        keep_alive=args.keep_alive,
        timeout_seconds=args.timeout,
        fault_injection=args.fault_injection,
        debug_prompts=args.debug_prompts,
        base_url=args.base_url,
    )


async def async_main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = config_from_args(args)
    runner = StatefulBenchmarkRunner(config)
    summary = await runner.run()
    print(json.dumps({
        "benchmark_version": BENCHMARK_VERSION,
        "output": str(Path(config.output_dir).resolve()),
        "mode": config.mode.value,
        "scenario_repetitions": summary["scenario_repetitions"],
        "passed_repetitions": summary["passed_repetitions"],
        "failed_repetitions": summary["failed_repetitions"],
        "model_calls": summary["model_calls"],
        "integrity_unchanged": summary["integrity"]["unchanged"],
        "decision": summary["decision"],
    }, ensure_ascii=False, indent=2))
    return 0 if (
        summary["failed_repetitions"] == 0
        and summary["integrity"]["unchanged"]
        and not summary["infrastructure_errors"]
    ) else 1


def main() -> int:
    return asyncio.run(async_main())


if __name__ == "__main__":
    raise SystemExit(main())
