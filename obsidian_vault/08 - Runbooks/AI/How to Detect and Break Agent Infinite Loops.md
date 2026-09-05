---
type: troubleshooting
domain: ai-engineering
difficulty: intermediate
tags:
  - ai-engineering
  - troubleshooting
  - loop-breaking
  - circuit-breaker
  - autonomous-agents
status: verified
---

# 🛠️ï¸ How to Detect and Break Agent Infinite Loops

## 1. Sintomas & Diagnóstico
- O agente gera mais de 5 turnos consecutivos chamando a mesma ferramenta com argumentos idênticos ou ligeiras variações sem progresso.
- O traceback de erro de teste unitário repete-se com a mesma mensagem de `AssertionError` por 3 tentativas seguidas.
- A memória de contexto atinge o limite máximo enquanto o agente oscila entre duas soluções mutuamente exclusivas.

---

## 2. Diagnóstico Passo a Passo

```bash
# 1. Verificar histórico recente de ações do agente
# Observar se o tool_name e args_hash se repetem:
[Step 12] Tool: read_file (path: "backend/server.py") -> Error: not found
[Step 13] Tool: read_file (path: "backend/server.py") -> Error: not found
[Step 14] Tool: read_file (path: "backend/server.py") -> LOOP DETETADO
```

---

## 3. Procedimento de Quebra e Recuperação (Runbook)

### Passo 1: Interrupção Imediata do Runner (Circuit Breaker)
Travar a execução do loop antes que consuma mais tokens ou execute ações potencialmente destrutivas.

### Passo 2: Injeção de Contexto de Resolução (Forced Pivot)
Injetar no prompt do agente uma mensagem de sistema de prioridade máxima com a seguinte estrutura:

```markdown
<system_override_alert>
ALERTA DO SISTEMA: A tua abordagem anterior falhou 3 vezes consecutivas.
- Ação repetida: read_file("backend/server.py")
- Motivo da falha: O ficheiro não existe nessa localização.

AÇÃƒO OBRIGATÃ“RIA:
1. Executa 'list_dir' na raiz do workspace para localizar a estrutura real de pastas.
2. Não tentes ler 'backend/server.py' novamente até confirmares a sua localização.
</system_override_alert>
```

### Passo 3: Escalação para Modelo com Maior Capacidade Cognitiva
Se o modelo em execução for um modelo local (ex: Ollama 7B), o orquestrador deve escalar a requisição para um modelo de raciocínio de ponta (ex: Claude 3.5 Sonnet / Gemini Pro) com instrução explícita para desbloquear o impasse.

### Passo 4: Se o Impasse Persistir $\rightarrow$ Human Gate
Se após a escalação o agente não conseguir progredir em 2 iterações adicionais:
1. Salvar o estado da missão na base de dados (`status = "PAUSED_WAITING_HUMAN"`).
2. Emitir uma notificação com o diagnóstico detalhado para o operador.

---

## 4. Prevenção
- Implementar a classe `AgentLoopDetector` (ver [[Agent Loop Detection and Circuit Breaker]]) no loop principal do `SwarmOrchestrator`.
- Definir limites estritos de iterações por subtarefa ($MaxSteps \le 10$).

---

## 5. Related Concepts
- [[Agent Loop Detection and Circuit Breaker]]
- [[Planner-Executor Agent Pattern]]
- [[Anti-Pattern - Unbounded Context Accumulation]]
- [[Model Harness Architecture]]

---

## 6. Sources
- *Google SRE Book - Cascading Failures and Circuit Breaking*: https://sre.google/sre-book/addressing-cascading-failures/
- *JARVIS OS Swarm Orchestrator Architecture Documentation*

## Query Relevance
Como detectar e interromper loops infinitos de agentes com circuit breaker.

