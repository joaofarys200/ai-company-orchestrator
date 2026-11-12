const electron = require('electron');
if (typeof electron === 'string') {
  // Invoked as Node.js or with ELECTRON_RUN_AS_NODE=1 inherited from IDE/terminal.
  // Re-spawn the real Electron runtime with ELECTRON_RUN_AS_NODE stripped.
  const { spawn } = require('child_process');
  const env = { ...process.env };
  delete env.ELECTRON_RUN_AS_NODE;
  const child = spawn(electron, [__filename, ...process.argv.slice(2)], {
    stdio: 'inherit',
    env,
  });
  child.on('close', (code) => process.exit(code ?? 0));
  return;
}

const { app, BrowserWindow, ipcMain, dialog, shell } = electron;
const path = require('path');
const { spawn, execFileSync } = require('child_process');
const fs = require('fs');
const http = require('http');
const crypto = require('crypto');
const os = require('os');

// Per-launch ephemeral HTTP auth token for local backend HTTP routes (/api/study/*, /data/study/*)
const SESSION_HTTP_TOKEN = (process.env.JARVIS_HTTP_TOKEN || '').trim() || crypto.randomBytes(24).toString('hex');

// Allow audio autoplay without user gesture requirements in Electron
app.commandLine.appendSwitch('autoplay-policy', 'no-user-gesture-required');
app.commandLine.appendSwitch('disable-http-cache');

let mainWindow;
let pythonProcess = null;
let isQuitting = false;
let isStoppingBackend = false;
let backendRestartTimer = null;
let backendRestartCount = 0;
let isPageLoaded = false;
let retryLoadTimer = null;

const MAX_BACKEND_RESTARTS = 3;
const BACKEND_RESTART_DELAY_MS = 1500;
const BACKEND_SHUTDOWN_TIMEOUT_MS = 5000;

function freePortIfLocked(port) {
  try {
    if (process.platform === 'win32') {
      const output = execFileSync('netstat', ['-ano', '-p', 'tcp'], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] });
      const portSuffixRe = new RegExp(`:${Number(port)}$`);
      const lines = output.split('\n');
      for (const line of lines) {
        const parts = line.trim().split(/\s+/);
        if (parts.length < 5) continue;
        const localAddr = parts[1] || '';
        const state = parts[3] || '';
        if (state === 'LISTENING' && portSuffixRe.test(localAddr)) {
          const pid = parseInt(parts[parts.length - 1], 10);
          if (pid && pid !== process.pid) {
            try {
              execFileSync('taskkill', ['/pid', String(pid), '/T', '/F'], { stdio: 'ignore' });
              console.log(`[Electron] Liberada porta ${port} matando processo orfao PID ${pid}`);
            } catch {}
          }
        }
      }
    }
  } catch (e) {}
}

function logElectron(event, details = {}) {
  console.log(JSON.stringify({
    ts: new Date().toISOString(),
    source: 'electron',
    event,
    details,
  }));
}

// Forward messages from Renderer to Python Backend stdin
ipcMain.on('jarvis-to-backend', (event, message) => {
  if (pythonProcess && pythonProcess.stdin && !pythonProcess.killed) {
    try {
      const line = JSON.stringify(message) + '\n';
      pythonProcess.stdin.write(line);
    } catch (err) {
      console.error('[Electron IPC] Error writing to Python stdin:', err);
    }
  }
});

// Native folder selection dialog for Study area
ipcMain.handle('select-folder', async () => {
  try {
    const result = await dialog.showOpenDialog(mainWindow, {
      title: 'Selecionar Pasta de Materiais de Estudo',
      properties: ['openDirectory', 'createDirectory'],
    });
    if (result.canceled || !result.filePaths || result.filePaths.length === 0) {
      return null;
    }
    return result.filePaths[0];
  } catch (err) {
    console.error('[Electron IPC] Error in select-folder dialog:', err);
    return null;
  }
});

function isPathWithinAllowedRoots(targetPath) {
  if (!targetPath || typeof targetPath !== 'string' || targetPath.includes('\0')) {
    return { allowed: false, resolved: '', error: 'Caminho inválido.' };
  }
  const allowedRootsRaw = [
    __dirname,
    path.join(__dirname, 'data'),
    path.join(__dirname, 'obsidian_vault'),
    os.tmpdir(),
  ];
  const resolveCanonical = (p) => {
    const abs = path.resolve(p);
    try {
      return fs.realpathSync(abs);
    } catch {
      return abs;
    }
  };
  const norm = (p) => (process.platform === 'win32' ? p.toLowerCase() : p);
  const candidate = resolveCanonical(targetPath);
  const candNorm = norm(candidate);
  const inRoot = allowedRootsRaw.some((root) => {
    const rootNorm = norm(resolveCanonical(root));
    const sep = rootNorm.endsWith(path.sep) ? '' : path.sep;
    return candNorm === rootNorm || candNorm.startsWith(rootNorm + sep);
  });
  if (!inRoot) {
    return {
      allowed: false,
      resolved: candidate,
      error: 'Acesso negado: caminho fora das raízes permitidas (workspace, data, obsidian_vault, temp).',
    };
  }
  return { allowed: true, resolved: candidate, error: '' };
}

// Native folder opener in OS file explorer
ipcMain.handle('open-path', async (event, targetPath) => {
  try {
    const check = isPathWithinAllowedRoots(targetPath);
    if (!check.allowed) {
      return { ok: false, error: check.error };
    }
    const openError = await shell.openPath(check.resolved);
    if (openError && typeof openError === 'string' && openError.trim().length > 0) {
      return { ok: false, error: openError };
    }
    return { ok: true, error: '' };
  } catch (err) {
    console.error('[Electron IPC] Error opening path:', err);
    return { ok: false, error: err?.message || 'Erro ao abrir caminho.' };
  }
});

function startPythonBackend() {
  if (pythonProcess) {
    logElectron('backend.start_skipped', { reason: 'already_running', pid: pythonProcess.pid });
    return;
  }

  // Ensure ports 8000 and 8001 are free from any previous orphan process
  freePortIfLocked(8000);
  freePortIfLocked(8001);

  // Try to use the virtual environment's python.exe, fall back to global python
  const venvPython = path.join(__dirname, 'venv', 'Scripts', 'python.exe');
  const pythonCmd = fs.existsSync(venvPython) ? venvPython : 'python';

  logElectron('backend.starting', { command: path.basename(pythonCmd) });

  // Start the server.py process with unbuffered output to prevent logging delays
  isStoppingBackend = false;
  pythonProcess = spawn(pythonCmd, ['-u', 'server.py'], {
    cwd: __dirname,
    env: { 
      ...process.env, 
      PYTHONUNBUFFERED: '1',
      PYTHONIOENCODING: 'utf-8',
      PYTHONUTF8: '1',
      JARVIS_HTTP_TOKEN: SESSION_HTTP_TOKEN,
    },
    shell: false
  });

  // Pipe Python stdout and forward JSON messages to Renderer via IPC
  let stdoutBuffer = '';
  pythonProcess.stdout.on('data', (data) => {
    stdoutBuffer += data.toString();
    const lines = stdoutBuffer.split('\n');
    stdoutBuffer = lines.pop() || ''; // Keep incomplete trailing line in buffer

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;

      // Check if line is a JSON message destined for the UI
      if (trimmed.startsWith('{') && trimmed.endsWith('}')) {
        try {
          const parsed = JSON.parse(trimmed);
          if (parsed && typeof parsed === 'object' && parsed.type && mainWindow && !mainWindow.isDestroyed()) {
            mainWindow.webContents.send('jarvis-from-backend', parsed);
            continue;
          }
        } catch (e) {
          // Not a JSON message or parse error, fallback to normal log
        }
      }

      // If the frontend server starts running, load the page immediately if window exists
      if (trimmed.includes('Frontend HTTP server running') && mainWindow) {
        console.log('[Electron] Servidor Python detetado!');
        const isDev = process.argv.includes('--dev') || process.env.VITE_DEV === '1';
        const targetUrl = isDev ? 'http://localhost:5173' : 'http://localhost:8000';
        console.log(`[Electron] A carregar UI em ${targetUrl}...`);
        loadURLWithRetry(targetUrl, 20, 400, 'http://localhost:8000');
      }
    }
  });

  // Pipe Python stderr to Electron main console
  pythonProcess.stderr.on('data', (data) => {
    console.error(`[Python STDERR] ${data.toString().trim()}`);
  });

  pythonProcess.on('close', (code) => {
    const wasStopping = isStoppingBackend || isQuitting;
    logElectron('backend.closed', { code, wasStopping });
    pythonProcess = null;
    isStoppingBackend = false;
    if (!wasStopping && code !== 0) {
      scheduleBackendRestart(code);
    }
  });
}

function scheduleBackendRestart(exitCode) {
  if (backendRestartTimer || isQuitting) return;
  if (backendRestartCount >= MAX_BACKEND_RESTARTS) {
    logElectron('backend.restart_aborted', { reason: 'max_restarts', exitCode });
    return;
  }
  backendRestartCount += 1;
  logElectron('backend.restart_scheduled', {
    attempt: backendRestartCount,
    delayMs: BACKEND_RESTART_DELAY_MS,
    exitCode,
  });
  backendRestartTimer = setTimeout(() => {
    backendRestartTimer = null;
    startPythonBackend();
  }, BACKEND_RESTART_DELAY_MS);
}

function clearBackendRestartTimer() {
  if (backendRestartTimer) {
    clearTimeout(backendRestartTimer);
    backendRestartTimer = null;
  }
}

function showDiagnosticErrorPage(failedUrls, reason) {
  if (!mainWindow || mainWindow.isDestroyed()) return;
  const isPythonRunning = Boolean(pythonProcess && !pythonProcess.killed);
  const pid = pythonProcess ? pythonProcess.pid : 'N/A';
  mainWindow.loadURL('data:text/html;charset=utf-8,' + encodeURIComponent(`
    <!DOCTYPE html>
    <html lang="pt-PT">
    <head>
      <meta charset="UTF-8">
      <title>JARVIS OS // Erro de Inicialização</title>
      <style>
        body {
          background-color: #08090d;
          color: #e2e8f0;
          font-family: ui-sans-serif, system-ui, -apple-system, sans-serif;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          min-height: 100vh;
          margin: 0;
          padding: 24px;
          box-sizing: border-box;
        }
        .card {
          background: #0f131f;
          border: 1px solid rgba(244, 63, 94, 0.3);
          border-radius: 12px;
          padding: 32px;
          max-width: 580px;
          width: 100%;
          box-shadow: 0 20px 40px rgba(0,0,0,0.5);
        }
        h2 { color: #f43f5e; margin-top: 0; font-size: 18px; letter-spacing: 1px; }
        p { font-size: 13px; line-height: 1.6; color: #94a3b8; }
        .details {
          background: #05070d;
          border: 1px solid rgba(255,255,255,0.08);
          border-radius: 6px;
          padding: 12px;
          font-family: monospace;
          font-size: 12px;
          color: #38bdf8;
          margin: 16px 0;
        }
        .btn {
          display: inline-block;
          background: #0284c7;
          color: #fff;
          font-weight: 600;
          font-size: 13px;
          padding: 10px 20px;
          border-radius: 6px;
          border: none;
          cursor: pointer;
          transition: background 0.2s;
        }
        .btn:hover { background: #0369a1; }
      </style>
    </head>
    <body>
      <div class="card">
        <h2>⚠️ NÃO FOI POSSÍVEL CONECTAR AOS SERVIÇOS DO JARVIS OS</h2>
        <p>O Electron tentou ligar-se aos seguintes endpoints locais sem sucesso:</p>
        <div class="details">
          URLs tentados: ${failedUrls.join(', ')}<br/>
          Estado Backend Python: ${isPythonRunning ? `EM EXECUÇÃO (PID ${pid})` : 'DESLIGADO'}<br/>
          Motivo: ${reason}
        </div>
        <p><strong>Como resolver:</strong></p>
        <ul style="font-size: 12px; color: #cbd5e1; padding-left: 20px;">
          <li>Para desenvolvimento com Vite: execute <code>npm run dev</code> num terminal.</li>
          <li>Para modo desktop padrão: execute <code>npm start</code>.</li>
        </ul>
        <div style="margin-top: 24px;">
          <button class="btn" onclick="location.reload()">Tentar Novamente</button>
        </div>
      </div>
    </body>
    </html>
  `)).catch(() => {});
}

function checkUrlReady(targetUrl, timeoutMs = 600) {
  return new Promise((resolve) => {
    try {
      const req = http.get(targetUrl, { timeout: timeoutMs }, (res) => {
        res.resume();
        resolve(Boolean(res.statusCode && res.statusCode < 500));
      });
      req.on('error', () => resolve(false));
      req.on('timeout', () => {
        req.destroy();
        resolve(false);
      });
    } catch {
      resolve(false);
    }
  });
}

function loadURLWithRetry(url, maxRetries = 35, delayMs = 450, fallbackUrl = 'http://localhost:8000') {
  if (isPageLoaded && mainWindow && !mainWindow.isDestroyed()) {
    const currentLoaded = mainWindow.webContents.getURL() || '';
    if (currentLoaded.startsWith('http://localhost:') || currentLoaded.startsWith('http://127.0.0.1:')) {
      return;
    }
    isPageLoaded = false;
  }
  if (retryLoadTimer) {
    clearTimeout(retryLoadTimer);
    retryLoadTimer = null;
  }
  let attempts = 0;
  const attemptedUrls = [url];
  if (fallbackUrl && fallbackUrl !== url) attemptedUrls.push(fallbackUrl);

  async function tryLoad(currentUrl) {
    if (!mainWindow || mainWindow.isDestroyed() || isPageLoaded) return;
    const ready = await checkUrlReady(currentUrl);
    if (!ready) {
      if (isPageLoaded) return;
      attempts += 1;
      if (attempts < maxRetries) {
        retryLoadTimer = setTimeout(() => tryLoad(currentUrl), delayMs);
      } else if (fallbackUrl && currentUrl !== fallbackUrl) {
        console.log(`[Electron] Falha ao carregar ${currentUrl}. A alternar para fallback: ${fallbackUrl}`);
        attempts = 0;
        tryLoad(fallbackUrl);
      } else {
        console.error(`[Electron] Não foi possível carregar ${attemptedUrls.join(' ou ')} após múltiplas tentativas.`);
        showDiagnosticErrorPage(attemptedUrls, 'Timeout na resposta dos servidores locais.');
      }
      return;
    }

    mainWindow.loadURL(currentUrl).catch(() => {
      if (isPageLoaded) return;
      attempts += 1;
      if (attempts < maxRetries) {
        retryLoadTimer = setTimeout(() => tryLoad(currentUrl), delayMs);
      } else if (fallbackUrl && currentUrl !== fallbackUrl) {
        console.log(`[Electron] Falha ao carregar ${currentUrl}. A alternar para fallback: ${fallbackUrl}`);
        attempts = 0;
        tryLoad(fallbackUrl);
      } else {
        console.error(`[Electron] Não foi possível carregar ${attemptedUrls.join(' ou ')} após múltiplas tentativas.`);
        showDiagnosticErrorPage(attemptedUrls, 'Timeout na resposta dos servidores locais.');
      }
    });
  }
  tryLoad(url);
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1300,
    height: 850,
    minWidth: 1024,
    minHeight: 700,
    title: "JARVIS OS // ORCHESTRATOR",
    backgroundColor: "#080c12",
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
    }
  });

  // Track successful HTTP page loads (ignore chrome-error:// or about:blank) to stop background retries
  mainWindow.webContents.on('did-finish-load', () => {
    const loadedUrl = mainWindow ? (mainWindow.webContents.getURL() || '') : '';
    if (loadedUrl.startsWith('http://localhost:') || loadedUrl.startsWith('http://127.0.0.1:')) {
      isPageLoaded = true;
      if (retryLoadTimer) {
        clearTimeout(retryLoadTimer);
        retryLoadTimer = null;
      }
    }
  });

  // Clear HTTP/disk cache and code caches immediately on start to prevent loading stale bundles
  mainWindow.webContents.session.clearCache().catch(() => {});
  mainWindow.webContents.session.clearStorageData({ storages: ['cachestorage', 'shadercache', 'serviceworkers'] }).catch(() => {});
  if (mainWindow.webContents.session.clearCodeCaches) {
    mainWindow.webContents.session.clearCodeCaches({}).catch(() => {});
  }

  // Inject ephemeral per-launch HTTP token on local backend requests from this Electron window
  mainWindow.webContents.session.webRequest.onBeforeSendHeaders(
    {
      urls: [
        'http://127.0.0.1:8000/*',
        'http://localhost:8000/*',
        'http://127.0.0.1:5173/api/*',
        'http://localhost:5173/api/*',
        'http://127.0.0.1:5173/data/*',
        'http://localhost:5173/data/*',
      ],
    },
    (details, callback) => {
      if (mainWindow && !mainWindow.isDestroyed() && details.webContentsId === mainWindow.webContents.id) {
        callback({
          requestHeaders: {
            ...details.requestHeaders,
            'X-Jarvis-Token': SESSION_HTTP_TOKEN,
          },
        });
      } else {
        callback({ requestHeaders: details.requestHeaders });
      }
    }
  );

  // Enable F5 / Ctrl+R to reload with cache bypass, and F12 for DevTools
  mainWindow.webContents.on('before-input-event', (event, input) => {
    if ((input.control && input.key.toLowerCase() === 'r') || input.key === 'F5') {
      isPageLoaded = false;
      mainWindow.webContents.session.clearCache().then(() => {
        mainWindow.webContents.reloadIgnoringCache();
      }).catch(() => {
        mainWindow.webContents.reloadIgnoringCache();
      });
      event.preventDefault();
    }
    if ((input.control && input.shift && input.key.toLowerCase() === 'i') || input.key === 'F12') {
      mainWindow.webContents.toggleDevTools();
      event.preventDefault();
    }
  });

  const isDev = process.argv.includes('--dev') || process.env.VITE_DEV === '1';
  const targetUrl = isDev ? 'http://localhost:5173' : 'http://localhost:8000';
  loadURLWithRetry(targetUrl, 35, 450, 'http://localhost:8000');

  mainWindow.on('closed', () => {
    mainWindow = null;
    isPageLoaded = false;
  });
}

app.on('ready', () => {
  startPythonBackend();
  createWindow();
});

function forceKillOwnBackendProcess(processToStop) {
  if (!processToStop || !processToStop.pid) return;
  if (process.platform === 'win32') {
    execFileSync('taskkill', ['/pid', String(processToStop.pid), '/T', '/F']);
  } else {
    processToStop.kill('SIGKILL');
  }
}

function stopPythonBackend(onStopped) {
  clearBackendRestartTimer();
  if (!pythonProcess) {
    if (onStopped) onStopped();
    return;
  }

  const processToStop = pythonProcess;
  isStoppingBackend = true;
  logElectron('backend.stopping', { pid: processToStop.pid });

  let finished = false;
  const finish = () => {
    if (finished) return;
    finished = true;
    if (onStopped) onStopped();
  };

  processToStop.once('close', finish);

  try {
    processToStop.kill('SIGINT');
  } catch (err) {
    logElectron('backend.sigint_error', { message: err.message });
  }

  setTimeout(() => {
    if (finished) return;
    try {
      logElectron('backend.force_stop', { pid: processToStop.pid });
      forceKillOwnBackendProcess(processToStop);
    } catch (err) {
      logElectron('backend.force_stop_error', { message: err.message });
    } finally {
      finish();
    }
  }, BACKEND_SHUTDOWN_TIMEOUT_MS).unref();
}

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', (event) => {
  isQuitting = true;
  if (pythonProcess && !isStoppingBackend) {
    event.preventDefault();
    stopPythonBackend(() => app.quit());
  }
});

app.on('will-quit', () => {
  isQuitting = true;
  if (pythonProcess) {
    try {
      forceKillOwnBackendProcess(pythonProcess);
    } catch {}
    pythonProcess = null;
  }
});

for (const sig of ['SIGINT', 'SIGTERM']) {
  process.on(sig, () => {
    isQuitting = true;
    stopPythonBackend(() => process.exit(0));
  });
}
