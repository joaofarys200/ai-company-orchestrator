import React, { useState } from 'react';
import {
  CheckCircle2,
  AlertTriangle,
  ShieldAlert,
  FileCheck,
  Play,
  Sparkles,
  Layers,
  Eye,
  Activity,
  Award,
  Hash,
  Clock,
  Zap,
  Check,
  X,
} from 'lucide-react';

interface AutonomousTaskCompletionPanelProps {
  missionId?: string;
}

export const AutonomousTaskCompletionPanel: React.FC<AutonomousTaskCompletionPanelProps> = ({
  missionId = 'm_p57_demo_01',
}) => {
  const [activeTab, setActiveTab] = useState<
    'intent_understanding' | 'mission_flow' | 'evidence_ledger' | 'completion_proof' | 'human_escalation' | 'scorecard'
  >('intent_understanding');

  const [intentInput, setIntentInput] = useState(
    'Criar uma API de utilizadores com frontend React e validação de contratos em tempo real'
  );
  const [isExecuting, setIsExecuting] = useState(false);
  const [showProofModal, setShowProofModal] = useState(false);

  // Active Simulated Mission State
  const [missionState, setMissionState] = useState({
    mission_id: missionId || 'msn_phase57_prod_01',
    task_id: 'task_user_api_01',
    objective: 'Criar uma API de utilizadores com frontend React e validação de contratos',
    original_objective: 'Criar uma API de utilizadores com frontend React e validação de contratos',
    state: 'COMPLETED',
    risk: 0.12,
    domain: 'fullstack',
    confidence: 0.95,
    final_decision: 'MISSION_PROVEN_COMPLETE',
    initial_state_hash: 'a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8',
    final_state_hash: 'f1e2d3c4b5a6f7e8d9c0b1a2f3e4d5c6b7a8f9e0d1c2b3a4f5e6d7c8b9a0f1e2',
    proof_signature: 'sig_sha256_88e4f1a23c09b55d812e44f8819a002bc91e7741d44091a329ff0891d4e0821b',
    requirements: [
      { req_id: 'req_1', description: 'API de utilizadores funcional e acessível', category: 'USER_REQUIREMENT', critical: true },
      { req_id: 'req_2', description: 'Interface frontend React responsiva e interativa', category: 'USER_REQUIREMENT', critical: true },
      { req_id: 'req_3', description: 'Compilação estrita sem erros de tipos no TypeScript', category: 'SYSTEM_INFERENCE', critical: true },
      { req_id: 'req_4', description: 'Conformidade absoluta com esquema de contratos JSON', category: 'SYSTEM_INFERENCE', critical: true },
      { req_id: 'req_5', description: 'Persistência padrão em SQLite com WAL ativado', category: 'ASSUMPTION', critical: false },
    ],
    acceptance_criteria: [
      { criterion_id: 'crit_build_valid', description: 'Projeto e artefactos compilam sem erros de sintaxe ou tipos', method: 'BUILD', status: 'SATISFIED' },
      { criterion_id: 'crit_tests_pass', description: 'Suíte de testes unitários e de integração passa a 100%', method: 'TEST', status: 'SATISFIED' },
      { criterion_id: 'crit_endpoint_exists', description: 'Endpoint de API responde adequadamente na porta de serviço', method: 'CONTRACT', status: 'SATISFIED' },
      { criterion_id: 'crit_contract_valid', description: 'Esquemas de dados e tipos estão em conformidade com o contrato', method: 'CONTRACT', status: 'SATISFIED' },
      { criterion_id: 'crit_frontend_loads', description: 'Página frontend carrega sem erros críticos de consola', method: 'BROWSER', status: 'SATISFIED' },
      { criterion_id: 'crit_ui_elements_visible', description: 'Elementos de utilizador são renderizados no DOM', method: 'BROWSER', status: 'SATISFIED' },
      { criterion_id: 'crit_security_valid', description: 'Nenhuma violação de isolamento, sandbox ou política Sentinel', method: 'SECURITY', status: 'SATISFIED' },
    ],
    evidences: [
      { id: 'evi_01', type: 'build', source: 'tsc_build_pipeline', hash: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', status: 'VALID', desc: 'Compilação TS com 0 erros em 5.86s' },
      { id: 'evi_02', type: 'test', source: 'pytest_runner', hash: 'ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb', status: 'VALID', desc: '24/24 testes aprovados sem falhas' },
      { id: 'evi_03', type: 'contract', source: 'contract_governance', hash: '4e07408562bedb8b60ce05c1decfe3ad16b72230967de01f640b7e4729b49fce', status: 'VALID', desc: 'Esquema validado com 0 breaking changes' },
      { id: 'evi_04', type: 'browser', source: 'playwright_edge', hash: '4b227777d4dd1fc61c6f884f48641d02b4d121d3fd328cb08b5531fcacdabf8a', status: 'VALID', desc: 'Renderização no Microsoft Edge com 0 erros de consola' },
      { id: 'evi_05', type: 'security', source: 'sentinel_watchdog', hash: 'ef2d127de37b942baad06145e54b0c619a1f22327b2ebbcfbec78f5564afe39d', status: 'VALID', desc: 'Auditoria de segurança Sentinel limpa' },
      { id: 'evi_06', type: 'convergence', source: 'repair_governance', hash: '5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8', status: 'VALID', desc: 'Convergência Lyapunov confirmada V(S) < 0.05' },
    ],
    human_tickets: [
      { ticket_id: 'tkt_demo_01', reason: 'REQUIREMENT_AMBIGUITY', evidence: 'Mecanismo de sessão vs JWT não explicitado', blocked_action: 'PLANNING_GATE', resolved: true, resolution: 'Adotado padrão JWT com claims assinados' }
    ],
    scorecard: {
      tasks_total: 5,
      tasks_completed: 5,
      tasks_failed: 0,
      repairs: 0,
      rollbacks: 0,
      risk: 0.12,
      coverage: 1.0,
      evidence_count: 6,
      proofs: 1,
      human_reviews: 0,
      mission_duration: 1.42,
      prediction_accuracy: 0.95,
      repair_success: 1.0,
      browser_status: 'PASSED',
    }
  });

  const handleSimulateCycle = (presetType: 'NORMAL' | 'REPAIR' | 'SECURITY' | 'AMBIGUITY' | 'DRIFT') => {
    setIsExecuting(true);
    setTimeout(() => {
      setIsExecuting(false);
      if (presetType === 'NORMAL') {
        setMissionState(prev => ({
          ...prev,
          state: 'COMPLETED',
          final_decision: 'MISSION_PROVEN_COMPLETE',
          risk: 0.08,
          scorecard: { ...prev.scorecard, tasks_failed: 0, repairs: 0, risk: 0.08 }
        }));
      } else if (presetType === 'REPAIR') {
        setMissionState(prev => ({
          ...prev,
          state: 'COMPLETED',
          final_decision: 'MISSION_PROVEN_COMPLETE',
          risk: 0.22,
          scorecard: { ...prev.scorecard, tasks_failed: 1, repairs: 1, repair_success: 1.0, risk: 0.22 }
        }));
      } else if (presetType === 'SECURITY') {
        setMissionState(prev => ({
          ...prev,
          state: 'BLOCKED',
          final_decision: 'MISSION_BLOCKED',
          risk: 0.95,
          scorecard: { ...prev.scorecard, tasks_failed: 1, risk: 0.95 }
        }));
      } else if (presetType === 'AMBIGUITY') {
        setMissionState(prev => ({
          ...prev,
          state: 'HUMAN_REVIEW_REQUIRED',
          final_decision: 'HUMAN_REVIEW_REQUIRED',
          risk: 0.50,
        }));
      } else if (presetType === 'DRIFT') {
        setMissionState(prev => ({
          ...prev,
          state: 'HUMAN_REVIEW_REQUIRED',
          final_decision: 'HUMAN_REVIEW_REQUIRED',
          objective: 'Objetivo alterado arbitrariamente',
          risk: 0.65,
        }));
      }
    }, 600);
  };

  const getStatusBadge = (state: string) => {
    switch (state) {
      case 'COMPLETED':
        return <span className="px-2.5 py-1 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 text-xs font-bold flex items-center gap-1.5"><CheckCircle2 className="w-3.5 h-3.5" /> COMPLETED (PROVEN)</span>;
      case 'BLOCKED':
        return <span className="px-2.5 py-1 rounded bg-red-500/20 text-red-300 border border-red-500/40 text-xs font-bold flex items-center gap-1.5"><ShieldAlert className="w-3.5 h-3.5" /> BLOCKED</span>;
      case 'HUMAN_REVIEW_REQUIRED':
        return <span className="px-2.5 py-1 rounded bg-amber-500/20 text-amber-300 border border-amber-500/40 text-xs font-bold flex items-center gap-1.5"><AlertTriangle className="w-3.5 h-3.5" /> HUMAN REVIEW REQUIRED</span>;
      default:
        return <span className="px-2.5 py-1 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 text-xs font-bold flex items-center gap-1.5"><Activity className="w-3.5 h-3.5" /> {state}</span>;
    }
  };

  return (
    <div className="space-y-6 text-gray-200">
      {/* HEADER WITH METADATA */}
      <div className="bg-slate-900/90 border border-cyan-500/30 rounded-xl p-5 shadow-2xl backdrop-blur-md relative overflow-hidden">
        <div className="absolute top-0 right-0 w-80 h-80 bg-gradient-to-bl from-cyan-500/10 via-indigo-500/5 to-transparent pointer-events-none rounded-full blur-2xl" />
        
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 relative z-10">
          <div>
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-lg bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 shadow-inner">
                <Award className="w-6 h-6" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-xl font-black tracking-tight text-white">Autonomous Task Completion Layer</h2>
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-cyan-500/20 text-cyan-300 border border-cyan-500/40">FASE 57</span>
                </div>
                <p className="text-xs text-slate-400 mt-0.5">
                  Unificação das Fases 40–56: Intenção → Requisitos → Plano → Execução → Observação → Verificação → Reparação → Convergência → Prova Formal
                </p>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {getStatusBadge(missionState.state)}
            <button
              onClick={() => setShowProofModal(true)}
              className="px-3 py-1.5 rounded-lg bg-indigo-600/30 hover:bg-indigo-600/50 border border-indigo-400/40 text-indigo-200 text-xs font-semibold flex items-center gap-1.5 transition-all shadow-md"
            >
              <FileCheck className="w-4 h-4 text-indigo-400" />
              Ver Certificado de Prova
            </button>
          </div>
        </div>

        {/* CONTROLS & PRESET RUNNER */}
        <div className="mt-5 pt-4 border-t border-slate-800/80 flex flex-col md:flex-row items-center gap-3">
          <div className="flex-1 w-full flex items-center gap-2 bg-slate-950/60 border border-slate-800 rounded-lg px-3 py-1.5">
            <Zap className="w-4 h-4 text-cyan-400 shrink-0" />
            <input
              type="text"
              value={intentInput}
              onChange={(e) => setIntentInput(e.target.value)}
              className="bg-transparent text-xs text-white placeholder-slate-500 focus:outline-none w-full"
              placeholder="Descreva a intenção da missão de engenharia..."
            />
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={() => handleSimulateCycle('NORMAL')}
              disabled={isExecuting}
              className="px-3.5 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-bold flex items-center gap-1.5 transition-all shadow-lg shadow-cyan-900/30 disabled:opacity-50"
            >
              <Play className="w-3.5 h-3.5" />
              {isExecuting ? 'A Executar Ciclo...' : 'Executar Missão'}
            </button>
            <div className="h-4 w-px bg-slate-700 mx-1" />
            <button
              onClick={() => handleSimulateCycle('REPAIR')}
              className="px-2.5 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-[11px] font-medium transition-all"
            >
              Auto-Cura
            </button>
            <button
              onClick={() => handleSimulateCycle('SECURITY')}
              className="px-2.5 py-1.5 rounded bg-red-950/40 hover:bg-red-900/40 text-red-300 border border-red-800/40 text-[11px] font-medium transition-all"
            >
              Bloqueio Sentinel
            </button>
            <button
              onClick={() => handleSimulateCycle('DRIFT')}
              className="px-2.5 py-1.5 rounded bg-amber-950/40 hover:bg-amber-900/40 text-amber-300 border border-amber-800/40 text-[11px] font-medium transition-all"
            >
              Objective Drift
            </button>
          </div>
        </div>
      </div>

      {/* SUB-TABS NAVIGATION */}
      <div className="flex border-b border-slate-800 bg-slate-900/60 rounded-t-xl px-2 overflow-x-auto">
        {[
          { id: 'intent_understanding', label: 'Task Understanding', icon: Sparkles },
          { id: 'mission_flow', label: 'Fluxo da Missão & Estados', icon: Layers },
          { id: 'evidence_ledger', label: 'Livro-Razão de Evidências', icon: Hash },
          { id: 'completion_proof', label: '12 Critérios & Prova Formal', icon: CheckCircle2 },
          { id: 'human_escalation', label: 'Escalonamento Humano', icon: AlertTriangle },
          { id: 'scorecard', label: 'Scorecard Multidimensional', icon: Activity },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`flex items-center gap-2 px-4 py-3 text-xs font-semibold border-b-2 transition-all shrink-0 ${
                isActive
                  ? 'border-cyan-400 text-cyan-300 bg-cyan-500/5'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* TAB 1: INTENT & TASK UNDERSTANDING */}
      {activeTab === 'intent_understanding' && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          <div className="md:col-span-2 space-y-4">
            <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5">
              <h3 className="text-sm font-bold text-white mb-3 flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-cyan-400" />
                Requisitos Formulados (Separação Epistémica Estrita)
              </h3>
              <div className="space-y-2.5">
                {missionState.requirements.map((req) => (
                  <div
                    key={req.req_id}
                    className="p-3 rounded-lg bg-slate-950/60 border border-slate-800 flex items-start justify-between gap-3"
                  >
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded border ${
                          req.category === 'USER_REQUIREMENT'
                            ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40'
                            : req.category === 'SYSTEM_INFERENCE'
                            ? 'bg-purple-500/20 text-purple-300 border-purple-500/40'
                            : 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                        }`}>
                          {req.category}
                        </span>
                        {req.critical && (
                          <span className="text-[10px] font-bold px-1.5 py-0.2 rounded bg-red-500/10 text-red-400 border border-red-500/30">
                            CRITICAL
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-slate-200">{req.description}</p>
                    </div>
                    <span className="text-[10px] text-slate-500 font-mono">{req.req_id}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5">
              <h3 className="text-sm font-bold text-white mb-3 flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                Critérios de Aceitação Observáveis (Acceptance Criteria)
              </h3>
              <div className="space-y-2">
                {missionState.acceptance_criteria.map((crit) => (
                  <div
                    key={crit.criterion_id}
                    className="p-2.5 rounded-lg bg-slate-950/40 border border-slate-800/80 flex items-center justify-between"
                  >
                    <div className="flex items-center gap-2.5">
                      <span className="p-1 rounded bg-emerald-500/20 text-emerald-400">
                        <Check className="w-3.5 h-3.5" />
                      </span>
                      <div>
                        <p className="text-xs text-slate-200 font-medium">{crit.description}</p>
                        <span className="text-[10px] text-slate-500 font-mono">Método: {crit.method}</span>
                      </div>
                    </div>
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                      {crit.status}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="space-y-4">
            <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5">
              <h3 className="text-sm font-bold text-white mb-3 flex items-center gap-2">
                <Eye className="w-4 h-4 text-indigo-400" />
                Metadados de Entendimento
              </h3>
              <div className="space-y-3 text-xs">
                <div>
                  <span className="text-slate-500 block text-[10px] uppercase">Domínio Classificado</span>
                  <span className="font-semibold text-cyan-300 uppercase">{missionState.domain}</span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[10px] uppercase">Confiança Epistémica</span>
                  <div className="flex items-center gap-2 mt-1">
                    <div className="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden">
                      <div className="h-full bg-cyan-400 rounded-full" style={{ width: `${missionState.confidence * 100}%` }} />
                    </div>
                    <span className="font-mono text-cyan-400 font-bold">{(missionState.confidence * 100).toFixed(0)}%</span>
                  </div>
                </div>
                <div>
                  <span className="text-slate-500 block text-[10px] uppercase">Avaliação de Risco</span>
                  <div className="flex items-center gap-2 mt-1">
                    <div className="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden">
                      <div className="h-full bg-emerald-400 rounded-full" style={{ width: `${missionState.risk * 100}%` }} />
                    </div>
                    <span className="font-mono text-emerald-400 font-bold">{missionState.risk.toFixed(2)}</span>
                  </div>
                </div>
                <div className="pt-2 border-t border-slate-800">
                  <span className="text-slate-500 block text-[10px] uppercase">Regra Fundamental</span>
                  <p className="text-[11px] text-slate-300 mt-1 italic">
                    "Nenhuma inferência do sistema é convertida automaticamente em requisito explícito de utilizador."
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: MISSION FLOW & STATE */}
      {activeTab === 'mission_flow' && (
        <div className="space-y-6">
          <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-6">
            <h3 className="text-sm font-bold text-white mb-4 flex items-center gap-2">
              <Layers className="w-4 h-4 text-cyan-400" />
              Ciclo Autónomo de Conclusão de Tarefas (Pipeline Soberano)
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
              {[
                { stage: 'UNDERSTAND', desc: 'Normalização & Extração', active: true, done: true },
                { stage: 'PLAN', desc: 'Impacto & Previsão', active: true, done: true },
                { stage: 'EXECUTE', desc: 'Síntese & Dispatch', active: true, done: true },
                { stage: 'VERIFY', desc: 'Testes, Build, Contratos', active: true, done: true },
                { stage: 'CONVERGE', desc: 'Lyapunov & Estagnação', active: true, done: true },
                { stage: 'PROVE & FINISH', desc: 'Emissão de Prova Formal', active: true, done: true },
              ].map((step, idx) => (
                <div
                  key={step.stage}
                  className={`p-3 rounded-lg border flex flex-col justify-between ${
                    step.done
                      ? 'bg-slate-950/80 border-cyan-500/40 text-cyan-300'
                      : 'bg-slate-950/30 border-slate-800/60 text-slate-500'
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] font-bold text-slate-500">ETAPA {idx + 1}</span>
                    <CheckCircle2 className="w-4 h-4 text-cyan-400" />
                  </div>
                  <span className="text-xs font-bold text-white">{step.stage}</span>
                  <span className="text-[10px] text-slate-400 mt-1">{step.desc}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5">
              <h3 className="text-sm font-bold text-white mb-3 flex items-center gap-2">
                <Hash className="w-4 h-4 text-indigo-400" />
                Lineage de Estado SHA-256
              </h3>
              <div className="space-y-3 text-xs font-mono">
                <div className="p-3 bg-slate-950/80 rounded border border-slate-800">
                  <span className="text-[10px] text-slate-500 block uppercase">Initial State Hash</span>
                  <span className="text-indigo-300 break-all">{missionState.initial_state_hash}</span>
                </div>
                <div className="p-3 bg-slate-950/80 rounded border border-slate-800">
                  <span className="text-[10px] text-slate-500 block uppercase">Final State Hash</span>
                  <span className="text-emerald-300 break-all">{missionState.final_state_hash}</span>
                </div>
              </div>
            </div>

            <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5">
              <h3 className="text-sm font-bold text-white mb-3 flex items-center gap-2">
                <Clock className="w-4 h-4 text-amber-400" />
                Pontos de Recuperação (Checkpoints)
              </h3>
              <div className="space-y-2 text-xs">
                {['UNDERSTOOD', 'PLANNED', 'EXECUTION_STARTED', 'FIRST_VALIDATION', 'COMPLETED'].map((cp, idx) => (
                  <div key={cp} className="flex items-center justify-between p-2 rounded bg-slate-950/40 border border-slate-800/80">
                    <span className="font-mono text-slate-300">{cp}</span>
                    <span className="text-[10px] text-slate-500 font-mono">seq #{idx + 1} • SHA-256 Valid</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: EVIDENCE LEDGER */}
      {activeTab === 'evidence_ledger' && (
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <Hash className="w-4 h-4 text-cyan-400" />
              Livro-Razão Imutável de Evidências SHA-256 (Append-Only)
            </h3>
            <span className="text-xs text-slate-400 font-mono">
              Total: {missionState.evidences.length} evidências auditadas
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 text-[10px] uppercase">
                  <th className="pb-2">ID</th>
                  <th className="pb-2">Tipo</th>
                  <th className="pb-2">Origem</th>
                  <th className="pb-2">Descrição da Evidência</th>
                  <th className="pb-2">Hash SHA-256</th>
                  <th className="pb-2 text-right">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono">
                {missionState.evidences.map((ev) => (
                  <tr key={ev.id} className="hover:bg-white/[0.02]">
                    <td className="py-2.5 text-cyan-400">{ev.id}</td>
                    <td className="py-2.5">
                      <span className="px-2 py-0.5 rounded text-[10px] font-semibold uppercase bg-slate-800 text-slate-300">
                        {ev.type}
                      </span>
                    </td>
                    <td className="py-2.5 text-slate-400">{ev.source}</td>
                    <td className="py-2.5 text-slate-200 font-sans">{ev.desc}</td>
                    <td className="py-2.5 text-slate-500 text-[11px] truncate max-w-[140px]">{ev.hash}</td>
                    <td className="py-2.5 text-right font-sans">
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                        {ev.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 4: 12 CRITERIA & COMPLETION PROOF */}
      {activeTab === 'completion_proof' && (
        <div className="space-y-6">
          <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  Os 12 Critérios Mínimos de Conclusão (Mission Completion Evaluator)
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Nenhum critério pode ser ignorado silenciosamente. "Tests passed" não equivale a "Mission Complete".
                </p>
              </div>
              <span className="px-3 py-1 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 text-xs font-bold">
                12 / 12 SATISFEITOS
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
              {[
                { name: '1. objective_satisfied', desc: 'Objetivo original do utilizador integralmente satisfeito', ok: true },
                { name: '2. acceptance_criteria_satisfied', desc: 'Todos os critérios de aceitação observáveis validados', ok: true },
                { name: '3. required_artifacts_present', desc: 'Todos os artefactos exigidos foram gerados e verificados', ok: true },
                { name: '4. build_valid', desc: 'Compilação de código limpa com zero erros de tipos ou sintaxe', ok: true },
                { name: '5. relevant_tests_valid', desc: 'Suíte completa de testes unitários e de integração aprovada', ok: true },
                { name: '6. contracts_valid', desc: 'Esquemas de contratos e interfaces sem drift quebrado', ok: true },
                { name: '7. behavior_valid', desc: 'Preservação comprovada de contratos comportamentais', ok: true },
                { name: '8. security_valid', desc: 'Segurança Sentinel confirmada sem violação de políticas', ok: true },
                { name: '9. browser_valid_when_required', desc: 'Validação visual no browser com zero erros de rede/consola', ok: true },
                { name: '10. no_blocking_failures', desc: 'Zero falhas bloqueantes remanescentes no sistema', ok: true },
                { name: '11. convergence_valid', desc: 'Convergência estrita com garantia matemática de Lyapunov', ok: true },
                { name: '12. evidence_complete', desc: 'Conjunto de evidências completo com assinatura criptográfica', ok: true },
              ].map((c) => (
                <div key={c.name} className="p-3 rounded-lg bg-slate-950/60 border border-slate-800 flex items-start gap-3">
                  <span className="p-1 rounded bg-emerald-500/20 text-emerald-400 mt-0.5 shrink-0">
                    <Check className="w-3.5 h-3.5" />
                  </span>
                  <div>
                    <span className="font-mono text-cyan-300 font-bold block">{c.name}</span>
                    <span className="text-slate-400 text-[11px]">{c.desc}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* TAB 5: HUMAN ESCALATION & SAFETY */}
      {activeTab === 'human_escalation' && (
        <div className="space-y-6">
          <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5">
            <h3 className="text-sm font-bold text-white mb-3 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-400" />
              Tickets de Revisão Humana (Human Review Tickets)
            </h3>
            <div className="space-y-3">
              {missionState.human_tickets.map((t) => (
                <div key={t.ticket_id} className="p-4 rounded-lg bg-slate-950/80 border border-amber-500/30 space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/40 text-[10px] font-bold">
                        {t.reason}
                      </span>
                      <span className="text-xs text-white font-mono">{t.ticket_id}</span>
                    </div>
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
                      RESOLVIDO
                    </span>
                  </div>
                  <p className="text-xs text-slate-300">Evidência: {t.evidence}</p>
                  <p className="text-xs text-slate-400">Ação Bloqueada: {t.blocked_action}</p>
                  <div className="p-2 rounded bg-slate-900 border border-slate-800 text-xs text-emerald-300">
                    Resolução Humana: {t.resolution}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* TAB 6: SCORECARD */}
      {activeTab === 'scorecard' && (
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5">
          <h3 className="text-sm font-bold text-white mb-4 flex items-center gap-2">
            <Activity className="w-4 h-4 text-cyan-400" />
            Scorecard Multidimensional (Métricas Transparentes sem Ocultação)
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
            <div className="p-3.5 rounded-lg bg-slate-950/60 border border-slate-800">
              <span className="text-slate-500 block text-[10px] uppercase">Tarefas Concluídas</span>
              <span className="text-lg font-bold text-cyan-400 font-mono">
                {missionState.scorecard.tasks_completed} / {missionState.scorecard.tasks_total}
              </span>
            </div>
            <div className="p-3.5 rounded-lg bg-slate-950/60 border border-slate-800">
              <span className="text-slate-500 block text-[10px] uppercase">Reparações & Auto-Cura</span>
              <span className="text-lg font-bold text-purple-400 font-mono">{missionState.scorecard.repairs}</span>
            </div>
            <div className="p-3.5 rounded-lg bg-slate-950/60 border border-slate-800">
              <span className="text-slate-500 block text-[10px] uppercase">Risco Sistémico Final</span>
              <span className="text-lg font-bold text-emerald-400 font-mono">{missionState.scorecard.risk.toFixed(3)}</span>
            </div>
            <div className="p-3.5 rounded-lg bg-slate-950/60 border border-slate-800">
              <span className="text-slate-500 block text-[10px] uppercase">Cobertura de Invariantes</span>
              <span className="text-lg font-bold text-emerald-400 font-mono">{(missionState.scorecard.coverage * 100).toFixed(0)}%</span>
            </div>
            <div className="p-3.5 rounded-lg bg-slate-950/60 border border-slate-800">
              <span className="text-slate-500 block text-[10px] uppercase">Total de Evidências SHA-256</span>
              <span className="text-lg font-bold text-white font-mono">{missionState.scorecard.evidence_count}</span>
            </div>
            <div className="p-3.5 rounded-lg bg-slate-950/60 border border-slate-800">
              <span className="text-slate-500 block text-[10px] uppercase">Acurácia Preditiva do Plano</span>
              <span className="text-lg font-bold text-cyan-400 font-mono">{(missionState.scorecard.prediction_accuracy * 100).toFixed(0)}%</span>
            </div>
            <div className="p-3.5 rounded-lg bg-slate-950/60 border border-slate-800">
              <span className="text-slate-500 block text-[10px] uppercase">Status de Browser QA</span>
              <span className="text-lg font-bold text-emerald-400 font-mono">{missionState.scorecard.browser_status}</span>
            </div>
            <div className="p-3.5 rounded-lg bg-slate-950/60 border border-slate-800">
              <span className="text-slate-500 block text-[10px] uppercase">Duração da Missão</span>
              <span className="text-lg font-bold text-white font-mono">{missionState.scorecard.mission_duration.toFixed(2)}s</span>
            </div>
          </div>
        </div>
      )}

      {/* PROOF MODAL */}
      {showProofModal && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-cyan-500/40 rounded-2xl max-w-xl w-full p-6 space-y-4 shadow-2xl relative">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <Award className="w-5 h-5 text-cyan-400" />
                <h3 className="text-base font-bold text-white">Mission Completion Proof</h3>
              </div>
              <button
                onClick={() => setShowProofModal(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 font-mono space-y-1">
                <span className="text-slate-500 block text-[10px] uppercase">Veredicto Formal</span>
                <span className="text-emerald-400 font-bold text-sm block">{missionState.final_decision}</span>
              </div>
              <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 font-mono space-y-1">
                <span className="text-slate-500 block text-[10px] uppercase">Assinatura Criptográfica SHA-256</span>
                <span className="text-cyan-300 break-all text-[11px] block">{missionState.proof_signature}</span>
              </div>
              <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 font-mono space-y-1">
                <span className="text-slate-500 block text-[10px] uppercase">Final State Hash Lineage</span>
                <span className="text-indigo-300 break-all text-[11px] block">{missionState.final_state_hash}</span>
              </div>
            </div>

            <div className="flex justify-end pt-3 border-t border-slate-800">
              <button
                onClick={() => setShowProofModal(false)}
                className="px-4 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white font-bold text-xs"
              >
                Fechar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AutonomousTaskCompletionPanel;
