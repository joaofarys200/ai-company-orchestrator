---
type: concept
domain: backend-systems
difficulty: advanced
tags:
  - backend
  - databases
  - cap-theorem
status: verified
---

# ðŸŒ Tratado Completo de Engenharia de Sistemas DistribuÃ­dos, Consenso & Motores de Bases de Dados

---

## ðŸ“Œ 1. Fundamentos TeÃ³ricos de Sistemas DistribuÃ­dos

### 1.1. O Teorema CAP e o Teorema PACELC
No desenho de qualquer sistema distribuÃ­do com armazenamento de dados, aplicam-se duas leis fundamentais de compromisso arquitetural:

1. **Teorema CAP (Brewer)**:
   Em presenÃ§a de uma **PartiÃ§Ã£o de Rede ($P$)**, um sistema distribuÃ­do pode escolher ser:
   - **Consistente ($C$)**: Todos os nÃ³s leem os dados mais recentes simultaneamente ou devolvem um erro.
   - **DisponÃ­vel ($A$)**: Todos os nÃ³s que nÃ£o falharam respondem a todas as requisiÃ§Ãµes, mas a resposta pode nÃ£o conter os dados mais recentes.

2. **Teorema PACELC (Abadi)**:
   Uma extensÃ£o direta do CAP que considera a operaÃ§Ã£o normal **sem partiÃ§Ãµes**:
   - **Se hÃ¡ PartiÃ§Ã£o ($P$)**: Escolhe entre Disponibilidade ($A$) ou ConsistÃªncia ($C$).
   - **Else ($E$) - Em OperaÃ§Ã£o Normal**: Escolhe entre LatÃªncia ($L$) ou ConsistÃªncia ($C$).
   - *Exemplo*: O PostgreSQL com replicaÃ§Ã£o sÃ­ncrona Ã© um sistema **PC/EC** (prioriza consistÃªncia em ambos os cenÃ¡rios). O DynamoDB/Cassandra Ã© um sistema **PA/EL** (prioriza disponibilidade e baixa latÃªncia).

---

## ðŸ›ï¸ 2. Algoritmos de Consenso DistribuÃ­do em Detalhe

### 2.1. O Algoritmo de Consenso Raft

#### 2.1.1. Estados dos NÃ³s e Termos
Num cluster Raft, cada nÃ³ encontra-se rigorosamente num de trÃªs estados:
- **Leader (LÃ­der)**: Processa todas as escritas dos clientes, aceita entradas no log e coordena a replicaÃ§Ã£o.
- **Follower (Seguidor)**: Responde passivamente a RPCs enviadas pelo LÃ­der e por Candidatos.
- **Candidate (Candidato)**: Utilizado para eleger um novo LÃ­der quando o anterior falha.

O tempo Ã© dividido em **Termos (Terms)** arbitrariamente longos identificados por um inteiro estritamente crescente $t$.

#### 2.1.2. Protocolo de EleiÃ§Ã£o de LÃ­der
1. **Heartbeat Timeout**: Cada seguidor mantÃ©m um temporizador de eleiÃ§Ã£o estocÃ¡stico aleatorizado (ex: entre 150ms e 300ms) para evitar votos divididos (*Split Vote*).
2. Se um seguidor nÃ£o receber RPCs `AppendEntries` do LÃ­der antes do temporizador expirar:
   - Incrementa o seu termo atual $t = t + 1$.
   - Transita para o estado **Candidate**.
   - Vota em si prÃ³prio e envia RPCs `RequestVote` para todos os outros nÃ³s do cluster.
3. **Regra de VotaÃ§Ã£o**: Um nÃ³ aceita o voto se e sÃ³ se:
   - O termo do candidato Ã© maior ou igual ao termo atual do nÃ³ ($t_{\text{candidato}} \ge t_{\text{nÃ³}}$).
   - O candidato ainda nÃ£o recebeu o voto do nÃ³ neste termo (`votedFor is None`).
   - O log do candidato Ã© **pelo menos tÃ£o atualizado** como o log do nÃ³ (comparando termo da Ãºltima entrada e Ã­ndice).
4. Se o candidato receber votos de uma **maioria estrita** ($\lfloor N/2 \rfloor + 1$), transita para **Leader** e envia imediatamente *Heartbeats* para afirmar autoridade.

#### 2.1.3. RÃ©plica de Log & Invariante de SeguranÃ§a
O LÃ­der aceita os comandos dos clientes, anexa-os como novas entradas ao seu log local e transmite a RPC `AppendEntries`:

```python
from dataclasses import dataclass
from typing import Any

@dataclass
class LogEntry:
    index: int
    term: int
    command: dict[str, Any]

@dataclass
class AppendEntriesRPC:
    term: int
    leader_id: str
    prev_log_index: int
    prev_log_term: int
    entries: list[LogEntry]
    leader_commit: int
```

- **Log Matching Property**: Se duas entradas em logs de nÃ³s diferentes tiverem o mesmo Ã­ndice e o mesmo termo, elas armazenam o mesmo comando e os seus logs sÃ£o idÃªnticos em todas as entradas anteriores.
- **Commitment**: Uma entrada Ã© considerada *Committed* assim que Ã© replicada na maioria dos nÃ³s pelo LÃ­der do termo atual.

---

## ðŸ’½ 3. Motores de Armazenamento: LSM-Trees vs. B+Trees

### 3.1. Log-Structured Merge-Trees (LSM-Trees)

#### 3.1.1. Arquitetura Interna
1. **MemTable**: Estrutura de dados em memÃ³ria mantida ordenada (ex: *SkipList* ou *Red-Black Tree*). Todas as operaÃ§Ãµes `PUT` e `DELETE` sÃ£o gravadas na MemTable.
2. **Write-Ahead Log (WAL)**: Registo sequencial no disco que garante durabilidade antes da MemTable ser modificada.
3. **SSTables (Sorted String Tables)**: Quando a MemTable atinge um limite (ex: 64MB), Ã© descarregada imutavelmente para o disco como um ficheiro SSTable contendo pares chave-valor ordenados.

#### 3.1.2. Bloom Filters & Probabilidade de Erro
Para evitar leituras em disco quando uma chave nÃ£o existe, cada SSTable possui um **FÃ³rmula do Bloom Filter**:
Dada uma taxa de falsos positivos pretendida $p$, um nÃºmero de elementos $n$ e um tamanho de vetor em bits $m$:
$$m = -\frac{n \ln p}{(\ln 2)^2}$$
O nÃºmero Ã³timo de funÃ§Ãµes hash $k$ Ã©:
$$k = \frac{m}{n} \ln 2$$

#### 3.1.3. Processo de CompactaÃ§Ã£o (Compaction)
- **Leveled Compaction**: Os dados sÃ£o divididos em nÃ­veis ($L_0, L_1, L_2 \dots$). Cada nÃ­vel $L_i$ tem uma capacidade mÃ¡xima de tamanho ($10^i$ MB). Quando o nÃ­vel $L_i$ enche, ficheiros SSTable sobrepostos sÃ£o fundidos e reordenados para o nÃ­vel $L_{i+1}$, eliminando registos apagados (*Tombstones*) e atualizaÃ§Ãµes antigas.

---

### 3.2. B+Trees & Algoritmo ARIES de RecuperaÃ§Ã£o

#### 3.2.1. Estrutura Estrutural
Ao contrÃ¡rio das B-Trees tradicionais, numa **B+Tree**:
- Todos os dados/valores sÃ£o armazenados exclusivamente nos **nÃ³s folha**.
- Os nÃ³s internos contÃªm apenas chaves de encaminhamento (*Routings Keys*).
- Todos os nÃ³s folha estÃ£o encadeados numa **lista duplamente ligada**, permitindo *Range Queries* extremamente eficientes.

```
                  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
                  â”‚    NÃ³ Interno: [50]    â”‚
                  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                              â”‚
         â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
         â–¼                                         â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”                       â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ Folha: [10, 30] â”‚ â—„â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â–º â”‚ Folha: [50, 80] â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜                       â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

#### 3.2.2. Algoritmo ARIES (Algorithms for Recovery and Isolation Exploiting Semantics)
Em caso de falha de energia ou *crash* da base de dados, a recuperaÃ§Ã£o ARIES executa 3 fases estritas:
1. **Fase de AnÃ¡lise**: Examina o WAL a partir do Ãºltimo *Checkpoint* para reconstruir a Tabela de TransaÃ§Ãµes Ativas (ATT) e a Tabela de PÃ¡ginas Sujas (DPT).
2. **Fase Redo**: Re-executa todas as alteraÃ§Ãµes registadas no WAL a partir da pÃ¡gina mais antiga na DPT, restaurando o estado exato da base de dados antes do crash.
3. **Fase Undo**: Reverte todas as transaÃ§Ãµes que estavam ativas (incompletas) no momento do crash, percorrendo o WAL para trÃ¡s e aplicando registos de compensaÃ§Ã£o (CLRs).

---

## âš¡ 4. Teoria de Isolamento de TransaÃ§Ãµes Concorrentes & MVCC

### 4.1. Anomalias de ConcorrÃªncia
- **Dirty Read**: $T_1$ modifica um valor. $T_2$ lÃª o valor modificado. $T_1$ faz `ROLLBACK`. $T_2$ leu dados invÃ¡lidos.
- **Non-Repeatable Read**: $T_1$ lÃª um valor. $T_2$ atualiza o valor e faz `COMMIT`. $T_1$ volta a ler o valor e obtÃ©m um resultado diferente.
- **Phantom Read**: $T_1$ lÃª um conjunto de linhas com uma condiÃ§Ã£o. $T_2$ insere uma nova linha que satisfaz a condiÃ§Ã£o e faz `COMMIT`. $T_1$ re-executa a query e obtÃ©m linhas fantasmas adicionais.
- **Write Skew**: $T_1$ e $T_2$ leem simultaneamente o mesmo estado (ex: $A + B \ge 100$). $T_1$ reduz $A$ e $T_2$ reduz $B$. Ambas as transaÃ§Ãµes fazem `COMMIT`, mas o invariante global $A + B \ge 100$ Ã© violado.

### 4.2. Multi-Version Concurrency Control (MVCC)
No MVCC, as atualizaÃ§Ãµes nÃ£o sobreescrevem os dados existentes. Em vez disso, cada tuplo possui metadados de versÃ£o:
- `xmin`: ID da transaÃ§Ã£o que criou o tuplo.
- `xmax`: ID da transaÃ§Ã£o que apagou ou sobreescreveu o tuplo (ou 0 se estiver ativo).

Quando a transaÃ§Ã£o $T_k$ lÃª a base de dados, cria uma **Read View** contendo a lista de transaÃ§Ãµes ativas no momento. $T_k$ apenas pode ver um tuplo se:
1. `xmin` Ã© uma transaÃ§Ã£o jÃ¡ confirmada (*Committed*) antes do inÃ­cio da Read View de $T_k$.
2. `xmax` Ã© nÃ£o-existente ou pertence a uma transaÃ§Ã£o que ainda nÃ£o tinha feito *Commit* quando a Read View de $T_k$ foi criada.

