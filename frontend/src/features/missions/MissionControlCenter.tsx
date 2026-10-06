import React, { useState, useMemo, useEffect } from 'react';
import {
  LayoutDashboard,
  Layers,
  Cpu,
  Activity,
  Sparkles,
  Lock,
} from 'lucide-react';
import { usePermissionStore } from '../permissions/PermissionStore';
import type {
  MissionControlStateData,
  MissionControlEventData,
  CommandType,
} from '../../protocol/websocket';
import { useWebSocket } from '../../context/WebSocketContext';
import {
  MissionHeader,
  MissionControlActions,
  CancelConfirmModal,
  IntentPreviewModal,
  MissionOverviewPanel,
  MissionTasksView,
  MissionAgentsView,
  MissionActivityView,
  MissionDiagnosticsView,
} from './components';

export interface MissionControlCenterProps {
  onOpenInCode?: (filePath: string, line?: number) => void;
  onOpenArchitecture?: () => void;
  onBackToList?: () => void;
  activeMissionId?: string | null;
}

export type ScenarioKey = 'INTERACTIVE' | 'NORMAL' | 'REPAIR' | 'REPLAN' | 'RECOVERY' | 'BLOCKED';

export const SCENARIOS: Array<{ key: ScenarioKey; label: string; badge: string; desc: string }> = [
  {
    key: 'INTERACTIVE',
    label: 'Interativo: Controlo Bidirecional',
    badge: 'Human-in-the-Loop',
    desc: 'Missão ativa com comandos humanos de Pausa, Retoma, Cancelamento, Aprovação, Prioridade e Reordenação.',
  },
  {
    key: 'NORMAL',
    label: 'Normal: Gestor de Despesas Web',
    badge: '100% Autônomo',
    desc: 'Missão completa do início ao fim com síntese de código, testes unitários e validação no browser.',
  },
  {
    key: 'REPAIR',
    label: 'Auto-Cura: Falha e Reparação AST',
    badge: 'Self-Healing',
    desc: 'Diagnóstico de erro de ordenação nula, aplicação de patch cirúrgico e re-validação determinística.',
  },
  {
    key: 'REPLAN',
    label: 'Re-planeamento: Adaptação de SubDAG',
    badge: 'Dynamic Adaptation',
    desc: 'Deteção de novos requisitos em runtime e expansão topológica do plano sem reiniciar a execução.',
  },
  {
    key: 'RECOVERY',
    label: 'Recuperação: Crash & Checkpoint',
    badge: 'Durable Recovery',
    desc: 'Interrupção abrupta do worker, deteção de checkpoint incremental e retoma com zero duplicação.',
  },
  {
    key: 'BLOCKED',
    label: 'Bloqueio: Sentinel Policy Gate',
    badge: 'Refusal Gate',
    desc: 'Bloqueio preventivo de instruções destrutivas ou violação de políticas de isolamento.',
  },
];

// Fallback mock states for offline/immediate rendering matching the Python engine contracts exactly
const FALLBACK_INTERACTIVE_STATE: MissionControlStateData = {
  mission_id: 'm_p36_interactive',
  user_goal: 'Executa a missão de despesas com controlo bidirecional do operador ativado.',
  interpreted_goal: 'Gestor de Despesas & Controlo Humano',
  status: 'RUNNING',
  current_stage: 'EXECUTION',
  elapsed_time_seconds: 0.085,
  progress_percentage: 40,
  eta_seconds: 0.15,
  active_agents_count: 2,
  requirements_count: 4,
  requirements_validated_count: 1,
  time_to_first_output_seconds: 0.040,
  time_to_first_validated_seconds: 0.000,
  time_to_useful_result_seconds: 0.000,
  total_duration_seconds: 0.085,
  user_effort_score: 0.0,
  output_quality_score: 0.950,
  execution_success: false,
  requirement_satisfaction: false,
  validation_evidence: false,
  is_user_useful: true,
  unknowns: [],
  final_result: {},
  mission_version: 1,
  intent_version: 1,
  plan_version: 1,
  requirements: [
    { id: 'REQ_01', desc: 'Registo e categorização de despesas (Alimentação, Transporte, Lazer)', source: 'USER_REQUIREMENT', status: 'VALIDATED', verification_status: 'VERIFIED' },
    { id: 'REQ_02', desc: 'Cálculo dinâmico de total acumulado e contagem de itens em tempo real', source: 'USER_REQUIREMENT', status: 'IDENTIFIED', verification_status: 'INFERRED' },
    { id: 'REQ_03', desc: 'Pesquisa reativa e filtragem instantânea por categoria', source: 'USER_REQUIREMENT', status: 'IDENTIFIED', verification_status: 'INFERRED' },
    { id: 'REQ_04', desc: 'Persistência duradoura e resiliente no localStorage do navegador', source: 'USER_REQUIREMENT', status: 'IDENTIFIED', verification_status: 'INFERRED' },
  ],
  assumptions: [
    {
      id: 'ASM_01',
      desc: 'Aplicação Web de página única (SPA) estritamente Vanilla TypeScript & CSS responsivo',
      source: 'SYSTEM_ASSUMPTION',
      status: 'INFERRED',
      verification_status: 'INFERRED',
      rationale: 'Garante arranque em < 15ms sem dependências externas (Confiança 95%)',
    },
    {
      id: 'ASM_02',
      desc: 'Armazenamento direto via API nativa do Web Storage (localStorage)',
      source: 'SYSTEM_ASSUMPTION',
      status: 'INFERRED',
      verification_status: 'INFERRED',
      rationale: 'Elimina necessidade de backend remoto para execução offline (Confiança 90%)',
    },
  ],
  tasks: [
    {
      id: 'TSK_01',
      title: 'Configurar esqueleto Vanilla TypeScript e estrutura SPA',
      status: 'DONE',
      owner: 'dev_lead',
      priority: 'HIGH',
      dependencies: [],
      evidence: 'Ficheiros src/index.html e src/main.ts criados com compilação sem erros',
      duration_seconds: 42,
    },
    {
      id: 'TSK_02',
      title: 'Implementar modelo de dados de despesa e persistência localStorage',
      status: 'IN_PROGRESS',
      owner: 'coder',
      priority: 'HIGH',
      dependencies: ['TSK_01'],
      evidence: 'Implementação de ExpenseManager com métodos add, list, delete em curso',
      duration_seconds: 18,
    },
    {
      id: 'TSK_03',
      title: 'Construir interface responsiva e formulário de adição',
      status: 'PENDING',
      owner: 'coder',
      priority: 'MEDIUM',
      dependencies: ['TSK_02'],
      evidence: '',
      duration_seconds: 0,
    },
    {
      id: 'TSK_04',
      title: 'Auditoria de segurança de input e sanitização contra XSS',
      status: 'PENDING',
      owner: 'auditor',
      priority: 'HIGH',
      dependencies: ['TSK_03'],
      evidence: '',
      duration_seconds: 0,
    },
  ],
  agents: [
    {
      agent_id: 'ag_dev_lead',
      name: 'Clara // Arquitetura & Decomposição',
      role: 'Planner',
      status: 'COMPLETED',
      current_task: 'Decomposição de DAG concluída',
      completed_tasks_count: 1,
      failures_count: 0,
      handoffs_count: 1,
      files_touched: ['index.html'],
    },
    {
      agent_id: 'ag_coder',
      name: 'Devon // Engenharia & Síntese de Código',
      role: 'Coder',
      status: 'BUSY',
      current_task: 'A implementar ExpenseManager no app.js',
      completed_tasks_count: 0,
      failures_count: 0,
      handoffs_count: 0,
      files_touched: ['app.js', 'styles.css'],
    },
    {
      agent_id: 'ag_tester',
      name: 'Quinn // Qualidade, Validação & Browser QA',
      role: 'QA',
      status: 'IDLE',
      current_task: 'A aguardar conclusão da implementação',
      completed_tasks_count: 0,
      failures_count: 0,
      handoffs_count: 0,
      files_touched: [],
    },
  ],
  events: [
    {
      event_id: 'ev_01',
      mission_id: 'm-exp-01',
      timestamp: Date.now() / 1000 - 45,
      type: 'STAGE_STARTED',
      stage: 'PLANNING',
      title: 'Início do planeamento autónomo da missão',
      agent: 'Sistema',
    },
    {
      event_id: 'ev_02',
      mission_id: 'm-exp-01',
      timestamp: Date.now() / 1000 - 30,
      type: 'TASK_COMPLETED',
      stage: 'EXECUTION',
      title: 'Plano aprovado e grafo de tarefas validado (TSK_01 concluída)',
      agent: 'Clara',
    },
    {
      event_id: 'ev_03',
      mission_id: 'm-exp-01',
      timestamp: Date.now() / 1000 - 15,
      type: 'TASK_STARTED',
      stage: 'EXECUTION',
      title: 'Síntese de código iniciada para TSK_02 (ExpenseManager)',
      agent: 'Devon',
    },
    {
      event_id: 'ev_04',
      mission_id: 'm-exp-01',
      timestamp: Date.now() / 1000 - 2,
      type: 'SUPERVISION',
      stage: 'EXECUTION',
      title: 'Sessão supervisionada bidirecionalmente ativa',
      agent: 'Operador',
    },
  ],
  why_items: [],
  repairs: [],
  replans: [],
  recoveries: [],
  evidence: [],
  artifacts: [],
};

export type MissionPrimarySection = 'overview' | 'tasks' | 'agents' | 'activity' | 'diagnostics';

export const MissionControlCenter: React.FC<MissionControlCenterProps> = ({
  onOpenInCode,
  onOpenArchitecture,
  onBackToList,
  activeMissionId,
}) => {
  const {
    missionControlState,
    missionControlCommandResult,
    missionIntentPreviewResult,
    missionIntentResult,
    clearMissionControlCommandResult,
    sendMissionControlCommand,
    sendMissionIntentPreview,
    sendMissionIntentChange,
  } = useWebSocket();

  const [selectedScenario, setSelectedScenario] = useState<ScenarioKey>('INTERACTIVE');
  const [missionState, setMissionState] = useState<MissionControlStateData>(FALLBACK_INTERACTIVE_STATE);
  const [activeViewSection, setActiveViewSection] = useState<MissionPrimarySection>('overview');

  useEffect(() => {
    if (activeMissionId) {
      setMissionState((prev) => ({
        ...prev,
        mission_id: activeMissionId,
      }));
    }
  }, [activeMissionId]);

  // Interactive Control UI state
  const [showCancelModal, setShowCancelModal] = useState(false);
  const [cancelReason, setCancelReason] = useState('');
  const [lastCommandFeedback, setLastCommandFeedback] = useState<{
    status: string;
    reason: string;
    timestamp: number;
  } | null>(null);
  const [isSubmittingCommand, setIsSubmittingCommand] = useState(false);

  // Intent Editing & Preview state
  const [showIntentModal, setShowIntentModal] = useState(false);
  const [intentInputText, setIntentInputText] = useState('');
  const [currentIntentPreview, setCurrentIntentPreview] = useState<any | null>(null);
  const [isAnalyzingIntent, setIsAnalyzingIntent] = useState(false);
  const [isApplyingIntent, setIsApplyingIntent] = useState(false);

  // Sync real-time state from WebSocket if live
  useEffect(() => {
    if (missionControlState) {
      const liveState = (missionControlState as any).data || missionControlState;
      setMissionState((prev) => ({
        ...prev,
        ...liveState,
        requirements: liveState.requirements || prev.requirements || [],
        assumptions: liveState.assumptions || prev.assumptions || [],
        tasks: liveState.tasks || prev.tasks || [],
        agents: liveState.agents || prev.agents || [],
        why_items: liveState.why_items || prev.why_items || [],
        repairs: liveState.repairs || prev.repairs || [],
        replans: liveState.replans || prev.replans || [],
        recoveries: liveState.recoveries || prev.recoveries || [],
        evidence: liveState.evidence || prev.evidence || [],
        events: liveState.events || prev.events || [],
        artifacts: liveState.artifacts || prev.artifacts || [],
      }));
    }
  }, [missionControlState]);

  // Sync command feedback when received from server
  useEffect(() => {
    if (missionControlCommandResult) {
      setIsSubmittingCommand(false);
      setLastCommandFeedback({
        status: missionControlCommandResult.status,
        reason: missionControlCommandResult.reason,
        timestamp: Date.now(),
      });
    }
  }, [missionControlCommandResult]);

  // Sync intent preview response from WebSocket
  useEffect(() => {
    if (missionIntentPreviewResult) {
      setIsAnalyzingIntent(false);
      const res = missionIntentPreviewResult as any;
      const rawImpact = res.impact !== undefined ? res.impact : (res.data?.impact || 'LOCAL');
      const normalizedImpact =
        typeof rawImpact === 'object' && rawImpact !== null
          ? rawImpact.level || 'LOCAL'
          : String(rawImpact || 'LOCAL');

      setCurrentIntentPreview({
        resolved: res.success ?? true,
        operation: res.data?.operation || 'ADD_REQUIREMENT',
        target: res.data?.target || 'REQ_NEW',
        payload: res.data?.payload || {},
        impact: normalizedImpact,
        requires_pause:
          res.data?.requires_pause !== undefined ? res.data.requires_pause : normalizedImpact === 'STRUCTURAL',
        tasks_affected: res.data?.affected_tasks || ['TSK_02', 'TSK_03'],
        evidence_affected: res.data?.affected_evidence || ['EVD_01'],
        approval_status: res.data?.approval_status || 'CONFIRM_REQUIRED',
        conflicts: res.conflicts || res.data?.conflicts || [],
        confidence: 0.98,
        base_intent_version: res.data?.base_intent_version || missionState.intent_version || 1,
        suggested_replan: res.data?.suggested_replan || 'Adicionar tarefas de compensação no DAG',
      });
    }
  }, [missionIntentPreviewResult, missionState.intent_version]);

  // Sync applied intent change result
  useEffect(() => {
    if (missionIntentResult) {
      setIsApplyingIntent(false);
      setShowIntentModal(false);
      setCurrentIntentPreview(null);
      const res = missionIntentResult as any;
      if (res) {
        const liveData = res.data || res;
        const newIntentVer =
          res.intent_version || liveData.intent_version || (missionState.intent_version || 1) + 1;
        const newPlanVer =
          res.plan_version || liveData.plan_version || (missionState.plan_version || 1) + 1;
        setMissionState((prev) => ({
          ...prev,
          ...(typeof liveData === 'object' ? liveData : {}),
          status: (liveData.mission_status as any) || (liveData.status as any) || prev.status,
          intent_version: newIntentVer,
          plan_version: newPlanVer,
        }));
      }
    }
  }, [missionIntentResult]);

  const loadScenarioState = (key: ScenarioKey) => {
    setSelectedScenario(key);
    setMissionState(FALLBACK_INTERACTIVE_STATE);
  };

  const handleSendCommand = (
    cmdType: CommandType,
    taskId?: string | null,
    payload: Record<string, any> = {},
    reason?: string
  ) => {
    setIsSubmittingCommand(true);
    setTimeout(() => {
      setIsSubmittingCommand(false);
    }, 300);
    const commandPayload = {
      command_id: `cmd_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
      command_type: cmdType,
      mission_id: missionState.mission_id,
      target_task_id: taskId || undefined,
      user_id: 'operador_humano',
      expected_mission_version: missionState.mission_version || 1,
      payload,
      reason: reason || `Comando ${cmdType} executado pelo utilizador`,
      idempotency_key: `idemp_${Date.now()}`,
    };

    sendMissionControlCommand(commandPayload as any);

    // Optimistic local state updates
    if (cmdType === 'PAUSE') {
      setMissionState((prev) => ({
        ...prev,
        status: 'PAUSED',
        mission_version: (prev.mission_version || 1) + 1,
      }));
    } else if (cmdType === 'RESUME') {
      setMissionState((prev) => ({
        ...prev,
        status: 'RUNNING',
        mission_version: (prev.mission_version || 1) + 1,
      }));
    } else if (cmdType === 'CANCEL') {
      setMissionState((prev) => ({
        ...prev,
        status: 'CANCELLED',
        mission_version: (prev.mission_version || 1) + 1,
      }));
    } else if (cmdType === 'APPROVE' && taskId) {
      setMissionState((prev) => ({
        ...prev,
        tasks: prev.tasks.map((t) =>
          t.id === taskId
            ? { ...t, status: 'DONE' as const, evidence: 'Aprovado pelo operador humano' }
            : t
        ),
        mission_version: (prev.mission_version || 1) + 1,
      }));
    } else if (cmdType === 'CHANGE_PRIORITY' && taskId) {
      const newPrio = payload.new_priority || 'HIGH';
      setMissionState((prev) => ({
        ...prev,
        tasks: prev.tasks.map((t) => (t.id === taskId ? { ...t, priority: newPrio } : t)),
        mission_version: (prev.mission_version || 1) + 1,
      }));
    } else if (cmdType === 'REORDER' && taskId) {
      const dir = payload.direction || 'UP';
      setMissionState((prev) => {
        const tasks = [...prev.tasks];
        const idx = tasks.findIndex((t) => t.id === taskId);
        if (idx < 0) return prev;
        const targetIdx = dir === 'UP' ? idx - 1 : idx + 1;
        if (targetIdx < 0 || targetIdx >= tasks.length) return prev;
        const temp = tasks[idx];
        tasks[idx] = tasks[targetIdx];
        tasks[targetIdx] = temp;
        return {
          ...prev,
          tasks,
          mission_version: (prev.mission_version || 1) + 1,
        };
      });
    }
  };

  const handleAnalyzeIntent = (presetText?: string) => {
    const textToAnalyze = presetText || intentInputText;
    if (!textToAnalyze.trim()) return;
    setIsAnalyzingIntent(true);

    const lower = textToAnalyze.toLowerCase();
    const isStructural = lower.includes('auth') || lower.includes('autentica') || lower.includes('react');
    setCurrentIntentPreview({
      resolved: true,
      operation: isStructural ? 'ADD_REQUIREMENT' : 'MODIFY_SCOPE',
      target: 'REQ_NEW',
      payload: { instruction: textToAnalyze },
      impact: isStructural ? 'STRUCTURAL' : 'LOCAL',
      scope: isStructural ? 'CROSS_MODULE' : 'LOCAL',
      risk: isStructural ? 'MEDIUM' : 'LOW',
      tasks_affected: isStructural ? ['TSK_02', 'TSK_03'] : ['TSK_01'],
      files_count: isStructural ? '3 direct, 2 indirect' : '1 direct',
      requires_pause: isStructural,
      evidence_affected: ['EVD_01'],
      approval_status: 'CONFIRM_REQUIRED',
      conflicts: [],
      confidence: 0.98,
      base_intent_version: missionState.intent_version || 1,
      suggested_replan: 'Adicionar tarefas de compensação no DAG',
    });

    try {
      sendMissionIntentPreview(missionState.mission_id, textToAnalyze);
    } catch {
      // Offline fallback
    } finally {
      setTimeout(() => {
        setIsAnalyzingIntent(false);
      }, 400);
    }
  };

  const handleApplyIntent = () => {
    if (!currentIntentPreview) return;
    setIsApplyingIntent(true);
    const baseVersion = missionState.intent_version || 1;
    const delta = {
      delta_id: `delta_${Date.now()}`,
      mission_id: missionState.mission_id,
      base_intent_version: baseVersion,
      operation: currentIntentPreview.operation || 'ADD_REQUIREMENT',
      target: currentIntentPreview.target || 'REQ_NEW',
      payload: currentIntentPreview.payload || {},
      reason: intentInputText || 'Alteração semântica solicitada pelo operador',
      requested_by: 'operador_humano',
      created_at: Date.now() / 1000,
    };

    setMissionState((prev) => ({
      ...prev,
      intent_version: (prev.intent_version || 1) + 1,
      plan_version: (prev.plan_version || 1) + 1,
    }));

    try {
      sendMissionIntentChange(missionState.mission_id, delta, true);
    } catch {
      // Offline fallback
    } finally {
      setTimeout(() => {
        setIsApplyingIntent(false);
        setShowIntentModal(false);
        setCurrentIntentPreview(null);
      }, 400);
    }
  };

  const deduplicatedEvents = useMemo(() => {
    const seen = new Set<string>();
    const res: MissionControlEventData[] = [];
    const source = missionState.events && Array.isArray(missionState.events) ? missionState.events : [];
    for (const ev of source) {
      if (!seen.has(ev.event_id)) {
        seen.add(ev.event_id);
        res.push(ev);
      }
    }
    return res;
  }, [missionState.events]);

  return (
    <div className="flex h-full flex-col overflow-hidden bg-[#091217] text-gray-100">
      {/* 1. COMPACT HEADER WITH ACTIONS */}
      <MissionHeader
        scenarios={SCENARIOS}
        selectedScenario={selectedScenario}
        onSelectScenario={loadScenarioState}
        missionState={missionState}
        lastCommandFeedback={lastCommandFeedback}
        onDismissFeedback={() => {
          setLastCommandFeedback(null);
          clearMissionControlCommandResult();
        }}
        onOpenArchitecture={onOpenArchitecture}
        onBackToList={onBackToList}
      >
        <MissionControlActions
          status={missionState.status}
          isSubmittingCommand={isSubmittingCommand}
          onEditGoal={() => setShowIntentModal(true)}
          onPause={() => handleSendCommand('PAUSE', null, {}, 'Pausa de trabalho pelo operador')}
          onResume={() => handleSendCommand('RESUME', null, {}, 'Retoma de execução autorizada pelo operador')}
          onCancel={() => setShowCancelModal(true)}
        />
      </MissionHeader>

      {/* HITL PERMISSION GATEWAY BANNER */}
      {missionState.status === 'AWAITING_HUMAN_APPROVAL' && (
        <div className="mx-6 mt-3 p-3 rounded-lg border border-amber-500/30 bg-amber-500/10 flex items-center justify-between text-amber-200 text-xs">
          <div className="flex items-center gap-2.5">
            <Lock className="w-4 h-4 text-amber-400 shrink-0 animate-pulse" />
            <div>
              <span className="font-semibold text-amber-100">É necessária uma autorização.</span>
              <span className="text-amber-300/80 ml-2">Esta missão solicitou uma ferramenta externa ou privilégio e está pausada a aguardar confirmação.</span>
            </div>
          </div>
          <button
            onClick={() => usePermissionStore.getState().setModalOpen(true)}
            className="px-3 py-1 bg-amber-500/20 hover:bg-amber-500/30 text-amber-200 border border-amber-500/30 rounded text-xs font-medium cursor-pointer transition"
          >
            Rever Pedido
          </button>
        </div>
      )}

      {/* 2. PRIMARY 5-TAB NAVIGATION (CLEAN, NO HORIZONTAL SCROLL) */}
      <div className="flex border-b border-white/8 bg-[#070b10]/60 px-6">
        {[
          { id: 'overview', label: 'Visão geral', icon: LayoutDashboard },
          { id: 'tasks', label: 'Tarefas', icon: Layers },
          { id: 'agents', label: 'Agentes', icon: Cpu },
          { id: 'activity', label: 'Atividade', icon: Activity },
          { id: 'diagnostics', label: 'Diagnóstico', icon: Sparkles },
        ].map((tab) => {
          const isActive = activeViewSection === tab.id;
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              id={`mission-nav-tab-${tab.id}`}
              onClick={() => setActiveViewSection(tab.id as MissionPrimarySection)}
              className={`flex items-center gap-2 border-b-2 px-4 py-2.5 text-xs font-semibold transition-all ${
                isActive
                  ? 'border-cyan-400 text-cyan-200 bg-white/[0.04]'
                  : 'border-transparent text-gray-400 hover:text-gray-200 hover:bg-white/[0.02]'
              }`}
            >
              <Icon className={`h-4 w-4 shrink-0 ${isActive ? 'text-cyan-300' : 'text-gray-400'}`} />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* 3. MAIN CONTENT VIEW */}
      <div className="flex-1 overflow-y-auto p-4 md:p-6">
        {activeViewSection === 'overview' && (
          <MissionOverviewPanel
            missionState={missionState}
            onNavigateTab={(tab) => setActiveViewSection(tab)}
            onOpenInCode={onOpenInCode}
          />
        )}

        {activeViewSection === 'tasks' && (
          <MissionTasksView
            tasks={missionState.tasks || []}
            onSendCommand={handleSendCommand}
            isSubmittingCommand={isSubmittingCommand}
          />
        )}

        {activeViewSection === 'agents' && (
          <MissionAgentsView
            agents={missionState.agents || []}
            onOpenInCode={onOpenInCode}
          />
        )}

        {activeViewSection === 'activity' && (
          <MissionActivityView events={deduplicatedEvents} />
        )}

        {activeViewSection === 'diagnostics' && (
          <MissionDiagnosticsView
            missionState={missionState}
            onOpenInCode={onOpenInCode}
            onSendCommand={handleSendCommand}
          />
        )}
      </div>

      {/* MODALS */}
      <CancelConfirmModal
        isOpen={showCancelModal}
        cancelReason={cancelReason}
        onChangeReason={setCancelReason}
        onConfirm={() => {
          handleSendCommand('CANCEL', null, {}, cancelReason || 'Cancelado pelo operador');
          setShowCancelModal(false);
        }}
        onDismiss={() => setShowCancelModal(false)}
      />

      <IntentPreviewModal
        isOpen={showIntentModal}
        intentInputText={intentInputText}
        isAnalyzingIntent={isAnalyzingIntent}
        isApplyingIntent={isApplyingIntent}
        currentIntentPreview={currentIntentPreview}
        onChangeInputText={setIntentInputText}
        onAnalyzeIntent={handleAnalyzeIntent}
        onApplyIntent={handleApplyIntent}
        onClose={() => {
          setShowIntentModal(false);
          setCurrentIntentPreview(null);
        }}
      />
    </div>
  );
};

export default MissionControlCenter;
