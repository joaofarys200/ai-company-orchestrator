---
type: pattern
domain: backend-systems
difficulty: advanced
tags:
  - backend
  - distributed-systems
  - saga-pattern
  - transactions
  - microservices
status: verified
---

# 🌐 Distributed Transactions and Saga Pattern

## 1. O Problema do Two-Phase Commit (2PC)
Em sistemas distribuídos e arquiteturas agênticas multi-serviço, manter transações ACID clássicas através do protocolo *Two-Phase Commit (2PC)* gera acoplamento temporal excessivo, bloqueios de longa duração e pontos únicos de falha quando nós de rede caem.

---

## 2. O Padrão Saga (Saga Pattern)
Uma **Saga** é uma sequência de transações locais $T_1, T_2, \dots, T_n$. Cada transação local atualiza o banco de dados de um único serviço e publica uma mensagem ou evento.

Se uma etapa $T_k$ falhar, a Saga executa uma série de **Transações Compensatórias** $C_{k-1}, \dots, C_1$ para desfazer as alterações e restaurar a consistência eventual do sistema.

```
Fluxo Normal (Sucesso):
[ T1: Reservar Recursos ] -> [ T2: Executar Build ] -> [ T3: Fazer Deploy ] -> (Concluído)

Fluxo de Falha com Compensação:
[ T1: Reservar Recursos ] -> [ T2: Executar Build ] -> [ T3: Falha no Deploy! ]
                                                               |
[ C1: Libertar Recursos ] <-- [ C2: Limpar Artefatos ] <-------+
```

---

## 3. Orquestração vs Coreografia de Sagas

| Modelo | Mecanismo | Vantagens | Desvantagens |
|---|---|---|---|
| **Orquestrada (Orchestrated)** | Um Orquestrador central (`MissionOrchestrator`) diz a cada agente o que executar | Fácil visualização de estado, sem dependências cíclicas | O orquestrador centraliza a lógica de coordenação |
| **Coreografada (Choreographed)** | Cada serviço/agente reage a eventos no Event Bus (`AsyncEventBus`) | Desacoplamento total | Difícil rastrear o fluxo completo e risco de dependências cíclicas |

---

## 4. Implementação de Saga Orquestrada em Python

```python
from typing import List, Callable, Awaitable
from dataclasses import dataclass

@dataclass
class SagaStep:
    name: str
    action: Callable[..., Awaitable[None]]
    compensate: Callable[..., Awaitable[None]]

class SagaOrchestrator:
    def __init__(self, steps: List[SagaStep]):
        self.steps = steps
        self.executed_steps: List[SagaStep] = []

    async def execute(self) -> bool:
        for step in self.steps:
            try:
                print(f"[Saga] Executando: {step.name}")
                await step.action()
                self.executed_steps.append(step)
            except Exception as error:
                print(f"[Saga] Erro em '{step.name}': {error}. Iniciando compensação...")
                await self._compensate()
                return False
        return True

    async def _compensate(self):
        for step in reversed(self.executed_steps):
            try:
                print(f"[Saga] Compensando: {step.name}")
                await step.compensate()
            except Exception as comp_err:
                print(f"[Saga CRÍTICO] Falha ao compensar '{step.name}': {comp_err}")
```

---

## 5. Used When
- No **JARVIS OS** para missões que tocam em múltiplos subsistemas (ex: criar branch git $\rightarrow$ provisionar sandbox $\rightarrow$ atualizar base de dados de missões $\rightarrow$ disparar agente). Se o agente falhar no boot, a sandbox é destruída e o branch revertido.

---

## 6. Related Concepts
- [[Idempotency in Software Systems]]
- [[Database Crash Consistency and Recovery]]
- [[Planner-Executor Agent Pattern]]
- [[Engenharia_de_Sistemas_Distribuidos_e_Concorrencia]]

---

## 7. Sources
- *Garcia-Molina & Salem, 1987 - Sagas*: https://www.cs.cornell.edu/andru/cs711/2002fa/reading/sagas.pdf
- *Chris Richardson - Microservices Patterns (Pattern: Saga)*: https://microservices.io/patterns/data/saga.html
