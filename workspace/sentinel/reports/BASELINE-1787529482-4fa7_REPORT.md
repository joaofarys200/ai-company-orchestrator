# 🛡️ JARVIS OS — Security Sentinel Audit Report (Fase S1)

**Data da Auditoria**: `2026-08-24T00:58:02.047977`  
**Baseline ID**: `BASELINE-1787529482-4fa7`  
**Integridade Criptográfica (SHA-256)**: `f07f76e935164fdbcd827334bf264272c526c42f494d13060927279613cfd4a8`  
**Host**: `BIGBALLSG` (`Windows-11-10.0.26200-SP0`)  

---

## 📊 1. Resumo Executivo da Telemetria

| Vetor de Telemetria | Total Observado | Observações de Destaque |
|---|---|---|
| **Processos Ativos** | `275` | `0` em pastas temporárias |
| **Sockets de Rede** | `264` | `37` portas em escuta (*LISTEN*) |
| **Pontos de Persistência** | `552` | Registo Run, Startup, Tasks e Serviços |
| **Extensões de Navegadores** | `26` | Chrome e Edge |
| **Ficheiro Hosts** | `0` mapeamentos | Hash: `2d6bdfb341be3a62...` |

---

## 🛡️ 2. Estado do Subsistema de Segurança do Windows

- **Windows Defender Proteção em Tempo Real**: `🟢 ATIVO`
- **Windows Defender Antivírus**: `🟢 ATIVO`
- **Firewall Perfil Domínio**: `🟢 ATIVO`
- **Firewall Perfil Privado**: `🟢 ATIVO`
- **Firewall Perfil Público**: `🟢 ATIVO`

---

## 🔍 3. Auditoria de Pontos de Persistência (Amostra de Chaves de Arranque)

| Nome | Caminho do Executável | Localização |
|---|---|---|
| `OneDrive` | `"C:\Program Files\Microsoft OneDrive\OneDrive.exe" /background` | `HKCU_RUN\OneDrive` |
| `Discord` | `"C:\Users\joaor\AppData\Local\Discord\Update.exe" --processStart Discord.exe --process-start-args "--start-inactive"` | `HKCU_RUN\Discord` |
| `Steam` | `"C:\Program Files (x86)\Steam\steam.exe" -silent` | `HKCU_RUN\Steam` |
| `MicrosoftCopilotAutoLaunch_A51DA9B135BD7FD570A2D2932EB29DCA` | `"C:\Program Files (x86)\Microsoft\Copilot\Application\mscopilot.exe" --no-startup-window --win-session-start` | `HKCU_RUN\MicrosoftCopilotAutoLaunch_A51DA9B135BD7FD570A2D2932EB29DCA` |
| `MicrosoftEdgeAutoLaunch_6E20E1E1F951B41D4FBF37A7896BBAA6` | `"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --no-startup-window --win-session-start` | `HKCU_RUN\MicrosoftEdgeAutoLaunch_6E20E1E1F951B41D4FBF37A7896BBAA6` |
| `SecurityHealth` | `%windir%\system32\SecurityHealthSystray.exe` | `HKLM_RUN\SecurityHealth` |
| `RtkAudUService` | `"C:\WINDOWS\System32\DriverStore\FileRepository\realtekservice.inf_amd64_61225a54a5775612\RtkAudUService64.exe" -background` | `HKLM_RUN\RtkAudUService` |
| `msedge_cleanup_{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}` | `"C:\Program Files (x86)\Microsoft\EdgeWebView\Application\151.0.4129.101\Installer\setup.exe" --msedgewebview --delete-old-versions --system-level --verbose-logging --on-logon` | `HKLM_RUNONCE\msedge_cleanup_{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}` |
| `msedge_cleanup_{56EB18F8-B008-4CBD-B6D2-8C97FE7E9062}` | `"C:\Program Files (x86)\Microsoft\Edge\Application\151.0.4129.101\Installer\setup.exe" --msedge --channel=stable --delete-old-versions --system-level --verbose-logging --on-logon` | `HKLM_RUNONCE\msedge_cleanup_{56EB18F8-B008-4CBD-B6D2-8C97FE7E9062}` |

---

## 🌐 4. Portas de Rede em Escuta (Listening Ports)

| Protocolo | Porta Local | Endereço | Processo Associado | PID |
|---|---|---|---|---|
| `TCP` | `64332` | `127.0.0.1` | `language_server_windows_x64.exe` | `832` |
| `TCP` | `49671` | `::1` | `jhi_service.exe` | `5084` |
| `TCP` | `54384` | `127.0.0.1` | `language_server_windows_x64.exe` | `19280` |
| `TCP` | `54383` | `127.0.0.1` | `language_server_windows_x64.exe` | `19280` |
| `TCP` | `8001` | `127.0.0.1` | `python.exe` | `15820` |
| `TCP` | `49675` | `0.0.0.0` | `services.exe` | `1436` |
| `TCP` | `49664` | `::` | `lsass.exe` | `1488` |
| `TCP` | `11470` | `0.0.0.0` | `stremio-runtime.exe` | `11792` |
| `TCP` | `49670` | `::` | `spoolsv.exe` | `4532` |
| `TCP` | `49665` | `0.0.0.0` | `wininit.exe` | `1316` |
| `TCP` | `49675` | `::` | `services.exe` | `1436` |
| `TCP` | `445` | `0.0.0.0` | `System` | `4` |
| `TCP` | `42050` | `::1` | `OneDrive.Sync.Service.exe` | `20484` |
| `TCP` | `49667` | `0.0.0.0` | `svchost.exe` | `3848` |
| `TCP` | `64333` | `127.0.0.1` | `language_server_windows_x64.exe` | `832` |
| `TCP` | `7680` | `0.0.0.0` | `svchost.exe` | `12964` |
| `TCP` | `12470` | `0.0.0.0` | `stremio-runtime.exe` | `11792` |
| `TCP` | `139` | `10.20.2.56` | `System` | `4` |
| `TCP` | `8080` | `0.0.0.0` | `python.exe` | `15820` |
| `TCP` | `11470` | `::` | `stremio-runtime.exe` | `11792` |

---

## 🧩 5. Extensões de Navegador Instaladas

| Navegador | Nome da Extensão | ID | Versão | Total Permissões |
|---|---|---|---|---|
| `EDGE` | `Google Docs Offline` | `ghbmnnjooekpmoecnnnilnnbdlolhkhi` | `1.109.1` | `4` |
| `EDGE` | `Edge relevant text changes` | `jmjflgjpcpepeafmmgdpfkogkghcpiha` | `1.2.1` | `0` |
| `EDGE` | `Protocol Preregistration` | `AutoLaunchProtocolsComponent` | `1.0.0.12` | `0` |
| `EDGE` | `MicrosoftCRLSet` | `CertificateRevocation` | `6498.2025.9.4` | `0` |
| `EDGE` | `DomainActions` | `Domain Actions` | `3.0.0.20` | `0` |
| `EDGE` | `EADPData component` | `EADPData Component` | `4.0.4.21` | `0` |
| `EDGE` | `Edge Entity Extraction pt` | `Edge Entity Extraction` | `2026.6.30.7` | `0` |
| `EDGE` | `Edge Sidebar` | `Edge Sidebar` | `2026.2.24.1` | `0` |
| `EDGE` | `Edge Signal Triggers` | `Edge Signal Triggers` | `2026.3.4.1` | `0` |
| `EDGE` | `Edge 3P` | `Edge3pSerp` | `2026.8.12.1` | `0` |
| `EDGE` | `Edge Arbitration Priority List` | `EdgeArbitration` | `2026.5.28.1` | `0` |
| `EDGE` | `Edge LLM Language Detection Model` | `EdgeLanguageDetectionModel` | `2026.1.30.1` | `0` |
| `EDGE` | `First Party Sets` | `FirstPartySetsPreloaded` | `2025.7.24.0` | `0` |
| `EDGE` | `hyphens-data` | `hyphen-data` | `120.0.6050.0` | `0` |
| `EDGE` | `Unknown Extension` | `OriginTrials` | `0.0.1.7` | `0` |
| `EDGE` | `PKIMetadata` | `PKIMetadata` | `46.0.0.0` | `0` |
| `EDGE` | `Scareware Blocker Allowlist` | `ProvenanceDataAllowList` | `2026.6.16.1` | `0` |
| `EDGE` | `Image Classification Input Vectors` | `ProvenanceDataTensors` | `2026.2.23.1` | `0` |
| `EDGE` | `safetyTips` | `SafetyTips` | `3057` | `0` |
| `EDGE` | `Speech Recognition` | `Speech Recognition` | `1.15.0.1` | `0` |

---

## ⏱️ 6. Métricas de Execução dos Coletores

| Coletor | Duração (s) | Evidências Coletadas | Estado |
|---|---|---|---|
| `process_collector` | `7.168s` | `275` | `OK` |
| `network_collector` | `0.009s` | `264` | `OK` |
| `persistence_collector` | `1.017s` | `552` | `OK` |
| `hosts_collector` | `0.0s` | `1` | `OK` |
| `browser_collector` | `0.01s` | `26` | `OK` |
| `windows_security_events_collector` | `1.7s` | `1` | `OK` |

---

> [!NOTE]
> Este relatório foi gerado em modo estritamente **READ-ONLY**. Nenhuma alteração foi realizada no sistema operativo.
