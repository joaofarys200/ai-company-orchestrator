---
type: concept
domain: security
difficulty: advanced
tags:
  - security
  - ssrf
  - network-security
  - web-fetchers
  - agents
status: verified
---

# 🛡️ SSRF Defense in Agentic Fetchers

## 1. Definição do Ataque SSRF
**Server-Side Request Forgery (SSRF)** ocorre quando um agente autónomo com capacidade de fazer requisições HTTP (ferramenta `fetch_url` ou `read_web_page`) é induzido a requisitar recursos na rede interna do anfitrião ou em endereços especiais de infraestrutura em nuvem.

### Alvos Comuns de SSRF:
- **Cloud Metadata Services**: `http://169.254.169.254/latest/meta-data/` (AWS/GCP/Azure) para roubo de tokens temporários IAM.
- **Loopback Local**: `http://127.0.0.1:8000`, `http://localhost:5432` para interagir com bancos de dados ou APIs administrativas desprotegidas na mesma máquina.
- **Redes Privadas (RFC 1918)**: `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`.

```
[ Atacante instrui o agente a ler: "http://169.254.169.254/latest/meta-data/iam/security-credentials/" ]
                                           |
                                           v
[ Agente invoca ferramenta `fetch_url(url="...")` sem validação ]
                                           |
                                           v
[ Servidor faz a requisição na rede local e recebe as credenciais IAM do anfitrião ]
                                           |
                                           v
[ Agente imprime as credenciais na resposta ou relatório -> VAZAMENTO CRÍTICO ]
```

---

## 2. Padrão de Validação com Resolução DNS Prévia (Anti-DNS Rebinding)

Muitas implementações ingênuas verificam apenas se a string da URL começa com `localhost`. Atacantes contornam isso com domínios públicos que apontam para `127.0.0.1` (ex: `evil.localtest.me`) ou com **DNS Rebinding** (onde o domínio devolve IP público no primeiro lookup e IP privado no momento da conexão).

### Implementação Segura de Fetcher HTTP

```python
import socket
import ipaddress
import urllib.parse
import httpx

BLOCKED_IP_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),       # Loopback
    ipaddress.ip_network("10.0.0.0/8"),        # Private RFC 1918
    ipaddress.ip_network("172.16.0.0/12"),     # Private RFC 1918
    ipaddress.ip_network("192.168.0.0/16"),    # Private RFC 1918
    ipaddress.ip_network("169.254.0.0/16"),    # Link-Local / Cloud Metadata
    ipaddress.ip_network("::1/128"),           # IPv6 Loopback
    ipaddress.ip_network("fc00::/7"),          # IPv6 Private
]

def is_safe_external_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ["http", "https"]:
        return False

    hostname = parsed.hostname
    if not hostname:
        return False

    try:
        # Resolver todos os IPs do hostname
        addr_infos = socket.getaddrinfo(hostname, None)
        for family, _, _, _, sockaddr in addr_infos:
            ip_str = sockaddr[0]
            ip_obj = ipaddress.ip_address(ip_str)

            # Bloquear se qualquer IP pertencer a redes privadas ou reservadas
            for blocked_net in BLOCKED_IP_NETWORKS:
                if ip_obj in blocked_net:
                    return False
    except socket.gaierror:
        return False

    return True
```

---

## 3. Related Concepts
- [[Least-Privilege Process Sandboxing and Execution Jail]]
- [[Prompt Injection Defense in Autonomous Agents]]
- [[Indirect Prompt Injection via Web Pages]]
- [[Tratado_Completo_de_Ciberseguranca_Redes_e_DevSecOps]]

---

## 4. Sources
- *OWASP Top 10: A10:2021 – Server-Side Request Forgery (SSRF)*: https://owasp.org/Top10/A10_2021-Server-Side_Request_Forgery_%28SSRF%29/
- *RFC 1918 - Address Allocation for Private Internets*: https://datatracker.ietf.org/doc/html/rfc1918
