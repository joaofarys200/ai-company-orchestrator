import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

import { createDefaultTransport } from '../createDefaultTransport.ts';
import {
  isTauriRuntime,
  isVirtualDesktopOrigin,
  resolveDefaultHttpBaseUrl,
} from '../JarvisTransport.ts';
import {
  TauriTransportAdapter,
  type TauriDragDropEventPayload,
  type TauriRuntimeApis,
} from '../TauriTransportAdapter.ts';
import {
  TransportError,
  WS_READY_STATE_CLOSED,
  WS_READY_STATE_CONNECTING,
  WS_READY_STATE_OPEN,
  type WebSocketLike,
} from '../TransportTypes.ts';
import { WebSocketTransportAdapter } from '../WebSocketTransportAdapter.ts';

class MockWebSocket implements WebSocketLike {
  readonly url: string;
  readyState: number = WS_READY_STATE_CONNECTING;
  sentPayloads: string[] = [];

  onopen: ((event?: unknown) => void) | null = null;
  onclose: ((event?: { code?: number; reason?: string }) => void) | null = null;
  onerror: ((event?: unknown) => void) | null = null;
  onmessage: ((event: { data: unknown }) => void) | null = null;

  constructor(url: string) {
    this.url = url;
  }

  send(data: string): void {
    this.sentPayloads.push(data);
  }

  close(code = 1000, reason = ''): void {
    this.readyState = WS_READY_STATE_CLOSED;
    if (this.onclose) {
      this.onclose({ code, reason });
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
}

interface MockTauriHarness {
  apis: TauriRuntimeApis;
  invokedCommands: Array<{ command: string; args?: Record<string, unknown> }>;
  emitEvent: (eventName: string, payload: unknown) => void;
  emitDragDrop: (payload: TauriDragDropEventPayload) => void;
  unlistenCount: () => number;
}

function createMockTauriHarness(options?: {
  pingOk?: boolean;
  loopbackConfig?: { base_url: string; token: string; preview_base_url?: string } | Error;
  ticketFactory?: (docId: string) => { ticket: string; base_url?: string; expires_at_ms?: number } | Error;
  dialogResult?: string | string[] | null;
  openPathError?: Error;
  onInvokeDispatch?: (
    args: Record<string, unknown> | undefined,
    emit: (payload: unknown) => void
  ) => unknown;
}): MockTauriHarness {
  const invokedCommands: Array<{ command: string; args?: Record<string, unknown> }> = [];
  const listeners = new Map<string, Set<(event: { event?: string; payload: unknown }) => void>>();
  const dragHandlers = new Set<(payload: TauriDragDropEventPayload) => void>();
  let unlistenCalls = 0;

  const emitEvent = (eventName: string, payload: unknown) => {
    const handlers = listeners.get(eventName);
    if (!handlers) return;
    for (const handler of Array.from(handlers)) {
      handler({ event: eventName, payload });
    }
  };

  const apis: TauriRuntimeApis = {
    isTauri: () => true,
    invoke: async <T = unknown>(command: string, args?: Record<string, unknown>): Promise<T> => {
      invokedCommands.push({ command, args });
      if (command === 'system_ping') {
        return {
          ok: options?.pingOk ?? true,
          runtime: 'tauri-rust',
          timestamp_ms: 1700000000000,
        } as T;
      }
      if (command === 'get_loopback_config') {
        if (options?.loopbackConfig instanceof Error) {
          throw options.loopbackConfig;
        }
        if (options?.loopbackConfig) {
          return options.loopbackConfig as T;
        }
        throw new Error('command get_loopback_config not found');
      }
      if (command === 'get_media_ticket') {
        const docId = String(args?.docId ?? '');
        if (options?.ticketFactory) {
          const result = options.ticketFactory(docId);
          if (result instanceof Error) {
            throw result;
          }
          return result as T;
        }
        throw new Error('command get_media_ticket not found');
      }
      if (command === 'system_open_path') {
        if (options?.openPathError) {
          throw options.openPathError;
        }
        return undefined as T;
      }
      if (command === 'cancel_client_request') {
        return true as T;
      }
      if (command === 'dispatch_client_message') {
        if (options?.onInvokeDispatch) {
          return options.onInvokeDispatch(args, (payload) => emitEvent('jarvis:event', payload)) as T;
        }
        return undefined as T;
      }
      throw new Error(`Unexpected invoke command: ${command}`);
    },
    listen: async <T = unknown>(
      eventName: string,
      handler: (event: { event?: string; payload: T }) => void
    ) => {
      let set = listeners.get(eventName);
      if (!set) {
        set = new Set();
        listeners.set(eventName, set);
      }
      const wrapped = handler as (event: { event?: string; payload: unknown }) => void;
      set.add(wrapped);
      return () => {
        unlistenCalls += 1;
        listeners.get(eventName)?.delete(wrapped);
      };
    },
    openDialog: async () => options?.dialogResult ?? null,
    onDragDropEvent: async (handler) => {
      dragHandlers.add(handler);
      return () => {
        unlistenCalls += 1;
        dragHandlers.delete(handler);
      };
    },
  };

  return {
    apis,
    invokedCommands,
    emitEvent,
    emitDragDrop: (payload) => {
      for (const handler of Array.from(dragHandlers)) {
        handler(payload);
      }
    },
    unlistenCount: () => unlistenCalls,
  };
}

describe('Platform detection & virtual origin safety', () => {
  it('blocks virtual Tauri/Vite/file origins in resolveDefaultHttpBaseUrl', () => {
    const prevWindow = (globalThis as { window?: unknown }).window;
    try {
      assert.equal(isVirtualDesktopOrigin('http://tauri.localhost'), true);
      assert.equal(isVirtualDesktopOrigin('https://tauri.localhost'), true);
      assert.equal(isVirtualDesktopOrigin('tauri://localhost'), true);
      assert.equal(isVirtualDesktopOrigin('http://ipc.localhost'), true);
      assert.equal(isVirtualDesktopOrigin('http://127.0.0.1:5173'), true);
      assert.equal(isVirtualDesktopOrigin('file://'), true);
      assert.equal(isVirtualDesktopOrigin('http://127.0.0.1:49200'), false);

      (globalThis as { window?: unknown }).window = {
        location: {
          origin: 'http://tauri.localhost',
          protocol: 'http:',
          hostname: 'tauri.localhost',
        },
      };
      assert.equal(resolveDefaultHttpBaseUrl(), 'http://127.0.0.1:8000');
      assert.equal(resolveDefaultHttpBaseUrl('http://127.0.0.1:51234/'), 'http://127.0.0.1:51234');
      assert.equal(isTauriRuntime(), true);
    } finally {
      (globalThis as { window?: unknown }).window = prevWindow;
    }
  });

  it('auto-selects TauriTransportAdapter in createDefaultTransport when Tauri globals exist', () => {
    const g = globalThis as { __TAURI_INTERNALS__?: unknown };
    const hadInternals = '__TAURI_INTERNALS__' in g;
    const prevInternals = g.__TAURI_INTERNALS__;
    try {
      delete g.__TAURI_INTERNALS__;
      assert.equal(isTauriRuntime(), false);
      const wsTransport = createDefaultTransport({
        createWebSocket: (url) => new MockWebSocket(url),
      });
      assert.ok(wsTransport instanceof WebSocketTransportAdapter);
      wsTransport.dispose();

      g.__TAURI_INTERNALS__ = {};
      assert.equal(isTauriRuntime(), true);
      const harness = createMockTauriHarness();
      const tauriTransport = createDefaultTransport({
        tauriApis: harness.apis,
      });
      assert.ok(tauriTransport instanceof TauriTransportAdapter);
      assert.equal(tauriTransport.system.getStatus().backend, 'tauri-ipc');
      tauriTransport.dispose();
    } finally {
      if (hadInternals) {
        g.__TAURI_INTERNALS__ = prevInternals;
      } else {
        delete g.__TAURI_INTERNALS__;
      }
    }
  });
});

describe('TauriTransportAdapter native IPC mode', () => {
  it('bootstraps loopback config, handles native dialogs, drag-drop, media tickets and IPC correlation', async () => {
    let fakeNow = 10000;
    let ticketCounter = 0;
    const harness = createMockTauriHarness({
      loopbackConfig: {
        base_url: 'http://127.0.0.1:55123',
        token: 'loop-secret-token',
        preview_base_url: 'http://127.0.0.1:55124',
      },
      ticketFactory: (docId) => {
        ticketCounter += 1;
        return {
          ticket: `tkt-${docId}-${ticketCounter}`,
          expires_at_ms: fakeNow + 60000,
        };
      },
      dialogResult: ['C:\\Study\\Lecture01.pdf'],
      onInvokeDispatch: (args, emit) => {
        const msg = args?.message as { type: string; request_id?: string };
        if (msg?.type === 'study_get_document') {
          emit({
            type: 'study_document_details',
            request_id: msg.request_id,
            document: { document_id: 'doc-1', title: 'Calc I' },
          });
        }
        return null;
      },
    });

    const adapter = new TauriTransportAdapter({
      preferHybridFallback: false,
      tauriApis: harness.apis,
      nowFn: () => fakeNow,
    });

    let connectedFired = 0;
    adapter.onConnected(() => {
      connectedFired += 1;
    });

    adapter.connect();
    await new Promise((resolve) => setTimeout(resolve, 20));

    assert.equal(connectedFired, 1);
    assert.equal(adapter.system.isReady(), true);
    assert.equal(adapter.system.isNativeDesktop(), true);
    assert.equal(adapter.system.getStatus().backend, 'tauri-ipc');
    assert.equal(adapter.system.getStatus().status, 'CONNECTED');
    assert.equal(adapter.system.getHttpBaseUrl(), 'http://127.0.0.1:55123');
    assert.equal(adapter.system.getPreviewBaseUrl?.(), 'http://127.0.0.1:55124');

    // Native invoke correlation via jarvis:event
    const docDetails = await adapter.invoke<{ type: string; request_id: string; document: { document_id: string } }>({
      type: 'study_get_document',
      document_id: 'doc-1',
    });
    assert.equal(docDetails.type, 'study_document_details');
    assert.equal(docDetails.document.document_id, 'doc-1');
    assert.ok(docDetails.request_id.startsWith('study_get_document:'));

    // Native streaming + completion
    const receivedChunks: string[] = [];
    const streamHandle = adapter.openStream<string>(
      { type: 'study_generate_study_document', document_id: 'doc-1' },
      {
        matchChunk: (msg, corrId) => {
          if (msg.request_id !== corrId) return { kind: 'ignore' };
          if (msg.type === 'study_generated_document_progress') {
            return { kind: 'chunk', chunk: msg.stage };
          }
          if (msg.type === 'study_generated_document_result') {
            return { kind: 'complete' };
          }
          return { kind: 'ignore' };
        },
      },
      (chunk) => receivedChunks.push(chunk)
    );
    harness.emitEvent('jarvis:event', {
      type: 'study_generated_document_progress',
      request_id: streamHandle.requestId,
      document_id: 'doc-1',
      stage: 'drafting',
      progress: 40,
      message: 'Drafting',
    });
    harness.emitEvent('jarvis:event', {
      type: 'study_generated_document_progress',
      request_id: streamHandle.requestId,
      document_id: 'doc-1',
      stage: 'polishing',
      progress: 80,
      message: 'Polishing',
    });
    harness.emitEvent('jarvis:event', {
      type: 'study_generated_document_result',
      request_id: streamHandle.requestId,
      document_id: 'doc-1',
      result: { ok: true },
    });
    await streamHandle.done;
    assert.deepEqual(receivedChunks, ['drafting', 'polishing']);

    // Native dialog + file drop cache
    assert.equal(await adapter.system.selectFolder(), 'C:\\Study\\Lecture01.pdf');
    const selectedFile = await adapter.system.selectFile?.({ multiple: false });
    assert.deepEqual(selectedFile, ['C:\\Study\\Lecture01.pdf']);
    assert.equal(
      adapter.system.getPathForFile({ name: 'Lecture01.pdf' } as File),
      'C:\\Study\\Lecture01.pdf'
    );

    const dropEvents: string[][] = [];
    const unsubDrop = adapter.system.onFileDrop?.((paths) => dropEvents.push(paths));
    harness.emitDragDrop({ type: 'drop', paths: ['D:\\Videos\\Algebra.mp4'] });
    assert.deepEqual(dropEvents, [['D:\\Videos\\Algebra.mp4']]);
    assert.equal(
      adapter.system.getPathForFile({ name: 'Algebra.mp4' } as File),
      'D:\\Videos\\Algebra.mp4'
    );
    unsubDrop?.();

    // openPath success
    const openOk = await adapter.system.openPath('C:\\Study');
    assert.deepEqual(openOk, { ok: true });

    // Ticket caching + URL attachment (no raw bearer leak when ticket attached)
    const url1 = await adapter.system.resolveMediaUrlAsync?.('/api/study/document/doc-9/file', {
      docId: 'doc-9',
    });
    assert.equal(url1, 'http://127.0.0.1:55123/api/study/document/doc-9/file?ticket=tkt-doc-9-1');
    const url2 = await adapter.system.resolveMediaUrlAsync?.('/api/study/document/doc-9/video', {
      docId: 'doc-9',
    });
    assert.equal(url2, 'http://127.0.0.1:55123/api/study/document/doc-9/video?ticket=tkt-doc-9-1');
    assert.equal(ticketCounter, 1);

    // Expired ticket triggers fresh fetch
    fakeNow += 56000;
    const url3 = await adapter.system.resolveMediaUrlAsync?.('/api/study/document/doc-9/video', {
      docId: 'doc-9',
    });
    assert.equal(url3, 'http://127.0.0.1:55123/api/study/document/doc-9/video?ticket=tkt-doc-9-2');
    assert.equal(ticketCounter, 2);

    adapter.dispose();
    assert.equal(harness.unlistenCount(), 2);
  });

  it('rejects pending invoke cleanly on AbortSignal and returns openPath error cleanly', async () => {
    const harness = createMockTauriHarness({
      openPathError: new Error('Path outside allowed study roots'),
    });
    const adapter = new TauriTransportAdapter({
      preferHybridFallback: false,
      tauriApis: harness.apis,
    });
    adapter.connect();
    await new Promise((resolve) => setTimeout(resolve, 20));

    const openErr = await adapter.system.openPath('C:\\Windows\\System32');
    assert.deepEqual(openErr, { ok: false, error: 'Path outside allowed study roots' });

    const controller = new AbortController();
    const cancelSent: Array<Record<string, unknown>> = [];
    const harnessWithCancel = createMockTauriHarness({
      onInvokeDispatch: (args) => {
        const msg = args?.message as Record<string, unknown>;
        if (msg?.type === 'cancel_task') cancelSent.push(msg);
        return null;
      },
    });
    const adapter2 = new TauriTransportAdapter({
      preferHybridFallback: false,
      tauriApis: harnessWithCancel.apis,
    });
    adapter2.connect();
    await new Promise((resolve) => setTimeout(resolve, 20));

    const promise = adapter2.invoke(
      { type: 'slow_task' } as never,
      {
        signal: controller.signal,
        cancelMessage: (reqId) => ({ type: 'cancel_task', target_request_id: reqId } as never),
      }
    );
    controller.abort();

    await assert.rejects(promise, (err: unknown) => err instanceof TransportError && err.code === 'ABORTED');
    assert.equal(cancelSent.length, 1);

    adapter.dispose();
    adapter2.dispose();
  });
});

describe('TauriTransportAdapter hybrid coexistence mode', () => {
  it('routes legacy WS commands to fallback WS while handling native commands and system APIs over Tauri', async () => {
    let lastSocket: MockWebSocket | null = null;
    const harness = createMockTauriHarness({
      onInvokeDispatch: (args, emit) => {
        const msg = args?.message as { type: string; request_id?: string };
        if (msg?.type === 'study_get_document') {
          emit({
            type: 'study_document_details',
            request_id: msg.request_id,
            document: { document_id: 'doc-native', title: 'Native' },
          });
        }
        return null;
      },
    });

    const adapter = new TauriTransportAdapter({
      preferHybridFallback: true,
      nativeRpcCommands: ['study_get_document'],
      tauriApis: harness.apis,
      createWebSocket: (url) => {
        lastSocket = new MockWebSocket(url);
        return lastSocket;
      },
    });

    const receivedTypes: string[] = [];
    adapter.subscribeAny((msg) => {
      receivedTypes.push(msg.type);
    });

    adapter.connect();
    await new Promise((resolve) => setTimeout(resolve, 20));
    lastSocket!.simulateOpen();

    assert.equal(adapter.system.getStatus().backend, 'tauri-hybrid');
    assert.equal(adapter.system.getHttpBaseUrl(), 'http://127.0.0.1:8000');

    // Domain message goes to fallback WS
    assert.equal(adapter.send({ type: 'study_list_documents' }), true);
    assert.equal(lastSocket!.sentPayloads.length, 1);
    assert.equal(JSON.parse(lastSocket!.sentPayloads[0]).type, 'study_list_documents');

    // Native command goes to Tauri invoke
    const doc = await adapter.invoke<{ type: string }>({
      type: 'study_get_document',
      document_id: 'doc-native',
    });
    assert.equal(doc.type, 'study_document_details');
    assert.equal(lastSocket!.sentPayloads.length, 1);

    // Events from WS flow to unified subscribers
    lastSocket!.simulateServerJson({ type: 'system_status', cpu: 10, memory: 20 });
    assert.ok(receivedTypes.includes('study_document_details'));
    assert.ok(receivedTypes.includes('system_status'));

    adapter.dispose();
  });

  it('routes domain commands and native cancellation cleanly in pure Tauri IPC mode', async () => {
    const dispatchedTypes: string[] = [];
    const harness = createMockTauriHarness({
      onInvokeDispatch: (args, emit) => {
        const msg = args?.message as { type: string; request_id?: string };
        dispatchedTypes.push(msg.type);
        const eventTypeMap: Record<string, string> = {
          get_rules: 'rules_list',
          study_list_documents: 'study_documents_list',
          mission_list: 'mission_list_result',
          directive: 'state',
        };
        const replyType = eventTypeMap[msg.type] ?? 'system';
        emit({ type: replyType, request_id: msg.request_id });
        return null;
      },
    });

    const adapter = new TauriTransportAdapter({
      preferHybridFallback: false,
      tauriApis: harness.apis,
    });
    adapter.connect();
    await new Promise((resolve) => setTimeout(resolve, 20));

    const r1 = await adapter.invoke<{ type: string }>({ type: 'get_rules' });
    const r2 = await adapter.invoke<{ type: string }>({ type: 'study_list_documents' });
    const r3 = await adapter.invoke<{ type: string }>({ type: 'mission_list', project_id: 'ALL' } as never);
    const r4 = await adapter.invoke<{ type: string }>({ type: 'directive', prompt: 'status' } as never);

    assert.equal(r1.type, 'rules_list');
    assert.equal(r2.type, 'study_documents_list');
    assert.equal(r3.type, 'mission_list_result');
    assert.equal(r4.type, 'state');
    assert.deepEqual(dispatchedTypes, ['get_rules', 'study_list_documents', 'mission_list', 'directive']);

    const cancelled = await adapter.cancelNativeRequest('req-cancel-123', 'user_cancelled');
    assert.equal(cancelled, true);
    assert.ok(
      harness.invokedCommands.some(
        (c) => c.command === 'cancel_client_request' && c.args?.requestId === 'req-cancel-123'
      )
    );

    adapter.dispose();
  });
});
