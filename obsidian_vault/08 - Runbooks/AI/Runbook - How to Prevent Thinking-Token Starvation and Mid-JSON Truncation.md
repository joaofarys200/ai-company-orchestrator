---
type: runbook
domain: ai-engineering
difficulty: intermediate
status: verified
source_type: JARVIS_INTERNAL
confidence: high
freshness: stable
tags:
  - runbook
  - troubleshooting
  - reasoning-models
  - json-truncation
  - rate-limits
  - model-harness
---

# 🛠️ Runbook - How to Prevent Thinking-Token Starvation and Mid-JSON Truncation

## 1. Sintomas Observáveis
- Chamadas a modelos de raciocínio (`qwen3.5:9b`, `gemini-2.5-flash`, `gemini-4-argon`) demoram $20\text{–}40\text{ s}$ e devolvem `JSONDecodeError: Unterminated string starting at...`.
- O log mostra resposta iniciada por `<think>...` extensa ou JSON cortado a meio de uma lista com `len(raw_text)` próximo do limite configurado (`max_output_tokens = 2048` ou `4096`).
- Em seguida, um fallback de retry em `OutputFormat.TEXT` duplica o consumo de tokens por minuto (TPM) e dispara cascata de erros `HTTP 429 Too Many Requests`.

---

## 2. Diagnóstico Rápido (Checklist em 3 Passos)
1. **Inspecionar `finish_reason` e tags `<think>`**: Se o texto bruto contém `<think>` não fechado ou termina sem `}` final, o orçamento $B_{\text{total}} = T_{\text{think}} + T_{\text{payload}}$ foi esgotado.
2. **Verificar cardinalidade não delimitada no prompt**: Pedir *"resume todas as secções"* num PDF de 26 secções multiplica $T_{\text{payload}}$ acima de $6.000$ tokens.
3. **Auditar política de retry no Model Harness**: Confirmar se erros de transporte (`ConnectError`, `TimeoutException`) ou quota (`429`, `RESOURCE_EXHAUSTED`) estão a acionar uma segunda chamada `OutputFormat.TEXT` inútil no mesmo provedor.

---

## 3. Procedimento de Correção Definitiva

1. **Dimensionar `max_output_tokens` e Delimitar o Esquema**:
   - Elevar `max_output_tokens` para `8192` em sínteses multi-campo e limitar explicitamente no prompt o número de itens por array (ex.: *"4 a 7 secções principais, 3 a 4 blocos detalhados"*).
   - Limitar o excerto de entrada representativo (ex.: `18.000` chars amostrados uniformemente ao longo do documento).
2. **Bloquear Retry Duplicado em Erros de Quota/Transporte**:
   ```python
   err_lower = f"{type(exc).__name__}: {exc}".lower()
   is_transport_or_quota = any(
       k in err_lower for k in ("connecterror", "429", "quota", "rate limit", "timeout")
   )
   if is_transport_or_quota:
       raise  # Não repetir como OutputFormat.TEXT; acionar fallback extrativo imediato
   ```
3. **Ativar Fallback Extrativo Determinístico**: Quando o provedor estiver offline ou em `429`, degradar para extração TF-MMR fundamentada no documento em vez de devolver erro vazio ou texto pré-fabricado.

---

## 4. Referências Cruzadas
- [[Test-Time Compute Scaling and Reasoning Token Budgeting]]
- [[How to Handle Malformed Model Output]]
- [[Lesson - Unhandled Rate Limits and Context Explosion]]
- [[JARVIS Multimodal Study Engine and Grounded Synthesis Pipeline]]

