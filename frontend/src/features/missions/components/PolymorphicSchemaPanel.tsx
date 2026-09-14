import React, { useState } from 'react';
import {
  Layers,
  GitBranch,
  Split,
  ShieldCheck,
  AlertTriangle,
  CheckCircle2,
  HelpCircle,
  Code2,
  Users,
  Check,
  X,
  RotateCcw,
  Sparkles,
  Filter,
  Info,
  Lock,
} from 'lucide-react';

export interface PolymorphicSchemaPanelProps {
  missionId?: string;
}

export const FALLBACK_POLYMORPHIC_DATA = {
  monitored_polymorphic_count: 4,
  total_variants_count: 12,
  deterministic_count: 8,
  inferred_count: 3,
  uncertain_count: 1,
  discriminator_count: 3,
  compatibility_rate: '94.2%',
  security_sentinel: {
    status: 'SECURE',
    prompt_injections_blocked: 4,
    command_injections_blocked: 2,
    forged_variants_prevented: 3,
    metadata_sanitized: true,
  },
  polymorphic_schemas: [
    {
      schema_id: 'poly_events_v1',
      route: '/api/v1/events',
      method: 'POST',
      version: '1.2.0',
      status: 'VALIDATED',
      kind: 'DISCRIMINATED_UNION',
      discriminator: {
        field: 'type',
        location: 'BODY',
        type: 'STRING_ENUM',
        observed_values: ['user.created', 'user.updated', 'user.deleted', 'user.archived'],
        is_explicit: true,
        confidence: 1.0,
      },
      common_fields: ['id', 'timestamp', 'type', 'source', 'version'],
      variants: [
        {
          variant_id: 'var_user_created',
          label: 'UserCreated',
          discriminator_value: 'user.created',
          status: 'VALIDATED',
          observed_count: 8420,
          confidence: 1.0,
          required_fields: ['id', 'timestamp', 'type', 'payload.user_id', 'payload.email', 'payload.role'],
          optional_fields: ['payload.avatar_url', 'payload.metadata'],
          forbidden_fields: ['payload.deletion_reason', 'payload.archived_until'],
          description: 'Dispatched when a new user signs up in the system.',
        },
        {
          variant_id: 'var_user_updated',
          label: 'UserUpdated',
          discriminator_value: 'user.updated',
          status: 'VALIDATED',
          observed_count: 5120,
          confidence: 1.0,
          required_fields: ['id', 'timestamp', 'type', 'payload.user_id', 'payload.changes'],
          optional_fields: ['payload.updated_by'],
          forbidden_fields: ['payload.email', 'payload.deletion_reason'],
          description: 'Dispatched when an existing profile is modified.',
        },
        {
          variant_id: 'var_user_deleted',
          label: 'UserDeleted',
          discriminator_value: 'user.deleted',
          status: 'VALIDATED',
          observed_count: 420,
          confidence: 1.0,
          required_fields: ['id', 'timestamp', 'type', 'payload.user_id', 'payload.deletion_reason'],
          optional_fields: ['payload.scheduled_purge_date'],
          forbidden_fields: ['payload.email', 'payload.role', 'payload.changes'],
          description: 'Hard or soft user deletion record.',
        },
        {
          variant_id: 'var_user_archived',
          label: 'UserArchived',
          discriminator_value: 'user.archived',
          status: 'PROPOSED',
          observed_count: 85,
          confidence: 0.92,
          required_fields: ['id', 'timestamp', 'type', 'payload.user_id', 'payload.archived_until'],
          optional_fields: ['payload.archive_vault_id'],
          forbidden_fields: ['payload.deletion_reason'],
          description: 'Newly detected runtime variant: archived accounts preserved for compliance.',
        },
      ],
      consumers: [
        { consumer_id: 'audit-logger-svc', stance: 'ALREADY_TOLERATES', reason: 'Consumes common fields only' },
        { consumer_id: 'billing-dispatcher', stance: 'IGNORES', reason: 'Filters only billing related events' },
        { consumer_id: 'crm-sync-worker', stance: 'POTENTIALLY_BREAKING', reason: 'Exhaustive switch expects known types' },
      ],
    },
    {
      schema_id: 'poly_payment_response_v2',
      route: '/api/v2/payments/checkout',
      method: 'POST',
      version: '2.0.0',
      status: 'INFERRED',
      kind: 'DISCRIMINATED_UNION',
      discriminator: {
        field: 'status',
        location: 'BODY',
        type: 'STRING_ENUM',
        observed_values: ['SUCCESS', 'REQUIRES_ACTION', 'FAILED'],
        is_explicit: true,
        confidence: 0.98,
      },
      common_fields: ['transaction_id', 'amount', 'currency', 'status'],
      variants: [
        {
          variant_id: 'var_pay_success',
          label: 'PaymentSuccess',
          discriminator_value: 'SUCCESS',
          status: 'VALIDATED',
          observed_count: 6200,
          confidence: 1.0,
          required_fields: ['transaction_id', 'amount', 'currency', 'status', 'receipt_url', 'settled_at'],
          optional_fields: ['fee_breakdown'],
          forbidden_fields: ['action_url', 'failure_code'],
          description: 'Successful transaction completion.',
        },
        {
          variant_id: 'var_pay_action',
          label: 'PaymentRequiresAction',
          discriminator_value: 'REQUIRES_ACTION',
          status: 'INFERRED',
          observed_count: 410,
          confidence: 0.95,
          required_fields: ['transaction_id', 'amount', 'currency', 'status', 'action_url', 'action_type'],
          optional_fields: ['next_retry'],
          forbidden_fields: ['receipt_url', 'failure_code'],
          description: '3D Secure or customer authentication required before completion.',
        },
        {
          variant_id: 'var_pay_failed',
          label: 'PaymentFailed',
          discriminator_value: 'FAILED',
          status: 'VALIDATED',
          observed_count: 230,
          confidence: 0.99,
          required_fields: ['transaction_id', 'amount', 'currency', 'status', 'failure_code', 'failure_message'],
          optional_fields: ['decline_reason'],
          forbidden_fields: ['receipt_url', 'action_url'],
          description: 'Declined transaction with provider error code.',
        },
      ],
      consumers: [
        { consumer_id: 'frontend-checkout-app', stance: 'ALREADY_TOLERATES', reason: 'Handles action redirect' },
        { consumer_id: 'analytics-pipeline', stance: 'ALREADY_TOLERATES', reason: 'Captures all status transitions' },
      ],
    },
    {
      schema_id: 'poly_members_query_v1',
      route: '/api/v1/workspace/members',
      method: 'GET',
      version: '1.0.0',
      status: 'UNCERTAIN',
      kind: 'UNKNOWN_POLYMORPHIC_RESPONSE',
      discriminator: {
        field: 'FIELD_PRESENCE:permissions',
        location: 'BODY',
        type: 'INFERRED_STRUCTURAL',
        observed_values: ['permissions_present', 'permissions_absent'],
        is_explicit: false,
        confidence: 0.61,
      },
      common_fields: ['member_id', 'name', 'email'],
      variants: [
        {
          variant_id: 'var_member_basic',
          label: 'BasicMemberProfile',
          discriminator_value: 'permissions_absent',
          status: 'UNCERTAIN',
          observed_count: 154,
          confidence: 0.65,
          required_fields: ['member_id', 'name', 'email'],
          optional_fields: ['department'],
          forbidden_fields: [],
          description: 'Profile returned without permissions. Overlaps with admin profile.',
        },
        {
          variant_id: 'var_member_admin',
          label: 'AdminMemberProfile',
          discriminator_value: 'permissions_present',
          status: 'UNCERTAIN',
          observed_count: 142,
          confidence: 0.58,
          required_fields: ['member_id', 'name', 'email', 'permissions'],
          optional_fields: ['role_title'],
          forbidden_fields: [],
          description: 'Ambiguous variant: permissions could be optional field or distinct variant.',
        },
      ],
      consumers: [
        { consumer_id: 'admin-dashboard', stance: 'UNCERTAIN', reason: 'Ambiguous variant separation' },
      ],
    },
  ],
  cross_language_translations: [
    {
      contract_name: 'AuditEventUnion',
      languages: [
        { language: 'TypeScript', syntax: 'type Event = UserCreated | UserUpdated | UserDeleted;' },
        { language: 'Python', syntax: 'Event = Union[UserCreatedModel, UserUpdatedModel, UserDeletedModel]' },
        { language: 'Rust', syntax: 'enum Event { UserCreated(UserCreated), UserUpdated(UserUpdated), ... }' },
      ],
      semantic_equivalence: 'SAME_SEMANTIC_UNION',
      confidence: 0.99,
      evidence: 'Bi-directional payload test passed on 10,000 observations.',
    },
  ],
  why_polymorphic_drift_cases: [
    {
      id: 'why_01',
      title: 'Variant user.archived vs Schema Drift',
      verdict: 'POLYMORPHIC_VARIANTS (Not schema drift)',
      causal_chain: [
        'Observed 85 payloads with type="user.archived"',
        'Discriminator field "type" cleanly partitions payload structure',
        'Common fields (id, timestamp, type, source) remain strictly 100% compliant',
        'Payload fields (archived_until) follow consistent schema within discriminator partition',
        'Classified as VARIANT_ADDED rather than BREAKING_SCHEMA_DRIFT',
      ],
    },
  ],
};

export const PolymorphicSchemaPanel: React.FC<PolymorphicSchemaPanelProps> = ({ missionId: _missionId }) => {
  const [data, setData] = useState(FALLBACK_POLYMORPHIC_DATA);
  const [activeTab, setActiveTab] = useState<'overview' | 'discriminator' | 'variants' | 'compatibility' | 'consumers' | 'cross_lang' | 'approval' | 'why'>('overview');
  const [selectedSchemaId, setSelectedSchemaId] = useState<string>('poly_events_v1');
  const [reviewActionSuccess, setReviewActionSuccess] = useState<string | null>(null);

  const selectedSchema = data.polymorphic_schemas.find((s) => s.schema_id === selectedSchemaId) || data.polymorphic_schemas[0];

  const handleReviewVariant = (variantId: string, action: 'APPROVE' | 'REJECT' | 'REQUEST_EVIDENCE') => {
    setData((prev) => ({
      ...prev,
      polymorphic_schemas: prev.polymorphic_schemas.map((s) => {
        if (s.schema_id !== selectedSchema.schema_id) return s;
        return {
          ...s,
          variants: s.variants.map((v) => {
            if (v.variant_id !== variantId) return v;
            return {
              ...v,
              status: action === 'APPROVE' ? 'VALIDATED' : action === 'REJECT' ? 'REJECTED' : 'UNCERTAIN',
            };
          }),
        };
      }),
    }));
    setReviewActionSuccess(`Variant ${variantId} marked as ${action} successfully.`);
    setTimeout(() => setReviewActionSuccess(null), 4000);
  };

  const handleRollback = (variantId: string) => {
    setData((prev) => ({
      ...prev,
      polymorphic_schemas: prev.polymorphic_schemas.map((s) => {
        if (s.schema_id !== selectedSchema.schema_id) return s;
        return {
          ...s,
          variants: s.variants.filter((v) => v.variant_id !== variantId),
        };
      }),
    }));
    setReviewActionSuccess(`Variant ${variantId} rolled back successfully to previous baseline.`);
    setTimeout(() => setReviewActionSuccess(null), 4000);
  };

  return (
    <div data-testid="polymorphic-contracts-panel" className="space-y-6 rounded-xl border border-slate-800 bg-slate-950/80 p-6 text-slate-200 backdrop-blur-md">
      {/* Top Banner / Security Sentinel Badge */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800/80 pb-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-indigo-500/20 text-indigo-400 ring-1 ring-indigo-500/40">
            <Split className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-base font-bold tracking-tight text-white flex items-center gap-2">
              Governação Polimórfica & Variantes de Contrato
              <span className="rounded bg-indigo-500/20 px-2 py-0.5 text-[10px] font-mono font-medium text-indigo-300 border border-indigo-500/30">
                FASE 47
              </span>
            </h2>
            <p className="text-xs text-slate-400">
              Distingue Uniões Discriminadas de Schema Drift sem adivinhar variantes arbitrárias.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 rounded-lg border border-emerald-500/30 bg-emerald-950/30 px-3 py-1.5 text-xs text-emerald-300">
            <ShieldCheck className="h-4 w-4 text-emerald-400" />
            <span>Sentinel: <strong>{data.security_sentinel.status}</strong> ({data.security_sentinel.prompt_injections_blocked} Injeções Bloqueadas)</span>
          </div>
          <div className="flex items-center gap-2 rounded-lg border border-slate-800 bg-slate-900/60 px-3 py-1.5 text-xs text-slate-300">
            <Lock className="h-3.5 w-3.5 text-slate-400" />
            <span>Passivo como Dado</span>
          </div>
        </div>
      </div>

      {reviewActionSuccess && (
        <div className="flex items-center justify-between rounded-lg border border-emerald-500/40 bg-emerald-950/40 px-4 py-2.5 text-xs text-emerald-200">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-emerald-400" />
            <span>{reviewActionSuccess}</span>
          </div>
          <button onClick={() => setReviewActionSuccess(null)} className="text-emerald-400 hover:text-white">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Navigation Sub-Tabs */}
      <div className="flex flex-wrap gap-2 border-b border-slate-800 pb-2">
        {[
          { id: 'overview', label: 'Visão Geral & Métricas', testId: 'polymorphic-overview-tab', icon: Layers },
          { id: 'discriminator', label: 'Discriminadores & Roteamento', testId: 'discriminator-routing-tab', icon: GitBranch },
          { id: 'variants', label: 'Variantes & Requiredness', testId: 'variants-schemas-tab', icon: Split },
          { id: 'compatibility', label: 'Matriz de Compatibilidade', testId: 'compatibility-matrix-tab', icon: ShieldCheck },
          { id: 'consumers', label: 'Impacto em Consumidores', testId: 'consumer-impact-tab', icon: Users },
          { id: 'cross_lang', label: 'Grafo Cross-Language', testId: 'cross-language-tab', icon: Code2 },
          { id: 'approval', label: 'Revisão Humana & Rollback', testId: 'human-approval-tab', icon: Sparkles },
          { id: 'why', label: 'Porquê Drift Polimórfico', testId: 'why-polymorphic-tab', icon: Info },
        ].map((tab) => {
          const isActive = activeTab === tab.id;
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              data-testid={tab.testId}
              onClick={() => setActiveTab(tab.id as any)}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-all ${
                isActive
                  ? 'bg-indigo-600 text-white shadow-sm shadow-indigo-600/30'
                  : 'text-slate-400 hover:bg-slate-900 hover:text-slate-200'
              }`}
            >
              <Icon className="h-3.5 w-3.5" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Main Content Sections */}

      {/* 1. OVERVIEW TAB */}
      {activeTab === 'overview' && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
            <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-3.5">
              <span className="text-[11px] font-medium text-slate-400">Schemas Polimórficos</span>
              <p className="mt-1 text-xl font-bold text-white">{data.monitored_polymorphic_count}</p>
              <span className="text-[10px] text-indigo-400">Rotas mapeadas</span>
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-3.5">
              <span className="text-[11px] font-medium text-slate-400">Total Variantes</span>
              <p className="mt-1 text-xl font-bold text-white">{data.total_variants_count}</p>
              <span className="text-[10px] text-slate-400">Em 4 contratos</span>
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-3.5">
              <span className="text-[11px] font-medium text-slate-400">Determinísticas</span>
              <p className="mt-1 text-xl font-bold text-emerald-400" data-testid="status-deterministic">{data.deterministic_count}</p>
              <span className="text-[10px] text-emerald-500/80">Discriminador explícito</span>
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-3.5">
              <span className="text-[11px] font-medium text-slate-400">Inferidas / Propostas</span>
              <p className="mt-1 text-xl font-bold text-amber-400" data-testid="status-inferred">{data.inferred_count}</p>
              <span className="text-[10px] text-amber-500/80">Requer validação</span>
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-3.5">
              <span className="text-[11px] font-medium text-slate-400">Casos Ambíguos</span>
              <p className="mt-1 text-xl font-bold text-rose-400" data-testid="status-uncertain">{data.uncertain_count}</p>
              <span className="text-[10px] text-rose-500/80">UNCERTAIN (sem chute)</span>
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-3.5">
              <span className="text-[11px] font-medium text-slate-400">Compatibilidade</span>
              <p className="mt-1 text-xl font-bold text-indigo-400">{data.compatibility_rate}</p>
              <span className="text-[10px] text-slate-400">Subconjuntos válidos</span>
            </div>
          </div>

          {/* Schema Selector & Detail Card */}
          <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-4">
            <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
              <div className="flex items-center gap-2">
                <Filter className="h-4 w-4 text-indigo-400" />
                <span className="text-xs font-semibold text-slate-300">Contrato Polimórfico Ativo:</span>
                <select
                  data-testid="polymorphic-schema-select"
                  value={selectedSchemaId}
                  onChange={(e) => setSelectedSchemaId(e.target.value)}
                  className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-1.5 text-xs text-white focus:border-indigo-500 focus:outline-none"
                >
                  {data.polymorphic_schemas.map((s) => (
                    <option key={s.schema_id} value={s.schema_id}>
                      {s.method} {s.route} ({s.kind})
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex items-center gap-2 text-xs">
                <span className="text-slate-400">Versão: <strong className="text-slate-200">{selectedSchema.version}</strong></span>
                <span className="text-slate-600">•</span>
                <span className="text-slate-400">Status: <span className="rounded bg-indigo-500/20 px-2 py-0.5 text-[10px] font-bold text-indigo-300 border border-indigo-500/30">{selectedSchema.status}</span></span>
              </div>
            </div>

            {/* Invariant Alert Box */}
            <div className="rounded-lg border border-blue-500/20 bg-blue-950/20 p-3.5 text-xs text-blue-300 flex items-start gap-3">
              <Info className="h-4 w-4 text-blue-400 shrink-0 mt-0.5" />
              <div>
                <strong>Invariante Formal:</strong> <code className="text-blue-200">VARIANT ≠ CONTRACT</code>. Uma variante observada em runtime jamais é promovida a contrato universal sem evidência formal e validação humana. Campos ambíguos permanecem estritamente <code className="text-amber-300">UNCERTAIN</code>.
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 2. DISCRIMINATORS TAB */}
      {activeTab === 'discriminator' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white">Resolução de Discriminadores</h3>
            <span className="text-xs text-slate-400">Suporta discriminadores explícitos e inferidos não-autoritativos</span>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {/* Explicit Discriminator Card */}
            <div data-testid="explicit-discriminator-card" className="rounded-lg border border-emerald-500/30 bg-slate-900/60 p-4 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                  <h4 className="text-xs font-bold text-emerald-300">Discriminador Explícito</h4>
                </div>
                <span className="rounded bg-emerald-500/20 px-2 py-0.5 text-[10px] font-mono text-emerald-400 border border-emerald-500/30">
                  DETERMINISTIC
                </span>
              </div>
              <p className="text-xs text-slate-300">
                Campo discriminador identificado no payload com partição estrita de variantes:
              </p>
              <div className="rounded bg-slate-950 p-3 font-mono text-xs text-slate-300 space-y-1">
                <div>Field: <span className="text-emerald-400">"type"</span></div>
                <div>Location: <span className="text-indigo-400">BODY</span></div>
                <div>Type: <span className="text-amber-400">STRING_ENUM</span></div>
                <div>Values: <span className="text-slate-400">['user.created', 'user.updated', 'user.deleted', 'user.archived']</span></div>
                <div>Confidence: <span className="text-emerald-400">100% (13,960 amostras)</span></div>
              </div>
            </div>

            {/* Inferred Discriminator Card */}
            <div data-testid="inferred-discriminator-card" className="rounded-lg border border-amber-500/30 bg-slate-900/60 p-4 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4 text-amber-400" />
                  <h4 className="text-xs font-bold text-amber-300">Discriminador Inferido Estrutural</h4>
                </div>
                <span className="rounded bg-amber-500/20 px-2 py-0.5 text-[10px] font-mono text-amber-400 border border-amber-500/30">
                  INFERRED / PROPOSED
                </span>
              </div>
              <p className="text-xs text-slate-300">
                Deteção de candidato a variante com base em presença diferencial de campos:
              </p>
              <div className="rounded bg-slate-950 p-3 font-mono text-xs text-slate-300 space-y-1">
                <div>Field Candidate: <span className="text-amber-400">FIELD_PRESENCE:permissions</span></div>
                <div>Variant A: <span className="text-slate-400">name + email</span></div>
                <div>Variant B: <span className="text-slate-400">name + email + permissions</span></div>
                <div>Status: <span className="text-amber-400">Não promovido automaticamente</span></div>
                <div>Confidence: <span className="text-amber-400">61% (Ambiguidade detectada)</span></div>
              </div>
            </div>
          </div>

          {/* Ambiguous Warning Box */}
          <div data-testid="ambiguous-variant-warning" className="rounded-lg border border-rose-500/40 bg-rose-950/20 p-4 text-xs text-rose-300 space-y-2">
            <div className="flex items-center gap-2 font-bold text-rose-400">
              <HelpCircle className="h-4 w-4" />
              <span>Regra 28 — Variantes Ambíguas Mantidas como UNCERTAIN</span>
            </div>
            <p>
              Quando duas variantes observadas diferem apenas por campos opcionais sem discriminador explícito, o sistema recusa-se categoricamente a "chutar" uma variante. O estado permanece <strong>UNCERTAIN</strong> até o fornecimento de evidência humana ou anotação contratual formal.
            </p>
          </div>
        </div>
      )}

      {/* 3. VARIANTS & REQUIREDNESS TAB */}
      {activeTab === 'variants' && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white">Variantes do Contrato {selectedSchema.route}</h3>
            <span className="text-xs text-slate-400">Requiredness, Forbiddenness e Nullability por Variante</span>
          </div>

          {/* Common Fields Bar */}
          <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-3.5">
            <div className="text-xs font-semibold text-slate-300 mb-2 flex items-center gap-2">
              <Layers className="h-4 w-4 text-indigo-400" />
              <span>Campos Comuns Globais (Obrigatórios em 100% das variantes):</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {selectedSchema.common_fields.map((field) => (
                <span key={field} className="rounded bg-indigo-500/20 px-2.5 py-1 text-xs font-mono font-medium text-indigo-300 border border-indigo-500/30">
                  {field}
                </span>
              ))}
            </div>
          </div>

          {/* Requiredness Matrix Table */}
          <div data-testid="requiredness-matrix-table" className="overflow-x-auto rounded-lg border border-slate-800">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-900 text-slate-400 border-b border-slate-800">
                <tr>
                  <th className="px-4 py-3 font-semibold">Variante</th>
                  <th className="px-4 py-3 font-semibold">Discriminador</th>
                  <th className="px-4 py-3 font-semibold">Campos Required</th>
                  <th className="px-4 py-3 font-semibold">Campos Forbidden</th>
                  <th className="px-4 py-3 font-semibold">Observações</th>
                  <th className="px-4 py-3 font-semibold">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800 bg-slate-950/40">
                {selectedSchema.variants.map((v) => (
                  <tr key={v.variant_id} className="hover:bg-slate-900/40">
                    <td className="px-4 py-3 font-medium text-white">
                      <div>{v.label}</div>
                      <div className="text-[10px] text-slate-500 font-mono">{v.variant_id}</div>
                    </td>
                    <td className="px-4 py-3 font-mono text-indigo-300">{v.discriminator_value}</td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1">
                        {v.required_fields.map((f) => (
                          <span key={f} className="rounded bg-emerald-500/10 px-1.5 py-0.5 text-[10px] font-mono text-emerald-300 border border-emerald-500/20">
                            {f}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1">
                        {v.forbidden_fields.length > 0 ? (
                          v.forbidden_fields.map((f) => (
                            <span key={f} className="rounded bg-rose-500/10 px-1.5 py-0.5 text-[10px] font-mono text-rose-300 border border-rose-500/20">
                              {f}
                            </span>
                          ))
                        ) : (
                          <span className="text-slate-600 text-[10px]">nenhum</span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 font-mono text-slate-300">{v.observed_count}x</td>
                    <td className="px-4 py-3">
                      <span
                        className={`rounded px-2 py-0.5 text-[10px] font-bold border ${
                          v.status === 'VALIDATED'
                            ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                            : v.status === 'PROPOSED'
                            ? 'bg-amber-500/20 text-amber-300 border-amber-500/30'
                            : 'bg-rose-500/20 text-rose-300 border-rose-500/30'
                        }`}
                      >
                        {v.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Variant Diff Viewer */}
          <div data-testid="variant-diff-viewer" className="rounded-lg border border-slate-800 bg-slate-900/40 p-4 space-y-3">
            <h4 className="text-xs font-bold text-slate-300 flex items-center gap-2">
              <Code2 className="h-4 w-4 text-indigo-400" />
              <span>Diff Estrutural entre Variantes (UserCreated vs UserArchived)</span>
            </h4>
            <pre className="rounded bg-slate-950 p-3 font-mono text-xs text-slate-300 overflow-x-auto">
{`+ VARIANT_ADDED: UserArchived (discriminator='user.archived')
+ required: payload.user_id: string
+ required: payload.archived_until: timestamp
+ optional: payload.archive_vault_id: string
- forbidden: payload.deletion_reason
CLASSIFICATION: NON_BREAKING (Adição aditiva de variante em união aberta)`}
            </pre>
          </div>
        </div>
      )}

      {/* 4. COMPATIBILITY MATRIX TAB */}
      {activeTab === 'compatibility' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white">Matriz de Compatibilidade de Variantes (Old vs New)</h3>
            <span className="text-xs text-slate-400">Verificação formal de quebras de contrato</span>
          </div>

          <div className="overflow-x-auto rounded-lg border border-slate-800">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-900 text-slate-400 border-b border-slate-800">
                <tr>
                  <th className="px-4 py-3 font-semibold">Variante Original (v1)</th>
                  <th className="px-4 py-3 font-semibold">Variante Candidata (v2)</th>
                  <th className="px-4 py-3 font-semibold">Veredicto</th>
                  <th className="px-4 py-3 font-semibold">Justificação Formal</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800 bg-slate-950/40">
                <tr className="hover:bg-slate-900/40">
                  <td className="px-4 py-3 font-mono text-slate-300">UserCreated (v1)</td>
                  <td className="px-4 py-3 font-mono text-slate-300">UserCreated (v2)</td>
                  <td className="px-4 py-3">
                    <span className="rounded bg-emerald-500/20 px-2 py-0.5 text-[10px] font-bold text-emerald-300 border border-emerald-500/30">
                      COMPATIBLE
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-400">Estrutura idêntica, campos obrigatórios preservados.</td>
                </tr>
                <tr className="hover:bg-slate-900/40">
                  <td className="px-4 py-3 font-mono text-slate-300">UserCreated (v1)</td>
                  <td className="px-4 py-3 font-mono text-slate-300">UserArchived (v2)</td>
                  <td className="px-4 py-3">
                    <span className="rounded bg-rose-500/20 px-2 py-0.5 text-[10px] font-bold text-rose-300 border border-rose-500/30">
                      INCOMPATIBLE
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-400">Discriminador diferente ('user.created' ≠ 'user.archived'). Não intercambiáveis diretamente.</td>
                </tr>
                <tr className="hover:bg-slate-900/40">
                  <td className="px-4 py-3 font-mono text-slate-300">Union [Created, Updated, Deleted]</td>
                  <td className="px-4 py-3 font-mono text-slate-300">Union [Created, Updated, Deleted, Archived]</td>
                  <td className="px-4 py-3">
                    <span className="rounded bg-amber-500/20 px-2 py-0.5 text-[10px] font-bold text-amber-300 border border-amber-500/30">
                      POTENTIALLY_BREAKING
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-400">Compatível para produtores flexíveis; potencialmente quebra consumidores com pattern matching estrito/exaustivo.</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 5. CONSUMER IMPACT TAB */}
      {activeTab === 'consumers' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white">Impacto em Consumidores Registados</h3>
            <span className="text-xs text-slate-400">Rastreabilidade via ContractConsumerRegistry</span>
          </div>

          <div data-testid="consumer-impact-table" className="overflow-x-auto rounded-lg border border-slate-800">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-900 text-slate-400 border-b border-slate-800">
                <tr>
                  <th className="px-4 py-3 font-semibold">Consumidor</th>
                  <th className="px-4 py-3 font-semibold">Postura perante Nova Variante</th>
                  <th className="px-4 py-3 font-semibold">Evidência Estrutural</th>
                  <th className="px-4 py-3 font-semibold">Plano de Mitigação</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800 bg-slate-950/40">
                {selectedSchema.consumers.map((c) => (
                  <tr key={c.consumer_id} className="hover:bg-slate-900/40">
                    <td className="px-4 py-3 font-mono text-white">{c.consumer_id}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`rounded px-2 py-0.5 text-[10px] font-bold border ${
                          c.stance === 'ALREADY_TOLERATES'
                            ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                            : c.stance === 'IGNORES'
                            ? 'bg-slate-700/40 text-slate-300 border-slate-600'
                            : c.stance === 'POTENTIALLY_BREAKING'
                            ? 'bg-amber-500/20 text-amber-300 border-amber-500/30'
                            : 'bg-rose-500/20 text-rose-300 border-rose-500/30'
                        }`}
                      >
                        {c.stance}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-300">{c.reason}</td>
                    <td className="px-4 py-3 text-slate-400">
                      {c.stance === 'POTENTIALLY_BREAKING'
                        ? 'Tarefa derivada gerada: atualizar switch statement com caso default ou handler específico'
                        : 'Nenhuma ação necessária'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 6. CROSS-LANGUAGE TRANSLATION TAB */}
      {activeTab === 'cross_lang' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white">Grafo Semântico Cross-Language</h3>
            <span className="text-xs text-slate-400">Equivalência de tipos de uniões entre TypeScript e Python</span>
          </div>

          {data.cross_language_translations.map((t, idx) => (
            <div key={idx} data-testid="cross-language-card" className="rounded-lg border border-slate-800 bg-slate-900/50 p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-white">{t.contract_name}</span>
                <span className="rounded bg-indigo-500/20 px-2 py-0.5 text-[10px] font-bold text-indigo-300 border border-indigo-500/30">
                  {t.semantic_equivalence} ({(t.confidence * 100).toFixed(0)}%)
                </span>
              </div>
              <div className="space-y-2">
                {t.languages.map((l, lIdx) => (
                  <div key={lIdx} className="rounded bg-slate-950 p-2.5 font-mono text-xs flex items-center justify-between">
                    <span className="text-indigo-400 font-bold">{l.language}:</span>
                    <span className="text-slate-200">{l.syntax}</span>
                  </div>
                ))}
              </div>
              <p className="text-[11px] text-slate-400 italic">
                Evidência: {t.evidence}
              </p>
            </div>
          ))}
        </div>
      )}

      {/* 7. HUMAN APPROVAL & ROLLBACK TAB */}
      {activeTab === 'approval' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white">Revisão Humana de Variantes & Governação</h3>
            <span className="text-xs text-slate-400">Aprovação explícita antes da promoção de variantes</span>
          </div>

          <div className="space-y-3">
            {selectedSchema.variants.map((v) => (
              <div key={v.variant_id} className="rounded-lg border border-slate-800 bg-slate-900/50 p-4 flex flex-wrap items-center justify-between gap-4">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-white">{v.label}</span>
                    <span className="text-[10px] font-mono text-slate-400">({v.discriminator_value})</span>
                    <span className={`rounded px-1.5 py-0.2 text-[9px] font-bold ${
                      v.status === 'VALIDATED' ? 'bg-emerald-500/20 text-emerald-300' : 'bg-amber-500/20 text-amber-300'
                    }`}>
                      {v.status}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400">{v.description}</p>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    data-testid="btn-approve-variant"
                    onClick={() => handleReviewVariant(v.variant_id, 'APPROVE')}
                    className="flex items-center gap-1 rounded bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-500 transition-all"
                  >
                    <Check className="h-3.5 w-3.5" />
                    Aprovar
                  </button>
                  <button
                    data-testid="btn-reject-variant"
                    onClick={() => handleReviewVariant(v.variant_id, 'REJECT')}
                    className="flex items-center gap-1 rounded bg-rose-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-rose-500 transition-all"
                  >
                    <X className="h-3.5 w-3.5" />
                    Rejeitar
                  </button>
                  <button
                    data-testid="btn-request-evidence"
                    onClick={() => handleReviewVariant(v.variant_id, 'REQUEST_EVIDENCE')}
                    className="flex items-center gap-1 rounded bg-amber-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-amber-500 transition-all"
                  >
                    <HelpCircle className="h-3.5 w-3.5" />
                    Pedir Evidência
                  </button>
                  <button
                    data-testid="btn-rollback-variant"
                    onClick={() => handleRollback(v.variant_id)}
                    className="flex items-center gap-1 rounded border border-slate-700 bg-slate-800 px-3 py-1.5 text-xs font-semibold text-slate-300 hover:bg-slate-700 transition-all"
                  >
                    <RotateCcw className="h-3.5 w-3.5" />
                    Rollback
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 8. WHY POLYMORPHIC DRIFT TAB */}
      {activeTab === 'why' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white">Painel do Porquê: Causalidade e Diferenciação</h3>
            <span className="text-xs text-slate-400">Porquê variação foi classificada como Variante e não Drift de Ruído</span>
          </div>

          <div data-testid="why-explanation-card" className="space-y-4">
            {data.why_polymorphic_drift_cases.map((c) => (
              <div key={c.id} className="rounded-lg border border-indigo-500/30 bg-slate-900/50 p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold text-indigo-300">{c.title}</h4>
                  <span className="rounded bg-indigo-500/20 px-2 py-0.5 text-[10px] font-bold text-indigo-300 border border-indigo-500/30">
                    {c.verdict}
                  </span>
                </div>
                <div className="space-y-1.5 text-xs text-slate-300">
                  {c.causal_chain.map((step, sIdx) => (
                    <div key={sIdx} className="flex items-start gap-2">
                      <span className="text-indigo-400 font-mono">[{sIdx + 1}]</span>
                      <span>{step}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
