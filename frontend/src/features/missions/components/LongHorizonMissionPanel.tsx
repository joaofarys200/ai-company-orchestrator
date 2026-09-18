import React, { useState } from 'react';
import {
  Target,
  ShieldCheck,
  AlertTriangle,
  RotateCcw,
  Zap,
  Activity,
  Lock,
  GitMerge,
  Network,
  Clock,
  Award,
  Compass,
  CheckCircle2,
  Boxes,
  HelpCircle,
} from 'lucide-react';

interface LongHorizonMissionPanelProps {
  missionId?: string;
}

export const LongHorizonMissionPanel: React.FC<LongHorizonMissionPanelProps> = ({
  missionId = 'lhm_f67_demo',
}) => {
  const [activeSubtab, setActiveSubtab] = useState<string>('overview');
  const [policy, setPolicy] = useState<string>('GOVERNED');
  const [isExecuting, setIsExecuting] = useState<boolean>(false);
  const [missionStatus] = useState<string>('EXECUTING');
  const [currentStepIndex, setCurrentStepIndex] = useState<number>(4);

  return (
    <div className="flex h-full flex-col bg-[#0b1317] text-gray-200">
      {/* Header Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[#a1bebf]/15 bg-[#0d171b] px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-teal-500/10 text-teal-400 border border-teal-500/20">
            <Compass className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-white">
                Long-Horizon Autonomous Engineering Missions & Mission-Level Governance
              </h2>
              <span className="rounded bg-teal-500/20 px-2 py-0.5 text-xs font-semibold text-teal-300">
                FASE 67
              </span>
              <span className="flex items-center gap-1 rounded bg-emerald-500/20 px-2 py-0.5 text-xs font-semibold text-emerald-300">
                <ShieldCheck className="h-3 w-3" />
                LONG_HORIZON_MISSION_READY
              </span>
            </div>
            <p className="text-xs text-gray-400">
              Bounded DAG execution, multi-dimensional budget governance, SHA-256 checkpoints, crash reconciliation, and completion proofs.
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
              <option value="STRICT">STRICT (Zero Tolerance)</option>
              <option value="GOVERNED">GOVERNED (Balanced)</option>
              <option value="ADAPTIVE">ADAPTIVE (Dynamic Replanning)</option>
              <option value="LENIENT">LENIENT (Exploratory)</option>
            </select>
          </div>

          <button
            id="longhorizon-action-step"
            onClick={() => {
              setIsExecuting(true);
              setTimeout(() => {
                setCurrentStepIndex((prev) => prev + 1);
                setIsExecuting(false);
              }, 300);
            }}
            disabled={isExecuting}
            className="flex items-center gap-1.5 rounded bg-teal-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-teal-500 transition-colors disabled:opacity-50"
          >
            <Zap className="h-3.5 w-3.5" />
            {isExecuting ? 'A Executar...' : 'Passo de Missão'}
          </button>
        </div>
      </div>

      {/* 14 Scenario Subtabs */}
      <div className="flex border-b border-gray-800 bg-[#0c1417] px-6 text-xs font-semibold overflow-x-auto">
        {[
          { id: 'overview', label: '01. Overview', icon: Boxes },
          { id: 'objectives', label: '02. Objectives', icon: Target },
          { id: 'milestones', label: '03. Milestone DAG', icon: Network },
          { id: 'coordination', label: '04. Coordination', icon: GitMerge },
          { id: 'budget', label: '05. Budget', icon: Clock },
          { id: 'checkpoints', label: '06. Checkpoints', icon: Lock },
          { id: 'execution', label: '07. Execution', icon: Activity },
          { id: 'verification', label: '08. Verification', icon: ShieldCheck },
          { id: 'adaptation', label: '09. Adaptation', icon: RotateCcw },
          { id: 'failures', label: '10. Failures', icon: AlertTriangle },
          { id: 'recovery', label: '11. Recovery', icon: RotateCcw },
          { id: 'human-review', label: '12. Human Review', icon: HelpCircle },
          { id: 'completion', label: '13. Completion Proof', icon: Award },
          { id: 'termination', label: '14. Termination State', icon: CheckCircle2 },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeSubtab === tab.id;
          return (
            <button
              key={tab.id}
              id={`longhorizon-subtab-${tab.id}`}
              onClick={() => setActiveSubtab(tab.id)}
              className={`flex items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2.5 transition-colors ${
                isActive
                  ? 'border-teal-500 text-teal-300'
                  : 'border-transparent text-gray-400 hover:text-gray-200'
              }`}
            >
              <Icon className="h-3.5 w-3.5" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Content Area */}
      <div className="flex-1 overflow-y-auto p-6">
        {/* 01. Overview */}
        {activeSubtab === 'overview' && (
          <div id="longhorizon-view-overview" className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="rounded-lg border border-gray-800 bg-[#0f191d] p-4">
                <span className="text-xs text-gray-400">Estado Atual</span>
                <div className="mt-1 text-lg font-bold text-teal-300">{missionStatus}</div>
                <span className="text-xs text-gray-500 font-mono">ID: {missionId}</span>
              </div>
              <div className="rounded-lg border border-gray-800 bg-[#0f191d] p-4">
                <span className="text-xs text-gray-400">Milestones Concluídos</span>
                <div className="mt-1 text-lg font-bold text-white">{currentStepIndex} / 10</div>
                <span className="text-xs text-emerald-400">40% Progresso Verificado</span>
              </div>
              <div className="rounded-lg border border-gray-800 bg-[#0f191d] p-4">
                <span className="text-xs text-gray-400">Orçamento Restante</span>
                <div className="mt-1 text-lg font-bold text-emerald-400">92.4%</div>
                <span className="text-xs text-gray-500">11 Dimensões Monitorizadas</span>
              </div>
              <div className="rounded-lg border border-gray-800 bg-[#0f191d] p-4">
                <span className="text-xs text-gray-400">Último Checkpoint</span>
                <div className="mt-1 text-xs font-mono text-purple-300 truncate">chk_lhm_04_a9f1b2</div>
                <span className="text-xs text-gray-500">SHA-256 Imutável</span>
              </div>
            </div>

            <div className="rounded-lg border border-gray-800 bg-[#0f191d] p-4">
              <h3 className="text-sm font-semibold text-white mb-3">Pipeline de Execução Long-Horizon</h3>
              <div className="flex items-center justify-between text-xs font-mono text-gray-300 bg-[#0c1417] p-3 rounded border border-gray-800 overflow-x-auto">
                <span className="text-emerald-400 font-bold">START</span> →
                <span className="text-emerald-400 font-bold">PLAN</span> →
                <span className="text-teal-400 font-bold">EXECUTE</span> →
                <span className="text-teal-400 font-bold">WAIT</span> →
                <span className="text-teal-400 font-bold">COLLECT</span> →
                <span className="text-purple-400 font-bold">VERIFY</span> →
                <span className="text-purple-400 font-bold">CHECKPOINT</span> →
                <span className="text-yellow-400 font-bold">ADAPT</span> →
                <span className="text-teal-400 font-bold">CONTINUE</span> →
                <span className="text-gray-400">FINISH</span>
              </div>
            </div>
          </div>
        )}

        {/* 02. Objectives */}
        {activeSubtab === 'objectives' && (
          <div id="longhorizon-view-objectives" className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-white">Hierarquia de Objetivos & Drift Guard (F57)</h3>
              <span className="text-xs text-emerald-400 font-mono">OBJECTIVE_DRIFT = 0.00 (NOMINAL)</span>
            </div>
            <div className="space-y-3">
              {[
                { id: 'OBJ_PRIMARY_01', cat: 'PRIMARY', desc: 'Implementar arquitetura resiliente com testes e contratos intactos', status: 'IN_PROGRESS', prio: 1 },
                { id: 'OBJ_INV_01', cat: 'INVARIANT', desc: 'Zero quebra de compatibilidade em APIs públicas existentes', status: 'SATISFIED', prio: 1 },
                { id: 'OBJ_SEC_01', cat: 'SECONDARY', desc: 'Otimizar consumo de memória cache em 15%', status: 'UNSATISFIED', prio: 2 },
                { id: 'OBJ_NON_01', cat: 'NON_GOAL', desc: 'Reescrever subsistemas legado fora do escopo', status: 'UNKNOWN', prio: 3 },
              ].map((obj) => (
                <div key={obj.id} className="flex items-center justify-between rounded border border-gray-800 bg-[#0f191d] p-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className={`text-xs px-2 py-0.5 rounded font-mono font-bold ${
                        obj.cat === 'PRIMARY' ? 'bg-indigo-500/20 text-indigo-300' :
                        obj.cat === 'INVARIANT' ? 'bg-purple-500/20 text-purple-300' :
                        obj.cat === 'SECONDARY' ? 'bg-blue-500/20 text-blue-300' : 'bg-gray-700 text-gray-300'
                      }`}>{obj.cat}</span>
                      <span className="text-xs font-mono text-gray-400">{obj.id}</span>
                      <span className="text-xs text-white">{obj.desc}</span>
                    </div>
                  </div>
                  <span className={`text-xs font-semibold px-2 py-0.5 rounded ${
                    obj.status === 'SATISFIED' ? 'bg-emerald-500/20 text-emerald-300' :
                    obj.status === 'IN_PROGRESS' ? 'bg-yellow-500/20 text-yellow-300' : 'bg-gray-800 text-gray-400'
                  }`}>{obj.status}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 03. Milestone DAG */}
        {activeSubtab === 'milestones' && (
          <div id="longhorizon-view-milestones" className="space-y-4">
            <h3 className="text-sm font-bold text-white">Grafo Dirigido Acíclico (DAG) de Milestones</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {[
                { id: 'M_00001', title: 'Architecture Assessment', deps: [], status: 'COMPLETED' },
                { id: 'M_00002', title: 'Contract & Interface Design', deps: ['M_00001'], status: 'COMPLETED' },
                { id: 'M_00003', title: 'Transactional Patch Generation', deps: ['M_00002'], status: 'COMPLETED' },
                { id: 'M_00004', title: 'Unit & Contract Verification', deps: ['M_00003'], status: 'COMPLETED' },
                { id: 'M_00005', title: 'Continuous Integration & Tests', deps: ['M_00004'], status: 'READY' },
                { id: 'M_00006', title: 'Architecture Rescan & Proof', deps: ['M_00005'], status: 'PLANNED' },
              ].map((m) => (
                <div key={m.id} className="rounded border border-gray-800 bg-[#0f191d] p-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-mono font-bold text-teal-300">{m.id}</span>
                    <span className={`text-xs px-2 py-0.5 rounded font-semibold ${
                      m.status === 'COMPLETED' ? 'bg-emerald-500/20 text-emerald-300' :
                      m.status === 'READY' ? 'bg-teal-500/20 text-teal-300' : 'bg-gray-800 text-gray-400'
                    }`}>{m.status}</span>
                  </div>
                  <div className="text-xs text-white mt-1">{m.title}</div>
                  <div className="text-xs text-gray-500 mt-2 font-mono">
                    Deps: {m.deps.length > 0 ? m.deps.join(', ') : 'ROOT'}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 04. Agent Coordination */}
        {activeSubtab === 'coordination' && (
          <div id="longhorizon-view-coordination" className="space-y-4">
            <h3 className="text-sm font-bold text-white">Integração Multi-Agente (F66) & Intents</h3>
            <div className="rounded border border-gray-800 bg-[#0f191d] p-4 space-y-3">
              <div className="text-xs text-gray-400">
                Registo de claims e transações ativas por milestone:
              </div>
              <div className="space-y-2">
                {[
                  { intent_id: 'intent_M_04_1', agent: 'CoderAgent', tx: 'tx_8f10a2', files: 'src/m_00004.py', status: 'COMMITTED' },
                  { intent_id: 'intent_M_05_1', agent: 'TesterAgent', tx: 'tx_3b91c4', files: 'tests/test_m_00005.py', status: 'SCHEDULED' },
                  { intent_id: 'intent_M_05_2', agent: 'SecurityAgent', tx: 'tx_7d21e8', files: 'backend/security.py', status: 'PENDING_CLAIM' },
                ].map((row) => (
                  <div key={row.intent_id} className="flex items-center justify-between bg-[#0c1417] p-2.5 rounded border border-gray-800 text-xs">
                    <div className="flex items-center gap-3">
                      <span className="font-mono text-indigo-400">{row.intent_id}</span>
                      <span className="text-gray-300 font-semibold">{row.agent}</span>
                      <span className="font-mono text-gray-500">{row.files}</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="font-mono text-purple-400">{row.tx}</span>
                      <span className="text-emerald-400 font-semibold">{row.status}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* 05. Budget */}
        {activeSubtab === 'budget' && (
          <div id="longhorizon-view-budget" className="space-y-4">
            <h3 className="text-sm font-bold text-white">Governação Orçamental (11 Dimensões Bounded)</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {[
                { name: 'Wall Time', consumed: '124s', limit: '3600s', pct: '3.4%' },
                { name: 'CPU Time', consumed: '68s', limit: '1800s', pct: '3.7%' },
                { name: 'Memory', consumed: '412MB', limit: '4096MB', pct: '10.0%' },
                { name: 'Agent Executions', consumed: '4', limit: '500', pct: '0.8%' },
                { name: 'Patches Applied', consumed: '4', limit: '200', pct: '2.0%' },
                { name: 'Retries', consumed: '0', limit: '50', pct: '0.0%' },
                { name: 'Rollbacks', consumed: '0', limit: '30', pct: '0.0%' },
                { name: 'Generated Tests', consumed: '16', limit: '500', pct: '3.2%' },
                { name: 'Browser Sessions', consumed: '1', limit: '50', pct: '2.0%' },
                { name: 'Architecture Changes', consumed: '1', limit: '20', pct: '5.0%' },
                { name: 'Human Review Requests', consumed: '0', limit: '15', pct: '0.0%' },
              ].map((b) => (
                <div key={b.name} className="rounded border border-gray-800 bg-[#0f191d] p-3">
                  <div className="flex justify-between text-xs text-gray-400">
                    <span>{b.name}</span>
                    <span className="text-white font-mono">{b.consumed} / {b.limit}</span>
                  </div>
                  <div className="mt-2 h-1.5 w-full rounded bg-gray-800 overflow-hidden">
                    <div className="h-full bg-teal-500 rounded" style={{ width: b.pct }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 06. Checkpoints */}
        {activeSubtab === 'checkpoints' && (
          <div id="longhorizon-view-checkpoints" className="space-y-4">
            <h3 className="text-sm font-bold text-white">Cadeia de Checkpoints Imutáveis (SHA-256)</h3>
            <div className="space-y-3">
              {[
                { id: 'chk_lhm_01', type: 'FULL', time: '10:00:15', sha: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855' },
                { id: 'chk_lhm_02', type: 'MILESTONE', time: '10:02:40', sha: '5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8' },
                { id: 'chk_lhm_03', type: 'MILESTONE', time: '10:05:12', sha: '4b227777d4dd1fc61c6f884f48641d02b4d121d3fd328cb08b5531fcacdabf8a' },
                { id: 'chk_lhm_04', type: 'POST_VERIFICATION', time: '10:07:30', sha: 'ef2d127de37b942baad06145e54b0c619a1f22327b2ebbcfbec78f5564afe39d' },
              ].map((c) => (
                <div key={c.id} className="rounded border border-gray-800 bg-[#0f191d] p-3 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Lock className="h-4 w-4 text-purple-400" />
                    <div>
                      <div className="text-xs font-mono font-bold text-white">{c.id}</div>
                      <div className="text-xs font-mono text-gray-500 truncate max-w-md">{c.sha}</div>
                    </div>
                  </div>
                  <div className="text-right">
                    <span className="text-xs font-mono px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 font-semibold">{c.type}</span>
                    <div className="text-xs text-gray-500 mt-1">{c.time}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 07. Execution */}
        {activeSubtab === 'execution' && (
          <div id="longhorizon-view-execution" className="space-y-4">
            <h3 className="text-sm font-bold text-white">Histórico de Execução Controlada</h3>
            <div className="rounded border border-gray-800 bg-[#0f191d] p-4 space-y-2 font-mono text-xs text-gray-300">
              <div className="text-teal-400">[EXEC_ENGINE] Step 1 dispatched: M_00001 (Architecture Assessment) &rarr; VERIFIED</div>
              <div className="text-teal-400">[EXEC_ENGINE] Step 2 dispatched: M_00002 (Contract &amp; Interface Design) &rarr; VERIFIED</div>
              <div className="text-teal-400">[EXEC_ENGINE] Step 3 dispatched: M_00003 (Transactional Patch Generation) &rarr; VERIFIED</div>
              <div className="text-teal-400">[EXEC_ENGINE] Step 4 dispatched: M_00004 (Unit &amp; Contract Verification) &rarr; VERIFIED</div>
              <div className="text-yellow-400">[EXEC_ENGINE] Next ready milestone: M_00005 (Continuous Integration &amp; Tests)</div>
            </div>
          </div>
        )}

        {/* 08. Verification */}
        {activeSubtab === 'verification' && (
          <div id="longhorizon-view-verification" className="space-y-4">
            <h3 className="text-sm font-bold text-white">Cobertura Contínua Multi-Nível (F62)</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {['UNIT', 'INTEGRATION', 'CONTRACT', 'BEHAVIOR', 'ARCHITECTURE', 'BROWSER', 'SECURITY'].map((lvl) => (
                <div key={lvl} className="rounded border border-gray-800 bg-[#0f191d] p-3 flex items-center justify-between">
                  <span className="text-xs font-mono font-semibold text-gray-200">{lvl}</span>
                  <span className="text-xs font-mono px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-bold">PASS</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 09. Adaptation */}
        {activeSubtab === 'adaptation' && (
          <div id="longhorizon-view-adaptation" className="space-y-4">
            <h3 className="text-sm font-bold text-white">Adaptação Dinâmica & Prevenção de Oscilações (F56)</h3>
            <div className="rounded border border-gray-800 bg-[#0f191d] p-4 space-y-3">
              <div className="text-xs text-gray-300">
                Regra Invariante: <strong className="text-teal-400">REPLAN != OBJECTIVE_CHANGE</strong>.
                O motor pode adaptar ordem, paralelismo e testes, mas nunca altera objetivos sem autorização humana.
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-400">Estado de Convergência:</span>
                <span className="text-xs px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-bold">PROGRESSING</span>
              </div>
            </div>
          </div>
        )}

        {/* 10. Failures */}
        {activeSubtab === 'failures' && (
          <div id="longhorizon-view-failures" className="space-y-4">
            <h3 className="text-sm font-bold text-white">Classificação & Localização de Falhas</h3>
            <div className="rounded border border-gray-800 bg-[#0f191d] p-4">
              <div className="text-xs text-emerald-400 font-semibold">Zero Falhas Ativas no Passo Atual</div>
              <div className="text-xs text-gray-400 mt-1">
                Tipos monitorizados: IMPLEMENTATION_FAILURE, TEST_FAILURE, CONTRACT_FAILURE, BEHAVIOR_FAILURE, ARCHITECTURE_FAILURE, AGENT_FAILURE, RESOURCE_FAILURE, SECURITY_FAILURE, TIMEOUT.
              </div>
            </div>
          </div>
        )}

        {/* 11. Recovery */}
        {activeSubtab === 'recovery' && (
          <div id="longhorizon-view-recovery" className="space-y-4">
            <h3 className="text-sm font-bold text-white">Motor de Crash Recovery & Reconciliação</h3>
            <div className="rounded border border-gray-800 bg-[#0f191d] p-4 space-y-3">
              <div className="text-xs text-gray-300">
                Garante que após uma interrupção, o estado é reconciliado com o workspace antes de retomar, prevenindo side-effects duplicados.
              </div>
              <div className="text-xs font-mono text-teal-300 bg-[#0c1417] p-3 rounded border border-gray-800">
                CRASH → LOAD CHECKPOINT → RECONCILE → DETECT RESIDUALS → RESUME
              </div>
            </div>
          </div>
        )}

        {/* 12. Human Review */}
        {activeSubtab === 'human-review' && (
          <div id="longhorizon-view-human-review" className="space-y-4">
            <h3 className="text-sm font-bold text-white">Tickets de Governação & Revisão Humana</h3>
            <div className="rounded border border-gray-800 bg-[#0f191d] p-4">
              <div className="text-xs text-gray-400">Zero tickets de revisão pendentes. Se um timeout ocorrer, o motor transita para BLOCKED.</div>
            </div>
          </div>
        )}

        {/* 13. Completion Proof */}
        {activeSubtab === 'completion' && (
          <div id="longhorizon-view-completion" className="space-y-4">
            <h3 className="text-sm font-bold text-white">Scorecard de Prova de Conclusão (MissionCompletionProof)</h3>
            <div className="rounded border border-gray-800 bg-[#0f191d] p-4 space-y-3 text-xs">
              <div className="flex justify-between border-b border-gray-800 pb-2">
                <span className="text-gray-400">Primary Objectives Satisfied:</span>
                <span className="text-emerald-400 font-bold">TRUE</span>
              </div>
              <div className="flex justify-between border-b border-gray-800 pb-2">
                <span className="text-gray-400">Continuous Verification Coverage:</span>
                <span className="text-emerald-400 font-bold">100.0%</span>
              </div>
              <div className="flex justify-between border-b border-gray-800 pb-2">
                <span className="text-gray-400">Architecture Consistency:</span>
                <span className="text-emerald-400 font-bold">VERIFIED_STABLE</span>
              </div>
              <div className="flex justify-between border-b border-gray-800 pb-2">
                <span className="text-gray-400">Contract & Behavioral Proof:</span>
                <span className="text-emerald-400 font-bold">INSPECTED_PRESERVED</span>
              </div>
              <div className="flex justify-between pt-1">
                <span className="text-gray-400">Resultado Final:</span>
                <span className="text-emerald-300 font-bold">COMPLETED_WITHIN_SCOPE</span>
              </div>
            </div>
          </div>
        )}

        {/* 14. Termination State */}
        {activeSubtab === 'termination' && (
          <div id="longhorizon-view-termination" className="space-y-4">
            <h3 className="text-sm font-bold text-white">Estado Terminal & Auditoria Final</h3>
            <div className="rounded border border-gray-800 bg-[#0f191d] p-4 space-y-2 text-xs">
              <div className="text-gray-300">
                Estados terminais válidos: <span className="font-mono text-teal-300">COMPLETED_WITHIN_SCOPE, COMPLETED_WITH_UNRESOLVED_RISK, BLOCKED, FAILED, CANCELLED, ROLLED_BACK, INCONCLUSIVE</span>.
              </div>
              <div className="text-gray-500">
                Cada terminação possui registo de motivo, evidências criptográficas e hash de checkpoint final.
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
