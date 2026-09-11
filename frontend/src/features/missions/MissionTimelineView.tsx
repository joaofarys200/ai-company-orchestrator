import React, { useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Filter,
  GitBranch,
  GitCommit,
  History,
  Play,
  RefreshCw,
  RotateCcw,
  Wrench,
} from 'lucide-react';
import type { MissionTimelinePayload } from '../../protocol/websocket';

interface MissionTimelineViewProps {
  timeline?: MissionTimelinePayload | null;
  onRefresh?: () => void;
}

const SAMPLE_TIMELINE: MissionTimelinePayload = {
  mission_id: 'm_lh_saas_05_r1',
  title: 'Multi-Tenant SaaS Workspace & Document Management Engine',
  status: 'COMPLETED',
  complexity_level: 'LEVEL_4',
  total_transitions: 142,
  success_rate: 0.993,
  drift_score: 0.0,
  requirement_retention: 1.0,
  checkpoints_count: 12,
  active_agents_count: 6,
  events: [
    {
      id: 'evt_001',
      sequence: 1,
      type: 'TASK_CREATION',
      title: 'Decomposição Inicial de Requisitos e Tarefas Core',
      agent_role: 'ARCHITECTURE',
      timestamp: Date.now() - 150000,
      details: { tasks: 8, graph_version: 1, strategy: 'TOPOLOGICAL_KAHN' },
    },
    {
      id: 'evt_002',
      sequence: 2,
      type: 'TASK_START',
      title: 'Estruturação do Schema Multi-Tenant & RBAC',
      agent_role: 'ARCHITECTURE',
      timestamp: Date.now() - 140000,
      details: { task_id: 'lh_task_000', lease_duration: '30s' },
    },
    {
      id: 'evt_003',
      sequence: 3,
      type: 'TASK_COMPLETION',
      title: 'Contratos e Modelo de Dados Isolado Aprovados',
      agent_role: 'ARCHITECTURE',
      timestamp: Date.now() - 125000,
      details: { status: 'COMPLETED', exit_code: 0 },
    },
    {
      id: 'evt_004',
      sequence: 4,
      type: 'TASK_REPLAN',
      title: 'Expansão Dinâmica de SubDAG (ADAPT): Módulo RBAC',
      agent_role: 'ARCHITECTURE',
      timestamp: Date.now() - 110000,
      details: { subdags_added: 3, new_tasks: 12, graph_version: 2 },
    },
    {
      id: 'evt_005',
      sequence: 5,
      type: 'TASK_RETRY',
      title: 'Detecção de Conflito de Lease & Falha de Build Injetada',
      agent_role: 'CODING',
      timestamp: Date.now() - 95000,
      details: { fault: 'BUILD_FAILURE', retry_attempt: 1 },
    },
    {
      id: 'evt_006',
      sequence: 6,
      type: 'TASK_REPAIR',
      title: 'Auto-Cura Cirúrgica AST: Resolução de Dependência',
      agent_role: 'CODING',
      timestamp: Date.now() - 85000,
      details: { fault_resolved: 'BUILD_FAILURE', unrelated_changes: 0, duration_ms: 240 },
    },
    {
      id: 'evt_007',
      sequence: 7,
      type: 'TASK_ROLLBACK',
      title: 'Interrupção Abrupta Simulada de Worker (Crash)',
      agent_role: 'COORDINATOR',
      timestamp: Date.now() - 65000,
      details: { stage: 'worker_kill_at_task_45', simulated_crash: true },
    },
    {
      id: 'evt_008',
      sequence: 8,
      type: 'TASK_RECOVERY',
      title: 'Recuperação ACID de Checkpoint: Retomada sem Duplicação',
      agent_role: 'COORDINATOR',
      timestamp: Date.now() - 55000,
      details: { checkpoint_id: 'cp_rec_02', duplicated_work: 0, latency_ms: 18.5 },
    },
    {
      id: 'evt_009',
      sequence: 9,
      type: 'TASK_START',
      title: 'Geração da Suite de Testes de Quotas e Concorrência',
      agent_role: 'TESTING',
      timestamp: Date.now() - 35000,
      details: { test_files: ['test_rbac.py', 'test_tenancy.py'] },
    },
    {
      id: 'evt_010',
      sequence: 10,
      type: 'TASK_COMPLETION',
      title: 'Todos os Requisitos e Critérios Validados (PASS)',
      agent_role: 'REVIEW',
      timestamp: Date.now() - 10000,
      details: { requirements_retention: '100%', ledger: 'PASS', false_success: '0.00%' },
    },
  ],
};

export const MissionTimelineView: React.FC<MissionTimelineViewProps> = ({
  timeline: propTimeline,
  onRefresh,
}) => {
  const data = propTimeline || SAMPLE_TIMELINE;
  const [filterType, setFilterType] = useState<string>('ALL');

  const filteredEvents = data.events.filter((evt) => {
    if (filterType === 'ALL') return true;
    if (filterType === 'TASKS') return evt.type === 'TASK_START' || evt.type === 'TASK_COMPLETION';
    if (filterType === 'REPAIRS') return evt.type === 'TASK_REPAIR' || evt.type === 'TASK_RETRY';
    if (filterType === 'REPLANS') return evt.type === 'TASK_REPLAN';
    if (filterType === 'RECOVERY') return evt.type === 'TASK_RECOVERY' || evt.type === 'TASK_ROLLBACK';
    return true;
  });

  const getEventTone = (type: string) => {
    switch (type) {
      case 'TASK_COMPLETION':
        return {
          badgeBg: 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300',
          dot: 'bg-emerald-400',
          border: 'border-emerald-500/40',
          icon: CheckCircle2,
        };
      case 'TASK_START':
      case 'TASK_CREATION':
        return {
          badgeBg: 'bg-cyan-500/10 border-cyan-500/30 text-cyan-300',
          dot: 'bg-cyan-400',
          border: 'border-cyan-500/30',
          icon: Play,
        };
      case 'TASK_REPAIR':
        return {
          badgeBg: 'bg-violet-500/15 border-violet-500/30 text-violet-300',
          dot: 'bg-violet-400',
          border: 'border-violet-500/40',
          icon: Wrench,
        };
      case 'TASK_REPLAN':
        return {
          badgeBg: 'bg-amber-500/10 border-amber-500/30 text-amber-300',
          dot: 'bg-amber-400',
          border: 'border-amber-500/30',
          icon: GitBranch,
        };
      case 'TASK_RECOVERY':
        return {
          badgeBg: 'bg-sky-500/15 border-sky-500/30 text-sky-300',
          dot: 'bg-sky-400',
          border: 'border-sky-500/40',
          icon: RotateCcw,
        };
      case 'TASK_RETRY':
      case 'TASK_ROLLBACK':
        return {
          badgeBg: 'bg-rose-500/10 border-rose-500/30 text-rose-300',
          dot: 'bg-rose-400',
          border: 'border-rose-500/40',
          icon: AlertTriangle,
        };
      default:
        return {
          badgeBg: 'bg-gray-500/10 border-gray-500/30 text-gray-300',
          dot: 'bg-gray-400',
          border: 'border-white/10',
          icon: History,
        };
    }
  };

  return (
    <div className="flex h-full w-full flex-col overflow-hidden bg-[#070a10] text-gray-200">
      {/* ── TOP HEADER ── */}
      <header className="flex flex-shrink-0 items-center justify-between border-b border-white/10 bg-[#090d16] px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-cyan-400/30 bg-cyan-500/10 text-cyan-300 shadow-sm shadow-cyan-500/20">
            <GitCommit className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-base font-bold tracking-tight text-white">Visual Mission Timeline</h1>
              <span className="rounded border border-white/10 bg-white/[0.04] px-1.5 py-0.5 text-[10px] font-mono uppercase text-gray-400">
                FASE 32
              </span>
              <span className="rounded border border-cyan-400/30 bg-cyan-400/10 px-2 py-0.5 text-[10px] font-semibold text-cyan-300">
                {data.complexity_level}
              </span>
              <span className="rounded border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold text-emerald-300">
                {data.status}
              </span>
            </div>
            <p className="text-xs text-gray-400">
              Rastreamento cronológico de transições de tarefas, handoffs de agentes e retenção de autonomia
            </p>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-3">
          <span className="rounded-md border border-cyan-500/30 bg-cyan-500/10 px-2.5 py-1 text-xs font-mono font-bold text-cyan-300">
            {data.total_transitions} Transições
          </span>
          {onRefresh && (
            <button
              onClick={onRefresh}
              className="flex h-8 w-8 items-center justify-center rounded-md border border-white/10 bg-white/[0.04] text-gray-300 transition hover:bg-white/[0.08] hover:text-white"
              title="Atualizar timeline"
            >
              <RefreshCw className="h-4 w-4" />
            </button>
          )}
        </div>
      </header>

      {/* ── KPI METRICS CARDS ── */}
      <div className="grid grid-cols-2 gap-3 border-b border-white/10 bg-[#080c14] p-4 sm:grid-cols-3 lg:grid-cols-6">
        <div className="rounded-md border border-white/8 bg-black/25 p-3">
          <span className="text-[11px] font-medium text-gray-400">Transições Totais</span>
          <p className="mt-1 font-mono text-lg font-bold text-cyan-300">{data.total_transitions}</p>
        </div>
        <div className="rounded-md border border-white/8 bg-black/25 p-3">
          <span className="text-[11px] font-medium text-gray-400">Sucesso / Transição</span>
          <p className="mt-1 font-mono text-lg font-bold text-emerald-300">{(data.success_rate * 100).toFixed(1)}%</p>
        </div>
        <div className="rounded-md border border-white/8 bg-black/25 p-3">
          <span className="text-[11px] font-medium text-gray-400">Mission Drift Score</span>
          <p className="mt-1 font-mono text-lg font-bold text-emerald-300">{data.drift_score.toFixed(2)}</p>
        </div>
        <div className="rounded-md border border-white/8 bg-black/25 p-3">
          <span className="text-[11px] font-medium text-gray-400">Retenção de Requisitos</span>
          <p className="mt-1 font-mono text-lg font-bold text-cyan-300">{(data.requirement_retention * 100).toFixed(0)}%</p>
        </div>
        <div className="rounded-md border border-white/8 bg-black/25 p-3">
          <span className="text-[11px] font-medium text-gray-400">Agentes no Swarm</span>
          <p className="mt-1 font-mono text-lg font-bold text-violet-300">{data.active_agents_count} Roles</p>
        </div>
        <div className="rounded-md border border-white/8 bg-black/25 p-3">
          <span className="text-[11px] font-medium text-gray-400">Checkpoints ACID</span>
          <p className="mt-1 font-mono text-lg font-bold text-sky-300">{data.checkpoints_count}</p>
        </div>
      </div>

      {/* ── FILTER TOOLBAR ── */}
      <div className="flex items-center justify-between border-b border-white/10 bg-[#0a0f1c] px-6 py-2">
        <div className="flex items-center gap-1.5 overflow-x-auto text-xs">
          <Filter className="mr-1 h-3.5 w-3.5 text-gray-500" />
          {[
            { id: 'ALL', label: 'Todos os Eventos' },
            { id: 'TASKS', label: 'Execução de Tarefas' },
            { id: 'REPAIRS', label: 'Auto-Cura (Reparos)' },
            { id: 'REPLANS', label: 'Replanning & SubDAG' },
            { id: 'RECOVERY', label: 'Crash Recovery' },
          ].map((f) => (
            <button
              key={f.id}
              onClick={() => setFilterType(f.id)}
              className={`rounded-md px-2.5 py-1 font-medium transition ${
                filterType === f.id
                  ? 'border border-cyan-400/30 bg-cyan-400/10 text-cyan-200'
                  : 'text-gray-400 hover:bg-white/[0.04] hover:text-gray-200'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
        <span className="text-[11px] text-gray-400">
          Mostrando {filteredEvents.length} de {data.events.length} eventos
        </span>
      </div>

      {/* ── CHRONOLOGICAL TIMELINE STREAM ── */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="relative pl-6 before:absolute before:bottom-0 before:left-3 before:top-2 before:w-0.5 before:bg-white/10">
          <div className="space-y-4">
            {filteredEvents.map((evt) => {
              const tone = getEventTone(evt.type);
              const EventIcon = tone.icon;
              return (
                <div key={evt.id} className="relative flex items-start gap-4">
                  {/* Timeline Bubble Node */}
                  <div
                    className={`absolute -left-6 mt-1 flex h-6 w-6 items-center justify-center rounded-full border ${tone.border} bg-[#090d16] text-xs font-bold shadow-md`}
                  >
                    <EventIcon className={`h-3.5 w-3.5 ${tone.dot.replace('bg-', 'text-')}`} />
                  </div>

                  {/* Event Card */}
                  <div className="flex-1 rounded-lg border border-white/10 bg-[#090d16] p-4 transition hover:border-cyan-400/30">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className="flex h-5 w-5 items-center justify-center rounded bg-white/5 font-mono text-[10px] text-gray-400">
                          #{evt.sequence}
                        </span>
                        <span className={`rounded border px-2 py-0.5 text-[10px] font-bold ${tone.badgeBg}`}>
                          {evt.type}
                        </span>
                        <h3 className="text-xs font-bold text-white">{evt.title}</h3>
                      </div>

                      <div className="flex items-center gap-2 text-[11px]">
                        <span className="rounded bg-white/5 px-2 py-0.5 font-semibold text-gray-300">
                          Agente: {evt.agent_role}
                        </span>
                        <span className="flex items-center gap-1 font-mono text-gray-500">
                          <Clock className="h-3 w-3" />
                          {new Date(evt.timestamp).toLocaleTimeString()}
                        </span>
                      </div>
                    </div>

                    {/* Metadata details box */}
                    {evt.details && Object.keys(evt.details).length > 0 && (
                      <div className="mt-3 rounded border border-white/5 bg-black/30 p-2.5 font-mono text-[11px] text-gray-300">
                        <div className="flex flex-wrap gap-x-4 gap-y-1">
                          {Object.entries(evt.details).map(([k, v]) => (
                            <span key={k}>
                              <strong className="text-gray-500">{k}:</strong>{' '}
                              <span className="text-cyan-300">{typeof v === 'object' ? JSON.stringify(v) : String(v)}</span>
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};
