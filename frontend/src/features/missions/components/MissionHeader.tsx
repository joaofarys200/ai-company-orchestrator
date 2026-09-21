import React, { useState } from 'react';
import {
  CheckCircle2,
  ShieldAlert,
  Wrench,
  Pause,
  XCircle,
  X,
  ChevronDown,
  Sparkles,
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
  onBackToList?: () => void;
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
  onBackToList,
  children,
}) => {
  const [scenarioMenuOpen, setScenarioMenuOpen] = useState(false);

  const getStatusBadge = (status: MissionControlStatus) => {
    switch (status) {
      case 'RUNNING':
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-cyan-400/25 bg-cyan-400/10 px-2.5 py-0.5 text-xs font-medium text-cyan-200">
            <span className="h-1.5 w-1.5 rounded-full bg-cyan-400 animate-pulse" />
            Em execução
          </span>
        );
      case 'PLANNING':
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-purple-400/25 bg-purple-400/10 px-2.5 py-0.5 text-xs font-medium text-purple-200">
            <span className="h-1.5 w-1.5 rounded-full bg-purple-400" />
            A planear
          </span>
        );
      case 'COMPLETED':
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-400/25 bg-emerald-400/10 px-2.5 py-0.5 text-xs font-medium text-emerald-200">
            <CheckCircle2 className="h-3 w-3 text-emerald-400" />
            Concluída
          </span>
        );
      case 'BLOCKED':
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-rose-400/25 bg-rose-400/10 px-2.5 py-0.5 text-xs font-medium text-rose-200">
            <ShieldAlert className="h-3 w-3 text-rose-400" />
            Bloqueada
          </span>
        );
      case 'REPAIRING':
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-400/25 bg-amber-400/10 px-2.5 py-0.5 text-xs font-medium text-amber-200">
            <Wrench className="h-3 w-3 text-amber-400 animate-spin" />
            Auto-cura
          </span>
        );
      case 'PAUSED':
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-400/25 bg-amber-400/10 px-2.5 py-0.5 text-xs font-medium text-amber-200">
            <Pause className="h-3 w-3 text-amber-400" />
            Pausada
          </span>
        );
      case 'CANCELLED':
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-gray-500/25 bg-gray-500/10 px-2.5 py-0.5 text-xs font-medium text-gray-300">
            <XCircle className="h-3 w-3 text-gray-400" />
            Cancelada
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-gray-500/25 bg-gray-500/10 px-2.5 py-0.5 text-xs font-medium text-gray-400">
            {status}
          </span>
        );
    }
  };

  const currentScenario = scenarios.find((s) => s.key === selectedScenario);

  return (
    <div className="border-b border-white/8 bg-[#091217]/95 px-6 py-4">
      {/* 1. TOP UTILITY ROW: BREADCRUMB & DEMO SCENARIO SELECTOR */}
      <div className="mb-2.5 flex items-center justify-between gap-3 text-xs text-gray-400">
        <div className="flex items-center gap-2">
          {onBackToList && (
            <button
              type="button"
              onClick={onBackToList}
              className="mr-1 inline-flex items-center gap-1 rounded border border-white/10 bg-white/[0.04] px-2 py-0.5 text-xs font-medium text-cyan-300 transition hover:bg-cyan-500/10 hover:border-cyan-500/30"
              title="Voltar à lista de missões"
            >
              ← Missões
            </button>
          )}
          <span className="font-semibold text-gray-400">Projeto:</span>
          <span className="rounded bg-white/[0.06] px-1.5 py-0.5 font-medium text-cyan-300 border border-white/5">
            {missionState.project_name || missionState.project_id || 'task-app'}
          </span>
          <span className="text-gray-600">/</span>
          <span className="font-medium text-white">
            {missionState.interpreted_goal || missionState.mission_id}
          </span>
          <span className="text-gray-600">·</span>
          <span className="font-mono text-[10px] text-gray-500">{missionState.mission_id}</span>
        </div>

        {/* Subtle Demo Scenario Picker */}
        <div className="relative flex items-center gap-2">
          <span className="inline-flex items-center gap-1 rounded bg-white/[0.04] px-1.5 py-0.5 text-[11px] font-medium text-gray-400 border border-white/5">
            <Sparkles className="h-3 w-3 text-cyan-300" />
            <span>Simulador de Cenários:</span>
          </span>

          <div className="relative">
            <button
              onClick={() => setScenarioMenuOpen((prev) => !prev)}
              className="inline-flex items-center gap-1.5 rounded-md border border-white/10 bg-white/[0.03] px-2 py-1 text-xs font-medium text-gray-300 transition-colors hover:border-white/20 hover:text-white"
            >
              <span>{currentScenario?.label.split(':')[0] || 'Cenário'}</span>
              <ChevronDown className={`h-3 w-3 text-gray-400 transition-transform ${scenarioMenuOpen ? 'rotate-180' : ''}`} />
            </button>

            {scenarioMenuOpen && (
              <>
                <button
                  type="button"
                  aria-label="Fechar menu"
                  onClick={() => setScenarioMenuOpen(false)}
                  className="fixed inset-0 z-30 cursor-default"
                />
                <div className="absolute right-0 top-8 z-40 w-64 rounded-md border border-white/10 bg-[#0c1318] p-1.5 shadow-2xl space-y-0.5">
                  <div className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-gray-500 border-b border-white/5 mb-1">
                    Selecionar Modo Autónomo
                  </div>
                  {scenarios.map((sc) => {
                    const isSelected = selectedScenario === sc.key;
                    return (
                      <button
                        key={sc.key}
                        onClick={() => {
                          onSelectScenario(sc.key);
                          setScenarioMenuOpen(false);
                        }}
                        className={`w-full rounded px-2.5 py-1.5 text-left text-xs transition-colors flex items-center justify-between ${
                          isSelected
                            ? 'bg-cyan-500/15 text-cyan-200 font-semibold'
                            : 'text-gray-300 hover:bg-white/[0.06] hover:text-white'
                        }`}
                      >
                        <span className="truncate">{sc.label.split(':')[0]}</span>
                        <span className="text-[10px] text-gray-500 uppercase shrink-0">{sc.badge}</span>
                      </button>
                    );
                  })}
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {/* 2. MAIN HEADER CONSOLE: TITLE, STATUS & ACTION BUTTONS */}
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-2.5">
            <h1 className="text-lg font-semibold tracking-tight text-white">
              {missionState.interpreted_goal || 'Missão Autónoma'}
            </h1>
            {getStatusBadge(missionState.status)}
            <span className="text-xs text-gray-500">·</span>
            <span className="text-xs text-gray-400">
              Fase: <span className="font-medium text-gray-200">{missionState.current_stage}</span>
            </span>
            <span className="text-xs text-gray-500">·</span>
            <span className="font-mono text-xs font-semibold text-cyan-300">
              {missionState.progress_percentage}%
            </span>
          </div>

          <p className="text-xs text-gray-400 line-clamp-1 max-w-3xl">
            &quot;{missionState.user_goal}&quot;
          </p>
        </div>

        {/* 3. ACTIONS & QUICK ARCHITECTURE LINK */}
        <div className="flex items-center gap-2">
          {children}

          {onOpenArchitecture && (
            <button
              onClick={onOpenArchitecture}
              className="inline-flex items-center gap-1.5 rounded-md border border-white/10 bg-white/[0.04] px-2.5 py-1.5 text-xs font-medium text-gray-300 transition-colors hover:bg-white/[0.08] hover:text-white"
              title="Abrir vista de arquitetura do projeto e AST"
            >
              <Network className="h-3.5 w-3.5 text-cyan-300" />
              <span className="hidden sm:inline">Arquitetura</span>
            </button>
          )}
        </div>
      </div>

      {/* 4. FEEDBACK BANNER ON COMMAND OUTCOME */}
      {lastCommandFeedback && (
        <div
          id="command-feedback-banner"
          className={`mt-3 flex items-center justify-between rounded-md border px-3 py-2 text-xs font-medium ${
            lastCommandFeedback.status === 'ACCEPTED'
              ? 'border-emerald-400/25 bg-emerald-400/10 text-emerald-200'
              : lastCommandFeedback.status === 'SECURITY_BLOCK'
              ? 'border-rose-400/25 bg-rose-400/10 text-rose-200'
              : 'border-amber-400/25 bg-amber-400/10 text-amber-200'
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
            className="rounded p-1 text-gray-400 transition-colors hover:text-white"
            title="Fechar notificação"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}
    </div>
  );
};

export default MissionHeader;
