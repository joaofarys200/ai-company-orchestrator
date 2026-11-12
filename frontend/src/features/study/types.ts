export type SourceType =
  | 'PDF'
  | 'DOCX'
  | 'PPTX'
  | 'TXT'
  | 'MARKDOWN'
  | 'IMAGE'
  | 'AUDIO'
  | 'LECTURE_AUDIO'
  | 'NOTE'
  | 'VIDEO';

export type EvidenceStatus = 'OBSERVED' | 'INFERRED' | 'UNKNOWN';

export interface StudyParagraph {
  paragraph_id: string;
  text: string;
  page_number: number;
  section_id: string;
  order: number;
}

export interface StudySection {
  section_id: string;
  title: string;
  level: number;
  page_start: number;
  page_end: number;
  paragraphs: StudyParagraph[];
}

export interface StudyMedia {
  media_id: string;
  media_type: 'figure' | 'table' | 'image' | 'audio';
  title: string;
  caption: string;
  page_number: number;
  data_ref?: string;
  explanation?: string;
  evidence_status: EvidenceStatus;
}

export interface ArgumentItem {
  text: string;
  status: EvidenceStatus;
  page_ref?: number;
  source_refs?: string[];
}

export interface ArticleStructure {
  problem: ArgumentItem;
  research_gap: ArgumentItem;
  research_question: ArgumentItem;
  hypothesis: ArgumentItem;
  contribution: ArgumentItem;
  method: ArgumentItem;
  dataset: ArgumentItem;
  experiment: ArgumentItem;
  results: ArgumentItem;
  limitations: ArgumentItem;
  conclusion: ArgumentItem;
  is_argumentative?: boolean;
  argumentative_limitation?: string | null;
  relations?: Array<{ from: string; to: string; type: string; evidence?: string }>;
}

export interface GlossaryTerm {
  term: string;
  translation: string;
  explanation: string;
  first_occurrence: string;
  occurrences: number;
  importance: 'HIGH' | 'MEDIUM' | 'LOW';
}

export interface StudyReadingProgress {
  current_page: number;
  current_section: string;
  scroll_position: number;
  progress_percent: number;
  last_read_at: string;
  bookmarks: number[];
}

export interface StudyReadingNote {
  note_id: string;
  document_id: string;
  page: number;
  selection: string;
  note: string;
  created_at: string;
  section_id?: string;
}

export interface StudyHighlight {
  highlight_id: string;
  document_id: string;
  page: number;
  selected_text: string;
  context?: string;
  color?: string;
  created_at?: string;
}

export interface StudyDocument {
  document_id: string;
  source_id: string;
  title: string;
  source_type: SourceType;
  subject: string;
  language: string;
  page_count: number;
  sections: StudySection[];
  extracted_text: string;
  media: StudyMedia[];
  metadata: Record<string, unknown>;
  source_hash: string;
  collection_id?: string;
  source_origin?: 'manual_upload' | 'linked_folder';
  sync_status?: 'synced' | 'pending' | 'failed' | 'processing';
  sync_error?: string;
  provenance: {
    source_file: string;
    ingested_at: string;
    evidence_status: EvidenceStatus;
    source_origin?: 'manual_upload' | 'linked_folder';
    linked_folder_path?: string;
    rel_path?: string;
    sync_status?: 'synced' | 'pending' | 'failed' | 'processing';
    sync_error?: string;
  };
  reading_progress: StudyReadingProgress;
  structure?: ArticleStructure;
  glossary: GlossaryTerm[];
  created_at: string;
  updated_at: string;
}

export interface QuizQuestion {
  id: string;
  question: string;
  question_type: 'multiple_choice' | 'true_false' | 'short_answer';
  options: string[];
  correct_index: number;
  correct_answer: string;
  explanation: string;
  source_ids: string[];
  page_ref?: number;
  timestamp?: number;
  timestamp_str?: string;
  frame_id?: string;
}

export interface StudyQuiz {
  quiz_id: string;
  document_id: string;
  topic: string;
  questions: QuizQuestion[];
  transfer_question: {
    id: string;
    scenario: string;
    expected_concepts: string[];
  };
}

export interface QuizDetailedQuestionEval {
  question_id: string;
  status: 'CORRECT' | 'INCORRECT' | 'UNANSWERED';
  user_answer: number | string | null;
  correct_answer: string;
  explanation: string;
}

export interface QuizEvaluationResult {
  result_id: string;
  quiz_id: string;
  topic: string;
  total_questions: number;
  correct_answers: number;
  incorrect_answers: number;
  unanswered: number;
  score: number;
  passed: boolean;
  detailed_questions: QuizDetailedQuestionEval[];
  transfer_status: 'PASS' | 'PARTIAL' | 'NOT_ATTEMPTED' | 'INSUFFICIENT_EVIDENCE';
  transfer_feedback: string;
  evaluated_at: string;
}

export interface Flashcard {
  card_id: string;
  document_id: string;
  front: string;
  back: string;
  source_ids: string[];
  page_ref?: number;
  timestamp?: number;
  frame_id?: string;
  difficulty: 'EASY' | 'MEDIUM' | 'HARD';
  next_review: number;
  repetitions: number;
  interval_days: number;
}

export interface CornellNotesData {
  document_id: string;
  topic: string;
  subject: string;
  date: string;
  executive_summary: string;
  cue_column: Array<{ cue: string; idea: string; source_refs?: string[] }>;
  detailed_notes: string;
  glossary: string;
  action_items: string[];
  generation_mode?: string;
}

export interface StudyGenerationTelemetry {
  provider?: string;
  model?: string;
  generation_id?: string;
  input_tokens?: number;
  output_tokens?: number;
  ttft_ms?: number;
  total_ms?: number;
  tokens_per_sec?: number;
  context_used?: number;
  status?: string;
  grounding_ratio?: number;
  validation_errors?: string[];
  attempts?: number;
  failure_reason?: string;
}

export interface StudyFolderLink {
  folder_path: string;
  sync_enabled: boolean;
  recursive: boolean;
  last_synced_at?: string;
  file_count: number;
  unsupported_count?: number;
  status: 'IDLE' | 'SYNCING' | 'ERROR';
  error?: string;
  registered_at?: string;
}

export interface StudyCollection {
  collection_id: string;
  name: string;
  subject: string;
  document_ids: string[];
  created_at: string;
  linked_folders?: StudyFolderLink[];
  sync_preferences?: {
    auto_sync?: boolean;
    recursive?: boolean;
  };
}

export type ExplanationLevel = 'Básico' | 'Intermédio' | 'Académico';
export type SummaryMode = 'Quick' | 'Study' | 'Detailed' | 'Exam';

export interface StudySectionSummaryItem {
  section_id: string;
  title: string;
  page_ref?: string;
  summary: string;
  key_concepts?: string[];
  source_refs?: string[];
}

export interface StudyDetailedSummaryItem {
  title: string;
  text: string;
  source_refs?: string[];
}

export interface StudyExamSummary {
  high_yield_concepts: Array<{ concept: string; detail: string; source_refs?: string[] }>;
  likely_questions: Array<{ question: string; answer: string; source_refs?: string[] }>;
}

export interface StudySummariesBundle {
  quick?: string[];
  quick_refs?: string[][];
  study?: StudySectionSummaryItem[];
  detailed?: StudyDetailedSummaryItem[] | string;
  exam?: StudyExamSummary | string[];
}

export interface MultiDocSynthesisResult {
  common_points: string[];
  differences: string[];
  shared_concepts: string[];
  contradictions: string[];
  idea_evolution: string[];
}

export interface VideoTranscriptSegment {
  id: number;
  start: number;
  end: number;
  text: string;
  confidence?: number;
  words?: Array<{ word: string; start: number; end: number }>;
}

export interface VideoChapter {
  title: string;
  start_time: number;
  end_time: number;
  summary: string;
  key_concepts: string[];
}

export interface VideoKeyframe {
  frame_id: string;
  timestamp: number;
  timestamp_str: string;
  image_path: string;
  has_text: boolean;
  is_slide: boolean;
  confidence: number;
}

export interface VideoContextWindow {
  current_timestamp: number;
  current_timestamp_str: string;
  current_segment?: VideoTranscriptSegment;
  surrounding_transcript: string;
  current_chapter?: VideoChapter;
  relevant_frames: VideoKeyframe[];
  nearest_slide?: VideoKeyframe;
  video_metadata: {
    duration_seconds: number;
    title: string;
    width: number;
    height: number;
  };
}

export interface VideoNote {
  note_id: string;
  document_id: string;
  timestamp: number;
  timestamp_str: string;
  frame_id?: string;
  note: string;
  selected_text?: string;
  created_at: string;
}

export interface VideoSearchResult {
  segment_id: number;
  start: number;
  end: number;
  timestamp_str: string;
  text: string;
}

// ============================================================================
// Phase 4 — Editorial Intelligence & Academic Study Document Design
// ============================================================================

export type EpistemicStatusCode = 'SOURCE_FACT' | 'MODEL_INFERENCE' | 'NOT_FOUND' | 'UNVERIFIED';

export interface EditorialEvidenceRef {
  section_id: string;
  paragraph_id?: string | null;
  page_number?: number | null;
  excerpt?: string;
  status: EpistemicStatusCode | string;
}

export interface EditorialPlanMetadata {
  plan_id: string;
  document_id: string;
  source_sha256: string;
  ast_version: string;
  dossier_id: string;
  dossier_schema_version: string;
  dossier_engine_version: string;
  dossier_fingerprint: string;
  plan_version: number;
  previous_plan_id?: string | null;
  schema_version: string;
  engine_version: string;
  model_name: string;
  prompt_versions: Record<string, string>;
  created_at: string;
  status: 'COMPLETED' | 'PARTIAL' | 'FAILED' | 'CANCELLED' | string;
}

export interface EditorialLearningObjective {
  objective_id: string;
  description: string;
  epistemic_status: EpistemicStatusCode | string;
  source_section_ids: string[];
  evidence_refs?: EditorialEvidenceRef[];
}

export interface EditorialOverview {
  central_theme: string;
  central_theme_status: EpistemicStatusCode | string;
  learning_objectives: EditorialLearningObjective[];
  target_audience: string;
  target_audience_basis: EpistemicStatusCode | string;
  document_nature: string;
  recommended_structure_rationale: string;
  editorial_strategy: string;
  global_organization_summary: string;
  core_contents: string[];
  complementary_contents: string[];
  transversal_synthesis_opportunities: string[];
  evidence_refs: EditorialEvidenceRef[];
}

export interface PedagogicalExplanationSpec {
  target_topic_or_concept: string;
  concept_id?: string | null;
  depth_level: 'FOUNDATIONAL' | 'IN_DEPTH' | 'SYNTHETIC' | string;
  depth_justification: string;
  required_elements: string[];
  pedagogical_focus: Record<string, string>;
  epistemic_status: EpistemicStatusCode | string;
  evidence_refs: EditorialEvidenceRef[];
}

export interface EditorialSection {
  section_id: string;
  chapter_id: string;
  title: string;
  pedagogical_objective: string;
  parent_section_id?: string | null;
  level: number;
  order: number;
  content_role: string;
  contents_to_cover: Array<{
    summary: string;
    epistemic_status: string;
    source_section_id?: string;
    paragraph_ids?: string[];
    page_numbers?: number[];
  }>;
  associated_concept_ids: string[];
  introduced_concept_ids: string[];
  prerequisite_concept_ids: string[];
  explanation_strategy: string;
  planned_pedagogical_elements: string[];
  pedagogical_treatments: PedagogicalExplanationSpec[];
  original_section_ids: string[];
  merged_or_deduplicated_notes: string[];
  evidence_refs: EditorialEvidenceRef[];
  related_section_ids: Array<{
    target_section_id: string;
    relation_type: string;
    rationale: string;
  }>;
  visual_plan_ids: string[];
  editorial_recommendations: string[];
  limitations_and_uncertainties: string[];
}

export interface EditorialChapter {
  chapter_id: string;
  title: string;
  pedagogical_objective: string;
  description: string;
  order: number;
  role_in_progression: string;
  editorial_justification: string;
  sections: EditorialSection[];
  key_concept_ids: string[];
  original_section_ids: string[];
  evidence_refs: EditorialEvidenceRef[];
  learning_dependencies: string[];
}

export interface EditorialConceptRelationship {
  relationship_id: string;
  source_concept_id: string;
  source_concept_name: string;
  target_concept_id: string;
  target_concept_name: string;
  relation_type: string;
  is_hierarchical: boolean;
  pedagogical_dependency: string;
  justification: string;
  epistemic_status: string;
  evidence_refs: EditorialEvidenceRef[];
}

export interface VisualPlanItem {
  visual_id: string;
  target_chapter_id: string;
  target_section_id: string;
  visual_type: string;
  title: string;
  pedagogical_objective: string;
  content_to_explain: string;
  required_concepts_or_data: string[];
  information_to_represent: string[];
  feasibility_status: string;
  source_table_ids: string[];
  source_figure_ids: string[];
  evidence_refs: EditorialEvidenceRef[];
  inclusion_justification: string;
  constraints_and_limitations: string[];
  epistemic_status: string;
}

export interface EditorialQAFinding {
  finding_id: string;
  code: string;
  severity: 'BLOCKING_ERROR' | 'WARNING' | 'RECOMMENDATION' | string;
  message: string;
  affected_elements: string[];
  evidence_refs: EditorialEvidenceRef[];
  recommendation: string;
}

export interface EditorialQAReport {
  validation_status: 'VALID' | 'VALID_WITH_WARNINGS' | 'INVALID_BLOCKING' | string;
  is_valid: boolean;
  blocking_errors_count: number;
  warnings_count: number;
  recommendations_count: number;
  dossier_section_coverage_pct: number;
  dossier_concept_coverage_pct: number;
  valid_evidence_refs_pct: number;
  invalid_paragraph_refs: string[];
  invalid_section_refs: string[];
  invalid_page_refs: number[];
  epistemic_distribution: Record<string, number>;
  findings: EditorialQAFinding[];
}

export interface EditorialStudyPlan {
  metadata: EditorialPlanMetadata;
  overview: EditorialOverview;
  chapters: EditorialChapter[];
  conceptual_relationships: EditorialConceptRelationship[];
  visual_plans: VisualPlanItem[];
  qa_report: EditorialQAReport;
  telemetry?: Record<string, unknown>;
  failed_operations?: Array<Record<string, unknown>>;
}

export interface EditorialPlanStatus {
  document_id: string;
  state: 'NOT_GENERATED' | 'IN_PROGRESS_CHECKPOINT' | 'COMPLETED' | 'PARTIAL' | 'FAILED' | string;
  has_ast: boolean;
  has_dossier: boolean;
  has_checkpoint: boolean;
  has_plan: boolean;
  is_stale: boolean;
  stale_reason: string;
  plan_id?: string | null;
  plan_version?: number | null;
  validation_status?: string | null;
  updated_at?: string | null;
}

// ============================================================================
// Phase 5 — Document Generation Engine & Academic Document Composition
// ============================================================================

export interface StudyDocumentQAFinding {
  finding_id: string;
  axis: 'CONTENT_INTEGRITY' | 'VISUAL_INTEGRITY' | 'DOCUMENT_INTEGRITY' | 'PEDAGOGICAL_QUALITY' | string;
  severity: 'BLOCKING_ERROR' | 'WARNING' | 'RECOMMENDATION' | string;
  code: string;
  message: string;
  element_id?: string | null;
  page_number?: number | null;
  details?: Record<string, unknown>;
}

export interface StudyDocumentQAReport {
  validation_status: 'VALID' | 'VALID_WITH_WARNINGS' | 'INVALID_BLOCKING' | string;
  is_valid: boolean;
  overall_score: number;
  content_integrity_score: number;
  visual_integrity_score: number;
  document_integrity_score: number;
  pedagogical_quality_score: number;
  findings: StudyDocumentQAFinding[];
  blocking_count: number;
  warning_count: number;
  recommendation_count: number;
  verified_at: string;
}

export interface StudyDocumentTelemetry {
  llm_calls_count: number;
  llm_total_time_ms: number;
  visuals_rendered_count: number;
  ir_compilation_time_ms: number;
  pdf_generation_time_ms: number;
  docx_generation_time_ms: number;
  qa_verification_time_ms: number;
  total_pipeline_time_ms: number;
  pdf_pages_count: number;
  total_words_count: number;
  peak_ram_mb: number;
}

export interface StudyDocumentVersionRecord {
  version: number;
  document_id: string;
  created_at: string;
  plan_fingerprint: string;
  pdf_sha256: string;
  docx_sha256?: string | null;
  pdf_size_bytes: number;
  docx_size_bytes: number;
  pdf_pages_count: number;
  qa_status: string;
  design_profile_id: string;
}

export interface StudyDocumentGenerationStatus {
  document_id: string;
  state: 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'PARTIAL' | 'FAILED' | string;
  has_pdf: boolean;
  has_docx: boolean;
  has_checkpoint: boolean;
  version: number;
  pdf_path?: string | null;
  docx_path?: string | null;
  pdf_size_bytes: number;
  docx_size_bytes: number;
  qa_validation_status: string;
  qa_report?: StudyDocumentQAReport | null;
  telemetry?: StudyDocumentTelemetry | null;
  versions_count: number;
  updated_at?: string | null;
  is_stale?: boolean;
  stale_reason?: string;
}

export interface StudyDocumentGenerationResult {
  document_id: string;
  status: 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'PARTIAL' | 'FAILED' | string;
  version: number;
  pdf_path: string;
  docx_path?: string | null;
  pdf_size_bytes: number;
  docx_size_bytes: number;
  qa_report: StudyDocumentQAReport;
  telemetry: StudyDocumentTelemetry;
  failed_operations: Array<Record<string, unknown>>;
  created_at: string;
}

export interface StudyDocumentFilePayload {
  document_id: string;
  format: 'pdf' | 'docx';
  filename: string;
  file_path: string;
  size_bytes: number;
  mime_type: string;
  base64_data: string;
}

// ============================================================================
// Phase 6 — Study Modes, Active Recall & Adaptive Learning
// ============================================================================

export interface StudyModeReadiness {
  document_id: string;
  status: string;
  is_ready: boolean;
  has_ast: boolean;
  has_dossier: boolean;
  has_plan: boolean;
  has_study_document: boolean;
  is_stale: boolean;
  stale_reasons: string[];
  missing_artifacts: string[];
  actionable_message: string;
}

export interface ReviewSchedulingState {
  item_id: string;
  item_type: string;
  document_id: string;
  chapter_id?: string;
  section_id?: string;
  topic?: string;
  content_difficulty: string;
  question_difficulty: string;
  last_reviewed_ts: number;
  next_review_ts: number;
  reviews_count: number;
  successful_recalls: number;
  failed_recalls: number;
  consecutive_successes: number;
  consecutive_failures: number;
  last_confidence: number;
  last_performance_quality: number;
  learning_state: 'NEW' | 'LEARNING' | 'DUE' | 'LAPSED' | 'MATURE' | 'SUSPENDED' | string;
  interval_days: number;
  ease_factor: number;
  algorithm_version: string;
}

export interface AdaptiveFlashcard {
  card_id: string;
  document_id: string;
  front: string;
  back: string;
  card_type: string;
  content_difficulty: string;
  question_difficulty: 'EASY' | 'MEDIUM' | 'HARD' | string;
  chapter_id: string;
  chapter_title: string;
  section_id: string;
  section_title: string;
  topic: string;
  learning_objective_id: string;
  learning_objective_text: string;
  concept_ids: string[];
  evidence_refs: EditorialEvidenceRef[];
  source_pages: number[];
  epistemic_status: EpistemicStatusCode | string;
  is_hypothetical_scenario: boolean;
  generation_mode: string;
  review_status: string;
  user_edited: boolean;
  edited_at?: string | null;
  is_deleted: boolean;
  srs?: ReviewSchedulingState;
}

export interface StudyDeckPayload {
  document_id: string;
  deck: {
    deck_id: string;
    title: string;
    document_nature: string;
    generation_mode: string;
    status: string;
    updated_at: string;
  } | null;
  cards: AdaptiveFlashcard[];
  readiness?: StudyModeReadiness;
}

export interface CornellCueItem {
  cue_id: string;
  cue_prompt: string;
  cue_type: string;
  answer_hint: string;
  epistemic_status: string;
  concept_ids: string[];
  evidence_refs: EditorialEvidenceRef[];
  is_important: boolean;
  user_edited: boolean;
}

export interface CornellPersonalNote {
  note_id: string;
  section_id: string;
  content: string;
  is_important: boolean;
  created_at: string;
  updated_at: string;
}

export interface CornellNoteEntry {
  entry_id: string;
  chapter_id: string;
  chapter_title: string;
  section_id: string;
  section_title: string;
  sufficient_evidence: boolean;
  insufficiency_reason: string;
  main_concepts: Array<{ name: string; note: string }>;
  explanations: string[];
  supporting_details: string[];
  examples: string[];
  concept_relationships: string[];
  methodology_notes: string;
  results_and_conclusions_notes: string;
  cue_column: CornellCueItem[];
  summary_section: string;
  source_pages: number[];
  evidence_refs: EditorialEvidenceRef[];
  epistemic_status: string;
  is_important: boolean;
  personal_notes: CornellPersonalNote[];
  user_edited: boolean;
  edited_fields: string[];
  generation_mode: string;
}

export interface CornellStudyDocument {
  cornell_id: string;
  document_id: string;
  title: string;
  subject: string;
  global_summary: string;
  entries: CornellNoteEntry[];
  generation_mode: string;
  status: string;
  updated_at: string;
}

export interface ScoringCriterion {
  criterion_id: string;
  description: string;
  weight: number;
  required_concepts: string[];
  factual_anchors: string[];
}

export interface AssessmentQuestion {
  question_id: string;
  document_id: string;
  question_text: string;
  question_type: string;
  content_difficulty: string;
  question_difficulty: string;
  options: string[];
  correct_index?: number | null;
  correct_answer: string;
  explanation: string;
  topic: string;
  chapter_id: string;
  section_id: string;
  learning_objective_id: string;
  learning_objective_text: string;
  related_concept_ids: string[];
  related_concept_names: string[];
  evidence_refs: EditorialEvidenceRef[];
  epistemic_status: string;
  is_hypothetical_scenario: boolean;
  scoring_criteria: ScoringCriterion[];
  generation_mode: string;
}

export interface AssessmentConfig {
  question_count: number;
  chapter_ids: string[];
  topics: string[];
  difficulty: string;
  question_types: string[];
  session_mode: 'PRACTICE' | 'ASSESSMENT' | string;
  feedback_mode: 'IMMEDIATE' | 'DEFERRED' | string;
}

export interface StudyAssessment {
  assessment_id: string;
  document_id: string;
  title: string;
  config: AssessmentConfig;
  questions: AssessmentQuestion[];
  generation_mode: string;
  status: string;
  created_at: string;
}

export interface OpenAnswerEvaluation {
  question_id: string;
  student_answer: string;
  verdict: string;
  score_ratio: number;
  is_correct: boolean;
  is_uncertain: boolean;
  factual_errors: string[];
  missing_points: string[];
  covered_points: string[];
  reasoning: string;
  evaluation_mode: string;
}

export interface QuestionAttemptOutcome {
  question_id: string;
  question_type: string;
  topic: string;
  chapter_id: string;
  section_id: string;
  question_difficulty: string;
  student_answer: any;
  correct_answer: string;
  is_correct: boolean;
  score_ratio: number;
  verdict: string;
  explanation: string;
  open_evaluation?: OpenAnswerEvaluation | null;
  evidence_refs: EditorialEvidenceRef[];
  epistemic_status: string;
}

export interface AssessmentAttempt {
  attempt_id: string;
  assessment_id: string;
  document_id: string;
  session_mode: string;
  feedback_mode: string;
  total_questions: number;
  answered_count: number;
  correct_count: number;
  partial_count: number;
  incorrect_count: number;
  unanswered_count: number;
  score_pct: number;
  passed: boolean;
  outcomes: QuestionAttemptOutcome[];
  by_topic: Record<string, { total: number; correct: number; accuracy_pct: number }>;
  by_difficulty: Record<string, { total: number; correct: number; accuracy_pct: number }>;
  incorrect_question_ids: string[];
  submitted_at: string;
}

export interface ActiveRecallPrompt {
  prompt_id: string;
  document_id: string;
  prompt_text: string;
  prompt_type: string;
  content_difficulty: string;
  question_difficulty: string;
  chapter_id: string;
  chapter_title: string;
  section_id: string;
  section_title: string;
  topic: string;
  learning_objective_id: string;
  learning_objective_text: string;
  concept_ids: string[];
  optional_outline: string[];
  grounded_reference_answer: string;
  evidence_refs: EditorialEvidenceRef[];
  source_pages: number[];
  epistemic_status: string;
  answer_hidden?: boolean;
}

export interface ActiveRecallAttempt {
  attempt_id: string;
  prompt_id: string;
  document_id: string;
  student_response: string;
  self_confidence: number;
  self_rating: string;
  outline_used: boolean;
  evaluation?: OpenAnswerEvaluation | null;
  score_ratio: number;
  revealed_reference: string;
  evidence_refs: EditorialEvidenceRef[];
  identified_gap_triggered: boolean;
  scheduled_next_review_ts: number;
  created_at: string;
}

export interface DailyQueueItem {
  item_id: string;
  item_type: 'flashcard' | 'active_recall' | string;
  queue_category?: 'lapsed' | 'due' | 'low_confidence' | 'new' | string;
  title: string;
  topic: string;
  chapter_id: string;
  section_id: string;
  srs_state: string;
  interval_days: number;
  ease_factor: number;
  last_confidence?: number;
  epistemic_status: string;
}

export interface DailyReviewQueue {
  document_id: string;
  generated_at: string;
  daily_new_limit: number;
  daily_review_limit: number;
  due_items: DailyQueueItem[];
  lapsed_items: DailyQueueItem[];
  low_confidence_items: DailyQueueItem[];
  new_items: DailyQueueItem[];
  weak_topics: string[];
  total_queue_count: number;
}

export interface KnowledgeGap {
  gap_id: string;
  document_id: string;
  gap_type: string;
  concept_id: string;
  concept_name: string;
  section_id: string;
  chapter_id: string;
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | string;
  failure_count: number;
  attempts_count: number;
  description: string;
  evidence_refs: EditorialEvidenceRef[];
  suggested_activities: Array<{ mode: string; label: string; target: string }>;
}

export interface LearningProgressSnapshot {
  document_id: string;
  questions_answered: number;
  correct_answers: number;
  partial_answers: number;
  incorrect_answers: number;
  flashcard_reviews_total: number;
  active_recall_attempts_total: number;
  overall_accuracy_pct: number | null;
  avg_recall_confidence: number | null;
  mastery_level: 'INSUFFICIENT_EVIDENCE' | 'EMERGING' | 'DEVELOPING' | 'PROFICIENT' | string;
  by_chapter: Record<string, { id: string; label: string; attempts: number; accuracy_pct: number; mastery_level: string }>;
  by_section: Record<string, { id: string; label: string; attempts: number; accuracy_pct: number; mastery_level: string }>;
  by_concept: Record<string, { id: string; label: string; attempts: number; failures: number; accuracy_pct: number; mastery_level: string }>;
  by_objective: Record<string, { id: string; label: string; attempts: number; accuracy_pct: number; mastery_level: string }>;
  repeatedly_missed_concepts: string[];
  consistently_recalled_concepts: string[];
  insufficient_evidence_objectives: string[];
  knowledge_gaps: KnowledgeGap[];
  updated_at: string;
}

export interface StudySessionItemRef {
  item_id: string;
  item_type: 'flashcard' | 'active_recall' | string;
  queue_category?: 'lapsed' | 'due' | 'low_confidence' | 'new' | string;
  title?: string;
  topic?: string;
  chapter_id?: string;
  section_id?: string;
}

export interface StudySessionState {
  session_id: string;
  document_id: string;
  mode: string;
  status: 'IN_PROGRESS' | 'PAUSED' | 'COMPLETED' | 'ABANDONED' | string;
  title: string;
  items?: StudySessionItemRef[];
  item_ids: string[];
  current_index: number;
  completed_item_ids: string[];
  partial_responses: Record<string, any>;
  config: Record<string, any>;
  summary_stats: Record<string, any>;
  started_at: string;
  last_activity_at: string;
  paused_at?: string | null;
  completed_at?: string | null;
}

export interface StudyModesBridge {
  getReadiness: (documentId: string) => Promise<StudyModeReadiness>;
  getFlashcards: (documentId: string) => Promise<StudyDeckPayload>;
  generateFlashcards: (documentId: string, forceRegenerate?: boolean, targetCards?: number) => Promise<StudyDeckPayload>;
  editFlashcard: (documentId: string, cardId: string, updates: { front?: string; back?: string; topic?: string; question_difficulty?: string }) => Promise<AdaptiveFlashcard>;
  deleteFlashcard: (documentId: string, cardId: string) => Promise<boolean>;
  createFlashcard: (documentId: string, fields: { front: string; back: string; topic?: string; chapter_id?: string; section_id?: string; question_difficulty?: string; card_type?: string }) => Promise<AdaptiveFlashcard>;
  regenerateFlashcard: (documentId: string, cardId: string, allowOverwriteEdited?: boolean) => Promise<AdaptiveFlashcard>;
  reviewFlashcard: (documentId: string, cardId: string, rating: string, confidence?: number) => Promise<{ flashcard: AdaptiveFlashcard; srs_state: ReviewSchedulingState; progress: LearningProgressSnapshot }>;
  getCornell: (documentId: string) => Promise<{ cornell: CornellStudyDocument | null; readiness: StudyModeReadiness }>;
  generateCornell: (documentId: string, forceRegenerate?: boolean) => Promise<{ cornell: CornellStudyDocument | null; readiness: StudyModeReadiness }>;
  editCornellEntry: (documentId: string, sectionId: string, updates: { summary_section?: string; explanations?: string[]; supporting_details?: string[]; cue_column?: CornellCueItem[]; is_important?: boolean }) => Promise<CornellNoteEntry>;
  addCornellNote: (documentId: string, sectionId: string, content: string, isImportant?: boolean) => Promise<CornellPersonalNote>;
  exportCornellVault: (documentId: string) => Promise<{ vault_path: string; markdown: string }>;
  getAssessments: (documentId: string) => Promise<{ assessments: StudyAssessment[]; history: AssessmentAttempt[]; readiness: StudyModeReadiness }>;
  generateAssessment: (documentId: string, config: Partial<AssessmentConfig>) => Promise<StudyAssessment>;
  checkQuestion: (documentId: string, assessmentId: string, questionId: string, answer: any, useLlmForOpen?: boolean) => Promise<QuestionAttemptOutcome>;
  submitAssessment: (documentId: string, assessmentId: string, answers: Record<string, any>, useLlmForOpen?: boolean) => Promise<{ attempt: AssessmentAttempt; progress: LearningProgressSnapshot }>;
  getActiveRecall: (documentId: string) => Promise<{ prompts: ActiveRecallPrompt[]; history: ActiveRecallAttempt[]; readiness: StudyModeReadiness }>;
  generateActiveRecall: (documentId: string, forceRegenerate?: boolean, targetPrompts?: number) => Promise<{ prompts: ActiveRecallPrompt[] }>;
  submitActiveRecall: (documentId: string, promptId: string, payload: { student_response: string; self_confidence: number; outline_used?: boolean; use_llm?: boolean }) => Promise<{ attempt: ActiveRecallAttempt; srs_state: ReviewSchedulingState; progress: LearningProgressSnapshot }>;
  getDailyQueue: (documentId: string, dailyNewLimit?: number, dailyReviewLimit?: number) => Promise<DailyReviewQueue>;
  getProgress: (documentId: string, recompute?: boolean) => Promise<LearningProgressSnapshot>;
  startSession: (payload: { document_id: string; mode: string; title?: string; items?: StudySessionItemRef[]; item_ids?: string[]; config?: Record<string, any> }) => Promise<StudySessionState>;
  updateSession: (sessionId: string, payload: { item_id?: string; item_type?: string; partial_response?: any; outcome?: any; next_index?: number; mark_completed?: boolean }) => Promise<StudySessionState>;
  pauseSession: (sessionId: string) => Promise<StudySessionState>;
  resumeSession: (sessionId: string) => Promise<StudySessionState>;
  completeSession: (sessionId: string, summaryStats?: Record<string, any>) => Promise<StudySessionState>;
  listSessions: (documentId?: string, status?: string) => Promise<StudySessionState[]>;
}

