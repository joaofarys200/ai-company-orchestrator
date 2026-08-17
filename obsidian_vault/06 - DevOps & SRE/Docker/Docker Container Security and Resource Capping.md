---
type: technology
domain: devops
difficulty: intermediate
tags:
  - devops
  - docker
  - security
  - cgroups
  - containers
status: verified
---

# 🐳 Docker Container Security and Resource Capping

## 1. Princípios de Isolamento de Containers
Containers Docker partilham o mesmo kernel do sistema operativo anfitrião. Sem restrições explícitas de segurança e limites de recursos (*cgroups* e *namespaces*), um processo comprometido dentro do container pode esgotar toda a memória RAM da máquina host (provocando travamento do sistema) ou tentar escapar para o host (*Container Breakout*).

---

## 2. Configuração de Hardening de Produção

### 2.1. Execução Não-Root (Non-Root User)
Nunca executar containers como utilizador `root`. Criar um utilizador dedicado com UID/GID fixo no Dockerfile:

```dockerfile
# Criar utilizador seguro sem privilégios
RUN addgroup --system --gid 1001 jarvisgroup && \
    adduser --system --uid 1001 --ingroup jarvisgroup jarvisuser

# Ajustar permissões apenas para o diretório da aplicação
WORKDIR /app
COPY --chown=jarvisuser:jarvisgroup . /app

USER jarvisuser
```

### 2.2. Limitação de Recursos (CPU e Memória com Cgroups)
No `docker-compose.yml` ou flag `docker run`:

```yaml
version: '3.8'
services:
  jarvis-sandbox:
    image: jarvis/sandbox-runner:latest
    deploy:
      resources:
        limits:
          cpus: '2.00'
          memory: 2048M
        reservations:
          cpus: '0.50'
          memory: 512M
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    read_only: true
    tmpfs:
      - /tmp:rw,noexec,nosuid,size=128m
```

---

## 3. Diretrizes de Segurança Invioláveis
1. **`read_only: true`**: Monta o sistema de ficheiros raiz do container como somente leitura, impedindo modificações de binários ou injeção de scripts no sistema.
2. **`cap_drop: ALL`**: Remove todas as capacidades do Linux (`CAP_NET_RAW`, `CAP_SYS_ADMIN`, etc.), deixando o processo com privilégios mínimos.
3. **`no-new-privileges:true`**: Previne que executáveis com bit SUID/SGID elevem privilégios dentro do container.

---

## 4. Related Concepts
- [[Least-Privilege Process Sandboxing and Execution Jail]]
- [[Threat Modeling for Autonomous Coding Agents]]
- [[CI-CD Pipeline Failure Triage and Automated Healing]]

---

## 5. Sources
- *Docker Security Best Practices*: https://docs.docker.com/engine/security/
- *CIS Docker Benchmark*: https://www.cisecurity.org/benchmark/docker
