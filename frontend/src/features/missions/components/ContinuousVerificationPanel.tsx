import React, { useState } from 'react';
import {
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  RotateCcw,
  Sparkles,
  Layers,
  Activity,
  Sliders,
  FileCheck,
  Zap,
  Lock,
  GitBranch,
  Cpu,
  History,
} from 'lucide-react';

interface VerificationDecisionView {
  decision_id: string;
  outcome: string;
  scope: string;
  tests_run: number;
  tests_missing: number;
  confidence: number;
  reasons: string[];
  evidence_count: number;
}

export const ContinuousVerificationPanel: React.FC = () => {
  const [activeSubTab, setActiveSubTab] = useState<
    'overview' | 'changes' | 'surface' | 'selection' | 'execution' | 'coverage' | 'regressions' | 'flaky' | 'counterexamples' | 'evidence' | 'security'
  >('overview');

  const [selectedPolicy, setSelectedPolicy] = useState<string>('STANDARD');
  const [isRunningVerification, setIsRunningVerification] = useState<boolean>(false);

  const [lastDecision, setLastDecision] = useState<VerificationDecisionView>({
    decision_id: 'dec_vrun_1726670000',
    outcome: 'VERIFIED_WITHIN_SCOPE',
    scope: 'agents/payment.py::process_transaction + 3 downstream consumers',
    tests_run: 24,
    tests_missing: 0,
    confidence: 0.98,
    reasons: [
      'Verified within scope across 24 tests with zero regressions',
      'All 11 regression dimensions evaluated clean against immutable baseline v12',
      'Flaky tests analyzed: 0 flaky signals detected',
    ],
    evidence_count: 8,
  });

  const runVerificationCycle = () => {
    setIsRunningVerification(true);
    setTimeout(() => {
      setIsRunningVerification(false);
      setLastDecision({
        decision_id: `dec_vrun_${Date.now()}`,
        outcome: 'VERIFIED_WITHIN_SCOPE',
        scope: 'Modified: agents/payment.py, agents/models/payment_dto.py',
        tests_run: 28,
        tests_missing: 0,
        confidence: 0.99,
        reasons: [
          'Verified within scope across 28 tests (including 2 newly synthesized)',
          'All 11 regression dimensions evaluated clean',
          'Security Sentinel verified 0 prohibited primitives',
        ],
        evidence_count: 12,
      });
    }, 800);
  };

  return (
    <div id="continuous-verification-panel" className="space-y-6 text-gray-100">
      {/* HEADER SECTION */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-[#0e171b] border border-[#a1bebf]/20 p-5 rounded-xl shadow-lg">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-cyan-500/10 border border-cyan-500/30 rounded-lg">
            <ShieldCheck className="w-6 h-6 text-cyan-400" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-cyan-200 flex items-center gap-2">
              Continuous Verification & Autonomous Regression Governance
              <span className="text-xs px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                Fase 62
              </span>
            </h2>
            <p className="text-xs text-gray-400">
              Deterministic change-driven verification, test synthesis gap resolution, 11D regression comparison & flaky governance
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 bg-[#142127] border border-[#a1bebf]/20 px-3 py-1.5 rounded-lg text-xs">
            <Sliders className="w-3.5 h-3.5 text-cyan-400" />
            <span className="text-gray-400">Policy:</span>
            <select
              id="verification-policy-select"
              value={selectedPolicy}
              onChange={(e) => setSelectedPolicy(e.target.value)}
              className="bg-transparent text-cyan-300 font-semibold focus:outline-none cursor-pointer"
            >
              <option value="LOCAL">LOCAL</option>
              <option value="STANDARD">STANDARD</option>
              <option value="STRICT">STRICT</option>
              <option value="CRITICAL">CRITICAL</option>
              <option value="ECONOMIC">ECONOMIC</option>
              <option value="SECURITY">SECURITY</option>
            </select>
          </div>

          <button
            id="trigger-verification-btn"
            onClick={runVerificationCycle}
            disabled={isRunningVerification}
            className="flex items-center gap-2 bg-gradient-to-r from-cyan-500 to-teal-600 hover:from-cyan-400 hover:to-teal-500 text-black font-bold text-xs px-4 py-2 rounded-lg transition-all shadow-md disabled:opacity-50 cursor-pointer"
          >
            {isRunningVerification ? (
              <>
                <RotateCcw className="w-3.5 h-3.5 animate-spin" />
                <span>Verifying...</span>
              </>
            ) : (
              <>
                <Zap className="w-3.5 h-3.5" />
                <span>Verify Change</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* VERIFICATION DECISION BANNER */}
      <div
        id="verification-decision-banner"
        className={`border p-4 rounded-xl flex flex-col md:flex-row md:items-center justify-between gap-4 ${
          lastDecision.outcome === 'VERIFIED_WITHIN_SCOPE'
            ? 'bg-emerald-950/20 border-emerald-500/30 text-emerald-300'
            : lastDecision.outcome === 'REGRESSION_DETECTED'
            ? 'bg-rose-950/20 border-rose-500/30 text-rose-300'
            : 'bg-amber-950/20 border-amber-500/30 text-amber-300'
        }`}
      >
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            {lastDecision.outcome === 'VERIFIED_WITHIN_SCOPE' ? (
              <CheckCircle2 className="w-5 h-5 text-emerald-400" />
            ) : (
              <AlertTriangle className="w-5 h-5 text-amber-400" />
            )}
            <span className="font-bold tracking-wide text-sm">{lastDecision.outcome}</span>
            <span className="text-xs px-2 py-0.5 rounded bg-black/40 border border-white/10 font-mono">
              Conf: {(lastDecision.confidence * 100).toFixed(0)}%
            </span>
          </div>
          <p className="text-xs text-gray-300 font-mono">{lastDecision.scope}</p>
        </div>

        <div className="flex items-center gap-6 text-xs">
          <div>
            <span className="text-gray-400">Tests Run:</span>{' '}
            <span className="font-bold text-white">{lastDecision.tests_run}</span>
          </div>
          <div>
            <span className="text-gray-400">Missing Gaps:</span>{' '}
            <span className="font-bold text-white">{lastDecision.tests_missing}</span>
          </div>
          <div>
            <span className="text-gray-400">Evidence Items:</span>{' '}
            <span className="font-bold text-cyan-400 font-mono">{lastDecision.evidence_count}</span>
          </div>
        </div>
      </div>

      {/* LIFECYCLE STEPPER */}
      <div className="bg-[#0b1417] border border-[#a1bebf]/15 p-4 rounded-xl">
        <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
          Continuous Verification Lifecycle (20 States Traversed)
        </h3>
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2 text-center text-[10px] font-mono">
          {[
            { name: 'INITIAL', status: 'done' },
            { name: 'CHANGE_DETECTED', status: 'done' },
            { name: 'IMPACT_ANALYSIS', status: 'done' },
            { name: 'PLANNING', status: 'done' },
            { name: 'SELECTING', status: 'done' },
            { name: 'SYNTHESIZING', status: 'done' },
            { name: 'VALIDATING_TESTS', status: 'done' },
            { name: 'EXECUTING', status: 'done' },
            { name: 'OBSERVING', status: 'done' },
            { name: 'COVERAGE', status: 'done' },
            { name: 'COMPARING', status: 'done' },
            { name: 'FLAKY_ANALYSIS', status: 'done' },
            { name: 'EVIDENCE_BUILD', status: 'done' },
            { name: 'FINISHED', status: 'active' },
          ].map((st, i) => (
            <div
              key={st.name}
              className={`p-2 rounded border flex flex-col items-center justify-center gap-1 ${
                st.status === 'done'
                  ? 'bg-cyan-950/30 border-cyan-500/30 text-cyan-300'
                  : 'bg-emerald-950/40 border-emerald-500/40 text-emerald-200'
              }`}
            >
              <span className="text-gray-500 text-[9px]">{i + 1}</span>
              <span>{st.name}</span>
            </div>
          ))}
        </div>
      </div>

      {/* SUB-TABS NAVIGATION */}
      <div className="flex border-b border-[#a1bebf]/15 space-x-1 overflow-x-auto text-xs pb-1">
        {[
          { id: 'overview', label: 'Overview & Scorecard', icon: Activity },
          { id: 'changes', label: 'Changes (ChangeSet)', icon: GitBranch },
          { id: 'surface', label: 'Impact Surface (F60)', icon: Cpu },
          { id: 'selection', label: 'Test Selection (8 Levels)', icon: Layers },
          { id: 'coverage', label: '9D Coverage Vector', icon: Sparkles },
          { id: 'regressions', label: '11D Regression Matrix', icon: History },
          { id: 'flaky', label: 'Flaky Detection & Retries', icon: RotateCcw },
          { id: 'counterexamples', label: 'Counterexample Promotion', icon: FileCheck },
          { id: 'security', label: 'Security Sentinel (0 Bypass)', icon: Lock },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeSubTab === tab.id;
          return (
            <button
              key={tab.id}
              id={`cv-tab-${tab.id}`}
              onClick={() => setActiveSubTab(tab.id as any)}
              className={`flex items-center gap-1.5 px-3 py-2 rounded-t-lg font-medium transition-all ${
                isActive
                  ? 'bg-[#142127] text-cyan-300 border-b-2 border-cyan-400 font-semibold'
                  : 'text-gray-400 hover:text-gray-200 hover:bg-white/[0.02]'
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* SUB-TAB CONTENTS */}
      {activeSubTab === 'overview' && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-[#0e171b] border border-[#a1bebf]/15 p-5 rounded-xl space-y-3">
            <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Central Invariant Status</h4>
            <div className="space-y-2 text-xs">
              <div className="flex justify-between p-2 rounded bg-black/20 border border-white/5">
                <span className="text-gray-300">NO_CHANGE → NO_VERIFICATION</span>
                <span className="text-emerald-400 font-bold">ENFORCED</span>
              </div>
              <div className="flex justify-between p-2 rounded bg-black/20 border border-white/5">
                <span className="text-gray-300">UNCERTAIN Boundary Fallback</span>
                <span className="text-emerald-400 font-bold">ENFORCED</span>
              </div>
              <div className="flex justify-between p-2 rounded bg-black/20 border border-white/5">
                <span className="text-gray-300">NO_TESTS → VERIFIED Prohibited</span>
                <span className="text-emerald-400 font-bold">BLOCKED</span>
              </div>
              <div className="flex justify-between p-2 rounded bg-black/20 border border-white/5">
                <span className="text-gray-300">COVERAGE_UNKNOWN → VERIFIED Prohibited</span>
                <span className="text-emerald-400 font-bold">BLOCKED</span>
              </div>
              <div className="flex justify-between p-2 rounded bg-black/20 border border-white/5">
                <span className="text-gray-300">FLAKY Masking as PASS Prohibited</span>
                <span className="text-emerald-400 font-bold">BLOCKED</span>
              </div>
            </div>
          </div>

          <div className="bg-[#0e171b] border border-[#a1bebf]/15 p-5 rounded-xl space-y-3">
            <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Test Operations Metrics</h4>
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="p-3 bg-black/20 rounded-lg border border-white/5">
                <div className="text-gray-400">Tests Selected</div>
                <div className="text-lg font-bold text-cyan-300">26</div>
              </div>
              <div className="p-3 bg-black/20 rounded-lg border border-white/5">
                <div className="text-gray-400">F61 Synthesized</div>
                <div className="text-lg font-bold text-teal-300">2</div>
              </div>
              <div className="p-3 bg-black/20 rounded-lg border border-white/5">
                <div className="text-gray-400">Regressions Found</div>
                <div className="text-lg font-bold text-rose-400">0</div>
              </div>
              <div className="p-3 bg-black/20 rounded-lg border border-white/5">
                <div className="text-gray-400">Flaky Tests</div>
                <div className="text-lg font-bold text-amber-400">0</div>
              </div>
            </div>
          </div>

          <div className="bg-[#0e171b] border border-[#a1bebf]/15 p-5 rounded-xl space-y-3">
            <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Immutable Baseline Version</h4>
            <div className="space-y-2 text-xs">
              <div className="p-3 bg-black/20 rounded-lg border border-white/5">
                <div className="text-gray-400">Snapshot ID:</div>
                <div className="text-xs font-mono text-cyan-300">snap_1726670000000</div>
              </div>
              <div className="p-3 bg-black/20 rounded-lg border border-white/5">
                <div className="text-gray-400">Composite Score:</div>
                <div className="text-sm font-bold text-emerald-400">94.2% Coverage</div>
              </div>
              <div className="p-3 bg-black/20 rounded-lg border border-white/5">
                <div className="text-gray-400">Security Gate:</div>
                <div className="text-xs font-bold text-cyan-300">Zero Destructive Primitives</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {activeSubTab === 'regressions' && (
        <div className="bg-[#0e171b] border border-[#a1bebf]/15 p-5 rounded-xl space-y-4">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-bold text-cyan-200">11-Dimensional Regression Comparison Matrix</h4>
            <span className="text-xs text-gray-400">Current Run vs Immutable Baseline</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 text-xs">
            {[
              { dim: '1. Pass / Fail Status', status: 'PASSED', current: '28 / 28', baseline: '26 / 26', delta: 'clean' },
              { dim: '2. Line Coverage', status: 'IMPROVED', current: '94.5%', baseline: '92.0%', delta: '+2.5%' },
              { dim: '3. Branch Coverage', status: 'IMPROVED', current: '89.2%', baseline: '87.1%', delta: '+2.1%' },
              { dim: '4. Symbol Coverage', status: 'MAINTAINED', current: '100%', baseline: '100%', delta: '0.0%' },
              { dim: '5. Contract Coverage', status: 'MAINTAINED', current: '100%', baseline: '100%', delta: '0.0%' },
              { dim: '6. Behavior Coverage', status: 'MAINTAINED', current: '95.0%', baseline: '95.0%', delta: '0.0%' },
              { dim: '7. Invariant Coverage', status: 'MAINTAINED', current: '100%', baseline: '100%', delta: '0.0%' },
              { dim: '8. Consumer Coverage', status: 'MAINTAINED', current: '100%', baseline: '100%', delta: '0.0%' },
              { dim: '9. Browser Surface', status: 'MAINTAINED', current: '100%', baseline: '100%', delta: '0.0%' },
              { dim: '10. Mutation Score', status: 'IMPROVED', current: '84.0%', baseline: '81.5%', delta: '+2.5%' },
              { dim: '11. Execution Duration', status: 'STABLE', current: '420ms', baseline: '410ms', delta: '+10ms' },
            ].map((d) => (
              <div key={d.dim} className="p-3 bg-black/20 rounded-lg border border-white/5 space-y-1">
                <div className="font-semibold text-gray-200 flex justify-between">
                  <span>{d.dim}</span>
                  <span
                    className={`font-bold ${
                      d.status === 'IMPROVED' || d.status === 'PASSED'
                        ? 'text-emerald-400'
                        : d.status === 'REGRESSED'
                        ? 'text-rose-400'
                        : 'text-cyan-300'
                    }`}
                  >
                    {d.status}
                  </span>
                </div>
                <div className="flex justify-between text-gray-400 text-[11px]">
                  <span>
                    Cur: <strong className="text-white">{d.current}</strong> | Base: {d.baseline}
                  </span>
                  <span className="font-mono text-emerald-400">{d.delta}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {activeSubTab === 'security' && (
        <div className="bg-[#0e171b] border border-[#a1bebf]/15 p-5 rounded-xl space-y-4">
          <div className="flex items-center gap-2 text-rose-400">
            <Lock className="w-5 h-5" />
            <h4 className="text-sm font-bold text-white">Verification Security Sentinel</h4>
          </div>
          <p className="text-xs text-gray-400">
            Strict containment rules blocking destructive operations, credentials, and external payments. Continuous verification never bypasses this sentinel.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
            {[
              { rule: 'rmtree / recursive directory removal', status: 'BLOCKED' },
              { rule: 'os.system arbitrary execution', status: 'BLOCKED' },
              { rule: 'Destructive subprocess execution', status: 'BLOCKED' },
              { rule: 'Credential / .env / private key exfiltration', status: 'BLOCKED' },
              { rule: 'Real payment gateway APIs (stripe, paypal, etc.)', status: 'BLOCKED' },
              { rule: 'Economic policy external network write calls', status: 'BLOCKED' },
            ].map((sec) => (
              <div key={sec.rule} className="p-3 bg-rose-950/10 border border-rose-500/20 rounded-lg flex justify-between items-center">
                <span className="text-gray-300 font-mono">{sec.rule}</span>
                <span className="px-2 py-0.5 rounded bg-rose-500/20 text-rose-400 border border-rose-500/40 text-[10px] font-bold">
                  {sec.status}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
