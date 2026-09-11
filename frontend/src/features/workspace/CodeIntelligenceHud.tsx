import React, { useMemo } from 'react';
import {
  ArrowRight,
  Boxes,
  Braces,
  FileCode2,
  Layers,
  Network,
  RefreshCw,
  Search,
  Sparkles,
  Zap,
} from 'lucide-react';
import type {
  ArchitectureSnapshot,
  AstState,
  ProjectContextData,
} from '../../protocol/websocket';

export interface CodeIntelligenceHudProps {
  projectContext: ProjectContextData | Partial<ProjectContextData> | null;
  architectureSnapshot?: ArchitectureSnapshot | null;
  astState?: AstState | null;
  onOpenEntrypoint?: (path: string) => void;
  onReindex?: () => void;
  onOpenArchitecture?: () => void;
  onSearchSymbols?: () => void;
  onOpenChanges?: () => void;
  isIndexing?: boolean;
}

export const CodeIntelligenceHud: React.FC<CodeIntelligenceHudProps> = ({
  projectContext,
  architectureSnapshot,
  astState,
  onOpenEntrypoint,
  onReindex,
  onOpenArchitecture,
  onSearchSymbols,
  onOpenChanges,
  isIndexing = false,
}) => {
  // 1. Compute Stack items with verified/inferred evidence
  const stackItems = useMemo(() => {
    const items: Array<{ name: string; status: 'VERIFIED' | 'INFERRED' | 'UNKNOWN' }> = [];
    const evidenceMap = architectureSnapshot?.stack?.evidence || {};

    const rawStack = [
      ...(architectureSnapshot?.stack?.languages || projectContext?.stack || []),
      ...(architectureSnapshot?.stack?.frameworks || projectContext?.frameworks || []),
      ...(architectureSnapshot?.stack?.package_managers || projectContext?.package_managers || []),
    ];

    const seen = new Set<string>();
    for (const item of rawStack) {
      if (!item || seen.has(item.toLowerCase())) continue;
      seen.add(item.toLowerCase());
      const evidence = evidenceMap[item];
      const status = (evidence?.status as 'VERIFIED' | 'INFERRED' | 'UNKNOWN') || 'VERIFIED';
      items.push({ name: item, status });
    }
    return items;
  }, [architectureSnapshot, projectContext]);

  // 2. Primary Entrypoint
  const primaryEntrypoint = useMemo(() => {
    if (architectureSnapshot?.entrypoints && architectureSnapshot.entrypoints.length > 0) {
      return architectureSnapshot.entrypoints[0];
    }
    if (projectContext?.entrypoints && projectContext.entrypoints.length > 0) {
      const epPath = projectContext.entrypoints[0];
      return {
        path: epPath,
        kind: epPath.endsWith('.html') ? 'FRONTEND' : 'BACKEND',
        source: 'package.json / entrypoint_scan',
        confidence: 0.95,
        resolution_method: 'intake_scan',
        status: 'VERIFIED',
      };
    }
    return null;
  }, [architectureSnapshot, projectContext]);

  // 3. Count symbols (functions, classes) and files from live AST / snapshot
  const counts = useMemo(() => {
    let filesCount = 0;
    let functionsCount = 0;
    let classesCount = 0;

    if (architectureSnapshot?.symbols) {
      functionsCount = architectureSnapshot.symbols.functions_count || 0;
      classesCount = architectureSnapshot.symbols.classes_count || 0;
    }

    if (astState) {
      let astFuncs = 0;
      let astClasses = 0;
      const fileKeys = Object.keys(astState);
      fileKeys.forEach((f) => {
        astFuncs += astState[f]?.functions?.length || 0;
        astClasses += astState[f]?.classes?.length || 0;
      });
      if (astFuncs > 0 || astClasses > 0) {
        functionsCount = astFuncs;
        classesCount = astClasses;
      }
      filesCount = fileKeys.length;
    }

    if (filesCount === 0) {
      filesCount = architectureSnapshot?.files?.length ||
        (projectContext?.ast_index?.files ? Object.keys(projectContext.ast_index.files).length : 0);
    }

    return { filesCount, functionsCount, classesCount };
  }, [architectureSnapshot, astState, projectContext]);

  // 4. Freshness status
  const freshness = useMemo(() => {
    const rawFreshness = architectureSnapshot?.freshness;
    if (rawFreshness) {
      return {
        status: rawFreshness.status || 'FRESH',
        changedFiles: rawFreshness.changed_files || [],
        lastIndexedAt: rawFreshness.last_indexed_at || projectContext?.last_indexed_at,
      };
    }
    if (architectureSnapshot?.staleness) {
      return {
        status: architectureSnapshot.staleness === 'FRESH' ? 'FRESH' : 'STALE',
        changedFiles: [],
        lastIndexedAt: projectContext?.last_indexed_at,
      };
    }
    return {
      status: 'FRESH' as const,
      changedFiles: [],
      lastIndexedAt: projectContext?.last_indexed_at,
    };
  }, [architectureSnapshot, projectContext]);

  const isStale = freshness.status === 'STALE' || freshness.status === 'PARTIALLY_STALE';

  if (!projectContext) return null;

  return (
    <div className="w-full border-b border-white/10 bg-gradient-to-r from-[#090e17] via-[#0b121e] to-[#070b13] px-3.5 py-2.5 text-xs text-gray-300">
      {/* ── Top Row: Project Header, Stack, Primary Entrypoint, Freshness, Actions ── */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        {/* Left Section: Project & Stack */}
        <div className="flex flex-wrap items-center gap-2.5 min-w-0">
          {/* Project Identity */}
          <div className="flex items-center gap-1.5 shrink-0">
            <span className="rounded bg-cyan-500/15 border border-cyan-400/30 p-1 text-cyan-300">
              <Layers className="h-3.5 w-3.5" />
            </span>
            <span className="font-semibold text-white tracking-wide">{projectContext.project_name}</span>
          </div>

          <div className="h-3 w-px bg-white/10 shrink-0" />

          {/* Stack Pills with Evidence Badges */}
          <div className="flex flex-wrap items-center gap-1.5">
            {stackItems.slice(0, 4).map((st) => (
              <span
                key={st.name}
                className="inline-flex items-center gap-1 rounded border border-white/8 bg-white/[0.04] px-1.5 py-0.5 text-[11px] font-medium text-gray-200"
                title={`Stack detetada: ${st.name} (${st.status})`}
              >
                <span>{st.name}</span>
                <span
                  className={`text-[9px] font-mono px-1 rounded uppercase tracking-wider ${
                    st.status === 'VERIFIED'
                      ? 'bg-emerald-400/15 text-emerald-300 border border-emerald-400/20'
                      : st.status === 'INFERRED'
                      ? 'bg-cyan-400/15 text-cyan-300 border border-cyan-400/20'
                      : 'bg-gray-500/20 text-gray-400 border border-gray-500/20'
                  }`}
                >
                  {st.status === 'VERIFIED' ? 'VERIF' : st.status === 'INFERRED' ? 'INF' : 'UNK'}
                </span>
              </span>
            ))}
          </div>

          <div className="h-3 w-px bg-white/10 shrink-0" />

          {/* Entrypoint with Confidence */}
          {primaryEntrypoint && (
            <div className="flex items-center gap-1.5 shrink-0">
              <span className="text-[10px] uppercase tracking-wider font-semibold text-gray-400">Entry:</span>
              <button
                type="button"
                onClick={() => onOpenEntrypoint?.(primaryEntrypoint.path)}
                className="inline-flex items-center gap-1 rounded bg-amber-400/10 border border-amber-400/25 px-1.5 py-0.5 text-[11px] font-mono font-medium text-amber-200 hover:bg-amber-400/20 hover:text-white transition-colors cursor-pointer"
                title={`Entrypoint primário: ${primaryEntrypoint.path} (${primaryEntrypoint.kind}, ${Math.round(
                  (primaryEntrypoint.confidence ?? 1) * 100
                )}% confiança)`}
              >
                <Zap className="h-3 w-3 text-amber-400" />
                <span>{primaryEntrypoint.path}</span>
                <span className="rounded bg-amber-400/20 px-1 text-[9px] font-semibold uppercase">
                  {primaryEntrypoint.kind}
                </span>
              </button>
            </div>
          )}
        </div>

        {/* Right Section: Metrics & Actions */}
        <div className="flex flex-wrap items-center gap-2 shrink-0">
          {/* Metrics Badges */}
          <div className="flex items-center gap-2 rounded-md border border-white/6 bg-black/40 px-2 py-1 font-mono text-[11px]">
            <span className="flex items-center gap-1 text-cyan-300" title="Ficheiros indexados">
              <FileCode2 className="h-3 w-3 text-cyan-400" />
              <strong className="font-semibold">{counts.filesCount}</strong> f
            </span>
            <span className="text-white/20">·</span>
            <span className="flex items-center gap-1 text-violet-300" title="Funções mapeadas no AST">
              <Braces className="h-3 w-3 text-violet-400" />
              <strong className="font-semibold">{counts.functionsCount}</strong> fn
            </span>
            <span className="text-white/20">·</span>
            <span className="flex items-center gap-1 text-sky-300" title="Classes mapeadas no AST">
              <Boxes className="h-3 w-3 text-sky-400" />
              <strong className="font-semibold">{counts.classesCount}</strong> cls
            </span>
          </div>

          {/* Freshness Badge */}
          <div
            className={`flex items-center gap-1 rounded border px-2 py-1 text-[10px] font-semibold tracking-wider uppercase font-mono ${
              freshness.status === 'FRESH'
                ? 'border-emerald-400/30 bg-emerald-400/10 text-emerald-300'
                : freshness.status === 'PARTIALLY_STALE'
                ? 'border-amber-400/30 bg-amber-400/10 text-amber-300'
                : 'border-rose-400/30 bg-rose-400/10 text-rose-300'
            }`}
            title={
              isStale
                ? `Arquitetura STALE: ${freshness.changedFiles.length} ficheiros modificados desde a última indexação.`
                : 'Arquitetura FRESH: índice sincronizado com o disco.'
            }
          >
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                freshness.status === 'FRESH'
                  ? 'bg-emerald-400 animate-pulse'
                  : freshness.status === 'PARTIALLY_STALE'
                  ? 'bg-amber-400'
                  : 'bg-rose-400 animate-ping'
              }`}
            />
            <span>{freshness.status}</span>
          </div>

          {/* Action: Reindex */}
          {onReindex && (
            <button
              type="button"
              onClick={onReindex}
              disabled={isIndexing}
              className={`flex items-center gap-1.5 rounded border px-2.5 py-1 text-xs font-semibold transition-all cursor-pointer ${
                isStale
                  ? 'border-amber-400/50 bg-amber-400/20 text-amber-100 hover:bg-amber-400/30 animate-pulse'
                  : 'border-white/10 bg-white/[0.04] text-gray-300 hover:bg-white/[0.08] hover:text-white'
              } disabled:opacity-50`}
              title="Atualizar árvore e re-computar snapshot AST"
            >
              <RefreshCw className={`h-3 w-3 ${isIndexing ? 'animate-spin text-cyan-300' : ''}`} />
              <span>{isIndexing ? 'A indexar...' : 'Atualizar Árvore'}</span>
            </button>
          )}

          {/* Action: Open Architecture */}
          {onOpenArchitecture && (
            <button
              type="button"
              onClick={onOpenArchitecture}
              className="flex items-center gap-1.5 rounded border border-cyan-400/30 bg-cyan-400/10 px-2.5 py-1 text-xs font-semibold text-cyan-200 hover:bg-cyan-400/20 transition-all cursor-pointer"
              title="Explorar Mapa de Arquitetura e AST Completo"
            >
              <Network className="h-3 w-3 text-cyan-300" />
              <span>Arquitetura & AST</span>
              <ArrowRight className="h-3 w-3" />
            </button>
          )}

          {/* Action: Search Symbols */}
          {onSearchSymbols && (
            <button
              type="button"
              onClick={onSearchSymbols}
              className="flex items-center gap-1 rounded border border-white/8 bg-white/[0.03] p-1 text-gray-400 hover:bg-white/[0.08] hover:text-white transition-all"
              title="Pesquisar Símbolos AST"
            >
              <Search className="h-3.5 w-3.5" />
            </button>
          )}

          {/* Action: Assisted Changes */}
          {onOpenChanges && (
            <button
              type="button"
              onClick={onOpenChanges}
              className="flex items-center gap-1 rounded border border-violet-400/30 bg-violet-400/10 px-2 py-1 text-xs font-semibold text-violet-200 hover:bg-violet-400/20 transition-all cursor-pointer"
              title="Alteração Assistida por IA"
            >
              <Sparkles className="h-3 w-3 text-violet-300" />
              <span>Alteração</span>
            </button>
          )}
        </div>
      </div>

      {/* ── Stale Warning Alert Banner (Visible when files changed on disk) ── */}
      {isStale && (
        <div className="mt-2.5 flex items-center justify-between gap-3 rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-1.5 text-xs text-amber-200 animate-fadeIn">
          <div className="flex items-center gap-2 min-w-0">
            <span className="flex h-2 w-2 rounded-full bg-amber-400 animate-ping shrink-0" />
            <span className="font-semibold uppercase tracking-wider text-[11px] text-amber-300">
              Arquitetura STALE:
            </span>
            <span className="truncate">
              {freshness.changedFiles.length > 0
                ? `${freshness.changedFiles.length} ficheiro(s) modificado(s) desde a última indexação (${freshness.changedFiles.slice(0, 3).join(', ')}${freshness.changedFiles.length > 3 ? '...' : ''}).`
                : 'Ficheiros foram alterados em disco desde o último snapshot.'}
            </span>
          </div>
          {onReindex && (
            <button
              type="button"
              onClick={onReindex}
              disabled={isIndexing}
              className="flex items-center gap-1.5 rounded bg-amber-400/25 border border-amber-400/40 px-2.5 py-0.5 text-[11px] font-bold text-amber-100 hover:bg-amber-400/35 transition-colors shrink-0 cursor-pointer"
            >
              <RefreshCw className={`h-3 w-3 ${isIndexing ? 'animate-spin' : ''}`} />
              <span>Reindexar Agora</span>
            </button>
          )}
        </div>
      )}
    </div>
  );
};
