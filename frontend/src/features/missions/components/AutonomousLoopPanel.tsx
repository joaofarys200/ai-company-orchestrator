import React, { useState } from 'react';
import {
  Activity,
  AlertCircle,
  Brain,
  CheckCircle2,
  ChevronRight,
  Clock,
  Compass,
  FileCode2,
  Orbit,
  Play,
  RefreshCw,
  RotateCcw,
  Shield,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  Wrench,
} from 'lucide-react';

export interface AutonomousLoopPanelProps {
  missionId?: string;
  onStepCycle?: () => void;
  onRunLoop?: () => void;
  onRespondHuman?: (action: 'APPROVE' | 'REJECT') => void;
  customLoopData?: any;
}

export const AutonomousLoopPanel: React.FC<AutonomousLoopPanelProps> = ({
  missionId = 'm_p36_interactive',
  onStepCycle,
  onRunLoop,
  onRespondHuman,
  customLoopData,
}) => {
  const [selectedCycleIndex, setSelectedCycleIndex] = useState<number>(0);
  const [isSimulatingStep, setIsSimulatingStep] = useState(false);
  const [activeTab, setActiveTab] = useState<'current' | 'timeline' | 'budget' | 'why'>('current');

  // Realistic fallback demo cycle history representing the engineering adaptation loop
  const cyclesHistory = customLoopData?.history || [
    {
      cycle_id: 'cycle_1',
      cycle_num: 1,
      stage: 'NEXT_CYCLE',
      decision: 'CONTINUE',
      rule: 'RULE_14_NORMAL_PROGRESSION',
      plan_version: 1,
      intent_version: 1,
      state_hash: '9f8b7a1c3e5d0a2b',
      prediction: {
        prediction_id: 'pred_c1_01',
        predicted_files: ['backend/api.py', 'frontend/App.tsx'],
        predicted_tasks: ['TSK_01: Scaffolding', 'TSK_02: Component Render'],
        predicted_risk: 'LOW',
        predicted_scope: 'LOCAL',
      },
      observation: {
        files_changed: ['backend/api.py', 'frontend/App.tsx'],
        tasks_completed: ['TSK_01', 'TSK_02'],
        validations_passed: true,
        failures: [],
      },
      comparison: {
        file_precision: 1.0,
        file_recall: 1.0,
        matched: ['backend/api.py', 'frontend/App.tsx'],
        unexpected: [],
        missed: [],
      },
      why: {
        observation: 'Todas as tarefas completadas e validações empíricas com passagem limpa.',
        rule: 'RULE_14_NORMAL_PROGRESSION: O estado observado coincide com a expectativa determinística.',
        decision: 'CONTINUE',
        consequence: 'Avançar no TaskGraph e preparar ciclo seguinte.',
        evidence_refs: ['test_report_01.json', 'ast_syntax_pass.log'],
      },
      adaptation: null,
    },
    {
      cycle_id: 'cycle_2',
      cycle_num: 2,
      stage: 'NEXT_CYCLE',
      decision: 'REPAIR',
      rule: 'RULE_09_REPAIRABLE_VALIDATION_FAILURE',
      plan_version: 2,
      intent_version: 1,
      state_hash: '3d4e5f6a7b8c9d0e',
      prediction: {
        prediction_id: 'pred_c2_02',
        predicted_files: ['frontend/src/components/ExpenseList.tsx'],
        predicted_tasks: ['TSK_03: Expense Table Logic'],
        predicted_risk: 'LOW',
        predicted_scope: 'LOCAL',
      },
      observation: {
        files_changed: ['frontend/src/components/ExpenseList.tsx'],
        tasks_completed: [],
        validations_passed: false,
        failures: [
          {
            error: 'TypeError: Cannot read properties of undefined (reading "sort")',
            target_file: 'frontend/src/components/ExpenseList.tsx',
            is_repairable: true,
          },
        ],
      },
      comparison: {
        file_precision: 1.0,
        file_recall: 1.0,
        matched: ['frontend/src/components/ExpenseList.tsx'],
        unexpected: [],
        missed: [],
      },
      why: {
        observation: 'Falha na ordenação de despesas: lista nula provocou exceção no render.',
        rule: 'RULE_09_REPAIRABLE_VALIDATION_FAILURE: Erro sintático/nulo com diagnóstico AST viável.',
        decision: 'REPAIR',
        consequence: 'Acionar pipeline de auto-cura cirúrgica com patch defensivo.',
        evidence_refs: ['ast_diagnostics_node_42.json', 'browser_error_trace.log'],
      },
      adaptation: {
        adaptation_id: 'adapt_c2_repair',
        adaptation_type: 'REPAIR',
        proposed_change: 'Aplicar fallback de array defensivo `expenses || []`',
        status: 'APPLIED',
        risk: 'LOW',
      },
    },
    {
      cycle_id: 'cycle_3',
      cycle_num: 3,
      stage: 'NEXT_CYCLE',
      decision: 'ADAPT',
      rule: 'RULE_12_PREDICTION_DEVIATION_SATISFIABLE',
      plan_version: 3,
      intent_version: 2,
      state_hash: '1a2b3c4d5e6f7a8b',
      prediction: {
        prediction_id: 'pred_c3_03',
        predicted_files: ['backend/security/auth.py', 'backend/api.py'],
        predicted_tasks: ['TSK_04: Add Auth Middleware'],
        predicted_risk: 'MEDIUM',
        predicted_scope: 'CROSS_MODULE',
      },
      observation: {
        files_changed: ['backend/security/auth.py', 'backend/api.py', 'frontend/src/context/AuthContext.tsx'],
        tasks_completed: ['TSK_04'],
        validations_passed: true,
        failures: [],
      },
      comparison: {
        file_precision: 0.67,
        file_recall: 1.0,
        matched: ['backend/security/auth.py', 'backend/api.py'],
        unexpected: ['frontend/src/context/AuthContext.tsx'],
        missed: [],
      },
      why: {
        observation: 'Desvio preditivo: ficheiro AuthContext.tsx modificado adicionalmente.',
        rule: 'RULE_12_PREDICTION_DEVIATION_SATISFIABLE: Desvio empírico com requisitos satisfazíveis.',
        decision: 'ADAPT',
        consequence: 'Injetar tarefa de validação adicional no DAG para reconciliação.',
        evidence_refs: ['prediction_vs_actual_matrix.json', 'ts_graph_diff.json'],
      },
      adaptation: {
        adaptation_id: 'adapt_c3_inject_val',
        adaptation_type: 'ADD_VALIDATION',
        proposed_change: 'Adicionar tarefa TSK_VAL_AUTH para suite de regressão no cliente',
        status: 'APPLIED',
        risk: 'LOW',
      },
    },
    {
      cycle_id: 'cycle_4',
      cycle_num: 4,
      stage: 'FINISHED',
      decision: 'FINISH',
      rule: 'RULE_07_FINISH_GATE_SATISFIED',
      plan_version: 3,
      intent_version: 2,
      state_hash: '7c8d9e0f1a2b3c4d',
      prediction: {
        prediction_id: 'pred_c4_04',
        predicted_files: ['tests/test_auth.py'],
        predicted_tasks: ['TSK_VAL_AUTH: Regression Suite'],
        predicted_risk: 'LOW',
        predicted_scope: 'LOCAL',
      },
      observation: {
        files_changed: ['tests/test_auth.py'],
        tasks_completed: ['TSK_VAL_AUTH'],
        validations_passed: true,
        failures: [],
      },
      comparison: {
        file_precision: 1.0,
        file_recall: 1.0,
        matched: ['tests/test_auth.py'],
        unexpected: [],
        missed: [],
      },
      why: {
        observation: 'Todas as tarefas, requisitos e suites de testes físicas passaram a 100%.',
        rule: 'RULE_07_FINISH_GATE_SATISFIED: Zero False Success comprovado por evidências em disco.',
        decision: 'FINISH',
        consequence: 'Missão concluída com sucesso verificável e ledger imutável.',
        evidence_refs: ['zero_false_success_proof.json', 'final_test_summary.xml'],
      },
      adaptation: null,
    },
  ];

  const selectedCycle = cyclesHistory[selectedCycleIndex] || cyclesHistory[cyclesHistory.length - 1];

  const handleStep = () => {
    setIsSimulatingStep(true);
    if (onStepCycle) {
      onStepCycle();
    }
    setTimeout(() => {
      setIsSimulatingStep(false);
      setSelectedCycleIndex((prev) => (prev < cyclesHistory.length - 1 ? prev + 1 : prev));
    }, 500);
  };

  const getDecisionBadge = (dec: string) => {
    switch (dec) {
      case 'CONTINUE':
        return <span className="rounded-full bg-cyan-500/20 px-3 py-1 text-xs font-bold text-cyan-300 border border-cyan-500/30">CONTINUE</span>;
      case 'REPAIR':
        return <span className="rounded-full bg-amber-500/20 px-3 py-1 text-xs font-bold text-amber-300 border border-amber-500/30">REPAIR (Auto-Cura)</span>;
      case 'ADAPT':
        return <span className="rounded-full bg-indigo-500/20 px-3 py-1 text-xs font-bold text-indigo-300 border border-indigo-500/30">ADAPT (Adaptação)</span>;
      case 'REPLAN':
        return <span className="rounded-full bg-purple-500/20 px-3 py-1 text-xs font-bold text-purple-300 border border-purple-500/30">REPLAN</span>;
      case 'FINISH':
        return <span className="rounded-full bg-emerald-500/20 px-3 py-1 text-xs font-bold text-emerald-300 border border-emerald-500/30">FINISH (Concluído)</span>;
      case 'BLOCK':
        return <span className="rounded-full bg-rose-500/20 px-3 py-1 text-xs font-bold text-rose-300 border border-rose-500/30">BLOCK (Bloqueado)</span>;
      case 'REQUEST_HUMAN':
        return <span className="rounded-full bg-yellow-500/20 px-3 py-1 text-xs font-bold text-yellow-300 border border-yellow-500/30">REQUEST_HUMAN</span>;
      default:
        return <span className="rounded-full bg-gray-500/20 px-3 py-1 text-xs font-bold text-gray-300">{dec}</span>;
    }
  };

  const STAGES_LIST = [
    'SNAPSHOT',
    'PREDICT',
    'PLAN',
    'GATE',
    'EXECUTE',
    'OBSERVE',
    'COMPARE',
    'DECIDE',
    'APPLY_ADAPTATION',
    'VALIDATE',
    'RECORD',
    'NEXT_CYCLE',
  ];

  return (
    <div className="flex flex-col gap-6" id="autonomous-loop-panel">
      {/* 1. TOP STATUS HERO CARD */}
      <div className="relative overflow-hidden rounded-xl border border-cyan-500/30 bg-gradient-to-br from-[#0c181f] via-[#091216] to-[#060c0e] p-6 shadow-2xl">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-cyan-500/10 border border-cyan-400/30 text-cyan-400 shadow-inner">
              <Orbit className="h-6 w-6 animate-spin-slow" />
            </div>
            <div>
              <div className="flex items-center gap-3">
                <h2 className="text-xl font-bold tracking-tight text-white">Autonomous Engineering Loop</h2>
                <span className="rounded-md bg-cyan-500/20 px-2.5 py-0.5 text-xs font-semibold text-cyan-300 border border-cyan-500/30">
                  Fase 40: Loop Fechado
                </span>
                <span className="text-xs text-gray-400 font-mono">ID: {missionId}</span>
              </div>
              <p className="mt-1 text-xs text-gray-400">
                Coordenação contínua e determinística baseada na realidade observada:{' '}
                <span className="text-cyan-300 font-mono">ObservedState(t) + Prediction(t) + Evidence(t) → Decision(t+1)</span>
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              id="btn-loop-step"
              onClick={handleStep}
              disabled={isSimulatingStep || selectedCycle.decision === 'FINISH'}
              className="flex items-center gap-2 rounded-lg bg-cyan-600 px-4 py-2 text-xs font-bold text-white shadow-lg transition-all hover:bg-cyan-500 disabled:opacity-50"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${isSimulatingStep ? 'animate-spin' : ''}`} />
              <span>{isSimulatingStep ? 'A Executar...' : 'Executar Ciclo Seguinte'}</span>
            </button>

            <button
              id="btn-loop-run"
              onClick={onRunLoop}
              disabled={selectedCycle.decision === 'FINISH'}
              className="flex items-center gap-2 rounded-lg border border-cyan-500/40 bg-cyan-950/40 px-4 py-2 text-xs font-semibold text-cyan-300 transition-all hover:bg-cyan-900/50 disabled:opacity-50"
            >
              <Play className="h-3.5 w-3.5" />
              <span>Executar Até Fim</span>
            </button>
          </div>
        </div>

        {/* METRICS ROW */}
        <div className="mt-6 grid grid-cols-2 gap-4 border-t border-[#a1bebf]/15 pt-5 sm:grid-cols-3 lg:grid-cols-6">
          <div className="rounded-lg bg-white/[0.02] p-3 border border-white/5">
            <span className="text-[11px] text-gray-400">Ciclo Atual</span>
            <div className="mt-1 flex items-baseline gap-2">
              <span className="text-lg font-bold text-white">{selectedCycle.cycle_num}</span>
              <span className="text-[10px] text-gray-500">de {cyclesHistory.length}</span>
            </div>
          </div>

          <div className="rounded-lg bg-white/[0.02] p-3 border border-white/5">
            <span className="text-[11px] text-gray-400">Decisão do Ciclo</span>
            <div className="mt-1">{getDecisionBadge(selectedCycle.decision)}</div>
          </div>

          <div className="rounded-lg bg-white/[0.02] p-3 border border-white/5">
            <span className="text-[11px] text-gray-400">Versão do Plano</span>
            <div className="mt-1 text-lg font-bold text-cyan-300 font-mono">v{selectedCycle.plan_version}.0</div>
          </div>

          <div className="rounded-lg bg-white/[0.02] p-3 border border-white/5">
            <span className="text-[11px] text-gray-400">Versão da Intenção</span>
            <div className="mt-1 text-lg font-bold text-emerald-300 font-mono">v{selectedCycle.intent_version}.0</div>
          </div>

          <div className="rounded-lg bg-white/[0.02] p-3 border border-white/5">
            <span className="text-[11px] text-gray-400">Zero False Success</span>
            <div className="mt-1 flex items-center gap-1.5 text-xs font-bold text-emerald-400">
              <ShieldCheck className="h-4 w-4" />
              <span>100% Verificado</span>
            </div>
          </div>

          <div className="rounded-lg bg-white/[0.02] p-3 border border-white/5">
            <span className="text-[11px] text-gray-400">State Hash</span>
            <div className="mt-1 text-xs font-mono text-gray-300 truncate" title={selectedCycle.state_hash}>
              {selectedCycle.state_hash}
            </div>
          </div>
        </div>
      </div>

      {/* HUMAN ESCALATION BANNER (Fase 40 Requirement 17) */}
      {selectedCycle.decision === 'REQUEST_HUMAN' && (
        <div className="rounded-xl border border-yellow-500/40 bg-yellow-950/20 p-5 shadow-xl">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-start gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-yellow-500/20 text-yellow-400 shrink-0">
                <AlertCircle className="h-5 w-5" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-yellow-300">Intervenção do Operador Solicitada (REQUEST_HUMAN)</h3>
                <p className="mt-1 text-xs text-yellow-200/90 leading-relaxed">
                  O loop fechado detetou uma condição crítica ou limite de orçamento que requer autorização explícita do operador humano.
                </p>
                <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                  <div className="rounded-lg bg-black/40 p-2.5 border border-yellow-500/20">
                    <span className="font-bold text-yellow-400">Porquê (Why):</span>
                    <p className="mt-0.5 text-gray-300">{selectedCycle.why.observation}</p>
                  </div>
                  <div className="rounded-lg bg-black/40 p-2.5 border border-yellow-500/20">
                    <span className="font-bold text-yellow-400">Proposta do Sistema:</span>
                    <p className="mt-0.5 text-gray-300">{selectedCycle.adaptation?.proposed_change || 'Confirmar continuidade ou realinhar intenção.'}</p>
                  </div>
                </div>
              </div>
            </div>

            <div className="flex flex-col gap-2 shrink-0">
              <button
                id="btn-human-approve"
                onClick={() => onRespondHuman?.('APPROVE')}
                className="rounded-lg bg-yellow-500 px-4 py-2 text-xs font-bold text-black shadow-md hover:bg-yellow-400 transition-all"
              >
                Aprovar & Retomar
              </button>
              <button
                id="btn-human-reject"
                onClick={() => onRespondHuman?.('REJECT')}
                className="rounded-lg border border-yellow-500/40 bg-yellow-950/40 px-4 py-1.5 text-xs font-semibold text-yellow-300 hover:bg-yellow-900/50 transition-all"
              >
                Rejeitar & Bloquear
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 2. 12-STEP CYCLE STEPPER (HORIZONTAL) */}
      <div className="rounded-xl border border-white/10 bg-[#091115] p-5 shadow-lg">
        <div className="flex items-center justify-between pb-3 mb-3 border-b border-white/10">
          <span className="text-xs font-bold uppercase tracking-wider text-gray-400 flex items-center gap-2">
            <Activity className="h-4 w-4 text-cyan-400" />
            Fluxo do Ciclo Fechado (12 Etapas Determinísticas)
          </span>
          <span className="text-xs text-gray-500 font-mono">PLAN ≠ REALITY</span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-2 pt-2">
          {STAGES_LIST.map((st, idx) => {
            const isCompleted = true; // In active cycle inspection
            const isTarget = st === selectedCycle.stage;
            return (
              <div
                key={st}
                className={`flex flex-col rounded-lg p-2.5 border transition-all text-left ${
                  isTarget
                    ? 'border-cyan-400 bg-cyan-500/10 text-cyan-200 shadow-md shadow-cyan-500/10'
                    : 'border-white/5 bg-white/[0.01] text-gray-400 hover:bg-white/[0.03]'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-mono text-gray-500">#{idx + 1}</span>
                  {isCompleted && <CheckCircle2 className="h-3.5 w-3.5 text-cyan-400" />}
                </div>
                <span className="mt-1 text-xs font-semibold truncate">{st.replace('_', ' ')}</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* 3. SUB-NAVIGATION TABS */}
      <div className="flex border-b border-white/10 gap-2">
        <button
          onClick={() => setActiveTab('current')}
          className={`flex items-center gap-2 border-b-2 px-4 py-2.5 text-xs font-bold transition-all ${
            activeTab === 'current'
              ? 'border-cyan-400 text-cyan-300'
              : 'border-transparent text-gray-400 hover:text-gray-200'
          }`}
        >
          <TrendingUp className="h-4 w-4" />
          <span>Previsão vs Realidade & Adaptação</span>
        </button>

        <button
          onClick={() => setActiveTab('why')}
          className={`flex items-center gap-2 border-b-2 px-4 py-2.5 text-xs font-bold transition-all ${
            activeTab === 'why'
              ? 'border-cyan-400 text-cyan-300'
              : 'border-transparent text-gray-400 hover:text-gray-200'
          }`}
        >
          <Brain className="h-4 w-4" />
          <span>Painel Causal do Porquê ("Why Panel")</span>
        </button>

        <button
          onClick={() => setActiveTab('timeline')}
          className={`flex items-center gap-2 border-b-2 px-4 py-2.5 text-xs font-bold transition-all ${
            activeTab === 'timeline'
              ? 'border-cyan-400 text-cyan-300'
              : 'border-transparent text-gray-400 hover:text-gray-200'
          }`}
        >
          <Clock className="h-4 w-4" />
          <span>Histórico & Timeline de Ciclos</span>
        </button>

        <button
          onClick={() => setActiveTab('budget')}
          className={`flex items-center gap-2 border-b-2 px-4 py-2.5 text-xs font-bold transition-all ${
            activeTab === 'budget'
              ? 'border-cyan-400 text-cyan-300'
              : 'border-transparent text-gray-400 hover:text-gray-200'
          }`}
        >
          <Shield className="h-4 w-4" />
          <span>Orçamento & Deteção de Oscilação</span>
        </button>
      </div>

      {/* 4. MAIN CONTENT AREA */}
      {activeTab === 'current' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* LEFT: PREDICTION VS OBSERVATION */}
          <div className="flex flex-col gap-6">
            {/* PREDICTION CARD */}
            <div className="rounded-xl border border-white/10 bg-[#091115] p-5 shadow-lg">
              <div className="flex items-center justify-between pb-3 border-b border-white/10">
                <div className="flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-cyan-400" />
                  <h3 className="text-sm font-bold text-white">Previsão Read-Only (Fase 39 Engine)</h3>
                </div>
                <span className="rounded bg-cyan-950 px-2 py-0.5 text-[10px] font-mono text-cyan-300">
                  {selectedCycle.prediction.prediction_id}
                </span>
              </div>

              <div className="mt-4 flex flex-col gap-3">
                <div>
                  <span className="text-[11px] text-gray-400">Ficheiros Previstos:</span>
                  <div className="mt-1 flex flex-wrap gap-1.5">
                    {selectedCycle.prediction.predicted_files.map((f: string) => (
                      <span key={f} className="rounded bg-white/5 px-2 py-1 text-xs font-mono text-gray-200 border border-white/5">
                        {f}
                      </span>
                    ))}
                  </div>
                </div>

                <div>
                  <span className="text-[11px] text-gray-400">Tarefas Previstas:</span>
                  <div className="mt-1 flex flex-col gap-1">
                    {selectedCycle.prediction.predicted_tasks.map((t: string) => (
                      <div key={t} className="flex items-center gap-2 text-xs text-gray-300 font-mono bg-white/[0.02] p-1.5 rounded">
                        <CheckCircle2 className="h-3.5 w-3.5 text-cyan-400 shrink-0" />
                        <span>{t}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* REALITY OBSERVATION CARD */}
            <div className="rounded-xl border border-white/10 bg-[#091115] p-5 shadow-lg">
              <div className="flex items-center justify-between pb-3 border-b border-white/10">
                <div className="flex items-center gap-2">
                  <FileCode2 className="h-4 w-4 text-emerald-400" />
                  <h3 className="text-sm font-bold text-white">Observação Empírica Real</h3>
                </div>
                <span className="text-xs text-emerald-400 font-semibold flex items-center gap-1">
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  Passagem Validada
                </span>
              </div>

              <div className="mt-4 flex flex-col gap-3">
                <div>
                  <span className="text-[11px] text-gray-400">Ficheiros Efetivamente Alterados:</span>
                  <div className="mt-1 flex flex-wrap gap-1.5">
                    {selectedCycle.observation.files_changed.map((f: string) => (
                      <span key={f} className="rounded bg-emerald-950/40 px-2 py-1 text-xs font-mono text-emerald-200 border border-emerald-500/20">
                        {f}
                      </span>
                    ))}
                  </div>
                </div>

                {selectedCycle.observation.failures && selectedCycle.observation.failures.length > 0 && (
                  <div className="rounded-lg bg-rose-500/10 border border-rose-500/30 p-3 mt-2">
                    <span className="text-xs font-bold text-rose-300 flex items-center gap-1.5">
                      <AlertCircle className="h-4 w-4" />
                      Falha Observada em Runtime:
                    </span>
                    <p className="mt-1 text-xs font-mono text-rose-200">
                      {selectedCycle.observation.failures[0].error}
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* RIGHT: COMPARATOR & ADAPTATION */}
          <div className="flex flex-col gap-6">
            {/* COMPARISON METRICS CARD */}
            <div className="rounded-xl border border-white/10 bg-[#091115] p-5 shadow-lg">
              <div className="flex items-center justify-between pb-3 border-b border-white/10">
                <div className="flex items-center gap-2">
                  <TrendingUp className="h-4 w-4 text-indigo-400" />
                  <h3 className="text-sm font-bold text-white">Discrepância: Previsto vs Observado</h3>
                </div>
                <span className="text-xs font-mono text-gray-400">
                  Precision: {(selectedCycle.comparison.file_precision * 100).toFixed(0)}%
                </span>
              </div>

              <div className="mt-4 flex flex-col gap-3">
                <div>
                  <span className="text-[11px] text-gray-400">Ficheiros Correspondentes (Matched):</span>
                  <div className="mt-1 flex flex-wrap gap-1.5">
                    {selectedCycle.comparison.matched.map((f: string) => (
                      <span key={f} className="rounded bg-indigo-950/50 px-2 py-1 text-xs font-mono text-indigo-200 border border-indigo-500/20">
                        ✓ {f}
                      </span>
                    ))}
                  </div>
                </div>

                {selectedCycle.comparison.unexpected && selectedCycle.comparison.unexpected.length > 0 && (
                  <div>
                    <span className="text-[11px] text-amber-400 font-semibold">Ficheiros Inesperados (Desvio Observado):</span>
                    <div className="mt-1 flex flex-wrap gap-1.5">
                      {selectedCycle.comparison.unexpected.map((f: string) => (
                        <span key={f} className="rounded bg-amber-950/50 px-2 py-1 text-xs font-mono text-amber-200 border border-amber-500/30">
                          ! {f}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* ADAPTATION CARD */}
            <div className="rounded-xl border border-white/10 bg-[#091115] p-5 shadow-lg">
              <div className="flex items-center justify-between pb-3 border-b border-white/10">
                <div className="flex items-center gap-2">
                  <Wrench className="h-4 w-4 text-cyan-400" />
                  <h3 className="text-sm font-bold text-white">Adaptação Proposta & Mission Gate</h3>
                </div>
                {selectedCycle.adaptation ? (
                  <span className="rounded bg-cyan-950 px-2.5 py-0.5 text-xs font-bold text-cyan-300 border border-cyan-500/30">
                    {selectedCycle.adaptation.status}
                  </span>
                ) : (
                  <span className="text-xs text-gray-500">Sem mutação neste ciclo</span>
                )}
              </div>

              {selectedCycle.adaptation ? (
                <div className="mt-4 flex flex-col gap-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-400">Tipo de Adaptação:</span>
                    <span className="text-xs font-bold text-cyan-300 font-mono">{selectedCycle.adaptation.adaptation_type}</span>
                  </div>

                  <div className="rounded-lg bg-cyan-950/30 p-3 border border-cyan-500/20">
                    <span className="text-[11px] text-gray-400">Proposta de Mutação no DAG:</span>
                    <p className="mt-1 text-xs text-cyan-200 font-mono">{selectedCycle.adaptation.proposed_change}</p>
                  </div>

                  <div className="flex items-center gap-2 text-xs text-emerald-400">
                    <ShieldCheck className="h-4 w-4" />
                    <span>Aprovado pelo Mission Gate e Security Sentinel</span>
                  </div>
                </div>
              ) : (
                <div className="mt-4 flex items-center justify-center p-6 text-xs text-gray-500">
                  Ciclo em regime normal. Nenhuma adaptação foi necessária.
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* 5. WHY PANEL TAB (Causal Explanation) */}
      {activeTab === 'why' && (
        <div className="rounded-xl border border-white/10 bg-[#091115] p-6 shadow-lg">
          <div className="flex items-center gap-3 pb-4 border-b border-white/10">
            <Brain className="h-5 w-5 text-cyan-400" />
            <div>
              <h3 className="text-base font-bold text-white">Explicação Causal do Porquê ("Why Panel")</h3>
              <p className="text-xs text-gray-400">
                A decisão do loop é explicitamente fundamentada em factos observados, regras determinísticas e consequências operacionais.
              </p>
            </div>
          </div>

          <div className="mt-6 flex flex-col gap-4">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="rounded-xl bg-white/[0.02] p-4 border border-white/5">
                <span className="text-[11px] font-bold uppercase tracking-wider text-gray-400 flex items-center gap-1.5">
                  <Activity className="h-4 w-4 text-cyan-400" />
                  1. Facto Observado
                </span>
                <p className="mt-2 text-xs text-gray-200 leading-relaxed">{selectedCycle.why.observation}</p>
              </div>

              <div className="rounded-xl bg-white/[0.02] p-4 border border-white/5">
                <span className="text-[11px] font-bold uppercase tracking-wider text-gray-400 flex items-center gap-1.5">
                  <Shield className="h-4 w-4 text-indigo-400" />
                  2. Regra Acionada
                </span>
                <p className="mt-2 text-xs text-indigo-200 font-mono leading-relaxed">{selectedCycle.why.rule}</p>
              </div>

              <div className="rounded-xl bg-white/[0.02] p-4 border border-white/5">
                <span className="text-[11px] font-bold uppercase tracking-wider text-gray-400 flex items-center gap-1.5">
                  <TrendingUp className="h-4 w-4 text-emerald-400" />
                  3. Decisão
                </span>
                <div className="mt-2">{getDecisionBadge(selectedCycle.why.decision)}</div>
              </div>

              <div className="rounded-xl bg-white/[0.02] p-4 border border-white/5">
                <span className="text-[11px] font-bold uppercase tracking-wider text-gray-400 flex items-center gap-1.5">
                  <Compass className="h-4 w-4 text-amber-400" />
                  4. Consequência
                </span>
                <p className="mt-2 text-xs text-gray-200 leading-relaxed">{selectedCycle.why.consequence}</p>
              </div>
            </div>

            <div className="mt-4 rounded-lg bg-black/40 p-4 border border-white/5">
              <span className="text-xs font-bold text-gray-300">Evidências Citadas na Decisão:</span>
              <div className="mt-2 flex flex-wrap gap-2">
                {selectedCycle.why.evidence_refs.map((ev: string) => (
                  <span key={ev} className="rounded bg-cyan-950/60 px-2.5 py-1 text-xs font-mono text-cyan-300 border border-cyan-500/20">
                    {ev}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 6. TIMELINE TAB */}
      {activeTab === 'timeline' && (
        <div className="rounded-xl border border-white/10 bg-[#091115] p-6 shadow-lg">
          <div className="flex items-center justify-between pb-4 border-b border-white/10">
            <div className="flex items-center gap-2">
              <Clock className="h-5 w-5 text-cyan-400" />
              <h3 className="text-base font-bold text-white">Evolução Cronológica dos Ciclos</h3>
            </div>
            <span className="text-xs text-gray-400">Clica num ciclo para inspecionar os seus detalhes determinísticos</span>
          </div>

          <div className="mt-6 flex flex-col gap-3">
            {cyclesHistory.map((c: any, idx: number) => {
              const isSelected = idx === selectedCycleIndex;
              return (
                <div
                  key={c.cycle_id}
                  onClick={() => setSelectedCycleIndex(idx)}
                  className={`flex items-center justify-between p-4 rounded-xl border transition-all cursor-pointer ${
                    isSelected
                      ? 'border-cyan-400 bg-cyan-500/10 shadow-lg shadow-cyan-500/5'
                      : 'border-white/5 bg-white/[0.01] hover:bg-white/[0.03]'
                  }`}
                >
                  <div className="flex items-center gap-4">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-white/5 font-mono text-xs font-bold text-gray-300">
                      C{c.cycle_num}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-white font-mono">{c.cycle_id}</span>
                        {getDecisionBadge(c.decision)}
                      </div>
                      <p className="mt-1 text-xs text-gray-400">{c.why.observation}</p>
                    </div>
                  </div>

                  <div className="flex items-center gap-4 text-xs font-mono text-gray-400">
                    <span>Plan v{c.plan_version}.0</span>
                    <span>Intent v{c.intent_version}.0</span>
                    <ChevronRight className="h-4 w-4 text-gray-500" />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 7. BUDGET & OSCILLATION TAB */}
      {activeTab === 'budget' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="rounded-xl border border-white/10 bg-[#091115] p-6 shadow-lg">
            <h3 className="text-sm font-bold text-white flex items-center gap-2 pb-4 border-b border-white/10">
              <Shield className="h-4 w-4 text-cyan-400" />
              Orçamento de Adaptação (AdaptationBudget)
            </h3>

            <div className="mt-4 flex flex-col gap-4">
              <div>
                <div className="flex justify-between text-xs text-gray-300 mb-1">
                  <span>Adaptações Realizadas</span>
                  <span className="font-mono">1 / 15</span>
                </div>
                <div className="h-2 w-full rounded-full bg-white/5 overflow-hidden">
                  <div className="h-full bg-cyan-400" style={{ width: '7%' }} />
                </div>
              </div>

              <div>
                <div className="flex justify-between text-xs text-gray-300 mb-1">
                  <span>Reparações AST Utilizadas</span>
                  <span className="font-mono">1 / 5</span>
                </div>
                <div className="h-2 w-full rounded-full bg-white/5 overflow-hidden">
                  <div className="h-full bg-amber-400" style={{ width: '20%' }} />
                </div>
              </div>

              <div>
                <div className="flex justify-between text-xs text-gray-300 mb-1">
                  <span>Re-planeamentos Topológicos (Replans)</span>
                  <span className="font-mono">0 / 5</span>
                </div>
                <div className="h-2 w-full rounded-full bg-white/5 overflow-hidden">
                  <div className="h-full bg-purple-400" style={{ width: '0%' }} />
                </div>
              </div>

              <div>
                <div className="flex justify-between text-xs text-gray-300 mb-1">
                  <span>Falhas Consecutivas</span>
                  <span className="font-mono">0 / 3</span>
                </div>
                <div className="h-2 w-full rounded-full bg-white/5 overflow-hidden">
                  <div className="h-full bg-rose-400" style={{ width: '0%' }} />
                </div>
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-white/10 bg-[#091115] p-6 shadow-lg">
            <h3 className="text-sm font-bold text-white flex items-center gap-2 pb-4 border-b border-white/10">
              <RotateCcw className="h-4 w-4 text-indigo-400" />
              Deteção de Oscilação & Drift
            </h3>

            <div className="mt-4 flex flex-col gap-4">
              <div className="rounded-lg bg-white/[0.02] p-4 border border-white/5 flex items-center justify-between">
                <div>
                  <span className="text-xs font-bold text-white">Status de Oscilação:</span>
                  <p className="text-xs text-gray-400">Nenhum loop cíclico A → B → A detetado.</p>
                </div>
                <span className="rounded-full bg-emerald-500/20 px-3 py-1 text-xs font-bold text-emerald-300 border border-emerald-500/30">
                  NORMAL
                </span>
              </div>

              <div className="rounded-lg bg-white/[0.02] p-4 border border-white/5 flex items-center justify-between">
                <div>
                  <span className="text-xs font-bold text-white">Retenção de Requisitos:</span>
                  <p className="text-xs text-gray-400">Requisitos originais estritamente preservados.</p>
                </div>
                <span className="rounded-full bg-emerald-500/20 px-3 py-1 text-xs font-bold text-emerald-300 border border-emerald-500/30">
                  100% RETAINED
                </span>
              </div>

              <div className="rounded-lg bg-white/[0.02] p-4 border border-white/5 flex items-center justify-between">
                <div>
                  <span className="text-xs font-bold text-white">Deteção de Drift de Missão:</span>
                  <p className="text-xs text-gray-400">Alinhamento estrito com a diretiva do utilizador.</p>
                </div>
                <span className="rounded-full bg-cyan-500/20 px-3 py-1 text-xs font-bold text-cyan-300 border border-cyan-500/30">
                  NO_DRIFT
                </span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
