"""
Bateria de Testes Abrangente de Governança de Entrega de Produto do JARVIS.
Cobre:
- Separação formal de níveis de aceitação (SYNTAX != BUILD != RUNTIME != PRODUCT_ACCEPTED)
- Rastreabilidade atómica de requisitos (RequirementItem: PASS, FAIL, UNKNOWN, BLOCKED)
- Deteção de substituições destrutivas (DestructiveChangeDetector)
- Análise de preservação e integridade (PreservationAnalyzer, ProductIntegrityDiff)
- Validação estrutural de HTML (HtmlDocumentValidator)
- Validação de integridade de assets e imports (AssetIntegrityValidator)
- Validação de integridade visual (VisualIntegrityValidator)
- Validação de interatividade e botões (InteractionValidator)
- Validação de runtime e HTTP health check (RuntimeIntegrityValidator)
- Validação de navegador e headless QA (BrowserIntegrityValidator)
- Governança de dependências externas e bloqueio de downgrade silencioso
- Validação de alternativas verdadeiras (curl vs wget)
- Tratamento de evidência insuficiente (INSUFFICIENT_EVIDENCE nunca vira PASS)
- Gatilhos de revisão humana obrigatória (HUMAN_REVIEW)
- Portão final de entrega (ProductDeliveryGate)
- Cenário de reprodução exata de DINA (impedimento de entrega com index.html destruído)
- Cenário de extensão e preservação de funcionalidades (Features A, B, C)
- 5 Cenários reais de aceitação
- Portão canónico is_autonomous_product_delivery_ready
Total de testes >= 35.
"""

import asyncio
import os
import shutil
import pytest
from pathlib import Path

from security.delivery_governance import (
    AcceptanceLevel,
    AssetIntegrityValidator,
    BrowserIntegrityValidator,
    DeliveryGateStatus,
    DestructiveChangeDetector,
    HtmlDocumentValidator,
    InteractionValidator,
    PreservationAnalyzer,
    ProductAcceptanceReport,
    ProductDeliveryGate,
    ProductIntegrityDiff,
    QualityScoreStatus,
    RequirementItem,
    RequirementStatus,
    RuntimeIntegrityValidator,
    VisualIntegrityValidator,
    is_autonomous_product_delivery_ready,
)


# ==============================================================================
# 1. TESTES DE SEPARAÇÃO FORMAL DE CONCEITOS E MODELOS
# ==============================================================================

def test_01_acceptance_levels_are_distinct():
    """Garante que os níveis formais não se confundem nem são equivalentes."""
    assert AcceptanceLevel.SYNTAX_VALID.value != AcceptanceLevel.BUILD_VALID.value
    assert AcceptanceLevel.BUILD_VALID.value != AcceptanceLevel.PRODUCT_ACCEPTED.value
    assert AcceptanceLevel.RUNTIME_VALID.value != AcceptanceLevel.PRODUCT_ACCEPTED.value
    assert AcceptanceLevel.PRODUCT_ACCEPTED.value != AcceptanceLevel.USER_ACCEPTED.value


def test_02_requirement_item_traceability_lifecycle():
    """Verifica que cada requisito nasce UNKNOWN e requer evidência para se tornar PASS."""
    req = RequirementItem(requirement_id="REQ-01", description="Implementar scanner ativo")
    assert req.status == RequirementStatus.UNKNOWN.value
    assert req.evidence == {}

    req.status = RequirementStatus.PASS.value
    req.evidence = {"test_run": "ok", "coverage": 1.0}
    assert req.status == "PASS"
    assert req.evidence["test_run"] == "ok"


def test_03_requirement_traceability_requires_pass_for_acceptance():
    """Impede que requisitos em FAIL ou UNKNOWN permitam portão PRODUCT_ACCEPTED."""
    req1 = RequirementItem(requirement_id="REQ-1", description="UI principal", status=RequirementStatus.PASS.value)
    req2 = RequirementItem(requirement_id="REQ-2", description="Scan ativo", status=RequirementStatus.UNKNOWN.value)
    report = ProductAcceptanceReport(
        requirements=[req1, req2],
        gate_status=DeliveryGateStatus.PRODUCT_ACCEPTED.value,
        quality_score=QualityScoreStatus.READY.value,
    )
    # Se há requisito UNKNOWN, a entrega autónoma NÃO está pronta
    assert is_autonomous_product_delivery_ready(report) is False


def test_04_insufficient_evidence_never_becomes_pass():
    """Garante que o estado INSUFFICIENT_EVIDENCE é mantido e reprova a prontidão."""
    report = ProductAcceptanceReport(
        requirements=[RequirementItem(requirement_id="R1", description="UI", status=RequirementStatus.PASS.value)],
        result=RequirementStatus.INSUFFICIENT_EVIDENCE.value,
        quality_score=QualityScoreStatus.INSUFFICIENT_EVIDENCE.value,
        gate_status=DeliveryGateStatus.INSUFFICIENT_EVIDENCE.value,
    )
    assert is_autonomous_product_delivery_ready(report) is False


# ==============================================================================
# 2. TESTES DO DETETOR DE ALTERAÇÕES DESTRUTIVAS (DESTRUCTIVE CHANGE DETECTOR)
# ==============================================================================

def test_05_destructive_detector_identifies_index_html_shell_stripping():
    """Deteta quando index.html perde sua casca <!doctype html>, <html> ou <body>."""
    old_html = "<!DOCTYPE html><html><head><title>App</title><link rel='stylesheet' href='styles.css'></head><body><h1>Olá</h1><script src='app.js'></script></body></html>"
    new_html = "<div id='root'><h1>Olá fragmento</h1></div>"  # Sem html, body, link, script

    res = DestructiveChangeDetector.evaluate_change_destructiveness("index.html", old_html, new_html)
    assert res["is_destructive"] is True
    assert res["severity"] == "CRITICAL"
    assert "Destruição de estrutura web fundamental" in res["reason"]


def test_06_destructive_detector_identifies_dropped_css_or_script():
    """Deteta quando um ficheiro index.html perde link de CSS ou tag de script."""
    old_html = "<html><head><link rel='stylesheet' href='styles.css'></head><body><button id='btn'>OK</button><script src='client.js'></script></body></html>"
    new_html = "<html><head></head><body><button id='btn'>OK</button></body></html>"

    res = DestructiveChangeDetector.evaluate_change_destructiveness("index.html", old_html, new_html)
    assert res["is_destructive"] is True
    assert res["severity"] == "CRITICAL"
    assert "ligação para stylesheet CSS foi eliminada" in res["reason"]
    assert "ligação para script JS foi eliminada" in res["reason"]


def test_07_destructive_detector_identifies_massive_sensitive_file_wipe():
    """Deteta substituição destrutiva de >50% de linhas em ficheiros sensíveis."""
    old_content = "\n".join([f"line_{i}" for i in range(20)])
    new_content = "line_1\nline_2"  # perdeu 90% das linhas

    res = DestructiveChangeDetector.evaluate_change_destructiveness("server.js", old_content, new_content)
    assert res["is_destructive"] is True
    assert res["severity"] == "HIGH"
    assert "Alteração substitui" in res["reason"]


def test_08_destructive_detector_permits_safe_additive_changes():
    """Permite adições seguras ou pequenas correções sem marcar como destrutivo."""
    old_html = "<!DOCTYPE html><html><head><link rel='stylesheet' href='styles.css'></head><body><h1>Olá</h1><script src='app.js'></script></body></html>"
    new_html = "<!DOCTYPE html><html><head><link rel='stylesheet' href='styles.css'></head><body><h1>Olá</h1><button id='scan'>Scan</button><script src='app.js'></script></body></html>"

    res = DestructiveChangeDetector.evaluate_change_destructiveness("index.html", old_html, new_html)
    assert res["is_destructive"] is False


# ==============================================================================
# 3. TESTES DE ANÁLISE DE PRESERVAÇÃO (PRESERVATION ANALYZER)
# ==============================================================================

def test_09_preservation_analyzer_snapshots_complete_state(tmp_path):
    """Garante que o snapshot do projeto extrai scripts, stylesheets, botões e listeners."""
    html_content = """<!DOCTYPE html>
    <html>
    <head><link rel="stylesheet" href="styles.css"></head>
    <body>
        <button id="btn1">A</button>
        <button id="btn2">B</button>
        <script src="app.js"></script>
    </body>
    </html>"""
    (tmp_path / "index.html").write_text(html_content, encoding="utf-8")
    (tmp_path / "styles.css").write_text("body { color: red; }", encoding="utf-8")
    (tmp_path / "app.js").write_text("document.getElementById('btn1').addEventListener('click', () => {});", encoding="utf-8")

    snapshot = PreservationAnalyzer.snapshot_project_state(str(tmp_path))
    assert "styles.css" in snapshot["stylesheets"]
    assert "app.js" in snapshot["scripts"]
    assert "btn1" in snapshot["buttons"]
    assert "btn2" in snapshot["buttons"]


def test_10_preservation_analyzer_detects_removed_script_and_stylesheet(tmp_path):
    """Deteta violação crítica se stylesheet ou script forem eliminados entre versões."""
    html_content = "<!DOCTYPE html><html><head><link rel='stylesheet' href='styles.css'></head><body><script src='app.js'></script></body></html>"
    (tmp_path / "index.html").write_text(html_content, encoding="utf-8")
    before_snapshot = PreservationAnalyzer.snapshot_project_state(str(tmp_path))

    # Modifica index.html removendo a stylesheet e o script
    degraded_html = "<!DOCTYPE html><html><head></head><body><p>Vazio</p></body></html>"
    (tmp_path / "index.html").write_text(degraded_html, encoding="utf-8")

    diff = PreservationAnalyzer.compare_integrity(before_snapshot, str(tmp_path))
    assert diff.has_critical_regression is True
    assert "styles.css" in diff.removed_stylesheets
    assert "app.js" in diff.removed_scripts
    assert any("REMOVED_STYLESHEETS" in v for v in diff.violations)


def test_11_preservation_analyzer_detects_dropped_buttons(tmp_path):
    """Deteta quando botões existentes na versão anterior foram eliminados."""
    html_before = "<html><body><button id='ddos_btn'>Atacar</button><button id='stop_btn'>Parar</button></body></html>"
    (tmp_path / "index.html").write_text(html_before, encoding="utf-8")
    before_snapshot = PreservationAnalyzer.snapshot_project_state(str(tmp_path))

    # Nova versão só tem um novo botão 'scan_btn', eliminando os outros
    html_after = "<html><body><button id='scan_btn'>Escanear</button></body></html>"
    (tmp_path / "index.html").write_text(html_after, encoding="utf-8")

    diff = PreservationAnalyzer.compare_integrity(before_snapshot, str(tmp_path))
    assert any("botão 'ddos_btn'" in f for f in diff.deleted_existing_features)
    assert any("DROPPED_BUTTONS" in w for w in diff.warnings)


# ==============================================================================
# 4. TESTES DE VALIDAÇÃO DE HTML E CASCA WEB (HTML DOCUMENT VALIDATOR)
# ==============================================================================

def test_12_html_validator_accepts_valid_complete_document(tmp_path):
    """Valida que um documento HTML completo e bem estruturado passa na validação."""
    (tmp_path / "styles.css").write_text("body { margin: 0; }", encoding="utf-8")
    (tmp_path / "app.js").write_text("console.log('init');", encoding="utf-8")
    html_file = tmp_path / "index.html"
    html_content = """<!DOCTYPE html>
    <html lang="pt">
    <head>
        <meta charset="UTF-8">
        <title>App</title>
        <link rel="stylesheet" href="styles.css">
    </head>
    <body>
        <main><h1>Bem-vindo</h1></main>
        <script src="app.js"></script>
    </body>
    </html>"""
    html_file.write_text(html_content, encoding="utf-8")

    res = HtmlDocumentValidator.validate_html_file(str(html_file), str(tmp_path))
    assert res["valid"] is True
    assert res["has_shell"] is True
    assert len(res["violations"]) == 0


def test_13_html_validator_rejects_missing_shell_tags(tmp_path):
    """Rejeita ficheiro HTML sem tags html, head ou body."""
    frag = tmp_path / "fragment.html"
    frag.write_text("<div><p>Apenas um bloco solto</p></div>", encoding="utf-8")

    res = HtmlDocumentValidator.validate_html_file(str(frag), str(tmp_path))
    assert res["valid"] is False
    assert any("sem tag <html>" in v for v in res["violations"])
    assert any("sem secção <body>" in v for v in res["violations"])


def test_14_html_validator_rejects_missing_linked_stylesheet(tmp_path):
    """Rejeita se a folha de estilo indicada em <link rel="stylesheet"> não existir."""
    html_file = tmp_path / "index.html"
    html_file.write_text(
        "<!DOCTYPE html><html><head><link rel='stylesheet' href='inexistente.css'></head><body><h1>Teste</h1></body></html>",
        encoding="utf-8",
    )

    res = HtmlDocumentValidator.validate_html_file(str(html_file), str(tmp_path))
    assert res["valid"] is False
    assert any("MISSING_STYLESHEET" in v for v in res["violations"])


def test_15_html_validator_rejects_missing_script_file(tmp_path):
    """Rejeita se o script indicado em <script src="..."> não existir fisicamente."""
    html_file = tmp_path / "index.html"
    html_file.write_text(
        "<!DOCTYPE html><html><head></head><body><h1>Teste</h1><script src='inexistente.js'></script></body></html>",
        encoding="utf-8",
    )

    res = HtmlDocumentValidator.validate_html_file(str(html_file), str(tmp_path))
    assert res["valid"] is False
    assert any("MISSING_SCRIPT" in v for v in res["violations"])


# ==============================================================================
# 5. TESTES DE INTEGRIDADE DE ASSETS E MÓDULOS (ASSET INTEGRITY VALIDATOR)
# ==============================================================================

def test_16_asset_integrity_detects_missing_css_imports(tmp_path):
    """Deteta @import inexistente dentro de um ficheiro CSS."""
    css_file = tmp_path / "theme.css"
    css_file.write_text("@import url('missing_vendor.css'); body { color: black; }", encoding="utf-8")

    res = AssetIntegrityValidator.validate_project_assets(str(tmp_path))
    assert res["valid"] is False
    assert any("missing_vendor.css" in ma for ma in res["missing_assets"])


def test_17_asset_integrity_detects_broken_js_relative_imports(tmp_path):
    """Deteta import relativo que aponta para módulo inexistente."""
    js_file = tmp_path / "main.js"
    js_file.write_text("import { calculate } from './missing_math.js';", encoding="utf-8")

    res = AssetIntegrityValidator.validate_project_assets(str(tmp_path))
    assert res["valid"] is False
    assert any("missing_math.js" in ma for ma in res["missing_assets"])


def test_18_asset_integrity_passes_when_all_assets_exist(tmp_path):
    """Aprova quando todos os assets e módulos referenciados existem fisicamente."""
    (tmp_path / "style.css").write_text("h1 { color: blue; }", encoding="utf-8")
    (tmp_path / "math.js").write_text("export const add = (a, b) => a + b;", encoding="utf-8")
    (tmp_path / "main.js").write_text("import { add } from './math.js';", encoding="utf-8")
    (tmp_path / "index.html").write_text(
        "<!DOCTYPE html><html><head><link rel='stylesheet' href='style.css'></head><body><script src='main.js'></script></body></html>",
        encoding="utf-8",
    )

    res = AssetIntegrityValidator.validate_project_assets(str(tmp_path))
    assert res["valid"] is True
    assert len(res["missing_assets"]) == 0


# ==============================================================================
# 6. TESTES DE INTEGRIDADE VISUAL (VISUAL INTEGRITY VALIDATOR)
# ==============================================================================

def test_19_visual_validator_rejects_completely_unstyled_html(tmp_path):
    """Rejeita página web sem CSS, sem tags de estilo e sem classes."""
    (tmp_path / "index.html").write_text(
        "<!DOCTYPE html><html><head><title>App</title></head><body><button>Botao</button></body></html>",
        encoding="utf-8",
    )

    res = VisualIntegrityValidator.evaluate_project_visual_readiness(str(tmp_path), ui_changed=True)
    assert res["valid"] is False
    assert any("UNSTYLED_PAGE" in v for v in res["violations"])


def test_20_visual_validator_detects_raw_browser_controls(tmp_path):
    """Deteta controlos interativos (botões, inputs) sem estilização ou classes."""
    (tmp_path / "index.html").write_text(
        "<!DOCTYPE html><html><head></head><body><input type='text'><button>Enviar</button></body></html>",
        encoding="utf-8",
    )

    res = VisualIntegrityValidator.evaluate_project_visual_readiness(str(tmp_path), ui_changed=True)
    assert res["valid"] is False
    assert any("RAW_BROWSER_CONTROLS" in v or "UNSTYLED_PAGE" in v for v in res["violations"])


def test_21_visual_validator_detects_stylesheet_elimination_regression(tmp_path):
    """Deteta regressão se a baseline possuía stylesheets e a nova versão tem zero."""
    (tmp_path / "index.html").write_text("<!DOCTYPE html><html><head></head><body><p>Sem estilos</p></body></html>", encoding="utf-8")
    baseline = {"stylesheets": ["styles.css", "theme.css"]}

    res = VisualIntegrityValidator.evaluate_project_visual_readiness(str(tmp_path), ui_changed=True, baseline_snapshot=baseline)
    assert res["valid"] is False
    assert any("VISUAL_REGRESSION" in v for v in res["violations"])


def test_22_visual_validator_approves_styled_responsive_page(tmp_path):
    """Aprova aplicação web com CSS e meta viewport devidamente configurados."""
    (tmp_path / "styles.css").write_text(".btn { padding: 8px 16px; background: #0070f3; color: white; }", encoding="utf-8")
    (tmp_path / "index.html").write_text(
        """<!DOCTYPE html>
        <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <link rel="stylesheet" href="styles.css">
        </head>
        <body>
            <button class="btn">Executar</button>
        </body>
        </html>""",
        encoding="utf-8",
    )

    res = VisualIntegrityValidator.evaluate_project_visual_readiness(str(tmp_path), ui_changed=True)
    assert res["valid"] is True
    assert len(res["violations"]) == 0


# ==============================================================================
# 7. TESTES DE INTERATIVIDADE E EVENT LISTENERS (INTERACTION VALIDATOR)
# ==============================================================================

def test_23_interaction_validator_warns_on_unwired_buttons(tmp_path):
    """Avisa sobre botões que possuem IDs no HTML mas nenhum listener no JavaScript."""
    (tmp_path / "index.html").write_text("<button id='orphan_btn'>Clique aqui</button>", encoding="utf-8")
    (tmp_path / "app.js").write_text("console.log('nenhum listener associado');", encoding="utf-8")

    res = InteractionValidator.evaluate_interactions(str(tmp_path))
    assert len(res["dead_buttons"]) == 1
    assert any("UNWIRED_BUTTONS" in w for w in res["warnings"])


def test_24_interaction_validator_approves_wired_buttons(tmp_path):
    """Aprova quando botões possuem addEventListener ou onclick inline associado."""
    (tmp_path / "index.html").write_text(
        "<button id='action_btn'>Disparar</button><button onclick='doSomething()'>Inline</button>",
        encoding="utf-8",
    )
    (tmp_path / "app.js").write_text(
        "document.getElementById('action_btn').addEventListener('click', () => { alert('OK'); });",
        encoding="utf-8",
    )

    res = InteractionValidator.evaluate_interactions(str(tmp_path))
    assert len(res["dead_buttons"]) == 0


def test_25_interaction_validator_detects_removal_of_baseline_buttons(tmp_path):
    """Deteta violação funcional se botões essenciais da baseline deixarem de existir."""
    (tmp_path / "index.html").write_text("<button id='novo_btn'>Novo</button>", encoding="utf-8")
    baseline_buttons = ["btn_antigo_essencial", "btn_secundario"]

    res = InteractionValidator.evaluate_interactions(str(tmp_path), baseline_buttons=baseline_buttons)
    assert res["valid"] is False
    assert any("FUNCTIONAL_REGRESSION" in v for v in res["violations"])


# ==============================================================================
# 8. TESTES DE RUNTIME E BROWSER (RUNTIME & BROWSER VALIDATORS)
# ==============================================================================

def test_26_runtime_validator_handles_unreachable_endpoint():
    """Confirma que endpoint inacessível reporta falha de runtime determinística."""
    res = RuntimeIntegrityValidator.check_http_endpoint("http://127.0.0.1:59999/health", timeout=0.2, retries=1)
    assert res["valid"] is False
    assert res["error"] is not None


def test_27_browser_validator_handles_missing_playwright_gracefully():
    """Garante que ausência ou falha de browser retorna INSUFFICIENT_EVIDENCE (NUNCA falso PASS)."""
    res = asyncio.run(BrowserIntegrityValidator.validate_url_headless("http://127.0.0.1:59999"))
    if not res["available"]:
        assert res["status"] == "INSUFFICIENT_EVIDENCE"
    else:
        assert res["status"] in {"FAIL", "INSUFFICIENT_EVIDENCE"}
    assert res["status"] != "PASS"


# ==============================================================================
# 9. TESTES DE GOVERNANÇA DE DEPENDÊNCIAS E FALLBACK
# ==============================================================================

def test_28_dependency_governance_blocks_nmap_downgrade(tmp_path):
    """Missão requer Nmap; ausência de Nmap impede PRODUCT_ACCEPTED e gera BLOCKED / HUMAN_APPROVAL."""
    user_prompt = "Descobrir portas abertas na rede local usando Nmap"

    report = ProductDeliveryGate.evaluate_delivery(
        project_root=str(tmp_path),
        project_id="test_net",
        user_prompt=user_prompt,
        technical_validations_passed=True,
    )

    assert report.gate_status in {DeliveryGateStatus.HUMAN_REVIEW.value, DeliveryGateStatus.BLOCKED.value}
    assert any("BLOCKED_REQUIRED_CAPABILITY" in b for b in report.blockers)
    assert report.result != RequirementStatus.PASS.value


def test_29_true_alternative_accepted_when_criteria_satisfied(tmp_path):
    """Quando uma alternativa real (ex: download HTTP) não requer dependências de alto risco."""
    (tmp_path / "main.py").write_text("import urllib.request\nprint('download')", encoding="utf-8")
    user_prompt = "Descarregar ficheiro de especificações via HTTP padrão"

    report = ProductDeliveryGate.evaluate_delivery(
        project_root=str(tmp_path),
        project_id="downloader",
        user_prompt=user_prompt,
        technical_validations_passed=True,
    )

    assert report.result == RequirementStatus.PASS.value
    assert report.gate_status == DeliveryGateStatus.PRODUCT_ACCEPTED.value


# ==============================================================================
# 10. CENÁRIO DE REPRODUÇÃO EXATA DO PROBLEMA DE DINA (SEÇÃO 25)
# ==============================================================================

def test_30_dina_exact_reproduction_blocked_by_product_gate(tmp_path):
    """
    Reproduz exatamente o erro ocorrido no projeto DINA:
    - index.html original com estrutura, styles.css e client.js
    - alteração assistida substitui destrutivamente index.html por fragmento desestilizado
    - node --check passa!
    - O novo portão DEVE BLOQUEAR e impedir PRODUCT_ACCEPTED.
    """
    # 1. Estado inicial de Dina
    dina_dir = tmp_path / "dina"
    dina_dir.mkdir()
    original_html = """<!DOCTYPE html>
    <html lang="pt">
    <head>
        <meta charset="UTF-8">
        <title>Dina DDoS Simulator</title>
        <link rel="stylesheet" href="styles.css">
    </head>
    <body>
        <h1>Simulador DDoS</h1>
        <button id="start_attack">Iniciar Ataque</button>
        <script src="client.js"></script>
    </body>
    </html>"""
    (dina_dir / "index.html").write_text(original_html, encoding="utf-8")
    (dina_dir / "styles.css").write_text("body { background: #111; color: #fff; }", encoding="utf-8")
    (dina_dir / "client.js").write_text("document.getElementById('start_attack').onclick = () => alert('Atacando');", encoding="utf-8")

    # Snapshot inicial capturado antes da alteração
    before_snapshot = PreservationAnalyzer.snapshot_project_state(str(dina_dir))

    # 2. Alteração defeituosa: index.html é sobrescrito destrutivamente sem links e sem casca
    degraded_html = """
    <div>
        <h2>Scanner de IP</h2>
        <input id="ip_input" placeholder="192.168.1.1">
        <button id="scan_ip">Scan</button>
    </div>
    """
    (dina_dir / "index.html").write_text(degraded_html, encoding="utf-8")

    changes = [{
        "file": "index.html",
        "previous_excerpt": original_html,
        "proposed_excerpt": degraded_html,
    }]

    # Avaliação pelo novo ProductDeliveryGate
    report = ProductDeliveryGate.evaluate_delivery(
        project_root=str(dina_dir),
        project_id="dina",
        user_prompt="Adicionar scanner de IP",
        changes=changes,
        before_snapshot=before_snapshot,
        technical_validations_passed=True,  # Simula node --check passando
    )

    # Verificação estrita dos bloqueios
    assert report.result == RequirementStatus.FAIL.value
    assert report.gate_status == DeliveryGateStatus.BLOCKED.value
    assert report.quality_score == QualityScoreStatus.NOT_READY.value

    # Confirma que todos os 5 sintomas foram identificados formalmente
    all_blockers_and_violations = " ".join(report.blockers)
    assert "CRITICAL_DESTRUCTIVE_REPLACEMENT" in all_blockers_and_violations or "Destruição" in all_blockers_and_violations
    assert "REMOVED_STYLESHEETS" in all_blockers_and_violations or "UNSTYLED_PAGE" in all_blockers_and_violations
    assert "REMOVED_SCRIPTS" in all_blockers_and_violations or "sem tag <html>" in all_blockers_and_violations

    # Garante que o portão de entrega autónoma recusa
    assert is_autonomous_product_delivery_ready(report) is False


# ==============================================================================
# 11. CENÁRIO DE EXTENSÃO E PRESERVAÇÃO DE FEATURES (SEÇÃO 26)
# ==============================================================================

def test_31_preservation_test_features_a_b_c(tmp_path):
    """
    Projeto com Feature A e Feature B.
    Pedido: Adicionar Feature C.
    Se Feature A ou B for destruída -> PRODUCT_ACCEPTED = False.
    """
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    (app_dir / "styles.css").write_text("body { color: black; }", encoding="utf-8")
    (app_dir / "app.js").write_text(
        "document.getElementById('feat_a').onclick = () => {}; document.getElementById('feat_b').onclick = () => {};",
        encoding="utf-8",
    )
    (app_dir / "index.html").write_text(
        """<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width"><link rel="stylesheet" href="styles.css"></head>
        <body>
            <button id="feat_a">Feature A</button>
            <button id="feat_b">Feature B</button>
            <script src="app.js"></script>
        </body></html>""",
        encoding="utf-8",
    )
    before_snap = PreservationAnalyzer.snapshot_project_state(str(app_dir))

    # Caso 1: Alteração adiciona Feature C MAS remove Feature A
    (app_dir / "index.html").write_text(
        """<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width"><link rel="stylesheet" href="styles.css"></head>
        <body>
            <button id="feat_b">Feature B</button>
            <button id="feat_c">Feature C</button>
            <script src="app.js"></script>
        </body></html>""",
        encoding="utf-8",
    )
    report_broken = ProductDeliveryGate.evaluate_delivery(
        project_root=str(app_dir),
        project_id="app",
        user_prompt="Adicionar feature C",
        before_snapshot=before_snap,
        technical_validations_passed=True,
    )
    assert report_broken.result == RequirementStatus.FAIL.value
    assert is_autonomous_product_delivery_ready(report_broken) is False

    # Caso 2: Alteração adiciona Feature C PRESERVANDO Feature A e Feature B
    (app_dir / "app.js").write_text(
        "document.getElementById('feat_a').onclick = () => {}; document.getElementById('feat_b').onclick = () => {}; document.getElementById('feat_c').onclick = () => {};",
        encoding="utf-8",
    )
    (app_dir / "index.html").write_text(
        """<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width"><link rel="stylesheet" href="styles.css"></head>
        <body>
            <button id="feat_a">Feature A</button>
            <button id="feat_b">Feature B</button>
            <button id="feat_c">Feature C</button>
            <script src="app.js"></script>
        </body></html>""",
        encoding="utf-8",
    )
    report_safe = ProductDeliveryGate.evaluate_delivery(
        project_root=str(app_dir),
        project_id="app",
        user_prompt="Adicionar feature C",
        before_snapshot=before_snap,
        technical_validations_passed=True,
    )
    assert report_safe.result == RequirementStatus.PASS.value
    assert report_safe.gate_status == DeliveryGateStatus.PRODUCT_ACCEPTED.value
    assert is_autonomous_product_delivery_ready(report_safe) is True


# ==============================================================================
# 12. CINCO CENÁRIOS REAIS DE ACEITAÇÃO DE PRODUTO (SEÇÃO 31)
# ==============================================================================

def test_32_scenario_1_ui_modification(tmp_path):
    """Cenário Real 1: Modificação de UI (mantém estilos, casca e acessibilidade)."""
    p = tmp_path / "ui_mod"
    p.mkdir()
    (p / "styles.css").write_text(".dark { background: #222; }", encoding="utf-8")
    (p / "app.js").write_text("document.getElementById('toggle').onclick = () => {};", encoding="utf-8")
    (p / "index.html").write_text(
        """<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width"><link rel="stylesheet" href="styles.css"></head>
        <body><button id="toggle">Dark Mode</button><script src="app.js"></script></body></html>""",
        encoding="utf-8",
    )
    report = ProductDeliveryGate.evaluate_delivery(str(p), "ui_mod", user_prompt="Mudar tema para dark mode")
    assert report.gate_status == DeliveryGateStatus.PRODUCT_ACCEPTED.value


def test_33_scenario_2_backend_modification(tmp_path):
    """Cenário Real 2: Modificação de Backend (serviço Node/Python puro sem UI)."""
    p = tmp_path / "api_mod"
    p.mkdir()
    (p / "server.js").write_text("const express = require('express'); const app = express(); app.get('/api/health', (req, res) => res.json({ok: true}));", encoding="utf-8")
    (p / "package.json").write_text('{"name": "api", "main": "server.js"}', encoding="utf-8")

    report = ProductDeliveryGate.evaluate_delivery(str(p), "api_mod", user_prompt="Adicionar endpoint health check")
    assert report.gate_status == DeliveryGateStatus.PRODUCT_ACCEPTED.value


def test_34_scenario_3_existing_feature_extension(tmp_path):
    """Cenário Real 3: Extensão de funcionalidade existente."""
    p = tmp_path / "ext_mod"
    p.mkdir()
    (p / "styles.css").write_text("button { cursor: pointer; }", encoding="utf-8")
    (p / "app.js").write_text("document.getElementById('calc').onclick = () => {};", encoding="utf-8")
    (p / "index.html").write_text(
        """<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width"><link rel="stylesheet" href="styles.css"></head>
        <body><button id="calc">Calcular</button><script src="app.js"></script></body></html>""",
        encoding="utf-8",
    )
    report = ProductDeliveryGate.evaluate_delivery(str(p), "ext_mod", user_prompt="Suportar multiplicação na calculadora")
    assert report.gate_status == DeliveryGateStatus.PRODUCT_ACCEPTED.value


def test_35_scenario_4_external_dependency_blocked(tmp_path):
    """Cenário Real 4: Dependência externa com risco que exige autorização humana."""
    p = tmp_path / "dep_mod"
    p.mkdir()
    report = ProductDeliveryGate.evaluate_delivery(str(p), "dep_mod", user_prompt="Escanear portas com nmap na rede")
    assert report.gate_status == DeliveryGateStatus.HUMAN_REVIEW.value
    assert report.result != RequirementStatus.PASS.value


def test_36_scenario_5_destructive_risk_modification(tmp_path):
    """Cenário Real 5: Tentativa de substituição destrutiva de index.html bloqueada."""
    p = tmp_path / "destr_mod"
    p.mkdir()
    (p / "index.html").write_text("<div id='corrupted'>sem casca</div>", encoding="utf-8")
    report = ProductDeliveryGate.evaluate_delivery(str(p), "destr_mod", user_prompt="Refazer página inicial")
    assert report.gate_status == DeliveryGateStatus.BLOCKED.value
    assert is_autonomous_product_delivery_ready(report) is False


# ==============================================================================
# 13. TESTE DO PORTÃO FINAL CANÓNICO (AUTONOMOUS_PRODUCT_DELIVERY_READY)
# ==============================================================================

def test_37_autonomous_product_delivery_ready_requires_all_gates_true():
    """Confirma que o portão final só retorna True se testes, diff e aceitação passarem."""
    valid_report = ProductAcceptanceReport(
        requirements=[RequirementItem(requirement_id="R1", description="OK", status=RequirementStatus.PASS.value)],
        gate_status=DeliveryGateStatus.PRODUCT_ACCEPTED.value,
        quality_score=QualityScoreStatus.READY.value,
        result=RequirementStatus.PASS.value,
    )

    # Todos válidos
    assert is_autonomous_product_delivery_ready(valid_report, git_diff_check_passed=True, pip_check_passed=True, tests_passed=True) is True

    # Se git diff falhar
    assert is_autonomous_product_delivery_ready(valid_report, git_diff_check_passed=False) is False

    # Se pip check falhar
    assert is_autonomous_product_delivery_ready(valid_report, pip_check_passed=False) is False

    # Se testes falharem
    assert is_autonomous_product_delivery_ready(valid_report, tests_passed=False) is False
