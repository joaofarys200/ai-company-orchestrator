import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { once } from "node:events";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const backend = path.join(root, "backend", "server.js");

function sleep(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

async function startBackend() {
  const selectedPort = 32000 + Math.floor(Math.random() * 1000);
  const child = spawn(process.execPath, [backend], {
    cwd: root,
    env: { ...process.env, PORT: String(selectedPort) },
    stdio: ["ignore", "pipe", "pipe"],
  });
  let stderr = "";
  child.stderr.setEncoding("utf8");
  child.stderr.on("data", (chunk) => { stderr += chunk; });
  const url = `http://127.0.0.1:${selectedPort}`;
  for (let attempt = 0; attempt < 50; attempt += 1) {
    if (child.exitCode !== null) throw new Error(`backend exited: ${stderr}`);
    try {
      const response = await fetch(`${url}/health`);
      if (response.status === 200) return { child, url };
    } catch {}
    await sleep(50);
  }
  throw new Error(`backend did not become ready: ${stderr}`);
}

async function stopBackend(child) {
  if (child.exitCode !== null) return;
  child.kill("SIGTERM");
  await Promise.race([once(child, "exit"), sleep(2000)]);
  if (child.exitCode === null) child.kill();
}

async function runTests() {
  let backendProcess;
  const record = { id: "restart-proof", value: 42 };
  try {
    ({ child: backendProcess, url: globalThis.backendUrl } = await startBackend());
    const health = await fetch(`${globalThis.backendUrl}/health`);
    assert.equal(health.status, 200);
    assert.equal((await health.json()).status, "ok");
    const created = await fetch(`${globalThis.backendUrl}/records`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(record),
    });
    assert.equal(created.status, 201);
    await stopBackend(backendProcess);
    backendProcess = undefined;

    ({ child: backendProcess, url: globalThis.backendUrl } = await startBackend());
    const records = await fetch(`${globalThis.backendUrl}/records`);
    assert.equal(records.status, 200);
    assert.deepEqual((await records.json()).at(-1), record);
    console.log("real backend, healthcheck, persistence restart and cleanup passed");
  } finally {
    if (backendProcess) await stopBackend(backendProcess);
  }
}

runTests().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
