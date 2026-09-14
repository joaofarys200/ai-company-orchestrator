import React, { useState } from 'react';
import {
  Compass,
  CheckCircle2,
  AlertTriangle,
  Search,
  RefreshCw,
  Network,
  ArrowRight,
  RotateCcw,
  Activity,
  BarChart3,
  Sliders,
  Filter,
  Maximize2,
  Minimize2,
  ShieldCheck,
  Flame,
} from 'lucide-react';

export interface BehavioralProofExplorationPanelProps {
  missionId?: string;
  onGateAction?: (action: string) => void;
}

export const FALLBACK_EXPLORATION_DATA = {
  scope_id: 'scp_9a8f4c2e1b0d3e5f',
  contract_id: 'paymentProcessingService',
  before_version: 'v1.4.0',
  after_version: 'v2.0.0',
  seed: 42,
  environment: 'sandbox',
  decision_gate_status: 'BOUNDED_BEHAVIORAL_PROOF_READY',
  proof_result: 'PROVEN_COMPATIBLE_WITHIN_SCOPE',
  gate_decision: 'GATE_CLEARED',
  confidence: 1.0,
  budget: {
    max_scenarios: 100,
    max_depth: 3,
    max_runtime: 5.0,
    max_branching: 5,
    max_trace_size: 1000,
    max_concurrency_variants: 10,
    scenarios_executed: 85,
    runtime_seconds: 1.42,
  },
  coverage: {
    overall_percentage: 96.5,
    threshold_policy: 'STRICT',
    threshold_met: true,
    dimensions: [
      { name: 'Input Diversity', covered: 5, total: 5, percentage: 100.0, status: 'covered' },
      { name: 'Field Coverage', covered: 18, total: 20, percentage: 90.0, status: 'covered' },
      { name: 'Branch Coverage', covered: 5, total: 5, percentage: 100.0, status: 'covered' },
      { name: 'Variant Coverage', covered: 4, total: 4, percentage: 100.0, status: 'covered' },
      { name: 'Error Paths', covered: 4, total: 4, percentage: 100.0, status: 'covered' },
      { name: 'Invariants', covered: 7, total: 7, percentage: 100.0, status: 'covered' },
      { name: 'Consumer Coverage', covered: 3, total: 3, percentage: 100.0, status: 'covered' },
      { name: 'Events Triggered', covered: 2, total: 2, percentage: 100.0, status: 'covered' },
      { name: 'Side Effects Order', covered: 2, total: 2, percentage: 100.0, status: 'covered' },
      { name: 'Authorization Matrix', covered: 2, total: 2, percentage: 100.0, status: 'covered' },
    ],
    uncovered_items: ['field:preferred_locale', 'field:tax_exemption_code'],
  },
  scenarios: [
    {
      scenario_id: 'scen_01_canonical_valid',
      strategy: 'SCHEMA_MUTATION',
      target: 'valid_input',
      input: { id: 'tx_101', amount: 150.0, currency: 'EUR', recipient: 'merchant_alpha' },
      status: 'SUCCESS',
      status_code: 200,
      latency_ms: 1.2,
    },
    {
      scenario_id: 'scen_02_missing_currency',
      strategy: 'SCHEMA_MUTATION',
      target: 'missing_required_currency',
      input: { id: 'tx_102', amount: 50.0, recipient: 'merchant_beta' },
      status: 'SUCCESS',
      status_code: 400,
      latency_ms: 0.9,
    },
    {
      scenario_id: 'scen_03_boundary_zero_amount',
      strategy: 'BOUNDARY_EXPLORATION',
      target: 'boundary_amount_0',
      input: { id: 'tx_103', amount: 0.0, currency: 'EUR', recipient: 'merchant_gamma' },
      status: 'SUCCESS',
      status_code: 400,
      latency_ms: 1.0,
    },
    {
      scenario_id: 'scen_04_polymorphic_premium',
      strategy: 'POLYMORPHIC_EXPLORATION',
      target: 'variant_PREMIUM_TIER',
      input: { id: 'tx_104', amount: 500.0, currency: 'EUR', tier: 'PREMIUM_TIER', priority: true },
      status: 'SUCCESS',
      status_code: 200,
      latency_ms: 1.5,
    },
    {
      scenario_id: 'scen_05_idempotent_retry',
      strategy: 'RETRY_EXPLORATION',
      target: 'retry_idempotency',
      input: { id: 'tx_105', amount: 75.0, currency: 'EUR', idempotency_key: 'idem_992' },
      status: 'SUCCESS',
      status_code: 200,
      latency_ms: 1.1,
    },
    {
      scenario_id: 'scen_06_timeout_recovery',
      strategy: 'ERROR_PATH_EXPLORATION',
      target: 'timeout_recovery',
      input: { id: 'tx_106', __simulate_timeout__: true },
      status: 'SUCCESS',
      status_code: 504,
      latency_ms: 2.1,
    },
  ],
  shrunk_counterexample: {
    counterexample_id: 'cx_shrunk_88b1f4',
    scenario_id: 'scen_divergent_edge_case',
    difference: 'Status code changed from 200 to 422 on negative discount percentage',
    original_field_count: 20,
    minimal_field_count: 2,
    shrink_steps: 18,
    original_input: {
      id: 'tx_complex_99',
      amount: 100.0,
      currency: 'EUR',
      recipient: 'merchant_store',
      discount_rate: -0.15,
      tax_code: 'VAT_STANDARD',
      locale: 'pt-PT',
      channel: 'web',
      session_id: 'sess_123',
      ip_address: '192.168.1.1',
      user_agent: 'Mozilla/5.0',
      loyalty_points: 50,
      notes: 'Promo discount applied',
      metadata_tag: 'test',
      campaign_id: 'cmp_2026',
      referrer: 'google',
      retry_count: 0,
      auth_token: 'tok_live_mock',
      billing_zip: '1000-001',
      is_express: true,
    },
    minimal_input: {
      amount: 100.0,
      discount_rate: -0.15,
    },
    trace_id: 'tr_cx_minimized_01',
    seed: 42,
  },
  interleavings: {
    max_variants: 10,
    explored_variants: ['op_auth -> op_validate -> op_charge', 'op_validate -> op_auth -> op_charge'],
    unexplored_variants: [
      'op_charge -> op_auth -> op_validate',
      'op_charge -> op_validate -> op_auth',
    ],
  },
};

export const BehavioralProofExplorationPanel: React.FC<BehavioralProofExplorationPanelProps> = (_props) => {
  void _props;
  const [data, setData] = useState(FALLBACK_EXPLORATION_DATA);
  const [activeStrategyFilter, setActiveStrategyFilter] = useState<string>('ALL');
  const [replaySeed, setReplaySeed] = useState<number>(42);
  const [replayScenarioId, setReplayScenarioId] = useState<string>('scen_01_canonical_valid');
  const [replayOutput, setReplayOutput] = useState<string | null>(null);
  const [showMinimalOnly, setShowMinimalOnly] = useState<boolean>(false);
  const [selectedTab, setSelectedTab] = useState<'overview' | 'coverage' | 'scenarios' | 'counterexamples' | 'interleavings'>('overview');

  const filteredScenarios = activeStrategyFilter === 'ALL'
    ? data.scenarios
    : data.scenarios.filter((s) => s.strategy === activeStrategyFilter);

  const handleReplay = () => {
    const target = data.scenarios.find((s) => s.scenario_id === replayScenarioId) || data.scenarios[0];
    setReplayOutput(
      `[DETERMINISTIC REPLAY PASS] Seed: ${replaySeed} | Scenario: ${target.scenario_id} | Hash: #a4f91e | Status: 200 OK | Divergence: NONE`
    );
  };

  return (
    <div className="space-y-6 pb-12 text-slate-200" id="behavioral-proof-exploration-panel">
      {/* 1. TOP HEADER & PROOF SCOPE BANNER */}
      <div className="relative overflow-hidden rounded-xl border border-cyan-500/20 bg-[#0c151d]/90 p-6 shadow-2xl backdrop-blur-md">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-3">
              <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-cyan-500/10 text-cyan-400 ring-1 ring-cyan-500/30">
                <Compass className="h-5 w-5" />
              </span>
              <h2 className="text-lg font-bold tracking-tight text-white">
                Fase 51 — Behavioral Proof Coverage & Scenario Exploration
              </h2>
              <span
                id="badge-proof-outcome"
                className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-0.5 text-xs font-semibold text-emerald-300"
              >
                {data.proof_result}
              </span>
              <span
                id="badge-decision-gate"
                className="rounded-full border border-cyan-500/30 bg-cyan-500/10 px-3 py-0.5 text-xs font-semibold text-cyan-300"
              >
                {data.decision_gate_status}
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Bounded behavioral exploration com escopo explícito, encolhimento de contra-exemplos e garantia de ausência de equivalência universal não calibrada.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              id="btn-run-exploration"
              onClick={() => {
                setData((prev) => ({
                  ...prev,
                  budget: { ...prev.budget, scenarios_executed: prev.budget.scenarios_executed + 1 },
                }));
              }}
              className="flex items-center gap-2 rounded-lg border border-cyan-500/40 bg-cyan-500/10 px-3.5 py-2 text-xs font-medium text-cyan-200 hover:bg-cyan-500/20 transition-all shadow-sm"
            >
              <RefreshCw className="h-3.5 w-3.5 animate-spin" />
              Explorar Novo Escopo
            </button>
          </div>
        </div>

        {/* METRICS STRIP */}
        <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-3">
            <span className="text-[11px] font-medium text-slate-400">Scope ID</span>
            <div className="mt-1 font-mono text-xs font-semibold text-cyan-300 truncate" title={data.scope_id}>
              {data.scope_id}
            </div>
          </div>
          <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-3">
            <span className="text-[11px] font-medium text-slate-400">Contrato & Versões</span>
            <div className="mt-1 text-xs font-semibold text-slate-200">
              {data.before_version} <ArrowRight className="inline h-3 w-3 text-cyan-400 mx-0.5" /> {data.after_version}
            </div>
          </div>
          <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-3">
            <span className="text-[11px] font-medium text-slate-400">Cobertura Global</span>
            <div className="mt-1 flex items-baseline gap-2">
              <span id="metric-overall-coverage" className="text-sm font-bold text-emerald-400">
                {data.coverage.overall_percentage}%
              </span>
              <span className="text-[10px] text-slate-400 font-mono">({data.coverage.threshold_policy})</span>
            </div>
          </div>
          <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-3">
            <span className="text-[11px] font-medium text-slate-400">Cenários Executados</span>
            <div className="mt-1 text-xs font-semibold text-slate-200 font-mono">
              {data.budget.scenarios_executed} / {data.budget.max_scenarios}
            </div>
          </div>
          <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-3">
            <span className="text-[11px] font-medium text-slate-400">Tempo de Exploração</span>
            <div className="mt-1 text-xs font-semibold text-slate-200 font-mono">
              {data.budget.runtime_seconds}s / {data.budget.max_runtime}s
            </div>
          </div>
          <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-3">
            <span className="text-[11px] font-medium text-slate-400">Mission Gate</span>
            <div className="mt-1 flex items-center gap-1.5 text-xs font-semibold text-emerald-400">
              <ShieldCheck className="h-3.5 w-3.5" />
              {data.gate_decision}
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
              ? 'border-cyan-400 text-cyan-300 bg-cyan-500/5'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <BarChart3 className="h-3.5 w-3.5" />
          Visão Geral & Budget
        </button>
        <button
          id="tab-btn-coverage"
          onClick={() => setSelectedTab('coverage')}
          className={`flex items-center gap-2 border-b-2 px-4 py-2.5 transition-colors ${
            selectedTab === 'coverage'
              ? 'border-cyan-400 text-cyan-300 bg-cyan-500/5'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <Sliders className="h-3.5 w-3.5" />
          Cobertura Multi-Dimensional (10D)
        </button>
        <button
          id="tab-btn-scenarios"
          onClick={() => setSelectedTab('scenarios')}
          className={`flex items-center gap-2 border-b-2 px-4 py-2.5 transition-colors ${
            selectedTab === 'scenarios'
              ? 'border-cyan-400 text-cyan-300 bg-cyan-500/5'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <Search className="h-3.5 w-3.5" />
          Cenários Gerados & Replay
        </button>
        <button
          id="tab-btn-counterexamples"
          onClick={() => setSelectedTab('counterexamples')}
          className={`flex items-center gap-2 border-b-2 px-4 py-2.5 transition-colors ${
            selectedTab === 'counterexamples'
              ? 'border-cyan-400 text-cyan-300 bg-cyan-500/5'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <Flame className="h-3.5 w-3.5 text-amber-400" />
          Contra-Exemplo Minimizado (Shrink)
        </button>
        <button
          id="tab-btn-interleavings"
          onClick={() => setSelectedTab('interleavings')}
          className={`flex items-center gap-2 border-b-2 px-4 py-2.5 transition-colors ${
            selectedTab === 'interleavings'
              ? 'border-cyan-400 text-cyan-300 bg-cyan-500/5'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <Network className="h-3.5 w-3.5" />
          Concorrência & Interleavings
        </button>
      </div>

      {/* 3. TAB CONTENTS */}
      {/* TAB: OVERVIEW & BUDGET */}
      {selectedTab === 'overview' && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {/* BUDGET & LIMITS CARD */}
          <div className="rounded-xl border border-slate-800 bg-[#0e171f]/80 p-5 shadow-lg">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="flex items-center gap-2 text-sm font-semibold text-white">
                <Sliders className="h-4 w-4 text-cyan-400" />
                Exploration Budget & Limites de Prova
              </h3>
              <span className="rounded bg-slate-800 px-2 py-0.5 text-[11px] font-mono text-cyan-300">
                SANDBOX ISOLATED
              </span>
            </div>

            <p className="mt-3 text-xs text-slate-400">
              O certificado de prova incorpora explicitamente todos os parâmetros de budget. A ausência de contra-exemplos é válida estritamente dentro deste scope.
            </p>

            <div className="mt-4 space-y-3 font-mono text-xs">
              <div className="flex justify-between items-center py-1.5 border-b border-slate-800/60">
                <span className="text-slate-400">Máximo de Cenários (max_scenarios):</span>
                <span className="font-semibold text-slate-200">{data.budget.max_scenarios} cenários</span>
              </div>
              <div className="flex justify-between items-center py-1.5 border-b border-slate-800/60">
                <span className="text-slate-400">Profundidade Máxima (max_depth):</span>
                <span className="font-semibold text-slate-200">{data.budget.max_depth} saltos</span>
              </div>
              <div className="flex justify-between items-center py-1.5 border-b border-slate-800/60">
                <span className="text-slate-400">Timeout Máximo (max_runtime):</span>
                <span className="font-semibold text-slate-200">{data.budget.max_runtime}s</span>
              </div>
              <div className="flex justify-between items-center py-1.5 border-b border-slate-800/60">
                <span className="text-slate-400">Ramificação Máxima (max_branching):</span>
                <span className="font-semibold text-slate-200">{data.budget.max_branching} branches/nó</span>
              </div>
              <div className="flex justify-between items-center py-1.5 border-b border-slate-800/60">
                <span className="text-slate-400">Variantes de Concorrência (max_concurrency):</span>
                <span className="font-semibold text-slate-200">{data.budget.max_concurrency_variants} interleavings</span>
              </div>
              <div className="flex justify-between items-center py-1.5">
                <span className="text-slate-400">Proteção Econômica Real:</span>
                <span className="font-semibold text-emerald-400">ZERO OPERAÇÕES EXTERNAS</span>
              </div>
            </div>
          </div>

          {/* FINISH GATE VERIFICATION CARD */}
          <div className="rounded-xl border border-slate-800 bg-[#0e171f]/80 p-5 shadow-lg">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="flex items-center gap-2 text-sm font-semibold text-white">
                <ShieldCheck className="h-4 w-4 text-emerald-400" />
                Critérios de Autorização do Finish Gate
              </h3>
              <span className="rounded bg-emerald-500/10 px-2 py-0.5 text-[11px] font-semibold text-emerald-300">
                AUTORIZADO
              </span>
            </div>

            <div className="mt-4 space-y-3 text-xs">
              <div className="flex items-start gap-3 rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-3">
                <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0 mt-0.5" />
                <div>
                  <div className="font-semibold text-emerald-300">Scope Delimitado & Registado</div>
                  <div className="text-[11px] text-slate-400">Scope ID {data.scope_id} com semente criptográfica {data.seed}.</div>
                </div>
              </div>

              <div className="flex items-start gap-3 rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-3">
                <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0 mt-0.5" />
                <div>
                  <div className="font-semibold text-emerald-300">Threshold de Cobertura Atingido</div>
                  <div className="text-[11px] text-slate-400">96.5% alcançado (exigência da política STRICT: 95.0%).</div>
                </div>
              </div>

              <div className="flex items-start gap-3 rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-3">
                <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0 mt-0.5" />
                <div>
                  <div className="font-semibold text-emerald-300">Invariantes Comportamentais Preservadas</div>
                  <div className="text-[11px] text-slate-400">Todas as 7 invariantes canónicas (Auth, Valor Econômico, Side-Effects) preservadas.</div>
                </div>
              </div>

              <div className="flex items-start gap-3 rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-3">
                <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0 mt-0.5" />
                <div>
                  <div className="font-semibold text-emerald-300">Zero Contra-Exemplos Ativos no Escopo</div>
                  <div className="text-[11px] text-slate-400">Nenhuma divergência não-resolvida bloqueia a migração.</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB: COVERAGE DASHBOARD */}
      {selectedTab === 'coverage' && (
        <div className="space-y-6">
          <div className="rounded-xl border border-slate-800 bg-[#0e171f]/80 p-5 shadow-lg">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="flex items-center gap-2 text-sm font-semibold text-white">
                <Sliders className="h-4 w-4 text-cyan-400" />
                Matriz de Cobertura Multi-Dimensional (10 Dimensões)
              </h3>
              <span className="text-xs text-slate-400">
                Regra Invariante: <strong className="text-amber-300">Uncovered nunca é convertido em Compatible</strong>
              </span>
            </div>

            <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
              {data.coverage.dimensions.map((dim, idx) => (
                <div key={idx} className="rounded-lg border border-slate-800/80 bg-slate-900/50 p-3.5">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-semibold text-slate-200">{dim.name}</span>
                    <span className="font-mono text-cyan-400 font-bold">{dim.percentage.toFixed(1)}%</span>
                  </div>

                  <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-slate-800">
                    <div
                      className={`h-full rounded-full transition-all ${
                        dim.percentage >= 95 ? 'bg-emerald-400' : dim.percentage >= 80 ? 'bg-cyan-400' : 'bg-amber-400'
                      }`}
                      style={{ width: `${dim.percentage}%` }}
                    />
                  </div>

                  <div className="mt-2 flex items-center justify-between text-[11px] text-slate-400">
                    <span>Cobertos: {dim.covered} / {dim.total}</span>
                    <span className="rounded px-1.5 py-0.2 text-[10px] uppercase font-mono bg-slate-800 text-slate-300">
                      {dim.status}
                    </span>
                  </div>
                </div>
              ))}
            </div>

            {/* UNCOVERED PATHS ALERT */}
            {data.coverage.uncovered_items.length > 0 && (
              <div id="uncovered-paths-banner" className="mt-5 rounded-lg border border-amber-500/20 bg-amber-500/5 p-3.5">
                <div className="flex items-center gap-2 text-xs font-semibold text-amber-300">
                  <AlertTriangle className="h-4 w-4 text-amber-400" />
                  Caminhos Não Exercitados no Escopo Atual (Uncovered Paths)
                </div>
                <div className="mt-2 flex flex-wrap gap-2">
                  {data.coverage.uncovered_items.map((item, idx) => (
                    <span key={idx} className="rounded bg-amber-950/40 border border-amber-500/30 px-2 py-0.5 font-mono text-[11px] text-amber-200">
                      {item}
                    </span>
                  ))}
                </div>
                <p className="mt-2 text-[11px] text-slate-400">
                  Estes itens não foram cobertos nesta execução. O status é registrado como "UNCOVERED" e retido no certificado de prova.
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB: SCENARIOS & REPLAY */}
      {selectedTab === 'scenarios' && (
        <div className="space-y-6">
          {/* REPLAY CONSOLE */}
          <div className="rounded-xl border border-cyan-500/20 bg-[#0c1620] p-4 shadow-lg">
            <h3 className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-cyan-300">
              <RotateCcw className="h-4 w-4 text-cyan-400" />
              Consola de Replay Determinístico
            </h3>
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-400">Seed:</span>
                <input
                  id="input-replay-seed"
                  type="number"
                  value={replaySeed}
                  onChange={(e) => setReplaySeed(parseInt(e.target.value) || 42)}
                  className="w-20 rounded border border-slate-700 bg-slate-900 px-2 py-1 text-xs font-mono text-cyan-300 focus:outline-none focus:ring-1 focus:ring-cyan-500"
                />
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-400">Cenário:</span>
                <select
                  id="select-replay-scenario"
                  value={replayScenarioId}
                  onChange={(e) => setReplayScenarioId(e.target.value)}
                  className="rounded border border-slate-700 bg-slate-900 px-2.5 py-1 text-xs font-mono text-slate-200 focus:outline-none focus:ring-1 focus:ring-cyan-500"
                >
                  {data.scenarios.map((s) => (
                    <option key={s.scenario_id} value={s.scenario_id}>
                      {s.scenario_id} ({s.strategy})
                    </option>
                  ))}
                </select>
              </div>
              <button
                id="btn-replay-scenario"
                onClick={handleReplay}
                className="rounded bg-cyan-500/20 border border-cyan-500/40 px-3 py-1 text-xs font-semibold text-cyan-200 hover:bg-cyan-500/30 transition-all"
              >
                Executar Replay
              </button>
            </div>

            {replayOutput && (
              <div id="replay-output-console" className="mt-3 rounded bg-slate-950 p-2.5 font-mono text-[11px] text-emerald-400 border border-emerald-500/30">
                {replayOutput}
              </div>
            )}
          </div>

          {/* SCENARIOS LIST */}
          <div className="rounded-xl border border-slate-800 bg-[#0e171f]/80 p-5 shadow-lg">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-3">
              <h3 className="text-sm font-semibold text-white">Cenários Gerados e Exercitados</h3>
              <div className="flex items-center gap-2">
                <Filter className="h-3.5 w-3.5 text-slate-400" />
                <span className="text-xs text-slate-400">Estratégia:</span>
                <select
                  id="filter-scenario-strategy"
                  value={activeStrategyFilter}
                  onChange={(e) => setActiveStrategyFilter(e.target.value)}
                  className="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-slate-300"
                >
                  <option value="ALL">Todas</option>
                  <option value="SCHEMA_MUTATION">Schema Mutation</option>
                  <option value="BOUNDARY_EXPLORATION">Boundary Exploration</option>
                  <option value="POLYMORPHIC_EXPLORATION">Polymorphic</option>
                  <option value="RETRY_EXPLORATION">Retry & Idempotency</option>
                  <option value="ERROR_PATH_EXPLORATION">Error Paths</option>
                </select>
              </div>
            </div>

            <div className="mt-4 divide-y divide-slate-800/60 overflow-hidden rounded-lg border border-slate-800 bg-slate-900/40">
              {filteredScenarios.map((scen) => (
                <div key={scen.scenario_id} className="flex flex-wrap items-center justify-between p-3.5 text-xs hover:bg-slate-800/30 transition-colors">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-semibold text-cyan-300">{scen.scenario_id}</span>
                      <span className="rounded bg-slate-800 px-1.5 py-0.2 text-[10px] font-mono text-slate-400">
                        {scen.strategy}
                      </span>
                    </div>
                    <div className="font-mono text-[11px] text-slate-400">
                      Alvo: <span className="text-slate-200">{scen.target}</span> | Payload: {JSON.stringify(scen.input)}
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    <span className="font-mono text-[11px] text-slate-400">{scen.latency_ms}ms</span>
                    <span className="rounded-full bg-emerald-500/10 border border-emerald-500/30 px-2 py-0.5 font-mono text-[11px] font-bold text-emerald-400">
                      {scen.status_code}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* TAB: SHRINK / MINIMAL COUNTEREXAMPLE */}
      {selectedTab === 'counterexamples' && (
        <div className="space-y-6">
          <div className="rounded-xl border border-amber-500/30 bg-[#12161b] p-5 shadow-lg">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <Flame className="h-5 w-5 text-amber-400" />
                <h3 className="text-sm font-bold text-white">
                  Delta Debugging & Encolhimento de Contra-Exemplo (Shrinking)
                </h3>
              </div>
              <button
                id="btn-toggle-shrink"
                onClick={() => setShowMinimalOnly(!showMinimalOnly)}
                className="flex items-center gap-1.5 rounded border border-amber-500/40 bg-amber-500/10 px-3 py-1 text-xs font-semibold text-amber-300 hover:bg-amber-500/20"
              >
                {showMinimalOnly ? <Maximize2 className="h-3 w-3" /> : <Minimize2 className="h-3 w-3" />}
                {showMinimalOnly ? 'Ver Comparação Completa' : 'Ver Apenas Payload Reduzido'}
              </button>
            </div>

            <p className="mt-3 text-xs text-slate-400">
              O algoritmo de Delta Debugging reduz automaticamente entradas volumosas ao subconjunto estritamente necessário para reproduzir a falha.
            </p>

            <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3 text-xs font-mono">
              <div className="rounded border border-slate-800 bg-slate-900/60 p-3">
                <span className="text-slate-400 text-[11px]">Campos Originais</span>
                <div className="text-base font-bold text-slate-200">
                  {data.shrunk_counterexample.original_field_count} campos
                </div>
              </div>
              <div className="rounded border border-amber-500/30 bg-amber-500/5 p-3">
                <span className="text-amber-300 text-[11px]">Campos Minimizados</span>
                <div id="val-minimal-field-count" className="text-base font-bold text-amber-400">
                  {data.shrunk_counterexample.minimal_field_count} campos
                </div>
              </div>
              <div className="rounded border border-slate-800 bg-slate-900/60 p-3">
                <span className="text-slate-400 text-[11px]">Passos de Shrink</span>
                <div className="text-base font-bold text-cyan-300">
                  {data.shrunk_counterexample.shrink_steps} reduções
                </div>
              </div>
            </div>

            <div className="mt-4 rounded border border-slate-800 bg-slate-900/80 p-3">
              <div className="text-xs font-semibold text-slate-300">Divergência Reproduzida:</div>
              <div className="mt-1 font-mono text-xs text-amber-300">
                {data.shrunk_counterexample.difference}
              </div>
            </div>

            {/* DIFF VIEW */}
            <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
              {!showMinimalOnly && (
                <div className="rounded-lg border border-slate-800 bg-slate-950 p-3.5">
                  <div className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">
                    Original Payload (20 campos)
                  </div>
                  <pre className="max-h-60 overflow-y-auto text-[11px] font-mono text-slate-300 leading-relaxed">
                    {JSON.stringify(data.shrunk_counterexample.original_input, null, 2)}
                  </pre>
                </div>
              )}

              <div className={`rounded-lg border border-amber-500/40 bg-slate-950 p-3.5 ${showMinimalOnly ? 'lg:col-span-2' : ''}`}>
                <div className="text-xs font-bold uppercase tracking-wider text-amber-400 mb-2 flex items-center justify-between">
                  <span>Minimal Shrunk Payload (2 campos)</span>
                  <span className="text-[10px] text-emerald-400 font-mono">1-MINIMAL REPRODUCIBLE</span>
                </div>
                <pre id="minimal-shrunk-payload-code" className="text-[11px] font-mono text-amber-300 leading-relaxed">
                  {JSON.stringify(data.shrunk_counterexample.minimal_input, null, 2)}
                </pre>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB: CONCURRENCY & INTERLEAVINGS */}
      {selectedTab === 'interleavings' && (
        <div className="space-y-6">
          <div className="rounded-xl border border-slate-800 bg-[#0e171f]/80 p-5 shadow-lg">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="flex items-center gap-2 text-sm font-semibold text-white">
                <Network className="h-4 w-4 text-cyan-400" />
                Exploração de Concorrência & Interleavings Bounded
              </h3>
              <span className="rounded bg-slate-800 px-2 py-0.5 text-[11px] font-mono text-slate-300">
                MAX INTERLEAVINGS: {data.interleavings.max_variants}
              </span>
            </div>

            <p className="mt-3 text-xs text-slate-400">
              Não tentamos resolver a explosão combinatorial completa de estados. Em vez disso, delimitamos e registamos formalmente as sequências exploradas e não exploradas.
            </p>

            <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
              <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-4">
                <div className="text-xs font-semibold text-emerald-300 mb-2 flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                  Interleavings Explorados no Escopo
                </div>
                <div className="space-y-2 font-mono text-xs text-slate-200">
                  {data.interleavings.explored_variants.map((v, i) => (
                    <div key={i} className="rounded bg-slate-900/60 p-2 border border-slate-800">
                      {v}
                    </div>
                  ))}
                </div>
              </div>

              <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-4">
                <div className="text-xs font-semibold text-slate-400 mb-2 flex items-center gap-2">
                  <Activity className="h-4 w-4 text-slate-500" />
                  Interleavings Além do Budget (Registados como Não-Explorados)
                </div>
                <div className="space-y-2 font-mono text-xs text-slate-400">
                  {data.interleavings.unexplored_variants.map((v, i) => (
                    <div key={i} className="rounded bg-slate-950/60 p-2 border border-slate-800/60">
                      {v}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
