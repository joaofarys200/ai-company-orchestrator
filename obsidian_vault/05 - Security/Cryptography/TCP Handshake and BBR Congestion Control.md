---
type: concept
domain: security
status: verified
source_type: PRIMARY_SOURCE
confidence: high
difficulty: advanced
tags:
  - security
  - networking
  - tcp
  - bbr
  - devsecops
prerequisites:
  - "[[Tratado_Completo_de_Ciberseguranca_Redes_e_DevSecOps]]"
related:
  - "[[FastAPI and WebSocket Lifecycle Management]]"
  - "[[SSRF Defense in Agentic Fetchers]]"
used_by:
  - "[[JARVIS Component Architecture]]"
failure_modes:
  - "[[Lesson - Accidental Secret Leaks in Telemetry Broadcast]]"
implementation:
  - "[[JARVIS System Architecture]]"
sources:
  - title: RFC 9293 - Transmission Control Protocol (TCP)
    type: PRIMARY_SOURCE
    url: https://datatracker.ietf.org/doc/html/rfc9293
  - title: BBR - Congestion-Based Congestion Control (Google Research)
    type: PRIMARY_SOURCE
    url: https://research.google/pubs/bbr-congestion-based-congestion-control/
---

# 🌐 TCP Handshake and BBR Congestion Control

## 1. Pergunta Central
> *Como o protocolo TCP estabelece sessões com garantia de entrega e como algoritmos modernos como BBR (Bottleneck Bandwidth and RTT) maximizam o rendimento de rede sem causar saturação de buffers (Bufferbloat)?*

---

## 2. O Three-Way Handshake & Encerramento

```
Cliente                                         Servidor
   |                                               |
   | --- 1. SYN (seq = x) -----------------------> | (Estado: SYN-RECEIVED)
   | <--- 2. SYN-ACK (seq = y, ack = x + 1) ------ | (Estado: ESTABLISHED)
   | --- 3. ACK (seq = x + 1, ack = y + 1) ------> | (Estado: ESTABLISHED)
```

---

## 3. Mecânica do Algoritmo Google BBR
Ao contrário de algoritmos de perda de pacotes como Reno e CUBIC (que interpretam qualquer perda como congestionamento, reduzindo drasticamente a janela de envio), o **BBR** constrói um modelo contínuo de:
1. **Bottleneck Bandwidth ($BtlBw$)**: A capacidade máxima do nó mais lento no trajeto.
2. **Round-Trip Propagation Time ($RTprop$)**: A menor latência física de ida e volta observada.

A taxa de envio é ajustada para operar exatamente no ponto ótimo de Kleinrock:

$$\text{Pacing Rate} = BtlBw \times \text{Pacing Gain}$$

---

## 4. Related Concepts
- [[FastAPI and WebSocket Lifecycle Management]]
- [[SSRF Defense in Agentic Fetchers]]
- [[Tratado_Completo_de_Ciberseguranca_Redes_e_DevSecOps]]
