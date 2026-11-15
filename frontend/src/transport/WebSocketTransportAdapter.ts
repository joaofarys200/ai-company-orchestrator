import type { ClientMessage, ServerMessage } from '../protocol/websocket';
import {
  buildMediaCandidateUrls,
  getWindowHttpToken,
  getWindowNativeBridge,
  resolveDefaultHttpBaseUrl,
  resolveTransportMediaUrl,
  type JarvisTransport,
} from './JarvisTransport.ts';
import { TransportCorrelationRegistry } from './TransportCorrelation.ts';
import {
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
  private readonly createWebSocket: (url: string) => WebSocketLike;
  private readonly nativeBridge: NativeDesktopBridge | null;
  private readonly normalizeMessage: (raw: unknown) => ServerMessage | null;
  private readonly randomFn: () => number;
  private readonly nowFn: () => number;
  private readonly correlation: TransportCorrelationRegistry;

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
    this.createWebSocket = config.createWebSocket ?? defaultWebSocketFactory;
    this.nativeBridge = config.nativeBridge !== undefined ? config.nativeBridge : getWindowNativeBridge();
    this.normalizeMessage = config.normalizeMessage ?? defaultNormalizeMessage;
    this.randomFn = config.randomFn ?? Math.random;
    this.nowFn = config.nowFn ?? Date.now;
    this.correlation = new TransportCorrelationRegistry({
      nowFn: this.nowFn,
      maxSettledHistory: config.maxSettledHistory ?? 1000,
      timeoutBounds: config.timeoutBounds,
      sendCancel: (cancelMsg) => this.send(cancelMsg),
      onPendingChanged: () => this.notifyStatusListeners(),
    });

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
      pendingRequests: this.correlation.pendingCount,
      activeStreams: this.correlation.activeStreamCount,
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
        this.correlation.rejectDisconnected(
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
    this.correlation.rejectAll(new TransportError('DISCONNECTED', 'Transporte desligado pelo cliente.'));
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

    this.correlation.rejectAll(new TransportError('TRANSPORT_CLOSED', 'Transporte encerrado.'));
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
    const requireReady = options.requireReady ?? true;
    return this.correlation.runInvoke(
      message,
      options,
      {
        isDisposed: this.disposed,
        isReady: this.isReady(),
        disconnectedMessage: 'Transporte não está ligado para executar pedido.',
      },
      (outboundMessage, requestId, rejectEarly) => {
        const sent = this.send(outboundMessage);
        if (!sent && requireReady) {
          rejectEarly(
            new TransportError('DISCONNECTED', `Falha ao enviar pedido ${outboundMessage.type}.`, {
              requestId,
            })
          );
        }
      }
    );
  }

  openStream<TChunk = ServerMessage>(
    message: ClientMessage,
    options: OpenStreamOptions<TChunk>,
    onChunk: (chunk: TChunk) => void
  ): TransportStreamHandle {
    const requireReady = options.requireReady ?? true;
    return this.correlation.openStream(
      message,
      options,
      onChunk,
      {
        isDisposed: this.disposed,
        isReady: this.isReady(),
        disconnectedMessage: 'Transporte não está ligado para abrir stream.',
      },
      (outboundMessage, requestId, rejectEarly) => {
        const sent = this.send(outboundMessage);
        if (!sent && requireReady) {
          rejectEarly(
            new TransportError('DISCONNECTED', `Falha ao iniciar stream ${outboundMessage.type}.`, {
              requestId,
            })
          );
        }
      }
    );
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
    return this.correlation.cancelWhere(predicate, reason);
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

    this.correlation.handleMessage(msg, effectiveRequestId);

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
