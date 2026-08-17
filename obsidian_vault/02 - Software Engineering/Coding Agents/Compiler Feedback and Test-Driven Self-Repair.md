---
type: pattern
domain: software-engineering
difficulty: intermediate
tags:
  - software-engineering
  - coding-agents
  - self-repair
  - tdd
  - compiler-feedback
status: verified
---

# 🔁 Compiler Feedback and Test-Driven Self-Repair

## 1. Definição & Ciclo Fechado de Reparação
O padrão de **Auto-Reparação Guiada por Compilador e Testes (Compiler Feedback / TDD Self-Repair Loop)** é o processo iterativo em que um agente de IA gera uma modificação de código, executa os validadores do ecossistema de compilação/teste, extrai os erros objetivos e retroalimenta o modelo até que todos os testes passem com sucesso.

```
       +---------------------------------------------+
       |   1. Agente Gera / Modifica Código-Fonte    |
       +----------------------+----------------------+
                              |
                              v
       +---------------------------------------------+
       |   2. Execução da Sandbox de Validação       |
       |      - Compilação / AST Parsing             |
       |      - Linter & Type Checker (pyright/tsc)  |
       |      - Suíte de Testes (pytest / vitest)    |
       +----------------------+----------------------+
                              |
              +---------------+---------------+
              |                               |
        (Sucesso 100%)                  (Erros / Falhas)
              |                               |
              v                               v
    +-------------------+           +---------------------------------+
    | 3. Commit / Merge |           | 4. Extração Cirúrgica do Erro   |
    |    do Patch       |           |    - File, Line, Expected vs Got|
    +-------------------+           +----------------+----------------+
                                                     |
                                                     v
                                    +---------------------------------+
                                    | 5. Prompt de Auto-Correção com  |
                                    |    Traceback Focado             |
                                    +----------------+----------------+
                                                     |
                                                     +---> Volta ao Passo 1 (Max 3-5 iterações)
```

---

## 2. Extração Focada de Tracebacks (Noise Reduction)

Para evitar saturar o contexto com milhares de linhas de logs inúteis do terminal, o extrator isola apenas o diagnóstico essencial:

```python
import re

def extract_test_failure_summary(pytest_output: str) -> str:
    """
    Extrai estritamente as falhas de asserção e linhas do pytest.
    """
    failures = []
    # Capturar blocos de FAILURES
    match = re.search(r"=+\s+FAILURES\s+=+([\s\S]*?)=+\s+short test summary info", pytest_output)
    if match:
        raw_failures = match.group(1).strip()
        # Truncar se for excessivamente longo
        if len(raw_failures) > 2000:
            raw_failures = raw_failures[:2000] + "\n...[Restante truncado]"
        return raw_failures

    # Fallback para as últimas 30 linhas se não houver formato padrão
    lines = pytest_output.splitlines()
    return "\n".join(lines[-30:])
```

---

## 3. Diretrizes de Auto-Correção para o Agente
1. **Nunca Apagar Testes para Passar**: O agente é estritamente proibido de alterar as asserções do teste unitário para mascarar o bug, a menos que o objetivo explícito da missão seja atualizar o contrato de testes.
2. **Modificações Incrementais**: Corrigir um erro de cada vez em vez de reescrever a arquitetura completa a cada falha.

---

## 4. Related Concepts
- [[Patch Generation and Safe Application]]
- [[Safe Rollback and Git Transactional Strategies]]
- [[Unit Tests vs End-to-End Tests in Agent Validation]]
- [[How to Safely Validate and Apply Code Patches]]

---

## 5. Sources
- *Kent Beck - Test-Driven Development: By Example*
- *Jimenez et al., 2023 - SWE-bench: Can Language Models Resolve Real-World GitHub Issues?*: https://arxiv.org/abs/2310.06770
