import React, { useState } from 'react';
import {
  ShieldCheck,
  ShieldAlert,
  AlertTriangle,
  CheckCircle2,
  GitCompare,
  RotateCcw,
  Activity,
  Brain,
  HelpCircle,
  FileCode,
  Users,
  Check,
  Clock,
  Lock,
} from 'lucide-react';

export interface ContractHealthPanelProps {
  missionId?: string;
}

export const FALLBACK_GOVERNANCE_DATA = {
  monitored_contracts_count: 5,
  in_sync_count: 2,
  drifting_count: 1,
  breaking_count: 1,
  uncertain_count: 1,
  drift_events_count: 3,
  non_breaking_drift_count: 1,
  potentially_breaking_drift_count: 0,
  breaking_drift_count: 1,
  uncertain_drift_count: 1,
  security_sentinel: {
    status: 'SECURE',
    prompt_injections_blocked: 5,
    command_injections_blocked: 3,
    forged_signatures_prevented: 2,
    baseline_hashes_verified: 5,
    passive_data_enforced: true,
  },
  contracts: [
    {
      contract_id: 'ctr_users_v1',
      route: '/api/v1/users/search',
      method: 'GET',
      active_version: '1.0.0',
      schema_hash: 'a8f5e1b2c3d4e5f67890abcdef1234567890abcdef1234567890abcdef123456',
      status: 'NON_BREAKING_DRIFT',
      environment: 'PRODUCTION',
      sample_count: 1420,
      confidence: 0.98,
      temporal_status: 'CURRENT',
      last_validated: '2026-09-12T14:00:00Z',
      validated_by: 'lead_architect',
      consumers_count: 3,
      risk_level: 'LOW',
      changes_summary: "Optional field 'user_tier' observed in 88% of requests",
    },
    {
      contract_id: 'ctr_auth_v1',
      route: '/api/v1/auth/token',
      method: 'POST',
      active_version: '1.0.0',
      schema_hash: 'b7e4d2a1f0c9e8d76543ba9876fedcba0987654321fedcba0987654321fedcba',
      status: 'IN_SYNC',
      environment: 'PRODUCTION',
      sample_count: 890,
      confidence: 0.99,
      temporal_status: 'CURRENT',
      last_validated: '2026-09-12T13:30:00Z',
      validated_by: 'security_officer',
      consumers_count: 4,
      risk_level: 'NONE',
      changes_summary: 'Zero deviations observed. 100% compliant with baseline.',
    },
    {
      contract_id: 'ctr_reports_v1',
      route: '/api/v1/reports/export',
      method: 'POST',
      active_version: '1.0.0',
      schema_hash: 'c6d3b0e9f8a7d6c543210fedcba9876543210fedcba9876543210fedcba98765',
      status: 'BREAKING_DRIFT',
      environment: 'PRODUCTION',
      sample_count: 340,
      confidence: 0.95,
      temporal_status: 'DRIFTING',
      last_validated: '2026-09-10T10:00:00Z',
      validated_by: 'lead_architect',
      consumers_count: 4,
      risk_level: 'CRITICAL',
      changes_summary: "BREAKING: Response field 'format' changed type from STRING to OBJECT",
    },
    {
      contract_id: 'ctr_billing_v1',
      route: '/api/v1/billing/invoices',
      method: 'GET',
      active_version: '1.0.0',
      schema_hash: 'd5c2a9e8f7b6c5d43210fedcba9876543210fedcba9876543210fedcba98765',
      status: 'IN_SYNC',
      environment: 'PRODUCTION',
      sample_count: 210,
      confidence: 0.97,
      temporal_status: 'CURRENT',
      last_validated: '2026-09-11T16:00:00Z',
      validated_by: 'finance_engineer',
      consumers_count: 2,
      risk_level: 'NONE',
      changes_summary: 'Fully compliant with baseline schema.',
    },
    {
      contract_id: 'ctr_telemetry_v0',
      route: '/api/v0/telemetry/metrics',
      method: 'GET',
      active_version: '0.1.0',
      schema_hash: 'e4b1a8f7e6d5c4b3210fedcba9876543210fedcba9876543210fedcba98765',
      status: 'UNCERTAIN_DRIFT',
      environment: 'DEVELOPMENT',
      sample_count: 4,
      confidence: 0.42,
      temporal_status: 'STALE',
      last_validated: '2026-09-08T09:00:00Z',
      validated_by: 'devops_engineer',
      consumers_count: 1,
      risk_level: 'MEDIUM',
      changes_summary: 'Stale contract: No traffic in >48h and sporadic 404 responses.',
    },
  ],
  drift_events: [
    {
      drift_id: 'drift_01_users',
      contract_id: 'ctr_users_v1',
      baseline_version: '1.0.0',
      observed_version: '1.1.0-observed',
      classification: 'NON_BREAKING',
      status: 'NON_BREAKING_DRIFT',
      variation_type: 'SYSTEMATIC_DRIFT',
      recommended_action: 'MONITOR',
      environment: 'PRODUCTION',
      sample_count: 1420,
      confidence: 0.98,
      temporal_status: 'CURRENT',
      why_drift: "Backend service added optional 'user_tier' field to support enterprise multi-tenancy without breaking existing consumers.",
      what_changed: "Response object gained 'user_tier': string (optional, observed in 88% of requests).",
      who_is_affected: 'Downstream consumers can safely ignore the new field. Frontend SearchBox component may adopt it.',
      what_should_happen: 'System continues monitoring. No human intervention or contract freeze required.',
      changes: [
        {
          field_path: 'response.user_tier',
          drift_type: 'FIELD_ADDED',
          classification: 'NON_BREAKING',
          baseline_value: null,
          observed_value: 'string',
          observed_frequency: 0.88,
          baseline_frequency: 0.0,
          sample_count: 1420,
          message: "Optional field 'user_tier' (string) observed in response",
        },
      ],
      affected_consumers: [
        { consumer_id: 'SearchBox.tsx', consumer_type: 'FRONTEND_COMPONENT', impact_level: 'DIRECT', description: 'React SearchBox component consumes search response' },
        { consumer_id: 'users_router.py', consumer_type: 'BACKEND_SERVICE', impact_level: 'DIRECT', description: 'FastAPI router implementation' },
        { consumer_id: 'test_users_api.py', consumer_type: 'TEST', impact_level: 'INDIRECT', description: 'Pytest API suite' },
      ],
    },
    {
      drift_id: 'drift_02_reports',
      contract_id: 'ctr_reports_v1',
      baseline_version: '1.0.0',
      observed_version: '2.0.0-proposed',
      classification: 'BREAKING',
      status: 'BREAKING_DRIFT',
      variation_type: 'SYSTEMATIC_DRIFT',
      recommended_action: 'REQUEST_HUMAN',
      environment: 'PRODUCTION',
      sample_count: 340,
      confidence: 0.95,
      temporal_status: 'DRIFTING',
      why_drift: "Backend refactoring changed 'format' from primitive string ('csv'|'pdf') to structured object ({ type: string, compress: bool }).",
      what_changed: "Response field 'format' altered type from STRING to OBJECT. Required by new backend workers.",
      who_is_affected: 'Frontend ExportReportModal expects string format; will encounter runtime TypeError if unmigrated.',
      what_should_happen: 'Block automatic deployment, create Proposed Contract v2.0.0, and require explicit Human Approval before activation.',
      changes: [
        {
          field_path: 'response.format',
          drift_type: 'TYPE_CHANGED',
          classification: 'BREAKING',
          baseline_value: 'STRING',
          observed_value: 'OBJECT ({ type: str, compress: bool })',
          observed_frequency: 1.0,
          baseline_frequency: 1.0,
          sample_count: 340,
          message: 'Type conflict: baseline specifies STRING, runtime produces OBJECT',
        },
      ],
      affected_consumers: [
        { consumer_id: 'ExportReportModal.tsx', consumer_type: 'FRONTEND_COMPONENT', impact_level: 'DIRECT', description: 'Export modal rendering format selection and parser' },
        { consumer_id: 'ReportGeneratorService.py', consumer_type: 'BACKEND_SERVICE', impact_level: 'DIRECT', description: 'FastAPI report background worker' },
        { consumer_id: 'test_report_exports.py', consumer_type: 'TEST', impact_level: 'DIRECT', description: 'Pytest test suite expecting string format' },
        { consumer_id: 'browser_qa_reports.py', consumer_type: 'BROWSER_SCENARIO', impact_level: 'POTENTIAL', description: 'Playwright QA scenario' },
      ],
      proposed_version: {
        proposal_id: 'prop_v2_reports',
        parent_version: '1.0.0',
        new_version: '2.0.0',
        status: 'PENDING_APPROVAL',
        migration_impact: 'Requires frontend adapter update in ExportReportModal.tsx and test suite update.',
        approval_required: true,
      },
    },
    {
      drift_id: 'drift_03_telemetry',
      contract_id: 'ctr_telemetry_v0',
      baseline_version: '0.1.0',
      observed_version: '0.1.0-stale',
      classification: 'UNCERTAIN',
      status: 'UNCERTAIN_DRIFT',
      variation_type: 'ONE_OFF_VARIATION',
      recommended_action: 'REQUEST_VALIDATION',
      environment: 'DEVELOPMENT',
      sample_count: 4,
      confidence: 0.42,
      temporal_status: 'STALE',
      why_drift: 'Legacy telemetry endpoint has had zero production traffic in 72h and sporadic 404s in development.',
      what_changed: 'Endpoint missing or decommissioned in newer backend builds.',
      who_is_affected: 'Legacy dashboard widgets calling /api/v0/telemetry/metrics.',
      what_should_happen: 'Validate whether endpoint is officially deprecated and schedule deprecation lifecycle.',
      changes: [
        {
          field_path: 'route.status',
          drift_type: 'STATUS_CHANGED',
          classification: 'UNCERTAIN',
          baseline_value: 200,
          observed_value: 404,
          observed_frequency: 0.5,
          baseline_frequency: 1.0,
          sample_count: 4,
          message: 'Sporadic 404 responses observed in development traffic',
        },
      ],
      affected_consumers: [
        { consumer_id: 'LegacyMetricsWidget.tsx', consumer_type: 'FRONTEND_COMPONENT', impact_level: 'DIRECT', description: 'Legacy telemetry widget' },
      ],
    },
  ],
};

export const ContractHealthPanel: React.FC<ContractHealthPanelProps> = () => {
  const [activeTab, setActiveTab] = useState<'overview' | 'why' | 'consumers' | 'evolution' | 'security'>('overview');
  const [selectedEnv, setSelectedEnv] = useState<string>('ALL');
  const [data, setData] = useState(FALLBACK_GOVERNANCE_DATA);
  const [selectedDriftId, setSelectedDriftId] = useState<string>('drift_02_reports');
  const [actionFeedback, setActionFeedback] = useState<string | null>(null);

  const activeDrift = data.drift_events.find((d) => d.drift_id === selectedDriftId) || data.drift_events[0];

  const filteredContracts = data.contracts.filter((c) => {
    if (selectedEnv === 'ALL') return true;
    return c.environment.toUpperCase() === selectedEnv.toUpperCase();
  });

  const handleApproveV2 = () => {
    setData((prev) => {
      const updatedContracts = prev.contracts.map((c) => {
        if (c.contract_id === 'ctr_reports_v1') {
          return {
            ...c,
            active_version: '2.0.0',
            status: 'IN_SYNC',
            risk_level: 'NONE',
            changes_summary: 'Evolved to v2.0.0. Fully compliant with new baseline.',
          };
        }
        return c;
      });

      const updatedEvents = prev.drift_events.map((e) => {
        if (e.drift_id === 'drift_02_reports') {
          return {
            ...e,
            status: 'RESOLVED',
            recommended_action: 'MONITOR',
            proposed_version: {
              ...(e.proposed_version as any),
              status: 'APPROVED',
            },
          };
        }
        return e;
      });

      return {
        ...prev,
        contracts: updatedContracts,
        drift_events: updatedEvents,
        breaking_count: Math.max(0, prev.breaking_count - 1),
        in_sync_count: prev.in_sync_count + 1,
      };
    });

    setActionFeedback('Proposta de evolução para v2.0.0 aprovada com sucesso! Contrato ativo atualizado.');
    setTimeout(() => setActionFeedback(null), 4000);
  };

  const handleRollback = () => {
    setData((prev) => {
      const updatedContracts = prev.contracts.map((c) => {
        if (c.contract_id === 'ctr_reports_v1') {
          return {
            ...c,
            active_version: '1.0.0',
            status: 'IN_SYNC',
            risk_level: 'NONE',
            changes_summary: 'Rollback executado para v1.0.0. Histórico v2.0.0 preservado.',
          };
        }
        return c;
      });

      return {
        ...prev,
        contracts: updatedContracts,
      };
    });

    setActionFeedback('Rollback determinístico para v1.0.0 efetuado. Histórico preservado.');
    setTimeout(() => setActionFeedback(null), 4000);
  };

  return (
    <div className="space-y-6" data-testid="contract-health-container">
      {/* HEADER WITH CONTROLS & ENVIRONMENT SELECTOR */}
      <div className="flex flex-col gap-4 rounded-xl border border-cyan-500/20 bg-[#0b1417] p-5 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-lg border border-cyan-400/30 bg-cyan-500/10 text-cyan-300">
            <ShieldCheck className="h-6 w-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-bold text-gray-100">Governação Contínua & Deteção de Drift (Fase 46)</h2>
              <span className="rounded-full bg-cyan-500/10 px-2.5 py-0.5 text-xs font-semibold text-cyan-400 border border-cyan-500/20">
                ACTIVE_GOVERNANCE
              </span>
            </div>
            <p className="text-xs text-gray-400">
              Tri-state separation: CONTRACT ≠ CURRENT RUNTIME BEHAVIOR ≠ OBSERVED VARIATION.
            </p>
          </div>
        </div>

        {/* ENVIRONMENT SELECTOR & ACTIONS */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 text-xs text-gray-400">
            <span>Ambiente:</span>
            <select
              data-testid="environment-filter-select"
              value={selectedEnv}
              onChange={(e) => setSelectedEnv(e.target.value)}
              className="rounded-lg border border-gray-700 bg-gray-900 px-3 py-1.5 text-xs text-gray-200 outline-none focus:border-cyan-500"
            >
              <option value="ALL">Todos os Ambientes</option>
              <option value="PRODUCTION">PRODUCTION (Isolado)</option>
              <option value="STAGING">STAGING</option>
              <option value="DEVELOPMENT">DEVELOPMENT</option>
            </select>
          </div>

          <div className="rounded-lg border border-gray-800 bg-black/40 px-3 py-1.5 text-xs font-mono text-gray-300">
            Baselines: <span className="text-cyan-400 font-bold">{data.monitored_contracts_count}</span>
          </div>
        </div>
      </div>

      {actionFeedback && (
        <div className="flex items-center gap-2 rounded-lg border border-emerald-500/40 bg-emerald-950/20 px-4 py-2.5 text-xs font-medium text-emerald-300">
          <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
          <span>{actionFeedback}</span>
        </div>
      )}

      {/* KPI METRICS OVERVIEW */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div className="rounded-lg border border-emerald-500/20 bg-emerald-950/10 p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-gray-400">In Sync</span>
            <CheckCircle2 className="h-4 w-4 text-emerald-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-emerald-400">{data.in_sync_count}</span>
            <span className="text-xs text-gray-500">contratos 100% conformes</span>
          </div>
        </div>

        <div className="rounded-lg border border-amber-500/20 bg-amber-950/10 p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-gray-400">Drifting (Non-Breaking)</span>
            <AlertTriangle className="h-4 w-4 text-amber-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-amber-400">{data.drifting_count}</span>
            <span className="text-xs text-gray-500">em monitorização contínua</span>
          </div>
        </div>

        <div className="rounded-lg border border-rose-500/20 bg-rose-950/10 p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-gray-400">Breaking Drift</span>
            <ShieldAlert className="h-4 w-4 text-rose-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-rose-400">{data.breaking_count}</span>
            <span className="text-xs text-gray-500">bloqueio preventivo</span>
          </div>
        </div>

        <div className="rounded-lg border border-purple-500/20 bg-purple-950/10 p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-gray-400">Uncertain / Stale</span>
            <HelpCircle className="h-4 w-4 text-purple-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-purple-400">{data.uncertain_count}</span>
            <span className="text-xs text-gray-500">requer revalidação</span>
          </div>
        </div>
      </div>

      {/* SUB-NAVIGATION TABS */}
      <div className="flex border-b border-gray-800 bg-[#0c1619] px-4">
        {[
          { id: 'overview', label: 'Contratos & Baselines', icon: FileCode },
          { id: 'why', label: 'Painel do Porquê ("Why Drift")', icon: Brain },
          { id: 'consumers', label: 'Impacto nos Consumidores', icon: Users },
          { id: 'evolution', label: 'Evolução de Versão & Rollback', icon: GitCompare },
          { id: 'security', label: 'Segurança & Sentinela', icon: Lock },
        ].map((tab) => {
          const isActive = activeTab === tab.id;
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              id={`tab-gov-${tab.id}`}
              onClick={() => setActiveTab(tab.id as any)}
              className={`flex items-center gap-2 border-b-2 px-4 py-3 text-xs font-medium transition-colors ${
                isActive
                  ? 'border-cyan-400 text-cyan-300 bg-cyan-500/5 font-semibold'
                  : 'border-transparent text-gray-400 hover:text-gray-200 hover:bg-white/[0.02]'
              }`}
            >
              <Icon className="h-4 w-4" />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* TAB 1: OVERVIEW & BASELINES */}
      {activeTab === 'overview' && (
        <div className="space-y-4" data-testid="contract-health-overview">
          {/* BREAKING DRIFT ALERT BANNER */}
          {data.breaking_count > 0 && (
            <div
              className="flex flex-col gap-3 rounded-lg border border-rose-500/40 bg-rose-950/20 p-4 md:flex-row md:items-center md:justify-between"
              data-testid="breaking-drift-alert"
            >
              <div className="flex items-start gap-3">
                <ShieldAlert className="h-5 w-5 text-rose-400 shrink-0 mt-0.5" />
                <div>
                  <h4 className="text-sm font-semibold text-rose-300">
                    Alerta de Breaking Contract Drift Detetado: POST /api/v1/reports/export
                  </h4>
                  <p className="text-xs text-rose-400/90 mt-0.5">
                    O campo <code>format</code> sofreu alteração de tipo de STRING para OBJECT no backend. Consumidores existentes (Frontend Modal) falharão se não forem migrados.
                  </p>
                </div>
              </div>
              <button
                onClick={() => {
                  setSelectedDriftId('drift_02_reports');
                  setActiveTab('evolution');
                }}
                className="inline-flex items-center gap-1.5 rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-1.5 text-xs font-semibold text-rose-300 hover:bg-rose-500/20 transition-all shrink-0"
              >
                <span>Analisar Proposta v2.0.0</span>
              </button>
            </div>
          )}

          {/* ACTIVE BASELINES TABLE */}
          <div className="overflow-hidden rounded-xl border border-gray-800 bg-[#0c1619]">
            <div className="border-b border-gray-800 bg-black/30 px-4 py-3">
              <h3 className="text-xs font-semibold text-gray-300 uppercase tracking-wider">
                Baselines de Contrato Verificados ({filteredContracts.length})
              </h3>
            </div>
            <div className="divide-y divide-gray-800/60">
              {filteredContracts.map((c) => {
                const isInSync = c.status === 'IN_SYNC';
                const isBreaking = c.status === 'BREAKING_DRIFT';
                const isNonBreaking = c.status === 'NON_BREAKING_DRIFT';
                const isStale = c.temporal_status === 'STALE';

                return (
                  <div
                    key={c.contract_id}
                    data-testid={
                      isInSync
                        ? 'in-sync-contract-card'
                        : isNonBreaking
                        ? 'observed-non-breaking-drift'
                        : isStale
                        ? 'stale-contract-card'
                        : isBreaking
                        ? 'breaking-contract-card'
                        : undefined
                    }
                    className={`p-4 transition-colors hover:bg-white/[0.02] flex flex-col gap-3 md:flex-row md:items-center md:justify-between ${
                      isBreaking ? 'bg-rose-950/5' : ''
                    }`}
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="rounded bg-gray-800 px-2 py-0.5 font-mono text-[10px] font-bold text-gray-300">
                          {c.method}
                        </span>
                        <span className="font-mono text-sm font-semibold text-gray-200">{c.route}</span>
                        <span className="rounded-full bg-cyan-500/10 border border-cyan-500/20 px-2 py-0.5 text-[10px] font-mono text-cyan-300">
                          v{c.active_version}
                        </span>

                        {isStale && (
                          <span
                            data-testid="stale-contract-badge"
                            className="rounded bg-purple-500/20 border border-purple-500/30 px-2 py-0.5 text-[10px] font-bold text-purple-300"
                          >
                            STALE
                          </span>
                        )}

                        <span
                          className={`rounded px-2 py-0.5 text-[10px] font-bold ${
                            isInSync
                              ? 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-400'
                              : isBreaking
                              ? 'bg-rose-500/10 border border-rose-500/30 text-rose-400'
                              : isNonBreaking
                              ? 'bg-amber-500/10 border border-amber-500/20 text-amber-400'
                              : 'bg-purple-500/10 border border-purple-500/20 text-purple-400'
                          }`}
                        >
                          {c.status}
                        </span>
                      </div>

                      <div className="text-xs text-gray-400 flex flex-wrap items-center gap-4">
                        <span>Amostras: <strong className="text-gray-200">{c.sample_count}</strong></span>
                        <span>Confiança: <strong className="text-cyan-400">{Math.round(c.confidence * 100)}%</strong></span>
                        <span>Consumidores: <strong className="text-gray-200">{c.consumers_count}</strong></span>
                        <span>Ambiente: <strong className="text-gray-300">{c.environment}</strong></span>
                        <span className="text-gray-500">Hash: <code className="text-[10px]">{c.schema_hash.slice(0, 10)}...</code></span>
                      </div>

                      <div className="text-xs text-gray-400 italic">
                        {c.changes_summary}
                      </div>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      <button
                        onClick={() => {
                          const event = data.drift_events.find((d) => d.contract_id === c.contract_id);
                          if (event) setSelectedDriftId(event.drift_id);
                          setActiveTab('why');
                        }}
                        className="rounded-lg border border-gray-700 bg-gray-800/80 px-3 py-1.5 text-xs font-medium text-gray-300 hover:bg-gray-700 transition-colors"
                      >
                        Ver Causalidade
                      </button>

                      {isBreaking && (
                        <button
                          onClick={() => {
                            setSelectedDriftId('drift_02_reports');
                            setActiveTab('evolution');
                          }}
                          className="rounded-lg border border-rose-500/40 bg-rose-500/15 px-3 py-1.5 text-xs font-semibold text-rose-300 hover:bg-rose-500/25 transition-colors"
                        >
                          Gerir Evolução v2
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: WHY PANEL & CAUSALITY */}
      {activeTab === 'why' && (
        <div className="space-y-4" data-testid="why-drift-panel">
          <div className="rounded-xl border border-gray-800 bg-[#0c1619] p-5">
            <div className="flex items-center justify-between border-b border-gray-800 pb-4 mb-4">
              <div>
                <h3 className="text-sm font-bold text-gray-100 flex items-center gap-2">
                  <Brain className="h-4 w-4 text-cyan-400" />
                  <span>Painel Causal do Porquê: {activeDrift.contract_id}</span>
                </h3>
                <p className="text-xs text-gray-400 mt-0.5">
                  Explicação determinística da discrepância observada entre baseline v{activeDrift.baseline_version} e tráfego real.
                </p>
              </div>
              <span
                className={`rounded-full px-3 py-1 text-xs font-bold border ${
                  activeDrift.classification === 'BREAKING'
                    ? 'border-rose-500/40 bg-rose-500/10 text-rose-300'
                    : 'border-amber-500/30 bg-amber-500/10 text-amber-300'
                }`}
              >
                {activeDrift.classification} DRIFT
              </span>
            </div>

            {/* 4 CORE QUESTIONS */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="rounded-lg border border-gray-800/80 bg-black/20 p-4 space-y-1">
                <span className="text-[11px] font-bold text-cyan-400 uppercase tracking-wider">1. Why Drift? (Causa Raiz)</span>
                <p className="text-xs text-gray-200 leading-relaxed">{activeDrift.why_drift}</p>
              </div>

              <div className="rounded-lg border border-gray-800/80 bg-black/20 p-4 space-y-1">
                <span className="text-[11px] font-bold text-amber-400 uppercase tracking-wider">2. What Changed? (Discrepância Concreta)</span>
                <p className="text-xs text-gray-200 leading-relaxed">{activeDrift.what_changed}</p>
              </div>

              <div className="rounded-lg border border-gray-800/80 bg-black/20 p-4 space-y-1">
                <span className="text-[11px] font-bold text-rose-400 uppercase tracking-wider">3. Who is Affected? (Consumidores)</span>
                <p className="text-xs text-gray-200 leading-relaxed">{activeDrift.who_is_affected}</p>
              </div>

              <div className="rounded-lg border border-gray-800/80 bg-black/20 p-4 space-y-1">
                <span className="text-[11px] font-bold text-emerald-400 uppercase tracking-wider">4. What Should Happen? (Ação Recomendada)</span>
                <p className="text-xs text-gray-200 leading-relaxed">{activeDrift.what_should_happen}</p>
              </div>
            </div>

            {/* ERROR AND AUTH DETECTIONS */}
            <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="rounded-lg border border-gray-800 bg-gray-900/50 p-3" data-testid="auth-drift-indicator">
                <div className="flex items-center gap-2 text-xs font-semibold text-gray-300">
                  <Lock className="h-4 w-4 text-emerald-400" />
                  <span>Contrato de Autenticação</span>
                </div>
                <p className="text-xs text-gray-400 mt-1">
                  Cabeçalhos de autorização e tokens em runtime estão estritamente conformes com os requisitos de segurança.
                </p>
              </div>

              <div className="rounded-lg border border-gray-800 bg-gray-900/50 p-3" data-testid="error-contract-drift-alert">
                <div className="flex items-center gap-2 text-xs font-semibold text-gray-300">
                  <AlertTriangle className="h-4 w-4 text-amber-400" />
                  <span>Deteção de Error Contract Drift</span>
                </div>
                <p className="text-xs text-gray-400 mt-1">
                  Nenhuma falha de aplicação (5xx) mascarada como contrato. Contratos de erro (4xx) mapeados.
                </p>
              </div>
            </div>

            {/* DIFF TABLE */}
            <div className="mt-5 overflow-hidden rounded-lg border border-gray-800" data-testid="contract-diff-viewer">
              <div className="border-b border-gray-800 bg-black/40 px-3 py-2 text-xs font-semibold text-gray-300">
                Diff Estrutural de Campos & Tipos
              </div>
              <div className="divide-y divide-gray-800/60 font-mono text-xs">
                {activeDrift.changes.map((ch, idx) => (
                  <div key={idx} className="flex flex-col gap-1 p-3 bg-gray-900/20 md:flex-row md:items-center md:justify-between">
                    <div>
                      <span className="font-bold text-gray-200">{ch.field_path}</span>
                      <span className="ml-2 rounded bg-gray-800 px-1.5 py-0.5 text-[10px] text-gray-400">{ch.drift_type}</span>
                      <p className="text-gray-400 font-sans text-xs mt-0.5">{ch.message}</p>
                    </div>
                    <div className="flex items-center gap-3 text-[11px] shrink-0">
                      <span className="text-gray-500">Baseline: <code className="text-rose-300">{String(ch.baseline_value)}</code></span>
                      <span className="text-gray-500">→</span>
                      <span className="text-gray-500">Runtime: <code className="text-emerald-300">{String(ch.observed_value)}</code></span>
                      <span className="rounded bg-cyan-950 px-2 py-0.5 text-cyan-400 font-bold">{Math.round(ch.observed_frequency * 100)}% freq</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: CONSUMER IMPACT MATRIX */}
      {activeTab === 'consumers' && (
        <div className="space-y-4" data-testid="consumer-impact-matrix">
          <div className="overflow-hidden rounded-xl border border-gray-800 bg-[#0c1619]">
            <div className="border-b border-gray-800 bg-black/30 px-4 py-3 flex items-center justify-between">
              <div>
                <h3 className="text-xs font-semibold text-gray-300 uppercase tracking-wider">
                  Matriz Reversa de Consumidores via Semantic Graph
                </h3>
                <p className="text-xs text-gray-400 mt-0.5">
                  Rastreabilidade direta de componentes dependentes de {activeDrift.contract_id}.
                </p>
              </div>
              <span className="rounded-full bg-cyan-500/10 border border-cyan-500/20 px-2.5 py-0.5 text-xs text-cyan-300 font-mono">
                {activeDrift.affected_consumers.length} Consumidores Localizados
              </span>
            </div>

            <div className="divide-y divide-gray-800/60">
              {activeDrift.affected_consumers.map((c, i) => (
                <div key={i} data-testid="consumer-impact-row" className="p-4 flex items-center justify-between hover:bg-white/[0.01]">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-sm font-semibold text-gray-200">{c.consumer_id}</span>
                      <span className="rounded bg-gray-800 px-2 py-0.5 font-mono text-[10px] text-gray-300">
                        {c.consumer_type}
                      </span>
                      <span
                        className={`rounded px-2 py-0.5 text-[10px] font-bold ${
                          c.impact_level === 'DIRECT'
                            ? 'bg-rose-500/15 border border-rose-500/30 text-rose-300'
                            : 'bg-amber-500/15 border border-amber-500/30 text-amber-300'
                        }`}
                      >
                        {c.impact_level}
                      </span>
                    </div>
                    <p className="text-xs text-gray-400">{c.description}</p>
                  </div>
                  <div className="text-xs text-gray-500 font-mono">
                    status: <span className="text-emerald-400">TRACKED</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* TAB 4: VERSION EVOLUTION & ROLLBACK */}
      {activeTab === 'evolution' && (
        <div className="space-y-5">
          {/* PROPOSED V2 CARD */}
          <div className="rounded-xl border border-cyan-500/30 bg-[#0c1619] p-5 shadow-lg" data-testid="proposed-v2-card">
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between border-b border-gray-800 pb-4">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                  <GitCompare className="h-5 w-5" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-bold text-gray-100">Proposta de Evolução Contratual: v1.0.0 → v2.0.0</h3>
                    <span className="rounded bg-rose-500/20 border border-rose-500/30 px-2 py-0.5 text-[10px] font-bold text-rose-300">
                      HUMAN_APPROVAL_REQUIRED
                    </span>
                  </div>
                  <p className="text-xs text-gray-400 mt-0.5">
                    Contrato: <code>POST /api/v1/reports/export</code>. Discrepância de runtime confirmada em 340 amostras.
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <button
                  data-testid="approve-v2-btn"
                  onClick={handleApproveV2}
                  className="flex items-center gap-1.5 rounded-lg border border-emerald-500/40 bg-emerald-600/20 px-3.5 py-2 text-xs font-semibold text-emerald-300 hover:bg-emerald-600/30 transition-all"
                >
                  <Check className="h-4 w-4" />
                  <span>Aprovar Evolução v2.0.0</span>
                </button>

                <button
                  data-testid="rollback-btn"
                  onClick={handleRollback}
                  className="flex items-center gap-1.5 rounded-lg border border-rose-500/40 bg-rose-600/20 px-3.5 py-2 text-xs font-semibold text-rose-300 hover:bg-rose-600/30 transition-all"
                >
                  <RotateCcw className="h-4 w-4" />
                  <span>Rollback para v1.0.0</span>
                </button>
              </div>
            </div>

            <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
              <div className="rounded-lg border border-gray-800 bg-black/20 p-3 space-y-1">
                <span className="font-semibold text-gray-400">Versão Pai (Imutável):</span>
                <div className="font-mono text-gray-200">v1.0.0 (hash: c6d3b0e9...)</div>
                <div className="text-[11px] text-gray-500">Permanece preservada em histórico histórico.</div>
              </div>

              <div className="rounded-lg border border-gray-800 bg-black/20 p-3 space-y-1">
                <span className="font-semibold text-gray-400">Nova Versão Proposta:</span>
                <div className="font-mono text-cyan-300">v2.0.0 (hash: f1e2d3c4...)</div>
                <div className="text-[11px] text-gray-500">Adapta formato estruturado de exportação.</div>
              </div>

              <div className="rounded-lg border border-gray-800 bg-black/20 p-3 space-y-1">
                <span className="font-semibold text-gray-400">Plano de Migração:</span>
                <div className="text-gray-300">Atualizar ExportReportModal e suite pytest.</div>
                <div className="text-[11px] text-gray-500">Causal origin: DRIFT:drift_02_reports</div>
              </div>
            </div>

            {/* TIMELINE OF VERSIONS */}
            <div className="mt-5 border-t border-gray-800 pt-4">
              <span className="text-xs font-bold text-gray-300 uppercase tracking-wider flex items-center gap-2">
                <Clock className="h-4 w-4 text-gray-400" />
                <span>Linha Temporal de Versões e Rollbacks</span>
              </span>
              <div className="mt-3 flex items-center gap-4 text-xs font-mono">
                <div className="flex items-center gap-2 rounded border border-gray-700 bg-gray-800/60 px-3 py-1.5 text-gray-300">
                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                  <span>v1.0.0 (Verificada)</span>
                </div>
                <span className="text-gray-500">→</span>
                <div className="flex items-center gap-2 rounded border border-amber-500/40 bg-amber-950/20 px-3 py-1.5 text-amber-300">
                  <Activity className="h-3.5 w-3.5 text-amber-400" />
                  <span>Drift Detetado (340 reqs)</span>
                </div>
                <span className="text-gray-500">→</span>
                <div className="flex items-center gap-2 rounded border border-cyan-500/40 bg-cyan-950/20 px-3 py-1.5 text-cyan-300">
                  <GitCompare className="h-3.5 w-3.5 text-cyan-400" />
                  <span>Proposta v2.0.0</span>
                </div>
                <span className="text-gray-500">→</span>
                <div className="flex items-center gap-2 rounded border border-purple-500/40 bg-purple-950/20 px-3 py-1.5 text-purple-300">
                  <RotateCcw className="h-3.5 w-3.5 text-purple-400" />
                  <span>Rollback Suportado</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 5: SECURITY & SENTINEL */}
      {activeTab === 'security' && (
        <div className="space-y-4">
          <div className="rounded-xl border border-emerald-500/30 bg-[#0c1619] p-5">
            <div className="flex items-center justify-between border-b border-gray-800 pb-4 mb-4">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  <Lock className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-gray-100">Security Sentinel: Governação de Dados Passivos</h3>
                  <p className="text-xs text-gray-400 mt-0.5">
                    Metadados de drift são tratados estritamente como DADOS. Zero execução de instruções embutidas.
                  </p>
                </div>
              </div>
              <span className="rounded-full bg-emerald-500/10 border border-emerald-500/30 px-3 py-1 text-xs font-bold text-emerald-400">
                SENTINEL_ACTIVE
              </span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
              <div className="rounded-lg border border-gray-800 bg-black/20 p-3">
                <span className="text-gray-400">Injeções de Prompt:</span>
                <div className="text-lg font-bold text-emerald-400 mt-1">{data.security_sentinel.prompt_injections_blocked} Bloqueadas</div>
              </div>
              <div className="rounded-lg border border-gray-800 bg-black/20 p-3">
                <span className="text-gray-400">Comandos Shell:</span>
                <div className="text-lg font-bold text-emerald-400 mt-1">{data.security_sentinel.command_injections_blocked} Bloqueados</div>
              </div>
              <div className="rounded-lg border border-gray-800 bg-black/20 p-3">
                <span className="text-gray-400">Assinaturas Forjadas:</span>
                <div className="text-lg font-bold text-emerald-400 mt-1">{data.security_sentinel.forged_signatures_prevented} Rejeitadas</div>
              </div>
              <div className="rounded-lg border border-gray-800 bg-black/20 p-3">
                <span className="text-gray-400">Hashes Verificados:</span>
                <div className="text-lg font-bold text-cyan-400 mt-1">{data.security_sentinel.baseline_hashes_verified}/5 Válidos</div>
              </div>
            </div>

            <div className="mt-4 rounded-lg border border-gray-800 bg-gray-900/30 p-3 text-xs text-gray-300">
              <strong>Invariante de Segurança:</strong> Nenhuma alteração de tráfego de runtime pode contornar a porta de aprovação humana, nem enfraquecer o Security Sentinel, nem alterar contratos em ambientes de produção sem validação formal.
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
