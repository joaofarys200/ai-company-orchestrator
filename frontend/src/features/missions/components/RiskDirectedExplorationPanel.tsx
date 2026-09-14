import React, { useState } from 'react';
import {
  Crosshair,
  CheckCircle2,
  Search,
  Network,
  BarChart3,
  Sliders,
  ShieldCheck,
  Flame,
  Zap,
  TrendingDown,
  FastForward,
  Lock,
  Sparkles,
} from 'lucide-react';

export interface RiskDirectedExplorationPanelProps {
  missionId?: string;
  onGateAction?: (action: string) => void;
}

export const FALLBACK_RISK_EXPLORATION_DATA = {
  migration_id: 'mig_risk_directed_01',
  contract_id: 'economicDisbursementContract',
  scope_id: 'scp_adapt_7c2b9a4e',
  policy: 'ECONOMIC_CRITICAL',
  seed: 42,
  decision_gate_status: 'RISK_DIRECTED_BEHAVIORAL_EXPLORATION_READY',
  proof_result: 'PROVEN_COMPATIBLE_WITHIN_SCOPE',
  gate_decision: 'GATE_CLEARED',
  confidence: 1.0,
  initial_risk_score: 0.865,
  current_risk_score: 0.142,
  initial_uncertainty_score: 0.780,
  current_uncertainty_score: 0.115,
  efficiency: {
    scenarios_ranked: 85,
    scenarios_executed: 24,
    scenarios_skipped: 61,
    budget_saved_pct: 71.8,
    scenario_efficiency: 0.030125,
    time_saved_sec: 3.85,
  },
  risk_dimensions: [
    { name: 'Economic Value Drift', value: 0.95, level: 'CRITICAL', color: 'text-rose-400' },
    { name: 'Security & Auth State', value: 0.90, level: 'CRITICAL', color: 'text-rose-400' },
    { name: 'Dynamic Consumer Inconsistency', value: 0.65, level: 'ELEVATED', color: 'text-amber-400' },
    { name: 'Change Magnitude', value: 0.50, level: 'MODERATE', color: 'text-cyan-400' },
    { name: 'Blast Radius', value: 0.80, level: 'HIGH', color: 'text-amber-400' },
    { name: 'Historical Failure Rate', value: 0.40, level: 'MODERATE', color: 'text-cyan-400' },
    { name: 'Coverage Gap', value: 0.15, level: 'LOW', color: 'text-emerald-400' },
    { name: 'Contract Structural Delta', value: 0.30, level: 'LOW', color: 'text-emerald-400' },
  ],
  uncertainty_dimensions: [
    { source: 'Uncertain Consumer', score: 0.10, status: 'RESOLVED' },
    { source: 'Unknown Polymorphic Variant', score: 0.05, status: 'RESOLVED' },
    { source: 'Unexplored Error Branch', score: 0.08, status: 'BOUNDED' },
    { source: 'Concurrency Interleaving Gap', score: 0.12, status: 'EXPLICIT_BOUND' },
  ],
  ranked_queue: [
    {
      rank: 1,
      scenario_id: 'scen_econ_auth_boundary',
      target: 'authorization_failure',
      priority: 3.845,
      information_value: 0.92,
      risk_component: 'Security/Auth',
      status: 'EXECUTED_PASSED',
      policy_override: true,
      explanation: 'Mandatory Economic Critical scenario: tests caller authorization downgrade and invalid tokens',
    },
    {
      rank: 2,
      scenario_id: 'scen_econ_zero_amount',
      target: 'boundary_amount_0',
      priority: 3.720,
      information_value: 0.89,
      risk_component: 'Economic Boundary',
      status: 'EXECUTED_PASSED',
      policy_override: true,
      explanation: 'Mandatory boundary: amount=0.0 rejects with 400 Bad Request and zero balance debit',
    },
    {
      rank: 3,
      scenario_id: 'scen_econ_currency_mismatch',
      target: 'currency_substitution',
      priority: 3.510,
      information_value: 0.86,
      risk_component: 'Economic Invariant',
      status: 'EXECUTED_PASSED',
      policy_override: true,
      explanation: 'Currency substitution EUR -> USD must trigger explicit conversion or contract failure',
    },
    {
      rank: 4,
      scenario_id: 'scen_econ_retry_idempotent',
      target: 'retry_idempotency',
      priority: 3.420,
      information_value: 0.84,
      risk_component: 'Flow/Idempotency',
      status: 'EXECUTED_PASSED',
      policy_override: true,
      explanation: 'Repeated transaction with same idempotency_key must deduplicate side-effects',
    },
    {
      rank: 5,
      scenario_id: 'scen_econ_gateway_timeout',
      target: 'timeout_recovery',
      priority: 3.150,
      information_value: 0.78,
      risk_component: 'Timing/Failure',
      status: 'EXECUTED_PASSED',
      policy_override: true,
      explanation: '504 Gateway Timeout triggers clean compensation rollback in persistence ledger',
    },
    {
      rank: 6,
      scenario_id: 'scen_low_risk_cosmetic_desc',
      target: 'optional_note_omitted',
      priority: 0.210,
      information_value: 0.12,
      risk_component: 'Cosmetic Schema',
      status: 'SKIPPED_BUDGET_SAVED',
      policy_override: false,
      explanation: 'Low information value: negligible risk and 0% impact on behavioral invariants',
    },
  ],
  mandatory_safety_set: [
    { target: 'Authorization Matrix', status: 'VERIFIED', icon: 'Lock' },
    { target: 'Amount Boundaries (0, -1, Max)', status: 'VERIFIED', icon: 'Percent' },
    { target: 'Currency Preservation', status: 'VERIFIED', icon: 'CheckCircle2' },
    { target: 'Idempotency & Retry Deduplication', status: 'VERIFIED', icon: 'RotateCcw' },
    { target: 'Timeout & Failure Rollback', status: 'VERIFIED', icon: 'ShieldCheck' },
  ],
};

export const RiskDirectedExplorationPanel: React.FC<RiskDirectedExplorationPanelProps> = (_props) => {
  void _props;
  const [data, setData] = useState(FALLBACK_RISK_EXPLORATION_DATA);
  const [selectedTab, setSelectedTab] = useState<'overview' | 'queue' | 'adaptive_loop' | 'feedback' | 'safety'>('overview');
  const [activeStep, setActiveStep] = useState<number>(4);
  const [filterPolicy, setFilterPolicy] = useState<string>('ECONOMIC_CRITICAL');
  const [searchQuery, setSearchQuery] = useState<string>('');

  const filteredQueue = data.ranked_queue.filter((q) => {
    if (searchQuery && !q.scenario_id.includes(searchQuery) && !q.target.includes(searchQuery)) {
      return false;
    }
    return true;
  });

  const handleStepSimulation = () => {
    setActiveStep((prev) => (prev % 5) + 1);
    setData((prev) => ({
      ...prev,
      current_risk_score: Math.max(0.05, prev.current_risk_score - 0.02),
      current_uncertainty_score: Math.max(0.04, prev.current_uncertainty_score - 0.015),
    }));
  };

  return (
    <div className="space-y-6 pb-12 text-slate-200" id="risk-directed-exploration-panel">
      {/* 1. TOP HEADER & RISK SCOPE BANNER */}
      <div className="relative overflow-hidden rounded-xl border border-amber-500/30 bg-[#0e141a]/95 p-6 shadow-2xl backdrop-blur-md">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-3">
              <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-amber-500/10 text-amber-400 ring-1 ring-amber-500/30">
                <Crosshair className="h-5 w-5" />
              </span>
              <h2 className="text-lg font-bold tracking-tight text-white">
                Fase 52 — Risk-Directed Behavioral Exploration & Adaptive Proof Search
              </h2>
              <span
                id="badge-proof-outcome"
                className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-0.5 text-xs font-semibold text-emerald-300"
              >
                {data.proof_result}
              </span>
              <span
                id="badge-decision-gate"
                className="rounded-full border border-amber-500/30 bg-amber-500/10 px-3 py-0.5 text-xs font-semibold text-amber-300"
              >
                {data.decision_gate_status}
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Exploração comportamental inteligente guiada por risco, incerteza e valor de informação. Re-ranqueamento adaptativo contínuo mitigando a explosão de espaço de estados.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              id="btn-run-adaptive-step"
              onClick={handleStepSimulation}
              className="flex items-center gap-2 rounded-lg border border-amber-500/40 bg-amber-500/10 px-3.5 py-2 text-xs font-medium text-amber-200 hover:bg-amber-500/20 transition-all shadow-sm"
            >
              <FastForward className="h-3.5 w-3.5 text-amber-400" />
              Executar Ciclo Adaptativo
            </button>
          </div>
        </div>

        {/* METRICS STRIP */}
        <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-3">
            <span className="text-[11px] font-medium text-slate-400">Risk Score Residual</span>
            <div className="mt-1 flex items-baseline gap-1.5">
              <span id="metric-risk-score" className="text-base font-bold text-amber-400 font-mono">
                {data.current_risk_score.toFixed(3)}
              </span>
              <span className="text-[10px] text-emerald-400 flex items-center font-mono">
                <TrendingDown className="h-3 w-3 mr-0.5" /> -{((data.initial_risk_score - data.current_risk_score) * 100).toFixed(0)}%
              </span>
            </div>
          </div>

          <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-3">
            <span className="text-[11px] font-medium text-slate-400">Incerteza Residual</span>
            <div className="mt-1 flex items-baseline gap-1.5">
              <span id="metric-uncertainty-score" className="text-base font-bold text-purple-400 font-mono">
                {data.current_uncertainty_score.toFixed(3)}
              </span>
              <span className="text-[10px] text-emerald-400 flex items-center font-mono">
                <TrendingDown className="h-3 w-3 mr-0.5" /> -{((data.initial_uncertainty_score - data.current_uncertainty_score) * 100).toFixed(0)}%
              </span>
            </div>
          </div>

          <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-3">
            <span className="text-[11px] font-medium text-slate-400">Cenários Executados</span>
            <div className="mt-1 font-mono text-xs font-semibold text-slate-200">
              <span className="text-cyan-300 font-bold">{data.efficiency.scenarios_executed}</span> / {data.efficiency.scenarios_ranked}
            </div>
          </div>

          <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-3">
            <span className="text-[11px] font-medium text-slate-400">Cenários Evitados (Skipped)</span>
            <div className="mt-1 flex items-baseline gap-1.5">
              <span className="text-base font-bold text-emerald-400 font-mono">
                {data.efficiency.scenarios_skipped}
              </span>
              <span className="text-[10px] text-slate-400 font-mono">({data.efficiency.budget_saved_pct}%)</span>
            </div>
          </div>

          <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-3">
            <span className="text-[11px] font-medium text-slate-400">Eficiência de Evidência</span>
            <div className="mt-1 font-mono text-xs font-semibold text-emerald-400" id="metric-scenario-efficiency">
              {data.efficiency.scenario_efficiency.toFixed(5)} dR/$
            </div>
          </div>

          <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-3">
            <span className="text-[11px] font-medium text-slate-400">Política Ativa</span>
            <div className="mt-1 flex items-center gap-1.5 text-xs font-semibold text-amber-300">
              <Lock className="h-3 w-3 text-amber-400" />
              {data.policy}
            </div>
          </div>
        </div>
      </div>

      {/* 2. SUB-NAVIGATION TABS */}
      <div className="flex border-b border-slate-800 text-xs font-medium">
        <button
          id="tab-btn-overview"
          onClick={() => setSelectedTab('overview')}
          className={`flex items-center gap-2 border-b-2 px-4 py-2.5 transition-colors ${
            selectedTab === 'overview'
              ? 'border-amber-400 text-amber-300 bg-amber-500/5'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <BarChart3 className="h-3.5 w-3.5" />
          Perfil de Risco & Incerteza (11D)
        </button>
        <button
          id="tab-btn-queue"
          onClick={() => setSelectedTab('queue')}
          className={`flex items-center gap-2 border-b-2 px-4 py-2.5 transition-colors ${
            selectedTab === 'queue'
              ? 'border-amber-400 text-amber-300 bg-amber-500/5'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <Crosshair className="h-3.5 w-3.5" />
          Fila Priorizada & Valor de Informação
        </button>
        <button
          id="tab-btn-adaptive-loop"
          onClick={() => setSelectedTab('adaptive_loop')}
          className={`flex items-center gap-2 border-b-2 px-4 py-2.5 transition-colors ${
            selectedTab === 'adaptive_loop'
              ? 'border-amber-400 text-amber-300 bg-amber-500/5'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <Zap className="h-3.5 w-3.5 text-amber-400" />
          Ciclo Adaptativo (Select → Re-Rank)
        </button>
        <button
          id="tab-btn-feedback"
          onClick={() => setSelectedTab('feedback')}
          className={`flex items-center gap-2 border-b-2 px-4 py-2.5 transition-colors ${
            selectedTab === 'feedback'
              ? 'border-amber-400 text-amber-300 bg-amber-500/5'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <Network className="h-3.5 w-3.5" />
          Feedback & Grafo de Cenários
        </button>
        <button
          id="tab-btn-safety"
          onClick={() => setSelectedTab('safety')}
          className={`flex items-center gap-2 border-b-2 px-4 py-2.5 transition-colors ${
            selectedTab === 'safety'
              ? 'border-amber-400 text-amber-300 bg-amber-500/5'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" />
          Conjunto Mínimo Obrigatório de Segurança
        </button>
      </div>

      {/* 3. TAB CONTENTS */}
      {/* TAB: OVERVIEW & 11D BREAKDOWN */}
      {selectedTab === 'overview' && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {/* RISK BREAKDOWN */}
          <div className="rounded-xl border border-slate-800 bg-[#0e171f]/80 p-5 shadow-lg">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="flex items-center gap-2 text-sm font-semibold text-white">
                <Flame className="h-4 w-4 text-amber-400" />
                Decomposição Transparente de Risco (11 Dimensões)
              </h3>
              <span className="rounded bg-slate-800 px-2 py-0.5 text-[11px] font-mono text-amber-300">
                AUDIT-READY (NO BLACK BOX)
              </span>
            </div>

            <div className="mt-4 space-y-3">
              {data.risk_dimensions.map((dim, idx) => (
                <div key={idx} className="rounded-lg border border-slate-800/80 bg-slate-900/50 p-2.5">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-slate-300 font-medium">{dim.name}</span>
                    <span className={`font-mono font-bold ${dim.color}`}>
                      {(dim.value * 100).toFixed(0)}% ({dim.level})
                    </span>
                  </div>
                  <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-slate-800">
                    <div
                      className={`h-full rounded-full ${
                        dim.value >= 0.8 ? 'bg-rose-500' : dim.value >= 0.5 ? 'bg-amber-400' : 'bg-emerald-400'
                      }`}
                      style={{ width: `${dim.value * 100}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* UNCERTAINTY & RISK-ADAPTIVE BUDGET */}
          <div className="space-y-6">
            <div className="rounded-xl border border-slate-800 bg-[#0e171f]/80 p-5 shadow-lg">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <h3 className="flex items-center gap-2 text-sm font-semibold text-white">
                  <Sliders className="h-4 w-4 text-purple-400" />
                  Fontes Contínuas de Incerteza Comportamental
                </h3>
                <span className="rounded bg-purple-500/10 px-2 py-0.5 text-[11px] font-mono text-purple-300">
                  SCORE: {data.current_uncertainty_score.toFixed(3)}
                </span>
              </div>

              <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
                {data.uncertainty_dimensions.map((u, idx) => (
                  <div key={idx} className="rounded-lg border border-slate-800/80 bg-slate-900/50 p-3">
                    <div className="text-xs text-slate-300 font-medium">{u.source}</div>
                    <div className="mt-1 flex items-baseline justify-between">
                      <span className="text-xs font-mono font-bold text-purple-300">
                        {(u.score * 100).toFixed(1)}%
                      </span>
                      <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] font-mono text-emerald-400">
                        {u.status}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-5 shadow-lg">
              <div className="flex items-center gap-2 text-sm font-bold text-emerald-300">
                <Sparkles className="h-4 w-4 text-emerald-400" />
                Ganhos de Eficiência contra State-Space Explosion
              </div>
              <p className="mt-2 text-xs text-slate-300 leading-relaxed">
                Em vez de executar uniformemente todos os 85 cenários sintéticos, a Fase 52 direcionou a exploração aos 24 cenários de maior risco e valor de informação, economizando <strong>71.8% do budget</strong> de computação e emitindo a prova em apenas <strong>14.2ms</strong>.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* TAB: RANKED QUEUE */}
      {selectedTab === 'queue' && (
        <div className="space-y-6">
          <div className="rounded-xl border border-slate-800 bg-[#0e171f]/80 p-5 shadow-lg">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-3">
              <div>
                <h3 className="text-sm font-semibold text-white">Fila de Cenários Ranqueados por Prioridade</h3>
                <p className="text-xs text-slate-400">
                  Fórmula: priority = risk × information_value × uncertainty_reduction × impact_weight
                </p>
              </div>

              <div className="flex items-center gap-2">
                <select
                  id="select-policy-filter"
                  value={filterPolicy}
                  onChange={(e) => setFilterPolicy(e.target.value)}
                  className="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-amber-300 focus:outline-none"
                >
                  <option value="ECONOMIC_CRITICAL">ECONOMIC_CRITICAL</option>
                  <option value="SECURITY_CRITICAL">SECURITY_CRITICAL</option>
                  <option value="CRITICAL">CRITICAL</option>
                  <option value="STRICT">STRICT</option>
                  <option value="STANDARD">STANDARD</option>
                </select>

                <div className="flex items-center gap-1.5 rounded border border-slate-700 bg-slate-900 px-2.5 py-1">
                  <Search className="h-3.5 w-3.5 text-slate-400" />
                  <input
                    id="input-priority-search"
                    type="text"
                    placeholder="Filtrar cenários..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="bg-transparent text-xs text-slate-200 focus:outline-none w-32 sm:w-44"
                  />
                </div>
              </div>
            </div>

            <div className="mt-4 divide-y divide-slate-800/60 overflow-hidden rounded-lg border border-slate-800 bg-slate-900/40">
              {filteredQueue.map((item) => (
                <div key={item.scenario_id} className="p-4 hover:bg-slate-800/30 transition-colors">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2.5">
                      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-slate-800 text-xs font-mono font-bold text-cyan-300">
                        #{item.rank}
                      </span>
                      <span className="font-mono text-xs font-bold text-slate-200">{item.scenario_id}</span>
                      {item.policy_override && (
                        <span className="rounded bg-rose-500/10 border border-rose-500/30 px-2 py-0.5 text-[10px] font-semibold text-rose-300">
                          MANDATORY OVERRIDE
                        </span>
                      )}
                      <span className="rounded bg-slate-800 px-2 py-0.5 text-[10px] font-mono text-slate-400">
                        {item.risk_component}
                      </span>
                    </div>

                    <div className="flex items-center gap-3">
                      <span className="text-xs font-mono text-slate-400">
                        InfoVal: <strong className="text-cyan-300">{item.information_value}</strong>
                      </span>
                      <span className="rounded-full bg-amber-500/10 border border-amber-500/30 px-2.5 py-0.5 font-mono text-xs font-bold text-amber-300">
                        P = {item.priority.toFixed(3)}
                      </span>
                    </div>
                  </div>

                  <p className="mt-2 text-xs text-slate-400 leading-relaxed font-sans">
                    {item.explanation}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* TAB: ADAPTIVE LOOP */}
      {selectedTab === 'adaptive_loop' && (
        <div className="space-y-6">
          <div className="rounded-xl border border-slate-800 bg-[#0e171f]/80 p-5 shadow-lg">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="flex items-center gap-2 text-sm font-semibold text-white">
                <Zap className="h-4 w-4 text-amber-400" />
                Ciclo de Exploração Adaptativa (State Machine)
              </h3>
              <span className="text-xs font-mono text-cyan-300">
                ETAPA {activeStep} / 5 ATIVA
              </span>
            </div>

            <div className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-5 text-center text-xs">
              <div className={`rounded-lg border p-3 ${activeStep === 1 ? 'border-cyan-400 bg-cyan-500/10 text-cyan-200 ring-1 ring-cyan-400' : 'border-slate-800 bg-slate-900/50 text-slate-400'}`}>
                <div className="font-bold">1. SELECT</div>
                <div className="text-[10px] mt-1">Topo do ranking</div>
              </div>
              <div className={`rounded-lg border p-3 ${activeStep === 2 ? 'border-cyan-400 bg-cyan-500/10 text-cyan-200 ring-1 ring-cyan-400' : 'border-slate-800 bg-slate-900/50 text-slate-400'}`}>
                <div className="font-bold">2. EXECUTE</div>
                <div className="text-[10px] mt-1">Sandbox isolado</div>
              </div>
              <div className={`rounded-lg border p-3 ${activeStep === 3 ? 'border-cyan-400 bg-cyan-500/10 text-cyan-200 ring-1 ring-cyan-400' : 'border-slate-800 bg-slate-900/50 text-slate-400'}`}>
                <div className="font-bold">3. OBSERVE</div>
                <div className="text-[10px] mt-1">Traço & invariantes</div>
              </div>
              <div className={`rounded-lg border p-3 ${activeStep === 4 ? 'border-amber-400 bg-amber-500/10 text-amber-200 ring-1 ring-amber-400' : 'border-slate-800 bg-slate-900/50 text-slate-400'}`}>
                <div className="font-bold">4. UPDATE</div>
                <div className="text-[10px] mt-1">Risco & Cobertura</div>
              </div>
              <div className={`rounded-lg border p-3 ${activeStep === 5 ? 'border-emerald-400 bg-emerald-500/10 text-emerald-200 ring-1 ring-emerald-400' : 'border-slate-800 bg-slate-900/50 text-slate-400'}`}>
                <div className="font-bold">5. RE-RANK</div>
                <div className="text-[10px] mt-1">Repriorização dinâmica</div>
              </div>
            </div>

            <div className="mt-6 rounded-lg border border-slate-800 bg-slate-950 p-4 font-mono text-xs text-slate-300">
              <div className="text-cyan-300 font-bold mb-1">[ADAPTIVE LOOP TELEMETRY]</div>
              <div>Cenário Selecionado: scen_econ_currency_mismatch | Target: currency_substitution</div>
              <div>Resultado: SUCCESS (200 OK) | Divergência: ZERO | Negative Evidence Registrada</div>
              <div>Atualização de Cobertura: 85.0% → 88.5% (+3.5%)</div>
              <div>Ajuste Dinâmico: Economic Risk 0.95 $\to$ 0.85 | Residual Risk: 0.142</div>
              <div className="text-emerald-400 mt-1">Re-Ranking concluído: 61 cenários cosméticos mantidos em baixa prioridade</div>
            </div>
          </div>
        </div>
      )}

      {/* TAB: FEEDBACK & SCENARIO GRAPH */}
      {selectedTab === 'feedback' && (
        <div className="space-y-6">
          <div className="rounded-xl border border-slate-800 bg-[#0e171f]/80 p-5 shadow-lg">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="flex items-center gap-2 text-sm font-semibold text-white">
                <Network className="h-4 w-4 text-cyan-400" />
                Grafo de Relações de Cenários & Feedback de Contra-Exemplo
              </h3>
              <span className="rounded bg-slate-800 px-2 py-0.5 text-[11px] font-mono text-slate-300">
                TOPOLOGICAL CLUSTER
              </span>
            </div>

            <p className="mt-3 text-xs text-slate-400">
              Quando surge uma divergência comportamental, o sistema gera mutações derivadas vizinhas no grafo (`child_mutation`) e amplifica a prioridade de nós que compartilham o mesmo campo ou invariante.
            </p>

            <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
              <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
                <div className="text-xs font-semibold text-slate-300 mb-2">Arestas de Associação no Grafo:</div>
                <ul className="space-y-1.5 text-xs text-slate-400 font-mono">
                  <li>• parent ↔ child_mutation</li>
                  <li>• `same_contract_field` (ex: `discount_rate`, `amount`)</li>
                  <li>• `same_consumer` (ex: `treasury-service`)</li>
                  <li>• `same_invariant` (ex: `ECONOMIC_VALUE_PRESERVED`)</li>
                  <li>• `same_risk_dimension` (ex: `economic_risk`)</li>
                </ul>
              </div>

              <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
                <div className="text-xs font-semibold text-slate-300 mb-2">Efeito de Feedback Negativo (Cenários Aprovados):</div>
                <p className="text-xs text-slate-400 leading-relaxed font-sans">
                  Passar em testes de retry e timeout não zera o risco residual, mas reduz a incerteza marginal para $\le 0.05$, permitindo que o escalonador pare com segurança sem testar combinações redundantes.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB: MANDATORY SAFETY SET */}
      {selectedTab === 'safety' && (
        <div className="space-y-6">
          <div className="rounded-xl border border-emerald-500/30 bg-[#0d161a] p-5 shadow-lg">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <ShieldCheck className="h-5 w-5 text-emerald-400" />
                <h3 className="text-sm font-bold text-white">
                  Conjunto Mínimo Obrigatório de Segurança Econômica
                </h3>
              </div>
              <span className="rounded bg-emerald-500/10 border border-emerald-500/30 px-2.5 py-0.5 text-xs font-semibold text-emerald-300">
                100% EXECUTADO & APROVADO
              </span>
            </div>

            <p className="mt-3 text-xs text-slate-400">
              Sob a política <strong>ECONOMIC_CRITICAL</strong>, a otimização de custo e a busca por score são terminantemente subordinadas: nenhum dos cenários abaixo pode ser ignorado ou postergado, independentemente de prioridade heurística.
            </p>

            <div className="mt-4 space-y-2.5">
              {data.mandatory_safety_set.map((item, idx) => (
                <div key={idx} className="flex items-center justify-between rounded-lg border border-slate-800 bg-slate-900/50 p-3 text-xs">
                  <div className="flex items-center gap-2.5">
                    <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                    <span className="font-semibold text-slate-200">{item.target}</span>
                  </div>
                  <span className="rounded bg-emerald-500/10 px-2 py-0.5 font-mono text-[11px] font-bold text-emerald-300">
                    {item.status}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
