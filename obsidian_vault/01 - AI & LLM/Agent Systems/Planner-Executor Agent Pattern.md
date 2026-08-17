---
type: pattern
domain: ai-engineering
difficulty: intermediate
tags:
  - ai-engineering
  - agent-patterns
  - architecture
  - planner-executor
  - orchestration
status: verified
---

# ♟️ Planner-Executor Agent Pattern

## 1. Problema & Contexto
Quando um único modelo de linguagem tenta planear uma tarefa multi-etapas complexa e, simultaneamente, executar comandos de baixo nível (como criar ficheiros, rodar testes e depurar erros), ele sofre frequentemente de:
- **Perda de Objetivo Global (Goal Drift)**: Fica preso a resolver um erro de sintaxe menor e esquece o objetivo principal da missão.
- **Saturação Rápida de Contexto**: Logs e saídas detalhadas de ferramentas consomem a janela de raciocínio estratégico.

---

## 2. Solução Arquitetural
O padrão **Planner-Executor** desacopla a inteligência em dois papéis distintos:

```
                  +-------------------------------+
                  |      User / Mission Prompt    |
                  +---------------+---------------+
                                  |
                                  v
                  +-------------------------------+
                  |       PLANNER AGENT           |
                  |  - Decomposição em DAG        |
                  |  - Avaliação de Dependências  |
                  |  - Ordem de Execução          |
                  +---------------+---------------+
                                  | (Plano Estruturado com Tarefas)
                                  v
+-------------------------------------------------------------------+
|                        ORCHESTRATOR / BUS                         |
|   (Monitoriza Estado, Checkpointing, Valida Pré/Pós-Condições)    |
+---------------------------------+---------------------------------+
                                  |
                  +---------------+---------------+
                  |                               |
                  v                               v
+-------------------------------+ +-------------------------------+
|      EXECUTOR AGENT           | |      VALIDATOR AGENT          |
|  - Executa 1 tarefa por vez   | |  - Executa testes e linters   |
|  - Foco em ferramentas locais | |  - Fornece feedback objetivo  |
+-------------------------------+ +-------------------------------+
```

1. **Planner (Estratégico)**:
   - Recebe a meta de alto nível.
   - Decompõe a missão num Grafo Acíclico Dirigido (**DAG**) de tarefas atómicas.
   - Não interage diretamente com ferramentas de baixo nível (mantendo o contexto limpo).
2. **Executor (Tático / Especialista)**:
   - Recebe apenas uma tarefa atómica com o contexto restrito necessário.
   - Executa as ferramentas necessárias até concluir a etapa.
3. **Validator / Reviewer**:
   - Valida se a etapa cumpriu os critérios de aceitação antes de permitir o avanço para o próximo nó do DAG.

---

## 3. Estrutura de Dados do Plano em JSON

```json
{
  "mission_id": "mission-refactor-auth-102",
  "steps": [
    {
      "step_id": 1,
      "title": "Criar middleware de sanitização de tokens",
      "assigned_to": "Devon",
      "dependencies": [],
      "status": "COMPLETED"
    },
    {
      "step_id": 2,
      "title": "Atualizar rotas da API para usar o novo middleware",
      "assigned_to": "Devon",
      "dependencies": [1],
      "status": "PENDING"
    },
    {
      "step_id": 3,
      "title": "Executar suíte de testes de regressão de segurança",
      "assigned_to": "Quinn",
      "dependencies": [2],
      "status": "PENDING"
    }
  ]
}
```

---

## 4. Vantagens do Padrão
- **Tolerância a Falhas e Checkpointing**: Se o executor falhar no passo 3, o sistema não precisa recomeçar do zero; retoma a partir do último checkpoint concluído.
- **Especialização de Modelos**: O Planner pode utilizar um modelo topo de gama (ex: Claude 3.5 Sonnet / Gemini Pro), enquanto os executores de tarefas pontuais podem rodar modelos locais mais rápidos (ex: Ollama).

---

## 5. Used When
- No **JARVIS OS** para gerir missões de desenvolvimento de software de ponta a ponta (planeadas pela Clara, executadas pelo Devon, validadas pelo Quinn).
- Em refatorações de arquitetura que tocam em múltiplos serviços ou módulos.

---

## 6. Related Concepts
- [[Model Harness Architecture]]
- [[Agent Loop Detection and Circuit Breaker]]
- [[Safe Rollback and Git Transactional Strategies]]
- [[Distributed Transactions and Saga Pattern]]

---

## 7. Sources
- *Wang et al., 2023 - A Survey on Large Language Model based Autonomous Agents*: https://arxiv.org/abs/2308.11432
- *Microsoft Semantic Kernel - Planner Architectures*: https://learn.microsoft.com/en-us/semantic-kernel/concepts/planning
