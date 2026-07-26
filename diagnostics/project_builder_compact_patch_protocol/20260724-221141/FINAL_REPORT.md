# Compact Patch Trusted Metadata Fix

## Resultado
Baseline manual: `MANUAL_COMPACT_PATCH_PASSED`. Testes: `39/39 passed`.

## Alteração realizada
O modelo deixou de declarar `expected_sha256`. O executor calcula o hash do snapshot, cria `trusted_bindings` internos e rejeita alterações concorrentes com `SNAPSHOT_CHANGED`.

## Testes
O schema não contém `expected_sha256`; operações sem hash são aceites; hashes fornecidos pelo modelo são rejeitados; binding, stale detection, transform, path policy e atomicidade foram testados.

## Reavaliação K1–K4
{
  "K1": {
    "source": "previous_response_hash_removed_only",
    "schema_new": true,
    "coverage": false,
    "binding": true,
    "apply": false,
    "validators": false,
    "errors": [
      {
        "code": "INVALID_TRANSFORM_PARAMETER",
        "message": "storage_filename must be a single JSON filename",
        "details": {
          "value": null
        }
      }
    ],
    "model_hash_fields_removed": 1
  },
  "K2": {
    "source": "previous_response_hash_removed_only",
    "schema_new": true,
    "coverage": false,
    "binding": true,
    "apply": false,
    "validators": false,
    "errors": [
      {
        "code": "INVALID_TRANSFORM_PARAMETER",
        "message": "storage_filename must be a single JSON filename",
        "details": {
          "value": null
        }
      }
    ],
    "model_hash_fields_removed": 1
  },
  "K3": {
    "source": "previous_response_hash_removed_only",
    "schema_new": true,
    "coverage": false,
    "binding": true,
    "apply": false,
    "validators": false,
    "errors": [
      {
        "code": "INVALID_TRANSFORM_PARAMETER",
        "message": "storage_filename must be a single JSON filename",
        "details": {
          "value": null
        }
      }
    ],
    "model_hash_fields_removed": 1
  },
  "K4": {
    "source": "previous_response_hash_removed_only",
    "schema_new": true,
    "coverage": false,
    "binding": true,
    "apply": false,
    "validators": false,
    "errors": [
      {
        "code": "UNKNOWN_OPERATION_REFERENCE",
        "message": "error_resolutions references unknown operation",
        "details": {
          "operation_id": "op_01"
        }
      }
    ],
    "model_hash_fields_removed": 1
  }
}

## Chamada final
{
  "done": true,
  "done_reason": "stop",
  "json_valid": true,
  "schema_valid": true,
  "coverage": false,
  "binding": true,
  "apply": false,
  "validators": false,
  "errors": [
    {
      "code": "UNKNOWN_OPERATION_REFERENCE",
      "message": "error_resolutions references unknown operation",
      "details": {
        "operation_id": "op_01"
      }
    }
  ],
  "model": "qwen3.5:9b",
  "elapsed_seconds": 32.668,
  "content_sha256": "b365efcb1add2d8a15868e0a01578387decd52df6c062adc379f48bfa91e4c55"
}

## Validators
Resultado: `False`. Não houve reparação local nem materialização.

## Decisão
`MODEL_SEMANTIC_SELECTION_FAILED`.

## Próximo passo
Não executar outra ronda automaticamente. Se aprovado, preparar apenas a integração mínima do contrato compacto no ProjectBuilder.
