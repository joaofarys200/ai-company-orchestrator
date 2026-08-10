import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "generate_architecture_map.py"


def load_generator():
    spec = importlib.util.spec_from_file_location("architecture_map_generator", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_map_is_deterministic_and_references_are_valid():
    generator = load_generator()
    first = generator.MapBuilder(ROOT).build()
    second = generator.MapBuilder(ROOT).build()
    assert json.dumps(first, sort_keys=True, ensure_ascii=False) == json.dumps(second, sort_keys=True, ensure_ascii=False)
    generator.validate_map(first)

    ids = []
    for bucket in generator.MAP_BUCKETS:
        ids.extend(item["id"] for item in first.get(bucket, []))
    assert len(ids) == len(set(ids))
    assert any(item["path"] == "server.py" for item in first["components"])
    assert any(item["path"] == "frontend/src/main.tsx" for item in first["components"])


def test_exclusions_and_redaction_are_applied():
    generator = load_generator()
    data = generator.MapBuilder(ROOT).build()
    file_buckets = (
        "components", "contracts", "endpoints", "websockets", "tools", "agents",
        "providers", "tests", "benchmarks", "diagnostics",
    )
    paths = [
        item.get("path", "")
        for bucket in file_buckets
        for item in data.get(bucket, [])
    ]
    for excluded in ("node_modules/", "venv/", ".venv/", "diagnostics/", "workspace/"):
        assert not any(path.lower().startswith(excluded) for path in paths)
    assert "sk-123" not in generator.redact("api_key=sk-123")
    assert "<redacted>" in generator.redact("api_key=sk-123")


def test_artifacts_are_written_and_html_is_self_contained(tmp_path):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(ROOT), "--out-dir", str(tmp_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert '"components"' in result.stdout
    document = json.loads((tmp_path / "architecture-map.json").read_text(encoding="utf-8"))
    html = (tmp_path / "architecture-map.html").read_text(encoding="utf-8")
    assert document["meta"]["project_name"]
    assert document["blueprint"]["format"] == "architecture_blueprint_v1"
    assert document["blueprint"]["layout"]["direction"] == "left_to_right"
    assert document["blueprint"]["nodes"]
    assert all("position" in node for node in document["blueprint"]["nodes"])
    assert len(document["blueprint"]["nodes"]) <= document["blueprint"]["selection_policy"]["maximum_nodes"]
    assert 'id="architecture-data"' in html
    assert "Repository blueprint" in html
    assert "Blueprint arquitetural" in html
    assert "blueprint-search" in html
    assert "flow-filter" in html
    assert "C ${mx}" in html
    assert "addEventListener" in html
    assert "show-edges" in html
    assert "global-search" in html
    assert "subsystem-filter" in html
    assert "export-json" in html
    assert "http://" not in html
    assert "https://" not in html
    assert "<script src=" not in html
    assert "fetch(" not in html


def test_schema_covers_required_top_level_contract():
    generator = load_generator()
    schema = generator.SCHEMA
    assert set(schema["required"]) >= {"meta", "blueprint", "components", "relations", "evidence_index"}
    assert set(schema["properties"]) >= set(generator.MAP_BUCKETS)
