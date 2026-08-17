---
type: audit
domain: jarvis
difficulty: intermediate
tags:
  - jarvis
  - audit
  - rag
status: verified
---

# ðŸ” Auditoria TÃ©cnica do Sistema RAG do Obsidian (JARVIS OS)

**Data da Auditoria:** 17 de Agosto de 2026  
**Componente Auditado:** `agents/obsidian_tools.py` (`buscar_contexto_obsidian`)  
**Status:** Auditado â€” Nenhuma alteraÃ§Ã£o de cÃ³digo aplicada em runtime (aguardando autorizaÃ§Ã£o).

---

## 1. VisÃ£o Geral e Arquitetura Atual
O mecanismo de RAG do Obsidian no JARVIS OS Ã© implementado pela funÃ§Ã£o `buscar_contexto_obsidian(prompt: str) -> str` em [`agents/obsidian_tools.py`](file:///c:/Users/joaor/Desktop/JarvisOS/agents/obsidian_tools.py).

### Funcionamento Atual:
1. **TokenizaÃ§Ã£o LÃ©xica BÃ¡sica**: Extrai palavras com tamanho $> 3$ caracteres via `re.findall(r"\w+", prompt)`.
2. **Varredura no Sistema de Arquivos**: Executa `os.walk()` sobre a pasta do cofre ignorando `.obsidian`.
3. **CÃ¡lculo de Score Simples**:
   - PontuaÃ§Ã£o por Nome de Ficheiro: $+10$ pontos se a palavra estiver contida no nome do ficheiro.
   - PontuaÃ§Ã£o por ConteÃºdo: $+1$ ponto por ocorrÃªncia de cada palavra no texto completo da nota (`content_lower.count(p)`).
4. **SeleÃ§Ã£o e Truncagem**:
   - Ordena e seleciona as **top-2 notas**.
   - Trunca cada nota em **3.000 caracteres** (`content[:3000]`).
5. **FormataÃ§Ã£o de SaÃ­da**: Devolve as notas encapsuladas num bloco markdown para injeÃ§Ã£o no prompt.

---

## 2. DiagnÃ³stico de Problemas, Impacto e RecomendaÃ§Ãµes

### ðŸš¨ Problema 1: Contagem IngÃªnua de FrequÃªncia de Termos (Term Frequency Distortion)
- **DiagnÃ³stico**: Notas muito longas (como os tratados de 8KB em `3. Recursos/`) acumulam dezenas de ocorrÃªncias de palavras comuns como "dados", "sistema", "cÃ³digo" e "erros", obtendo scores muito mais altos que notas atÃ³micas de 2KB altamente focadas e especÃ­ficas no problema.
- **Impacto**: O RAG recupera um tratado longo genÃ©rico em vez do guia de troubleshooting exato (ex: recupera um tratado de 8KB em vez de `How to Diagnose and Resolve SQLite Database Locked Errors.md`).
- **RecomendaÃ§Ã£o**: Implementar o algoritmo **BM25** (que normaliza a frequÃªncia pelo comprimento do documento - *document length penalization*) ou adotar Hybrid Search (BM25 + Dense Embeddings locais).
- **Prioridade**: **ALTA**.

---

### ðŸš¨ Problema 2: Truncagem RÃ­gida por Caracteres (`len(content) > 3000`)
- **DiagnÃ³stico**: O corte de 3.000 caracteres Ã© feito por slice de string crua (`content[:3000]`), cortando blocos de cÃ³digo Python e tabelas a meio da sintaxe.
- **Impacto**: O LLM recebe JSON Schema incompleto ou cÃ³digo truncado sem a funÃ§Ã£o final ou fontes, aumentando o risco de alucinaÃ§Ã£o de fechamento de blocos.
- **RecomendaÃ§Ã£o**:
  1. Truncar estritamente em fronteiras de parÃ¡grafos (`\n\n`) ou blocos de cÃ³digo fechados (```` ````).
  2. Implementar chunking hierÃ¡rquico por seÃ§Ãµes Markdown (`## Heading`).
- **Prioridade**: **ALTA**.

---

### âš ï¸ Problema 3: AusÃªncia de Filtragem por Metadados (Frontmatter Ignorado)
- **DiagnÃ³stico**: O parser ignora completamente o cabeÃ§alho YAML (`type`, `domain`, `tags`, `status`), pesquisando apenas no texto plano.
- **Impacto**: Se um agente de testes (Quinn) precisa apenas de notas do tipo `troubleshooting`, o RAG nÃ£o consegue filtrar por `type: troubleshooting`.
- **RecomendaÃ§Ã£o**: Fazer parse do frontmatter com `yaml.safe_load` ou regex na indexaÃ§Ã£o e permitir queries com filtros (ex: `buscar_contexto_obsidian(prompt, domain="security")`).
- **Prioridade**: **MÃ‰DIA**.

---

### âš ï¸ Problema 4: Falta de Cache / ReindexaÃ§Ã£o a Cada InvocaÃ§Ã£o
- **DiagnÃ³stico**: A cada chamada de funÃ§Ã£o, o cÃ³digo executa `os.walk()` e relÃª todos os ficheiros do disco (`open(full_path).read()`).
- **Impacto**: Para cofres com mais de 80 notas, a latÃªncia de I/O em disco adiciona entre 50ms a 200ms desnecessÃ¡rios em cada turno do agente.
- **RecomendaÃ§Ã£o**: Manter um Ã­ndice em memÃ³ria atualizado com base no timestamp de modificaÃ§Ã£o dos ficheiros (`mtime`), recarregando apenas notas alteradas.
- **Prioridade**: **MÃ‰DIA**.

---

## 3. Tabela Resumo da Auditoria

| DimensÃ£o | Estado Atual | AvaliaÃ§Ã£o | RecomendaÃ§Ãµes Propostas |
|---|---|---|---|
| **Chunking** | Inexistente (ficheiro inteiro com slice de 3000 chars) | ðŸ”´ FrÃ¡gil | Chunking por seÃ§Ãµes semÃ¢nticas Markdown |
| **Retrieval & Ranking** | Contagem linear de palavras + peso de nome | ðŸŸ¡ RazoÃ¡vel | BM25 com penalizaÃ§Ã£o de tamanho de documento |
| **Metadata Filtering** | Nenhum (ignora Frontmatter) | ðŸ”´ Ausente | Suporte a filtros por `domain` e `type` |
| **Busca SemÃ¢ntica** | Apenas correspondÃªncia lÃ©xica exata | ðŸŸ¡ BÃ¡sica | Hybrid Search (Embeddings locais + BM25) |
| **Contexto Injetado** | Top-2 notas completas (mÃ¡x 6000 chars) | ðŸŸ¢ Adequado | Preservar integridade de blocos de cÃ³digo |
| **Performance / Cache**| Leitura de disco por `os.walk` a cada query | ðŸŸ¡ MelhorÃ¡vel | Cache em memÃ³ria com invalidaÃ§Ã£o por `mtime` |

---

## 4. PrÃ³ximos Passos
As alteraÃ§Ãµes no mÃ³dulo `agents/obsidian_tools.py` **NÃƒO foram aplicadas**, preservando a estabilidade atual do sistema, e ficam documentadas para aprovaÃ§Ã£o explÃ­cita futura do operador.

