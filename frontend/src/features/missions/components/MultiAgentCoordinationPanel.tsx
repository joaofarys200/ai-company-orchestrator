import React, { useState } from 'react';
import {
  Users,
  ShieldCheck,
  AlertTriangle,
  RotateCcw,
  Zap,
  Activity,
  Lock,
  GitMerge,
  Network,
  Clock,
  Scale,
  Award,
} from 'lucide-react';

interface MultiAgentCoordinationPanelProps {
  missionId?: string;
}

export const MultiAgentCoordinationPanel: React.FC<MultiAgentCoordinationPanelProps> = ({
  missionId: _missionId,
}) => {
  const [activeSubtab, setActiveSubtab] = useState<string>('agents');
  const [policy, setPolicy] = useState<string>('STANDARD');

  return (
    <div className="flex h-full flex-col bg-[#0b1317] text-gray-200">
      {/* Header bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[#a1bebf]/15 bg-[#0d171b] px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
            <Users className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-white">
                Multi-Agent Engineering Coordination & Conflict Arbitration
              </h2>
              <span className="rounded bg-indigo-500/20 px-2 py-0.5 text-xs font-semibold text-indigo-300">
                FASE 66
              </span>
              <span className="flex items-center gap-1 rounded bg-emerald-500/20 px-2 py-0.5 text-xs font-semibold text-emerald-300">
                <ShieldCheck className="h-3 w-3" />
                COORDINATION ENGINE ACTIVE
              </span>
            </div>
            <p className="text-xs text-gray-400">
              Multi-granularity resource claims, Kahn DAG scheduling, semantic conflict arbitration, 3-way merge, and commit gate verification.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-400">Política:</span>
            <select
              value={policy}
              onChange={(e) => setPolicy(e.target.value)}
              className="rounded border border-gray-700 bg-[#121e23] px-2.5 py-1 text-xs text-gray-200 focus:border-indigo-500 focus:outline-none"
            >
              <option value="STRICT">STRICT (Zero Tolerance)</option>
              <option value="STANDARD">STANDARD (Governed)</option>
              <option value="OPTIMISTIC">OPTIMISTIC (Merge Priority)</option>
              <option value="FAIR">FAIR (Anti-Starvation)</option>
            </select>
          </div>

          <button
            id="coord-action-submit-intent"
            className="flex items-center gap-1.5 rounded bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-500 transition-colors"
          >
            <Zap className="h-3.5 w-3.5" />
            Submeter Intenção
          </button>
        </div>
      </div>

      {/* 12 Scenario Subtabs */}
      <div className="flex border-b border-gray-800 bg-[#0c1417] px-6 text-xs font-semibold overflow-x-auto">
        <button
          id="coord-subtab-agents"
          onClick={() => setActiveSubtab('agents')}
          className={`flex items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2.5 transition-colors ${
            activeSubtab === 'agents'
              ? 'border-indigo-500 text-indigo-300'
              : 'border-transparent text-gray-400 hover:text-gray-200'
          }`}
        >
          <Users className="h-3.5 w-3.5" />
          01. Agent Overview
        </button>

        <button
          id="coord-subtab-intents"
          onClick={() => setActiveSubtab('intents')}
          className={`flex items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2.5 transition-colors ${
            activeSubtab === 'intents'
              ? 'border-indigo-500 text-indigo-300'
              : 'border-transparent text-gray-400 hover:text-gray-200'
          }`}
        >
          <Zap className="h-3.5 w-3.5" />
          02. Intents
        </button>

        <button
          id="coord-subtab-claims"
          onClick={() => setActiveSubtab('claims')}
          className={`flex items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2.5 transition-colors ${
            activeSubtab === 'claims'
              ? 'border-indigo-500 text-indigo-300'
              : 'border-transparent text-gray-400 hover:text-gray-200'
          }`}
        >
          <Lock className="h-3.5 w-3.5" />
          03. Resource Claims
        </button>

        <button
          id="coord-subtab-dependencies"
          onClick={() => setActiveSubtab('dependencies')}
          className={`flex items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2.5 transition-colors ${
            activeSubtab === 'dependencies'
              ? 'border-indigo-500 text-indigo-300'
              : 'border-transparent text-gray-400 hover:text-gray-200'
          }`}
        >
          <Network className="h-3.5 w-3.5" />
          04. Dependency Graph
        </button>

        <button
          id="coord-subtab-conflicts"
          onClick={() => setActiveSubtab('conflicts')}
          className={`flex items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2.5 transition-colors ${
            activeSubtab === 'conflicts'
              ? 'border-indigo-500 text-indigo-300'
              : 'border-transparent text-gray-400 hover:text-gray-200'
          }`}
        >
          <AlertTriangle className="h-3.5 w-3.5" />
          05. Conflict Matrix
        </button>

        <button
          id="coord-subtab-arbitration"
          onClick={() => setActiveSubtab('arbitration')}
          className={`flex items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2.5 transition-colors ${
            activeSubtab === 'arbitration'
              ? 'border-indigo-500 text-indigo-300'
              : 'border-transparent text-gray-400 hover:text-gray-200'
          }`}
        >
          <Scale className="h-3.5 w-3.5" />
          06. Arbitration
        </button>

        <button
          id="coord-subtab-waves"
          onClick={() => setActiveSubtab('waves')}
          className={`flex items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2.5 transition-colors ${
            activeSubtab === 'waves'
              ? 'border-indigo-500 text-indigo-300'
              : 'border-transparent text-gray-400 hover:text-gray-200'
          }`}
        >
          <Activity className="h-3.5 w-3.5" />
          07. Parallel Waves
        </button>

        <button
          id="coord-subtab-merge"
          onClick={() => setActiveSubtab('merge')}
          className={`flex items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2.5 transition-colors ${
            activeSubtab === 'merge'
              ? 'border-indigo-500 text-indigo-300'
              : 'border-transparent text-gray-400 hover:text-gray-200'
          }`}
        >
          <GitMerge className="h-3.5 w-3.5" />
          08. Merge
        </button>

        <button
          id="coord-subtab-rebase"
          onClick={() => setActiveSubtab('rebase')}
          className={`flex items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2.5 transition-colors ${
            activeSubtab === 'rebase'
              ? 'border-indigo-500 text-indigo-300'
              : 'border-transparent text-gray-400 hover:text-gray-200'
          }`}
        >
          <RotateCcw className="h-3.5 w-3.5" />
          09. Rebase
        </button>

        <button
          id="coord-subtab-deadlock"
          onClick={() => setActiveSubtab('deadlock')}
          className={`flex items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2.5 transition-colors ${
            activeSubtab === 'deadlock'
              ? 'border-indigo-500 text-indigo-300'
              : 'border-transparent text-gray-400 hover:text-gray-200'
          }`}
        >
          <Clock className="h-3.5 w-3.5" />
          10. Deadlock & Starvation
        </button>

        <button
          id="coord-subtab-rollback"
          onClick={() => setActiveSubtab('rollback')}
          className={`flex items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2.5 transition-colors ${
            activeSubtab === 'rollback'
              ? 'border-indigo-500 text-indigo-300'
              : 'border-transparent text-gray-400 hover:text-gray-200'
          }`}
        >
          <RotateCcw className="h-3.5 w-3.5" />
          11. Rollback & Isolation
        </button>

        <button
          id="coord-subtab-verification"
          onClick={() => setActiveSubtab('verification')}
          className={`flex items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2.5 transition-colors ${
            activeSubtab === 'verification'
              ? 'border-indigo-500 text-indigo-300'
              : 'border-transparent text-gray-400 hover:text-gray-200'
          }`}
        >
          <Award className="h-3.5 w-3.5" />
          12. Shared Verification
        </button>
      </div>

      {/* Main Content Body */}
      <div className="flex-1 overflow-y-auto p-6">
        {/* SUBTAB 01: AGENT OVERVIEW */}
        {activeSubtab === 'agents' && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <div className="rounded-lg border border-gray-800 bg-[#0d171b] p-4">
                <span className="text-xs text-gray-400">Agentes Ativos Concorrentes</span>
                <p className="mt-1 text-2xl font-bold text-indigo-400">8 / 64</p>
                <span className="text-[10px] text-emerald-400">Enxame em coordenação segura</span>
              </div>
              <div className="rounded-lg border border-gray-800 bg-[#0d171b] p-4">
                <span className="text-xs text-gray-400">Taxa de Conflitos</span>
                <p className="mt-1 text-2xl font-bold text-amber-400">12.5%</p>
                <span className="text-[10px] text-gray-400">1 conflito arbitrado deterministicamente</span>
              </div>
              <div className="rounded-lg border border-gray-800 bg-[#0d171b] p-4">
                <span className="text-xs text-gray-400">Ondas Paralelas Seguras</span>
                <p className="mt-1 text-2xl font-bold text-emerald-400">3 Ondas</p>
                <span className="text-[10px] text-emerald-400">Zero escritas concorrentes no mesmo workspace</span>
              </div>
              <div className="rounded-lg border border-gray-800 bg-[#0d171b] p-4">
                <span className="text-xs text-gray-400">Commit Gate</span>
                <p className="mt-1 text-2xl font-bold text-emerald-400">PASS</p>
                <span className="text-[10px] text-emerald-400">100% verificado pós-merge</span>
              </div>
            </div>

            <div className="rounded-lg border border-gray-800 bg-[#0d171b] p-5">
              <h3 className="mb-4 text-sm font-semibold text-white">Agentes de Engenharia Concorrentes em Execução</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-gray-800 text-gray-400">
                      <th className="pb-2">Agente ID</th>
                      <th className="pb-2">Especialidade / Tarefa</th>
                      <th className="pb-2">Recursos Solicitados</th>
                      <th className="pb-2">Granularidade</th>
                      <th className="pb-2">Estado</th>
                      <th className="pb-2">Workspace ID</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-800/50">
                    <tr>
                      <td className="py-2.5 font-mono text-indigo-300">agent_frontend_01</td>
                      <td className="py-2.5">Frontend Extraction & UI Migration</td>
                      <td className="py-2.5 text-gray-300">frontend/src/features/missions/</td>
                      <td className="py-2.5"><span className="rounded bg-blue-500/20 px-1.5 py-0.5 text-blue-300">FILE</span></td>
                      <td className="py-2.5"><span className="rounded bg-emerald-500/20 px-1.5 py-0.5 text-emerald-300">RUNNING</span></td>
                      <td className="py-2.5 font-mono text-gray-400">ws_fe_7a2f</td>
                    </tr>
                    <tr>
                      <td className="py-2.5 font-mono text-indigo-300">agent_backend_02</td>
                      <td className="py-2.5">Backend Handler Extraction & Routes</td>
                      <td className="py-2.5 text-gray-300">backend/websocket/handlers/</td>
                      <td className="py-2.5"><span className="rounded bg-cyan-500/20 px-1.5 py-0.5 text-cyan-300">SYMBOL</span></td>
                      <td className="py-2.5"><span className="rounded bg-emerald-500/20 px-1.5 py-0.5 text-emerald-300">RUNNING</span></td>
                      <td className="py-2.5 font-mono text-gray-400">ws_be_8b3e</td>
                    </tr>
                    <tr>
                      <td className="py-2.5 font-mono text-indigo-300">agent_contract_03</td>
                      <td className="py-2.5">Contract Schema & Interface Update</td>
                      <td className="py-2.5 text-gray-300">backend/websocket/contracts.py</td>
                      <td className="py-2.5"><span className="rounded bg-purple-500/20 px-1.5 py-0.5 text-purple-300">CONTRACT</span></td>
                      <td className="py-2.5"><span className="rounded bg-amber-500/20 px-1.5 py-0.5 text-amber-300">WAITING (Dependency)</span></td>
                      <td className="py-2.5 font-mono text-gray-400">ws_ct_9c4d</td>
                    </tr>
                    <tr>
                      <td className="py-2.5 font-mono text-indigo-300">agent_test_04</td>
                      <td className="py-2.5">Test Suite Synthesis & Validation</td>
                      <td className="py-2.5 text-gray-300">tests/test_multi_agent_coord.py</td>
                      <td className="py-2.5"><span className="rounded bg-blue-500/20 px-1.5 py-0.5 text-blue-300">FILE</span></td>
                      <td className="py-2.5"><span className="rounded bg-emerald-500/20 px-1.5 py-0.5 text-emerald-300">RUNNING</span></td>
                      <td className="py-2.5 font-mono text-gray-400">ws_ts_1d5e</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* SUBTAB 02: INTENTS */}
        {activeSubtab === 'intents' && (
          <div className="space-y-6">
            <div className="rounded-lg border border-gray-800 bg-[#0d171b] p-5">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-white">Fila de Intenções de Engenharia (AgentEngineeringIntent)</h3>
                <span className="rounded bg-indigo-500/20 px-2 py-0.5 text-xs text-indigo-300">8 Intenções Registadas</span>
              </div>
              <div className="space-y-3">
                <div className="rounded border border-gray-800 bg-[#121e23] p-3">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs text-indigo-300 font-bold">intent_task_frontend_extraction</span>
                    <span className="rounded bg-emerald-500/20 px-2 py-0.5 text-[10px] font-semibold text-emerald-300">VALIDATED</span>
                  </div>
                  <p className="mt-1 text-xs text-gray-300">Extrair painel de coordenação multi-agente e montar abas com isolamento modular.</p>
                  <div className="mt-2 flex gap-4 text-[11px] text-gray-400">
                    <span>Ficheiros: 2</span>
                    <span>Símbolos: MultiAgentCoordinationPanel</span>
                    <span>Prioridade: Vector(Crit: 0.8, Risk: 0.2, Rev: 1.0)</span>
                  </div>
                </div>

                <div className="rounded border border-gray-800 bg-[#121e23] p-3">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs text-indigo-300 font-bold">intent_task_contract_update</span>
                    <span className="rounded bg-amber-500/20 px-2 py-0.5 text-[10px] font-semibold text-amber-300">CLAIMED</span>
                  </div>
                  <p className="mt-1 text-xs text-gray-300">Adicionar 4 novos tipos de mensagens WebSocket para arbitragem e escalonamento.</p>
                  <div className="mt-2 flex gap-4 text-[11px] text-gray-400">
                    <span>Ficheiros: 1</span>
                    <span>Símbolos: EXPECTED_MESSAGE_TYPES</span>
                    <span>Prioridade: Vector(Crit: 0.9, Risk: 0.4, Rev: 0.9)</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* SUBTAB 03: RESOURCE CLAIMS */}
        {activeSubtab === 'claims' && (
          <div className="space-y-6">
            <div className="rounded-lg border border-gray-800 bg-[#0d171b] p-5">
              <h3 className="mb-4 text-sm font-semibold text-white">Bloqueios & Resource Claims por Granularidade</h3>
              <p className="text-xs text-gray-400 mb-4">
                Coordenação fina por Símbolo, Contrato e Arquitetura sem bloqueio monolítico por ficheiro quando seguro.
              </p>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="rounded border border-gray-800 bg-[#121e23] p-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-white">backend/websocket/contracts.py</span>
                    <span className="rounded bg-amber-500/20 px-1.5 py-0.5 text-[10px] text-amber-300">EXCLUSIVE</span>
                  </div>
                  <p className="mt-1 text-xs text-gray-400">Granularidade: CONTRACT</p>
                  <p className="text-xs text-gray-400">Detentor: agent_contract_03</p>
                  <span className="text-[10px] text-emerald-400">TTL: 42s restantes</span>
                </div>
                <div className="rounded border border-gray-800 bg-[#121e23] p-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-white">MultiAgentCoordinationPanel</span>
                    <span className="rounded bg-blue-500/20 px-1.5 py-0.5 text-[10px] text-blue-300">WRITE</span>
                  </div>
                  <p className="mt-1 text-xs text-gray-400">Granularidade: SYMBOL</p>
                  <p className="text-xs text-gray-400">Detentor: agent_frontend_01</p>
                  <span className="text-[10px] text-emerald-400">TTL: 58s restantes</span>
                </div>
                <div className="rounded border border-gray-800 bg-[#121e23] p-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-white">tests/test_multi_agent_coord.py</span>
                    <span className="rounded bg-emerald-500/20 px-1.5 py-0.5 text-[10px] text-emerald-300">EXCLUSIVE</span>
                  </div>
                  <p className="mt-1 text-xs text-gray-400">Granularidade: FILE</p>
                  <p className="text-xs text-gray-400">Detentor: agent_test_04</p>
                  <span className="text-[10px] text-emerald-400">TTL: 110s restantes</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* SUBTAB 04: DEPENDENCY GRAPH */}
        {activeSubtab === 'dependencies' && (
          <div className="space-y-6">
            <div className="rounded-lg border border-gray-800 bg-[#0d171b] p-5">
              <h3 className="mb-2 text-sm font-semibold text-white">Grafo de Coordenação & Análise Causal (Kahn DAG)</h3>
              <p className="text-xs text-gray-400 mb-4">
                Identificação formal de dependências seriais, componentes fortemente conexas (SCC) e tarefas seguras em paralelo.
              </p>
              <div className="rounded border border-gray-800 bg-[#121e23] p-4 text-xs font-mono">
                <p className="text-indigo-400"># Ordem Topológica Determinística:</p>
                <p className="text-gray-300 mt-1">1. [WAVE 1] agent_frontend_01, agent_backend_02, agent_test_04 (Disjuntos)</p>
                <p className="text-gray-300 mt-1">2. [WAVE 2] agent_contract_03 (Depende da definição dos contratos no backend)</p>
                <p className="text-gray-300 mt-1">3. [WAVE 3] agent_browser_05 (Depende do frontend montado para QA Playwright)</p>
                <div className="mt-3 border-t border-gray-700/50 pt-2 flex gap-4 text-gray-400">
                  <span>Ciclos Causalidade: <strong className="text-emerald-400">0 Detectados</strong></span>
                  <span>Tarefas Paralelas: <strong className="text-indigo-300">6/8</strong></span>
                  <span>Tarefas Seriais: <strong className="text-amber-300">2/8</strong></span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* SUBTAB 05: CONFLICT MATRIX */}
        {activeSubtab === 'conflicts' && (
          <div className="space-y-6">
            <div className="rounded-lg border border-gray-800 bg-[#0d171b] p-5">
              <h3 className="mb-4 text-sm font-semibold text-white">Matriz de Conflitos Multi-Granularidade</h3>
              <div className="space-y-3">
                <div className="rounded border border-amber-500/30 bg-amber-500/10 p-4 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-amber-300">CONTRACT_CONFLICT (Severidade: ALTA)</span>
                    <span className="rounded bg-amber-500/20 px-2 py-0.5 text-[10px] text-amber-200">RESOLVIDO</span>
                  </div>
                  <p className="mt-1 text-gray-200">
                    Agente B (Backend) e Agente C (Contratos) solicitaram alteração simultânea da assinatura de mensagens WebSocket.
                  </p>
                  <p className="mt-2 text-gray-400">Resolução do Árbitro: SERIALIZE (Agente B precede Agente C com verificação de compatibilidade reversa).</p>
                </div>

                <div className="rounded border border-blue-500/30 bg-blue-500/10 p-4 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-blue-300">SAME_FILE_DIFFERENT_SYMBOLS (Severidade: BAIXA)</span>
                    <span className="rounded bg-blue-500/20 px-2 py-0.5 text-[10px] text-blue-200">PARALLEL_SAFE</span>
                  </div>
                  <p className="mt-1 text-gray-200">
                    Agente A e Agente F tocam o mesmo ficheiro em funções disjuntas. Bloqueio ao nível de símbolo permitiu execução paralela.
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* SUBTAB 06: ARBITRATION */}
        {activeSubtab === 'arbitration' && (
          <div className="space-y-6">
            <div className="rounded-lg border border-gray-800 bg-[#0d171b] p-5">
              <h3 className="mb-4 text-sm font-semibold text-white">Motor de Arbitragem Determinístico (ConflictArbiter)</h3>
              <p className="text-xs text-gray-400 mb-4">
                Decisões governadas por consistência arquitetural, invariantes contratuais e veto do Security Sentinel.
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                <div className="rounded border border-gray-800 bg-[#121e23] p-3">
                  <span className="font-semibold text-indigo-300">Regra de Segurança Estrita:</span>
                  <p className="mt-1 text-gray-300">
                    Nenhum conflito envolvendo ficheiros protegidos (ex: security/, .env, secrets) pode ser ignorado por prioridade de missão.
                  </p>
                </div>
                <div className="rounded border border-gray-800 bg-[#121e23] p-3">
                  <span className="font-semibold text-indigo-300">Preservação de Semântica Contratual:</span>
                  <p className="mt-1 text-gray-300">
                    Se dois agentes alterarem o mesmo contrato sem garantia de backward compatibility, o árbitro impõe SERIALIZE ou SPLIT.
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* SUBTAB 07: PARALLEL WAVES */}
        {activeSubtab === 'waves' && (
          <div className="space-y-6">
            <div className="rounded-lg border border-gray-800 bg-[#0d171b] p-5">
              <h3 className="mb-4 text-sm font-semibold text-white">Escalonamento por Ondas Paralelas (CoordinationScheduler)</h3>
              <div className="space-y-4">
                <div className="rounded border border-emerald-500/30 bg-[#121e23] p-4">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-emerald-400">ONDA 1 — Execução Paralela Safe</span>
                    <span className="rounded bg-emerald-500/20 px-2 py-0.5 text-[10px] text-emerald-300">CONCLUÍDO</span>
                  </div>
                  <p className="mt-1 text-xs text-gray-300">Agentes: [Frontend, Backend, Test, Docs, Refactor] — 5 agentes simultâneos em workspaces isolados.</p>
                </div>
                <div className="rounded border border-indigo-500/30 bg-[#121e23] p-4">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-indigo-400">ONDA 2 — Dependência Causal Resolvida</span>
                    <span className="rounded bg-indigo-500/20 px-2 py-0.5 text-[10px] text-indigo-300">EM CURSO</span>
                  </div>
                  <p className="mt-1 text-xs text-gray-300">Agentes: [Contract Update, Architecture Observation] — 2 agentes simultâneos após rebase limpo.</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* SUBTAB 08: MERGE */}
        {activeSubtab === 'merge' && (
          <div className="space-y-6">
            <div className="rounded-lg border border-gray-800 bg-[#0d171b] p-5">
              <h3 className="mb-4 text-sm font-semibold text-white">Motor de Merge Semântico 3-Way (CoordinationMergeEngine)</h3>
              <p className="text-xs text-gray-400 mb-4">
                Base comum + Patch A + Patch B $\rightarrow$ Verificação de AST e Ausência de Quebra Sintática.
              </p>
              <div className="rounded border border-gray-800 bg-[#121e23] p-4 text-xs font-mono">
                <div className="flex justify-between border-b border-gray-700/50 pb-2">
                  <span className="text-gray-400">Snapshot Base: <strong className="text-indigo-300">snap_base_04f1</strong></span>
                  <span className="text-emerald-400 font-bold">MERGE_SUCCESS</span>
                </div>
                <div className="mt-3 space-y-1 text-gray-300">
                  <p>$\checkmark$ Ficheiros mesclados: 8 ficheiros</p>
                  <p>$\checkmark$ Conflitos de texto: 0</p>
                  <p>$\checkmark$ Validação de AST pós-merge: 100% Válido</p>
                  <p>$\checkmark$ Hash de Evidência: <span className="text-indigo-400 font-mono">e6a2b8...c719</span></p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* SUBTAB 09: REBASE */}
        {activeSubtab === 'rebase' && (
          <div className="space-y-6">
            <div className="rounded-lg border border-gray-800 bg-[#0d171b] p-5">
              <h3 className="mb-4 text-sm font-semibold text-white">Rebase Semântico & Stale Base Detection (RebaseEngine)</h3>
              <p className="text-xs text-gray-400 mb-4">
                Quando a base evolui concorrentemente, o patch é reaplicado e reverificado quanto a desvios de intenção.
              </p>
              <div className="rounded border border-gray-800 bg-[#121e23] p-4 text-xs">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-indigo-300">Histórico de Rebases:</span>
                  <span className="rounded bg-emerald-500/20 px-2 py-0.5 text-[10px] text-emerald-300">100% INTENT PRESERVED</span>
                </div>
                <p className="mt-2 text-gray-300">
                  Patch da Tarefa 4 (Browser Test Update) foi rebaseado após o merge da Tarefa 1 (Frontend Extraction). A semântica original permaneceu inalterada.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* SUBTAB 10: DEADLOCK & STARVATION */}
        {activeSubtab === 'deadlock' && (
          <div className="space-y-6">
            <div className="rounded-lg border border-gray-800 bg-[#0d171b] p-5">
              <h3 className="mb-4 text-sm font-semibold text-white">Detetor de Deadlock & Prevenção de Starvation</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                <div className="rounded border border-emerald-500/30 bg-emerald-500/10 p-4">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-emerald-300">Deadlock Detector</span>
                    <span className="rounded bg-emerald-500/20 px-2 py-0.5 text-[10px] text-emerald-200">NO_DEADLOCK</span>
                  </div>
                  <p className="mt-1 text-gray-200">Grafo de espera direcionado livre de ciclos circulares.</p>
                </div>
                <div className="rounded border border-indigo-500/30 bg-indigo-500/10 p-4">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-indigo-300">Anti-Starvation Engine</span>
                    <span className="rounded bg-indigo-500/20 px-2 py-0.5 text-[10px] text-indigo-200">FAIR PRIORITY ACTIVE</span>
                  </div>
                  <p className="mt-1 text-gray-200">Nenhum agente esperando há mais de 4 ondas. Starvation boost ativo.</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* SUBTAB 11: ROLLBACK & ISOLATION */}
        {activeSubtab === 'rollback' && (
          <div className="space-y-6">
            <div className="rounded-lg border border-gray-800 bg-[#0d171b] p-5">
              <h3 className="mb-4 text-sm font-semibold text-white">Isolamento Transacional & Rollback Deterministico</h3>
              <p className="text-xs text-gray-400 mb-4">
                Cada agente executa em sandbox transacional independente. Falhas revertem apenas a transação afetada.
              </p>
              <div className="rounded border border-gray-800 bg-[#121e23] p-4 text-xs font-mono">
                <div className="flex justify-between text-gray-300 pb-2 border-b border-gray-700/50">
                  <span>Workspaces Transacionais Ativos: <strong className="text-indigo-300">8</strong></span>
                  <span>Isolamento: <strong className="text-emerald-400">100% ISOLATED</strong></span>
                </div>
                <p className="mt-2 text-gray-400">
                  Em caso de teste com falha pós-merge, o snapshot restaura atomicamente o repositório sem deixar resíduos.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* SUBTAB 12: SHARED VERIFICATION */}
        {activeSubtab === 'verification' && (
          <div className="space-y-6">
            <div className="rounded-lg border border-gray-800 bg-[#0d171b] p-5">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-white">Verificação Contínua Pós-Merge & Commit Gate</h3>
                <span className="rounded bg-emerald-500/20 px-2 py-0.5 text-xs font-bold text-emerald-300">MULTI_AGENT_COORDINATION_READY = TRUE</span>
              </div>
              <div className="rounded border border-gray-800 bg-[#121e23] p-4 text-xs space-y-2">
                <p className="text-gray-300">$\checkmark$ Verificação Multi-Agente: 8 tarefas concorrentes aprovadas</p>
                <p className="text-gray-300">$\checkmark$ Regressão F40–F66: Denominadores reconciliados ($\Delta = 0$)</p>
                <p className="text-gray-300">$\checkmark$ Veto do Security Sentinel: 0 violações de segurança</p>
                <p className="text-gray-300">$\checkmark$ Grafo Causal de Proveniência: Registado em ledger imutável</p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default MultiAgentCoordinationPanel;
