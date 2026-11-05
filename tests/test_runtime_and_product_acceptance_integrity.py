"""
JARVIS OS — Bateria de Testes de Regressão: Integridade de Runtime, Preview e Aceitação de Produto.
Implementa os 16 Cenários Canónicos definidos na Secção 10:

1. Código alterado e runtime antigo (STALE_RUNTIME).
2. Reinício correto do preview gerido (Controlled Preview Lifecycle).
3. Processo de outra aplicação na mesma porta (PORT_CONFLICT_UNOWNED - nunca mata PIDs alheios).
4. HTML atualizado com asset JavaScript antigo (STALE_SERVED_ASSET).
5. API correta e frontend desatualizado (FRONTEND_CONTRACT_DESYNC).
6. API com contrato incompatível com o frontend (BACKEND_CONTRACT_VIOLATION).
7. Botão presente sem comportamento (INERT_CONTROL_ERROR).
8. Carregamento com falhas de rede (ASSET_HTTP_404_OR_NETWORK_ERROR).
9. Preview indisponível (RUNTIME_UNAVAILABLE).
10. Browser indisponível (INSUFFICIENT_EVIDENCE / BROWSER_QA_FAILED).
11. Versão correta, mas interface funcionalmente incorreta (DOM_DATA_RENDER_FAILURE).
12. Cache-busting correto (Query param ou bundler hash verificado contra disco).
13. Dados GeoIP ausentes ou incompletos (Sem GPS falso nem ISP alucinado).
14. Resolução DNS sem hostname (Tratamento seguro de ausência de PTR).
15. Retoma de missão após falha do preview (Mission Resumption).
16. Entrega com todas as verificações aplicáveis aprovadas (PRODUCT_ACCEPTED em todos os 7 níveis).
"""

import hashlib
import http.server
import json
import os
import socketserver
import threading
import time
from pathlib import Path
from typing import Any, Dict
import pytest

from security.delivery_governance import (
    AcceptanceLevel,
    DeliveryGateStatus,
    ProductAcceptanceReport,
    ProductDeliveryGate,
    RequirementStatus,
    is_autonomous_product_delivery_ready,
)
from security.delivery_governance.contract_validator import ContractValidator
from security.delivery_governance.preview_lifecycle import PreviewLifecycleManager
from security.delivery_governance.real_browser_qa import RealBrowserQAValidator
from security.delivery_governance.runtime_identity import RuntimeIdentity, RuntimeTracker
from security.delivery_governance.validators.asset_validator import AssetIntegrityValidator


# ==============================================================================
# CENÁRIO 1: Código alterado e runtime antigo (STALE_RUNTIME)
# ==============================================================================
def test_scenario_01_code_altered_stale_runtime(tmp_path, monkeypatch):
    """
    Cenário 1: O código foi alterado no disco, mas o processo foi iniciado antes dessa alteração.
    O gate deve detetar STALE_RUNTIME e bloquear a entrega.
    """
    proj_dir = tmp_path / "proj_dina_stale"
    proj_dir.mkdir()
    app_js = proj_dir / "app.js"
    app_js.write_text("console.log('v2 updated code');", encoding="utf-8")
    (proj_dir / "index.html").write_text("<!DOCTYPE html><html><body><h1>Dina</h1></body></html>", encoding="utf-8")

    # Simula processo iniciado no passado (100 segundos antes)
    past_start_time = time.time() - 100.0

    mock_ident = RuntimeIdentity(
        project_id="proj_dina_stale",
        preview_id="prev-01",
        process_id=99999,
        command_line="node app.js",
        working_directory=str(proj_dir),
        port=3000,
        endpoint="http://127.0.0.1:3000",
        start_time=past_start_time,
        is_running=True,
        is_owned=True,
        is_stale=True,
        stale_reason="Ficheiro app.js foi modificado após o arranque do processo",
        healthcheck_ok=True,
        status="STALE_RUNTIME",
    )

    monkeypatch.setattr(RuntimeTracker, "inspect_runtime", lambda *args, **kwargs: mock_ident)

    report = ProductDeliveryGate.evaluate_delivery(
        project_root=str(proj_dir),
        project_id="proj_dina_stale",
        runtime_endpoint="http://127.0.0.1:3000",
        user_prompt="Atualizar deteção de rede",
    )

    assert report.gate_status == DeliveryGateStatus.BLOCKED.value
    assert report.result == RequirementStatus.FAIL.value
    assert any("STALE_RUNTIME" in b for b in report.blockers)
    assert report.validation_levels[AcceptanceLevel.RUNTIME_VERSION_VALIDATED.value] is False
    assert report.validation_levels[AcceptanceLevel.PRODUCT_ACCEPTED.value] is False
    assert is_autonomous_product_delivery_ready(report) is False
    assert "Preview desatualizado" in report.user_summary


# ==============================================================================
# CENÁRIO 2: Reinício correto do preview gerido
# ==============================================================================
def test_scenario_02_proper_managed_preview_restart(tmp_path, monkeypatch):
    """
    Cenário 2: O preview gerenciado é reiniciado de forma controlada após confirmar propriedade.
    Após reinício e verificação de saúde, a versão servida é validada como fresca.
    """
    proj_dir = tmp_path / "proj_restart"
    proj_dir.mkdir()
    (proj_dir / "app.js").write_text("console.log('fresh');", encoding="utf-8")
    (proj_dir / "index.html").write_text("<!DOCTYPE html><html><body><h1>Fresh</h1></body></html>", encoding="utf-8")

    restarted = False

    def mock_ensure_fresh(*args, **kwargs):
        nonlocal restarted
        restarted = True
        return {"success": True, "action": "RESTARTED", "port": 3000}

    now = time.time()
    fresh_ident = RuntimeIdentity(
        project_id="proj_restart",
        preview_id="prev-02",
        process_id=12345,
        command_line="node app.js",
        working_directory=str(proj_dir),
        port=3000,
        endpoint="http://127.0.0.1:3000",
        start_time=now + 5.0,
        is_running=True,
        is_owned=True,
        is_stale=False,
        healthcheck_ok=True,
        status="RUNNING_FRESH",
    )

    monkeypatch.setattr(PreviewLifecycleManager, "ensure_fresh_preview", mock_ensure_fresh)
    monkeypatch.setattr(RuntimeTracker, "inspect_runtime", lambda *args, **kwargs: fresh_ident)
    monkeypatch.setattr(AssetIntegrityValidator, "validate_served_assets", lambda *a, **k: {"valid": True, "violations": []})

    report = ProductDeliveryGate.evaluate_delivery(
        project_root=str(proj_dir),
        project_id="proj_restart",
        runtime_endpoint="http://127.0.0.1:3000",
        auto_manage_preview=True,
        preview_start_command="node app.js",
        user_prompt="Reiniciar e validar",
    )

    assert restarted is True
    assert report.validation_levels[AcceptanceLevel.RUNTIME_VERSION_VALIDATED.value] is True
    assert not any("STALE_RUNTIME" in b for b in report.blockers)


# ==============================================================================
# CENÁRIO 3: Processo de outra aplicação na mesma porta
# ==============================================================================
def test_scenario_03_foreign_process_on_target_port(tmp_path, monkeypatch):
    """
    Cenário 3: A porta está ocupada por um processo que não pertence ao projeto.
    O JARVIS NUNCA termina o processo alheio e bloqueia com PORT_CONFLICT_UNOWNED.
    """
    proj_dir = tmp_path / "proj_target"
    proj_dir.mkdir()
    (proj_dir / "index.html").write_text("<!DOCTYPE html><html><body><h1>App</h1></body></html>", encoding="utf-8")

    foreign_ident = RuntimeIdentity(
        project_id="proj_target",
        preview_id="",
        process_id=8888,
        command_line="python -m http.server 3000 (c:\\other_company\\finance_app)",
        working_directory="c:\\other_company\\finance_app",
        port=3000,
        endpoint="http://127.0.0.1:3000",
        start_time=time.time(),
        is_running=True,
        is_owned=False,  # NÃO PERTENCE AO PROJETO
        is_stale=False,
        healthcheck_ok=True,
        status="PORT_CONFLICT_UNOWNED",
    )

    monkeypatch.setattr(RuntimeTracker, "inspect_runtime", lambda *args, **kwargs: foreign_ident)

    report = ProductDeliveryGate.evaluate_delivery(
        project_root=str(proj_dir),
        project_id="proj_target",
        runtime_endpoint="http://127.0.0.1:3000",
        user_prompt="Iniciar preview",
    )

    assert report.gate_status == DeliveryGateStatus.BLOCKED.value
    assert any("PORT_CONFLICT_UNOWNED" in b for b in report.blockers)
    assert report.validation_levels[AcceptanceLevel.RUNTIME_VERSION_VALIDATED.value] is False
    assert is_autonomous_product_delivery_ready(report) is False
    assert "Porta ocupada por processo externo" in report.user_summary


# ==============================================================================
# CENÁRIO 4: HTML atualizado com asset JavaScript antigo (STALE_SERVED_ASSET)
# ==============================================================================
def test_scenario_04_html_updated_stale_served_js_asset(tmp_path, monkeypatch):
    """
    Cenário 4: O ficheiro client.js no disco foi atualizado, mas o servidor/browser entrega
    uma versão antiga em cache cujo hash SHA256 difere do disco.
    """
    proj_dir = tmp_path / "proj_cache_stale"
    proj_dir.mkdir()
    (proj_dir / "index.html").write_text(
        '<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width"></head><body><script src="client.js"></script></body></html>',
        encoding="utf-8",
    )
    (proj_dir / "client.js").write_text("console.log('client v2 with rich cards');", encoding="utf-8")

    fresh_ident = RuntimeIdentity(
        project_id="proj_cache_stale",
        preview_id="prev-04",
        process_id=1111,
        command_line="node server.js",
        working_directory=str(proj_dir),
        port=3000,
        endpoint="http://127.0.0.1:3000",
        start_time=time.time() + 10.0,
        is_running=True,
        is_owned=True,
        is_stale=False,
        healthcheck_ok=True,
        status="RUNNING_FRESH",
    )

    monkeypatch.setattr(RuntimeTracker, "inspect_runtime", lambda *args, **kwargs: fresh_ident)

    # Simula asset validator detetando hash SHA256 desatualizado na resposta HTTP
    def mock_validate_served(*args, **kwargs):
        return {
            "valid": False,
            "violations": ["HASH_MISMATCH: Asset servido client.js tem hash SHA256 diferente do disco (cache ativo)"],
            "assets": [],
        }

    monkeypatch.setattr(AssetIntegrityValidator, "validate_served_assets", mock_validate_served)

    report = ProductDeliveryGate.evaluate_delivery(
        project_root=str(proj_dir),
        project_id="proj_cache_stale",
        runtime_endpoint="http://127.0.0.1:3000",
        user_prompt="Validar entrega com cache",
    )

    assert report.gate_status == DeliveryGateStatus.BLOCKED.value
    assert any("STALE_SERVED_ASSET" in b for b in report.blockers)
    assert report.validation_levels[AcceptanceLevel.RUNTIME_VERSION_VALIDATED.value] is False


# ==============================================================================
# CENÁRIO 5: API correta e frontend desatualizado (FRONTEND_CONTRACT_DESYNC)
# ==============================================================================
def test_scenario_05_api_correct_frontend_desynced():
    """
    Cenário 5 (Caso Dina): O backend envia 'devices' com IP, MAC, vendor e role,
    mas o frontend apenas consome 'ips' e contém um fallback silencioso que mascara
    a renderização dos novos cartões.
    """
    mock_payload = {
        "ips": ["192.168.1.1"],
        "devices": [{"ip": "192.168.1.1", "mac": "aa:bb:cc:dd:ee:ff", "vendor": "Asus", "role": "Gateway"}],
    }

    # Frontend desatualizado que só procura data.ips
    stale_frontend = """
    fetch('/scan-local-ips').then(r => r.json()).then(data => {
        const list = document.getElementById('list');
        if (data.ips) {
            data.ips.forEach(ip => { list.innerHTML += '<li>' + ip + '</li>'; });
        }
    });
    """

    res = ContractValidator.validate_local_scan_contract(mock_payload, stale_frontend)
    assert res["valid"] is False
    assert any("FRONTEND_CONTRACT_DESYNC" in v for v in res["violations"])


# ==============================================================================
# CENÁRIO 6: API com contrato incompatível com o frontend (BACKEND_VIOLATION)
# ==============================================================================
def test_scenario_06_api_contract_incompatible_with_frontend():
    """
    Cenário 6: O backend falha em devolver os campos estruturados esperados ('devices' ou 'targetIp').
    """
    broken_payload = {
        "status": "ok"  # Ausência de ips e devices
    }
    frontend_code = "if (data.devices) { data.devices.forEach(d => console.log(d.ip, d.mac)); }"

    res = ContractValidator.validate_local_scan_contract(broken_payload, frontend_code)
    assert res["valid"] is False
    assert any("BACKEND_CONTRACT_VIOLATION" in v for v in res["violations"])


# ==============================================================================
# CENÁRIO 7: Botão presente sem comportamento (INERT_CONTROL_ERROR)
# ==============================================================================
def test_scenario_07_inert_button_without_handler(tmp_path):
    """
    Cenário 7: O HTML introduz um botão (ex: #scanIpButton), mas o script da interface
    não adiciona qualquer listener ou manipulador onclick.
    """
    proj_dir = tmp_path / "proj_inert_button"
    proj_dir.mkdir()
    (proj_dir / "index.html").write_text(
        '<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width"></head><body><button id="scanIpButton">Scan</button><script src="client.js"></script></body></html>',
        encoding="utf-8",
    )
    (proj_dir / "client.js").write_text("console.log('no handler for scan button');", encoding="utf-8")

    report = ProductDeliveryGate.evaluate_delivery(
        project_root=str(proj_dir),
        project_id="proj_inert_button",
        user_prompt="Adicionar botão de scan",
    )

    assert report.gate_status == DeliveryGateStatus.BLOCKED.value
    assert any("FUNCTIONALITY_FAILURE" in b or "UNWIRED_BUTTON" in b or "DEAD_BUTTON" in b or "scanIpButton" in b for b in report.blockers)
    assert is_autonomous_product_delivery_ready(report) is False


# ==============================================================================
# CENÁRIO 8: Carregamento com falhas de rede (ASSET_HTTP_404)
# ==============================================================================
def test_scenario_08_served_assets_network_failures(tmp_path, monkeypatch):
    """
    Cenário 8: O servidor preview responde 404 a um script ou estilo essencial.
    """
    proj_dir = tmp_path / "proj_404"
    proj_dir.mkdir()
    (proj_dir / "index.html").write_text(
        '<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width"><link rel="stylesheet" href="missing.css"></head><body><h1>Hello</h1></body></html>',
        encoding="utf-8",
    )

    fresh_ident = RuntimeIdentity(
        project_id="proj_404",
        preview_id="p-08",
        process_id=3333,
        command_line="node s.js",
        working_directory=str(proj_dir),
        port=3000,
        endpoint="http://127.0.0.1:3000",
        start_time=time.time() + 10.0,
        is_running=True,
        is_owned=True,
        is_stale=False,
        healthcheck_ok=True,
        status="RUNNING_FRESH",
    )

    monkeypatch.setattr(RuntimeTracker, "inspect_runtime", lambda *args, **kwargs: fresh_ident)

    def mock_validate_404(*args, **kwargs):
        return {
            "valid": False,
            "violations": ["HTTP_ERROR: Asset missing.css devolveu código HTTP 404"],
            "assets": [],
        }

    monkeypatch.setattr(AssetIntegrityValidator, "validate_served_assets", mock_validate_404)

    report = ProductDeliveryGate.evaluate_delivery(
        project_root=str(proj_dir),
        project_id="proj_404",
        runtime_endpoint="http://127.0.0.1:3000",
        user_prompt="Verificar integridade de rede",
    )

    assert report.gate_status == DeliveryGateStatus.BLOCKED.value
    assert any("STALE_SERVED_ASSET" in b for b in report.blockers)


# ==============================================================================
# CENÁRIO 9: Preview indisponível (RUNTIME_UNAVAILABLE)
# ==============================================================================
def test_scenario_09_preview_unavailable_connection_refused(tmp_path, monkeypatch):
    """
    Cenário 9: O preview não está ativo ou não escuta na porta configurada.
    """
    proj_dir = tmp_path / "proj_offline"
    proj_dir.mkdir()
    (proj_dir / "index.html").write_text("<!DOCTYPE html><html><body>Offline</body></html>", encoding="utf-8")

    dead_ident = RuntimeIdentity(
        project_id="proj_offline",
        preview_id="",
        process_id=0,
        command_line="",
        working_directory="",
        port=3000,
        endpoint="http://127.0.0.1:3000",
        start_time=0.0,
        is_running=False,
        is_owned=False,
        is_stale=False,
        healthcheck_ok=False,
        status="RUNTIME_UNAVAILABLE",
    )

    monkeypatch.setattr(RuntimeTracker, "inspect_runtime", lambda *args, **kwargs: dead_ident)

    report = ProductDeliveryGate.evaluate_delivery(
        project_root=str(proj_dir),
        project_id="proj_offline",
        runtime_endpoint="http://127.0.0.1:3000",
        user_prompt="Validar preview",
    )

    assert report.gate_status == DeliveryGateStatus.BLOCKED.value
    assert any("RUNTIME_UNAVAILABLE" in b for b in report.blockers)
    assert report.validation_levels[AcceptanceLevel.RUNTIME_VERSION_VALIDATED.value] is False


# ==============================================================================
# CENÁRIO 10: Browser indisponível (INSUFFICIENT_EVIDENCE / BROWSER_QA_FAILED)
# ==============================================================================
def test_scenario_10_browser_unavailable_blocks_acceptance(tmp_path, monkeypatch):
    """
    Cenário 10: Browser QA foi solicitado mas o browser falha no arranque.
    O sistema não inventa aprovação e bloqueia PRODUCT_ACCEPTED com BROWSER_QA_FAILED.
    """
    proj_dir = tmp_path / "proj_no_browser"
    proj_dir.mkdir()
    (proj_dir / "index.html").write_text("<!DOCTYPE html><html><body>Test</body></html>", encoding="utf-8")

    fresh_ident = RuntimeIdentity(
        project_id="proj_no_browser",
        preview_id="p-10",
        process_id=4444,
        command_line="node s.js",
        working_directory=str(proj_dir),
        port=3000,
        endpoint="http://127.0.0.1:3000",
        start_time=time.time() + 10.0,
        is_running=True,
        is_owned=True,
        is_stale=False,
        healthcheck_ok=True,
        status="RUNNING_FRESH",
    )

    monkeypatch.setattr(RuntimeTracker, "inspect_runtime", lambda *args, **kwargs: fresh_ident)
    monkeypatch.setattr(AssetIntegrityValidator, "validate_served_assets", lambda *a, **k: {"valid": True, "violations": []})

    # Simula falha de browser
    monkeypatch.setattr(
        RealBrowserQAValidator,
        "execute_browser_qa",
        lambda *a, **k: {"valid": False, "error": "Playwright browser binary not reachable or crashed", "violations": []},
    )

    report = ProductDeliveryGate.evaluate_delivery(
        project_root=str(proj_dir),
        project_id="proj_no_browser",
        runtime_endpoint="http://127.0.0.1:3000",
        browser_test_requested=True,
        user_prompt="Executar Browser QA",
    )

    assert report.gate_status == DeliveryGateStatus.BLOCKED.value
    assert report.validation_levels[AcceptanceLevel.FUNCTIONAL_BROWSER_VALIDATED.value] is False
    assert report.validation_levels[AcceptanceLevel.PRODUCT_ACCEPTED.value] is False
    assert report.evidence["browser_tested"] is False


# ==============================================================================
# CENÁRIO 11: Versão correta, mas interface funcionalmente incorreta
# ==============================================================================
def test_scenario_11_fresh_version_but_dom_rendering_broken(tmp_path, monkeypatch):
    """
    Cenário 11: A versão e os assets são frescos, mas a interação no DOM
    não renderiza os elementos pretendidos (ex: cartões de dispositivos).
    """
    proj_dir = tmp_path / "proj_dom_broken"
    proj_dir.mkdir()
    (proj_dir / "index.html").write_text("<!DOCTYPE html><html><body><div id='deviceList'></div></body></html>", encoding="utf-8")

    fresh_ident = RuntimeIdentity(
        project_id="proj_dom_broken",
        preview_id="p-11",
        process_id=5555,
        command_line="node s.js",
        working_directory=str(proj_dir),
        port=3000,
        endpoint="http://127.0.0.1:3000",
        start_time=time.time() + 10.0,
        is_running=True,
        is_owned=True,
        is_stale=False,
        healthcheck_ok=True,
        status="RUNNING_FRESH",
    )

    monkeypatch.setattr(RuntimeTracker, "inspect_runtime", lambda *args, **kwargs: fresh_ident)
    monkeypatch.setattr(AssetIntegrityValidator, "validate_served_assets", lambda *a, **k: {"valid": True, "violations": []})

    # Browser QA deteta que o DOM permaneceu vazio após clicar
    monkeypatch.setattr(
        RealBrowserQAValidator,
        "execute_browser_qa",
        lambda *a, **k: {
            "valid": False,
            "error": "DOM assertion failed",
            "violations": ["DOM_MISSING_ELEMENT: O elemento '#deviceList .device-card' não foi renderizado após o clique."],
        },
    )

    report = ProductDeliveryGate.evaluate_delivery(
        project_root=str(proj_dir),
        project_id="proj_dom_broken",
        runtime_endpoint="http://127.0.0.1:3000",
        browser_test_requested=True,
        user_prompt="Validar cartões no DOM",
    )

    assert report.gate_status == DeliveryGateStatus.BLOCKED.value
    assert any("BROWSER_QA_VIOLATION" in b for b in report.blockers)
    assert report.validation_levels[AcceptanceLevel.FUNCTIONAL_BROWSER_VALIDATED.value] is False


# ==============================================================================
# CENÁRIO 12: Cache-busting correto
# ==============================================================================
def test_scenario_12_cache_busting_handling(tmp_path):
    """
    Cenário 12: O HTML faz referência a scripts com parâmetros de cache-busting (ex: client.js?v=hash).
    O AssetIntegrityValidator remove a query string para localizar o ficheiro em disco sem falso positivo.
    """
    proj_dir = tmp_path / "proj_cache_busting"
    proj_dir.mkdir()
    (proj_dir / "index.html").write_text(
        '<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width"></head><body><script src="client.js?v=20261015"></script></body></html>',
        encoding="utf-8",
    )
    (proj_dir / "client.js").write_text("console.log('cache busted script');", encoding="utf-8")

    res = AssetIntegrityValidator.validate_project_assets(str(proj_dir))
    assert res["valid"] is True
    assert len(res["missing_assets"]) == 0


# ==============================================================================
# CENÁRIO 13: Dados GeoIP ausentes ou incompletos (Sem GPS falso nem ISP alucinado)
# ==============================================================================
def test_scenario_13_geoip_missing_or_private_data_handled_factually():
    """
    Cenário 13: Endereço privado (192.168.1.1) ou sem dados de geolocalização.
    O validador proíbe declarar GPS exato e assegura conformidade factual.
    """
    # 1. Payload factual seguro para IP privado
    safe_private_payload = {
        "targetIp": "192.168.1.1",
        "ipType": "Privado",
        "ipOrigin": {
            "summary": "Rede Local / Não Roteável",
            "country": None,
            "city": None,
            "hostname": "router.local",
        },
    }
    frontend_code = "if (data.ipOrigin) { renderOrigin(data.ipOrigin.summary); }"

    res_safe = ContractValidator.validate_geoip_contract(safe_private_payload, frontend_code)
    assert res_safe["valid"] is True

    # 2. Payload que alucina GPS exato -> DEVE FALHAR
    fraudulent_payload = {
        "targetIp": "8.8.8.8",
        "ipType": "Público",
        "ipOrigin": {
            "exact_physical_address": "Rua das Flores 123, Lisboa (GPS: 38.72, -9.13)",
        },
    }
    res_fraud = ContractValidator.validate_geoip_contract(fraudulent_payload, frontend_code)
    assert res_fraud["valid"] is False
    assert any("FACTUAL_INTEGRITY_VIOLATION" in v for v in res_fraud["violations"])


# ==============================================================================
# CENÁRIO 14: Resolução DNS sem hostname
# ==============================================================================
def test_scenario_14_dns_reverse_resolution_without_hostname():
    """
    Cenário 14: O IP não tem registo PTR reverso de DNS (hostname é null ou ausente).
    O sistema deve aceitar e tratar factualmente sem falhar por exceção.
    """
    payload_no_host = {
        "targetIp": "198.51.100.5",
        "ipType": "Público",
        "ipOrigin": {
            "country": "US",
            "city": "Dallas",
            "hostname": None,  # Sem PTR
            "summary": "US (Dallas)",
        },
    }
    frontend_code = "if (data.ipOrigin) { const host = data.ipOrigin.hostname || 'Sem registo DNS'; }"

    res = ContractValidator.validate_geoip_contract(payload_no_host, frontend_code)
    assert res["valid"] is True


# ==============================================================================
# CENÁRIO 15: Retoma de missão após falha do preview
# ==============================================================================
def test_scenario_15_mission_resumption_after_preview_failure(tmp_path, monkeypatch):
    """
    Cenário 15: O preview falha inicialmente, mas a rotina de recuperação restaura
    a instância e reavalia com sucesso.
    """
    proj_dir = tmp_path / "proj_resumption"
    proj_dir.mkdir()
    (proj_dir / "index.html").write_text(
        '<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width"><link rel="stylesheet" href="style.css"></head><body><h1>Recovered</h1><script src="app.js"></script></body></html>',
        encoding="utf-8",
    )
    (proj_dir / "style.css").write_text("body { font-family: sans-serif; background: #fff; }", encoding="utf-8")
    (proj_dir / "app.js").write_text("console.log('app running');", encoding="utf-8")

    attempt = 0

    def mock_inspect_runtime(*args, **kwargs):
        nonlocal attempt
        attempt += 1
        if attempt == 1:
            return RuntimeIdentity(
                project_id="proj_resumption",
                preview_id="",
                process_id=0,
                command_line="",
                working_directory="",
                port=3000,
                endpoint="http://127.0.0.1:3000",
                start_time=0.0,
                is_running=False,
                is_owned=False,
                is_stale=False,
                healthcheck_ok=False,
                status="RUNTIME_UNAVAILABLE",
            )
        else:
            return RuntimeIdentity(
                project_id="proj_resumption",
                preview_id="p-15",
                process_id=7777,
                command_line="node app.js",
                working_directory=str(proj_dir),
                port=3000,
                endpoint="http://127.0.0.1:3000",
                start_time=time.time() + 10.0,
                is_running=True,
                is_owned=True,
                is_stale=False,
                healthcheck_ok=True,
                status="RUNNING_FRESH",
            )

    monkeypatch.setattr(RuntimeTracker, "inspect_runtime", mock_inspect_runtime)
    monkeypatch.setattr(AssetIntegrityValidator, "validate_served_assets", lambda *a, **k: {"valid": True, "violations": []})

    # Primeira tentativa: falha
    report1 = ProductDeliveryGate.evaluate_delivery(str(proj_dir), "proj_resumption", runtime_endpoint="http://127.0.0.1:3000")
    assert report1.gate_status == DeliveryGateStatus.BLOCKED.value

    # Retoma: sucesso
    report2 = ProductDeliveryGate.evaluate_delivery(str(proj_dir), "proj_resumption", runtime_endpoint="http://127.0.0.1:3000")
    assert report2.gate_status == DeliveryGateStatus.PRODUCT_ACCEPTED.value
    assert report2.validation_levels[AcceptanceLevel.RUNTIME_VERSION_VALIDATED.value] is True


# ==============================================================================
# CENÁRIO 16: Entrega com todas as verificações aplicáveis aprovadas
# ==============================================================================
def test_scenario_16_clean_delivery_with_all_verifications_passing(tmp_path, monkeypatch):
    """
    Cenário 16: Todos os 7 níveis independentes de validação são cumpridos com evidências reais.
    O sistema declara PRODUCT_ACCEPTED e is_autonomous_product_delivery_ready retorna True.
    """
    proj_dir = tmp_path / "proj_full_acceptance"
    proj_dir.mkdir()
    (proj_dir / "index.html").write_text(
        '<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width"><link rel="stylesheet" href="style.css"></head><body><button id="scanIpButton">Scan</button><div id="deviceList"></div><script src="client.js"></script></body></html>',
        encoding="utf-8",
    )
    (proj_dir / "style.css").write_text("body { font-family: sans-serif; background: #fff; }", encoding="utf-8")
    (proj_dir / "client.js").write_text(
        "document.getElementById('scanIpButton').onclick = () => { document.getElementById('deviceList').innerHTML = '<div class=\"device-card\">192.168.1.1</div>'; };",
        encoding="utf-8",
    )

    fresh_ident = RuntimeIdentity(
        project_id="proj_full_acceptance",
        preview_id="p-16",
        process_id=9999,
        command_line="node server.js",
        working_directory=str(proj_dir),
        port=3000,
        endpoint="http://127.0.0.1:3000",
        start_time=time.time() + 10.0,
        is_running=True,
        is_owned=True,
        is_stale=False,
        healthcheck_ok=True,
        status="RUNNING_FRESH",
    )

    monkeypatch.setattr(RuntimeTracker, "inspect_runtime", lambda *args, **kwargs: fresh_ident)
    monkeypatch.setattr(AssetIntegrityValidator, "validate_served_assets", lambda *a, **k: {"valid": True, "violations": []})
    monkeypatch.setattr(
        RealBrowserQAValidator,
        "execute_browser_qa",
        lambda *a, **k: {
            "valid": True,
            "screenshots": ["evidence/product_delivery/proj_full_acceptance_after.png"],
            "violations": [],
            "dom_verified": True,
        },
    )

    report = ProductDeliveryGate.evaluate_delivery(
        project_root=str(proj_dir),
        project_id="proj_full_acceptance",
        runtime_endpoint="http://127.0.0.1:3000",
        browser_test_requested=True,
        user_prompt="Entregar aplicação completa com validação no browser",
        technical_validations_passed=True,
    )

    assert report.gate_status == DeliveryGateStatus.PRODUCT_ACCEPTED.value
    assert report.result == RequirementStatus.PASS.value
    assert len(report.blockers) == 0

    # Todos os 7 níveis formais
    vl = report.validation_levels
    assert vl[AcceptanceLevel.CODE_VALIDATED.value] is True
    assert vl[AcceptanceLevel.BUILD_VALIDATED.value] is True
    assert vl[AcceptanceLevel.RUNTIME_VERSION_VALIDATED.value] is True
    assert vl[AcceptanceLevel.API_CONTRACT_VALIDATED.value] is True
    assert vl[AcceptanceLevel.FUNCTIONAL_BROWSER_VALIDATED.value] is True
    assert vl[AcceptanceLevel.VISUAL_BROWSER_VALIDATED.value] is True
    assert vl[AcceptanceLevel.PRODUCT_ACCEPTED.value] is True

    assert is_autonomous_product_delivery_ready(report) is True
    assert "Produto aceite para entrega" in report.user_summary
