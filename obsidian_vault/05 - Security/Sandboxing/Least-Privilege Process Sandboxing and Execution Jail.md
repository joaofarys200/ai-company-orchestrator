---
type: concept
domain: security
difficulty: advanced
tags:
  - security
  - sandboxing
  - least-privilege
  - isolation
  - process-security
status: verified
---

# 🧱 Least-Privilege Process Sandboxing and Execution Jail

## 1. Princípio do Menor Privilégio (Principle of Least Privilege)
O **Princípio do Menor Privilégio (PoLP)** estabelece que todo o processo ou agente deve aceder estritamente aos recursos mínimos indispensáveis para a sua função legítima.

Quando agentes de IA executam código arbitrário ou ferramentas de terminal, conceder acesso irrestrito ao sistema de ficheiros ou à rede permite que prompts maliciosos formatem discos, roubem chaves SSH (`~/.ssh/id_rsa`) ou façam escaneamento da rede interna.

```
+--------------------------------------------------------------------+
|                         SISTEMA OPERACIONAL HOST                   |
|                                                                    |
|  +--------------------------------------------------------------+  |
|  |                  SANDBOX JAIL / CONTAINER                    |  |
|  |                                                              |  |
|  |  - Diretório Restrito: /workspace/sandbox_dir                |  |
|  |  - Sem Acesso a: C:\Windows, /etc, ~/.ssh, C:\Users\*\App... |  |
|  |  - Limite de CPU: Máx 2 Cores                                |  |
|  |  - Limite de RAM: Máx 2048 MB                                |  |
|  |  - Timeout de Processo: Máx 60s                              |  |
|  |  - Rede: Bloqueio de Loopback (127.0.0.1) & Metadata Cloud    |  |
|  |                                                              |  |
|  |  +--------------------+    +--------------------+            |  |
|  |  | Python Subprocess  |    | Node/Playwright    |            |  |
|  |  +--------------------+    +--------------------+            |  |
|  +--------------------------------------------------------------+  |
+--------------------------------------------------------------------+
```

---

## 2. Camadas de Isolamento no JARVIS OS

1. **Jail de Sistema de Ficheiros (Path Jail / Chroot Virtual)**:
   - Toda a operação de leitura/escrita é validada com `os.path.commonpath([sandbox_root, target_path]) == sandbox_root`.
   - Lançamento imediato de `PermissionError` se o caminho contiver `..` ou tentar escapar do diretório autorizado.
2. **Restrições de Subprocesso (Subprocess Limits)**:
   - Execução com `shell=False` estrito; argumentos passados como listas de strings.
   - `timeout` obrigatório em todas as chamadas `subprocess.run()`.
3. **Isolamento de Variáveis de Ambiente**:
   - O subprocesso recebe um ambiente limpo (`env={}`), omitindo credenciais globais do host a menos que explicitamente injetadas.

---

## 3. Implementação de Execução em Sandbox Segura (Python)

```python
import subprocess
import os
from pathlib import Path
from typing import List, Tuple

SANDBOX_DIR = Path("c:/Users/joaor/Desktop/JarvisOS/workspace").resolve()

def execute_in_secure_sandbox(cmd_args: List[str], cwd: Path = SANDBOX_DIR, timeout_sec: int = 30) -> Tuple[int, str, str]:
    # 1. Validar integridade do caminho de execução
    resolved_cwd = cwd.resolve()
    if not str(resolved_cwd).startswith(str(SANDBOX_DIR)):
        raise PermissionError(f"Tentativa de execução fora da sandbox: {resolved_cwd}")

    # 2. Ambiente restrito sem variáveis sensíveis do sistema anfitrião
    safe_env = {
        "PATH": os.environ.get("PATH", ""),
        "TEMP": os.environ.get("TEMP", ""),
        "TMP": os.environ.get("TMP", ""),
        "PYTHONIOENCODING": "utf-8"
    }

    # 3. Executar subprocesso isolado
    process = subprocess.run(
        cmd_args,
        cwd=resolved_cwd,
        env=safe_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout_sec,
        shell=False # Previne Command Injection via shell meta-characters
    )

    return process.returncode, process.stdout, process.stderr
```

---

## 4. Related Concepts
- [[Threat Modeling for Autonomous Coding Agents]]
- [[SSRF Defense in Agentic Fetchers]]
- [[Prompt Injection Defense in Autonomous Agents]]
- [[Seguranca_Defensiva_DevSecOps_e_Sandboxing]]

---

## 5. Sources
- *NIST SP 800-53 - Security and Privacy Controls for Information Systems (AC-6: Least Privilege)*: https://csrc.nist.gov/publications/detail/sp/800-53/rev-5/final
- *OWASP Top 10 - Sandboxing and Defense in Depth*
