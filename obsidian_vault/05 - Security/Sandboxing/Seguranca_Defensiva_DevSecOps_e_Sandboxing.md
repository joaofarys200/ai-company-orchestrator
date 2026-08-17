---
type: concept
domain: security
difficulty: advanced
tags:
  - security
  - sandboxing
  - devsecops
status: verified
---

# ðŸ›¡ï¸ Manual Completo de SeguranÃ§a Defensiva, DevSecOps & Sandboxing

## ðŸ“Œ 1. VisÃ£o Geral
Este manual estabelece o **framework de seguranÃ§a e proteÃ§Ã£o em profundidade** aplicado em todas as operaÃ§Ãµes de execuÃ§Ã£o de cÃ³digo, automaÃ§Ã£o de ambiente de trabalho e serviÃ§os de API do **JARVIS OS**.

---

## ðŸ”’ 2. PrincÃ­pios de SeguranÃ§a em Profundidade (Defense in Depth)

### 2.1. PrincÃ­pio do Menor PrivilÃ©gio (Least Privilege)
- Agentes de IA e subprocessos locais executam estritamente com as permissÃµes mÃ­nimas necessÃ¡rias.
- OperaÃ§Ãµes no sistema de ficheiros ficam restritas Ã  diretoria do projeto e Ã  sandbox autorizada (`sandbox_dir/`).

### 2.2. SanitizaÃ§Ã£o de Input e PrevenÃ§Ã£o de Injection
- NUNCA executar strings nÃ£o higienizadas diretamente em `shell=True` no `subprocess.run` ou PowerShell.
- **NormalizaÃ§Ã£o de Argumentos**: Argumentos fornecidos pelo LLM para ferramentas de SO devem ser validados contra dicionÃ¡rios rÃ­gidos de permissÃµes.

---

## ðŸ³ 3. Sandbox de ExecuÃ§Ã£o & Isolamento de Processos

### 3.1. Arquitetura de Sandbox Dual-Mode
O JARVIS OS emprega uma arquitetura de sandbox de dois nÃ­veis:
1. **Modo Contentorizado (Docker/Seccomp)**: ExecuÃ§Ã£o de previews web e scripts dentro de um contentor isolado sem acesso Ã  rede host ou ao sistema de ficheiros raiz.
2. **Modo Fallback Local Seguro**: Em sistemas sem Docker ativo, a sandbox utiliza um servidor HTTP local estÃ¡tico limitado Ã  pasta `sandbox_dir/` com sanitizaÃ§Ã£o de caminhos (`os.path.commonpath`).

### 3.2. PrevenÃ§Ã£o de Path Traversal
Todos os acessos a ficheiros recebem verificaÃ§Ã£o rigorosa contra ataques de navegaÃ§Ã£o relativa de diretÃ³rios (`../`):
```python
import os

def is_safe_path(base_dir: str, target_path: str) -> bool:
    abs_base = os.path.realpath(os.path.abspath(base_dir))
    abs_target = os.path.realpath(os.path.abspath(target_path))
    try:
        return os.path.commonpath([abs_base, abs_target]) == abs_base
    except ValueError:
        return False
```

---

## ðŸ”‘ 4. GestÃ£o de Segredos & ProteÃ§Ã£o de Dados SensÃ­veis

### 4.1. ProibiÃ§Ã£o de Hardcoding de Credenciais
- Chaves de API (`GEMINI_API_KEY`, `OPENROUTER_API_KEY`), tokens WebSocket e passwords NUNCA devem ser gravados diretamente no cÃ³digo-fonte ou em notas pÃºblicas.
- Utilizar exclusivamente variÃ¡veis de ambiente carregadas a partir de um ficheiro `.env` nÃ£o commitado.

### 4.2. SanitizaÃ§Ã£o de Logs de Telemetria
O motor de telemetria (`ModelTelemetry`) higieniza automaticamente os registos para garantir que os prompts do utilizador e dados pessoais nÃ£o sÃ£o expostos em mÃ©tricas pÃºblicas de APM.

---

## âš¡ 5. ProteÃ§Ã£o contra NegaÃ§Ã£o de ServiÃ§o (Rate Limiting & Memory Bounds)

### 5.1. Rate Limiting por IP/ConexÃ£o
- O servidor de API e WebSockets aplica limites de taxa de pedidos por IP para prevenir exaustÃ£o de recursos ou ataques de forÃ§a bruta.

### 5.2. Limites de OrÃ§amento de Contexto e MemÃ³ria
- O `ModelHarness` aplica limites estritos de `max_context_tokens` e `max_output_tokens` para impedir estouro de memÃ³ria GPU/RAM durante a geraÃ§Ã£o de respostas.

