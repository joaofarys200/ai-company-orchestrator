# 🧠 JARVIS OS — MODEL HARNESS ENGINEERING AUDIT

**Data**: 2026-08-13  
**Foco**: Avaliação em profundidade do subsistema `backend/model_harness/` e integração com `qwen3.5:9b`.

---

## 1. ⚙️ FLUXO REAL DE EXECUÇÃO DO MODEL HARNESS

```
[Request do Agente]
        │
        ▼
[ModelHarness.execute(request)]
        │
        ├──► 1. Injeção Dinâmica de Regras SHE (Segurança) & RHO (Aprendizado Contínuo)
        ├──► 2. Roteador de Modelos (Router.route() -> Ollama qwen3.5:9b)
        ├──► 3. Geração via Provedor (Provider.generate() com streaming e tool parser)
        ├──► 4. Pipeline de Validação de 7 Estágios (ValidationPipeline):
        │       ├── [PARSING]          ──► Verificação sintática JSON/Text
        │       ├── [SCHEMA]           ──► Verificação de chaves obrigatórias
        │       ├── [ENUMS]            ──► Validação de valores permitidos
        │       ├── [REFERENCES]       ──► Validação de ficheiros e IDs citados
        │       ├── [PRECONDITIONS]    ──► Verificação de estado inicial
        │       ├── [COMPATIBILITY]    ──► Compatibilidade de formatos
        │       └── [ACCEPTANCE]       ──► Critérios de aceitação da tarefa
        ├──► 5. Progress Tracker (Deteção de NO_PROGRESS / REPEATED_REASONING)
        ├──► 6. Motor de Recuperação Semântica (RecoveryEngine.decide())
        └──► 7. Gravação de Trajetória & Telemetria no SQLite RHO
```

---

## 2. 📊 CLASSIFICAÇÃO DE ROBUSTEZ DO MODEL HARNESS

### A. O Que Está Comprovadamente Robusto (Comprovado em Testes & Benchmark):
- **Validação Estruturada**: O pipeline de 7 estágios rejeita instantaneamente saídas com esquemas corrompidos.
- **Deteção de Loops**: O `ProgressTracker` interrompe execuções redundantes antes de esgotar a cota de tokens.
- **Isolamento de Provedores**: O motor trata falhas no Ollama ou Gemini sem quebrar o loop principal do agente.
- **RHO & SHE Dynamic Injections**: Injeção semântica de regras no `system_prompt` funciona sem interferir com o prompt base do utilizador.

### B. O Que Está Apenas Testado Superficialmente:
- **Janelas de Contexto Extremamente Longas (>32k tokens)**: Necessidade de monitorizar o overhead de latência no Ollama local quando ficheiros grandes são inseridos.
- **Streaming de Tool Calls Parciais**: O parser atual reconstrói tool calls após recepção do bloco completo; chamadas ultra-rápidas em stream duplex devem ser acompanhadas.

### C. O Que Continua Vulnerável:
- **Alucinação de Ficheiros em Projetos Grandes**: Se o contexto não contiver a lista completa da árvore do projeto, o modelo pode sugerir editar caminhos inexistentes (já mitigado pelo `ProjectContextService`).

---

## 3. 🎯 DECISÕES ESTRATÉGICAS

- **Manter o Qwen 3.5:9b**: O modelo demonstra excelente performance em chamadas estruturadas de ferramentas e geração de código AST quando guiado pelo harness.
- **NÃO alterar o pipeline de validação**: É a salvaguarda central que garante a integridade de todas as missões.
