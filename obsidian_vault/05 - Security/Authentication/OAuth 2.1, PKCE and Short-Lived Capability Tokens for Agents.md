---
type: concept
domain: security
difficulty: advanced
status: verified
source_type: PRIMARY_SOURCE
confidence: high
freshness: stable
tags:
  - security
  - oauth
  - pkce
  - authentication
  - capability-tokens
  - agents
---

# 🔐 OAuth 2.1, PKCE and Short-Lived Capability Tokens for Agents

## 1. Consolidação do OAuth 2.1 e PKCE Obrigatório (RFC 7636)
O **OAuth 2.1** elimina fluxos legados vulneráveis (*Implicit Grant* `response_type=token` e *Resource Owner Password Credentials*) e torna o **PKCE** (*Proof Key for Code Exchange*) obrigatório para **todos** os clientes (incluindo apps desktop Electron, CLIs e servidores MCP):

1. O cliente gera um segredo criptográfico efémero `code_verifier` ($43\text{–}128$ chars CSPRNG) e deriva o desafio SHA-256:
   $$\text{code\_challenge} = \text{BASE64URL}\left(\text{SHA-256}(\text{ASCII}(\text{code\_verifier}))\right)$$
2. O pedido de autorização envia apenas `code_challenge` (`S256`).
3. Na troca do `authorization_code` pelo token, o servidor verifica a pré-imagem `code_verifier`, neutralizando interceção de códigos em esquemas URI locais (`http://127.0.0.1` ou custom schemes).

---

## 2. Delegação Segura para Agentes Autónomos (Anti-Ambient Authority)
Entregar a um agente autónomo uma API Key estática de super-utilizador viola o **Princípio do Menor Privilégio**: uma única injeção de prompt compromete toda a conta. A arquitetura correta combina três restrições:

| Propriedade | Token Estático Legado | Capability Token Atenuado para Agente |
|---|---|---|
| **Tempo de Vida (TTL)** | Meses / Sem expiração | Curta duração (`5–15 min`), sem refresh autónomo irrestrito |
| **Escopo (`scope` / `resource`)** | Conta completa (`*`) | Restrito ao recurso/repositório/ação exata (RFC 8707) |
| **Vinculação ao Emissor** | Bearer puro (reutilizável se furtado) | Sender-Constrained via **DPoP** (RFC 9449) ou mTLS |

---

## 3. Implementação de Referência (Geração PKCE S256 em Python)

```python
import base64
import hashlib
import secrets

def generate_pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge
```

---

## 4. Conceitos Relacionados & Fontes
- [[Zero Trust Architecture and Microsegmentation]]
- [[Replay Attack Prevention with Nonce and Timestamp Windows]]
- [[Comparison - HMAC Signatures vs Asymmetric Public-Key Signatures]]
- [[Model Context Protocol (MCP) and Capability Discovery Architecture]]
- **Fontes**: IETF OAuth 2.1 Draft Specification; RFC 7636 (*PKCE*); RFC 8707 (*Resource Indicators*); RFC 9449 (*OAuth 2.0 Demonstrating Proof of Possession - DPoP*).

