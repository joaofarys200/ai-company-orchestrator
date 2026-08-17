---
type: troubleshooting
domain: devops
difficulty: intermediate
tags:
  - devops
  - troubleshooting
  - cicd
  - build-failures
  - runbook
status: verified
---

# 🛠️ How to Triage and Fix Broken CI-CD Pipelines

## 1. Objetivo & Quando Executar
Este runbook deve ser executado quando um pipeline de CI/CD falha após o push de código ou durante testes noturnos de integração.

---

## 2. Roteiro de Diagnóstico em 4 Etapas

```
[ Step 1: Inspecionar o Código de Saída (Exit Code) ]
  - Exit 1: Erro de aplicação / asserção de teste
  - Exit 137: Processo morto pelo Kernel (OOM - Out of Memory)
  - Exit 124 / 143: Timeout de execução excedido
         |
         v
[ Step 2: Extrair o Bloco de Erro Específico ]
  - Isolar o output entre as tags `FAILURES` ou `ERROR:`
         |
         v
[ Step 3: Reprodução Local em Ambiente Controlado ]
  - Executar exatamente o comando do CI na raiz do projeto
         |
         v
[ Step 4: Aplicação da Solução e Revalidação ]
```

---

## 3. Matriz de Correção de Falhas Frequentes

| Causa Raiz | Sintoma no Log | Ação Corretiva Imediata |
|---|---|---|
| **Linter / Formatação** | `black/flake8 found errors` | Executar `black .` ou corrigir violações de regras |
| **Dependência em Falta** | `ModuleNotFoundError: no module X` | Adicionar dependência ao `requirements.txt` ou `package.json` |
| **Porta em Uso / Conflito** | `OSError: [Errno 98] Address already in use` | Configurar o teste para usar porta dinâmica (`port=0`) ou parar serviços zumbis |
| **OOM Killed (137)** | `Command died with signal 9` | Aumentar limite de RAM no runner ou reduzir concorrência de workers no pytest (`-n 2` em vez de `-n 8`) |

---

## 4. Comandos de Reprodução Rápida

```powershell
# Executar suíte de testes exatamente como no CI
pytest -v --tb=short

# Verificar se há ficheiros fora do padrão de formatação
flake8 . --count --select=E9,F63,F7,F82 --show-source
```

---

## 5. Related Concepts
- [[CI-CD Pipeline Failure Triage and Automated Healing]]
- [[Compiler Feedback and Test-Driven Self-Repair]]
- [[How to Safely Validate and Apply Code Patches]]

---

## 6. Sources
- *GitHub Actions Documentation - Troubleshooting workflow runs*: https://docs.github.com/en/actions/monitoring-and-troubleshooting-workflows/troubleshooting-workflow-runs
- *GitLab CI/CD Troubleshooting Guide*: https://docs.gitlab.com/ee/ci/troubleshooting.html
