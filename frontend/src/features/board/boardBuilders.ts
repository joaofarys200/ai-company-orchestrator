import type { StudyDocument } from '../study/types';
import type {
  ProjectSummary,
  ProjectContextData,
  SentinelStatusData,
  SentinelSecurityEventData,
} from '../../protocol/websocket';

export type SpatialBoardDomain = 'study' | 'obsidian' | 'project' | 'sentinel';

export type SpatialCardKind =
  | 'stat'
  | 'bar_chart'
  | 'insight'
  | 'video'
  | 'study_notes'
  | 'code_files'
  | 'sentinel_alert';

export interface SpatialBoardCardData {
  id: string;
  title: string;
  subtitle?: string;
  kind: SpatialCardKind;
  type: SpatialCardKind;
  badge?: string;
  accent?: 'terracotta' | 'cyan' | 'emerald' | 'amber' | 'rose';
  colSpan?: 1 | 2;
}

export interface SpatialBoardData {
  boardId: string;
  domain: SpatialBoardDomain;
  title: string;
  subtitle: string;
  statusBadge: string;
  generationMode?: string;
  documentId?: string;
  projectId?: string;
  cards: SpatialBoardCardData[];
}

export function buildStudySpatialBoard(
  doc?: StudyDocument,
  allDocsCount = 0
): SpatialBoardData {
  if (!doc) {
    return {
      boardId: 'board_study_empty',
      domain: 'study',
      title: 'Estudo & Investigação Multimodal',
      subtitle: `${allDocsCount} materiais disponíveis`,
      statusBadge: 'Estudo Interativo',
      cards: [
        { id: 'card_reader', title: 'Leitor & Vídeo da Aula', kind: 'video', type: 'video' },
        { id: 'card_synthesis', title: 'Síntese Fundamentada (qwen3.5:9b)', kind: 'insight', type: 'insight' },
        { id: 'card_practice', title: 'Cornell Notes, Quiz & Flashcards', kind: 'study_notes', type: 'study_notes' },
      ],
    };
  }
  const meta = (doc.metadata || {}) as Record<string, unknown>;
  const genMode = String(meta.generation_mode || 'EXTRACTIVE_GROUNDED');
  return {
    boardId: `board_study_${doc.document_id}`,
    domain: 'study',
    documentId: doc.document_id,
    title: doc.title,
    subtitle: `${doc.subject || 'Geral'} • ${doc.source_type || 'DOC'}`,
    statusBadge:
      genMode === 'LLM_GROUNDED'
        ? 'IA Fundamentada • qwen3.5:9b'
        : genMode === 'PARTIAL'
          ? 'Síntese Parcial • qwen3.5:9b'
          : 'Extração Local Determinística',
    generationMode: genMode,
    cards: [
      { id: 'card_reader', title: 'Leitor Multimodal & Vídeo', kind: 'video', type: 'video' },
      { id: 'card_synthesis', title: 'Síntese & Mapa de Argumentos', kind: 'insight', type: 'insight' },
      { id: 'card_practice', title: 'Cornell Notes, Quiz & Flashcards', kind: 'study_notes', type: 'study_notes' },
    ],
  };
}

export function buildProjectSpatialBoard(
  projectId: string,
  projects: ProjectSummary[],
  _projectContext?: ProjectContextData | null,
  projectFiles: Record<string, string> = {},
  previewUrl = ''
): SpatialBoardData {
  const fileNames = Object.keys(projectFiles);
  const projSummary = projects.find((p) => p.project_id === projectId);
  const isRunning = Boolean(previewUrl);
  return {
    boardId: `board_project_${projectId || 'default'}`,
    domain: 'project',
    projectId: projectId || 'dina',
    title: `Projeto: ${projSummary?.project_name || projectId || 'Workspace'}`,
    subtitle: `${fileNames.length} ficheiros • ${isRunning ? `Em execução (${previewUrl})` : 'Pronto para editar/executar'}`,
    statusBadge: isRunning ? 'LIVE PREVIEW ATIVO' : 'Editor & Engenharia',
    cards: [
      { id: 'card_editor', title: 'Explorador & Editor de Código', kind: 'code_files', type: 'code_files' },
      { id: 'card_preview', title: 'Live Preview & Consola', kind: 'video', type: 'video' },
      { id: 'card_ai_change', title: 'Alteração Assistida por IA', kind: 'insight', type: 'insight' },
    ],
  };
}

export function buildObsidianSpatialBoard(
  notes: string[],
  studyDocuments?: StudyDocument[],
  query?: string
): SpatialBoardData {
  return {
    boardId: `board_obsidian_${query || 'vault'}`,
    domain: 'obsidian',
    title: 'Obsidian Knowledge Vault',
    subtitle: `${notes.length} notas Markdown indexadas • ${studyDocuments?.length || 0} materiais de estudo ligados`,
    statusBadge: 'Knowledge Graph Ativo',
    cards: [
      { id: 'card_vault_explorer', title: 'Explorador do Cofre Obsidian', kind: 'study_notes', type: 'study_notes' },
      { id: 'card_vault_editor', title: 'Leitor & Editor Markdown', kind: 'insight', type: 'insight' },
    ],
  };
}

export function buildSentinelSpatialBoard(
  status: SentinelStatusData | null,
  events: SentinelSecurityEventData[]
): SpatialBoardData {
  const mode = status?.status === 'RUNNING' ? 'WATCHDOG ATIVO' : 'STANDBY';
  return {
    boardId: 'board_sentinel_security',
    domain: 'sentinel',
    title: 'Sentinel Security & Runtime Governance',
    subtitle: `${events.length} eventos monitorizados • Postura: ${status?.posture || 'GOOD'}`,
    statusBadge: mode,
    cards: [
      { id: 'card_sentinel_control', title: 'Controlo & Ações Sentinel', kind: 'sentinel_alert', type: 'sentinel_alert' },
      { id: 'card_sentinel_events', title: 'Eventos & Auditoria em Tempo Real', kind: 'insight', type: 'insight' },
    ],
  };
}
