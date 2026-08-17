---
type: troubleshooting
domain: software-engineering
difficulty: intermediate
tags:
  - software-engineering
  - troubleshooting
  - python
  - imports
  - sys-path
status: verified
---

# 🛠️ How to Diagnose Python Import and Module Resolution Failures

## 1. Sintomas & Diagnóstico
- `ModuleNotFoundError: No module named 'agents'`
- `ImportError: cannot import name 'ModelHarness' from partially initialized module (most likely due to a circular import)`
- `ValueError: attempted relative import beyond top-level package`

---

## 2. Árvore de Decisão de Causa Raiz

```
                            [ Erro de Import no Python ]
                                          |
                   +----------------------+----------------------+
                   |                                             |
     [ ModuleNotFoundError ]                            [ ImportError: circular ]
                   |                                             |
   +---------------+---------------+                     +-------+-------+
   |                               |                     |               |
[ Pacote não instalado ]   [ PYTHONPATH não contém ]  [ Dependência    [ Import no topo
(ex: pip install missing)  [ o diretório raiz ]       [ cíclica A <-> B[ de ficheiros ]
```

---

## 3. Procedimento de Correção Passo a Passo

### Cenário A: O Módulo Existe no Repositório mas o Python não o Encontra
**Causa**: O script foi executado de dentro de uma subpasta (ex: `cd agents/ && python swarm.py`), fazendo com que `sys.path[0]` seja `agents/` em vez da raiz do projeto.

**Correção**:
1. Executar sempre os comandos a partir da raiz do workspace:
   ```powershell
   python -m agents.swarm
   ```
2. Ou configurar a variável de ambiente `PYTHONPATH`:
   ```powershell
   $env:PYTHONPATH = "c:\Users\joaor\Desktop\JarvisOS"
   ```

### Cenário B: Importação Circular (`partially initialized module`)
**Causa**: O módulo `A.py` faz `import B` no topo, e o módulo `B.py` faz `import A` no topo.

**Correção**:
1. Extrair os tipos/modelos partilhados para um ficheiro neutro `types.py` ou `interfaces.py`.
2. Mover o import para dentro da função que o utiliza (Lazy Import) em vez do topo do ficheiro.

---

## 4. Comandos de Diagnóstico Rápido

```python
# Inspecionar caminhos de busca do interpretador em tempo real:
import sys
import pprint
pprint.pprint(sys.path)
```

---

## 5. Related Concepts
- [[Abstract Syntax Tree (AST) Parsing and Manipulation]]
- [[Clean Architecture and Hexagonal Ports]]
- [[How to Safely Validate and Apply Code Patches]]

---

## 6. Sources
- *Python Official Documentation - The import system (PEP 302 / PEP 451)*: https://docs.python.org/3/reference/import.html
- *Python Documentation - sys.path handling*: https://docs.python.org/3/library/sys.html#sys.path
