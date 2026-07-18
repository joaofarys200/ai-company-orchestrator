export type SystemStatus = 'ONLINE' | 'PROCESSING' | 'OFFLINE';
export type RuntimeState = 'idle' | 'processing' | string;
export type KanbanColumn = 'backlog' | 'progress' | 'review' | 'done';
export type UiAction =
  | 'open_chat'
  | 'close_chat'
  | 'toggle_chat'
  | 'open_dev'
  | 'close_dev'
  | 'toggle_dev'
  | 'show_dashboard'
  | 'show_arena_tab'
  | 'show_main_screen'
  | string;

export interface Agent {
  id: string;
  name: string;
  role: string;
  icon: string;
}

export interface Task {
  id: string;
  title: string;
  agent: string;
}

export interface TemplateSuggestion {
  label: string;
  prompt: string;
}

export interface ActiveTemplate {
  template_name: string;
  name: string;
  description: string;
  suggestions: TemplateSuggestion[];
  agents: Agent[];
}

export interface ChatMessage {
  id: string;
  sender: string;
  role: string;
  content: string;
  audio?: string;
  timestamp: string;
}

export interface KanbanCard {
  id: string;
  title: string;
  agent: string;
}

export interface KanbanState {
  backlog: KanbanCard[];
  progress: KanbanCard[];
  review: KanbanCard[];
  done: KanbanCard[];
}

export interface ArenaModelData {
  status: string;
  content: string;
  time: number | string;
  tokens: number | string;
}

export interface ArenaState {
  gemini: ArenaModelData;
  groq: ArenaModelData;
  qwen: ArenaModelData;
  claude: ArenaModelData;
}

export interface RuleMemory {
  rule_key: string;
  description: string;
  correction: string;
}

export interface ArchitectureMemory {
  module: string;
  purpose?: string;
  dependencies?: string;
  constraints?: string;
}

export interface EngineeringDecision {
  decision: string;
  reason: string;
  impact?: string;
}

export interface PlannerStep {
  id: number | string;
  action: string;
  status: string;
}

export interface PlannerState {
  goal: string;
  steps?: PlannerStep[];
  status?: string;
}

export interface MissionData {
  mission_id: string;
  project_id: string;
  title: string;
  objective: string;
  description: string;
  status: string;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  completed_at: string | null;
  current_phase: string;
  progress: number;
  metadata: Record<string, unknown>;
  version: number;
}

export interface MissionWorkPackage {
  work_package_id: string;
  mission_id: string;
  title: string;
  description: string;
  type: string;
  status: string;
  stored_status?: string;
  priority: number;
  dependencies: string[];
  acceptance_criteria: string[];
  required_deliverables: string[];
  executor_kind: string;
  executor_ref: string;
  blocked_reason: string;
  required: boolean;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface MissionDeliverable {
  deliverable_id: string;
  mission_id: string;
  work_package_id: string;
  name: string;
  description: string;
  kind: string;
  status: string;
  artifact_refs: string[];
  acceptance_criteria: string[];
  evidence_refs: string[];
  version: number;
  created_at: string;
  updated_at: string;
}

export interface MissionEvidence {
  evidence_id: string;
  mission_id: string;
  work_package_id: string;
  deliverable_id: string | null;
  kind: string;
  source_ref: string;
  description: string;
  content_hash: string | null;
  version: number;
  created_at: string;
}

export interface MissionCriterion {
  criterion_id: string;
  mission_id: string;
  owner_type: string;
  owner_id: string;
  description: string;
  status: string;
  required_evidence_kinds: string[];
  evidence_refs: string[];
  validated_at: string | null;
  validation_note: string;
  required: boolean;
  version: number;
}

export interface MissionExecution {
  execution_id: string;
  mission_id: string;
  work_package_id: string;
  executor_kind: string;
  executor_ref: string;
  status: string;
  started_at: string | null;
  updated_at: string;
  completed_at: string | null;
  attempt: number;
  input_snapshot: Record<string, unknown>;
  output_summary: Record<string, unknown>;
  artifact_refs: string[];
  evidence_refs: string[];
  validation_refs: string[];
  primary_error: Record<string, string> | null;
  rollback_error: Record<string, string> | null;
  lock_owner: string | null;
  lock_acquired_at: string | null;
  heartbeat_at: string | null;
  version: number;
  review_note: string;
  previous_execution_id: string | null;
}

export interface MissionEvent {
  event_id: string;
  mission_id: string;
  entity_type: string;
  entity_id: string;
  event_type: string;
  timestamp: string;
  previous_version: number;
  new_version: number;
  payload: Record<string, unknown>;
}

export interface MissionSnapshot {
  mission: MissionData;
  work_packages: MissionWorkPackage[];
  deliverables: MissionDeliverable[];
  evidence: MissionEvidence[];
  acceptance_criteria: MissionCriterion[];
  executions: MissionExecution[];
  eligible_work_packages: string[];
  recent_events: MissionEvent[];
  resumed_at: string;
  read_only_execution: boolean;
  controlled_execution?: boolean;
  autonomous_execution?: boolean;
  executor_registry?: Record<string, { supported: boolean; executor: string | null; requires_apply_approval?: boolean }>;
}

export type MissionClientOperation =
  | { type: 'mission_list'; project_id: string }
  | { type: 'mission_create'; project_id: string; title: string; objective: string; description?: string; current_phase?: string; metadata?: Record<string, unknown> }
  | { type: 'mission_get' | 'mission_resume_snapshot'; project_id: string; mission_id: string }
  | { type: 'mission_update'; project_id: string; mission_id: string; expected_version: number; changes: Record<string, unknown> }
  | { type: 'mission_set_status'; project_id: string; mission_id: string; expected_version: number; status: string }
  | { type: 'work_package_create'; project_id: string; mission_id: string; title: string; description?: string; work_package_type?: string; priority?: number; required?: boolean; executor_kind?: string; executor_ref?: string }
  | { type: 'work_package_update'; project_id: string; mission_id: string; work_package_id: string; expected_version: number; changes: Record<string, unknown> }
  | { type: 'work_package_set_status'; project_id: string; mission_id: string; work_package_id: string; expected_version: number; status: string; blocked_reason?: string }
  | { type: 'work_package_add_dependency'; project_id: string; mission_id: string; work_package_id: string; dependency_id: string; expected_version: number }
  | { type: 'deliverable_create'; project_id: string; mission_id: string; work_package_id: string; name: string; description?: string; kind?: string; required?: boolean; expected_work_package_version?: number }
  | { type: 'deliverable_update'; project_id: string; mission_id: string; deliverable_id: string; expected_version: number; changes: Record<string, unknown> }
  | { type: 'deliverable_set_status'; project_id: string; mission_id: string; deliverable_id: string; expected_version: number; status: string }
  | { type: 'evidence_attach'; project_id: string; mission_id: string; work_package_id: string; kind: string; source_ref: string; description?: string; deliverable_id?: string }
  | { type: 'criterion_create'; project_id: string; mission_id: string; owner_type: string; owner_id: string; description: string; required_evidence_kinds?: string[]; required?: boolean }
  | { type: 'criterion_set_status'; project_id: string; mission_id: string; criterion_id: string; expected_version: number; status: string; evidence_refs?: string[]; validation_note?: string }
  | { type: 'mission_execute_work_package'; project_id: string; mission_id: string; work_package_id: string; expected_mission_version: number; expected_work_package_version: number }
  | { type: 'mission_apply_execution'; project_id: string; mission_id: string; execution_id: string; expected_execution_version: number; confirmed: true }
  | { type: 'mission_review_execution'; project_id: string; mission_id: string; execution_id: string; decision: 'ACCEPT' | 'REJECT'; review_note: string; accepted_evidence_refs: string[]; expected_execution_version: number; validation_failed?: boolean }
  | { type: 'mission_retry_execution'; project_id: string; mission_id: string; execution_id: string; expected_execution_version: number }
  | { type: 'mission_cancel_execution'; project_id: string; mission_id: string; execution_id: string; expected_execution_version: number; confirmed: true }
  | { type: 'mission_release_stale_lock'; project_id: string; mission_id: string; execution_id: string; expected_execution_version: number; confirmed: true; minimum_age_seconds?: number };

export interface AstSymbol {
  name: string;
  line?: number;
  code?: string;
}

export interface AstFileSymbols {
  type?: string;
  classes?: AstSymbol[];
  functions?: AstSymbol[];
  imports?: string[];
  exports?: string[];
}

export type AstState = Record<string, AstFileSymbols>;

export interface ProjectSummary {
  project_id: string;
  project_name: string;
  root_path: string;
}

export interface SuggestedCommand {
  kind: string;
  command: string;
  source: string;
}

export interface ProjectContextData {
  project_id: string;
  root_path: string;
  project_name: string;
  python_executable: string | null;
  runtime_source: string;
  runtime_version: string | null;
  stack: string[];
  frameworks: string[];
  package_managers: string[];
  entrypoints: string[];
  source_roots: string[];
  package_scripts: Record<string, string>;
  suggested_commands: SuggestedCommand[];
  git_state: Record<string, unknown>;
  ast_index: Record<string, unknown>;
  last_indexed_at: string | null;
  diagnostics: Array<Record<string, string>>;
}

export interface ProjectReference {
  kind: string;
  file: string;
  line: number;
  confirmed: boolean;
  text: string;
  symbol_kind?: string;
}

export interface ProjectReferenceResult {
  symbol: string;
  definitions: ProjectReference[];
  references: ProjectReference[];
}

export interface CodingValidationResult {
  kind: string;
  command: string;
  required: boolean;
  exit_code: number;
  stdout: string;
  stderr: string;
  duration_seconds: number;
}

export interface CodingProposedChange {
  file: string;
  operation: string;
  symbol?: string | null;
  previous_excerpt: string;
  proposed_excerpt: string;
  reason: string;
  unified_diff: string;
  before_hash?: string | null;
  after_hash: string;
  existed: boolean;
}

export interface CodingChangePlan {
  objective: string;
  affected_files: string[];
  affected_symbols: string[];
  intended_changes: Array<{ file: string; symbol?: string | null; change: string }>;
  risks: string[];
  validations: Array<{ kind: string; command: string; source: string; required: boolean }>;
}

export interface CodingSessionData {
  session_id: string;
  project_id: string;
  objective: string;
  project_context_snapshot: ProjectContextData | Record<string, unknown>;
  affected_files: string[];
  proposed_changes: CodingProposedChange[];
  applied_changes: Array<Record<string, unknown>>;
  validation_results: CodingValidationResult[];
  checkpoint: Record<string, unknown>;
  status: string;
  errors: string[];
  change_plan: CodingChangePlan;
  created_at: string;
  updated_at: string;
}

export interface SystemMessage {
  type: 'system';
  content: string;
}

export interface ChatProtocolMessage {
  type: 'chat';
  sender: string;
  role: string;
  content: string;
  audio?: string;
}

export interface StateMessage {
  type: 'state';
  value: RuntimeState;
}

export interface VoiceStatusMessage {
  type: 'voice_status';
  status: string;
  text?: string;
}

export interface FileMessage {
  type: 'file';
  filename: string;
  content: string;
}

export interface KanbanMessage {
  type: 'kanban';
  card_id: string;
  status: KanbanColumn | string;
}

export interface TemplateChangedMessage {
  type: 'template_changed';
  template_name: string;
  name: string;
  description: string;
  agents: Agent[];
  tasks: Task[];
  suggestions: TemplateSuggestion[];
}

export interface ArenaUpdateMessage {
  type: 'arena_update';
  model_id: keyof ArenaState;
  status: string;
  content: string;
  time: number | string;
  tokens: number | string;
}

export interface ProjectOutputMessage {
  type: 'project_output';
  content: string;
}

export interface ProjectStatusMessage {
  type: 'project_status';
  running: boolean;
  preview_url?: string;
}

export interface CompleteMessage {
  type: 'complete';
  result?: string;
}

export interface NotesListMessage {
  type: 'notes_list';
  notes: string[];
}

export interface NoteContentMessage {
  type: 'note_content';
  filename: string;
  content: string;
}

export interface NoteSavedMessage {
  type: 'note_saved';
  filename: string;
  result: string;
}

export interface RulesMessage {
  type: 'rules_list' | 'rules_updated';
  rules: RuleMemory[];
}

export interface ArchitectureMessage {
  type: 'architecture_list' | 'architecture_updated';
  architecture: ArchitectureMemory[];
}

export interface DecisionsMessage {
  type: 'decisions_list' | 'decisions_updated';
  decisions: EngineeringDecision[];
}

export interface PlannerStateMessage {
  type: 'planner_state';
  data: PlannerState | null;
}

export interface MissionListMessage {
  type: 'mission_list';
  project_id: string;
  missions: MissionData[];
}

export interface MissionSnapshotMessage {
  type: 'mission_snapshot';
  data: MissionSnapshot | null;
}

export interface AstStateMessage {
  type: 'ast_state';
  data: AstState | null;
}

export interface ProjectsListMessage {
  type: 'projects_list';
  projects: ProjectSummary[];
}

export interface ProjectContextMessage {
  type: 'project_context';
  context: ProjectContextData | null;
  files: Record<string, string>;
  symbols: AstState;
}

export interface ProjectReferencesMessage {
  type: 'project_references';
  data: ProjectReferenceResult;
}

export interface SemanticResultsMessage {
  type: 'semantic_results';
  query: string;
  content: string;
}

export interface CodingSessionMessage {
  type: 'coding_session';
  data: CodingSessionData | null;
}

export interface UiMessage {
  type: 'ui' | 'ui_action';
  action: UiAction;
}

export interface UiThemeMessage {
  type: 'ui_theme';
  theme: string;
}

export interface UnknownServerMessage {
  type: 'unknown';
  originalType: string;
  payload: Record<string, unknown>;
}

export type ServerMessage =
  | SystemMessage
  | ChatProtocolMessage
  | StateMessage
  | VoiceStatusMessage
  | FileMessage
  | KanbanMessage
  | TemplateChangedMessage
  | ArenaUpdateMessage
  | ProjectOutputMessage
  | ProjectStatusMessage
  | CompleteMessage
  | NotesListMessage
  | NoteContentMessage
  | NoteSavedMessage
  | RulesMessage
  | ArchitectureMessage
  | DecisionsMessage
  | PlannerStateMessage
  | MissionListMessage
  | MissionSnapshotMessage
  | AstStateMessage
  | ProjectsListMessage
  | ProjectContextMessage
  | ProjectReferencesMessage
  | SemanticResultsMessage
  | CodingSessionMessage
  | UiMessage
  | UiThemeMessage
  | UnknownServerMessage;

export type ClientMessage =
  | { type: 'directive'; text: string }
  | { type: 'select_template'; template: string }
  | { type: 'toggle_voice'; active: boolean }
  | { type: 'run_project'; project_id?: string }
  | { type: 'stop_project' }
  | { type: 'get_notes' }
  | { type: 'read_note'; filename: string }
  | { type: 'save_note'; filename: string; content: string }
  | { type: 'delete_rule'; key: string }
  | { type: 'delete_architecture'; module: string }
  | { type: 'delete_decision'; decision: string }
  | { type: 'get_rules' }
  | { type: 'get_planner_state' }
  | { type: 'get_ast_state'; project_id?: string }
  | { type: 'list_projects' }
  | { type: 'open_project'; project_id: string }
  | { type: 'index_project'; project_id: string }
  | { type: 'find_references'; project_id: string; symbol: string }
  | { type: 'semantic_search'; project_id: string; query: string }
  | { type: 'create_coding_session'; project_id: string; objective: string }
  | { type: 'apply_coding_session'; project_id: string; session_id: string }
  | { type: 'rollback_coding_session'; project_id: string; session_id: string; confirmed: boolean }
  | { type: 'get_coding_session'; project_id: string }
  | MissionClientOperation;

const isRecord = (value: unknown): value is Record<string, unknown> => {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
};

const asString = (value: unknown, fallback = ''): string => {
  return typeof value === 'string' ? value : fallback;
};

const asBoolean = (value: unknown): boolean => Boolean(value);

const asNumber = (value: unknown, fallback = 0): number => {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback;
};

const asStringArray = (value: unknown): string[] => {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : [];
};

const asRecordArray = (value: unknown): Record<string, unknown>[] => {
  return Array.isArray(value) ? value.filter(isRecord) : [];
};

const normalizeAgents = (value: unknown): Agent[] => {
  return asRecordArray(value).map((agent) => ({
    id: asString(agent.id),
    name: asString(agent.name),
    role: asString(agent.role),
    icon: asString(agent.icon, 'shield-check'),
  }));
};

const normalizeTasks = (value: unknown): Task[] => {
  return asRecordArray(value).map((task) => ({
    id: asString(task.id),
    title: asString(task.title),
    agent: asString(task.agent, 'pm'),
  }));
};

const normalizeSuggestions = (value: unknown): TemplateSuggestion[] => {
  return asRecordArray(value).map((suggestion) => ({
    label: asString(suggestion.label),
    prompt: asString(suggestion.prompt),
  }));
};

const normalizeRules = (value: unknown): RuleMemory[] => {
  return asRecordArray(value).map((rule) => ({
    rule_key: asString(rule.rule_key),
    description: asString(rule.description),
    correction: asString(rule.correction),
  }));
};

const normalizeArchitecture = (value: unknown): ArchitectureMemory[] => {
  return asRecordArray(value).map((item) => ({
    module: asString(item.module),
    purpose: asString(item.purpose),
    dependencies: asString(item.dependencies),
    constraints: asString(item.constraints),
  }));
};

const normalizeDecisions = (value: unknown): EngineeringDecision[] => {
  return asRecordArray(value).map((item) => ({
    decision: asString(item.decision),
    reason: asString(item.reason),
    impact: asString(item.impact),
  }));
};

const normalizePlanner = (value: unknown): PlannerState | null => {
  if (!isRecord(value)) return null;
  const goal = asString(value.goal).trim();
  const status = asString(value.status);
  const steps = asRecordArray(value.steps).map((step) => ({
    id: typeof step.id === 'number' || typeof step.id === 'string' ? step.id : '',
    action: asString(step.action),
    status: asString(step.status),
  }));
  if (['NONE', 'DONE', 'COMPLETED'].includes(status.toUpperCase())) return null;
  if (!goal && steps.length === 0) return null;
  return {
    goal,
    status,
    steps,
  };
};

const normalizeMission = (value: Record<string, unknown>): MissionData => ({
  mission_id: asString(value.mission_id),
  project_id: asString(value.project_id),
  title: asString(value.title),
  objective: asString(value.objective),
  description: asString(value.description),
  status: asString(value.status),
  created_at: asString(value.created_at),
  updated_at: asString(value.updated_at),
  started_at: typeof value.started_at === 'string' ? value.started_at : null,
  completed_at: typeof value.completed_at === 'string' ? value.completed_at : null,
  current_phase: asString(value.current_phase),
  progress: asNumber(value.progress),
  metadata: isRecord(value.metadata) ? value.metadata : {},
  version: asNumber(value.version, 1),
});

const normalizeMissionSnapshot = (value: unknown): MissionSnapshot | null => {
  if (!isRecord(value) || !isRecord(value.mission)) return null;
  return {
    mission: normalizeMission(value.mission),
    work_packages: asRecordArray(value.work_packages).map((item) => ({
      work_package_id: asString(item.work_package_id),
      mission_id: asString(item.mission_id),
      title: asString(item.title),
      description: asString(item.description),
      type: asString(item.type),
      status: asString(item.status),
      stored_status: item.stored_status ? asString(item.stored_status) : undefined,
      priority: asNumber(item.priority),
      dependencies: asStringArray(item.dependencies),
      acceptance_criteria: asStringArray(item.acceptance_criteria),
      required_deliverables: asStringArray(item.required_deliverables),
      executor_kind: asString(item.executor_kind),
      executor_ref: asString(item.executor_ref),
      blocked_reason: asString(item.blocked_reason),
      required: item.required === undefined ? true : asBoolean(item.required),
      version: asNumber(item.version, 1),
      created_at: asString(item.created_at),
      updated_at: asString(item.updated_at),
    })),
    deliverables: asRecordArray(value.deliverables).map((item) => ({
      deliverable_id: asString(item.deliverable_id),
      mission_id: asString(item.mission_id),
      work_package_id: asString(item.work_package_id),
      name: asString(item.name),
      description: asString(item.description),
      kind: asString(item.kind),
      status: asString(item.status),
      artifact_refs: asStringArray(item.artifact_refs),
      acceptance_criteria: asStringArray(item.acceptance_criteria),
      evidence_refs: asStringArray(item.evidence_refs),
      version: asNumber(item.version, 1),
      created_at: asString(item.created_at),
      updated_at: asString(item.updated_at),
    })),
    evidence: asRecordArray(value.evidence).map((item) => ({
      evidence_id: asString(item.evidence_id),
      mission_id: asString(item.mission_id),
      work_package_id: asString(item.work_package_id),
      deliverable_id: typeof item.deliverable_id === 'string' ? item.deliverable_id : null,
      kind: asString(item.kind),
      source_ref: asString(item.source_ref),
      description: asString(item.description),
      content_hash: typeof item.content_hash === 'string' ? item.content_hash : null,
      version: asNumber(item.version, 1),
      created_at: asString(item.created_at),
    })),
    acceptance_criteria: asRecordArray(value.acceptance_criteria).map((item) => ({
      criterion_id: asString(item.criterion_id),
      mission_id: asString(item.mission_id),
      owner_type: asString(item.owner_type),
      owner_id: asString(item.owner_id),
      description: asString(item.description),
      status: asString(item.status),
      required_evidence_kinds: asStringArray(item.required_evidence_kinds),
      evidence_refs: asStringArray(item.evidence_refs),
      validated_at: typeof item.validated_at === 'string' ? item.validated_at : null,
      validation_note: asString(item.validation_note),
      required: item.required === undefined ? true : asBoolean(item.required),
      version: asNumber(item.version, 1),
    })),
    executions: asRecordArray(value.executions).map((item) => ({
      execution_id: asString(item.execution_id),
      mission_id: asString(item.mission_id),
      work_package_id: asString(item.work_package_id),
      executor_kind: asString(item.executor_kind),
      executor_ref: asString(item.executor_ref),
      status: asString(item.status),
      started_at: typeof item.started_at === 'string' ? item.started_at : null,
      updated_at: asString(item.updated_at),
      completed_at: typeof item.completed_at === 'string' ? item.completed_at : null,
      attempt: asNumber(item.attempt, 1),
      input_snapshot: isRecord(item.input_snapshot) ? item.input_snapshot : {},
      output_summary: isRecord(item.output_summary) ? item.output_summary : {},
      artifact_refs: asStringArray(item.artifact_refs),
      evidence_refs: asStringArray(item.evidence_refs),
      validation_refs: asStringArray(item.validation_refs),
      primary_error: isRecord(item.primary_error)
        ? Object.fromEntries(Object.entries(item.primary_error).map(([key, entry]) => [key, asString(entry)]))
        : null,
      rollback_error: isRecord(item.rollback_error)
        ? Object.fromEntries(Object.entries(item.rollback_error).map(([key, entry]) => [key, asString(entry)]))
        : null,
      lock_owner: typeof item.lock_owner === 'string' ? item.lock_owner : null,
      lock_acquired_at: typeof item.lock_acquired_at === 'string' ? item.lock_acquired_at : null,
      heartbeat_at: typeof item.heartbeat_at === 'string' ? item.heartbeat_at : null,
      version: asNumber(item.version, 1),
      review_note: asString(item.review_note),
      previous_execution_id: typeof item.previous_execution_id === 'string' ? item.previous_execution_id : null,
    })),
    eligible_work_packages: asStringArray(value.eligible_work_packages),
    recent_events: asRecordArray(value.recent_events).map((item) => ({
      event_id: asString(item.event_id),
      mission_id: asString(item.mission_id),
      entity_type: asString(item.entity_type),
      entity_id: asString(item.entity_id),
      event_type: asString(item.event_type),
      timestamp: asString(item.timestamp),
      previous_version: asNumber(item.previous_version),
      new_version: asNumber(item.new_version),
      payload: isRecord(item.payload) ? item.payload : {},
    })),
    resumed_at: asString(value.resumed_at),
    read_only_execution: asBoolean(value.read_only_execution),
    controlled_execution: asBoolean(value.controlled_execution),
    autonomous_execution: asBoolean(value.autonomous_execution),
    executor_registry: isRecord(value.executor_registry)
      ? Object.fromEntries(Object.entries(value.executor_registry).filter(([, entry]) => isRecord(entry)).map(([key, entry]) => [key, {
        supported: asBoolean((entry as Record<string, unknown>).supported),
        executor: typeof (entry as Record<string, unknown>).executor === 'string' ? asString((entry as Record<string, unknown>).executor) : null,
        requires_apply_approval: asBoolean((entry as Record<string, unknown>).requires_apply_approval),
      }]))
      : undefined,
  };
};

const normalizeAst = (value: unknown): AstState | null => {
  if (!isRecord(value)) return null;
  return Object.fromEntries(
    Object.entries(value)
      .filter(([, fileValue]) => isRecord(fileValue))
      .map(([filename, fileValue]) => {
        const fileRecord = fileValue as Record<string, unknown>;
        return [
          filename,
          {
            type: asString(fileRecord.type),
            imports: asStringArray(fileRecord.imports),
            exports: asStringArray(fileRecord.exports),
            classes: asRecordArray(fileRecord.classes).map((symbol) => ({
              name: asString(symbol.name),
              line: typeof symbol.line === 'number' ? symbol.line : undefined,
              code: asString(symbol.code),
            })),
            functions: asRecordArray(fileRecord.functions).map((symbol) => ({
              name: asString(symbol.name),
              line: typeof symbol.line === 'number' ? symbol.line : undefined,
              code: asString(symbol.code),
            })),
          },
        ];
      }),
  );
};

const normalizeProjects = (value: unknown): ProjectSummary[] => {
  return asRecordArray(value).map((project) => ({
    project_id: asString(project.project_id),
    project_name: asString(project.project_name),
    root_path: asString(project.root_path),
  })).filter((project) => Boolean(project.project_id));
};

const normalizeProjectContext = (value: unknown): ProjectContextData | null => {
  if (!isRecord(value)) return null;
  const packageScripts = isRecord(value.package_scripts)
    ? Object.fromEntries(Object.entries(value.package_scripts).map(([key, item]) => [key, asString(item)]))
    : {};
  const gitState = isRecord(value.git_state) ? value.git_state : {};
  const astIndex = isRecord(value.ast_index) ? value.ast_index : {};
  return {
    project_id: asString(value.project_id),
    root_path: asString(value.root_path),
    project_name: asString(value.project_name),
    python_executable: typeof value.python_executable === 'string' ? value.python_executable : null,
    runtime_source: asString(value.runtime_source, 'unavailable'),
    runtime_version: typeof value.runtime_version === 'string' ? value.runtime_version : null,
    stack: asStringArray(value.stack),
    frameworks: asStringArray(value.frameworks),
    package_managers: asStringArray(value.package_managers),
    entrypoints: asStringArray(value.entrypoints),
    source_roots: asStringArray(value.source_roots),
    package_scripts: packageScripts,
    suggested_commands: asRecordArray(value.suggested_commands).map((command) => ({
      kind: asString(command.kind),
      command: asString(command.command),
      source: asString(command.source),
    })),
    git_state: gitState,
    ast_index: astIndex,
    last_indexed_at: typeof value.last_indexed_at === 'string' ? value.last_indexed_at : null,
    diagnostics: asRecordArray(value.diagnostics).map((diagnostic) => (
      Object.fromEntries(Object.entries(diagnostic).map(([key, item]) => [key, asString(item)]))
    )),
  };
};

const normalizeReference = (value: Record<string, unknown>): ProjectReference => ({
  kind: asString(value.kind),
  file: asString(value.file),
  line: typeof value.line === 'number' ? value.line : 0,
  confirmed: asBoolean(value.confirmed),
  text: asString(value.text),
  symbol_kind: value.symbol_kind ? asString(value.symbol_kind) : undefined,
});

const normalizeReferences = (value: unknown): ProjectReferenceResult => {
  if (!isRecord(value)) return { symbol: '', definitions: [], references: [] };
  return {
    symbol: asString(value.symbol),
    definitions: asRecordArray(value.definitions).map(normalizeReference),
    references: asRecordArray(value.references).map(normalizeReference),
  };
};

const normalizeCodingSession = (value: unknown): CodingSessionData | null => {
  if (!isRecord(value)) return null;
  const rawPlan = isRecord(value.change_plan) ? value.change_plan : {};
  const plan: CodingChangePlan = {
    objective: asString(rawPlan.objective),
    affected_files: asStringArray(rawPlan.affected_files),
    affected_symbols: asStringArray(rawPlan.affected_symbols),
    intended_changes: asRecordArray(rawPlan.intended_changes).map((item) => ({
      file: asString(item.file),
      symbol: item.symbol ? asString(item.symbol) : null,
      change: asString(item.change),
    })),
    risks: asStringArray(rawPlan.risks),
    validations: asRecordArray(rawPlan.validations).map((item) => ({
      kind: asString(item.kind),
      command: asString(item.command),
      source: asString(item.source),
      required: asBoolean(item.required),
    })),
  };
  return {
    session_id: asString(value.session_id),
    project_id: asString(value.project_id),
    objective: asString(value.objective),
    project_context_snapshot: isRecord(value.project_context_snapshot) ? value.project_context_snapshot : {},
    affected_files: asStringArray(value.affected_files),
    proposed_changes: asRecordArray(value.proposed_changes).map((item) => ({
      file: asString(item.file),
      operation: asString(item.operation),
      symbol: item.symbol ? asString(item.symbol) : null,
      previous_excerpt: asString(item.previous_excerpt),
      proposed_excerpt: asString(item.proposed_excerpt),
      reason: asString(item.reason),
      unified_diff: asString(item.unified_diff),
      before_hash: item.before_hash ? asString(item.before_hash) : null,
      after_hash: asString(item.after_hash),
      existed: asBoolean(item.existed),
    })),
    applied_changes: asRecordArray(value.applied_changes),
    validation_results: asRecordArray(value.validation_results).map((item) => ({
      kind: asString(item.kind),
      command: asString(item.command),
      required: asBoolean(item.required),
      exit_code: typeof item.exit_code === 'number' ? item.exit_code : -1,
      stdout: asString(item.stdout),
      stderr: asString(item.stderr),
      duration_seconds: typeof item.duration_seconds === 'number' ? item.duration_seconds : 0,
    })),
    checkpoint: isRecord(value.checkpoint) ? value.checkpoint : {},
    status: asString(value.status),
    errors: asStringArray(value.errors),
    change_plan: plan,
    created_at: asString(value.created_at),
    updated_at: asString(value.updated_at),
  };
};

export const normalizeServerMessage = (raw: unknown): ServerMessage | null => {
  if (!isRecord(raw)) return null;
  const type = asString(raw.type, 'unknown');

  switch (type) {
    case 'system':
      return { type, content: asString(raw.content) };
    case 'chat':
      return {
        type,
        sender: asString(raw.sender, 'SISTEMA'),
        role: asString(raw.role, 'System'),
        content: asString(raw.content),
        audio: raw.audio ? asString(raw.audio) : undefined,
      };
    case 'state':
      return { type, value: asString(raw.value, 'idle') };
    case 'voice_status':
      return { type, status: asString(raw.status, 'offline'), text: raw.text ? asString(raw.text) : undefined };
    case 'file':
      return { type, filename: asString(raw.filename), content: asString(raw.content) };
    case 'kanban':
      return { type, card_id: asString(raw.card_id), status: asString(raw.status, 'backlog') };
    case 'template_changed':
      return {
        type,
        template_name: asString(raw.template_name),
        name: asString(raw.name),
        description: asString(raw.description),
        agents: normalizeAgents(raw.agents),
        tasks: normalizeTasks(raw.tasks),
        suggestions: normalizeSuggestions(raw.suggestions),
      };
    case 'arena_update':
      return {
        type,
        model_id: asString(raw.model_id, 'gemini') as keyof ArenaState,
        status: asString(raw.status),
        content: asString(raw.content),
        time: typeof raw.time === 'number' || typeof raw.time === 'string' ? raw.time : '-',
        tokens: typeof raw.tokens === 'number' || typeof raw.tokens === 'string' ? raw.tokens : '-',
      };
    case 'project_output':
      return { type, content: asString(raw.content) };
    case 'project_status':
      return { type, running: asBoolean(raw.running), preview_url: raw.preview_url ? asString(raw.preview_url) : undefined };
    case 'complete':
      return { type, result: raw.result ? asString(raw.result) : undefined };
    case 'notes_list':
      return { type, notes: asStringArray(raw.notes) };
    case 'note_content':
      return { type, filename: asString(raw.filename), content: asString(raw.content) };
    case 'note_saved':
      return { type, filename: asString(raw.filename), result: asString(raw.result) };
    case 'rules_list':
    case 'rules_updated':
      return { type, rules: normalizeRules(raw.rules) };
    case 'architecture_list':
    case 'architecture_updated':
      return { type, architecture: normalizeArchitecture(raw.architecture) };
    case 'decisions_list':
    case 'decisions_updated':
      return { type, decisions: normalizeDecisions(raw.decisions) };
    case 'planner_state':
      return { type, data: normalizePlanner(raw.data) };
    case 'mission_list':
      return { type, project_id: asString(raw.project_id), missions: asRecordArray(raw.missions).map(normalizeMission) };
    case 'mission_snapshot':
      return { type, data: normalizeMissionSnapshot(raw.data) };
    case 'ast_state':
      return { type, data: normalizeAst(raw.data) };
    case 'projects_list':
      return { type, projects: normalizeProjects(raw.projects) };
    case 'project_context':
      return {
        type,
        context: normalizeProjectContext(raw.context),
        files: isRecord(raw.files) ? Object.fromEntries(Object.entries(raw.files).map(([key, value]) => [key, asString(value)])) : {},
        symbols: normalizeAst(raw.symbols) ?? {},
      };
    case 'project_references':
      return { type, data: normalizeReferences(raw.data) };
    case 'semantic_results':
      return { type, query: asString(raw.query), content: asString(raw.content) };
    case 'coding_session':
      return { type, data: normalizeCodingSession(raw.data) };
    case 'ui':
    case 'ui_action':
      return { type, action: asString(raw.action) };
    case 'ui_theme':
      return { type, theme: asString(raw.theme) };
    default:
      return { type: 'unknown', originalType: type, payload: raw };
  }
};
