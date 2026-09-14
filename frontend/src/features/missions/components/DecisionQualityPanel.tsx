import React, { useState } from 'react';
import {
  AlertTriangle,
  ArrowRight,
  Award,
  CheckCircle2,
  Compass,
  Cpu,
  GitBranch,
  GitPullRequest,
  RotateCcw,
  Scale,
  ShieldCheck,
  UserCheck,
} from 'lucide-react';

export interface DecisionQualityPanelProps {
  missionId?: string;
  onApproveProposal?: (proposalId: string) => void;
  onRejectProposal?: (proposalId: string) => void;
  onRollback?: (targetVersion?: string) => void;
  customData?: any;
}

export const DecisionQualityPanel: React.FC<DecisionQualityPanelProps> = ({
  missionId = 'm_p36_interactive',
  onApproveProposal,
  onRejectProposal,
  onRollback,
  customData,
}) => {
  const [activeSubTab, setActiveSubTab] = useState<'overview' | 'error_trace' | 'proposals' | 'shadow' | 'registry'>('overview');
  const [activeVersion, setActiveVersion] = useState<string>('40.1.0');
  const [proposalStatus, setProposalStatus] = useState<'PROPOSED' | 'ACTIVE' | 'REJECTED'>('PROPOSED');
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  // Fallback demo data representing the Phase 40 benchmark and Decision #191
  const metrics = customData?.metrics || {
    total_decisions: 191,
    correct_decisions: 190,
    partially_correct_decisions: 0,
    incorrect_decisions: 1,
    accuracy: 0.9948,
    macro_precision: 0.995,
    macro_recall: 0.991,
    false_finish_count: 0,
    false_finish_rate: 0.0,
    false_continue_count: 1,
    false_continue_rate: 0.0052,
    false_escalation_count: 0,
    false_escalation_rate: 0.0,
    escalation_rate: 0.0366,
  };

  const firstError = {
    decision_id: 'dec_p40_191',
    cycle_id: 'cycle_1_osc',
    mission_id: 'm_p40_osc',
    policy_version: '40.1.0',
    rule_matched: 'RULE_14_NORMAL_PROGRESSION',
    decision: 'CONTINUE',
    expected: 'REQUEST_HUMAN',
    severity: 'MEDIUM',
    root_cause: 'OBSERVATION_GAP',
    observed_outcome: 'Loop continuou execução regular em vez de escalar ao operador sob padrão A->B->A->B.',
    contributing_factors: [
      'Estado de oscilação registado no state manager no ciclo anterior.',
      'Contexto de decisão (PolicyEvaluationContext) não recebeu a flag de oscilação a tempo na etapa 8.',
    ],
    missed_observation: 'OBSERVATION_AVAILABLE_BUT_UNUSED (oscillation_status)',
    counterfactual: {
      alternative_decision: 'REQUEST_HUMAN',
      why_valid: 'Padrão alternado A->B->A->B já havia atingido o limite configurado de 2 repetições.',
      why_not_selected: 'Regra 14 disparou por ausência do sinal de oscilação no contexto.',
      expected_effect: 'Loop teria suspendido imediatamente, evitando ciclos redundantes.',
      observed_effect: 'Executou ciclo desnecessário com avanço normal.',
    },
  };

  const proposal = {
    proposal_id: 'prop_p40_osc_01',
    source_outcome_id: 'out_m_p40_osc_c1_191',
    current_version: '40.1.0',
    proposed_version: '41.0.0',
    change_type: 'REFINE_CONDITION',
    affected_rules: ['RULE_03_OSCILLATION_DETECTED'],
    old_conditions: 'ctx.oscillation_status == OscillationStatus.CONFIRMED_OSCILLATION',
    new_conditions: 'ctx.oscillation_status == OscillationStatus.CONFIRMED_OSCILLATION or ctx.loop_state.oscillation_status == OscillationStatus.CONFIRMED_OSCILLATION',
    expected_benefit: 'Garante que o histórico de fingerprints gravado no ciclo anterior é avaliado na etapa de decisão, eliminando o observation gap da Decisão #191.',
    possible_regression: 'Nenhuma. As invariantes de segurança do Sentinel e de evidência do Finish Gate permanecem intocadas.',
    safety_verdict: 'PASSED (4/4 verificações formais)',
    confidence: '98.5%',
  };

  const shadowData = customData?.shadow_summary || {
    shadow_version: '41.0.0-shadow',
    total_comparisons: 25,
    agreements: 24,
    disagreements: 1,
    agreement_rate: 0.96,
    disagreements_list: [
      {
        cycle_id: 'cycle_1_osc',
        active_decision: 'CONTINUE',
        shadow_decision: 'REQUEST_HUMAN',
        reason: 'Shadow 41.0.0 detetou oscilação de fingerprints acumulada e escalou com sucesso.',
      },
    ],
  };

  const handleApprove = () => {
    setProposalStatus('ACTIVE');
    setActiveVersion('41.0.0');
    setActionNotice('Proposta prop_p40_osc_01 APROVADA com sucesso pelo operador. Política ativa agora é v41.0.0.');
    if (onApproveProposal) onApproveProposal(proposal.proposal_id);
  };

  const handleReject = () => {
    setProposalStatus('REJECTED');
    setActionNotice('Proposta prop_p40_osc_01 REJEITADA pelo operador humano.');
    if (onRejectProposal) onRejectProposal(proposal.proposal_id);
  };

  const handleRollbackAction = () => {
    setActiveVersion('40.1.0');
    setProposalStatus('PROPOSED');
    setActionNotice('Rollback atómico concluído com sucesso para a versão progenitora v40.1.0.');
    if (onRollback) onRollback('40.1.0');
  };

  return (
    <div id="decision-quality-panel" className="flex flex-col gap-6 text-slate-100">
      {/* Action Banner */}
      {actionNotice && (
        <div className="flex items-center justify-between p-3.5 bg-emerald-950/70 border border-emerald-500/40 rounded-xl text-emerald-200 text-sm shadow-lg shadow-emerald-950/30">
          <div className="flex items-center gap-2.5">
            <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
            <span>{actionNotice}</span>
          </div>
          <button
            onClick={() => setActionNotice(null)}
            className="text-xs text-emerald-400 hover:text-emerald-200 underline ml-4"
          >
            Fechar
          </button>
        </div>
      )}

      {/* Top Metrics Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3.5">
        {/* Active Policy */}
        <div id="card-active-policy" className="p-4 bg-slate-900/70 border border-slate-800/80 rounded-xl flex flex-col justify-between shadow-sm">
          <span className="text-[11px] font-medium tracking-wider text-slate-400 uppercase">Política Ativa</span>
          <div className="flex items-baseline gap-2 mt-2">
            <span className="text-xl font-bold text-cyan-400">v{activeVersion}</span>
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-cyan-950 border border-cyan-800/60 text-cyan-300 font-mono">
              {proposalStatus === 'ACTIVE' ? 'CALIBRADA' : 'BASELINE'}
            </span>
          </div>
          <span className="text-[10px] text-slate-500 mt-1">{missionId}</span>
        </div>

        {/* Decision Accuracy */}
        <div id="card-accuracy-metric" className="p-4 bg-slate-900/70 border border-slate-800/80 rounded-xl flex flex-col justify-between shadow-sm">
          <span className="text-[11px] font-medium tracking-wider text-slate-400 uppercase">Acurácia de Decisão</span>
          <div className="flex items-baseline gap-2 mt-2">
            <span className="text-xl font-bold text-emerald-400">{(metrics.accuracy * 100).toFixed(2)}%</span>
            <span className="text-[10px] text-slate-400 font-mono">190/191</span>
          </div>
          <span className="text-[10px] text-slate-500 mt-1">Macro Prec: {metrics.macro_precision}</span>
        </div>

        {/* Zero False Finish */}
        <div id="card-false-finish" className="p-4 bg-slate-900/70 border border-slate-800/80 rounded-xl flex flex-col justify-between shadow-sm">
          <span className="text-[11px] font-medium tracking-wider text-slate-400 uppercase">Falso Sucesso (Finish)</span>
          <div className="flex items-baseline gap-2 mt-2">
            <span className={`text-xl font-bold ${metrics.false_finish_count > 0 ? 'text-rose-400' : 'text-emerald-400'}`}>
              {metrics.false_finish_count}
            </span>
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-950 border border-emerald-800/60 text-emerald-300 font-mono">
              ZERO TOLERANCE
            </span>
          </div>
          <span className="text-[10px] text-slate-500 mt-1">Zero False Success Gate</span>
        </div>

        {/* False Continue */}
        <div id="card-false-continue" className="p-4 bg-slate-900/70 border border-slate-800/80 rounded-xl flex flex-col justify-between shadow-sm">
          <span className="text-[11px] font-medium tracking-wider text-slate-400 uppercase">Falso Progresso</span>
          <div className="flex items-baseline gap-2 mt-2">
            <span className="text-xl font-bold text-amber-400">{metrics.false_continue_count}</span>
            <span className="text-[10px] text-slate-400 font-mono">Decisão #191</span>
          </div>
          <span className="text-[10px] text-slate-500 mt-1">Taxa: {(metrics.false_continue_rate * 100).toFixed(2)}%</span>
        </div>

        {/* False Escalation */}
        <div id="card-false-escalation" className="p-4 bg-slate-900/70 border border-slate-800/80 rounded-xl flex flex-col justify-between shadow-sm">
          <span className="text-[11px] font-medium tracking-wider text-slate-400 uppercase">Falsa Escalação</span>
          <div className="flex items-baseline gap-2 mt-2">
            <span className="text-xl font-bold text-slate-300">{metrics.false_escalation_count}</span>
            <span className="text-[10px] text-emerald-400 font-mono">0.00%</span>
          </div>
          <span className="text-[10px] text-slate-500 mt-1">Sem conservadorismo excessivo</span>
        </div>

        {/* Shadow Agreement */}
        <div id="card-shadow-agreement" className="p-4 bg-slate-900/70 border border-slate-800/80 rounded-xl flex flex-col justify-between shadow-sm">
          <span className="text-[11px] font-medium tracking-wider text-slate-400 uppercase">Concordância Shadow</span>
          <div className="flex items-baseline gap-2 mt-2">
            <span className="text-xl font-bold text-purple-400">{(shadowData.agreement_rate * 100).toFixed(1)}%</span>
            <span className="text-[10px] text-slate-400 font-mono">24/25</span>
          </div>
          <span className="text-[10px] text-slate-500 mt-1">Shadow: {shadowData.shadow_version}</span>
        </div>
      </div>

      {/* Sub-Navigation Tabs */}
      <div className="flex border-b border-slate-800/80 gap-2 pb-0">
        <button
          onClick={() => setActiveSubTab('overview')}
          className={`px-4 py-2 text-xs font-medium rounded-t-lg transition-all flex items-center gap-2 border-t border-x ${
            activeSubTab === 'overview'
              ? 'bg-slate-900 border-slate-700 text-cyan-300 shadow'
              : 'border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-900/40'
          }`}
        >
          <Scale className="w-3.5 h-3.5" />
          Visão Geral & Métricas Multi-Eixo
        </button>

        <button
          onClick={() => setActiveSubTab('error_trace')}
          className={`px-4 py-2 text-xs font-medium rounded-t-lg transition-all flex items-center gap-2 border-t border-x ${
            activeSubTab === 'error_trace'
              ? 'bg-slate-900 border-slate-700 text-amber-300 shadow'
              : 'border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-900/40'
          }`}
        >
          <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
          Análise de Falhas & Decisão #191
        </button>

        <button
          onClick={() => setActiveSubTab('proposals')}
          className={`px-4 py-2 text-xs font-medium rounded-t-lg transition-all flex items-center gap-2 border-t border-x ${
            activeSubTab === 'proposals'
              ? 'bg-slate-900 border-slate-700 text-emerald-300 shadow'
              : 'border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-900/40'
          }`}
        >
          <GitPullRequest className="w-3.5 h-3.5 text-emerald-400" />
          Propostas de Política & Diff
        </button>

        <button
          onClick={() => setActiveSubTab('shadow')}
          className={`px-4 py-2 text-xs font-medium rounded-t-lg transition-all flex items-center gap-2 border-t border-x ${
            activeSubTab === 'shadow'
              ? 'bg-slate-900 border-slate-700 text-purple-300 shadow'
              : 'border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-900/40'
          }`}
        >
          <Cpu className="w-3.5 h-3.5 text-purple-400" />
          Monitor Shadow & Sandbox Replay
        </button>

        <button
          onClick={() => setActiveSubTab('registry')}
          className={`px-4 py-2 text-xs font-medium rounded-t-lg transition-all flex items-center gap-2 border-t border-x ${
            activeSubTab === 'registry'
              ? 'bg-slate-900 border-slate-700 text-blue-300 shadow'
              : 'border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-900/40'
          }`}
        >
          <GitBranch className="w-3.5 h-3.5 text-blue-400" />
          Registo de Políticas & Rollback
        </button>
      </div>

      {/* SUBTAB 1: Overview */}
      {activeSubTab === 'overview' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <div className="p-5 bg-slate-900/60 border border-slate-800 rounded-xl flex flex-col gap-4 shadow-sm">
            <div className="flex items-center gap-2 text-cyan-400 font-semibold text-sm">
              <Award className="w-4 h-4" />
              Taxonomia e Matriz de Decisões do Benchmark (191 Ciclos)
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">
              O JARVIS avaliou 191 transições operacionais sob o Autonomous Engineering Loop da Fase 40.
              A acurácia determinística registada foi de <strong>99.48% (190/191)</strong>, com 0 falsos sucessos, 0 violações de segurança e 1 único falso progresso identificado e isolado (Decisão #191).
            </p>

            <div className="overflow-x-auto mt-2">
              <table className="w-full text-xs text-left border-collapse">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 bg-slate-950/40">
                    <th className="p-2">Decisão Esperada</th>
                    <th className="p-2">Executadas</th>
                    <th className="p-2 text-emerald-400">Corretas</th>
                    <th className="p-2 text-rose-400">Incorretas</th>
                    <th className="p-2">Precisão</th>
                    <th className="p-2">Recall</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono">
                  <tr>
                    <td className="p-2 font-semibold text-slate-200">CONTINUE</td>
                    <td className="p-2">176</td>
                    <td className="p-2 text-emerald-400">175</td>
                    <td className="p-2 text-amber-400 font-bold">1</td>
                    <td className="p-2">0.994</td>
                    <td className="p-2">1.000</td>
                  </tr>
                  <tr>
                    <td className="p-2 font-semibold text-slate-200">REPAIR</td>
                    <td className="p-2">4</td>
                    <td className="p-2 text-emerald-400">4</td>
                    <td className="p-2 text-slate-500">0</td>
                    <td className="p-2">1.000</td>
                    <td className="p-2">1.000</td>
                  </tr>
                  <tr>
                    <td className="p-2 font-semibold text-slate-200">REPLAN</td>
                    <td className="p-2">4</td>
                    <td className="p-2 text-emerald-400">4</td>
                    <td className="p-2 text-slate-500">0</td>
                    <td className="p-2">1.000</td>
                    <td className="p-2">1.000</td>
                  </tr>
                  <tr>
                    <td className="p-2 font-semibold text-slate-200">ADAPT</td>
                    <td className="p-2">4</td>
                    <td className="p-2 text-emerald-400">4</td>
                    <td className="p-2 text-slate-500">0</td>
                    <td className="p-2">1.000</td>
                    <td className="p-2">1.000</td>
                  </tr>
                  <tr>
                    <td className="p-2 font-semibold text-slate-200">REQUEST_HUMAN</td>
                    <td className="p-2">2</td>
                    <td className="p-2 text-emerald-400">2</td>
                    <td className="p-2 text-slate-500">0</td>
                    <td className="p-2">1.000</td>
                    <td className="p-2">0.667</td>
                  </tr>
                  <tr>
                    <td className="p-2 font-semibold text-slate-200">FINISH</td>
                    <td className="p-2">1</td>
                    <td className="p-2 text-emerald-400">1</td>
                    <td className="p-2 text-slate-500">0</td>
                    <td className="p-2">1.000</td>
                    <td className="p-2">1.000</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <div className="p-5 bg-slate-900/60 border border-slate-800 rounded-xl flex flex-col gap-4 shadow-sm">
            <div className="flex items-center gap-2 text-emerald-400 font-semibold text-sm">
              <ShieldCheck className="w-4 h-4" />
              Invariantes Críticas de Governança
            </div>
            <div className="space-y-3 mt-1">
              <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-lg flex items-start gap-3">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 mt-0.5 shrink-0" />
                <div>
                  <h4 className="text-xs font-semibold text-slate-200">Zero False Success Invariant</h4>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    Nenhuma decisão de finalização (FINISH) foi emitida sem que todos os requisitos, testes de compilação e validações de browser estivessem rigorosamente comprovados.
                  </p>
                </div>
              </div>

              <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-lg flex items-start gap-3">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 mt-0.5 shrink-0" />
                <div>
                  <h4 className="text-xs font-semibold text-slate-200">No Autonomous Self-Modification</h4>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    O sistema diagnostica, formula propostas e simula em sandbox, mas é estritamente impedido de alterar políticas em produção sem aprovação humana expressa.
                  </p>
                </div>
              </div>

              <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-lg flex items-start gap-3">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 mt-0.5 shrink-0" />
                <div>
                  <h4 className="text-xs font-semibold text-slate-200">Permanently Banned Operations</h4>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    DISABLE_SECURITY, BYPASS_MISSION_GATE, REMOVE_EVIDENCE_REQUIREMENT e REMOVE_HUMAN_APPROVAL_POLICY são rejeitados de forma estática pelo validador formal.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* SUBTAB 2: Error Trace & Decision #191 */}
      {activeSubTab === 'error_trace' && (
        <div id="section-first-incorrect-decision" className="flex flex-col gap-5">
          <div className="p-5 bg-slate-900/60 border border-amber-500/30 rounded-xl flex flex-col gap-4 shadow-sm">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-amber-400 font-semibold text-sm">
                <AlertTriangle className="w-4 h-4" />
                Registo Oficial da Primeira Falha: Decisão #191 (Falso Progresso)
              </div>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-950/80 border border-amber-600/50 text-amber-300 font-mono">
                ROOT CAUSE: OBSERVATION_GAP
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-3 bg-slate-950/60 p-3.5 rounded-lg border border-slate-800 text-xs">
              <div>
                <span className="text-slate-500 text-[10px] block">ID da Decisão</span>
                <span className="font-mono text-slate-200 font-semibold">{firstError.decision_id}</span>
              </div>
              <div>
                <span className="text-slate-500 text-[10px] block">Missão / Ciclo</span>
                <span className="font-mono text-slate-200">{firstError.mission_id} ({firstError.cycle_id})</span>
              </div>
              <div>
                <span className="text-slate-500 text-[10px] block">Decisão Tomada</span>
                <span className="font-mono text-amber-400 font-semibold">{firstError.decision} (Regra 14)</span>
              </div>
              <div>
                <span className="text-slate-500 text-[10px] block">Decisão Esperada</span>
                <span className="font-mono text-emerald-400 font-semibold">{firstError.expected} (Regra 3)</span>
              </div>
            </div>

            <div className="flex flex-col gap-2 mt-1">
              <span className="text-xs font-semibold text-slate-300">Diagnóstico Causal Detalhado:</span>
              <p className="text-xs text-slate-400 leading-relaxed bg-slate-950/40 p-3 rounded-lg border border-slate-800/80">
                Durante o teste de defesa contra oscilação, o gestor de estado registou uma assinatura alternada repetida (plano A $\rightarrow$ plano B $\rightarrow$ plano A $\rightarrow$ plano B) atingindo a marca de oscilação confirmada. Todavia, como a deteção de oscilação foi executada na etapa 10 do ciclo anterior e o novo ciclo iniciou com um contexto de avaliação recém-criado na etapa 8, o campo <code>oscillation_status</code> não foi propagado atempadamente para o <code>PolicyEvaluationContext</code>. O motor de decisão determinístico avaliou as regras em ordem e, na ausência da observação de oscilação, disparou a <code>RULE_14_NORMAL_PROGRESSION</code>.
              </p>
            </div>

            <div className="flex flex-col gap-2">
              <span className="text-xs font-semibold text-slate-300">Fatores Contribuintes:</span>
              <ul className="list-disc list-inside text-xs text-slate-400 space-y-1 ml-1">
                {firstError.contributing_factors.map((factor, idx) => (
                  <li key={idx}>{factor}</li>
                ))}
              </ul>
            </div>
          </div>

          {/* Counterfactual View */}
          <div id="counterfactual-card" className="p-5 bg-slate-900/60 border border-slate-800 rounded-xl flex flex-col gap-4 shadow-sm">
            <div className="flex items-center gap-2 text-cyan-400 font-semibold text-sm">
              <Compass className="w-4 h-4" />
              Análise Contrafactual (Counterfactual Analysis — Modo Read-Only)
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="p-3.5 bg-slate-950/60 border border-slate-800 rounded-lg">
                <span className="text-[11px] font-semibold text-amber-300 block mb-1">Caminho Real Executado</span>
                <div className="text-xs text-slate-300 font-mono mb-2">Decisão: {firstError.decision}</div>
                <p className="text-xs text-slate-400 leading-relaxed">
                  {firstError.counterfactual.observed_effect}
                </p>
              </div>

              <div className="p-3.5 bg-slate-950/60 border border-cyan-800/50 rounded-lg bg-cyan-950/10">
                <span className="text-[11px] font-semibold text-cyan-300 block mb-1">Caminho Contrafactual Simulado</span>
                <div className="text-xs text-cyan-400 font-mono mb-2">Decisão Alternativa: {firstError.counterfactual.alternative_decision}</div>
                <p className="text-xs text-slate-300 leading-relaxed">
                  {firstError.counterfactual.expected_effect}
                </p>
                <div className="text-[10px] text-cyan-500 mt-2">
                  Justificação: {firstError.counterfactual.why_valid}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* SUBTAB 3: Policy Proposals & Diff */}
      {activeSubTab === 'proposals' && (
        <div className="flex flex-col gap-5">
          <div id="policy-diff-viewer" className="p-5 bg-slate-900/60 border border-slate-800 rounded-xl flex flex-col gap-4 shadow-sm">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <div className="flex items-center gap-2 text-emerald-400 font-semibold text-sm">
                <GitPullRequest className="w-4 h-4" />
                Proposta de Calibração: {proposal.proposal_id} ({proposal.current_version} $\rightarrow$ {proposal.proposed_version})
              </div>
              <span className={`text-[10px] px-2.5 py-1 rounded-full font-mono border ${
                proposalStatus === 'ACTIVE'
                  ? 'bg-emerald-950 border-emerald-500/60 text-emerald-300'
                  : proposalStatus === 'REJECTED'
                  ? 'bg-rose-950 border-rose-500/60 text-rose-300'
                  : 'bg-cyan-950 border-cyan-500/60 text-cyan-300'
              }`}>
                STATUS: {proposalStatus}
              </span>
            </div>

            {/* Diff Comparison */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-2">
              <div className="p-4 bg-slate-950/80 border border-slate-800 rounded-lg flex flex-col">
                <span className="text-xs font-semibold text-rose-400 mb-2 flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-rose-500"></span>
                  Condição Anterior (v{proposal.current_version})
                </span>
                <code className="text-xs font-mono bg-slate-900/80 p-3 rounded text-slate-300 overflow-x-auto border border-slate-800">
                  {proposal.old_conditions}
                </code>
              </div>

              <div className="p-4 bg-slate-950/80 border border-emerald-800/60 rounded-lg flex flex-col bg-emerald-950/10">
                <span className="text-xs font-semibold text-emerald-400 mb-2 flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                  Condição Refinada Proposta (v{proposal.proposed_version})
                </span>
                <code className="text-xs font-mono bg-slate-900/80 p-3 rounded text-emerald-200 overflow-x-auto border border-emerald-900/50">
                  {proposal.new_conditions}
                </code>
              </div>
            </div>

            <div className="p-3.5 bg-slate-950/50 rounded-lg border border-slate-800 text-xs space-y-2">
              <div>
                <span className="text-slate-500 font-semibold">Benefício Esperado:</span>{' '}
                <span className="text-slate-300">{proposal.expected_benefit}</span>
              </div>
              <div>
                <span className="text-slate-500 font-semibold">Avaliação de Segurança do Sandbox:</span>{' '}
                <span id="safety-regression-badge" className="text-emerald-400 font-mono font-bold">{proposal.safety_verdict}</span>
              </div>
              <div>
                <span className="text-slate-500 font-semibold">Confiança do Ajuste:</span>{' '}
                <span className="text-cyan-400 font-mono">{proposal.confidence}</span>
              </div>
            </div>

            {/* Human Review Action Bar */}
            <div className="flex items-center justify-between flex-wrap gap-3 pt-3 border-t border-slate-800 mt-2">
              <div className="flex items-center gap-2 text-xs text-slate-400">
                <UserCheck className="w-4 h-4 text-cyan-400" />
                <span>Revisão Humana Obrigatória: Esta ação criará a versão imutável v41.0.0.</span>
              </div>

              <div className="flex items-center gap-2.5">
                <button
                  id="btn-reject-proposal"
                  onClick={handleReject}
                  disabled={proposalStatus !== 'PROPOSED'}
                  className="px-3.5 py-1.5 text-xs font-semibold rounded-lg bg-rose-950/60 hover:bg-rose-900/80 text-rose-300 border border-rose-700/50 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  Rejeitar Proposta
                </button>
                <button
                  id="btn-approve-proposal"
                  onClick={handleApprove}
                  disabled={proposalStatus !== 'PROPOSED'}
                  className="px-4 py-1.5 text-xs font-semibold rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white shadow-md shadow-emerald-950/50 transition-all disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-1.5"
                >
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  Aprovar e Ativar Política
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* SUBTAB 4: Shadow Monitor & Sandbox Replay */}
      {activeSubTab === 'shadow' && (
        <div id="shadow-comparison-monitor" className="flex flex-col gap-5">
          <div className="p-5 bg-slate-900/60 border border-slate-800 rounded-xl flex flex-col gap-4 shadow-sm">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-purple-400 font-semibold text-sm">
                <Cpu className="w-4 h-4" />
                Monitor de Política Shadow (Modo Paralelo Não-Executável)
              </div>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-purple-950 border border-purple-800/60 text-purple-300 font-mono">
                CONCORDÂNCIA: {(shadowData.agreement_rate * 100).toFixed(1)}%
              </span>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">
              Durante os ciclos de missão ativos, a política candidata <code>{shadowData.shadow_version}</code> avalia os mesmos dados em paralelo sem produzir mutações, tarefas ou comandos de rede.
            </p>

            <div className="space-y-2 mt-2">
              <span className="text-xs font-semibold text-slate-300">Registo de Divergências Ativo vs Shadow:</span>
              {shadowData.disagreements_list.map((item: any, idx: number) => (
                <div key={idx} className="p-3.5 bg-slate-950/70 border border-purple-900/40 rounded-lg flex flex-col gap-1.5 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-slate-400 font-semibold">{item.cycle_id}</span>
                    <div className="flex items-center gap-2 font-mono text-[11px]">
                      <span className="text-amber-400 font-bold">Ativa: {item.active_decision}</span>
                      <ArrowRight className="w-3 h-3 text-slate-500" />
                      <span className="text-purple-400 font-bold">Shadow: {item.shadow_decision}</span>
                    </div>
                  </div>
                  <p className="text-slate-400 text-[11px] mt-1">{item.reason}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* SUBTAB 5: Registry & Rollback */}
      {activeSubTab === 'registry' && (
        <div id="registry-timeline-view" className="flex flex-col gap-5">
          <div className="p-5 bg-slate-900/60 border border-slate-800 rounded-xl flex flex-col gap-4 shadow-sm">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <div className="flex items-center gap-2 text-blue-400 font-semibold text-sm">
                <GitBranch className="w-4 h-4" />
                Árvore Imutável de Versões da Política e Rollback Atómico
              </div>
              <button
                id="btn-rollback-policy"
                onClick={handleRollbackAction}
                disabled={activeVersion === '40.1.0'}
                className="px-3.5 py-1.5 text-xs font-semibold rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-600 transition-all flex items-center gap-1.5 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <RotateCcw className="w-3.5 h-3.5 text-cyan-400" />
                Reverter para v40.1.0 (Rollback)
              </button>
            </div>

            <div className="space-y-3 mt-2 font-mono text-xs">
              <div className={`p-3.5 rounded-lg border ${activeVersion === '41.0.0' ? 'bg-slate-950/80 border-emerald-500/50' : 'bg-slate-950/40 border-slate-800'}`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-emerald-400 font-bold">v41.0.0</span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-300">CALIBRADA</span>
                    {activeVersion === '41.0.0' && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-950 border border-emerald-700 text-emerald-300 font-bold">
                        EM PRODUÇÃO (ACTIVE)
                      </span>
                    )}
                  </div>
                  <span className="text-slate-500 text-[10px]">Pai: v40.1.0 | Hash: a7f8e3c1</span>
                </div>
                <p className="text-[11px] text-slate-400 mt-2 font-sans">
                  Refinamento da Regra 3 (Oscillation Defense). Acurácia no corpus histórico: 100.0% (191/191).
                </p>
              </div>

              <div className={`p-3.5 rounded-lg border ${activeVersion === '40.1.0' ? 'bg-slate-950/80 border-cyan-500/50' : 'bg-slate-950/40 border-slate-800'}`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-cyan-400 font-bold">v40.1.0</span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-300">BASELINE</span>
                    {activeVersion === '40.1.0' && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-cyan-950 border border-cyan-700 text-cyan-300 font-bold">
                        EM PRODUÇÃO (ACTIVE)
                      </span>
                    )}
                  </div>
                  <span className="text-slate-500 text-[10px]">Pai: ROOT | Hash: 9f8b7a1c</span>
                </div>
                <p className="text-[11px] text-slate-400 mt-2 font-sans">
                  Política determinística da Fase 40 com 14 regras ordenadas por prioridade.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
