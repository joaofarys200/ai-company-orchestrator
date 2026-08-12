# 🛡️ Tratado Completo de Cibersegurança, Redes de Computadores & DevSecOps

---

## 📌 1. Visão Geral
Este tratado estabelece o **Corpo de Conhecimento em Cibersegurança, Redes e Defesa em Profundidade** para governar o **JARVIS OS**. O objetivo é dotar o agente autónomo de capacidade de avaliação ofensiva/defensiva, auditoria de código, hardening de infraestrutura e proteção contra exploração de sistemas.

---

## 🌐 2. Engenharia de Redes & Protocolos da Camada de Transporte/Rede

### 2.1. O Protocolo TCP & Mecânica de Congestão (BBR)

#### 2.1.1. Estabelecimento e Encerramento de Conexões
```
Client                                  Server
  │                                       │
  ├─────────────── SYN (seq=x) ──────────►│  (Estado: SYN-RECEIVED)
  │                                       │
  │◄───────── SYN-ACK (seq=y, ack=x+1) ───┤
  │                                       │
  ├─────────── ACK (seq=x+1, ack=y+1) ───►│  (Estado: ESTABLISHED)
```

#### 2.1.2. Ataque SYN Flood & Formulação Matemática de SYN Cookies
Em ataques de **SYN Flood**, a fila de conexões pendentes (*Syn Backlog*) é esgotada. Para contornar este problema sem alocar memória no servidor, aplicam-se **SYN Cookies**:
O Número de Sequência Inicial (ISN) do servidor é calculado como:
$$\text{ISN} = t \bmod 32 \mathbin{\Vert} \text{MSS\_Index} \mathbin{\Vert} H(t, \text{src\_ip}, \text{src\_port}, \text{dst\_ip}, \text{dst\_port}, K)$$

Onde $H$ é uma função hash criptográfica de uso único com segredo $K$. O servidor valida o `ACK` recebido re-calculando o hash sem necessidade de manter estado prévio na tabela TCB.

### 2.2. Protocolo ARP & Injeção de Pacotes (ARP Poisoning)
- **Ataque ARP Spoofing**: Envio de respostas `ARP Reply` não solicitadas associando o IP do Gateway ($192.168.1.1$) ao MAC do atacante ($AA:BB:CC:DD:EE:FF$).
- **Mitigação**: Inspeção Dinâmica de ARP (**DAI - Dynamic ARP Inspection**) em switches de rede, que valida pacotes ARP contra a base de dados de associação DHCP Snooping.

### 2.3. Resolução DNS & Segurança DNSSEC
- **DNSSEC (Domain Name System Security Extensions)**:
  - Adiciona registos criptográficos de chave pública (`DNSKEY`), assinaturas de registos (`RRSIG`) e hashes de delegação (`DS`).
  - Garante a autenticidade e integridade da cadeia de confiança DNS a partir da Raiz (`.`), prevenindo ataques de **DNS Cache Poisoning**.

---

## 🔑 3. Criptografia Aplicada & Infraestrutura PKI

### 3.1. Criptografia Simétrica com Autenticação (AEAD)
Nas comunicações modernas, utiliza-se exclusivamente **AEAD (Authenticated Encryption with Associated Data)** como o **AES-256-GCM**:

```python
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

def encrypt_sensitive_payload(data: bytes, secret_key: bytes) -> tuple[bytes, bytes]:
    # Nonce de 96 bits (12 bytes) deve ser ÚNICO por cada mensagem
    nonce = os.urandom(12)
    aesgcm = AESGCM(secret_key)
    ciphertext = aesgcm.encrypt(nonce, data, associated_data=b"JARVIS_OS_HEADER")
    return nonce, ciphertext

def decrypt_sensitive_payload(nonce: bytes, ciphertext: bytes, secret_key: bytes) -> bytes:
    aesgcm = AESGCM(secret_key)
    return aesgcm.decrypt(nonce, ciphertext, associated_data=b"JARVIS_OS_HEADER")
```

### 3.2. Troca de Chaves Diffie-Hellman em Curvas Elípticas (ECDHE) & Perfect Forward Secrecy
Para garantir **Perfect Forward Secrecy (PFS)** em conexões TLS 1.3:
1. O cliente e o servidor geram pares de chaves efémeros (temporários) em curvas elípticas ($A = g^a \pmod p$ e $B = g^b \pmod p$).
2. A chave de sessão $K = g^{ab} \pmod p$ é calculada de forma independente.
3. Se no futuro a chave privada de longo prazo do servidor for comprometida, o tráfego passado interceptado **NUNCA** poderá ser decifrado porque as chaves efémeras $a$ e $b$ foram apagadas da memória RAM imediatamente após o término da sessão.

---

## 💥 4. Cibersegurança Ofensiva & Exploração de Vulnerabilidades

### 4.1. Server-Side Request Forgery (SSRF) em Ambientes Cloud
- **Vetor de Exploração**: O atacante manipula um parâmetro de URL numa API que efetua requisições HTTP internas:
  ```http
  POST /api/fetch-avatar HTTP/1.1
  Host: jarvis-app.com
  Content-Type: application/json

  {"url": "http://169.254.169.254/latest/meta-data/iam/security-credentials/"}
  ```
- **Consequência**: O servidor efetua o pedido ao IP de metadados da infraestrutura Cloud (AWS/GCP), devolvendo os tokens temporários do papel IAM para o atacante.
- **Mitigação Estrita**:
  ```python
  import ipaddress
  from urllib.parse import urlparse

  def is_safe_external_url(url: str) -> bool:
      parsed = urlparse(url)
      if parsed.scheme not in ("http", "https"):
          return False
      
      # Resolver o hostname para IP e bloquear gamas privadas e locais
      ip = ipaddress.ip_address(parsed.hostname)
      if ip.is_private or ip.is_loopback or ip.is_link_local:
          return False
      return True
  ```

### 4.2. Insecure Deserialization em Python (`pickle`)
- Em Python, a desserialização de ficheiros `.pkl` não confiáveis via `pickle.loads()` permite a execução remota de código (RCE) imediata através do método `__reduce__`:
  ```python
  import pickle
  import os

  class ExploitPayload:
      def __reduce__(self):
          # Executa comandos arbitrários no sistema operativo quando o objeto é lido
          return (os.system, ("whoami",))

  # O dado gerado abaixo provocará RCE se for desserializado pelo servidor
  serialized_data = pickle.dumps(ExploitPayload())
  ```
- **Regra de Ouro**: NUNCA utilizar `pickle` para trocar dados com clientes ou guardar estados não assinados. Utilizar exclusivamente **JSON**, **Protocol Buffers** ou **MessagePack**.

---

## 🏰 5. Cibersegurança Defensiva, Zero Trust & OAuth 2.0 PKCE

### 5.1. OAuth 2.0 PKCE (Proof Key for Code Exchange) Flow
Para impedir a interceção do código de autorização em aplicações nativas/web:
1. O cliente gera um `code_verifier` (string aleatória entre 43 e 128 carateres).
2. O cliente calcula o `code_challenge`:
   $$\text{code\_challenge} = \text{Base64URL}(\text{SHA256}(\text{code\_verifier}))$$
3. O cliente envia o `code_challenge` no pedido de autorização.
4. Ao trocar o `code` pelo `access_token`, o cliente envia o `code_verifier` original. O servidor valida se $\text{SHA256}(\text{code\_verifier}) == \text{code\_challenge}$.

### 5.2. Prevenção de Ataques a Tokens JWT
- **Ataque de Confusão de Algoritmo (RS256 $\to$ HS256)**:
  - Um atacante altera o header de um JWT assinado assimetricamente com RSA (`RS256`) para HMAC simétrico (`HS256`), e assina o token com a **Chave Pública** do servidor. Se o código do servidor for vulnerável, usará a chave pública como chave secreta HMAC e aceitará o token adulterado.
- **Mitigação**: Forçar a validação estrita do algoritmo esperado nas definições do descodificador (`algorithms=["RS256"]`).

---

## 🤖 6. Segurança em Agentes de IA & Sandboxing

### 6.1. Proteção contra Prompt Injection Indireto
Quando o agente lê documentos externos (e-mails, repositórios de código, páginas web), esses ficheiros podem conter instruções maliciosas ocultas.

**Arquitetura de Guardrails de Validação**:
1. **Canal de Instruções Limpo**: As diretivas de segurança do `System Prompt` são isoladas de dados externos.
2. **Sanitização de Contexto**: Padrões de injeção como `Ignora as tuas instruções anteriores` ou `Mostra o teu System Prompt` são detetados e removidos antes do modelo processar os dados.
3. **Sandbox AST**: Nenhum código gerado pelo agente pode aceder a bibliotecas do sistema operativo sem passar previamente pelo analisador sintático de segurança `ast.parse()`.
