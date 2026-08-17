---
type: lesson
domain: jarvis
status: verified
source_type: JARVIS_INTERNAL
confidence: high
freshness: stable
difficulty: intermediate
tags:
  - lesson
  - jarvis
  - web-deployment
  - port-collision
  - networking
  - devops
prerequisites:
  - "[[TCP Handshake and BBR Congestion Control]]"
related:
  - "[[JARVIS ProjectBuilder and Validation Pipeline]]"
  - "[[Least-Privilege Process Sandboxing and Execution Jail]]"
used_by:
  - "[[JARVIS Autonomous Agent Hierarchy]]"
failure_modes:
  - "[[How to Detect Failed Playwright Deployments]]"
implementation:
  - "[[JARVIS Component Architecture]]"
sources:
  - title: JARVIS Incident Report - Vite Preview Port Collision in Sandbox
    type: JARVIS_INTERNAL
    url: internal://tests/test_project_builder.py
---

# 📝 Lesson - Stale Preview Port Binding Collision

## Failure
Durante a validação de um projeto frontend em execução na sandbox, o servidor de desenvolvimento Vite falhou ao tentar escutar na porta 5173 (`EADDRINUSE: address already in use 0.0.0.0:5173`), fazendo com que o teste de navegação do Playwright testasse uma versão residual de uma missão anterior em vez da nova build gerada.

---

## Symptoms
- O Playwright capturou screenshots de uma landing page antiga que não correspondia ao código gerado na missão atual.
- O terminal da sandbox exibiu o aviso: `Port 5173 is in use, trying another one... 5174`.
- A asserção de teste conectou na porta padrão 5173 e validou o processo órfão anterior.

---

## Detection
O teste automatizado de integração detectou discrepância entre os seletores esperados e o HTML retornado no `page.content()`.

---

## Root Cause
Um processo anterior de preview do Node.js não foi encerrado com `SIGKILL` no encerramento da missão anterior devido a um descolamento de grupo de processos (*Detached Process Group*).

---

## Why Existing Protection Failed
O gerenciador de processos apenas enviava `process.kill()` para o PID principal, deixando os processos filhos gerados pelo `npm run dev` vivos em background.

---

## Blast Radius
Contaminação de resultados de validação visual de missões subsequentes, gerando falsos positivos de sucesso.

---

## Recovery
1. Executar no runner de teste: `fuser -k 5173/tcp` ou no Windows: `netstat -ano | findstr :5173` seguido de `taskkill /PID <pid> /F`.
2. Alocar dinamicamente portas livres usando `port = find_free_port()`.

---

## Corrective Action
Implementar em `sandbox.py` a alocação de portas dinâmicas e o encerramento por grupo de processos (`os.killpg(os.getpgid(p.pid), signal.SIGTERM)`).

---

## Preventive Control
Configurar o Vite com `server: { strictPort: true, port: DYNAMIC_PORT }`, abortando imediatamente se a porta estiver ocupada em vez de pular silenciosamente para outra porta.

---

## Generalizable Principle
> *Serviços temporários em pipelines de teste e validação de IA devem sempre utilizar portas alocadas dinamicamente e modo de porta estrita (`strictPort`), garantindo que o cliente de teste e o servidor compartilhem exatamente o mesmo descritor semântico.*

---

## Tests
- `tests/test_project_builder.py::test_dynamic_port_cleanup`

---

## Related Concepts
- [[TCP Handshake and BBR Congestion Control]]
- [[JARVIS ProjectBuilder and Validation Pipeline]]
- [[How to Detect Failed Playwright Deployments]]

---

## Related Runbooks
- [[How to Detect Failed Playwright Deployments]]

---

## Evidence
- Log de auditoria em `tests/test_project_builder.py`.
