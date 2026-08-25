import React, { useState, useEffect } from 'react';
import {
  Shield,
  ShieldAlert,
  ShieldCheck,
  Activity,
  Cpu,
  RefreshCw,
  Search,
  CheckCircle,
  AlertTriangle,
  Lock,
  Globe,
  Radio,
  Clock,
  Database,
  ChevronRight,
  Info,
  Check,
  X,
  RotateCcw,
  Eye,
  UserCheck,
} from 'lucide-react';
import { useWebSocket } from '../../context/WebSocketContext';
import { motion, AnimatePresence } from 'framer-motion';

export const SentinelDashboard: React.FC = () => {
  const {
    sentinelStatus,
    sentinelEvents,
    sentinelBaseline,
    sentinelActions,
    isSentinelAuditing,
    getSentinelStatus,
    runSentinelAudit,
    getSentinelBaseline,
    acceptSentinelKnownGood,
    getSentinelActions,
    approveSentinelAction,
    rejectSentinelAction,
    rollbackSentinelAction,
    submitSentinelReview,
  } = useWebSocket();

  const [activeTab, setActiveTab] = useState<
    'overview' | 'actions' | 'processes' | 'network' | 'persistence' | 'browser' | 'events' | 'evidence'
  >('overview');

  const [searchFilter, setSearchFilter] = useState('');
  const [processFilter, setProcessFilter] = useState<'all' | 'temp' | 'unsigned'>('all');
  const [networkFilter, setNetworkFilter] = useState<'all' | 'listen' | 'active'>('all');
  const [actionFilter, setActionFilter] = useState<'all' | 'pending' | 'completed' | 'rolled_back'>('all');
  const [selectedEvidence, setSelectedEvidence] = useState<Record<string, unknown> | null>(null);
  const [knownGoodModalItem, setKnownGoodModalItem] = useState<string | null>(null);
  const [knownGoodReason, setKnownGoodReason] = useState('');
  const [actionConfirmModal, setActionConfirmModal] = useState<any | null>(null);
  const [rejectReasonModal, setRejectReasonModal] = useState<string | null>(null);
  const [rejectReasonText, setRejectReasonText] = useState('');
  const [reviewModalEvent, setReviewModalEvent] = useState<any | null>(null);
  const [reviewClass, setReviewClass] = useState<string>('BENIGN');
  const [reviewReason, setReviewReason] = useState<string>('');

  useEffect(() => {
    getSentinelStatus();
    getSentinelBaseline();
    getSentinelActions();
  }, [getSentinelStatus, getSentinelBaseline, getSentinelActions]);

  const posture = sentinelStatus?.posture || 'MONITORING';
  const postureColor =
    posture === 'GOOD'
      ? 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10'
      : posture === 'MONITORING'
      ? 'text-cyan-400 border-cyan-500/30 bg-cyan-500/10'
      : posture === 'ATTENTION'
      ? 'text-amber-400 border-amber-500/30 bg-amber-500/10'
      : posture === 'HIGH_RISK'
      ? 'text-rose-400 border-rose-500/30 bg-rose-500/10'
      : 'text-gray-400 border-gray-500/30 bg-gray-500/10';

  const processes = (sentinelBaseline?.processes as Array<Record<string, unknown>>) || [];
  const network = (sentinelBaseline?.network as Array<Record<string, unknown>>) || [];
  const persistence = (sentinelBaseline?.persistence as Array<Record<string, unknown>>) || [];
  const browserExts = (sentinelBaseline?.browser_extensions as Array<Record<string, unknown>>) || [];
  const winSec = (sentinelBaseline?.windows_security as Record<string, unknown>) || {};
  const hostsInfo = (sentinelBaseline?.hosts_info as Record<string, unknown>) || {};

  const filteredProcesses = processes.filter((p) => {
    const name = String(p.name || '').toLowerCase();
    const pid = String(p.pid || '');
    const exe = String(p.exe_path || '').toLowerCase();
    const matchesSearch = name.includes(searchFilter.toLowerCase()) || pid.includes(searchFilter) || exe.includes(searchFilter.toLowerCase());

    if (!matchesSearch) return false;
    if (processFilter === 'temp') return Boolean(p.is_temp_dir);
    if (processFilter === 'unsigned') return p.is_signed === false;
    return true;
  });

  const filteredNetwork = network.filter((n) => {
    const local = `${n.local_address}:${n.local_port}`.toLowerCase();
    const remote = `${n.remote_address || ''}:${n.remote_port || ''}`.toLowerCase();
    const proc = String(n.process_name || '').toLowerCase();
    const pid = String(n.pid || '');
    const matchesSearch =
      local.includes(searchFilter.toLowerCase()) ||
      remote.includes(searchFilter.toLowerCase()) ||
      proc.includes(searchFilter.toLowerCase()) ||
      pid.includes(searchFilter);

    if (!matchesSearch) return false;
    if (networkFilter === 'listen') return n.status === 'LISTEN';
    if (networkFilter === 'active') return n.status !== 'LISTEN';
    return true;
  });

  const handleConfirmKnownGood = () => {
    if (knownGoodModalItem) {
      acceptSentinelKnownGood(knownGoodModalItem, knownGoodReason || 'Validado e aprovado pelo utilizador');
      setKnownGoodModalItem(null);
      setKnownGoodReason('');
    }
  };

  return (
    <div className="flex flex-col h-full bg-[#05070e] text-gray-200 overflow-hidden font-sans">
      {/* Header Banner */}
      <div className="flex flex-wrap items-center justify-between gap-4 px-6 py-4 border-b border-white/10 bg-[#080b14]/80 backdrop-blur-md">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-lg bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400 shadow-lg shadow-cyan-500/10">
            <Shield className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-bold text-white tracking-wide">JARVIS SECURITY SENTINEL</h2>
              <span className="text-[10px] px-2 py-0.5 rounded-full border border-cyan-400/30 bg-cyan-500/10 text-cyan-300 font-mono">
                FASE S2: CONTINUOUS WATCHDOG
              </span>
            </div>
            <p className="text-xs text-gray-400">
              Monitorização passiva 100% Read-Only e correlação determinística de ameaças no Windows.
            </p>
          </div>
        </div>

        {/* Action Button & Status Pill */}
        <div className="flex items-center gap-3">
          {sentinelStatus?.shadow_mode !== false && (
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-purple-500/30 bg-purple-500/10 text-purple-300 text-xs font-semibold font-mono shadow-sm">
              <Eye className="w-3.5 h-3.5 text-purple-400" />
              <span>SHADOW MODE: 100% READ-ONLY</span>
            </div>
          )}

          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-md border text-xs font-semibold uppercase ${postureColor}`}>
            {posture === 'GOOD' ? (
              <ShieldCheck className="w-4 h-4" />
            ) : posture === 'HIGH_RISK' ? (
              <ShieldAlert className="w-4 h-4" />
            ) : (
              <Activity className="w-4 h-4" />
            )}
            <span>Postura: {posture}</span>
          </div>

          <button
            onClick={() => runSentinelAudit()}
            disabled={isSentinelAuditing}
            className="flex items-center gap-2 px-4 py-2 rounded-md bg-cyan-400 hover:bg-cyan-300 text-black font-semibold text-xs transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-md cursor-pointer active:scale-98"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isSentinelAuditing ? 'animate-spin' : ''}`} />
            <span>{isSentinelAuditing ? 'A auditar...' : 'Executar Auditoria Agora'}</span>
          </button>
        </div>
      </div>

      {/* Navigation Sub-Tabs */}
      <div className="flex border-b border-white/8 bg-black/20 px-6 gap-2 select-none overflow-x-auto">
        {[
          { id: 'overview', label: 'Overview', icon: Activity },
          {
            id: 'actions',
            label: `Ações & Contenção (${sentinelActions?.length || 0})`,
            icon: ShieldCheck,
            badge: sentinelActions?.filter((a) => a.status === 'WAITING_APPROVAL' || a.status === 'PROPOSED').length || 0,
          },
          { id: 'processes', label: `Processos (${processes.length})`, icon: Cpu },
          { id: 'network', label: `Rede & Portas (${network.length})`, icon: Globe },
          { id: 'persistence', label: `Persistência (${persistence.length})`, icon: Lock },
          { id: 'browser', label: `Extensões (${browserExts.length})`, icon: Radio },
          { id: 'events', label: `Eventos de Segurança (${sentinelEvents.length})`, icon: AlertTriangle },
          { id: 'evidence', label: 'Evidence Inspector', icon: Database },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`flex items-center gap-2 px-4 py-3 text-xs font-medium border-b-2 transition-all cursor-pointer whitespace-nowrap ${
                isActive
                  ? 'border-cyan-400 text-cyan-300 bg-white/[0.03]'
                  : 'border-transparent text-gray-400 hover:text-gray-200 hover:bg-white/[0.01]'
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              <span>{tab.label}</span>
              {tab.badge && tab.badge > 0 ? (
                <span className="px-1.5 py-0.2 rounded-full bg-amber-500/30 text-amber-300 font-mono text-[10px] font-bold">
                  {tab.badge}
                </span>
              ) : null}
            </button>
          );
        })}
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* OVERVIEW TAB */}
        {activeTab === 'overview' && (
          <div className="space-y-6">
            {/* Startup Lifecycle / Degraded Mode Banners */}
            {sentinelStatus?.lifecycle_state === 'BASELINE_RUNNING' && (
              <div className="p-4 rounded-lg bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-between gap-3 text-cyan-300">
                <div className="flex items-center gap-3">
                  <RefreshCw className="w-5 h-5 animate-spin text-cyan-400" />
                  <div>
                    <h4 className="text-xs font-bold uppercase tracking-wider text-white">
                      Captura de Baseline Inicial em Background
                    </h4>
                    <p className="text-xs text-cyan-200/80">
                      O Sentinel está a mapear processos, conexões de rede e persistência sem bloquear o sistema.
                    </p>
                  </div>
                </div>
                <span className="text-[10px] px-2.5 py-1 rounded bg-cyan-500/20 font-mono text-cyan-300 font-bold">
                  BASELINE_RUNNING
                </span>
              </div>
            )}

            {sentinelStatus?.lifecycle_state === 'DEGRADED' && (
              <div className="p-4 rounded-lg bg-amber-500/10 border border-amber-500/30 flex items-center justify-between gap-3 text-amber-300">
                <div className="flex items-center gap-3">
                  <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0" />
                  <div>
                    <h4 className="text-xs font-bold uppercase tracking-wider text-white">
                      Sentinel em Modo Degradado
                    </h4>
                    <p className="text-xs text-amber-200/80">
                      {sentinelStatus?.degraded_reason || 'Alguns coletores de telemetria falharam.'}
                    </p>
                  </div>
                </div>
                {sentinelStatus?.degraded_collectors && sentinelStatus.degraded_collectors.length > 0 && (
                  <div className="flex gap-1 flex-wrap">
                    {sentinelStatus.degraded_collectors.map((c) => (
                      <span key={c} className="text-[9px] px-2 py-0.5 rounded bg-amber-500/20 font-mono text-amber-200">
                        {c}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}

            {sentinelStatus?.lifecycle_state === 'FAILED' && (
              <div className="p-4 rounded-lg bg-rose-500/10 border border-rose-500/30 flex items-center justify-between gap-3 text-rose-300">
                <div className="flex items-center gap-3">
                  <ShieldAlert className="w-5 h-5 text-rose-400 shrink-0" />
                  <div>
                    <h4 className="text-xs font-bold uppercase tracking-wider text-white">
                      Falha Crítica no Sentinel
                    </h4>
                    <p className="text-xs text-rose-200/80">
                      {sentinelStatus?.degraded_reason || 'Erro irrecuperável durante a inicialização.'}
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => runSentinelAudit()}
                  className="text-xs px-3 py-1.5 rounded bg-rose-500/20 hover:bg-rose-500/30 text-rose-200 font-semibold cursor-pointer"
                >
                  Tentar Reiniciar
                </button>
              </div>
            )}

            {/* KPI Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="p-4 rounded-lg bg-white/[0.03] border border-white/8 flex flex-col justify-between">
                <div className="flex items-center justify-between text-xs text-gray-400">
                  <span>Watchdog Status</span>
                  <Activity className="w-4 h-4 text-cyan-400" />
                </div>
                <div className="mt-2 flex items-baseline gap-2">
                  <span className="text-xl font-bold text-white font-mono">{sentinelStatus?.status || 'RUNNING'}</span>
                  <span className="text-[10px] text-gray-500">Scan: a cada {sentinelStatus?.scan_interval_seconds || 60}s</span>
                </div>
                <div className="mt-2 text-[10px] text-gray-400 flex justify-between">
                  <span>Total Scans: {sentinelStatus?.total_scans || 0}</span>
                  <span>Próximo em: {sentinelStatus?.next_scan_in_seconds || 0}s</span>
                </div>
              </div>

              <div className="p-4 rounded-lg bg-white/[0.03] border border-white/8 flex flex-col justify-between">
                <div className="flex items-center justify-between text-xs text-gray-400">
                  <span>Recursos Sentinel</span>
                  <Cpu className="w-4 h-4 text-violet-400" />
                </div>
                <div className="mt-2 flex items-baseline gap-2">
                  <span className="text-xl font-bold text-white font-mono">{sentinelStatus?.memory_mb || 0} MB</span>
                  <span className="text-[10px] text-gray-500">RAM (RSS)</span>
                </div>
                <div className="mt-2 text-[10px] text-gray-400 flex justify-between">
                  <span>CPU: {sentinelStatus?.cpu_percent || 0}%</span>
                  <span>Duração: {sentinelStatus?.last_scan_duration_seconds || 0}s</span>
                </div>
              </div>

              <div className="p-4 rounded-lg bg-white/[0.03] border border-white/8 flex flex-col justify-between">
                <div className="flex items-center justify-between text-xs text-gray-400">
                  <span>Windows Defender</span>
                  <ShieldCheck className="w-4 h-4 text-emerald-400" />
                </div>
                <div className="mt-2 flex items-baseline gap-2">
                  <span className="text-xl font-bold text-emerald-400 font-mono">
                    {winSec.defender_realtime_enabled !== false ? 'ATIVO' : 'DESATIVADO'}
                  </span>
                </div>
                <div className="mt-2 text-[10px] text-gray-400">
                  Antivírus & Proteção em Tempo Real
                </div>
              </div>

              <div className="p-4 rounded-lg bg-white/[0.03] border border-white/8 flex flex-col justify-between">
                <div className="flex items-center justify-between text-xs text-gray-400">
                  <span>Windows Firewall</span>
                  <Lock className="w-4 h-4 text-emerald-400" />
                </div>
                <div className="mt-2 flex items-baseline gap-2">
                  <span className="text-xl font-bold text-emerald-400 font-mono">
                    {winSec.firewall_public_enabled !== false ? 'ATIVO' : 'DESATIVADO'}
                  </span>
                </div>
                <div className="mt-2 text-[10px] text-gray-400">
                  Perfis Domínio, Privado e Público
                </div>
              </div>
            </div>

            {/* Baseline ID Banner */}
            <div className="p-4 rounded-lg bg-white/[0.02] border border-white/8 flex flex-wrap items-center justify-between gap-4">
              <div>
                <span className="text-xs text-gray-400">Baseline Ativo Atual:</span>
                <div className="text-sm font-mono font-bold text-cyan-300">
                  {String(sentinelBaseline?.baseline_id || 'Carregando baseline...')}
                </div>
              </div>
              <div>
                <span className="text-xs text-gray-400">Integridade SHA-256:</span>
                <div className="text-xs font-mono text-gray-500 max-w-md truncate">
                  {String(sentinelBaseline?.integrity_hash || '...')}
                </div>
              </div>
              <div className="flex gap-2">
                <span className="text-xs px-2.5 py-1 rounded bg-white/[0.05] border border-white/10 text-gray-300 font-mono">
                  Hosts: {String(hostsInfo.line_count || 0)} linhas
                </span>
                <span className="text-xs px-2.5 py-1 rounded bg-white/[0.05] border border-white/10 text-gray-300 font-mono">
                  Extensões: {browserExts.length}
                </span>
              </div>
            </div>

            {/* Recent Correlated Security Events */}
            <div className="space-y-3">
              <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-cyan-400" />
                Eventos e Alterações Observadas Recentemente
              </h3>

              {sentinelEvents.length === 0 ? (
                <div className="p-8 rounded-lg bg-white/[0.02] border border-white/8 text-center text-gray-500">
                  <CheckCircle className="w-8 h-8 text-emerald-400/50 mx-auto mb-2" />
                  <p className="text-sm font-medium text-gray-300">Nenhuma anomalia crítica detetada.</p>
                  <p className="text-xs text-gray-500 mt-1">O sistema mantém a integridade face ao baseline ativo.</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {sentinelEvents.slice(0, 5).map((ev) => (
                    <div
                      key={ev.event_id}
                      className="p-4 rounded-lg bg-white/[0.03] border border-white/8 hover:border-cyan-500/30 transition-all flex flex-col md:flex-row items-start md:items-center justify-between gap-4"
                    >
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span
                            className={`text-[10px] font-bold px-2 py-0.5 rounded border uppercase ${
                              ev.severity === 'HIGH_RISK'
                                ? 'bg-rose-500/20 text-rose-300 border-rose-500/30'
                                : ev.severity === 'SUSPICIOUS'
                                ? 'bg-amber-500/20 text-amber-300 border-amber-500/30'
                                : 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30'
                            }`}
                          >
                            {ev.severity}
                          </span>
                          <span className="text-xs font-mono text-gray-400">[{ev.category}]</span>
                          <span className="text-xs font-bold text-white">{ev.event_id}</span>
                          {ev.is_known_good && (
                            <span className="text-[10px] bg-emerald-500/10 text-emerald-300 border border-emerald-500/30 px-2 py-0.2 rounded">
                              KNOWN GOOD
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-gray-300">{ev.rationale}</p>
                        <p className="text-[10px] text-gray-500">
                          Recomendação defensiva: {ev.recommended_action}
                        </p>
                      </div>

                      <div className="flex items-center gap-2 shrink-0">
                        {!ev.is_known_good && (
                          <button
                            onClick={() => setKnownGoodModalItem(ev.fingerprint)}
                            className="px-3 py-1.5 rounded bg-white/[0.05] hover:bg-emerald-500/20 border border-white/10 hover:border-emerald-500/30 text-xs text-gray-300 hover:text-emerald-200 transition-all cursor-pointer"
                          >
                            Aceitar como Benigno
                          </button>
                        )}
                        <button
                          onClick={() => {
                            setSelectedEvidence(ev as any);
                            setActiveTab('evidence');
                          }}
                          className="p-1.5 rounded hover:bg-white/10 text-gray-400 hover:text-white"
                        >
                          <ChevronRight className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* ACTIONS & CONTAINMENT TAB */}
        {activeTab === 'actions' && (
          <div className="space-y-6">
            {/* Safety Policy Notice */}
            <div className="p-4 rounded-lg bg-amber-500/10 border border-amber-500/30 flex items-start gap-3 text-amber-200">
              <ShieldAlert className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
              <div>
                <h4 className="text-xs font-bold uppercase tracking-wider text-white">
                  Política de Resposta & Contenção Defensiva (Fase S3)
                </h4>
                <p className="text-xs text-amber-200/90 mt-1">
                  Todas as mutações no sistema operativo exigem autorização humana prévia. Nenhuma ação destrutiva é executada autonomamente. Cada ação gera evidência imutável, verificação de pós-estado e plano determinístico de reversão (rollback).
                </p>
              </div>
            </div>

            {/* Filter Bar */}
            <div className="flex flex-wrap items-center justify-between gap-4 p-3 rounded-lg bg-white/[0.02] border border-white/8">
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-400 font-medium">Filtrar Ações:</span>
                {(['all', 'pending', 'completed', 'rolled_back'] as const).map((filter) => (
                  <button
                    key={filter}
                    onClick={() => setActionFilter(filter)}
                    className={`px-3 py-1 text-xs rounded-md border transition-all cursor-pointer ${
                      actionFilter === filter
                        ? 'bg-cyan-500/20 border-cyan-500/40 text-cyan-300 font-semibold'
                        : 'border-white/5 bg-white/[0.02] text-gray-400 hover:text-white'
                    }`}
                  >
                    {filter === 'all'
                      ? `Todas (${sentinelActions?.length || 0})`
                      : filter === 'pending'
                      ? `Pendentes (${sentinelActions?.filter((a) => a.status === 'PROPOSED' || a.status === 'WAITING_APPROVAL').length || 0})`
                      : filter === 'completed'
                      ? `Concluídas (${sentinelActions?.filter((a) => a.status === 'COMPLETED').length || 0})`
                      : `Revertidas (${sentinelActions?.filter((a) => a.status === 'ROLLED_BACK').length || 0})`}
                  </button>
                ))}
              </div>

              <button
                onClick={() => getSentinelActions()}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-white/[0.05] hover:bg-white/10 text-xs text-gray-300 cursor-pointer"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Atualizar Ações</span>
              </button>
            </div>

            {/* Actions List */}
            {(!sentinelActions || sentinelActions.length === 0) ? (
              <div className="p-12 text-center rounded-lg bg-white/[0.01] border border-white/5 text-gray-500 space-y-2">
                <ShieldCheck className="w-10 h-10 mx-auto text-cyan-400/40" />
                <h4 className="text-sm font-semibold text-gray-300">Nenhuma ação de contenção registada</h4>
                <p className="text-xs text-gray-500 max-w-md mx-auto">
                  O sistema está em operação passiva e nenhum incidente exigiu propostas de mitigação até ao momento.
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                {sentinelActions
                  .filter((a) => {
                    if (actionFilter === 'pending') return a.status === 'PROPOSED' || a.status === 'WAITING_APPROVAL';
                    if (actionFilter === 'completed') return a.status === 'COMPLETED';
                    if (actionFilter === 'rolled_back') return a.status === 'ROLLED_BACK';
                    return true;
                  })
                  .map((action) => {
                    const isPending = action.status === 'PROPOSED' || action.status === 'WAITING_APPROVAL';
                    const isExecuting = action.status === 'APPROVED' || action.status === 'EXECUTING' || action.status === 'VERIFYING';
                    const isCompleted = action.status === 'COMPLETED';
                    const isRolledBack = action.status === 'ROLLED_BACK';
                    const isFailed = action.status === 'FAILED';

                    const actionTypeColor =
                      action.action_type === 'TERMINATE_PROCESS'
                        ? 'bg-rose-500/20 text-rose-300 border-rose-500/40'
                        : action.action_type === 'DISABLE_SCHEDULED_TASK'
                        ? 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                        : action.action_type === 'BLOCK_NETWORK_ENDPOINT'
                        ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40'
                        : action.action_type === 'QUARANTINE_FILE'
                        ? 'bg-purple-500/20 text-purple-300 border-purple-500/40'
                        : 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40';

                    return (
                      <div
                        key={action.action_id}
                        className={`p-5 rounded-xl border transition-all space-y-4 ${
                          isPending
                            ? 'bg-amber-500/[0.03] border-amber-500/30 shadow-lg shadow-amber-500/5'
                            : isCompleted
                            ? 'bg-emerald-500/[0.02] border-emerald-500/20'
                            : isFailed
                            ? 'bg-rose-500/[0.03] border-rose-500/30'
                            : 'bg-white/[0.02] border-white/8'
                        }`}
                      >
                        {/* Header */}
                        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/5 pb-3">
                          <div className="flex items-center gap-3">
                            <span className={`px-2.5 py-1 rounded-md text-xs font-bold border font-mono ${actionTypeColor}`}>
                              {action.action_type}
                            </span>
                            <span className="text-xs font-mono text-gray-400">{action.action_id}</span>
                            <span className="text-[10px] text-gray-500 font-mono">
                              Nível: {action.permission_level}
                            </span>
                          </div>

                          <div className="flex items-center gap-2">
                            <span
                              className={`text-[10px] px-2.5 py-1 rounded font-bold font-mono uppercase tracking-wider ${
                                isPending
                                  ? 'bg-amber-500/20 text-amber-300 animate-pulse border border-amber-500/30'
                                  : isExecuting
                                  ? 'bg-blue-500/20 text-blue-300 border border-blue-500/30'
                                  : isCompleted
                                  ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                                  : isRolledBack
                                  ? 'bg-gray-500/20 text-gray-400 border border-gray-500/30'
                                  : 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                              }`}
                            >
                              {action.status}
                            </span>
                            <span className="text-[10px] text-gray-500 font-mono">
                              {new Date(action.created_at * 1000).toLocaleTimeString()}
                            </span>
                          </div>
                        </div>

                        {/* Body Details */}
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                          <div>
                            <span className="text-gray-500 uppercase tracking-wider text-[10px] font-mono">Alvo da Ação:</span>
                            <div className="mt-1 font-mono font-bold text-white bg-black/40 px-3 py-2 rounded border border-white/5 break-all">
                              {action.target}
                            </div>
                          </div>

                          <div>
                            <span className="text-gray-500 uppercase tracking-wider text-[10px] font-mono">Motivo / Racional:</span>
                            <p className="mt-1 text-gray-300 leading-relaxed bg-black/40 px-3 py-2 rounded border border-white/5">
                              {action.rationale}
                            </p>
                          </div>
                        </div>

                        {/* Evidence & Rollback Plan */}
                        <div className="flex flex-wrap items-center justify-between gap-3 text-xs pt-1">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-[10px] text-gray-500 uppercase font-mono">Evidências:</span>
                            {action.evidence_ids.map((evId) => (
                              <button
                                key={evId}
                                onClick={() => {
                                  setSelectedEvidence({ evidence_id: evId, action_id: action.action_id, target: action.target });
                                  setActiveTab('evidence');
                                }}
                                className="px-2 py-0.5 rounded bg-cyan-500/10 hover:bg-cyan-500/20 border border-cyan-500/30 font-mono text-[10px] text-cyan-300 flex items-center gap-1 cursor-pointer"
                              >
                                <Eye className="w-2.5 h-2.5" />
                                {evId}
                              </button>
                            ))}
                          </div>

                          {action.rollback_available && (
                            <div className="text-[11px] text-gray-400 font-mono flex items-center gap-1.5">
                              <RotateCcw className="w-3 h-3 text-cyan-400" />
                              <span>Rollback: {action.rollback_plan}</span>
                            </div>
                          )}
                        </div>

                        {/* Error message box if failed */}
                        {action.error_message && (
                          <div className="p-3 rounded bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs font-mono">
                            ⚠️ {action.error_message}
                          </div>
                        )}

                        {/* Actions Control Footer */}
                        <div className="flex items-center justify-between pt-2 border-t border-white/5 gap-3">
                          <div className="text-[10px] text-gray-500 font-mono">
                            {action.approved_by ? `Aprovado por: ${action.approved_by}` : 'Aguardando Operador Humano'}
                          </div>

                          <div className="flex items-center gap-2">
                            {isPending && (
                              <>
                                <button
                                  onClick={() => setRejectReasonModal(action.action_id)}
                                  className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-white/[0.05] hover:bg-rose-500/20 border border-white/10 hover:border-rose-500/30 text-xs text-gray-300 hover:text-rose-200 transition-all cursor-pointer font-semibold"
                                >
                                  <X className="w-3.5 h-3.5" />
                                  <span>Rejeitar</span>
                                </button>
                                <button
                                  onClick={() => setActionConfirmModal(action)}
                                  className="flex items-center gap-1.5 px-4 py-1.5 rounded bg-emerald-500 hover:bg-emerald-400 text-black font-bold text-xs shadow-md transition-all cursor-pointer active:scale-98"
                                >
                                  <Check className="w-3.5 h-3.5" />
                                  <span>Aprovar e Executar</span>
                                </button>
                              </>
                            )}

                            {isCompleted && action.rollback_available && (
                              <button
                                onClick={() => rollbackSentinelAction(action.action_id)}
                                className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-amber-500/20 hover:bg-amber-500/30 border border-amber-500/40 text-amber-200 text-xs font-semibold cursor-pointer transition-all active:scale-98"
                              >
                                <RotateCcw className="w-3.5 h-3.5" />
                                <span>Executar Rollback</span>
                              </button>
                            )}

                            <button
                              onClick={() => {
                                setSelectedEvidence(action as any);
                                setActiveTab('evidence');
                              }}
                              className="px-3 py-1.5 rounded bg-white/[0.05] hover:bg-white/10 text-xs text-gray-400 hover:text-white cursor-pointer"
                            >
                              Inspecionar Ação
                            </button>
                          </div>
                        </div>
                      </div>
                    );
                  })}
              </div>
            )}
          </div>
        )}

        {/* PROCESSES TAB */}
        {activeTab === 'processes' && (
          <div className="space-y-4">
            {/* Search & Filter Bar */}
            <div className="flex flex-wrap items-center justify-between gap-4 p-3 rounded-lg bg-white/[0.02] border border-white/8">
              <div className="relative flex-1 min-w-[240px]">
                <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
                <input
                  type="text"
                  placeholder="Pesquisar por processo, PID ou caminho do executável..."
                  value={searchFilter}
                  onChange={(e) => setSearchFilter(e.target.value)}
                  className="w-full pl-9 pr-4 py-1.5 bg-black/40 border border-white/10 rounded-md text-xs text-white placeholder-gray-500 outline-none focus:border-cyan-400"
                />
              </div>

              <div className="flex gap-2">
                {(['all', 'temp', 'unsigned'] as const).map((mode) => (
                  <button
                    key={mode}
                    onClick={() => setProcessFilter(mode)}
                    className={`px-3 py-1.5 text-xs rounded-md border transition-all cursor-pointer ${
                      processFilter === mode
                        ? 'bg-cyan-500/20 border-cyan-400 text-cyan-200'
                        : 'bg-white/[0.02] border-white/8 text-gray-400 hover:text-white'
                    }`}
                  >
                    {mode === 'all' ? 'Todos' : mode === 'temp' ? '⚠️ Pastas %TEMP%' : 'Não Assinados'}
                  </button>
                ))}
              </div>
            </div>

            {/* Process Table */}
            <div className="border border-white/8 rounded-lg overflow-hidden bg-white/[0.01]">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="border-b border-white/8 bg-white/[0.03] text-gray-400 font-mono">
                      <th className="p-3">PID</th>
                      <th className="p-3">Processo</th>
                      <th className="p-3">Caminho Executável</th>
                      <th className="p-3">Assinatura / Signer</th>
                      <th className="p-3">Utilizador</th>
                      <th className="p-3">Hash SHA-256</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5 font-sans">
                    {filteredProcesses.slice(0, 100).map((p, idx) => (
                      <tr key={idx} className="hover:bg-white/[0.02] transition-colors">
                        <td className="p-3 font-mono text-cyan-300 font-semibold">{p.pid as number}</td>
                        <td className="p-3 font-medium text-white flex items-center gap-2">
                          {String(p.name || '')}
                          {Boolean(p.is_temp_dir) && (
                            <span className="text-[9px] bg-rose-500/20 border border-rose-500/40 text-rose-300 px-1.5 py-0.2 rounded font-mono">
                              %TEMP%
                            </span>
                          )}
                        </td>
                        <td className="p-3 text-gray-400 font-mono text-[11px] max-w-xs truncate" title={p.exe_path as string}>
                          {p.exe_path as string || '-'}
                        </td>
                        <td className="p-3">
                          {p.is_signed === true ? (
                            <span className="text-emerald-400 font-mono text-[10px]">🟢 Assinado</span>
                          ) : p.is_signed === false ? (
                            <span className="text-amber-400 font-mono text-[10px]">⚠️ Não Assinado</span>
                          ) : (
                            <span className="text-gray-500 font-mono text-[10px]">-</span>
                          )}
                        </td>
                        <td className="p-3 text-gray-400">{p.username as string || '-'}</td>
                        <td className="p-3 font-mono text-[10px] text-gray-500 max-w-[140px] truncate" title={p.sha256 as string}>
                          {p.sha256 as string || '-'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* NETWORK TAB */}
        {activeTab === 'network' && (
          <div className="space-y-4">
            {/* Filter Bar */}
            <div className="flex flex-wrap items-center justify-between gap-4 p-3 rounded-lg bg-white/[0.02] border border-white/8">
              <div className="relative flex-1 min-w-[240px]">
                <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
                <input
                  type="text"
                  placeholder="Pesquisar por endereço local, remoto, porta ou PID..."
                  value={searchFilter}
                  onChange={(e) => setSearchFilter(e.target.value)}
                  className="w-full pl-9 pr-4 py-1.5 bg-black/40 border border-white/10 rounded-md text-xs text-white placeholder-gray-500 outline-none focus:border-cyan-400"
                />
              </div>

              <div className="flex gap-2">
                {(['all', 'listen', 'active'] as const).map((mode) => (
                  <button
                    key={mode}
                    onClick={() => setNetworkFilter(mode)}
                    className={`px-3 py-1.5 text-xs rounded-md border transition-all cursor-pointer ${
                      networkFilter === mode
                        ? 'bg-cyan-500/20 border-cyan-400 text-cyan-200'
                        : 'bg-white/[0.02] border-white/8 text-gray-400 hover:text-white'
                    }`}
                  >
                    {mode === 'all' ? 'Todos' : mode === 'listen' ? 'Portas LISTEN' : 'Conexões Ativas'}
                  </button>
                ))}
              </div>
            </div>

            {/* Network Table */}
            <div className="border border-white/8 rounded-lg overflow-hidden bg-white/[0.01]">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="border-b border-white/8 bg-white/[0.03] text-gray-400 font-mono">
                      <th className="p-3">Protocolo</th>
                      <th className="p-3">Endereço Local</th>
                      <th className="p-3">Porta Local</th>
                      <th className="p-3">Endereço Remoto</th>
                      <th className="p-3">Estado</th>
                      <th className="p-3">PID / Processo</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5 font-sans">
                    {filteredNetwork.slice(0, 100).map((n, idx) => (
                      <tr key={idx} className="hover:bg-white/[0.02] transition-colors">
                        <td className="p-3 font-mono text-cyan-300 font-bold">{n.protocol as string}</td>
                        <td className="p-3 font-mono text-gray-300">{n.local_address as string}</td>
                        <td className="p-3 font-mono font-bold text-white">{n.local_port as number}</td>
                        <td className="p-3 font-mono text-gray-400">
                          {n.remote_address ? `${n.remote_address}:${n.remote_port}` : '-'}
                        </td>
                        <td className="p-3 font-mono">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              n.status === 'LISTEN'
                                ? 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/30'
                                : 'bg-cyan-500/10 text-cyan-300 border border-cyan-500/30'
                            }`}
                          >
                            {n.status as string}
                          </span>
                        </td>
                        <td className="p-3 font-medium text-gray-200">
                          {n.process_name ? `${n.process_name} (PID ${n.pid})` : `PID ${n.pid || '-'}`}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* PERSISTENCE TAB */}
        {activeTab === 'persistence' && (
          <div className="space-y-4">
            <div className="border border-white/8 rounded-lg overflow-hidden bg-white/[0.01]">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="border-b border-white/8 bg-white/[0.03] text-gray-400 font-mono">
                      <th className="p-3">Mecanismo</th>
                      <th className="p-3">Nome / Chave</th>
                      <th className="p-3">Destino / Executável</th>
                      <th className="p-3">Localização</th>
                      <th className="p-3">Estado</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5 font-sans">
                    {persistence.slice(0, 100).map((p, idx) => (
                      <tr key={idx} className="hover:bg-white/[0.02] transition-colors">
                        <td className="p-3 font-mono text-cyan-300 font-semibold">{p.kind as string}</td>
                        <td className="p-3 font-medium text-white">{p.name as string}</td>
                        <td className="p-3 text-gray-400 font-mono text-[11px] max-w-sm truncate" title={p.target_path as string}>
                          {p.target_path as string || '-'}
                        </td>
                        <td className="p-3 text-gray-500 font-mono text-[10px] max-w-xs truncate">{p.location as string || '-'}</td>
                        <td className="p-3">
                          <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-emerald-500/10 text-emerald-300 border border-emerald-500/30">
                            {p.status_label as string || 'KNOWN_GOOD'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* BROWSER EXTENSIONS TAB */}
        {activeTab === 'browser' && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {browserExts.map((ext, idx) => {
              const perms = (ext.permissions as string[]) || [];
              const hasSensitive = perms.some((p) =>
                ['cookies', 'webRequest', 'webRequestBlocking', '<all_urls>', '*://*/*'].includes(p)
              );
              return (
                <div
                  key={idx}
                  className="p-4 rounded-lg bg-white/[0.02] border border-white/8 hover:border-cyan-500/30 transition-all flex flex-col justify-between"
                >
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-mono font-bold text-cyan-400">{ext.browser as string}</span>
                      <span className="text-[10px] font-mono text-gray-500">v{ext.version as string}</span>
                    </div>
                    <h4 className="text-sm font-bold text-white">{ext.name as string}</h4>
                    <p className="text-xs text-gray-400 line-clamp-2">{ext.description as string || 'Sem descrição disponível.'}</p>
                  </div>

                  <div className="mt-4 pt-3 border-t border-white/5 space-y-2">
                    <div className="flex items-center justify-between text-[10px] text-gray-500">
                      <span>Permissões: {perms.length}</span>
                      {hasSensitive && (
                        <span className="text-amber-400 font-bold">⚠️ Permissões Elevadas</span>
                      )}
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {perms.slice(0, 4).map((p, pIdx) => (
                        <span
                          key={pIdx}
                          className="px-1.5 py-0.5 rounded bg-white/[0.04] text-[9px] font-mono text-gray-400"
                        >
                          {p}
                        </span>
                      ))}
                      {perms.length > 4 && (
                        <span className="text-[9px] text-gray-600 font-mono">+{perms.length - 4} mais</span>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* SECURITY EVENTS TAB */}
        {activeTab === 'events' && (
          <div className="space-y-4">
            {sentinelEvents.length === 0 ? (
              <div className="p-12 text-center rounded-xl bg-white/[0.02] border border-white/8 space-y-3">
                <ShieldCheck className="w-12 h-12 mx-auto text-emerald-400/70" />
                <h3 className="text-base font-bold text-white">Nenhum Incidente Ativo ou Anomalia Detetada</h3>
                <p className="text-xs text-gray-400 max-w-md mx-auto leading-relaxed">
                  A postura do sistema encontra-se segura. Todos os processos, conexões e entradas de persistência observados estão em conformidade com o baseline de integridade.
                </p>
              </div>
            ) : (
              sentinelEvents.map((ev) => (
                <div
                  key={ev.event_id}
                  className="p-5 rounded-lg bg-white/[0.03] border border-white/8 space-y-3"
                >
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <span
                        className={`text-xs font-bold px-2.5 py-0.5 rounded border uppercase ${
                          ev.severity === 'HIGH_RISK'
                            ? 'bg-rose-500/20 text-rose-300 border-rose-500/30'
                            : ev.severity === 'SUSPICIOUS'
                            ? 'bg-amber-500/20 text-amber-300 border-amber-500/30'
                            : ev.severity === 'UNKNOWN'
                            ? 'bg-purple-500/20 text-purple-300 border-purple-500/30'
                            : 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30'
                        }`}
                      >
                        {ev.severity}
                      </span>
                      <span className="text-sm font-bold text-white font-mono">{ev.event_id}</span>
                      <span className="text-xs text-gray-400 font-mono">[{ev.category}]</span>
                      {ev.confidence !== undefined && (
                        <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-white/5 border border-white/10 text-cyan-200">
                          Confiança: {(ev.confidence * 100).toFixed(0)}%
                        </span>
                      )}
                    </div>

                    <div className="text-xs font-mono text-gray-500">
                      Observações: {ev.occurrence_count}x | Primeira: {new Date(ev.first_seen * 1000).toLocaleTimeString()}
                    </div>
                  </div>

                  <p className="text-sm text-gray-200 font-medium">{ev.rationale}</p>

                  <div className="p-3 rounded bg-black/30 border border-white/5 text-xs text-cyan-300">
                    <span className="font-semibold text-white">Recomendação Defensiva:</span> {ev.recommended_action}
                  </div>

                  {/* Human Review Banner if already reviewed */}
                  {ev.human_review && (
                    <div className="p-3 rounded bg-emerald-500/10 border border-emerald-500/30 text-xs text-emerald-300 font-mono flex flex-wrap items-center justify-between gap-2">
                      <span>✓ Revisto por <strong>{ev.human_review.operator}</strong>: <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-200 uppercase font-bold">{ev.human_review.final_classification}</span> ({ev.human_review.reason})</span>
                      {ev.human_review.is_false_positive && (
                        <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30 text-[10px] font-bold">
                          FALSO POSITIVO IDENTIFICADO
                        </span>
                      )}
                    </div>
                  )}

                  {/* Observation Timeline */}
                  {ev.observation_timeline && ev.observation_timeline.length > 0 && (
                    <div className="pt-2 border-t border-white/5 space-y-1">
                      <span className="text-[10px] text-gray-500 uppercase tracking-wider font-mono">
                        Linha do Tempo de Observações:
                      </span>
                      <div className="space-y-1">
                        {ev.observation_timeline.map((ot, otIdx) => (
                          <div key={otIdx} className="text-xs text-gray-400 flex items-center gap-2 font-mono">
                            <Clock className="w-3 h-3 text-cyan-400" />
                            <span>{new Date(ot.timestamp * 1000).toLocaleTimeString()}</span>
                            <span className="text-gray-500">—</span>
                            <span>{ot.note}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Human Review Footer Action */}
                  <div className="flex items-center justify-between pt-2 border-t border-white/5 gap-3">
                    <div className="text-[10px] text-gray-500 font-mono">
                      {ev.human_review
                        ? `Classificação Inicial: ${ev.model_classification || ev.severity} | Revisto em ${new Date(ev.human_review.timestamp * 1000).toLocaleTimeString()}`
                        : 'Aguardando Revisão Humana Opcional'}
                    </div>

                    <button
                      onClick={() => {
                        setReviewModalEvent(ev);
                        setReviewClass(ev.severity === 'HIGH_RISK' ? 'BENIGN' : 'KNOWN_GOOD');
                        setReviewReason('');
                      }}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-purple-500/20 hover:bg-purple-500/30 border border-purple-500/40 text-purple-200 text-xs font-semibold cursor-pointer transition-all active:scale-98"
                    >
                      <UserCheck className="w-3.5 h-3.5 text-purple-400" />
                      <span>Rever Incidente (Human Review)</span>
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {/* EVIDENCE INSPECTOR TAB */}
        {activeTab === 'evidence' && (
          <div className="space-y-4">
            <div className="p-4 rounded-lg bg-white/[0.02] border border-white/8">
              <h4 className="text-sm font-bold text-white mb-2">Evidence Metadata & Cryptographic Integrity</h4>
              <p className="text-xs text-gray-400 mb-4">
                Todas as evidências recolhidas pelo Sentinel são 100% não-destrutivas, higienizadas contra credenciais e assinadas criptograficamente por SHA-256.
              </p>

              {selectedEvidence ? (
                <div className="p-4 rounded bg-black/40 border border-white/10 font-mono text-xs text-gray-300 overflow-x-auto">
                  <pre>{JSON.stringify(selectedEvidence, null, 2)}</pre>
                </div>
              ) : (
                <div className="p-8 text-center text-gray-500">
                  <Info className="w-8 h-8 mx-auto mb-2 text-cyan-400/50" />
                  <p className="text-xs">Seleciona um evento ou processo para inspecionar os metadados brutos normalizados.</p>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Accept Known Good Modal */}
      <AnimatePresence>
        {knownGoodModalItem && (
          <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="bg-[#0b0e18] border border-white/10 rounded-xl p-6 max-w-md w-full shadow-2xl space-y-4"
            >
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
                  <CheckCircle className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white">Aceitar como Known Good</h3>
                  <p className="text-xs text-gray-400">Marca esta alteração como comportamento legítimo.</p>
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-xs text-gray-300 font-medium">Motivo da Aprovação:</label>
                <input
                  type="text"
                  placeholder="Ex: Atualização legítima do Chrome / VS Code..."
                  value={knownGoodReason}
                  onChange={(e) => setKnownGoodReason(e.target.value)}
                  className="w-full px-3 py-2 bg-black/40 border border-white/10 rounded-md text-xs text-white placeholder-gray-500 outline-none focus:border-cyan-400"
                />
              </div>

              <div className="flex justify-end gap-3 pt-2">
                <button
                  onClick={() => setKnownGoodModalItem(null)}
                  className="px-4 py-2 rounded-md bg-white/[0.05] hover:bg-white/10 text-xs text-gray-300 cursor-pointer"
                >
                  Cancelar
                </button>
                <button
                  onClick={handleConfirmKnownGood}
                  className="px-4 py-2 rounded-md bg-emerald-500 hover:bg-emerald-400 text-black font-bold text-xs cursor-pointer"
                >
                  Aprovar Alteração
                </button>
              </div>
            </motion.div>
          </div>
        )}

        {/* Action Confirmation & Human Approval Modal */}
        {actionConfirmModal && (
          <div className="fixed inset-0 bg-black/80 backdrop-blur-md z-50 flex items-center justify-center p-4">
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="bg-[#0c0f1d] border border-amber-500/40 rounded-xl p-6 max-w-lg w-full shadow-2xl space-y-5"
            >
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 rounded-lg bg-amber-500/10 border border-amber-500/40 flex items-center justify-center text-amber-400 shrink-0">
                  <ShieldAlert className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white">Autorização de Resposta Defensiva</h3>
                  <span className="text-xs font-mono text-amber-300">Ação ID: {actionConfirmModal.action_id}</span>
                </div>
              </div>

              <div className="p-3.5 rounded-lg bg-amber-500/15 border border-amber-500/40 text-amber-200 text-xs font-semibold flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
                <span>⚠️ ESTA AÇÃO ALTERARÁ O SISTEMA (REQUER AUTORIZAÇÃO EXPLÍCITA)</span>
              </div>

              <div className="space-y-3 bg-black/40 p-4 rounded-lg border border-white/10 text-xs font-mono">
                <div className="flex justify-between">
                  <span className="text-gray-500">Tipo de Ação:</span>
                  <span className="text-cyan-300 font-bold">{actionConfirmModal.action_type}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Nível de Risco:</span>
                  <span className="text-amber-300">{actionConfirmModal.permission_level}</span>
                </div>
                <div>
                  <span className="text-gray-500 block mb-1">Alvo Identificado:</span>
                  <div className="bg-black/60 p-2 rounded text-white break-all">{actionConfirmModal.target}</div>
                </div>
                <div>
                  <span className="text-gray-500 block mb-1">Racional Defensivo:</span>
                  <p className="text-gray-300 font-sans text-xs">{actionConfirmModal.rationale}</p>
                </div>
                {actionConfirmModal.rollback_available && (
                  <div className="pt-2 border-t border-white/5 flex items-center gap-2 text-gray-400 font-sans text-[11px]">
                    <RotateCcw className="w-3.5 h-3.5 text-cyan-400" />
                    <span>Plano de Rollback: {actionConfirmModal.rollback_plan}</span>
                  </div>
                )}
              </div>

              <div className="text-[11px] text-gray-400">
                A aprovação será auditada e assinada com a identidade da sessão do operador humano.
              </div>

              <div className="flex justify-end gap-3 pt-1">
                <button
                  onClick={() => setActionConfirmModal(null)}
                  className="px-4 py-2 rounded-md bg-white/[0.05] hover:bg-white/10 text-xs text-gray-300 cursor-pointer"
                >
                  Cancelar
                </button>
                <button
                  onClick={() => {
                    approveSentinelAction(
                      actionConfirmModal.action_id,
                      'human_operator',
                      'web_session',
                      actionConfirmModal.incident_id
                    );
                    setActionConfirmModal(null);
                  }}
                  className="px-5 py-2 rounded-md bg-emerald-500 hover:bg-emerald-400 text-black font-bold text-xs cursor-pointer shadow-lg active:scale-98"
                >
                  Confirmar e Executar
                </button>
              </div>
            </motion.div>
          </div>
        )}

        {/* Reject Reason Modal */}
        {rejectReasonModal && (
          <div className="fixed inset-0 bg-black/80 backdrop-blur-md z-50 flex items-center justify-center p-4">
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="bg-[#0c0f1d] border border-rose-500/30 rounded-xl p-6 max-w-md w-full shadow-2xl space-y-4"
            >
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 rounded-lg bg-rose-500/10 border border-rose-500/30 flex items-center justify-center text-rose-400">
                  <X className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white">Rejeitar Proposta de Resposta</h3>
                  <p className="text-xs text-gray-400">A ação será cancelada e registada como rejeitada.</p>
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-xs text-gray-300 font-medium">Motivo da Rejeição:</label>
                <input
                  type="text"
                  placeholder="Ex: Falso positivo / processo legítimo de manutenção..."
                  value={rejectReasonText}
                  onChange={(e) => setRejectReasonText(e.target.value)}
                  className="w-full px-3 py-2 bg-black/40 border border-white/10 rounded-md text-xs text-white placeholder-gray-500 outline-none focus:border-rose-400"
                />
              </div>

              <div className="flex justify-end gap-3 pt-2">
                <button
                  onClick={() => {
                    setRejectReasonModal(null);
                    setRejectReasonText('');
                  }}
                  className="px-4 py-2 rounded-md bg-white/[0.05] hover:bg-white/10 text-xs text-gray-300 cursor-pointer"
                >
                  Voltar
                </button>
                <button
                  onClick={() => {
                    if (rejectReasonModal) {
                      rejectSentinelAction(rejectReasonModal, rejectReasonText || 'Rejeitado pelo operador');
                      setRejectReasonModal(null);
                      setRejectReasonText('');
                    }
                  }}
                  className="px-4 py-2 rounded-md bg-rose-500 hover:bg-rose-400 text-white font-bold text-xs cursor-pointer"
                >
                  Confirmar Rejeição
                </button>
              </div>
            </motion.div>
          </div>
        )}

        {/* HUMAN REVIEW MODAL */}
        {reviewModalEvent && (
          <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="bg-[#12141a] border border-purple-500/40 rounded-xl max-w-lg w-full p-6 shadow-2xl space-y-4"
            >
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-lg bg-purple-500/20 text-purple-400">
                  <UserCheck className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white">Revisão Humana de Incidente</h3>
                  <p className="text-xs text-gray-400">Classificação e verificação manual por operador de segurança.</p>
                </div>
              </div>

              <div className="p-3.5 rounded-lg bg-black/40 border border-white/5 space-y-1.5 font-mono text-xs">
                <div className="flex justify-between text-gray-400">
                  <span>ID do Incidente:</span>
                  <span className="text-white font-bold">{reviewModalEvent.event_id}</span>
                </div>
                <div className="flex justify-between text-gray-400">
                  <span>Classificação do Modelo:</span>
                  <span className="text-amber-300 font-bold">{reviewModalEvent.model_classification || reviewModalEvent.severity}</span>
                </div>
                <div className="flex justify-between text-gray-400">
                  <span>Categoria:</span>
                  <span className="text-cyan-300">{reviewModalEvent.category}</span>
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-xs text-gray-300 font-medium">Classificação Final do Operador:</label>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                  {['BENIGN', 'KNOWN_GOOD', 'SUSPICIOUS', 'HIGH_RISK', 'UNKNOWN'].map((cls) => (
                    <button
                      key={cls}
                      type="button"
                      onClick={() => setReviewClass(cls)}
                      className={`px-3 py-2 rounded border text-xs font-bold font-mono transition-all cursor-pointer ${
                        reviewClass === cls
                          ? 'border-purple-400 bg-purple-500/20 text-purple-200 shadow-md'
                          : 'border-white/10 bg-white/[0.02] text-gray-400 hover:border-white/20 hover:text-white'
                      }`}
                    >
                      {cls}
                    </button>
                  ))}
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-xs text-gray-300 font-medium">Justificativa / Motivo da Decisão:</label>
                <textarea
                  rows={3}
                  placeholder="Ex: Falso positivo verificado. Trata-se de script de build interno ou processo autorizado."
                  value={reviewReason}
                  onChange={(e) => setReviewReason(e.target.value)}
                  className="w-full px-3 py-2 bg-black/40 border border-white/10 rounded-md text-xs text-white placeholder-gray-500 outline-none focus:border-purple-400 resize-none font-sans"
                />
              </div>

              <div className="flex justify-end gap-3 pt-2">
                <button
                  onClick={() => {
                    setReviewModalEvent(null);
                    setReviewReason('');
                  }}
                  className="px-4 py-2 rounded-md bg-white/[0.05] hover:bg-white/10 text-xs text-gray-300 cursor-pointer"
                >
                  Cancelar
                </button>
                <button
                  onClick={() => {
                    submitSentinelReview(
                      reviewModalEvent.event_id,
                      reviewClass,
                      reviewReason || 'Revisão manual concluída pelo operador',
                      'human_operator'
                    );
                    setReviewModalEvent(null);
                    setReviewReason('');
                  }}
                  className="px-4 py-2 rounded-md bg-purple-600 hover:bg-purple-500 text-white font-bold text-xs cursor-pointer transition-all active:scale-98 shadow-md"
                >
                  Confirmar Revisão Humana
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
};
