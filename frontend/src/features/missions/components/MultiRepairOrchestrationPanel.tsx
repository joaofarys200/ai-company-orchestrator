import React, { useState } from 'react';
import {
  GitMerge,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  RotateCcw,
  Layers,
  Lock,
  Search,
  Activity,
  ArrowRight,
  RefreshCw,
  Check,
  XCircle,
  Zap,
} from 'lucide-react';

export const MultiRepairOrchestrationPanel: React.FC = () => {
  const [activeSubTab, setActiveSubTab] = useState<
    'failure_clusters' | 'repair_dag' | 'transaction_lifecycle' | 'checkpoints_rollback' | 'convergence_monitor' | 'proof_ledger'
  >('failure_clusters');

  const [transactionState, setTransactionState] = useState<'PROVEN' | 'ROLLED_BACK_PARTIAL' | 'ROLLED_BACK_GLOBAL' | 'DIVERGING' | 'SECURITY_BLOCKED'>('PROVEN');
  const [selectedClusterId, setSelectedClusterId] = useState<string>('cluster_dina_startup_crash');
  const [simulatedRevealed, setSimulatedRevealed] = useState<boolean>(true);

  // Clusters data
  const clusters = [
    {
      id: 'cluster_dina_startup_crash',
      rootCause: 'UNBOUND_EXPRESS_SCOPE_AND_ROUTES',
      riskScore: 0.35,
      sharedFiles: ['app.js', 'package.json'],
      sharedSymbols: ['express', 'app', 'PORT'],
      sharedContracts: ['HTTP_ROOT_V1', 'DDOS_POST_V1'],
      failuresCount: 3,
      failures: [
        {
          id: 'fail_01_ref_app',
          errorClass: 'ReferenceError',
          symbol: 'app',
          file: 'app.js:79',
          message: 'app is not defined at app.post(/ddos)',
          type: 'ORIGINAL_FAILURE',
        },
        {
          id: 'fail_02_pkg_express',
          errorClass: 'ModuleNotFoundError',
          symbol: 'express',
          file: 'package.json:14',
          message: "Cannot find module 'express'",
          type: 'ORIGINAL_FAILURE',
        },
        {
          id: 'fail_03_auth_secret',
          errorClass: 'ReferenceError',
          symbol: 'authToken',
          file: 'app.js:105',
          message: 'authToken is not defined in secondary route /ddos/status',
          type: 'REVEALED_FAILURE',
        },
      ],
    },
    {
      id: 'cluster_frontend_consumer_sync',
      rootCause: 'CLIENT_PAYLOAD_SHAPE_MISMATCH',
      riskScore: 0.25,
      sharedFiles: ['frontend/src/api.ts', 'frontend/src/types.ts'],
      sharedSymbols: ['DdosPayload', 'postTelemetry'],
      sharedContracts: ['DDOS_POST_V1'],
      failuresCount: 1,
      failures: [
        {
          id: 'fail_04_fe_type',
          errorClass: 'TypeError',
          symbol: 'DdosPayload',
          file: 'frontend/src/types.ts:44',
          message: 'Property timestamp is missing in payload type definition',
          type: 'ORIGINAL_FAILURE',
        },
      ],
    },
  ];

  // DAG nodes & edges
  const dagNodes = [
    { id: 'rep_01_pkg', label: '1. Add express to package.json', type: 'PRODUCER_REPAIR', status: 'VERIFIED', wave: 1 },
    { id: 'rep_02_backend', label: '2. Instantiate express in app.js', type: 'PRODUCER_REPAIR', status: 'VERIFIED', wave: 2 },
    { id: 'rep_03_auth_secret', label: '3. Define authToken in app.js:105', type: 'REVEALED_REPAIR', status: 'VERIFIED', wave: 3 },
    { id: 'rep_04_frontend', label: '4. Update DdosPayload in types.ts', type: 'CONSUMER_REPAIR', status: 'VERIFIED', wave: 4 },
  ];

  const checkpoints = [
    {
      id: 'chk_tx_55_0_rep_01_pkg',
      stepIndex: 0,
      repairId: 'rep_01_pkg',
      file: 'package.json',
      stateHash: 'sha256:7f83b1657ff1...a9',
      treeHash: 'sha256:b5120194bc...12',
      verification: 'PASSED (Syntax & JSON format valid)',
      status: 'IMMUTABLE_PRESERVED',
    },
    {
      id: 'chk_tx_55_1_rep_02_backend',
      stepIndex: 1,
      repairId: 'rep_02_backend',
      file: 'app.js',
      stateHash: 'sha256:4a88f01b92cd...44',
      treeHash: 'sha256:b5120194bc...12',
      verification: 'PASSED (AST parsed & preflight startup OK)',
      status: 'IMMUTABLE_PRESERVED',
    },
    {
      id: 'chk_tx_55_2_rep_03_auth_secret',
      stepIndex: 2,
      repairId: 'rep_03_auth_secret',
      file: 'app.js',
      stateHash: 'sha256:9c12df882310...88',
      treeHash: 'sha256:b5120194bc...12',
      verification: 'PASSED (Targeted route test passed)',
      status: 'IMMUTABLE_PRESERVED',
    },
    {
      id: 'chk_tx_55_3_rep_04_frontend',
      stepIndex: 3,
      repairId: 'rep_04_frontend',
      file: 'frontend/src/types.ts',
      stateHash: 'sha256:3e459011baec...f0',
      treeHash: 'sha256:b5120194bc...12',
      verification: 'PASSED (Vite build & Browser smoke OK)',
      status: 'IMMUTABLE_PRESERVED',
    },
  ];

  const currentCluster = clusters.find((c) => c.id === selectedClusterId) || clusters[0];

  return (
    <div id="multi-repair-orchestration-panel" className="flex flex-col h-full bg-[#0a0f1d] text-slate-200 p-6 overflow-y-auto">
      {/* Header with Decision Gate */}
      <div className="flex flex-wrap items-center justify-between pb-6 border-b border-slate-800/80 gap-4">
        <div>
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-cyan-500/10 border border-cyan-500/30 rounded-xl text-cyan-400">
              <GitMerge className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2.5">
                <h1 className="text-xl font-bold tracking-tight text-white">
                  Transactional Multi-Repair Orchestration & Convergence
                </h1>
                <span className="px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wider rounded-full bg-cyan-500/20 text-cyan-300 border border-cyan-500/40">
                  Fase 55
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-1">
                Decision Gate: <span className="font-mono text-cyan-300 font-semibold">MULTI_REPAIR_TRANSACTION_READY</span> • Coordinated atomic multi-step repair with cryptographic rollback lineage.
              </p>
            </div>
          </div>
        </div>

        {/* Badges */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-1.5 px-3 py-1 bg-emerald-500/10 border border-emerald-500/30 rounded-lg text-xs font-mono text-emerald-400">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>TRANSACTION: {transactionState}</span>
          </div>
          <div className="flex items-center gap-1.5 px-3 py-1 bg-blue-500/10 border border-blue-500/30 rounded-lg text-xs font-mono text-blue-400">
            <Layers className="w-3.5 h-3.5" />
            <span>CONVERGENCE: {transactionState === 'DIVERGING' ? 'DIVERGING' : 'CONVERGED'}</span>
          </div>
          <div className="flex items-center gap-1.5 px-3 py-1 bg-purple-500/10 border border-purple-500/30 rounded-lg text-xs font-mono text-purple-400">
            <RotateCcw className="w-3.5 h-3.5" />
            <span>ATOMIC_ROLLBACK: READY</span>
          </div>
          <div className="flex items-center gap-1.5 px-3 py-1 bg-amber-500/10 border border-amber-500/30 rounded-lg text-xs font-mono text-amber-400">
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>SENTINEL: {transactionState === 'SECURITY_BLOCKED' ? 'VETO_ENFORCED' : 'APPROVED'}</span>
          </div>
        </div>
      </div>

      {/* Interactive Sub-tab Navigation */}
      <div className="flex items-center gap-2 mt-6 border-b border-slate-800 pb-3">
        <button
          id="btn-tab-failure-clusters"
          onClick={() => setActiveSubTab('failure_clusters')}
          className={`flex items-center gap-2 px-3.5 py-1.5 text-xs font-medium rounded-lg transition-all ${
            activeSubTab === 'failure_clusters'
              ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
          }`}
        >
          <Search className="w-4 h-4" />
          Failure Clusters
        </button>

        <button
          id="btn-tab-repair-dag"
          onClick={() => setActiveSubTab('repair_dag')}
          className={`flex items-center gap-2 px-3.5 py-1.5 text-xs font-medium rounded-lg transition-all ${
            activeSubTab === 'repair_dag'
              ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
          }`}
        >
          <GitMerge className="w-4 h-4" />
          Repair DAG & Ordering
        </button>

        <button
          id="btn-tab-transaction-lifecycle"
          onClick={() => setActiveSubTab('transaction_lifecycle')}
          className={`flex items-center gap-2 px-3.5 py-1.5 text-xs font-medium rounded-lg transition-all ${
            activeSubTab === 'transaction_lifecycle'
              ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
          }`}
        >
          <Activity className="w-4 h-4" />
          Transaction Lifecycle
        </button>

        <button
          id="btn-tab-checkpoints-rollback"
          onClick={() => setActiveSubTab('checkpoints_rollback')}
          className={`flex items-center gap-2 px-3.5 py-1.5 text-xs font-medium rounded-lg transition-all ${
            activeSubTab === 'checkpoints_rollback'
              ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
          }`}
        >
          <RotateCcw className="w-4 h-4" />
          Checkpoints & Rollback
        </button>

        <button
          id="btn-tab-convergence-monitor"
          onClick={() => setActiveSubTab('convergence_monitor')}
          className={`flex items-center gap-2 px-3.5 py-1.5 text-xs font-medium rounded-lg transition-all ${
            activeSubTab === 'convergence_monitor'
              ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
          }`}
        >
          <Layers className="w-4 h-4" />
          Convergence & Revealed Failures
        </button>

        <button
          id="btn-tab-proof-ledger"
          onClick={() => setActiveSubTab('proof_ledger')}
          className={`flex items-center gap-2 px-3.5 py-1.5 text-xs font-medium rounded-lg transition-all ${
            activeSubTab === 'proof_ledger'
              ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
          }`}
        >
          <ShieldCheck className="w-4 h-4" />
          Cryptographic Proof Ledger
        </button>
      </div>

      {/* Main Content Areas */}
      <div className="mt-6 flex-1">
        {/* SUBTAB 1: Failure Clusters */}
        {activeSubTab === 'failure_clusters' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-1 bg-slate-900/60 border border-slate-800/80 rounded-xl p-5">
              <h3 className="text-sm font-semibold text-white mb-3 flex items-center justify-between">
                <span>Identified Failure Clusters</span>
                <span className="text-xs bg-slate-800 px-2 py-0.5 rounded text-cyan-300 font-mono">
                  {clusters.length} Active
                </span>
              </h3>
              <div className="space-y-3">
                {clusters.map((c) => (
                  <div
                    key={c.id}
                    onClick={() => setSelectedClusterId(c.id)}
                    className={`p-4 rounded-lg border cursor-pointer transition-all ${
                      selectedClusterId === c.id
                        ? 'bg-cyan-950/30 border-cyan-500/50 text-white shadow-md'
                        : 'bg-slate-800/40 border-slate-700/50 text-slate-300 hover:bg-slate-800/80'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs font-bold text-cyan-400">{c.id}</span>
                      <span className="text-xs font-mono px-2 py-0.5 rounded bg-slate-800 text-amber-400">
                        Risk: {c.riskScore}
                      </span>
                    </div>
                    <div className="text-xs text-slate-300 mt-2 font-medium">{c.rootCause}</div>
                    <div className="text-[11px] text-slate-400 mt-2 flex items-center gap-3">
                      <span>{c.failuresCount} Failures</span>
                      <span>•</span>
                      <span>{c.sharedFiles.length} Shared Files</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="lg:col-span-2 bg-slate-900/60 border border-slate-800/80 rounded-xl p-5">
              <h3 className="text-sm font-semibold text-white mb-3">Cluster Multi-Dimensional Details</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                <div className="p-3 bg-slate-800/40 border border-slate-700/50 rounded-lg">
                  <div className="text-[11px] text-slate-400">Root Cause Category</div>
                  <div className="text-xs font-bold text-cyan-300 mt-1 font-mono">{currentCluster.rootCause}</div>
                </div>
                <div className="p-3 bg-slate-800/40 border border-slate-700/50 rounded-lg">
                  <div className="text-[11px] text-slate-400">Risk Score</div>
                  <div className="text-xs font-bold text-amber-400 mt-1 font-mono">{currentCluster.riskScore}</div>
                </div>
                <div className="p-3 bg-slate-800/40 border border-slate-700/50 rounded-lg">
                  <div className="text-[11px] text-slate-400">Shared Symbols</div>
                  <div className="text-xs font-bold text-slate-200 mt-1 font-mono">{currentCluster.sharedSymbols.join(', ')}</div>
                </div>
                <div className="p-3 bg-slate-800/40 border border-slate-700/50 rounded-lg">
                  <div className="text-[11px] text-slate-400">Affected Contracts</div>
                  <div className="text-xs font-bold text-indigo-300 mt-1 font-mono">{currentCluster.sharedContracts.join(', ')}</div>
                </div>
              </div>

              <h4 className="text-xs font-semibold text-slate-300 mb-2">Clustered Failure Items (Structural & Causal):</h4>
              <div className="space-y-2.5">
                {currentCluster.failures.map((f) => (
                  <div key={f.id} className="p-3.5 bg-slate-800/30 border border-slate-700/40 rounded-lg flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs font-bold text-red-400">{f.errorClass}</span>
                        <span className="text-xs text-slate-400 font-mono">[{f.file}]</span>
                        <span className={`px-2 py-0.5 text-[10px] rounded font-semibold ${
                          f.type === 'REVEALED_FAILURE' ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30' : 'bg-red-500/20 text-red-300 border border-red-500/30'
                        }`}>
                          {f.type}
                        </span>
                      </div>
                      <div className="text-xs text-slate-300 mt-1">{f.message}</div>
                    </div>
                    <span className="text-[11px] font-mono text-cyan-400 bg-cyan-950/40 px-2 py-1 rounded">
                      Symbol: {f.symbol}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* SUBTAB 2: Repair DAG & Ordering */}
        {activeSubTab === 'repair_dag' && (
          <div className="bg-slate-900/60 border border-slate-800/80 rounded-xl p-5">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-sm font-semibold text-white">Topological Repair Execution DAG</h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Kahn topological sort enforcing strict producer-before-consumer execution with deterministic tie-breaking.
                </p>
              </div>
              <span className="text-xs px-3 py-1 bg-cyan-500/10 text-cyan-300 border border-cyan-500/30 rounded font-mono">
                CYCLE_CHECK: PASS (0 cycles)
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mt-6">
              {dagNodes.map((node, i) => (
                <div key={node.id} className="relative p-4 bg-slate-800/50 border border-slate-700/60 rounded-xl flex flex-col justify-between">
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-950 text-cyan-400 border border-cyan-800">
                        Wave {node.wave}
                      </span>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800">
                        {node.status}
                      </span>
                    </div>
                    <div className="text-xs font-semibold text-white mt-1">{node.label}</div>
                    <div className="text-[11px] font-mono text-slate-400 mt-2">Type: {node.type}</div>
                  </div>
                  {i < dagNodes.length - 1 && (
                    <div className="hidden md:flex absolute -right-3 top-1/2 -translate-y-1/2 z-10 p-1 bg-cyan-500 text-slate-950 rounded-full shadow-lg">
                      <ArrowRight className="w-3.5 h-3.5" />
                    </div>
                  )}
                </div>
              ))}
            </div>

            <div className="mt-8 p-4 bg-slate-800/30 border border-slate-700/40 rounded-lg">
              <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-2">Architectural Invariant Enforcement:</h4>
              <ul className="text-xs text-slate-400 space-y-1.5 list-disc list-inside">
                <li><strong className="text-slate-200">Producer Before Consumer:</strong> Backend package dependencies & Express server instance (Waves 1-2) must be verified healthy prior to compiling frontend consumers (Wave 4).</li>
                <li><strong className="text-slate-200">Revealed Failure Absorption:</strong> Secondary unmasked failure (<code className="text-amber-300">authToken</code>) is dynamically inserted into Wave 3 without requiring full mission replan.</li>
                <li><strong className="text-slate-200">Zero Regressions:</strong> Invariant checker halts execution immediately if any step breaks an existing test or route.</li>
              </ul>
            </div>
          </div>
        )}

        {/* SUBTAB 3: Transaction Lifecycle */}
        {activeSubTab === 'transaction_lifecycle' && (
          <div className="bg-slate-900/60 border border-slate-800/80 rounded-xl p-5">
            <h3 className="text-sm font-semibold text-white mb-2">Transaction State Machine & Audit History</h3>
            <p className="text-xs text-slate-400 mb-6">
              Full lifecycle tracking with strict cryptographic barriers: <code className="text-cyan-300">PLANNED → GATED → EXECUTING → CHECKPOINTED → COMMITTED → PROVEN</code>
            </p>

            <div className="relative border-l border-slate-700 ml-4 space-y-6">
              <div className="relative pl-6">
                <div className="absolute -left-2.5 top-1 w-5 h-5 rounded-full bg-cyan-500 flex items-center justify-center text-slate-950">
                  <Check className="w-3 h-3" />
                </div>
                <div className="font-mono text-xs font-bold text-cyan-400">1. PLANNED</div>
                <div className="text-xs text-slate-300 mt-1">Multi-repair candidates synthesized and clustered. 0 overlapping patch conflicts detected.</div>
                <div className="text-[11px] font-mono text-slate-500 mt-0.5">hash: sha256:d8a94b...</div>
              </div>

              <div className="relative pl-6">
                <div className="absolute -left-2.5 top-1 w-5 h-5 rounded-full bg-cyan-500 flex items-center justify-center text-slate-950">
                  <Check className="w-3 h-3" />
                </div>
                <div className="font-mono text-xs font-bold text-cyan-400">2. GATED (Mission Control & Security Sentinel)</div>
                <div className="text-xs text-slate-300 mt-1">Blast radius: 4 entities. Risk: 0.35. Sovereign Security Sentinel validation: APPROVED.</div>
                <div className="text-[11px] font-mono text-slate-500 mt-0.5">gate_id: GATE_MULTI_REPAIR_55</div>
              </div>

              <div className="relative pl-6">
                <div className="absolute -left-2.5 top-1 w-5 h-5 rounded-full bg-cyan-500 flex items-center justify-center text-slate-950">
                  <Check className="w-3 h-3" />
                </div>
                <div className="font-mono text-xs font-bold text-cyan-400">3. EXECUTING (Incremental Steps)</div>
                <div className="text-xs text-slate-300 mt-1">4 sequential waves executed. Incremental preflight and AST verification passed after each patch.</div>
                <div className="text-[11px] font-mono text-slate-500 mt-0.5">checkpoints: 4 snapshots captured</div>
              </div>

              <div className="relative pl-6">
                <div className="absolute -left-2.5 top-1 w-5 h-5 rounded-full bg-cyan-500 flex items-center justify-center text-slate-950">
                  <Check className="w-3 h-3" />
                </div>
                <div className="font-mono text-xs font-bold text-cyan-400">4. COMMITTED & PROVEN</div>
                <div className="text-xs text-slate-300 mt-1">Full preflight, build, and browser smoke test validated. Cryptographic proof issued.</div>
                <div className="text-[11px] font-mono text-emerald-400 mt-0.5">outcome: TRANSACTION_PROVEN (Status: {transactionState})</div>
              </div>
            </div>
          </div>
        )}

        {/* SUBTAB 4: Checkpoints & Rollback */}
        {activeSubTab === 'checkpoints_rollback' && (
          <div className="bg-slate-900/60 border border-slate-800/80 rounded-xl p-5">
            <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
              <div>
                <h3 className="text-sm font-semibold text-white">Immutable Rollback Checkpoints</h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Granular before/after snapshots preserved across all repair steps. Checkpoints are never deleted.
                </p>
              </div>

              {/* Interactive Rollback Triggers */}
              <div className="flex items-center gap-2">
                <button
                  id="btn-trigger-partial-rollback"
                  onClick={() => setTransactionState('ROLLED_BACK_PARTIAL')}
                  className="px-3 py-1.5 bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/40 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  Rollback to Step 1 (Partial)
                </button>
                <button
                  id="btn-trigger-global-rollback"
                  onClick={() => setTransactionState('ROLLED_BACK_GLOBAL')}
                  className="px-3 py-1.5 bg-red-500/20 hover:bg-red-500/30 text-red-300 border border-red-500/40 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  Global Rollback (All)
                </button>
                <button
                  id="btn-reset-transaction"
                  onClick={() => setTransactionState('PROVEN')}
                  className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  Reset
                </button>
              </div>
            </div>

            {transactionState === 'ROLLED_BACK_PARTIAL' && (
              <div className="mb-4 p-3 bg-amber-950/40 border border-amber-500/50 rounded-lg text-xs text-amber-200 flex items-center justify-between">
                <span><strong>Partial Rollback Executed:</strong> State successfully rolled back to Checkpoint 1 (chk_tx_55_1). Repairs in package.json & app.js:29 preserved; subsequent patches reverted. Cryptographic hash equivalence verified.</span>
                <span className="font-mono text-[10px] bg-amber-900/60 px-2 py-0.5 rounded">RESTORED_HASH_MATCH: 100%</span>
              </div>
            )}

            {transactionState === 'ROLLED_BACK_GLOBAL' && (
              <div className="mb-4 p-3 bg-red-950/40 border border-red-500/50 rounded-lg text-xs text-red-200 flex items-center justify-between">
                <span><strong>Global Rollback Executed:</strong> Whole transaction reverted to initial workspace state before any repair was applied. Original state hash perfectly restored.</span>
                <span className="font-mono text-[10px] bg-red-900/60 px-2 py-0.5 rounded">INITIAL_HASH_MATCH: 100%</span>
              </div>
            )}

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-300 border-collapse">
                <thead>
                  <tr className="border-b border-slate-700/80 bg-slate-800/40 text-slate-400 font-mono">
                    <th className="p-3">Step</th>
                    <th className="p-3">Checkpoint ID</th>
                    <th className="p-3">Target File</th>
                    <th className="p-3">State Hash</th>
                    <th className="p-3">Incremental Verification</th>
                    <th className="p-3">Lineage Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {checkpoints.map((chk) => (
                    <tr key={chk.id} className="hover:bg-slate-800/30">
                      <td className="p-3 font-mono font-bold text-cyan-400">#{chk.stepIndex}</td>
                      <td className="p-3 font-mono text-slate-300">{chk.id}</td>
                      <td className="p-3 font-mono text-indigo-300">{chk.file}</td>
                      <td className="p-3 font-mono text-slate-400">{chk.stateHash}</td>
                      <td className="p-3 text-emerald-400">{chk.verification}</td>
                      <td className="p-3">
                        <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-cyan-950 text-cyan-300 border border-cyan-800">
                          {chk.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* SUBTAB 5: Convergence Monitor */}
        {activeSubTab === 'convergence_monitor' && (
          <div className="bg-slate-900/60 border border-slate-800/80 rounded-xl p-5">
            <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
              <div>
                <h3 className="text-sm font-semibold text-white">Convergence & Revealed Failures Engine</h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Differentiates revealed failures (pre-existing unmasked code paths) from true regressions.
                </p>
              </div>

              <div className="flex items-center gap-2">
                <button
                  id="btn-simulate-revealed-failure"
                  onClick={() => setSimulatedRevealed(!simulatedRevealed)}
                  className="px-3 py-1.5 bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-300 border border-cyan-500/40 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all"
                >
                  <Zap className="w-3.5 h-3.5" />
                  Toggle Revealed Failure ({simulatedRevealed ? 'Active' : 'None'})
                </button>
                <button
                  id="btn-simulate-regression"
                  onClick={() => setTransactionState(transactionState === 'DIVERGING' ? 'PROVEN' : 'DIVERGING')}
                  className="px-3 py-1.5 bg-red-500/20 hover:bg-red-500/30 text-red-300 border border-red-500/40 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all"
                >
                  <AlertTriangle className="w-3.5 h-3.5" />
                  Simulate Lateral Regression ({transactionState === 'DIVERGING' ? 'Diverging' : 'Clean'})
                </button>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
              <div className="p-4 bg-slate-800/40 border border-slate-700/50 rounded-lg">
                <div className="text-xs text-slate-400">System Convergence State</div>
                <div className={`text-lg font-bold font-mono mt-1 ${transactionState === 'DIVERGING' ? 'text-red-400' : 'text-emerald-400'}`}>
                  {transactionState === 'DIVERGING' ? 'DIVERGING' : 'CONVERGED'}
                </div>
                <div className="text-[11px] text-slate-400 mt-1">
                  {transactionState === 'DIVERGING' ? 'New lateral regression detected; transaction halted' : 'Target failures: 0 • New blocking failures: 0'}
                </div>
              </div>

              <div className="p-4 bg-slate-800/40 border border-slate-700/50 rounded-lg">
                <div className="text-xs text-slate-400">Revealed Failures (Unmasked)</div>
                <div className="text-lg font-bold font-mono text-amber-400 mt-1">
                  {simulatedRevealed ? '1 Revealed' : '0 Revealed'}
                </div>
                <div className="text-[11px] text-slate-400 mt-1">
                  Classified as latent path (not a regression)
                </div>
              </div>

              <div className="p-4 bg-slate-800/40 border border-slate-700/50 rounded-lg">
                <div className="text-xs text-slate-400">Iteration Budget</div>
                <div className="text-lg font-bold font-mono text-cyan-300 mt-1">1 / 5 Used</div>
                <div className="text-[11px] text-slate-400 mt-1">Convergence achieved well within limits</div>
              </div>
            </div>

            <div className="p-4 bg-slate-800/30 border border-slate-700/40 rounded-lg">
              <h4 className="text-xs font-semibold text-slate-200 mb-2">Epistemic Failure Classification Taxonomy:</h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                <div className="p-3 bg-amber-950/20 border border-amber-600/30 rounded">
                  <div className="font-bold text-amber-300 flex items-center gap-1.5">
                    <CheckCircle2 className="w-4 h-4" />
                    REVEALED_FAILURE
                  </div>
                  <p className="text-slate-300 mt-1 text-[11px]">
                    Occurs when fixing an initial crash exposes a previously unexercised branch that had an existing defect. It does NOT count as a regression and does not abort convergence.
                  </p>
                </div>
                <div className="p-3 bg-red-950/20 border border-red-600/30 rounded">
                  <div className="font-bold text-red-300 flex items-center gap-1.5">
                    <XCircle className="w-4 h-4" />
                    REGRESSION_FAILURE
                  </div>
                  <p className="text-slate-300 mt-1 text-[11px]">
                    Occurs when a patch breaks previously passing behavior or alters contract semantics. Immediately flags DIVERGING and halts proof issuance.
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* SUBTAB 6: Cryptographic Proof Ledger */}
        {activeSubTab === 'proof_ledger' && (
          <div className="bg-slate-900/60 border border-slate-800/80 rounded-xl p-5">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-sm font-semibold text-white">Cryptographic Transaction Proof</h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Proof verification ledger guaranteeing bounded behavioral convergence and rollback lineage.
                </p>
              </div>
              <button
                id="btn-toggle-security-block"
                onClick={() => setTransactionState(transactionState === 'SECURITY_BLOCKED' ? 'PROVEN' : 'SECURITY_BLOCKED')}
                className="px-3 py-1.5 bg-purple-500/20 hover:bg-purple-500/30 text-purple-300 border border-purple-500/40 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all"
              >
                <Lock className="w-3.5 h-3.5" />
                Toggle Security Sentinel Veto
              </button>
            </div>

            <div className="p-4 bg-slate-950/60 border border-slate-800 rounded-xl font-mono text-xs text-slate-300 space-y-2.5">
              <div className="flex justify-between border-b border-slate-800 pb-2">
                <span className="text-slate-400">proof_id:</span>
                <span className="text-cyan-400 font-bold">prf_tx_55_convergence_verified_9db9</span>
              </div>
              <div className="flex justify-between border-b border-slate-800 pb-2">
                <span className="text-slate-400">transaction_id:</span>
                <span className="text-slate-200">tx_dina_multi_repair_01</span>
              </div>
              <div className="flex justify-between border-b border-slate-800 pb-2">
                <span className="text-slate-400">result:</span>
                <span className={`font-bold ${transactionState === 'PROVEN' ? 'text-emerald-400' : 'text-red-400'}`}>
                  {transactionState === 'PROVEN' ? 'TRANSACTION_PROVEN' : 'TRANSACTION_REJECTED'}
                </span>
              </div>
              <div className="flex justify-between border-b border-slate-800 pb-2">
                <span className="text-slate-400">state_before_hash:</span>
                <span className="text-slate-400">sha256:d8a94b3278ce019fa...</span>
              </div>
              <div className="flex justify-between border-b border-slate-800 pb-2">
                <span className="text-slate-400">state_after_hash:</span>
                <span className="text-slate-400">sha256:4a88f01b92cd0412e...</span>
              </div>
              <div className="flex justify-between border-b border-slate-800 pb-2">
                <span className="text-slate-400">invariants_verified:</span>
                <span className="text-emerald-400 font-semibold">[STATE_HASH_LINEAGE, SECURITY_SENTINEL_APPROVED, PRODUCER_BEFORE_CONSUMER, CHECKPOINT_ROLLBACK_INTEGRITY]</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">convergence_status:</span>
                <span className="text-cyan-300 font-semibold">CONVERGED (All targets resolved, 0 blocking failures)</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
