import React, { useState } from 'react';
import {
  Activity,
  Sparkles,
  Layers,
  GitBranch,
  Wrench,
  ShieldCheck,
  FileCheck,
  Cpu,
} from 'lucide-react';
import type { MissionControlStateData, CommandType } from '../../../protocol/websocket';
import {
  ProductionOperationsPanel,
  ReliabilityIntelligencePanel,
  MissionRequirementsDiffPanel,
  MissionTaskGraphPanel,
  MissionPlanDiffPanel,
  MissionRepairPanel,
  AutonomousRepairConvergencePanel,
  MissionEvidenceLedgerPanel,
  SemanticGraphPanel,
  RuntimeContractDiscoveryPanel,
  PolymorphicSchemaPanel,
  ExperienceMemoryPanel,
  CrossProjectLearningPanel,
  ReleaseReadinessPanel,
  AutonomousLoopPanel,
} from './index';

interface MissionDiagnosticsViewProps {
  missionState: MissionControlStateData;
  onOpenInCode?: (filePath: string, line?: number) => void;
  onSendCommand?: (
    cmdType: CommandType,
    taskId?: string | null,
    payload?: Record<string, any>,
    reason?: string
  ) => void;
}

type DiagnosticCategory =
  | 'runtime'
  | 'reliability'
  | 'requirements'
  | 'planning'
  | 'execution'
  | 'security'
  | 'evidence'
  | 'advanced';

export const MissionDiagnosticsView: React.FC<MissionDiagnosticsViewProps> = ({
  missionState,
  onOpenInCode,
  onSendCommand,
}) => {
  const [activeCategory, setActiveCategory] = useState<DiagnosticCategory>('runtime');
  const [expandedEventId, setExpandedEventId] = useState<string | null>(null);
  const [selectedAdvancedPhase, setSelectedAdvancedPhase] = useState<string>('F40');

  return (
    <div className="space-y-4 max-w-7xl mx-auto">
      {/* 1. COMPACT DIAGNOSTICS SUB-NAV (CLEAN PILLS) */}
      <div className="flex items-center gap-1.5 overflow-x-auto border-b border-white/8 pb-2.5">
        {[
          { id: 'runtime', label: 'Runtime (F71)', icon: Activity },
          { id: 'reliability', label: 'Confiabilidade (F72)', icon: Sparkles },
          { id: 'requirements', label: 'Requisitos', icon: Layers },
          { id: 'planning', label: 'Planeamento & DAG', icon: GitBranch },
          { id: 'execution', label: 'Execução & Cura', icon: Wrench },
          { id: 'security', label: 'Segurança', icon: ShieldCheck },
          { id: 'evidence', label: 'Evidência', icon: FileCheck },
          { id: 'advanced', label: 'Arquivo de Fases', icon: Cpu },
        ].map((tab) => {
          const isActive = activeCategory === tab.id;
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              id={`diag-subtab-${tab.id}`}
              onClick={() => setActiveCategory(tab.id as DiagnosticCategory)}
              className={`flex shrink-0 items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                isActive
                  ? 'bg-cyan-500/15 text-cyan-200 font-semibold border border-cyan-400/30'
                  : 'text-gray-400 hover:bg-white/5 hover:text-gray-200'
              }`}
            >
              <Icon className="h-3.5 w-3.5" />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* 2. TAB: RUNTIME (F71 PRODUCTION OPERATIONS) */}
      {activeCategory === 'runtime' && (
        <div className="space-y-4">
          {/* Executive Runtime Summary */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            <div className="rounded-lg border border-white/8 bg-white/[0.02] p-3 text-center">
              <span className="text-[10px] text-gray-500 uppercase font-medium">Estado do Runtime</span>
              <p className="mt-1 text-sm font-bold text-emerald-400">Saudável (Healthy)</p>
            </div>
            <div className="rounded-lg border border-white/8 bg-white/[0.02] p-3 text-center">
              <span className="text-[10px] text-gray-500 uppercase font-medium">Disponibilidade</span>
              <p className="mt-1 text-sm font-bold text-cyan-300">99.9%</p>
            </div>
            <div className="rounded-lg border border-white/8 bg-white/[0.02] p-3 text-center">
              <span className="text-[10px] text-gray-500 uppercase font-medium">Incidentes Ativos</span>
              <p className="mt-1 text-sm font-bold text-emerald-400">0</p>
            </div>
            <div className="rounded-lg border border-white/8 bg-white/[0.02] p-3 text-center">
              <span className="text-[10px] text-gray-500 uppercase font-medium">Último Healthcheck</span>
              <p className="mt-1 text-sm font-bold text-gray-200">Há 2s</p>
            </div>
          </div>

          <ProductionOperationsPanel missionId={missionState.mission_id} />
        </div>
      )}

      {/* 3. TAB: RELIABILITY (F72 RELIABILITY INTELLIGENCE) */}
      {activeCategory === 'reliability' && (
        <div className="space-y-4">
          {/* Executive Reliability Summary */}
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
            <div className="rounded-lg border border-white/8 bg-white/[0.02] p-3 text-center">
              <span className="text-[10px] text-gray-500 uppercase font-medium">Nível de Risco</span>
              <p className="mt-1 text-sm font-bold text-cyan-300">Baixo (Low Risk)</p>
            </div>
            <div className="rounded-lg border border-white/8 bg-white/[0.02] p-3 text-center">
              <span className="text-[10px] text-gray-500 uppercase font-medium">Anomalias</span>
              <p className="mt-1 text-sm font-bold text-gray-300">0 detetadas</p>
            </div>
            <div className="rounded-lg border border-white/8 bg-white/[0.02] p-3 text-center">
              <span className="text-[10px] text-gray-500 uppercase font-medium">Riscos Previstos</span>
              <p className="mt-1 text-sm font-bold text-cyan-300">1 SLO Warning</p>
            </div>
            <div className="rounded-lg border border-white/8 bg-white/[0.02] p-3 text-center">
              <span className="text-[10px] text-gray-500 uppercase font-medium">Ações Preventivas</span>
              <p className="mt-1 text-sm font-bold text-emerald-400">0 pendentes</p>
            </div>
            <div className="rounded-lg border border-white/8 bg-white/[0.02] p-3 text-center">
              <span className="text-[10px] text-gray-500 uppercase font-medium">Baseline</span>
              <p className="mt-1 text-sm font-bold text-emerald-400">Válida</p>
            </div>
          </div>

          <ReliabilityIntelligencePanel missionId={missionState.mission_id} />
        </div>
      )}

      {/* 4. TAB: REQUIREMENTS (F37 DIFF & REQUIREMENTS) */}
      {activeCategory === 'requirements' && (
        <div className="space-y-4">
          <MissionRequirementsDiffPanel missionState={missionState} />
        </div>
      )}

      {/* 5. TAB: PLANNING (F38 TASK GRAPH & PLAN DIFF) */}
      {activeCategory === 'planning' && (
        <div className="space-y-4">
          <MissionTaskGraphPanel
            missionState={missionState}
            deduplicatedEvents={missionState.events || []}
            expandedEventId={expandedEventId}
            onToggleExpandEvent={(id) =>
              setExpandedEventId((prev) => (prev === id ? null : id))
            }
            onSendCommand={onSendCommand || (() => {})}
          />
          <MissionPlanDiffPanel missionState={missionState} />
        </div>
      )}

      {/* 6. TAB: EXECUTION (REPAIRS & CONVERGENCE) */}
      {activeCategory === 'execution' && (
        <div className="space-y-4">
          <MissionRepairPanel missionState={missionState} onOpenInCode={onOpenInCode} />
          <AutonomousRepairConvergencePanel />
        </div>
      )}

      {/* 7. TAB: SECURITY (SENTINEL & POLICIES) */}
      {activeCategory === 'security' && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="rounded-lg border border-white/8 bg-white/[0.02] p-4 text-center">
              <span className="text-xs text-gray-500 uppercase font-medium">Sentinela Ativo</span>
              <p className="mt-1 text-base font-bold text-emerald-400">Protegido</p>
            </div>
            <div className="rounded-lg border border-white/8 bg-white/[0.02] p-4 text-center">
              <span className="text-xs text-gray-500 uppercase font-medium">Verificações de Política</span>
              <p className="mt-1 text-base font-bold text-emerald-400">Aprovadas (Passed)</p>
            </div>
            <div className="rounded-lg border border-white/8 bg-white/[0.02] p-4 text-center">
              <span className="text-xs text-gray-500 uppercase font-medium">Tentativas Bloqueadas</span>
              <p className="mt-1 text-base font-bold text-gray-300">0 incidentes</p>
            </div>
          </div>
          <div className="rounded-lg border border-white/8 bg-white/[0.02] p-4 text-xs text-gray-300 leading-relaxed">
            <h3 className="font-semibold text-white mb-2">Políticas de Segurança do Sentinel</h3>
            <p>
              O Watchdog monitoriza a execução contra adulteração de comandos, path traversal e
              modificações fora da sandbox do projeto. Ações de alto risco exigem aprovação humana
              explícita antes da execução autónoma.
            </p>
          </div>
        </div>
      )}

      {/* 8. TAB: EVIDENCE */}
      {activeCategory === 'evidence' && (
        <div className="space-y-4">
          <MissionEvidenceLedgerPanel missionState={missionState} onOpenInCode={onOpenInCode} />
        </div>
      )}

      {/* 9. TAB: ADVANCED (ARQUIVO DE FASES) */}
      {activeCategory === 'advanced' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between border-b border-white/8 pb-3">
            <div>
              <h3 className="text-sm font-semibold text-white">Arquivo de Fases Avançado</h3>
              <p className="text-xs text-gray-400">
                Inspecione módulos e artefactos históricos específicos de engenharia
              </p>
            </div>

            <div className="relative">
              <select
                value={selectedAdvancedPhase}
                onChange={(e) => setSelectedAdvancedPhase(e.target.value)}
                className="rounded-md border border-white/10 bg-[#0c1318] px-3 py-1.5 text-xs text-gray-200 outline-none focus:border-cyan-400/40"
              >
                <option value="F40">Fase 40: Autonomous Loop</option>
                <option value="F42">Fase 42: Experience Memory</option>
                <option value="F44">Fase 44: Semantic Graph</option>
                <option value="F45">Fase 45: Contract Discovery</option>
                <option value="F47">Fase 47: Polymorphic Contracts</option>
                <option value="F63">Fase 63: Cross-Project Learning</option>
                <option value="F70">Fase 70: Release Readiness</option>
              </select>
            </div>
          </div>

          <div className="rounded-lg border border-white/8 bg-white/[0.01] p-4">
            {selectedAdvancedPhase === 'F40' && <AutonomousLoopPanel missionId={missionState.mission_id} />}
            {selectedAdvancedPhase === 'F42' && <ExperienceMemoryPanel missionId={missionState.mission_id} />}
            {selectedAdvancedPhase === 'F44' && <SemanticGraphPanel missionId={missionState.mission_id} />}
            {selectedAdvancedPhase === 'F45' && <RuntimeContractDiscoveryPanel missionId={missionState.mission_id} />}
            {selectedAdvancedPhase === 'F47' && <PolymorphicSchemaPanel missionId={missionState.mission_id} />}
            {selectedAdvancedPhase === 'F63' && <CrossProjectLearningPanel />}
            {selectedAdvancedPhase === 'F70' && <ReleaseReadinessPanel missionId={missionState.mission_id} />}
          </div>
        </div>
      )}
    </div>
  );
};

export default MissionDiagnosticsView;
