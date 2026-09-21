import React, { useState } from 'react';
import {
  CheckCircle2,
  Clock,
  Circle,
  AlertCircle,
  ArrowRight,
  ShieldCheck,
  Activity,
  Cpu,
  Sparkles,
  ChevronDown,
  Layers,
} from 'lucide-react';
import type { MissionControlStateData } from '../../../protocol/websocket';

interface MissionOverviewPanelProps {
  missionState: MissionControlStateData;
  onNavigateTab: (tab: 'tasks' | 'agents' | 'activity' | 'diagnostics') => void;
  onOpenInCode?: (filePath: string, line?: number) => void;
}

export const MissionOverviewPanel: React.FC<MissionOverviewPanelProps> = ({
  missionState,
  onNavigateTab,
}) => {
  const [showAssumptions, setShowAssumptions] = useState(false);

  const tasks = missionState.tasks || [];
  const previewTasks = tasks.slice(0, 4);

  const agents = missionState.agents || [];
  const previewAgents = agents.slice(0, 3);

  const events = (missionState.events || []).slice(-4).reverse();
  const requirements = missionState.requirements || [];
  const assumptions = missionState.assumptions || [];

  return (
    <div className="space-y-4 max-w-7xl mx-auto">
      {/* 1. PROGRESS BAR & CORE METRICS ROW */}
      <div className="rounded-lg border border-white/8 bg-white/[0.02] p-4">
        <div className="flex items-center justify-between gap-4 mb-2">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-gray-400">
              Progresso Geral da Missão
            </span>
            <span className="text-xs text-gray-500">·</span>
            <span className="text-xs text-gray-300">
              Fase: <strong className="text-white">{missionState.current_stage}</strong>
            </span>
          </div>
          <span className="font-mono text-sm font-bold text-cyan-300">
            {missionState.progress_percentage}%
          </span>
        </div>

        {/* Clean Progress Bar */}
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/10">
          <div
            className="h-full bg-gradient-to-r from-cyan-400 to-emerald-400 transition-all duration-500"
            style={{ width: `${Math.max(4, Math.min(100, missionState.progress_percentage))}%` }}
          />
        </div>

        {/* Condensed Sub-metrics */}
        <div className="mt-3 flex flex-wrap items-center gap-4 text-xs text-gray-400">
          <div className="flex items-center gap-1.5">
            <Cpu className="h-3.5 w-3.5 text-purple-300" />
            <span>
              <strong className="text-gray-200">{missionState.active_agents_count}</strong> de 6 agentes ativos
            </span>
          </div>
          <span className="text-gray-700">|</span>
          <div className="flex items-center gap-1.5">
            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-300" />
            <span>
              <strong className="text-gray-200">{missionState.requirements_validated_count}</strong> de{' '}
              {missionState.requirements_count} requisitos validados
            </span>
          </div>
          <span className="text-gray-700">|</span>
          <div className="flex items-center gap-1.5">
            <Clock className="h-3.5 w-3.5 text-cyan-300" />
            <span>
              Tempo: <strong className="font-mono text-gray-200">{missionState.total_duration_seconds}s</strong>
            </span>
          </div>
          <span className="text-gray-700">|</span>
          <div className="flex items-center gap-1.5">
            <ShieldCheck className="h-3.5 w-3.5 text-emerald-300" />
            <span className="text-emerald-300 font-medium">0 incidentes em runtime</span>
          </div>
        </div>
      </div>

      {/* 2. MAIN 2-COLUMN BALANCED CONTENT GRID */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* LEFT COLUMN: TASKS & REQUIREMENTS */}
        <div className="space-y-4">
          {/* Card: Tarefas em Curso */}
          <div className="rounded-lg border border-white/8 bg-white/[0.02] p-4">
            <div className="flex items-center justify-between pb-3 border-b border-white/6 mb-3">
              <div className="flex items-center gap-2">
                <Layers className="h-4 w-4 text-cyan-300" />
                <h2 className="text-xs font-semibold uppercase tracking-wider text-gray-200">
                  Tarefas da Missão
                </h2>
              </div>
              <button
                onClick={() => onNavigateTab('tasks')}
                className="inline-flex items-center gap-1 text-xs text-cyan-300 hover:text-cyan-200 font-medium transition-colors"
              >
                <span>Ver todas ({tasks.length})</span>
                <ArrowRight className="h-3 w-3" />
              </button>
            </div>

            <div className="space-y-2">
              {previewTasks.length === 0 ? (
                <p className="text-xs text-gray-500 py-3 text-center">Nenhuma tarefa no plano ativo.</p>
              ) : (
                previewTasks.map((t) => (
                  <div
                    key={t.id}
                    onClick={() => onNavigateTab('tasks')}
                    className="group flex items-center justify-between gap-3 rounded-md border border-white/5 bg-white/[0.015] px-3 py-2 text-xs transition-colors hover:border-white/15 hover:bg-white/[0.04] cursor-pointer"
                  >
                    <div className="flex items-center gap-2.5 min-w-0 flex-1">
                      {t.status === 'DONE' && <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />}
                      {t.status === 'IN_PROGRESS' && (
                        <div className="h-3.5 w-3.5 shrink-0 rounded-full border-2 border-cyan-400 border-t-transparent animate-spin" />
                      )}
                      {t.status === 'BLOCKED' && <AlertCircle className="h-4 w-4 shrink-0 text-rose-400" />}
                      {t.status !== 'DONE' && t.status !== 'IN_PROGRESS' && t.status !== 'BLOCKED' && (
                        <Circle className="h-3.5 w-3.5 shrink-0 text-gray-600" />
                      )}
                      <span className="font-mono text-[11px] text-gray-400">{t.id}</span>
                      <span className="truncate text-gray-200 group-hover:text-white font-medium">
                        {t.title}
                      </span>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      {t.owner && (
                        <span className="rounded bg-white/5 px-1.5 py-0.5 text-[10px] font-medium text-gray-400">
                          {t.owner}
                        </span>
                      )}
                      <span
                        className={`text-[10px] uppercase font-bold ${
                          t.status === 'DONE'
                            ? 'text-emerald-400'
                            : t.status === 'IN_PROGRESS'
                            ? 'text-cyan-300'
                            : 'text-gray-500'
                        }`}
                      >
                        {t.status}
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Card: Requisitos & Assunções */}
          <div className="rounded-lg border border-white/8 bg-white/[0.02] p-4">
            <div className="flex items-center justify-between pb-3 border-b border-white/6 mb-3">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                <h2 className="text-xs font-semibold uppercase tracking-wider text-gray-200">
                  Requisitos do Utilizador
                </h2>
              </div>
              <span className="text-xs text-gray-400">
                {requirements.filter((r) => r.status === 'VALIDATED').length} de {requirements.length} verificados
              </span>
            </div>

            <div className="space-y-2">
              {requirements.map((req) => (
                <div
                  key={req.id}
                  className="flex items-start gap-2.5 rounded-md border border-white/5 bg-white/[0.015] p-2.5 text-xs"
                >
                  <CheckCircle2
                    className={`mt-0.5 h-3.5 w-3.5 shrink-0 ${
                      req.status === 'VALIDATED' ? 'text-emerald-400' : 'text-gray-500'
                    }`}
                  />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-[11px] font-semibold text-gray-300">{req.id}</span>
                      <span
                        className={`text-[10px] font-bold ${
                          req.status === 'VALIDATED' ? 'text-emerald-400' : 'text-gray-500'
                        }`}
                      >
                        {req.status}
                      </span>
                    </div>
                    <p className="mt-0.5 text-gray-300">{req.desc}</p>
                  </div>
                </div>
              ))}
            </div>

            {/* Collapsible System Assumptions */}
            {assumptions.length > 0 && (
              <div className="mt-3 border-t border-white/6 pt-3">
                <button
                  onClick={() => setShowAssumptions((prev) => !prev)}
                  className="flex w-full items-center justify-between text-xs text-gray-400 hover:text-gray-200 transition-colors"
                >
                  <div className="flex items-center gap-1.5">
                    <Sparkles className="h-3.5 w-3.5 text-purple-300" />
                    <span>Assunções do Sistema ({assumptions.length} ativas)</span>
                  </div>
                  <ChevronDown className={`h-3 w-3 transition-transform ${showAssumptions ? 'rotate-180' : ''}`} />
                </button>

                {showAssumptions && (
                  <div className="mt-2 space-y-1.5 pl-4 border-l border-white/8">
                    {assumptions.map((asm) => (
                      <div key={asm.id} className="text-xs text-gray-400 py-1">
                        <span className="font-mono text-[11px] text-purple-300">{asm.id}:</span>{' '}
                        <span className="text-gray-300">{asm.desc}</span>
                        {asm.rationale && (
                          <span className="block text-[11px] text-gray-500 italic">Razão: {asm.rationale}</span>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* RIGHT COLUMN: AGENTS, ACTIVITY & HEALTH */}
        <div className="space-y-4">
          {/* Card: Agentes Especialistas */}
          <div className="rounded-lg border border-white/8 bg-white/[0.02] p-4">
            <div className="flex items-center justify-between pb-3 border-b border-white/6 mb-3">
              <div className="flex items-center gap-2">
                <Cpu className="h-4 w-4 text-purple-300" />
                <h2 className="text-xs font-semibold uppercase tracking-wider text-gray-200">
                  Agentes Ativos
                </h2>
              </div>
              <button
                onClick={() => onNavigateTab('agents')}
                className="inline-flex items-center gap-1 text-xs text-cyan-300 hover:text-cyan-200 font-medium transition-colors"
              >
                <span>Ver todos ({agents.length})</span>
                <ArrowRight className="h-3 w-3" />
              </button>
            </div>

            <div className="space-y-2">
              {previewAgents.map((ag) => (
                <div
                  key={ag.agent_id}
                  onClick={() => onNavigateTab('agents')}
                  className="group flex items-center justify-between gap-3 rounded-md border border-white/5 bg-white/[0.015] p-2.5 text-xs transition-colors hover:border-white/15 hover:bg-white/[0.04] cursor-pointer"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-white group-hover:text-cyan-200">{ag.name}</span>
                      <span className="rounded bg-white/5 px-1.5 py-0.2 text-[10px] text-gray-400 font-mono">
                        {ag.role}
                      </span>
                    </div>
                    <p className="mt-0.5 text-gray-400 truncate">
                      Tarefa: <span className="text-gray-300">{ag.current_task || 'Aguardando ordens'}</span>
                    </p>
                  </div>

                  <span
                    className={`shrink-0 text-[10px] uppercase font-bold px-2 py-0.5 rounded-full ${
                      ag.status === 'BUSY'
                        ? 'bg-cyan-500/10 text-cyan-300 animate-pulse'
                        : ag.status === 'COMPLETED'
                        ? 'bg-emerald-500/10 text-emerald-300'
                        : 'bg-white/5 text-gray-400'
                    }`}
                  >
                    {ag.status === 'BUSY' ? 'A trabalhar' : ag.status === 'COMPLETED' ? 'Concluído' : 'Disponível'}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Card: Atividade Recente */}
          <div className="rounded-lg border border-white/8 bg-white/[0.02] p-4">
            <div className="flex items-center justify-between pb-3 border-b border-white/6 mb-3">
              <div className="flex items-center gap-2">
                <Activity className="h-4 w-4 text-cyan-300" />
                <h2 className="text-xs font-semibold uppercase tracking-wider text-gray-200">
                  Atividade Recente
                </h2>
              </div>
              <button
                onClick={() => onNavigateTab('activity')}
                className="inline-flex items-center gap-1 text-xs text-cyan-300 hover:text-cyan-200 font-medium transition-colors"
              >
                <span>Ver histórico</span>
                <ArrowRight className="h-3 w-3" />
              </button>
            </div>

            <div className="space-y-2">
              {events.length === 0 ? (
                <div className="py-2 text-xs text-gray-500 text-center">Nenhum evento recente registado.</div>
              ) : (
                events.map((ev, idx) => (
                  <div
                    key={ev.event_id || idx}
                    className="flex items-start gap-3 rounded-md border border-white/5 bg-white/[0.015] p-2 text-xs"
                  >
                    <span className="font-mono text-[11px] text-gray-500 shrink-0 mt-0.5">
                      {new Date(ev.timestamp * 1000).toLocaleTimeString([], {
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-1.5">
                        <span className="font-semibold text-gray-300">{(ev as any).actor || ev.agent || 'Sistema'}</span>
                        <span className="text-gray-600">·</span>
                        <span className="text-gray-400 truncate">{(ev as any).summary || ev.title || ev.type}</span>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Card: Estado Operacional & Confiabilidade */}
          <div className="rounded-lg border border-white/8 bg-white/[0.02] p-4">
            <div className="flex items-center justify-between pb-3 border-b border-white/6 mb-3">
              <div className="flex items-center gap-2">
                <ShieldCheck className="h-4 w-4 text-emerald-400" />
                <h2 className="text-xs font-semibold uppercase tracking-wider text-gray-200">
                  Estado Operacional & Confiabilidade
                </h2>
              </div>
              <button
                onClick={() => onNavigateTab('diagnostics')}
                className="inline-flex items-center gap-1 text-xs text-cyan-300 hover:text-cyan-200 font-medium transition-colors"
              >
                <span>Diagnóstico avançado</span>
                <ArrowRight className="h-3 w-3" />
              </button>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              <div className="rounded border border-white/5 bg-white/[0.015] p-2.5 text-center">
                <span className="text-[10px] text-gray-500 uppercase font-medium">Runtime</span>
                <p className="mt-1 text-xs font-bold text-emerald-400">Saudável</p>
              </div>
              <div className="rounded border border-white/5 bg-white/[0.015] p-2.5 text-center">
                <span className="text-[10px] text-gray-500 uppercase font-medium">Risco Preditivo</span>
                <p className="mt-1 text-xs font-bold text-cyan-300">Baixo</p>
              </div>
              <div className="rounded border border-white/5 bg-white/[0.015] p-2.5 text-center">
                <span className="text-[10px] text-gray-500 uppercase font-medium">Anomalias</span>
                <p className="mt-1 text-xs font-bold text-gray-300">0 detetadas</p>
              </div>
              <div className="rounded border border-white/5 bg-white/[0.015] p-2.5 text-center">
                <span className="text-[10px] text-gray-500 uppercase font-medium">Incidentes</span>
                <p className="mt-1 text-xs font-bold text-emerald-400">0 ativos</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MissionOverviewPanel;
