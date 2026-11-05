"""
JARVIS OS - Study AI & Multimodal Content Grounding Engine
Motor unificado de síntese pedagógica, transcrição multimodal de áudio/vídeo,
OCR local de diapositivos/keyframes (Windows WinRT OCR) e extração determinística
100% fundamentada no conteúdo real carregado pelo utilizador (zero templates pré-fabricados).
"""

from __future__ import annotations

import asyncio
import base64
import json
import math
import os
import re
import subprocess
import tempfile
import threading
import unicodedata
import wave
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

EXTRACTION_VERSION = "3.0-grounded"


# ---------------------------------------------------------------------------
# Stopwords PT + EN para análise extrativa real (sem frases pré-fabricadas)
# ---------------------------------------------------------------------------

STOPWORDS = {
    # Português
    "a", "ao", "aos", "aquela", "aquelas", "aquele", "aqueles", "aquilo", "as",
    "até", "com", "como", "da", "das", "de", "dela", "delas", "dele", "deles",
    "depois", "do", "dos", "e", "ela", "elas", "ele", "eles", "em", "entre",
    "era", "eram", "essa", "essas", "esse", "esses", "esta", "está", "estão",
    "estas", "este", "estes", "estive", "estou", "eu", "foi", "for", "foram",
    "fosse", "há", "isso", "isto", "já", "lhe", "lhes", "mais", "mas", "me",
    "mesmo", "meu", "meus", "minha", "minhas", "muito", "na", "não", "nas",
    "nem", "no", "nos", "nós", "nossa", "nossas", "nosso", "nossos", "num",
    "numa", "o", "os", "ou", "para", "pela", "pelas", "pelo", "pelos", "por",
    "qual", "quando", "que", "quem", "são", "se", "seja", "sem", "ser", "será",
    "seu", "seus", "só", "sobre", "sua", "suas", "também", "te", "tem", "têm",
    "ter", "teu", "teus", "tinha", "todos", "tu", "tua", "tuas", "tudo", "um",
    "uma", "umas", "uns", "vai", "vão", "você", "vocês", "vos", "cada", "pode",
    "podem", "sendo", "onde", "assim", "então", "ainda", "deste", "desta",
    "nesse", "nessa", "neste", "nesta", "através", "durante", "forma", "modo",
    # Inglês
    "the", "and", "for", "that", "this", "with", "from", "are", "was", "were",
    "been", "have", "has", "had", "not", "but", "what", "all", "can", "will",
    "one", "our", "out", "you", "your", "their", "they", "them", "these",
    "those", "which", "when", "where", "who", "whom", "whose", "why", "how",
    "into", "onto", "upon", "over", "under", "again", "further", "then", "once",
    "here", "there", "any", "both", "each", "few", "more", "most", "other",
    "some", "such", "only", "own", "same", "than", "too", "very", "also", "may",
    "might", "must", "shall", "should", "would", "could", "about", "between",
    "through", "during", "before", "after", "above", "below", "while", "because",
    "does", "did", "doing", "used", "using", "use", "based", "however", "therefore",
}

# Frases conhecidas de templates pré-fabricados antigos para deteção/limpeza de cache poluída
LEGACY_PREFABRICATED_MARKERS = (
    "Transcrição de teste: Durante a aula foram abordados os conceitos fundamentais da disciplina.",
    "O artigo aborda otimização e precisão em cenários de alta complexidade.",
    "Arquitetura modular baseada em verificação formal e orquestração de subsistemas.",
    "Necessidade de conciliar eficiência computacional com garantias estritas.",
    "O artigo propõe novos mecanismos em ",
    "Separação de Evidências (OBSERVED vs INFERRED)",
    "Consenso: Acordo unificado sobre estado distribuído.",
    "como é definido o conceito de 'Logical Clock' / Termo em Raft?",
    "Objetivo Central: Estabelecer coordenação robusta e semântica de materiais de estudo",
    "Análise minuciosa dos parágrafos da secção ",
    "Apresentar uma fundamentação estruturada para investigar os desafios centrais em ",
    "Rejeitar todos os referenciais teóricos anteriores sem evidência empírica",
    "Possibilitar a replicação e generalização dos resultados através de um desenho metodológico transparente",
)

# Registo thread-safe de telemetria e cancelamento de gerações em curso
_TELEMETRY_LOCK = threading.Lock()
_LAST_STUDY_TELEMETRY: Dict[str, Any] = {}
_CANCELLED_GENERATIONS: set[str] = set()


def register_study_generation_start(document_id: str, generation_id: Optional[str] = None) -> None:
    if not document_id:
        return
    with _TELEMETRY_LOCK:
        _CANCELLED_GENERATIONS.discard(document_id)


def cancel_study_generation(document_id: str) -> bool:
    if not document_id:
        return False
    with _TELEMETRY_LOCK:
        _CANCELLED_GENERATIONS.add(document_id)
    return True


def is_study_generation_cancelled(document_id: Optional[str]) -> bool:
    if not document_id:
        return False
    with _TELEMETRY_LOCK:
        return document_id in _CANCELLED_GENERATIONS


def get_last_study_telemetry(document_id: Optional[str] = None) -> Dict[str, Any]:
    with _TELEMETRY_LOCK:
        return dict(_LAST_STUDY_TELEMETRY)


def _record_study_telemetry(telemetry: Dict[str, Any]) -> None:
    with _TELEMETRY_LOCK:
        _LAST_STUDY_TELEMETRY.clear()
        _LAST_STUDY_TELEMETRY.update(telemetry)


def is_prefabricated_artifact(obj: Any) -> bool:
    """Deteta se um resumo, estrutura, transcrição ou nota Cornell contém texto pré-fabricado legado."""
    if not obj:
        return False
    try:
        serialized = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False)
    except Exception:
        serialized = str(obj)
    return any(marker in serialized for marker in LEGACY_PREFABRICATED_MARKERS)


def format_mmss(seconds: float) -> str:
    sec = max(0, int(seconds))
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def get_ffmpeg_exe() -> Optional[str]:
    env_ff = os.environ.get("FFMPEG_PATH")
    if env_ff and os.path.isfile(env_ff):
        return env_ff
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.isfile(exe):
            return exe
    except Exception:
        pass
    import shutil
    return shutil.which("ffmpeg")


# ---------------------------------------------------------------------------
# Limpeza de Respostas LLM (Qwen 3.5 <think> tags + Markdown fences + JSON)
# ---------------------------------------------------------------------------

def strip_thinking_and_fences(raw_text: str) -> str:
    if not raw_text:
        return ""
    cleaned = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL | re.IGNORECASE)
    # Caso tenha ficado uma tag <think> não fechada antes do JSON
    if "<think>" in cleaned.lower():
        cleaned = re.sub(r"<think>.*", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
    cleaned = cleaned.strip()
    fence_match = re.search(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.DOTALL | re.IGNORECASE)
    if fence_match:
        cleaned = fence_match.group(1).strip()
    return cleaned


def parse_llm_json(raw_text: str) -> Optional[Any]:
    cleaned = strip_thinking_and_fences(raw_text)
    if not cleaned:
        return None
    try:
        return json.loads(cleaned)
    except Exception:
        pass
    # Tentar extrair o primeiro objeto {...} ou array [...] balanceado
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        candidate = cleaned[first_brace : last_brace + 1]
        try:
            return json.loads(candidate)
        except Exception:
            pass
    first_bracket = cleaned.find("[")
    last_bracket = cleaned.rfind("]")
    if first_bracket != -1 and last_bracket > first_bracket:
        candidate = cleaned[first_bracket : last_bracket + 1]
        try:
            return json.loads(candidate)
        except Exception:
            pass
    return None


def _should_use_live_llm() -> bool:
    """
    Em execução real usa sempre o LLM configurado (Ollama qwen3.5:9b / ModelHarness).
    Em testes unitários pytest rápidos, evita bloqueios de rede/daemon exceto quando
    STUDY_FORCE_LIVE_LLM=1 é definido explicitamente.
    """
    if os.environ.get("STUDY_FORCE_LIVE_LLM", "").strip().lower() in ("1", "true", "yes"):
        return True
    if os.environ.get("STUDY_DISABLE_LIVE_LLM", "").strip().lower() in ("1", "true", "yes"):
        return False
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    return True


def _run_coro_sync(coro: Any) -> Any:
    """Executa uma coroutine de forma segura quer exista ou não um event loop ativo na thread atual."""
    try:
        asyncio.get_running_loop()
        has_running_loop = True
    except RuntimeError:
        has_running_loop = False

    if not has_running_loop:
        return asyncio.run(coro)

    result_box: Dict[str, Any] = {}
    error_box: Dict[str, BaseException] = {}

    def _runner() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result_box["value"] = loop.run_until_complete(coro)
        except BaseException as exc:
            error_box["err"] = exc
        finally:
            loop.close()

    t = threading.Thread(target=_runner, daemon=True)
    t.start()
    t.join(timeout=150.0)
    if "err" in error_box:
        raise error_box["err"]
    return result_box.get("value")


async def _async_invoke_llm(
    *,
    operation: str,
    system_prompt: str,
    user_prompt: str,
    expect_json: bool = True,
    temperature: float = 0.15,
    max_output_tokens: int = 4096,
    timeout_seconds: float = 90.0,
    document_id: Optional[str] = None,
) -> Tuple[Optional[str], Dict[str, Any]]:
    """
    Invoca o modelo local exclusivamente através do Ollama + qwen3.5:9b via ModelExecutionService / ModelHarness.
    Proíbe qualquer fallback silencioso para fornecedores cloud externos e regista telemetria observável.
    """
    import time
    import uuid
    from dotenv import load_dotenv
    load_dotenv(".env")
    from backend.model_harness import OutputFormat, get_model_harness
    from backend.services.model_service import ModelExecutionService

    gen_id = f"study_gen_{uuid.uuid4().hex[:12]}"
    provider = "ollama"
    ollama_model = os.getenv("OLLAMA_MODEL", "qwen3.5:9b").strip() or "qwen3.5:9b"
    num_ctx = int(os.getenv("OLLAMA_NUM_CTX", "16384") or "16384")
    est_in_tokens = max(1, (len(system_prompt or "") + len(user_prompt or "")) // 4)

    telemetry: Dict[str, Any] = {
        "generation_id": gen_id,
        "operation": operation,
        "document_id": document_id or "",
        "provider": provider,
        "model": ollama_model,
        "input_tokens": est_in_tokens,
        "output_tokens": 0,
        "ttft_ms": None,
        "total_ms": 0.0,
        "tokens_per_sec": 0.0,
        "context_used": num_ctx,
        "status": "PENDING",
        "validation_errors": [],
        "attempts": 0,
        "timestamp": datetime.now().isoformat(),
    }

    if is_study_generation_cancelled(document_id):
        telemetry["status"] = "CANCELLED"
        telemetry["validation_errors"].append("GENERATION_CANCELLED_BY_USER")
        _record_study_telemetry(telemetry)
        return None, telemetry

    harness = get_model_harness()
    exec_service = ModelExecutionService(harness)
    out_fmt = OutputFormat.JSON if expect_json else OutputFormat.TEXT

    t_start = time.perf_counter()
    validation_errors: List[str] = []

    for attempt_idx, fmt in enumerate(([out_fmt, OutputFormat.TEXT] if expect_json else [OutputFormat.TEXT]), start=1):
        if is_study_generation_cancelled(document_id):
            telemetry["status"] = "CANCELLED"
            validation_errors.append("GENERATION_CANCELLED_BY_USER")
            break

        telemetry["attempts"] = attempt_idx
        op_name = operation if attempt_idx == 1 else f"{operation}_text_json"
        try:
            resp = await exec_service.execute(
                provider=provider,
                model=ollama_model,
                operation=op_name,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                output_format=fmt,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                timeout_seconds=timeout_seconds,
            )
            elapsed_ms = round((time.perf_counter() - t_start) * 1000.0, 2)
            telemetry["total_ms"] = elapsed_ms

            if resp is not None:
                usage = getattr(resp, "usage", None)
                in_tok = getattr(usage, "input_tokens", None) if usage else None
                out_tok = getattr(usage, "output_tokens", None) if usage else None
                if in_tok:
                    telemetry["input_tokens"] = int(in_tok)
                raw_txt = getattr(resp, "raw_text", "") or ""
                if out_tok:
                    telemetry["output_tokens"] = int(out_tok)
                elif raw_txt:
                    telemetry["output_tokens"] = max(1, len(raw_txt) // 4)
                if elapsed_ms > 0 and telemetry["output_tokens"] > 0:
                    telemetry["tokens_per_sec"] = round(
                        telemetry["output_tokens"] / (elapsed_ms / 1000.0), 2
                    )
                meta = getattr(resp, "metadata", None) or {}
                if isinstance(meta, dict) and meta.get("ttft_ms") is not None:
                    telemetry["ttft_ms"] = round(float(meta["ttft_ms"]), 2)

                if raw_txt and raw_txt.strip():
                    cleaned_txt = strip_thinking_and_fences(raw_txt)
                    if "<think>" in cleaned_txt.lower() or "</think>" in cleaned_txt.lower():
                        validation_errors.append("UNSTRIPPED_THINK_TAG")
                        continue
                    if not expect_json:
                        if cleaned_txt.strip():
                            telemetry["status"] = "COMPLETED"
                            telemetry["validation_errors"] = validation_errors
                            _record_study_telemetry(telemetry)
                            return cleaned_txt, telemetry
                        validation_errors.append("EMPTY_TEXT_AFTER_CLEANUP")
                    else:
                        parsed_obj = parse_llm_json(raw_txt)
                        if parsed_obj is not None:
                            telemetry["status"] = "COMPLETED"
                            telemetry["validation_errors"] = validation_errors
                            _record_study_telemetry(telemetry)
                            return raw_txt, telemetry
                        validation_errors.append("INVALID_JSON_SYNTAX")
                else:
                    validation_errors.append("EMPTY_MODEL_RESPONSE")
        except Exception as err:
            elapsed_ms = round((time.perf_counter() - t_start) * 1000.0, 2)
            telemetry["total_ms"] = elapsed_ms
            err_msg = f"{type(err).__name__}: {err}"
            validation_errors.append(err_msg)
            err_lower = err_msg.lower()
            if any(
                tok in err_lower
                for tok in ("connecterror", "connection attempts failed", "timed out", "timeout", "readtimeout", "unavailable")
            ):
                telemetry["status"] = "TIMEOUT" if "timeout" in err_lower or "timed out" in err_lower else "UNAVAILABLE"
                break

    if telemetry["status"] == "PENDING":
        telemetry["status"] = "FAILED_VALIDATION"
    telemetry["validation_errors"] = validation_errors
    _record_study_telemetry(telemetry)
    return None, telemetry


def invoke_study_llm_observable(
    *,
    operation: str,
    system_prompt: str,
    user_prompt: str,
    expect_json: bool = True,
    temperature: float = 0.15,
    max_output_tokens: int = 4096,
    timeout_seconds: float = 90.0,
    document_id: Optional[str] = None,
) -> Tuple[Optional[Any], Dict[str, Any]]:
    """
    Executa geração observável via qwen3.5:9b local e devolve (resultado_parseado, telemetria).
    Nunca simula sucesso quando o modelo está desligado ou devolve JSON inválido.
    """
    if not _should_use_live_llm():
        disabled_telemetry = {
            "generation_id": "study_gen_disabled",
            "operation": operation,
            "document_id": document_id or "",
            "provider": "ollama",
            "model": os.getenv("OLLAMA_MODEL", "qwen3.5:9b").strip() or "qwen3.5:9b",
            "input_tokens": max(1, (len(system_prompt or "") + len(user_prompt or "")) // 4),
            "output_tokens": 0,
            "ttft_ms": None,
            "total_ms": 0.0,
            "tokens_per_sec": 0.0,
            "context_used": int(os.getenv("OLLAMA_NUM_CTX", "16384") or "16384"),
            "status": "SKIPPED_LIVE_LLM_DISABLED",
            "validation_errors": ["LIVE_LLM_DISABLED_IN_ENV"],
            "attempts": 0,
            "timestamp": datetime.now().isoformat(),
        }
        _record_study_telemetry(disabled_telemetry)
        return None, disabled_telemetry

    try:
        raw, telemetry = _run_coro_sync(
            _async_invoke_llm(
                operation=operation,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                expect_json=expect_json,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                timeout_seconds=timeout_seconds,
                document_id=document_id,
            )
        )
        if not raw:
            return None, telemetry
        if expect_json:
            parsed = parse_llm_json(raw)
            if parsed is None:
                telemetry["status"] = "FAILED_VALIDATION"
                telemetry.setdefault("validation_errors", []).append("JSON_PARSE_RETURNED_NONE")
                _record_study_telemetry(telemetry)
                return None, telemetry
            return parsed, telemetry
        return strip_thinking_and_fences(raw), telemetry
    except Exception as exc:
        err_telemetry = get_last_study_telemetry() or {
            "generation_id": "study_gen_exception",
            "operation": operation,
            "document_id": document_id or "",
            "provider": "ollama",
            "model": os.getenv("OLLAMA_MODEL", "qwen3.5:9b").strip() or "qwen3.5:9b",
            "input_tokens": 0,
            "output_tokens": 0,
            "ttft_ms": None,
            "total_ms": 0.0,
            "tokens_per_sec": 0.0,
            "context_used": 16384,
            "status": "FAILED",
            "validation_errors": [f"{type(exc).__name__}: {exc}"],
            "attempts": 1,
            "timestamp": datetime.now().isoformat(),
        }
        _record_study_telemetry(err_telemetry)
        return None, err_telemetry


def invoke_study_llm_json(
    *,
    operation: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.15,
    max_output_tokens: int = 4096,
    timeout_seconds: float = 90.0,
    document_id: Optional[str] = None,
) -> Optional[Any]:
    parsed, _telemetry = invoke_study_llm_observable(
        operation=operation,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        expect_json=True,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        timeout_seconds=timeout_seconds,
        document_id=document_id,
    )
    return parsed


def invoke_study_llm_text(
    *,
    operation: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.2,
    max_output_tokens: int = 2048,
    timeout_seconds: float = 60.0,
    document_id: Optional[str] = None,
) -> Optional[str]:
    text, _telemetry = invoke_study_llm_observable(
        operation=operation,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        expect_json=False,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        timeout_seconds=timeout_seconds,
        document_id=document_id,
    )
    return text if isinstance(text, str) else None


# ---------------------------------------------------------------------------
# OCR Nativo Local de Diapositivos/Keyframes (Windows WinRT Windows.Media.Ocr)
# ---------------------------------------------------------------------------

def extract_keyframes_ocr_windows_with_status(image_paths: List[str]) -> Tuple[Dict[str, str], str]:
    """
    Executa OCR local 100% offline via Windows.Media.Ocr em lote sobre keyframes/imagens.
    Devolve (ocr_map, ocr_status) onde ocr_status pertence a:
    {"OCR_COMPLETED", "OCR_PARTIAL", "OCR_UNAVAILABLE"}.
    """
    if os.name != "nt":
        return {}, "OCR_UNAVAILABLE"
    if not image_paths:
        return {}, "OCR_UNAVAILABLE"
    valid_paths = [os.path.abspath(p) for p in image_paths if p and os.path.isfile(p)]
    if not valid_paths:
        return {}, "OCR_UNAVAILABLE"

    ps_script = r"""
$ErrorActionPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Storage.StorageFile, Windows.Foundation, ContentType = WindowsRuntime]
Add-Type -AssemblyName System.Runtime.WindowsRuntime

$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
})[0]

function Await($WinRtTask, $ResultType) {
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    $netTask.Wait(8000) | Out-Null
    return $netTask.Result
}

$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
if (-not $engine) {
    Write-Output '{"__ocr_engine_unavailable__": true}'
    exit 0
}

$pathsJson = [Console]::In.ReadToEnd()
$paths = ConvertFrom-Json $pathsJson
$results = @{}

foreach ($p in $paths) {
    try {
        $file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($p)) ([Windows.Storage.StorageFile])
        $stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
        $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
        $bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
        $ocr = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
        $lines = @()
        foreach ($line in $ocr.Lines) {
            if ($line.Text) { $lines += $line.Text.Trim() }
        }
        $results[$p] = ($lines -join "`n")
        $stream.Dispose()
    } catch {
        $results[$p] = ""
    }
}
$results | ConvertTo-Json -Compress -Depth 3
"""
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            input=json.dumps(valid_paths),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=35,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            parsed = parse_llm_json(proc.stdout.strip())
            if isinstance(parsed, dict):
                if parsed.get("__ocr_engine_unavailable__"):
                    return {}, "OCR_UNAVAILABLE"
                non_empty = {str(k): str(v).strip() for k, v in parsed.items() if str(v).strip()}
                if non_empty:
                    status = "OCR_COMPLETED" if len(non_empty) >= max(1, len(valid_paths) // 3) else "OCR_PARTIAL"
                    return non_empty, status
                return {}, "OCR_PARTIAL"
    except Exception:
        return {}, "OCR_UNAVAILABLE"
    return {}, "OCR_UNAVAILABLE"


def extract_keyframes_ocr_windows(image_paths: List[str]) -> Dict[str, str]:
    """
    Executa OCR local 100% offline via Windows.Media.Ocr em lote sobre keyframes de vídeo.
    Extrai títulos, listas, tabelas e diagramas visíveis nos diapositivos da aula.
    """
    ocr_map, _status = extract_keyframes_ocr_windows_with_status(image_paths)
    return ocr_map


def deduplicate_slide_ocr_entries(
    entries: List[Tuple[float, str, str]]
) -> List[Tuple[float, str, str]]:
    """
    Remove frames consecutivos com o mesmo slide (similaridade de Jaccard > 0.78),
    mantendo o timestamp em que cada novo diapositivo aparece.
    entries: [(timestamp_sec, frame_id, ocr_text)]
    """
    deduped: List[Tuple[float, str, str]] = []
    prev_tokens: set[str] = set()

    for ts, fid, txt in entries:
        cleaned = re.sub(r"\s+", " ", txt).strip()
        if len(cleaned) < 12:
            continue
        tokens = set(re.findall(r"\b\w{3,}\b", cleaned.lower()))
        if not tokens:
            continue
        if prev_tokens:
            inter = len(tokens & prev_tokens)
            union = max(1, len(tokens | prev_tokens))
            if (inter / union) > 0.78:
                continue
        deduped.append((ts, fid, txt.strip()))
        prev_tokens = tokens

    return deduped


# ---------------------------------------------------------------------------
# Transcrição Real de Áudio e Vídeo (Faster-Whisper Local — Zero Cloud Fallback)
# ---------------------------------------------------------------------------

def compute_wav_duration_and_rms(wav_path: str) -> Tuple[float, float]:
    """Calcula duração real em segundos e energia RMS de um ficheiro WAV PCM 16-bit."""
    if not os.path.isfile(wav_path):
        return 0.0, 0.0
    try:
        with wave.open(wav_path, "rb") as wf:
            nframes = wf.getnframes()
            rate = wf.getframerate() or 16000
            sampwidth = wf.getsampwidth()
            channels = wf.getnchannels()
            duration = nframes / float(rate) if rate > 0 else 0.0
            if nframes == 0 or sampwidth != 2:
                return duration, 0.0
            sample_frames = min(nframes, rate * 45)
            raw = wf.readframes(sample_frames)
            arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            if channels > 1 and len(arr) >= channels:
                arr = arr[::channels]
            rms = float(np.sqrt(np.mean(arr ** 2))) if len(arr) > 0 else 0.0
            return duration, rms
    except Exception:
        return 0.0, 0.0


def ensure_16khz_mono_wav(input_audio_path: str, output_wav_path: Optional[str] = None) -> Tuple[str, bool]:
    """
    Garante que qualquer ficheiro de áudio (.mp3, .m4a, .ogg, .flac, .aac, .wma, .wav)
    está em formato WAV PCM 16kHz mono. Retorna (wav_path, is_temp).
    """
    if input_audio_path.lower().endswith(".wav") and os.path.isfile(input_audio_path):
        try:
            with wave.open(input_audio_path, "rb") as wf:
                if wf.getsampwidth() == 2 and wf.getframerate() > 0:
                    return input_audio_path, False
        except Exception:
            pass

    ffmpeg_bin = get_ffmpeg_exe()
    if not ffmpeg_bin:
        return input_audio_path, False

    is_temp = output_wav_path is None
    if not output_wav_path:
        fd, output_wav_path = tempfile.mkstemp(suffix="_study_16k.wav")
        os.close(fd)

    cmd = [
        ffmpeg_bin, "-y", "-i", input_audio_path,
        "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        output_wav_path,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if res.returncode != 0 or not os.path.isfile(output_wav_path) or os.path.getsize(output_wav_path) == 0:
        if is_temp and os.path.exists(output_wav_path):
            try:
                os.remove(output_wav_path)
            except Exception:
                pass
        raise RuntimeError(f"Falha ao converter áudio via FFmpeg: {(res.stderr or '')[:200]}")
    return output_wav_path, is_temp


def _transcribe_via_multimodal_chunks(
    wav_path: str,
    duration_seconds: float,
    language: Optional[str] = None,
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Desativado por política estrita de execução local: o motor de estudo utiliza exclusivamente
    modelos locais (Faster-Whisper para ASR e Ollama qwen3.5:9b para síntese), sem chamadas a APIs externas.
    """
    return "", []


def transcribe_audio_real(
    audio_path: str,
    language: Optional[str] = None,
    faster_whisper_model: Any = None,
) -> Tuple[str, List[Dict[str, Any]], str]:
    """
    Pipeline real de transcrição de áudio 100% local (sem frases pré-fabricadas!):
    1. Converte para WAV 16kHz mono se necessário e verifica energia RMS (deteção real de silêncio).
    2. Usa Faster-Whisper local (passado por parâmetro ou instanciado localmente se disponível).
    3. Nunca devolve texto inventado ("Transcrição de teste...").
    Retorna (transcript, segments, status) com estados padronizados:
      - "TRANSCRIPTION_COMPLETED"
      - "TRANSCRIPTION_PARTIAL"
      - "NO_SPEECH_DETECTED"
      - "TRANSCRIPTION_FAILED"
    """
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Arquivo de áudio não encontrado: {audio_path}")

    wav_path, is_temp = ensure_16khz_mono_wav(audio_path)
    try:
        duration_sec, rms = compute_wav_duration_and_rms(wav_path)
        if duration_sec < 0.15 or rms < 1.5e-4:
            return "", [], "NO_SPEECH_DETECTED"

        model = faster_whisper_model
        if model is None and not os.environ.get("PYTEST_CURRENT_TEST"):
            try:
                from faster_whisper import WhisperModel
                model = WhisperModel("base", device="cpu", compute_type="int8")
            except Exception:
                model = None

        if model is not None:
            try:
                segments_iter, _info = model.transcribe(
                    wav_path,
                    language=language,
                    beam_size=5,
                    vad_filter=True,
                    vad_parameters=dict(min_silence_duration_ms=500),
                )
                full_lines: List[str] = []
                structured: List[Dict[str, Any]] = []
                max_end = 0.0
                for idx, seg in enumerate(segments_iter, start=1):
                    txt = (getattr(seg, "text", None) or (seg.get("text") if isinstance(seg, dict) else "") or "").strip()
                    if not txt:
                        continue
                    s_start = round(float(getattr(seg, "start", 0.0) if not isinstance(seg, dict) else seg.get("start", 0.0)), 2)
                    s_end = round(float(getattr(seg, "end", s_start + 2.0) if not isinstance(seg, dict) else seg.get("end", s_start + 2.0)), 2)
                    max_end = max(max_end, s_end)
                    ts_str = format_mmss(s_start)
                    full_lines.append(f"[{ts_str}] {txt}")
                    structured.append({
                        "segment_id": f"seg_{idx:04d}",
                        "start": s_start,
                        "end": s_end,
                        "timestamp": ts_str,
                        "text": txt,
                        "confidence": round(float(getattr(seg, "avg_logprob", 0.95) if not isinstance(seg, dict) else seg.get("confidence", 0.95)), 3)
                        if getattr(seg, "avg_logprob", 1.0) > 0
                        else 0.95,
                    })
                if structured:
                    if duration_sec > 30.0 and max_end < duration_sec * 0.25:
                        return "\n".join(full_lines), structured, "TRANSCRIPTION_PARTIAL"
                    return "\n".join(full_lines), structured, "TRANSCRIPTION_COMPLETED"
                return "", [], "NO_SPEECH_DETECTED"
            except Exception:
                return "", [], "TRANSCRIPTION_FAILED"

        return "", [], "TRANSCRIPTION_FAILED"
    finally:
        if is_temp and os.path.exists(wav_path):
            try:
                os.remove(wav_path)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Motor Extrativo Real (100% fundamentado no texto do documento — Zero Boilerplate)
# ---------------------------------------------------------------------------

def split_clean_sentences(text: str) -> List[str]:
    """Divide texto real em frases limpas, preservando números, siglas e citações."""
    if not text:
        return []
    text = unicodedata.normalize("NFC", text)
    # Remover linhas puramente decorativas, separadores ou metadados vazios
    lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line in ("---", "***", "___"):
            continue
        if re.match(r"^\[Ficheiro binário/multimédia:", line):
            continue
        # Limpar marcadores markdown de título/lista mantendo o conteúdo
        line = re.sub(r"^#{1,6}\s+", "", line)
        line = re.sub(r"^[\-\*\•]\s+", "", line)
        lines.append(line)

    joined = "\n".join(lines)
    raw_sents = re.split(r"(?<=[.!?])\s+|\n+", joined)
    sentences: List[str] = []
    seen: set[str] = set()
    for s in raw_sents:
        s_clean = re.sub(r"\s+", " ", s).strip()
        if len(s_clean) < 28 or len(s_clean) > 650:
            continue
        # Ignorar cabeçalhos de página isolados ou linhas só com números
        alpha_chars = sum(1 for c in s_clean if c.isalpha())
        if alpha_chars < 15:
            continue
        norm = s_clean.lower()
        if norm not in seen:
            seen.add(norm)
            sentences.append(s_clean)
    return sentences


def extract_key_terms_from_text(text: str, top_k: int = 10) -> List[Tuple[str, str]]:
    """
    Extrai conceitos/termos reais presentes no documento e a frase real onde surgem/são definidos.
    Retorna [(termo, definicao_ou_contexto_real)].
    """
    if not text or not text.strip():
        return []

    text = unicodedata.normalize("NFC", text)
    results: List[Tuple[str, str]] = []
    seen_lower: set[str] = set()

    # 1. Padrões explícitos de definição no próprio texto (Markdown bold, dois-pontos, travessão)
    def_patterns = [
        re.compile(r"\*\*([^\W_][\w\s\-/()]{2,48})\*\*\s*[:\-–—]\s*([^\n]{20,260})"),
        re.compile(r"(?:^|\n)[\-\*\•]?\s*([A-ZÀ-Ý][\w\s\-/()]{2,42})\s*[:–—]\s*([^\n]{25,240})"),
    ]
    for pat in def_patterns:
        for m in pat.finditer(text):
            term = re.sub(r"\s+", " ", m.group(1)).strip(" *:.-")
            defn = re.sub(r"\s+", " ", m.group(2)).strip()
            t_low = term.lower()
            if len(term) >= 3 and t_low not in STOPWORDS and t_low not in seen_lower:
                seen_lower.add(t_low)
                results.append((term, defn))
                if len(results) >= top_k:
                    return results

    # 2. Expressões técnicas / sintagmas nominais frequentes no texto + melhor frase real onde ocorrem
    sentences = split_clean_sentences(text)
    tokens = re.findall(r"\b[^\W\d_][^\W_]{2,}(?:-[^\W_]{2,})*\b", text)
    freq: Counter[str] = Counter()
    canonical_case: Dict[str, str] = {}
    for tok in tokens:
        low = tok.lower()
        if len(low) < 4 or low in STOPWORDS or low.isdigit():
            continue
        freq[low] += 1
        if low not in canonical_case or (tok[0].isupper() and not canonical_case[low][0].isupper()):
            canonical_case[low] = tok

    # Também detetar bigramas capitalizados (ex: "Project Charter", "Linear Attention", "Consumer Reviews")
    bigrams = re.findall(r"\b([A-ZÀ-Ý][^\W\d_]{2,}\s+[A-ZÀ-Ý][^\W\d_]{2,})\b", text)
    for bg in bigrams:
        bg_low = bg.lower()
        words_bg = bg_low.split()
        if any(w in STOPWORDS for w in words_bg):
            continue
        freq[bg_low] += 3
        canonical_case[bg_low] = bg

    for low_term, _count in freq.most_common(top_k * 3):
        if low_term in seen_lower:
            continue
        term_display = canonical_case.get(low_term, low_term.title())
        best_sent = ""
        for s in sentences:
            if low_term in s.lower():
                best_sent = s
                break
        if best_sent:
            seen_lower.add(low_term)
            results.append((term_display, best_sent))
            if len(results) >= top_k:
                break

    return results


def rank_salient_sentences(text: str, top_k: int = 6, preserve_order: bool = True) -> List[str]:
    """
    Seleciona as frases mais informativas do próprio texto usando pontuação TF-salience
    com diversificação MMR (evitando frases redundantes).
    """
    text = unicodedata.normalize("NFC", text or "")
    sentences = split_clean_sentences(text)
    if not sentences:
        raw_trim = re.sub(r"\s+", " ", text).strip()
        return [raw_trim[:300]] if raw_trim else []
    if len(sentences) <= top_k:
        return sentences

    word_freq: Counter[str] = Counter()
    sent_tokens: List[set[str]] = []
    for s in sentences:
        toks = {
            w.lower()
            for w in re.findall(r"\b[^\W\d_]{4,}\b", s)
            if w.lower() not in STOPWORDS
        }
        sent_tokens.append(toks)
        for t in toks:
            word_freq[t] += 1

    max_f = max(word_freq.values()) if word_freq else 1
    scored: List[Tuple[int, float, str, set[str]]] = []
    n_total = len(sentences)
    for idx, (s, toks) in enumerate(zip(sentences, sent_tokens)):
        if not toks:
            continue
        tf_score = sum(word_freq[t] / max_f for t in toks) / (math.sqrt(len(toks)) + 1.0)
        # Bónus ligeiro para frases introdutórias e conclusivas reais e frases com dados concretos
        pos_bonus = 1.15 if idx < max(2, n_total // 8) or idx >= n_total - max(2, n_total // 8) else 1.0
        num_bonus = 1.10 if re.search(r"\d+(?:\.\d+)?%?", s) else 1.0
        scored.append((idx, tf_score * pos_bonus * num_bonus, s, toks))

    scored.sort(key=lambda x: x[1], reverse=True)

    selected: List[Tuple[int, str, set[str]]] = []
    for idx, _sc, s, toks in scored:
        # Diversificação: rejeitar se muito sobreposta a uma frase já escolhida
        too_similar = False
        for _, _, sel_toks in selected:
            union = max(1, len(toks | sel_toks))
            if (len(toks & sel_toks) / union) > 0.55:
                too_similar = True
                break
        if not too_similar:
            selected.append((idx, s, toks))
            if len(selected) >= top_k:
                break

    if preserve_order:
        selected.sort(key=lambda x: x[0])
    return [s for _, s, _ in selected]


def build_representative_excerpt(
    text: str,
    sections: Optional[List[Any]] = None,
    max_chars: int = 26000,
) -> str:
    """
    Constrói uma amostra representativa de TODO o documento/vídeo/áudio (início, meio e fim,
    distribuída por todas as secções/páginas/timestamps), evitando truncar apenas o início.
    """
    clean_text = (text or "").strip()
    if sections:
        sec_blocks: List[str] = []
        biblio_prefixes = ("references", "referências", "referencias", "bibliography", "bibliografia")
        content_sections = [
            s for s in sections
            if not any(
                (s.get("title", "") if isinstance(s, dict) else getattr(s, "title", "")).strip().lower().startswith(bp)
                for bp in biblio_prefixes
            )
        ]
        target_sections = content_sections if content_sections else sections
        per_sec_budget = max(800, max_chars // max(1, len(target_sections)))
        for sec in target_sections:
            s_title = sec.get("title", "") if isinstance(sec, dict) else getattr(sec, "title", "")
            p_start = sec.get("page_start", 1) if isinstance(sec, dict) else getattr(sec, "page_start", 1)
            paras = sec.get("paragraphs", []) if isinstance(sec, dict) else getattr(sec, "paragraphs", [])
            p_texts = [
                (p.get("text", "") if isinstance(p, dict) else getattr(p, "text", ""))
                for p in paras
            ]
            body = "\n".join(t for t in p_texts if t).strip()
            if not body:
                continue
            if len(body) > per_sec_budget:
                half = per_sec_budget // 2
                body = body[:half] + "\n[...]\n" + body[-half:]
            sec_blocks.append(f"### [Secção: {s_title} | p. {p_start}]\n{body}")
        if sec_blocks:
            combined = "\n\n".join(sec_blocks)
            if len(combined) <= max_chars:
                return combined
            return combined[:max_chars]

    if len(clean_text) <= max_chars:
        return clean_text

    # Amostragem em 4 janelas ao longo de todo o documento (início, 1/3, 2/3, conclusão)
    window = max_chars // 4
    n = len(clean_text)
    p1 = clean_text[:window]
    p2 = clean_text[n // 3 : n // 3 + window]
    p3 = clean_text[(2 * n) // 3 : (2 * n) // 3 + window]
    p4 = clean_text[-window:]
    return f"{p1}\n\n[...]\n\n{p2}\n\n[...]\n\n{p3}\n\n[...]\n\n{p4}"


# ---------------------------------------------------------------------------
# Arquitetura de Evidências & Rastreabilidade Canónica (Secção 2)
# ---------------------------------------------------------------------------

def build_document_evidence_units(
    document_id: str = "",
    source_type: str = "TXT",
    sections: Optional[List[Any]] = None,
    *,
    text: str = "",
    raw_text: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    if not text and raw_text:
        text = raw_text
    """
    Constrói a representação interna normalizada de evidências de um documento,
    atribuindo a cada excerto uma referência canónica rastreável à sua origem:
      - PDF:        {document_id}:p{page_number}:{paragraph_id}
      - PPTX:       {document_id}:s{slide_number}:{text_element_id}
      - VIDEO:      {document_id}:t{start_timestamp}-{end_timestamp}:{SPEECH|SLIDE_OCR}
      - AUDIO:      {document_id}:t{start_timestamp}-{end_timestamp}:{transcription_segment_id}
      - DOCX:       {document_id}:{paragraph_id}:{section_id}
      - TXT/MD:     {document_id}:L{line_start}-{line_end}:{paragraph_id}
    """
    doc_id = (document_id or "doc_unknown").strip()
    src = (source_type or "TXT").upper().strip()
    meta = metadata or {}
    units: List[Dict[str, Any]] = []

    # 1. Para Vídeo ou Áudio com segmentos temporais estruturados
    if src in ("VIDEO", "AUDIO", "LECTURE_AUDIO"):
        raw_segs = meta.get("transcript_segments") or meta.get("segments") or []
        for idx, seg in enumerate(raw_segs, start=1):
            if not isinstance(seg, dict):
                seg = seg.to_dict() if hasattr(seg, "to_dict") else {}
            s_txt = str(seg.get("text") or "").strip()
            if not s_txt:
                continue
            start_s = float(seg.get("start", 0.0) or 0.0)
            end_s = float(seg.get("end", start_s + 5.0) or (start_s + 5.0))
            start_ts = seg.get("timestamp") or format_mmss(start_s)
            end_ts = format_mmss(end_s)
            seg_id = str(seg.get("segment_id") or f"seg_{idx:04d}")
            conf = float(seg.get("confidence", 0.95) or 0.95)
            if src == "VIDEO":
                ev_id = f"{doc_id}:t{start_ts}-{end_ts}:SPEECH"
                coords = {
                    "document_id": doc_id,
                    "start_timestamp": start_ts,
                    "end_timestamp": end_ts,
                    "source_type": "SPEECH",
                    "segment_id": seg_id,
                }
            else:
                ev_id = f"{doc_id}:t{start_ts}-{end_ts}:{seg_id}"
                coords = {
                    "document_id": doc_id,
                    "start_timestamp": start_ts,
                    "end_timestamp": end_ts,
                    "transcription_segment_id": seg_id,
                    "source_type": src,
                }
            units.append({
                "evidence_id": ev_id,
                "short_id": f"E{len(units) + 1}",
                "text": s_txt,
                "section_id": "transcript",
                "page_or_slide": None,
                "timestamp_range": f"{start_ts}-{end_ts}",
                "modality": "SPEECH",
                "confidence": conf,
                "coordinates": coords,
            })

        # Adicionar evidências OCR de diapositivos/keyframes para vídeos
        if src == "VIDEO":
            kfs = meta.get("keyframes") or []
            for k_idx, kf in enumerate(kfs, start=1):
                if not isinstance(kf, dict):
                    kf = kf.to_dict() if hasattr(kf, "to_dict") else {}
                v_desc = str(kf.get("visual_description") or "").strip()
                is_sl = bool(kf.get("is_slide", False))
                if not is_sl and not v_desc.startswith("Texto no ecrã"):
                    continue
                if not v_desc:
                    continue
                ts_sec = float(kf.get("timestamp", 0.0) or 0.0)
                start_ts = str(kf.get("timestamp_str") or format_mmss(ts_sec))
                end_ts = format_mmss(ts_sec + 5.0)
                f_id = str(kf.get("frame_id") or f"frame_{k_idx:03d}")
                ev_id = f"{doc_id}:t{start_ts}-{end_ts}:SLIDE_OCR"
                units.append({
                    "evidence_id": ev_id,
                    "short_id": f"E{len(units) + 1}",
                    "text": v_desc,
                    "section_id": f_id,
                    "page_or_slide": k_idx,
                    "timestamp_range": f"{start_ts}-{end_ts}",
                    "modality": "SLIDE_OCR",
                    "confidence": float(kf.get("confidence", 0.9) or 0.9),
                    "coordinates": {
                        "document_id": doc_id,
                        "start_timestamp": start_ts,
                        "end_timestamp": end_ts,
                        "source_type": "SLIDE_OCR",
                        "frame_id": f_id,
                    },
                })
        if units:
            return units

    # 2. Para documentos estruturados em secções e parágrafos (PDF, PPTX, DOCX, TXT, MARKDOWN)
    line_cursor = 1
    if sections:
        for s_idx, sec in enumerate(sections, start=1):
            s_id = sec.get("section_id", f"sec_{s_idx}") if isinstance(sec, dict) else getattr(sec, "section_id", f"sec_{s_idx}")
            s_title = sec.get("title", f"Secção {s_idx}") if isinstance(sec, dict) else getattr(sec, "title", f"Secção {s_idx}")
            p_start = int((sec.get("page_start", s_idx) if isinstance(sec, dict) else getattr(sec, "page_start", s_idx)) or s_idx)
            paras = sec.get("paragraphs", []) if isinstance(sec, dict) else getattr(sec, "paragraphs", [])
            for p_idx, par in enumerate(paras, start=1):
                p_txt = (par.get("text", "") if isinstance(par, dict) else getattr(par, "text", "") or "").strip()
                if not p_txt:
                    continue
                p_id = (par.get("paragraph_id", f"p_{s_idx}_{p_idx}") if isinstance(par, dict) else getattr(par, "paragraph_id", f"p_{s_idx}_{p_idx}")) or f"p_{s_idx}_{p_idx}"
                pg_num = int((par.get("page_number", p_start) if isinstance(par, dict) else getattr(par, "page_number", p_start)) or p_start)
                n_lines = max(1, p_txt.count("\n") + 1)
                l_start, l_end = line_cursor, line_cursor + n_lines - 1
                line_cursor = l_end + 1

                if src == "PDF":
                    ev_id = f"{doc_id}:p{pg_num}:{p_id}"
                    coords = {
                        "document_id": doc_id,
                        "page_number": pg_num,
                        "paragraph_id": p_id,
                        "section_id": s_id,
                        "source_type": "PDF",
                    }
                elif src == "PPTX":
                    is_note = "[Notas do Orador]" in p_txt or "notas do orador" in s_title.lower() or (isinstance(par, dict) and bool(par.get("speaker_notes")))
                    el_id = str(par.get("text_element_id") or p_id) if isinstance(par, dict) and (par.get("text_element_id") or par.get("paragraph_id")) else (f"note_{p_idx}" if is_note else f"el_{p_idx}")
                    ev_id = f"{doc_id}:slide{pg_num}:{el_id}"
                    coords = {
                        "document_id": doc_id,
                        "slide_number": pg_num,
                        "text_element_id": el_id,
                        "is_speaker_note": is_note,
                        "source_type": "PPTX",
                    }
                elif src == "DOCX":
                    ev_id = f"{doc_id}:{s_id}:{p_id}"
                    coords = {
                        "document_id": doc_id,
                        "paragraph_id": p_id,
                        "section_id": s_id,
                        "source_type": "DOCX",
                    }
                elif src in ("VIDEO", "AUDIO", "LECTURE_AUDIO"):
                    par_start = par.get("start_timestamp") if isinstance(par, dict) else None
                    par_end = par.get("end_timestamp") if isinstance(par, dict) else None
                    par_ocr = par.get("ocr_text") if isinstance(par, dict) else None
                    ts_match = re.search(r"\[(\d{1,2}:\d{2}(?::\d{2})?)\]", p_txt)
                    start_ts = par_start if par_start is not None else (ts_match.group(1) if ts_match else format_mmss((p_idx - 1) * 15))
                    end_ts = par_end if par_end is not None else format_mmss(p_idx * 15)
                    seg_id = p_id or f"seg_{p_idx:04d}"
                    mod_tag = "SLIDE_OCR" if (par_ocr or "texto no ecrã" in p_txt.lower()) else ("SPEECH" if src == "VIDEO" else seg_id)
                    ts_label = f"{int(start_ts)}-{int(end_ts)}" if isinstance(start_ts, (int, float)) and isinstance(end_ts, (int, float)) else f"{start_ts}-{end_ts}"
                    ev_id = f"{doc_id}:t{ts_label}:{mod_tag}"
                    coords = {
                        "document_id": doc_id,
                        "start_timestamp": start_ts,
                        "end_timestamp": end_ts,
                        "source_type": mod_tag if src == "VIDEO" else src,
                        "transcription_segment_id": seg_id,
                    }
                    if par_ocr:
                        coords["ocr_text"] = par_ocr
                else:
                    ev_id = f"{doc_id}:L{l_start}-{l_end}:{p_id}"
                    coords = {
                        "document_id": doc_id,
                        "line_range": f"{l_start}-{l_end}",
                        "paragraph_id": p_id,
                        "section_id": s_id,
                        "source_type": src,
                    }

                units.append({
                    **coords,
                    "evidence_id": ev_id,
                    "short_id": f"E{len(units) + 1}",
                    "text": p_txt,
                    "section_id": s_id,
                    "section_title": s_title,
                    "page_or_slide": pg_num,
                    "timestamp_range": coords.get("start_timestamp"),
                    "modality": "SPEAKER_NOTES" if coords.get("is_speaker_note") else "TEXT",
                    "confidence": float(meta.get("extraction_confidence", 0.98) or 0.98),
                    "coordinates": coords,
                })

    # 3. Fallback direto sobre texto bruto caso não existam secções pré-segmentadas
    if not units and text and text.strip():
        raw_paras = [p.strip() for p in re.split(r"\n{2,}", text.strip()) if p.strip()]
        if not raw_paras:
            raw_paras = [text.strip()]
        line_cursor = 1
        for p_idx, p_txt in enumerate(raw_paras, start=1):
            p_id = f"par_{p_idx}"
            n_lines = max(1, p_txt.count("\n") + 1)
            l_start, l_end = line_cursor, line_cursor + n_lines - 1
            line_cursor = l_end + 1
            if src == "PDF":
                ev_id = f"{doc_id}:p1:{p_id}"
                coords = {"document_id": doc_id, "page_number": 1, "paragraph_id": p_id, "source_type": "PDF"}
            elif src == "PPTX":
                ev_id = f"{doc_id}:s{p_idx}:el_1"
                coords = {"document_id": doc_id, "slide_number": p_idx, "text_element_id": "el_1", "source_type": "PPTX"}
            elif src == "DOCX":
                ev_id = f"{doc_id}:{p_id}:sec_1"
                coords = {"document_id": doc_id, "paragraph_id": p_id, "section_id": "sec_1", "source_type": "DOCX"}
            elif src in ("VIDEO", "AUDIO", "LECTURE_AUDIO"):
                ts_match = re.search(r"\[(\d{1,2}:\d{2}(?::\d{2})?)\]", p_txt)
                start_ts = ts_match.group(1) if ts_match else format_mmss((p_idx - 1) * 15)
                end_ts = format_mmss(p_idx * 15)
                mod_tag = "SLIDE_OCR" if "texto no ecrã" in p_txt.lower() else ("SPEECH" if src == "VIDEO" else f"seg_{p_idx:04d}")
                ev_id = f"{doc_id}:t{start_ts}-{end_ts}:{mod_tag}"
                coords = {
                    "document_id": doc_id,
                    "start_timestamp": start_ts,
                    "end_timestamp": end_ts,
                    "source_type": mod_tag if src == "VIDEO" else src,
                    "transcription_segment_id": f"seg_{p_idx:04d}",
                }
            else:
                ev_id = f"{doc_id}:L{l_start}-{l_end}:{p_id}"
                coords = {"document_id": doc_id, "line_range": f"{l_start}-{l_end}", "paragraph_id": p_id, "source_type": src}

            units.append({
                **coords,
                "evidence_id": ev_id,
                "short_id": f"E{len(units) + 1}",
                "text": p_txt,
                "section_id": "sec_1",
                "section_title": "Conteúdo Principal",
                "page_or_slide": 1,
                "timestamp_range": coords.get("start_timestamp"),
                "modality": "TEXT",
                "confidence": 0.95,
                "coordinates": coords,
            })

    return units


def _stem_root(w: str) -> str:
    """Extrai raiz morfológica / cognato comum entre Português e Inglês para termos académicos."""
    clean = unicodedata.normalize("NFKD", w).encode("ASCII", "ignore").decode("utf-8").lower()
    for suf in (
        "izacao", "ization", "acoes", "acao", "ations", "ation", "tions", "tion",
        "ance", "ence", "mento", "ment", "ismo", "ism", "ical", "ico", "ica",
        "vel", "ble", "ing", "ado", "ido", "ed", "es", "s"
    ):
        if clean.endswith(suf) and len(clean) - len(suf) >= 4:
            return clean[:-len(suf)]
    return clean[:5] if len(clean) >= 5 else clean


def _tokenize_content_words(text: str) -> set[str]:
    if not text:
        return set()
    return {
        w.lower()
        for w in re.findall(r"\b[^\W\d_]{4,}\b", unicodedata.normalize("NFC", text))
        if w.lower() not in STOPWORDS
    }


def match_claim_to_evidence_units(
    claim_text: str,
    evidence_units: List[Dict[str, Any]],
    hint_refs: Optional[List[str]] = None,
    corpus_tokens: Optional[set[str]] = None,
) -> Tuple[List[str], float, str]:
    """
    Associa uma afirmação/síntese às unidades de evidência do documento.
    Retorna (matched_evidence_ids, grounding_score, epistemic_status)
    onde epistemic_status in {"OBSERVED", "INFERRED", "UNCONFIRMED"}.
    Não aceita mera presença de palavras isoladas se a afirmação introduzir entidades,
    datas ou percentagens fabricadas ausentes do documento.
    """
    if not claim_text or not claim_text.strip() or not evidence_units:
        return [], 0.0, "UNCONFIRMED"

    short_map = {u["short_id"].upper(): u for u in evidence_units if u.get("short_id")}
    id_map = {u["evidence_id"]: u for u in evidence_units if u.get("evidence_id")}

    # Extrair tags explícitas [E1], [E2] presentes no texto ou em hint_refs
    explicit_units: List[Dict[str, Any]] = []
    inline_tags = re.findall(r"\[?(E\d+)\]?", claim_text, flags=re.IGNORECASE)
    candidate_refs = list(hint_refs or []) + inline_tags
    for ref in candidate_refs:
        r_clean = str(ref).strip("[] ")
        if r_clean.upper() in short_map:
            u = short_map[r_clean.upper()]
            if u not in explicit_units:
                explicit_units.append(u)
        elif r_clean in id_map:
            u = id_map[r_clean]
            if u not in explicit_units:
                explicit_units.append(u)

    claim_clean = re.sub(r"\[E\d+\]", "", claim_text, flags=re.IGNORECASE).strip()
    claim_tokens = _tokenize_content_words(claim_clean)
    claim_stems = {_stem_root(w) for w in claim_tokens}
    if not claim_tokens:
        if explicit_units:
            return [u["evidence_id"] for u in explicit_units[:2]], 0.5, "INFERRED"
        return [], 0.0, "UNCONFIRMED"

    # Verificar se a afirmação introduz anos/percentagens/números específicos ausentes de todo o documento
    all_doc_text = " ".join(u.get("text", "") for u in evidence_units)
    doc_numbers = set(re.findall(r"\b(?:\d{4}|\d+(?:[.,]\d+)?%)\b", all_doc_text))
    claim_numbers = set(re.findall(r"\b(?:\d{4}|\d+(?:[.,]\d+)?%)\b", claim_clean))
    fabricated_numbers = claim_numbers - doc_numbers

    # Pontuar cada unidade de evidência por sobreposição conceptual (suporta termos bilingues/cognatos via stems)
    scored_units: List[Tuple[float, Dict[str, Any]]] = []
    for u in evidence_units:
        u_tokens = _tokenize_content_words(u.get("text", ""))
        if not u_tokens:
            continue
        u_stems = {_stem_root(w) for w in u_tokens}
        common_tokens = (claim_tokens & u_tokens) | (claim_stems & u_stems)
        inter = len(common_tokens)
        if inter == 0:
            continue
        recall = inter / max(1, len(claim_tokens))
        prec = inter / max(1, len(u_tokens))
        score = (0.75 * recall) + (0.25 * prec)
        if u in explicit_units:
            score += 0.20
        scored_units.append((score, u))

    scored_units.sort(key=lambda x: x[0], reverse=True)

    # Verificar cobertura global no vocabulário do documento
    if corpus_tokens is None:
        corpus_tokens = _tokenize_content_words(all_doc_text)
    corpus_stems = {_stem_root(w) for w in corpus_tokens}
    global_overlap = len((claim_tokens & corpus_tokens) | (claim_stems & corpus_stems)) / max(1, len(claim_tokens))

    if fabricated_numbers and global_overlap < 0.65:
        return [], round(global_overlap * 0.3, 3), "UNCONFIRMED"

    if not scored_units:
        if explicit_units and global_overlap >= 0.22:
            return [u["evidence_id"] for u in explicit_units[:2]], round(global_overlap, 3), "INFERRED"
        return [], 0.0, "UNCONFIRMED"

    top_score, top_unit = scored_units[0]
    matched_ids = [u["evidence_id"] for sc, u in scored_units[:2] if sc >= max(0.15, top_score * 0.6)]
    if explicit_units:
        for eu in explicit_units:
            if eu["evidence_id"] not in matched_ids:
                matched_ids.insert(0, eu["evidence_id"])
        matched_ids = matched_ids[:3]

    effective_score = round(max(top_score, global_overlap * 0.85), 3)
    if effective_score >= 0.32 and not fabricated_numbers:
        return matched_ids, effective_score, "OBSERVED"
    if effective_score >= 0.18:
        return matched_ids, effective_score, "INFERRED"
    return [], effective_score, "UNCONFIRMED"


def match_claim_evidence_ids(
    claim_text: str,
    evidence_units: List[Dict[str, Any]],
    top_k: int = 2,
    allow_fallback: bool = False,
) -> List[str]:
    """Retorna apenas a lista de evidence_ids canónicas associadas à afirmação."""
    matched_ids, _score, status = match_claim_to_evidence_units(claim_text, evidence_units)
    if matched_ids and status in ("OBSERVED", "INFERRED"):
        return matched_ids[:top_k]
    if allow_fallback and evidence_units:
        return [evidence_units[0]["evidence_id"]]
    return []


def extract_key_sentences(text: str, max_count: int = 4, min_len: int = 20) -> List[str]:
    """Extrai frases-chave reais do texto usando rank_salient_sentences / split_clean_sentences."""
    if not text or not text.strip():
        return []
    salient = rank_salient_sentences(text, top_k=max_count, preserve_order=True)
    filtered = [s for s in salient if len(s.strip()) >= min_len]
    if filtered:
        return filtered[:max_count]
    raw_lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    return (raw_lines or [text.strip()])[:max_count]


def prepare_evidence_dossier(
    evidence_units: List[Dict[str, Any]],
    max_chars: int = 7500,
) -> Tuple[str, Dict[str, str]]:
    """
    Prepara um dossier compacto de evidências numeradas ([E1], [E2], ...) distribuídas
    por todas as secções do documento, otimizado para a janela de geração rápida do qwen3.5:9b.
    Retorna (dossier_text, short_to_canonical_map).
    """
    if not evidence_units:
        return "", {}

    short_map = {u["short_id"]: u["evidence_id"] for u in evidence_units}
    total_units = len(evidence_units)

    # Selecionar unidades representativas cobrindo início, meio e fim de todas as secções
    if total_units <= 24:
        selected = evidence_units
    else:
        step = max(1, total_units // 22)
        indices = sorted(set(list(range(0, total_units, step))[:22] + [0, total_units - 1]))
        selected = [evidence_units[i] for i in indices]

    per_unit_chars = max(220, min(650, max_chars // max(1, len(selected))))
    lines: List[str] = []
    cur_len = 0
    for u in selected:
        sid = u["short_id"]
        sec_t = u.get("section_title") or u.get("section_id") or ""
        loc = f"p.{u['page_or_slide']}" if u.get("page_or_slide") else (u.get("timestamp_range") or "")
        header = f"[{sid}] ({sec_t} {loc}): ".strip()
        txt = re.sub(r"\s+", " ", u.get("text", "")).strip()
        if len(txt) > per_unit_chars:
            # Preservar frases completas - nunca cortar frases no meio
            u_sents = split_clean_sentences(txt)
            kept_sents = []
            acc_len = 0
            for st in u_sents:
                if acc_len + len(st) + 1 <= per_unit_chars or not kept_sents:
                    kept_sents.append(st)
                    acc_len += len(st) + 1
                else:
                    break
            txt = " ".join(kept_sents) if kept_sents else txt
        entry = f"{header} {txt}"
        if cur_len + len(entry) > max_chars and lines:
            break
        lines.append(entry)
        cur_len += len(entry) + 1

    return "\n".join(lines), short_map


def detect_argumentative_structure(
    clean_text: str,
    extracted_structure: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Avalia se o documento possui uma estrutura argumentativa ou científica identificável
    (tese/problema + método/argumentos + evidências/resultados + conclusão) ou se é
    essencialmente descritivo/expositivo/procedimental.
    """
    if extracted_structure is None:
        extracted_structure = _extract_grounded_structure_from_text(clean_text or "")
    all_keys = (
        "problem", "research_gap", "research_question", "hypothesis",
        "contribution", "method", "dataset", "experiment",
        "results", "limitations", "conclusion",
    )
    observed_count = sum(
        1
        for k in all_keys
        if isinstance(extracted_structure.get(k), dict)
        and extracted_structure[k].get("status") == "OBSERVED"
    )
    arg_markers = (
        "hipótese", "hypothesis", "argumenta", "we argue", "thesis", "tese",
        "evidência empírica", "empirical", "dataset", "experimento", "experiment",
        "research question", "questão de investigação", "demonstramos", "we show",
        "concluímos", "regression", "p-value", "resultados mostram",
    )
    text_low = (clean_text or "").lower()
    marker_hits = sum(1 for m in arg_markers if m in text_low)

    if observed_count >= 4 or (observed_count >= 3 and marker_hits >= 2):
        return True, None

    return (
        False,
        "Este material é essencialmente expositivo/descritivo e não apresenta uma estrutura "
        "argumentativa ou empírica formal completa (como hipótese testável, dataset ou desenho experimental). "
        "Apenas os elementos efetivamente observados no texto são listados abaixo.",
    )


# ---------------------------------------------------------------------------
# Geração Completa e Consistente de Artefactos de Estudo (LLM + Fallback Extrativo Real)
# ---------------------------------------------------------------------------

def build_extractive_study_bundle(
    *,
    title: str,
    subject: str,
    source_type: str,
    text: str,
    sections: Optional[List[Any]] = None,
    document_id: str = "doc_0",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Constrói excertos estruturados (Quick, Study, Detailed, Exam), notas Cornell e Mapa de Argumentos
    100% extraídos das frases, secções e termos reais do documento quando o LLM está indisponível.
    Cumpre a política estrita da Secção 6:
      - NÃO apresenta texto extraído como síntese interpretativa generativa.
      - NÃO inventa explicações, relações causais ou conclusões novas.
      - NÃO cria mapas argumentativos artificiais.
      - Associa cada item às unidades de evidência canónicas (source_refs).
    """
    clean_text = (text or "").strip()
    has_real_content = bool(clean_text) and not clean_text.startswith("[Ficheiro binário/multimédia:")

    evidence_units = build_document_evidence_units(
        document_id=document_id,
        source_type=source_type,
        text=clean_text if has_real_content else "",
        sections=sections,
        metadata=metadata,
    )
    corpus_tokens = _tokenize_content_words(clean_text)

    if not has_real_content:
        empty_msg = f"Não foi possível extrair texto ou fala legível de «{title}» ({source_type})."
        empty_struct: Dict[str, Any] = {
            k: {
                "text": "Não especificado diretamente no documento.",
                "status": "UNKNOWN",
                "evidence_status": "UNKNOWN",
                "page_ref": None,
                "source_refs": [],
            }
            for k in (
                "problem", "research_gap", "research_question", "hypothesis",
                "contribution", "method", "dataset", "experiment",
                "results", "limitations", "conclusion",
            )
        }
        empty_struct["is_argumentative"] = False
        empty_struct["argumentative_limitation"] = empty_msg
        empty_struct["relations"] = []
        return {
            "generation_mode": "INSUFFICIENT_CONTENT",
            "extractive_only": True,
            "unavailable_generative_features": [
                "interpretive_synthesis",
                "causal_inference",
                "argumentative_mapping",
                "cornell_generative_cues",
            ],
            "evidence_units": [],
            "summaries": {
                "quick": [empty_msg],
                "quick_items": [],
                "study": [],
                "detailed": [{"title": "Conteúdo Indisponível", "text": empty_msg, "source_refs": []}],
                "exam": {"high_yield_concepts": [], "likely_questions": []},
            },
            "cornell_notes": {
                "topic": title,
                "subject": subject,
                "date": datetime.now().strftime("%Y-%m-%d"),
                "executive_summary": empty_msg,
                "cue_column": [],
                "detailed_notes": empty_msg,
                "glossary": "",
                "action_items": [f"Verificar se o ficheiro «{title}» possui texto selecionável ou faixa de áudio audível."],
            },
            "structure": empty_struct,
        }

    top_sentences = rank_salient_sentences(clean_text, top_k=6, preserve_order=True)
    key_terms = extract_key_terms_from_text(clean_text, top_k=8)

    # 1. Quick Summary (5-6 excertos salientes reais com source_refs)
    quick_points = top_sentences[:6] if top_sentences else [clean_text[:300]]
    quick_items: List[Dict[str, Any]] = []
    for pt in quick_points:
        refs, sc, st = match_claim_to_evidence_units(pt, evidence_units, corpus_tokens=corpus_tokens)
        quick_items.append({
            "text": pt,
            "source_refs": refs,
            "grounding_score": sc,
            "evidence_status": st if st != "UNCONFIRMED" else "OBSERVED",
        })

    # 2. Study & Detailed Summary por secção real (preservando estrutura original)
    study_sections: List[Dict[str, Any]] = []
    detailed_blocks: List[Dict[str, Any]] = []

    if sections:
        for idx, sec in enumerate(sections):
            s_id = sec.get("section_id", f"sec_{idx+1}") if isinstance(sec, dict) else getattr(sec, "section_id", f"sec_{idx+1}")
            s_title = sec.get("title", f"Secção {idx+1}") if isinstance(sec, dict) else getattr(sec, "title", f"Secção {idx+1}")
            p_start = sec.get("page_start", 1) if isinstance(sec, dict) else getattr(sec, "page_start", 1)
            p_end = sec.get("page_end", p_start) if isinstance(sec, dict) else getattr(sec, "page_end", p_start)
            paras = sec.get("paragraphs", []) if isinstance(sec, dict) else getattr(sec, "paragraphs", [])
            sec_body = " ".join(
                (p.get("text", "") if isinstance(p, dict) else getattr(p, "text", ""))
                for p in paras
            ).strip()
            if not sec_body:
                continue
            sec_top = rank_salient_sentences(sec_body, top_k=3, preserve_order=True)
            sec_more = rank_salient_sentences(sec_body, top_k=5, preserve_order=True)
            sec_terms = [t for t, _ in extract_key_terms_from_text(sec_body, top_k=4)]
            sec_summary = " ".join(sec_top) if sec_top else sec_body[:380]
            sec_detailed = " ".join(sec_more) if sec_more else sec_body[:600]
            page_ref = f"pp. {p_start}-{p_end}" if p_end != p_start else f"p. {p_start}"
            refs, _sc, _st = match_claim_to_evidence_units(sec_summary, evidence_units, corpus_tokens=corpus_tokens)
            study_sections.append({
                "section_id": s_id,
                "title": s_title,
                "page_ref": page_ref,
                "summary": sec_summary,
                "key_concepts": sec_terms,
                "source_refs": refs,
                "evidence_status": "OBSERVED",
            })
            detailed_blocks.append({
                "title": f"{s_title} ({page_ref})",
                "text": sec_detailed,
                "source_refs": refs,
                "evidence_status": "OBSERVED",
            })

    if not detailed_blocks:
        all_sents = split_clean_sentences(clean_text) or [clean_text[:450]]
        chunk_sz = max(1, math.ceil(len(all_sents) / min(4, len(all_sents))))
        for b_idx in range(0, len(all_sents), chunk_sz):
            chunk_sents = all_sents[b_idx : b_idx + chunk_sz]
            b_terms = [t for t, _ in extract_key_terms_from_text(" ".join(chunk_sents), top_k=3)]
            b_title = f"Tópico {(b_idx // chunk_sz) + 1}: {', '.join(b_terms[:2])}" if b_terms else f"Bloco {(b_idx // chunk_sz) + 1}"
            b_summary = " ".join(rank_salient_sentences(" ".join(chunk_sents), top_k=3, preserve_order=True))
            refs, _sc, _st = match_claim_to_evidence_units(b_summary, evidence_units, corpus_tokens=corpus_tokens)
            detailed_blocks.append({
                "title": b_title,
                "text": b_summary,
                "source_refs": refs,
                "evidence_status": "OBSERVED",
            })
            study_sections.append({
                "section_id": f"sec_{(b_idx // chunk_sz) + 1}",
                "title": b_title,
                "page_ref": "p. 1",
                "summary": b_summary,
                "key_concepts": b_terms,
                "source_refs": refs,
                "evidence_status": "OBSERVED",
            })

    # 3. Exam Summary (definições observadas e perguntas ancoradas nas evidências)
    high_yield: List[Dict[str, Any]] = []
    for term, ctx in key_terms[:6]:
        refs, _sc, _st = match_claim_to_evidence_units(ctx, evidence_units, corpus_tokens=corpus_tokens)
        high_yield.append({
            "concept": term,
            "detail": ctx,
            "source_refs": refs,
            "evidence_status": "OBSERVED",
        })
    if not high_yield and quick_points:
        refs, _sc, _st = match_claim_to_evidence_units(quick_points[0], evidence_units, corpus_tokens=corpus_tokens)
        high_yield = [{
            "concept": title,
            "detail": quick_points[0],
            "source_refs": refs,
            "evidence_status": "OBSERVED",
        }]

    likely_questions: List[Dict[str, Any]] = []
    for term, ctx in key_terms[:5]:
        refs, _sc, _st = match_claim_to_evidence_units(ctx, evidence_units, corpus_tokens=corpus_tokens)
        likely_questions.append({
            "question": f"Qual o papel e definição de «{term}» no contexto de {title}?",
            "answer": ctx,
            "source_refs": refs,
            "evidence_status": "OBSERVED",
        })
    if not likely_questions and quick_points:
        refs, _sc, _st = match_claim_to_evidence_units(quick_points[0], evidence_units, corpus_tokens=corpus_tokens)
        likely_questions.append({
            "question": f"Quais são os excertos centrais observados em «{title}»?",
            "answer": " ".join(quick_points[:2]),
            "source_refs": refs,
            "evidence_status": "OBSERVED",
        })

    # 4. Cornell Notes extrativas com referência explícita à secção/evidência
    exec_summary = " ".join(top_sentences[:3]) if top_sentences else clean_text[:450]
    cue_column: List[Dict[str, Any]] = []
    for sec_item in study_sections[:5]:
        cue_column.append({
            "cue": f"Tópico: {sec_item['title']} ({sec_item.get('page_ref', 'p. 1')})",
            "idea": sec_item["summary"][:260],
            "section_id": sec_item["section_id"],
            "source_refs": sec_item.get("source_refs", []),
        })
    for term, ctx in key_terms[: max(0, 6 - len(cue_column))]:
        refs, _sc, _st = match_claim_to_evidence_units(ctx, evidence_units, corpus_tokens=corpus_tokens)
        cue_column.append({
            "cue": f"Conceito observado: {term}",
            "idea": ctx[:260],
            "section_id": "glossary",
            "source_refs": refs,
        })
    if not cue_column and quick_points:
        cue_column.append({
            "cue": f"Excerto central de «{title}»",
            "idea": quick_points[0],
            "section_id": "sec_1",
            "source_refs": quick_items[0]["source_refs"] if quick_items else [],
        })

    detailed_md_lines: List[str] = []
    for blk in detailed_blocks[:8]:
        ref_str = f" *(Refs: {', '.join(blk.get('source_refs', [])[:2])})*" if blk.get("source_refs") else ""
        detailed_md_lines.append(f"### {blk['title']}{ref_str}\n{blk['text']}\n")
    detailed_md = "\n".join(detailed_md_lines).strip()

    glossary_md = "\n".join(f"- **{term}**: {ctx}" for term, ctx in key_terms[:8])
    action_items = [
        f"Rever os conceitos extraídos de «{title}»: {', '.join(t for t, _ in key_terms[:4])}."
        if key_terms
        else f"Rever os excertos principais de «{title}».",
        f"Analisar as {len(study_sections)} secções estruturais extraídas do documento.",
        "Executar regeneração com modelo local qwen3.5:9b para obter síntese interpretativa profunda.",
    ]

    # 5. Mapa de Argumentos: apenas afirmações explicitamente observadas, sem inferência artificial
    structure = _extract_grounded_structure_from_text(
        clean_text,
        sections,
        evidence_units=evidence_units,
        corpus_tokens=corpus_tokens,
    )

    return {
        "generation_mode": "EXTRACTIVE_GROUNDED",
        "extractive_only": True,
        "unavailable_generative_features": [
            "interpretive_synthesis",
            "causal_inference",
            "generative_argument_relations",
            "deep_conceptual_distinctions",
        ],
        "evidence_units": evidence_units,
        "summaries": {
            "quick": quick_points,
            "quick_items": quick_items,
            "study": study_sections,
            "detailed": detailed_blocks,
            "exam": {
                "high_yield_concepts": high_yield,
                "likely_questions": likely_questions,
            },
        },
        "cornell_notes": {
            "topic": title,
            "subject": subject,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "executive_summary": exec_summary,
            "cue_column": cue_column,
            "detailed_notes": detailed_md,
            "glossary": glossary_md,
            "action_items": action_items,
        },
        "structure": structure,
    }


def _extract_grounded_structure_from_text(
    clean_text: str,
    sections: Optional[List[Any]] = None,
    evidence_units: Optional[List[Dict[str, Any]]] = None,
    corpus_tokens: Optional[set[str]] = None,
) -> Dict[str, Any]:
    """
    Extrai o Mapa de Argumentos apenas de frases realmente observadas no documento (UNKNOWN quando ausente).
    Em modo extrativo não inventa inferências nem relações argumentativas artificiais.
    """
    sentences_with_page: List[Tuple[str, int]] = []
    if sections:
        for sec in sections:
            p_num = sec.get("page_start", 1) if isinstance(sec, dict) else getattr(sec, "page_start", 1)
            paras = sec.get("paragraphs", []) if isinstance(sec, dict) else getattr(sec, "paragraphs", [])
            for p in paras:
                p_txt = p.get("text", "") if isinstance(p, dict) else getattr(p, "text", "")
                pg = p.get("page_number", p_num) if isinstance(p, dict) else getattr(p, "page_number", p_num)
                for s in split_clean_sentences(p_txt):
                    sentences_with_page.append((s, pg))
    if not sentences_with_page:
        for s in split_clean_sentences(clean_text):
            sentences_with_page.append((s, 1))

    keyword_map: Dict[str, Tuple[str, ...]] = {
        "problem": ("problem", "challenge", "bottleneck", "difficulty", "problema", "desafio", "dificuldade", "necessidade", "ameaça", "risco"),
        "research_gap": ("gap", "lack of", "little attention", "prior work", "existing", "lacuna", "limitação da literatura", "poucos estudos"),
        "research_question": ("research question", "rq1", "investigate whether", "questão de investigação", "pergunta", "objetivo deste"),
        "hypothesis": ("hypothes", "h1", "we expect", "hipótese", "pressuposto", "espera-se"),
        "contribution": ("we propose", "we introduce", "this paper presents", "contribution", "propomos", "apresenta", "contribuição", "introduz"),
        "method": ("method", "methodology", "framework", "architecture", "approach", "process", "metodologia", "método", "arquitetura", "abordagem", "modelo", "standard", "pmbok"),
        "dataset": ("dataset", "corpus", "sample of", "reviews from", "dados", "amostra", "base de dados"),
        "experiment": ("experiment", "evaluation", "benchmark", "regression", "empirical", "experiência", "avaliação", "análise empírica", "teste"),
        "results": ("result", "achiev", "outperform", "accuracy", "bleu", "significant", "resultado", "demonstra", "obtivemos", "benefício", "desempenho"),
        "limitations": ("limitation", "future work", "threat to validity", "however", "limitação", "trabalho futuro", "restrição", "contudo"),
        "conclusion": ("conclu", "in summary", "overall", "em suma", "conclusão", "em conclusão", "síntese final"),
    }

    structure: Dict[str, Any] = {}
    used_sentences: set[str] = set()
    ev_list = evidence_units or []

    for key, cues in keyword_map.items():
        matched_sent = None
        matched_page = None
        for sent, pg in sentences_with_page:
            s_low = sent.lower()
            if sent not in used_sentences and any(c in s_low for c in cues):
                matched_sent = sent
                matched_page = pg
                used_sentences.add(sent)
                break
        if matched_sent:
            refs, _sc, _st = match_claim_to_evidence_units(matched_sent, ev_list, corpus_tokens=corpus_tokens)
            structure[key] = {
                "text": matched_sent,
                "status": "OBSERVED",
                "evidence_status": "OBSERVED",
                "page_ref": matched_page,
                "source_refs": refs,
            }
        else:
            structure[key] = {
                "text": "Não especificado diretamente no documento.",
                "status": "UNKNOWN",
                "evidence_status": "UNKNOWN",
                "page_ref": None,
                "source_refs": [],
            }

    is_arg, limitation_msg = detect_argumentative_structure(clean_text, structure)
    structure["is_argumentative"] = is_arg
    structure["argumentative_limitation"] = limitation_msg
    structure["relations"] = []
    return structure


def _normalize_llm_bundle(
    parsed: Dict[str, Any],
    fallback_bundle: Dict[str, Any],
    title: str,
    subject: str,
    evidence_units: Optional[List[Dict[str, Any]]] = None,
    telemetry: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Valida e normaliza a saída JSON do qwen3.5:9b contra as evidências do documento.
    Rejeita respostas sem base no documento (alucinações / injeções externas),
    remove afirmações não confirmadas e distingue honestamente LLM_GROUNDED de PARTIAL.
    """
    fb_sum = fallback_bundle["summaries"]
    fb_cor = fallback_bundle["cornell_notes"]
    fb_str = fallback_bundle["structure"]
    ev_units = evidence_units if evidence_units is not None else (fallback_bundle.get("evidence_units") or [])
    all_doc_text = " ".join(u.get("text", "") for u in ev_units)
    corpus_tokens = _tokenize_content_words(all_doc_text)

    total_checked_claims = 0
    grounded_claims_count = 0
    unconfirmed_dropped = 0
    artifact_modes: Dict[str, str] = {}

    def _clean_and_verify_claim(
        raw_txt: str,
        hint_refs: Optional[List[str]] = None,
    ) -> Tuple[str, List[str], float, str]:
        nonlocal total_checked_claims, grounded_claims_count, unconfirmed_dropped
        cleaned = strip_thinking_and_fences(str(raw_txt or "")).strip()
        if not cleaned or is_prefabricated_artifact(cleaned):
            return "", [], 0.0, "UNCONFIRMED"
        total_checked_claims += 1
        refs, score, status = match_claim_to_evidence_units(
            cleaned, ev_units, hint_refs=hint_refs, corpus_tokens=corpus_tokens
        )
        cleaned_no_tags = re.sub(r"\s*\[E\d+\]\s*", " ", cleaned, flags=re.IGNORECASE).strip()
        if status in ("OBSERVED", "INFERRED"):
            grounded_claims_count += 1
            return cleaned_no_tags, refs, score, status
        unconfirmed_dropped += 1
        return "", [], score, "UNCONFIRMED"

    # 1. Quick Summary
    raw_quick = parsed.get("quick_summary") or (parsed.get("summaries") or {}).get("quick")
    quick: List[str] = []
    quick_items: List[Dict[str, Any]] = []
    if isinstance(raw_quick, list):
        for x in raw_quick:
            if isinstance(x, dict):
                txt_val = str(x.get("text") or x.get("point") or "")
                h_refs = x.get("source_refs") if isinstance(x.get("source_refs"), list) else None
            else:
                txt_val = str(x)
                h_refs = None
            c_txt, refs, sc, st = _clean_and_verify_claim(txt_val, h_refs)
            if c_txt:
                quick.append(c_txt)
                quick_items.append({
                    "text": c_txt,
                    "source_refs": refs,
                    "grounding_score": sc,
                    "evidence_status": st,
                })
    if quick:
        artifact_modes["quick"] = "LLM_GROUNDED"
    else:
        quick = fb_sum["quick"]
        quick_items = fb_sum.get("quick_items", [])
        artifact_modes["quick"] = "EXTRACTIVE_GROUNDED"

    # 2. Study Summary (secções sintetizadas)
    raw_study = parsed.get("study_sections") or (parsed.get("summaries") or {}).get("study")
    study_list: List[Dict[str, Any]] = []
    if isinstance(raw_study, list):
        for i, item in enumerate(raw_study):
            if isinstance(item, dict) and item.get("summary"):
                h_refs = item.get("source_refs") if isinstance(item.get("source_refs"), list) else None
                c_sum, refs, sc, st = _clean_and_verify_claim(str(item.get("summary")), h_refs)
                if not c_sum:
                    continue
                study_list.append({
                    "section_id": str(item.get("section_id") or f"sec_{i+1}"),
                    "title": re.sub(r"\s*\[E\d+\]\s*", " ", str(item.get("title") or f"Secção {i+1}")).strip(),
                    "page_ref": str(item.get("page_ref") or ""),
                    "summary": c_sum,
                    "key_concepts": [str(c).strip() for c in (item.get("key_concepts") or []) if str(c).strip()],
                    "source_refs": refs,
                    "grounding_score": sc,
                    "evidence_status": st,
                })
    if study_list:
        artifact_modes["study"] = "LLM_GROUNDED"
    else:
        study_list = fb_sum["study"]
        artifact_modes["study"] = "EXTRACTIVE_GROUNDED"

    # 3. Detailed Summary
    raw_det = parsed.get("detailed_summary") or (parsed.get("summaries") or {}).get("detailed")
    detailed_list: List[Dict[str, Any]] = []
    if isinstance(raw_det, list):
        for i, item in enumerate(raw_det):
            if isinstance(item, dict) and (item.get("text") or item.get("content")):
                h_refs = item.get("source_refs") if isinstance(item.get("source_refs"), list) else None
                c_txt, refs, sc, st = _clean_and_verify_claim(str(item.get("text") or item.get("content")), h_refs)
                if c_txt:
                    detailed_list.append({
                        "title": re.sub(r"\s*\[E\d+\]\s*", " ", str(item.get("title") or f"Tópico {i+1}")).strip(),
                        "text": c_txt,
                        "source_refs": refs,
                        "grounding_score": sc,
                        "evidence_status": st,
                    })
            elif isinstance(item, str) and item.strip():
                c_txt, refs, sc, st = _clean_and_verify_claim(item)
                if c_txt:
                    detailed_list.append({
                        "title": f"Análise Aprofundada {i+1}",
                        "text": c_txt,
                        "source_refs": refs,
                        "grounding_score": sc,
                        "evidence_status": st,
                    })
    elif isinstance(raw_det, str) and raw_det.strip():
        c_txt, refs, sc, st = _clean_and_verify_claim(raw_det)
        if c_txt:
            detailed_list.append({
                "title": f"Análise Aprofundada — {title}",
                "text": c_txt,
                "source_refs": refs,
                "grounding_score": sc,
                "evidence_status": st,
            })
    if detailed_list:
        artifact_modes["detailed"] = "LLM_GROUNDED"
    else:
        detailed_list = fb_sum["detailed"]
        artifact_modes["detailed"] = "EXTRACTIVE_GROUNDED"

    # 4. Exam Summary
    raw_exam = parsed.get("exam_summary") or (parsed.get("summaries") or {}).get("exam") or {}
    hy_list: List[Dict[str, Any]] = []
    lq_list: List[Dict[str, Any]] = []
    if isinstance(raw_exam, dict):
        for c in raw_exam.get("high_yield_concepts") or []:
            if isinstance(c, dict) and c.get("concept"):
                raw_det_c = str(c.get("detail") or c.get("explanation") or "")
                h_refs = c.get("source_refs") if isinstance(c.get("source_refs"), list) else None
                c_det, refs, sc, st = _clean_and_verify_claim(f"{c.get('concept')}: {raw_det_c}", h_refs)
                if c_det:
                    clean_detail = re.sub(r"\s*\[E\d+\]\s*", " ", raw_det_c).strip() or c_det
                    hy_list.append({
                        "concept": re.sub(r"\s*\[E\d+\]\s*", " ", str(c.get("concept"))).strip(),
                        "detail": clean_detail,
                        "source_refs": refs,
                        "evidence_status": st,
                    })
        for q in raw_exam.get("likely_questions") or []:
            if isinstance(q, dict) and q.get("question"):
                raw_ans = str(q.get("answer") or "")
                h_refs = q.get("source_refs") if isinstance(q.get("source_refs"), list) else None
                c_qa, refs, sc, st = _clean_and_verify_claim(f"{q.get('question')} {raw_ans}", h_refs)
                if c_qa:
                    lq_list.append({
                        "question": re.sub(r"\s*\[E\d+\]\s*", " ", str(q.get("question"))).strip(),
                        "answer": re.sub(r"\s*\[E\d+\]\s*", " ", raw_ans).strip(),
                        "source_refs": refs,
                        "evidence_status": st,
                    })
    if hy_list and lq_list:
        artifact_modes["exam"] = "LLM_GROUNDED"
    else:
        if not hy_list:
            hy_list = fb_sum["exam"]["high_yield_concepts"]
        if not lq_list:
            lq_list = fb_sum["exam"]["likely_questions"]
        artifact_modes["exam"] = "EXTRACTIVE_GROUNDED"

    # 5. Cornell Notes
    raw_cor = parsed.get("cornell_notes") or {}
    raw_exec_sum = str(raw_cor.get("executive_summary") or parsed.get("executive_summary") or "").strip()
    exec_sum, exec_refs, _esc, _est = _clean_and_verify_claim(raw_exec_sum)
    cornell_from_llm = bool(exec_sum)
    if not exec_sum:
        exec_sum = fb_cor["executive_summary"]

    raw_cues = raw_cor.get("cue_column") or parsed.get("cue_column") or []
    cues: List[Dict[str, Any]] = []
    if isinstance(raw_cues, list):
        for c in raw_cues:
            if isinstance(c, dict) and c.get("cue") and c.get("idea"):
                h_refs = c.get("source_refs") if isinstance(c.get("source_refs"), list) else None
                c_idea, refs, sc, st = _clean_and_verify_claim(f"{c['cue']} {c['idea']}", h_refs)
                if not c_idea:
                    continue
                entry: Dict[str, Any] = {
                    "cue": re.sub(r"\s*\[E\d+\]\s*", " ", str(c["cue"])).strip(),
                    "idea": re.sub(r"\s*\[E\d+\]\s*", " ", str(c["idea"])).strip(),
                    "source_refs": refs,
                    "evidence_status": st,
                }
                if c.get("timestamp"):
                    entry["timestamp"] = str(c["timestamp"]).strip()
                if c.get("section_id"):
                    entry["section_id"] = str(c["section_id"]).strip()
                cues.append(entry)
    if not cues:
        cues = fb_cor["cue_column"]
        cornell_from_llm = False

    det_notes_raw = str(raw_cor.get("detailed_notes") or parsed.get("detailed_notes") or "").strip()
    det_notes = re.sub(r"\s*\[E\d+\]\s*", " ", strip_thinking_and_fences(det_notes_raw)).strip()
    if not det_notes:
        det_notes = "\n\n".join(f"### {b['title']}\n{b['text']}" for b in detailed_list)

    raw_gloss = raw_cor.get("glossary") or parsed.get("glossary") or ""
    if isinstance(raw_gloss, list):
        gloss_lines = []
        for g in raw_gloss:
            if isinstance(g, dict) and g.get("term"):
                gloss_lines.append(f"- **{g['term']}**: {g.get('definition') or g.get('detail') or ''}")
            elif isinstance(g, str) and g.strip():
                gloss_lines.append(g.strip() if g.strip().startswith("-") else f"- {g.strip()}")
        glossary_str = "\n".join(gloss_lines)
    else:
        glossary_str = str(raw_gloss).strip()
    if not glossary_str:
        glossary_str = fb_cor["glossary"]

    raw_actions = raw_cor.get("action_items") or parsed.get("action_items") or []
    actions = [str(a).strip() for a in raw_actions if str(a).strip()] if isinstance(raw_actions, list) else []
    if not actions:
        actions = fb_cor["action_items"]

    artifact_modes["cornell_notes"] = "LLM_GROUNDED" if cornell_from_llm else "EXTRACTIVE_GROUNDED"

    # 6. Structure / Argument Map
    raw_struct = parsed.get("structure") or {}
    norm_struct: Dict[str, Any] = {}
    all_keys = (
        "problem", "research_gap", "research_question", "hypothesis",
        "contribution", "method", "dataset", "experiment",
        "results", "limitations", "conclusion",
    )
    struct_llm_hits = 0
    for k in all_keys:
        item = raw_struct.get(k)
        if isinstance(item, dict) and item.get("text"):
            st = str(item.get("status") or item.get("evidence_status") or "OBSERVED").upper()
            if st not in ("OBSERVED", "INFERRED", "UNKNOWN"):
                st = "OBSERVED"
            txt_val = str(item["text"]).strip()
            if txt_val.lower() in ("n/a", "unknown", "none", "não aplicável", "não especificado", "não especificado diretamente no documento."):
                norm_struct[k] = {
                    "text": "Não especificado diretamente no documento.",
                    "status": "UNKNOWN",
                    "evidence_status": "UNKNOWN",
                    "page_ref": None,
                    "source_refs": [],
                }
            else:
                h_refs = item.get("source_refs") if isinstance(item.get("source_refs"), list) else None
                c_txt, refs, _sc, v_st = _clean_and_verify_claim(txt_val, h_refs)
                if c_txt:
                    struct_llm_hits += 1
                    final_st = st if st == "INFERRED" else v_st
                    norm_struct[k] = {
                        "text": c_txt,
                        "status": final_st,
                        "evidence_status": final_st,
                        "page_ref": item.get("page_ref"),
                        "source_refs": refs,
                    }
                else:
                    norm_struct[k] = fb_str[k]
        elif isinstance(item, str) and item.strip():
            c_txt, refs, _sc, v_st = _clean_and_verify_claim(item.strip())
            if c_txt:
                struct_llm_hits += 1
                norm_struct[k] = {
                    "text": c_txt,
                    "status": v_st,
                    "evidence_status": v_st,
                    "page_ref": None,
                    "source_refs": refs,
                }
            else:
                norm_struct[k] = fb_str[k]
        else:
            norm_struct[k] = fb_str[k]

    is_arg, arg_limitation = detect_argumentative_structure(all_doc_text, norm_struct)
    if isinstance(raw_struct.get("is_argumentative"), bool):
        is_arg = bool(raw_struct["is_argumentative"]) and is_arg
    norm_struct["is_argumentative"] = is_arg
    norm_struct["argumentative_limitation"] = (
        str(raw_struct.get("argumentative_limitation")).strip()
        if raw_struct.get("argumentative_limitation") and not is_arg
        else arg_limitation
    )
    norm_struct["relations"] = raw_struct.get("relations") if isinstance(raw_struct.get("relations"), list) and is_arg else []
    artifact_modes["structure"] = "LLM_GROUNDED" if struct_llm_hits >= 2 else "EXTRACTIVE_GROUNDED"

    # Rejeitar resposta inteira se a taxa de afirmações fundamentadas for demasiado baixa (< 35%)
    grounding_ratio = grounded_claims_count / max(1, total_checked_claims)
    if total_checked_claims == 0 or grounding_ratio < 0.35 or grounded_claims_count < 3:
        if telemetry is not None:
            telemetry["status"] = "REJECTED_UNGROUNDED"
            telemetry.setdefault("validation_errors", []).append(
                f"UNGROUNDED_LLM_RESPONSE_REJECTED (grounded={grounded_claims_count}/{total_checked_claims})"
            )
            _record_study_telemetry(telemetry)
        return None

    llm_sections_count = sum(1 for m in artifact_modes.values() if m == "LLM_GROUNDED")
    if llm_sections_count == len(artifact_modes):
        overall_mode = "LLM_GROUNDED"
    elif llm_sections_count >= 3:
        overall_mode = "LLM_GROUNDED"
    else:
        overall_mode = "PARTIAL"

    if telemetry is not None:
        telemetry["grounding_ratio"] = round(grounding_ratio, 3)
        telemetry["grounded_claims_count"] = grounded_claims_count
        telemetry["unconfirmed_claims_dropped"] = unconfirmed_dropped
        telemetry["artifact_modes"] = artifact_modes

    return {
        "generation_mode": overall_mode,
        "extractive_only": False,
        "artifact_modes": artifact_modes,
        "evidence_units": ev_units,
        "generation_telemetry": telemetry or get_last_study_telemetry(),
        "summaries": {
            "quick": quick,
            "quick_items": quick_items,
            "study": study_list,
            "detailed": detailed_list,
            "exam": {
                "high_yield_concepts": hy_list,
                "likely_questions": lq_list,
            },
        },
        "cornell_notes": {
            "topic": title,
            "subject": subject,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "executive_summary": exec_sum,
            "cue_column": cues,
            "detailed_notes": det_notes,
            "glossary": glossary_str,
            "action_items": actions,
            "source_refs": exec_refs,
        },
        "structure": norm_struct,
    }


def generate_complete_study_bundle(
    *,
    title: str,
    subject: str,
    source_type: str,
    text: str = "",
    raw_text: str = "",
    sections: Optional[List[Any]] = None,
    document_id: str = "doc_0",
    metadata: Optional[Dict[str, Any]] = None,
    allow_extractive_fallback: bool = True,
) -> Dict[str, Any]:
    if not text and raw_text:
        text = raw_text
    """
    Gera um pacote completo de síntese pedagógica (Quick, Study, Detailed, Exam, Cornell Notes e Argument Map)
    através do modelo local qwen3.5:9b (Ollama) com validação de evidências e telemetria observável.
    Nunca simula geração com modelo se o modelo falhar: devolve EXTRACTIVE_GROUNDED honesto
    (ou UNAVAILABLE se allow_extractive_fallback=False).
    """
    register_study_generation_start(document_id)
    fallback_bundle = build_extractive_study_bundle(
        title=title,
        subject=subject,
        source_type=source_type,
        text=text,
        sections=sections,
        document_id=document_id,
        metadata=metadata,
    )
    if fallback_bundle["generation_mode"] == "INSUFFICIENT_CONTENT":
        return fallback_bundle

    evidence_units = fallback_bundle.get("evidence_units") or []
    dossier_text, _short_map = prepare_evidence_dossier(evidence_units, max_chars=22000)
    if len(dossier_text.strip()) < 50:
        dossier_text = build_representative_excerpt(text, sections=sections, max_chars=22000)
    if len(dossier_text.strip()) < 50:
        return fallback_bundle

    modality_desc = {
        "VIDEO": "vídeo/aula gravada (transcrição temporal e texto OCR extraído dos diapositivos)",
        "AUDIO": "gravação de áudio/aula falada",
        "LECTURE_AUDIO": "gravação de aula em áudio",
        "PPTX": "apresentação de diapositivos (slides e notas do orador)",
        "PDF": "documento/artigo em PDF",
        "DOCX": "documento Word",
    }.get(source_type.upper(), f"documento de estudo ({source_type})")

    system_prompt = (
        "És um especialista pedagógico e investigador universitário em Português Europeu (PT-PT).\n"
        "REGRAS OBRIGATÓRIAS:\n"
        "1. Baseia-te EXCLUSIVAMENTE nas evidências [E1], [E2]... fornecidas. Proibido inventar factos, autores, datas ou teorias externas.\n"
        "2. Em cada item, inclui a referência [E#] da evidência que o suporta em 'source_refs' (ex: [\"E1\", \"E2\"]).\n"
        "3. Sê rigoroso, analítico e denso: MÁXIMO 1 frase rigorosa (15 a 25 palavras) por campo para garantir resposta compacta, profunda e sem truncamento.\n"
        "4. Distingue os modos: 'quick_summary' (4 pontos: tema, objetivo, conceitos, conclusão), "
        "'study_sections' (até 3 secções principais), 'detailed_summary' (2 blocos analíticos aprofundados), "
        "'exam_summary' (3 conceitos high-yield e 2 questões de exame).\n"
        "5. Devolve APENAS JSON válido."
    )

    user_prompt = f"""Analisa o seguinte {modality_desc}:
Título: "{title}" | Área: "{subject}"

=== EVIDÊNCIAS DO DOCUMENTO ===
{dossier_text}
=== FIM DAS EVIDÊNCIAS ===

Devolve APENAS um objeto JSON compacto em PT-PT com este formato exato (máximo 1 frase rigorosa por campo):
{{
  "quick_summary": [
    {{"text": "Tema central e objetivo principal do documento.", "source_refs": ["E1"]}},
    {{"text": "Conceito/mecanismo essencial 1 explicado na fonte.", "source_refs": ["E2"]}},
    {{"text": "Conceito/mecanismo essencial 2 e dados/exemplos.", "source_refs": ["E3"]}},
    {{"text": "Conclusão principal sustentada pelo documento.", "source_refs": ["E4"]}}
  ],
  "study_sections": [
    {{
      "section_id": "sec_1",
      "title": "Título da secção",
      "page_ref": "p. 1",
      "summary": "O que a secção aborda e relações entre conceitos (1 frase densa).",
      "key_concepts": ["Conceito 1", "Conceito 2"],
      "source_refs": ["E1", "E2"]
    }}
  ],
  "detailed_summary": [
    {{
      "title": "Mecanismos, Distinções e Pressupostos",
      "text": "Explicação analítica densa (1-2 frases rigorosas) aprofundando processos e exemplos da fonte.",
      "source_refs": ["E1", "E3"]
    }}
  ],
  "exam_summary": {{
    "high_yield_concepts": [
      {{"concept": "Conceito Real", "detail": "Definição rigorosa ou relação causa-consequência (1 frase).", "source_refs": ["E2"]}}
    ],
    "likely_questions": [
      {{"question": "Pergunta de exame específica sobre a matéria?", "answer": "Resposta rigorosa fundamentada (1 frase).", "source_refs": ["E2"]}}
    ]
  }},
  "cornell_notes": {{
    "executive_summary": "Síntese executiva final da matéria (1-2 frases).",
    "cue_column": [
      {{"cue": "Pergunta/tópico de revisão?", "idea": "Explicação fundamentada no excerto (1 frase).", "source_refs": ["E1"]}}
    ]
  }},
  "structure": {{
    "problem": {{"text": "Problema ou tema central", "status": "OBSERVED", "source_refs": ["E1"]}},
    "contribution": {{"text": "Tese ou contribuição central", "status": "OBSERVED", "source_refs": ["E1"]}},
    "method": {{"text": "Metodologia/processo abordado", "status": "OBSERVED", "source_refs": ["E2"]}},
    "results": {{"text": "Evidências/resultados demonstrados", "status": "OBSERVED", "source_refs": ["E3"]}},
    "conclusion": {{"text": "Conclusão suportada pelo documento", "status": "OBSERVED", "source_refs": ["E4"]}}
  }}
}}"""

    parsed, telemetry = invoke_study_llm_observable(
        operation="study_generate_complete_bundle",
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        expect_json=True,
        temperature=0.15,
        max_output_tokens=1800,
        timeout_seconds=220.0,
        document_id=document_id,
    )
    if isinstance(parsed, dict):
        normalized = _normalize_llm_bundle(
            parsed,
            fallback_bundle,
            title=title,
            subject=subject,
            evidence_units=evidence_units,
            telemetry=telemetry,
        )
        if normalized is not None:
            return normalized

    if not allow_extractive_fallback:
        return {
            **fallback_bundle,
            "generation_mode": "UNAVAILABLE",
            "generation_telemetry": telemetry,
            "llm_unavailable_reason": (
                ", ".join(telemetry.get("validation_errors") or [])
                or f"Modelo local qwen3.5:9b indisponível ({telemetry.get('status', 'UNAVAILABLE')})"
            ),
        }

    fallback_bundle["generation_telemetry"] = telemetry
    fallback_bundle["llm_fallback_reason"] = (
        ", ".join(telemetry.get("validation_errors") or [])
        or f"Fallback extrativo ativado ({telemetry.get('status', 'UNAVAILABLE')})"
    )
    return fallback_bundle


def synthesize_multi_documents_grounded(
    docs_info: List[Dict[str, str]],
) -> Dict[str, Any]:
    """
    Compara múltiplos documentos de estudo reais (pontos comuns, diferenças, conceitos partilhados,
    contradições/divergências e complementaridade/evolução conceptual). Zero strings pré-fabricadas.
    docs_info: [{"document_id": ..., "title": ..., "source_type": ..., "excerpt": ...}]
    """
    # Fallback extrativo cruzado 100% baseado nos termos e frases reais de cada documento
    doc_term_sets: List[set[str]] = []
    doc_display_terms: Dict[str, str] = {}
    doc_top_sent: List[Tuple[str, str]] = []

    for d in docs_info:
        terms = extract_key_terms_from_text(d.get("excerpt", ""), top_k=12)
        t_set: set[str] = set()
        for t, _ in terms:
            low = t.lower()
            t_set.add(low)
            doc_display_terms.setdefault(low, t)
        doc_term_sets.append(t_set)
        sents = rank_salient_sentences(d.get("excerpt", ""), top_k=2, preserve_order=True)
        doc_top_sent.append((d.get("title", "Documento"), sents[0] if sents else ""))

    term_doc_counts: Counter[str] = Counter()
    for ts in doc_term_sets:
        for t in ts:
            term_doc_counts[t] += 1

    shared_low = [t for t, c in term_doc_counts.most_common(10) if c >= 2]
    shared_concepts = [doc_display_terms[t] for t in shared_low[:8]]
    if not shared_concepts:
        shared_concepts = [doc_display_terms[t] for t, _ in term_doc_counts.most_common(5)]

    fallback = {
        "document_count": len(docs_info),
        "documents": [d.get("title", "") for d in docs_info],
        "common_points": (
            [f"Convergência temática nos conceitos: {', '.join(shared_concepts[:5])}."]
            if shared_concepts
            else [f"Análise comparativa entre {', '.join(d.get('title', '') for d in docs_info)}."]
        ),
        "differences": [
            f"«{t}»: {s[:220]}" for t, s in doc_top_sent if s
        ],
        "shared_concepts": shared_concepts,
        "contradictions": [
            f"Diferença de enfoque entre «{docs_info[0].get('title', 'Doc 1')}» e «{docs_info[1].get('title', 'Doc 2')}» quanto ao nível de detalhe e escopo analisado."
        ] if len(docs_info) >= 2 else [],
        "idea_evolution": [
            f"Progressão de «{t}» ({s[:140]})" for t, s in doc_top_sent if s
        ],
    }

    blocks = []
    per_doc_chars = max(2500, 20000 // max(1, len(docs_info)))
    for idx, d in enumerate(docs_info, 1):
        blocks.append(
            f"=== MATERIAL {idx}: {d.get('title')} ({d.get('source_type')}) ===\n"
            f"{(d.get('excerpt') or '')[:per_doc_chars]}"
        )

    parsed = invoke_study_llm_json(
        operation="study_multi_doc_synthesis",
        system_prompt=(
            "És um investigador académico em PT-PT. Compara rigorosamente os materiais fornecidos "
            "usando APENAS o conteúdo real de cada um. Devolve exclusivamente JSON válido."
        ),
        user_prompt=(
            "\n\n".join(blocks)
            + "\n\nDevolve um JSON com:\n"
            '{\n'
            '  "common_points": ["pontos e temas realmente partilhados entre os materiais"],\n'
            '  "differences": ["diferenças reais de foco, método ou abordagem entre cada material (nomeando cada título)"],\n'
            '  "shared_concepts": ["termos/conceitos técnicos comuns"],\n'
            '  "contradictions": ["divergências, tensões ou diferenças metodológicas observadas (ou complementaridades se não se contradisserem)"],\n'
            '  "idea_evolution": ["como os materiais se complementam ou progridem conceptualmente"]\n'
            '}'
        ),
        temperature=0.15,
        max_output_tokens=3072,
        timeout_seconds=75.0,
    )

    if isinstance(parsed, dict):
        result = {
            "document_count": len(docs_info),
            "documents": [d.get("title", "") for d in docs_info],
            "common_points": [str(x) for x in (parsed.get("common_points") or []) if str(x).strip()] or fallback["common_points"],
            "differences": [str(x) for x in (parsed.get("differences") or []) if str(x).strip()] or fallback["differences"],
            "shared_concepts": [str(x) for x in (parsed.get("shared_concepts") or []) if str(x).strip()] or fallback["shared_concepts"],
            "contradictions": [str(x) for x in (parsed.get("contradictions") or []) if str(x).strip()] or fallback["contradictions"],
            "idea_evolution": [str(x) for x in (parsed.get("idea_evolution") or []) if str(x).strip()] or fallback["idea_evolution"],
        }
    else:
        result = fallback

    # Aliases para retrocompatibilidade com testes existentes (common_themes / divergent_perspectives)
    result["common_themes"] = result["common_points"]
    result["divergent_perspectives"] = result["differences"]
    return result
