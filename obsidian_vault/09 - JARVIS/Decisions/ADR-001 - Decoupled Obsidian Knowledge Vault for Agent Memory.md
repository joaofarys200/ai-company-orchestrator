---
type: decision
domain: jarvis
difficulty: intermediate
tags:
  - jarvis
  - adr
  - architectural-decision
  - memory
  - obsidian
status: verified
---

# 📋 ADR-001 - Decoupled Obsidian Knowledge Vault for Agent Memory

## Status
**Aceite / Em Produção**

## Contexto
Os agentes autónomos do JARVIS OS necessitam de aceder a uma base de conhecimento técnico rica (tratados, padrões de engenharia, especificações de protocolos e runbooks operacionais). Injetar todos esses manuais diretamente nos prompts de sistema consome centenas de milhares de tokens, torna a inferência excessivamente cara e lenta, e introduz o problema do "Lost in the Middle".

Por outro lado, utilizar bases de dados proprietárias ou formatos binários opacos dificulta a edição, curadoria e auditoria direta pelo utilizador humano.

## Decisão
Adotar um **Obsidian Knowledge Vault (`obsidian_vault/`) em formato Markdown puro (`.md`) com Wikilinks e MOCs** como a camada desacoplada de memória externa do JARVIS OS.
A integração é feita através de uma ferramenta RAG local (`buscar_contexto_obsidian` em `agents/obsidian_tools.py`), permitindo:
1. Recuperação sob demanda das notas mais relevantes para a tarefa ativa.
2. Leitura e edição direta pelo utilizador no editor Obsidian desktop.
3. Rastreabilidade total e controlo de versão local.

## Consequências
- **Positivas**: Redução drástica de consumo de tokens por turno; capacidade do utilizador enriquecer e auditar o conhecimento sem reiniciar o sistema; interoperabilidade com ferramentas padrão de Markdown.
- **Negativas**: Requer manutenção contínua de integridade de links e algoritmos de pontuação léxica/semântica para garantir alta precisão de recuperação.
