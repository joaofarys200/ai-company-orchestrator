import React, { useState } from 'react';
import {
  Scale,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  RotateCcw,
  Layers,
  Activity,
  XCircle,
  TrendingUp,
  FileCheck2,
  Sliders,
  Check,
} from 'lucide-react';

export const AutonomousRepairConvergencePanel: React.FC = () => {
  const [activeSubTab, setActiveSubTab] = useState<
    'overview' | 'progress_vector' | 'cycle_oscillation' | 'stall_divergence' | 'adaptive_budget' | 'ledger_audit'
  >('overview');

  const [activeState, setActiveState] = useState<
    'CONVERGED' | 'CONVERGING' | 'OSCILLATING' | 'STALLED' | 'DIVERGING' | 'HUMAN_REVIEW_REQUIRED'
  >('CONVERGED');

  const [certVerified, setCertVerified] = useState<boolean>(true);
  const [showCertModal, setShowCertModal] = useState<boolean>(false);
  const [rollbackStatus, setRollbackStatus] = useState<string | null>(null);

  // 8-Dimensional Progress Vector
  const progressVector = {
    resolvedFailures: 4,
    newFailures: 0,
    blockingFailures: 0,
    coverageGain: 0.92,
    riskReduction: 0.45,
    uncertaintyReduction: 0.18,
    proofProgress: 1.0,
    repairCost: 14.5,
  };

  const deltaP = {
    score: +18.4,
    isPositive: true,
    monotonicity: true,
  };

  // Trajectory history
  const trajectory = [
    { step: 0, failures: 4, risk: 0.58, coverage: 0.65, status: 'INITIAL', hash: 'sha256:4f9a...01' },
    { step: 1, failures: 3, risk: 0.44, coverage: 0.74, status: 'CONVERGING', hash: 'sha256:7b2c...14' },
    { step: 2, failures: 2, risk: 0.31, coverage: 0.81, status: 'CONVERGING', hash: 'sha256:3d8e...55' },
    { step: 3, failures: 1, risk: 0.19, coverage: 0.88, status: 'CONVERGING', hash: 'sha256:9a1f...82' },
    { step: 4, failures: 0, risk: 0.08, coverage: 0.95, status: 'COMMITTED', hash: 'sha256:e4b0...99' },
  ];

  // Divergence score breakdown
  const divergenceScore = {
    riskGrowth: 0.0,
    failureGrowth: 0.0,
    coverageDrop: 0.0,
    regressionGrowth: 0.0,
    rollbackRate: 0.0,
    totalScore: 0.0,
    isDiverging: activeState === 'DIVERGING',
  };

  // Budget
  const budget = {
    maxRepairs: 25,
    consumedRepairs: 4,
    maxCycles: 2,
    consumedCycles: activeState === 'OSCILLATING' ? 2 : 0,
    maxRuntime: 300,
    consumedRuntime: 18.5,
    maxRollbacks: 3,
    consumedRollbacks: rollbackStatus ? 1 : 0,
    remainingPct: 84.0,
  };

  // Cryptographic certificate
  const certificate = {
    certificateId: 'cert_conv_56_9981a',
    missionId: 'msn_repair_convergence_56',
    transactionId: 'tx_multirepair_phase56',
    terminationReason: activeState === 'CONVERGED' ? 'CONVERGED_VERIFIED' : `${activeState}_DETECTED`,
    convergenceVerdict: activeState === 'CONVERGED' ? 'CONVERGED' : activeState,
    initialStateHash: 'sha256:4f9a7210e53a1201',
    finalStateHash: 'sha256:e4b09f18cb663a99',
    totalIterations: 4,
    totalDurationSeconds: 18.5,
    signature: 'CERT_SIG_8a3f701c9b2e5541',
    sentinelApproved: true,
  };

  return (
    <div className="flex flex-col h-full bg-[#0a0f18] text-slate-100 p-6 overflow-y-auto" id="phase56-convergence-panel">
      {/* Top Banner & Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 pb-6 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-3">
            <Scale className="w-8 h-8 text-cyan-400" />
            <h1 className="text-2xl font-bold tracking-tight text-white">
              Governação de Convergência & Terminação Autónoma
            </h1>
            <span className="px-3 py-1 text-xs font-semibold rounded-full bg-cyan-500/10 border border-cyan-500/30 text-cyan-300">
              Fase 56
            </span>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            Autonomous Repair Termination, Multi-Order Cycle Detection, Lyapunov Monotonicity & Cryptographic Ledger.
          </p>
        </div>

        {/* State Badges & Decision Gate */}
        <div className="flex flex-wrap items-center gap-3">
          <div
            id="convergence-state-badge"
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border font-mono text-sm ${
              activeState === 'CONVERGED'
                ? 'bg-emerald-500/10 border-emerald-500/40 text-emerald-400'
                : activeState === 'OSCILLATING'
                ? 'bg-amber-500/10 border-amber-500/40 text-amber-400'
                : activeState === 'STALLED'
                ? 'bg-purple-500/10 border-purple-500/40 text-purple-400'
                : activeState === 'DIVERGING'
                ? 'bg-rose-500/10 border-rose-500/40 text-rose-400'
                : 'bg-blue-500/10 border-blue-500/40 text-blue-400'
            }`}
          >
            <Activity className="w-4 h-4 animate-pulse" />
            <span>ESTADO: {activeState}</span>
          </div>

          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-emerald-950/40 border border-emerald-500/40 text-emerald-300 font-semibold text-xs">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            <span>AUTONOMOUS_REPAIR_CONVERGENCE_READY</span>
          </div>

          <button
            id="convergence-certificate-view"
            onClick={() => setShowCertModal(true)}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white font-medium text-xs transition"
          >
            <FileCheck2 className="w-4 h-4" />
            <span>Ver Certificado</span>
          </button>
        </div>
      </div>

      {/* State Simulator Switcher for Browser QA */}
      <div className="flex flex-wrap items-center gap-2 mt-4 p-3 bg-slate-900/60 rounded-lg border border-slate-800 text-xs">
        <span className="text-slate-400 font-semibold uppercase">Simulação Interativa:</span>
        <button
          id="btn-state-converged"
          onClick={() => { setActiveState('CONVERGED'); setRollbackStatus(null); }}
          className={`px-2.5 py-1 rounded transition ${activeState === 'CONVERGED' ? 'bg-emerald-600 text-white' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'}`}
        >
          Convergência Bem-Sucedida
        </button>
        <button
          id="btn-state-oscillating"
          onClick={() => { setActiveState('OSCILLATING'); setRollbackStatus(null); }}
          className={`px-2.5 py-1 rounded transition ${activeState === 'OSCILLATING' ? 'bg-amber-600 text-white' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'}`}
        >
          Oscilação / Ciclo A↔B
        </button>
        <button
          id="btn-state-stalled"
          onClick={() => { setActiveState('STALLED'); setRollbackStatus(null); }}
          className={`px-2.5 py-1 rounded transition ${activeState === 'STALLED' ? 'bg-purple-600 text-white' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'}`}
        >
          Estagnação (Stall)
        </button>
        <button
          id="btn-state-diverging"
          onClick={() => { setActiveState('DIVERGING'); setRollbackStatus(null); }}
          className={`px-2.5 py-1 rounded transition ${activeState === 'DIVERGING' ? 'bg-rose-600 text-white' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'}`}
        >
          Divergência
        </button>
        <button
          id="btn-state-escalated"
          onClick={() => { setActiveState('HUMAN_REVIEW_REQUIRED'); setRollbackStatus(null); }}
          className={`px-2.5 py-1 rounded transition ${activeState === 'HUMAN_REVIEW_REQUIRED' ? 'bg-indigo-600 text-white' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'}`}
        >
          Revisão Humana
        </button>
        <button
          id="trigger-rollback-button"
          onClick={() => setRollbackStatus('Rollback determinístico executado com sucesso para ckpt_stable (SHA-256 equivalente).')}
          className="ml-auto flex items-center gap-1.5 px-3 py-1 rounded bg-rose-900/60 border border-rose-600/40 text-rose-200 hover:bg-rose-800/80 transition"
        >
          <RotateCcw className="w-3.5 h-3.5" />
          <span>Disparar Rollback</span>
        </button>
      </div>

      {rollbackStatus && (
        <div className="mt-3 p-3 bg-rose-950/40 border border-rose-500/50 rounded-lg flex items-center gap-2 text-xs text-rose-200">
          <RotateCcw className="w-4 h-4 text-rose-400 animate-spin" />
          <span>{rollbackStatus}</span>
        </div>
      )}

      {/* Sub-tabs Navigation */}
      <div className="flex border-b border-slate-800 gap-6 mt-6">
        {[
          { id: 'overview', label: 'Visão Geral & Lyapunov', icon: Activity },
          { id: 'progress_vector', label: 'Vetor de Progresso P', icon: TrendingUp },
          { id: 'cycle_oscillation', label: 'Deteção de Ciclos & Oscilação', icon: AlertTriangle },
          { id: 'stall_divergence', label: 'Divergência & Estagnação', icon: XCircle },
          { id: 'adaptive_budget', label: 'Orçamento Bounded', icon: Sliders },
          { id: 'ledger_audit', label: 'Ledger Auditável SHA-256', icon: Layers },
        ].map((tab) => {
          const Icon = tab.icon;
          const isSelected = activeSubTab === tab.id;
          return (
            <button
              key={tab.id}
              id={`tab-btn-${tab.id}`}
              onClick={() => setActiveSubTab(tab.id as any)}
              className={`flex items-center gap-2 py-3 px-1 text-sm font-medium border-b-2 transition ${
                isSelected
                  ? 'border-cyan-500 text-cyan-400'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <Icon className="w-4 h-4" />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* Content Panels */}
      <div className="mt-6 flex-1">
        {/* Tab 1: Overview & Lyapunov Trajectory */}
        {activeSubTab === 'overview' && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="bg-slate-900/50 border border-slate-800 p-4 rounded-xl">
                <span className="text-xs text-slate-400 uppercase font-medium">Falhas Restantes</span>
                <div className="text-3xl font-bold text-white mt-1">
                  {activeState === 'CONVERGED' ? 0 : activeState === 'OSCILLATING' ? 2 : 3}
                </div>
                <span className="text-xs text-emerald-400 mt-1 flex items-center gap-1">
                  <Check className="w-3 h-3" /> Progresso estritamente mono-direcional
                </span>
              </div>

              <div className="bg-slate-900/50 border border-slate-800 p-4 rounded-xl">
                <span className="text-xs text-slate-400 uppercase font-medium">Cobertura de Prova</span>
                <div className="text-3xl font-bold text-cyan-400 mt-1">
                  {activeState === 'CONVERGED' ? '95.0%' : '76.0%'}
                </div>
                <span className="text-xs text-slate-400 mt-1">Limiar mínimo: 80.0%</span>
              </div>

              <div className="bg-slate-900/50 border border-slate-800 p-4 rounded-xl">
                <span className="text-xs text-slate-400 uppercase font-medium">Score de Risco</span>
                <div className="text-3xl font-bold text-emerald-400 mt-1">
                  {activeState === 'DIVERGING' ? '0.780' : '0.080'}
                </div>
                <span className="text-xs text-slate-400 mt-1">Baseline inicial: 0.580</span>
              </div>

              <div className="bg-slate-900/50 border border-slate-800 p-4 rounded-xl">
                <span className="text-xs text-slate-400 uppercase font-medium">Monotonicidade Lyapunov</span>
                <div className="text-xl font-bold text-emerald-400 mt-1 flex items-center gap-1.5">
                  <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                  <span>V(S_k+1) &lt; V(S_k)</span>
                </div>
                <span className="text-xs text-slate-400 mt-1">Função de energia estritamente decrescente</span>
              </div>
            </div>

            {/* Trajectory Table */}
            <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-5">
              <h3 className="text-sm font-semibold text-slate-200 mb-4 flex items-center gap-2">
                <Activity className="w-4 h-4 text-cyan-400" />
                Trajetória Formal de Estados & Transições
              </h3>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs text-slate-300">
                  <thead className="bg-slate-800/60 text-slate-400 uppercase">
                    <tr>
                      <th className="p-2.5">Passo</th>
                      <th className="p-2.5">Falhas Ativas</th>
                      <th className="p-2.5">Risco</th>
                      <th className="p-2.5">Cobertura</th>
                      <th className="p-2.5">Estado Formal</th>
                      <th className="p-2.5">State Hash SHA-256</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800">
                    {trajectory.map((t) => (
                      <tr key={t.step} className="hover:bg-slate-800/30">
                        <td className="p-2.5 font-mono text-cyan-400">#{t.step}</td>
                        <td className="p-2.5">{t.failures}</td>
                        <td className="p-2.5 font-mono">{t.risk}</td>
                        <td className="p-2.5 font-mono">{(t.coverage * 100).toFixed(1)}%</td>
                        <td className="p-2.5">
                          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-cyan-500/10 text-cyan-300 border border-cyan-500/30">
                            {t.status}
                          </span>
                        </td>
                        <td className="p-2.5 font-mono text-slate-400">{t.hash}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: Progress Vector */}
        {activeSubTab === 'progress_vector' && (
          <div className="space-y-6" id="progress-vector-card">
            <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-5">
              <h3 className="text-sm font-semibold text-slate-200 mb-2 flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-cyan-400" />
                Vetor de Progresso Multidimensional (P)
              </h3>
              <p className="text-xs text-slate-400 mb-4">
                P = (resolved_failures, new_failures, blocking_failures, coverage_gain, risk_reduction, uncertainty_reduction, proof_progress, repair_cost)
              </p>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="p-3 bg-slate-800/40 rounded-lg border border-slate-700/50">
                  <span className="text-slate-400 text-xs">Falhas Resolvidas</span>
                  <div className="text-2xl font-bold text-emerald-400 mt-1">+{progressVector.resolvedFailures}</div>
                </div>
                <div className="p-3 bg-slate-800/40 rounded-lg border border-slate-700/50">
                  <span className="text-slate-400 text-xs">Novas Falhas</span>
                  <div className="text-2xl font-bold text-slate-200 mt-1">{progressVector.newFailures}</div>
                </div>
                <div className="p-3 bg-slate-800/40 rounded-lg border border-slate-700/50">
                  <span className="text-slate-400 text-xs">Falhas Bloqueantes</span>
                  <div className="text-2xl font-bold text-slate-200 mt-1">{progressVector.blockingFailures}</div>
                </div>
                <div className="p-3 bg-slate-800/40 rounded-lg border border-slate-700/50">
                  <span className="text-slate-400 text-xs">Ganho de Cobertura</span>
                  <div className="text-2xl font-bold text-cyan-400 mt-1">+{(progressVector.coverageGain * 100).toFixed(0)}%</div>
                </div>
                <div className="p-3 bg-slate-800/40 rounded-lg border border-slate-700/50">
                  <span className="text-slate-400 text-xs">Redução de Risco</span>
                  <div className="text-2xl font-bold text-emerald-400 mt-1">-{(progressVector.riskReduction * 100).toFixed(0)}%</div>
                </div>
                <div className="p-3 bg-slate-800/40 rounded-lg border border-slate-700/50">
                  <span className="text-slate-400 text-xs">Redução Incerteza</span>
                  <div className="text-2xl font-bold text-cyan-400 mt-1">-{(progressVector.uncertaintyReduction * 100).toFixed(0)}%</div>
                </div>
                <div className="p-3 bg-slate-800/40 rounded-lg border border-slate-700/50">
                  <span className="text-slate-400 text-xs">Progresso de Prova</span>
                  <div className="text-2xl font-bold text-emerald-400 mt-1">100%</div>
                </div>
                <div className="p-3 bg-slate-800/40 rounded-lg border border-slate-700/50">
                  <span className="text-slate-400 text-xs">Custo de Reparação</span>
                  <div className="text-2xl font-bold text-slate-200 mt-1">{progressVector.repairCost}s</div>
                </div>
              </div>

              <div className="mt-5 p-4 bg-cyan-950/30 border border-cyan-500/30 rounded-lg flex items-center justify-between">
                <div>
                  <span className="text-xs text-cyan-300 font-semibold uppercase">Pontuação Agregada Delta P:</span>
                  <span className="text-xl font-bold text-white ml-2 font-mono">{deltaP.score}</span>
                </div>
                <div className="flex items-center gap-2 text-xs text-emerald-400 font-semibold">
                  <CheckCircle2 className="w-4 h-4" />
                  <span>Delta P &gt; 0 (Progresso Positivo Estrito)</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tab 3: Cycle & Oscillation */}
        {activeSubTab === 'cycle_oscillation' && (
          <div className="space-y-6" id="cycle-alert-card">
            <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-5">
              <h3 className="text-sm font-semibold text-slate-200 mb-2 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-amber-400" />
                Detetor de Ciclos de Reparação & Oscilação Ping-Pong
              </h3>
              <p className="text-xs text-slate-400 mb-4">
                Deteção determinística de ciclos de ordem 2 (A↔B), ordem 3 (A→B→C→A), repetições de patches e inversões.
              </p>

              {activeState === 'OSCILLATING' ? (
                <div className="p-4 bg-amber-950/30 border border-amber-500/40 rounded-lg space-y-3">
                  <div className="flex items-center gap-2 text-amber-400 font-semibold text-sm">
                    <AlertTriangle className="w-5 h-5" />
                    <span>CICLO OSCILATÓRIO DE COMPRIMENTO 2 DETETADO!</span>
                  </div>
                  <p className="text-xs text-slate-300">
                    Alternância cíclica detetada entre os passos #2 e #4: Patch A elimina Erro 1 gerando Erro 2; Patch B elimina Erro 2 reintroduzindo Erro 1.
                  </p>
                  <div className="font-mono text-xs text-amber-300 bg-black/40 p-2.5 rounded border border-amber-500/20">
                    Pattern: [&#39;MissingAuthSecret&#39;] ↔ [&#39;TypeError: Cannot read property token&#39;]
                  </div>
                  <div className="text-xs text-slate-400">
                    Ação mandatória: <span className="text-rose-400 font-semibold">PARAGEM IMEDIATA</span> e reversão atómica para o último checkpoint estável.
                  </div>
                </div>
              ) : (
                <div className="p-4 bg-emerald-950/20 border border-emerald-500/30 rounded-lg flex items-center gap-3">
                  <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                  <span className="text-xs text-emerald-300 font-medium">
                    Nenhum ciclo ou oscilação detetado. Todos os fingerprints de estado são unívocos e mono-direcionais.
                  </span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Tab 4: Stall & Divergence */}
        {activeSubTab === 'stall_divergence' && (
          <div className="space-y-6" id="divergence-score-card">
            <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-5">
              <h3 className="text-sm font-semibold text-slate-200 mb-2 flex items-center gap-2">
                <XCircle className="w-4 h-4 text-rose-400" />
                Decomposição Transparente do DivergenceScore
              </h3>
              <p className="text-xs text-slate-400 mb-4">
                Score explícito de 5 fatores: Risk Growth (30%), Failure Growth (25%), Coverage Drop (20%), Regression Growth (15%), Rollback Rate (10%).
              </p>

              <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
                <div className="p-3 bg-slate-800/40 rounded border border-slate-700/50">
                  <span className="text-slate-400 text-xs">Crescimento de Risco</span>
                  <div className="text-xl font-bold text-slate-200 mt-1 font-mono">{divergenceScore.riskGrowth.toFixed(3)}</div>
                  <span className="text-[10px] text-slate-500">Peso: 30%</span>
                </div>
                <div className="p-3 bg-slate-800/40 rounded border border-slate-700/50">
                  <span className="text-slate-400 text-xs">Crescimento de Falhas</span>
                  <div className="text-xl font-bold text-slate-200 mt-1 font-mono">{divergenceScore.failureGrowth.toFixed(3)}</div>
                  <span className="text-[10px] text-slate-500">Peso: 25%</span>
                </div>
                <div className="p-3 bg-slate-800/40 rounded border border-slate-700/50">
                  <span className="text-slate-400 text-xs">Queda de Cobertura</span>
                  <div className="text-xl font-bold text-slate-200 mt-1 font-mono">{divergenceScore.coverageDrop.toFixed(3)}</div>
                  <span className="text-[10px] text-slate-500">Peso: 20%</span>
                </div>
                <div className="p-3 bg-slate-800/40 rounded border border-slate-700/50">
                  <span className="text-slate-400 text-xs">Regressões</span>
                  <div className="text-xl font-bold text-slate-200 mt-1 font-mono">{divergenceScore.regressionGrowth.toFixed(3)}</div>
                  <span className="text-[10px] text-slate-500">Peso: 15%</span>
                </div>
                <div className="p-3 bg-slate-800/40 rounded border border-slate-700/50">
                  <span className="text-slate-400 text-xs">Taxa de Rollbacks</span>
                  <div className="text-xl font-bold text-slate-200 mt-1 font-mono">{divergenceScore.rollbackRate.toFixed(3)}</div>
                  <span className="text-[10px] text-slate-500">Peso: 10%</span>
                </div>
              </div>

              <div className="mt-5 p-4 bg-slate-800/50 rounded-lg flex items-center justify-between border border-slate-700">
                <span className="text-xs text-slate-300 font-semibold">Total DivergenceScore:</span>
                <div className="flex items-center gap-2">
                  <span className="text-lg font-bold font-mono text-emerald-400">{divergenceScore.totalScore.toFixed(3)}</span>
                  <span className="text-xs text-slate-400">(Limiar de divergência: 0.850)</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tab 5: Adaptive Budget */}
        {activeSubTab === 'adaptive_budget' && (
          <div className="space-y-6" id="budget-consumption-gauge">
            <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-5">
              <h3 className="text-sm font-semibold text-slate-200 mb-2 flex items-center gap-2">
                <Sliders className="w-4 h-4 text-cyan-400" />
                Orçamento Bounded & Adaptativo (Fase 52 + Sentinel)
              </h3>
              <p className="text-xs text-slate-400 mb-4">
                Limites inegociáveis de passos de reparação, ciclos, runtime e rollbacks permitidos.
              </p>

              <div className="space-y-4">
                <div>
                  <div className="flex justify-between text-xs text-slate-300 mb-1">
                    <span>Reparações Consumidas</span>
                    <span className="font-mono">{budget.consumedRepairs} / {budget.maxRepairs} ({((budget.consumedRepairs / budget.maxRepairs) * 100).toFixed(0)}%)</span>
                  </div>
                  <div className="w-full bg-slate-800 h-2.5 rounded-full overflow-hidden">
                    <div className="bg-cyan-500 h-full rounded-full" style={{ width: `${(budget.consumedRepairs / budget.maxRepairs) * 100}%` }}></div>
                  </div>
                </div>

                <div>
                  <div className="flex justify-between text-xs text-slate-300 mb-1">
                    <span>Tempo de Execução (segundos)</span>
                    <span className="font-mono">{budget.consumedRuntime}s / {budget.maxRuntime}s</span>
                  </div>
                  <div className="w-full bg-slate-800 h-2.5 rounded-full overflow-hidden">
                    <div className="bg-emerald-500 h-full rounded-full" style={{ width: `${(budget.consumedRuntime / budget.maxRuntime) * 100}%` }}></div>
                  </div>
                </div>

                <div>
                  <div className="flex justify-between text-xs text-slate-300 mb-1">
                    <span>Rollbacks Executados</span>
                    <span className="font-mono">{budget.consumedRollbacks} / {budget.maxRollbacks}</span>
                  </div>
                  <div className="w-full bg-slate-800 h-2.5 rounded-full overflow-hidden">
                    <div className="bg-rose-500 h-full rounded-full" style={{ width: `${(budget.consumedRollbacks / budget.maxRollbacks) * 100}%` }}></div>
                  </div>
                </div>
              </div>

              <div className="mt-5 p-3 bg-cyan-950/20 border border-cyan-500/20 rounded-lg flex items-center gap-2 text-xs text-cyan-300">
                <ShieldCheck className="w-4 h-4 text-cyan-400" />
                <span>Orçamento protegido pelo Security Sentinel: nenhuma expansão adaptativa pode ultrapassar 50 reparações ou 600 segundos.</span>
              </div>
            </div>
          </div>
        )}

        {/* Tab 6: Append-Only Ledger */}
        {activeSubTab === 'ledger_audit' && (
          <div className="space-y-6">
            <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-5">
              <h3 className="text-sm font-semibold text-slate-200 mb-2 flex items-center gap-2">
                <Layers className="w-4 h-4 text-cyan-400" />
                Livro-Razão Criptográfico Append-Only (SHA-256)
              </h3>
              <p className="text-xs text-slate-400 mb-4">
                Registo encadeado e imutável de transições de estado, impedindo reordenação ou adulteração de histórico.
              </p>

              <div className="space-y-2">
                {[
                  { seq: 0, event: 'convergence_started', hash: 'sha256:4f9a7210e53a1201', prev: '0000000000000000' },
                  { seq: 1, event: 'progress_recorded', hash: 'sha256:7b2c991823a011ef', prev: 'sha256:4f9a7210e53a1201' },
                  { seq: 2, event: 'progress_recorded', hash: 'sha256:3d8e5108cb927144', prev: 'sha256:7b2c991823a011ef' },
                  { seq: 3, event: 'progress_recorded', hash: 'sha256:9a1f77401129bc33', prev: 'sha256:3d8e5108cb927144' },
                  { seq: 4, event: 'transaction_committed', hash: 'sha256:e4b09f18cb663a99', prev: 'sha256:9a1f77401129bc33' },
                  { seq: 5, event: 'convergence_certificate_created', hash: 'sha256:8a3f701c9b2e5541', prev: 'sha256:e4b09f18cb663a99' },
                ].map((entry) => (
                  <div key={entry.seq} className="p-3 bg-slate-800/40 rounded border border-slate-700/60 flex items-center justify-between text-xs font-mono">
                    <div className="flex items-center gap-3">
                      <span className="text-cyan-400 font-bold">#{entry.seq}</span>
                      <span className="text-slate-200 font-sans font-semibold">{entry.event}</span>
                    </div>
                    <div className="flex items-center gap-4 text-slate-400 text-[11px]">
                      <span>prev: {entry.prev.substring(0, 16)}...</span>
                      <span className="text-emerald-400 font-semibold">hash: {entry.hash.substring(0, 16)}...</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Cryptographic Certificate Modal */}
      {showCertModal && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center p-4 z-50">
          <div className="bg-slate-900 border border-slate-700 rounded-xl p-6 max-w-xl w-full space-y-4 text-xs">
            <div className="flex justify-between items-center border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2 text-cyan-400 font-bold text-sm">
                <FileCheck2 className="w-5 h-5" />
                <span>Certificado Formal de Convergência (Fase 56)</span>
              </div>
              <button onClick={() => setShowCertModal(false)} className="text-slate-400 hover:text-white">
                ✕
              </button>
            </div>

            <div className="space-y-2 font-mono text-slate-300">
              <div><span className="text-slate-500">ID Certificado:</span> {certificate.certificateId}</div>
              <div><span className="text-slate-500">ID Transação:</span> {certificate.transactionId}</div>
              <div><span className="text-slate-500">Razão Terminação:</span> <span className="text-cyan-400">{certificate.terminationReason}</span></div>
              <div><span className="text-slate-500">Veredicto Final:</span> <span className="text-emerald-400 font-bold">{certificate.convergenceVerdict}</span></div>
              <div><span className="text-slate-500">Hash Inicial:</span> {certificate.initialStateHash}</div>
              <div><span className="text-slate-500">Hash Final:</span> {certificate.finalStateHash}</div>
              <div><span className="text-slate-500">Total Passos:</span> {certificate.totalIterations} em {certificate.totalDurationSeconds}s</div>
              <div className="p-3 bg-black/40 rounded border border-cyan-500/30 text-cyan-300 break-all">
                <span className="text-slate-500 block text-[10px]">Assinatura Criptográfica SHA-256:</span>
                {certificate.signature}
              </div>
            </div>

            <div className="flex items-center justify-between pt-3 border-t border-slate-800">
              <div className="flex items-center gap-2 text-emerald-400">
                <ShieldCheck className="w-4 h-4" />
                <span>Security Sentinel: APROVADO</span>
              </div>
              <button
                id="verify-cert-button"
                onClick={() => setCertVerified(true)}
                className="px-3 py-1.5 rounded bg-emerald-600 hover:bg-emerald-500 text-white font-medium transition"
              >
                {certVerified ? 'Assinatura Verificada ✓' : 'Validar Assinatura'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
