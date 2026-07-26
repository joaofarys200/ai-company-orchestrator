from __future__ import annotations

import json
from pathlib import Path

import run_content_operation_audit as audit


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    plan, errors, schema, namespace, request, prompt = audit.load_case()
    audit.BASE_PROMPT = prompt
    cases = audit.make_cases(plan, errors, namespace, schema, request, prompt)
    summary = json.loads((audit.OUTPUT / "summary.json").read_text(encoding="utf-8"))
    records = []
    for case in cases:
        directory = audit.OUTPUT / case["id"]
        raw_path = directory / "response_raw.txt"
        envelope_path = directory / "response_envelope.json"
        content = raw_path.read_text(encoding="utf-8") if raw_path.exists() else ""
        envelope = json.loads(envelope_path.read_text(encoding="utf-8")) if envelope_path.exists() else {}
        case["content"] = content
        case["generation_complete"] = envelope.get("done", True)
        assessment, composed = audit.analyze_response(case, plan, errors, namespace)
        write_json(directory / "assessment.json", assessment)
        if composed is not None:
            write_json(directory / "composed_plan.json", composed.plan)
            write_json(directory / "changes.json", composed.changes)
        records.append({
            "id": case["id"],
            "description": case["description"],
            "status": "PASSED" if assessment.get("validators", {}).get("valid") else "FAILED",
            "assessment": assessment,
        })
    summary["cases"] = records
    summary["classifications"] = {
        "REQUIRED_OPERATION_NOT_SALIENT": {
            "evidence": "C1 reproduced the plan-only response. C2 made the operation mandatory but returned an incomplete JSON generation.",
            "counterevidence": "C2 lexical output began a replace_file_content operation, so salience changed intent without producing a usable response.",
            "confidence": "medium",
            "test_needed": "A protocol with mandatory operation plus a bounded content representation.",
        },
        "SCHEMA_BRANCH_AVOIDANCE": {
            "evidence": "C1 selected only set_* operations; the original schema allows plan-only output. C3 remained incomplete despite removing replace_text.",
            "counterevidence": "C3 also had generation incomplete, so branch choice and generation failure are confounded.",
            "confidence": "medium",
            "test_needed": "Repeat with a schema requiring one content operation and a compact bounded payload.",
        },
        "CONTENT_GENERATION_TOO_COMPLEX": {
            "evidence": "C4 with a structural template still returned incomplete JSON; C2/C3/C6 also emitted truncated content operations.",
            "counterevidence": "No test produced a complete full-file replacement, so syntax/content quality cannot be separated from truncation.",
            "confidence": "high",
            "test_needed": "Bound content size or use a typed edit plan with a compact template expansion.",
        },
        "LOCAL_TEXT_PATCH_PROTOCOL_PREFERRED": {
            "evidence": "C5 produced a valid replace_text with correct target and hash.",
            "counterevidence": "It omitted the required plan-field operations and lost the http import, so real validators failed.",
            "confidence": "medium",
            "test_needed": "Require field coverage and validate a compact localized patch that preserves all imports.",
        },
        "ERROR_TO_OPERATION_LINK_MISSING": {
            "evidence": "Original schema has no resolved_error_codes or required operation coverage, and C1 legally omitted persistence content.",
            "counterevidence": "The prompt contains the persistence error text, but the schema does not enforce its resolution.",
            "confidence": "high",
            "test_needed": "Offline resolved_error_codes extension, no model call.",
        },
        "MODEL_CAPACITY_LIMIT_FOR_CODE_PATCH": {
            "evidence": "Four cases ended with done=false and truncated JSON while attempting content operations.",
            "counterevidence": "The test set changes prompt/schema representation, so protocol generation pressure remains a confounder.",
            "confidence": "medium",
            "test_needed": "A compact operation whose content is a bounded insertion or template slot.",
        },
    }
    summary["decision"] = "QWEN_9B_TYPED_PATCH_UNRELIABLE"
    write_json(audit.OUTPUT / "summary.json", summary)
    audit.write_report(summary, audit.schema_analysis(schema))


if __name__ == "__main__":
    main()
