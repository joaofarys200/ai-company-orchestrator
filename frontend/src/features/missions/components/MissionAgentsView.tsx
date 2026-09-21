import React from 'react';
import {
  Cpu,
  Code,
  ShieldCheck,
  CheckCircle2,
  FileCode,
  Terminal,
  Layers,
} from 'lucide-react';
import type { SwarmAgentDetailData } from '../../../protocol/websocket';

interface MissionAgentsViewProps {
  agents: SwarmAgentDetailData[];
  onOpenInCode?: (filePath: string, line?: number) => void;
}

export const MissionAgentsView: React.FC<MissionAgentsViewProps> = ({
  agents,
  onOpenInCode,
}) => {
  const getAgentRoleIcon = (role: string) => {
    switch (role.toLowerCase()) {
      case 'coder':
      case 'developer':
      case 'programador':
        return <Code className="h-4 w-4 text-cyan-300" />;
      case 'qa':
      case 'tester':
      case 'auditor':
        return <ShieldCheck className="h-4 w-4 text-emerald-300" />;
      case 'planner':
      case 'designer':
      case 'architect':
        return <Layers className="h-4 w-4 text-purple-300" />;
      case 'devops':
      case 'infra':
        return <Terminal className="h-4 w-4 text-amber-300" />;
      default:
        return <Cpu className="h-4 w-4 text-cyan-400" />;
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'BUSY':
        return (
          <span className="inline-flex items-center gap-1 rounded-full border border-cyan-400/30 bg-cyan-400/10 px-2 py-0.5 text-[10px] font-bold text-cyan-300 animate-pulse">
            <span className="h-1.5 w-1.5 rounded-full bg-cyan-400" />
            A trabalhar
          </span>
        );
      case 'COMPLETED':
        return (
          <span className="inline-flex items-center gap-1 rounded-full border border-emerald-400/30 bg-emerald-400/10 px-2 py-0.5 text-[10px] font-bold text-emerald-300">
            <CheckCircle2 className="h-3 w-3" />
            Concluído
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] font-medium text-gray-400">
            Disponível
          </span>
        );
    }
  };

  return (
    <div className="space-y-4 max-w-7xl mx-auto">
      {/* HEADER BAR */}
      <div className="flex items-center justify-between border-b border-white/8 pb-3">
        <div>
          <h2 className="text-sm font-semibold text-white">Agentes Especialistas</h2>
          <p className="text-xs text-gray-400">
            Enxame autónomo federado colaborando na execução das tarefas
          </p>
        </div>
        <span className="text-xs font-mono text-gray-400">
          {agents.filter((a) => a.status === 'BUSY').length} de {agents.length} em execução
        </span>
      </div>

      {/* AGENT CARDS GRID */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {agents.map((ag) => (
          <div
            key={ag.agent_id}
            className="rounded-lg border border-white/8 bg-white/[0.02] p-4 transition-colors hover:border-white/15 hover:bg-white/[0.035]"
          >
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-center gap-2.5">
                <div className="flex h-8 w-8 items-center justify-center rounded-md border border-white/10 bg-white/[0.04]">
                  {getAgentRoleIcon(ag.role)}
                </div>
                <div>
                  <h3 className="text-xs font-semibold text-white">{ag.name}</h3>
                  <span className="text-[11px] text-gray-400 font-medium">{ag.role}</span>
                </div>
              </div>
              {getStatusBadge(ag.status)}
            </div>

            {/* Current Task */}
            <div className="mt-3 rounded border border-white/5 bg-black/20 p-2.5 text-xs">
              <span className="text-[10px] text-gray-500 uppercase font-semibold">Tarefa atual</span>
              <p className="mt-0.5 text-gray-200 font-medium truncate">
                {ag.current_task || 'Sem tarefa em execução'}
              </p>
            </div>

            {/* Compact Metrics */}
            <div className="mt-3 flex items-center justify-between border-t border-white/5 pt-2 text-[11px] text-gray-400">
              <span>
                Tarefas: <strong className="text-gray-200">{ag.completed_tasks_count}</strong>
              </span>
              <span>
                Falhas:{' '}
                <strong className={ag.failures_count > 0 ? 'text-amber-300' : 'text-gray-500'}>
                  {ag.failures_count}
                </strong>
              </span>
              <span>
                Handoffs: <strong className="text-purple-300">{ag.handoffs_count}</strong>
              </span>
            </div>

            {/* Touched Files */}
            {(ag.files_touched || []).length > 0 && (
              <div className="mt-2.5 flex flex-wrap gap-1">
                {(ag.files_touched as string[] || []).map((f: string) => (
                  <button
                    key={f}
                    onClick={() => onOpenInCode && onOpenInCode(f)}
                    className="inline-flex items-center gap-1 rounded border border-white/6 bg-white/[0.02] px-1.5 py-0.5 font-mono text-[10px] text-cyan-300 hover:bg-cyan-500/10 hover:border-cyan-400/30 transition-colors"
                  >
                    <FileCode className="h-3 w-3 text-gray-500" />
                    <span>{f}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

export default MissionAgentsView;
