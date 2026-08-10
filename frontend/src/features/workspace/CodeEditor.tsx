import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Editor, { loader, type BeforeMount, type OnMount } from '@monaco-editor/react';
import * as monaco from 'monaco-editor';
import {
  Braces,
  ChevronDown,
  ChevronRight,
  CircleAlert,
  Code2,
  FileCode2,
  FileJson,
  FileText,
  Files,
  Folder,
  FolderOpen,
  GitPullRequest,
  Play,
  Save,
  Search,
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
  if (extension === 'json') return <FileJson className="h-3.5 w-3.5 shrink-0 text-amber-300" />;
  if (extension === 'md' || extension === 'txt') return <FileText className="h-3.5 w-3.5 shrink-0 text-sky-300" />;
  if (['js', 'jsx', 'ts', 'tsx'].includes(extension ?? '')) return <Braces className="h-3.5 w-3.5 shrink-0 text-yellow-300" />;
  return <FileCode2 className="h-3.5 w-3.5 shrink-0 text-cyan-300/80" />;
}

function TreeRow({
  node,
  depth,
  selectedFile,
  expanded,
  onToggle,
  onSelect,
}: {
  node: FileTreeNode;
  depth: number;
  selectedFile: string;
  expanded: Set<string>;
  onToggle: (path: string) => void;
  onSelect: (path: string) => void;
}) {
  const isExpanded = expanded.has(node.path);
  const selected = node.type === 'file' && node.path === selectedFile;

  return (
    <>
      <button
        type="button"
        onClick={() => node.type === 'directory' ? onToggle(node.path) : onSelect(node.path)}
        className={`flex h-6 w-full items-center gap-1.5 pr-2 text-left text-[12px] transition-colors ${
          selected ? 'bg-[#37373d] text-white' : 'text-[#cccccc] hover:bg-white/[0.045]'
        }`}
        style={{ paddingLeft: `${6 + depth * 12}px` }}
        title={node.path}
      >
        {node.type === 'directory' ? (
          <>
            {isExpanded
              ? <ChevronDown className="h-3.5 w-3.5 shrink-0 text-gray-400" />
              : <ChevronRight className="h-3.5 w-3.5 shrink-0 text-gray-400" />}
            {isExpanded
              ? <FolderOpen className="h-3.5 w-3.5 shrink-0 text-cyan-300/80" />
              : <Folder className="h-3.5 w-3.5 shrink-0 text-cyan-300/70" />}
          </>
        ) : (
          <>
            <span className="w-3.5 shrink-0" />
            <FileIcon filename={node.name} />
          </>
        )}
        <span className="truncate">{node.name}</span>
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
  onOpenChanges,
  onOpenPreview,
  isSaving,
  saveState,
  insights,
}: CodeEditorProps) {
  const filenames = useMemo(() => Object.keys(files).sort((left, right) => left.localeCompare(right)), [files]);
  const tree = useMemo(() => buildTree(filenames), [filenames]);
  const [openFiles, setOpenFiles] = useState<string[]>(selectedFile ? [selectedFile] : []);
  const [drafts, setDrafts] = useState<Record<string, string>>(files);
  const [expanded, setExpanded] = useState<Set<string>>(() => {
    const parentParts = selectedFile.split('/').slice(0, -1);
    return new Set(parentParts.map((_, index) => parentParts.slice(0, index + 1).join('/')));
  });
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [insightsOpen, setInsightsOpen] = useState(false);
  const [cursor, setCursor] = useState({ line: 1, column: 1 });
  const saveCurrentRef = useRef<() => void>(() => undefined);

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
    editor.focus();
    editor.onDidChangeCursorPosition((event) => {
      setCursor({ line: event.position.lineNumber, column: event.position.column });
    });
    editor.addCommand(editorApi.KeyMod.CtrlCmd | editorApi.KeyCode.KeyS, () => saveCurrentRef.current());
  };

  const handleBeforeMount: BeforeMount = (editorApi) => {
    editorApi.editor.defineTheme('jarvis-vscode-dark', {
      base: 'vs-dark',
      inherit: true,
      rules: [],
      colors: {
        'editor.background': '#090b10',
        'editorGutter.background': '#090b10',
        'editorLineNumber.foreground': '#4f535d',
        'editorLineNumber.activeForeground': '#c6c9d0',
        'editor.selectionBackground': '#264f78',
        'editor.inactiveSelectionBackground': '#1d3a56',
        'editorCursor.foreground': '#67e8f9',
        'editorIndentGuide.background1': '#20232b',
        'editorIndentGuide.activeBackground1': '#39404d',
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
    <div className="relative flex h-full min-h-[32rem] overflow-hidden border border-white/8 bg-[#090b10]">
      <nav className="z-30 flex w-11 shrink-0 flex-col items-center border-r border-[#272a31] bg-[#14171d] py-1">
        <button
          type="button"
          onClick={() => setSidebarOpen((current) => !current)}
          className={`relative flex h-11 w-11 items-center justify-center border-l-2 ${
            sidebarOpen ? 'border-cyan-300 text-white' : 'border-transparent text-gray-500 hover:text-gray-200'
          }`}
          title="Explorador"
        >
          <Files className="h-5 w-5" />
        </button>
        <button
          type="button"
          onClick={() => setInsightsOpen((current) => !current)}
          className={`relative flex h-11 w-11 items-center justify-center border-l-2 ${
            insightsOpen ? 'border-violet-300 text-white' : 'border-transparent text-gray-500 hover:text-gray-200'
          }`}
          title="Símbolos e referências"
        >
          <Search className="h-5 w-5" />
        </button>
        <button
          type="button"
          onClick={onOpenChanges}
          className="flex h-11 w-11 items-center justify-center border-l-2 border-transparent text-gray-500 hover:text-gray-200"
          title="Alteração assistida"
        >
          <GitPullRequest className="h-5 w-5" />
        </button>
        <button
          type="button"
          onClick={onOpenPreview}
          className="flex h-11 w-11 items-center justify-center border-l-2 border-transparent text-gray-500 hover:text-gray-200"
          title="Preview"
        >
          <Play className="h-5 w-5" />
        </button>
      </nav>

      {sidebarOpen && (
        <aside className="absolute inset-y-0 left-11 z-20 flex w-64 flex-col border-r border-[#272a31] bg-[#101319] md:relative md:left-auto md:z-auto">
          <div className="flex h-9 items-center justify-between px-3">
            <span className="text-[11px] font-medium uppercase text-[#bbbbbb]">Explorador</span>
            <span className="text-[11px] text-gray-600">{filenames.length}</span>
          </div>
          <div className="flex h-7 items-center gap-1 border-y border-white/[0.04] px-1.5 text-xs font-semibold text-[#cccccc]">
            <ChevronDown className="h-3.5 w-3.5" />
            <span className="truncate uppercase" title={rootPath}>{projectName}</span>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto py-1">
            {tree.length === 0 ? (
              <div className="px-4 py-8 text-center text-xs text-gray-600">Sem ficheiros editáveis</div>
            ) : tree.map((node) => (
              <TreeRow
                key={`${node.type}-${node.path}`}
                node={node}
                depth={0}
                selectedFile={selectedFile}
                expanded={visibleExpanded}
                onToggle={toggleDirectory}
                onSelect={selectFile}
              />
            ))}
          </div>
        </aside>
      )}

      <section className="flex min-w-0 flex-1 flex-col bg-[#090b10]">
        <div className="flex h-9 shrink-0 overflow-x-auto border-b border-[#272a31] bg-[#101319]">
          {visibleOpenFiles.map((filename) => {
            const active = filename === selectedFile;
            return (
              <div
                key={filename}
                className={`group flex h-9 min-w-32 max-w-52 shrink-0 items-center gap-1 border-r border-[#272a31] px-1 text-xs ${
                  active ? 'border-t border-t-cyan-300 bg-[#090b10] text-white' : 'text-gray-500 hover:bg-white/[0.025] hover:text-gray-300'
                }`}
                title={filename}
              >
                <button
                  type="button"
                  onClick={() => selectFile(filename)}
                  className="flex min-w-0 flex-1 items-center gap-2 px-2"
                >
                  <FileIcon filename={filename} />
                  <span className="min-w-0 flex-1 truncate text-left">{filename.split('/').pop()}</span>
                  {dirtyFiles.has(filename) && <span className="h-2 w-2 shrink-0 rounded-full bg-gray-300" />}
                </button>
                <button
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation();
                    closeFile(filename);
                  }}
                  className="hidden h-6 w-6 shrink-0 items-center justify-center rounded hover:bg-white/10 group-hover:flex"
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
            <div className="flex h-8 shrink-0 items-center gap-1 border-b border-white/[0.04] px-3 text-[11px] text-gray-500">
              {selectedFile.split('/').map((part, index, parts) => (
                <span key={`${part}-${index}`} className="flex items-center gap-1">
                  {index > 0 && <ChevronRight className="h-3 w-3 text-gray-700" />}
                  <span className={index === parts.length - 1 ? 'text-gray-300' : ''}>{part}</span>
                </span>
              ))}
              <div className="ml-auto flex items-center gap-2">
                {saveState?.filename === selectedFile && !saveState.ok && (
                  <span className="flex max-w-72 items-center gap-1 truncate text-rose-300" title={saveState.error}>
                    <CircleAlert className="h-3.5 w-3.5 shrink-0" />
                    {saveState.error}
                  </span>
                )}
                <button
                  type="button"
                  onClick={saveCurrent}
                  disabled={!currentDirty || isSaving}
                  className="flex h-6 w-6 items-center justify-center rounded text-gray-500 hover:bg-white/[0.06] hover:text-white disabled:opacity-30"
                  title="Guardar (Ctrl+S)"
                >
                  <Save className={`h-3.5 w-3.5 ${isSaving ? 'animate-pulse' : ''}`} />
                </button>
              </div>
            </div>
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
                theme="jarvis-vscode-dark"
                options={{
                  automaticLayout: true,
                  bracketPairColorization: { enabled: true },
                  cursorBlinking: 'smooth',
                  cursorSmoothCaretAnimation: 'on',
                  fontFamily: "'Cascadia Code', 'Cascadia Mono', Consolas, monospace",
                  fontLigatures: true,
                  fontSize: 13,
                  folding: true,
                  guides: { indentation: true, bracketPairs: true },
                  lineHeight: 21,
                  minimap: { enabled: true, maxColumn: 90, renderCharacters: false },
                  padding: { top: 10, bottom: 10 },
                  renderLineHighlight: 'all',
                  scrollBeyondLastLine: false,
                  smoothScrolling: true,
                  tabSize: 2,
                  wordWrap: 'off',
                }}
              />
            </div>
            <footer className="flex h-6 shrink-0 items-center gap-4 bg-[#117a8b] px-2 text-[11px] text-white">
              <Code2 className="h-3 w-3" />
              <span className="ml-auto">Ln {cursor.line}, Col {cursor.column}</span>
              <span>UTF-8</span>
              <span>{languageFor(selectedFile)}</span>
            </footer>
          </>
        ) : (
          <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-3 text-gray-600">
            <Code2 className="h-8 w-8" />
            <span className="text-sm">Selecione um ficheiro</span>
          </div>
        )}
      </section>

      {insightsOpen && (
        <div className="absolute inset-y-0 right-0 z-20 flex w-[min(20rem,calc(100%-2.75rem))] bg-[#101319] xl:relative xl:z-auto xl:w-auto">
          {insights}
        </div>
      )}
    </div>
  );
}
