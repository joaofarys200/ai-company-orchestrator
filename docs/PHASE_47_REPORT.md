# JARVIS OS — RELATÓRIO DE ENGENHARIA & GOVERNAÇÃO TÉCNICA
## Fase 47: Polymorphic Schema Semantics & Contract Compatibility

---

### 1. OBJETIVO DA FASE 47
A Fase 47 resolve de forma definitiva a primeira limitação real descoberta na Fase 46 (`POLYMORPHIC_DYNAMIC_ENDPOINTS`). Na Fase 46, quando uma rota da API retornava diferentes formatos legítimos em função de parâmetros ou subtipos (ex: eventos de auditoria com payloads distintos ou transações bancárias com estados `SUCCESS`, `REQUIRES_ACTION`, `FAILED`), o motor de governança clássico tendia a interpretar as variações como drift ou conflito estrutural contínuo, gerando alertas espúrios.

O objetivo da Fase 47 **NÃO É ADIVINHAR** qual variante existe através de heurísticas frágeis ou suposições cegas. O objetivo é **representar formalmente a variabilidade do contrato**, separando de forma estrita e matematicamente comprovável:
1. Esquemas de união discriminada vs esquemas simples;
2. Campos comuns universais vs campos específicos de variantes;
3. Variantes determinísticas (com discriminador explícito) vs variantes inferidas estruturalmente;
4. Casos ambíguos mantidos como `UNCERTAIN` conforme a **Regra 28**;
5. Matriz de compatibilidade entre versões de esquemas polimórficos ($Old\ vs\ New$);
6. Impacto diferencial em consumidores baseado na sua postura real de tolerância.

---

### 2. PRINCÍPIO FUNDAMENTAL E INVARIANTES FORMAIS

#### 2.1 Invariante Fundamental: $\text{VARIANT} \neq \text{CONTRACT}$
Nenhuma variante observada em runtime é promovida a contrato universal sem evidência formal e validação. A observação de um payload novo representa unicamente uma **amostra factual**, que é categorizada no estado `PROPOSED` ou `INFERRED` até que passe pela malha de segurança e revisão humana.

#### 2.2 Separação Tri-State / Quad-State de Esquemas
O sistema rejeita categoricamente reducionismos binários. Todo endpoint é classificado em:
$$\text{SINGLE\_SCHEMA} \neq \text{UNION\_SCHEMA} \neq \text{DISCRIMINATED\_UNION} \neq \text{UNKNOWN\_POLYMORPHIC\_RESPONSE}$$

- **`SINGLE_SCHEMA`**: Contrato monomórfico clássico com forma única.
- **`DISCRIMINATED_UNION`**: União onde um campo explícito (ex: `type`, `kind`, `status`, header) atua como chave de partição determinística.
- **`UNION_SCHEMA`**: União não-discriminada onde formas disjuntas e estruturalmente distintas coexistem.
- **`UNKNOWN_POLYMORPHIC_RESPONSE`**: Respostas variáveis cuja relação estrutural não pôde ser decidida com 100% de certeza.

#### 2.3 Ciclo de Vida Epistémico dos Statuses
Cada variante transita por estados bem definidos:
$$\text{PROPOSED} \longrightarrow \text{INFERRED} \longrightarrow \text{VALIDATED} \quad \text{ou} \quad \text{UNCERTAIN}$$
- `DETERMINISTIC`: Provado por discriminador explícito ou tipagem estática do compilador.
- `INFERRED`: Agrupado por semelhança estrutural estrita com confiança acima do limiar.
- `PROPOSED`: Proposta gerada pelo runtime discovery aguardando revisão.
- `VALIDATED`: Aprovado formalmente por assinatura de operador humano ou contrato canónico.
- `UNCERTAIN`: Casos com sobreposição de conjuntos de campos sem discriminador inequívoco.

#### 2.4 Regra 28 — Invariante de Ambiguidade Estrutural
Se para duas observações $A$ e $B$ os conjuntos de chaves $K(A)$ e $K(B)$ mantêm relação de subconjunto estrito:
$$K(A) \subset K(B) \quad \text{e} \quad K(A) \setminus K(B) = \emptyset$$
sem a presença de uma chave discriminadora explícita, o sistema **NUNCA CHUTA** que $B$ é uma nova variante polimórfica. A ausência de chaves exclusivas em $A$ torna indistinguível se $K(B) \setminus K(A)$ são campos opcionais ou uma variante polimórfica. O veredicto do discriminador é `(None, is_ambiguous=True)` e o esquema permanece categorizado como `UNKNOWN_POLYMORPHIC_RESPONSE` com status `UNCERTAIN`.

---

### 3. ARQUITETURA DO SISTEMA (`agents/polymorphic_schema/`)

O módulo foi implementado em Python 3.12 com tipagem estrita, imutabilidade em dataclasses críticas e zero dependências circulares:

```
agents/polymorphic_schema/
├── __init__.py           # Exportação canónica das classes e enums
├── models.py             # Modelos de dados, enums e contratos de domínio
├── discriminator.py      # Motor de resolução de discriminadores (explícitos e estruturais)
├── detector.py           # Agrupamento de observações e inferência de uniões
├── compatibility.py      # Matriz de compatibilidade par-a-par e Old vs New
├── diff.py               # Motor de diff semântico e deteção de drift polimórfico
├── consumers.py          # Análise de impacto reverso em consumidores registados
├── security.py           # Sentinela de segurança (injeções, validação de assinaturas)
└── bridge.py             # Ponte de governança para os subsistemas das Fases 39 a 46
```

#### 3.1 Modelos e Contratos (`models.py`)
- **`DiscriminatorDefinition`**: Define campo, localização (`BODY`, `HEADER`, `QUERY`), tipo (`STRING_ENUM`, `INFERRED_STRUCTURAL`, etc.), valores observados e confiança.
- **`SchemaVariant`**: Encapsula identificador, discriminador, contagem de observações, campos obrigatórios, opcionais e proibidos (`forbidden_fields`).
- **`PolymorphicSchema`**: Agrupa variantes sob uma rota/método, campos comuns globais, tipo de esquema e versão semântica.
- **`VariantDiff`**: Modela adições, remoções e alterações de campos obrigatórios, opcionais e proibidos entre variantes.
- **`SchemaCompatibilityMatrix`**: Tabela $N \times M$ avaliando compatibilidade para produtores e consumidores.
- **`ConsumerVariantImpact`**: Mapeia a postura de cada consumidor (`ALREADY_TOLERATES`, `IGNORES`, `POTENTIALLY_BREAKING`, `UNCERTAIN`).
- **`PolymorphicDriftReport`**: Relatório causal detalhado distinguindo evolução polimórfica de drift destrutivo.

---

### 4. DISCRIMINADORES EXPLÍCITOS VS INFERIDOS

O motor `DiscriminatorEngine` executa resolução em duas camadas:

1. **Camada Determinística**:
   Busca campos canónicos no payload (`type`, `kind`, `event_type`, `status`, `action`, `operation`) ou headers específicos. Se o campo existe em 100% dos payloads e particiona univocamente as observações sem colisões, é gerado um `DiscriminatorDefinition` com `is_explicit=True` e confiança $1.0$.

2. **Camada Estrutural Inferida**:
   Na ausência de discriminador explícito, analisa a presença e ausência diferencial de campos (`FIELD_PRESENCE`). Se um grupo $A$ possui chaves exclusivas $E_A$ e um grupo $B$ possui chaves exclusivas $E_B$ tais que:
   $$E_A \neq \emptyset \quad \land \quad E_B \neq \emptyset \quad \land \quad E_A \cap E_B = \emptyset$$
   o motor infere que a presença de $E_B$ funciona como discriminador estrutural, emitindo um `DiscriminatorDefinition` com `type=INFERRED_STRUCTURAL` e confiança balanceada.

---

### 5. REQUIREDNESS, FORBIDDENNESS E NULLABILITY POR VARIANTE

A governança polimórfica estabelece que um campo pode ser:
1. **Comum e Obrigatório em Todas as Variantes**: Pertence a `common_fields`.
2. **Obrigatório Apenas na Variante $V_k$**: Presente em `variant.required_fields`.
3. **Opcional na Variante $V_k$**: Presente em `variant.optional_fields`.
4. **Proibido na Variante $V_k$ (`forbidden_fields`)**: Um campo que é estritamente proibido de aparecer na variante $V_k$ (ex: `deletion_reason` não pode constar num evento `UserCreated`). A presença de um campo proibido invalida o payload mesmo que o restante esteja conforme.
5. **Nullable**: Especificado na assinatura do tipo da propriedade.

---

### 6. MATRIZ DE COMPATIBILIDADE DE VARIANTES ($Old\ vs\ New$)

O `PolymorphicCompatibilityEngine` avalia a evolução de um esquema polimórfico entre versões através das seguintes regras:

| Alteração Estrutural | Veredicto | Justificação Causal Formal |
|---|---|---|
| Adição de Variante a União Aberta | `COMPATIBLE` / `NON_BREAKING` | Produtor gera novo subtipo; consumidores resilientes continuam processando campos comuns. |
| Adição de Variante com Consumidor Exaustivo | `POTENTIALLY_BREAKING` | Consumidores com pattern-matching rígido falham no caso não coberto. |
| Remoção de Variante | `BREAKING` / `INCOMPATIBLE` | Consumidores que esperavam o subtipo removido entram em falha ou timeout. |
| Alteração de Discriminador | `BREAKING` / `INCOMPATIBLE` | Roteamento quebra globalmente para todos os consumidores. |
| Adição de Campo Obrigatório à Variante | `BREAKING` (para clientes) | Clientes legados não fornecem o novo campo obrigatório. |
| Remoção de Campo Obrigatório da Variante | `BREAKING` (para consumidores) | Consumidores que liam o campo recebem `null` ou `KeyError`. |

---

### 7. INTEGRAÇÃO COM SUBSISTEMAS EXISTENTES

1. **Cross-Language Semantic Graph (Fase 44)**:
   Mapeia equivalências de união tipada:
   - TypeScript: `type AuditEvent = UserCreated | UserUpdated | UserDeleted | UserArchived;`
   - Python: `AuditEvent = Union[UserCreatedModel, UserUpdatedModel, UserDeletedModel, UserArchivedModel]`
   - Rust: `enum AuditEvent { UserCreated(..), UserUpdated(..), .. }`
   Validando equivalência semântica bidirecional.

2. **Continuous Contract Governance (Fase 46)**:
   O `PolymorphicGovernanceBridge` intercepta desvios observados. Se um payload desconhecido contém um valor de discriminador já previsto ou deriva de uma união conhecida, é classificado como `VARIANT_ADDED` ao invés de `BREAKING_DRIFT`, prevenindo falsos positivos de quebra de contrato.

3. **Predictive Impact (Fase 39) & Task Reconciliation (Fase 39.2)**:
   Quando uma variante com veredicto `POTENTIALLY_BREAKING` é adicionada, o sistema calcula o blast radius exato e gera tarefas de reconciliação para os consumidores afetados (ex: `crm-sync-worker`).

4. **Experience Memory (Fases 42/43)**:
   Decisões passadas de classificação de uniões e aprovações humanas são indexadas na memória semântica, acelerando classificações futuras com base em padrões consolidados.

---

### 8. SEGURANÇA E PROTEÇÃO CONTRA INJEÇÃO (`PolymorphicSecuritySentinel`)

1. **Proteção contra Injeção de Prompt**:
   Filtra padrões maliciosos como `ignore previous instructions`, `system prompt override` e tentativas de coerção semântica em nomes de variantes, descrições e payloads.
2. **Proteção contra Injeção de Shell / Comandos**:
   Deteta e bloqueia sintaxes como `$(...)`, `` `...` ``, `; rm -rf`, `&& cat /etc/passwd` em identificadores de variante e metadados.
3. **Validação de Assinatura Humana**:
   Aprovações de variantes exigem assinatura criptográfica válida (`VALID_OPERATOR_SIGNATURE_2026`). Assinaturas forjadas são bloqueadas e registradas na auditoria.

---

### 9. BENCHMARK DE PERFORMANCE E TESTES DE CARGA

Executado via `scripts/run_phase47_polymorphic_schema_benchmark.py`:

```
================================================================================
JARVIS OS - PHASE 47 BENCHMARK: POLYMORPHIC SCHEMA & COMPATIBILITY
================================================================================
[BENCHMARK 1] Scaling Variant Count:
  - 10 variants:      0.32 ms
  - 100 variants:     1.32 ms
  - 1,000 variants:  12.40 ms  (Target: < 100ms -> PASSED)

[BENCHMARK 2] Observation Ingestion (10,000 observations):
  - Cold Detection:  6.86 ms  (Target: < 50ms -> PASSED)
  - Warm Resolution: 19.03 ms  (Target: < 50ms -> PASSED)
  - Incremental Add:  0.0058 ms (Target: < 1ms -> PASSED, Blast Radius: 1)

[BENCHMARK 3] Graph Propagation:
  - Traversal Latency: 0.08 ms (Target: < 20ms -> PASSED)
================================================================================
ALL BENCHMARKS PASSED!
```

---

### 10. SUÍTE DE TESTES AUTOMATIZADOS (PYTEST)

Todos os 9 arquivos de teste dedicados à Fase 47 foram executados com 100% de sucesso:

| Ficheiro de Teste | Cenários Cobertos | Resultado | Tempo |
|---|---|---|---|
| `tests/test_polymorphic_schema.py` | Modelos de dados, criação e invariantes | 4 Passed | 0.04s |
| `tests/test_discriminator.py` | Discriminadores explícitos, por campo e ambiguidade | 5 Passed | 0.05s |
| `tests/test_variant_detection.py` | Agrupamento de variantes, campos comuns e proibidos | 4 Passed | 0.04s |
| `tests/test_union_compatibility.py` | Matriz de compatibilidade par-a-par e Old vs New | 5 Passed | 0.05s |
| `tests/test_polymorphic_diff.py` | Diff estrutural entre variantes e classificações | 4 Passed | 0.04s |
| `tests/test_polymorphic_drift.py` | Deteção de drift polimórfico vs drift de quebra | 2 Passed | 0.03s |
| `tests/test_polymorphic_consumers.py` | Análise de impacto e posturas de consumidores | 3 Passed | 0.03s |
| `tests/test_polymorphic_security.py` | Bloqueio de injeções de prompt e comandos | 4 Passed | 0.04s |
| `tests/test_polymorphic_incremental.py` | Ingestão incremental com raio de impacto isolado | 1 Passed | 0.02s |
| **Total Fase 47** | **Todas as 32 asserções críticas** | **32 Passed** | **0.34s** |

#### Testes de Regressão (Fases 44, 45, 46)
- `tests/test_contract_drift.py` + `tests/test_drift_*.py` + `tests/test_contract_*.py` + `tests/test_semantic_graph.py`:
- **26 Passed, 0 Failed** em 0.47s.

---

### 11. BROWSER QA EM MICROSOFT EDGE OFICIAL (15 CENÁRIOS)

Executado pelo script `scripts/run_browser_qa_phase47.py` com o binário oficial `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`:
- **Scenarios Validated**: 15 / 15
- **Screenshots Taken**: 15 (armazenados em `docs/screenshots/phase47/` e copiados para o diretório de artefatos)
- **Console Errors**: **0**
- **Network Errors**: **0**
- **Ficheiro de Evidência**: `docs/phase47_browser_qa.json`

| ID | Cenário | Imagem | Descrição da Evidência |
|---|---|---|---|
| 01 | Polymorphic Overview | `phase47_01_polymorphic_contract_overview.png` | Painel com métricas de variantes e alerta da invariante formal `VARIANT != CONTRACT`. |
| 02 | Explicit Discriminator | `phase47_02_explicit_discriminator.png` | Card do discriminador `type` no BODY com 100% de confiança e partição estrita. |
| 03 | Inferred Variant | `phase47_03_inferred_variant.png` | Card de discriminador inferido estrutural por presença de campos sem promoção cega. |
| 04 | Ambiguous Variant | `phase47_04_ambiguous_variant.png` | Banner de alerta da Regra 28: sobreposição de campos mantida estritamente como `UNCERTAIN`. |
| 05 | Variant Requiredness | `phase47_05_variant_specific_requiredness.png` | Tabela matricial detalhando campos obrigatórios, opcionais e proibidos por variante. |
| 06 | Variant Diff | `phase47_06_variant_diff.png` | Visualizador de diff semântico entre variantes `UserCreated` vs `UserArchived`. |
| 07 | Variant Addition | `phase47_07_variant_addition.png` | Variante proposta em runtime (`UserArchived`) com discriminador `user.archived`. |
| 08 | Variant Removal Check | `phase47_08_variant_removal.png` | Matriz $Old\ vs\ New$ indicando incompatibilidade formal na remoção ou troca de variantes. |
| 09 | Consumer Impact | `phase47_09_consumer_impact.png` | Mapeamento de consumidores e postura individual (`ALREADY_TOLERATES`, `POTENTIALLY_BREAKING`). |
| 10 | Cross-Language Union | `phase47_10_cross_language_union.png` | Equivalência tipada de união semântica entre TypeScript, Python e Rust. |
| 11 | Runtime Discovery | `phase47_11_runtime_discovery.png` | Descoberta em tempo de execução da união discriminada de `/api/v2/payments/checkout`. |
| 12 | Human Approval | `phase47_12_human_approval.png` | Ação de validação por operador humano com feedback de sucesso e promoção a `VALIDATED`. |
| 13 | Breaking Variant Change | `phase47_13_breaking_variant_change.png` | Alerta de quebra potencial para `crm-sync-worker` com plano de mitigação gerado. |
| 14 | Variant Rollback | `phase47_14_variant_rollback.png` | Rollback determinístico revertendo variante aprovada e restaurando baseline estável. |
| 15 | Why Polymorphic Drift | `phase47_15_why_polymorphic_drift.png` | Painel causal do "Porquê" comprovando que a variação observada é uma variante e não drift. |

---

### 12. PRIMEIRA FALHA REAL E PRIMEIRO LIMITE REAL

#### Primeira Falha Real Identificada
Na primeira tentativa de inferência de discriminador semântico para o endpoint de membros do workspace (`/api/v1/workspace/members`), os payloads do perfil de administrador continham `{member_id, name, email, permissions}` enquanto os perfis normais continham `{member_id, name, email}`.
O motor inicial tentou inferir que `permissions` era um discriminador de variante. No entanto, por se tratar de uma relação estrita de subconjunto sem uma chave mutuamente exclusiva no perfil normal, o sistema falhou ao tentar garantir se `permissions` era uma variante polimórfica ou apenas um campo opcional (`permissions?: string[]`).
**Solução Implementada (Regra 28)**: O motor recusa-se a promover o candidato a variante. Emite `(None, is_ambiguous=True)` e rotula o status como `UNCERTAIN`, solicitando anotação contratual explícita ou evidência humana.

#### Primeiro Limite Real da Fase 47
**`COMPLEX_NESTED_POLYMORPHISM_AND_RECURSIVE_DISCRIMINATORS`**:
Quando o discriminador não reside no topo ou em um caminho estático (`payload.type`), mas sim em nós aninhados de profundidade arbitrária com arrays heterogêneos polimórficos recursivos (ex: ASTs, grafos de expressões booleanas `OR/AND` aninhadas), o custo de partição determinística cresce combinatorialmente. Esse limite fornece a fundação exata para a Fase 48.

---

### 13. DECISION GATE

Com 32 testes unitários passando, 26 testes de regressão íntegros, benchmark de 1.000 variantes em 12.4ms, 15 cenários de Browser QA validados no Microsoft Edge com zero erros de console e zero erros de rede, declaramos:

$$\mathbf{A:\ POLYMORPHIC\_CONTRACT\_GOVERNANCE\_READY}$$
