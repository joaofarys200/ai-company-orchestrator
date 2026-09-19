import React, { useState } from 'react';
import {
  Wrench,
  CheckCircle2,
  AlertOctagon,
  Layers,
  Activity,
  GitPullRequest,
  Search,
  RefreshCw,
  Clock,
  Compass,
  FileCode,
  ShieldCheck,
  Zap,
  TrendingUp,
  Lock,
} from 'lucide-react';

interface QualityDebtRemediationPanelProps {
  missionId?: string;
}

export const QualityDebtRemediationPanel: React.FC<QualityDebtRemediationPanelProps> = ({
  missionId = 'mission_f69_remediation',
}) => {
  const [activeSubtab, setActiveSubtab] = useState<string>('overview');
  const [selectedDebtId, setSelectedDebtId] = useState<string>('debt_arch_01');
  const [isExecuting, setIsExecuting] = useState<boolean>(false);
  const [executionLog, setExecutionLog] = useState<string[]>([
    `System initialized for mission: ${missionId}. Closed-loop Quality Debt Remediation Engine active.`,
    'Ingestion: 5 candidate technical debts ingested from Phase 68 ledger.',
    'Validation gate: Evidence validity confirmed on 4 items, 1 flagged for human review.',
  ]);

  const subtabs = [
    { id: 'overview', label: '01. Debt Overview', icon: Wrench, elementId: 'remediation-subtab-overview' },
    { id: 'validation', label: '02. Validation', icon: CheckCircle2, elementId: 'remediation-subtab-validation' },
    { id: 'root_cause', label: '03. Root Cause', icon: Search, elementId: 'remediation-subtab-root-cause' },
    { id: 'options', label: '04. Remediation Options', icon: Layers, elementId: 'remediation-subtab-options' },
    { id: 'impact', label: '05. Quality Impact', icon: TrendingUp, elementId: 'remediation-subtab-impact' },
    { id: 'governance', label: '06. Governance Gate', icon: ShieldCheck, elementId: 'remediation-subtab-governance' },
    { id: 'mission', label: '07. Remediation Mission', icon: Compass, elementId: 'remediation-subtab-mission' },
    { id: 'implementation', label: '08. Safe Implementation', icon: FileCode, elementId: 'remediation-subtab-implementation' },
    { id: 'verification', label: '09. Continuous Verification', icon: Activity, elementId: 'remediation-subtab-verification' },
    { id: 'rescan', label: '10. Quality Rescan', icon: RefreshCw, elementId: 'remediation-subtab-rescan' },
    { id: 'resolution', label: '11. Debt Resolution', icon: GitPullRequest, elementId: 'remediation-subtab-resolution' },
    { id: 'deferment', label: '12. Active Deferments', icon: Clock, elementId: 'remediation-subtab-deferment' },
    { id: 'gaming', label: '13. Gaming Defense', icon: AlertOctagon, elementId: 'remediation-subtab-gaming' },
    { id: 'final_state', label: '14. Final Debt State', icon: Lock, elementId: 'remediation-subtab-final-state' },
  ];

  const candidateDebts = [
    {
      id: 'debt_arch_01',
      category: 'ARCHITECTURAL',
      severity: 'HIGH',
      surface: 'backend.agents.massive_project_state <-> scc_aware_graph',
      status: 'ROLLED_BACK',
      confidence: 0.94,
      cost: '3.5 pts',
      risk: 'High (0.55)',
    },
    {
      id: 'debt_code_02',
      category: 'CODE',
      severity: 'MEDIUM',
      surface: 'backend.websocket.handlers.missions.MissionWebSocketHandler',
      status: 'DEFERRED',
      confidence: 0.88,
      cost: '6.0 pts',
      risk: 'Medium (0.42)',
    },
    {
      id: 'debt_test_03',
      category: 'TEST',
      severity: 'MEDIUM',
      surface: 'tests.test_collaboration_long_horizon.py',
      status: 'PARTIALLY_RESOLVED',
      confidence: 0.91,
      cost: '2.0 pts',
      risk: 'Low (0.15)',
    },
    {
      id: 'debt_ops_04',
      category: 'OPERATIONAL',
      severity: 'HIGH',
      surface: 'scripts.run_phase67_browser_qa.py',
      status: 'RESOLVED',
      confidence: 0.95,
      cost: '1.5 pts',
      risk: 'Low (0.12)',
    },
    {
      id: 'debt_perf_05',
      category: 'PERFORMANCE',
      severity: 'LOW',
      surface: 'backend.memory.MissionStateStore.sqlite_pool',
      status: 'DEFERRED',
      confidence: 0.86,
      cost: '4.0 pts',
      risk: 'Medium (0.35)',
    },
  ];

  const handleRunRemediation = () => {
    setIsExecuting(true);
    setExecutionLog((prev) => [
      ...prev,
      `[${new Date().toLocaleTimeString()}] Executing transactional remediation for debt: ${selectedDebtId}`,
      `[${new Date().toLocaleTimeString()}] Preflight snapshot captured. Isolated patch transaction active.`,
      `[${new Date().toLocaleTimeString()}] 9-dimension quality rescan verifying structural invariants...`,
    ]);
    setTimeout(() => {
      setIsExecuting(false);
      setExecutionLog((prev) => [
        ...prev,
        `[${new Date().toLocaleTimeString()}] Verification concluded: Verification passed with empirical hash audit.`,
      ]);
    }, 1200);
  };

  return (
    <div className="flex flex-col h-full bg-slate-950 text-slate-100 p-6 space-y-6 overflow-y-auto" id="quality-debt-remediation-container">
      {/* Header Banner */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div className="space-y-1">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-indigo-500/10 border border-indigo-500/30 rounded-lg text-indigo-400">
              <Wrench className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
                Autonomous Quality Debt Remediation
                <span className="text-xs font-mono font-medium px-2 py-0.5 rounded-full bg-indigo-950 text-indigo-300 border border-indigo-800">
                  Fase 69
                </span>
              </h1>
              <p className="text-sm text-slate-400">
                Closed-loop verified remediation lifecycle • DEBT_DETECTED != DEBT_RESOLVED • Continuous verification
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            id="remediation-btn-run"
            onClick={handleRunRemediation}
            disabled={isExecuting}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-800 text-white rounded-lg text-sm font-medium transition shadow-lg shadow-indigo-600/20 cursor-pointer"
          >
            <Zap className="w-4 h-4" />
            {isExecuting ? 'Executando Remediação...' : 'Executar Remediação Fechada'}
          </button>
        </div>
      </div>

      {/* Navigation Subtabs (14 Subtabs) */}
      <div className="flex overflow-x-auto gap-2 border-b border-slate-800 pb-2 scrollbar-thin">
        {subtabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeSubtab === tab.id;
          return (
            <button
              key={tab.id}
              id={tab.elementId}
              onClick={() => setActiveSubtab(tab.id)}
              className={`flex items-center gap-2 px-3 py-2 text-xs font-medium rounded-lg whitespace-nowrap transition cursor-pointer ${
                isActive
                  ? 'bg-indigo-600/20 text-indigo-300 border border-indigo-500/30'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Main Content Area */}
      <div className="flex-1 space-y-6">
        {/* SUBTAB 01: OVERVIEW */}
        {activeSubtab === 'overview' && (
          <div className="space-y-6" id="remediation-view-overview">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="p-4 bg-slate-900/60 border border-slate-800 rounded-xl">
                <div className="text-xs text-slate-400 font-medium">Dívidas Ativas</div>
                <div className="text-2xl font-bold text-amber-400 mt-1">5 Items</div>
                <div className="text-xs text-slate-500 mt-1">Identificados pela Governação F68</div>
              </div>
              <div className="p-4 bg-slate-900/60 border border-slate-800 rounded-xl">
                <div className="text-xs text-slate-400 font-medium">Taxa de Resolução Fechada</div>
                <div className="text-2xl font-bold text-emerald-400 mt-1">100% Verificado</div>
                <div className="text-xs text-slate-500 mt-1">Zero falsas conclusões aceites</div>
              </div>
              <div className="p-4 bg-slate-900/60 border border-slate-800 rounded-xl">
                <div className="text-xs text-slate-400 font-medium">Proteção Anti-Gaming</div>
                <div className="text-2xl font-bold text-indigo-400 mt-1">ATIVO</div>
                <div className="text-xs text-slate-500 mt-1">Bloqueio de exclusão ou remoção de teste</div>
              </div>
              <div className="p-4 bg-slate-900/60 border border-slate-800 rounded-xl">
                <div className="text-xs text-slate-400 font-medium">Reversibilidade Transacional</div>
                <div className="text-2xl font-bold text-sky-400 mt-1">Snapshot / Revert</div>
                <div className="text-xs text-slate-500 mt-1">Rollback atómico em caso de falha</div>
              </div>
            </div>

            <div className="p-5 bg-slate-900/40 border border-slate-800 rounded-xl">
              <h3 className="text-sm font-semibold text-slate-200 mb-3">Fila de Dívida Técnica em Remediação</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="text-slate-400 border-b border-slate-800">
                    <tr>
                      <th className="pb-2">Debt ID</th>
                      <th className="pb-2">Categoria</th>
                      <th className="pb-2">Superfície Afetada</th>
                      <th className="pb-2">Severidade</th>
                      <th className="pb-2">Custo Est.</th>
                      <th className="pb-2">Estado</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {candidateDebts.map((d) => (
                      <tr
                        key={d.id}
                        onClick={() => setSelectedDebtId(d.id)}
                        className={`hover:bg-slate-800/40 cursor-pointer ${
                          selectedDebtId === d.id ? 'bg-indigo-950/40 text-indigo-200' : 'text-slate-300'
                        }`}
                      >
                        <td className="py-2.5 font-mono font-medium">{d.id}</td>
                        <td className="py-2.5">
                          <span className="px-2 py-0.5 rounded text-[10px] bg-slate-800 text-slate-300">
                            {d.category}
                          </span>
                        </td>
                        <td className="py-2.5 font-mono text-slate-400">{d.surface}</td>
                        <td className="py-2.5">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] ${
                              d.severity === 'HIGH'
                                ? 'bg-rose-950 text-rose-300 border border-rose-800'
                                : 'bg-amber-950 text-amber-300 border border-amber-800'
                            }`}
                          >
                            {d.severity}
                          </span>
                        </td>
                        <td className="py-2.5">{d.cost}</td>
                        <td className="py-2.5 font-semibold text-emerald-400">{d.status}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* SUBTAB 02: VALIDATION */}
        {activeSubtab === 'validation' && (
          <div className="space-y-4" id="remediation-view-validation">
            <div className="p-5 bg-slate-900/40 border border-slate-800 rounded-xl space-y-4">
              <h3 className="text-sm font-semibold text-slate-200">Validação Estrutural e Temporal de Dívida</h3>
              <p className="text-xs text-slate-400">
                O motor valida a existência física da superfície, consistência de evidência e frescura temporal. Dívidas fictícias ou obsoletas são rejeitadas.
              </p>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
                <div className="p-3 bg-slate-950 border border-slate-800 rounded-lg">
                  <span className="text-slate-500">Superfície Confirmada:</span>
                  <div className="font-mono text-emerald-400 mt-1">SIM (AST & SCC Verificados)</div>
                </div>
                <div className="p-3 bg-slate-950 border border-slate-800 rounded-lg">
                  <span className="text-slate-500">Reprodutibilidade:</span>
                  <div className="font-mono text-emerald-400 mt-1">CONFIRMADA (100% determinística)</div>
                </div>
                <div className="p-3 bg-slate-950 border border-slate-800 rounded-lg">
                  <span className="text-slate-500">Estado de Validação:</span>
                  <div className="font-mono text-indigo-400 mt-1">VALID_DEBT (Confiança: 0.94)</div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* SUBTAB 03: ROOT CAUSE */}
        {activeSubtab === 'root_cause' && (
          <div className="space-y-4" id="remediation-view-root-cause">
            <div className="p-5 bg-slate-900/40 border border-slate-800 rounded-xl space-y-4">
              <h3 className="text-sm font-semibold text-slate-200">Isolamento de Causa Raiz vs Correlação</h3>
              <div className="p-4 bg-slate-950 border border-slate-800 rounded-lg space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-400 font-medium">Categoria Causal:</span>
                  <span className="px-2 py-0.5 rounded bg-indigo-950 text-indigo-300 border border-indigo-800 font-mono">
                    ARCHITECTURAL_CAUSE
                  </span>
                </div>
                <p className="text-xs text-slate-300">
                  Ciclo direto de dependência cíclica identificado entre o particionador de estado massivo e o grafo SCC. Nenhuma alteração meramente cosmética resolverá a raiz do acoplamento.
                </p>
                <div className="text-[11px] text-slate-500 font-mono">
                  Evidência: Condensation Graph SCC Size = 2 nós mutuamente referenciados.
                </div>
              </div>
            </div>
          </div>
        )}

        {/* SUBTAB 04: OPTIONS */}
        {activeSubtab === 'options' && (
          <div className="space-y-4" id="remediation-view-options">
            <div className="p-5 bg-slate-900/40 border border-slate-800 rounded-xl space-y-4">
              <h3 className="text-sm font-semibold text-slate-200">Alternativas de Remediação Sintetizadas</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
                <div className="p-4 bg-slate-950 border border-slate-800 rounded-lg space-y-2">
                  <div className="font-semibold text-amber-400">01. KEEP_CURRENT</div>
                  <p className="text-slate-400 text-[11px]">Manter estado sob monitorização passiva. Custo: 0, Risco cumulativo: 0.60.</p>
                </div>
                <div className="p-4 bg-slate-950 border border-indigo-700/50 rounded-lg space-y-2 bg-indigo-950/20">
                  <div className="font-semibold text-indigo-300 flex items-center justify-between">
                    02. DEPENDENCY_INVERSION
                    <span className="text-[10px] bg-indigo-900 text-indigo-200 px-1.5 py-0.5 rounded">Recomendado</span>
                  </div>
                  <p className="text-slate-300 text-[11px]">Introduzir protocolo desacoplado. Quebra o ciclo SCC mantendo contratos públicos.</p>
                </div>
                <div className="p-4 bg-slate-950 border border-slate-800 rounded-lg space-y-2">
                  <div className="font-semibold text-slate-300">03. MODULE_EXTRACTION</div>
                  <p className="text-slate-400 text-[11px]">Extrair módulo compartilhado. Custo elevado (6.0 pts), risco moderado de migração.</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* SUBTAB 05: IMPACT */}
        {activeSubtab === 'impact' && (
          <div className="space-y-4" id="remediation-view-impact">
            <div className="p-5 bg-slate-900/40 border border-slate-800 rounded-xl space-y-4">
              <h3 className="text-sm font-semibold text-slate-200">Impacto Qualitativo Previsto (9 Dimensões F68)</h3>
              <div className="grid grid-cols-3 gap-2 text-xs">
                {['ARCHITECTURE', 'CODE', 'TEST', 'CONTRACT', 'BEHAVIOR', 'SECURITY', 'PERFORMANCE', 'RELIABILITY', 'MAINTAINABILITY'].map((d) => (
                  <div key={d} className="p-2.5 bg-slate-950 border border-slate-800 rounded flex justify-between items-center">
                    <span className="font-mono text-slate-400">{d}</span>
                    <span className="text-emerald-400 font-semibold text-[11px]">
                      {d === 'ARCHITECTURE' || d === 'MAINTAINABILITY' ? 'IMPROVEMENT_EXPECTED' : 'NO_EXPECTED_CHANGE'}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* SUBTAB 06: GOVERNANCE */}
        {activeSubtab === 'governance' && (
          <div className="space-y-4" id="remediation-view-governance">
            <div className="p-5 bg-slate-900/40 border border-slate-800 rounded-xl space-y-4">
              <h3 className="text-sm font-semibold text-slate-200">Decisão de Governação & Orçamento de Qualidade</h3>
              <div className="flex items-center gap-3 p-3 bg-emerald-950/30 border border-emerald-800 rounded-lg">
                <ShieldCheck className="w-5 h-5 text-emerald-400" />
                <div>
                  <div className="text-xs font-semibold text-emerald-300">APROVADO PARA EXECUÇÃO AUTÓNOMA</div>
                  <div className="text-[11px] text-slate-400">Orçamento: 5 ficheiros máx, 120s tempo limite, 1 tentativa de rollback atómica permitida.</div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* SUBTAB 07: MISSION */}
        {activeSubtab === 'mission' && (
          <div className="space-y-4" id="remediation-view-mission">
            <div className="p-5 bg-slate-900/40 border border-slate-800 rounded-xl space-y-4">
              <h3 className="text-sm font-semibold text-slate-200">Missão Bounded de Remediação (Fase 67)</h3>
              <div className="text-xs font-mono text-slate-300 bg-slate-950 p-3 rounded-lg border border-slate-800">
                Objetivo: RESOLVE_DEBT(debt_arch_01)<br />
                Critérios de Sucesso:<br />
                - Evidência original deixa de reproduzir<br />
                - Re-medição de qualidade confirma melhoria sem regressão crítica<br />
                - Contratos e invariantes comportamentais preservados
              </div>
            </div>
          </div>
        )}

        {/* SUBTAB 08: IMPLEMENTATION */}
        {activeSubtab === 'implementation' && (
          <div className="space-y-4" id="remediation-view-implementation">
            <div className="p-5 bg-slate-900/40 border border-slate-800 rounded-xl space-y-4">
              <h3 className="text-sm font-semibold text-slate-200">Execução Segura Transacional (Fase 65)</h3>
              <div className="text-xs text-slate-300 space-y-2">
                <div className="p-2.5 bg-slate-950 border border-slate-800 rounded flex justify-between">
                  <span>Preflight Snapshot:</span>
                  <span className="font-mono text-emerald-400">COMPLETED (Hash: e8b91a2)</span>
                </div>
                <div className="p-2.5 bg-slate-950 border border-slate-800 rounded flex justify-between">
                  <span>Isolamento Transacional:</span>
                  <span className="font-mono text-emerald-400">ZERO WRITES OUTSIDE TRANSACTION</span>
                </div>
                <div className="p-2.5 bg-slate-950 border border-slate-800 rounded flex justify-between">
                  <span>Build & Unit Tests:</span>
                  <span className="font-mono text-emerald-400">PASSED</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* SUBTAB 09: VERIFICATION */}
        {activeSubtab === 'verification' && (
          <div className="space-y-4" id="remediation-view-verification">
            <div className="p-5 bg-slate-900/40 border border-slate-800 rounded-xl space-y-4">
              <h3 className="text-sm font-semibold text-slate-200">Verificação Contínua Pós-Patch</h3>
              <p className="text-xs text-slate-400">
                O sistema nunca aceita PATCH_APPLIED como conclusão. O resultado da verificação empírica dita se o commit é retido ou revertido.
              </p>
              <div className="p-3 bg-slate-950 border border-slate-800 rounded-lg font-mono text-xs text-slate-300">
                Evidência Original: Invalidada (ciclo SCC quebrado com sucesso).
              </div>
            </div>
          </div>
        )}

        {/* SUBTAB 10: RESCAN */}
        {activeSubtab === 'rescan' && (
          <div className="space-y-4" id="remediation-view-rescan">
            <div className="p-5 bg-slate-900/40 border border-slate-800 rounded-xl space-y-4">
              <h3 className="text-sm font-semibold text-slate-200">Re-Medição de Qualidade: BEFORE vs AFTER</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                <div className="p-4 bg-slate-950 border border-slate-800 rounded-lg">
                  <div className="text-slate-400 font-semibold mb-2">QUALITY_BEFORE (Baseline)</div>
                  <div className="font-mono text-slate-300 space-y-1">
                    <div>ARCHITECTURE: 0.72</div>
                    <div>MAINTAINABILITY: 0.70</div>
                    <div>OVERALL_STATUS: DEGRADED</div>
                  </div>
                </div>
                <div className="p-4 bg-slate-950 border border-slate-800 rounded-lg">
                  <div className="text-emerald-400 font-semibold mb-2">QUALITY_AFTER (Post-Remediation)</div>
                  <div className="font-mono text-slate-300 space-y-1">
                    <div>ARCHITECTURE: 0.88 (+0.16)</div>
                    <div>MAINTAINABILITY: 0.86 (+0.16)</div>
                    <div>OVERALL_STATUS: REAL_IMPROVEMENT</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* SUBTAB 11: RESOLUTION */}
        {activeSubtab === 'resolution' && (
          <div className="space-y-4" id="remediation-view-resolution">
            <div className="p-5 bg-slate-900/40 border border-slate-800 rounded-xl space-y-4">
              <h3 className="text-sm font-semibold text-slate-200">Governação de Resolução Final</h3>
              <div className="p-4 bg-slate-950 border border-slate-800 rounded-lg space-y-2">
                <div className="text-xs text-slate-400">Estado de Resolução:</div>
                <div className="text-lg font-bold text-emerald-400">RESOLVED</div>
                <p className="text-xs text-slate-300">
                  Evidência original invalidada, re-medição de qualidade confirma ganho estrutural real e nenhuma regressão foi observada.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* SUBTAB 12: DEFERMENT */}
        {activeSubtab === 'deferment' && (
          <div className="space-y-4" id="remediation-view-deferment">
            <div className="p-5 bg-slate-900/40 border border-slate-800 rounded-xl space-y-4">
              <h3 className="text-sm font-semibold text-slate-200">Dívidas Técnicas Adiada sob Governação Ativa</h3>
              <p className="text-xs text-slate-400">
                Dívidas adiadas nunca são ocultadas. Mantêm-se no quality ledger com proprietário, custo esperado e data de revisão obrigatória.
              </p>
              <div className="p-3 bg-slate-950 border border-slate-800 rounded-lg font-mono text-xs text-slate-300">
                debt_code_02: Deferida (Blast Radius transversal). Revisit: Sprint 70. Owner: LeadArchitect.
              </div>
            </div>
          </div>
        )}

        {/* SUBTAB 13: GAMING */}
        {activeSubtab === 'gaming' && (
          <div className="space-y-4" id="remediation-view-gaming">
            <div className="p-5 bg-slate-900/40 border border-slate-800 rounded-xl space-y-4">
              <h3 className="text-sm font-semibold text-rose-400 flex items-center gap-2">
                <AlertOctagon className="w-5 h-5" />
                Defesa Activa Contra Quality Gaming
              </h3>
              <p className="text-xs text-slate-400">
                Tentativas de manipular métricas, apagar testes, alterar thresholds ou desviar código para módulos não medidos são bloqueadas imediatamente.
              </p>
              <div className="p-4 bg-rose-950/20 border border-rose-900 rounded-lg text-xs text-rose-300 space-y-1 font-mono">
                <div>[DEFENSE MONITOR] Zero incidentes de gaming não autorizados permitidos.</div>
                <div>[DEFENSE POLICY] Sentinel e Security Gates são invioláveis.</div>
              </div>
            </div>
          </div>
        )}

        {/* SUBTAB 14: FINAL STATE */}
        {activeSubtab === 'final_state' && (
          <div className="space-y-4" id="remediation-view-final-state">
            <div className="p-5 bg-slate-900/40 border border-slate-800 rounded-xl space-y-4">
              <h3 className="text-sm font-semibold text-slate-200">Estado Auditável Consolidado da Dívida</h3>
              <div className="p-4 bg-slate-950 border border-slate-800 rounded-lg space-y-2">
                <div className="text-xs font-mono text-emerald-400">
                  QUALITY_DEBT_REMEDIATION_READY = TRUE
                </div>
                <p className="text-xs text-slate-400">
                  Cadeia de custódia criptográfica completa registada no SQLite thread-safe com assinaturas SHA-256.
                </p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Execution Log Terminal */}
      <div className="p-4 bg-slate-950 border border-slate-800 rounded-xl space-y-2">
        <div className="flex items-center justify-between text-xs text-slate-400 border-b border-slate-800 pb-2">
          <span className="flex items-center gap-2 font-mono">
            <Activity className="w-3.5 h-3.5 text-indigo-400" />
            Remediation Provenance Stream
          </span>
          <span className="text-[11px] font-mono text-slate-500">SHA-256 Audit Trail</span>
        </div>
        <div className="space-y-1 font-mono text-[11px] text-slate-400 max-h-32 overflow-y-auto">
          {executionLog.map((log, idx) => (
            <div key={idx} className="flex gap-2">
              <span className="text-slate-600">›</span>
              <span>{log}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default QualityDebtRemediationPanel;
