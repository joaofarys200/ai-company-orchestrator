import React, { useState } from 'react';
import {
  Radio,
  FileCode,
  CheckCircle2,
  AlertTriangle,
  ShieldCheck,
  ShieldAlert,
  GitCompare,
  RefreshCw,
  Layers,
  Activity,
  Lock,
  Check,
  Ban,
  HelpCircle,
} from 'lucide-react';

export interface RuntimeContractDiscoveryPanelProps {
  missionId?: string;
}

export const FALLBACK_DISCOVERY_DATA = {
  total_observations: 156,
  active_proposals: 4,
  validated_contracts: 1,
  rejected_proposals: 0,
  stale_proposals: 1,
  uncertain_schemas_count: 2,
  detected_conflicts: 1,
  breaking_changes_count: 1,
  security_redactions_count: 24,
  malicious_metadata_blocked: 6,
  graph_updates_count: 1,
  security_defense: {
    status: 'SECURE',
    redacted_authorization_headers: 14,
    redacted_cookie_headers: 8,
    redacted_jwt_payloads: 5,
    prompt_injections_neutralized: 4,
    command_injections_blocked: 2,
    data_instruction_separation: 'STRICT_ENFORCED',
  },
  observations: [
    {
      observation_id: 'obs_01',
      route: '/api/v1/users/search',
      method: 'GET',
      status_code: 200,
      source_type: 'browser_network_logs',
      latency_ms: 42.5,
      redacted_credentials: 1,
      timestamp: '2026-09-12T14:32:10Z',
    },
    {
      observation_id: 'obs_02',
      route: '/api/v1/auth/token',
      method: 'POST',
      status_code: 200,
      source_type: 'backend_http_middleware',
      latency_ms: 110.2,
      redacted_credentials: 2,
      timestamp: '2026-09-12T14:31:45Z',
    },
    {
      observation_id: 'obs_03',
      route: '/api/v1/reports/export',
      method: 'POST',
      status_code: 409,
      source_type: 'local_dev_proxy',
      latency_ms: 85.0,
      redacted_credentials: 1,
      timestamp: '2026-09-12T14:30:20Z',
    },
    {
      observation_id: 'obs_04',
      route: '/api/v1/users/search',
      method: 'GET',
      status_code: 400,
      source_type: 'browser_network_logs',
      latency_ms: 15.8,
      redacted_credentials: 0,
      timestamp: '2026-09-12T14:28:11Z',
    },
  ],
  proposals: [
    {
      proposal_id: 'prop_p45_01_users_search',
      source: 'browser_network_logs',
      route: '/api/v1/users/search',
      method: 'GET',
      status: 'PROPOSED',
      sample_count: 8,
      confidence: 0.88,
      contract_version: '1.0.0-proposed',
      parent_version: 'UNVERSIONED_OBSERVED',
      assumptions: [
        "Query parameter 'q' com presença constante em todas as chamadas",
        'Array de utilizadores retornado na raiz do corpo JSON',
      ],
      uncertainties: [
        'Cursor de paginação ausente em 3/8 amostras observadas',
      ],
      created_at: '2026-09-12T14:30:00Z',
      observed_variations: 1,
      inferred_schema: {
        name: 'UserSearchResult',
        fields: {
          id: { type: 'integer', presence_ratio: 1.0, is_required: true, is_nullable: false, is_enum: false },
          username: { type: 'string', presence_ratio: 1.0, is_required: true, is_nullable: false, is_enum: false },
          email: { type: 'string', presence_ratio: 1.0, is_required: true, is_nullable: false, is_enum: false },
          bio: { type: 'string', presence_ratio: 0.625, is_required: false, is_nullable: true, is_enum: false },
          role: { type: 'string', presence_ratio: 1.0, is_required: true, is_nullable: false, is_enum: true, enum_values: ['ADMIN', 'MEMBER', 'GUEST'] },
          avatar_url: { type: 'string', presence_ratio: 0.5, is_required: false, is_nullable: true, is_enum: false },
        },
      },
      observed_errors: [
        { status_code: 400, sample_count: 2, error_shape: { detail: "Query parameter 'q' too short" } },
        { status_code: 401, sample_count: 1, error_shape: { detail: 'Missing authentication header' } },
      ],
      contract_diff: {
        severity: 'NON_BREAKING',
        differences: [
          { field_path: 'bio', diff_type: 'ADDED_FIELD', severity: 'NON_BREAKING', description: 'Campo opcional bio detectado em 5/8 amostras' },
          { field_path: 'avatar_url', diff_type: 'ADDED_FIELD', severity: 'NON_BREAKING', description: 'Campo nullable avatar_url detectado em 4/8 amostras' },
        ],
      },
    },
    {
      proposal_id: 'prop_p45_02_auth_token',
      source: 'backend_http_middleware',
      route: '/api/v1/auth/token',
      method: 'POST',
      status: 'VALIDATED',
      sample_count: 14,
      confidence: 0.95,
      contract_version: '1.0.0',
      parent_version: '1.0.0-proposed',
      assumptions: ['Payload de login com username e password devidamente anonimizados'],
      uncertainties: [],
      created_at: '2026-09-12T14:10:00Z',
      observed_variations: 0,
      inferred_schema: {
        name: 'TokenResponse',
        fields: {
          access_token: { type: 'string', presence_ratio: 1.0, is_required: true, is_nullable: false, is_enum: false },
          token_type: { type: 'string', presence_ratio: 1.0, is_required: true, is_nullable: false, is_enum: true, enum_values: ['bearer'] },
          expires_in: { type: 'integer', presence_ratio: 1.0, is_required: true, is_nullable: false, is_enum: false },
        },
      },
      observed_errors: [
        { status_code: 401, sample_count: 3, error_shape: { detail: 'Invalid credentials' } },
      ],
      contract_diff: {
        severity: 'NON_BREAKING',
        differences: [],
      },
    },
    {
      proposal_id: 'prop_p45_03_legacy_reports',
      source: 'local_dev_proxy',
      route: '/api/v1/reports/export',
      method: 'POST',
      status: 'CONFLICT',
      sample_count: 5,
      confidence: 0.65,
      contract_version: '0.9.0-conflict',
      parent_version: 'UNVERSIONED_OBSERVED',
      assumptions: ['Conflito de negociação de conteúdo entre CSV e JSON'],
      uncertainties: ['Polimorfismo de schema detectado entre payload do frontend e do exportador batch'],
      created_at: '2026-09-12T14:35:00Z',
      observed_variations: 3,
      inferred_schema: {
        name: 'ExportReportResponse',
        fields: {
          report_id: { type: 'string', presence_ratio: 1.0, is_required: true, is_nullable: false, is_enum: false },
          status: { type: 'string', presence_ratio: 1.0, is_required: true, is_nullable: false, is_enum: true, enum_values: ['PENDING', 'PROCESSING', 'READY', 'FAILED'] },
        },
      },
      observed_errors: [
        { status_code: 409, sample_count: 2, error_shape: { detail: 'Export job already queued' } },
      ],
      contract_diff: {
        severity: 'BREAKING',
        differences: [
          { field_path: 'format', diff_type: 'TYPE_CHANGED', severity: 'BREAKING', description: 'Tipo alterado de string para objeto complexo' },
        ],
      },
    },
    {
      proposal_id: 'prop_p45_04_stale_metrics',
      source: 'test_traffic',
      route: '/api/v0/telemetry/metrics',
      method: 'GET',
      status: 'STALE',
      sample_count: 2,
      confidence: 0.40,
      contract_version: '0.1.0-stale',
      parent_version: 'UNVERSIONED_OBSERVED',
      assumptions: ['Endpoint de telemetria deprecated da v0'],
      uncertainties: ['Zero tráfego observado nas últimas 48 horas'],
      created_at: '2026-09-10T09:00:00Z',
      observed_variations: 0,
      inferred_schema: {
        name: 'StaleMetricsResponse',
        fields: {
          cpu: { type: 'float', presence_ratio: 1.0, is_required: false, is_nullable: false, is_enum: false },
        },
      },
      observed_errors: [],
      contract_diff: {
        severity: 'POTENTIALLY_BREAKING',
        differences: [
          { field_path: 'cpu', diff_type: 'REMOVED_FIELD', severity: 'POTENTIALLY_BREAKING', description: 'Campo ausente no tráfego recente' },
        ],
      },
    },
  ],
  policy: {
    auto_observe: 'ACTIVE',
    mission_gate: 'ENFORCED',
    security_sentinel: 'ACTIVE',
    invariant_rule: 'OBSERVED != INFERRED != VERIFIED',
  },
};

export const RuntimeContractDiscoveryPanel: React.FC<RuntimeContractDiscoveryPanelProps> = () => {
  const [data, setData] = useState(FALLBACK_DISCOVERY_DATA);
  const [selectedProposalId, setSelectedProposalId] = useState<string>('prop_p45_01_users_search');
  const [activeTab, setActiveTab] = useState<'proposals' | 'observations' | 'security'>('proposals');
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  const selectedProposal = data.proposals.find((p) => p.proposal_id === selectedProposalId) || data.proposals[0];

  const handleReviewAction = (proposalId: string, action: 'ACCEPT' | 'REJECT' | 'REQUEST_MORE_EVIDENCE') => {
    setData((prev) => {
      const updated = prev.proposals.map((prop) => {
        if (prop.proposal_id !== proposalId) return prop;
        if (action === 'ACCEPT') {
          return {
            ...prop,
            status: 'VALIDATED',
            contract_version: prop.contract_version.replace('-proposed', ''),
          };
        } else if (action === 'REJECT') {
          return {
            ...prop,
            status: 'REJECTED',
          };
        } else {
          return {
            ...prop,
            assumptions: [...prop.assumptions, 'Mais amostras solicitadas pelo operador humano'],
          };
        }
      });

      const validatedCount = updated.filter((p) => p.status === 'VALIDATED').length;
      return {
        ...prev,
        proposals: updated,
        validated_contracts: validatedCount,
        graph_updates_count: validatedCount,
      };
    });

    const msg =
      action === 'ACCEPT'
        ? `Proposta ${proposalId} VALIDADA e sincronizada com o Semantic Graph incrementalmente!`
        : action === 'REJECT'
        ? `Proposta ${proposalId} REJEITADA.`
        : `Solicitação de evidência adicional registada para ${proposalId}.`;
    setActionNotice(msg);
    setTimeout(() => setActionNotice(null), 4000);
  };

  return (
    <div
      data-testid="runtime-contract-discovery-panel"
      className="flex flex-col gap-6 text-gray-200"
    >
      {/* EPISTEMIC INVARIANT BANNER */}
      <div
        data-testid="runtime-evidence-explanation"
        className="rounded-xl border border-cyan-500/30 bg-gradient-to-r from-cyan-950/40 via-[#0a1922] to-blue-950/40 p-5 backdrop-blur-md shadow-lg"
      >
        <div className="flex items-start gap-4">
          <div className="rounded-lg bg-cyan-500/20 p-2 text-cyan-300">
            <Radio className="h-6 w-6 animate-pulse" />
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-3">
              <h2 className="text-base font-bold text-white tracking-wide">
                Fase 45 — Descoberta de Contratos em Runtime & Inferência Segura de Schema
              </h2>
              <span className="rounded-full bg-cyan-500/10 px-2.5 py-0.5 text-[10px] font-semibold text-cyan-300 border border-cyan-500/30">
                ACTIVE OBSERVER
              </span>
            </div>
            <p className="mt-1 text-xs text-gray-300 leading-relaxed">
              <strong className="text-cyan-200">Princípio Fundamental:</strong>{' '}
              <code className="rounded bg-black/40 px-1.5 py-0.5 text-cyan-300 font-mono">
                OBSERVED ≠ INFERRED ≠ VERIFIED
              </code>
              . O tráfego de runtime observado gera hipóteses estruturadas (
              <span className="text-amber-300 font-medium">ContractProposal</span>), mas{' '}
              <span className="underline decoration-cyan-400 font-semibold">nunca é promovido automaticamente</span> para a verdade
              arquitetural sem validação formal, verificação de compatibilidade e aprovação no Mission Gate.
            </p>
          </div>
        </div>
      </div>

      {/* FEEDBACK NOTICE */}
      {actionNotice && (
        <div className="flex items-center gap-3 rounded-lg border border-emerald-500/40 bg-emerald-950/40 px-4 py-3 text-xs text-emerald-200 shadow-md">
          <CheckCircle2 className="h-4 w-4 text-emerald-400" />
          <span>{actionNotice}</span>
        </div>
      )}

      {/* TOP KPI CARDS (discovery-overview) */}
      <div
        data-testid="discovery-overview"
        className="grid grid-cols-2 gap-4 md:grid-cols-4 lg:grid-cols-7"
      >
        <div className="rounded-xl border border-white/10 bg-[#0d161a] p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between text-gray-400">
            <span className="text-[11px] font-medium uppercase tracking-wider">Observações</span>
            <Activity className="h-4 w-4 text-cyan-400" />
          </div>
          <div className="mt-2 text-2xl font-bold text-white">{data.total_observations}</div>
          <span className="mt-1 text-[10px] text-cyan-400">Tráfego Real Passivo</span>
        </div>

        <div className="rounded-xl border border-white/10 bg-[#0d161a] p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between text-gray-400">
            <span className="text-[11px] font-medium uppercase tracking-wider">Propostas</span>
            <FileCode className="h-4 w-4 text-amber-400" />
          </div>
          <div className="mt-2 text-2xl font-bold text-amber-300">{data.active_proposals}</div>
          <span className="mt-1 text-[10px] text-amber-400/80">Aguardam Validação</span>
        </div>

        <div className="rounded-xl border border-white/10 bg-[#0d161a] p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between text-gray-400">
            <span className="text-[11px] font-medium uppercase tracking-wider">Validados</span>
            <CheckCircle2 className="h-4 w-4 text-emerald-400" />
          </div>
          <div className="mt-2 flex items-center gap-2">
            <span className="text-2xl font-bold text-emerald-300">{data.validated_contracts}</span>
            <span
              data-testid="validated-contract-badge"
              className="rounded bg-emerald-500/20 px-1.5 py-0.5 text-[9px] font-bold text-emerald-300 border border-emerald-500/40"
            >
              VALIDATED
            </span>
          </div>
          <span className="mt-1 text-[10px] text-emerald-400/80">Formalizados</span>
        </div>

        <div className="rounded-xl border border-white/10 bg-[#0d161a] p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between text-gray-400">
            <span className="text-[11px] font-medium uppercase tracking-wider">Conflitos</span>
            <AlertTriangle className="h-4 w-4 text-rose-400" />
          </div>
          <div className="mt-2 text-2xl font-bold text-rose-300">{data.detected_conflicts}</div>
          <span className="mt-1 text-[10px] text-rose-400/80">Variação de Schema</span>
        </div>

        <div className="rounded-xl border border-white/10 bg-[#0d161a] p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between text-gray-400">
            <span className="text-[11px] font-medium uppercase tracking-wider">Redações</span>
            <Lock className="h-4 w-4 text-purple-400" />
          </div>
          <div className="mt-2 flex items-center gap-2">
            <span className="text-2xl font-bold text-purple-300">{data.security_redactions_count}</span>
            <span
              data-testid="security-redaction-badge"
              className="rounded bg-purple-500/20 px-1.5 py-0.5 text-[9px] font-bold text-purple-300 border border-purple-500/40"
            >
              REDACTED
            </span>
          </div>
          <span className="mt-1 text-[10px] text-purple-400/80">Credenciais Sanitizadas</span>
        </div>

        <div className="rounded-xl border border-white/10 bg-[#0d161a] p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between text-gray-400">
            <span className="text-[11px] font-medium uppercase tracking-wider">Bloqueios</span>
            <ShieldAlert className="h-4 w-4 text-orange-400" />
          </div>
          <div className="mt-2 flex items-center gap-2">
            <span className="text-2xl font-bold text-orange-300">{data.malicious_metadata_blocked}</span>
            <span
              data-testid="malicious-metadata-blocked"
              className="rounded bg-orange-500/20 px-1.5 py-0.5 text-[9px] font-bold text-orange-300 border border-orange-500/40"
            >
              BLOCKED
            </span>
          </div>
          <span className="mt-1 text-[10px] text-orange-400/80">Sentinel Neutralized</span>
        </div>

        <div className="rounded-xl border border-white/10 bg-[#0d161a] p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between text-gray-400">
            <span className="text-[11px] font-medium uppercase tracking-wider">Grafo Sync</span>
            <RefreshCw className="h-4 w-4 text-cyan-400" />
          </div>
          <div className="mt-2 flex items-center gap-2">
            <span className="text-2xl font-bold text-cyan-300">{data.graph_updates_count}</span>
            <span
              data-testid="graph-update-indicator"
              className="rounded bg-cyan-500/20 px-1.5 py-0.5 text-[9px] font-bold text-cyan-300 border border-cyan-500/40"
            >
              INCREMENTAL
            </span>
          </div>
          <span className="mt-1 text-[10px] text-cyan-400/80">Versionado v3</span>
        </div>
      </div>

      {/* SUB-NAVIGATION */}
      <div className="flex items-center gap-2 border-b border-white/10 pb-3">
        <button
          onClick={() => setActiveTab('proposals')}
          className={`flex items-center gap-2 rounded-lg px-4 py-2 text-xs font-semibold transition-all ${
            activeTab === 'proposals'
              ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm'
              : 'text-gray-400 hover:text-gray-200 hover:bg-white/5'
          }`}
        >
          <FileCode className="h-4 w-4" />
          <span>Propostas de Contratos ({data.proposals.length})</span>
        </button>

        <button
          onClick={() => setActiveTab('observations')}
          className={`flex items-center gap-2 rounded-lg px-4 py-2 text-xs font-semibold transition-all ${
            activeTab === 'observations'
              ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm'
              : 'text-gray-400 hover:text-gray-200 hover:bg-white/5'
          }`}
        >
          <Activity className="h-4 w-4" />
          <span>Feed de Observação em Runtime ({data.observations.length})</span>
        </button>

        <button
          onClick={() => setActiveTab('security')}
          className={`flex items-center gap-2 rounded-lg px-4 py-2 text-xs font-semibold transition-all ${
            activeTab === 'security'
              ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm'
              : 'text-gray-400 hover:text-gray-200 hover:bg-white/5'
          }`}
        >
          <ShieldCheck className="h-4 w-4" />
          <span>Segurança & Redação de Credenciais</span>
        </button>
      </div>

      {/* MAIN CONTENT AREA */}
      {activeTab === 'proposals' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* LEFT: PROPOSALS LIST (5 cols) */}
          <div className="lg:col-span-5 flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold uppercase tracking-wider text-gray-400">
                Propostas Inferred
              </h3>
              <span className="text-[11px] text-gray-400">
                {data.proposals.length} propostas registadas
              </span>
            </div>

            {data.proposals.map((prop) => {
              const isSelected = prop.proposal_id === selectedProposalId;
              const isConflict = prop.status === 'CONFLICT';
              const isStale = prop.status === 'STALE';
              const isValidated = prop.status === 'VALIDATED';

              return (
                <div
                  key={prop.proposal_id}
                  data-testid="contract-proposal-card"
                  onClick={() => setSelectedProposalId(prop.proposal_id)}
                  className={`cursor-pointer rounded-xl border p-4 transition-all duration-200 ${
                    isSelected
                      ? 'border-cyan-400 bg-[#122329] shadow-lg shadow-cyan-950/50'
                      : 'border-white/10 bg-[#0d161a] hover:border-white/20 hover:bg-[#101b20]'
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-2">
                      <span
                        className={`rounded px-2 py-0.5 font-mono text-[10px] font-bold ${
                          prop.method === 'GET'
                            ? 'bg-blue-500/20 text-blue-300 border border-blue-500/30'
                            : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                        }`}
                      >
                        {prop.method}
                      </span>
                      <span className="font-mono text-xs font-semibold text-white">
                        {prop.route}
                      </span>
                    </div>

                    <div className="flex items-center gap-1.5">
                      {isConflict && (
                        <span className="rounded bg-rose-500/20 px-2 py-0.5 text-[10px] font-bold text-rose-300 border border-rose-500/40">
                          CONFLICT
                        </span>
                      )}
                      {isStale && (
                        <span
                          data-testid="stale-proposal-badge"
                          className="rounded bg-gray-500/20 px-2 py-0.5 text-[10px] font-bold text-gray-300 border border-gray-500/40"
                        >
                          STALE
                        </span>
                      )}
                      {isValidated && (
                        <span className="rounded bg-emerald-500/20 px-2 py-0.5 text-[10px] font-bold text-emerald-300 border border-emerald-500/40">
                          VALIDATED
                        </span>
                      )}
                      {!isConflict && !isStale && !isValidated && (
                        <span className="rounded bg-amber-500/20 px-2 py-0.5 text-[10px] font-bold text-amber-300 border border-amber-500/40">
                          PROPOSED
                        </span>
                      )}
                    </div>
                  </div>

                  {prop.observed_variations > 0 && (
                    <div
                      data-testid="schema-variation-card"
                      className="mt-2 flex items-center gap-2 rounded bg-amber-950/30 border border-amber-500/30 px-2.5 py-1 text-[11px] text-amber-300"
                    >
                      <GitCompare className="h-3.5 w-3.5" />
                      <span>{prop.observed_variations} variação(ões) estruturais observadas</span>
                    </div>
                  )}

                  {isConflict && (
                    <div
                      data-testid="conflict-detected-card"
                      className="mt-2 flex items-center gap-2 rounded bg-rose-950/30 border border-rose-500/30 px-2.5 py-1 text-[11px] text-rose-300"
                    >
                      <AlertTriangle className="h-3.5 w-3.5" />
                      <span>Conflito estrutural detectado com contrato formal pré-existente</span>
                    </div>
                  )}

                  <div className="mt-3 flex items-center justify-between text-[11px] text-gray-400">
                    <span>Amostras: <strong className="text-white">{prop.sample_count}</strong></span>
                    <span>Confiança: <strong className="text-cyan-300">{Math.round(prop.confidence * 100)}%</strong></span>
                    <span className="font-mono text-[10px] text-gray-400">{prop.contract_version}</span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* RIGHT: PROPOSAL DETAILS & SCHEMA INFERENCE (7 cols) */}
          <div className="lg:col-span-7 flex flex-col gap-5">
            {/* PROPOSAL HEADER & ACTIONS */}
            <div className="rounded-xl border border-white/10 bg-[#0d161a] p-5">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 pb-4">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-sm font-bold text-white">
                      {selectedProposal.method} {selectedProposal.route}
                    </span>
                    <span className="rounded bg-cyan-500/10 px-2 py-0.5 font-mono text-[10px] text-cyan-300 border border-cyan-500/30">
                      v{selectedProposal.contract_version}
                    </span>
                  </div>
                  <p className="mt-1 text-[11px] text-gray-400">
                    Fonte de Tráfego:{' '}
                    <span className="text-gray-300 font-mono">{selectedProposal.source}</span> • Registado em{' '}
                    {selectedProposal.created_at}
                  </p>
                </div>

                {/* HUMAN APPROVAL ACTIONS */}
                <div className="flex items-center gap-2">
                  <button
                    data-testid="human-approval-btn"
                    onClick={() => handleReviewAction(selectedProposal.proposal_id, 'ACCEPT')}
                    disabled={selectedProposal.status === 'VALIDATED'}
                    className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition-all ${
                      selectedProposal.status === 'VALIDATED'
                        ? 'bg-emerald-950/40 text-emerald-400/60 border border-emerald-900/40 cursor-not-allowed'
                        : 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-md shadow-emerald-950/50'
                    }`}
                  >
                    <Check className="h-3.5 w-3.5" />
                    <span>Validar & Promover</span>
                  </button>

                  <button
                    onClick={() => handleReviewAction(selectedProposal.proposal_id, 'REQUEST_MORE_EVIDENCE')}
                    className="flex items-center gap-1.5 rounded-lg border border-amber-500/40 bg-amber-950/30 hover:bg-amber-900/40 px-3 py-1.5 text-xs font-semibold text-amber-300 transition-all"
                  >
                    <HelpCircle className="h-3.5 w-3.5" />
                    <span>Mais Amostras</span>
                  </button>

                  <button
                    onClick={() => handleReviewAction(selectedProposal.proposal_id, 'REJECT')}
                    disabled={selectedProposal.status === 'REJECTED'}
                    className="flex items-center gap-1.5 rounded-lg border border-rose-500/40 bg-rose-950/30 hover:bg-rose-900/40 px-3 py-1.5 text-xs font-semibold text-rose-300 transition-all"
                  >
                    <Ban className="h-3.5 w-3.5" />
                    <span>Rejeitar</span>
                  </button>
                </div>
              </div>

              {/* ASSUMPTIONS & UNCERTAINTIES */}
              <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                <div className="rounded-lg bg-black/20 p-3 border border-white/5">
                  <span className="font-semibold text-cyan-300 flex items-center gap-1.5">
                    <CheckCircle2 className="h-3.5 w-3.5" /> Assunções Inferidas
                  </span>
                  <ul className="mt-2 space-y-1 text-gray-300">
                    {selectedProposal.assumptions.map((asm, i) => (
                      <li key={i} className="flex items-start gap-1.5">
                        <span className="text-cyan-400">•</span>
                        <span>{asm}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="rounded-lg bg-black/20 p-3 border border-white/5">
                  <span className="font-semibold text-amber-300 flex items-center gap-1.5">
                    <AlertTriangle className="h-3.5 w-3.5" /> Incertezas Epistémicas
                  </span>
                  <ul className="mt-2 space-y-1 text-gray-300">
                    {selectedProposal.uncertainties.length > 0 ? (
                      selectedProposal.uncertainties.map((unc, i) => (
                        <li key={i} className="flex items-start gap-1.5">
                          <span className="text-amber-400">•</span>
                          <span>{unc}</span>
                        </li>
                      ))
                    ) : (
                      <li className="text-gray-400 italic">Nenhuma incerteza residual detectada</li>
                    )}
                  </ul>
                </div>
              </div>
            </div>

            {/* INFERRED SCHEMA CARD */}
            <div
              data-testid="inferred-schema-card"
              className="rounded-xl border border-white/10 bg-[#0d161a] p-5"
            >
              <div className="flex items-center justify-between border-b border-white/10 pb-3">
                <div className="flex items-center gap-2">
                  <Layers className="h-4 w-4 text-cyan-400" />
                  <h4 className="text-xs font-bold uppercase tracking-wider text-white">
                    Schema Inferred: {selectedProposal.inferred_schema.name}
                  </h4>
                </div>
                <span className="text-[11px] text-gray-400">
                  {Object.keys(selectedProposal.inferred_schema.fields).length} campos analisados
                </span>
              </div>

              {/* FIELDS TABLE */}
              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-white/10 text-gray-400">
                      <th className="pb-2 font-medium">Campo</th>
                      <th className="pb-2 font-medium">Tipo</th>
                      <th className="pb-2 font-medium">Presença</th>
                      <th className="pb-2 font-medium">Propriedades</th>
                      <th className="pb-2 font-medium">Valores Observados</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5 font-mono">
                    {Object.entries(selectedProposal.inferred_schema.fields).map(([fieldName, f]: [string, any]) => (
                      <tr key={fieldName} className="hover:bg-white/[0.02]">
                        <td className="py-2.5 font-bold text-white">{fieldName}</td>
                        <td className="py-2.5 text-cyan-300">{f.type}</td>
                        <td className="py-2.5 text-gray-300">{Math.round(f.presence_ratio * 100)}%</td>
                        <td className="py-2.5">
                          <div className="flex flex-wrap gap-1">
                            {f.is_required ? (
                              <span className="rounded bg-emerald-500/20 px-1.5 py-0.5 text-[9px] font-bold text-emerald-300">
                                REQUIRED
                              </span>
                            ) : (
                              <span
                                data-testid="optional-field-badge"
                                className="rounded bg-amber-500/20 px-1.5 py-0.5 text-[9px] font-bold text-amber-300 border border-amber-500/30"
                              >
                                OPTIONAL
                              </span>
                            )}

                            {f.is_nullable && (
                              <span
                                data-testid="nullable-field-badge"
                                className="rounded bg-purple-500/20 px-1.5 py-0.5 text-[9px] font-bold text-purple-300 border border-purple-500/30"
                              >
                                NULLABLE
                              </span>
                            )}

                            {f.is_enum && (
                              <span className="rounded bg-blue-500/20 px-1.5 py-0.5 text-[9px] font-bold text-blue-300 border border-blue-500/30">
                                ENUM_CANDIDATE
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="py-2.5 text-[11px] text-gray-400">
                          {f.enum_values ? f.enum_values.join(', ') : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* CONTRACT DIFF CARD */}
            <div
              data-testid="contract-diff-card"
              className="rounded-xl border border-white/10 bg-[#0d161a] p-5"
            >
              <div className="flex items-center justify-between border-b border-white/10 pb-3">
                <div className="flex items-center gap-2">
                  <GitCompare className="h-4 w-4 text-cyan-400" />
                  <h4 className="text-xs font-bold uppercase tracking-wider text-white">
                    Contract Diff Engine (Versus Contrato Histórico)
                  </h4>
                </div>

                <span
                  className={`rounded px-2 py-0.5 text-[10px] font-bold ${
                    selectedProposal.contract_diff.severity === 'BREAKING'
                      ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40'
                      : selectedProposal.contract_diff.severity === 'POTENTIALLY_BREAKING'
                      ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                      : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                  }`}
                >
                  {selectedProposal.contract_diff.severity}
                </span>
              </div>

              <div className="mt-3 space-y-2 text-xs">
                {selectedProposal.contract_diff.differences.length > 0 ? (
                  selectedProposal.contract_diff.differences.map((diff: any, idx: number) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between rounded-lg bg-black/20 p-3 border border-white/5"
                    >
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-bold text-white">{diff.field_path}</span>
                        <span className="rounded bg-white/5 px-2 py-0.5 font-mono text-[10px] text-cyan-300">
                          {diff.diff_type}
                        </span>
                      </div>
                      <span className="text-gray-300">{diff.description}</span>
                    </div>
                  ))
                ) : (
                  <p className="text-gray-400 italic">
                    Nenhuma divergência estrutural em relação ao schema base. Totalmente compatível.
                  </p>
                )}
              </div>
            </div>

            {/* ERROR CONTRACTS OBSERVED */}
            {selectedProposal.observed_errors && selectedProposal.observed_errors.length > 0 && (
              <div className="rounded-xl border border-white/10 bg-[#0d161a] p-5">
                <div className="flex items-center gap-2 border-b border-white/10 pb-3">
                  <AlertTriangle className="h-4 w-4 text-amber-400" />
                  <h4 className="text-xs font-bold uppercase tracking-wider text-white">
                    Contratos de Erro Observados em Runtime (4xx / 5xx)
                  </h4>
                </div>

                <div className="mt-3 space-y-2">
                  {selectedProposal.observed_errors.map((err: any, i: number) => (
                    <div
                      key={i}
                      className="flex items-center justify-between rounded-lg bg-black/20 p-3 border border-white/5 text-xs font-mono"
                    >
                      <div className="flex items-center gap-2">
                        <span className="rounded bg-rose-500/20 px-2 py-0.5 text-rose-300 font-bold border border-rose-500/40">
                          {err.status_code}
                        </span>
                        <span className="text-gray-400">{err.sample_count} ocorrência(s)</span>
                      </div>
                      <span className="text-gray-300">
                        {JSON.stringify(err.error_shape)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* OBSERVATION FEED TAB */}
      {activeTab === 'observations' && (
        <div data-testid="observation-feed" className="rounded-xl border border-white/10 bg-[#0d161a] p-5">
          <div className="flex items-center justify-between border-b border-white/10 pb-4">
            <div>
              <h3 className="text-sm font-bold text-white">Feed de Observações em Runtime (Passivo)</h3>
              <p className="text-xs text-gray-400">
                Captura segura via Proxy Local, Browser QA logs e Middleware Backend sem retenção de payloads confidenciais.
              </p>
            </div>
            <span className="rounded bg-cyan-500/20 px-2.5 py-1 text-xs font-mono font-bold text-cyan-300 border border-cyan-500/40">
              {data.observations.length} observações recentes
            </span>
          </div>

          <div className="mt-4 space-y-3">
            {data.observations.map((obs) => (
              <div
                key={obs.observation_id}
                className="flex items-center justify-between rounded-lg border border-white/5 bg-black/30 p-3.5 text-xs font-mono hover:border-white/15 transition-all"
              >
                <div className="flex items-center gap-3">
                  <span
                    className={`rounded px-2 py-0.5 text-[10px] font-bold ${
                      obs.method === 'GET'
                        ? 'bg-blue-500/20 text-blue-300'
                        : 'bg-emerald-500/20 text-emerald-300'
                    }`}
                  >
                    {obs.method}
                  </span>
                  <span className="font-semibold text-white">{obs.route}</span>
                  <span className="rounded bg-white/10 px-2 py-0.5 text-[10px] text-gray-300">
                    {obs.status_code}
                  </span>
                </div>

                <div className="flex items-center gap-4 text-gray-400 text-[11px]">
                  <span>{obs.latency_ms}ms</span>
                  <span className="rounded bg-cyan-950/40 px-2 py-0.5 text-cyan-300 border border-cyan-800/40">
                    {obs.source_type}
                  </span>
                  {obs.redacted_credentials > 0 && (
                    <span
                      data-testid="security-redaction-badge"
                      className="rounded bg-purple-950/40 px-2 py-0.5 text-purple-300 border border-purple-800/40 font-bold"
                    >
                      {obs.redacted_credentials} Redacted
                    </span>
                  )}
                  <span className="text-gray-400">{obs.timestamp}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* SECURITY TAB */}
      {activeTab === 'security' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="rounded-xl border border-white/10 bg-[#0d161a] p-5">
            <div className="flex items-center gap-2 border-b border-white/10 pb-3">
              <ShieldCheck className="h-5 w-5 text-emerald-400" />
              <h3 className="text-sm font-bold text-white">Higienização e Redação Automática</h3>
            </div>
            <p className="mt-3 text-xs text-gray-300 leading-relaxed">
              O observador de runtime implementa sanitização estrita antes de persistir metadados. Headers como
              <code className="text-purple-300 font-mono"> Authorization</code>,{' '}
              <code className="text-purple-300 font-mono">Cookie</code>,{' '}
              <code className="text-purple-300 font-mono">X-API-Key</code> e campos com senhas/tokens são substituídos
              por <code className="text-purple-300 font-mono">[REDACTED_CREDENTIAL]</code>.
            </p>

            <div className="mt-4 space-y-2 text-xs font-mono">
              <div className="flex items-center justify-between rounded bg-black/30 p-2.5 border border-white/5">
                <span className="text-gray-300">Headers de Autorização Redigidos</span>
                <span className="text-purple-300 font-bold">{data.security_defense.redacted_authorization_headers}</span>
              </div>
              <div className="flex items-center justify-between rounded bg-black/30 p-2.5 border border-white/5">
                <span className="text-gray-300">Cookies de Sessão Sanitizados</span>
                <span className="text-purple-300 font-bold">{data.security_defense.redacted_cookie_headers}</span>
              </div>
              <div className="flex items-center justify-between rounded bg-black/30 p-2.5 border border-white/5">
                <span className="text-gray-300">Payloads JWT Anonimizados</span>
                <span className="text-purple-300 font-bold">{data.security_defense.redacted_jwt_payloads}</span>
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-white/10 bg-[#0d161a] p-5">
            <div className="flex items-center gap-2 border-b border-white/10 pb-3">
              <ShieldAlert className="h-5 w-5 text-orange-400" />
              <h3 className="text-sm font-bold text-white">Separação Estrita de Dados vs Instrução</h3>
            </div>
            <p className="mt-3 text-xs text-gray-300 leading-relaxed">
              Metadados de tráfego contendo comandos maliciosos, injeções de prompt ou falsas mensagens de aprovação
              são mantidos estritamente como dados inertes (DATA) e bloqueados pelo Security Sentinel.
            </p>

            <div className="mt-4 space-y-2 text-xs font-mono">
              <div className="flex items-center justify-between rounded bg-black/30 p-2.5 border border-white/5">
                <span className="text-gray-300">Injeções de Prompt Neutralizadas</span>
                <span className="text-orange-300 font-bold">{data.security_defense.prompt_injections_neutralized}</span>
              </div>
              <div className="flex items-center justify-between rounded bg-black/30 p-2.5 border border-white/5">
                <span className="text-gray-300">Comandos Shell Bloqueados</span>
                <span className="text-orange-300 font-bold">{data.security_defense.command_injections_blocked}</span>
              </div>
              <div className="flex items-center justify-between rounded bg-black/30 p-2.5 border border-white/5">
                <span className="text-gray-300">Estado de Separação de Dados</span>
                <span className="text-emerald-300 font-bold">{data.security_defense.data_instruction_separation}</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default RuntimeContractDiscoveryPanel;
