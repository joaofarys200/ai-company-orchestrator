import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { normalizeServerMessage, type ClientMessage, type ServerMessage } from '../../protocol/websocket.ts';
import {
  buildMediaCandidateUrls,
  createTransportRequestId,
  resolveTransportMediaUrl,
} from '../JarvisTransport.ts';
import {
  normalizeTransportTimeout,
  TRANSPORT_DEFAULT_TIMEOUT_MS,
  TRANSPORT_MAX_TIMEOUT_MS,
  TRANSPORT_MIN_TIMEOUT_MS,
  TransportError,
  WS_READY_STATE_CLOSED,
  WS_READY_STATE_CONNECTING,
  WS_READY_STATE_OPEN,
  type NativeDesktopBridge,
  type TransportStatusSnapshot,
  type WebSocketCloseEventLike,
  type WebSocketLike,
  type WebSocketMessageEventLike,
} from '../TransportTypes.ts';
import { WebSocketTransportAdapter } from '../WebSocketTransportAdapter.ts';

class MockWebSocket implements WebSocketLike {
  readonly url: string;
  readyState: number = WS_READY_STATE_CONNECTING;
  readonly sentMessages: string[] = [];
  closeCalls: Array<{ code?: number; reason?: string }> = [];

  onopen: ((event: unknown) => void) | null = null;
  onclose: ((event: WebSocketCloseEventLike) => void) | null = null;
  onerror: ((event: unknown) => void) | null = null;
  onmessage: ((event: WebSocketMessageEventLike) => void) | null = null;

  constructor(url: string) {
    this.url = url;
  }

  send(data: string): void {
    if (this.readyState !== WS_READY_STATE_OPEN) {
      throw new Error('WebSocket is not open');
    }
    this.sentMessages.push(data);
  }

  close(code?: number, reason?: string): void {
    this.closeCalls.push({ code, reason });
    if (this.readyState === WS_READY_STATE_CLOSED) {
      return;
    }
    this.readyState = WS_READY_STATE_CLOSED;
    if (this.onclose) {
      this.onclose({ code: code ?? 1000, reason: reason ?? '', wasClean: true });
    }
  }

  simulateOpen(): void {
    this.readyState = WS_READY_STATE_OPEN;
    if (this.onopen) {
      this.onopen({});
    }
  }

  simulateServerJson(payload: unknown): void {
    if (this.onmessage) {
      this.onmessage({ data: JSON.stringify(payload) });
    }
  }

  simulateRawMessage(data: unknown): void {
    if (this.onmessage) {
      this.onmessage({ data });
    }
  }

  simulateDrop(code = 1006, reason = 'network dropped'): void {
    this.readyState = WS_READY_STATE_CLOSED;
    if (this.onclose) {
      this.onclose({ code, reason, wasClean: false });
    }
  }

  simulateError(err: unknown): void {
    if (this.onerror) {
      this.onerror(err);
    }
  }
}

interface MockNativeHarness {
  bridge: NativeDesktopBridge;
  sent: unknown[];
  openedPaths: string[];
  emit: (payload: unknown) => void;
  getListenerCount: () => number;
}

function createMockNativeBridge(options?: { selectedFolder?: string | null }): MockNativeHarness {
  const listeners = new Set<(data: unknown) => void>();
  const sent: unknown[] = [];
  const openedPaths: string[] = [];

  const bridge: NativeDesktopBridge = {
    isNativeIPC: true,
    send: (msg: unknown) => {
      sent.push(msg);
    },
    onMessage: (cb: (data: unknown) => void) => {
      listeners.add(cb);
      return () => {
        listeners.delete(cb);
      };
    },
    getPathForFile: (file: File) => `/native/path/${file.name}`,
    selectFolder: async () => options?.selectedFolder ?? '/courses/math',
    openPath: async (targetPath: string) => {
      openedPaths.push(targetPath);
      return { ok: true };
    },
  };

  return {
    bridge,
    sent,
    openedPaths,
    emit: (payload: unknown) => {
      for (const cb of Array.from(listeners)) {
        cb(payload);
      }
    },
    getListenerCount: () => listeners.size,
  };
}

function createAdapterHarness(options?: {
  nativeBridge?: NativeDesktopBridge | null;
  wsUrl?: string;
  httpBaseUrl?: string;
  httpToken?: string;
  randomFn?: () => number;
}) {
  const sockets: MockWebSocket[] = [];
  const adapter = new WebSocketTransportAdapter({
    wsUrl: options?.wsUrl ?? 'ws://127.0.0.1:8001/?token=test-token',
    httpBaseUrl: options?.httpBaseUrl,
    getHttpToken: () => options?.httpToken ?? '',
    nativeBridge: options?.nativeBridge ?? null,
    normalizeMessage: normalizeServerMessage,
    randomFn: options?.randomFn ?? (() => 0.5),
    createWebSocket: (url) => {
      const ws = new MockWebSocket(url);
      sockets.push(ws);
      return ws;
    },
  });
  return { adapter, sockets };
}

function parseLastSent(ws: MockWebSocket): Record<string, unknown> {
  assert.ok(ws.sentMessages.length > 0, 'Expected at least one outbound WebSocket message');
  return JSON.parse(ws.sentMessages[ws.sentMessages.length - 1]) as Record<string, unknown>;
}

describe('JarvisTransport & WebSocketTransportAdapter Compatibility', () => {
  it('correlates concurrent out-of-order invoke requests by unique request_id', async () => {
    const { adapter, sockets } = createAdapterHarness();
    adapter.system.connect();
    const ws = sockets[0];
    ws.simulateOpen();

    const p1 = adapter.invoke<ServerMessage>(
      { type: 'study_generate_summary', document_id: 'doc_1', mode: 'Quick' },
      {
        requestId: 'req-sum-1',
        matchResponse: (m) =>
          m.type === 'study_summary_ready' ? { kind: 'resolve', value: m } : { kind: 'ignore' },
      }
    );

    const p2 = adapter.invoke<ServerMessage>(
      { type: 'study_generate_summary', document_id: 'doc_2', mode: 'Study' },
      {
        requestId: 'req-sum-2',
        matchResponse: (m) =>
          m.type === 'study_summary_ready' ? { kind: 'resolve', value: m } : { kind: 'ignore' },
      }
    );

    assert.equal(ws.sentMessages.length, 2);
    assert.equal(JSON.parse(ws.sentMessages[0]).request_id, 'req-sum-1');
    assert.equal(JSON.parse(ws.sentMessages[1]).request_id, 'req-sum-2');
    assert.equal(adapter.system.getStatus().pendingRequests, 2);

    // Resolve request 2 before request 1 (out of order)
    ws.simulateServerJson({
      type: 'study_summary_ready',
      document_id: 'doc_2',
      summary: 'Summary Two',
      request_id: 'req-sum-2',
    });
    ws.simulateServerJson({
      type: 'study_summary_ready',
      document_id: 'doc_1',
      summary: 'Summary One',
      request_id: 'req-sum-1',
    });

    const [r1, r2] = await Promise.all([p1, p2]);
    assert.equal((r1 as Extract<ServerMessage, { type: 'study_summary_ready' }>).summary, 'Summary One');
    assert.equal((r2 as Extract<ServerMessage, { type: 'study_summary_ready' }>).summary, 'Summary Two');
    assert.equal(adapter.system.getStatus().pendingRequests, 0);

    adapter.dispose();
  });

  it('prevents duplicate responses and misattributed legacy fallback responses', async () => {
    const { adapter, sockets } = createAdapterHarness();
    adapter.system.connect();
    const ws = sockets[0];
    ws.simulateOpen();

    let matchCountA = 0;
    const pA = adapter.invoke<string>(
      { type: 'read_note', filename: 'Alpha.md' },
      {
        requestId: 'req-note-a',
        matchResponse: (msg) => {
          matchCountA += 1;
          return msg.type === 'note_content'
            ? { kind: 'resolve', value: msg.content }
            : { kind: 'ignore' };
        },
        legacyMatchResponse: (msg) =>
          msg.type === 'note_content' && msg.filename === 'Alpha.md'
            ? { kind: 'resolve', value: msg.content }
            : { kind: 'ignore' },
      }
    );

    let legacyCalledB = false;
    const controllerB = new AbortController();
    const pB = adapter.invoke<string>(
      { type: 'read_note', filename: 'Beta.md' },
      {
        requestId: 'req-note-b',
        signal: controllerB.signal,
        matchResponse: () => ({ kind: 'ignore' }),
        legacyMatchResponse: (msg) => {
          legacyCalledB = true;
          return msg.type === 'note_content'
            ? { kind: 'resolve', value: msg.content }
            : { kind: 'ignore' };
        },
      }
    );

    // Response tagged with foreign request_id must NEVER trigger legacyMatchResponse on B
    ws.simulateServerJson({
      type: 'note_content',
      filename: 'Foreign.md',
      content: 'wrong note',
      request_id: 'req-unknown-foreign',
    });
    assert.equal(legacyCalledB, false);

    // Note that raw request_id on note_content correlates pA even if normalizeServerMessage omits request_id
    ws.simulateServerJson({
      type: 'note_content',
      filename: 'Alpha.md',
      content: 'Alpha body',
      request_id: 'req-note-a',
    });
    // Duplicate response for already-settled req-note-a must be ignored cleanly
    ws.simulateServerJson({
      type: 'note_content',
      filename: 'Alpha.md',
      content: 'Alpha duplicate',
      request_id: 'req-note-a',
    });

    assert.equal(await pA, 'Alpha body');
    assert.equal(matchCountA, 1);

    // Reject duplicate in-flight requestId
    await assert.rejects(
      adapter.invoke({ type: 'list_projects' }, { requestId: 'req-note-b' }),
      (err: unknown) => err instanceof TransportError && err.code === 'DUPLICATE_REQUEST_ID'
    );

    controllerB.abort();
    await assert.rejects(
      pB,
      (err: unknown) => err instanceof TransportError && err.code === 'ABORTED'
    );

    adapter.dispose();
  });

  it('supports configurable timeouts between 5s and 900s and clamps out-of-range bounds', async (t) => {
    assert.equal(normalizeTransportTimeout(undefined), TRANSPORT_DEFAULT_TIMEOUT_MS);
    assert.equal(normalizeTransportTimeout(100), TRANSPORT_MIN_TIMEOUT_MS);
    assert.equal(normalizeTransportTimeout(5000), 5000);
    assert.equal(normalizeTransportTimeout(900000), 900000);
    assert.equal(normalizeTransportTimeout(1_500_000), TRANSPORT_MAX_TIMEOUT_MS);

    t.mock.timers.enable({ apis: ['setTimeout'] });
    const { adapter, sockets } = createAdapterHarness();
    adapter.system.connect();
    const ws = sockets[0];
    ws.simulateOpen();

    // 1. Clamped low (<5s) becomes 5000ms
    const lowPromise = adapter.invoke(
      { type: 'study_get_document_file', document_id: 'doc_1' },
      { requestId: 'req-timeout-5s', timeoutMs: 1000 }
    );
    let lowSettled = false;
    void lowPromise.catch(() => {
      lowSettled = true;
    });

    t.mock.timers.tick(4999);
    await Promise.resolve();
    assert.equal(lowSettled, false);

    t.mock.timers.tick(1);
    await assert.rejects(
      lowPromise,
      (err: unknown) => err instanceof TransportError && err.code === 'TIMEOUT'
    );

    // 2. Maximum 900s timeout stays alive at 899,999ms and expires at 900,000ms
    const longPromise = adapter.invoke(
      { type: 'study_generate_study_document', document_id: 'doc_1' },
      { requestId: 'req-timeout-900s', timeoutMs: 900000 }
    );
    let longSettled = false;
    void longPromise.catch(() => {
      longSettled = true;
    });

    t.mock.timers.tick(899999);
    await Promise.resolve();
    assert.equal(longSettled, false);

    t.mock.timers.tick(1);
    await assert.rejects(
      longPromise,
      (err: unknown) => err instanceof TransportError && err.code === 'TIMEOUT'
    );

    adapter.dispose();
  });

  it('supports AbortSignal cancellation, cancelMessage dispatch, and predicate cancellation', async () => {
    const { adapter, sockets } = createAdapterHarness();
    adapter.system.connect();
    const ws = sockets[0];
    ws.simulateOpen();

    // Already aborted before send -> never sends
    const preAborted = new AbortController();
    preAborted.abort('cancelled upfront');
    const preCount = ws.sentMessages.length;
    await assert.rejects(
      adapter.invoke({ type: 'study_generate_summary', document_id: 'doc_pre' }, { signal: preAborted.signal }),
      (err: unknown) => err instanceof TransportError && err.code === 'ABORTED'
    );
    assert.equal(ws.sentMessages.length, preCount);

    // Mid-flight abort sends cancelMessage and rejects pending request
    const controller = new AbortController();
    const p = adapter.invoke(
      { type: 'study_generate_study_document', document_id: 'doc_abort' },
      {
        requestId: 'req-abort-mid',
        signal: controller.signal,
        cancelMessage: (reqId): ClientMessage => ({
          type: 'study_cancel_generation',
          document_id: 'doc_abort',
          request_id: reqId,
        }),
      }
    );
    controller.abort();
    await assert.rejects(p, (err: unknown) => err instanceof TransportError && err.code === 'ABORTED');
    const lastSent = parseLastSent(ws);
    assert.equal(lastSent.type, 'study_cancel_generation');
    assert.equal(lastSent.request_id, 'req-abort-mid');

    // cancelPendingRequests cancels all document-tagged requests
    const tagged1 = adapter.invoke(
      { type: 'study_generate_summary', document_id: 'doc_tag' },
      { requestId: 'req-tag-1', tag: 'doc_tag' }
    );
    const tagged2 = adapter.invoke(
      { type: 'study_generate_cornell', document_id: 'doc_other' },
      { requestId: 'req-tag-2', tag: 'doc_other' }
    );

    const cancelled = adapter.cancelPendingRequests((meta) => meta.tag === 'doc_tag', 'User stopped doc_tag');
    assert.equal(cancelled, 1);
    await assert.rejects(
      tagged1,
      (err: unknown) => err instanceof TransportError && err.code === 'ABORTED'
    );
    assert.equal(adapter.system.getStatus().pendingRequests, 1);

    ws.simulateServerJson({
      type: 'study_notes_ready',
      document_id: 'doc_other',
      cornell: { topic: 'EVM' },
      request_id: 'req-tag-2',
    });
    await tagged2;

    adapter.dispose();
  });

  it('reconnects with exponential backoff + jitter and recovers cleanly after connection drops', async (t) => {
    t.mock.timers.enable({ apis: ['setTimeout'] });
    const sockets: MockWebSocket[] = [];
    // randomFn = 1.0 gives maximum positive jitter (+25%)
    const adapter = new WebSocketTransportAdapter({
      normalizeMessage: normalizeServerMessage,
      randomFn: () => 1.0,
      reconnectPolicy: {
        initialDelayMs: 1000,
        maxDelayMs: 4000,
        multiplier: 2,
        jitterFactor: 0.25,
      },
      createWebSocket: (url) => {
        const ws = new MockWebSocket(url);
        sockets.push(ws);
        return ws;
      },
    });

    const states: Array<TransportStatusSnapshot['status']> = [];
    adapter.subscribeConnectionState((snap) => states.push(snap.status));
    let connectedEvents = 0;
    adapter.onConnected(() => {
      connectedEvents += 1;
    });

    adapter.system.connect();
    assert.equal(sockets.length, 1);
    sockets[0].simulateOpen();
    assert.equal(connectedEvents, 1);

    // Start an in-flight call, then drop the socket
    const droppedCall = adapter.invoke(
      { type: 'get_vault_diagnostics' },
      { requestId: 'req-drop-1' }
    );
    sockets[0].simulateDrop(1006, 'connection lost');

    await assert.rejects(
      droppedCall,
      (err: unknown) => err instanceof TransportError && err.code === 'DISCONNECTED'
    );
    assert.equal(adapter.system.getStatus().status, 'RECONNECTING');

    // Attempt 0: base=1000 +25% => 1250ms
    t.mock.timers.tick(1249);
    assert.equal(sockets.length, 1);
    t.mock.timers.tick(1);
    assert.equal(sockets.length, 2);

    // Drop attempt 1 immediately: base=2000 +25% => 2500ms
    sockets[1].simulateDrop(1006, 'still down');
    t.mock.timers.tick(2499);
    assert.equal(sockets.length, 2);
    t.mock.timers.tick(1);
    assert.equal(sockets.length, 3);

    // Drop attempt 2: base=4000 +25% => 5000ms (capped at maxDelayMs=4000 + jitter)
    sockets[2].simulateDrop(1006, 'still down');
    t.mock.timers.tick(4999);
    assert.equal(sockets.length, 3);
    t.mock.timers.tick(1);
    assert.equal(sockets.length, 4);

    // Recover cleanly on socket 4
    sockets[3].simulateOpen();
    assert.equal(connectedEvents, 2);
    assert.equal(adapter.system.getStatus().status, 'CONNECTED');
    assert.equal(adapter.system.getStatus().reconnectAttempt, 0);

    // New request works immediately after recovery
    const recoveredCall = adapter.invoke<ServerMessage>(
      { type: 'list_projects' },
      {
        requestId: 'req-recovered-1',
        matchResponse: (m) =>
          m.type === 'projects_list' ? { kind: 'resolve', value: m } : { kind: 'ignore' },
      }
    );
    sockets[3].simulateServerJson({
      type: 'projects_list',
      projects: [],
      request_id: 'req-recovered-1',
    });
    const res = await recoveredCall;
    assert.equal(res.type, 'projects_list');
    assert.ok(states.includes('RECONNECTING'));
    assert.equal(states[states.length - 1], 'CONNECTED');

    adapter.dispose();
  });

  it('supports openStream progress chunks, completion, error rejection, and cancellation', async () => {
    const { adapter, sockets } = createAdapterHarness();
    adapter.system.connect();
    const ws = sockets[0];
    ws.simulateOpen();

    const chunks: number[] = [];
    const stream = adapter.openStream<number>(
      { type: 'study_generate_study_document', document_id: 'doc_stream' },
      {
        correlationId: 'stream-doc-1',
        timeoutMs: 10000,
        matchChunk: (msg) => {
          if (msg.type === 'study_generated_document_progress') {
            return { kind: 'chunk', chunk: msg.progress };
          }
          if (msg.type === 'study_generated_document_result') {
            return { kind: 'complete', chunk: 1 };
          }
          if (msg.type === 'study_error') {
            return { kind: 'error', error: new Error(msg.message) };
          }
          return { kind: 'ignore' };
        },
      },
      (progress) => {
        chunks.push(progress);
      }
    );

    ws.simulateServerJson({
      type: 'study_generated_document_progress',
      document_id: 'doc_stream',
      stage: 'planning',
      progress: 0.25,
      message: 'Planning',
      request_id: 'stream-doc-1',
    });
    ws.simulateServerJson({
      type: 'study_generated_document_progress',
      document_id: 'doc_stream',
      stage: 'rendering',
      progress: 0.75,
      message: 'Rendering',
      request_id: 'stream-doc-1',
    });
    ws.simulateServerJson({
      type: 'study_generated_document_result',
      document_id: 'doc_stream',
      result: null,
      status: null,
      request_id: 'stream-doc-1',
    });

    await stream.done;
    assert.deepEqual(chunks, [0.25, 0.75, 1]);
    assert.equal(adapter.system.getStatus().activeStreams, 0);

    // Second stream cancelled explicitly
    const cancelledStream = adapter.openStream<ServerMessage>(
      { type: 'study_generate_editorial_plan', document_id: 'doc_cancel_stream' },
      {
        correlationId: 'stream-cancel-1',
        matchChunk: (m) => ({ kind: 'chunk', chunk: m }),
        cancelMessage: (id): ClientMessage => ({
          type: 'study_cancel_generation',
          document_id: 'doc_cancel_stream',
          request_id: id,
        }),
      },
      () => {}
    );
    cancelledStream.cancel('Stopped stream');
    await assert.rejects(
      cancelledStream.done,
      (err: unknown) => err instanceof TransportError && err.code === 'ABORTED'
    );
    assert.equal(parseLastSent(ws).type, 'study_cancel_generation');

    adapter.dispose();
  });

  it('cleans up all subscribers, native IPC hooks, and pending requests on unsubscribe and dispose', async () => {
    const nativeHarness = createMockNativeBridge();
    const { adapter, sockets } = createAdapterHarness({
      nativeBridge: nativeHarness.bridge,
    });
    assert.equal(nativeHarness.getListenerCount(), 1);

    let systemCount = 0;
    let anyCount = 0;
    const unsubSystem = adapter.subscribe('system', () => {
      systemCount += 1;
    });
    const unsubAny = adapter.subscribeAny(() => {
      anyCount += 1;
    });

    adapter.system.connect();
    const ws = sockets[0];
    ws.simulateOpen();

    ws.simulateServerJson({ type: 'system', content: 'first' });
    assert.equal(systemCount, 1);
    assert.equal(anyCount, 1);

    unsubSystem();
    ws.simulateServerJson({ type: 'system', content: 'second' });
    assert.equal(systemCount, 1);
    assert.equal(anyCount, 2);

    unsubAny();
    const pendingBeforeDispose = adapter.invoke(
      { type: 'get_notes' },
      { requestId: 'req-dispose-pending' }
    );

    adapter.dispose();
    assert.equal(nativeHarness.getListenerCount(), 0);
    assert.equal(ws.readyState, WS_READY_STATE_CLOSED);
    await assert.rejects(
      pendingBeforeDispose,
      (err: unknown) => err instanceof TransportError && err.code === 'TRANSPORT_CLOSED'
    );

    // Post-dispose send/invoke are safely rejected / ignored
    assert.equal(adapter.send({ type: 'list_projects' }), false);
    await assert.rejects(
      adapter.invoke({ type: 'list_projects' }),
      (err: unknown) => err instanceof TransportError && err.code === 'TRANSPORT_CLOSED'
    );
  });

  it('preserves compatibility across Study, IDE, Obsidian, Agents, Sentinel, Native IPC, and Media URLs', async () => {
    const nativeHarness = createMockNativeBridge({ selectedFolder: 'D:/University/Courses' });
    const { adapter, sockets } = createAdapterHarness({
      nativeBridge: nativeHarness.bridge,
      httpBaseUrl: 'http://127.0.0.1:8000',
      httpToken: 'secret-http-token',
    });

    // Native IPC fallback works even before WebSocket opens
    assert.equal(adapter.system.isNativeDesktop(), true);
    assert.equal(adapter.system.isReady(), true);
    assert.equal(await adapter.system.selectFolder(), 'D:/University/Courses');
    const openRes = await adapter.system.openPath('D:/University/Courses');
    assert.deepEqual(openRes, { ok: true });
    assert.deepEqual(nativeHarness.openedPaths, ['D:/University/Courses']);

    const ipcRequest = adapter.invoke<ServerMessage>(
      { type: 'study_get_document_file', document_id: 'doc_pdf_1' },
      {
        requestId: 'req-ipc-study',
        matchResponse: (m) =>
          m.type === 'study_document_file_result'
            ? { kind: 'resolve', value: m }
            : { kind: 'ignore' },
      }
    );
    assert.equal(nativeHarness.sent.length, 1);
    nativeHarness.emit({
      type: 'study_document_file_result',
      document_id: 'doc_pdf_1',
      filename: 'lecture1.pdf',
      content_base64: 'JVBERi0xLjQK',
      request_id: 'req-ipc-study',
    });
    const studyFileMsg = await ipcRequest;
    assert.equal(studyFileMsg.type, 'study_document_file_result');

    // Media URL helpers preserve token query & candidate paths
    assert.equal(
      resolveTransportMediaUrl('/api/study/document/doc%201/video', {
        baseUrl: 'http://127.0.0.1:8000',
        token: 'tok 1',
        appendToken: true,
      }),
      'http://127.0.0.1:8000/api/study/document/doc%201/video?token=tok%201'
    );
    const candidates = buildMediaCandidateUrls(['/api/study/document/d1/file'], {
      baseUrl: 'http://127.0.0.1:8000',
      token: 'abc',
      appendToken: true,
    });
    assert.ok(candidates.includes('/api/study/document/d1/file?token=abc'));
    assert.ok(candidates.includes('http://127.0.0.1:8000/api/study/document/d1/file?token=abc'));

    // Connect WebSocket for domain events across IDE, Obsidian, Agents/Missions, Sentinel
    adapter.system.connect();
    const ws = sockets[0];
    ws.simulateOpen();

    const receivedTypes: string[] = [];
    adapter.subscribe('project_context', (m) => receivedTypes.push(m.type));
    adapter.subscribe('vault_diagnostics', (m) => receivedTypes.push(m.type));
    adapter.subscribe('mission_snapshot', (m) => receivedTypes.push(m.type));
    adapter.subscribe('sentinel_status', (m) => receivedTypes.push(m.type));
    adapter.subscribe('permission_request_created', (m) => receivedTypes.push(m.type));

    ws.simulateServerJson({
      type: 'project_context',
      context: { project_id: 'proj_1', project_name: 'Demo', root_path: '/repo' },
      files: { 'main.py': 'print(1)' },
    });
    ws.simulateServerJson({
      type: 'vault_diagnostics',
      diagnostics: { quality_average: 91, total_notes: 5 },
      queue: [],
    });
    ws.simulateServerJson({
      type: 'mission_snapshot',
      data: { mission_id: 'm1', goal: 'Test', status: 'RUNNING' },
    });
    ws.simulateServerJson({
      type: 'sentinel_status',
      data: { posture: 'GOOD', status: 'RUNNING' },
    });
    ws.simulateServerJson({
      type: 'permission_request_created',
      request: {
        request_id: 'perm_1',
        tool_name: 'run_shell',
        reason: 'Execute pytest',
      },
    });

    assert.deepEqual(receivedTypes, [
      'project_context',
      'vault_diagnostics',
      'mission_snapshot',
      'sentinel_status',
      'permission_request_created',
    ]);

    const generatedId = createTransportRequestId('unit');
    assert.ok(generatedId.startsWith('unit:'));

    adapter.dispose();
  });
});
