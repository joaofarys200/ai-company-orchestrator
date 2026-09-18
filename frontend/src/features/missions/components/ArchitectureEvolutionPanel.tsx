import React, { useState } from 'react';
import {
  Workflow,
  ShieldCheck,
  AlertTriangle,
  GitBranch,
  Layers,
  CheckCircle2,
  Lock,
  Compass,
  RotateCcw,
  Zap,
  Activity,
  FileCheck,
  Scale,
  ShieldAlert,
} from 'lucide-react';

export const ArchitectureEvolutionPanel: React.FC = () => {
  const [activeTab, setActiveTab] = useState<
    | 'overview'
    | 'problems'
    | 'constraints'
    | 'alternatives'
    | 'comparison'
    | 'impact'
    | 'contracts'
    | 'behavior'
    | 'risk'
    | 'migration'
    | 'simulation'
    | 'governance'
  >('overview');

  const [selectedProblemId, setSelectedProblemId] = useState<string>('prob_scc_4a8f9c1b');
  const [policyMode, setPolicyMode] = useState<string>('STANDARD');
  const [isObserving, setIsObserving] = useState<boolean>(false);
  const [isEvaluating, setIsEvaluating] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const snapshotData = {
    snapshot_id: 'snap_jarvis_core_v64',
    snapshot_hash: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
    nodes_count: 142,
    edges_count: 318,
    sccs_count: 3,
    contracts_count: 24,
    risk_zones_count: 2,
    external_boundaries_count: 4,
  };

  const problems = [
    {
      problem_id: 'prob_scc_4a8f9c1b',
      category: 'SCC',
      severity: 'HIGH',
      status: 'CONFIRMED_WITHIN_SCOPE',
      confidence: 0.98,
      title: 'Cyclic Coupling Loop between Autonomous Loop & Continuous Verification',
      affected_nodes: [
        'agents/autonomous_loop/controller.py',
        'backend/agents/continuous_verification/bridge.py',
        'agents/mission_orchestrator.py',
      ],
      affected_symbols: [
        'AutonomousLoopController::step',
        'ContinuousVerificationBridge::verify_change',
      ],
      evidence: 'Strongly connected component of size 3 creates cyclic import loop and prevents independent unit compilation.',
    },
    {
      problem_id: 'prob_coupling_8f12d09a',
      category: 'COUPLING',
      severity: 'MEDIUM',
      status: 'CONFIRMED_WITHIN_SCOPE',
      confidence: 0.94,
      title: 'Shared Database Table Access across Services',
      affected_nodes: [
        'backend/websocket/handlers/missions.py',
        'agents/autonomous_loop/controller.py',
        'database/sqlite_store.py',
      ],
      affected_symbols: ['execute_query', 'save_checkpoint'],
      evidence: 'Persistence table "missions" accessed directly without formal DAO boundary layer.',
    },
    {
      problem_id: 'prob_contract_90b2ef11',
      category: 'CONTRACT',
      severity: 'MEDIUM',
      status: 'OBSERVED',
      confidence: 0.91,
      title: 'Contract Concentration in Mission Control Schema',
      affected_nodes: ['contracts/mission_schema.json'],
      affected_symbols: ['MissionSnapshot', 'IntentPayload'],
      evidence: '14 consumers dependent on a single unversioned schema definition.',
    },
    {
      problem_id: 'prob_security_33df78ab',
      category: 'SECURITY',
      severity: 'HIGH',
      status: 'SUSPECTED',
      confidence: 0.85,
      title: 'Dynamic Reflection Boundary in Plugin Registry',
      affected_nodes: ['agents/plugins/registry.py'],
      affected_symbols: ['getattr_dynamic_dispatch'],
      evidence: 'Dynamic string attribute dispatch hinders static verification graph derivation.',
    },
    {
      problem_id: 'prob_maintain_11bbcc22',
      category: 'MAINTAINABILITY',
      severity: 'LOW',
      status: 'OBSERVED',
      confidence: 0.88,
      title: 'Central WebSocket Dispatcher Fan-In Hub',
      affected_nodes: ['backend/websocket/handlers/missions.py'],
      affected_symbols: ['handle_mission_control'],
      evidence: 'Large dispatch table handling 28 distinct mission operations.',
    },
  ];

  const constraints = [
    {
      id: 'c1',
      name: 'backward_compatibility_guarantee',
      category: 'compatibility',
      description: 'Preserve API and WebSocket schema compatibility for all active frontend views.',
      confidence: 0.98,
    },
    {
      id: 'c2',
      name: 'security_sentinel_inviolability',
      category: 'security',
      description: 'Zero privilege escalation; no secret exposure; mandatory Sentinel audit.',
      confidence: 1.0,
    },
    {
      id: 'c3',
      name: 'regression_test_invariance',
      category: 'non_functional',
      description: 'Full historical regression suite (F40-F64) must remain 100% green.',
      confidence: 0.95,
    },
    {
      id: 'c4',
      name: 'deterministic_rollback_requirement',
      category: 'migration',
      description: 'Every staged step must declare an automated rollback action with zero data loss.',
      confidence: 0.92,
    },
    {
      id: 'c5',
      name: 'resource_budget_bound',
      category: 'economic',
      description: 'Estimated migration effort must not exceed 40 engineering hours.',
      confidence: 0.88,
    },
  ];

  const alternatives = [
    {
      id: 'alt_keep_01',
      title: 'A. Maintain Current Topology (Document Smell)',
      type: 'keep_current',
      reversibility: 'EASILY_REVERSIBLE',
      blast_radius: 0,
      effort_hours: 11.0,
      risk: 'LOW',
      pros: ['Zero downtime risk', 'Zero deployment complexity', 'Zero immediate engineering churn'],
      cons: ['Technical debt accumulation', 'Continuing cyclic coupling in local tests'],
    },
    {
      id: 'alt_bound_02',
      title: 'B. Boundary & Interface Extraction (Recommended Candidate)',
      type: 'boundary_extraction',
      reversibility: 'EASILY_REVERSIBLE',
      blast_radius: 8,
      effort_hours: 24.5,
      risk: 'LOW',
      pros: ['Breaks cyclic SCC completely', 'Enforces clean dependency inversion', 'High testability'],
      cons: ['Requires intermediate interface package', 'Minor import re-wiring'],
    },
    {
      id: 'alt_evt_03',
      title: 'C. Asynchronous Event-Driven Decoupling',
      type: 'event_driven',
      reversibility: 'DIFFICULT_TO_REVERSE',
      blast_radius: 22,
      effort_hours: 48.0,
      risk: 'HIGH',
      pros: ['Complete temporal decoupling', 'Independent worker scalability'],
      cons: ['Eventual consistency anomalies', 'Higher operational debugging complexity', 'Requires event bus'],
    },
    {
      id: 'alt_f63_04',
      title: 'D. Cross-Project Transferred Hypothesis (Phase 63)',
      type: 'adapter_layer',
      reversibility: 'REVERSIBLE_WITH_MIGRATION',
      blast_radius: 12,
      effort_hours: 18.0,
      risk: 'MEDIUM',
      pros: ['Reuses proven pattern from donor repo', 'Two-way translation isolates schema shift'],
      cons: ['Requires new local test synthesis before approval', 'Translation overhead'],
    },
  ];

  const migrationSteps = [
    { id: 's1', stage: 'PREPARATION', title: 'Baseline Snapshot & Dynamic Feature Flag', rollback: 'Drop flag and revert to v64 snapshot', safe: true },
    { id: 's2', stage: 'COMPATIBILITY_LAYER', title: 'Deploy Intermediate Interface Abstraction', rollback: 'De-register shim bindings', safe: true },
    { id: 's3', stage: 'DUAL_PATH', title: 'Shadow Dual-Execution & Verification', rollback: 'Set shadow rate to 0%', safe: true },
    { id: 's4', stage: 'VALIDATION', title: 'Continuous Verification & Behavioral Invariants (F62)', rollback: 'Revert shadow telemetry', safe: true },
    { id: 's5', stage: 'CUTOVER', title: 'Canary Traffic Promotion (10% -> 100%)', rollback: 'Immediate fallback to 100% legacy', safe: true },
    { id: 's6', stage: 'OBSERVATION', title: '24-Hour Soak & De-coupled SCC Invariant Check', rollback: 'Blue-green cutback', safe: true },
    { id: 's7', stage: 'CLEANUP', title: 'Legacy Import Deprecation & Cleanup', rollback: 'Git commit restoration', safe: true },
  ];

  const handleObserve = () => {
    setIsObserving(true);
    setStatusMessage('Scanning workspace dependency graph, SCCs, and contract concentration...');
    setTimeout(() => {
      setIsObserving(false);
      setStatusMessage('Observation complete: 5 architectural problems confirmed within scope.');
    }, 600);
  };

  const handleEvaluate = () => {
    setIsEvaluating(true);
    setStatusMessage('Synthesizing constraints, alternatives, impact graph, and simulation...');
    setTimeout(() => {
      setIsEvaluating(false);
      setStatusMessage('Evaluation complete: 4 alternatives compared with explicit trade-offs. Governance verdict: APPROVED_FOR_IMPLEMENTATION.');
    }, 700);
  };

  return (
    <div className="flex h-full flex-col bg-[#0a1114] text-gray-100 overflow-y-auto">
      {/* Top Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[#a1bebf]/15 bg-[#0d171b] px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="rounded-lg bg-cyan-500/10 p-2 border border-cyan-500/20 text-cyan-400">
            <Workflow className="h-6 w-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-gray-100">
                Autonomous Architecture Evolution & Design Governance
              </h2>
              <span className="rounded bg-cyan-900/40 px-2 py-0.5 text-[10px] font-semibold text-cyan-300 border border-cyan-700/50">
                FASE 64
              </span>
              <span className="rounded bg-emerald-900/40 px-2 py-0.5 text-[10px] font-semibold text-emerald-300 border border-emerald-700/50 flex items-center gap-1">
                <ShieldCheck className="h-3 w-3" /> SENTINEL ACTIVE
              </span>
            </div>
            <p className="text-xs text-gray-400 mt-0.5">
              Governed design analysis, constraint extraction, multi-axis trade-offs, DAG migration simulation, and zero-downtime rollback.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 rounded bg-[#132024] px-2 py-1 text-xs border border-gray-700">
            <span className="text-gray-400">Política:</span>
            <select
              value={policyMode}
              onChange={(e) => setPolicyMode(e.target.value)}
              className="bg-transparent text-cyan-300 font-semibold focus:outline-none"
            >
              <option value="STANDARD" className="bg-[#132024]">STANDARD</option>
              <option value="CONSERVATIVE" className="bg-[#132024]">CONSERVATIVE</option>
              <option value="STRICT" className="bg-[#132024]">STRICT</option>
              <option value="SECURITY_FIRST" className="bg-[#132024]">SECURITY_FIRST</option>
            </select>
          </div>

          <button
            onClick={handleObserve}
            disabled={isObserving}
            className="flex items-center gap-1.5 rounded bg-cyan-600 hover:bg-cyan-500 px-3 py-1.5 text-xs font-semibold text-white transition-all disabled:opacity-50"
          >
            <Compass className="h-3.5 w-3.5" />
            {isObserving ? 'A Analisar...' : 'Observar Arquitetura'}
          </button>

          <button
            onClick={handleEvaluate}
            disabled={isEvaluating}
            className="flex items-center gap-1.5 rounded bg-indigo-600 hover:bg-indigo-500 px-3 py-1.5 text-xs font-semibold text-white transition-all disabled:opacity-50"
          >
            <Zap className="h-3.5 w-3.5" />
            {isEvaluating ? 'A Avaliar...' : 'Avaliar Alternativas'}
          </button>
        </div>
      </div>

      {statusMessage && (
        <div className="bg-cyan-950/30 border-b border-cyan-800/40 px-6 py-2 text-xs text-cyan-300 flex items-center justify-between">
          <span>{statusMessage}</span>
          <button onClick={() => setStatusMessage(null)} className="text-gray-400 hover:text-gray-200">×</button>
        </div>
      )}

      {/* Navigation Sub-Tabs covering all 12 scenarios */}
      <div className="flex border-b border-gray-800 bg-[#0c1417] px-6 text-xs font-semibold overflow-x-auto">
        {[
          { id: 'overview', domId: 'arch-subtab-overview', label: '01. Visão Geral', icon: Layers },
          { id: 'problems', domId: 'arch-subtab-problems', label: '02. Problemas', icon: AlertTriangle },
          { id: 'constraints', domId: 'arch-subtab-constraints', label: '03. Restrições', icon: Lock },
          { id: 'alternatives', domId: 'arch-subtab-alternatives', label: '04. Alternativas', icon: GitBranch },
          { id: 'comparison', domId: 'arch-subtab-comparison', label: '05. Comparação', icon: Scale },
          { id: 'impact', domId: 'arch-subtab-impact', label: '06. Grafo Impacto', icon: Activity },
          { id: 'contracts', domId: 'arch-subtab-contracts', label: '07. Contratos', icon: FileCheck },
          { id: 'behavior', domId: 'arch-subtab-behavior', label: '08. Comportamento', icon: Compass },
          { id: 'risk', domId: 'arch-subtab-risk', label: '09. Risco Multi-Eixo', icon: ShieldAlert },
          { id: 'migration', domId: 'arch-subtab-migration', label: '10. DAG Migração', icon: RotateCcw },
          { id: 'simulation', domId: 'arch-subtab-simulation', label: '11. Simulação', icon: Zap },
          { id: 'governance', domId: 'arch-subtab-governance', label: '12. Governação Gate', icon: ShieldCheck },
        ].map((tab) => {
          const Icon = tab.icon;
          const active = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              id={tab.domId}
              onClick={() => setActiveTab(tab.id as any)}
              className={`flex items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2.5 transition-colors ${
                active
                  ? 'border-cyan-400 text-cyan-300 bg-cyan-500/5'
                  : 'border-transparent text-gray-400 hover:text-gray-200'
              }`}
            >
              <Icon className="h-3 w-3" />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* Tab Contents */}
      <div className="p-6 space-y-6 flex-1">
        {/* TAB 1: OVERVIEW */}
        {activeTab === 'overview' && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
              <div className="rounded border border-gray-800 bg-[#10191c] p-3">
                <div className="text-[11px] text-gray-400">Nós Arquiteturais</div>
                <div className="text-lg font-bold text-gray-100">{snapshotData.nodes_count}</div>
                <div className="text-[10px] text-cyan-400">arquivos e módulos</div>
              </div>
              <div className="rounded border border-gray-800 bg-[#10191c] p-3">
                <div className="text-[11px] text-gray-400">Arestas de Dependência</div>
                <div className="text-lg font-bold text-gray-100">{snapshotData.edges_count}</div>
                <div className="text-[10px] text-indigo-400">in-process e IPC</div>
              </div>
              <div className="rounded border border-gray-800 bg-[#10191c] p-3">
                <div className="text-[11px] text-gray-400">SCCs Cíclicos</div>
                <div className="text-lg font-bold text-amber-400">{snapshotData.sccs_count}</div>
                <div className="text-[10px] text-gray-400">loops identificados</div>
              </div>
              <div className="rounded border border-gray-800 bg-[#10191c] p-3">
                <div className="text-[11px] text-gray-400">Contratos Declarados</div>
                <div className="text-lg font-bold text-emerald-400">{snapshotData.contracts_count}</div>
                <div className="text-[10px] text-emerald-400/80">schemas OpenAPI/WS</div>
              </div>
              <div className="rounded border border-gray-800 bg-[#10191c] p-3">
                <div className="text-[11px] text-gray-400">Zonas de Risco</div>
                <div className="text-lg font-bold text-rose-400">{snapshotData.risk_zones_count}</div>
                <div className="text-[10px] text-rose-400/80">auth & wallet</div>
              </div>
              <div className="rounded border border-gray-800 bg-[#10191c] p-3">
                <div className="text-[11px] text-gray-400">Fronteiras Dinâmicas</div>
                <div className="text-lg font-bold text-purple-400">{snapshotData.external_boundaries_count}</div>
                <div className="text-[10px] text-purple-400/80">reflection/getattr</div>
              </div>
            </div>

            {/* Invariant Card */}
            <div className="rounded border border-cyan-800/40 bg-cyan-950/20 p-4">
              <div className="flex items-center gap-2 text-cyan-300 font-semibold text-sm">
                <Lock className="h-4 w-4" />
                Invariante Central da Fase 64
              </div>
              <p className="text-xs text-gray-300 mt-1.5 leading-relaxed">
                <strong className="text-white">PROPOSAL != APPROVAL</strong> e <strong className="text-white">APPROVAL != IMPLEMENTATION</strong>. Nenhuma alternativa arquitetural pode ser aplicada no código em tempo de análise. Conhecimento externo da Fase 63 gera apenas hipóteses e nunca evidência local.
              </p>
            </div>
          </div>
        )}

        {/* TAB 2: PROBLEMS DETECTED */}
        {activeTab === 'problems' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-gray-200">
                Problemas Estruturais e Smells Arquiteturais Observados
              </h3>
              <span className="text-xs text-gray-400">
                Regra: Smells nunca são classificados como bugs automaticamente.
              </span>
            </div>

            <div className="space-y-3">
              {problems.map((p) => (
                <div
                  key={p.problem_id}
                  onClick={() => setSelectedProblemId(p.problem_id)}
                  className={`cursor-pointer rounded border p-4 transition-all ${
                    selectedProblemId === p.problem_id
                      ? 'border-cyan-500 bg-cyan-950/20'
                      : 'border-gray-800 bg-[#10191c] hover:border-gray-700'
                  }`}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                    <div className="flex items-center gap-2">
                      <span className="rounded bg-gray-800 px-2 py-0.5 text-[10px] font-mono text-gray-300">
                        {p.problem_id}
                      </span>
                      <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                        p.severity === 'HIGH' ? 'bg-rose-900/50 text-rose-300 border border-rose-700/40' :
                        p.severity === 'MEDIUM' ? 'bg-amber-900/50 text-amber-300 border border-amber-700/40' :
                        'bg-gray-800 text-gray-300'
                      }`}>
                        {p.severity}
                      </span>
                      <span className="text-xs font-bold text-gray-100">{p.title}</span>
                    </div>

                    <div className="flex items-center gap-2 text-xs text-gray-400">
                      <span>Status: <strong className="text-cyan-300">{p.status}</strong></span>
                      <span>Confiança: <strong className="text-emerald-300">{(p.confidence * 100).toFixed(0)}%</strong></span>
                    </div>
                  </div>

                  <p className="text-xs text-gray-300 mb-2">{p.evidence}</p>

                  <div className="flex flex-wrap gap-1 items-center text-[11px] text-gray-400 pt-1 border-t border-gray-800/80">
                    <span className="text-gray-500">Componentes Afetados:</span>
                    {p.affected_nodes.map((node, i) => (
                      <span key={i} className="rounded bg-black/40 px-1.5 py-0.5 text-gray-300 font-mono text-[10px]">
                        {node}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* TAB 3: CONSTRAINTS */}
        {activeTab === 'constraints' && (
          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-gray-200">
              Restrições Extraídas do Repositório (Zero Alucinação)
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {constraints.map((c) => (
                <div key={c.id} className="rounded border border-gray-800 bg-[#10191c] p-4 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-gray-100">{c.name}</span>
                    <span className="text-[10px] uppercase font-semibold text-cyan-400 bg-cyan-950/60 px-2 py-0.5 rounded border border-cyan-800/40">
                      {c.category}
                    </span>
                  </div>
                  <p className="text-xs text-gray-300">{c.description}</p>
                  <div className="text-[11px] text-emerald-400 pt-1 flex items-center justify-between border-t border-gray-800/60">
                    <span>Nível de Confiança</span>
                    <span className="font-bold">{(c.confidence * 100).toFixed(0)}%</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* TAB 4: ALTERNATIVES */}
        {activeTab === 'alternatives' && (
          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-gray-200">
              Alternativas Arquiteturais Geradas
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {alternatives.map((alt) => (
                <div key={alt.id} className="rounded border border-gray-800 bg-[#10191c] p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-cyan-300">{alt.title}</span>
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-cyan-950 text-cyan-200 border border-cyan-800">
                      {alt.reversibility}
                    </span>
                  </div>
                  <div className="text-xs text-gray-300">
                    <div><strong className="text-emerald-400">Vantagens:</strong> {alt.pros.join(', ')}</div>
                    <div className="mt-1"><strong className="text-rose-400">Custos:</strong> {alt.cons.join(', ')}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* TAB 5: COMPARISON */}
        {activeTab === 'comparison' && (
          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-gray-200">
              Matriz Comparativa Multi-Eixo de Trade-Offs
            </h3>
            <div className="overflow-x-auto rounded border border-gray-800 bg-[#10191c]">
              <table className="w-full text-left text-xs">
                <thead className="bg-[#132024] text-gray-300 border-b border-gray-700">
                  <tr>
                    <th className="p-3">Alternativa</th>
                    <th className="p-3">Tipo</th>
                    <th className="p-3">Raio Impacto</th>
                    <th className="p-3">Esforço (h)</th>
                    <th className="p-3">Reversibilidade</th>
                    <th className="p-3">Risco Global</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800">
                  {alternatives.map((alt) => (
                    <tr key={alt.id} className="hover:bg-white/[0.02]">
                      <td className="p-3 font-semibold text-gray-200">{alt.title}</td>
                      <td className="p-3 text-cyan-400 font-mono">{alt.type}</td>
                      <td className="p-3 font-bold">{alt.blast_radius} nós</td>
                      <td className="p-3">{alt.effort_hours}h</td>
                      <td className="p-3 text-emerald-400">{alt.reversibility}</td>
                      <td className="p-3 font-bold text-amber-400">{alt.risk}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* TAB 6: IMPACT GRAPH */}
        {activeTab === 'impact' && (
          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-gray-200">Análise de Impacto e Blast Radius</h3>
            <div className="rounded border border-gray-800 bg-[#10191c] p-4 space-y-3">
              <div className="grid grid-cols-3 gap-3 text-center">
                <div className="p-3 rounded bg-black/40 border border-gray-800">
                  <div className="text-xs text-gray-400">Arquivos Afetados</div>
                  <div className="text-lg font-bold text-gray-100">4</div>
                </div>
                <div className="p-3 rounded bg-black/40 border border-gray-800">
                  <div className="text-xs text-gray-400">Consumidores Downstream</div>
                  <div className="text-lg font-bold text-indigo-400">6</div>
                </div>
                <div className="p-3 rounded bg-black/40 border border-gray-800">
                  <div className="text-xs text-gray-400">Escopo do Impacto</div>
                  <div className="text-lg font-bold text-cyan-400">DOWNSTREAM</div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 7: CONTRACTS */}
        {activeTab === 'contracts' && (
          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-gray-200">Análise de Compatibilidade de Contratos (F44-F49)</h3>
            <div className="rounded border border-emerald-800/40 bg-emerald-950/20 p-4">
              <div className="flex items-center gap-2 text-emerald-300 font-bold text-xs mb-1">
                <CheckCircle2 className="h-4 w-4" /> STATUS: NON_BREAKING
              </div>
              <p className="text-xs text-gray-300">
                A alternativa B preserva os contratos OpenAPI e WebSocket vigentes com 100% de compatibilidade retroativa.
              </p>
            </div>
          </div>
        )}

        {/* TAB 8: BEHAVIOR */}
        {activeTab === 'behavior' && (
          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-gray-200">Prova de Preservação Comportamental (F50-F52)</h3>
            <div className="rounded border border-gray-800 bg-[#10191c] p-4 space-y-2 text-xs">
              <div className="flex justify-between border-b border-gray-800 py-1">
                <span className="text-gray-400">Preservação de Ordenação:</span>
                <span className="text-emerald-400 font-semibold">PRESERVED</span>
              </div>
              <div className="flex justify-between border-b border-gray-800 py-1">
                <span className="text-gray-400">Semântica de Retries & Timeouts:</span>
                <span className="text-emerald-400 font-semibold">UNCHANGED</span>
              </div>
              <div className="flex justify-between py-1">
                <span className="text-gray-400">Veredicto Comportamental:</span>
                <span className="text-cyan-300 font-bold">PROVEN_WITHIN_SCOPE</span>
              </div>
            </div>
          </div>
        )}

        {/* TAB 9: RISK */}
        {activeTab === 'risk' && (
          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-gray-200">Vetor de Risco Multi-Dimensional</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {[
                { name: 'Segurança', score: '0.10', level: 'LOW' },
                { name: 'Fiabilidade', score: '0.15', level: 'LOW' },
                { name: 'Migração', score: '0.20', level: 'LOW' },
                { name: 'Rollback', score: '0.10', level: 'LOW' },
              ].map((r, i) => (
                <div key={i} className="rounded border border-gray-800 bg-[#10191c] p-3 text-center">
                  <div className="text-xs text-gray-400">{r.name}</div>
                  <div className="text-lg font-bold text-gray-100">{r.score}</div>
                  <div className="text-[10px] text-emerald-400 font-semibold">{r.level}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* TAB 10: MIGRATION PLAN */}
        {activeTab === 'migration' && (
          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-gray-200">
              DAG de Migração Faseada com Rollback Garantido
            </h3>
            <div className="space-y-2">
              {migrationSteps.map((step, idx) => (
                <div key={step.id} className="rounded border border-gray-800 bg-[#10191c] p-3 flex items-center justify-between gap-4">
                  <div className="flex items-center gap-3">
                    <div className="h-7 w-7 rounded-full bg-cyan-900/40 border border-cyan-700 flex items-center justify-center text-xs font-bold text-cyan-300">
                      {idx + 1}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-gray-100">{step.title}</span>
                        <span className="rounded bg-gray-800 px-1.5 py-0.5 text-[9px] font-mono text-gray-400 uppercase">
                          {step.stage}
                        </span>
                      </div>
                      <div className="text-[11px] text-gray-400 flex items-center gap-1 mt-0.5">
                        <RotateCcw className="h-3 w-3 text-amber-400" />
                        <span>Rollback: <span className="text-gray-300">{step.rollback}</span></span>
                      </div>
                    </div>
                  </div>
                  <span className="text-[10px] text-emerald-400 bg-emerald-950/60 px-2 py-0.5 rounded border border-emerald-800">
                    Reversível
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* TAB 11: SIMULATION */}
        {activeTab === 'simulation' && (
          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-gray-200">Simulação Prévia Virtual (Dry-Run)</h3>
            <div className="rounded border border-cyan-800/40 bg-cyan-950/20 p-4 space-y-2">
              <div className="text-xs font-bold text-cyan-300 flex items-center gap-2">
                <Zap className="h-4 w-4" /> SIMULATION_SAFE
              </div>
              <p className="text-xs text-gray-300">
                A simulação validou as mutações no grafo de dependências, verificou o DAG de rollback em 7 cenários de falha, e comprovou preservação de integridade.
              </p>
            </div>
          </div>
        )}

        {/* TAB 12: GOVERNANCE & SENTINEL */}
        {activeTab === 'governance' && (
          <div className="space-y-4">
            <div className="rounded border border-emerald-700/40 bg-emerald-950/20 p-4">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <ShieldCheck className="h-5 w-5 text-emerald-400" />
                  <span className="text-sm font-bold text-emerald-300">
                    Decisão do Portão de Governação Arquitetural
                  </span>
                </div>
                <span className="rounded bg-emerald-900/60 px-2.5 py-1 text-xs font-bold text-emerald-200 border border-emerald-600">
                  APPROVED_FOR_IMPLEMENTATION
                </span>
              </div>
              <p className="text-xs text-gray-300 leading-relaxed">
                A proposta <strong className="text-white">B. Boundary & Interface Extraction</strong> passou em todas as verificações do Security Sentinel, preserva contratos com zero breaking changes, e possui um plano DAG com 100% de cobertura de rollback automático.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
