import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Editor, { loader, type BeforeMount, type OnMount } from '@monaco-editor/react';
import * as monaco from 'monaco-editor';
import {
  Braces,
  Check,
  ChevronDown,
  ChevronRight,
  CircleAlert,
  Code2,
  Copy,
  FileCode2,
  FileJson,
  FileSpreadsheet,
  FileText,
  Files,
  Folder,
  FolderOpen,
  GitPullRequest,
  Layers,
  Palette,
  Play,
  Save,
  Search,
  Trash2,
  WandSparkles,
  X,
} from 'lucide-react';

type MonacoGlobal = typeof globalThis & {
  MonacoEnvironment?: {
    getWorker: (_moduleId: string, label: string) => Worker;
  };
};

(globalThis as MonacoGlobal).MonacoEnvironment = {
  getWorker: (_moduleId, label) => {
    if (label === 'json') {
      return new Worker(new URL('../../../node_modules/monaco-editor/esm/vs/language/json/json.worker.js', import.meta.url), { type: 'module' });
    }
    if (label === 'css' || label === 'scss' || label === 'less') {
      return new Worker(new URL('../../../node_modules/monaco-editor/esm/vs/language/css/css.worker.js', import.meta.url), { type: 'module' });
    }
    if (label === 'html' || label === 'handlebars' || label === 'razor') {
      return new Worker(new URL('../../../node_modules/monaco-editor/esm/vs/language/html/html.worker.js', import.meta.url), { type: 'module' });
    }
    if (label === 'typescript' || label === 'javascript') {
      return new Worker(new URL('../../../node_modules/monaco-editor/esm/vs/language/typescript/ts.worker.js', import.meta.url), { type: 'module' });
    }
    return new Worker(new URL('../../../node_modules/monaco-editor/esm/vs/editor/editor.worker.js', import.meta.url), { type: 'module' });
  },
};

loader.config({ monaco });

interface FileTreeNode {
  name: string;
  path: string;
  type: 'file' | 'directory';
  children: FileTreeNode[];
}

interface SaveState {
  ok: boolean;
  filename: string;
  error: string;
}

interface CodeEditorProps {
  projectId: string;
  projectName: string;
  rootPath: string;
  files: Record<string, string>;
  selectedFile: string;
  onSelectFile: (filename: string) => void;
  onSaveFile: (filename: string, content: string) => void;
  onDeleteFile?: (filename: string) => void;
  onOpenChanges: () => void;
  onOpenPreview: () => void;
  isSaving: boolean;
  saveState: SaveState | null;
  insights: React.ReactNode;
}

const languageByExtension: Record<string, string> = {
  cjs: 'javascript',
  css: 'css',
  html: 'html',
  htm: 'html',
  js: 'javascript',
  json: 'json',
  jsx: 'javascript',
  md: 'markdown',
  mjs: 'javascript',
  py: 'python',
  sql: 'sql',
  toml: 'ini',
  ts: 'typescript',
  tsx: 'typescript',
  txt: 'plaintext',
  yaml: 'yaml',
  yml: 'yaml',
};

function languageFor(filename: string) {
  const extension = filename.split('.').pop()?.toLowerCase() ?? '';
  return languageByExtension[extension] ?? 'plaintext';
}

function buildTree(filenames: string[]): FileTreeNode[] {
  const root: FileTreeNode = { name: '', path: '', type: 'directory', children: [] };

  for (const filename of filenames) {
    const parts = filename.split('/').filter(Boolean);
    let parent = root;
    parts.forEach((part, index) => {
      const path = parts.slice(0, index + 1).join('/');
      const type = index === parts.length - 1 ? 'file' : 'directory';
      let node = parent.children.find((entry) => entry.name === part && entry.type === type);
      if (!node) {
        node = { name: part, path, type, children: [] };
        parent.children.push(node);
      }
      parent = node;
    });
  }

  const sortNodes = (nodes: FileTreeNode[]) => {
    nodes.sort((left, right) => {
      if (left.type !== right.type) return left.type === 'directory' ? -1 : 1;
      return left.name.localeCompare(right.name);
    });
    nodes.forEach((node) => sortNodes(node.children));
  };
  sortNodes(root.children);
  return root.children;
}

function FileIcon({ filename }: { filename: string }) {
  const extension = filename.split('.').pop()?.toLowerCase();
  if (extension === 'json') return <FileJson className="h-3.5 w-3.5 shrink-0 text-amber-400" />;
  if (extension === 'md' || extension === 'txt') return <FileText className="h-3.5 w-3.5 shrink-0 text-sky-300" />;
  if (['js', 'mjs', 'cjs'].includes(extension ?? '')) return <Braces className="h-3.5 w-3.5 shrink-0 text-amber-300" />;
  if (['ts', 'tsx', 'jsx'].includes(extension ?? '')) return <Braces className="h-3.5 w-3.5 shrink-0 text-cyan-400" />;
  if (['html', 'htm'].includes(extension ?? '')) return <FileCode2 className="h-3.5 w-3.5 shrink-0 text-orange-400" />;
  if (['css', 'scss', 'less'].includes(extension ?? '')) return <Palette className="h-3.5 w-3.5 shrink-0 text-pink-400" />;
  if (extension === 'py') return <FileCode2 className="h-3.5 w-3.5 shrink-0 text-emerald-400" />;
  if (['yaml', 'yml', 'toml'].includes(extension ?? '')) return <FileSpreadsheet className="h-3.5 w-3.5 shrink-0 text-violet-400" />;
  return <FileCode2 className="h-3.5 w-3.5 shrink-0 text-cyan-300/80" />;
}

function TreeRow({
  node,
  depth,
  selectedFile,
  expanded,
  onToggle,
  onSelect,
  onDelete,
}: {
  node: FileTreeNode;
  depth: number;
  selectedFile: string;
  expanded: Set<string>;
  onToggle: (path: string) => void;
  onSelect: (path: string) => void;
  onDelete?: (path: string) => void;
}) {
  const isExpanded = expanded.has(node.path);
  const selected = node.type === 'file' && node.path === selectedFile;

  return (
    <>
      <button
        type="button"
        onClick={() => (node.type === 'directory' ? onToggle(node.path) : onSelect(node.path))}
        className={`group flex h-7 w-full items-center gap-1.5 pr-2 text-left text-xs transition-colors ${
          selected
            ? 'bg-cyan-500/15 text-cyan-200 font-medium border-l-2 border-cyan-400'
            : 'text-gray-300 hover:bg-white/[0.04] hover:text-white'
        }`}
        style={{ paddingLeft: `${8 + depth * 14}px` }}
        title={node.path}
      >
        {node.type === 'directory' ? (
          <>
            {isExpanded ? (
              <ChevronDown className="h-3.5 w-3.5 shrink-0 text-gray-400 group-hover:text-gray-200" />
            ) : (
              <ChevronRight className="h-3.5 w-3.5 shrink-0 text-gray-400 group-hover:text-gray-200" />
            )}
            {isExpanded ? (
              <FolderOpen className="h-3.5 w-3.5 shrink-0 text-cyan-300" />
            ) : (
              <Folder className="h-3.5 w-3.5 shrink-0 text-cyan-400/70" />
            )}
          </>
        ) : (
          <>
            <span className="w-3.5 shrink-0" />
            <FileIcon filename={node.name} />
          </>
        )}
        <span className="min-w-0 flex-1 truncate">{node.name}</span>
        {node.type === 'file' && onDelete && (
          <button
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              onDelete(node.path);
            }}
            className="opacity-0 group-hover:opacity-100 p-0.5 text-gray-500 hover:text-rose-400 rounded transition-all shrink-0"
            title={`Eliminar ${node.name}`}
          >
            <Trash2 className="h-3 w-3" />
          </button>
        )}
      </button>
      {node.type === 'directory' && isExpanded && node.children.map((child) => (
        <TreeRow
          key={`${child.type}-${child.path}`}
          node={child}
          depth={depth + 1}
          selectedFile={selectedFile}
          expanded={expanded}
          onToggle={onToggle}
          onSelect={onSelect}
          onDelete={onDelete}
        />
      ))}
    </>
  );
}

export function CodeEditor({
  projectId,
  projectName,
  rootPath,
  files,
  selectedFile,
  onSelectFile,
  onSaveFile,
  onDeleteFile,
  onOpenChanges,
  onOpenPreview,
  isSaving,
  saveState,
  insights,
}: CodeEditorProps) {
  const filenames = useMemo(() => Object.keys(files).sort((left, right) => left.localeCompare(right)), [files]);
  const [fileFilter, setFileFilter] = useState('');
  const filteredFilenames = useMemo(() => {
    if (!fileFilter.trim()) return filenames;
    return filenames.filter((f) => f.toLowerCase().includes(fileFilter.toLowerCase().trim()));
  }, [filenames, fileFilter]);
  const tree = useMemo(() => buildTree(filteredFilenames), [filteredFilenames]);

  const [openFiles, setOpenFiles] = useState<string[]>(selectedFile ? [selectedFile] : []);
  const [drafts, setDrafts] = useState<Record<string, string>>(files);
  const [expanded, setExpanded] = useState<Set<string>>(() => {
    const parentParts = selectedFile.split('/').slice(0, -1);
    return new Set(parentParts.map((_, index) => parentParts.slice(0, index + 1).join('/')));
  });
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [insightsOpen, setInsightsOpen] = useState(false);
  const [fileToDelete, setFileToDelete] = useState<string | null>(null);
  const [cursor, setCursor] = useState({ line: 1, column: 1 });
  const [copiedPath, setCopiedPath] = useState(false);
  const editorInstanceRef = useRef<monaco.editor.IStandaloneCodeEditor | null>(null);
  const saveCurrentRef = useRef<() => void>(() => undefined);

  const handleDeleteRequest = (path: string) => {
    setFileToDelete(path);
  };

  const handleConfirmDelete = () => {
    if (fileToDelete && onDeleteFile) {
      onDeleteFile(fileToDelete);
      closeFile(fileToDelete);
      setFileToDelete(null);
    }
  };

  const currentDraft = selectedFile ? drafts[selectedFile] ?? files[selectedFile] ?? '' : '';
  const dirtyFiles = new Set(filenames.filter((filename) => (drafts[filename] ?? files[filename]) !== files[filename]));
  const currentDirty = Boolean(selectedFile && dirtyFiles.has(selectedFile));

  const saveCurrent = useCallback(() => {
    if (!selectedFile || !currentDirty || isSaving) return;
    onSaveFile(selectedFile, currentDraft);
  }, [currentDirty, currentDraft, isSaving, onSaveFile, selectedFile]);

  useEffect(() => {
    saveCurrentRef.current = saveCurrent;
  }, [saveCurrent]);

  const formatCode = useCallback(() => {
    if (editorInstanceRef.current) {
      editorInstanceRef.current.getAction('editor.action.formatDocument')?.run();
    }
  }, []);

  const copyFilePath = useCallback(() => {
    if (!selectedFile) return;
    navigator.clipboard.writeText(selectedFile);
    setCopiedPath(true);
    setTimeout(() => setCopiedPath(false), 1500);
  }, [selectedFile]);

  const visibleOpenFiles = selectedFile && !openFiles.includes(selectedFile)
    ? [...openFiles, selectedFile]
    : openFiles;

  const visibleExpanded = useMemo(() => {
    const next = new Set(expanded);
    const parentParts = selectedFile.split('/').slice(0, -1);
    parentParts.forEach((_, index) => next.add(parentParts.slice(0, index + 1).join('/')));
    return next;
  }, [expanded, selectedFile]);

  const handleEditorMount: OnMount = (editor, editorApi) => {
    editorInstanceRef.current = editor;
    editor.focus();
    editor.onDidChangeCursorPosition((event) => {
      setCursor({ line: event.position.lineNumber, column: event.position.column });
    });
    editor.addCommand(editorApi.KeyMod.CtrlCmd | editorApi.KeyCode.KeyS, () => saveCurrentRef.current());
    editor.addCommand(editorApi.KeyMod.Shift | editorApi.KeyMod.Alt | editorApi.KeyCode.KeyF, formatCode);
  };

  const handleBeforeMount: BeforeMount = (editorApi) => {
    editorApi.editor.defineTheme('jarvis-studio-dark', {
      base: 'vs-dark',
      inherit: true,
      rules: [
        { token: 'comment', foreground: '6b7280', fontStyle: 'italic' },
        { token: 'keyword', foreground: 'c084fc', fontStyle: 'bold' },
        { token: 'string', foreground: '34d399' },
        { token: 'number', foreground: 'f59e0b' },
        { token: 'type', foreground: '38bdf8' },
        { token: 'function', foreground: '60a5fa' },
      ],
      colors: {
        'editor.background': '#07090e',
        'editorGutter.background': '#07090e',
        'editorLineNumber.foreground': '#374151',
        'editorLineNumber.activeForeground': '#9ca3af',
        'editor.selectionBackground': '#1e3a5f',
        'editor.inactiveSelectionBackground': '#14253d',
        'editorCursor.foreground': '#38bdf8',
        'editorIndentGuide.background1': '#111827',
        'editorIndentGuide.activeBackground1': '#1f2937',
        'editorOverviewRuler.border': '#07090e',
      },
    });
  };

  const selectFile = (filename: string) => {
    onSelectFile(filename);
    setOpenFiles((current) => current.includes(filename) ? current : [...current, filename]);
  };

  const closeFile = (filename: string) => {
    if (dirtyFiles.has(filename)) {
      if (!window.confirm(`Fechar ${filename} sem guardar?`)) return;
      setDrafts((current) => ({ ...current, [filename]: files[filename] ?? '' }));
    }
    const index = visibleOpenFiles.indexOf(filename);
    const nextFiles = visibleOpenFiles.filter((item) => item !== filename);
    setOpenFiles(nextFiles);
    if (selectedFile === filename) {
      onSelectFile(nextFiles[Math.min(index, nextFiles.length - 1)] ?? '');
    }
  };

  const toggleDirectory = (path: string) => {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  };

  return (
    <div className="relative flex h-full min-h-[32rem] overflow-hidden rounded-lg border border-white/10 bg-[#07090e] shadow-2xl">
      {/* ── 1. Activity Bar (Navigation Icons) ── */}
      <nav className="z-30 flex w-12 shrink-0 flex-col items-center border-r border-white/8 bg-[#0b0e17] py-2">
        <button
          type="button"
          onClick={() => setSidebarOpen((current) => !current)}
          className={`relative flex h-10 w-10 items-center justify-center rounded-lg transition-all ${
            sidebarOpen ? 'bg-cyan-500/15 text-cyan-300 font-semibold shadow-[0_0_12px_rgba(34,211,238,0.15)]' : 'text-gray-400 hover:bg-white/[0.05] hover:text-gray-200'
          }`}
          title="Explorador de Ficheiros"
        >
          <Files className="h-5 w-5" />
          {sidebarOpen && <span className="absolute left-0 top-1/2 -translate-y-1/2 h-5 w-0.5 rounded-r bg-cyan-400" />}
        </button>

        <button
          type="button"
          onClick={() => setInsightsOpen((current) => !current)}
          className={`relative mt-1 flex h-10 w-10 items-center justify-center rounded-lg transition-all ${
            insightsOpen ? 'bg-violet-500/15 text-violet-300 font-semibold shadow-[0_0_12px_rgba(167,139,250,0.15)]' : 'text-gray-400 hover:bg-white/[0.05] hover:text-gray-200'
          }`}
          title="Símbolos e Relações"
        >
          <Search className="h-5 w-5" />
          {insightsOpen && <span className="absolute left-0 top-1/2 -translate-y-1/2 h-5 w-0.5 rounded-r bg-violet-400" />}
        </button>

        <div className="my-2 h-px w-6 bg-white/8" />

        <button
          type="button"
          onClick={onOpenChanges}
          className="flex h-10 w-10 items-center justify-center rounded-lg text-gray-400 hover:bg-white/[0.05] hover:text-cyan-300 transition-all"
          title="Alterações e Diff"
        >
          <GitPullRequest className="h-5 w-5" />
        </button>

        <button
          type="button"
          onClick={onOpenPreview}
          className="mt-1 flex h-10 w-10 items-center justify-center rounded-lg text-gray-400 hover:bg-emerald-500/15 hover:text-emerald-300 transition-all"
          title="Executar Preview"
        >
          <Play className="h-5 w-5" />
        </button>

        <div className="mt-auto flex flex-col items-center gap-1">
          <span className="text-[10px] font-mono text-gray-400">{filenames.length}f</span>
        </div>
      </nav>

      {/* ── 2. Sidebar Explorer ── */}
      {sidebarOpen && (
        <aside className="absolute inset-y-0 left-12 z-20 flex w-64 flex-col border-r border-white/8 bg-[#0a0d15] md:relative md:left-auto md:z-auto">
          {/* Header */}
          <div className="flex h-10 items-center justify-between border-b border-white/8 px-3.5">
            <span className="text-xs font-semibold uppercase tracking-wider text-gray-400">Explorador</span>
            <span className="rounded bg-white/[0.06] px-1.5 py-0.5 font-mono text-[10px] text-cyan-300">{filenames.length} ficheiros</span>
          </div>

          {/* Project Title Badge */}
          <div className="flex h-8 items-center gap-1.5 border-b border-white/[0.04] bg-white/[0.02] px-3 text-xs font-medium text-gray-300">
            <Layers className="h-3.5 w-3.5 text-cyan-400" />
            <span className="truncate font-semibold text-white" title={rootPath}>{projectName}</span>
          </div>

          {/* Quick File Filter */}
          <div className="border-b border-white/8 px-2 py-1.5">
            <div className="flex items-center gap-1.5 rounded border border-white/8 bg-black/30 px-2 py-1 text-xs text-gray-400 focus-within:border-cyan-400/40">
              <Search className="h-3 w-3 text-gray-400" />
              <input
                type="text"
                value={fileFilter}
                onChange={(e) => setFileFilter(e.target.value)}
                placeholder="Filtrar ficheiros..."
                className="w-full bg-transparent text-xs text-gray-200 outline-none placeholder:text-gray-400"
              />
              {fileFilter && (
                <button onClick={() => setFileFilter('')} className="text-gray-400 hover:text-white">
                  <X className="h-3 w-3" />
                </button>
              )}
            </div>
          </div>

          {/* File Tree */}
          <div className="min-h-0 flex-1 overflow-y-auto py-1.5 select-none">
            {tree.length === 0 ? (
              <div className="px-4 py-8 text-center text-xs text-gray-400">
                {fileFilter ? 'Nenhum ficheiro corresponde ao filtro' : 'Sem ficheiros editáveis'}
              </div>
            ) : (
              tree.map((node) => (
                <TreeRow
                  key={`${node.type}-${node.path}`}
                  node={node}
                  depth={0}
                  selectedFile={selectedFile}
                  expanded={visibleExpanded}
                  onToggle={toggleDirectory}
                  onSelect={selectFile}
                  onDelete={onDeleteFile ? handleDeleteRequest : undefined}
                />
              ))
            )}
          </div>
        </aside>
      )}

      {/* ── 3. Main Editor Body ── */}
      <section className="flex min-w-0 flex-1 flex-col bg-[#07090e]">
        {/* Editor Tabs */}
        <div className="flex h-9 shrink-0 items-center overflow-x-auto border-b border-white/8 bg-[#0b0e17] px-1 gap-1">
          {visibleOpenFiles.map((filename) => {
            const active = filename === selectedFile;
            const isDirty = dirtyFiles.has(filename);
            return (
              <div
                key={filename}
                className={`group flex h-7 min-w-32 max-w-56 shrink-0 items-center gap-1.5 rounded-md px-2 text-xs transition-all ${
                  active
                    ? 'bg-cyan-500/15 text-cyan-200 border border-cyan-500/30 font-medium'
                    : 'text-gray-400 hover:bg-white/[0.04] hover:text-gray-200 border border-transparent'
                }`}
                title={filename}
              >
                <button
                  type="button"
                  onClick={() => selectFile(filename)}
                  className="flex min-w-0 flex-1 items-center gap-1.5 text-left"
                >
                  <FileIcon filename={filename} />
                  <span className="min-w-0 flex-1 truncate">{filename.split('/').pop()}</span>
                  {isDirty && (
                    <span className="h-2 w-2 shrink-0 rounded-full bg-amber-400 ring-2 ring-amber-400/20" title="Alterações não gravadas" />
                  )}
                </button>
                <button
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation();
                    closeFile(filename);
                  }}
                  className="flex h-4 w-4 shrink-0 items-center justify-center rounded text-gray-400 hover:bg-white/10 hover:text-white transition-colors"
                  aria-label={`Fechar ${filename}`}
                >
                  <X className="h-3 w-3" />
                </button>
              </div>
            );
          })}
        </div>

        {selectedFile ? (
          <>
            {/* Breadcrumb & Action Toolbar */}
            <div className="flex h-8 shrink-0 items-center justify-between gap-2 border-b border-white/8 bg-[#090c14] px-3 text-xs text-gray-400">
              {/* Path Breadcrumbs */}
              <div className="flex min-w-0 items-center gap-1 overflow-hidden font-mono text-[11px]">
                {selectedFile.split('/').map((part, index, parts) => (
                  <span key={`${part}-${index}`} className="flex items-center gap-1">
                    {index > 0 && <ChevronRight className="h-3 w-3 text-gray-400 shrink-0" />}
                    <span className={index === parts.length - 1 ? 'font-semibold text-cyan-200' : 'text-gray-400'}>
                      {part}
                    </span>
                  </span>
                ))}
                <button
                  onClick={copyFilePath}
                  className="ml-1.5 p-1 text-gray-400 hover:text-cyan-300 rounded transition-colors"
                  title="Copiar caminho relativo"
                >
                  {copiedPath ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
                </button>
              </div>

              {/* Formatting & Save Toolbar */}
              <div className="flex items-center gap-2 shrink-0">
                {saveState?.filename === selectedFile && !saveState.ok && (
                  <span className="flex max-w-72 items-center gap-1 truncate text-rose-300 text-[11px]" title={saveState.error}>
                    <CircleAlert className="h-3.5 w-3.5 shrink-0" />
                    {saveState.error}
                  </span>
                )}

                {onDeleteFile && (
                  <button
                    type="button"
                    onClick={() => handleDeleteRequest(selectedFile)}
                    className="flex items-center gap-1 rounded bg-rose-500/10 px-2 py-0.5 text-[11px] font-medium text-rose-300 hover:bg-rose-500/20 border border-rose-500/20 transition-colors"
                    title="Eliminar este ficheiro"
                  >
                    <Trash2 className="h-3 w-3 text-rose-400" />
                    <span>Eliminar</span>
                  </button>
                )}

                <button
                  type="button"
                  onClick={formatCode}
                  className="flex items-center gap-1 rounded bg-white/[0.04] px-2 py-0.5 text-[11px] font-medium text-gray-300 hover:bg-white/[0.08] hover:text-cyan-200 border border-white/8 transition-colors"
                  title="Formatar Código (Shift+Alt+F)"
                >
                  <WandSparkles className="h-3 w-3 text-cyan-400" />
                  <span>Formatar</span>
                </button>

                <button
                  type="button"
                  onClick={saveCurrent}
                  disabled={!currentDirty || isSaving}
                  className={`flex items-center gap-1 rounded px-2.5 py-0.5 text-[11px] font-medium transition-all ${
                    currentDirty
                      ? 'bg-cyan-500/20 text-cyan-200 border border-cyan-400/40 hover:bg-cyan-500/30'
                      : 'bg-white/[0.03] text-gray-400 border border-white/8 opacity-50 cursor-not-allowed'
                  }`}
                  title="Guardar ficheiro (Ctrl+S)"
                >
                  <Save className={`h-3 w-3 ${isSaving ? 'animate-pulse' : ''}`} />
                  <span>{isSaving ? 'A gravar...' : 'Guardar'}</span>
                </button>
              </div>
            </div>

            {/* Monaco Code Editor */}
            <div className="min-h-0 flex-1">
              <Editor
                path={`${projectId}/${selectedFile}`}
                language={languageFor(selectedFile)}
                value={currentDraft}
                beforeMount={handleBeforeMount}
                onMount={handleEditorMount}
                onChange={(value) => {
                  setDrafts((current) => ({ ...current, [selectedFile]: value ?? '' }));
                }}
                theme="jarvis-studio-dark"
                options={{
                  automaticLayout: true,
                  bracketPairColorization: { enabled: true },
                  cursorBlinking: 'smooth',
                  cursorSmoothCaretAnimation: 'on',
                  fontFamily: "'Cascadia Code', 'Fira Code', Consolas, 'Courier New', monospace",
                  fontLigatures: true,
                  fontSize: 13.5,
                  folding: true,
                  guides: { indentation: true, bracketPairs: true },
                  lineHeight: 22,
                  minimap: { enabled: true, maxColumn: 90, renderCharacters: false },
                  padding: { top: 12, bottom: 12 },
                  renderLineHighlight: 'all',
                  scrollBeyondLastLine: false,
                  smoothScrolling: true,
                  tabSize: 2,
                  wordWrap: 'off',
                }}
              />
            </div>

            {/* Status Bar */}
            <footer className="flex h-6 shrink-0 items-center justify-between border-t border-white/8 bg-[#090c14] px-3 font-mono text-[11px] text-gray-400">
              <div className="flex items-center gap-3">
                <span className="flex items-center gap-1 text-cyan-300 font-semibold">
                  <Code2 className="h-3 w-3" />
                  {languageFor(selectedFile).toUpperCase()}
                </span>
                <span className="text-gray-400">UTF-8</span>
                <span className="text-gray-400">Espaços: 2</span>
              </div>
              <div className="flex items-center gap-3">
                <span>Ln {cursor.line}, Col {cursor.column}</span>
              </div>
            </footer>
          </>
        ) : (
          <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-3 text-gray-400">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-white/10 bg-white/[0.03]">
              <Code2 className="h-6 w-6 text-cyan-400" />
            </div>
            <div className="text-center">
              <p className="text-sm font-semibold text-white">Nenhum ficheiro aberto</p>
              <p className="mt-0.5 text-xs text-gray-400">Selecione um ficheiro no explorador lateral para editar e formatar código.</p>
            </div>
          </div>
        )}
      </section>

      {/* ── 4. Insights Sidebar (Symbols / References) ── */}
      {insightsOpen && (
        <div className="absolute inset-y-0 right-0 z-20 flex w-[min(22rem,calc(100%-3rem))] border-l border-white/8 bg-[#0a0d15] shadow-2xl xl:relative xl:z-auto xl:w-auto">
          {insights}
        </div>
      )}

      {/* ── 5. Delete File Confirmation Modal ── */}
      {fileToDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4">
          <div className="w-full max-w-sm rounded-lg border border-white/10 bg-[#0d1117] p-5 shadow-2xl space-y-4">
            <div className="flex items-center gap-3 text-rose-400">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-rose-500/10 border border-rose-500/20">
                <Trash2 className="h-5 w-5" />
              </div>
              <div className="min-w-0 flex-1">
                <h4 className="text-sm font-semibold text-white">Eliminar Ficheiro</h4>
                <p className="text-xs text-gray-400 font-mono truncate">{fileToDelete}</p>
              </div>
            </div>
            <p className="text-xs text-gray-300 leading-relaxed">
              Tem a certeza de que deseja eliminar permanentemente este ficheiro? Esta ação não pode ser desfeita.
            </p>
            <div className="flex justify-end gap-2 pt-2 border-t border-white/8">
              <button
                type="button"
                onClick={() => setFileToDelete(null)}
                className="rounded-md border border-white/10 bg-white/[0.04] px-3 py-1.5 text-xs text-gray-300 hover:bg-white/[0.08]"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={handleConfirmDelete}
                className="rounded-md border border-rose-500/30 bg-rose-500/20 px-3 py-1.5 text-xs font-semibold text-rose-200 hover:bg-rose-500/30"
              >
                Eliminar Ficheiro
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
