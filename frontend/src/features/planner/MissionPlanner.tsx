import { useEffect, useMemo, useState } from 'react';
import {
  Activity,
  CheckCircle2,
  CircleAlert,
  FileCheck2,
  GitBranch,
  Link2,
  ListPlus,
  Pencil,
  Play,
  Plus,
  RefreshCw,
  RotateCcw,
  ShieldCheck,
  ThumbsDown,
  ThumbsUp,
  X,
} from 'lucide-react';
import { useWebSocket } from '../../context/WebSocketContext';
import { Modal } from '../../components/Modal';
import type { MissionClientOperation, MissionCriterion, MissionDeliverable, MissionExecution, MissionWorkPackage } from '../../protocol/websocket';

const PANEL = 'rounded-md border border-white/8 bg-[#090d14]';
const SUBTLE = 'rounded-md border border-white/8 bg-black/20';
const BUTTON = 'inline-flex min-h-8 items-center justify-center gap-2 rounded-md border border-white/10 bg-white/[0.04] px-2.5 text-xs font-semibold text-gray-200 transition hover:bg-white/[0.08] disabled:cursor-not-allowed disabled:opacity-40';
const ICON_BUTTON = 'inline-flex h-8 w-8 items-center justify-center rounded-md border border-white/10 bg-white/[0.04] text-gray-300 transition hover:bg-white/[0.08] hover:text-white disabled:opacity-40';
const INPUT_CLASS = 'w-full rounded-md border border-white/10 bg-[#070a10] px-3 py-2 text-xs text-gray-200 outline-none focus:border-cyan-300/40';

const missionTransitions: Record<string, string[]> = {
  DRAFT: ['READY', 'CANCELLED'],
  READY: ['ACTIVE', 'CANCELLED'],
  ACTIVE: ['BLOCKED', 'COMPLETED', 'FAILED', 'CANCELLED'],
  BLOCKED: ['ACTIVE', 'CANCELLED'],
};

const workPackageTransitions: Record<string, string[]> = {
  PENDING: ['BLOCKED', 'CANCELLED'],
  READY: ['IN_PROGRESS', 'BLOCKED', 'CANCELLED'],
  IN_PROGRESS: ['BLOCKED', 'VALIDATION_FAILED', 'COMPLETED', 'CANCELLED'],
  BLOCKED: ['READY', 'IN_PROGRESS', 'CANCELLED'],
  VALIDATION_FAILED: ['READY', 'IN_PROGRESS', 'CANCELLED'],
};

const deliverableStates = ['PLANNED', 'IN_PROGRESS', 'READY_FOR_REVIEW', 'ACCEPTED', 'REJECTED'];
const workPackageTypes = ['PROJECT_BUILD', 'RESEARCH', 'CODING', 'DOCUMENT', 'EXPERIMENT', 'REVIEW', 'GENERIC'];
const supportedExecutors = new Set(['CODING', 'PROJECT_BUILD']);

const statusLabels: Record<string, string> = {
  DRAFT: 'Rascunho',
  READY: 'Pronta',
  ACTIVE: 'Em curso',
  BLOCKED: 'Bloqueada',
  COMPLETED: 'Concluída',
  FAILED: 'Falhou',
  CANCELLED: 'Cancelada',
  PENDING: 'Pendente',
  IN_PROGRESS: 'Em curso',
  VALIDATION_FAILED: 'Validação falhou',
  PLANNED: 'Planeada',
  READY_FOR_REVIEW: 'Em revisão',
  ACCEPTED: 'Aceite',
  REJECTED: 'Rejeitada',
  RUNNING: 'Em execução',
  WAITING_FOR_REVIEW: 'A aguardar revisão',
};

const statusLabel = (status: string) => statusLabels[status] ?? status.replaceAll('_', ' ').toLowerCase();

const executorFor = (item: MissionWorkPackage) => item.executor_kind && item.executor_kind !== 'MANUAL'
  ? item.executor_kind.toUpperCase()
  : item.type.toUpperCase();
const record = (value: unknown): Record<string, unknown> => value && typeof value === 'object' && !Array.isArray(value)
  ? value as Record<string, unknown>
  : {};
const records = (value: unknown): Array<Record<string, unknown>> => Array.isArray(value)
  ? value.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === 'object' && !Array.isArray(item))
  : [];

interface ExecutionDetailsProps {
  execution: MissionExecution;
  onApply: (execution: MissionExecution) => void;
  onReview: (execution: MissionExecution, decision: 'ACCEPT' | 'REJECT') => void;
  onRetry: (execution: MissionExecution) => void;
  onCancel: (execution: MissionExecution) => void;
}

function ExecutionDetails({ execution, onApply, onReview, onRetry, onCancel }: ExecutionDetailsProps) {
  const output = record(execution.output_summary);
  const plan = record(output.change_plan);
  const changes = records(output.proposed_changes);
  const validations = records(output.validation_results);
  const phase = String(output.phase ?? '');

  return (
    <div className="mt-3 space-y-3 border-t border-white/8 pt-3">
      <div className="flex flex-wrap items-center gap-2 text-[11px]">
        <Activity className="h-3.5 w-3.5 text-cyan-300" />
        <span className="font-semibold text-gray-200">{execution.executor_kind}</span>
        <span className="rounded bg-white/[0.06] px-2 py-0.5 text-gray-300">{statusLabel(execution.status)}</span>
        <span className="text-gray-600">tentativa {execution.attempt}</span>
        {phase && <span className="text-cyan-200">{phase}</span>}
      </div>

      {Object.keys(plan).length > 0 && (
        <div className="text-xs text-gray-400">
          <p className="font-semibold text-gray-300">Plano</p>
          <p className="mt-1">{String(plan.objective ?? '')}</p>
          {Array.isArray(plan.affected_files) && <p className="mt-1 text-gray-600">Ficheiros: {plan.affected_files.map(String).join(', ')}</p>}
        </div>
      )}

      {changes.map((change, index) => (
        <div key={`${String(change.file)}-${index}`} className="min-w-0 text-xs">
          <p className="mb-1 font-semibold text-gray-300">{String(change.file ?? 'Diff')}</p>
          <pre className="max-h-52 overflow-auto whitespace-pre-wrap break-words border-l border-cyan-300/20 bg-black/20 p-2 font-mono text-[10px] leading-relaxed text-gray-400">
            {String(change.unified_diff ?? '')}
          </pre>
        </div>
      ))}

      {execution.artifact_refs.length > 0 && (
        <div className="text-[11px] text-gray-500">
          <p className="font-semibold text-gray-300">Artefactos</p>
          {execution.artifact_refs.map((item) => <p key={item} className="break-all">{item}</p>)}
        </div>
      )}

      {validations.length > 0 && (
        <div className="text-[11px] text-gray-500">
          <p className="font-semibold text-gray-300">Validações</p>
          {validations.map((item, index) => (
            <p key={`${String(item.command)}-${index}`} className="break-all">
              {Number(item.exit_code ?? (item.ok ? 0 : 1)) === 0 ? 'OK' : 'FALHOU'} · {String(item.command ?? 'preview')}
            </p>
          ))}
        </div>
      )}

      {execution.evidence_refs.length > 0 && (
        <p className="break-all text-[11px] text-gray-500">Evidência: {execution.evidence_refs.join(', ')}</p>
      )}
      {execution.primary_error && <p className="text-xs text-red-300">{execution.primary_error.message}</p>}
      {execution.rollback_error && <p className="text-xs text-red-300">Rollback: {execution.rollback_error.message}</p>}

      <div className="flex flex-wrap gap-2">
        {execution.status === 'RUNNING' && phase === 'AWAITING_APPLY_APPROVAL' && (
          <button onClick={() => onApply(execution)} className={BUTTON}><Play className="h-3.5 w-3.5" /> Aplicar</button>
        )}
        {execution.status === 'WAITING_FOR_REVIEW' && (
          <>
            <button onClick={() => onReview(execution, 'ACCEPT')} className={BUTTON}><ThumbsUp className="h-3.5 w-3.5" /> Aprovar</button>
            <button onClick={() => onReview(execution, 'REJECT')} className={BUTTON}><ThumbsDown className="h-3.5 w-3.5" /> Rejeitar</button>
          </>
        )}
        {['FAILED', 'VALIDATION_FAILED', 'CANCELLED'].includes(execution.status) && (
          <button onClick={() => onRetry(execution)} className={BUTTON}><RotateCcw className="h-3.5 w-3.5" /> Tentar novamente</button>
        )}
        {['RUNNING', 'WAITING_FOR_REVIEW'].includes(execution.status) && (
          <button onClick={() => onCancel(execution)} className={BUTTON}><X className="h-3.5 w-3.5" /> Cancelar</button>
        )}
      </div>
    </div>
  );
}

export function MissionPlanner() {
  const {
    projectContext,
    missions,
    missionSnapshot,
    getMissions,
    openMission,
    sendMissionOperation,
    plannerState,
    getPlannerState,
  } = useWebSocket();

  // Persist selected mission in sessionStorage
  const [selectedMissionId, setSelectedMissionId] = useState(() => (
    sessionStorage.getItem('jarvis_selected_mission_id') || ''
  ));

  const projectId = projectContext?.project_id ?? '';
  const activeMissionId = missionSnapshot?.mission.mission_id ?? selectedMissionId;

  // Modal States
  const [createMissionOpen, setCreateMissionOpen] = useState(false);
  const [editMissionOpen, setEditMissionOpen] = useState(false);
  const [createWPOpen, setCreateWPOpen] = useState(false);
  const [createDeliverableTarget, setCreateDeliverableTarget] = useState<MissionWorkPackage | null>(null);
  const [addDependencyTarget, setAddDependencyTarget] = useState<MissionWorkPackage | null>(null);
  const [attachEvidenceTarget, setAttachEvidenceTarget] = useState<{ wp: MissionWorkPackage; deliverableId?: string } | null>(null);
  const [createCriterionTarget, setCreateCriterionTarget] = useState<{ ownerType: 'MISSION' | 'WORK_PACKAGE' | 'DELIVERABLE'; ownerId: string } | null>(null);
  const [satisfyCriterionTarget, setSatisfyCriterionTarget] = useState<{ criterion: MissionCriterion; status: 'SATISFIED' | 'FAILED' } | null>(null);
  const [reviewExecutionTarget, setReviewExecutionTarget] = useState<{ execution: MissionExecution; decision: 'ACCEPT' | 'REJECT' } | null>(null);
  const [blockWPTarget, setBlockWPTarget] = useState<{ item: MissionWorkPackage; status: string } | null>(null);
  const [confirmAction, setConfirmAction] = useState<{ title: string; message: string; action: () => void } | null>(null);

  // Form Field States
  const [missionTitle, setMissionTitle] = useState('');
  const [missionObjective, setMissionObjective] = useState('');
  const [missionDescription, setMissionDescription] = useState('');

  const [wpTitle, setWpTitle] = useState('');
  const [wpType, setWpType] = useState('GENERIC');
  const [wpDescription, setWpDescription] = useState('');

  const [delivName, setDelivName] = useState('');
  const [delivKind, setDelivKind] = useState('GENERIC');
  const [delivDescription, setDelivDescription] = useState('');
  const [delivRequired, setDelivRequired] = useState(true);

  const [selectedDepId, setSelectedDepId] = useState('');

  const [evidenceKind, setEvidenceKind] = useState('FILE');
  const [evidenceSourceRef, setEvidenceSourceRef] = useState('');
  const [evidenceDescription, setEvidenceDescription] = useState('');

  const [criterionDescription, setCriterionDescription] = useState('');
  const [criterionEvidenceKinds, setCriterionEvidenceKinds] = useState('');

  const [satisfyEvidenceRefs, setSatisfyEvidenceRefs] = useState('');
  const [satisfyNote, setSatisfyNote] = useState('');

  const [reviewNote, setReviewNote] = useState('');
  const [blockReason, setBlockReason] = useState('');

  useEffect(() => {
    if (activeMissionId) {
      sessionStorage.setItem('jarvis_selected_mission_id', activeMissionId);
    }
  }, [activeMissionId]);

  useEffect(() => {
    if (projectId) {
      getMissions();
      getPlannerState();
    }
  }, [getMissions, getPlannerState, projectId]);

  useEffect(() => {
    if (!missionSnapshot && missions.length > 0 && !selectedMissionId) {
      openMission(missions[0].mission_id);
    }
  }, [missionSnapshot, missions, openMission, selectedMissionId]);

  const workPackageNames = useMemo(
    () => Object.fromEntries((missionSnapshot?.work_packages ?? []).map((item) => [item.work_package_id, item.title])),
    [missionSnapshot?.work_packages],
  );

  const send = (operation: MissionClientOperation) => sendMissionOperation(operation);

  const handleCreateMissionSubmit = () => {
    if (!projectId || !missionTitle.trim() || !missionObjective.trim()) return;
    send({ type: 'mission_create', project_id: projectId, title: missionTitle.trim(), objective: missionObjective.trim(), description: missionDescription.trim() });
    setCreateMissionOpen(false);
    setMissionTitle('');
    setMissionObjective('');
    setMissionDescription('');
  };

  const handleEditMissionSubmit = () => {
    if (!projectId || !missionSnapshot || !missionTitle.trim()) return;
    send({
      type: 'mission_update',
      project_id: projectId,
      mission_id: missionSnapshot.mission.mission_id,
      expected_version: missionSnapshot.mission.version,
      changes: { title: missionTitle.trim(), description: missionDescription.trim() },
    });
    setEditMissionOpen(false);
  };

  const handleCreateWPSubmit = () => {
    if (!projectId || !missionSnapshot || !wpTitle.trim()) return;
    send({
      type: 'work_package_create',
      project_id: projectId,
      mission_id: missionSnapshot.mission.mission_id,
      title: wpTitle.trim(),
      description: wpDescription.trim(),
      work_package_type: wpType,
      executor_kind: wpType,
      required: true,
    });
    setCreateWPOpen(false);
    setWpTitle('');
    setWpDescription('');
    setWpType('GENERIC');
  };

  const handleCreateDeliverableSubmit = () => {
    if (!projectId || !missionSnapshot || !createDeliverableTarget || !delivName.trim()) return;
    send({
      type: 'deliverable_create',
      project_id: projectId,
      mission_id: missionSnapshot.mission.mission_id,
      work_package_id: createDeliverableTarget.work_package_id,
      name: delivName.trim(),
      kind: delivKind || 'GENERIC',
      description: delivDescription.trim(),
      required: delivRequired,
      expected_work_package_version: createDeliverableTarget.version,
    });
    setCreateDeliverableTarget(null);
    setDelivName('');
    setDelivDescription('');
  };

  const handleAddDependencySubmit = () => {
    if (!projectId || !missionSnapshot || !addDependencyTarget || !selectedDepId) return;
    send({
      type: 'work_package_add_dependency',
      project_id: projectId,
      mission_id: missionSnapshot.mission.mission_id,
      work_package_id: addDependencyTarget.work_package_id,
      dependency_id: selectedDepId,
      expected_version: addDependencyTarget.version,
    });
    setAddDependencyTarget(null);
    setSelectedDepId('');
  };

  const handleAttachEvidenceSubmit = () => {
    if (!projectId || !missionSnapshot || !attachEvidenceTarget || !evidenceSourceRef.trim()) return;
    send({
      type: 'evidence_attach',
      project_id: projectId,
      mission_id: missionSnapshot.mission.mission_id,
      work_package_id: attachEvidenceTarget.wp.work_package_id,
      deliverable_id: attachEvidenceTarget.deliverableId,
      kind: evidenceKind || 'FILE',
      source_ref: evidenceSourceRef.trim(),
      description: evidenceDescription.trim(),
    });
    setAttachEvidenceTarget(null);
    setEvidenceSourceRef('');
    setEvidenceDescription('');
  };

  const handleCreateCriterionSubmit = () => {
    if (!projectId || !missionSnapshot || !createCriterionTarget || !criterionDescription.trim()) return;
    const kinds = criterionEvidenceKinds.split(',').map((item) => item.trim()).filter(Boolean);
    send({
      type: 'criterion_create',
      project_id: projectId,
      mission_id: missionSnapshot.mission.mission_id,
      owner_type: createCriterionTarget.ownerType,
      owner_id: createCriterionTarget.ownerId,
      description: criterionDescription.trim(),
      required_evidence_kinds: kinds,
      required: true,
    });
    setCreateCriterionTarget(null);
    setCriterionDescription('');
    setCriterionEvidenceKinds('');
  };

  const handleSatisfyCriterionSubmit = () => {
    if (!projectId || !missionSnapshot || !satisfyCriterionTarget) return;
    const { criterion, status } = satisfyCriterionTarget;
    const refs = status === 'SATISFIED'
      ? satisfyEvidenceRefs.split(',').map((item) => item.trim()).filter(Boolean)
      : [];
    if (status === 'SATISFIED' && refs.length === 0) return;
    send({
      type: 'criterion_set_status',
      project_id: projectId,
      mission_id: missionSnapshot.mission.mission_id,
      criterion_id: criterion.criterion_id,
      expected_version: criterion.version,
      status,
      evidence_refs: refs,
      validation_note: satisfyNote.trim(),
    });
    setSatisfyCriterionTarget(null);
    setSatisfyEvidenceRefs('');
    setSatisfyNote('');
  };

  const handleReviewExecutionSubmit = () => {
    if (!projectId || !missionSnapshot || !reviewExecutionTarget) return;
    const { execution, decision } = reviewExecutionTarget;
    if (decision === 'REJECT' && !reviewNote.trim()) return;
    send({
      type: 'mission_review_execution',
      project_id: projectId,
      mission_id: missionSnapshot.mission.mission_id,
      execution_id: execution.execution_id,
      decision,
      review_note: reviewNote.trim(),
      accepted_evidence_refs: decision === 'ACCEPT' ? execution.evidence_refs : [],
      expected_execution_version: execution.version,
    });
    setReviewExecutionTarget(null);
    setReviewNote('');
  };

  const handleBlockWPSubmit = () => {
    if (!projectId || !missionSnapshot || !blockWPTarget) return;
    const { item, status } = blockWPTarget;
    send({
      type: 'work_package_set_status',
      project_id: projectId,
      mission_id: missionSnapshot.mission.mission_id,
      work_package_id: item.work_package_id,
      expected_version: item.version,
      status,
      blocked_reason: blockReason.trim(),
    });
    setBlockWPTarget(null);
    setBlockReason('');
  };

  const setWorkPackageStatus = (item: MissionWorkPackage, status: string) => {
    if (!projectId || !missionSnapshot || !status) return;
    if (status === 'BLOCKED') {
      setBlockWPTarget({ item, status });
      return;
    }
    send({
      type: 'work_package_set_status',
      project_id: projectId,
      mission_id: missionSnapshot.mission.mission_id,
      work_package_id: item.work_package_id,
      expected_version: item.version,
      status,
    });
  };

  const setDeliverableStatus = (item: MissionDeliverable, status: string) => {
    if (!projectId || !missionSnapshot || !status || status === item.status) return;
    send({
      type: 'deliverable_set_status',
      project_id: projectId,
      mission_id: missionSnapshot.mission.mission_id,
      deliverable_id: item.deliverable_id,
      expected_version: item.version,
      status,
    });
  };

  const executeWorkPackage = (item: MissionWorkPackage) => {
    if (!projectId || !missionSnapshot || missionSnapshot.mission.status !== 'ACTIVE') return;
    send({
      type: 'mission_execute_work_package',
      project_id: projectId,
      mission_id: missionSnapshot.mission.mission_id,
      work_package_id: item.work_package_id,
      expected_mission_version: missionSnapshot.mission.version,
      expected_work_package_version: item.version,
    });
  };

  const applyExecution = (execution: MissionExecution) => {
    if (!projectId || !missionSnapshot) return;
    setConfirmAction({
      title: 'Aplicar Alterações',
      message: 'Confirma a aplicação deste diff e a execução das validações associadas?',
      action: () => {
        send({
          type: 'mission_apply_execution',
          project_id: projectId,
          mission_id: missionSnapshot.mission.mission_id,
          execution_id: execution.execution_id,
          expected_execution_version: execution.version,
          confirmed: true,
        });
      },
    });
  };

  const reviewExecution = (execution: MissionExecution, decision: 'ACCEPT' | 'REJECT') => {
    setReviewExecutionTarget({ execution, decision });
    setReviewNote('');
  };

  const retryExecution = (execution: MissionExecution) => {
    if (!projectId || !missionSnapshot) return;
    send({
      type: 'mission_retry_execution',
      project_id: projectId,
      mission_id: missionSnapshot.mission.mission_id,
      execution_id: execution.execution_id,
      expected_execution_version: execution.version,
    });
  };

  const cancelExecution = (execution: MissionExecution) => {
    if (!projectId || !missionSnapshot) return;
    setConfirmAction({
      title: 'Cancelar Execução',
      message: 'Tem a certeza que pretende cancelar esta execução controlada?',
      action: () => {
        send({
          type: 'mission_cancel_execution',
          project_id: projectId,
          mission_id: missionSnapshot.mission.mission_id,
          execution_id: execution.execution_id,
          expected_execution_version: execution.version,
          confirmed: true,
        });
      },
    });
  };

  if (!projectId) {
    return <div className={`${PANEL} flex h-full items-center justify-center text-sm text-gray-500`}>Selecione um projeto.</div>;
  }

  return (
    <section className={`${PANEL} flex min-h-0 flex-col overflow-hidden`}>
      <div className="flex flex-wrap items-center gap-2 border-b border-white/8 px-3 py-3">
        <Activity className="h-4 w-4 text-cyan-300" />
        <span className="hidden text-sm font-semibold text-gray-200 sm:inline">Missão</span>
        <select
          value={activeMissionId}
          onChange={(event) => { setSelectedMissionId(event.target.value); openMission(event.target.value); }}
          className="h-8 min-w-0 flex-1 rounded-md border border-white/10 bg-[#070a10] px-2 text-xs font-semibold text-gray-200 outline-none"
        >
          <option value="">Missões do projeto</option>
          {missions.map((mission) => <option key={mission.mission_id} value={mission.mission_id}>{mission.title}</option>)}
        </select>
        <button onClick={() => setCreateMissionOpen(true)} className={ICON_BUTTON} title="Criar missão"><Plus className="h-4 w-4" /></button>
        <button onClick={getMissions} className={ICON_BUTTON} title="Atualizar missões"><RefreshCw className="h-4 w-4" /></button>
      </div>

      {!missionSnapshot ? (
        <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-3 p-6 text-center text-sm text-gray-500">
          <Activity className="h-8 w-8 text-gray-600" />
          <p>Nenhuma missão selecionada.</p>
          <button onClick={() => setCreateMissionOpen(true)} className={BUTTON}>
            <Plus className="h-3.5 w-3.5" /> Criar primeira missão
          </button>
        </div>
      ) : (
        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-3">
          <div className={`${SUBTLE} p-3`}>
            <div className="flex items-start gap-3">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-sm font-semibold text-gray-100">{missionSnapshot.mission.title}</h3>
                  <span className="rounded bg-cyan-300/10 px-2 py-0.5 text-[10px] font-semibold text-cyan-100">{statusLabel(missionSnapshot.mission.status)}</span>
                </div>
                <p className="mt-2 text-xs leading-relaxed text-gray-400">{missionSnapshot.mission.objective}</p>
              </div>
              <button
                onClick={() => {
                  setMissionTitle(missionSnapshot.mission.title);
                  setMissionDescription(missionSnapshot.mission.description);
                  setEditMissionOpen(true);
                }}
                className={ICON_BUTTON}
                title="Editar missão"
              >
                <Pencil className="h-3.5 w-3.5" />
              </button>
            </div>
            <div className="mt-3 h-1.5 overflow-hidden rounded bg-white/[0.05]">
              <div className="h-full bg-cyan-300" style={{ width: `${missionSnapshot.mission.progress}%` }} />
            </div>
            <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-[11px] text-gray-500">
              <span>{missionSnapshot.mission.progress}% concluído</span>
              <span>{missionSnapshot.eligible_work_packages.length} elegíveis</span>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {(missionTransitions[missionSnapshot.mission.status] ?? []).map((status) => (
                <button
                  key={status}
                  onClick={() => send({ type: 'mission_set_status', project_id: projectId, mission_id: missionSnapshot.mission.mission_id, expected_version: missionSnapshot.mission.version, status })}
                  className={BUTTON}
                >
                  {status === 'COMPLETED' ? <CheckCircle2 className="h-3.5 w-3.5" /> : <Activity className="h-3.5 w-3.5" />}
                  {statusLabel(status)}
                </button>
              ))}
              <button onClick={() => setCreateCriterionTarget({ ownerType: 'MISSION', ownerId: missionSnapshot.mission.mission_id })} className={BUTTON}>
                <ShieldCheck className="h-3.5 w-3.5" /> Critério
              </button>
            </div>
          </div>

          {missionSnapshot.eligible_work_packages.length > 0 && (
            <div className="rounded-md border border-emerald-300/15 bg-emerald-300/[0.04] p-3 text-xs text-emerald-100">
              <span className="font-semibold">Elegíveis:</span>{' '}
              {missionSnapshot.eligible_work_packages.map((id) => workPackageNames[id] ?? id).join(', ')}
            </div>
          )}

          <div className="flex items-center justify-between gap-3">
            <h4 className="text-xs font-semibold uppercase text-gray-400">Etapas</h4>
            <button onClick={() => setCreateWPOpen(true)} className={BUTTON}><ListPlus className="h-3.5 w-3.5" /> Adicionar</button>
          </div>

          <div className="space-y-3">
            {missionSnapshot.work_packages.length === 0 && (
              <div className="py-12 text-center text-sm text-gray-600">Ainda não existem etapas nesta missão.</div>
            )}
            {missionSnapshot.work_packages.map((item) => {
              const itemDeliverables = missionSnapshot.deliverables.filter((entry) => entry.work_package_id === item.work_package_id);
              const itemCriteria = missionSnapshot.acceptance_criteria.filter((entry) => entry.owner_type === 'WORK_PACKAGE' && entry.owner_id === item.work_package_id);
              const itemEvidence = missionSnapshot.evidence.filter((entry) => entry.work_package_id === item.work_package_id);
              const itemExecutions = missionSnapshot.executions
                .filter((entry) => entry.work_package_id === item.work_package_id)
                .sort((left, right) => left.attempt - right.attempt || left.version - right.version);
              const latestExecution = itemExecutions[itemExecutions.length - 1];
              const executorKind = executorFor(item);
              const executorSupported = supportedExecutors.has(executorKind);
              return (
                <article key={item.work_package_id} className={`${SUBTLE} p-3`}>
                  <div className="flex flex-wrap items-start gap-2">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="rounded bg-white/[0.06] px-2 py-0.5 text-[10px] text-gray-300">{statusLabel(item.status)}</span>
                        {item.required && <span className="text-[10px] text-amber-200">obrigatório</span>}
                        {executorSupported ? (
                          <span className="inline-flex items-center gap-1 rounded border border-cyan-400/20 bg-cyan-500/10 px-2 py-0.5 text-[10px] font-medium text-cyan-300">
                            ⚡ Agente IA
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 rounded border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] font-medium text-gray-400">
                            📋 Manual
                          </span>
                        )}
                      </div>
                      <h5 className="mt-1 text-sm font-semibold text-gray-100">{item.title}</h5>
                    </div>
                    <select
                      value=""
                      onChange={(event) => { setWorkPackageStatus(item, event.target.value); event.target.value = ''; }}
                      className="h-8 rounded-md border border-white/10 bg-[#070a10] px-2 text-[10px] text-gray-300"
                    >
                      <option value="">Alterar estado</option>
                      {(workPackageTransitions[item.status] ?? []).map((status) => <option key={status} value={status}>{statusLabel(status)}</option>)}
                    </select>
                  </div>
                  {item.dependencies.length > 0 && (
                    <p className="mt-2 text-xs text-gray-500"><GitBranch className="mr-1 inline h-3 w-3" />Depende de: {item.dependencies.map((id) => workPackageNames[id] ?? id).join(', ')}</p>
                  )}
                  {item.blocked_reason && <p className="mt-2 text-xs text-amber-200"><CircleAlert className="mr-1 inline h-3 w-3" />{item.blocked_reason}</p>}
                  <div className="mt-3 flex flex-wrap gap-2">
                    {item.status === 'READY' && missionSnapshot.mission.status === 'ACTIVE' && executorSupported && !latestExecution?.lock_owner && (
                      <button onClick={() => executeWorkPackage(item)} className={BUTTON}><Play className="h-3 w-3" /> Executar</button>
                    )}
                    {!executorSupported && (
                      <span className="inline-flex min-h-8 items-center text-[10px] text-gray-500">Execução manual</span>
                    )}
                    <details className="relative">
                      <summary className={`${BUTTON} cursor-pointer list-none`}>Mais ações</summary>
                      <div className="absolute left-0 top-10 z-20 flex min-w-48 flex-col gap-1 rounded-md border border-white/10 bg-[#0b0e15] p-1.5 shadow-xl">
                        <button onClick={() => { setAddDependencyTarget(item); setSelectedDepId(''); }} className="flex items-center gap-2 rounded px-2 py-2 text-left text-xs text-gray-300 hover:bg-white/[0.06]"><GitBranch className="h-3 w-3" /> Dependência</button>
                        <button onClick={() => setCreateDeliverableTarget(item)} className="flex items-center gap-2 rounded px-2 py-2 text-left text-xs text-gray-300 hover:bg-white/[0.06]"><FileCheck2 className="h-3 w-3" /> Entrega</button>
                        <button onClick={() => setAttachEvidenceTarget({ wp: item })} className="flex items-center gap-2 rounded px-2 py-2 text-left text-xs text-gray-300 hover:bg-white/[0.06]"><Link2 className="h-3 w-3" /> Evidência</button>
                        <button onClick={() => setCreateCriterionTarget({ ownerType: 'WORK_PACKAGE', ownerId: item.work_package_id })} className="flex items-center gap-2 rounded px-2 py-2 text-left text-xs text-gray-300 hover:bg-white/[0.06]"><ShieldCheck className="h-3 w-3" /> Critério</button>
                      </div>
                    </details>
                  </div>

                  {itemDeliverables.length > 0 && (
                    <div className="mt-3 space-y-2 border-l border-violet-300/15 pl-3">
                      {itemDeliverables.map((deliverable) => (
                        <div key={deliverable.deliverable_id} className="flex flex-wrap items-center gap-2 text-xs">
                          <FileCheck2 className="h-3.5 w-3.5 text-violet-300" />
                          <span className="min-w-0 flex-1 text-gray-200">{deliverable.name} <span className="text-gray-600">({deliverable.kind})</span></span>
                          <select
                            value={deliverable.status}
                            onChange={(event) => setDeliverableStatus(deliverable, event.target.value)}
                            className="h-7 rounded border border-white/10 bg-[#070a10] px-1 text-[10px] text-gray-300"
                          >
                            {deliverableStates.map((status) => <option key={status} value={status}>{statusLabel(status)}</option>)}
                          </select>
                          <button onClick={() => setAttachEvidenceTarget({ wp: item, deliverableId: deliverable.deliverable_id })} className={ICON_BUTTON} title="Anexar Evidence"><Link2 className="h-3 w-3" /></button>
                          <button onClick={() => setCreateCriterionTarget({ ownerType: 'DELIVERABLE', ownerId: deliverable.deliverable_id })} className={ICON_BUTTON} title="Adicionar critério"><ShieldCheck className="h-3 w-3" /></button>
                        </div>
                      ))}
                    </div>
                  )}

                  {itemCriteria.length > 0 && (
                    <div className="mt-3 space-y-2">
                      {itemCriteria.map((criterion) => (
                        <div key={criterion.criterion_id} className="flex flex-wrap items-center gap-2 text-xs text-gray-400">
                          <ShieldCheck className={criterion.status === 'SATISFIED' ? 'h-3.5 w-3.5 text-emerald-300' : 'h-3.5 w-3.5 text-amber-300'} />
                          <span className="min-w-0 flex-1">{criterion.description}</span>
                          <span className="text-[10px]">{criterion.status}</span>
                          {criterion.status !== 'SATISFIED' && (
                            <button onClick={() => { setSatisfyCriterionTarget({ criterion, status: 'SATISFIED' }); setSatisfyEvidenceRefs(''); setSatisfyNote(''); }} className={BUTTON}>Satisfazer</button>
                          )}
                          {criterion.status === 'PENDING' && (
                            <button onClick={() => { setSatisfyCriterionTarget({ criterion, status: 'FAILED' }); setSatisfyNote(''); }} className={BUTTON}>Falhar</button>
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  {itemEvidence.length > 0 && (
                    <div className="mt-3 space-y-1 text-[11px] text-gray-500">
                      {itemEvidence.map((entry) => <p key={entry.evidence_id}><Link2 className="mr-1 inline h-3 w-3" /><code>{entry.evidence_id}</code> · {entry.kind} · {entry.source_ref}</p>)}
                    </div>
                  )}

                  {latestExecution && (
                    <ExecutionDetails
                      execution={latestExecution}
                      onApply={applyExecution}
                      onReview={reviewExecution}
                      onRetry={retryExecution}
                      onCancel={cancelExecution}
                    />
                  )}
                </article>
              );
            })}
          </div>

          <details className={`${SUBTLE} p-3`}>
            <summary className="cursor-pointer text-xs font-semibold text-gray-400">Histórico recente</summary>
            <div className="mt-2 max-h-40 space-y-1 overflow-y-auto text-[11px] text-gray-500">
              {missionSnapshot.recent_events.length === 0 ? <p>Sem eventos.</p> : missionSnapshot.recent_events.slice().reverse().map((event) => (
                <p key={event.event_id}><span className="text-gray-300">{event.event_type}</span> · {event.entity_type}:{event.entity_id}</p>
              ))}
            </div>
          </details>

          {plannerState && (
            <div className={`${SUBTLE} hidden p-3 text-xs text-gray-500`} aria-hidden="true">
              <div className="mb-2 flex items-center gap-2">
                <Activity className="h-3.5 w-3.5 text-gray-400" />
                <span className="font-semibold text-gray-300">Plano legado · apenas leitura</span>
              </div>
              <p>{plannerState.goal}</p>
              <p className="mt-1">{plannerState.steps?.length ?? 0} passos · {plannerState.status || 'sem estado'}</p>
            </div>
          )}
        </div>
      )}

      {/* --- REACT MODALS REPLACING WINDOW.PROMPT / WINDOW.CONFIRM --- */}

      {/* Create Mission Modal */}
      <Modal
        isOpen={createMissionOpen}
        onClose={() => setCreateMissionOpen(false)}
        title="Criar Nova Missão"
        footer={(
          <>
            <button onClick={() => setCreateMissionOpen(false)} className={BUTTON}>Cancelar</button>
            <button onClick={handleCreateMissionSubmit} disabled={!missionTitle.trim() || !missionObjective.trim()} className={`${BUTTON} bg-cyan-400/20 text-cyan-100 hover:bg-cyan-400/30`}>Criar Missão</button>
          </>
        )}
      >
        <div className="space-y-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-300">Título da missão *</label>
            <input value={missionTitle} onChange={(e) => setMissionTitle(e.target.value)} placeholder="Ex: Refatorar autenticação" className={INPUT_CLASS} autoFocus />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-300">Objetivo verificável *</label>
            <textarea value={missionObjective} onChange={(e) => setMissionObjective(e.target.value)} placeholder="Ex: Adicionar suporte JWT com testes unitários passando" className={`${INPUT_CLASS} h-20 resize-none`} />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-300">Descrição</label>
            <textarea value={missionDescription} onChange={(e) => setMissionDescription(e.target.value)} placeholder="Detalhes adicionais sobre o contexto..." className={`${INPUT_CLASS} h-16 resize-none`} />
          </div>
        </div>
      </Modal>

      {/* Edit Mission Modal */}
      <Modal
        isOpen={editMissionOpen}
        onClose={() => setEditMissionOpen(false)}
        title="Editar Missão"
        footer={(
          <>
            <button onClick={() => setEditMissionOpen(false)} className={BUTTON}>Cancelar</button>
            <button onClick={handleEditMissionSubmit} disabled={!missionTitle.trim()} className={`${BUTTON} bg-cyan-400/20 text-cyan-100 hover:bg-cyan-400/30`}>Guardar Alterações</button>
          </>
        )}
      >
        <div className="space-y-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-300">Título *</label>
            <input value={missionTitle} onChange={(e) => setMissionTitle(e.target.value)} className={INPUT_CLASS} />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-300">Descrição</label>
            <textarea value={missionDescription} onChange={(e) => setMissionDescription(e.target.value)} className={`${INPUT_CLASS} h-24 resize-none`} />
          </div>
        </div>
      </Modal>

      {/* Create Work Package Modal */}
      <Modal
        isOpen={createWPOpen}
        onClose={() => setCreateWPOpen(false)}
        title="Adicionar Etapa (Work Package)"
        footer={(
          <>
            <button onClick={() => setCreateWPOpen(false)} className={BUTTON}>Cancelar</button>
            <button onClick={handleCreateWPSubmit} disabled={!wpTitle.trim()} className={`${BUTTON} bg-cyan-400/20 text-cyan-100 hover:bg-cyan-400/30`}>Adicionar Etapa</button>
          </>
        )}
      >
        <div className="space-y-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-300">Título da etapa *</label>
            <input value={wpTitle} onChange={(e) => setWpTitle(e.target.value)} placeholder="Ex: Implementar rotas API" className={INPUT_CLASS} autoFocus />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-300">Tipo de etapa</label>
            <select value={wpType} onChange={(e) => setWpType(e.target.value)} className={INPUT_CLASS}>
              {workPackageTypes.map((type) => <option key={type} value={type}>{type}</option>)}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-300">Descrição</label>
            <textarea value={wpDescription} onChange={(e) => setWpDescription(e.target.value)} placeholder="Instruções para o executor..." className={`${INPUT_CLASS} h-20 resize-none`} />
          </div>
        </div>
      </Modal>

      {/* Create Deliverable Modal */}
      <Modal
        isOpen={Boolean(createDeliverableTarget)}
        onClose={() => setCreateDeliverableTarget(null)}
        title="Criar Entrega (Deliverable)"
        footer={(
          <>
            <button onClick={() => setCreateDeliverableTarget(null)} className={BUTTON}>Cancelar</button>
            <button onClick={handleCreateDeliverableSubmit} disabled={!delivName.trim()} className={`${BUTTON} bg-cyan-400/20 text-cyan-100 hover:bg-cyan-400/30`}>Criar Entrega</button>
          </>
        )}
      >
        <div className="space-y-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-300">Nome da entrega *</label>
            <input value={delivName} onChange={(e) => setDelivName(e.target.value)} placeholder="Ex: auth_controller.ts" className={INPUT_CLASS} autoFocus />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-300">Tipo</label>
            <input value={delivKind} onChange={(e) => setDelivKind(e.target.value)} placeholder="FILE, DOCUMENT, etc." className={INPUT_CLASS} />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-300">Descrição</label>
            <textarea value={delivDescription} onChange={(e) => setDelivDescription(e.target.value)} className={`${INPUT_CLASS} h-16 resize-none`} />
          </div>
          <label className="flex items-center gap-2 text-xs text-gray-300">
            <input type="checkbox" checked={delivRequired} onChange={(e) => setDelivRequired(e.target.checked)} className="rounded border-white/10 bg-black/40" />
            Entrega obrigatória para concluir a etapa
          </label>
        </div>
      </Modal>

      {/* Add Dependency Modal */}
      <Modal
        isOpen={Boolean(addDependencyTarget)}
        onClose={() => setAddDependencyTarget(null)}
        title="Adicionar Dependência"
        footer={(
          <>
            <button onClick={() => setAddDependencyTarget(null)} className={BUTTON}>Cancelar</button>
            <button onClick={handleAddDependencySubmit} disabled={!selectedDepId} className={`${BUTTON} bg-cyan-400/20 text-cyan-100 hover:bg-cyan-400/30`}>Adicionar</button>
          </>
        )}
      >
        <div className="space-y-3">
          <p className="text-xs text-gray-400">Selecione a etapa da qual <span className="font-semibold text-gray-200">{addDependencyTarget?.title}</span> depende:</p>
          <select value={selectedDepId} onChange={(e) => setSelectedDepId(e.target.value)} className={INPUT_CLASS}>
            <option value="">Selecione uma etapa</option>
            {missionSnapshot?.work_packages
              .filter((wp) => wp.work_package_id !== addDependencyTarget?.work_package_id && !addDependencyTarget?.dependencies.includes(wp.work_package_id))
              .map((wp) => <option key={wp.work_package_id} value={wp.work_package_id}>{wp.title} ({wp.work_package_id})</option>)}
          </select>
        </div>
      </Modal>

      {/* Attach Evidence Modal */}
      <Modal
        isOpen={Boolean(attachEvidenceTarget)}
        onClose={() => setAttachEvidenceTarget(null)}
        title="Anexar Evidência"
        footer={(
          <>
            <button onClick={() => setAttachEvidenceTarget(null)} className={BUTTON}>Cancelar</button>
            <button onClick={handleAttachEvidenceSubmit} disabled={!evidenceSourceRef.trim()} className={`${BUTTON} bg-cyan-400/20 text-cyan-100 hover:bg-cyan-400/30`}>Anexar</button>
          </>
        )}
      >
        <div className="space-y-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-300">Tipo de Evidência</label>
            <select value={evidenceKind} onChange={(e) => setEvidenceKind(e.target.value)} className={INPUT_CLASS}>
              <option value="FILE">FILE</option>
              <option value="CODING_SESSION">CODING_SESSION</option>
              <option value="PROJECT_CONTEXT">PROJECT_CONTEXT</option>
              <option value="OBSIDIAN">OBSIDIAN</option>
              <option value="VALIDATION">VALIDATION</option>
              <option value="EXPERIMENT">EXPERIMENT</option>
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-300">Referência (Source Ref) *</label>
            <input value={evidenceSourceRef} onChange={(e) => setEvidenceSourceRef(e.target.value)} placeholder="Ex: file:src/index.ts ou validation:build" className={INPUT_CLASS} autoFocus />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-300">Descrição</label>
            <textarea value={evidenceDescription} onChange={(e) => setEvidenceDescription(e.target.value)} className={`${INPUT_CLASS} h-16 resize-none`} />
          </div>
        </div>
      </Modal>

      {/* Create Criterion Modal */}
      <Modal
        isOpen={Boolean(createCriterionTarget)}
        onClose={() => setCreateCriterionTarget(null)}
        title="Criar Critério de Aceitação"
        footer={(
          <>
            <button onClick={() => setCreateCriterionTarget(null)} className={BUTTON}>Cancelar</button>
            <button onClick={handleCreateCriterionSubmit} disabled={!criterionDescription.trim()} className={`${BUTTON} bg-cyan-400/20 text-cyan-100 hover:bg-cyan-400/30`}>Criar Critério</button>
          </>
        )}
      >
        <div className="space-y-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-300">Descrição do critério *</label>
            <textarea value={criterionDescription} onChange={(e) => setCriterionDescription(e.target.value)} placeholder="Ex: Todos os testes unitários da auth devem passar com exit status 0" className={`${INPUT_CLASS} h-20 resize-none`} autoFocus />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-300">Kinds de evidência exigidos (separados por vírgula)</label>
            <input value={criterionEvidenceKinds} onChange={(e) => setCriterionEvidenceKinds(e.target.value)} placeholder="Ex: FILE, VALIDATION" className={INPUT_CLASS} />
          </div>
        </div>
      </Modal>

      {/* Satisfy Criterion Modal */}
      <Modal
        isOpen={Boolean(satisfyCriterionTarget)}
        onClose={() => setSatisfyCriterionTarget(null)}
        title={satisfyCriterionTarget?.status === 'SATISFIED' ? 'Satisfazer Critério' : 'Marcar Critério como Falhado'}
        footer={(
          <>
            <button onClick={() => setSatisfyCriterionTarget(null)} className={BUTTON}>Cancelar</button>
            <button
              onClick={handleSatisfyCriterionSubmit}
              disabled={satisfyCriterionTarget?.status === 'SATISFIED' && !satisfyEvidenceRefs.trim()}
              className={`${BUTTON} ${satisfyCriterionTarget?.status === 'SATISFIED' ? 'bg-emerald-400/20 text-emerald-100 hover:bg-emerald-400/30' : 'bg-rose-400/20 text-rose-100 hover:bg-rose-400/30'}`}
            >
              Confirmar
            </button>
          </>
        )}
      >
        <div className="space-y-3">
          {satisfyCriterionTarget?.status === 'SATISFIED' && (
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-300">IDs de Evidência (separados por vírgula) *</label>
              <input value={satisfyEvidenceRefs} onChange={(e) => setSatisfyEvidenceRefs(e.target.value)} placeholder="Ex: ev_123, ev_456" className={INPUT_CLASS} autoFocus />
            </div>
          )}
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-300">Nota de Validação</label>
            <textarea value={satisfyNote} onChange={(e) => setSatisfyNote(e.target.value)} placeholder="Observações adicionais..." className={`${INPUT_CLASS} h-16 resize-none`} />
          </div>
        </div>
      </Modal>

      {/* Review Execution Modal */}
      <Modal
        isOpen={Boolean(reviewExecutionTarget)}
        onClose={() => setReviewExecutionTarget(null)}
        title={reviewExecutionTarget?.decision === 'ACCEPT' ? 'Aprovar Execução' : 'Rejeitar Execução'}
        footer={(
          <>
            <button onClick={() => setReviewExecutionTarget(null)} className={BUTTON}>Cancelar</button>
            <button
              onClick={handleReviewExecutionSubmit}
              disabled={reviewExecutionTarget?.decision === 'REJECT' && !reviewNote.trim()}
              className={`${BUTTON} ${reviewExecutionTarget?.decision === 'ACCEPT' ? 'bg-emerald-400/20 text-emerald-100 hover:bg-emerald-400/30' : 'bg-rose-400/20 text-rose-100 hover:bg-rose-400/30'}`}
            >
              Submeter Revisão
            </button>
          </>
        )}
      >
        <div className="space-y-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-300">
              {reviewExecutionTarget?.decision === 'ACCEPT' ? 'Nota de aprovação' : 'Motivo da rejeição *'}
            </label>
            <textarea value={reviewNote} onChange={(e) => setReviewNote(e.target.value)} placeholder={reviewExecutionTarget?.decision === 'ACCEPT' ? 'Aprovado com sucesso...' : 'Especifique o erro ou motivo da rejeição...'} className={`${INPUT_CLASS} h-20 resize-none`} autoFocus />
          </div>
        </div>
      </Modal>

      {/* Block Work Package Modal */}
      <Modal
        isOpen={Boolean(blockWPTarget)}
        onClose={() => setBlockWPTarget(null)}
        title="Bloquear Etapa"
        footer={(
          <>
            <button onClick={() => setBlockWPTarget(null)} className={BUTTON}>Cancelar</button>
            <button onClick={handleBlockWPSubmit} className={`${BUTTON} bg-amber-400/20 text-amber-100 hover:bg-amber-400/30`}>Bloquear</button>
          </>
        )}
      >
        <div className="space-y-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-300">Motivo do bloqueio</label>
            <textarea value={blockReason} onChange={(e) => setBlockReason(e.target.value)} placeholder="Descreva o motivo do bloqueio..." className={`${INPUT_CLASS} h-20 resize-none`} autoFocus />
          </div>
        </div>
      </Modal>

      {/* Confirm Action Modal */}
      <Modal
        isOpen={Boolean(confirmAction)}
        onClose={() => setConfirmAction(null)}
        title={confirmAction?.title ?? 'Confirmação'}
        footer={(
          <>
            <button onClick={() => setConfirmAction(null)} className={BUTTON}>Cancelar</button>
            <button
              onClick={() => {
                confirmAction?.action();
                setConfirmAction(null);
              }}
              className={`${BUTTON} bg-cyan-400/20 text-cyan-100 hover:bg-cyan-400/30`}
            >
              Confirmar
            </button>
          </>
        )}
      >
        <p className="text-xs leading-relaxed text-gray-300">{confirmAction?.message}</p>
      </Modal>
    </section>
  );
}
