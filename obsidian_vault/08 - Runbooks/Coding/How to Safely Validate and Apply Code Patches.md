---
type: troubleshooting
domain: software-engineering
difficulty: intermediate
tags:
  - software-engineering
  - troubleshooting
  - patch-engine
  - code-validation
  - runbook
status: verified
---

# 🛠️ How to Safely Validate and Apply Code Patches

## 1. Objetivo & Quando Executar
Este procedimento operacional deve ser executado pelo agente **Devon** sempre que um patch de código é gerado, antes de efetivar as alterações no branch principal.

---

## 2. Checklist Automatizado Passo a Passo

```
[ Patch Gerado pelo Modelo ]
             |
             v
[ 1. Verificação de Caminho ] ---> Fora do workspace ou contém '..'? -> REJEITAR
             | (OK)
             v
[ 2. Simulação em Buffer ] ------> Bloco de substituição é ambíguo? -> PEDIR ÂNCORAS
             | (OK)
             v
[ 3. Validação de Sintaxe ] -----> `py_compile` ou `tsc --noEmit` falhou? -> REVERTER
             | (OK)
             v
[ 4. Execução de Testes ] -------> `pytest tests/test_modulo.py` falhou? -> FEEDBACK LOOP
             | (OK)
             v
[ 5. Persistência Final ]
```

---

## 3. Comandos de Diagnóstico e Validação Rápida

```powershell
# 1. Validar sintaxe Python de um ficheiro modificado sem executá-lo
python -m py_compile backend/server.py

# 2. Executar linter focado apenas no ficheiro alterado
flake8 backend/server.py --count --select=E9,F63,F7,F82 --show-source --statistics

# 3. Rodar apenas o teste unitário correspondente
pytest tests/test_server.py -q --tb=short
```

---

## 4. O Que Fazer se o Patch Falhar
1. Não tentar adivinhar a linha sem reler o ficheiro: invocar `read_file` com linhas de contexto aumentadas.
2. Se o erro for de indentação ou parênteses, utilizar a ferramenta baseada em AST ou fornecer o bloco inteiro da função a ser substituída.
3. Se 3 tentativas consecutivas falharem, executar [[How to Safely Rollback Failed Code Changes]].

---

## 5. Related Concepts
- [[Patch Generation and Safe Application]]
- [[Compiler Feedback and Test-Driven Self-Repair]]
- [[Safe Rollback and Git Transactional Strategies]]
- [[How to Diagnose Python Import and Module Resolution Failures]]

---

## 6. Sources
- *Python py_compile standard library documentation*: https://docs.python.org/3/library/py_compile.html
- *JARVIS OS Code Modification Policy Specification*
