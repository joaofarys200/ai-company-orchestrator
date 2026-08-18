const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const { spawn, execFileSync } = require('child_process');
const fs = require('fs');

// Allow audio autoplay without user gesture requirements in Electron
app.commandLine.appendSwitch('autoplay-policy', 'no-user-gesture-required');

let mainWindow;
let pythonProcess = null;
let isQuitting = false;
let isStoppingBackend = false;
let backendRestartTimer = null;
let backendRestartCount = 0;

const MAX_BACKEND_RESTARTS = 3;
const BACKEND_RESTART_DELAY_MS = 1500;
const BACKEND_SHUTDOWN_TIMEOUT_MS = 5000;

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

function startPythonBackend() {
  if (pythonProcess) {
    logElectron('backend.start_skipped', { reason: 'already_running', pid: pythonProcess.pid });
    return;
  }

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
      PYTHONUTF8: '1'
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

      console.log(`[Python STDOUT] ${trimmed}`);

      // If the frontend server starts running, load the page immediately if window exists
      if (trimmed.includes('Frontend HTTP server running') && mainWindow) {
        console.log('[Electron] Servidor Python detetado!');
        const isDev = process.argv.includes('--dev') || process.env.VITE_DEV === '1' || process.env.npm_lifecycle_event === 'dev';
        const targetUrl = isDev ? 'http://localhost:5173' : 'http://localhost:8000';
        console.log(`[Electron] A carregar UI em ${targetUrl}...`);
        loadURLWithRetry(targetUrl);
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

function loadURLWithRetry(url, maxRetries = 30, delayMs = 600) {
  let attempts = 0;
  function tryLoad() {
    if (!mainWindow || mainWindow.isDestroyed()) return;
    mainWindow.loadURL(url).catch(() => {
      attempts += 1;
      if (attempts < maxRetries) {
        setTimeout(tryLoad, delayMs);
      } else {
        console.error(`[Electron] Não foi possível carregar ${url} após ${maxRetries} tentativas.`);
      }
    });
  }
  tryLoad();
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1300,
    height: 850,
    title: "JARVIS OS // ORCHESTRATOR",
    backgroundColor: "#08090d",
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
    }
  });

  mainWindow.webContents.on('did-fail-load', (event, errorCode, errorDescription, validatedURL) => {
    if (validatedURL && (validatedURL.includes('5173') || validatedURL.includes('8000'))) {
      setTimeout(() => {
        if (mainWindow && !mainWindow.isDestroyed()) {
          mainWindow.loadURL(validatedURL).catch(() => {});
        }
      }, 1000);
    }
  });

  // Load a simple loading screen or wait for python server
  mainWindow.loadURL('data:text/html;charset=utf-8,' + encodeURIComponent(`
    <!DOCTYPE html>
    <html>
    <head>
      <title>Jarvis OS // Loading</title>
      <style>
        body {
          background-color: #08090d;
          color: #66fcf1;
          font-family: sans-serif;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          height: 100vh;
          margin: 0;
          overflow: hidden;
        }
        .spinner {
          width: 50px;
          height: 50px;
          border: 3px solid rgba(102, 252, 241, 0.1);
          border-radius: 50%;
          border-top-color: #66fcf1;
          animation: spin 1s ease-in-out infinite;
        }
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
        h2 {
          margin-top: 20px;
          letter-spacing: 2px;
          font-weight: 300;
        }
      </style>
    </head>
    <body>
      <div class="spinner"></div>
      <h2>A INICIALIZAR SISTEMA JARVIS OS...</h2>
    </body>
    </html>
  `));

  mainWindow.on('closed', () => {
    mainWindow = null;
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
