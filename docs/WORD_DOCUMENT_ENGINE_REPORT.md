# JARVIS OS — MOTOR DOCUMENTAL E REVISÃO PROFISSIONAL DE DOCUMENTOS WORD (.DOCX)
**Relatório Final de Auditoria Adversarial e Fidelidade Real de Renderização**
*Data: 2026-10-15 | Pipeline: Document Engine v2 & Real Office Rendering Fidelity*

---

## 1. Defeitos Comprovados e Respetivas Causas

Durante a auditoria adversarial aprofundada, foram identificadas e comprovadas as seguintes anomalias de raiz:

1. **Falha Silenciosa na Invocação de Microsoft Word COM via PowerShell**:
   - *Causa*: O script de automação Word COM continha variáveis PowerShell (`$word`, `$doc`, `$toc`) passadas diretamente numa string de linha de comando inline (`powershell.exe -Command "..."`). Na expansão inicial pelo interpretador de comandos do Windows, as variáveis eram suprimidas ou avaliadas prematuramente no contexto externo, falhando silenciosamente e acionando o fallback não planeado para o sintetizador `PyMuPDF`.
   - *Correção*: Criação do mecanismo `RenderEngineManager` com geração e execução de scripts `.ps1` isolados e temporários, invocados com política explícita (`-NoProfile -ExecutionPolicy Bypass -File <script>`). O Microsoft Word COM 16.0 (`Word.Application`) passou a responder e a renderizar com 100% de fiabilidade.

2. **Falsa Fidelidade Visual e Pontuação Perfeita em Renderização Sintética**:
   - *Causa*: O validador anterior aceitava um PDF sintético produzido via PyMuPDF e concedia conformidade visual com pontuação de 100/100, mesmo quando o motor de paginação do Microsoft Word nunca tinha sido executado.
   - *Correção*: Implementação da distinção inequívoca entre `REAL_OFFICE_RENDER`, `SYNTHETIC_RENDER` e `RENDER_UNAVAILABLE`. O validador agora proíbe categoricamente `visual_acceptance_validated = True` quando o motor utilizado for sintético, limitando a pontuação a um teto máximo de 60.0/100.

3. **Tentativa de Pré-computação de Offsets no Índice (TOC)**:
   - *Causa*: A intenção anterior de pré-calcular posições verticais na AST e estampar números de página estáticos no XML do Word violava o princípio de fidelidade, pois o layout de fontes, kerning e paginação do Word diverge do layout do PyMuPDF.
   - *Correção*: O campo TOC foi mantido na sua forma nativa OpenXML (`w:fldChar` com instrução `TOC \o "1-3" \h \z \u`). Quando o motor Office real está ativo, o Word executa `$doc.Fields.Update()` e `$doc.TablesOfContents.Update()`, calculando e salvando a paginação autêntica. Quando ausente, o campo permanece dinâmico sem fabricação de números de página artificiais.

4. **Auditoria Superficial de Preservação em Revisões**:
   - *Causa*: Apenas a contagem bruta de imagens e tabelas era comparada, sem verificação de células unidas (`gridSpan`/`vMerge`), fórmulas matemáticas OMML (`m:oMath`), desenhos ancorados (`wp:anchor`) ou integridade binária dos ficheiros de media.
   - *Correção*: Implementação do `OpenXMLPreservationAuditor` em `surgical_revisor.py`, que audita o arquivo `.docx` (ZIP), calcula e compara hashes SHA-256 byte-a-byte de `word/media/*` e verifica a retenção de todos os elementos complexos OpenXML.

5. **Deteção Lexical Simplista de Alucinações / Afirmações Sem Suporte**:
   - *Causa*: Apenas expressões regulares procuravam percentagens soltas sem relacionar as afirmações com as fontes fornecidas.
   - *Correção*: Implementação do `ClaimGroundingAuditor` em `editorial_planner.py`, com categorização rigorosa de asserções em `EXPLICITLY_SUPPORTED`, `INFERENCE`, `UNSUPPORTED` e `REQUIRES_CONFIRMATION`.

---

## 2. Motor de Renderização Efetivamente Utilizado em Cada Teste

| Cenário de Teste | Motor Efetivamente Utilizado | Versão / Configuração | Origem do PDF |
|---|---|---|---|
| `test_scenario_01..08` | N/A (Testes estruturais e editoriais da AST) | python-docx 1.2.0 | N/A |
| `test_scenario_09` | Microsoft Word COM Automation | Word 16.0 (wdFormatPDF = 17) | Conversão Real Word COM |
| `test_scenario_10` | Microsoft Word COM Automation | Word 16.0 (Deteção de BLANK_PAGE) | Conversão Real Word COM |
| `test_scenario_11..12` | N/A (Diff unificado e Exportação) | Hash SHA-256 criptográfico | N/A |
| `test_adversarial_01` | N/A (Criação e reabertura AST) | AST Parser OpenXML | N/A |
| `test_adversarial_02` | Microsoft Word COM Automation | Word 16.0 (`REAL_OFFICE_RENDER`) | Conversão Real Word COM |
| `test_adversarial_03` | PyMuPDF Synthetic Layout Synthesizer | PyMuPDF 1.28.2 (`SYNTHETIC_RENDER`) | Sintetizador AST com marca de água |
| `test_adversarial_04` | Microsoft Word COM Automation | Word 16.0 (`$doc.TablesOfContents.Update()`) | Conversão Real Word COM |
| `test_adversarial_05` | Microsoft Word COM Automation | Word 16.0 (Correspondência de Páginas) | Conversão Real Word COM |
| `test_adversarial_06` | N/A (Auditoria de Células Unidas) | `OpenXMLPreservationAuditor` | N/A |
| `test_adversarial_07` | N/A (Auditoria de Hashes de Media) | Verificação SHA-256 ZIP | N/A |
| `test_adversarial_08` | N/A (Auditoria de Equações OMML) | Verificação XML `m:oMath` | N/A |
| `test_adversarial_09` | Microsoft Word COM Automation | Word 16.0 (Deteção de Defeito Real) | Conversão Real Word COM |
| `test_adversarial_10` | Falha Controlada (`require_real_office`) | Exceção `RuntimeError` | N/A |
| `test_adversarial_11` | PyMuPDF Synthetic Layout Synthesizer | Rejeição de Aceitação Visual | Sintetizador AST |
| `test_adversarial_12` | Microsoft Word COM Automation | Word 16.0 (Trilha de Auditoria Integral) | Conversão Real Word COM |

---

## 3. Ficheiros Efetivamente Alterados / Criados

1. **[`backend/document_engine/render_engine.py`](file:///c:/Users/joaor/Desktop/JarvisOS/backend/document_engine/render_engine.py)** *(Novo)*:
   - Abstração formal do motor de renderização com enum `RenderEngineType`: `REAL_OFFICE_RENDER`, `SYNTHETIC_RENDER`, `RENDER_UNAVAILABLE`.
   - `RenderEngineManager`: deteção de motores, execução de scripts PowerShell isolados, atualização real de campos e TOC via COM, e fallback sintético rastreado com marca de água visível.
2. **[`backend/document_engine/visual_inspector.py`](file:///c:/Users/joaor/Desktop/JarvisOS/backend/document_engine/visual_inspector.py)** *(Atualizado)*:
   - Vinculação estrita ao `RenderResult`. Registo de `is_real_office`, `engine_name` e `render_engine_type`.
   - Regra absoluta: `visual_fidelity_verified = False` sempre que a renderização for sintética.
3. **[`backend/document_engine/surgical_revisor.py`](file:///c:/Users/joaor/Desktop/JarvisOS/backend/document_engine/surgical_revisor.py)** *(Atualizado)*:
   - Implementação de `OpenXMLPreservationAuditor` e `PreservationAuditResult`.
   - Verificação byte-a-byte de hashes SHA-256 de todas as imagens em `word/media/*`.
   - Verificação de células unidas (`gridSpan`, `vMerge`), equações OMML (`m:oMath`), desenhos ancorados/em linha e partes de cabeçalho/rodapé.
4. **[`backend/document_engine/editorial_planner.py`](file:///c:/Users/joaor/Desktop/JarvisOS/backend/document_engine/editorial_planner.py)** *(Atualizado)*:
   - Implementação de `ClaimGroundingAuditor`, `GroundedClaim` e enum `ClaimGroundingStatus` (`EXPLICITLY_SUPPORTED`, `INFERENCE`, `UNSUPPORTED`, `REQUIRES_CONFIRMATION`).
   - Mapeamento contextual de evidências e ligação entre afirmações do documento e fontes fornecidas.
5. **[`backend/document_engine/word_engine.py`](file:///c:/Users/joaor/Desktop/JarvisOS/backend/document_engine/word_engine.py)** *(Atualizado)*:
   - Separação formal dos portões de aceitação (`AcceptanceGates`): `structure_validated`, `editorial_validated`, `docx_integrity_validated`, `real_render_validated`, `visual_acceptance_validated`.
   - Teto de pontuação de 60.0/100 caso `real_render_validated == False`.
   - Parâmetros `prefer_real_office`, `update_fields` e `require_real_office` propagados.
6. **[`tests/test_word_document_engine.py`](file:///c:/Users/joaor/Desktop/JarvisOS/tests/test_word_document_engine.py)** *(Atualizado)*:
   - Expansão de 13 para 25 testes cobrindo os 12 cenários adversariais exigidos.

---

## 4. Resultados dos Testes Anteriores e Novos

Executado em ambiente Windows com Python 3.14.7 e pytest 9.1.1:

```
tests/test_word_document_engine.py::test_scenario_01_create_document_from_scratch PASSED [  4%]
tests/test_word_document_engine.py::test_scenario_02_read_document_ast PASSED [  8%]
tests/test_word_document_engine.py::test_scenario_03_preserve_section_hierarchy PASSED [ 12%]
tests/test_word_document_engine.py::test_scenario_04_revise_without_losing_untargeted_content PASSED [ 16%]
tests/test_word_document_engine.py::test_scenario_05_preserve_images_and_tables_during_revision PASSED [ 20%]
tests/test_word_document_engine.py::test_scenario_06_maintain_styles_and_numbering PASSED [ 24%]
tests/test_word_document_engine.py::test_scenario_07_follow_provided_template PASSED [ 28%]
tests/test_word_document_engine.py::test_scenario_08_detect_unsupported_claims_and_hallucinations PASSED [ 32%]
tests/test_word_document_engine.py::test_scenario_09_render_document_to_pdf_and_images PASSED [ 36%]
tests/test_word_document_engine.py::test_scenario_10_detect_pagination_flaws PASSED [ 40%]
tests/test_word_document_engine.py::test_scenario_11_version_comparison_and_diff PASSED [ 44%]
tests/test_word_document_engine.py::test_scenario_12_export_document_with_sha256 PASSED [ 48%]
tests/test_word_document_engine.py::test_comprehensive_validation_pipeline PASSED [ 52%]
tests/test_word_document_engine.py::test_adversarial_01_create_and_reopen_docx PASSED [ 56%]
tests/test_word_document_engine.py::test_adversarial_02_render_via_real_available_engine PASSED [ 60%]
tests/test_word_document_engine.py::test_adversarial_03_synthetic_render_identification PASSED [ 64%]
tests/test_word_document_engine.py::test_adversarial_04_toc_and_fields_update PASSED [ 68%]
tests/test_word_document_engine.py::test_adversarial_05_page_numbers_correspondence PASSED [ 72%]
tests/test_word_document_engine.py::test_adversarial_06_preservation_of_untargeted_elements PASSED [ 76%]
tests/test_word_document_engine.py::test_adversarial_07_media_sha256_integrity PASSED [ 80%]
tests/test_word_document_engine.py::test_adversarial_08_omml_equations_preservation PASSED [ 84%]
tests/test_word_document_engine.py::test_adversarial_09_real_pagination_defect_detection PASSED [ 88%]
tests/test_word_document_engine.py::test_adversarial_10_controlled_failure_when_real_office_required PASSED [ 92%]
tests/test_word_document_engine.py::test_adversarial_11_prohibit_visual_acceptance_on_simulation PASSED [ 96%]
tests/test_word_document_engine.py::test_adversarial_12_audit_trail_and_engine_logging PASSED [100%]

============================= 25 passed in 48.91s =============================
```

**Regressões de Governação e Execução**:
- `tests/test_product_delivery_governance.py`: **37 PASSED**
- `tests/test_autonomous_execution_and_overblocking.py`: **15 PASSED**
- `tests/test_chat_mission_bridge.py`: **12 PASSED**
- `tests/test_study_reading_experience.py`: **49 PASSED**
- **Total de Regressões Executadas e Aprovadas**: **138 testes PASSED** (0 falhas).

---

## 5. Fidelidade Real dos Números de Página do Índice

1. **Validação do Índice Nativo**:
   - O campo TOC é inserido como `<w:instrText xml:space="preserve"> TOC \o "1-3" \h \z \u </w:instrText>`.
2. **Atualização pelo Motor Real**:
   - Na renderização via Microsoft Word COM, é executado `$doc.TablesOfContents.Update()` seguido de `$doc.Save()`.
   - O Word calcula as quebras de linha e página reais para cada heading e persiste os números exatos no ficheiro DOCX.
   - O PDF gerado pelo Word reflete exatamente essa paginação (ex: Índice na página 1, Sumário na página 2, etc.).
3. **Comportamento quando o Motor Real Não Está Disponível**:
   - O sistema preserva o campo dinâmico nativo sem adulteração.
   - Não são calculados offsets estimados nem escritos números fictícios no XML.
   - O relatório de validação regista formalmente a limitação: `"TOC dynamic fields preserved without evaluation; real pagination requires Microsoft Word or LibreOffice"`.

---

## 6. Elementos Preservados e Método Usado para Provar a Preservação

| Elemento OpenXML | Método de Verificação Utilizado | Prova Obtida |
|---|---|---|
| **Ficheiros de Imagem / Media** | Extração do arquivo ZIP `.docx` e cálculo de hash SHA-256 pré e pós-revisão | `media_hashes_verified == True` (Hashes idênticos byte-a-byte em `word/media/*`) |
| **Células Unidas de Tabelas** | Contagem de tags XML `<w:gridSpan>` e `<w:vMerge>` no nó `word/document.xml` | `merged_cells_preserved == True` (Contagem mantida intacta) |
| **Equações Matemáticas OMML** | Contagem de tags XML `<m:oMath>` e nós matemáticos | `omml_equations_preserved == True` (Fórmulas conservadas) |
| **Desenhos Ancorados e em Linha** | Inspeção das tags `<wp:anchor>` e `<wp:inline>` | Desenhos e relacionamentos embutidos inalterados |
| **Cabeçalhos e Rodapés com Paginação** | Verificação das partes `word/header*.xml` e `word/footer*.xml` no ZIP | Todas as partes e relações vinculadas persistidas |
| **Hiperligações** | Contagem de elementos `<w:hyperlink>` e identificadores em `_rels` | Hiperligações e URLs de destino preservadas |
| **Secções e Quebras de Página** | Contagem de tags `<w:sectPr>` | Propriedades de secção e margens preservadas |

---

## 7. Resultados da Validação Estrutural e Editorial

A validação agora opera com critérios independentes:
1. **Estrutural (`structure_validated`)**:
   - Verifica conformidade semântica da árvore AST com o perfil (`AcademicProfile`, `TechnicalSpecProfile`, etc.).
   - Rejeita o documento se faltarem secções obrigatórias (ex: Resumo e Metodologia em trabalhos académicos).
2. **Editorial (`editorial_validated`)**:
   - Avaliação por `ClaimGroundingAuditor`:
     - Asserções com métricas e percentagens comprovadas nas fontes: `EXPLICITLY_SUPPORTED`.
     - Deduções analíticas decorrentes do contexto: `INFERENCE`.
     - Dados estatísticos/números sem suporte documental: `UNSUPPORTED` (aciona aviso e penalização de pontuação).
     - Obrigações críticas sem fonte: `REQUIRES_CONFIRMATION`.

---

## 8. Resultados da Renderização e Inspeção Visual

- **Validação com Motor Office Real**:
  - `render_engine_type`: `REAL_OFFICE_RENDER`
  - `engine_name`: `"Microsoft Word COM Automation"`
  - `is_real_office`: `True`
  - `visual_fidelity_verified`: `True`
  - `visual_acceptance_validated`: `True` (desde que 0 falhas graves de paginação sejam detetadas).
  - `quality_score`: Reflete rigorosamente os eixos estrutural, editorial e visual (podendo atingir até 100.0/100).
- **Validação em Modo Sintético (Fallback PyMuPDF)**:
  - `render_engine_type`: `SYNTHETIC_RENDER`
  - `is_real_office`: `False`
  - `visual_fidelity_verified`: `False`
  - `visual_acceptance_validated`: `False` (obrigatoriamente rejeitada).
  - `quality_score`: Teto máximo travado em `60.0/100`.
  - Resumo de Validação: Inclui aviso explícito de simulação limitada sem prova de paginação Word.

---

## 9. Limitações Ainda Existentes

1. **Dependência do Ambiente para Renderização Real**:
   - A obtenção de fidelidade visual 100% autêntica ao Word requer a presença do Microsoft Word (Windows) ou LibreOffice (`soffice`) na máquina de execução.
   - Em servidores Linux sem LibreOffice instalado, o sistema opera em modo de fidelidade estrutural/editorial, gerando visualização sintética limitada com a respetiva advertência.
2. **Controlos de Conteúdo Legados do Word 2003 (w:formField)**:
   - Campos de formulários antigos permanecem íntegros no ficheiro, mas o parser AST interpreta-os como blocos de texto não editáveis.

---

## 10. Primeira Falha Restante e Menor Correção Seguinte

- **Primeira Falha Restante**:
  Em ambientes headless sem interface gráfica onde apenas o LibreOffice estiver disponível (em vez de Word COM), a conversão de campos dinâmicos complexos de cabeçalho pode requerer a diretiva explícita de atualização `--convert-to pdf:writer_pdf_Export` com macro de atualização de campos antes do fecho do documento.
- **Menor Correção Seguinte**:
  Adicionar ao `RenderEngineManager._convert_via_libreoffice` uma chamada complementar com macro básica de atualização de campos (`soffice --headless "vnd.sun.star.script:Standard.Module1.UpdateAll?language=Basic&location=document"`) para assegurar paridade funcional com o Word COM em servidores Linux dedicados.
