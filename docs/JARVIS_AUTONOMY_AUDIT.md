# 🤖 JARVIS OS — AUTONOMY & BOUNDED CAPABILITIES AUDIT

**Data**: 2026-08-13  
**Foco**: Análise das capacidades autónomas do JARVIS, segurança de execução e fronteiras operacionais.

---

## 1. 📊 MATRIZ GERAL DE CAPACIDADES & AUTONOMIA

| Capacidade | Disponível? | Verificado? | Seguro? | Nível de Autonomia | Tipo de Ação |
|---|---|---|---|---|---|
| **Criar / Modificar Ficheiro** | ✅ Sim | ✅ Sim | ✅ Sim (AST Sandbox) | Autonomia Total | Local |
| **Executar Comandos Shell** | ✅ Sim | ✅ Sim | ✅ Sim (Allowlist) | Autonomia Total (Local) | Local |
| **Executar Testes Unitários** | ✅ Sim | ✅ Sim | ✅ Sim | Autonomia Total | Local |
| **Pesquisa Web / Scraping** | ✅ Sim | ✅ Sim | ✅ Sim | Autonomia Total (Read-only) | Externa (Leitura) |
| **Criar Documento Técnico** | ✅ Sim | ✅ Sim | ✅ Sim | Autonomia Total | Local |
| **Deploy no Sandbox Local** | ✅ Sim | ✅ Sim | ✅ Sim (Port 8080) | Autonomia Total | Local |
| **Publicação Pública na Web** | ⚠️ Parcial | ⚠️ Parcial | 🛡️ Protegido | Requer Aprovação Humana | Externa (Escrita) |
| **Enviar Email Real** | ❌ Não | ❌ Não | 🛡️ Protegido | Requer Aprovação Humana | Externa (Escrita) |
| **Adquirir Lead (Sandbox)** | ✅ Sim | ✅ Sim | ✅ Sim (SQLite) | Autonomia Total (Local) | Local |
| **Adquirir Lead (Tráfego Real)** | ⚠️ Parcial | ⚠️ Parcial | 🛡️ Protegido | Autonomia Bounded | Externa |
| **Processar Pagamento Real** | ❌ Não | ❌ Não | 🛡️ Protegido | Requer Aprovação Humana | Externa (Financeira) |
| **Calcular Métricas Financeiras** | ✅ Sim | ✅ Sim | ✅ Sim | Autonomia Total | Local |
| **Iterar / Abandonar Missão** | ✅ Sim | ✅ Sim | ✅ Sim | Autonomia Total (Decisão) | Local |
| **Retomar Missão após Restart** | ✅ Sim | ✅ Sim | ✅ Sim | Autonomia Total | Local |

---

## 2. 🛡️ DISTINÇÃO ESTRITA DOS NÍVEIS DE AUTONOMIA

1. **AUTONOMOUS PLANNING**:
   - O JARVIS decompõe objetivos em work packages e grafos de dependências sem qualquer assistência humana.
2. **AUTONOMOUS EXECUTION**:
   - O JARVIS escreve código, aplica patches AST, executa testes e verifica health checks em loop local fechado.
3. **AUTONOMOUS RECOVERY**:
   - Se um patch falhar a sintaxe ou um teste unitário quebrar, o motor faz rollback automático e tenta uma abordagem alternativa.
4. **AUTONOMOUS DECISION**:
   - O agente analisa métricas e decide se continua a iterar ou se abandona uma hipótese com base em critérios matemáticos ($EV$, ROI).
5. **AUTONOMOUS EXTERNAL ACTION (Apenas com Bounded Policy)**:
   - Ações que afetam o mundo exterior (gastos financeiros, publicações externas, envio de emails) **permanecem estritamente bloqueadas por portões de aprovação humana** (`PENDING_APPROVAL`).
