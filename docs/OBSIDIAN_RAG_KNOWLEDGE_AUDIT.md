# 🔍 Auditoria Técnica do Sistema RAG do Obsidian (JARVIS OS)

**Data da Auditoria:** 17 de Agosto de 2026  
**Componente Auditado:** `agents/obsidian_tools.py` (`buscar_contexto_obsidian`)  
**Status:** Auditado — Nenhuma alteração de código aplicada em runtime (aguardando autorização).

---

## 1. Visão Geral e Arquitetura Atual
O mecanismo de RAG do Obsidian no JARVIS OS é implementado pela função `buscar_contexto_obsidian(prompt: str) -> str` em [`agents/obsidian_tools.py`](file:///c:/Users/joaor/Desktop/JarvisOS/agents/obsidian_tools.py).

### Funcionamento Atual:
1. **Tokenização Léxica Básica**: Extrai palavras com tamanho $> 3$ caracteres via `re.findall(r"\w+", prompt)`.
2. **Varredura no Sistema de Arquivos**: Executa `os.walk()` sobre a pasta do cofre ignorando `.obsidian`.
3. **Cálculo de Score Simples**:
   - Pontuação por Nome de Ficheiro: $+10$ pontos se a palavra estiver contida no nome do ficheiro.
   - Pontuação por Conteúdo: $+1$ ponto por ocorrência de cada palavra no texto completo da nota (`content_lower.count(p)`).
4. **Seleção e Truncagem**:
   - Ordena e seleciona as **top-2 notas**.
   - Trunca cada nota em **3.000 caracteres** (`content[:3000]`).
5. **Formatação de Saída**: Devolve as notas encapsuladas num bloco markdown para injeção no prompt.

---

## 2. Diagnóstico de Problemas, Impacto e Recomendações

### 🚨 Problema 1: Contagem Ingênua de Frequência de Termos (Term Frequency Distortion)
- **Diagnóstico**: Notas muito longas (como os tratados de 8KB em `3. Recursos/`) acumulam dezenas de ocorrências de palavras comuns como "dados", "sistema", "código" e "erros", obtendo scores muito mais altos que notas atómicas de 2KB altamente focadas e específicas no problema.
- **Impacto**: O RAG recupera um tratado longo genérico em vez do guia de troubleshooting exato (ex: recupera um tratado de 8KB em vez de `How to Diagnose and Resolve SQLite Database Locked Errors.md`).
- **Recomendação**: Implementar o algoritmo **BM25** (que normaliza a frequência pelo comprimento do documento - *document length penalization*) ou adotar Hybrid Search (BM25 + Dense Embeddings locais).
- **Prioridade**: **ALTA**.

---

### 🚨 Problema 2: Truncagem Rígida por Caracteres (`len(content) > 3000`)
- **Diagnóstico**: O corte de 3.000 caracteres é feito por slice de string crua (`content[:3000]`), cortando blocos de código Python e tabelas a meio da sintaxe.
- **Impacto**: O LLM recebe JSON Schema incompleto ou código truncado sem a função final ou fontes, aumentando o risco de alucinação de fechamento de blocos.
- **Recomendação**:
  1. Truncar estritamente em fronteiras de parágrafos (`\n\n`) ou blocos de código fechados (```` ````).
  2. Implementar chunking hierárquico por seções Markdown (`## Heading`).
- **Prioridade**: **ALTA**.

---

### ⚠️ Problema 3: Ausência de Filtragem por Metadados (Frontmatter Ignorado)
- **Diagnóstico**: O parser ignora completamente o cabeçalho YAML (`type`, `domain`, `tags`, `status`), pesquisando apenas no texto plano.
- **Impacto**: Se um agente de testes (Quinn) precisa apenas de notas do tipo `troubleshooting`, o RAG não consegue filtrar por `type: troubleshooting`.
- **Recomendação**: Fazer parse do frontmatter com `yaml.safe_load` ou regex na indexação e permitir queries com filtros (ex: `buscar_contexto_obsidian(prompt, domain="security")`).
- **Prioridade**: **MÉDIA**.

---

### ⚠️ Problema 4: Falta de Cache / Reindexação a Cada Invocação
- **Diagnóstico**: A cada chamada de função, o código executa `os.walk()` e relê todos os ficheiros do disco (`open(full_path).read()`).
- **Impacto**: Para cofres com mais de 80 notas, a latência de I/O em disco adiciona entre 50ms a 200ms desnecessários em cada turno do agente.
- **Recomendação**: Manter um índice em memória atualizado com base no timestamp de modificação dos ficheiros (`mtime`), recarregando apenas notas alteradas.
- **Prioridade**: **MÉDIA**.

---

## 3. Tabela Resumo da Auditoria

| Dimensão | Estado Atual | Avaliação | Recomendações Propostas |
|---|---|---|---|
| **Chunking** | Inexistente (ficheiro inteiro com slice de 3000 chars) | 🔴 Frágil | Chunking por seções semânticas Markdown |
| **Retrieval & Ranking** | Contagem linear de palavras + peso de nome | 🟡 Razoável | BM25 com penalização de tamanho de documento |
| **Metadata Filtering** | Nenhum (ignora Frontmatter) | 🔴 Ausente | Suporte a filtros por `domain` e `type` |
| **Busca Semântica** | Apenas correspondência léxica exata | 🟡 Básica | Hybrid Search (Embeddings locais + BM25) |
| **Contexto Injetado** | Top-2 notas completas (máx 6000 chars) | 🟢 Adequado | Preservar integridade de blocos de código |
| **Performance / Cache**| Leitura de disco por `os.walk` a cada query | 🟡 Melhorável | Cache em memória com invalidação por `mtime` |

---

## 4. Próximos Passos
As alterações no módulo `agents/obsidian_tools.py` **NÃO foram aplicadas**, preservando a estabilidade atual do sistema, e ficam documentadas para aprovação explícita futura do operador.
