export type SourceType =
  | 'PDF'
  | 'DOCX'
  | 'PPTX'
  | 'TXT'
  | 'MARKDOWN'
  | 'IMAGE'
  | 'AUDIO'
  | 'LECTURE_AUDIO'
  | 'NOTE';

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
  provenance: {
    source_file: string;
    ingested_at: string;
    evidence_status: EvidenceStatus;
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
  cue_column: Array<{ cue: string; idea: string }>;
  detailed_notes: string;
  glossary: string;
  action_items: string[];
}

export interface StudyCollection {
  collection_id: string;
  name: string;
  subject: string;
  document_ids: string[];
  created_at: string;
}

export type ExplanationLevel = 'Básico' | 'Intermédio' | 'Académico';
export type SummaryMode = 'Quick' | 'Study' | 'Detailed' | 'Exam';
