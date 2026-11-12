import type { ClientMessage, ServerMessage } from '../protocol/websocket';
import {
  createTransportRequestId,
  getWindowHttpToken,
  getWindowNativeBridge,
  resolveTransportMediaUrl,
  buildMediaCandidateUrls,
  resolveDefaultHttpBaseUrl,
  type JarvisTransport,
} from './JarvisTransport.ts';
import {
  normalizeTransportTimeout,
  TransportError,
  WS_READY_STATE_CLOSED,
  WS_READY_STATE_CLOSING,
  WS_READY_STATE_CONNECTING,
  WS_READY_STATE_OPEN,
  type InvokeOptions,
  type NativeDesktopBridge,
  type OpenStreamOptions,
  type PendingRequestMeta,
  type ReconnectPolicy,
  type ResponseDecision,
  type StreamDecision,
  type TransportConnectionStatus,
  type TransportStatusSnapshot,
  type TransportStreamHandle,
  type TransportSystemCapabilities,
  type WebSocketLike,
} from './TransportTypes.ts';

export interface WebSocketTransportAdapterConfig {
  wsUrl?: string;
  wsToken?: string;
  httpBaseUrl?: string;
  getHttpToken?: () => string;
  reconnectPolicy?: Partial<ReconnectPolicy>;
  timeoutBounds?: { min?: number; max?: number };
  createWebSocket?: (url: string) => WebSocketLike;
  nativeBridge?: NativeDesktopBridge | null;
  normalizeMessage?: (raw: unknown) => ServerMessage | null;
  randomFn?: () => number;
  nowFn?: () => number;
  maxSettledHistory?: number;
}

interface PendingInvokeEntry<TResult> {
  meta: PendingRequestMeta;
  resolve: (value: TResult) => void;
  reject: (error: Error) => void;
  timer: ReturnType<typeof setTimeout>;
  abortCleanup?: () => void;
  rejectOnDisconnect: boolean;
  matchResponse: (message: ServerMessage, requestId: string) => ResponseDecision<TResult>;
  legacyMatchResponse?: (message: ServerMessage) => ResponseDecision<TResult>;
  cancelMessage?: ClientMessage | ((requestId: string) => ClientMessage);
}

interface ActiveStreamEntry<TChunk> {
  meta: PendingRequestMeta;
  onChunk: (chunk: TChunk) => void;
  resolveDone: () => void;
  rejectDone: (error: Error) => void;
  timer: ReturnType<typeof setTimeout>;
  timeoutMs: number;
  timeoutMessage: string;
  abortCleanup?: () => void;
  matchChunk: (message: ServerMessage, correlationId: string) => StreamDecision<TChunk>;
  legacyMatchChunk?: (message: ServerMessage) => StreamDecision<TChunk>;
  cancelMessage?: ClientMessage | ((correlationId: string) => ClientMessage);
  settled: boolean;
}

const DEFAULT_RECONNECT_POLICY: ReconnectPolicy = {
  initialDelayMs: 1000,
  maxDelayMs: 30000,
  multiplier: 2,
  jitterFactor: 0.25,
};

function defaultWebSocketFactory(url: string): WebSocketLike {
  if (typeof WebSocket === 'undefined') {
    throw new TransportError('UNKNOWN', 'Global WebSocket implementation is not available in this runtime');
  }
  return new WebSocket(url) as unknown as WebSocketLike;
}

function defaultNormalizeMessage(raw: unknown): ServerMessage | null {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    return null;
  }
  const rec = raw as Record<string, unknown>;
  if (typeof rec.type !== 'string' || rec.type.length === 0) {
    return null;
  }
  return rec as unknown as ServerMessage;
}

export class WebSocketTransportAdapter implements JarvisTransport {
  private readonly wsUrl: string;
  private readonly httpBaseUrl?: string;
  private readonly getHttpToken: () => string;
  private readonly reconnectPolicy: ReconnectPolicy;
  private readonly timeoutBounds?: { min?: number; max?: number };
  private readonly createWebSocket: (url: string) => WebSocketLike;
  private readonly nativeBridge: NativeDesktopBridge | null;
  private readonly normalizeMessage: (raw: unknown) => ServerMessage | null;
  private readonly randomFn: () => number;
  private readonly nowFn: () => number;
  private readonly maxSettledHistory: number;

  private socket: WebSocketLike | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private shouldReconnect = true;
  private disposed = false;
  private nativeUnsubscribe: (() => void) | null = null;

  private connectionStatus: TransportConnectionStatus = 'DISCONNECTED';
  private reconnectAttempt = 0;
  private lastConnectedAt: number | null = null;
  private lastDisconnectedAt: number | null = null;
  private lastError: string | null = null;

  private readonly pendingInvokes = new Map<string, PendingInvokeEntry<unknown>>();
  private readonly activeStreams = new Map<string, ActiveStreamEntry<unknown>>();
  private readonly settledRequestIds = new Map<string, number>();

  private readonly typeListeners = new Map<string, Set<(msg: ServerMessage, raw?: unknown) => void>>();
  private readonly anyListeners = new Set<(msg: ServerMessage, raw?: unknown) => void>();
  private readonly statusListeners = new Set<(snapshot: TransportStatusSnapshot) => void>();
  private readonly connectedListeners = new Set<() => void>();

  readonly system: TransportSystemCapabilities;

  constructor(config: WebSocketTransportAdapterConfig = {}) {
    const token =
      config.wsToken ??
      (typeof import.meta !== 'undefined' &&
      (import.meta as { env?: Record<string, string | undefined> }).env?.VITE_JARVIS_WS_TOKEN) ??
      'local-dev-token';
    this.wsUrl =
      config.wsUrl ??
      `ws://127.0.0.1:8001/?token=${encodeURIComponent(token || 'local-dev-token')}`;
    this.httpBaseUrl = config.httpBaseUrl;
    this.getHttpToken = config.getHttpToken ?? getWindowHttpToken;
    this.reconnectPolicy = {
      ...DEFAULT_RECONNECT_POLICY,
      ...(config.reconnectPolicy ?? {}),
    };
    this.timeoutBounds = config.timeoutBounds;
    this.createWebSocket = config.createWebSocket ?? defaultWebSocketFactory;
    this.nativeBridge = config.nativeBridge !== undefined ? config.nativeBridge : getWindowNativeBridge();
    this.normalizeMessage = config.normalizeMessage ?? defaultNormalizeMessage;
    this.randomFn = config.randomFn ?? Math.random;
    this.nowFn = config.nowFn ?? Date.now;
    this.maxSettledHistory = config.maxSettledHistory ?? 1000;

    this.system = {
      getStatus: () => this.getStatusSnapshot(),
      isReady: () => this.isReady(),
      isNativeDesktop: () => Boolean(this.nativeBridge?.isNativeIPC),
      connect: () => this.connect(),
      reconnect: () => this.reconnect(),
      disconnect: () => this.disconnect(),
      selectFolder: async () => {
        if (this.nativeBridge?.selectFolder) {
          return this.nativeBridge.selectFolder();
        }
        return null;
      },
      openPath: async (targetPath: string) => {
        if (this.nativeBridge?.openPath) {
          return this.nativeBridge.openPath(targetPath);
        }
        return null;
      },
      getPathForFile: (file: File) => {
        if (this.nativeBridge?.getPathForFile) {
          return this.nativeBridge.getPathForFile(file);
        }
        const fallbackFile = file as File & { path?: string };
        return typeof fallbackFile.path === 'string' ? fallbackFile.path : '';
      },
      getHttpBaseUrl: () => resolveDefaultHttpBaseUrl(this.httpBaseUrl),
      resolveMediaUrl: (pathOrUrl: string, mediaOpts?: { appendToken?: boolean }) =>
        resolveTransportMediaUrl(pathOrUrl, {
          baseUrl: this.httpBaseUrl,
          token: this.getHttpToken(),
          appendToken: mediaOpts?.appendToken,
        }),
      getMediaCandidateUrls: (relativePaths: string[], mediaOpts?: { appendToken?: boolean }) =>
        buildMediaCandidateUrls(relativePaths, {
          baseUrl: this.httpBaseUrl,
          token: this.getHttpToken(),
          appendToken: mediaOpts?.appendToken,
        }),
    };

    this.attachNativeIpcListener();
  }

  private attachNativeIpcListener(): void {
    if (!this.nativeBridge?.isNativeIPC || this.nativeUnsubscribe) {
      return;
    }
    this.nativeUnsubscribe = this.nativeBridge.onMessage((rawData) => {
      this.handleIncomingRawMessage(rawData);
    });
  }

  private getStatusSnapshot(): TransportStatusSnapshot {
    const wsOpen = this.socket?.readyState === WS_READY_STATE_OPEN;
    return {
      status: this.connectionStatus,
      backend: !wsOpen && this.nativeBridge?.isNativeIPC ? 'electron-ipc' : 'websocket',
      reconnectAttempt: this.reconnectAttempt,
      lastConnectedAt: this.lastConnectedAt,
      lastDisconnectedAt: this.lastDisconnectedAt,
      lastError: this.lastError,
      pendingRequests: this.pendingInvokes.size,
      activeStreams: this.activeStreams.size,
    };
  }

  private notifyStatusListeners(): void {
    const snapshot = this.getStatusSnapshot();
    for (const listener of Array.from(this.statusListeners)) {
      try {
        listener(snapshot);
      } catch (err) {
        console.error('[Transport] Error in status listener:', err);
      }
    }
  }

  private isReady(): boolean {
    return Boolean(
      !this.disposed &&
        (this.socket?.readyState === WS_READY_STATE_OPEN || this.nativeBridge?.isNativeIPC)
    );
  }

  connect(): void {
    if (this.disposed) {
      return;
    }
    this.attachNativeIpcListener();
    this.shouldReconnect = true;

    if (
      this.socket &&
      (this.socket.readyState === WS_READY_STATE_OPEN ||
        this.socket.readyState === WS_READY_STATE_CONNECTING)
    ) {
      return;
    }

    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    this.connectionStatus = this.reconnectAttempt > 0 ? 'RECONNECTING' : 'CONNECTING';
    this.notifyStatusListeners();

    let ws: WebSocketLike;
    try {
      ws = this.createWebSocket(this.wsUrl);
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : String(err);
      this.lastError = errorMsg;
      this.lastDisconnectedAt = this.nowFn();
      this.connectionStatus = this.shouldReconnect ? 'RECONNECTING' : 'OFFLINE';
      this.notifyStatusListeners();
      if (this.shouldReconnect) {
        this.scheduleReconnect();
      }
      return;
    }

    this.socket = ws;

    ws.onopen = () => {
      if (this.disposed || this.socket !== ws) {
        if (ws.readyState === WS_READY_STATE_OPEN) {
          ws.close();
        }
        return;
      }
      if (this.reconnectTimer !== null) {
        clearTimeout(this.reconnectTimer);
        this.reconnectTimer = null;
      }
      this.reconnectAttempt = 0;
      this.lastConnectedAt = this.nowFn();
      this.lastError = null;
      this.connectionStatus = 'CONNECTED';
      this.notifyStatusListeners();

      for (const listener of Array.from(this.connectedListeners)) {
        try {
          listener();
        } catch (err) {
          console.error('[Transport] Error in onConnected listener:', err);
        }
      }
    };

    ws.onclose = (event) => {
      const isCurrentSocket = this.socket === ws;
      if (isCurrentSocket) {
        this.socket = null;
      }
      if (this.disposed) {
        return;
      }
      if (!isCurrentSocket) {
        return;
      }

      this.lastDisconnectedAt = this.nowFn();
      const closeReason = event?.reason ? ` (${event.reason})` : '';
      if (event?.code && event.code !== 1000) {
        this.lastError = `Socket closed with code ${event.code}${closeReason}`;
      }

      if (!this.nativeBridge?.isNativeIPC) {
        this.rejectDisconnectedRequests(
          new TransportError(
            'DISCONNECTED',
            `Ligação de transporte interrompida${closeReason || '.'}`
          )
        );
      }

      this.connectionStatus = this.shouldReconnect ? 'RECONNECTING' : 'OFFLINE';
      this.notifyStatusListeners();

      if (this.shouldReconnect) {
        this.scheduleReconnect();
      }
    };

    ws.onerror = (err) => {
      if (this.socket !== ws) {
        return;
      }
      this.lastError = err instanceof Error ? err.message : 'WebSocket transport error';
      this.notifyStatusListeners();
    };

    ws.onmessage = (event) => {
      if (this.socket !== ws || this.disposed) {
        return;
      }
      this.handleIncomingRawMessage(event.data);
    };
  }

  reconnect(): void {
    if (this.disposed) {
      return;
    }
    this.reconnectAttempt = 0;
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    const prevSocket = this.socket;
    this.socket = null;
    if (
      prevSocket &&
      prevSocket.readyState !== WS_READY_STATE_CLOSED &&
      prevSocket.readyState !== WS_READY_STATE_CLOSING
    ) {
      try {
        prevSocket.close(1000, 'manual reconnect');
      } catch {
        // Ignore close errors during reconnect
      }
    }
    this.connect();
  }

  disconnect(): void {
    this.shouldReconnect = false;
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    const prevSocket = this.socket;
    this.socket = null;
    if (
      prevSocket &&
      prevSocket.readyState !== WS_READY_STATE_CLOSED &&
      prevSocket.readyState !== WS_READY_STATE_CLOSING
    ) {
      try {
        prevSocket.close(1000, 'client disconnect');
      } catch {
        // Ignore close errors
      }
    }
    this.rejectAllPending(new TransportError('DISCONNECTED', 'Transporte desligado pelo cliente.'));
    this.connectionStatus = 'OFFLINE';
    this.lastDisconnectedAt = this.nowFn();
    this.notifyStatusListeners();
  }

  dispose(): void {
    if (this.disposed) {
      return;
    }
    this.disposed = true;
    this.shouldReconnect = false;

    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    const prevSocket = this.socket;
    this.socket = null;
    if (
      prevSocket &&
      prevSocket.readyState !== WS_READY_STATE_CLOSED &&
      prevSocket.readyState !== WS_READY_STATE_CLOSING
    ) {
      try {
        prevSocket.close(1000, 'transport disposed');
      } catch {
        // Ignore close errors
      }
    }

    if (this.nativeUnsubscribe) {
      try {
        this.nativeUnsubscribe();
      } catch {
        // Ignore unsubscribe error
      }
      this.nativeUnsubscribe = null;
    }

    this.rejectAllPending(new TransportError('TRANSPORT_CLOSED', 'Transporte encerrado.'));
    this.typeListeners.clear();
    this.anyListeners.clear();
    this.connectedListeners.clear();
    this.connectionStatus = 'OFFLINE';
    this.notifyStatusListeners();
    this.statusListeners.clear();
  }

  send(message: ClientMessage): boolean {
    if (this.disposed) {
      return false;
    }
    if (this.socket?.readyState === WS_READY_STATE_OPEN) {
      try {
        this.socket.send(JSON.stringify(message));
        return true;
      } catch (err) {
        this.lastError = err instanceof Error ? err.message : 'Serialization failure';
        return false;
      }
    }
    if (this.nativeBridge?.isNativeIPC) {
      try {
        this.nativeBridge.send(message);
        return true;
      } catch (err) {
        this.lastError = err instanceof Error ? err.message : 'Native IPC send failure';
        return false;
      }
    }
    return false;
  }

  invoke<TResult = ServerMessage>(
    message: ClientMessage,
    options: InvokeOptions<TResult> = {}
  ): Promise<TResult> {
    if (this.disposed) {
      return Promise.reject(
        new TransportError('TRANSPORT_CLOSED', 'Não é possível invocar após dispose do transporte.')
      );
    }

    const requestId =
      options.requestId ??
      (typeof (message as { request_id?: unknown }).request_id === 'string' &&
      (message as { request_id: string }).request_id.length > 0
        ? (message as { request_id: string }).request_id
        : createTransportRequestId(message.type));

    if (this.pendingInvokes.has(requestId) || this.activeStreams.has(requestId)) {
      return Promise.reject(
        new TransportError(
          'DUPLICATE_REQUEST_ID',
          `Request ID duplicado ainda em curso: ${requestId}`,
          { requestId }
        )
      );
    }

    if (options.signal?.aborted) {
      return Promise.reject(
        new TransportError('ABORTED', `Pedido ${requestId} cancelado antes do envio.`, {
          requestId,
          cause: options.signal.reason,
        })
      );
    }

    const requireReady = options.requireReady ?? true;
    if (requireReady && !this.isReady()) {
      return Promise.reject(
        new TransportError('DISCONNECTED', 'Transporte não está ligado para executar pedido.', {
          requestId,
        })
      );
    }

    const timeoutMs = normalizeTransportTimeout(options.timeoutMs, this.timeoutBounds);
    const attachRequestId = options.attachRequestId ?? true;
    const outboundMessage = (
      attachRequestId ? { ...message, request_id: requestId } : message
    ) as ClientMessage;

    const matchResponse =
      options.matchResponse ??
      ((msg: ServerMessage): ResponseDecision<TResult> => ({
        kind: 'resolve',
        value: msg as unknown as TResult,
      }));

    return new Promise<TResult>((resolve, reject) => {
      const cleanupEntry = (): PendingInvokeEntry<unknown> | null => {
        const entry = this.pendingInvokes.get(requestId);
        if (!entry) {
          return null;
        }
        this.pendingInvokes.delete(requestId);
        clearTimeout(entry.timer);
        if (entry.abortCleanup) {
          entry.abortCleanup();
        }
        this.markSettled(requestId);
        this.notifyStatusListeners();
        return entry;
      };

      const timer = setTimeout(() => {
        const entry = cleanupEntry();
        if (!entry) return;
        const msg =
          options.timeoutMessage ??
          `Tempo limite excedido (${timeoutMs}ms) para ${outboundMessage.type}.`;
        reject(new TransportError('TIMEOUT', msg, { requestId }));
      }, timeoutMs);

      let abortCleanup: (() => void) | undefined;
      if (options.signal) {
        const onAbort = () => {
          const entry = cleanupEntry();
          if (!entry) return;
          if (entry.cancelMessage) {
            const cancelPayload =
              typeof entry.cancelMessage === 'function'
                ? entry.cancelMessage(requestId)
                : entry.cancelMessage;
            this.send(cancelPayload);
          }
          reject(
            new TransportError('ABORTED', `Pedido ${requestId} cancelado.`, {
              requestId,
              cause: options.signal?.reason,
            })
          );
        };
        options.signal.addEventListener('abort', onAbort, { once: true });
        abortCleanup = () => options.signal?.removeEventListener('abort', onAbort);
      }

      const entry: PendingInvokeEntry<unknown> = {
        meta: {
          requestId,
          messageType: outboundMessage.type,
          tag: options.tag,
          startedAt: this.nowFn(),
        },
        resolve: (value: unknown) => resolve(value as TResult),
        reject,
        timer,
        abortCleanup,
        rejectOnDisconnect: options.rejectOnDisconnect ?? true,
        matchResponse: (msg, reqId) => matchResponse(msg, reqId) as ResponseDecision<unknown>,
        legacyMatchResponse: options.legacyMatchResponse
          ? (msg) => options.legacyMatchResponse!(msg) as ResponseDecision<unknown>
          : undefined,
        cancelMessage: options.cancelMessage,
      };

      this.pendingInvokes.set(requestId, entry);
      this.notifyStatusListeners();

      const sent = this.send(outboundMessage);
      if (!sent && requireReady) {
        cleanupEntry();
        reject(
          new TransportError('DISCONNECTED', `Falha ao enviar pedido ${outboundMessage.type}.`, {
            requestId,
          })
        );
      }
    });
  }

  openStream<TChunk = ServerMessage>(
    message: ClientMessage,
    options: OpenStreamOptions<TChunk>,
    onChunk: (chunk: TChunk) => void
  ): TransportStreamHandle {
    const requestId =
      options.correlationId ??
      (typeof (message as { request_id?: unknown }).request_id === 'string' &&
      (message as { request_id: string }).request_id.length > 0
        ? (message as { request_id: string }).request_id
        : createTransportRequestId(`stream_${message.type}`));

    if (this.disposed) {
      return {
        requestId,
        done: Promise.reject(
          new TransportError('TRANSPORT_CLOSED', 'Não é possível abrir stream após dispose.')
        ),
        cancel: () => {},
      };
    }

    if (this.pendingInvokes.has(requestId) || this.activeStreams.has(requestId)) {
      return {
        requestId,
        done: Promise.reject(
          new TransportError('DUPLICATE_REQUEST_ID', `Correlation ID duplicado em curso: ${requestId}`, {
            requestId,
          })
        ),
        cancel: () => {},
      };
    }

    if (options.signal?.aborted) {
      return {
        requestId,
        done: Promise.reject(
          new TransportError('ABORTED', `Stream ${requestId} cancelado antes de iniciar.`, {
            requestId,
            cause: options.signal.reason,
          })
        ),
        cancel: () => {},
      };
    }

    const requireReady = options.requireReady ?? true;
    if (requireReady && !this.isReady()) {
      return {
        requestId,
        done: Promise.reject(
          new TransportError('DISCONNECTED', 'Transporte não está ligado para abrir stream.', {
            requestId,
          })
        ),
        cancel: () => {},
      };
    }

    const timeoutMs = normalizeTransportTimeout(options.timeoutMs, this.timeoutBounds);
    const timeoutMessage =
      options.timeoutMessage ?? `Tempo limite de stream excedido (${timeoutMs}ms) para ${message.type}.`;
    const attachRequestId = options.attachRequestId ?? true;
    const outboundMessage = (
      attachRequestId ? { ...message, request_id: requestId } : message
    ) as ClientMessage;

    let cancelStream: (reason?: string) => void = () => {};

    const done = new Promise<void>((resolveDone, rejectDone) => {
      const cleanupStream = (): ActiveStreamEntry<unknown> | null => {
        const entry = this.activeStreams.get(requestId);
        if (!entry || entry.settled) {
          return null;
        }
        entry.settled = true;
        this.activeStreams.delete(requestId);
        clearTimeout(entry.timer);
        if (entry.abortCleanup) {
          entry.abortCleanup();
        }
        this.markSettled(requestId);
        this.notifyStatusListeners();
        return entry;
      };

      const startTimer = () =>
        setTimeout(() => {
          const entry = cleanupStream();
          if (!entry) return;
          if (entry.cancelMessage) {
            const cancelPayload =
              typeof entry.cancelMessage === 'function'
                ? entry.cancelMessage(requestId)
                : entry.cancelMessage;
            this.send(cancelPayload);
          }
          rejectDone(new TransportError('TIMEOUT', timeoutMessage, { requestId }));
        }, timeoutMs);

      const handleCancel = (reason?: string, cause?: unknown) => {
        const entry = cleanupStream();
        if (!entry) return;
        if (entry.cancelMessage) {
          const cancelPayload =
            typeof entry.cancelMessage === 'function'
              ? entry.cancelMessage(requestId)
              : entry.cancelMessage;
          this.send(cancelPayload);
        }
        rejectDone(
          new TransportError('ABORTED', reason || `Stream ${requestId} cancelado.`, {
            requestId,
            cause,
          })
        );
      };

      cancelStream = (reason?: string) => handleCancel(reason);

      let abortCleanup: (() => void) | undefined;
      if (options.signal) {
        const onAbort = () => handleCancel(`Stream ${requestId} cancelado via AbortSignal.`, options.signal?.reason);
        options.signal.addEventListener('abort', onAbort, { once: true });
        abortCleanup = () => options.signal?.removeEventListener('abort', onAbort);
      }

      const entry: ActiveStreamEntry<unknown> = {
        meta: {
          requestId,
          messageType: outboundMessage.type,
          tag: options.tag,
          startedAt: this.nowFn(),
        },
        onChunk: (chunk: unknown) => onChunk(chunk as TChunk),
        resolveDone: () => {
          if (cleanupStream()) {
            resolveDone();
          }
        },
        rejectDone: (err: Error) => {
          if (cleanupStream()) {
            rejectDone(err);
          }
        },
        timer: startTimer(),
        timeoutMs,
        timeoutMessage,
        abortCleanup,
        matchChunk: (msg, corrId) => options.matchChunk(msg, corrId) as StreamDecision<unknown>,
        legacyMatchChunk: options.legacyMatchChunk
          ? (msg) => options.legacyMatchChunk!(msg) as StreamDecision<unknown>
          : undefined,
        cancelMessage: options.cancelMessage,
        settled: false,
      };

      this.activeStreams.set(requestId, entry);
      this.notifyStatusListeners();

      const sent = this.send(outboundMessage);
      if (!sent && requireReady) {
        if (cleanupStream()) {
          rejectDone(
            new TransportError('DISCONNECTED', `Falha ao iniciar stream ${outboundMessage.type}.`, {
              requestId,
            })
          );
        }
      }
    });

    return {
      requestId,
      done,
      cancel: cancelStream,
    };
  }

  subscribe<TType extends ServerMessage['type']>(
    eventType: TType,
    handler: (message: Extract<ServerMessage, { type: TType }>, raw?: unknown) => void
  ): () => void {
    if (this.disposed) {
      return () => {};
    }
    let set = this.typeListeners.get(eventType);
    if (!set) {
      set = new Set();
      this.typeListeners.set(eventType, set);
    }
    const wrapped = handler as (msg: ServerMessage, raw?: unknown) => void;
    set.add(wrapped);
    return () => {
      const current = this.typeListeners.get(eventType);
      if (!current) return;
      current.delete(wrapped);
      if (current.size === 0) {
        this.typeListeners.delete(eventType);
      }
    };
  }

  subscribeAny(handler: (message: ServerMessage, raw?: unknown) => void): () => void {
    if (this.disposed) {
      return () => {};
    }
    this.anyListeners.add(handler);
    return () => {
      this.anyListeners.delete(handler);
    };
  }

  subscribeConnectionState(handler: (snapshot: TransportStatusSnapshot) => void): () => void {
    if (this.disposed) {
      return () => {};
    }
    this.statusListeners.add(handler);
    try {
      handler(this.getStatusSnapshot());
    } catch (err) {
      console.error('[Transport] Error in initial connection state callback:', err);
    }
    return () => {
      this.statusListeners.delete(handler);
    };
  }

  onConnected(handler: () => void): () => void {
    if (this.disposed) {
      return () => {};
    }
    this.connectedListeners.add(handler);
    return () => {
      this.connectedListeners.delete(handler);
    };
  }

  cancelPendingRequests(predicate: (meta: PendingRequestMeta) => boolean, reason = 'Cancelado pelo utilizador'): number {
    let cancelledCount = 0;

    for (const [reqId, entry] of Array.from(this.pendingInvokes.entries())) {
      if (predicate(entry.meta)) {
        this.pendingInvokes.delete(reqId);
        clearTimeout(entry.timer);
        if (entry.abortCleanup) {
          entry.abortCleanup();
        }
        this.markSettled(reqId);
        entry.reject(new TransportError('ABORTED', reason, { requestId: reqId }));
        cancelledCount += 1;
      }
    }

    for (const [corrId, stream] of Array.from(this.activeStreams.entries())) {
      if (predicate(stream.meta)) {
        stream.rejectDone(new TransportError('ABORTED', reason, { requestId: corrId }));
        cancelledCount += 1;
      }
    }

    if (cancelledCount > 0) {
      this.notifyStatusListeners();
    }
    return cancelledCount;
  }

  computeNextReconnectDelayMs(attempt = this.reconnectAttempt): number {
    const base = Math.min(
      this.reconnectPolicy.maxDelayMs,
      this.reconnectPolicy.initialDelayMs * Math.pow(this.reconnectPolicy.multiplier, attempt)
    );
    const jitter = base * this.reconnectPolicy.jitterFactor * (this.randomFn() * 2 - 1);
    return Math.max(0, Math.round(base + jitter));
  }

  private scheduleReconnect(): void {
    if (this.disposed || !this.shouldReconnect) {
      return;
    }
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    const delayMs = this.computeNextReconnectDelayMs(this.reconnectAttempt);
    this.reconnectAttempt += 1;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      if (!this.disposed && this.shouldReconnect) {
        this.connect();
      }
    }, delayMs);
  }

  private markSettled(requestId: string): void {
    this.settledRequestIds.set(requestId, this.nowFn());
    while (this.settledRequestIds.size > this.maxSettledHistory) {
      const oldestKey = this.settledRequestIds.keys().next().value;
      if (oldestKey === undefined) break;
      this.settledRequestIds.delete(oldestKey);
    }
  }

  private rejectDisconnectedRequests(error: TransportError): void {
    let changed = false;
    for (const [reqId, entry] of Array.from(this.pendingInvokes.entries())) {
      if (entry.rejectOnDisconnect) {
        this.pendingInvokes.delete(reqId);
        clearTimeout(entry.timer);
        if (entry.abortCleanup) {
          entry.abortCleanup();
        }
        this.markSettled(reqId);
        entry.reject(error);
        changed = true;
      }
    }
    for (const stream of Array.from(this.activeStreams.values())) {
      stream.rejectDone(error);
      changed = true;
    }
    if (changed) {
      this.notifyStatusListeners();
    }
  }

  private rejectAllPending(error: TransportError): void {
    const hadPending = this.pendingInvokes.size > 0 || this.activeStreams.size > 0;
    for (const [reqId, entry] of Array.from(this.pendingInvokes.entries())) {
      this.pendingInvokes.delete(reqId);
      clearTimeout(entry.timer);
      if (entry.abortCleanup) {
        entry.abortCleanup();
      }
      this.markSettled(reqId);
      entry.reject(error);
    }
    for (const stream of Array.from(this.activeStreams.values())) {
      stream.rejectDone(error);
    }
    if (hadPending) {
      this.notifyStatusListeners();
    }
  }

  private settlePendingInvoke<TResult>(
    requestId: string,
    entry: PendingInvokeEntry<TResult>,
    decision: ResponseDecision<TResult>
  ): boolean {
    if (decision.kind === 'ignore') {
      return false;
    }
    this.pendingInvokes.delete(requestId);
    clearTimeout(entry.timer);
    if (entry.abortCleanup) {
      entry.abortCleanup();
    }
    this.markSettled(requestId);
    this.notifyStatusListeners();

    if (decision.kind === 'resolve') {
      entry.resolve(decision.value);
    } else {
      entry.reject(decision.error);
    }
    return true;
  }

  private applyStreamDecision<TChunk>(
    stream: ActiveStreamEntry<TChunk>,
    decision: StreamDecision<TChunk>
  ): boolean {
    if (decision.kind === 'ignore' || stream.settled) {
      return false;
    }

    if (decision.kind === 'chunk') {
      clearTimeout(stream.timer);
      stream.timer = setTimeout(() => {
        if (!stream.settled) {
          if (stream.cancelMessage) {
            const payload =
              typeof stream.cancelMessage === 'function'
                ? stream.cancelMessage(stream.meta.requestId)
                : stream.cancelMessage;
            this.send(payload);
          }
          stream.rejectDone(
            new TransportError('TIMEOUT', stream.timeoutMessage, { requestId: stream.meta.requestId })
          );
        }
      }, stream.timeoutMs);

      try {
        stream.onChunk(decision.chunk);
      } catch (err) {
        stream.rejectDone(err instanceof Error ? err : new Error(String(err)));
        return true;
      }

      if (decision.done) {
        stream.resolveDone();
      }
      return true;
    }

    if (decision.kind === 'complete') {
      if (decision.chunk !== undefined) {
        try {
          stream.onChunk(decision.chunk);
        } catch (err) {
          stream.rejectDone(err instanceof Error ? err : new Error(String(err)));
          return true;
        }
      }
      stream.resolveDone();
      return true;
    }

    stream.rejectDone(decision.error);
    return true;
  }

  private handleIncomingRawMessage(rawData: unknown): void {
    if (this.disposed) {
      return;
    }

    let parsed: unknown = rawData;
    if (typeof rawData === 'string') {
      try {
        parsed = JSON.parse(rawData);
      } catch (err) {
        console.warn('[Transport] Ignored invalid JSON message:', err);
        return;
      }
    }

    const rawRecord =
      parsed && typeof parsed === 'object' && !Array.isArray(parsed)
        ? (parsed as Record<string, unknown>)
        : null;
    const rawRequestId =
      rawRecord && typeof rawRecord.request_id === 'string' && rawRecord.request_id.length > 0
        ? rawRecord.request_id
        : undefined;

    const msg = this.normalizeMessage(parsed);
    if (!msg) {
      console.warn('[Transport] Ignored malformed message');
      return;
    }

    const msgReqId = (msg as { request_id?: unknown }).request_id;
    const effectiveRequestId =
      rawRequestId ?? (typeof msgReqId === 'string' && msgReqId.length > 0 ? msgReqId : undefined);

    if (effectiveRequestId) {
      if (!this.settledRequestIds.has(effectiveRequestId)) {
        const invokeEntry = this.pendingInvokes.get(effectiveRequestId);
        if (invokeEntry) {
          const decision = invokeEntry.matchResponse(msg, effectiveRequestId);
          this.settlePendingInvoke(effectiveRequestId, invokeEntry, decision);
        } else {
          const streamEntry = this.activeStreams.get(effectiveRequestId);
          if (streamEntry) {
            const decision = streamEntry.matchChunk(msg, effectiveRequestId);
            this.applyStreamDecision(streamEntry, decision);
          }
        }
      }
      // Guard: tagged request_id messages must NEVER fall through to legacy untagged matching
    } else {
      for (const [reqId, entry] of Array.from(this.pendingInvokes.entries())) {
        if (!entry.legacyMatchResponse) continue;
        const decision = entry.legacyMatchResponse(msg);
        if (this.settlePendingInvoke(reqId, entry, decision)) {
          break;
        }
      }
      for (const stream of Array.from(this.activeStreams.values())) {
        if (!stream.legacyMatchChunk || stream.settled) continue;
        const decision = stream.legacyMatchChunk(msg);
        if (this.applyStreamDecision(stream, decision)) {
          break;
        }
      }
    }

    const typedHandlers = this.typeListeners.get(msg.type);
    if (typedHandlers) {
      for (const handler of Array.from(typedHandlers)) {
        try {
          handler(msg, parsed);
        } catch (err) {
          console.error(`[Transport] Error in subscriber for '${msg.type}':`, err);
        }
      }
    }

    for (const handler of Array.from(this.anyListeners)) {
      try {
        handler(msg, parsed);
      } catch (err) {
        console.error('[Transport] Error in subscribeAny listener:', err);
      }
    }
  }
}
