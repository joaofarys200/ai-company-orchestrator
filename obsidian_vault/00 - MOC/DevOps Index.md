---
type: index
domain: devops
difficulty: intermediate
tags:
  - devops
  - sre
  - observability
  - tracing
  - chaos-engineering
  - ebpf
  - moc
status: verified
source_type: PRIMARY_SOURCE
confidence: high
freshness: stable
---

# 🚀 DevOps, SRE & Observability Knowledge Index

Este MOC organiza o conhecimento sobre confiabilidade de sistemas, observabilidade com OpenTelemetry/eBPF, resposta a incidentes SRE, rate limiting adaptativo e testes de caos.

---

## 📊 Observability, Distributed Tracing & eBPF
- [[Distributed Tracing and W3C Propagation Mechanics]] — Propagação de contexto com cabeçalho `traceparent` (W3C Recommendation).
- [[Structured Logging and Distributed Trace Context]] — Injeção de `trace_id` e correlação de spans com JSON estruturado.
- [[eBPF Syscall Tracing and Sandbox Process Auditing]] — Rastreamento de chamadas de sistema no kernel Linux sem sobrecarga de ptrace.

## 🎯 SRE, Reliability & Chaos Engineering
- [[Google SRE Incident Response and Postmortems]] — Protocolo Blameless, papéis no comando de incidentes e métricas MTTD/MTTR.
- [[SLI-SLO Metrics and Error Budgets]] — Indicadores de nível de serviço, objetivos e cálculo de queima de error budget.
- [[Healthchecks and Circuit Breakers]] — Estados fechado, aberto e meio-aberto para degradação graciosa.
- [[Adaptive Rate Limiting and Token Bucket with Jitter]] — Balde de tokens e mitigação de thundering herd com full jitter.
- [[Chaos Engineering and Fault Injection in Autonomous Swarms]] — Injeção de falhas e prova de invariantes sob interrupções forçadas.
- [[SRE_Site_Reliability_Engineering_Body_of_Knowledge]] — Monografia sobre as disciplinas de SRE do Google.

## 🔄 CI-CD & Automated Healing
- [[CI-CD Pipeline Failure Triage and Automated Healing]] — Ciclo fechado de detecção e correção automática de falhas de pipeline.

## 🐳 Containerization & Resources
- [[Docker Container Security and Resource Capping]] — Limites de memória/CPU (`cgroups`) e execução sem privilégios de root.

---

## 🛠️ Runbooks Relacionados em 08 - Runbooks/DevOps
- [[How to Triage and Fix Broken CI-CD Pipelines]] — Protocolo de diagnóstico de falhas em runners de integração contínua.
- [[How to Implement Circuit Breakers for Flaky External APIs]] — Implementação de circuit breaker em clientes HTTP assíncronos.
- [[Runbook - How to Recover from Worker Thrashing and CPU Throttling]] — Recuperação de sobrecarga de CPU e processos órfãos.

## 📝 Lições de Produção em 09 - JARVIS/Lessons
- [[Lesson - Stale Preview Port Binding Collision]] — Colisão de portas de desenvolvimento em runners concorrentes.
