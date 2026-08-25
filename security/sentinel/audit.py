"""
JARVIS OS — Security Sentinel Read-Only Audit Runner
Execução orquestrada de auditorias de segurança, métricas e geração de relatórios formais.
"""

from __future__ import annotations

import datetime
import json
import os
import time
from typing import Any, Dict, Optional

from security.sentinel.baseline import BaselineEngine
from security.sentinel.contracts import SystemBaseline, BaselineDiff


class SecurityAuditRunner:
    """Orquestrador de auditorias de cibersegurança em modo estritamente READ-ONLY."""

    def __init__(
        self,
        baseline_engine: Optional[BaselineEngine] = None,
        reports_dir: str = r"workspace\sentinel\reports",
    ) -> None:
        self.baseline_engine = baseline_engine or BaselineEngine()
        self.reports_dir = reports_dir
        os.makedirs(self.reports_dir, exist_ok=True)

    def run_audit(self, save: bool = True) -> Dict[str, Any]:
        """Executa uma auditoria completa do sistema e compila as estatísticas de telemetria."""
        start_time = time.time()
        baseline = self.baseline_engine.capture_baseline()
        duration = time.time() - start_time

        summary = {
            "baseline_id": baseline.baseline_id,
            "timestamp": datetime.datetime.fromtimestamp(baseline.timestamp).isoformat(),
            "duration_seconds": round(duration, 3),
            "integrity_hash": baseline.integrity_hash,
            "host": baseline.host_info.get("hostname"),
            "os": baseline.host_info.get("os"),
            "counts": {
                "processes": len(baseline.processes),
                "temp_path_processes": sum(1 for p in baseline.processes if p.get("is_temp_dir")),
                "network_connections": len(baseline.network),
                "listening_ports": sum(1 for n in baseline.network if n.get("status") == "LISTEN"),
                "persistence_entries": len(baseline.persistence),
                "browser_extensions": len(baseline.browser_extensions),
                "hosts_custom_entries": len(baseline.hosts_info.get("custom_entries", [])),
            },
            "windows_security": baseline.windows_security,
            "collector_metrics": baseline.collector_metrics,
        }

        report_path = ""
        baseline_path = ""
        if save:
            baseline_path = self.baseline_engine.save_baseline(baseline)
            md_content = self.generate_markdown_report(baseline, summary)
            report_path = os.path.join(self.reports_dir, f"{baseline.baseline_id}_REPORT.md")
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(md_content)

        return {
            "baseline": baseline,
            "summary": summary,
            "baseline_path": baseline_path,
            "report_path": report_path,
        }

    def generate_markdown_report(self, baseline: SystemBaseline, summary: Dict[str, Any]) -> str:
        """Gera um relatório formal e legível em Markdown sobre a auditoria realizada."""
        counts = summary["counts"]
        sec = baseline.windows_security
        now_str = summary["timestamp"]

        md = f"""# 🛡️ JARVIS OS — Security Sentinel Audit Report (Fase S1)

**Data da Auditoria**: `{now_str}`  
**Baseline ID**: `{baseline.baseline_id}`  
**Integridade Criptográfica (SHA-256)**: `{baseline.integrity_hash}`  
**Host**: `{baseline.host_info.get('hostname')}` (`{baseline.host_info.get('os')}`)  

---

## 📊 1. Resumo Executivo da Telemetria

| Vetor de Telemetria | Total Observado | Observações de Destaque |
|---|---|---|
| **Processos Ativos** | `{counts['processes']}` | `{counts['temp_path_processes']}` em pastas temporárias |
| **Sockets de Rede** | `{counts['network_connections']}` | `{counts['listening_ports']}` portas em escuta (*LISTEN*) |
| **Pontos de Persistência** | `{counts['persistence_entries']}` | Registo Run, Startup, Tasks e Serviços |
| **Extensões de Navegadores** | `{counts['browser_extensions']}` | Chrome e Edge |
| **Ficheiro Hosts** | `{counts['hosts_custom_entries']}` mapeamentos | Hash: `{baseline.hosts_info.get('sha256', '')[:16]}...` |

---

## 🛡️ 2. Estado do Subsistema de Segurança do Windows

- **Windows Defender Proteção em Tempo Real**: `{'🟢 ATIVO' if sec.get('defender_realtime_enabled') else '⚠️ DESATIVADO'}`
- **Windows Defender Antivírus**: `{'🟢 ATIVO' if sec.get('defender_antivirus_enabled') else '⚠️ DESATIVADO'}`
- **Firewall Perfil Domínio**: `{'🟢 ATIVO' if sec.get('firewall_domain_enabled') else '⚠️ DESATIVADO'}`
- **Firewall Perfil Privado**: `{'🟢 ATIVO' if sec.get('firewall_private_enabled') else '⚠️ DESATIVADO'}`
- **Firewall Perfil Público**: `{'🟢 ATIVO' if sec.get('firewall_public_enabled') else '⚠️ DESATIVADO'}`

---

## 🔍 3. Auditoria de Pontos de Persistência (Amostra de Chaves de Arranque)

"""
        run_items = [p for p in baseline.persistence if p.get("kind") == "REGISTRY_RUN"]
        if run_items:
            md += "| Nome | Caminho do Executável | Localização |\n|---|---|---|\n"
            for item in run_items[:15]:
                md += f"| `{item.get('name')}` | `{item.get('target_path')}` | `{item.get('location')}` |\n"
        else:
            md += "*Nenhuma chave de arranque suspeita encontrada no Registo.*\n"

        md += """
---

## 🌐 4. Portas de Rede em Escuta (Listening Ports)

| Protocolo | Porta Local | Endereço | Processo Associado | PID |
|---|---|---|---|---|
"""
        listen_ports = [n for n in baseline.network if n.get("status") == "LISTEN"]
        for port in listen_ports[:20]:
            md += f"| `{port.get('protocol')}` | `{port.get('local_port')}` | `{port.get('local_address')}` | `{port.get('process_name')}` | `{port.get('pid')}` |\n"

        md += """
---

## 🧩 5. Extensões de Navegador Instaladas

| Navegador | Nome da Extensão | ID | Versão | Total Permissões |
|---|---|---|---|---|
"""
        for ext in baseline.browser_extensions[:20]:
            md += f"| `{ext.get('browser')}` | `{ext.get('name')}` | `{ext.get('extension_id')}` | `{ext.get('version')}` | `{len(ext.get('permissions', []))}` |\n"

        md += f"""
---

## ⏱️ 6. Métricas de Execução dos Coletores

| Coletor | Duração (s) | Evidências Coletadas | Estado |
|---|---|---|---|
"""
        for cname, cmetric in baseline.collector_metrics.items():
            md += f"| `{cname}` | `{cmetric.get('duration_seconds')}s` | `{cmetric.get('count')}` | `{cmetric.get('status')}` |\n"

        md += """
---

> [!NOTE]
> Este relatório foi gerado em modo estritamente **READ-ONLY**. Nenhuma alteração foi realizada no sistema operativo.
"""
        return md
