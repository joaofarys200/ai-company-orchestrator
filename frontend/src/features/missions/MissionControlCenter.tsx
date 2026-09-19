import React, { useState, useMemo, useEffect } from 'react';
import {
  Activity,
  Boxes,
  Brain,
  BookOpen,
  GitBranch,
  GitPullRequest,
  Layers,
  Orbit,
  Play,
  Scale,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  Wrench,
  Network,
  Radio,
  Split,
  GitMerge,
  FileCode2,
  FileCheck,
  Compass,
  Crosshair,
  Stethoscope,
  Award,
  Cpu,
  FlaskConical,
  Share2,
  Workflow,
  GitCommit,
  Users,
  Rocket,
} from 'lucide-react';
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
  MissionTaskGraphPanel,
  MissionRequirementsDiffPanel,
  MissionPlanDiffPanel,
  MissionEvidenceImpactPanel,
  MissionWhyCausalPanel,
  MissionRepairPanel,
  MissionEvidenceLedgerPanel,
  MissionAppPreviewPanel,
  MissionPredictedImpactPanel,
  MissionPredictionOutcomePanel,
  AutonomousLoopPanel,
  DecisionQualityPanel,
  ExperienceMemoryPanel,
  SemanticGraphPanel,
  RuntimeContractDiscoveryPanel,
  ContractHealthPanel,
  PolymorphicSchemaPanel,
  ContractChangeManagementPanel,
  BuildContractExtractionPanel,
  BehavioralContractProofPanel,
  BehavioralProofExplorationPanel,
  RiskDirectedExplorationPanel,
  UniversalPreflightRecoveryPanel,
  VerifiedRepairSynthesisPanel,
  MultiRepairOrchestrationPanel,
  AutonomousRepairConvergencePanel,
  AutonomousTaskCompletionPanel,
  MassiveProjectStatePanel,
  SCCAwareGraphPanel,
  SymbolFineGrainedGraphPanel,
  AutonomousTestSynthesisPanel,
  ContinuousVerificationPanel,
  CrossProjectLearningPanel,
  ArchitectureEvolutionPanel,
  SafeSelfModificationPanel,
  MultiAgentCoordinationPanel,
  LongHorizonMissionPanel,
  EngineeringQualityGovernancePanel,
  QualityDebtRemediationPanel,
  ReleaseReadinessPanel,
  ProductionOperationsPanel,
  ReliabilityIntelligencePanel,
} from './components';


export interface MissionControlCenterProps {
  onOpenInCode?: (filePath: string, line?: number) => void;
  onOpenArchitecture?: () => void;
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
  interpreted_goal: 'Consola Bidirecional de Operações: Gestor de Despesas & Controlo Humano',
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
  is_user_useful: false,
  mission_version: 1,
  intent_version: 1,
  plan_version: 1,
  command_history: [],
  intent: {
    intent_id: 'int_p37_v1',
    mission_id: 'm_p36_interactive',
    version: 1,
    source: 'USER_REQUIREMENT',
    requirements: [
      { id: 'REQ_01', desc: 'Registo e categorização de despesas (Alimentação, Transporte, Lazer)', source: 'USER_REQUIREMENT', status: 'VALIDATED', verification_status: 'VERIFIED' },
      { id: 'REQ_02', desc: 'Cálculo dinâmico de total acumulado e contagem de itens em tempo real', source: 'USER_REQUIREMENT', status: 'IDENTIFIED', verification_status: 'INFERRED' },
      { id: 'REQ_03', desc: 'Pesquisa reativa e filtragem instantânea por categoria', source: 'USER_REQUIREMENT', status: 'IDENTIFIED', verification_status: 'INFERRED' },
      { id: 'REQ_04', desc: 'Persistência duradoura e resiliente no localStorage do navegador', source: 'USER_REQUIREMENT', status: 'IDENTIFIED', verification_status: 'INFERRED' },
    ],
    constraints: [
      { id: 'CST_01', desc: 'Zero dependências de bibliotecas externas pesadas', status: 'ACTIVE' },
      { id: 'CST_02', desc: 'Isolamento estrito e sem bypass de segurança', status: 'ACTIVE' },
    ],
  },
  requirements: [
    { id: 'REQ_01', desc: 'Registo e categorização de despesas (Alimentação, Transporte, Lazer)', source: 'USER_REQUIREMENT', status: 'VALIDATED', verification_status: 'VERIFIED' },
    { id: 'REQ_02', desc: 'Cálculo dinâmico de total acumulado e contagem de itens em tempo real', source: 'USER_REQUIREMENT', status: 'IDENTIFIED', verification_status: 'INFERRED' },
    { id: 'REQ_03', desc: 'Pesquisa reativa e filtragem instantânea por categoria', source: 'USER_REQUIREMENT', status: 'IDENTIFIED', verification_status: 'INFERRED' },
    { id: 'REQ_04', desc: 'Persistência duradoura e resiliente no localStorage do navegador', source: 'USER_REQUIREMENT', status: 'IDENTIFIED', verification_status: 'INFERRED' },
  ],
  assumptions: [
    { id: 'ASM_01', desc: 'Aplicação Web de página única (SPA) estritamente Vanilla TypeScript & CSS responsivo', rationale: 'Garante arranque em < 15ms sem dependências', status: 'INFERRED', source: 'SYSTEM_ASSUMPTION', verification_status: 'INFERRED' },
    { id: 'ASM_02', desc: 'Armazenamento direto via API nativa do Web Storage (localStorage)', rationale: 'Elimina necessidade de backend remoto para execução offline', status: 'INFERRED', source: 'SYSTEM_ASSUMPTION', verification_status: 'INFERRED' },
  ],
  unknowns: [],
  events: [],
  tasks: [
    { id: 'TSK_01', title: 'Setup da estrutura web e manifesto de aplicação', owner: 'ArchitectAgent', status: 'DONE', duration_seconds: 0.015, dependencies: [], priority: 'NORMAL', evidence: 'Estrutura HTML5 com tags semânticas e viewport configurada' },
    { id: 'TSK_02', title: 'Implementação do motor de estado de despesas e cálculo financeiro', owner: 'CoderAgent', status: 'DONE', duration_seconds: 0.035, dependencies: ['TSK_01'], priority: 'HIGH', evidence: 'Classe ExpenseTracker com validação de montantes positivos' },
    { id: 'TSK_03', title: 'Verificação pelo Operador da Política de Filtragem e Limites de Gastos', owner: 'HumanOperator', status: 'PENDING_APPROVAL', duration_seconds: 0.010, dependencies: ['TSK_02'], priority: 'CRITICAL', approval_status: 'PENDING_APPROVAL', evidence: 'Aguardando validação humana para prosseguir' },
    { id: 'TSK_04', title: 'Construção da interface reativa e filtros por categoria', owner: 'CoderAgent', status: 'PENDING', duration_seconds: 0.025, dependencies: ['TSK_03'], priority: 'NORMAL', evidence: 'Pendente de aprovação da tarefa TSK_03' },
  ],
  agents: [
    { agent_id: 'ag_arch', name: 'ArchitectAgent', role: 'System Architect', status: 'IDLE', current_task: 'Arquitetura validada', completed_tasks_count: 1, failures_count: 0, handoffs_count: 1, files_touched: ['index.html'] },
    { agent_id: 'ag_coder', name: 'CoderAgent', role: 'Software Engineer', status: 'BUSY', current_task: 'TSK_02: Motor de Despesas', completed_tasks_count: 1, failures_count: 0, handoffs_count: 1, files_touched: ['src/tracker.ts', 'src/types.ts'] },
    { agent_id: 'ag_tester', name: 'TesterAgent', role: 'QA & Verification', status: 'IDLE', current_task: 'Aguardando entrega de código', completed_tasks_count: 0, failures_count: 0, handoffs_count: 0, files_touched: [] },
    { agent_id: 'ag_sentinel', name: 'SentinelAgent', role: 'Security & Safety Gate', status: 'IDLE', current_task: 'Políticas em conformidade', completed_tasks_count: 2, failures_count: 0, handoffs_count: 0, files_touched: [] },
    { agent_id: 'ag_replan', name: 'ReplannerAgent', role: 'Dynamic Adaptation', status: 'IDLE', current_task: 'Topologia estável', completed_tasks_count: 0, failures_count: 0, handoffs_count: 0, files_touched: [] },
    { agent_id: 'ag_obs', name: 'ObservabilityAgent', role: 'Telemetry & Evidence', status: 'IDLE', current_task: 'Métricas ativas', completed_tasks_count: 3, failures_count: 0, handoffs_count: 0, files_touched: [] },
  ],
  repairs: [],
  replans: [],
  recoveries: [],
  evidence: [
    { type: 'TEST_EXECUTION', status: 'VERIFIED', source: 'TesterAgent', timestamp: 0.045, details: { test_file: 'tests/tracker.test.ts', tests_passed: 3, tests_failed: 0, assertions: 8 } },
  ],
  artifacts: [
    { name: 'tracker.ts', path: 'src/tracker.ts', type: 'CODE', summary: 'Motor de cálculo de despesas com métodos addExpense, removeExpense e getTotalByCategory', line_target: 1 },
  ],
  why_items: [
    { action: 'Ativação do modo interativo supervisionado', reason: 'Permite intervenção do operador para pausar, cancelar e aprovar tarefas críticas', source: 'USER_REQUIREMENT', evidence: 'Parâmetro interactive_mode=true' },
    { action: 'Configuração da tarefa TSK_03 com exigência de aprovação humana', reason: 'Garante que os limites orçamentais são inspecionados antes da emissão de código de filtragem', source: 'SYSTEM_ASSUMPTION', evidence: 'Policy requirement: Approval gate on expenditure policies' },
  ],
  requirement_diff: [
    { id: 'REQ_01', desc: 'Registo e categorização de despesas (Alimentação, Transporte, Lazer)', type: 'UNCHANGED', status: 'VALIDATED' },
    { id: 'REQ_02', desc: 'Cálculo dinâmico de total acumulado e contagem de itens em tempo real', type: 'UNCHANGED', status: 'IDENTIFIED' },
    { id: 'REQ_03', desc: 'Pesquisa reativa e filtragem instantânea por categoria', type: 'UNCHANGED', status: 'IDENTIFIED' },
    { id: 'REQ_04', desc: 'Persistência duradoura e resiliente no localStorage do navegador', type: 'UNCHANGED', status: 'IDENTIFIED' },
  ],
  plan_diff: [],
  evidence_impact: [],
  final_result: {
    decision: 'RUNNING',
    why: 'Missão em execução ativa sob supervisão humana direta. Operador pode emitir comandos operacionais e alterar intenção dinamicamente.',
    what_changed: 'Grafo de tarefas configurado para controlo bidirecional',
    what_was_validated: 'Setup inicial e motor de despesas validados',
    what_remains: 'Aprovação humana de TSK_03 e conclusão das tarefas pendentes',
  },
};

export const MissionControlCenter: React.FC<MissionControlCenterProps> = ({
  onOpenInCode,
  onOpenArchitecture,
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
  const [activeViewSection, setActiveViewSection] = useState<
    'overview' | 'plan' | 'requirements_diff' | 'plan_diff' | 'predicted_impact' | 'prediction_vs_actual' | 'autonomous_loop' | 'decision_calibration' | 'experience_memory' | 'semantic_graph' | 'contract_discovery' | 'contract_health' | 'polymorphic_contracts' | 'contract_change_mgmt' | 'build_contract_extraction' | 'behavioral_contract_proof' | 'behavioral_proof_exploration' | 'risk_directed_exploration' | 'universal_preflight_recovery' | 'verified_repair_synthesis' | 'multi_repair_orchestration' | 'autonomous_repair_convergence' | 'autonomous_task_completion' | 'massive_project_state' | 'scc_aware_graph' | 'symbol_fine_grained_graph' | 'autonomous_test_synthesis' | 'continuous_verification' | 'cross_project_learning' | 'architecture_evolution' | 'safe_self_modification' | 'multi_agent_coordination' | 'long_horizon_missions' | 'quality_governance' | 'quality_debt_remediation' | 'release_readiness' | 'production_operations' | 'reliability_intelligence' | 'evidence_impact' | 'why' | 'repairs' | 'evidence' | 'preview'
  >('overview');

  const [expandedEventId, setExpandedEventId] = useState<string | null>(null);

  // Fase 36 Interactive Control UI state
  const [showCancelModal, setShowCancelModal] = useState(false);
  const [cancelReason, setCancelReason] = useState('');
  const [lastCommandFeedback, setLastCommandFeedback] = useState<{ status: string; reason: string; timestamp: number } | null>(null);
  const [isSubmittingCommand, setIsSubmittingCommand] = useState(false);

  // Fase 37 Intent Editing & Preview state
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
      const normalizedImpact = typeof rawImpact === 'object' && rawImpact !== null
        ? rawImpact.level || 'LOCAL'
        : String(rawImpact || 'LOCAL');

      setCurrentIntentPreview({
        resolved: res.success ?? true,
        operation: res.data?.operation || 'ADD_REQUIREMENT',
        target: res.data?.target || 'REQ_NEW',
        payload: res.data?.payload || {},
        impact: normalizedImpact,
        requires_pause: res.data?.requires_pause !== undefined ? res.data.requires_pause : normalizedImpact === 'STRUCTURAL',
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
        const newIntentVer = res.intent_version || liveData.intent_version || (missionState.intent_version || 1) + 1;
        const newPlanVer = res.plan_version || liveData.plan_version || (missionState.plan_version || 1) + 1;
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
    // Preserves mock scenarios when switching
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

    // Optimistic local state updates for offline resilience
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
        tasks: prev.tasks.map((t) =>
          t.id === taskId ? { ...t, priority: newPrio } : t
        ),
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
      // Fallback offline analysis
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

    // Optimistic local state update for instantaneous feedback
    setMissionState((prev) => ({
      ...prev,
      intent_version: (prev.intent_version || 1) + 1,
      plan_version: (prev.plan_version || 1) + 1,
    }));

    try {
      sendMissionIntentChange(missionState.mission_id, delta, true);
    } catch {
      // Fallback offline state update
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
    const source = (missionState.events && Array.isArray(missionState.events)) ? missionState.events : [];
    for (const ev of source) {
      if (!seen.has(ev.event_id)) {
        seen.add(ev.event_id);
        res.push(ev);
      }
    }
    return res;
  }, [missionState.events]);

  return (
    <div className="flex h-full flex-col overflow-hidden bg-[#0a1114] text-gray-100">
      {/* 1. SCENARIO SELECTOR & HEADER CONSOLE (COMPOSED) */}
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

      {/* CANCEL CONFIRMATION MODAL */}
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

      {/* INTENT EDIT / INTENT PREVIEW MODAL (FASE 37) */}
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

      {/* NAVIGATION TABS WITHIN MISSION CONTROL */}
      <div className="flex border-b border-[#a1bebf]/15 bg-[#0b1417] px-6">
        {[
          { id: 'overview', label: 'Visão Geral & Enxame', icon: Boxes },
          { id: 'plan', label: 'Plano & Grafo de Tarefas', icon: GitBranch },
          { id: 'requirements_diff', label: 'Requisitos & Diff (Fase 37)', icon: Layers },
          { id: 'plan_diff', label: 'Diff de Planos (DAG)', icon: GitPullRequest },
          { id: 'predicted_impact', label: 'Impacto Preditivo (Fase 39)', icon: Sparkles },
          { id: 'prediction_vs_actual', label: 'Previsão vs Realidade', icon: TrendingUp },
          { id: 'autonomous_loop', label: 'Loop Autónomo (Fase 40)', icon: Orbit },
          { id: 'decision_calibration', label: 'Calibração & Decisão (Fase 41)', icon: Scale },
          { id: 'experience_memory', label: 'Memória & Experiência (Fase 42)', icon: BookOpen },
          { id: 'semantic_graph', label: 'Grafo Semântico (Fase 44)', icon: Network },
          { id: 'contract_discovery', label: 'Contratos & Schema (Fase 45)', icon: Radio },
          { id: 'contract_health', label: 'Governação & Drift (Fase 46)', icon: ShieldCheck },
          { id: 'polymorphic_contracts', label: 'Polimorfismo & Uniões (Fase 47)', icon: Split },
          { id: 'contract_change_mgmt', label: 'Mudanças Contratuais (Fase 48)', icon: GitMerge },
          { id: 'build_contract_extraction', label: 'Extração & Consumers (Fase 49)', icon: FileCode2 },
          { id: 'behavioral_contract_proof', label: 'Prova Comportamental (Fase 50)', icon: FileCheck },
          { id: 'behavioral_proof_exploration', label: 'Exploração & Cobertura (Fase 51)', icon: Compass },
          { id: 'risk_directed_exploration', label: 'Exploração por Risco (Fase 52)', icon: Crosshair },
          { id: 'universal_preflight_recovery', label: 'Preflight & Auto-Recovery (Fase 53)', icon: Stethoscope },
          { id: 'verified_repair_synthesis', label: 'Síntese & Prova de Reparação (Fase 54)', icon: Wrench },
          { id: 'multi_repair_orchestration', label: 'Orquestração Multi-Reparação (Fase 55)', icon: GitMerge },
          { id: 'autonomous_repair_convergence', label: 'Governação de Convergência (Fase 56)', icon: Scale },
          { id: 'autonomous_task_completion', label: 'Conclusão Autónoma de Missões (Fase 57)', icon: Award },
          { id: 'massive_project_state', label: 'Estado Massivo & Monorepo (Fase 58)', icon: Layers },
          { id: 'scc_aware_graph', label: 'Grafo SCC & Condensação DAG (Fase 59)', icon: Network },
          { id: 'symbol_fine_grained_graph', label: 'Grafo de Símbolos & Precisão SCC (Fase 60)', icon: Cpu },
          { id: 'autonomous_test_synthesis', label: 'Síntese de Testes & Cobertura (Fase 61)', icon: FlaskConical },
          { id: 'continuous_verification', label: 'Verificação Contínua & Regressão (Fase 62)', icon: ShieldCheck },
          { id: 'cross_project_learning', label: 'Aprendizagem Cross-Project & Transfer (Fase 63)', icon: Share2 },
          { id: 'architecture_evolution', label: 'Evolução Arquitetural & Design (Fase 64)', icon: Workflow },
          { id: 'safe_self_modification', label: 'Self-Modification Segura (Fase 65)', icon: GitCommit },
          { id: 'multi_agent_coordination', label: 'Coordenação Multi-Agente (Fase 66)', icon: Users },
          { id: 'long_horizon_missions', label: 'Missões Long-Horizon & Governação (Fase 67)', icon: Compass },
          { id: 'quality_governance', label: 'Governação de Qualidade & Dívida Técnica (Fase 68)', icon: Award },
          { id: 'quality_debt_remediation', label: 'Remediação de Dívida Técnica (Fase 69)', icon: Wrench },
          { id: 'release_readiness', label: 'Release Readiness & Governação (Fase 70)', icon: Rocket },
          { id: 'production_operations', label: 'Operações de Produção & Governação de Incidentes (Fase 71)', icon: Activity },
          { id: 'reliability_intelligence', label: 'Inteligência de Confiabilidade & Operações Preventivas (Fase 72)', icon: Sparkles },
          { id: 'evidence_impact', label: 'Impacto em Evidências', icon: ShieldAlert },
          { id: 'why', label: 'Painel do Porquê ("Why Panel")', icon: Brain },
          { id: 'repairs', label: 'Auto-Cura & Adaptação', icon: Wrench },
          { id: 'evidence', label: 'Evidências & Validação', icon: ShieldCheck },
          { id: 'preview', label: 'Aplicação ao Vivo (Live QA)', icon: Play },
        ].map((tab) => {
          const isActive = activeViewSection === tab.id;
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              id={`view-tab-${tab.id}`}
              onClick={() => setActiveViewSection(tab.id as any)}
              className={`flex items-center gap-2 border-b-2 px-4 py-3 text-xs font-semibold transition-all ${
                isActive
                  ? 'border-cyan-400 text-cyan-300 bg-cyan-500/5'
                  : 'border-transparent text-gray-400 hover:text-gray-200 hover:bg-white/[0.02]'
              }`}
            >
              <Icon className="h-4 w-4" />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* MAIN VIEW CONTENT AREA (DECOMPOSED SUB-PANELS) */}
      <div className="flex-1 overflow-y-auto p-6">
        {activeViewSection === 'overview' && (
          <MissionOverviewPanel
            missionState={missionState}
            onOpenInCode={onOpenInCode}
          />
        )}

        {activeViewSection === 'plan' && (
          <MissionTaskGraphPanel
            missionState={missionState}
            deduplicatedEvents={deduplicatedEvents}
            expandedEventId={expandedEventId}
            onToggleExpandEvent={(id) => setExpandedEventId(expandedEventId === id ? null : id)}
            onSendCommand={handleSendCommand}
          />
        )}

        {activeViewSection === 'requirements_diff' && (
          <MissionRequirementsDiffPanel missionState={missionState} />
        )}

        {activeViewSection === 'plan_diff' && (
          <MissionPlanDiffPanel missionState={missionState} />
        )}

        {activeViewSection === 'predicted_impact' && (
          <MissionPredictedImpactPanel
            prediction={(missionState as any).last_prediction_report || {
              prediction_id: 'pred_demo_01',
              predicted_scope: 'CROSS_MODULE',
              predicted_risk: 'MEDIUM',
              simulation_marker: 'SIMULATION_ONLY',
              confidence: 0.90,
              predicted_browser_validation: true,
              predicted_pause_required: true,
              predicted_approval_required: false,
              predicted_tasks: [
                { predicted_task_id: 'ptask_impl_5', title: 'Implementar Autenticação & Controlo de Acesso', action: 'ADD_TASK', description: 'Desenvolver componentes e tokens JWT', predicted_owner: 'coder', status: 'PREDICTED_ONLY' },
                { predicted_task_id: 'ptask_test_6', title: 'Validar testes para Autenticação', action: 'ADD_TASK', description: 'Executar testes de autorização e sessão', predicted_owner: 'test_engineer', status: 'PREDICTED_ONLY' }
              ],
              predicted_files: [
                { file_path: 'backend/security/auth.py', classification: 'DIRECT', reason: 'Implementação de autenticação JWT' },
                { file_path: 'backend/api.py', classification: 'INDIRECT', reason: 'Injeção de middleware de autenticação' },
                { file_path: 'frontend/src/context/AuthContext.tsx', classification: 'POSSIBLE', reason: 'Gestão de token de sessão no frontend' }
              ],
              predicted_tests: [
                { test_file: 'tests/test_auth.py', target_module: 'backend/security/auth.py' }
              ],
              predicted_evidence_impact: [
                { evidence_id: 'EVD_AUTH_01', requirement_id: 'REQ_AUTH', predicted_status: 'REQUIRES_REVALIDATION', reason: 'Zero False Success: Requisito novo exige validação' }
              ],
              assumptions: [
                { assumption_id: 'asm_1', statement: 'Preservação da compatibilidade com endpoints existentes', category: 'SYSTEM_ASSUMPTION' },
                { assumption_id: 'asm_2', statement: 'Reutilização dos utilitários já mapeados no workspace', category: 'INFERRED' }
              ],
              uncertainties: [],
              causal_chains: [
                { origin: 'Directive auth/jwt', path: 'Directive -> Security Module -> API Endpoints -> Client AuthContext' }
              ]
            }}
            onApplyPrediction={handleApplyIntent}
            isApplying={isApplyingIntent}
          />
        )}

        {activeViewSection === 'prediction_vs_actual' && (
          <MissionPredictionOutcomePanel
            outcome={(missionState as any).last_prediction_outcome || {
              outcome_id: 'out_demo_01',
              prediction_id: 'pred_demo_01',
              classification: 'CORRECT',
              file_precision: 1.0,
              file_recall: 1.0,
              task_precision: 1.0,
              task_recall: 1.0,
              actual_files_changed: ['backend/security/auth.py', 'backend/api.py', 'frontend/src/context/AuthContext.tsx'],
              actual_tasks_added: ['ptask_impl_5', 'ptask_test_6'],
              actual_scope: 'CROSS_MODULE',
              actual_browser_validation: true,
              matched_files: ['backend/security/auth.py', 'backend/api.py', 'frontend/src/context/AuthContext.tsx'],
              missed_files: [],
              unexpected_files: [],
              deviations: []
            }}
            predictionReport={(missionState as any).last_prediction_report}
          />
        )}

        {activeViewSection === 'autonomous_loop' && (
          <AutonomousLoopPanel
            missionId={missionState.mission_id}
          />
        )}

        {activeViewSection === 'decision_calibration' && (
          <DecisionQualityPanel
            missionId={missionState.mission_id}
          />
        )}

        {activeViewSection === 'experience_memory' && (
          <ExperienceMemoryPanel
            missionId={missionState.mission_id}
          />
        )}

        {activeViewSection === 'semantic_graph' && (
          <SemanticGraphPanel
            missionId={missionState.mission_id}
          />
        )}

        {activeViewSection === 'contract_discovery' && (
          <RuntimeContractDiscoveryPanel
            missionId={missionState.mission_id}
          />
        )}

        {activeViewSection === 'contract_health' && (
          <ContractHealthPanel
            missionId={missionState.mission_id}
          />
        )}

        {activeViewSection === 'polymorphic_contracts' && (
          <PolymorphicSchemaPanel
            missionId={missionState.mission_id}
          />
        )}

        {activeViewSection === 'contract_change_mgmt' && (
          <ContractChangeManagementPanel
            missionId={missionState.mission_id}
          />
        )}

        {activeViewSection === 'build_contract_extraction' && (
          <BuildContractExtractionPanel
            missionId={missionState.mission_id}
          />
        )}

        {activeViewSection === 'behavioral_contract_proof' && (
          <BehavioralContractProofPanel
            missionId={missionState.mission_id}
          />
        )}

        {activeViewSection === 'behavioral_proof_exploration' && (
          <BehavioralProofExplorationPanel
            missionId={missionState.mission_id}
          />
        )}

        {activeViewSection === 'risk_directed_exploration' && (
          <RiskDirectedExplorationPanel
            missionId={missionState.mission_id}
          />
        )}

        {activeViewSection === 'universal_preflight_recovery' && (
          <UniversalPreflightRecoveryPanel />
        )}

        {activeViewSection === 'verified_repair_synthesis' && (
          <VerifiedRepairSynthesisPanel />
        )}

        {activeViewSection === 'multi_repair_orchestration' && (
          <MultiRepairOrchestrationPanel />
        )}

        {activeViewSection === 'autonomous_repair_convergence' && (
          <AutonomousRepairConvergencePanel />
        )}

        {activeViewSection === 'autonomous_task_completion' && (
          <AutonomousTaskCompletionPanel />
        )}

        {activeViewSection === 'massive_project_state' && (
          <MassiveProjectStatePanel />
        )}

        {activeViewSection === 'scc_aware_graph' && (
          <SCCAwareGraphPanel />
        )}

        {activeViewSection === 'symbol_fine_grained_graph' && (
          <SymbolFineGrainedGraphPanel />
        )}

        {activeViewSection === 'autonomous_test_synthesis' && (
          <AutonomousTestSynthesisPanel />
        )}

        {activeViewSection === 'continuous_verification' && (
          <ContinuousVerificationPanel />
        )}

        {activeViewSection === 'cross_project_learning' && (
          <CrossProjectLearningPanel />
        )}

        {activeViewSection === 'architecture_evolution' && (
          <ArchitectureEvolutionPanel />
        )}

        {activeViewSection === 'safe_self_modification' && (
          <SafeSelfModificationPanel />
        )}

        {activeViewSection === 'multi_agent_coordination' && (
          <MultiAgentCoordinationPanel />
        )}

        {activeViewSection === 'long_horizon_missions' && (
          <LongHorizonMissionPanel missionId={missionState.mission_id} />
        )}

        {activeViewSection === 'quality_governance' && (
          <EngineeringQualityGovernancePanel missionId={missionState.mission_id} />
        )}

        {activeViewSection === 'quality_debt_remediation' && (
          <QualityDebtRemediationPanel missionId={missionState.mission_id} />
        )}

        {activeViewSection === 'release_readiness' && (
          <ReleaseReadinessPanel missionId={missionState.mission_id} />
        )}

        {activeViewSection === 'production_operations' && (
          <ProductionOperationsPanel missionId={missionState.mission_id} />
        )}

        {activeViewSection === 'reliability_intelligence' && (
          <ReliabilityIntelligencePanel missionId={missionState.mission_id} />
        )}

        {activeViewSection === 'evidence_impact' && (
          <MissionEvidenceImpactPanel missionState={missionState} />
        )}

        {activeViewSection === 'why' && (
          <MissionWhyCausalPanel missionState={missionState} />
        )}

        {activeViewSection === 'repairs' && (
          <MissionRepairPanel
            missionState={missionState}
            onOpenInCode={onOpenInCode}
          />
        )}

        {activeViewSection === 'evidence' && (
          <MissionEvidenceLedgerPanel
            missionState={missionState}
            onOpenInCode={onOpenInCode}
          />
        )}

        {activeViewSection === 'preview' && (
          <MissionAppPreviewPanel />
        )}
      </div>
    </div>
  );
};

export default MissionControlCenter;
