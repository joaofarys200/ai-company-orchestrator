import React, { useState } from 'react';
import {
  BookOpen,
  Code2,
  Database,
  ShieldCheck,
  Maximize2,
  Minimize2,
  ArrowUpRight,
  Sparkles,
  FileText,
  Activity,
  FolderOpen,
} from 'lucide-react';
import type { SpatialBoardDomain } from './boardBuilders';
import type {
  ProjectContextData,
  VaultDiagnosticsData,
  SentinelStatusData,
  SentinelSecurityEventData,
  SentinelActionData,
} from '../../protocol/websocket';
import type { StudyDocument } from '../study/types';
import { StatusPill } from '../../components/ui';

export interface SpatialOverviewPanelProps {
  domain: SpatialBoardDomain;
  studyDocuments: StudyDocument[];
  activeStudyDoc: StudyDocument | null;
  projectContext: ProjectContextData | null;
  projectFilesCount: number;
  isProjectRunning: boolean;
  previewUrl: string;
  notesCount: number;
  vaultDiagnostics: VaultDiagnosticsData | null;
  sentinelStatus: SentinelStatusData | null;
  sentinelEvents: SentinelSecurityEventData[];
  sentinelActions: SentinelActionData[];
  onCloseOverview: () => void;
  onJumpToTarget: (target: {
    domain: SpatialBoardDomain;
    studyTab?: 'landing' | 'library' | 'reader' | 'generated_doc' | 'summary' | 'practice';
    projectTab?: 'files' | 'coding' | 'architecture' | 'mission_control';
    obsidianTab?: 'vault' | 'graph' | 'rules';
    sentinelTab?: string;
    documentId?: string;
  }) => void;
}

export const SpatialOverviewPanel: React.FC<SpatialOverviewPanelProps> = ({
  domain,
  studyDocuments,
  activeStudyDoc,
  projectContext,
  projectFilesCount,
  isProjectRunning,
  previewUrl,
  notesCount,
  vaultDiagnostics,
  sentinelStatus,
  sentinelEvents,
  sentinelActions,
  onCloseOverview,
  onJumpToTarget,
}) => {
  const [focusedCard, setFocusedCard] = useState<string | null>(null);

  const renderCard = (
    id: string,
    title: string,
    subtitle: string,
    icon: React.ReactNode,
    body: React.ReactNode,
    ctaLabel: string,
    onAction: () => void
  ) => {
    const isFocused = focusedCard === id;
    const isDimmed = focusedCard !== null && !isFocused;
    return (
      <article
        key={id}
        data-testid={`spatial-card-${id}`}
        className={`flex flex-col rounded-xl border border-slate-800 bg-[#0b111a] p-4 transition-all ${
          isFocused
            ? 'col-span-full ring-1 ring-sky-500/40 shadow-2xl'
            : isDimmed
              ? 'opacity-45'
              : 'hover:border-slate-700'
        }`}
      >
        <div className="mb-3 flex items-start justify-between gap-2 border-b border-slate-800/80 pb-2.5">
          <div className="flex min-w-0 items-center gap-2.5">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-slate-800 bg-[#0f1722] text-sky-400">
              {icon}
            </div>
            <div className="min-w-0">
              <h3 className="truncate text-sm font-semibold text-slate-100">{title}</h3>
              <p className="truncate text-[11px] text-slate-400">{subtitle}</p>
            </div>
          </div>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => setFocusedCard(isFocused ? null : id)}
              className="rounded-md p-1.5 text-slate-400 hover:bg-slate-800 hover:text-slate-100"
              title={isFocused ? 'Restaurar vista' : 'Focar painel'}
            >
              {isFocused ? <Minimize2 className="h-3.5 w-3.5" /> : <Maximize2 className="h-3.5 w-3.5" />}
            </button>
          </div>
        </div>
        <div className="flex-1 text-xs text-slate-300">{body}</div>
        <div className="mt-4 flex justify-end border-t border-slate-800/70 pt-2.5">
          <button
            type="button"
            onClick={() => {
              onCloseOverview();
              onAction();
            }}
            className="inline-flex items-center gap-1.5 rounded-md border border-sky-500/30 bg-sky-500/10 px-2.5 py-1 text-[11px] font-medium text-sky-300 hover:bg-sky-500/20"
          >
            <span>{ctaLabel}</span>
            <ArrowUpRight className="h-3.5 w-3.5" />
          </button>
        </div>
      </article>
    );
  };

  return (
    <section data-testid="spatial-overview-panel" className="flex h-full flex-col overflow-y-auto bg-[#080c12] p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-slate-800/80 pb-3">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold text-slate-100">Vista Espacial do Domínio</h2>
            <StatusPill tone="accent">Sincronizada</StatusPill>
          </div>
          <p className="mt-0.5 text-xs text-slate-400">
            Panorama rápido de contexto e atalhos diretos para o workspace canónico sem duplicação de estado.
          </p>
        </div>
        <button
          type="button"
          onClick={onCloseOverview}
          className="rounded-md border border-slate-700 bg-[#0f1722] px-3 py-1.5 text-xs font-medium text-slate-200 hover:border-slate-600"
        >
          Voltar ao Workspace
        </button>
      </div>

      {domain === 'study' && (
        <div className={`grid gap-4 ${focusedCard ? 'grid-cols-1' : 'grid-cols-1 md:grid-cols-3'}`}>
          {renderCard(
            'study_reader',
            activeStudyDoc?.title || 'Nenhum material selecionado',
            activeStudyDoc
              ? `${activeStudyDoc.source_type} • ${activeStudyDoc.page_count} pág. • ${activeStudyDoc.subject}`
              : `${studyDocuments.length} materiais no catálogo`,
            <BookOpen className="h-4 w-4" />,
            <div className="space-y-2">
              <p className="text-slate-400">
                {activeStudyDoc?.extracted_text
                  ? `${activeStudyDoc.extracted_text.slice(0, 220).trim()}…`
                  : 'Abre a Biblioteca ou carrega um PDF/Vídeo para iniciar a leitura ativa.'}
              </p>
              {activeStudyDoc?.reading_progress && (
                <div className="text-[11px] text-slate-400">
                  Página atual: <span className="font-mono text-slate-200">{activeStudyDoc.reading_progress.current_page || 1}</span>
                </div>
              )}
            </div>,
            activeStudyDoc ? 'Abrir no Leitor' : 'Abrir Biblioteca',
            () => onJumpToTarget({ domain: 'study', studyTab: activeStudyDoc ? 'reader' : 'library', documentId: activeStudyDoc?.document_id })
          )}
          {renderCard(
            'study_synthesis',
            'Síntese & Documento IA',
            activeStudyDoc?.metadata?.generation_mode ? `Modo: ${activeStudyDoc.metadata.generation_mode}` : 'Phase 3–5 Grounded Pipeline',
            <Sparkles className="h-4 w-4" />,
            <p className="text-slate-400">
              Acesso direto à composição editorial estruturada (Documento IA) e sínteses fundamentadas com citações e rastreio de evidência.
            </p>,
            'Abrir Documento IA',
            () => onJumpToTarget({ domain: 'study', studyTab: 'generated_doc', documentId: activeStudyDoc?.document_id })
          )}
          {renderCard(
            'study_practice',
            'Prática Adaptativa & Ferramentas',
            'Flashcards SM-2 · Recordação Ativa · Quiz · Cornell',
            <FileText className="h-4 w-4" />,
            <p className="text-slate-400">
              {studyDocuments.length} materiais indexados para revisão espaçada, fichas Cornell e sessões guiadas.
            </p>,
            'Abrir Prática',
            () => onJumpToTarget({ domain: 'study', studyTab: 'practice', documentId: activeStudyDoc?.document_id })
          )}
        </div>
      )}

      {domain === 'project' && (
        <div className={`grid gap-4 ${focusedCard ? 'grid-cols-1' : 'grid-cols-1 md:grid-cols-3'}`}>
          {renderCard(
            'project_code',
            projectContext?.project_name || 'Nenhum projeto aberto',
            projectContext ? `${projectFilesCount} ficheiros · ${projectContext.stack.join(', ') || 'stack não detetada'}` : 'Seleciona ou cria um projeto',
            <Code2 className="h-4 w-4" />,
            <p className="text-slate-400">
              {projectContext?.root_path || 'Abre o explorador de projetos para editar ficheiros, navegar símbolos AST e gerir alterações IA.'}
            </p>,
            projectContext ? 'Abrir Editor IDE' : 'Ver Projetos',
            () => onJumpToTarget({ domain: 'project', projectTab: 'files' })
          )}
          {renderCard(
            'project_runtime',
            isProjectRunning ? 'Runtime Ativo' : 'Execução & Preview',
            previewUrl && previewUrl !== 'about:blank' ? previewUrl : 'Sem servidor de preview ativo',
            <FolderOpen className="h-4 w-4" />,
            <p className="text-slate-400">
              Dock inferior integrado no IDE com consola de logs, preview visual ao vivo e problemas sem sair do editor.
            </p>,
            'Ir para Código & Dock',
            () => onJumpToTarget({ domain: 'project', projectTab: 'files' })
          )}
          {renderCard(
            'project_missions',
            'Arquitetura & Missões',
            'AST · Dependências · DAG de Execução',
            <Activity className="h-4 w-4" />,
            <p className="text-slate-400">
              Supervisão de planos DAG, validação de contratos, Kanban e mapa arquitetural do projeto ativo.
            </p>,
            'Abrir Arquitetura',
            () => onJumpToTarget({ domain: 'project', projectTab: 'architecture' })
          )}
        </div>
      )}

      {domain === 'obsidian' && (
        <div className={`grid gap-4 ${focusedCard ? 'grid-cols-1' : 'grid-cols-1 md:grid-cols-3'}`}>
          {renderCard(
            'obsidian_vault',
            'Obsidian Vault & Notas',
            `${vaultDiagnostics?.total_notes ?? notesCount} notas Markdown`,
            <Database className="h-4 w-4" />,
            <p className="text-slate-400">
              Qualidade média: {vaultDiagnostics ? `${vaultDiagnostics.quality_average.toFixed(1)}%` : 'por auditar'} · Órfãs genuínas:{' '}
              {vaultDiagnostics?.genuine_orphans ?? 0} · Links quebrados: {vaultDiagnostics?.broken_links ?? 0}.
            </p>,
            'Abrir Notas & Editor',
            () => onJumpToTarget({ domain: 'obsidian', obsidianTab: 'vault' })
          )}
          {renderCard(
            'obsidian_graph',
            'Grafo de Ligações Epistémicas',
            `${vaultDiagnostics?.outgoing_edges ?? 0} ligações direcionadas`,
            <Sparkles className="h-4 w-4" />,
            <p className="text-slate-400">
              Visualização interativa de nós e arestas wikilink com realce de hubs, órfãs e auditoria 10D.
            </p>,
            'Abrir Grafo do Vault',
            () => onJumpToTarget({ domain: 'obsidian', obsidianTab: 'graph' })
          )}
          {renderCard(
            'obsidian_rules',
            'Memória Técnica & Regras RHO',
            'Regras aprendidas, arquitetura e decisões',
            <FileText className="h-4 w-4" />,
            <p className="text-slate-400">
              Gestão de regras persistidas pelo sistema e decisões de engenharia ligadas ao conhecimento do workspace.
            </p>,
            'Abrir Memória Técnica',
            () => onJumpToTarget({ domain: 'obsidian', obsidianTab: 'rules' })
          )}
        </div>
      )}

      {domain === 'sentinel' && (
        <div className={`grid gap-4 ${focusedCard ? 'grid-cols-1' : 'grid-cols-1 md:grid-cols-2'}`}>
          {renderCard(
            'sentinel_posture',
            `Postura Operacional: ${sentinelStatus?.posture || 'NOMINAL'}`,
            `Estado: ${sentinelStatus?.status || 'DESCONHECIDO'} · ${sentinelActions.filter((a) => a.status === 'WAITING_APPROVAL' || a.status === 'PROPOSED').length} ações pendentes`,
            <ShieldCheck className="h-4 w-4" />,
            <p className="text-slate-400">
              {sentinelEvents.length} eventos recentes registados. Auditoria em tempo real de processos, portas, persistência e ações HITL.
            </p>,
            'Abrir Cockpit Sentinel',
            () => onJumpToTarget({ domain: 'sentinel', sentinelTab: 'overview' })
          )}
        </div>
      )}
    </section>
  );
};
