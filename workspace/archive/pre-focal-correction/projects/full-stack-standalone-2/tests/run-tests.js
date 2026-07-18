import http from 'http';
import { spawn } from 'child_process';
import { dirname, resolve } from 'path';
import { fileURLToPath } from 'url';

const currentDir = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(currentDir, '..');
const PORT = 32000 + (process.pid % 10000);

function sleep(ms) {
  return new Promise(resolveSleep => setTimeout(resolveSleep, ms));
}

function requestHealth() {
  return new Promise((resolveRequest, rejectRequest) => {
    const request = http.get(`http://127.0.0.1:${PORT}/health`, response => {
      let body = '';
      response.setEncoding('utf8');
      response.on('data', chunk => {
        body += chunk;
      });
      response.on('end', () => resolveRequest({ statusCode: response.statusCode, body }));
    });

    request.setTimeout(500, () => request.destroy(new Error('Health request timed out')));
    request.on('error', rejectRequest);
  });
}

async function waitForBackend(backend, getSpawnError, getStderr) {
  const deadline = Date.now() + 5000;
  let lastError = null;

  while (Date.now() < deadline) {
    const spawnError = getSpawnError();
    if (spawnError) {
      throw spawnError;
    }

    if (backend.exitCode !== null || backend.signalCode !== null) {
      throw new Error(`Backend exited before healthcheck: ${getStderr()}`);
    }

    try {
      const response = await requestHealth();
      if (response.statusCode !== 200) {
        throw new Error(`Expected HTTP 200, received ${response.statusCode}`);
      }
      const payload = JSON.parse(response.body);
      if (payload.status !== 'ok') {
        throw new Error('Health response does not contain status "ok"');
      }
      return;
    } catch (error) {
      lastError = error;
      await sleep(100);
    }
  }

  throw new Error(`Backend healthcheck timed out: ${lastError?.message || 'no response'}`);
}

async function stopBackend(backend) {
  if (!backend.pid || backend.exitCode !== null || backend.signalCode !== null) {
    return;
  }

  backend.kill();
  for (let attempt = 0; attempt < 20; attempt += 1) {
    if (backend.exitCode !== null || backend.signalCode !== null) {
      return;
    }
    await sleep(50);
  }

  backend.kill('SIGKILL');
  for (let attempt = 0; attempt < 20; attempt += 1) {
    if (backend.exitCode !== null || backend.signalCode !== null) {
      return;
    }
    await sleep(50);
  }

  throw new Error('Backend process could not be stopped');
}

async function runTests() {
  let stderr = '';
  let spawnError = null;
  const backend = spawn(process.execPath, ['backend/server.js'], {
    cwd: projectRoot,
    env: { ...process.env, PORT: String(PORT) },
    stdio: ['ignore', 'ignore', 'pipe']
  });

  backend.on('error', error => {
    spawnError = error;
  });
  backend.stderr.setEncoding('utf8');
  backend.stderr.on('data', chunk => {
    stderr += chunk;
  });

  try {
    await waitForBackend(backend, () => spawnError, () => stderr);
    console.log('Test passed: real backend health endpoint returned status ok.');
  } finally {
    await stopBackend(backend);
  }
}

runTests().catch(error => {
  console.error('Test suite failed:', error.message);
  process.exitCode = 1;
});
