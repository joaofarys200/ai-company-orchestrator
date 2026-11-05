---
type: runbook
domain: security
difficulty: intermediate
status: verified
source_type: PRIMARY_SOURCE
confidence: high
freshness: stable
tags:
  - runbook
  - security
  - supply-chain
  - dependencies
  - pip
  - npm
---

# 🛠️ Runbook - How to Audit and Quarantine Untrusted Third-Party Dependencies

## 1. Quando Executar Este Runbook
- Sempre que um agente autónomo, PR externo ou tutorial propuser adicionar um pacote novo ao `requirements.txt`, `pyproject.toml` ou `package.json`.
- Quando um alerta de CVE/OSV ou comportamento anómalo de rede/disco surgir após atualização de dependências.

---

## 2. Triagem Pré-Instalação (Antes de Executar `pip` / `npm`)

1. **Validar Existência Real e Anti-Slopsquatting**:
   - Confirmar que o nome do pacote existe oficialmente, verificar idade do registo, repositório fonte vinculado e volume real de manutenção (rejeitar pacotes recém-criados sem histórico verificável).
2. **Exigir Escopo Estrito de Projeto e Autorização**:
   - Nunca instalar no Python global do sistema ou com `sudo`/Administrador; direcionar exclusivamente para o `venv` ou `node_modules` isolado do projeto após aprovação no `PermissionGatewayService`.
3. **Inspecionar Scripts de Ciclo de Vida**:
   - Em Node.js, testar primeiro com `npm install --ignore-scripts --package-lock-only` e auditar o diff do `package-lock.json`.
   - Em Python, preferir wheels binárias puras (`--only-binary=:all:`) evitando execução arbitrária de `setup.py` em `sdist`.

---

## 3. Auditoria Pós-Lockfile e Quarentena de Incidente

```powershell
# Python: auditoria de vulnerabilidades conhecidas (PyPA / OSV) no venv isolado
& venv\Scripts\python.exe -m pip list --format=freeze
# Node.js: verificação determinística sem executar scripts postinstall
npm audit --audit-level=high
```

### Protocolo de Quarentena se um Pacote Suspeito Já Foi Instalado:
1. **Cortar Egress e Processos**: Terminar processos ativos do workspace afetado.
2. **Revogar Credenciais Expostas**: Assumir comprometimento de todas as variáveis em `.env` acessíveis ao utilizador local (rodar API keys e tokens OAuth/Git).
3. **Reconstruir Ambiente Limpo**: Eliminar integralmente a pasta `venv/` ou `node_modules/` (não confiar apenas em `pip uninstall`, pois hooks de instalação podem ter deixado ficheiros `.pth` persistentes em `site-packages`) e recriar a partir de um lockfile verificado.

---

## 4. Referências Cruzadas
- [[Software Supply Chain Security - SLSA, SBOM and Dependency Pinning]]
- [[Runbook - How to Detect and Mitigate Sandbox Escape Attempts]]
- [[How to Sanitize Secrets Before Logging or Ingestion]]
- [[JARVIS Phase 24-25 Durable Mission Lifecycle, Leases and Authorization]]

