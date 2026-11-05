---
type: concept
domain: backend-systems
difficulty: advanced
status: verified
source_type: PRIMARY_SOURCE
confidence: high
freshness: stable
tags:
  - backend
  - storage-engines
  - lsm-tree
  - b-tree
  - databases
  - compaction
---

# 🗄️ LSM-Trees vs B-Trees - Write Amplification, Compaction and Read Paths

## 1. A Conjetura RUM em Motores de Armazenamento
Segundo a **Conjetura RUM** (*Read, Update, Memory Overhead*), nenhum motor de armazenamento pode minimizar simultaneamente sobrecarga de leitura ($R$), custo de atualização/escrita ($U$) e espaço em disco/memória ($M$); otimizar dois degrada inevitavelmente o terceiro.

1. **B+Trees (SQLite, PostgreSQL, InnoDB — *Update-in-Place*)**:
   - Organizam dados em páginas de tamanho fixo (`4 KB`–`16 KB`) ordenadas por chave.
   - Leituras pontuais e *range scans* são previsíveis ($O(\log_B N)$, 2–4 acessos com nós internos em RAM), mas escritas aleatórias exigem reescrever páginas inteiras + WAL, gerando **Write Amplification (WA)** elevada e fragmentação por *page splits*.
2. **LSM-Trees (RocksDB, Cassandra, Pebble — *Append-Only + Merge*)**:
   - Absorvem escritas sequencialmente num `WAL` + `MemTable` ordenada em RAM (SkipList/Red-Black Tree).
   - Ao atingir o limiar, a `MemTable` é descarregada (*flush*) como um **SSTable** imutável em disco, enquanto threads de background executam **Compaction** (*merge-sort* assíncrono que descarta versões antigas e *tombstones*).

---

## 2. Comparação Arquitetural e Amplificações

| Dimensão | B+Tree (SQLite WAL / Postgres) | LSM-Tree (Leveled Compaction) | LSM-Tree (Size-Tiered / STCS) |
|---|---|---|---|
| **Throughput de Escrita Aleatória** | Moderado (I/O aleatório de página) | Alto (escrita sequencial) | Muito Alto (menor WA) |
| **Write Amplification ($\text{WA}$)** | Alta em updates pequenos | Moderada–Alta ($10\times\text{–}30\times$) | Baixa ($4\times\text{–}10\times$) |
| **Latência de Leitura (`GET`)** | Baixa e estável ($O(\log_B N)$) | Boa com **Bloom Filters** em RAM | Mais alta (verifica vários tiers) |
| **Space Amplification ($\text{SA}$)** | Fragmentação interna (~25–35%) | Muito Baixa (~1.1$\times$) | Alta durante compactação (~2$\times$) |

---

## 3. O Papel dos Bloom Filters e Leitura em LSM
Sem filtros auxiliares, consultar uma chave inexistente numa LSM-Tree obrigaria a inspecionar múltiplos SSTables em disco. Um **Bloom Filter** por bloco/SSTable com $m$ bits e $n$ chaves reduz a probabilidade de falso positivo a:

$$p_{\text{fp}} \approx \left(1 - e^{-kn/m}\right)^k \approx 0.6185^{m/n} \quad (\approx 1\% \text{ com } 10\text{ bits/chave})$$

evitando $>99\%$ das leituras físicas desnecessárias para chaves ausentes.

---

## 4. Conceitos Relacionados & Fontes
- [[SQLite WAL Mode and Concurrency]]
- [[Comparison - SQLite WAL vs Client-Server PostgreSQL]]
- [[Database Crash Consistency and Recovery]]
- [[DDIA_Designing_Data_Intensive_Applications_BOK]]
- **Fontes**: O'Neil et al. (1996), *The Log-Structured Merge-Tree (LSM-Tree)*; Athanassoulis et al. (2016), *Designing Access Methods: The RUM Conjecture*; Kleppmann (2017), *DDIA* (Cap. 3).

