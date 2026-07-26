# Content Operation Audit

Status: **QWEN_9B_TYPED_PATCH_UNRELIABLE**

This audit is diagnostic only. It did not run WP1/WP2, MissionState, npm, preview, materialization, or production validators changes.

## Controlled calls

- Model: `qwen3.5:9b`
- Context: `8192`
- Temperature: `0`
- Top-p: `0.8`
- Think: `false`
- Calls executed: `6`
- Retries: `0`
- Automatic repairs: `0`

## Baseline

`CONTENT_OPERATION_MANUAL_BASELINE_PASSED`: `True`

The manual patch changed only the virtual `server.js`, passed the real validators, and used the initial SHA256 `5bdbf49b0e707cf43da23ffb5d642e9ed97f8e98e103a8a0c9a69e6ccca9bd31` as its expected hash.

C1 is reproducible: its response SHA256 is `5925f58455857c47353bd07a6fbd42d8de79e12c504b6ccc1725d61afc7bfbce`, identical to the recorded P1 response. The parseable responses used only namespace paths; C3 did map `preview` to `package.json`, which is namespace-valid but semantically unsuitable.

## Comparison

| Test | Isolated modification | server.js operation | Persistence valid | Validators | Result |
|---|---|---:|---:|---:|---|
| C1 | exact P1 prompt and schema | none | False | FAILED |
| C2 | explicitly mandatory content operation | attempted/incomplete | False | FAILED |
| C3 | only required operation branches; server.js content target | attempted/incomplete | False | FAILED |
| C4 | full-file replacement with structural template | attempted/incomplete | False | FAILED |
| C5 | localized replace_text with exact insertion point | valid | False | FAILED |
| C6 | required_actions followed by operations | attempted/incomplete | False | FAILED |

## Schema findings

```json
{
  "root_type": "array",
  "allows_empty_array": true,
  "max_items": null,
  "branch_order": [
    "set_components",
    "set_component_files",
    "set_preview_strategy",
    "replace_file_content",
    "replace_text"
  ],
  "branches": [
    {
      "op": "set_components",
      "property_count": 2,
      "additional_properties": false,
      "required": [
        "op",
        "value"
      ],
      "content_fields": []
    },
    {
      "op": "set_component_files",
      "property_count": 3,
      "additional_properties": false,
      "required": [
        "op",
        "component",
        "paths"
      ],
      "content_fields": []
    },
    {
      "op": "set_preview_strategy",
      "property_count": 3,
      "additional_properties": false,
      "required": [
        "op",
        "field",
        "value"
      ],
      "content_fields": []
    },
    {
      "op": "replace_file_content",
      "property_count": 4,
      "additional_properties": false,
      "required": [
        "op",
        "path",
        "expected_sha256",
        "content"
      ],
      "content_fields": [
        "content"
      ]
    },
    {
      "op": "replace_text",
      "property_count": 6,
      "additional_properties": false,
      "required": [
        "op",
        "path",
        "expected_sha256",
        "old_text",
        "new_text",
        "expected_occurrences"
      ],
      "content_fields": [
        "old_text",
        "new_text"
      ]
    }
  ],
  "has_error_coverage_field": false,
  "represents_error_to_operation_dependency": false,
  "allows_plan_field_only_response": true,
  "observation": "A formally valid non-empty response may contain only set_* operations and omit content operations."
}
```

The original schema allows an empty operation array, does not require coverage of validator error IDs, and permits a formally valid response containing only plan-field operations. `replace_file_content` is not required by the schema and content-bearing branches are later than the simple branches.

The optional offline `resolved_error_codes` extension is in `coverage_extension.json`: it rejects the recorded C1 operations before validators with `PERSISTENCE_OPERATION_REQUIRED`, while accepting the manual eight-operation patch. It was not integrated into production and did not call the model.

## Answers

- The model did not consistently treat the `server.js` content change as mandatory: C1 omitted it; C2 recognized it lexically but failed to finish JSON.
- The original protocol made the operation optional in practice because no schema field required error coverage or a content operation.
- The schema permits simple plan operations without dependencies, so it can favor them over content branches.
- The controlled runs show incomplete structured generation for four content-attempt cases; they do not prove a pure model capacity limit independently of protocol pressure.
- `replace_file_content` was not reliable in these runs. `replace_text` produced a valid operation in C5, but not a valid complete correction.
- A template and a two-stage response did not produce a passing result in this six-call sample.
- The next step is protocol refinement around required error coverage and compact bounded content operations, not production integration or model replacement yet.

## Classification

{
  "REQUIRED_OPERATION_NOT_SALIENT": {
    "evidence": "C1 reproduced the plan-only response. C2 made the operation mandatory but returned an incomplete JSON generation.",
    "counterevidence": "C2 lexical output began a replace_file_content operation, so salience changed intent without producing a usable response.",
    "confidence": "medium",
    "test_needed": "A protocol with mandatory operation plus a bounded content representation."
  },
  "SCHEMA_BRANCH_AVOIDANCE": {
    "evidence": "C1 selected only set_* operations; the original schema allows plan-only output. C3 remained incomplete despite removing replace_text.",
    "counterevidence": "C3 also had generation incomplete, so branch choice and generation failure are confounded.",
    "confidence": "medium",
    "test_needed": "Repeat with a schema requiring one content operation and a compact bounded payload."
  },
  "CONTENT_GENERATION_TOO_COMPLEX": {
    "evidence": "C4 with a structural template still returned incomplete JSON; C2/C3/C6 also emitted truncated content operations.",
    "counterevidence": "No test produced a complete full-file replacement, so syntax/content quality cannot be separated from truncation.",
    "confidence": "high",
    "test_needed": "Bound content size or use a typed edit plan with a compact template expansion."
  },
  "LOCAL_TEXT_PATCH_PROTOCOL_PREFERRED": {
    "evidence": "C5 produced a valid replace_text with correct target and hash.",
    "counterevidence": "It omitted the required plan-field operations and lost the http import, so real validators failed.",
    "confidence": "medium",
    "test_needed": "Require field coverage and validate a compact localized patch that preserves all imports."
  },
  "ERROR_TO_OPERATION_LINK_MISSING": {
    "evidence": "Original schema has no resolved_error_codes or required operation coverage, and C1 legally omitted persistence content.",
    "counterevidence": "The prompt contains the persistence error text, but the schema does not enforce its resolution.",
    "confidence": "high",
    "test_needed": "Offline resolved_error_codes extension, no model call."
  },
  "MODEL_CAPACITY_LIMIT_FOR_CODE_PATCH": {
    "evidence": "Four cases ended with done=false and truncated JSON while attempting content operations.",
    "counterevidence": "The test set changes prompt/schema representation, so protocol generation pressure remains a confounder.",
    "confidence": "medium",
    "test_needed": "A compact operation whose content is a bounded insertion or template slot."
  }
}

## Decision

`QWEN_9B_TYPED_PATCH_UNRELIABLE`

The model is considered viable only if at least two semantically distinct tests pass, including one real content-generation test, with real validators passing and no manual full-solution injection. The recorded outcomes determine the decision above.

## Evidence

All requests, exact prompts, schemas, raw responses, normalized operations, validators, hashes and metrics are stored below this audit directory. No production file was edited.
