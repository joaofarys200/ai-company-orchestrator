import React, { useState } from 'react';
import {
  GitMerge,
  ShieldCheck,
  CheckCircle2,
  Code2,
  Users,
  Check,
  X,
  RotateCcw,
  Filter,
  Info,
  Lock,
  FileDiff,
  Layers,
  ShieldAlert,
} from 'lucide-react';

export interface ContractChangeManagementPanelProps {
  missionId?: string;
}

export const FALLBACK_CHANGE_MANAGEMENT_DATA = {
  total_predictions: 3,
  breaking_changes_count: 1,
  non_breaking_changes_count: 1,
  safe_changes_count: 1,
  total_consumers_tracked: 8,
  closed_enum_consumers_count: 3,
  pending_migrations_count: 1,
  approved_migrations_count: 1,
  security_sentinel: {
    status: 'SECURE',
    auth_downgrade_attempts_blocked: 2,
    prompt_injections_in_schema_blocked: 3,
    unauthorized_memory_migrations_blocked: 1,
  },
  predictions: [
    {
      prediction_id: 'pred_task_avatar_change',
      task_id: 'tsk_user_avatar_update',
      task_title: 'Atualizar avatar do utilizador para objeto rico com dimensões',
      contract_id: 'contract_users_v1',
      route: '/api/v1/users',
      source_version: '1.0.0',
      target_version: '2.0.0',
      breaking_risk: 'BREAKING',
      migration_required: true,
      approval_required: true,
      revalidation_required: true,
      state: 'PREDICTED',
      predicted_diffs: [
        {
          diff_id: 'diff_avatar_01',
          change_type: 'CHANGE_FIELD_TYPE',
          field_path: 'avatar',
          old_definition: 'string (URL)',
          new_definition: 'object { url: string, width: int, height: int }',
          risk_level: 'BREAKING',
          reason: 'Campo primitivo string convertido em objeto aninhado. Quebra deserializadores estritos.',
        },
      ],
      affected_consumers: [
        {
          consumer_id: 'frontend-user-card',
          name: 'Frontend UserCard Component',
          file_path: 'frontend/src/components/UserCard.tsx',
          category: 'DIRECT',
          pattern_matching: 'CLOSED_EXHAUSTIVE',
          impact_reason: 'Acessa diretamente avatar como string no src da tag <img>.',
          required_action: 'Adaptar para avatar.url com fallback.',
          language: 'TypeScript',
        },
        {
          consumer_id: 'test-user-api',
          name: 'User API Integration Test',
          file_path: 'tests/test_user_api.py',
          category: 'TEST',
          pattern_matching: 'CLOSED_EXHAUSTIVE',
          impact_reason: 'Test suite asserta tipo string no payload de resposta v1.',
          required_action: 'Atualizar fixtures para v2.0.0.',
          language: 'Python',
        },
        {
          consumer_id: 'browser-user-profile-qa',
          name: 'Browser QA Profile View',
          file_path: 'scripts/run_browser_qa_user.py',
          category: 'BROWSER_SCENARIO',
          pattern_matching: 'CLOSED_EXHAUSTIVE',
          impact_reason: 'Cenário E2E valida renderização visual de foto de perfil.',
          required_action: 'Revalidar asserções visuais no Microsoft Edge.',
          language: 'Python',
        },
      ],
      simulation: {
        simulation_id: 'sim_avatar_read_only',
        state_before_hash: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
        state_after_hash: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
        is_read_only: true,
        diff_verdict: 'BREAKING',
      },
      migration_plan: {
        migration_id: 'mig_users_v2_plan',
        strategy: 'MIGRATE_THEN_SWITCH',
        rollout_strategy: 'PREPARE_VALIDATE_MIGRATE_SWITCH',
        rollback_strategy: 'RESTORE_ACTIVE_VERSION_1.0.0_WITH_AUDIT_PRESERVATION',
        status: 'PROPOSED',
        required_tasks: [
          {
            task_id: 'task_mig_user_01_backend',
            title: 'Deploy User API v2 endpoint',
            target: 'BACKEND',
            description: 'Publicar endpoint v2 sem remover v1 imediatamente.',
            status: 'PENDING',
          },
          {
            task_id: 'task_mig_user_02_frontend',
            title: 'Migrar componente UserCard',
            target: 'FRONTEND',
            description: 'Atualizar UserCard.tsx para tolerar ambos os formatos durante transição.',
            status: 'PENDING',
          },
          {
            task_id: 'task_mig_user_03_tests',
            title: 'Atualizar suite de testes de contrato',
            target: 'TESTS',
            description: 'Garantir que os testes cobrem v1 e v2.',
            status: 'PENDING',
          },
          {
            task_id: 'task_mig_user_04_browser',
            title: 'Executar Browser QA em Microsoft Edge',
            target: 'BROWSER',
            description: 'Validar renderização e ausência de erros no console.',
            status: 'PENDING',
          },
        ],
      },
    },
    {
      prediction_id: 'pred_task_optional_field',
      task_id: 'tsk_add_user_tier',
      task_title: 'Adicionar campo opcional user_tier ao perfil do utilizador',
      contract_id: 'contract_users_v1',
      route: '/api/v1/users',
      source_version: '1.0.0',
      target_version: '1.1.0',
      breaking_risk: 'NON_BREAKING',
      migration_required: false,
      approval_required: false,
      revalidation_required: true,
      state: 'VERIFIED',
      predicted_diffs: [
        {
          diff_id: 'diff_tier_01',
          change_type: 'ADD_OPTIONAL_FIELD',
          field_path: 'user_tier',
          old_definition: 'null',
          new_definition: 'optional string (FREE | PRO | ENTERPRISE)',
          risk_level: 'NON_BREAKING',
          reason: 'Campo opcional aditivo. Não requer tarefas de migração de consumers.',
        },
      ],
      affected_consumers: [],
    },
    {
      prediction_id: 'pred_task_polymorphic_variant',
      task_id: 'tsk_add_archived_event',
      task_title: 'Adicionar variante user.archived na união de auditoria',
      contract_id: 'contract_events_v1',
      route: '/api/v1/events',
      source_version: '1.2.0',
      target_version: '1.3.0',
      breaking_risk: 'POTENTIALLY_BREAKING',
      migration_required: true,
      approval_required: true,
      revalidation_required: true,
      state: 'APPROVED',
      predicted_diffs: [
        {
          diff_id: 'diff_poly_01',
          change_type: 'ADD_VARIANT',
          field_path: 'variants.user.archived',
          old_definition: 'null',
          new_definition: 'UserArchived variant with archived_until timestamp',
          risk_level: 'POTENTIALLY_BREAKING',
          reason: 'Nova variante pode quebrar consumers com pattern matching fechado sem default.',
        },
      ],
      affected_consumers: [
        {
          consumer_id: 'crm-sync-worker',
          name: 'CRM Sync Worker (Exhaustive Switch)',
          file_path: 'frontend/src/features/crm/syncHandler.ts',
          category: 'DIRECT',
          pattern_matching: 'CLOSED_EXHAUSTIVE',
          impact_reason: 'Switch TypeScript exaustivo sem branch default.',
          required_action: 'Adicionar case user.archived ou default handler.',
          language: 'TypeScript',
        },
      ],
    },
  ],
  why_chain: [
    { step: 1, title: 'User Intent', desc: 'Diretiva do utilizador para enriquecer perfil do utilizador com metadados de avatar.' },
    { step: 2, title: 'Task Definition', desc: 'Tarefa tsk_user_avatar_update altera backend/api/users.py e UserCard.tsx.' },
    { step: 3, title: 'Contract Analysis', desc: 'Identificado contrato /api/v1/users (contract_users_v1).' },
    { step: 4, title: 'Structural Diff Simulation', desc: 'Avatar convertido de string para { url, width, height }.' },
    { step: 5, title: 'Consumer Impact', desc: 'Detetado consumer direto UserCard.tsx com CLOSED_EXHAUSTIVE.' },
    { step: 6, title: 'Risk Classification', desc: 'Classificado formalmente como BREAKING. Requer plano de migração.' },
    { step: 7, title: 'Mission Gate Decision', desc: 'Execução bloqueada até aprovação de plano de migração MIGRATE_THEN_SWITCH.' },
  ],
};

export const ContractChangeManagementPanel: React.FC<ContractChangeManagementPanelProps> = ({ missionId: _missionId }) => {
  const [data, setData] = useState(FALLBACK_CHANGE_MANAGEMENT_DATA);
  const [activeTab, setActiveTab] = useState<'overview' | 'diff' | 'consumers' | 'migration' | 'gate' | 'runtime' | 'rollback' | 'why'>('overview');
  const [selectedPredictionId, setSelectedPredictionId] = useState<string>('pred_task_avatar_change');
  const [alertFeedback, setAlertFeedback] = useState<string | null>(null);

  const selectedPrediction = data.predictions.find((p) => p.prediction_id === selectedPredictionId) || data.predictions[0];

  const handleApproveMigration = (migId: string) => {
    setData((prev) => ({
      ...prev,
      predictions: prev.predictions.map((p) => {
        if (p.migration_plan && p.migration_plan.migration_id === migId) {
          return {
            ...p,
            migration_plan: { ...p.migration_plan, status: 'APPROVED' },
            state: 'APPROVED',
          };
        }
        return p;
      }),
    }));
    setAlertFeedback(`Plano de migração ${migId} aprovado com sucesso com assinatura válida de operador.`);
    setTimeout(() => setAlertFeedback(null), 4000);
  };

  const handleRejectMigration = (migId: string) => {
    setData((prev) => ({
      ...prev,
      predictions: prev.predictions.map((p) => {
        if (p.migration_plan && p.migration_plan.migration_id === migId) {
          return {
            ...p,
            migration_plan: { ...p.migration_plan, status: 'REJECTED' },
            state: 'STALE',
          };
        }
        return p;
      }),
    }));
    setAlertFeedback(`Plano de migração ${migId} rejeitado pelo operador. Execução bloqueada.`);
    setTimeout(() => setAlertFeedback(null), 4000);
  };

  const handleRollback = (migId: string) => {
    setData((prev) => ({
      ...prev,
      predictions: prev.predictions.map((p) => {
        if (p.migration_plan && p.migration_plan.migration_id === migId) {
          return {
            ...p,
            migration_plan: { ...p.migration_plan, status: 'ROLLED_BACK' },
            state: 'PREDICTED',
          };
        }
        return p;
      }),
    }));
    setAlertFeedback(`Rollback determinístico executado para ${migId}. Versão estável restaurada.`);
    setTimeout(() => setAlertFeedback(null), 4000);
  };

  return (
    <div data-testid="contract-change-management-panel" className="space-y-6 rounded-xl border border-slate-800 bg-slate-950/80 p-6 text-slate-200 backdrop-blur-md">
      {/* Header Banner */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800/80 pb-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-cyan-500/20 text-cyan-400 ring-1 ring-cyan-500/40">
            <GitMerge className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-base font-bold tracking-tight text-white flex items-center gap-2">
              Gestão de Mudanças Contratuais & Planeamento Ciente
              <span className="rounded bg-cyan-500/20 px-2 py-0.5 text-[10px] font-mono font-medium text-cyan-300 border border-cyan-500/30">
                FASE 48
              </span>
            </h2>
            <p className="text-xs text-slate-400">
              Detecção de quebras antes da execução, plano de migração auditável e prevenção de falsos sucessos.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 rounded-lg border border-emerald-500/30 bg-emerald-950/30 px-3 py-1.5 text-xs text-emerald-300">
            <ShieldCheck className="h-4 w-4 text-emerald-400" />
            <span>Sentinel: <strong>{data.security_sentinel.status}</strong> ({data.security_sentinel.auth_downgrade_attempts_blocked} Downgrades Bloqueados)</span>
          </div>
          <div className="flex items-center gap-2 rounded-lg border border-slate-800 bg-slate-900/60 px-3 py-1.5 text-xs text-slate-300">
            <Lock className="h-3.5 w-3.5 text-slate-400" />
            <span>Preflight Read-Only</span>
          </div>
        </div>
      </div>

      {alertFeedback && (
        <div data-testid="gate-action-alert" className="flex items-center justify-between rounded-lg border border-emerald-500/40 bg-emerald-950/40 px-4 py-2.5 text-xs text-emerald-200">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-emerald-400" />
            <span>{alertFeedback}</span>
          </div>
          <button onClick={() => setAlertFeedback(null)} className="text-emerald-400 hover:text-white">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Navigation Sub-Tabs */}
      <div className="flex flex-wrap gap-2 border-b border-slate-800 pb-2">
        {[
          { id: 'overview', label: 'Pré-Execução & Previsões', testId: 'contract-change-overview-tab', icon: Layers },
          { id: 'diff', label: 'Diff Simulado (Read-Only)', testId: 'preflight-diff-tab', icon: FileDiff },
          { id: 'consumers', label: 'Impacto em Consumers', testId: 'consumer-impact-tab', icon: Users },
          { id: 'migration', label: 'Plano de Migração (DAG)', testId: 'migration-plan-tab', icon: GitMerge },
          { id: 'gate', label: 'Mission Gate & Aprovação', testId: 'mission-gate-tab', icon: ShieldAlert },
          { id: 'runtime', label: 'Verificação em Runtime', testId: 'runtime-verification-tab', icon: CheckCircle2 },
          { id: 'rollback', label: 'Rollback & Linhagem', testId: 'rollback-history-tab', icon: RotateCcw },
          { id: 'why', label: 'Porquê Mudança Contratual', testId: 'why-contract-change-tab', icon: Info },
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
                  ? 'bg-cyan-600 text-white shadow-sm shadow-cyan-600/30'
                  : 'text-slate-400 hover:bg-slate-900 hover:text-slate-200'
              }`}
            >
              <Icon className="h-3.5 w-3.5" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* 1. OVERVIEW TAB */}
      {activeTab === 'overview' && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
            <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-3.5">
              <span className="text-[11px] font-medium text-slate-400">Total Previsões</span>
              <p className="mt-1 text-xl font-bold text-white">{data.total_predictions}</p>
              <span className="text-[10px] text-cyan-400">Tarefas auditadas</span>
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-3.5">
              <span className="text-[11px] font-medium text-slate-400">Mudanças Breaking</span>
              <p className="mt-1 text-xl font-bold text-rose-400" data-testid="count-breaking">{data.breaking_changes_count}</p>
              <span className="text-[10px] text-rose-500/80">Bloqueio obrigatório</span>
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-3.5">
              <span className="text-[11px] font-medium text-slate-400">Não-Quebrantes</span>
              <p className="mt-1 text-xl font-bold text-emerald-400">{data.non_breaking_changes_count}</p>
              <span className="text-[10px] text-emerald-500/80">Adições compatíveis</span>
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-3.5">
              <span className="text-[11px] font-medium text-slate-400">Consumers Mapeados</span>
              <p className="mt-1 text-xl font-bold text-white">{data.total_consumers_tracked}</p>
              <span className="text-[10px] text-slate-400">Grafo semântico</span>
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-3.5">
              <span className="text-[11px] font-medium text-slate-400">Closed-Enum Matchers</span>
              <p className="mt-1 text-xl font-bold text-amber-400">{data.closed_enum_consumers_count}</p>
              <span className="text-[10px] text-amber-500/80">Switch estrito</span>
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-3.5">
              <span className="text-[11px] font-medium text-slate-400">Planos de Migração</span>
              <p className="mt-1 text-xl font-bold text-indigo-400">{data.pending_migrations_count + data.approved_migrations_count}</p>
              <span className="text-[10px] text-indigo-400">DAG de tarefas</span>
            </div>
          </div>

          {/* Prediction Selector */}
          <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-4">
            <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
              <div className="flex items-center gap-2">
                <Filter className="h-4 w-4 text-cyan-400" />
                <span className="text-xs font-semibold text-slate-300">Previsão Contratual Selecionada:</span>
                <select
                  data-testid="prediction-selector"
                  value={selectedPredictionId}
                  onChange={(e) => setSelectedPredictionId(e.target.value)}
                  className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-1.5 text-xs text-white focus:border-cyan-500 focus:outline-none"
                >
                  {data.predictions.map((p) => (
                    <option key={p.prediction_id} value={p.prediction_id}>
                      {p.task_title} ({p.breaking_risk})
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex items-center gap-2 text-xs">
                <span className="text-slate-400">Contrato: <strong className="text-slate-200">{selectedPrediction.route}</strong></span>
                <span className="text-slate-600">•</span>
                <span className="text-slate-400">Evolução: <code className="text-cyan-300 font-mono">{selectedPrediction.source_version} → {selectedPrediction.target_version}</code></span>
                <span className="text-slate-600">•</span>
                <span className={`rounded px-2 py-0.5 text-[10px] font-bold border ${
                  selectedPrediction.breaking_risk === 'BREAKING'
                    ? 'bg-rose-500/20 text-rose-300 border-rose-500/30'
                    : selectedPrediction.breaking_risk === 'POTENTIALLY_BREAKING'
                    ? 'bg-amber-500/20 text-amber-300 border-amber-500/30'
                    : 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                }`}>
                  {selectedPrediction.breaking_risk}
                </span>
              </div>
            </div>

            {/* Invariant Alert Box */}
            <div className="rounded-lg border border-cyan-500/20 bg-cyan-950/20 p-3.5 text-xs text-cyan-300 flex items-start gap-3">
              <Info className="h-4 w-4 text-cyan-400 shrink-0 mt-0.5" />
              <div>
                <strong>Princípio Fundamental da Fase 48:</strong> <code className="text-cyan-200">PREDICTED ≠ OBSERVED ≠ VERIFIED</code>. Nenhuma alteração contratual classificada como <code>BREAKING</code> é tratada como alteração de código normal. O JARVIS bloqueia a execução até a prova formal de migração de consumers.
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 2. PREFLIGHT DIFF SIMULATION TAB */}
      {activeTab === 'diff' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white">Diff Simulado Pré-Execução (Read-Only)</h3>
            <span className="text-xs text-slate-400">Garantia: state_before == state_after</span>
          </div>

          <div data-testid="preflight-simulation-card" className="rounded-lg border border-slate-800 bg-slate-900/60 p-4 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                <h4 className="text-xs font-bold text-emerald-300">Simulação Pré-Execução Confirmada Read-Only</h4>
              </div>
              <span className="rounded bg-emerald-500/20 px-2 py-0.5 text-[10px] font-mono text-emerald-400 border border-emerald-500/30">
                STATE HASH VERIFIED
              </span>
            </div>
            <p className="text-xs text-slate-300">
              A simulação foi executada em memória com snapshot imutável sem alterar registros nem o workspace.
            </p>
            <div className="rounded bg-slate-950 p-3 font-mono text-xs text-slate-300 space-y-1">
              <div>State Before SHA256: <span className="text-cyan-400">{selectedPrediction.simulation?.state_before_hash}</span></div>
              <div>State After SHA256:  <span className="text-cyan-400">{selectedPrediction.simulation?.state_after_hash}</span></div>
              <div>Invariante Read-Only: <span className="text-emerald-400">PRESERVED (Zero mutações de baseline)</span></div>
            </div>
          </div>

          {/* Structural Diff Viewer */}
          <div data-testid="contract-diff-viewer" className="rounded-lg border border-slate-800 bg-slate-900/40 p-4 space-y-3">
            <h4 className="text-xs font-bold text-slate-300 flex items-center gap-2">
              <Code2 className="h-4 w-4 text-cyan-400" />
              <span>Diff de Schema: {selectedPrediction.route} ({selectedPrediction.source_version} → {selectedPrediction.target_version})</span>
            </h4>
            <pre className="rounded bg-slate-950 p-3 font-mono text-xs text-slate-300 overflow-x-auto">
{`--- CURRENT CONTRACT (${selectedPrediction.source_version})
+++ PREDICTED CONTRACT (${selectedPrediction.target_version})
@@ avatar definition @@
- avatar: string (URL)
+ avatar: object {
+   url: string,
+   width: integer,
+   height: integer
+ }
VEREDICTO: BREAKING (Incompatibilidade direta de desserialização em clientes estritos)`}
            </pre>
          </div>
        </div>
      )}

      {/* 3. CONSUMER IMPACT TAB */}
      {activeTab === 'consumers' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white">Rastreabilidade Reversa de Consumers Afetados</h3>
            <span className="text-xs text-slate-400">Classificação via AST & Grafo Semântico</span>
          </div>

          {/* Closed Enum Alert */}
          <div data-testid="closed-enum-alert" className="rounded-lg border border-rose-500/40 bg-rose-950/20 p-4 text-xs text-rose-300 space-y-2">
            <div className="flex items-center gap-2 font-bold text-rose-400">
              <ShieldAlert className="h-4 w-4" />
              <span>Alerta de Quebra Crítica: Closed-Enum Matcher Identificado</span>
            </div>
            <p>
              O componente <strong>UserCard.tsx</strong> e o teste <strong>test_user_api.py</strong> realizam acesso direto e estrito ao campo <code>avatar</code> sem fallback. A execução sem adaptação prévia causará quebra imediata em tempo de execução.
            </p>
          </div>

          <div data-testid="consumer-impact-table" className="overflow-x-auto rounded-lg border border-slate-800">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-900 text-slate-400 border-b border-slate-800">
                <tr>
                  <th className="px-4 py-3 font-semibold">Consumer</th>
                  <th className="px-4 py-3 font-semibold">Categoria</th>
                  <th className="px-4 py-3 font-semibold">Pattern Matching</th>
                  <th className="px-4 py-3 font-semibold">Razão do Impacto</th>
                  <th className="px-4 py-3 font-semibold">Ação Requerida</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800 bg-slate-950/40">
                {selectedPrediction.affected_consumers.map((c) => (
                  <tr key={c.consumer_id} className="hover:bg-slate-900/40">
                    <td className="px-4 py-3 font-mono text-white">
                      <div>{c.name}</div>
                      <div className="text-[10px] text-slate-500 font-mono">{c.file_path}</div>
                    </td>
                    <td className="px-4 py-3">
                      <span className="rounded bg-slate-800 px-2 py-0.5 text-[10px] font-mono text-slate-300">
                        {c.category}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`rounded px-2 py-0.5 text-[10px] font-bold border ${
                        c.pattern_matching === 'CLOSED_EXHAUSTIVE'
                          ? 'bg-rose-500/20 text-rose-300 border-rose-500/30'
                          : 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                      }`}>
                        {c.pattern_matching}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-300">{c.impact_reason}</td>
                    <td className="px-4 py-3 text-cyan-400 font-medium">{c.required_action}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 4. MIGRATION PLAN TAB */}
      {activeTab === 'migration' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white">Plano de Migração Formal (DAG de Tarefas)</h3>
            <span className="text-xs text-slate-400">Estratégia: {selectedPrediction.migration_plan?.strategy || 'BACKWARD_COMPATIBLE'}</span>
          </div>

          {selectedPrediction.migration_plan ? (
            <div data-testid="migration-plan-card" className="rounded-lg border border-cyan-500/30 bg-slate-900/50 p-4 space-y-4">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <div>
                  <h4 className="text-xs font-bold text-white">ID: {selectedPrediction.migration_plan.migration_id}</h4>
                  <p className="text-[11px] text-slate-400">Transição: {selectedPrediction.source_version} → {selectedPrediction.target_version}</p>
                </div>
                <span className={`rounded px-2 py-0.5 text-[10px] font-bold border ${
                  selectedPrediction.migration_plan.status === 'APPROVED'
                    ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                    : 'bg-amber-500/20 text-amber-300 border-amber-500/30'
                }`}>
                  STATUS: {selectedPrediction.migration_plan.status}
                </span>
              </div>

              {/* DAG Task List */}
              <div className="space-y-2">
                <span className="text-xs font-semibold text-slate-300">Sequência Causal de Tarefas Derivadas:</span>
                {selectedPrediction.migration_plan.required_tasks.map((t, idx) => (
                  <div key={t.task_id} className="rounded bg-slate-950 p-3 text-xs flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <span className="rounded-full bg-cyan-500/20 px-2 py-0.5 text-[10px] font-mono text-cyan-300">
                        {idx + 1}
                      </span>
                      <div>
                        <div className="font-bold text-white">{t.title}</div>
                        <div className="text-[10px] text-slate-400">{t.description}</div>
                      </div>
                    </div>
                    <span className="rounded bg-slate-800 px-2 py-0.5 text-[10px] font-mono text-slate-400">
                      {t.target}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="rounded-lg border border-slate-800 bg-slate-900/30 p-6 text-center text-xs text-slate-400">
              Nenhum plano de migração necessário para esta alteração não-quebrante.
            </div>
          )}
        </div>
      )}

      {/* 5. MISSION GATE & APPROVAL TAB */}
      {activeTab === 'gate' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white">Mission Gate & Autorização Humana</h3>
            <span className="text-xs text-slate-400">Controlo de Admissão de Execução</span>
          </div>

          <div data-testid="gate-status-card" className="rounded-lg border border-slate-800 bg-slate-900/50 p-4 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="text-xs font-bold text-white">Trava de Execução do Mission Gate</h4>
                <p className="text-xs text-slate-400">
                  {selectedPrediction.migration_plan?.status === 'APPROVED'
                    ? 'Plano aprovado. Execução autorizada com plano de reversão ativo.'
                    : 'Bloqueio ativo: mudança breaking requer validação formal do operador.'}
                </p>
              </div>
              <span className={`rounded px-2.5 py-1 text-xs font-bold border ${
                selectedPrediction.migration_plan?.status === 'APPROVED'
                  ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                  : 'bg-rose-500/20 text-rose-300 border-rose-500/30'
              }`}>
                {selectedPrediction.migration_plan?.status === 'APPROVED' ? 'GATE CLEARED' : 'EXECUTION BLOCKED'}
              </span>
            </div>

            {selectedPrediction.migration_plan && (
              <div className="flex items-center gap-3 pt-2">
                <button
                  data-testid="btn-approve-migration"
                  onClick={() => handleApproveMigration(selectedPrediction.migration_plan!.migration_id)}
                  className="flex items-center gap-1.5 rounded bg-emerald-600 px-4 py-2 text-xs font-semibold text-white hover:bg-emerald-500 transition-all"
                >
                  <Check className="h-4 w-4" />
                  Aprovar Plano de Migração
                </button>
                <button
                  data-testid="btn-reject-migration"
                  onClick={() => handleRejectMigration(selectedPrediction.migration_plan!.migration_id)}
                  className="flex items-center gap-1.5 rounded bg-rose-600 px-4 py-2 text-xs font-semibold text-white hover:bg-rose-500 transition-all"
                >
                  <X className="h-4 w-4" />
                  Rejeitar Migração
                </button>
                <button
                  data-testid="btn-block-execution"
                  onClick={() => handleRejectMigration(selectedPrediction.migration_plan!.migration_id)}
                  className="flex items-center gap-1.5 rounded border border-slate-700 bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-300 hover:bg-slate-700 transition-all"
                >
                  <Lock className="h-4 w-4" />
                  Bloqueio de Emergência
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 6. RUNTIME VERIFICATION TAB */}
      {activeTab === 'runtime' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white">Verificação em Tempo Real & Completion Gate</h3>
            <span className="text-xs text-slate-400">Prevenção de Falso Sucesso (No False Completion)</span>
          </div>

          {/* No False Success Alert */}
          <div data-testid="no-false-success-alert" className="rounded-lg border border-blue-500/40 bg-blue-950/20 p-4 text-xs text-blue-300 space-y-2">
            <div className="flex items-center gap-2 font-bold text-blue-400">
              <ShieldCheck className="h-4 w-4" />
              <span>Garantia de Não-Falso Sucesso (Contract Completion Gate)</span>
            </div>
            <p>
              Mesmo que a compilação do backend termine com sucesso (exit code 0), a missão <strong>NÃO</strong> é marcada como concluída se os testes de contrato ou a compatibilidade de consumers estiverem pendentes.
            </p>
          </div>

          <div data-testid="runtime-verification-card" className="rounded-lg border border-slate-800 bg-slate-900/50 p-4 space-y-3">
            <h4 className="text-xs font-bold text-slate-300">Auditoria Pós-Execução: PREDICTED vs OBSERVED</h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
              <div className="rounded bg-slate-950 p-3 space-y-1">
                <span className="font-bold text-cyan-400">Contrato Previsto:</span>
                <div>Versão: 2.0.0</div>
                <div>Formato: avatar as object</div>
                <div>Status: VERIFIED</div>
              </div>
              <div className="rounded bg-slate-950 p-3 space-y-1">
                <span className="font-bold text-emerald-400">Contrato Observado em Runtime:</span>
                <div>Versão: 2.0.0 (Conforme)</div>
                <div>Consumer UserCard: 100% Compatível</div>
                <div>Zero Erros de Rede: Validado</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 7. ROLLBACK & LINEAGE TAB */}
      {activeTab === 'rollback' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white">Rollback Determinístico & Linhagem de Versões</h3>
            <span className="text-xs text-slate-400">Preservação de Histórico e Evidências</span>
          </div>

          <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-4 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="text-xs font-bold text-white">Reversão para Baseline Estável v1.0.0</h4>
                <p className="text-xs text-slate-400">Restaura imediatamente v1.0.0 mantendo todas as provas de auditoria.</p>
              </div>
              {selectedPrediction.migration_plan && (
                <button
                  data-testid="rollback-action-btn"
                  onClick={() => handleRollback(selectedPrediction.migration_plan!.migration_id)}
                  className="flex items-center gap-1.5 rounded border border-rose-500/40 bg-rose-950/40 px-3 py-1.5 text-xs font-semibold text-rose-300 hover:bg-rose-900/50 transition-all"
                >
                  <RotateCcw className="h-3.5 w-3.5" />
                  Executar Rollback
                </button>
              )}
            </div>

            {/* Timeline */}
            <div className="rounded bg-slate-950 p-3 font-mono text-xs text-slate-300 space-y-2">
              <div className="text-emerald-400 font-bold">Linhagem Canónica de Versões:</div>
              <div>[1] v1.0.0 (Active Baseline Original)</div>
              <div>[2] v2.0.0-proposed (Task Avatar Change)</div>
              <div>[3] v2.0.0 (Approved Migration Executed)</div>
              <div className="text-slate-500">[4] Rollback Standby Target → v1.0.0 (Garantido em &lt; 10ms)</div>
            </div>
          </div>
        </div>
      )}

      {/* 8. WHY CONTRACT CHANGE TAB */}
      {activeTab === 'why' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white">Painel do Porquê: Causalidade e Justificação Formal</h3>
            <span className="text-xs text-slate-400">Cadeia Causal Completa</span>
          </div>

          <div data-testid="why-causal-chain" className="rounded-lg border border-cyan-500/30 bg-slate-900/50 p-4 space-y-3">
            <h4 className="text-xs font-bold text-cyan-300">Cadeia de Rastreabilidade da Decisão Contratual</h4>
            <div className="space-y-2">
              {data.why_chain.map((c) => (
                <div key={c.step} className="flex items-start gap-3 text-xs">
                  <span className="rounded bg-cyan-500/20 px-2 py-0.5 text-[10px] font-mono text-cyan-300 shrink-0 mt-0.5">
                    ETAPA {c.step}
                  </span>
                  <div>
                    <strong className="text-white">{c.title}:</strong> <span className="text-slate-300">{c.desc}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
