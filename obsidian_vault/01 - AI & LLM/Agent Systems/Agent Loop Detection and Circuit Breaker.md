---
type: pattern
domain: ai-engineering
difficulty: intermediate
tags:
  - ai-engineering
  - loop-detection
  - circuit-breaker
  - safety
  - autonomous-agents
status: verified
---

# 🔄 Agent Loop Detection and Circuit Breaker

## 1. O Problema dos Loops de Raciocínio
Agentes autónomos operando em ambientes abertos são suscetíveis a entrar em **loops infinitos** ou **oscilações estéreis**:
1. **Loop de Ferramenta Idêntica**: O agente executa `read_file("main.py")`, obtém um erro, e volta a executar exatamente `read_file("main.py")` sem alterar os parâmetros nem a abordagem.
2. **Loop de Oscilação de Edição**: O agente altera `A -> B` para tentar resolver um teste, o teste falha por outro motivo, e ele reverte `B -> A`, repetindo o ciclo indefinitamente.
3. **Loop de Alucinação Argumentativa**: O modelo repete a mesma frase de justificação textual em cada iteração sem tomar nenhuma ação concreta.

---

## 2. Mecanismos de Deteção Algorítmica

```
+--------------------------------------------------------------------+
|  Nova Ação Gerada pelo Agente (Tool Call + Argumentos + Raciocínio) |
+---------------------------------+----------------------------------+
                                  |
                                  v
+--------------------------------------------------------------------+
|                      LOOP DETECTOR PIPELINE                        |
|                                                                    |
|  1. Hash de Assinatura de Ferramenta (Tool + Args Hash)            |
|     -> Se Hash repete >= 3 vezes em janela de 5 -> LOOP DETETADO   |
|                                                                    |
|  2. Distância de Edição Levenshtein no Raciocínio                  |
|     -> Se Similaridade(Thought_t, Thought_{t-1}) > 0.90 -> LOOP    |
|                                                                    |
|  3. Monitor de Progresso de Testes                                 |
|     -> Se Testes Falham com o MESMO traceback por 3 iterações      |
+---------------------------------+----------------------------------+
                                  |
               +------------------+------------------+
               | (Loop Detetado)                     | (Execução Normal)
               v                                     v
+-----------------------------+       +-----------------------------+
|    CIRCUIT BREAKER OPEN     |       |    Executa Ação na Sandbox  |
| - Injeta Intervenção Forçada|       +-----------------------------+
| - Ou Pausa para Humano      |
+-----------------------------+
```

---

## 3. Implementação em Python

```python
import hashlib
import json
from collections import deque
from typing import Optional

class AgentLoopDetector:
    def __init__(self, window_size: int = 6, max_identical_actions: int = 3):
        self.action_history: deque[str] = deque(maxlen=window_size)
        self.max_identical_actions = max_identical_actions

    def _compute_action_hash(self, tool_name: str, args: dict) -> str:
        serialized = json.dumps({"tool": tool_name, "args": args}, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def record_and_check(self, tool_name: str, args: dict) -> tuple[bool, Optional[str]]:
        action_hash = self._compute_action_hash(tool_name, args)
        self.action_history.append(action_hash)

        # Contar ocorrências do mesmo hash na janela deslizante
        count = self.action_history.count(action_hash)
        if count >= self.max_identical_actions:
            return True, (
                f"ALERTA DE CIRCUIT BREAKER: Detetada repetição idêntica da ferramenta '{tool_name}' "
                f"por {count} vezes. É OBRIGATÓRIO mudar de abordagem, inspecionar outros ficheiros "
                f"ou solicitar clarificação."
            )
            
        return False, None
```

---

## 4. Estratégias de Quebra de Loop (Intervenção)
1. **Injeção de Mensagem de Sistema Forçada (Interrupt Prompt)**:
   - *"O sistema detetou que estás a repetir a mesma ação sem progresso. O teu plano anterior falhou. Para e explica por que a abordagem atual não funciona antes de tentar outra ação."*
2. **Escalação de Modelo (Model Step-Up)**:
   - Se o modelo Tier 1 (local) estiver em loop, a requisição é promovida para um modelo Tier Frontier (Claude 3.5 Sonnet / Gemini Pro) para desbloqueio cognitivo.
3. **Pausa para Aprovação Humana (Human-in-the-Loop Gate)**:
   - Para operações destrutivas ou missões em impasse após 5 tentativas sem redução de erros.

---

## 5. Related Concepts
- [[Model Harness Architecture]]
- [[Planner-Executor Agent Pattern]]
- [[How to Detect and Break Agent Infinite Loops]]
- [[Anti-Pattern - Unbounded Context Accumulation]]

---

## 6. Sources
- *Schuurmans et al., 2023 - Memory Augmented Large Language Models are Computationally Universal*: https://arxiv.org/abs/2301.04589
- *Release It!: Design and Deploy Production-Ready Software (Circuit Breaker Pattern - Nygard)*
