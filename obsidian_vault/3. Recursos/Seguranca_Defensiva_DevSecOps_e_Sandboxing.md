# 🛡️ Manual Completo de Segurança Defensiva, DevSecOps & Sandboxing

## 📌 1. Visão Geral
Este manual estabelece o **framework de segurança e proteção em profundidade** aplicado em todas as operações de execução de código, automação de ambiente de trabalho e serviços de API do **JARVIS OS**.

---

## 🔒 2. Princípios de Segurança em Profundidade (Defense in Depth)

### 2.1. Princípio do Menor Privilégio (Least Privilege)
- Agentes de IA e subprocessos locais executam estritamente com as permissões mínimas necessárias.
- Operações no sistema de ficheiros ficam restritas à diretoria do projeto e à sandbox autorizada (`sandbox_dir/`).

### 2.2. Sanitização de Input e Prevenção de Injection
- NUNCA executar strings não higienizadas diretamente em `shell=True` no `subprocess.run` ou PowerShell.
- **Normalização de Argumentos**: Argumentos fornecidos pelo LLM para ferramentas de SO devem ser validados contra dicionários rígidos de permissões.

---

## 🐳 3. Sandbox de Execução & Isolamento de Processos

### 3.1. Arquitetura de Sandbox Dual-Mode
O JARVIS OS emprega uma arquitetura de sandbox de dois níveis:
1. **Modo Contentorizado (Docker/Seccomp)**: Execução de previews web e scripts dentro de um contentor isolado sem acesso à rede host ou ao sistema de ficheiros raiz.
2. **Modo Fallback Local Seguro**: Em sistemas sem Docker ativo, a sandbox utiliza um servidor HTTP local estático limitado à pasta `sandbox_dir/` com sanitização de caminhos (`os.path.commonpath`).

### 3.2. Prevenção de Path Traversal
Todos os acessos a ficheiros recebem verificação rigorosa contra ataques de navegação relativa de diretórios (`../`):
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

## 🔑 4. Gestão de Segredos & Proteção de Dados Sensíveis

### 4.1. Proibição de Hardcoding de Credenciais
- Chaves de API (`GEMINI_API_KEY`, `OPENROUTER_API_KEY`), tokens WebSocket e passwords NUNCA devem ser gravados diretamente no código-fonte ou em notas públicas.
- Utilizar exclusivamente variáveis de ambiente carregadas a partir de um ficheiro `.env` não commitado.

### 4.2. Sanitização de Logs de Telemetria
O motor de telemetria (`ModelTelemetry`) higieniza automaticamente os registos para garantir que os prompts do utilizador e dados pessoais não são expostos em métricas públicas de APM.

---

## ⚡ 5. Proteção contra Negação de Serviço (Rate Limiting & Memory Bounds)

### 5.1. Rate Limiting por IP/Conexão
- O servidor de API e WebSockets aplica limites de taxa de pedidos por IP para prevenir exaustão de recursos ou ataques de força bruta.

### 5.2. Limites de Orçamento de Contexto e Memória
- O `ModelHarness` aplica limites estritos de `max_context_tokens` e `max_output_tokens` para impedir estouro de memória GPU/RAM durante a geração de respostas.
