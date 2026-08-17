---
type: decision
domain: jarvis
difficulty: intermediate
tags:
  - jarvis
  - adr
  - architectural-decision
  - security
  - sandboxing
status: verified
---

# 📋 ADR-002 - Process Sandboxing and Path Jail Enforcement

## Status
**Aceite / Em Produção**

## Contexto
O agente Devon possui capacidade autónoma de gerar código e executar comandos de compilação, testes e terminais. Sem restrições de isolamento, comandos maliciosos introduzidos via prompt injection indireto ou bugs de geração de código poderiam apagar ficheiros do anfitrião (`C:\Windows`, `~/.ssh`) ou alterar configurações globais do sistema.

## Decisão
Implementar uma arquitetura de **Sandboxing em Duas Camadas**:
1. **Path Jail no Sistema de Ficheiros (`workspace_policy.py`)**: Valida que toda a operação de I/O em disco ocorre estritamente dentro da pasta do projeto e do subdiretório `sandbox_dir/`.
2. **Isolamento de Subprocessos (`sandbox.py`)**: Executa processos de terminal com `shell=False`, timeouts rígidos (máx 60s) e variáveis de ambiente higienizadas sem chaves mestras do sistema anfitrião.

## Consequências
- **Positivas**: Proteção robusta contra comandos destrutivos e evasão de sandbox; garantia de segurança para tarefas autónomas de longa duração.
- **Negativas**: Operações que legitimamente exigem alterações no host ou instalação de ferramentas de sistema requerem autorização explícita do operador humano (Human-in-the-Loop).
