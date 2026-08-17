---
type: concept
domain: software-engineering
difficulty: advanced
tags:
  - software-engineering
  - ast
  - compilers
status: verified
---

# ðŸ”¬ Tratado Completo de Engenharia de Software, AST, Compiladores & MetaprogramaÃ§Ã£o

---

## ðŸ“Œ 1. Teoria de Compiladores e Ãrvores de Sintaxe Abstrata (AST)

### 1.1. Pipeline de CompilaÃ§Ã£o & AnÃ¡lise SintÃ¡tica
O processo de transformaÃ§Ã£o de cÃ³digo-fonte em instruÃ§Ãµes executÃ¡veis ou representaÃ§Ãµes abstratas segue 4 etapas estritas:

```
Source Code (Text) â”€â”€â–º [ Lexer / Scanner ] â”€â”€â–º Token Stream
                                                    â”‚
                                                    â–¼
                                           [ Parser LALR(1) ]
                                                    â”‚
                                                    â–¼
                                         Abstract Syntax Tree (AST)
                                                    â”‚
                                                    â–¼
                                       [ Static Analysis / CFG ]
                                                    â”‚
                                                    â–¼
                                        Target Code / Bytecode
```

1. **AnÃ¡lise LÃ©xica (Lexing)**: Converte uma sequÃªncia de carateres num fluxo de *Tokens* tipados (ex: `IDENTIFIER`, `ASSIGN`, `NUMBER`).
2. **AnÃ¡lise SintÃ¡tica (Parsing)**: ConstrÃ³i a Ãrvore de Sintaxe Abstrata de acordo com a GramÃ¡tica Livre de Contexto (CFG) da linguagem.
3. **AnÃ¡lise SemÃ¢ntica**: VerificaÃ§Ã£o de tipos, resoluÃ§Ã£o de escopo de variÃ¡veis e checagem de invariantes de tipagem.
4. **GeraÃ§Ã£o de CÃ³digo / RefatoraÃ§Ã£o**: TransformaÃ§Ã£o da AST para emitir novo cÃ³digo-fonte, Bytecode Python ou representaÃ§Ã£o IL.

---

## âš™ï¸ 2. ManipulaÃ§Ã£o ProgramÃ¡tica de AST em Python (`ast` Module)

### 2.1. InspecÃ§Ã£o EstÃ¡tica de SÃ­mbolos com `ast.NodeVisitor`
Para inspecionar um cÃ³digo sem o executar (garantindo seguranÃ§a absoluta contra injeÃ§Ã£o de cÃ³digo), utiliza-se o padrÃ£o Visitor:

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

### 2.2. TransformaÃ§Ã£o de CÃ³digo CirÃºrgica com `ast.NodeTransformer`
Para refatorar cÃ³digo automaticamente (ex: injetar decoradores de telemetria ou substituir chamadas inseguras):

```python
import ast

class TelemetryInjector(ast.NodeTransformer):
    """Injeta automaticamente o decorador @log_execution em todas as funÃ§Ãµes pÃºblicas."""
    
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

## ðŸ›ï¸ 3. ModelaÃ§Ã£o TÃ¡tica de Domain-Driven Design (DDD) & Clean Architecture

### 3.1. ImplementaÃ§Ã£o de Agregados e Invariantes de NegÃ³cio
Um Agregado DDD Ã© uma fronteira de consistÃªncia transacional. Nenhuma entidade interna do agregado pode ser modificada diretamente por cÃ³digo externo; todas as alteraÃ§Ãµes DEVEM passar pela raiz do agregado (*Aggregate Root*):

```python
from __future__ import annotations
from dataclasses import dataclass, field
import uuid
import time

class DomainException(Exception):
    """ExceÃ§Ã£o base para violaÃ§Ãµes de regras de negÃ³cio."""

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
    """Aggregate Root que garante o invariante de valor mÃ­nimo de encomenda."""
    
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
            raise DomainException("NÃ£o Ã© possÃ­vel adicionar itens a uma encomenda jÃ¡ submetida.")
        if quantity <= 0:
            raise DomainException("A quantidade do item deve ser estritamente positiva.")
        
        self._items.append(OrderLineItem(product_id, quantity, unit_price))

    def submit(self, min_order_value: float = 50.0) -> None:
        if self.total_amount < min_order_value:
            raise DomainException(f"O valor total da encomenda (â‚¬{self.total_amount:.2f}) Ã© inferior ao mÃ­nimo (â‚¬{min_order_value:.2f}).")
        self._is_submitted = True
```

---

## ðŸ§ª 4. VerificaÃ§Ã£o de Cobertura de MutaÃ§Ã£o (Mutation Testing)

### 4.1. PrincÃ­pio do Mutation Testing
Ao contrÃ¡rio da cobertura de cÃ³digo tradicional (*Line/Branch Coverage*), que apenas indica quais linhas foram executadas durante os testes, o **Mutation Testing** avalia se os testes sÃ£o realmente capazes de detetar falhas:
1. O motor de mutaÃ§Ã£o modifica ligeiramente o cÃ³digo-fonte (ex: altera `>` para `>=`, substitui `+` por `-`, ou substitui `True` por `False`).
2. Executa a suÃ­te de testes unitÃ¡rios contra o cÃ³digo mutado.
3. Se algum teste falhar, o mutante Ã© considerado **Killed (Morto)** âœ….
4. Se todos os testes passarem, o mutante Ã© considerado **Survived (Sobreviveu)** âŒ (indicando que o teste Ã© fraco e nÃ£o valida adequadamente o comportamento).

