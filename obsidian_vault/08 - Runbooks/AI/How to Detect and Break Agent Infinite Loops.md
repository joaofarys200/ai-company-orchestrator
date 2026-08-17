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

# ðŸ› ï¸ How to Detect and Break Agent Infinite Loops

## 1. Sintomas & DiagnÃ³stico
- O agente gera mais de 5 turnos consecutivos chamando a mesma ferramenta com argumentos idÃªnticos ou ligeiras variaÃ§Ãµes sem progresso.
- O traceback de erro de teste unitÃ¡rio repete-se com a mesma mensagem de `AssertionError` por 3 tentativas seguidas.
- A memÃ³ria de contexto atinge o limite mÃ¡ximo enquanto o agente oscila entre duas soluÃ§Ãµes mutuamente exclusivas.

---

## 2. DiagnÃ³stico Passo a Passo

```bash
# 1. Verificar histÃ³rico recente de aÃ§Ãµes do agente
# Observar se o tool_name e args_hash se repetem:
[Step 12] Tool: read_file (path: "backend/server.py") -> Error: not found
[Step 13] Tool: read_file (path: "backend/server.py") -> Error: not found
[Step 14] Tool: read_file (path: "backend/server.py") -> LOOP DETETADO
```

---

## 3. Procedimento de Quebra e RecuperaÃ§Ã£o (Runbook)

### Passo 1: InterrupÃ§Ã£o Imediata do Runner (Circuit Breaker)
Travar a execuÃ§Ã£o do loop antes que consuma mais tokens ou execute aÃ§Ãµes potencialmente destrutivas.

### Passo 2: InjeÃ§Ã£o de Contexto de ResoluÃ§Ã£o (Forced Pivot)
Injetar no prompt do agente uma mensagem de sistema de prioridade mÃ¡xima com a seguinte estrutura:

```markdown
<system_override_alert>
ALERTA DO SISTEMA: A tua abordagem anterior falhou 3 vezes consecutivas.
- AÃ§Ã£o repetida: read_file("backend/server.py")
- Motivo da falha: O ficheiro nÃ£o existe nessa localizaÃ§Ã£o.

AÃ‡ÃƒO OBRIGATÃ“RIA:
1. Executa 'list_dir' na raiz do workspace para localizar a estrutura real de pastas.
2. NÃ£o tentes ler 'backend/server.py' novamente atÃ© confirmares a sua localizaÃ§Ã£o.
</system_override_alert>
```

### Passo 3: EscalaÃ§Ã£o para Modelo com Maior Capacidade Cognitiva
Se o modelo em execuÃ§Ã£o for um modelo local (ex: Ollama 7B), o orquestrador deve escalar a requisiÃ§Ã£o para um modelo de raciocÃ­nio de ponta (ex: Claude 3.5 Sonnet / Gemini Pro) com instruÃ§Ã£o explÃ­cita para desbloquear o impasse.

### Passo 4: Se o Impasse Persistir $\rightarrow$ Human Gate
Se apÃ³s a escalaÃ§Ã£o o agente nÃ£o conseguir progredir em 2 iteraÃ§Ãµes adicionais:
1. Salvar o estado da missÃ£o na base de dados (`status = "PAUSED_WAITING_HUMAN"`).
2. Emitir uma notificaÃ§Ã£o com o diagnÃ³stico detalhado para o operador.

---

## 4. PrevenÃ§Ã£o
- Implementar a classe `AgentLoopDetector` (ver [[Agent Loop Detection and Circuit Breaker]]) no loop principal do `SwarmOrchestrator`.
- Definir limites estritos de iteraÃ§Ãµes por subtarefa ($MaxSteps \le 10$).

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

