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
import type { MissionClientOperation, MissionCriterion, MissionDeliverable, MissionExecution, MissionWorkPackage } from '../../protocol/websocket';

const PANEL = 'rounded-md border border-white/8 bg-[#090d14]';
const SUBTLE = 'rounded-md border border-white/8 bg-black/20';
const BUTTON = 'inline-flex min-h-8 items-center justify-center gap-2 rounded-md border border-white/10 bg-white/[0.04] px-2.5 text-xs font-semibold text-gray-200 transition hover:bg-white/[0.08] disabled:cursor-not-allowed disabled:opacity-40';
const ICON_BUTTON = 'inline-flex h-8 w-8 items-center justify-center rounded-md border border-white/10 bg-white/[0.04] text-gray-300 transition hover:bg-white/[0.08] hover:text-white disabled:opacity-40';

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

const ask = (label: string, initial = '') => window.prompt(label, initial)?.trim() ?? '';
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
        <span className="rounded bg-white/[0.06] px-2 py-0.5 text-gray-300">{execution.status}</span>
        <span className="text-gray-600">tentativa {execution.attempt} · v{execution.version}</span>
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
        <p className="break-all text-[11px] text-gray-500">Evidence: {execution.evidence_refs.join(', ')}</p>
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
  const [selectedMissionId, setSelectedMissionId] = useState('');
  const projectId = projectContext?.project_id ?? '';
  const activeMissionId = missionSnapshot?.mission.mission_id ?? selectedMissionId;

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

  const createMission = () => {
    if (!projectId) return;
    const title = ask('Título da missão');
    if (!title) return;
    const objective = ask('Objetivo verificável da missão');
    if (!objective) return;
    const description = ask('Descrição', '');
    send({ type: 'mission_create', project_id: projectId, title, objective, description });
  };

  const editMission = () => {
    if (!projectId || !missionSnapshot) return;
    const title = ask('Título da missão', missionSnapshot.mission.title);
    if (!title) return;
    const description = ask('Descrição', missionSnapshot.mission.description);
    send({
      type: 'mission_update',
      project_id: projectId,
      mission_id: missionSnapshot.mission.mission_id,
      expected_version: missionSnapshot.mission.version,
      changes: { title, description },
    });
  };

  const createWorkPackage = () => {
    if (!projectId || !missionSnapshot) return;
    const title = ask('Título do WorkPackage');
    if (!title) return;
    const requestedType = ask(`Tipo: ${workPackageTypes.join(', ')}`, 'GENERIC').toUpperCase();
    const workPackageType = workPackageTypes.includes(requestedType) ? requestedType : 'GENERIC';
    send({
      type: 'work_package_create',
      project_id: projectId,
      mission_id: missionSnapshot.mission.mission_id,
      title,
      description: ask('Descrição', ''),
      work_package_type: workPackageType,
      executor_kind: workPackageType,
      required: true,
    });
  };

  const addDependency = (item: MissionWorkPackage) => {
    if (!projectId || !missionSnapshot) return;
    const dependencyId = ask('ID do WorkPackage do qual este depende');
    if (!dependencyId) return;
    send({
      type: 'work_package_add_dependency',
      project_id: projectId,
      mission_id: missionSnapshot.mission.mission_id,
      work_package_id: item.work_package_id,
      dependency_id: dependencyId,
      expected_version: item.version,
    });
  };

  const createDeliverable = (item: MissionWorkPackage) => {
    if (!projectId || !missionSnapshot) return;
    const name = ask('Nome do Deliverable');
    if (!name) return;
    send({
      type: 'deliverable_create',
      project_id: projectId,
      mission_id: missionSnapshot.mission.mission_id,
      work_package_id: item.work_package_id,
      name,
      kind: ask('Kind extensível', 'GENERIC') || 'GENERIC',
      description: ask('Descrição', ''),
      required: window.confirm('Este Deliverable é obrigatório para concluir o WorkPackage?'),
      expected_work_package_version: item.version,
    });
  };

  const attachEvidence = (item: MissionWorkPackage, deliverableId?: string) => {
    if (!projectId || !missionSnapshot) return;
    const sourceRef = ask('Referência: file:, coding_session:, project_context:, obsidian:, validation:, source: ou experiment:');
    if (!sourceRef) return;
    send({
      type: 'evidence_attach',
      project_id: projectId,
      mission_id: missionSnapshot.mission.mission_id,
      work_package_id: item.work_package_id,
      deliverable_id: deliverableId,
      kind: ask('Kind da evidência', 'FILE') || 'FILE',
      source_ref: sourceRef,
      description: ask('Descrição da evidência', ''),
    });
  };

  const createCriterion = (ownerType: 'MISSION' | 'WORK_PACKAGE' | 'DELIVERABLE', ownerId: string) => {
    if (!projectId || !missionSnapshot) return;
    const description = ask('Critério de aceitação verificável');
    if (!description) return;
    const kinds = ask('Kinds de evidência exigidos, separados por vírgula', '')
      .split(',').map((item) => item.trim()).filter(Boolean);
    send({
      type: 'criterion_create',
      project_id: projectId,
      mission_id: missionSnapshot.mission.mission_id,
      owner_type: ownerType,
      owner_id: ownerId,
      description,
      required_evidence_kinds: kinds,
      required: true,
    });
  };

  const satisfyCriterion = (criterion: MissionCriterion, status: 'SATISFIED' | 'FAILED') => {
    if (!projectId || !missionSnapshot) return;
    const evidenceRefs = status === 'SATISFIED'
      ? ask('IDs de Evidence, separados por vírgula').split(',').map((item) => item.trim()).filter(Boolean)
      : [];
    if (status === 'SATISFIED' && evidenceRefs.length === 0) return;
    send({
      type: 'criterion_set_status',
      project_id: projectId,
      mission_id: missionSnapshot.mission.mission_id,
      criterion_id: criterion.criterion_id,
      expected_version: criterion.version,
      status,
      evidence_refs: evidenceRefs,
      validation_note: ask('Nota de validação', ''),
    });
  };

  const setWorkPackageStatus = (item: MissionWorkPackage, status: string) => {
    if (!projectId || !missionSnapshot || !status) return;
    send({
      type: 'work_package_set_status',
      project_id: projectId,
      mission_id: missionSnapshot.mission.mission_id,
      work_package_id: item.work_package_id,
      expected_version: item.version,
      status,
      blocked_reason: status === 'BLOCKED' ? ask('Motivo do bloqueio', '') : undefined,
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
    if (!projectId || !missionSnapshot || !window.confirm('Aplicar este diff e executar as validações?')) return;
    send({
      type: 'mission_apply_execution',
      project_id: projectId,
      mission_id: missionSnapshot.mission.mission_id,
      execution_id: execution.execution_id,
      expected_execution_version: execution.version,
      confirmed: true,
    });
  };

  const reviewExecution = (execution: MissionExecution, decision: 'ACCEPT' | 'REJECT') => {
    if (!projectId || !missionSnapshot) return;
    const reviewNote = ask(decision === 'ACCEPT' ? 'Nota de aprovação' : 'Motivo da rejeição');
    if (decision === 'REJECT' && !reviewNote) return;
    send({
      type: 'mission_review_execution',
      project_id: projectId,
      mission_id: missionSnapshot.mission.mission_id,
      execution_id: execution.execution_id,
      decision,
      review_note: reviewNote,
      accepted_evidence_refs: decision === 'ACCEPT' ? execution.evidence_refs : [],
      expected_execution_version: execution.version,
    });
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
    if (!projectId || !missionSnapshot || !window.confirm('Cancelar esta execução controlada?')) return;
    send({
      type: 'mission_cancel_execution',
      project_id: projectId,
      mission_id: missionSnapshot.mission.mission_id,
      execution_id: execution.execution_id,
      expected_execution_version: execution.version,
      confirmed: true,
    });
  };

  if (!projectId) {
    return <div className={`${PANEL} flex h-full items-center justify-center text-sm text-gray-500`}>Selecione um projeto.</div>;
  }

  return (
    <section className={`${PANEL} flex min-h-0 flex-col overflow-hidden`}>
      <div className="flex flex-wrap items-center gap-2 border-b border-white/8 px-3 py-3">
        <Activity className="h-4 w-4 text-cyan-300" />
        <select
          value={activeMissionId}
          onChange={(event) => { setSelectedMissionId(event.target.value); openMission(event.target.value); }}
          className="h-8 min-w-0 flex-1 rounded-md border border-white/10 bg-[#070a10] px-2 text-xs font-semibold text-gray-200 outline-none"
        >
          <option value="">Missões do projeto</option>
          {missions.map((mission) => <option key={mission.mission_id} value={mission.mission_id}>{mission.title}</option>)}
        </select>
        <button onClick={createMission} className={ICON_BUTTON} title="Criar missão"><Plus className="h-4 w-4" /></button>
        <button onClick={getMissions} className={ICON_BUTTON} title="Atualizar missões"><RefreshCw className="h-4 w-4" /></button>
      </div>

      {!missionSnapshot ? (
        <div className="flex min-h-0 flex-1 items-center justify-center p-6 text-sm text-gray-500">Nenhuma missão selecionada.</div>
      ) : (
        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-3">
          <div className={`${SUBTLE} p-3`}>
            <div className="flex items-start gap-3">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-sm font-semibold text-gray-100">{missionSnapshot.mission.title}</h3>
                  <span className="rounded bg-cyan-300/10 px-2 py-0.5 text-[10px] font-semibold text-cyan-100">{missionSnapshot.mission.status}</span>
                  <span className="text-[10px] text-gray-600">v{missionSnapshot.mission.version}</span>
                </div>
                <p className="mt-2 text-xs leading-relaxed text-gray-400">{missionSnapshot.mission.objective}</p>
              </div>
              <button onClick={editMission} className={ICON_BUTTON} title="Editar missão"><Pencil className="h-3.5 w-3.5" /></button>
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
                  {status}
                </button>
              ))}
              <button onClick={() => createCriterion('MISSION', missionSnapshot.mission.mission_id)} className={BUTTON}>
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

          <div className="rounded-md border border-amber-300/15 bg-amber-300/[0.04] p-3 text-xs text-amber-100">
            Execução controlada e manual: apenas um WorkPackage é iniciado de cada vez. Não existe execução autónoma da missão.
          </div>

          <div className="flex items-center justify-between gap-3">
            <h4 className="text-xs font-semibold uppercase text-gray-400">WorkPackages</h4>
            <button onClick={createWorkPackage} className={BUTTON}><ListPlus className="h-3.5 w-3.5" /> Adicionar</button>
          </div>

          <div className="space-y-3">
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
                        <span className="text-[10px] font-semibold text-violet-200">{item.type}</span>
                        <span className="rounded bg-white/[0.06] px-2 py-0.5 text-[10px] text-gray-300">{item.status}</span>
                        {item.required && <span className="text-[10px] text-amber-200">obrigatório</span>}
                      </div>
                      <h5 className="mt-1 text-sm font-semibold text-gray-100">{item.title}</h5>
                      <code className="mt-1 block break-all text-[10px] text-gray-600">{item.work_package_id}</code>
                    </div>
                    <select
                      value=""
                      onChange={(event) => { setWorkPackageStatus(item, event.target.value); event.target.value = ''; }}
                      className="h-8 rounded-md border border-white/10 bg-[#070a10] px-2 text-[10px] text-gray-300"
                    >
                      <option value="">Alterar estado</option>
                      {(workPackageTransitions[item.status] ?? []).map((status) => <option key={status} value={status}>{status}</option>)}
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
                    <span className="inline-flex min-h-8 items-center text-[10px] text-gray-500">
                      Executor: {executorKind}{executorSupported ? '' : ' · indisponível'}
                    </span>
                    <button onClick={() => addDependency(item)} className={BUTTON}><GitBranch className="h-3 w-3" /> Dependência</button>
                    <button onClick={() => createDeliverable(item)} className={BUTTON}><FileCheck2 className="h-3 w-3" /> Deliverable</button>
                    <button onClick={() => attachEvidence(item)} className={BUTTON}><Link2 className="h-3 w-3" /> Evidence</button>
                    <button onClick={() => createCriterion('WORK_PACKAGE', item.work_package_id)} className={BUTTON}><ShieldCheck className="h-3 w-3" /> Critério</button>
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
                            {deliverableStates.map((status) => <option key={status} value={status}>{status}</option>)}
                          </select>
                          <button onClick={() => attachEvidence(item, deliverable.deliverable_id)} className={ICON_BUTTON} title="Anexar Evidence"><Link2 className="h-3 w-3" /></button>
                          <button onClick={() => createCriterion('DELIVERABLE', deliverable.deliverable_id)} className={ICON_BUTTON} title="Adicionar critério"><ShieldCheck className="h-3 w-3" /></button>
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
                          {criterion.status !== 'SATISFIED' && <button onClick={() => satisfyCriterion(criterion, 'SATISFIED')} className={BUTTON}>Satisfazer</button>}
                          {criterion.status === 'PENDING' && <button onClick={() => satisfyCriterion(criterion, 'FAILED')} className={BUTTON}>Falhar</button>}
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

          <div className={`${SUBTLE} p-3`}>
            <h4 className="mb-2 text-xs font-semibold uppercase text-gray-400">Eventos recentes</h4>
            <div className="max-h-40 space-y-1 overflow-y-auto text-[11px] text-gray-500">
              {missionSnapshot.recent_events.length === 0 ? <p>Sem eventos.</p> : missionSnapshot.recent_events.slice().reverse().map((event) => (
                <p key={event.event_id}><span className="text-gray-300">{event.event_type}</span> · {event.entity_type}:{event.entity_id} · v{event.previous_version}→v{event.new_version}</p>
              ))}
            </div>
          </div>

          {plannerState && (
            <div className={`${SUBTLE} p-3 text-xs text-gray-500`}>
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
    </section>
  );
}
