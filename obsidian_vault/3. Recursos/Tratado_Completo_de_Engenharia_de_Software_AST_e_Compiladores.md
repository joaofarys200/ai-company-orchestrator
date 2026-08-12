# 🔬 Tratado Completo de Engenharia de Software, AST, Compiladores & Metaprogramação

---

## 📌 1. Teoria de Compiladores e Árvores de Sintaxe Abstrata (AST)

### 1.1. Pipeline de Compilação & Análise Sintática
O processo de transformação de código-fonte em instruções executáveis ou representações abstratas segue 4 etapas estritas:

```
Source Code (Text) ──► [ Lexer / Scanner ] ──► Token Stream
                                                    │
                                                    ▼
                                           [ Parser LALR(1) ]
                                                    │
                                                    ▼
                                         Abstract Syntax Tree (AST)
                                                    │
                                                    ▼
                                       [ Static Analysis / CFG ]
                                                    │
                                                    ▼
                                        Target Code / Bytecode
```

1. **Análise Léxica (Lexing)**: Converte uma sequência de carateres num fluxo de *Tokens* tipados (ex: `IDENTIFIER`, `ASSIGN`, `NUMBER`).
2. **Análise Sintática (Parsing)**: Constrói a Árvore de Sintaxe Abstrata de acordo com a Gramática Livre de Contexto (CFG) da linguagem.
3. **Análise Semântica**: Verificação de tipos, resolução de escopo de variáveis e checagem de invariantes de tipagem.
4. **Geração de Código / Refatoração**: Transformação da AST para emitir novo código-fonte, Bytecode Python ou representação IL.

---

## ⚙️ 2. Manipulação Programática de AST em Python (`ast` Module)

### 2.1. Inspecção Estática de Símbolos com `ast.NodeVisitor`
Para inspecionar um código sem o executar (garantindo segurança absoluta contra injeção de código), utiliza-se o padrão Visitor:

```python
import ast

class CodeInspector(ast.NodeVisitor):
    def __init__(self):
        self.classes: list[str] = []
        self.functions: list[str] = []
        self.imports: list[str] = []

    def visit_ClassDef(self, node: ast.ClassDef):
        self.classes.append(node.name)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.functions.append(node.name)
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.imports.append(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module:
            self.imports.append(node.module)
        self.generic_visit(node)
```

### 2.2. Transformação de Código Cirúrgica com `ast.NodeTransformer`
Para refatorar código automaticamente (ex: injetar decoradores de telemetria ou substituir chamadas inseguras):

```python
import ast

class TelemetryInjector(ast.NodeTransformer):
    """Injeta automaticamente o decorador @log_execution em todas as funções públicas."""
    
    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        self.generic_visit(node)
        if not node.name.startswith("_"):
            decorator = ast.Name(id="log_execution", ctx=ast.Load())
            if not any(isinstance(d, ast.Name) and d.id == "log_execution" for d in node.decorator_list):
                node.decorator_list.insert(0, decorator)
        return node

def refactor_code(source: str) -> str:
    tree = ast.parse(source)
    transformer = TelemetryInjector()
    new_tree = transformer.visit(tree)
    ast.fix_missing_locations(new_tree)
    return ast.unparse(new_tree)
```

---

## 🏛️ 3. Modelação Tática de Domain-Driven Design (DDD) & Clean Architecture

### 3.1. Implementação de Agregados e Invariantes de Negócio
Um Agregado DDD é uma fronteira de consistência transacional. Nenhuma entidade interna do agregado pode ser modificada diretamente por código externo; todas as alterações DEVEM passar pela raiz do agregado (*Aggregate Root*):

```python
from __future__ import annotations
from dataclasses import dataclass, field
import uuid
import time

class DomainException(Exception):
    """Exceção base para violações de regras de negócio."""

@dataclass(frozen=True)
class OrderId:
    value: str = field(default_factory=lambda: str(uuid.uuid4()))

@dataclass(frozen=True)
class OrderLineItem:
    product_id: str
    quantity: int
    unit_price: float

    def subtotal(self) -> float:
        return self.quantity * self.unit_price

class OrderAggregate:
    """Aggregate Root que garante o invariante de valor mínimo de encomenda."""
    
    def __init__(self, order_id: OrderId, customer_id: str):
        self.id = order_id
        self.customer_id = customer_id
        self._items: list[OrderLineItem] = []
        self._is_submitted: bool = False

    @property
    def total_amount(self) -> float:
        return sum(item.subtotal() for item in self._items)

    def add_item(self, product_id: str, quantity: int, unit_price: float) -> None:
        if self._is_submitted:
            raise DomainException("Não é possível adicionar itens a uma encomenda já submetida.")
        if quantity <= 0:
            raise DomainException("A quantidade do item deve ser estritamente positiva.")
        
        self._items.append(OrderLineItem(product_id, quantity, unit_price))

    def submit(self, min_order_value: float = 50.0) -> None:
        if self.total_amount < min_order_value:
            raise DomainException(f"O valor total da encomenda (€{self.total_amount:.2f}) é inferior ao mínimo (€{min_order_value:.2f}).")
        self._is_submitted = True
```

---

## 🧪 4. Verificação de Cobertura de Mutação (Mutation Testing)

### 4.1. Princípio do Mutation Testing
Ao contrário da cobertura de código tradicional (*Line/Branch Coverage*), que apenas indica quais linhas foram executadas durante os testes, o **Mutation Testing** avalia se os testes são realmente capazes de detetar falhas:
1. O motor de mutação modifica ligeiramente o código-fonte (ex: altera `>` para `>=`, substitui `+` por `-`, ou substitui `True` por `False`).
2. Executa a suíte de testes unitários contra o código mutado.
3. Se algum teste falhar, o mutante é considerado **Killed (Morto)** ✅.
4. Se todos os testes passarem, o mutante é considerado **Survived (Sobreviveu)** ❌ (indicando que o teste é fraco e não valida adequadamente o comportamento).
