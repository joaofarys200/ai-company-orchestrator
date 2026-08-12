# 🌐 Tratado Completo de Engenharia de Sistemas Distribuídos, Consenso & Motores de Bases de Dados

---

## 📌 1. Fundamentos Teóricos de Sistemas Distribuídos

### 1.1. O Teorema CAP e o Teorema PACELC
No desenho de qualquer sistema distribuído com armazenamento de dados, aplicam-se duas leis fundamentais de compromisso arquitetural:

1. **Teorema CAP (Brewer)**:
   Em presença de uma **Partição de Rede ($P$)**, um sistema distribuído pode escolher ser:
   - **Consistente ($C$)**: Todos os nós leem os dados mais recentes simultaneamente ou devolvem um erro.
   - **Disponível ($A$)**: Todos os nós que não falharam respondem a todas as requisições, mas a resposta pode não conter os dados mais recentes.

2. **Teorema PACELC (Abadi)**:
   Uma extensão direta do CAP que considera a operação normal **sem partições**:
   - **Se há Partição ($P$)**: Escolhe entre Disponibilidade ($A$) ou Consistência ($C$).
   - **Else ($E$) - Em Operação Normal**: Escolhe entre Latência ($L$) ou Consistência ($C$).
   - *Exemplo*: O PostgreSQL com replicação síncrona é um sistema **PC/EC** (prioriza consistência em ambos os cenários). O DynamoDB/Cassandra é um sistema **PA/EL** (prioriza disponibilidade e baixa latência).

---

## 🏛️ 2. Algoritmos de Consenso Distribuído em Detalhe

### 2.1. O Algoritmo de Consenso Raft

#### 2.1.1. Estados dos Nós e Termos
Num cluster Raft, cada nó encontra-se rigorosamente num de três estados:
- **Leader (Líder)**: Processa todas as escritas dos clientes, aceita entradas no log e coordena a replicação.
- **Follower (Seguidor)**: Responde passivamente a RPCs enviadas pelo Líder e por Candidatos.
- **Candidate (Candidato)**: Utilizado para eleger um novo Líder quando o anterior falha.

O tempo é dividido em **Termos (Terms)** arbitrariamente longos identificados por um inteiro estritamente crescente $t$.

#### 2.1.2. Protocolo de Eleição de Líder
1. **Heartbeat Timeout**: Cada seguidor mantém um temporizador de eleição estocástico aleatorizado (ex: entre 150ms e 300ms) para evitar votos divididos (*Split Vote*).
2. Se um seguidor não receber RPCs `AppendEntries` do Líder antes do temporizador expirar:
   - Incrementa o seu termo atual $t = t + 1$.
   - Transita para o estado **Candidate**.
   - Vota em si próprio e envia RPCs `RequestVote` para todos os outros nós do cluster.
3. **Regra de Votação**: Um nó aceita o voto se e só se:
   - O termo do candidato é maior ou igual ao termo atual do nó ($t_{\text{candidato}} \ge t_{\text{nó}}$).
   - O candidato ainda não recebeu o voto do nó neste termo (`votedFor is None`).
   - O log do candidato é **pelo menos tão atualizado** como o log do nó (comparando termo da última entrada e índice).
4. Se o candidato receber votos de uma **maioria estrita** ($\lfloor N/2 \rfloor + 1$), transita para **Leader** e envia imediatamente *Heartbeats* para afirmar autoridade.

#### 2.1.3. Réplica de Log & Invariante de Segurança
O Líder aceita os comandos dos clientes, anexa-os como novas entradas ao seu log local e transmite a RPC `AppendEntries`:

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

- **Log Matching Property**: Se duas entradas em logs de nós diferentes tiverem o mesmo índice e o mesmo termo, elas armazenam o mesmo comando e os seus logs são idênticos em todas as entradas anteriores.
- **Commitment**: Uma entrada é considerada *Committed* assim que é replicada na maioria dos nós pelo Líder do termo atual.

---

## 💽 3. Motores de Armazenamento: LSM-Trees vs. B+Trees

### 3.1. Log-Structured Merge-Trees (LSM-Trees)

#### 3.1.1. Arquitetura Interna
1. **MemTable**: Estrutura de dados em memória mantida ordenada (ex: *SkipList* ou *Red-Black Tree*). Todas as operações `PUT` e `DELETE` são gravadas na MemTable.
2. **Write-Ahead Log (WAL)**: Registo sequencial no disco que garante durabilidade antes da MemTable ser modificada.
3. **SSTables (Sorted String Tables)**: Quando a MemTable atinge um limite (ex: 64MB), é descarregada imutavelmente para o disco como um ficheiro SSTable contendo pares chave-valor ordenados.

#### 3.1.2. Bloom Filters & Probabilidade de Erro
Para evitar leituras em disco quando uma chave não existe, cada SSTable possui um **Fórmula do Bloom Filter**:
Dada uma taxa de falsos positivos pretendida $p$, um número de elementos $n$ e um tamanho de vetor em bits $m$:
$$m = -\frac{n \ln p}{(\ln 2)^2}$$
O número ótimo de funções hash $k$ é:
$$k = \frac{m}{n} \ln 2$$

#### 3.1.3. Processo de Compactação (Compaction)
- **Leveled Compaction**: Os dados são divididos em níveis ($L_0, L_1, L_2 \dots$). Cada nível $L_i$ tem uma capacidade máxima de tamanho ($10^i$ MB). Quando o nível $L_i$ enche, ficheiros SSTable sobrepostos são fundidos e reordenados para o nível $L_{i+1}$, eliminando registos apagados (*Tombstones*) e atualizações antigas.

---

### 3.2. B+Trees & Algoritmo ARIES de Recuperação

#### 3.2.1. Estrutura Estrutural
Ao contrário das B-Trees tradicionais, numa **B+Tree**:
- Todos os dados/valores são armazenados exclusivamente nos **nós folha**.
- Os nós internos contêm apenas chaves de encaminhamento (*Routings Keys*).
- Todos os nós folha estão encadeados numa **lista duplamente ligada**, permitindo *Range Queries* extremamente eficientes.

```
                  ┌────────────────────────┐
                  │    Nó Interno: [50]    │
                  └───────────┬────────────┘
                              │
         ┌────────────────────┴────────────────────┐
         ▼                                         ▼
┌─────────────────┐                       ┌─────────────────┐
│ Folha: [10, 30] │ ◄───────────────────► │ Folha: [50, 80] │
└─────────────────┘                       └─────────────────┘
```

#### 3.2.2. Algoritmo ARIES (Algorithms for Recovery and Isolation Exploiting Semantics)
Em caso de falha de energia ou *crash* da base de dados, a recuperação ARIES executa 3 fases estritas:
1. **Fase de Análise**: Examina o WAL a partir do último *Checkpoint* para reconstruir a Tabela de Transações Ativas (ATT) e a Tabela de Páginas Sujas (DPT).
2. **Fase Redo**: Re-executa todas as alterações registadas no WAL a partir da página mais antiga na DPT, restaurando o estado exato da base de dados antes do crash.
3. **Fase Undo**: Reverte todas as transações que estavam ativas (incompletas) no momento do crash, percorrendo o WAL para trás e aplicando registos de compensação (CLRs).

---

## ⚡ 4. Teoria de Isolamento de Transações Concorrentes & MVCC

### 4.1. Anomalias de Concorrência
- **Dirty Read**: $T_1$ modifica um valor. $T_2$ lê o valor modificado. $T_1$ faz `ROLLBACK`. $T_2$ leu dados inválidos.
- **Non-Repeatable Read**: $T_1$ lê um valor. $T_2$ atualiza o valor e faz `COMMIT`. $T_1$ volta a ler o valor e obtém um resultado diferente.
- **Phantom Read**: $T_1$ lê um conjunto de linhas com uma condição. $T_2$ insere uma nova linha que satisfaz a condição e faz `COMMIT`. $T_1$ re-executa a query e obtém linhas fantasmas adicionais.
- **Write Skew**: $T_1$ e $T_2$ leem simultaneamente o mesmo estado (ex: $A + B \ge 100$). $T_1$ reduz $A$ e $T_2$ reduz $B$. Ambas as transações fazem `COMMIT`, mas o invariante global $A + B \ge 100$ é violado.

### 4.2. Multi-Version Concurrency Control (MVCC)
No MVCC, as atualizações não sobreescrevem os dados existentes. Em vez disso, cada tuplo possui metadados de versão:
- `xmin`: ID da transação que criou o tuplo.
- `xmax`: ID da transação que apagou ou sobreescreveu o tuplo (ou 0 se estiver ativo).

Quando a transação $T_k$ lê a base de dados, cria uma **Read View** contendo a lista de transações ativas no momento. $T_k$ apenas pode ver um tuplo se:
1. `xmin` é uma transação já confirmada (*Committed*) antes do início da Read View de $T_k$.
2. `xmax` é não-existente ou pertence a uma transação que ainda não tinha feito *Commit* quando a Read View de $T_k$ foi criada.
