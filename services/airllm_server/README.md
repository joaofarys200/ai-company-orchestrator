# AirLLM experimental smoke test

This directory is an isolated feasibility experiment for running one short
text generation with AirLLM. It is not a server despite the directory name:
there is no HTTP listener, background worker, Ollama call, or Jarvis entry
point in this phase.

AirLLM is **not integrated with the ProjectBuilder**. The focal correction
protocol, schemas, call budget, journals, materialization, and current Ollama
flows remain unchanged. The future target is AirLLM for initial generation and
Ollama for focal correction, but this experiment does not implement that route.

## Validated API boundary

The experiment is pinned to `airllm==3.0.1`. Its published API exposes:

```python
AutoModel.from_pretrained(pretrained_model_name_or_path, *inputs, **kwargs)
```

The official 3.0.1 documentation identifies `compression`,
`profiling_mode`, and `layer_shards_saving_path` as supported configuration.
The smoke test inspects the installed callable and fails clearly if an
installed signature cannot accept the requested kwargs. It also rejects an
AirLLM version other than 3.0.1 instead of silently assuming compatibility.

There is no proven JSON Schema or structured-output support here. The prompt
asks only for a short plain-text answer.

## Separate environment on Windows

From the repository root in PowerShell:

```powershell
py -3.11 -m venv .venv-airllm
.\.venv-airllm\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r services\airllm_server\requirements.txt
```

AirLLM 3.0.1 declares Torch 2.4 or later and Transformers 4.49 through 5.12 as
dependencies. `bitsandbytes` is included separately because the documented
`4bit` and `8bit` compression modes require it. Install a CUDA-compatible
Torch build appropriate for the local driver if the resolver selects a CPU-only
build.

## Configuration

Copy the example and edit only the experimental file:

```powershell
Copy-Item services\airllm_server\.env.example services\airllm_server\.env
notepad services\airllm_server\.env
```

Supported variables:

- `AIRLLM_MODEL`: required Hugging Face model ID or local model path.
- `AIRLLM_SHARDS_PATH`: required path for layer shards; normalized to an
  absolute path and created by the manual smoke test.
- `AIRLLM_COMPRESSION`: `none`, `4bit`, or `8bit`.
- `AIRLLM_MAX_CONTEXT`: positive prompt-token limit.
- `AIRLLM_MAX_NEW_TOKENS`: positive generation limit, not greater than context.
- `AIRLLM_TEMPERATURE`: number from 0 through 2.
- `AIRLLM_PROFILING_MODE`: `true/false`, `1/0`, or `yes/no`.
- `HF_HOME`: optional root for Hugging Face data.
- `HUGGINGFACE_HUB_CACHE`: optional model repository cache.

Process environment variables override values in
`services\airllm_server\.env`.

## Verify CUDA

Before the expensive first run:

```powershell
python -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CUDA unavailable')"
nvidia-smi
```

The smoke test deliberately fails when CUDA is unavailable. It does not fall
back to CPU because this phase is intended to validate the target GPU path.

## Run the smoke test

```powershell
python -m services.airllm_server.smoke_test
```

The first execution may download the selected model and split it into layer
shards. The model is loaded once. The prompt is tokenized without truncation;
the run fails if its original token count exceeds `AIRLLM_MAX_CONTEXT`.

The output includes Torch/AirLLM versions, GPU name, selected configuration,
preparation/loading duration, prompt and completion token counts, generation
duration, tokens per second, and only the newly generated text.

## Disk planning

The Hugging Face cache contains the downloaded source model. The AirLLM shards
path contains the transformed layer-by-layer representation used at inference.
They are different stores and can coexist. During the first preparation, allow
for the source weights, generated shards, and temporary overhead at the same
time. For a 32B full-precision source model this can exceed 80-100 GB; consult
the selected model card and keep additional safety margin. Compression reduces
the shard representation but does not avoid the initial source download.

## Interrupt and inspect residual activity

Use `Ctrl+C` to interrupt the foreground run. Then inspect, without killing
anything automatically:

```powershell
Get-Process python,pythonw -ErrorAction SilentlyContinue |
    Select-Object Id,ProcessName,Path,StartTime
nvidia-smi
```

AirLLM shard creation may leave partial files after interruption. Inspect exact
targets before deleting anything:

```powershell
$AirLLMCleanupTarget = 'D:\airllm\shards\qwen3-32b'
$ResolvedAirLLMCleanupTarget = Resolve-Path -LiteralPath $AirLLMCleanupTarget
Get-ChildItem -LiteralPath $ResolvedAirLLMCleanupTarget -Force
```

Only after confirming that the resolved path is the explicitly selected
experimental directory, remove that exact target if desired:

```powershell
Remove-Item -LiteralPath $ResolvedAirLLMCleanupTarget -Recurse -Force
```

Repeat the same inspect-first procedure separately for a chosen Hugging Face
cache directory. Never delete a broad drive, home directory, or unresolved
environment-variable path.

