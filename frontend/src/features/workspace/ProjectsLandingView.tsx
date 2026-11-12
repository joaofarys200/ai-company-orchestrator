import React, { useMemo, useState } from 'react';
import {
  Code2,
  FolderOpen,
  LayoutGrid,
  LayoutList,
  Plus,
  RefreshCw,
  Rocket,
  Search,
  Sparkles,
  Star,
  Terminal,
  Trash2,
} from 'lucide-react';
import type { ProjectSummary } from '../../protocol/websocket';
import { PanelEmptyState } from '../../components/ui';
import {
  STORAGE_FAV_KEY,
  STORAGE_RECENT_KEY,
  STORAGE_VIEW_KEY,
  readStringList,
  recordRecentProject,
} from './projectStorage';

const TECHNICAL_PROJECT_PATTERN =
  /(benchmark|fixture|flight-recorder|health-attempt|mission-validation|validation-|stress|scratch|diagnostic)/i;

export interface ProjectsLandingViewProps {
  projects: ProjectSummary[];
  activeProjectId?: string;
  onOpenProject: (projectId: string) => void;
  onCreateNewProject: (presetTemplate?: string) => void;
  onDeleteProject: (project: { id: string; name: string }) => void;
  onRefreshProjects: () => void;
}

const STARTER_TEMPLATES = [
  { id: 'web-app', label: 'Web App (React + API)', desc: 'Frontend SPA e servidor HTTP', icon: Rocket },
  { id: 'python-api', label: 'Python Service / API', desc: 'Backend Python modular e testes pytest', icon: Terminal },
  { id: 'empty', label: 'Workspace Limpo', desc: 'Estrutura mínima configurável', icon: Code2 },
] as const;

export const ProjectsLandingView: React.FC<ProjectsLandingViewProps> = ({
  projects,
  activeProjectId,
  onOpenProject,
  onCreateNewProject,
  onDeleteProject,
  onRefreshProjects,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [scope, setScope] = useState<'all' | 'recent' | 'favorites'>('all');
  const [showTechnical, setShowTechnical] = useState(false);
  const [viewMode, setViewMode] = useState<'list' | 'grid'>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_VIEW_KEY);
      return saved === 'grid' ? 'grid' : 'list';
    } catch {
      return 'list';
    }
  });
  const [favorites, setFavorites] = useState<string[]>(() => readStringList(STORAGE_FAV_KEY));
  const [recentIds] = useState<string[]>(() => readStringList(STORAGE_RECENT_KEY));

  const toggleViewMode = (mode: 'list' | 'grid') => {
    setViewMode(mode);
    try {
      localStorage.setItem(STORAGE_VIEW_KEY, mode);
    } catch {
      // Ignore storage write errors
    }
  };

  const toggleFavorite = (projectId: string) => {
    setFavorites((prev) => {
      const next = prev.includes(projectId) ? prev.filter((id) => id !== projectId) : [projectId, ...prev];
      try {
        localStorage.setItem(STORAGE_FAV_KEY, JSON.stringify(next));
      } catch {
        // Ignore storage write errors
      }
      return next;
    });
  };

  const filtered = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return projects
      .filter((p) => {
        const isTech = TECHNICAL_PROJECT_PATTERN.test(`${p.project_name} ${p.project_id}`);
        if (!showTechnical && isTech) return false;
        if (scope === 'favorites' && !favorites.includes(p.project_id)) return false;
        if (scope === 'recent' && recentIds.length > 0 && !recentIds.includes(p.project_id)) return false;
        if (!q) return true;
        const hay = `${p.project_name} ${p.project_id} ${p.root_path || ''}`.toLowerCase();
        return hay.includes(q);
      })
      .sort((a, b) => {
        if (scope === 'recent') {
          return recentIds.indexOf(a.project_id) - recentIds.indexOf(b.project_id);
        }
        const aFav = favorites.includes(a.project_id) ? 0 : 1;
        const bFav = favorites.includes(b.project_id) ? 0 : 1;
        if (aFav !== bFav) return aFav - bFav;
        return a.project_name.localeCompare(b.project_name, 'pt');
      });
  }, [favorites, projects, recentIds, scope, searchQuery, showTechnical]);

  return (
    <div data-testid="projects-landing-view" className="flex h-full flex-col overflow-y-auto bg-[#080c12] p-5 text-slate-200">
      <div className="mx-auto w-full max-w-6xl space-y-5">
        {/* Header + Primary Action */}
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800/80 pb-4">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wider text-sky-400">
              Ambiente de Engenharia & IDE
            </p>
            <h2 className="mt-0.5 text-lg font-semibold text-slate-100">Projetos & Repositórios</h2>
            <p className="text-xs text-slate-400">
              Seleciona um projeto para abrir o explorador de ficheiros, editor Monaco e consola integrada.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onRefreshProjects}
              className="inline-flex h-8.5 items-center gap-1.5 rounded-lg border border-slate-800 bg-[#0f1722] px-3 text-xs text-slate-300 hover:border-slate-700 hover:text-white cursor-pointer"
              title="Atualizar lista de projetos"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              <span>Atualizar</span>
            </button>
            <button
              type="button"
              data-testid="landing-new-project-btn"
              onClick={() => onCreateNewProject()}
              className="inline-flex h-8.5 items-center gap-1.5 rounded-lg border border-sky-400/35 bg-sky-500/15 px-3.5 text-xs font-semibold text-sky-200 hover:bg-sky-500/25 cursor-pointer"
            >
              <Plus className="h-3.5 w-3.5" />
              <span>Novo Projeto</span>
            </button>
          </div>
        </div>

        {/* Starter Templates Strip */}
        <section className="grid gap-3 md:grid-cols-3">
          {STARTER_TEMPLATES.map((tpl) => {
            const Icon = tpl.icon;
            return (
              <button
                key={tpl.id}
                type="button"
                onClick={() => onCreateNewProject(tpl.id)}
                className="flex items-start gap-3 rounded-xl border border-slate-800/90 bg-[#0b111a] p-3.5 text-left transition hover:border-sky-500/35 hover:bg-[#0f1722] cursor-pointer"
              >
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-sky-400/25 bg-sky-500/10 text-sky-300">
                  <Icon className="h-4 w-4" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-100">
                    <span>{tpl.label}</span>
                    <Sparkles className="h-3 w-3 text-sky-400" />
                  </div>
                  <p className="mt-1 text-[11px] text-slate-400">{tpl.desc}</p>
                </div>
              </button>
            );
          })}
        </section>

        {/* Filter Bar */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-1 rounded-lg border border-slate-800 bg-[#0b111a] p-0.5 text-xs">
            {(
              [
                { id: 'all', label: 'Todos' },
                { id: 'recent', label: 'Recentes' },
                { id: 'favorites', label: 'Favoritos' },
              ] as const
            ).map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setScope(tab.id)}
                className={`rounded-md px-3 py-1.5 font-medium transition cursor-pointer ${
                  scope === tab.id
                    ? 'bg-sky-500/15 text-sky-200 border border-sky-400/30'
                    : 'text-slate-400 hover:text-slate-200 border border-transparent'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-500" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Filtrar projetos ou stack..."
                className="h-8 w-56 rounded-lg border border-slate-800 bg-[#0b111a] pl-8 pr-3 text-xs text-slate-200 placeholder-slate-500 focus:border-sky-400/40 focus:outline-none"
              />
            </div>

            <button
              type="button"
              onClick={() => setShowTechnical((v) => !v)}
              className={`h-8 rounded-lg border px-2.5 text-[11px] font-medium transition cursor-pointer ${
                showTechnical
                  ? 'border-sky-400/30 bg-sky-500/10 text-sky-200'
                  : 'border-slate-800 bg-[#0b111a] text-slate-400 hover:text-slate-200'
              }`}
            >
              Técnicos
            </button>

            <div className="flex items-center rounded-lg border border-slate-800 bg-[#0b111a] p-0.5">
              <button
                type="button"
                onClick={() => toggleViewMode('list')}
                className={`rounded p-1.5 cursor-pointer ${viewMode === 'list' ? 'bg-slate-800 text-sky-300' : 'text-slate-500 hover:text-slate-300'}`}
                title="Vista em Lista"
              >
                <LayoutList className="h-3.5 w-3.5" />
              </button>
              <button
                type="button"
                onClick={() => toggleViewMode('grid')}
                className={`rounded p-1.5 cursor-pointer ${viewMode === 'grid' ? 'bg-slate-800 text-sky-300' : 'text-slate-500 hover:text-slate-300'}`}
                title="Vista em Grelha"
              >
                <LayoutGrid className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        </div>

        {/* Projects List or Grid */}
        {filtered.length === 0 ? (
          <PanelEmptyState
            icon={FolderOpen}
            title="Nenhum projeto encontrado"
            description="Cria um novo projeto ou ajusta os filtros de pesquisa acima."
            action={
              <button
                type="button"
                onClick={() => onCreateNewProject()}
                className="inline-flex items-center gap-1.5 rounded-lg border border-sky-400/35 bg-sky-500/15 px-3 py-1.5 text-xs font-semibold text-sky-200 hover:bg-sky-500/25 cursor-pointer"
              >
                <Plus className="h-3.5 w-3.5" />
                <span>Criar Primeiro Projeto</span>
              </button>
            }
          />
        ) : viewMode === 'list' ? (
          <div className="overflow-hidden rounded-xl border border-slate-800/90 bg-[#0b111a] divide-y divide-slate-800/70">
            {filtered.map((project) => {
              const isFav = favorites.includes(project.project_id);
              const isCurrent = activeProjectId === project.project_id;
              return (
                <div
                  key={project.project_id}
                  onClick={() => {
                    recordRecentProject(project.project_id);
                    onOpenProject(project.project_id);
                  }}
                  className="group flex items-center justify-between gap-4 px-4 py-3 transition hover:bg-[#0f1722] cursor-pointer"
                >
                  <div className="flex min-w-0 flex-1 items-center gap-3">
                    <FolderOpen className={`h-4 w-4 shrink-0 ${isCurrent ? 'text-sky-400' : 'text-slate-400'}`} />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="truncate text-xs font-semibold text-slate-100">{project.project_name}</span>
                        {isCurrent && (
                          <span className="rounded bg-sky-500/15 px-1.5 py-0.5 text-[10px] font-medium text-sky-300">
                            Ativo
                          </span>
                        )}
                      </div>
                      <p className="truncate font-mono text-[11px] text-slate-500">{project.project_id}</p>
                    </div>
                  </div>

                  <div className="hidden sm:flex items-center gap-1.5 min-w-0 max-w-xs">
                    {project.root_path && (
                      <span
                        className="truncate rounded border border-slate-800 bg-[#080c12] px-2 py-0.5 font-mono text-[10px] text-slate-400"
                        title={project.root_path}
                      >
                        {project.root_path}
                      </span>
                    )}
                  </div>

                  <div className="flex items-center gap-1.5 shrink-0">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        toggleFavorite(project.project_id);
                      }}
                      className={`rounded p-1.5 transition cursor-pointer ${
                        isFav ? 'text-amber-400 hover:bg-amber-500/10' : 'text-slate-500 hover:text-slate-200 hover:bg-slate-800'
                      }`}
                      title={isFav ? 'Remover dos favoritos' : 'Marcar como favorito'}
                    >
                      <Star className={`h-3.5 w-3.5 ${isFav ? 'fill-current' : ''}`} />
                    </button>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onDeleteProject({ id: project.project_id, name: project.project_name });
                      }}
                      className="rounded p-1.5 text-slate-500 opacity-0 group-hover:opacity-100 hover:bg-rose-500/10 hover:text-rose-400 transition cursor-pointer"
                      title={`Eliminar ${project.project_name}`}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {filtered.map((project) => {
              const isFav = favorites.includes(project.project_id);
              const isCurrent = activeProjectId === project.project_id;
              return (
                <article
                  key={project.project_id}
                  onClick={() => {
                    recordRecentProject(project.project_id);
                    onOpenProject(project.project_id);
                  }}
                  className="group flex flex-col justify-between gap-3 rounded-xl border border-slate-800/90 bg-[#0b111a] p-4 transition hover:border-sky-500/35 hover:bg-[#0f1722] cursor-pointer"
                >
                  <div>
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2 min-w-0">
                        <FolderOpen className={`h-4 w-4 shrink-0 ${isCurrent ? 'text-sky-400' : 'text-slate-400'}`} />
                        <h3 className="truncate text-sm font-semibold text-slate-100">{project.project_name}</h3>
                      </div>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          toggleFavorite(project.project_id);
                        }}
                        className={`rounded p-1 cursor-pointer ${isFav ? 'text-amber-400' : 'text-slate-500 hover:text-slate-200'}`}
                      >
                        <Star className={`h-3.5 w-3.5 ${isFav ? 'fill-current' : ''}`} />
                      </button>
                    </div>
                    <p className="mt-1 truncate font-mono text-[11px] text-slate-500">{project.project_id}</p>
                    {project.root_path && (
                      <p className="mt-2 truncate rounded border border-slate-800 bg-[#080c12] px-2 py-0.5 font-mono text-[10px] text-slate-400" title={project.root_path}>
                        {project.root_path}
                      </p>
                    )}
                  </div>
                  <div className="flex items-center justify-between border-t border-slate-800/70 pt-2.5 text-[11px]">
                    <span className="font-semibold text-sky-300">Abrir no Editor →</span>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onDeleteProject({ id: project.project_id, name: project.project_name });
                      }}
                      className="rounded p-1 text-slate-500 hover:bg-rose-500/10 hover:text-rose-400 cursor-pointer"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
