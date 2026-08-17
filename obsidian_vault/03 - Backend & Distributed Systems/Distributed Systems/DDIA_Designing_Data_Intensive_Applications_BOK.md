---
type: concept
domain: backend-systems
difficulty: advanced
tags:
  - backend
  - ddia
  - databases
status: verified
---

# ðŸ—„ï¸ DDIA BOK â€” Designing Data-Intensive Applications (Martin Kleppmann Reference)

## ðŸ“Œ 1. VisÃ£o Geral
Este manual de referÃªncia compila os pilares do livro **Designing Data-Intensive Applications (DDIA)** de Martin Kleppmann para fundamentar decisÃµes de arquitetura de dados, consistÃªncia, replicaÃ§Ã£o e sistemas distribuÃ­dos no **JARVIS OS**.

---

## ðŸ›ï¸ 2. Fundamentos de Arquiteturas de Dados

### 2.1. Os TrÃªs Pilares: Fiabilidade, Escalabilidade e Manutenibilidade
- **Fiabilidade (Reliability)**: O sistema continua a funcionar corretamente (no nÃ­vel de desempenho esperado) mesmo quando ocorrem falhas de hardware, software ou erros humanos.
- **Escalabilidade (Scalability)**: Capacidade de manter o desempenho razoÃ¡vel quando a carga (queries/seg, volume de dados, rÃ¡cio escrita/leitura) aumenta.
- **Manutenibilidade (Maintainability)**: Capacidade de permitir que mÃºltiplos engenheiros e agentes autÃ³nomos trabalhem e evoluam o cÃ³digo sem quebrar funcionalidades legadas.

---

## ðŸ’½ 3. Motores de Armazenamento: LSM-Trees vs. B-Trees

### 3.1. Log-Structured Merge-Trees (LSM-Trees)
- **Mecanismo**: As escritas sÃ£o gravadas sequencialmente numa estrutura em memÃ³ria chamada *MemTable* e num registo de escrita antecedente (*WAL*). Quando a MemTable atinge um limite, Ã© descarregada para o disco como uma tabela de strings ordenadas (*SSTable* imutÃ¡vel).
- **Vantagem**: **VazÃ£o de Escrita Extremamente Alta** (escritas sequenciais em disco). Utilizado em RocksDB, LevelDB, Cassandra.

### 3.2. B-Trees
- **Mecanismo**: Estrutura de Ã¡rvore equilibrada de tamanho fixo de pÃ¡ginas (habitualmente 4KB) gravadas diretamente no disco.
- **Vantagem**: **Leituras Mais RÃ¡pidas e Suporte a TransaÃ§Ãµes ACID Tradicionais**. Utilizado em PostgreSQL, MySQL (InnoDB), SQLite.

---

## ðŸ”„ 4. ReplicaÃ§Ã£o & Consenso DistribuÃ­do

### 4.1. Arquiteturas de ReplicaÃ§Ã£o
1. **Single-Leader (LÃ­der Ãšnico)**:
   - Todas as escritas sÃ£o enviadas exclusivamente para o nÃ³ LÃ­der, que replica as alteraÃ§Ãµes para os nÃ³s Seguidores (*Followers*).
   - *Desafio*: Failover em caso de queda do LÃ­der e prevenÃ§Ã£o de *Split-Brain*.
2. **Multi-Leader (MÃºltiplos LÃ­deres)**:
   - Permite escritas em mÃºltiplos nÃ³s (ex: data centers em regiÃµes geogrÃ¡ficas distintas).
   - *Desafio*: ResoluÃ§Ã£o de conflitos de escrita simultÃ¢nea (Last-Write-Wins, Merge CRDTs).
3. **Leaderless (Sem LÃ­der - Dynamo-style)**:
   - O cliente envia escritas e leituras diretamente para mÃºltiplos nÃ³s em paralelo. Utiliza quorum ($R + W > N$).

### 4.2. Algoritmos de Consenso DistribuÃ­do (Raft & Paxos)
- Para garantir que mÃºltiplos nÃ³s concordam sobre uma Ãºnica decisÃ£o de estado (ex: eleiÃ§Ã£o de lÃ­der, fecho de transaÃ§Ã£o distribuÃ­da), utiliza-se o algoritmo **Raft**:
  - *LÃ­der*: Gere todas as entradas no log replicado.
  - *Termos e EleiÃ§Ãµes*: Se o lÃ­der falhar, os seguidores iniciam uma eleiÃ§Ã£o por maioria de votos ($N/2 + 1$).

---

## âš¡ 5. NÃ­veis de Isolamento de TransaÃ§Ãµes (ACID vs. BASE)

| NÃ­vel de Isolamento | Previne Dirty Reads? | Previne Non-Repeatable Reads? | Previne Phantom Reads? | Previne Write Skew? |
|---|---|---|---|---|
| **Read Uncommitted** | âŒ NÃ£o | âŒ NÃ£o | âŒ NÃ£o | âŒ NÃ£o |
| **Read Committed** | âœ… Sim | âŒ NÃ£o | âŒ NÃ£o | âŒ NÃ£o |
| **Repeatable Read (Snapshot Isolation)** | âœ… Sim | âœ… Sim | âœ… Sim | âŒ NÃ£o |
| **Serializable (SSI)** | âœ… Sim | âœ… Sim | âœ… Sim | âœ… Sim |

- **Write Skew**: Ocorre quando duas transaÃ§Ãµes leem o mesmo conjunto de dados, tomam decisÃµes com base nisso e atualizam dados cruzados que quebram o invariante de negÃ³cio (ex: dois mÃ©dicos a sair de turno ao mesmo tempo). O nÃ­vel **Serializable** previne este problema.

---

## ðŸ“Š 6. Processamento Batch & Stream Processing

### 6.1. Processamento Batch (MapReduce / Spark)
- Processa grandes volumes de dados estÃ¡ticos imutÃ¡veis com garantias de idempotÃªncia e tolerÃ¢ncia a falhas.

### 6.2. Processamento em Fluxo (Stream Processing / Event-Driven)
- Trata dados como um fluxo infinito de eventos em tempo real (Kafka Streams, Flink).
- Permite cÃ¡lculo de janelas mÃ³veis (*Tumbling*, *Hopping*, *Sliding Windows*) para deteÃ§Ã£o instantÃ¢nea de padrÃµes e anomalias.

