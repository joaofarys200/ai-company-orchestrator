import React, { useState } from 'react';
import {
  ShieldCheck,
  Award,
  AlertTriangle,
  Activity,
  GitMerge,
  Clock,
  Compass,
  CheckCircle2,
  Boxes,
  Layers,
  Sliders,
  BarChart2,
  Flame,
  UserCheck,
  Key,
} from 'lucide-react';

interface EngineeringQualityGovernancePanelProps {
  missionId?: string;
}

export const EngineeringQualityGovernancePanel: React.FC<EngineeringQualityGovernancePanelProps> = ({
  missionId = 'mission_f68_demo',
}) => {
  const [activeSubtab, setActiveSubtab] = useState<string>('overview');
  const [policy, setPolicy] = useState<string>('GOVERNED');
  const [gateStatus, setGateStatus] = useState<string>('QUALITY_ACCEPTED_WITH_DEBT');
  const [evidenceEfficiency] = useState<number>(0.84);
  const [evaluating, setEvaluating] = useState<boolean>(false);

  const subtabs = [
    { id: 'overview', label: '01. Overview', icon: Award, elementId: 'quality-subtab-overview' },
    { id: 'dimensions', label: '02. Dimensions', icon: Layers, elementId: 'quality-subtab-dimensions' },
    { id: 'baseline', label: '03. Baseline', icon: Clock, elementId: 'quality-subtab-baseline' },
    { id: 'comparison', label: '04. Comparison', icon: GitMerge, elementId: 'quality-subtab-comparison' },
    { id: 'debt', label: '05. Technical Debt', icon: Boxes, elementId: 'quality-subtab-debt' },
    { id: 'priority', label: '06. Debt Priority', icon: Sliders, elementId: 'quality-subtab-priority' },
    { id: 'gates', label: '07. Quality Gates', icon: ShieldCheck, elementId: 'quality-subtab-gates' },
    { id: 'regression', label: '08. Regression', icon: AlertTriangle, elementId: 'quality-subtab-regression' },
    { id: 'trend', label: '09. Trend', icon: BarChart2, elementId: 'quality-subtab-trend' },
    { id: 'hotspots', label: '10. Hotspots', icon: Flame, elementId: 'quality-subtab-hotspots' },
    { id: 'mission', label: '11. Mission Quality', icon: Compass, elementId: 'quality-subtab-mission' },
    { id: 'agent', label: '12. Agent Quality', icon: UserCheck, elementId: 'quality-subtab-agent' },
    { id: 'security', label: '13. Security Quality', icon: Key, elementId: 'quality-subtab-security' },
    { id: 'governance', label: '14. Final Governance', icon: CheckCircle2, elementId: 'quality-subtab-governance' },
  ];

  const dimensionsData = [
    { name: 'ARCHITECTURE', status: 'HEALTHY', coupling: '0.32', sccSize: 4, modularity: '0.74', uncertainty: '0.06' },
    { name: 'CODE', status: 'HEALTHY', complexity: '8.4', duplication: '1.8%', nesting: '2.3', uncertainty: '0.04' },
    { name: 'TEST', status: 'HEALTHY', coverage: '88.5%', mutation: '78.0%', flaky: '0.8%', uncertainty: '0.02' },
    { name: 'CONTRACT', status: 'HEALTHY', breaking: 0, drift: 0, consumerCov: '96.2%', uncertainty: '0.03' },
    { name: 'BEHAVIOR', status: 'HEALTHY', invariants: '84.0%', counterexamples: 0, explored: '72%', uncertainty: '0.28' },
    { name: 'SECURITY', status: 'HEALTHY', blockedOps: 0, secrets: 0, violations: 0, uncertainty: '0.001' },
    { name: 'PERFORMANCE', status: 'HEALTHY', p95: '42ms', throughput: '480 ops/s', cacheEff: '91%', uncertainty: '0.05' },
    { name: 'RELIABILITY', status: 'HEALTHY', recovery: '100%', stalls: 0, oscillations: 0, uncertainty: '0.02' },
    { name: 'MAINTAINABILITY', status: 'HEALTHY', testability: '86%', documentation: '92%', ripple: '20%', uncertainty: '0.05' },
  ];

  const debtItems = [
    { id: 'debt_arch_01', category: 'ARCHITECTURAL', surface: 'backend.memory <-> backend.indexing', severity: 'MEDIUM', risk: 0.65, status: 'OPEN', recurrence: 2 },
    { id: 'debt_code_02', category: 'CODE', surface: 'ProjectIndexer.condense_large_subgraphs', severity: 'MEDIUM', risk: 0.55, status: 'OPEN', recurrence: 2 },
    { id: 'debt_test_03', category: 'TEST', surface: 'test_websocket_heartbeat_flaky', severity: 'MEDIUM', risk: 0.60, status: 'OPEN', recurrence: 3 },
    { id: 'debt_op_04', category: 'OPERATIONAL', surface: 'mission_state_resync_staging', severity: 'HIGH', risk: 0.75, status: 'ACKNOWLEDGED', recurrence: 2 },
    { id: 'debt_perf_05', category: 'PERFORMANCE', surface: 'sqlite_in_memory_connection_pooling', severity: 'LOW', risk: 0.40, status: 'PLANNED', recurrence: 1 },
  ];

  return (
    <div className="flex h-full flex-col bg-[#0b1317] text-gray-200">
      {/* Header Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[#a1bebf]/15 bg-[#0d171b] px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-teal-500/10 text-teal-400 border border-teal-500/20">
            <Award className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-white">
                Engineering Quality Governance & Autonomous Quality Debt Management
              </h2>
              <span className="rounded bg-teal-500/20 px-2 py-0.5 text-xs font-semibold text-teal-300">
                FASE 68
              </span>
              <span className="flex items-center gap-1 rounded bg-emerald-500/20 px-2 py-0.5 text-xs font-semibold text-emerald-300">
                <ShieldCheck className="h-3 w-3" />
                ENGINEERING_QUALITY_GOVERNANCE_READY
              </span>
            </div>
            <p className="text-xs text-gray-400">
              Multidimensional quality observation, debt lifecycle governance, and empirical quality gate enforcement (Missão: {missionId}).
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-400">Política:</span>
            <select
              value={policy}
              onChange={(e) => setPolicy(e.target.value)}
              className="rounded border border-gray-700 bg-[#121e23] px-2.5 py-1 text-xs text-gray-200 focus:border-teal-500 focus:outline-none"
            >
              <option value="STRICT">STRICT (Zero Debt)</option>
              <option value="GOVERNED">GOVERNED (Balanced Budget)</option>
              <option value="LENIENT">LENIENT (Exploratory)</option>
              <option value="CRITICAL_ONLY">CRITICAL_ONLY</option>
            </select>
          </div>

          <button
            onClick={() => {
              setEvaluating(true);
              setTimeout(() => {
                setEvaluating(false);
                setGateStatus('QUALITY_ACCEPTED_WITH_DEBT');
              }, 400);
            }}
            disabled={evaluating}
            className="flex items-center gap-1.5 rounded bg-teal-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-teal-500 transition-colors disabled:opacity-50"
          >
            <Activity className={`h-3.5 w-3.5 ${evaluating ? 'animate-spin' : ''}`} />
            {evaluating ? 'Avaliando...' : 'Avaliar Gate'}
          </button>
        </div>
      </div>

      {/* Subtab Navigation Bar */}
      <div className="flex overflow-x-auto border-b border-[#a1bebf]/10 bg-[#080e11] px-6 py-2 gap-1.5 scrollbar-thin">
        {subtabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeSubtab === tab.id;
          return (
            <button
              key={tab.id}
              id={tab.elementId}
              onClick={() => setActiveSubtab(tab.id)}
              className={`flex items-center gap-1.5 whitespace-nowrap rounded px-3 py-1.5 text-xs font-medium transition-colors ${
                isActive
                  ? 'bg-teal-500/20 text-teal-300 border border-teal-500/30'
                  : 'text-gray-400 hover:bg-[#121e23] hover:text-gray-200 border border-transparent'
              }`}
            >
              <Icon className="h-3.5 w-3.5" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Subtab Content Area */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* SUBTAB 01: OVERVIEW */}
        {activeSubtab === 'overview' && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="rounded-lg border border-teal-500/20 bg-[#0d171b] p-4">
                <div className="text-xs font-semibold uppercase tracking-wider text-teal-400">Decisão do Gate</div>
                <div className="mt-1 text-lg font-bold text-white">{gateStatus}</div>
                <div className="mt-1 text-xs text-gray-400">Escopo global • Política {policy}</div>
              </div>
              <div className="rounded-lg border border-teal-500/20 bg-[#0d171b] p-4">
                <div className="text-xs font-semibold uppercase tracking-wider text-teal-400">Eficiência de Evidência</div>
                <div className="mt-1 text-lg font-bold text-emerald-400">{(evidenceEfficiency * 100).toFixed(1)}%</div>
                <div className="mt-1 text-xs text-gray-400">MORE_TESTS vs MORE_USEFUL_EVIDENCE</div>
              </div>
              <div className="rounded-lg border border-teal-500/20 bg-[#0d171b] p-4">
                <div className="text-xs font-semibold uppercase tracking-wider text-teal-400">Dívida Técnica Ativa</div>
                <div className="mt-1 text-lg font-bold text-amber-400">{debtItems.length} Itens</div>
                <div className="mt-1 text-xs text-gray-400">0 Críticos • 1 Alto • 3 Médios</div>
              </div>
              <div className="rounded-lg border border-teal-500/20 bg-[#0d171b] p-4">
                <div className="text-xs font-semibold uppercase tracking-wider text-teal-400">Princípio Central</div>
                <div className="mt-1 text-xs font-mono text-emerald-300">MISSION_COMPLETED != QUALITY_IMPROVED</div>
                <div className="mt-0.5 text-xs font-mono text-cyan-300">QUALITY_SCORE != SINGLE_NUMBER_AUTHORITY</div>
              </div>
            </div>

            <div className="rounded-lg border border-[#a1bebf]/15 bg-[#0d171b] p-5 space-y-4">
              <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                <Layers className="h-4 w-4 text-teal-400" />
                Matriz Multidimensional de Governação (9 Dimensões)
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {dimensionsData.map((d) => (
                  <div key={d.name} className="rounded border border-gray-800 bg-[#121e23] p-3">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-white">{d.name}</span>
                      <span className="rounded bg-emerald-500/20 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-300">
                        {d.status}
                      </span>
                    </div>
                    <div className="mt-2 text-xs text-gray-400">Incerteza: {d.uncertainty}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* SUBTAB 02: DIMENSIONS */}
        {activeSubtab === 'dimensions' && (
          <div className="space-y-4">
            <h3 className="text-sm font-bold text-white">Avaliação Detalhada por Dimensão Observável</h3>
            <div className="space-y-3">
              {dimensionsData.map((d) => (
                <div key={d.name} className="rounded-lg border border-[#a1bebf]/15 bg-[#0d171b] p-4">
                  <div className="flex items-center justify-between border-b border-gray-800 pb-2 mb-3">
                    <span className="text-sm font-bold text-teal-300">{d.name}</span>
                    <span className="rounded bg-emerald-500/20 px-2 py-0.5 text-xs font-bold text-emerald-300">{d.status}</span>
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
                    <div><span className="text-gray-400">Incerteza:</span> <span className="font-mono text-white">{d.uncertainty}</span></div>
                    <div><span className="text-gray-400">Escopo:</span> <span className="font-mono text-white">global</span></div>
                    <div><span className="text-gray-400">Tipo:</span> <span className="font-mono text-white">OBSERVED</span></div>
                    <div><span className="text-gray-400">Evidência:</span> <span className="text-emerald-400">Verificada</span></div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* SUBTAB 03: BASELINE */}
        {activeSubtab === 'baseline' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-white">QUALITY_BASELINE (Imutável & Selada)</h3>
              <span className="text-xs font-mono text-teal-400">SHA-256: 7f8a91b...c40e</span>
            </div>
            <div className="rounded-lg border border-[#a1bebf]/15 bg-[#0d171b] p-5 space-y-3 text-xs">
              <p className="text-gray-300">
                Capturada de forma imutável antes da execução da missão. Serve de âncora factual para comparação Before/After.
              </p>
              <div className="grid grid-cols-2 gap-4 pt-2">
                <div className="rounded bg-[#121e23] p-3 border border-gray-800">
                  <span className="text-gray-400">Architecture Hash:</span>
                  <div className="font-mono text-white mt-1">arch_baseline_991b</div>
                </div>
                <div className="rounded bg-[#121e23] p-3 border border-gray-800">
                  <span className="text-gray-400">Contract Hash:</span>
                  <div className="font-mono text-white mt-1">contract_baseline_102a</div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* SUBTAB 04: COMPARISON */}
        {activeSubtab === 'comparison' && (
          <div className="space-y-4">
            <h3 className="text-sm font-bold text-white">Comparação BEFORE vs AFTER</h3>
            <div className="rounded-lg border border-[#a1bebf]/15 bg-[#0d171b] p-5 space-y-3 text-xs">
              <div className="grid grid-cols-3 gap-4 border-b border-gray-800 pb-3">
                <div className="text-gray-400 font-semibold">Dimensão</div>
                <div className="text-gray-400 font-semibold">Mudança</div>
                <div className="text-gray-400 font-semibold">Evidência</div>
              </div>
              {dimensionsData.map((d) => (
                <div key={d.name} className="grid grid-cols-3 gap-4 items-center">
                  <span className="font-mono text-white">{d.name}</span>
                  <span className="rounded bg-teal-500/20 px-2 py-0.5 text-xs text-teal-300 font-semibold w-fit">
                    UNCHANGED
                  </span>
                  <span className="text-gray-400">Dentro da incerteza de medição</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* SUBTAB 05: TECHNICAL DEBT */}
        {activeSubtab === 'debt' && (
          <div className="space-y-4">
            <h3 className="text-sm font-bold text-white">Itens de Dívida Técnica Governados</h3>
            <div className="space-y-2">
              {debtItems.map((item) => (
                <div key={item.id} className="rounded border border-gray-800 bg-[#0d171b] p-3 text-xs flex justify-between items-center">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-teal-300 font-bold">{item.id}</span>
                      <span className="rounded bg-gray-800 px-1.5 py-0.5 text-[10px] text-gray-300">{item.category}</span>
                      <span className="text-amber-400 font-semibold">{item.severity}</span>
                    </div>
                    <div className="text-gray-400 mt-1">{item.surface} (Recorrência: {item.recurrence}x)</div>
                  </div>
                  <div className="text-right">
                    <span className="rounded bg-blue-500/20 text-blue-300 px-2 py-0.5 font-mono">{item.status}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* SUBTAB 06: DEBT PRIORITY */}
        {activeSubtab === 'priority' && (
          <div className="space-y-4">
            <h3 className="text-sm font-bold text-white">Prioritização Multi-Critério (PRIORITY_VECTOR)</h3>
            <div className="rounded-lg border border-[#a1bebf]/15 bg-[#0d171b] p-5 space-y-3 text-xs">
              <p className="text-gray-300">
                A priorização avalia: risco, impacto, recorrência, custo de remediação, missões afetadas, relevância de segurança e reversibilidade.
              </p>
              {debtItems.map((item, idx) => (
                <div key={item.id} className="rounded bg-[#121e23] p-3 border border-gray-800 space-y-1">
                  <div className="flex justify-between">
                    <span className="font-bold text-white">Rank #{idx + 1} — {item.id}</span>
                    <span className="text-teal-400 font-mono">Risk: {item.risk}</span>
                  </div>
                  <p className="text-gray-400">
                    Prioridade calculada com base no vetor multi-atributo sem redução a score autoritário único.
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* SUBTAB 07: QUALITY GATES */}
        {activeSubtab === 'gates' && (
          <div className="space-y-4">
            <h3 className="text-sm font-bold text-white">Quality Gate: {gateStatus}</h3>
            <div className="rounded-lg border border-[#a1bebf]/15 bg-[#0d171b] p-5 space-y-3 text-xs">
              <div className="flex items-center gap-2 text-emerald-400 font-bold">
                <CheckCircle2 className="h-4 w-4" />
                Nenhuma regressão crítica de segurança ou degradação de arquitetura detectada.
              </div>
              <p className="text-gray-300">
                Decisão fundamentada: Aceite com Dívida Governada ({debtItems.length} itens registrados no catálogo com plano de amortização).
              </p>
            </div>
          </div>
        )}

        {/* SUBTAB 08: REGRESSION */}
        {activeSubtab === 'regression' && (
          <div className="space-y-4">
            <h3 className="text-sm font-bold text-white">Detecção de Regressão de Qualidade</h3>
            <div className="rounded-lg border border-[#a1bebf]/15 bg-[#0d171b] p-5 space-y-3 text-xs">
              <div className="rounded bg-emerald-500/10 border border-emerald-500/20 p-3 text-emerald-300">
                Nenhuma regressão empírica fora da incerteza de medição detectada no ciclo corrente.
              </div>
              <p className="text-gray-400">
                Regressões são classificadas como: CRITICAL, SIGNIFICANT, MINOR ou UNCERTAIN.
              </p>
            </div>
          </div>
        )}

        {/* SUBTAB 09: TREND */}
        {activeSubtab === 'trend' && (
          <div className="space-y-4">
            <h3 className="text-sm font-bold text-white">Tendência Histórica de Qualidade</h3>
            <div className="rounded-lg border border-[#a1bebf]/15 bg-[#0d171b] p-5 space-y-3 text-xs">
              <div className="flex items-center gap-2">
                <span className="text-gray-400">Classificação:</span>
                <span className="font-bold text-teal-300">STABLE (Estável com amortização progressiva)</span>
              </div>
              <p className="text-gray-400">
                Histórico consolidado através de múltiplas snapshots temporais T1..Tn.
              </p>
            </div>
          </div>
        )}

        {/* SUBTAB 10: HOTSPOTS */}
        {activeSubtab === 'hotspots' && (
          <div className="space-y-4">
            <h3 className="text-sm font-bold text-white">Hotspots de Qualidade Identificados</h3>
            <div className="rounded-lg border border-[#a1bebf]/15 bg-[#0d171b] p-5 space-y-2 text-xs">
              <div className="rounded bg-[#121e23] p-3 border border-gray-800 flex justify-between">
                <div>
                  <span className="font-bold text-white">backend.memory.partitioning</span>
                  <div className="text-gray-400">Concentração de alterações e verificações</div>
                </div>
                <span className="text-amber-400 font-mono">Risk Weight: 4.5</span>
              </div>
            </div>
          </div>
        )}

        {/* SUBTAB 11: MISSION QUALITY */}
        {activeSubtab === 'mission' && (
          <div className="space-y-4">
            <h3 className="text-sm font-bold text-white">Governação por Missão (F67 Integration)</h3>
            <div className="rounded-lg border border-[#a1bebf]/15 bg-[#0d171b] p-5 space-y-3 text-xs">
              <div className="flex items-center gap-2">
                <span className="text-gray-400">Estado da Missão:</span>
                <span className="rounded bg-teal-500/20 text-teal-300 font-bold px-2 py-0.5">
                  COMPLETED_WITH_QUALITY_DEBT
                </span>
              </div>
              <p className="text-gray-300">
                Objetivo funcional concluído com êxito sem pretender falsamente que a dívida acumulada é zero.
              </p>
            </div>
          </div>
        )}

        {/* SUBTAB 12: AGENT QUALITY */}
        {activeSubtab === 'agent' && (
          <div className="space-y-4">
            <h3 className="text-sm font-bold text-white">Qualidade Multi-Agente (F66 Integration)</h3>
            <div className="rounded-lg border border-[#a1bebf]/15 bg-[#0d171b] p-5 space-y-3 text-xs">
              <p className="text-gray-300">
                Métricas agregadas por agente, intent e merge. Nenhuma inferência de agente fraco a partir de falha isolada.
              </p>
            </div>
          </div>
        )}

        {/* SUBTAB 13: SECURITY QUALITY */}
        {activeSubtab === 'security' && (
          <div className="space-y-4">
            <h3 className="text-sm font-bold text-white">Qualidade de Segurança & Sentinel Guardrails</h3>
            <div className="rounded-lg border border-[#a1bebf]/15 bg-[#0d171b] p-5 space-y-3 text-xs">
              <div className="rounded bg-emerald-500/10 border border-emerald-500/20 p-3 text-emerald-300">
                Sentinel Ativo • Zero tentativas de exposição de segredos • Sandbox íntegro.
              </div>
              <p className="text-gray-400">
                Regra Inviolável: Qualquer regressão crítica de segurança bloqueia o Quality Gate imediatamente.
              </p>
            </div>
          </div>
        )}

        {/* SUBTAB 14: FINAL GOVERNANCE */}
        {activeSubtab === 'governance' && (
          <div className="space-y-4">
            <h3 className="text-sm font-bold text-white">Governação Final de Qualidade de Engenharia</h3>
            <div className="rounded-lg border border-emerald-500/20 bg-[#0d171b] p-5 space-y-3 text-xs">
              <div className="flex items-center gap-2 text-emerald-400 font-bold text-sm">
                <ShieldCheck className="h-5 w-5" />
                ENGINEERING_QUALITY_GOVERNANCE_READY = TRUE
              </div>
              <p className="text-gray-300">
                A camada transversal de governança de qualidade de engenharia está ativa, operando sem score único reducionista e governando o ciclo de vida completo de dívida técnica.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
