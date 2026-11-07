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
  created_at: string;
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
