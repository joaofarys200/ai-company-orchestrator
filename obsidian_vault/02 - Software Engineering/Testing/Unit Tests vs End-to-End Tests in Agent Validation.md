---
type: comparison
domain: software-engineering
difficulty: intermediate
tags:
  - software-engineering
  - testing
  - unit-testing
  - e2e-testing
  - validation
status: verified
---

# ⚖️ Unit Tests vs End-to-End Tests in Agent Validation

## 1. Tabela Comparativa

| Dimensão | Testes Unitários (Unit Tests) | Testes Ponta-a-Ponta (E2E Tests) |
|---|---|---|
| **Escopo de Validação** | Função, método ou módulo isolado (com mocks) | Sistema completo integrado (DB, API, Frontend, Rede) |
| **Velocidade de Execução** | Milissegundos ($10\text{ms} - 500\text{ms}$) | Segundos a minutos ($5\text{s} - 120\text{s}$) |
| **Determinismo** | Altíssimo (isolado de I/O e concorrência externa) | Moderado (suscetível a *flakiness*, latência e timeouts) |
| **Diagnóstico de Erros para IA** | Exato (indica o ficheiro, função e asserção que falhou) | Difuso (indica que a página falhou ao renderizar ou HTTP 500 genérico) |
| **Consumo de Recursos** | Baixíssimo (apenas CPU local) | Alto (requer browsers headless, containers, servidores ativos) |
| **Momento de Execução no Loop do Agente** | A cada patch gerado (feedback imediato) | Apenas no final da missão (aprovação para merge) |

---

## 2. A Pirâmide de Validação para Agentes Autónomos

```
                  / \
                 /   \
                / E2E \       <--- Validação Final (Playwright / Smoke Test)
               /-------\
              / Integr. \     <--- Validação de Contrato (FastAPI TestClient + SQLite)
             /-----------\
            /  Unitários  \   <--- Loop Interno Rápido do Agente (pytest puro)
           /---------------\
```

---

## 3. Conclusão & Padrão de Arquitetura para o JARVIS OS
- **Durante o ciclo iterativo de codificação (Devon)**: Executar exclusivamente **testes unitários** para obter ciclos de feedback inferiores a 2 segundos.
- **Após todos os testes unitários passarem**: Disparar os testes de integração e validação E2E (Quinn/Alex) como gate final de qualidade antes da entrega.

---

## 4. Related Concepts
- [[Compiler Feedback and Test-Driven Self-Repair]]
- [[Clean Architecture and Hexagonal Ports]]
- [[Playwright Architecture and Automation Protocol]]
- [[How to Safely Validate and Apply Code Patches]]

---

## 5. Sources
- *Martin Fowler - The Practical Test Pyramid*: https://martinfowler.com/articles/practical-test-pyramid.html
- *Google Testing Blog - Just Say No to More End-to-End Tests*: https://testing.googleblog.com/2015/04/just-say-no-to-more-end-to-end-tests.html
