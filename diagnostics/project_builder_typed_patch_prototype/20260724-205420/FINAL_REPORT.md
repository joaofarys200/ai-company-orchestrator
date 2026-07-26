# Typed Patch Prototype

Status: **MODEL_TYPED_PATCH_FAILED_VALIDATION**

This is an offline diagnostic prototype. It does not modify ProjectBuilder, run WP1/WP2, materialize a project, execute npm, or start preview.

## Scope

- Input case: real health-boundary-probe WP1 planning failure.
- File namespace: package.json, server.js, index.html, test.js.
- Replacement target: server.js only, derived from PERSISTENCE_NOT_IMPLEMENTED.
- Model calls: 1

## Baseline

- Manual typed patch: **MANUAL_TYPED_PATCH_PASSED**.
- Manual validator error codes: `none`.
- The manual baseline is accepted only when the real validator returns valid=true.

## Model P1

- Model: `qwen3.5:9b`; context: `8192`; temperature: `0`; top_p: `0.8`; think: `false`.
- Result: **MODEL_TYPED_PATCH_FAILED_VALIDATION**.
- Response time: `20.16s`.
- Contract errors: `none`.
- Model validator errors: `PERSISTENCE_NOT_IMPLEMENTED`.
- The recorded P1 call used `model_prompt_used.txt`; the current template in `typed_prompt_current.txt` additionally includes explicit current-file SHA256 values. It was not sent to a second model call.

## Safety

- Operations are validated before application.
- No create_file, rename_file, delete_file, arbitrary patch, merge object, or execute command operation exists.
- Hash mismatch, unknown path, duplicate/conflicting operations, and schema violations fail closed.
- Application is pure over a deep copy; no project path is opened or written.
- No local repair or third model call is present.

## Evidence

- Artifact hashes: `C:\Users\joaor\Desktop\ai-company-orchestrator\diagnostics\project_builder_typed_patch_prototype\20260724-205420\input\artifact_hashes.json`.
- Manual validation: `C:\Users\joaor\Desktop\ai-company-orchestrator\diagnostics\project_builder_typed_patch_prototype\20260724-205420\manual_validation.json`.
- Model response: `C:\Users\joaor\Desktop\ai-company-orchestrator\diagnostics\project_builder_typed_patch_prototype\20260724-205420\model_response.json`.
- Metrics: `C:\Users\joaor\Desktop\ai-company-orchestrator\diagnostics\project_builder_typed_patch_prototype\20260724-205420\metrics.json`.
