"""
JARVIS OS — Automated Documentation and Schema Integrity Test Suite
Asserts that all documentation links, SVG diagrams, JSON Schemas, and ADRs are valid and unbroken.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
import xml.etree.ElementTree as ET
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_svg_diagrams_exist_and_are_valid():
    """Validates that all 10 required architecture SVG diagrams exist and are valid XML."""
    diagram_dir = REPO_ROOT / "docs" / "diagrams"
    assert diagram_dir.exists(), "docs/diagrams/ directory must exist"

    expected_diagrams = [
        "01-system-architecture.svg",
        "02-agent-architecture.svg",
        "03-coding-agent-pipeline.svg",
        "04-model-harness.svg",
        "05-mission-lifecycle.svg",
        "06-sentinel-architecture.svg",
        "07-knowledge-architecture.svg",
        "08-economic-evidence-flow.svg",
        "09-runtime-websocket-flow.svg",
        "10-persistence-architecture.svg",
    ]

    for name in expected_diagrams:
        svg_path = diagram_dir / name
        assert svg_path.exists(), f"Missing required SVG diagram: {name}"
        assert svg_path.stat().st_size > 500, f"SVG diagram {name} is unusually small or empty"

        # Verify XML well-formedness
        content = svg_path.read_text(encoding="utf-8")
        try:
            root = ET.fromstring(content)
            assert "svg" in root.tag, f"Root element of {name} must be <svg>"
        except ET.ParseError as e:
            pytest.fail(f"Invalid SVG/XML in {name}: {e}")


def test_json_schemas_exist_and_are_valid_draft07():
    """Validates that all canonical JSON schemas in schemas/ are valid JSON with Draft-07 syntax."""
    schemas_dir = REPO_ROOT / "schemas"
    assert schemas_dir.exists(), "schemas/ directory must exist"

    expected_schemas = [
        "mission.schema.json",
        "model-request.schema.json",
        "model-response.schema.json",
        "tool-call.schema.json",
        "websocket-message.schema.json",
        "security-event.schema.json",
        "security-incident.schema.json",
        "security-response-action.schema.json",
        "economic-mission.schema.json",
        "evidence.schema.json",
        "document-provenance.schema.json",
    ]

    for name in expected_schemas:
        schema_path = schemas_dir / name
        assert schema_path.exists(), f"Missing required schema: {name}"

        content = schema_path.read_text(encoding="utf-8")
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            pytest.fail(f"Schema {name} is not valid JSON: {e}")

        assert "$schema" in data, f"Schema {name} must declare $schema"
        assert "$id" in data, f"Schema {name} must declare $id"
        assert "title" in data, f"Schema {name} must declare title"
        assert "type" in data, f"Schema {name} must declare type"
        assert data["$schema"] == "http://json-schema.org/draft-07/schema#"


def test_adrs_exist_and_are_valid():
    """Validates that all expected Architecture Decision Records exist in docs/decisions/."""
    decisions_dir = REPO_ROOT / "docs" / "decisions"
    assert decisions_dir.exists(), "docs/decisions/ directory must exist"

    expected_adrs = [
        "ADR-001-hybrid-dual-model-harness.md",
        "ADR-002-websocket-protocol-multiplexing.md",
        "ADR-003-host-security-sentinel-watchdog.md",
        "ADR-004-deterministic-ast-patch-engine.md",
        "ADR-005-sqlite-and-json-state-persistence.md",
        "ADR-006-four-tier-economic-evidence-taxonomy.md",
    ]

    for name in expected_adrs:
        adr_path = decisions_dir / name
        assert adr_path.exists(), f"Missing required ADR: {name}"
        content = adr_path.read_text(encoding="utf-8")
        assert "## Context" in content, f"ADR {name} must contain ## Context"
        assert "## Decision" in content, f"ADR {name} must contain ## Decision"
        assert "## Status" in content, f"ADR {name} must contain ## Status"


def test_markdown_relative_links_integrity():
    """Scans core markdown files and asserts that all relative file links point to existing targets."""
    core_markdown_files = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "ARCHITECTURE.md",
        REPO_ROOT / "SECURITY.md",
        REPO_ROOT / "CONTRIBUTING.md",
        REPO_ROOT / "CHANGELOG.md",
        REPO_ROOT / "docs" / "PROJECT_MAP.md",
        REPO_ROOT / "docs" / "REPOSITORY_PRESENTATION_AUDIT.md",
        REPO_ROOT / "schemas" / "README.md",
    ]

    link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

    for md_file in core_markdown_files:
        assert md_file.exists(), f"Missing core documentation file: {md_file}"
        content = md_file.read_text(encoding="utf-8")
        
        for match in link_pattern.finditer(content):
            target = match.group(2).strip()

            # Ignore external HTTP links, mailto, and internal anchor links (#)
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue

            # Strip anchor fragments if present (e.g. path/to/file.md#section)
            clean_target = target.split("#")[0]
            if not clean_target:
                continue

            # Resolve target path relative to the markdown file's parent directory
            resolved_path = (md_file.parent / clean_target).resolve()
            assert resolved_path.exists(), (
                f"Broken link in {md_file.relative_to(REPO_ROOT)}: '{target}' "
                f"resolves to non-existent path: {resolved_path}"
            )
