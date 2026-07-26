from __future__ import annotations

import asyncio
import hashlib
import json
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.orchestrator import project_builder as builder


AUDIT = Path(__file__).resolve().parent
JOURNAL = ROOT / "workspace/.jarvis/project_builder/runs/a794351f203f48828fde4de76fa34972.json"
MISSION = ROOT / "workspace/.jarvis/projects/flight-recorder-wp1-9864320f2fa3/missions/mission-9864320f2fa3/mission.json"
MODEL = "qwen3.5:9b"
ENDPOINT = "http://127.0.0.1:11434/api/chat"


def load_inputs() -> tuple[str, str, str]:
    journal = json.loads(JOURNAL.read_text(encoding="utf-8"))
    objective = json.loads(MISSION.read_text(encoding="utf-8"))["objective"]
    history = journal["planning_diagnostics"]["validation_history"]
    original = next(item for item in history if item["label"] == "original")
    correction = next(item for item in history if item["label"] == "corrected")
    try:
        builder._validated_raw_project_plan(original["response"], objective)
    except builder._PlanValidationFailure as failure:
        correction_prompt = builder._structured_plan_correction(
            failure, original["response"], objective
        )
    else:
        raise RuntimeError("The preserved original plan is unexpectedly valid.")
    expected_hash = journal["planning_diagnostics"]["correction_prompt_sha256"]
    actual_hash = hashlib.sha256(correction_prompt.encode("utf-8")).hexdigest()
    if actual_hash != expected_hash:
        raise RuntimeError(f"Correction prompt hash mismatch: {actual_hash} != {expected_hash}")
    return objective, correction_prompt, correction["response"]


def correction_messages(prompt: str) -> list[dict[str, str]]:
    return builder._ollama_messages("", prompt, compact=False)


async def chat(
    name: str,
    messages: list[dict[str, str]],
    response_format: dict | None,
) -> dict:
    payload = {
        "model": MODEL,
        "messages": messages,
        "stream": True,
        "think": False,
        "keep_alive": "15m",
        "options": {
            "temperature": 0,
            "top_p": 0.8,
            "num_predict": 2048,
            "num_ctx": 8192,
        },
    }
    if response_format is not None:
        payload["format"] = response_format
    started = time.perf_counter()
    chunks: list[dict] = []
    raw_lines: list[str] = []
    status_code = None
    error = None
    try:
        timeout = httpx.Timeout(connect=5, read=300, write=15, pool=5)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", ENDPOINT, json=payload) as response:
                status_code = response.status_code
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    raw_lines.append(line)
                    try:
                        chunks.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    except Exception as exc:  # diagnostic result, never swallowed in the report
        error = {"type": type(exc).__name__, "message": str(exc)}
    duration = time.perf_counter() - started
    content = "".join(
        str(item.get("message", {}).get("content") or "")
        for item in chunks
    )
    result = {
        "name": name,
        "model": MODEL,
        "status_code": status_code,
        "duration_seconds": round(duration, 3),
        "chunks": len(chunks),
        "raw_bytes": sum(len(line.encode("utf-8")) for line in raw_lines),
        "content_characters": len(content),
        "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "done_reason": next((item.get("done_reason") for item in reversed(chunks) if item.get("done")), None),
        "error": error,
        "content": content,
        "payload": payload,
    }
    (AUDIT / "model_tests" / f"{name}.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result


def correction_schema(correction: str) -> dict:
    return builder._focal_correction_response_schema(correction)


async def main() -> None:
    objective, correction_prompt, preserved_correction = load_inputs()
    schema = correction_schema(correction_prompt)
    results: list[dict] = []

    # M1 cannot be exact: the preserved run contains only prompt length/hash,
    # and the current equivalent prompt has a different recorded hash.
    saved_near_prompt = (ROOT / "diagnostics/ollama_requester_audit/20260724-145926/wp1_prompt.txt").read_text(encoding="utf-8")
    results.append({
        "name": "M1_exact",
        "status": "NOT_EXECUTED",
        "reason": "The real planning prompt content was not persisted; only length 609 and a SHA-256 were retained. The saved equivalent prompt is 583 bytes and cannot be called exact.",
        "saved_equivalent_prompt_bytes": len(saved_near_prompt.encode("utf-8")),
        "recorded_prompt_bytes": 609,
    })

    # M2: exact focal prompt, exact schema, no production path involved.
    m2 = await chat("M2_original_correction", correction_messages(correction_prompt), schema)
    results.append({"name": "M2_original_correction", **{k: m2[k] for k in ("status_code", "duration_seconds", "chunks", "content_characters", "content_sha256", "done_reason", "error")}})

    valid_paths = ["package.json", "server.js", "index.html", "test.js"]
    closed_prompt = correction_prompt + "\n\nVALID_PATHS (closed namespace): " + json.dumps(valid_paths) + ". Do not create, rename or refer to any other path."
    m3 = await chat("M3_closed_paths", correction_messages(closed_prompt), schema)
    results.append({"name": "M3_closed_paths", **{k: m3[k] for k in ("status_code", "duration_seconds", "chunks", "content_characters", "content_sha256", "done_reason", "error")}})

    operations_prompt = (
        "You are testing an offline correction representation. Using the preserved project plan and errors below, "
        "return one JSON object with only an operations array. Allowed operations are replace_field, replace_reference, "
        "add_required_field and remove_invalid_reference. Every operation must use an existing field ID or one of "
        + json.dumps(valid_paths)
        + ". Do not invent paths and do not return file contents.\n\n"
        + correction_prompt
        + "\n\nReturn exactly: {\"operations\":[{\"op\":\"...\",\"target\":\"...\",\"value\":...}]}"
    )
    operations_schema = {
        "type": "object",
        "required": ["operations"],
        "additionalProperties": False,
        "properties": {
            "operations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["op", "target", "value"],
                    "additionalProperties": False,
                    "properties": {
                        "op": {"type": "string", "enum": ["replace_field", "replace_reference", "add_required_field", "remove_invalid_reference"]},
                        "target": {"type": "string"},
                        "value": {},
                    },
                },
            }
        },
    }
    m4 = await chat("M4_operations", [{"role": "system", "content": "Return only valid JSON operations."}, {"role": "user", "content": operations_prompt}], operations_schema)
    results.append({"name": "M4_operations", **{k: m4[k] for k in ("status_code", "duration_seconds", "chunks", "content_characters", "content_sha256", "done_reason", "error")}})

    diagnosis_prompt = (
        "Analyze the preserved project-plan errors without returning a plan or file contents. Return JSON with "
        "required_changes, existing_paths, blocked_changes and dependencies. Use only existing paths: "
        + json.dumps(valid_paths)
        + ".\n\n"
        + correction_prompt
    )
    diagnosis_schema = {
        "type": "object",
        "required": ["required_changes", "existing_paths", "blocked_changes", "dependencies"],
        "additionalProperties": False,
        "properties": {
            "required_changes": {"type": "array", "items": {"type": "string"}},
            "existing_paths": {"type": "array", "items": {"type": "string", "enum": valid_paths}},
            "blocked_changes": {"type": "array", "items": {"type": "string"}},
            "dependencies": {"type": "array", "items": {"type": "string"}},
        },
    }
    m5a = await chat("M5a_diagnosis", [{"role": "system", "content": "Return only diagnostic JSON."}, {"role": "user", "content": diagnosis_prompt}], diagnosis_schema)
    results.append({"name": "M5a_diagnosis", **{k: m5a[k] for k in ("status_code", "duration_seconds", "chunks", "content_characters", "content_sha256", "done_reason", "error")}})
    m5b_prompt = (
        correction_prompt
        + "\n\nApply only the approved diagnosis below. Keep the path namespace closed to "
        + json.dumps(valid_paths)
        + ". Do not create paths. Diagnosis:\n"
        + m5a.get("content", "")
    )
    m5b = await chat("M5b_apply", correction_messages(m5b_prompt), schema)
    results.append({"name": "M5b_apply", **{k: m5b[k] for k in ("status_code", "duration_seconds", "chunks", "content_characters", "content_sha256", "done_reason", "error")}})

    (AUDIT / "model_tests" / "index.json").write_text(
        json.dumps({
            "configuration": {"provider": "ollama", "model": MODEL, "context_tokens": 8192, "temperature": 0, "top_p": 0.8, "think": False, "stream": True},
            "objective_sha256": hashlib.sha256(objective.encode("utf-8")).hexdigest(),
            "exact_correction_prompt_sha256": hashlib.sha256(correction_prompt.encode("utf-8")).hexdigest(),
            "preserved_correction_response_sha256": hashlib.sha256(preserved_correction.encode("utf-8")).hexdigest(),
            "results": results,
        }, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    asyncio.run(main())
