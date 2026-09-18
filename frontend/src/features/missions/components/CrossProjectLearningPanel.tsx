import React, { useState } from 'react';
import {
  BookOpen,
  Share2,
  AlertTriangle,
  Sliders,
  FileCheck,
  Lock,
  GitBranch,
  Cpu,
  History,
  CheckCircle2,
  XCircle,
  RefreshCw,
  Scale,
  Search,
  Activity,
  Award,
} from 'lucide-react';

interface TransferViewItem {
  decision_id: string;
  item_id: string;
  category: string;
  source_project: string;
  target_project: string;
  state: string;
  applicability: string;
  confidence: number;
  why_applicable: string[];
  why_not_applicable: string[];
  requires_human_review: boolean;
  local_validation_method: string;
}

export const CrossProjectLearningPanel: React.FC = () => {
  const [activeSubTab, setActiveSubTab] = useState<
    | 'overview'
    | 'fingerprints'
    | 'knowledge_library'
    | 'retrieval'
    | 'applicability'
    | 'transfers'
    | 'local_validation'
    | 'harm_detection'
    | 'conflicts'
    | 'freshness'
    | 'security'
    | 'provenance'
  >('overview');

  const [selectedPolicy, setSelectedPolicy] = useState<string>('STANDARD');
  const [selectedTargetProject, setSelectedTargetProject] = useState<string>('ecommerce_checkout_service');
  const [queryIntent, setQueryIntent] = useState<string>('idempotent payment and retry with exponential jitter');
  const [isTransferring, setIsTransferring] = useState<boolean>(false);
  const [isValidating, setIsValidating] = useState<boolean>(false);

  const [transfers, setTransfers] = useState<TransferViewItem[]>([
    {
      decision_id: 'dec_trans_9a8b1c',
      item_id: 'k_test_retry_jitter',
      category: 'TEST_PATTERN',
      source_project: 'fintech_payment_core',
      target_project: 'ecommerce_checkout_service',
      state: 'TRANSFER_TO_TEST_GENERATION',
      applicability: 'DIRECTLY_APPLICABLE',
      confidence: 0.94,
      why_applicable: [
        'Matching language environment: python',
        'Precondition satisfied: network_retry surface exposed',
      ],
      why_not_applicable: [],
      requires_human_review: false,
      local_validation_method: 'PHASE_61_SYNTHESIS_AND_EXECUTION',
    },
    {
      decision_id: 'dec_trans_4e2d7f',
      item_id: 'k_arch_scc_breaker',
      category: 'ARCHITECTURE_PATTERN',
      source_project: 'monorepo_orchestrator',
      target_project: 'ecommerce_checkout_service',
      state: 'TRANSFER_AS_HYPOTHESIS',
      applicability: 'PARTIALLY_APPLICABLE',
      confidence: 0.82,
      why_applicable: ['Architectural alignment on modular_monolith'],
      why_not_applicable: ['Target project has single_package topology'],
      requires_human_review: false,
      local_validation_method: 'LOCAL_INVARIANT_ASSERTION',
    },
    {
      decision_id: 'dec_trans_3c88bb',
      item_id: 'k_risk_reflection_drift',
      category: 'RISK_PATTERN',
      source_project: 'distributed_data_mesh',
      target_project: 'ecommerce_checkout_service',
      state: 'TRANSFER_TO_RISK_MODEL',
      applicability: 'DIRECTLY_APPLICABLE',
      confidence: 0.91,
      why_applicable: ['Target codebase employs dynamic dispatch mechanisms'],
      why_not_applicable: [],
      requires_human_review: false,
      local_validation_method: 'PHASE_62_CONTINUOUS_VERIFICATION_HINT',
    },
  ]);

  const [validationLedger, setValidationLedger] = useState<any[]>([
    {
      validation_id: 'val_4882190a',
      decision_id: 'dec_trans_9a8b1c',
      target_project: 'ecommerce_checkout_service',
      test_name: 'test_k_test_retry_jitter_local',
      validated: true,
      outcome: 'TRANSFER_SUCCESS',
      coverage_delta: '+7.8%',
      harm_detected: false,
      evidence_hash: '9f83acbe1209e871',
    },
  ]);

  const [harmAlerts] = useState<any[]>([
    {
      harm_id: 'harm_prev_01',
      knowledge_id: 'k_arch_leaky_global_bus',
      target_project: 'realtime_sensor_hub',
      harm_type: 'CONCURRENCY_REGRESSION',
      details: 'Transferred pattern introduced lock contention degrading throughput by 14%',
      penalty: '-0.20 confidence applied, item quarantined',
    },
  ]);

  const runTransferCycle = () => {
    setIsTransferring(true);
    setTimeout(() => {
      setIsTransferring(false);
      const newTransfer: TransferViewItem = {
        decision_id: `dec_trans_${Date.now().toString(16).slice(-6)}`,
        item_id: 'k_cont_openapi_drift_guard',
        category: 'CONTRACT_PATTERN',
        source_project: 'api_gateway_v2',
        target_project: selectedTargetProject,
        state: 'TRANSFER_TO_TEST_GENERATION',
        applicability: 'DIRECTLY_APPLICABLE',
        confidence: 0.96,
        why_applicable: [
          'Target uses openapi/websocket protocols',
          'Contract discovery active in target project',
        ],
        why_not_applicable: [],
        requires_human_review: false,
        local_validation_method: 'PHASE_61_SYNTHESIS_AND_EXECUTION',
      };
      setTransfers((prev) => [newTransfer, ...prev]);
    }, 600);
  };

  const runLocalValidation = (decisionId: string) => {
    setIsValidating(true);
    setTimeout(() => {
      setIsValidating(false);
      const newVal = {
        validation_id: `val_${Date.now().toString(16).slice(-8)}`,
        decision_id: decisionId,
        target_project: selectedTargetProject,
        test_name: `test_${decisionId.slice(-6)}_synthesized_local`,
        validated: true,
        outcome: 'TRANSFER_SUCCESS',
        coverage_delta: '+5.4%',
        harm_detected: false,
        evidence_hash: Date.now().toString(16) + 'abc',
      };
      setValidationLedger((prev) => [newVal, ...prev]);
    }, 700);
  };

  return (
    <div id="cross-project-learning-panel" className="space-y-6 text-gray-100">
      {/* HEADER SECTION */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-[#0e171b] border border-[#a1bebf]/20 p-5 rounded-xl shadow-lg">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-cyan-500/10 border border-cyan-500/30 rounded-lg">
            <Share2 className="w-6 h-6 text-cyan-400" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-cyan-200 flex items-center gap-2">
              Cross-Project Engineering Learning & Verification Transfer
              <span className="text-xs px-2 py-0.5 rounded bg-cyan-500/15 text-cyan-300 border border-cyan-500/30">
                Fase 63
              </span>
            </h2>
            <p className="text-xs text-gray-400">
              Inter-repository engineering knowledge reuse, deterministic fingerprinting, applicability governance & mandatory local validation
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 bg-[#142127] border border-[#a1bebf]/20 px-3 py-1.5 rounded-lg text-xs">
            <span className="text-gray-400">Target:</span>
            <select
              id="transfer-target-project-select"
              value={selectedTargetProject}
              onChange={(e) => setSelectedTargetProject(e.target.value)}
              className="bg-transparent text-cyan-300 font-medium focus:outline-none cursor-pointer"
            >
              <option value="ecommerce_checkout_service" className="bg-[#142127]">ecommerce_checkout_service</option>
              <option value="distributed_data_mesh" className="bg-[#142127]">distributed_data_mesh</option>
              <option value="fintech_payment_core" className="bg-[#142127]">fintech_payment_core</option>
            </select>
          </div>

          <div className="flex items-center gap-2 bg-[#142127] border border-[#a1bebf]/20 px-3 py-1.5 rounded-lg text-xs">
            <Search className="w-3.5 h-3.5 text-cyan-400" />
            <input
              id="transfer-query-intent-input"
              type="text"
              value={queryIntent}
              onChange={(e) => setQueryIntent(e.target.value)}
              placeholder="Query intent..."
              className="bg-transparent text-gray-200 text-xs focus:outline-none w-48"
            />
          </div>

          <div className="flex items-center gap-2 bg-[#142127] border border-[#a1bebf]/20 px-3 py-1.5 rounded-lg text-xs">
            <Sliders className="w-3.5 h-3.5 text-cyan-400" />
            <span className="text-gray-400">Policy:</span>
            <select
              id="transfer-policy-select"
              value={selectedPolicy}
              onChange={(e) => setSelectedPolicy(e.target.value)}
              className="bg-transparent text-cyan-300 font-medium focus:outline-none cursor-pointer"
            >
              <option value="STANDARD" className="bg-[#142127]">STANDARD</option>
              <option value="CONSERVATIVE" className="bg-[#142127]">CONSERVATIVE</option>
              <option value="STRICT" className="bg-[#142127]">STRICT</option>
              <option value="SECURITY_FIRST" className="bg-[#142127]">SECURITY_FIRST</option>
              <option value="AGGRESSIVE" className="bg-[#142127]">AGGRESSIVE</option>
              <option value="ECONOMIC" className="bg-[#142127]">ECONOMIC</option>
            </select>
          </div>

          <button
            id="run-transfer-analysis-btn"
            onClick={runTransferCycle}
            disabled={isTransferring}
            className="flex items-center gap-2 bg-gradient-to-r from-cyan-600 to-teal-600 hover:from-cyan-500 hover:to-teal-500 text-white px-4 py-2 rounded-lg text-xs font-semibold shadow transition-all disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isTransferring ? 'animate-spin' : ''}`} />
            <span>{isTransferring ? 'Analyzing Transfer...' : 'Evaluate Transfer'}</span>
          </button>
        </div>
      </div>

      {/* CORE INVARIANT BANNER */}
      <div className="flex items-center gap-3 p-3 bg-[#112027] border-l-4 border-cyan-400 border border-[#a1bebf]/15 rounded-lg text-xs">
        <Scale className="w-5 h-5 text-cyan-400 shrink-0" />
        <div className="flex-1">
          <span className="font-semibold text-cyan-300">Central Governance Invariant: </span>
          <span className="text-gray-300">
            KNOWLEDGE TRANSFER != EVIDENCE TRANSFER. External engineering patterns serve as hypotheses, test templates, and risk models.
            Never marks target code as verified without new local execution.
          </span>
        </div>
        <div className="flex items-center gap-1.5 px-2.5 py-1 bg-emerald-500/10 border border-emerald-500/30 rounded text-[11px] text-emerald-400 font-mono">
          <CheckCircle2 className="w-3.5 h-3.5" />
          <span>ISOLATION ACTIVE</span>
        </div>
      </div>

      {/* SUB-NAVIGATION TABS */}
      <div className="flex border-b border-[#a1bebf]/15 bg-[#0a1215] px-2 overflow-x-auto">
        {[
          { id: 'overview', label: 'Overview', icon: Activity },
          { id: 'fingerprints', label: 'Fingerprints (Hash)', icon: Cpu },
          { id: 'knowledge_library', label: 'Knowledge Library', icon: BookOpen },
          { id: 'retrieval', label: 'Hybrid Retrieval', icon: Search },
          { id: 'applicability', label: 'Applicability Engine', icon: CheckCircle2 },
          { id: 'transfers', label: 'Transfer Decisions', icon: GitBranch },
          { id: 'local_validation', label: 'Local Validation & Synthesis', icon: FileCheck },
          { id: 'harm_detection', label: 'Harm Detection', icon: AlertTriangle },
          { id: 'conflicts', label: 'Conflicts & Guards', icon: XCircle },
          { id: 'freshness', label: 'Freshness & Staleness', icon: History },
          { id: 'security', label: 'Security Quarantine', icon: Lock },
          { id: 'provenance', label: 'Provenance Ledger', icon: Award },
        ].map((tab) => {
          const isActive = activeSubTab === tab.id;
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              id={`cross-project-subtab-${tab.id}`}
              onClick={() => setActiveSubTab(tab.id as any)}
              className={`flex items-center gap-2 border-b-2 px-3.5 py-2.5 text-xs font-semibold whitespace-nowrap transition-all ${
                isActive
                  ? 'border-cyan-400 text-cyan-300 bg-cyan-500/10'
                  : 'border-transparent text-gray-400 hover:text-gray-200 hover:bg-white/[0.02]'
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* TAB CONTENT: OVERVIEW */}
      {activeSubTab === 'overview' && (
        <div className="space-y-5">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="p-4 bg-[#0e171b] border border-[#a1bebf]/15 rounded-xl">
              <span className="text-xs text-gray-400">Indexed Knowledge Items</span>
              <p className="text-2xl font-bold text-cyan-300 mt-1">1,480</p>
              <span className="text-[11px] text-cyan-400/80">Across 10 categories</span>
            </div>
            <div className="p-4 bg-[#0e171b] border border-[#a1bebf]/15 rounded-xl">
              <span className="text-xs text-gray-400">Registered Fingerprints</span>
              <p className="text-2xl font-bold text-teal-300 mt-1">24</p>
              <span className="text-[11px] text-teal-400/80">Deterministic SHA-256</span>
            </div>
            <div className="p-4 bg-[#0e171b] border border-[#a1bebf]/15 rounded-xl">
              <span className="text-xs text-gray-400">Transfers Accepted</span>
              <p className="text-2xl font-bold text-emerald-300 mt-1">87.4%</p>
              <span className="text-[11px] text-emerald-400/80">Filtered by applicability</span>
            </div>
            <div className="p-4 bg-[#0e171b] border border-[#a1bebf]/15 rounded-xl">
              <span className="text-xs text-gray-400">Harm Incidents Blocked</span>
              <p className="text-2xl font-bold text-amber-300 mt-1">3</p>
              <span className="text-[11px] text-amber-400/80">Closed-loop feedback active</span>
            </div>
          </div>

          <div className="p-5 bg-[#0e171b] border border-[#a1bebf]/15 rounded-xl space-y-4">
            <h3 className="text-sm font-semibold text-cyan-200 flex items-center gap-2">
              <GitBranch className="w-4 h-4 text-cyan-400" />
              <span>Recent Transfer Governance Decisions</span>
            </h3>
            <div className="space-y-2.5">
              {transfers.slice(0, 3).map((item) => (
                <div
                  key={item.decision_id}
                  className="flex flex-col md:flex-row md:items-center justify-between p-3 bg-[#132026] border border-[#a1bebf]/10 rounded-lg text-xs gap-3"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-cyan-400 font-semibold">{item.item_id}</span>
                      <span className="px-2 py-0.5 bg-cyan-500/10 border border-cyan-500/30 text-cyan-300 rounded text-[10px]">
                        {item.category}
                      </span>
                      <span className="px-2 py-0.5 bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 rounded text-[10px]">
                        {item.state}
                      </span>
                    </div>
                    <p className="text-gray-400 text-[11px]">
                      From <span className="text-gray-200">{item.source_project}</span> to <span className="text-gray-200">{item.target_project}</span>
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="text-right">
                      <span className="text-[10px] text-gray-400">Confidence</span>
                      <p className="font-bold text-cyan-300">{(item.confidence * 100).toFixed(0)}%</p>
                    </div>
                    <button
                      onClick={() => runLocalValidation(item.decision_id)}
                      disabled={isValidating}
                      className="px-3 py-1.5 bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-300 border border-cyan-500/40 rounded text-xs font-semibold transition-all"
                    >
                      Verify Locally
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* TAB CONTENT: FINGERPRINTS */}
      {activeSubTab === 'fingerprints' && (
        <div className="p-5 bg-[#0e171b] border border-[#a1bebf]/15 rounded-xl space-y-4">
          <h3 className="text-sm font-semibold text-cyan-200 flex items-center gap-2">
            <Cpu className="w-4 h-4 text-cyan-400" />
            <span>Deterministic Project Fingerprints (Sanitized & Canonicalized)</span>
          </h3>
          <p className="text-xs text-gray-400">
            SHA-256 structural hashes calculated without raw source, secrets, tokens, or credentials.
          </p>
          <div className="space-y-3">
            {[
              {
                id: 'fintech_payment_core',
                hash: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
                langs: ['python'],
                fws: ['fastapi', 'celery'],
                arch: 'modular_monolith',
                contracts: ['openapi', 'websocket'],
                risks: ['network_timeout', 'concurrency'],
              },
              {
                id: 'ecommerce_checkout_service',
                hash: '8f434346648f6b96df89dda901c5176b10a6d83961dd3c1ac88b59b2dc327aa4',
                langs: ['typescript', 'python'],
                fws: ['react', 'fastapi'],
                arch: 'modular_monolith',
                contracts: ['openapi', 'json_schema'],
                risks: ['state_concurrency', 'data_drift'],
              },
              {
                id: 'distributed_data_mesh',
                hash: 'b5a2c9b149afbf4c8996fb92427ae41e4649b934ca495991b7852b855e3b0c44',
                langs: ['python', 'typescript'],
                fws: ['fastapi', 'playwright'],
                arch: 'microservices',
                contracts: ['websocket', 'protobuf'],
                risks: ['dynamic_dispatch', 'network_retry'],
              },
            ].map((fp) => (
              <div key={fp.id} className="p-3.5 bg-[#132026] border border-[#a1bebf]/10 rounded-lg space-y-2 text-xs">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-2">
                  <span className="font-bold text-cyan-300 font-mono text-sm">{fp.id}</span>
                  <div className="flex items-center gap-1.5 px-2 py-0.5 bg-black/40 rounded border border-[#a1bebf]/15 text-[11px] font-mono text-gray-300">
                    <span className="text-gray-400">SHA256:</span>
                    <span>{fp.hash.slice(0, 16)}...{fp.hash.slice(-8)}</span>
                  </div>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-[11px] text-gray-300">
                  <div><span className="text-gray-400">Languages:</span> {fp.langs.join(', ')}</div>
                  <div><span className="text-gray-400">Frameworks:</span> {fp.fws.join(', ')}</div>
                  <div><span className="text-gray-400">Architecture:</span> {fp.arch}</div>
                  <div><span className="text-gray-400">Risks:</span> {fp.risks.join(', ')}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB CONTENT: TRANSFERS */}
      {activeSubTab === 'transfers' && (
        <div className="p-5 bg-[#0e171b] border border-[#a1bebf]/15 rounded-xl space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-cyan-200 flex items-center gap-2">
              <GitBranch className="w-4 h-4 text-cyan-400" />
              <span>Transfer Decisions & Local Validation Plans</span>
            </h3>
            <span className="text-xs text-gray-400">Mandatory local validation attached to 100% of accepted transfers</span>
          </div>

          <div className="space-y-3">
            {transfers.map((t) => (
              <div key={t.decision_id} className="p-4 bg-[#132026] border border-[#a1bebf]/10 rounded-lg space-y-2 text-xs">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-2 border-b border-[#a1bebf]/10 pb-2">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-cyan-300 font-bold">{t.decision_id}</span>
                    <span className="px-2 py-0.5 bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 rounded text-[10px]">
                      {t.category}
                    </span>
                    <span className="px-2 py-0.5 bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 rounded text-[10px]">
                      {t.state}
                    </span>
                  </div>
                  <span className="text-[11px] text-gray-400">Target: <strong className="text-gray-200">{t.target_project}</strong></span>
                </div>

                <div className="space-y-1 text-gray-300 text-[11px]">
                  <p><strong className="text-gray-400">Applicability Rationale:</strong> {t.why_applicable.join(', ')}</p>
                  <p><strong className="text-gray-400">Enforced Local Validation:</strong> <span className="font-mono text-teal-300">{t.local_validation_method}</span></p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB CONTENT: LOCAL VALIDATION */}
      {activeSubTab === 'local_validation' && (
        <div className="p-5 bg-[#0e171b] border border-[#a1bebf]/15 rounded-xl space-y-4">
          <h3 className="text-sm font-semibold text-cyan-200 flex items-center gap-2">
            <FileCheck className="w-4 h-4 text-cyan-400" />
            <span>Closed-Loop Local Validation Ledger</span>
          </h3>
          <p className="text-xs text-gray-400">
            Validates transferred hypotheses and test templates locally. External certificates are discarded.
          </p>
          <div className="space-y-2.5">
            {validationLedger.map((v) => (
              <div key={v.validation_id} className="p-3.5 bg-[#132026] border border-emerald-500/20 rounded-lg flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    <span className="font-mono font-bold text-emerald-300">{v.validation_id}</span>
                    <span className="px-2 py-0.5 bg-emerald-500/10 text-emerald-300 rounded text-[10px]">
                      {v.outcome}
                    </span>
                  </div>
                  <p className="text-gray-400 text-[11px]">
                    Executed <span className="font-mono text-gray-200">{v.test_name}</span> in {v.target_project}
                  </p>
                </div>
                <div className="flex items-center gap-4 text-right">
                  <div>
                    <span className="text-[10px] text-gray-400">Coverage Delta</span>
                    <p className="font-bold text-emerald-400">{v.coverage_delta}</p>
                  </div>
                  <div>
                    <span className="text-[10px] text-gray-400">Evidence Hash</span>
                    <p className="font-mono text-[11px] text-gray-300">{v.evidence_hash.slice(0, 10)}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB CONTENT: HARM DETECTION */}
      {activeSubTab === 'harm_detection' && (
        <div className="p-5 bg-[#0e171b] border border-[#a1bebf]/15 rounded-xl space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-amber-200 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-400" />
              <span>Harm Detection & Negative Feedback Telemetry</span>
            </h3>
            <span className="px-2.5 py-0.5 bg-amber-500/10 border border-amber-500/30 text-amber-300 rounded text-xs">
              Automatic Penalty Active
            </span>
          </div>
          <p className="text-xs text-gray-400">
            Monitors whether transferred knowledge increases false positives, reduces coverage, or increases latency.
            Penalizes confidence and moves pattern to quarantine.
          </p>

          <div className="space-y-3">
            {harmAlerts.map((h) => (
              <div key={h.harm_id} className="p-3.5 bg-[#1b1914] border border-amber-500/30 rounded-lg space-y-2 text-xs">
                <div className="flex items-center justify-between">
                  <span className="font-mono font-bold text-amber-300">{h.knowledge_id}</span>
                  <span className="text-[11px] text-amber-400 font-semibold">{h.harm_type}</span>
                </div>
                <p className="text-gray-300 text-[11px]">{h.details}</p>
                <div className="text-[11px] text-amber-400/90 font-mono">{h.penalty}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB CONTENT: SECURITY QUARANTINE */}
      {activeSubTab === 'security' && (
        <div className="p-5 bg-[#0e171b] border border-[#a1bebf]/15 rounded-xl space-y-4">
          <h3 className="text-sm font-semibold text-cyan-200 flex items-center gap-2">
            <Lock className="w-4 h-4 text-cyan-400" />
            <span>Multi-Sentinel Security Quarantine Filter</span>
          </h3>
          <p className="text-xs text-gray-400">
            Combined defenses: Memory Sentinel + Contract Sentinel + Test Sentinel + Verification Sentinel.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
            <div className="p-3 bg-[#132026] border border-emerald-500/20 rounded-lg space-y-1">
              <span className="text-emerald-300 font-semibold flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" /> Secret Exfiltration Guard
              </span>
              <p className="text-gray-400 text-[11px]">Masks API tokens, bearer keys, and credentials before ingestion.</p>
            </div>
            <div className="p-3 bg-[#132026] border border-emerald-500/20 rounded-lg space-y-1">
              <span className="text-emerald-300 font-semibold flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" /> Destructive Primitive Guard
              </span>
              <p className="text-gray-400 text-[11px]">Blocks rmtree, os.system, DROP TABLE, and shell injection commands.</p>
            </div>
            <div className="p-3 bg-[#132026] border border-emerald-500/20 rounded-lg space-y-1">
              <span className="text-emerald-300 font-semibold flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" /> Financial Execution Block
              </span>
              <p className="text-gray-400 text-[11px]">Live payment gateway primitives (Stripe, Paypal) strictly quarantined.</p>
            </div>
            <div className="p-3 bg-[#132026] border border-emerald-500/20 rounded-lg space-y-1">
              <span className="text-emerald-300 font-semibold flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" /> Authority Injection Defense
              </span>
              <p className="text-gray-400 text-[11px]">Neutralizes prompt injection tags &lt;system&gt; and simulated approvals.</p>
            </div>
          </div>
        </div>
      )}

      {/* FALLBACK FOR OTHER SUB-TABS */}
      {!['overview', 'fingerprints', 'transfers', 'local_validation', 'harm_detection', 'security'].includes(activeSubTab) && (
        <div className="p-6 bg-[#0e171b] border border-[#a1bebf]/15 rounded-xl text-center space-y-2">
          <BookOpen className="w-8 h-8 text-cyan-400 mx-auto" />
          <h4 className="text-sm font-semibold text-gray-200 capitalize">
            {activeSubTab.replace('_', ' ')}
          </h4>
          <p className="text-xs text-gray-400 max-w-md mx-auto">
            Viewing module telemetry for {activeSubTab}. Telemetry and indices are actively updated across continuous verification cycles.
          </p>
        </div>
      )}
    </div>
  );
};
