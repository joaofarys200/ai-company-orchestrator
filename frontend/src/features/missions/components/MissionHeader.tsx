import React from 'react';
import {
  Sparkles,
  CheckCircle2,
  ShieldAlert,
  Wrench,
  Pause,
  XCircle,
  X,
  UserCheck,
  Network,
} from 'lucide-react';
import type { MissionControlStateData, MissionControlStatus } from '../../../protocol/websocket';

export interface ScenarioDef {
  key: string;
  label: string;
  badge: string;
  desc: string;
}

interface MissionHeaderProps {
  scenarios: ScenarioDef[];
  selectedScenario: string;
  onSelectScenario: (key: any) => void;
  missionState: MissionControlStateData;
  lastCommandFeedback: { status: string; reason: string; timestamp: number } | null;
  onDismissFeedback: () => void;
  onOpenArchitecture?: () => void;
  children?: React.ReactNode;
}

export const MissionHeader: React.FC<MissionHeaderProps> = ({
  scenarios,
  selectedScenario,
  onSelectScenario,
  missionState,
  lastCommandFeedback,
  onDismissFeedback,
  onOpenArchitecture,
  children,
}) => {
  const getStatusBadgeStyle = (status: MissionControlStatus) => {
    switch (status) {
      case 'RUNNING':
        return 'border-cyan-500/40 bg-cyan-500/20 text-cyan-300 animate-pulse';
      case 'PLANNING':
        return 'border-purple-500/40 bg-purple-500/20 text-purple-300';
      case 'COMPLETED':
        return 'border-emerald-500/40 bg-emerald-500/20 text-emerald-300';
      case 'BLOCKED':
        return 'border-rose-500/40 bg-rose-500/20 text-rose-300';
      case 'REPAIRING':
        return 'border-amber-500/40 bg-amber-500/20 text-amber-300';
      case 'PAUSED':
        return 'border-amber-500/50 bg-amber-500/20 text-amber-200';
      case 'CANCELLED':
        return 'border-gray-500/40 bg-gray-500/20 text-gray-300';
      case 'FAILED':
        return 'border-red-500/40 bg-red-500/20 text-red-300';
      default:
        return 'border-gray-500/40 bg-gray-500/10 text-gray-300';
    }
  };

  return (
    <>
      {/* 1. SCENARIO SELECTOR BAR */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#a1bebf]/15 bg-[#0f1b20]/90 px-6 py-2.5">
        <div className="flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-cyan-300" />
          <span className="text-xs font-bold uppercase tracking-wider text-gray-300">
            Cenários de Execução Autónoma:
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          {scenarios.map((sc) => {
            const isSelected = selectedScenario === sc.key;
            return (
              <button
                key={sc.key}
                id={`scenario-btn-${sc.key.toLowerCase()}`}
                onClick={() => onSelectScenario(sc.key)}
                className={`flex items-center gap-2 rounded-md px-3 py-1.5 text-xs font-medium transition-all ${
                  isSelected
                    ? 'border border-cyan-400/40 bg-cyan-500/20 text-cyan-100 shadow-[0_0_15px_rgba(6,182,212,0.2)]'
                    : 'border border-white/8 bg-white/[0.03] text-gray-400 hover:border-white/20 hover:bg-white/[0.06] hover:text-gray-200'
                }`}
                title={sc.desc}
              >
                <span>{sc.label.split(':')[0]}</span>
                <span className={`text-[10px] uppercase ${isSelected ? 'text-cyan-300' : 'text-gray-500'}`}>
                  {sc.badge}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* 2. MISSION HEADER CONSOLE WITH CONTROLS AND METRICS */}
      <div className="border-b border-[#a1bebf]/15 bg-gradient-to-r from-[#0c1619] via-[#0f1c21] to-[#0c1619] px-6 py-4 shadow-lg">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="space-y-1">
            <div className="flex items-center gap-3">
              <span className="font-mono text-xs font-semibold text-cyan-300">
                {missionState.mission_id}
              </span>
              <span
                id="mission-status-badge"
                className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-bold tracking-wide ${getStatusBadgeStyle(
                  missionState.status
                )}`}
              >
                {missionState.status === 'COMPLETED' && <CheckCircle2 className="h-3 w-3" />}
                {missionState.status === 'BLOCKED' && <ShieldAlert className="h-3 w-3" />}
                {missionState.status === 'REPAIRING' && <Wrench className="h-3 w-3" />}
                {missionState.status === 'PAUSED' && <Pause className="h-3 w-3 text-amber-300" />}
                {missionState.status === 'CANCELLED' && <XCircle className="h-3 w-3 text-red-300" />}
                {missionState.status}
              </span>
              <span className="rounded-md border border-white/10 bg-white/5 px-2 py-0.5 text-[11px] font-medium text-gray-300">
                Fase: <strong className="text-white">{missionState.current_stage}</strong>
              </span>
              <span
                id="mission-version-badge"
                className="rounded-md border border-cyan-500/30 bg-cyan-950/40 px-2 py-0.5 font-mono text-[11px] font-bold text-cyan-300"
                title="Versão sequencial da missão"
              >
                v{missionState.mission_version || 1}
              </span>
              <span
                id="mission-intent-version-badge"
                className="rounded-md border border-purple-500/30 bg-purple-950/40 px-2 py-0.5 font-mono text-[11px] font-bold text-purple-300"
                title="Versão de Intenção Semântica (Fase 37)"
              >
                INTENT v{missionState.intent_version || 1}
              </span>
              <span
                id="mission-plan-version-badge"
                className="rounded-md border border-emerald-500/30 bg-emerald-950/40 px-2 py-0.5 font-mono text-[11px] font-bold text-emerald-300"
                title="Versão do Plano DAG (Fase 37)"
              >
                PLAN v{missionState.plan_version || 1}
              </span>
            </div>
            <h1 className="text-xl font-bold tracking-tight text-white">
              {missionState.interpreted_goal}
            </h1>
          </div>

          {/* Operational Intervention Buttons & Metrics */}
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            {children}

            {/* Metrics summary cards */}
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:gap-3">
              <div className="rounded-lg border border-white/8 bg-black/30 p-2.5 text-center">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-gray-400">Tempo Total</span>
                <p className="mt-0.5 font-mono text-sm font-bold text-cyan-200">
                  {missionState.total_duration_seconds}s
                </p>
              </div>
              <div className="rounded-lg border border-white/8 bg-black/30 p-2.5 text-center">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-gray-400">Progresso</span>
                <p className="mt-0.5 font-mono text-sm font-bold text-emerald-300">
                  {missionState.progress_percentage}%
                </p>
              </div>
              <div className="rounded-lg border border-white/8 bg-black/30 p-2.5 text-center">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-gray-400">Agentes Ativos</span>
                <p className="mt-0.5 font-mono text-sm font-bold text-purple-300">
                  {missionState.active_agents_count} de 6
                </p>
              </div>
              <div className="rounded-lg border border-white/8 bg-black/30 p-2.5 text-center">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-gray-400">Requisitos</span>
                <p className="mt-0.5 font-mono text-sm font-bold text-amber-300">
                  {missionState.requirements_validated_count} / {missionState.requirements_count}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* FEEDBACK BANNER ON COMMAND OUTCOME */}
        {lastCommandFeedback && (
          <div
            id="command-feedback-banner"
            className={`mt-3 flex items-center justify-between rounded-lg border p-3 text-xs font-medium ${
              lastCommandFeedback.status === 'ACCEPTED'
                ? 'border-emerald-500/30 bg-emerald-950/40 text-emerald-200'
                : lastCommandFeedback.status === 'SECURITY_BLOCK'
                ? 'border-rose-500/40 bg-rose-950/50 text-rose-200'
                : lastCommandFeedback.status === 'STALE'
                ? 'border-amber-500/40 bg-amber-950/50 text-amber-200'
                : 'border-blue-500/30 bg-blue-950/40 text-blue-200'
            }`}
          >
            <div className="flex items-center gap-2">
              <span className="font-mono font-bold uppercase tracking-wider">
                [{lastCommandFeedback.status}]
              </span>
              <span>{lastCommandFeedback.reason}</span>
            </div>
            <button
              id="btn-dismiss-feedback"
              onClick={onDismissFeedback}
              className="rounded p-1 text-gray-400 hover:text-white hover:bg-white/10"
              title="Fechar notificação"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        )}

        {/* 3. IMMUTABLE USER GOAL BANNER */}
        <div className="mt-3 flex items-start gap-3 rounded-md border border-cyan-500/20 bg-cyan-950/20 p-3 text-xs">
          <div className="rounded bg-cyan-500/20 p-1 text-cyan-300">
            <UserCheck className="h-4 w-4" />
          </div>
          <div className="min-w-0 flex-1">
            <span className="font-bold uppercase tracking-wider text-cyan-300">
              Objetivo Original do Utilizador (Imutável):
            </span>
            <p className="mt-0.5 text-sm font-medium text-gray-200">
              &quot;{missionState.user_goal}&quot;
            </p>
          </div>
          {onOpenArchitecture && (
            <button
              onClick={onOpenArchitecture}
              className="inline-flex items-center gap-1.5 rounded border border-cyan-400/30 bg-cyan-500/10 px-2.5 py-1 text-xs font-semibold text-cyan-200 hover:bg-cyan-500/20"
            >
              <Network className="h-3.5 w-3.5" />
              <span>Ver Arquitetura & AST</span>
            </button>
          )}
        </div>
      </div>
    </>
  );
};
