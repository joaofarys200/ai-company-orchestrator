# 🗄️ DDIA BOK — Designing Data-Intensive Applications (Martin Kleppmann Reference)

## 📌 1. Visão Geral
Este manual de referência compila os pilares do livro **Designing Data-Intensive Applications (DDIA)** de Martin Kleppmann para fundamentar decisões de arquitetura de dados, consistência, replicação e sistemas distribuídos no **JARVIS OS**.

---

## 🏛️ 2. Fundamentos de Arquiteturas de Dados

### 2.1. Os Três Pilares: Fiabilidade, Escalabilidade e Manutenibilidade
- **Fiabilidade (Reliability)**: O sistema continua a funcionar corretamente (no nível de desempenho esperado) mesmo quando ocorrem falhas de hardware, software ou erros humanos.
- **Escalabilidade (Scalability)**: Capacidade de manter o desempenho razoável quando a carga (queries/seg, volume de dados, rácio escrita/leitura) aumenta.
- **Manutenibilidade (Maintainability)**: Capacidade de permitir que múltiplos engenheiros e agentes autónomos trabalhem e evoluam o código sem quebrar funcionalidades legadas.

---

## 💽 3. Motores de Armazenamento: LSM-Trees vs. B-Trees

### 3.1. Log-Structured Merge-Trees (LSM-Trees)
- **Mecanismo**: As escritas são gravadas sequencialmente numa estrutura em memória chamada *MemTable* e num registo de escrita antecedente (*WAL*). Quando a MemTable atinge um limite, é descarregada para o disco como uma tabela de strings ordenadas (*SSTable* imutável).
- **Vantagem**: **Vazão de Escrita Extremamente Alta** (escritas sequenciais em disco). Utilizado em RocksDB, LevelDB, Cassandra.

### 3.2. B-Trees
- **Mecanismo**: Estrutura de árvore equilibrada de tamanho fixo de páginas (habitualmente 4KB) gravadas diretamente no disco.
- **Vantagem**: **Leituras Mais Rápidas e Suporte a Transações ACID Tradicionais**. Utilizado em PostgreSQL, MySQL (InnoDB), SQLite.

---

## 🔄 4. Replicação & Consenso Distribuído

### 4.1. Arquiteturas de Replicação
1. **Single-Leader (Líder Único)**:
   - Todas as escritas são enviadas exclusivamente para o nó Líder, que replica as alterações para os nós Seguidores (*Followers*).
   - *Desafio*: Failover em caso de queda do Líder e prevenção de *Split-Brain*.
2. **Multi-Leader (Múltiplos Líderes)**:
   - Permite escritas em múltiplos nós (ex: data centers em regiões geográficas distintas).
   - *Desafio*: Resolução de conflitos de escrita simultânea (Last-Write-Wins, Merge CRDTs).
3. **Leaderless (Sem Líder - Dynamo-style)**:
   - O cliente envia escritas e leituras diretamente para múltiplos nós em paralelo. Utiliza quorum ($R + W > N$).

### 4.2. Algoritmos de Consenso Distribuído (Raft & Paxos)
- Para garantir que múltiplos nós concordam sobre uma única decisão de estado (ex: eleição de líder, fecho de transação distribuída), utiliza-se o algoritmo **Raft**:
  - *Líder*: Gere todas as entradas no log replicado.
  - *Termos e Eleições*: Se o líder falhar, os seguidores iniciam uma eleição por maioria de votos ($N/2 + 1$).

---

## ⚡ 5. Níveis de Isolamento de Transações (ACID vs. BASE)

| Nível de Isolamento | Previne Dirty Reads? | Previne Non-Repeatable Reads? | Previne Phantom Reads? | Previne Write Skew? |
|---|---|---|---|---|
| **Read Uncommitted** | ❌ Não | ❌ Não | ❌ Não | ❌ Não |
| **Read Committed** | ✅ Sim | ❌ Não | ❌ Não | ❌ Não |
| **Repeatable Read (Snapshot Isolation)** | ✅ Sim | ✅ Sim | ✅ Sim | ❌ Não |
| **Serializable (SSI)** | ✅ Sim | ✅ Sim | ✅ Sim | ✅ Sim |

- **Write Skew**: Ocorre quando duas transações leem o mesmo conjunto de dados, tomam decisões com base nisso e atualizam dados cruzados que quebram o invariante de negócio (ex: dois médicos a sair de turno ao mesmo tempo). O nível **Serializable** previne este problema.

---

## 📊 6. Processamento Batch & Stream Processing

### 6.1. Processamento Batch (MapReduce / Spark)
- Processa grandes volumes de dados estáticos imutáveis com garantias de idempotência e tolerância a falhas.

### 6.2. Processamento em Fluxo (Stream Processing / Event-Driven)
- Trata dados como um fluxo infinito de eventos em tempo real (Kafka Streams, Flink).
- Permite cálculo de janelas móveis (*Tumbling*, *Hopping*, *Sliding Windows*) para deteção instantânea de padrões e anomalias.
