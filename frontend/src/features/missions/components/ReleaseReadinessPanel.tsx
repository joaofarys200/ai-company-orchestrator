import React, { useState } from 'react';
import {
  Rocket,
  ShieldAlert,
  ShieldCheck,
  Cpu,
  FileCode,
  GitBranch,
  Layers,
  Radio,
  Package,
  RotateCcw,
  Clock,
  AlertTriangle,
  Server,
  Eye,
  CheckCircle2,
  Play,
  FileCheck
} from 'lucide-react';

interface ReleaseReadinessPanelProps {
  missionId?: string;
}

export const ReleaseReadinessPanel: React.FC<ReleaseReadinessPanelProps> = ({
  missionId = 'mission_f70_release',
}) => {
  const [activeSubtab, setActiveSubtab] = useState<string>('overview');
  const [candidateState, setCandidateState] = useState<string>('RELEASE_READY_WITH_RISK');
  const [isEvaluating, setIsEvaluating] = useState<boolean>(false);

  const subtabs = [
    { id: 'overview', label: '01. Release Overview', icon: Rocket, elementId: 'release-subtab-overview' },
    { id: 'quality', label: '02. Quality Status', icon: FileCheck, elementId: 'release-subtab-quality' },
    { id: 'debt', label: '03. Debt Status', icon: Layers, elementId: 'release-subtab-debt' },
    { id: 'contracts', label: '04. Contract Status', icon: FileCode, elementId: 'release-subtab-contracts' },
    { id: 'behavior', label: '05. Behavior Status', icon: GitBranch, elementId: 'release-subtab-behavior' },
    { id: 'security', label: '06. Security Status', icon: ShieldAlert, elementId: 'release-subtab-security' },
    { id: 'performance', label: '07. Performance', icon: Cpu, elementId: 'release-subtab-performance' },
    { id: 'runtime', label: '08. Runtime Health', icon: Server, elementId: 'release-subtab-runtime' },
    { id: 'observability', label: '09. Observability', icon: Eye, elementId: 'release-subtab-observability' },
    { id: 'dependencies', label: '10. Dependencies', icon: Package, elementId: 'release-subtab-dependencies' },
    { id: 'rollback', label: '11. Rollback Readiness', icon: RotateCcw, elementId: 'release-subtab-rollback' },
    { id: 'plan', label: '12. Release Plan', icon: Radio, elementId: 'release-subtab-plan' },
    { id: 'gate', label: '13. Release Gate', icon: ShieldCheck, elementId: 'release-subtab-gate' },
    { id: 'blocked', label: '14. Blocked / Review', icon: AlertTriangle, elementId: 'release-subtab-blocked' },
  ];

  const handleEvaluate = () => {
    setIsEvaluating(true);
    setTimeout(() => {
      setIsEvaluating(false);
      setCandidateState('RELEASE_READY_WITH_RISK');
    }, 600);
  };

  return (
    <div className="flex flex-col h-full bg-slate-950 text-slate-100 rounded-lg overflow-hidden border border-slate-800 shadow-2xl">
      {/* Top Banner Header */}
      <div className="flex flex-wrap items-center justify-between p-4 bg-slate-900/90 border-b border-slate-800 backdrop-blur">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 bg-indigo-600/20 text-indigo-400 rounded-lg border border-indigo-500/30">
            <Rocket className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h2 className="text-lg font-bold text-slate-100 tracking-tight">Phase 70: Release Readiness & Production Governance</h2>
              <span className="px-2 py-0.5 text-xs font-mono bg-indigo-900/40 text-indigo-300 border border-indigo-700/50 rounded">
                RC-2026.09-PROD-01
              </span>
            </div>
            <p className="text-xs text-slate-400 font-mono">
              Mission: <span className="text-slate-300">{missionId}</span> | SHA: <span className="text-indigo-300">f87e2b10a9c</span> | Env: production
            </p>
          </div>
        </div>

        {/* Status Badges and Actions */}
        <div className="flex items-center space-x-3 mt-2 sm:mt-0">
          <div className="flex items-center space-x-1.5 px-3 py-1 bg-amber-950/40 border border-amber-500/40 text-amber-300 rounded text-xs font-mono">
            <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse"></span>
            <span>State: {candidateState}</span>
          </div>

          <button
            onClick={handleEvaluate}
            disabled={isEvaluating}
            className="flex items-center space-x-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded text-xs font-semibold shadow transition duration-150 disabled:opacity-50"
          >
            <Play className="w-3.5 h-3.5" />
            <span>{isEvaluating ? 'Evaluating...' : 'Evaluate Gate'}</span>
          </button>
        </div>
      </div>

      {/* Subtab Navigation Bar */}
      <div className="flex overflow-x-auto bg-slate-900 border-b border-slate-800 scrollbar-thin scrollbar-thumb-slate-700">
        {subtabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeSubtab === tab.id;
          return (
            <button
              key={tab.id}
              id={tab.elementId}
              onClick={() => setActiveSubtab(tab.id)}
              className={`flex items-center space-x-1.5 px-3.5 py-2.5 text-xs font-medium whitespace-nowrap transition-colors border-b-2 ${
                isActive
                  ? 'border-indigo-500 text-indigo-300 bg-indigo-950/30'
                  : 'border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
              }`}
            >
              <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-indigo-400' : 'text-slate-400'}`} />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* Subtab Content Area */}
      <div className="flex-1 p-5 overflow-y-auto bg-slate-950/60">
        {/* 01. Release Overview */}
        {activeSubtab === 'overview' && (
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="p-4 bg-slate-900/60 rounded-lg border border-slate-800">
                <div className="text-xs font-mono text-slate-400">CANDIDATE ID</div>
                <div className="text-sm font-mono font-bold text-slate-100 mt-1">rc-prod-release-01</div>
                <div className="text-xs text-emerald-400 mt-2 font-mono flex items-center">
                  <CheckCircle2 className="w-3 h-3 mr-1" /> Provenance Verified
                </div>
              </div>
              <div className="p-4 bg-slate-900/60 rounded-lg border border-slate-800">
                <div className="text-xs font-mono text-slate-400">LIFECYCLE STATE</div>
                <div className="text-sm font-bold text-amber-400 mt-1">{candidateState}</div>
                <div className="text-xs text-slate-400 mt-2 font-mono">Transition: VALIDATING → READY_WITH_RISK</div>
              </div>
              <div className="p-4 bg-slate-900/60 rounded-lg border border-slate-800">
                <div className="text-xs font-mono text-slate-400">IMMUTABLE BASELINE HASH</div>
                <div className="text-xs font-mono text-indigo-300 mt-1 truncate">7c8d9e2a1b4c3d5f6e8a0b1c2d3e4f5a</div>
                <div className="text-xs text-slate-400 mt-2 font-mono">Sealed: 13/13 Dimensions Frozen</div>
              </div>
              <div className="p-4 bg-slate-900/60 rounded-lg border border-slate-800">
                <div className="text-xs font-mono text-slate-400">OVERALL RISK SCORE</div>
                <div className="text-sm font-bold text-emerald-400 mt-1">0.18 / 1.0 (Low-Moderate)</div>
                <div className="text-xs text-slate-400 mt-2 font-mono">Epistemic Confidence: 92.4%</div>
              </div>
            </div>

            {/* Invariant Axiom Banner */}
            <div className="p-3 bg-indigo-950/30 border border-indigo-800/40 rounded-lg flex items-center justify-between text-xs font-mono text-indigo-200">
              <div className="flex items-center space-x-2">
                <ShieldCheck className="w-4 h-4 text-indigo-400" />
                <span>INVARIANT ENFORCEMENT: CREATED → RELEASED is strictly illegal. Full 12-domain governance required.</span>
              </div>
              <span className="px-2 py-0.5 bg-emerald-900/40 text-emerald-300 rounded border border-emerald-700/40 font-bold">
                ENFORCED
              </span>
            </div>

            {/* Candidate Metadata Breakdown */}
            <div className="p-4 bg-slate-900/40 rounded-lg border border-slate-800">
              <h3 className="text-sm font-bold text-slate-200 mb-3">Release Candidate Provenance & Topology</h3>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-xs font-mono">
                <div className="p-2.5 bg-slate-950 rounded border border-slate-850">
                  <span className="text-slate-400">Target Environment:</span> <span className="text-slate-200 font-bold">production</span>
                </div>
                <div className="p-2.5 bg-slate-950 rounded border border-slate-850">
                  <span className="text-slate-400">Version Semver:</span> <span className="text-indigo-300 font-bold">v1.2.0-rc3</span>
                </div>
                <div className="p-2.5 bg-slate-950 rounded border border-slate-850">
                  <span className="text-slate-400">Baseline Captured At:</span> <span className="text-slate-200">2026-09-19T18:00:00Z</span>
                </div>
                <div className="p-2.5 bg-slate-950 rounded border border-slate-850">
                  <span className="text-slate-400">Workspace Hash:</span> <span className="text-slate-300">b8109d94fa21</span>
                </div>
                <div className="p-2.5 bg-slate-950 rounded border border-slate-850">
                  <span className="text-slate-400">Artifacts Tracked:</span> <span className="text-slate-200">21 bundles</span>
                </div>
                <div className="p-2.5 bg-slate-950 rounded border border-slate-850">
                  <span className="text-slate-400">Deployment Status:</span> <span className="text-amber-400 font-bold">DEPLOYMENT_NOT_AVAILABLE</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 02. Quality Status */}
        {activeSubtab === 'quality' && (
          <div className="space-y-4">
            <div className="p-4 bg-slate-900/60 rounded-lg border border-slate-800">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-bold text-slate-200">Phase 68/69 Quality Integration & Uncertainty</h3>
                <span className="px-2.5 py-0.5 text-xs font-mono bg-emerald-950 text-emerald-400 border border-emerald-700/50 rounded">
                  Score: 0.94 / 1.0 (PASSED)
                </span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs font-mono mb-4">
                <div className="p-3 bg-slate-950 rounded border border-slate-850">
                  <div className="text-slate-400">Maintainability Delta</div>
                  <div className="text-sm font-bold text-emerald-400 mt-1">+0.04 (Improved)</div>
                </div>
                <div className="p-3 bg-slate-950 rounded border border-slate-850">
                  <div className="text-slate-400">Reliability Delta</div>
                  <div className="text-sm font-bold text-slate-200 mt-1">0.00 (Stable)</div>
                </div>
                <div className="p-3 bg-slate-950 rounded border border-slate-850">
                  <div className="text-slate-400">Quality Uncertainty Bound</div>
                  <div className="text-sm font-bold text-indigo-300 mt-1">0.042 (Low Uncertainty)</div>
                </div>
              </div>
              <p className="text-xs text-slate-400">
                Rule verified: <code className="text-indigo-300">ACCEPTED_WITH_DEBT != RELEASE_READY</code>. Releases require separate operational evidence.
              </p>
            </div>
          </div>
        )}

        {/* 03. Debt Status */}
        {activeSubtab === 'debt' && (
          <div className="space-y-4">
            <div className="p-4 bg-slate-900/60 rounded-lg border border-slate-800">
              <h3 className="text-sm font-bold text-slate-200 mb-3">Technical Debt Readiness Gate</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs font-mono mb-4">
                <div className="p-3 bg-slate-950 rounded border border-slate-850">
                  <div className="text-slate-400">Critical Security Debt</div>
                  <div className="text-sm font-bold text-emerald-400 mt-1">0 (Clear)</div>
                </div>
                <div className="p-3 bg-slate-950 rounded border border-slate-850">
                  <div className="text-slate-400">Critical Quality Debt</div>
                  <div className="text-sm font-bold text-emerald-400 mt-1">0 (Clear)</div>
                </div>
                <div className="p-3 bg-slate-950 rounded border border-slate-850">
                  <div className="text-slate-400">Unresolved Unknowns</div>
                  <div className="text-sm font-bold text-slate-200 mt-1">0 (None)</div>
                </div>
                <div className="p-3 bg-slate-950 rounded border border-slate-850">
                  <div className="text-slate-400">Deferred Debt Count</div>
                  <div className="text-sm font-bold text-amber-400 mt-1">1 (Governed)</div>
                </div>
              </div>
              <div className="p-3 bg-emerald-950/20 border border-emerald-800/40 rounded text-xs text-emerald-300 font-mono">
                ✓ No critical debt blockers active. 1 non-critical debt item deferred with governance authorization.
              </div>
            </div>
          </div>
        )}

        {/* 04. Contract Status */}
        {activeSubtab === 'contracts' && (
          <div className="space-y-4">
            <div className="p-4 bg-slate-900/60 rounded-lg border border-slate-800">
              <h3 className="text-sm font-bold text-slate-200 mb-3">Contract Readiness & Polymorphic Verification</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs font-mono mb-4">
                <div className="p-3 bg-slate-950 rounded border border-slate-850">
                  <div className="text-slate-400">Contract Hash Match</div>
                  <div className="text-sm font-bold text-emerald-400 mt-1">SYNCHRONIZED</div>
                </div>
                <div className="p-3 bg-slate-950 rounded border border-slate-850">
                  <div className="text-slate-400">Breaking Changes</div>
                  <div className="text-sm font-bold text-slate-200 mt-1">0 detected</div>
                </div>
                <div className="p-3 bg-slate-950 rounded border border-slate-850">
                  <div className="text-slate-400">Polymorphic Violations</div>
                  <div className="text-sm font-bold text-slate-200 mt-1">0 detected</div>
                </div>
              </div>
              <div className="text-xs text-slate-400 font-mono">
                Contract graph invariant holds: Any <span className="text-rose-400">BREAKING</span> or <span className="text-amber-400">UNKNOWN</span> change blocks automatic release.
              </div>
            </div>
          </div>
        )}

        {/* 05. Behavior Status */}
        {activeSubtab === 'behavior' && (
          <div className="space-y-4">
            <div className="p-4 bg-slate-900/60 rounded-lg border border-slate-800">
              <h3 className="text-sm font-bold text-slate-200 mb-3">Behavioral Contract Proof & Counterexamples</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs font-mono mb-4">
                <div className="p-3 bg-slate-950 rounded border border-slate-850">
                  <div className="text-slate-400">Invariants Verified</div>
                  <div className="text-sm font-bold text-emerald-400 mt-1">100% PRESERVED</div>
                </div>
                <div className="p-3 bg-slate-950 rounded border border-slate-850">
                  <div className="text-slate-400">Counterexamples</div>
                  <div className="text-sm font-bold text-emerald-400 mt-1">0 Found</div>
                </div>
                <div className="p-3 bg-slate-950 rounded border border-slate-850">
                  <div className="text-slate-400">Concurrency Hazards</div>
                  <div className="text-sm font-bold text-slate-200 mt-1">0 Detected</div>
                </div>
                <div className="p-3 bg-slate-950 rounded border border-slate-850">
                  <div className="text-slate-400">Idempotency Checks</div>
                  <div className="text-sm font-bold text-emerald-400 mt-1">Passed (12/12)</div>
                </div>
              </div>
              <div className="p-3 bg-indigo-950/20 border border-indigo-800/40 rounded text-xs text-indigo-300 font-mono">
                Status: <span className="text-emerald-400 font-bold">PRESERVED_WITHIN_SCOPE</span>. State transitions verified deterministically.
              </div>
            </div>
          </div>
        )}

        {/* 06. Security Status */}
        {activeSubtab === 'security' && (
          <div className="space-y-4">
            <div className="p-4 bg-slate-900/60 rounded-lg border border-slate-800">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center space-x-2">
                  <ShieldCheck className="w-5 h-5 text-emerald-400" />
                  <h3 className="text-sm font-bold text-slate-200">Security Sentinel Authority (Maximum Veto)</h3>
                </div>
                <span className="px-2.5 py-0.5 text-xs font-mono bg-emerald-950 text-emerald-400 border border-emerald-700/50 rounded">
                  VERDICT: PASSED
                </span>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs font-mono mb-4">
                <div className="p-3 bg-slate-950 rounded border border-slate-850">
                  <div className="text-slate-400">Secrets Scanner</div>
                  <div className="text-sm font-bold text-emerald-400 mt-1">0 Exposed</div>
                </div>
                <div className="p-3 bg-slate-950 rounded border border-slate-850">
                  <div className="text-slate-400">Sandbox Violations</div>
                  <div className="text-sm font-bold text-emerald-400 mt-1">0 Detected</div>
                </div>
                <div className="p-3 bg-slate-950 rounded border border-slate-850">
                  <div className="text-slate-400">Protected Paths</div>
                  <div className="text-sm font-bold text-emerald-400 mt-1">100% Inviolate</div>
                </div>
                <div className="p-3 bg-slate-950 rounded border border-slate-850">
                  <div className="text-slate-400">Critical CVEs</div>
                  <div className="text-sm font-bold text-emerald-400 mt-1">0 Found</div>
                </div>
              </div>
              <div className="p-3 bg-rose-950/20 border border-rose-800/40 rounded text-xs text-rose-300 font-mono">
                Invariant: Security policy can never be relaxed to pass a release. Sentinel authority is absolute.
              </div>
            </div>
          </div>
        )}

        {/* 07. Performance */}
        {activeSubtab === 'performance' && (
          <div className="space-y-4">
            <div className="p-4 bg-slate-900/60 rounded-lg border border-slate-800">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-bold text-slate-200">Performance Readiness (Observed vs Estimated)</h3>
                <span className="px-2 py-0.5 text-xs font-mono bg-indigo-950 text-indigo-300 border border-indigo-700/50 rounded">
                  Nature: observed
                </span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-xs font-mono text-left border-collapse">
                  <thead>
                    <tr className="border-b border-slate-800 text-slate-400">
                      <th className="py-2">Dimension</th>
                      <th className="py-2">Baseline</th>
                      <th className="py-2">Candidate</th>
                      <th className="py-2">Shift %</th>
                      <th className="py-2">Nature</th>
                      <th className="py-2">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-850">
                    <tr>
                      <td className="py-2 text-slate-200">Latency P95</td>
                      <td className="py-2 text-slate-400">12.5 ms</td>
                      <td className="py-2 text-slate-200">11.8 ms</td>
                      <td className="py-2 text-emerald-400">-5.6%</td>
                      <td className="py-2 text-indigo-300">observed</td>
                      <td className="py-2 text-emerald-400">IMPROVED</td>
                    </tr>
                    <tr>
                      <td className="py-2 text-slate-200">Throughput</td>
                      <td className="py-2 text-slate-400">1,450 rps</td>
                      <td className="py-2 text-slate-200">1,520 rps</td>
                      <td className="py-2 text-emerald-400">+4.8%</td>
                      <td className="py-2 text-indigo-300">observed</td>
                      <td className="py-2 text-emerald-400">WITHIN_BUDGET</td>
                    </tr>
                    <tr>
                      <td className="py-2 text-slate-200">CPU Usage</td>
                      <td className="py-2 text-slate-400">14.2%</td>
                      <td className="py-2 text-slate-200">14.8%</td>
                      <td className="py-2 text-slate-300">+4.2%</td>
                      <td className="py-2 text-indigo-300">observed</td>
                      <td className="py-2 text-emerald-400">WITHIN_BUDGET</td>
                    </tr>
                    <tr>
                      <td className="py-2 text-slate-200">Memory (RSS)</td>
                      <td className="py-2 text-slate-400">115.0 MB</td>
                      <td className="py-2 text-slate-200">118.2 MB</td>
                      <td className="py-2 text-slate-300">+2.7%</td>
                      <td className="py-2 text-indigo-300">observed</td>
                      <td className="py-2 text-emerald-400">WITHIN_BUDGET</td>
                    </tr>
                    <tr>
                      <td className="py-2 text-slate-200">Browser Render</td>
                      <td className="py-2 text-slate-400">18.4 ms</td>
                      <td className="py-2 text-slate-200">17.9 ms</td>
                      <td className="py-2 text-emerald-400">-2.7%</td>
                      <td className="py-2 text-indigo-300">observed</td>
                      <td className="py-2 text-emerald-400">IMPROVED</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* 08. Runtime Health */}
        {activeSubtab === 'runtime' && (
          <div className="space-y-4">
            <div className="p-4 bg-slate-900/60 rounded-lg border border-slate-800">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-bold text-slate-200">Runtime Health Verification</h3>
                <span className="px-2 py-0.5 text-xs font-mono bg-emerald-950 text-emerald-400 border border-emerald-700/50 rounded">
                  HEALTHY
                </span>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs font-mono mb-4">
                <div className="p-3 bg-slate-950 rounded border border-slate-850">
                  <div className="text-slate-400">Process Startup</div>
                  <div className="text-emerald-400 font-bold mt-1">✓ Started (PID: 4912)</div>
                </div>
                <div className="p-3 bg-slate-950 rounded border border-slate-850">
                  <div className="text-slate-400">Healthcheck Probe</div>
                  <div className="text-emerald-400 font-bold mt-1">✓ 200 OK (3.2ms)</div>
                </div>
                <div className="p-3 bg-slate-950 rounded border border-slate-850">
                  <div className="text-slate-400">Readiness Probe</div>
                  <div className="text-emerald-400 font-bold mt-1">✓ Ready (1.8ms)</div>
                </div>
                <div className="p-3 bg-slate-950 rounded border border-slate-850">
                  <div className="text-slate-400">WebSocket Handshake</div>
                  <div className="text-emerald-400 font-bold mt-1">✓ 101 Switching</div>
                </div>
              </div>
              <div className="p-3 bg-slate-900 rounded border border-slate-850 text-xs font-mono text-slate-300">
                Rule: Process startup alone does not imply runtime health. Error rate observed: <span className="text-emerald-400">0.00%</span>.
              </div>
            </div>
          </div>
        )}

        {/* 09. Observability */}
        {activeSubtab === 'observability' && (
          <div className="space-y-4">
            <div className="p-4 bg-slate-900/60 rounded-lg border border-slate-800">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-bold text-slate-200">Observability Readiness (Signals 7/7)</h3>
                <span className="px-2 py-0.5 text-xs font-mono bg-emerald-950 text-emerald-400 border border-emerald-700/50 rounded">
                  STATUS: READY
                </span>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs font-mono mb-4">
                <div className="p-3 bg-slate-950 rounded border border-slate-850">
                  <span className="text-emerald-400 font-bold">✓</span> Structured Logs
                </div>
                <div className="p-3 bg-slate-950 rounded border border-slate-850">
                  <span className="text-emerald-400 font-bold">✓</span> Error Visibility
                </div>
                <div className="p-3 bg-slate-950 rounded border border-slate-850">
                  <span className="text-emerald-400 font-bold">✓</span> Health Signals
                </div>
                <div className="p-3 bg-slate-950 rounded border border-slate-850">
                  <span className="text-emerald-400 font-bold">✓</span> Request Tracing
                </div>
                <div className="p-3 bg-slate-950 rounded border border-slate-850">
                  <span className="text-emerald-400 font-bold">✓</span> Mission Telemetry
                </div>
                <div className="p-3 bg-slate-950 rounded border border-slate-850">
                  <span className="text-emerald-400 font-bold">✓</span> Security Audit Trail
                </div>
                <div className="p-3 bg-slate-950 rounded border border-slate-850">
                  <span className="text-emerald-400 font-bold">✓</span> Evidence Ledger
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 10. Dependencies */}
        {activeSubtab === 'dependencies' && (
          <div className="space-y-4">
            <div className="p-4 bg-slate-900/60 rounded-lg border border-slate-800">
              <h3 className="text-sm font-bold text-slate-200 mb-3">Dependency Readiness & Supply Chain Invariants</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs font-mono mb-4">
                <div className="p-3 bg-slate-950 rounded border border-slate-850">
                  <div className="text-slate-400">Lockfile Consistency</div>
                  <div className="text-emerald-400 font-bold mt-1">100% Consistent</div>
                </div>
                <div className="p-3 bg-slate-950 rounded border border-slate-850">
                  <div className="text-slate-400">Unpinned Dependencies</div>
                  <div className="text-slate-200 font-bold mt-1">0 Unpinned</div>
                </div>
                <div className="p-3 bg-slate-950 rounded border border-slate-850">
                  <div className="text-slate-400">Auto-Install Invariant</div>
                  <div className="text-emerald-400 font-bold mt-1">No Unvetted Packages</div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 11. Rollback Readiness */}
        {activeSubtab === 'rollback' && (
          <div className="space-y-4">
            <div className="p-4 bg-slate-900/60 rounded-lg border border-slate-800">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-bold text-slate-200">Phase 65 Transactional Rollback Readiness</h3>
                <span className="px-2 py-0.5 text-xs font-mono bg-emerald-950 text-emerald-400 border border-emerald-700/50 rounded">
                  ROLLBACK_READY
                </span>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs font-mono mb-4">
                <div className="p-3 bg-slate-950 rounded border border-slate-850">
                  <div className="text-slate-400">Rollback Snapshot</div>
                  <div className="text-emerald-400 font-bold mt-1">Verified (chk-74a)</div>
                </div>
                <div className="p-3 bg-slate-950 rounded border border-slate-850">
                  <div className="text-slate-400">Artifact Availability</div>
                  <div className="text-emerald-400 font-bold mt-1">All 21 present</div>
                </div>
                <div className="p-3 bg-slate-950 rounded border border-slate-850">
                  <div className="text-slate-400">Migration Reversibility</div>
                  <div className="text-emerald-400 font-bold mt-1">100% Reversible</div>
                </div>
                <div className="p-3 bg-slate-950 rounded border border-slate-850">
                  <div className="text-slate-400">Drill Tested</div>
                  <div className="text-emerald-400 font-bold mt-1">Passed (42ms)</div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 12. Release Plan */}
        {activeSubtab === 'plan' && (
          <div className="space-y-4">
            <div className="p-4 bg-slate-900/60 rounded-lg border border-slate-800">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-bold text-slate-200">Release Execution DAG</h3>
                <span className="px-2 py-0.5 text-xs font-mono bg-amber-950 text-amber-300 border border-amber-700/50 rounded">
                  DEPLOYMENT_NOT_AVAILABLE
                </span>
              </div>
              <div className="flex flex-wrap gap-2 text-xs font-mono mb-4">
                {['PREPARE', 'PRE_RELEASE_VERIFY', 'SNAPSHOT', 'DEPLOY/START', 'HEALTHCHECK', 'CANARY', 'OBSERVE', 'VERIFY', 'PROMOTE'].map((step, idx) => (
                  <div key={step} className={`px-2.5 py-1.5 rounded border ${idx < 3 ? 'bg-emerald-950/40 border-emerald-700/50 text-emerald-300' : (idx === 3 ? 'bg-amber-950/40 border-amber-700/50 text-amber-300' : 'bg-slate-950 border-slate-800 text-slate-500')}`}>
                    {idx + 1}. {step}
                  </div>
                ))}
              </div>
              <div className="p-3 bg-amber-950/20 border border-amber-800/40 rounded text-xs text-amber-300 font-mono">
                Notice: Physical deployment runner is not configured. Emitting DEPLOYMENT_NOT_AVAILABLE rather than faking live deployment.
              </div>
            </div>
          </div>
        )}

        {/* 13. Release Gate */}
        {activeSubtab === 'gate' && (
          <div className="space-y-4">
            <div className="p-4 bg-slate-900/60 rounded-lg border border-slate-800">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-base font-bold text-slate-100">Release Gate Final Determination</h3>
                  <p className="text-xs text-slate-400 font-mono">Synthesizing 11-dimensional risk vector and empirical evidence</p>
                </div>
                <div className="text-right">
                  <div className="px-3 py-1 bg-amber-950 text-amber-300 border border-amber-600 rounded text-sm font-mono font-bold">
                    RELEASE_READY_WITH_RISK
                  </div>
                  <div className="text-[11px] text-slate-400 font-mono mt-1">Allowed with Governance Risk</div>
                </div>
              </div>

              {/* 11 Dimensions Grid */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2.5 text-xs font-mono mb-4">
                {[
                  { name: 'Security', val: 0.05, status: 'SAFE' },
                  { name: 'Quality', val: 0.08, status: 'SAFE' },
                  { name: 'Architecture', val: 0.12, status: 'SAFE' },
                  { name: 'Behavior', val: 0.05, status: 'SAFE' },
                  { name: 'Contract', val: 0.05, status: 'SAFE' },
                  { name: 'Performance', val: 0.10, status: 'SAFE' },
                  { name: 'Runtime', val: 0.05, status: 'SAFE' },
                  { name: 'Configuration', val: 0.05, status: 'SAFE' },
                  { name: 'Dependency', val: 0.08, status: 'SAFE' },
                  { name: 'Rollback', val: 0.05, status: 'SAFE' },
                  { name: 'Observability', val: 0.15, status: 'MODERATE' },
                ].map((d) => (
                  <div key={d.name} className="p-2.5 bg-slate-950 rounded border border-slate-850">
                    <div className="flex justify-between text-slate-400">
                      <span>{d.name}</span>
                      <span className="text-emerald-400">{d.val}</span>
                    </div>
                    <div className="w-full bg-slate-800 h-1.5 rounded-full mt-2 overflow-hidden">
                      <div className="bg-emerald-500 h-full rounded-full" style={{ width: `${d.val * 100}%` }}></div>
                    </div>
                  </div>
                ))}
              </div>

              <div className="p-3 bg-slate-950 rounded border border-slate-850 text-xs font-mono text-slate-400 flex justify-between items-center">
                <span>Cryptographic Digest: <code className="text-indigo-300">d41d8cd98f00b204e9800998ecf8427e</code></span>
                <span className="text-slate-500">Evaluated: 2026-09-19T18:05:00Z</span>
              </div>
            </div>
          </div>
        )}

        {/* 14. Blocked / Review State */}
        {activeSubtab === 'blocked' && (
          <div className="space-y-4">
            <div className="p-4 bg-slate-900/60 rounded-lg border border-slate-800">
              <h3 className="text-sm font-bold text-slate-200 mb-3">Human Review Ticket & Blocker Resolution</h3>
              
              <div className="p-4 bg-amber-950/20 border border-amber-800/40 rounded-lg mb-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-mono text-amber-300 font-bold flex items-center">
                    <Clock className="w-3.5 h-3.5 mr-1" /> TICKET #HR-9042: PHYSICAL DEPLOYMENT UNAVAILABLE
                  </span>
                  <span className="px-2 py-0.5 bg-amber-900/40 text-amber-300 rounded text-xs font-mono">
                    TIMEOUT: 3410s
                  </span>
                </div>
                <p className="text-xs text-slate-300 font-mono mb-3">
                  Reason: Physical production deployment target unavailable in offline local verification environment. Release promotion halted pending explicit signoff.
                </p>
                <div className="flex space-x-2">
                  <button className="px-3 py-1 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-xs font-mono font-bold">
                    Approve (Ready With Risk)
                  </button>
                  <button className="px-3 py-1 bg-rose-700 hover:bg-rose-600 text-white rounded text-xs font-mono font-bold">
                    Reject (Block Release)
                  </button>
                </div>
              </div>

              <div className="p-3 bg-slate-950 rounded border border-slate-850 text-xs font-mono text-slate-400">
                Invariant: If a Human Review Ticket reaches timeout, the release candidate immediately transitions to <span className="text-rose-400 font-bold">BLOCKED</span>.
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
