# Compact Patch Trusted Metadata Fix

## Resultado
Baseline manual: `MANUAL_COMPACT_PATCH_PASSED`. Testes: `39/39 passed`.

## Alteração realizada
O modelo seleciona apenas operações públicas. O executor atribui IDs internos, fornece `data.json`, calcula hashes confiáveis e rejeita `SNAPSHOT_CHANGED`.

## Testes
O schema público contém apenas `operations`; hashes, IDs, parâmetros, referências de erro e conteúdo livre são rejeitados.

## Reavaliação K1–K4
{
  "K1": {
    "source": "previous_response_metadata_removed_only",
    "schema_valid": true,
    "coverage": false,
    "binding": false,
    "apply": false,
    "validators": false,
    "errors": [
      {
        "code": "DUPLICATE_OPERATION",
        "message": "The same operation target was selected more than once",
        "details": {
          "operation": {
            "op": "set_component_files",
            "component": "backend",
            "paths": [
              "server.js"
            ],
            "id": "op-05"
          }
        }
      }
    ]
  },
  "K2": {
    "source": "previous_response_metadata_removed_only",
    "schema_valid": true,
    "coverage": false,
    "binding": false,
    "apply": false,
    "validators": false,
    "errors": [
      {
        "code": "DUPLICATE_OPERATION",
        "message": "The same operation target was selected more than once",
        "details": {
          "operation": {
            "op": "set_component_files",
            "component": "backend",
            "paths": [
              "server.js"
            ],
            "id": "op-05"
          }
        }
      }
    ]
  },
  "K3": {
    "source": "previous_response_metadata_removed_only",
    "schema_valid": true,
    "coverage": false,
    "binding": false,
    "apply": false,
    "validators": false,
    "errors": [
      {
        "code": "DUPLICATE_OPERATION",
        "message": "The same operation target was selected more than once",
        "details": {
          "operation": {
            "op": "set_component_files",
            "component": "backend",
            "paths": [
              "server.js"
            ],
            "id": "op-05"
          }
        }
      }
    ]
  },
  "K4": {
    "source": "previous_response_metadata_removed_only",
    "schema_valid": true,
    "coverage": false,
    "binding": false,
    "apply": false,
    "validators": false,
    "errors": [
      {
        "code": "DUPLICATE_OPERATION",
        "message": "The same operation target was selected more than once",
        "details": {
          "operation": {
            "op": "set_component_files",
            "component": "backend",
            "paths": [
              "server.js"
            ],
            "id": "op-05"
          }
        }
      }
    ]
  },
  "previous_final": {
    "source": "previous_response_metadata_removed_only",
    "schema_valid": true,
    "coverage": false,
    "binding": false,
    "apply": false,
    "validators": false,
    "errors": [
      {
        "code": "DUPLICATE_OPERATION",
        "message": "The same operation target was selected more than once",
        "details": {
          "operation": {
            "op": "set_component_files",
            "component": "backend",
            "paths": [
              "server.js"
            ],
            "id": "op-05"
          }
        }
      }
    ]
  }
}

## Chamada final
{
  "model": "qwen3.5:9b",
  "done": true,
  "done_reason": "stop",
  "json_valid": true,
  "schema_valid": true,
  "coverage": false,
  "binding": false,
  "apply": false,
  "validators": false,
  "errors": [
    {
      "code": "MISSING_ERROR_COVERAGE",
      "message": "Operation semantics do not cover every initial error",
      "details": {
        "coverage": {
          "valid": false,
          "required_errors": [
            "DECLARED_COMPONENT_WITHOUT_ARTIFACTS",
            "MISSING_COMPONENT_MAPPING",
            "MISSING_HEALTH_ROUTE",
            "MISSING_REQUESTED_COMPONENTS",
            "PERSISTENCE_NOT_IMPLEMENTED"
          ],
          "resolved": {
            "DECLARED_COMPONENT_WITHOUT_ARTIFACTS": [],
            "MISSING_COMPONENT_MAPPING": [],
            "MISSING_HEALTH_ROUTE": [
              "op-03"
            ],
            "MISSING_REQUESTED_COMPONENTS": [
              "op-01"
            ],
            "PERSISTENCE_NOT_IMPLEMENTED": []
          },
          "missing": [
            "DECLARED_COMPONENT_WITHOUT_ARTIFACTS",
            "MISSING_COMPONENT_MAPPING",
            "PERSISTENCE_NOT_IMPLEMENTED"
          ],
          "catalog": "compact-v2"
        }
      }
    }
  ],
  "elapsed_seconds": 45.784,
  "content_sha256": "2e738887b08059f6ee4d8bcd4e7492b8bee995f7a93989acebeb172cd7ea1c82"
}

## Validators
Resultado: `False`. Não houve retry, reparação local ou materialização.

## Decisão
`MODEL_OPERATION_SELECTION_FAILED`.

## Próximo passo
Não executar outra ronda automaticamente.
