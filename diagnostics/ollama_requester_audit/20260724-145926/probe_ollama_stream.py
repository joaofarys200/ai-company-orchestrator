from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.orchestrator import project_builder as pb  # noqa: E402


ENDPOINT = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
PROMPT = (
    "Cria um projeto full-stack pequeno chamado health-boundary-probe, com frontend, "
    "backend, persistencia simples, testes executaveis e preview. Usa apenas Node.js "
    "standard library, sem dependencias externas. Nao uses Obsidian."
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def command(args: list[str], timeout: float = 20.0) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        completed = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return {
            "command": args,
            "exit_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "duration_seconds": round(time.perf_counter() - started, 4),
        }
    except Exception as exc:
        return {
            "command": args,
            "exit_code": None,
            "stdout": "",
            "stderr": f"{type(exc).__name__}: {exc}",
            "duration_seconds": round(time.perf_counter() - started, 4),
        }


def capture_environment(suffix: str = "") -> None:
    ps = "Get-Process ollama -ErrorAction SilentlyContinue | Select-Object Id,ProcessName,CPU,WorkingSet64,StartTime,Path | ConvertTo-Json -Compress"
    os_info = "Get-CimInstance Win32_OperatingSystem | Select-Object TotalVisibleMemorySize,FreePhysicalMemory,LastBootUpTime | ConvertTo-Json -Compress"
    connection = "Get-NetTCPConnection -LocalPort 11434 -ErrorAction SilentlyContinue | Select-Object LocalAddress,LocalPort,RemoteAddress,State,OwningProcess | ConvertTo-Json -Compress"
    commands = [
        command([str(ROOT / "venv" / "Scripts" / "python.exe"), "--version"]),
        command([str(ROOT / "venv" / "Scripts" / "python.exe"), "-c", "import httpx; print(httpx.__version__)"]),
        command(["ollama", "--version"]),
        command(["ollama", "list"]),
        command(["ollama", "ps"]),
        command(["powershell", "-NoProfile", "-Command", ps]),
        command(["powershell", "-NoProfile", "-Command", os_info]),
        command(["powershell", "-NoProfile", "-Command", connection]),
        command(["nvidia-smi", "--query-gpu=name,driver_version,memory.total,memory.used,utilization.gpu", "--format=csv,noheader,nounits"]),
    ]
    result = {
        "captured_at": now_iso(),
        "endpoint": ENDPOINT,
        "python_executable": sys.executable,
        "requester": {
            "model": pb._project_builder_setting("OLLAMA_MODEL", "qwen2.5:14b"),
            "context_tokens": pb._positive_int_setting("PROJECT_BUILDER_PLAN_CONTEXT_TOKENS", 32768),
            "max_output_tokens": pb._positive_int_setting("PROJECT_BUILDER_PLAN_MAX_OUTPUT_TOKENS", 16384),
            "timeouts": pb.project_builder_plan_timeout_config().to_dict(),
            "keep_alive": pb._project_builder_setting("PROJECT_BUILDER_PLAN_KEEP_ALIVE", "15m"),
        },
        "commands": commands,
    }
    target = OUT / (f"environment_{suffix}.json" if suffix else "environment.json")
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def wp1_messages() -> tuple[str, list[dict[str, str]], dict[str, Any]]:
    intent = pb.detect_project_creation_intent(PROMPT)
    planning_prompt = pb._prompt_with_intent_constraints(PROMPT, intent)
    messages = pb._ollama_messages(planning_prompt, None, False)
    schema = pb.project_plan_schema_document()
    return planning_prompt, messages, schema


def schema_stats(value: Any) -> dict[str, Any]:
    properties = 0
    enums = 0
    arrays = 0
    descriptions = 0
    max_depth = 0

    def visit(item: Any, depth: int = 0) -> None:
        nonlocal properties, enums, arrays, descriptions, max_depth
        max_depth = max(max_depth, depth)
        if isinstance(item, dict):
            if isinstance(item.get("properties"), dict):
                properties += len(item["properties"])
            if "enum" in item:
                enums += 1
            if item.get("type") == "array":
                arrays += 1
            if isinstance(item.get("description"), str):
                descriptions += len(item["description"])
            for child in item.values():
                visit(child, depth + 1)
        elif isinstance(item, list):
            for child in item:
                visit(child, depth + 1)

    visit(value)
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return {
        "properties": properties,
        "enums": enums,
        "arrays": arrays,
        "description_characters": descriptions,
        "max_depth": max_depth,
        "bytes": len(encoded),
    }


def capture_payload() -> None:
    planning_prompt, messages, schema = wp1_messages()
    model = pb._project_builder_setting("OLLAMA_MODEL", "qwen2.5:14b")
    context_tokens = pb._positive_int_setting("PROJECT_BUILDER_PLAN_CONTEXT_TOKENS", 32768)
    max_output_tokens = pb._positive_int_setting("PROJECT_BUILDER_PLAN_MAX_OUTPUT_TOKENS", 16384)
    keep_alive = pb._project_builder_setting("PROJECT_BUILDER_PLAN_KEEP_ALIVE", "15m")
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "format": "json",
        "think": False,
        "keep_alive": keep_alive,
        "options": {
            "temperature": 0,
            "top_p": 0.8,
            "num_predict": max_output_tokens,
            "num_ctx": context_tokens,
        },
    }
    prompt_bytes = planning_prompt.encode("utf-8")
    payload_bytes = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    (OUT / "wp1_prompt.txt").write_text(planning_prompt, encoding="utf-8")
    (OUT / "wp1_schema.json").write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "wp1_schema_prompt.txt").write_text(pb.project_plan_schema_prompt(), encoding="utf-8")
    (OUT / "wp1_payload.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "payload_metrics.json").write_text(json.dumps({
        "prompt_characters": len(planning_prompt),
        "prompt_bytes": len(prompt_bytes),
        "message_bytes": sum(len(str(item["content"]).encode("utf-8")) for item in messages),
        "payload_bytes": len(payload_bytes),
        "estimated_prompt_tokens_chars_div_4": round(len(prompt_bytes) / 4),
        "real_token_count": None,
        "token_count_note": "No local tokenizer was invoked; probe response metrics may expose prompt_eval_count.",
        "schema_stats": schema_stats(schema),
        "first_call_ollama_format": "json",
        "structured_json_schema_sent_on_first_call": False,
        "model": model,
        "num_ctx": context_tokens,
        "num_predict": max_output_tokens,
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def make_base_payload(messages: list[dict[str, str]], *, stream: bool, num_predict: int, fmt: Any = None) -> dict[str, Any]:
    payload = {
        "model": pb._project_builder_setting("OLLAMA_MODEL", "qwen2.5:14b"),
        "messages": messages,
        "stream": stream,
        "think": False,
        "keep_alive": pb._project_builder_setting("PROJECT_BUILDER_PLAN_KEEP_ALIVE", "15m"),
        "options": {
            "temperature": 0,
            "top_p": 0.8,
            "num_predict": num_predict,
            "num_ctx": pb._positive_int_setting("PROJECT_BUILDER_PLAN_CONTEXT_TOKENS", 32768),
        },
    }
    if fmt is not None:
        payload["format"] = fmt
    return payload


def b_messages() -> list[dict[str, str]]:
    planning_prompt, actual, _schema = wp1_messages()
    system = actual[0]["content"]
    user = (
        "Cria um plano JSON completo para este pedido. Nao uses schema constrained output; "
        "responde com JSON normal e mantem todos os requisitos do pedido.\n"
        "Pedido e constraints obrigatorias:\n" + planning_prompt
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def c_messages() -> list[dict[str, str]]:
    return [{
        "role": "system",
        "content": "Return exactly one valid JSON object matching the supplied schema. No markdown or prose.",
    }, {
        "role": "user",
        "content": "Produz um plano minimo valido que cumpra exatamente o schema fornecido. Usa apenas um ficheiro de texto e um comando seguro.\nSchema:\n"
        + json.dumps(pb.project_plan_schema_document(), ensure_ascii=False, separators=(",", ":")),
    }]


def focal_schema() -> dict[str, Any]:
    return pb._focal_correction_response_schema({
        "protocol": pb.FOCAL_CORRECTION_PROTOCOL,
        "allowed_plan_updates": ["components"],
        "plan_update_context": {"components": {
            "original_complete_value": ["frontend", "backend", "persistence", "tests"],
            "missing_requested_components": ["preview"],
            "expected_final_complete_value": ["frontend", "backend", "persistence", "tests", "preview"],
        }},
        "allowed_replacements": ["package.json", "tests/run-tests.js", "backend/server.js"],
        "errors": [{"error_code": "COMMAND_TARGET_INVALID"}],
    })


def focal_messages() -> list[dict[str, str]]:
    return [{
        "role": "system",
        "content": "Return one valid JSON object matching the supplied correction schema. No markdown or prose.",
    }, {
        "role": "user",
        "content": "Produces uma correcao minima valida para o erro indicado. Nao devolvas ficheiros inalterados.\nSchema:\n"
        + json.dumps(focal_schema(), ensure_ascii=False, separators=(",", ":")),
    }]


class ResourceMonitor:
    def __init__(self, path: Path, interval: float = 5.0):
        self.path = path
        self.interval = interval
        self.stop = threading.Event()
        self.thread: threading.Thread | None = None
        self.records: list[dict[str, Any]] = []

    def _sample(self) -> dict[str, Any]:
        ps = command(["powershell", "-NoProfile", "-Command", "Get-Process ollama,python -ErrorAction SilentlyContinue | Select-Object Id,ProcessName,CPU,WorkingSet64,Threads | ConvertTo-Json -Compress"])
        memory = command(["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_OperatingSystem | Select-Object TotalVisibleMemorySize,FreePhysicalMemory | ConvertTo-Json -Compress"])
        gpu = command(["nvidia-smi", "--query-gpu=utilization.gpu,memory.total,memory.used,power.draw", "--format=csv,noheader,nounits"])
        return {"wall_time": now_iso(), "monotonic": time.perf_counter(), "processes": ps, "memory": memory, "gpu": gpu}

    def _run(self) -> None:
        while not self.stop.is_set():
            self.records.append(self._sample())
            self.stop.wait(self.interval)

    def __enter__(self) -> "ResourceMonitor":
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *_: Any) -> None:
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=self.interval + 2)
        self.path.write_text(json.dumps(self.records, ensure_ascii=False, indent=2), encoding="utf-8")


def _event(events: list[dict[str, Any]], label: str, started: float, **details: Any) -> None:
    events.append({"event": label, "wall_time": now_iso(), "monotonic_offset": round(time.perf_counter() - started, 6), **details})


async def probe(name: str, payload: dict[str, Any], read_timeout: float = 300.0) -> dict[str, Any]:
    test_dir = OUT / "tests"
    test_dir.mkdir(exist_ok=True)
    started = time.perf_counter()
    events: list[dict[str, Any]] = []
    raw_path = test_dir / f"{name}.stream.raw"
    event_path = test_dir / f"{name}.events.jsonl"
    metrics_path = test_dir / f"{name}.metrics.json"
    raw_file = raw_path.open("wb")
    resource_dir = OUT / "resources"
    resource_dir.mkdir(exist_ok=True)
    resource_monitor = ResourceMonitor(resource_dir / f"{name}.json")
    resource_monitor.__enter__()
    buffer = b""
    chunks = 0
    bytes_received = 0
    json_objects = 0
    content_bytes = 0
    first_content = None
    done_chunk: dict[str, Any] | None = None
    chunk_times: list[float] = []
    line_records: list[dict[str, Any]] = []
    timeout = httpx.Timeout(connect=5.0, read=read_timeout, write=15.0, pool=5.0)
    _event(events, "call_started", started, stream=payload.get("stream"), format=payload.get("format"), payload_bytes=len(json.dumps(payload, ensure_ascii=False).encode("utf-8")))

    def process_line(line: bytes, offset: float) -> None:
        nonlocal json_objects, content_bytes, first_content, done_chunk
        if not line.strip():
            return
        text = line.decode("utf-8", errors="replace")
        record: dict[str, Any] = {"offset": offset, "raw_line_base64": base64.b64encode(line).decode("ascii"), "raw_line": text}
        try:
            obj = json.loads(text)
            json_objects += 1
            record["json_valid"] = True
            record["json"] = obj
            _event(events, "valid_json_object", started, index=json_objects)
            message = obj.get("message") if isinstance(obj, dict) else None
            content = str((message or {}).get("content") or "") if isinstance(message, dict) else ""
            if content:
                content_bytes += len(content.encode("utf-8"))
                if first_content is None:
                    first_content = offset
                    _event(events, "first_non_empty_content", started, characters=len(content))
            if isinstance(obj, dict) and obj.get("done") is True:
                done_chunk = obj
                _event(events, "generation_done", started, done_reason=obj.get("done_reason"))
        except json.JSONDecodeError as exc:
            record["json_valid"] = False
            record["parse_error"] = str(exc)
            _event(events, "json_parse_error", started, error=str(exc))
        line_records.append(record)

    try:
        async with httpx.AsyncClient(base_url=ENDPOINT, timeout=timeout) as client:
            try:
                async with client.stream("POST", "/api/chat", json=payload) as response:
                    _event(events, "headers_received", started, status_code=response.status_code, headers={key: value for key, value in response.headers.items() if key.lower() in {"content-type", "date", "server", "content-length", "transfer-encoding"}})
                    if response.status_code >= 400:
                        body = await response.aread()
                        raw_file.write(body)
                        _event(events, "http_error", started, status_code=response.status_code, body=body.decode("utf-8", errors="replace")[:2000])
                    elif payload.get("stream"):
                        async for raw in response.aiter_raw():
                            offset = time.perf_counter() - started
                            if not chunk_times:
                                _event(events, "first_byte", started, bytes=len(raw))
                                _event(events, "first_http_chunk", started, bytes=len(raw))
                            chunks += 1
                            bytes_received += len(raw)
                            chunk_times.append(offset)
                            raw_file.write(raw)
                            buffer += raw
                            while b"\n" in buffer:
                                line, buffer = buffer.split(b"\n", 1)
                                process_line(line, offset)
                        if buffer:
                            process_line(buffer, time.perf_counter() - started)
                            _event(events, "remote_stream_closed_with_tail", started, bytes=len(buffer))
                    else:
                        body = await response.aread()
                        offset = time.perf_counter() - started
                        bytes_received = len(body)
                        chunks = 1 if body else 0
                        if body:
                            _event(events, "first_byte", started, bytes=len(body))
                            _event(events, "first_http_chunk", started, bytes=len(body))
                            raw_file.write(body)
                            process_line(body, offset)
            except httpx.ReadTimeout as exc:
                _event(events, "read_timeout", started, error=f"{type(exc).__name__}: {exc}")
            except httpx.HTTPError as exc:
                _event(events, "http_exception", started, error=f"{type(exc).__name__}: {exc}")
            except Exception as exc:
                _event(events, "client_exception", started, error=f"{type(exc).__name__}: {exc}")
    finally:
        raw_file.close()
        resource_monitor.__exit__(None, None, None)

    total = time.perf_counter() - started
    max_interval = max((right - left for left, right in zip(chunk_times, chunk_times[1:])), default=None)
    metrics = {
        "name": name,
        "started_at": events[0].get("wall_time") if events else now_iso(),
        "duration_seconds": round(total, 6),
        "read_timeout_seconds": read_timeout,
        "stream": payload.get("stream"),
        "format": payload.get("format"),
        "chunks": chunks,
        "bytes_received": bytes_received,
        "json_objects": json_objects,
        "content_bytes": content_bytes,
        "time_to_headers": next((item["monotonic_offset"] for item in events if item["event"] == "headers_received"), None),
        "time_to_first_byte": next((item["monotonic_offset"] for item in events if item["event"] == "first_byte"), None),
        "time_to_first_http_chunk": next((item["monotonic_offset"] for item in events if item["event"] == "first_http_chunk"), None),
        "time_to_first_json": next((item["monotonic_offset"] for item in events if item["event"] == "valid_json_object"), None),
        "time_to_first_content": next((item["monotonic_offset"] for item in events if item["event"] == "first_non_empty_content"), None),
        "max_chunk_interval": max_interval,
        "done": bool(done_chunk and done_chunk.get("done") is True),
        "done_reason": done_chunk.get("done_reason") if done_chunk else None,
        "prompt_eval_count": done_chunk.get("prompt_eval_count") if done_chunk else None,
        "prompt_eval_duration": done_chunk.get("prompt_eval_duration") if done_chunk else None,
        "eval_count": done_chunk.get("eval_count") if done_chunk else None,
        "eval_duration": done_chunk.get("eval_duration") if done_chunk else None,
        "load_duration": done_chunk.get("load_duration") if done_chunk else None,
        "total_duration": done_chunk.get("total_duration") if done_chunk else None,
        "first_content_offset": first_content,
        "useful_terminated": bool(done_chunk and done_chunk.get("done") is True and content_bytes > 0),
        "events": events,
        "payload_file": str((OUT / "payloads" / f"{name}.json").relative_to(OUT)),
    }
    (OUT / "payloads").mkdir(exist_ok=True)
    (OUT / "payloads" / f"{name}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    event_path.write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in events) + "\n", encoding="utf-8")
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    (test_dir / f"{name}.lines.json").write_text(json.dumps(line_records, ensure_ascii=False, indent=2), encoding="utf-8")
    return metrics


async def warmup() -> dict[str, Any]:
    payload = make_base_payload([{"role": "user", "content": "Responde apenas com {\"warmup\":true}"}], stream=False, num_predict=8)
    return await probe("warmup", payload, read_timeout=60.0)


async def cold_reset() -> dict[str, Any]:
    payload = {
        "model": pb._project_builder_setting("OLLAMA_MODEL", "qwen2.5:14b"),
        "messages": [{"role": "user", "content": "Responde apenas com ok"}],
        "stream": False,
        "keep_alive": 0,
        "options": {"num_predict": 1, "num_ctx": 8192, "temperature": 0, "top_p": 0.8},
    }
    started = time.perf_counter()
    result: dict[str, Any] = {"started_at": now_iso(), "payload": payload}
    try:
        timeout = httpx.Timeout(connect=5, read=60, write=15, pool=5)
        async with httpx.AsyncClient(base_url=ENDPOINT, timeout=timeout) as client:
            response = await client.post("/api/chat", json=payload)
            result.update({"status_code": response.status_code, "body": response.text})
    except Exception as exc:
        result.update({"error_type": type(exc).__name__, "error": str(exc)})
    result["duration_seconds"] = round(time.perf_counter() - started, 6)
    (OUT / "cold_reset.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


async def run_test(name: str) -> dict[str, Any]:
    planning_prompt, actual_messages, schema = wp1_messages()
    if name == "A1":
        payload = make_base_payload([{"role": "user", "content": 'Responde apenas com: {"ok":true}'}], stream=True, num_predict=64)
    elif name == "A2":
        payload = make_base_payload([{"role": "user", "content": 'Responde apenas com: {"ok":true}'}], stream=False, num_predict=64)
    elif name == "B1":
        payload = make_base_payload(b_messages(), stream=True, num_predict=1024)
    elif name == "B2":
        payload = make_base_payload(b_messages(), stream=False, num_predict=1024)
    elif name == "C1":
        payload = make_base_payload(c_messages(), stream=True, num_predict=1024, fmt=schema)
    elif name == "C2":
        payload = make_base_payload(c_messages(), stream=False, num_predict=1024, fmt=schema)
    elif name == "C-focal":
        payload = make_base_payload(focal_messages(), stream=True, num_predict=512, fmt=focal_schema())
    elif name == "D":
        payload = json.loads((OUT / "wp1_payload.json").read_text(encoding="utf-8"))
    elif name == "D-cold":
        payload = json.loads((OUT / "wp1_payload.json").read_text(encoding="utf-8"))
    else:
        raise ValueError(f"Unknown test: {name}")
    return await probe(name, payload)


async def run_requester() -> dict[str, Any]:
    planning_prompt, _messages, _schema = wp1_messages()
    requester = pb.OllamaPlanRequester()
    started = time.perf_counter()
    result: dict[str, Any] = {
        "started_at": now_iso(),
        "requester": "agents.orchestrator.project_builder.OllamaPlanRequester",
        "prompt_file": "wp1_prompt.txt",
    }
    try:
        raw = await requester(planning_prompt, None)
        result.update({
            "status": "SUCCEEDED",
            "raw_response_characters": len(str(raw)),
            "raw_response_bytes": len(str(raw).encode("utf-8")),
            "raw_response": str(raw),
        })
    except Exception as exc:
        result.update({
            "status": "FAILED",
            "error_type": type(exc).__name__,
            "error": str(exc),
        })
    result["duration_seconds"] = round(time.perf_counter() - started, 6)
    result["diagnostics"] = requester.diagnostics()
    (OUT / "requester_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "status": result["status"],
        "duration_seconds": result["duration_seconds"],
        "attempt_count": result["diagnostics"].get("attempt_count"),
        "raw_response_bytes": result.get("raw_response_bytes", 0),
        "final_error": result["diagnostics"].get("final_error"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["environment", "capture", "warmup", "cold-reset", "test", "requester"])
    parser.add_argument("--name", choices=["A1", "A2", "B1", "B2", "C1", "C2", "C-focal", "D", "D-cold"])
    parser.add_argument("--suffix", default="")
    args = parser.parse_args()
    if args.command == "environment":
        capture_environment(args.suffix)
        return 0
    if args.command == "capture":
        capture_payload()
        return 0
    if args.command == "warmup":
        result = asyncio.run(warmup())
    elif args.command == "cold-reset":
        result = asyncio.run(cold_reset())
        print(json.dumps({
            "status_code": result.get("status_code"),
            "duration_seconds": result.get("duration_seconds"),
            "error": result.get("error"),
        }, ensure_ascii=False))
        return 0
    elif args.command == "requester":
        result = asyncio.run(run_requester())
        print(json.dumps(result, ensure_ascii=False))
        return 0
    else:
        if not args.name:
            parser.error("test requires --name")
        result = asyncio.run(run_test(args.name))
    print(json.dumps({
        "name": result["name"],
        "duration_seconds": result["duration_seconds"],
        "chunks": result["chunks"],
        "bytes_received": result["bytes_received"],
        "done": result["done"],
        "useful_terminated": result["useful_terminated"],
        "first_content": result["time_to_first_content"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
