"""
JARVIS OS — Teste End-to-End com Fixture Isolada (Secção 11 da Especificação).

Percorre o ciclo completo de entrega autónoma de forma isolada e determinística:
Pedido
-> Resolução da intenção
-> Missão
-> Alteração dos artefactos
-> Build
-> Arranque/atualização do preview
-> Validação da API
-> Browser QA
-> Verificação funcional
-> Product Delivery Gate
-> Resposta final.

Assegura:
- O sistema NUNCA apresenta sucesso antes da validação factual completa.
- Gravação de correlation_id, mission_id, hashes antes/depois, identificação do runtime,
  versão dos assets servidos, resultados dos endpoints e screenshots reais.
- Zero impacto no projeto Dina original e zero tráfego para a rede real.
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
from security.delivery_governance.real_browser_qa import RealBrowserQAValidator


class IsolatedDinaServer(http.server.SimpleHTTPRequestHandler):
    """Servidor HTTP determinístico para fixture isolada do projeto Dina."""

    def do_GET(self):
        if self.path.startswith("/favicon.ico"):
            self.send_response(204)
            self.end_headers()
            return
        elif self.path.startswith("/scan-local-ips"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            payload = {
                "message": "Dispositivos encontrados na rede local",
                "ips": ["192.168.1.1", "192.168.1.45"],
                "devices": [
                    {
                        "ip": "192.168.1.1",
                        "mac": "00:1A:2B:3C:4D:5E",
                        "vendor": "Asus Computer",
                        "hostname": "router.local",
                        "role": "Gateway / Router",
                    },
                    {
                        "ip": "192.168.1.45",
                        "mac": "AA:BB:CC:DD:EE:FF",
                        "vendor": "Apple Inc.",
                        "hostname": "macbook-pro.local",
                        "role": "Estação de Trabalho",
                    },
                ],
            }
            self.wfile.write(json.dumps(payload).encode("utf-8"))
            return
        elif self.path.startswith("/api/health"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "HEALTHY", "build": "build-e2e-20261015"}).encode("utf-8"))
            return
        super().do_GET()

    def log_message(self, format, *args):
        pass  # Silencia logs de requisições no pytest


def get_free_port() -> int:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def test_e2e_isolated_fixture_gate_complete_flow(tmp_path):
    """
    Executa o teste end-to-end com fixture descartável, garantindo que o portão
    só declara PRODUCT_ACCEPTED após o percurso completo com validação de browser.
    """
    correlation_id = "corr-e2e-847291"
    mission_id = "miss-dina-runtime-integrity"
    port = get_free_port()

    # 1. Configurar diretório descartável e artefactos
    fixture_dir = tmp_path / "dina_e2e_fixture"
    fixture_dir.mkdir()

    index_html = fixture_dir / "index.html"
    client_js = fixture_dir / "client.js"
    style_css = fixture_dir / "styles.css"
    app_js = fixture_dir / "app.js"
    pkg_json = fixture_dir / "package.json"

    # Conteúdo inicial sincronizado
    style_css.write_text(
        """
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; padding: 20px; }
        .device-card { background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 12px; margin-top: 10px; }
        .device-ip { font-weight: bold; color: #38bdf8; }
        .device-meta { font-size: 0.85rem; color: #94a3b8; }
        button { background: #3b82f6; color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; }
        """,
        encoding="utf-8",
    )

    client_js.write_text(
        """
        document.addEventListener('DOMContentLoaded', () => {
            const btn = document.getElementById('scanIpButton');
            const list = document.getElementById('ipScanResults');
            btn.onclick = async () => {
                btn.disabled = true;
                btn.textContent = 'A pesquisar...';
                try {
                    const res = await fetch('/scan-local-ips');
                    const data = await res.json();
                    list.innerHTML = '';
                    if (data.devices && data.devices.length > 0) {
                        data.devices.forEach(dev => {
                            const li = document.createElement('li');
                            li.className = 'device-card';
                            li.innerHTML = '<span class="device-ip">' + dev.ip + '</span> ' +
                                             '<span class="device-role">(' + dev.role + ')</span>' +
                                             '<div class="device-meta">Fabricante: ' + dev.vendor + ' • MAC: ' + dev.mac + '</div>';
                            list.appendChild(li);
                        });
                    }
                    if (data.ipOrigin) {
                        const originDiv = document.createElement('div');
                        originDiv.className = 'ip-origin-info';
                        originDiv.textContent = 'Origem: ' + (data.ipOrigin.summary || data.ipOrigin.country || 'Desconhecida');
                        list.appendChild(originDiv);
                    }
                } finally {
                    btn.disabled = false;
                    btn.textContent = 'Procurar Dispositivos';
                }
            };
        });
        """,
        encoding="utf-8",
    )

    index_html.write_text(
        """<!DOCTYPE html>
        <html lang="pt">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Dina Network Scanner</title>
            <link rel="stylesheet" href="styles.css">
        </head>
        <body>
            <h1>Dina Network Scanner</h1>
            <p>Auditoria de integridade de rede local com deteção factual de dispositivos e GeoIP.</p>
            <button id="scanIpButton">Procurar Dispositivos</button>
            <ul id="ipScanResults"></ul>
            <script src="client.js"></script>
        </body>
        </html>
        """,
        encoding="utf-8",
    )

    app_js.write_text("// Dina backend express mock\nconst port = 3000;\n", encoding="utf-8")
    pkg_json.write_text('{"name": "dina-e2e", "version": "1.0.0", "main": "app.js"}', encoding="utf-8")

    # Hashes dos artefactos antes
    hash_html_before = hashlib.sha256(index_html.read_bytes()).hexdigest()
    hash_js_before = hashlib.sha256(client_js.read_bytes()).hexdigest()

    # 2. Iniciar servidor HTTP descartável no diretório
    handler = lambda *args, **kwargs: IsolatedDinaServer(*args, directory=str(fixture_dir), **kwargs)
    httpd = socketserver.TCPServer(("127.0.0.1", port), handler)
    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()

    time.sleep(0.5)
    runtime_endpoint = f"http://127.0.0.1:{port}"

    try:
        # 3. Fase 1: Avaliação preliminar antes da validação do browser
        # O portão NÃO deve conceder PRODUCT_ACCEPTED se o browser_test não foi executado com sucesso
        report_preflight = ProductDeliveryGate.evaluate_delivery(
            project_root=str(fixture_dir),
            project_id="dina_e2e_fixture",
            mission_id=mission_id,
            change_id=correlation_id,
            runtime_endpoint=runtime_endpoint,
            browser_test_requested=False,  # Ainda sem browser QA
            user_prompt="Adicionar cartões enriquecidos de rede local no Dina",
        )
        assert report_preflight.gate_status != DeliveryGateStatus.PRODUCT_ACCEPTED.value or is_autonomous_product_delivery_ready(report_preflight) is False

        # 4. Fase 2: Executar Real Browser QA via Playwright Edge
        browser_actions = [
            {"type": "wait_for_selector", "selector": "#scanIpButton", "timeout": 5000},
            {"type": "click", "selector": "#scanIpButton"},
            {"type": "wait_for_selector", "selector": ".device-card", "timeout": 8000},
            {"type": "assert_text_present", "selector": ".device-ip", "expected": "192.168.1.1"},
            {"type": "assert_text_present", "selector": ".device-role", "expected": "Gateway"},
        ]

        browser_qa_res = RealBrowserQAValidator.execute_browser_qa(
            preview_url=runtime_endpoint,
            actions=browser_actions,
            project_id="dina_e2e_fixture",
            mission_id=mission_id,
            timeout_ms=15000,
        )

        assert browser_qa_res["valid"] is True, f"Browser QA falhou: {browser_qa_res.get('error')} {browser_qa_res.get('violations')}"
        assert len(browser_qa_res.get("screenshots", [])) >= 1

        # 5. Fase 3: Avaliação Completa no Product Delivery Gate com evidência factual do Browser
        report_final = ProductDeliveryGate.evaluate_delivery(
            project_root=str(fixture_dir),
            project_id="dina_e2e_fixture",
            mission_id=mission_id,
            change_id=correlation_id,
            runtime_endpoint=runtime_endpoint,
            browser_test_requested=True,
            browser_actions=browser_actions,
            user_prompt="Adicionar cartões enriquecidos de rede local no Dina",
            technical_validations_passed=True,
        )

        # 6. Verificações formais de integridade
        assert report_final.blockers == [], f"Bloqueadores encontrados: {report_final.blockers}"
        assert report_final.gate_status == DeliveryGateStatus.PRODUCT_ACCEPTED.value

        # Rastreabilidade dos 7 níveis
        levels = report_final.validation_levels
        assert levels[AcceptanceLevel.CODE_VALIDATED.value] is True
        assert levels[AcceptanceLevel.BUILD_VALIDATED.value] is True
        assert levels[AcceptanceLevel.RUNTIME_VERSION_VALIDATED.value] is True
        assert levels[AcceptanceLevel.API_CONTRACT_VALIDATED.value] is True
        assert levels[AcceptanceLevel.FUNCTIONAL_BROWSER_VALIDATED.value] is True
        assert levels[AcceptanceLevel.VISUAL_BROWSER_VALIDATED.value] is True
        assert levels[AcceptanceLevel.PRODUCT_ACCEPTED.value] is True

        assert is_autonomous_product_delivery_ready(report_final) is True
        assert "Produto aceite para entrega" in report_final.user_summary

        # Gravação e confirmação de evidências
        evidence_record = {
            "correlation_id": correlation_id,
            "mission_id": mission_id,
            "project_id": "dina_e2e_fixture",
            "runtime_endpoint": runtime_endpoint,
            "hash_html_before": hash_html_before,
            "hash_js_before": hash_js_before,
            "hash_js_after": hashlib.sha256(client_js.read_bytes()).hexdigest(),
            "browser_screenshots": browser_qa_res["screenshots"],
            "validation_levels": levels,
            "final_gate_status": report_final.gate_status,
        }

        evidence_file = fixture_dir / "e2e_delivery_evidence.json"
        evidence_file.write_text(json.dumps(evidence_record, indent=2), encoding="utf-8")
        assert evidence_file.exists()

    finally:
        httpd.shutdown()
        httpd.server_close()
