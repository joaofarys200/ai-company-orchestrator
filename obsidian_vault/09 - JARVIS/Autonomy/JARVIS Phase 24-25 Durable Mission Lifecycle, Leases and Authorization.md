---
type: architecture
domain: jarvis
difficulty: advanced
status: verified
source_type: JARVIS_INTERNAL
confidence: high
freshness: stable
tags:
  - jarvis
  - mission-persistence
  - crash-recovery
  - file-leases
  - authorization
  - phase-24
  - phase-25
---

# 🛡️ JARVIS Phase 24-25 Durable Mission Lifecycle, Leases and Authorization

## 1. Modelo de Persistência e Governação de Missões (Fases 24–25)
As Fases 24 e 25 estabilizaram a execução de missões longas no **JARVIS OS**, garantindo que reinícios da aplicação, falhas de processo ou bloqueios de aprovação nunca corrompam o estado, não repitam efeitos colaterais perigosos nem reportem conclusão falsa.

### Componentes Centrais:
1. **`MissionStateStore` & Persistência JSON Atómica (`agents/mission_persistence.py`)**:
   - Fonte de verdade autoritativa baseada em escrita atómica (`write temp + fsync + os.replace`) com journal de checkpoints e registo estruturado de evidências por *Work Package* e *Acceptance Criteria*.
2. **`FileLeaseManager` (`agents/file_lease_manager.py`)**:
   - Concessão atómica de *leases* exclusivos por ficheiro com expiração temporal (TTL) e renovação explícita, impedindo condições de corrida entre workers concorrentes no mesmo workspace.
3. **`PermissionGatewayService` & `ProjectDependencyManager` (`security/permission_gateway/`)**:
   - Operações sensíveis de desenvolvimento (como instalação de pacotes `pip`/`npm` no ambiente isolado do projeto) exigem autorização explícita com escopo de projeto — proibindo instalações globais ou privilegiadas por omissão.

---

## 2. Invariantes de Crash Recovery (`agents/mission_recovery.py`)

| Estado no Momento da Queda | Ação na Recuperação de Arranque (`application_lifecycle.py`) | Garantia de Segurança |
|---|---|---|
| **A aguardar aprovação humana** | Mantém estado `WAITING_APPROVAL` bloqueado | Nunca retoma automaticamente operações sem consentimento renovado |
| **Durante efeito colateral mutável** | Inspeciona checkpoint pré-efeito e evidência observável | Evita reexecução cega de instalações ou mutações não idempotentes |
| **Lease órfão pós-crash** | Reconcilia/liberta leases expirados do processo morto | Desbloqueia workspace sem apagar alterações locais do utilizador |
| **Processo terminou sem verificação** | Exige validação real dos critérios de aceitação | Proibido marcar `COMPLETED` apenas por `exit_code == 0` do worker |

---

## 3. Regra de Ouro da Transição de Estado
Toda transição com efeito externo grava **intenção (`IN_PROGRESS` / checkpoint pré-ação) antes do side effect** e só grava **conclusão (`VERIFIED`) após observar evidência verificável** em disco ou em execução de testes.

---

## 4. Conceitos Relacionados & Fontes
- [[JARVIS Mission State Machine and Autonomy]]
- [[JARVIS MissionRecoveryWatchdog and Crash Recovery]]
- [[Idempotency in Software Systems]]
- [[Distributed Locks and Fencing Tokens]]
- [[Software Supply Chain Security - SLSA, SBOM and Dependency Pinning]]
- **Fontes**: Código-fonte do JARVIS OS — `agents/mission_orchestrator.py`, `agents/mission_persistence.py`, `agents/mission_recovery.py`, `agents/file_lease_manager.py`, `security/permission_gateway/`.

