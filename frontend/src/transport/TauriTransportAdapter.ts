import type { ClientMessage, ServerMessage } from '../protocol/websocket';
import {
  buildMediaCandidateUrls,
  getWindowHttpToken,
  isTauriRuntime,
  resolveDefaultHttpBaseUrl,
  resolveTransportMediaUrl,
  type JarvisTransport,
} from './JarvisTransport.ts';
import { TransportCorrelationRegistry } from './TransportCorrelation.ts';
import {
  TransportError,
  type InvokeOptions,
  type OpenStreamOptions,
  type PendingRequestMeta,
  type ReconnectPolicy,
  type TauriLoopbackConfig,
  type TauriMediaTicket,
  type TauriPingResult,
  type TauriSelectFileOptions,
  type TransportConnectionStatus,
  type TransportStatusSnapshot,
  type TransportStreamHandle,
  type TransportSystemCapabilities,
  type WebSocketLike,
} from './TransportTypes.ts';
import { WebSocketTransportAdapter } from './WebSocketTransportAdapter.ts';

export type TauriDragDropEventPayload =
  | { type: 'enter'; paths: string[] }
  | { type: 'over' }
  | { type: 'drop'; paths: string[] }
  | { type: 'leave' };

export interface TauriRuntimeApis {
  isTauri?: () => boolean;
  invoke: <T = unknown>(command: string, args?: Record<string, unknown>) => Promise<T>;
  listen?: <T = unknown>(
    eventName: string,
    handler: (event: { event?: string; payload: T }) => void
  ) => Promise<() => void>;
  openDialog?: (options: Record<string, unknown>) => Promise<string | string[] | null>;
  onDragDropEvent?: (
    handler: (payload: TauriDragDropEventPayload) => void
  ) => Promise<() => void>;
}

export interface TauriTransportAdapterConfig {
  preferHybridFallback?: boolean;
  nativeRpcCommands?: Iterable<string>;
  ipcDispatchCommand?: string;
  ipcEventName?: string;
  tauriApis?: TauriRuntimeApis;
  wsUrl?: string;
  wsToken?: string;
  httpBaseUrl?: string;
  getHttpToken?: () => string;
  reconnectPolicy?: Partial<ReconnectPolicy>;
  timeoutBounds?: { min?: number; max?: number };
  createWebSocket?: (url: string) => WebSocketLike;
  normalizeMessage?: (raw: unknown) => ServerMessage | null;
  randomFn?: () => number;
  nowFn?: () => number;
  maxSettledHistory?: number;
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

function createDefaultTauriApis(): TauriRuntimeApis {
  return {
    isTauri: () => isTauriRuntime(),
    invoke: async <T = unknown>(command: string, args?: Record<string, unknown>): Promise<T> => {
      const mod = await import('@tauri-apps/api/core');
      return mod.invoke<T>(command, args);
    },
    listen: async <T = unknown>(
      eventName: string,
      handler: (event: { event?: string; payload: T }) => void
    ): Promise<() => void> => {
      const mod = await import('@tauri-apps/api/event');
      return mod.listen<T>(eventName, (event) => {
        handler({ event: event.event, payload: event.payload });
      });
    },
    openDialog: async (options: Record<string, unknown>): Promise<string | string[] | null> => {
      const mod = await import('@tauri-apps/plugin-dialog');
      const result = await mod.open(options as never);
      if (typeof result === 'string' || Array.isArray(result)) {
        return result;
      }
      return null;
    },
    onDragDropEvent: async (
      handler: (payload: TauriDragDropEventPayload) => void
    ): Promise<() => void> => {
      const mod = await import('@tauri-apps/api/webview');
      const webview = mod.getCurrentWebview();
      return webview.onDragDropEvent((event) => {
        const payload = event.payload;
        if (payload.type === 'enter' || payload.type === 'drop') {
          handler({ type: payload.type, paths: payload.paths });
        } else if (payload.type === 'over' || payload.type === 'leave') {
          handler({ type: payload.type });
        }
      });
    },
  };
}

function extractBasename(filePath: string): string {
  const normalized = filePath.replace(/\\/g, '/');
  const idx = normalized.lastIndexOf('/');
  return idx >= 0 ? normalized.slice(idx + 1) : normalized;
}

function attachQueryParam(url: string, key: string, value: string): string {
  if (!url || !value) {
    return url;
  }
  const encodedKey = encodeURIComponent(key);
  const encodedVal = encodeURIComponent(value);
  const hashIdx = url.indexOf('#');
  const base = hashIdx >= 0 ? url.slice(0, hashIdx) : url;
  const hash = hashIdx >= 0 ? url.slice(hashIdx) : '';
  const queryPattern = new RegExp(`([?&])${encodedKey}=[^&]*`);
  if (queryPattern.test(base)) {
    return base.replace(queryPattern, `$1${encodedKey}=${encodedVal}`) + hash;
  }
  const sep = base.includes('?') ? '&' : '?';
  return `${base}${sep}${encodedKey}=${encodedVal}${hash}`;
}

export class TauriTransportAdapter implements JarvisTransport {
  private readonly apis: TauriRuntimeApis;
  private readonly preferHybridFallback: boolean;
  private readonly nativeRpcCommands: Set<string>;
  private readonly ipcDispatchCommand: string;
  private readonly ipcEventName: string;
  private readonly httpBaseUrlOverride?: string;
  private readonly getHttpToken: () => string;
  private readonly normalizeMessage: (raw: unknown) => ServerMessage | null;
  private readonly nowFn: () => number;
  private readonly fallbackWs: WebSocketTransportAdapter | null;
  private readonly correlation: TransportCorrelationRegistry;

  private disposed = false;
  private nativeReady = false;
  private connectInFlight = false;
  private connectionStatus: TransportConnectionStatus = 'DISCONNECTED';
  private lastConnectedAt: number | null = null;
  private lastDisconnectedAt: number | null = null;
  private lastError: string | null = null;
  private loopbackConfig: TauriLoopbackConfig | null = null;

  private ipcEventUnlisten: (() => void) | null = null;
  private dragDropUnlisten: (() => void) | null = null;
  private fallbackStatusUnsub: (() => void) | null = null;
  private fallbackConnectedUnsub: (() => void) | null = null;
  private fallbackAnyUnsub: (() => void) | null = null;

  private readonly droppedPathsByName = new Map<string, string>();
  private lastDroppedPaths: string[] = [];
  private readonly fileDropListeners = new Set<(paths: string[]) => void>();
  private readonly ticketCache = new Map<string, { ticket: string; expiresAtMs: number }>();

  private readonly typeListeners = new Map<string, Set<(msg: ServerMessage, raw?: unknown) => void>>();
  private readonly anyListeners = new Set<(msg: ServerMessage, raw?: unknown) => void>();
  private readonly statusListeners = new Set<(snapshot: TransportStatusSnapshot) => void>();
  private readonly connectedListeners = new Set<() => void>();

  readonly system: TransportSystemCapabilities;

  constructor(config: TauriTransportAdapterConfig = {}) {
    this.apis = config.tauriApis ?? createDefaultTauriApis();
    this.preferHybridFallback = config.preferHybridFallback ?? true;
    this.nativeRpcCommands = new Set(config.nativeRpcCommands ?? []);
    this.ipcDispatchCommand = config.ipcDispatchCommand ?? 'dispatch_client_message';
    this.ipcEventName = config.ipcEventName ?? 'jarvis:event';
    this.httpBaseUrlOverride = config.httpBaseUrl;
    this.getHttpToken = config.getHttpToken ?? getWindowHttpToken;
    this.normalizeMessage = config.normalizeMessage ?? defaultNormalizeMessage;
    this.nowFn = config.nowFn ?? Date.now;

    this.correlation = new TransportCorrelationRegistry({
      nowFn: this.nowFn,
      maxSettledHistory: config.maxSettledHistory ?? 1000,
      timeoutBounds: config.timeoutBounds,
      sendCancel: (cancelMsg) => this.send(cancelMsg),
      onPendingChanged: () => this.notifyStatusListeners(),
    });

    if (this.preferHybridFallback) {
      this.fallbackWs = new WebSocketTransportAdapter({
        wsUrl: config.wsUrl,
        wsToken: config.wsToken,
        httpBaseUrl: config.httpBaseUrl,
        getHttpToken: config.getHttpToken,
        reconnectPolicy: config.reconnectPolicy,
        timeoutBounds: config.timeoutBounds,
        createWebSocket: config.createWebSocket,
        nativeBridge: null,
        normalizeMessage: config.normalizeMessage,
        randomFn: config.randomFn,
        nowFn: config.nowFn,
        maxSettledHistory: config.maxSettledHistory,
      });
      this.fallbackStatusUnsub = this.fallbackWs.subscribeConnectionState(() => {
        this.notifyStatusListeners();
      });
      this.fallbackConnectedUnsub = this.fallbackWs.onConnected(() => {
        this.lastConnectedAt = this.nowFn();
        this.fireConnectedListeners();
      });
      this.fallbackAnyUnsub = this.fallbackWs.subscribeAny((msg, raw) => {
        this.dispatchMessageToSubscribers(msg, raw);
      });
    } else {
      this.fallbackWs = null;
    }

    this.system = {
      getStatus: () => this.getStatusSnapshot(),
      isReady: () => this.isReady(),
      isNativeDesktop: () => (this.apis.isTauri ? this.apis.isTauri() : true),
      connect: () => this.connect(),
      reconnect: () => this.reconnect(),
      disconnect: () => this.disconnect(),
      selectFolder: async () => {
        if (!this.apis.openDialog) {
          return null;
        }
        const selected = await this.apis.openDialog({
          directory: true,
          multiple: false,
          title: 'Selecionar pasta local',
        });
        if (typeof selected === 'string') {
          return selected;
        }
        if (Array.isArray(selected) && selected.length > 0 && typeof selected[0] === 'string') {
          return selected[0];
        }
        return null;
      },
      selectFile: async (options?: TauriSelectFileOptions) => {
        if (!this.apis.openDialog) {
          return null;
        }
        const selected = await this.apis.openDialog({
          directory: options?.directory ?? false,
          multiple: options?.multiple ?? false,
          title: options?.title,
          defaultPath: options?.defaultPath,
          filters: options?.filters,
        });
        if (typeof selected === 'string') {
          this.rememberNativePaths([selected]);
        } else if (Array.isArray(selected)) {
          this.rememberNativePaths(selected);
        }
        return selected;
      },
      openPath: async (targetPath: string) => {
        try {
          await this.apis.invoke('system_open_path', { target: targetPath });
          return { ok: true };
        } catch (err) {
          return {
            ok: false,
            error: err instanceof Error ? err.message : String(err),
          };
        }
      },
      getPathForFile: (file: File) => {
        const cached = this.droppedPathsByName.get(file.name);
        if (cached) {
          return cached;
        }
        const fallbackFile = file as File & { path?: string };
        return typeof fallbackFile.path === 'string' ? fallbackFile.path : '';
      },
      getHttpBaseUrl: () => this.getEffectiveHttpBaseUrl(),
      resolveMediaUrl: (
        pathOrUrl: string,
        mediaOpts?: { appendToken?: boolean; ticket?: string }
      ) => {
        const resolved = resolveTransportMediaUrl(pathOrUrl, {
          baseUrl: this.getEffectiveHttpBaseUrl(),
          token: this.getEffectiveHttpToken(),
          appendToken: mediaOpts?.appendToken,
        });
        return mediaOpts?.ticket ? attachQueryParam(resolved, 'ticket', mediaOpts.ticket) : resolved;
      },
      getMediaCandidateUrls: (
        relativePaths: string[],
        mediaOpts?: { appendToken?: boolean; ticket?: string }
      ) => {
        const urls = buildMediaCandidateUrls(relativePaths, {
          baseUrl: this.getEffectiveHttpBaseUrl(),
          token: this.getEffectiveHttpToken(),
          appendToken: mediaOpts?.appendToken,
        });
        return mediaOpts?.ticket
          ? urls.map((u) => attachQueryParam(u, 'ticket', mediaOpts.ticket!))
          : urls;
      },
      getMediaTicket: async (docId: string) => this.fetchMediaTicket(docId),
      resolveMediaUrlAsync: async (
        pathOrUrl: string,
        mediaOpts?: { appendToken?: boolean; docId?: string }
      ) => {
        const ticket = mediaOpts?.docId ? await this.fetchMediaTicket(mediaOpts.docId) : null;
        return this.system.resolveMediaUrl(pathOrUrl, {
          appendToken: ticket ? false : mediaOpts?.appendToken,
          ticket: ticket ?? undefined,
        });
      },
      getMediaCandidateUrlsAsync: async (
        relativePaths: string[],
        mediaOpts?: { appendToken?: boolean; docId?: string }
      ) => {
        const ticket = mediaOpts?.docId ? await this.fetchMediaTicket(mediaOpts.docId) : null;
        return this.system.getMediaCandidateUrls(relativePaths, {
          appendToken: ticket ? false : mediaOpts?.appendToken,
          ticket: ticket ?? undefined,
        });
      },
      onFileDrop: (handler: (paths: string[]) => void) => {
        if (this.disposed) {
          return () => {};
        }
        this.fileDropListeners.add(handler);
        return () => {
          this.fileDropListeners.delete(handler);
        };
      },
      getLastDroppedPaths: () => [...this.lastDroppedPaths],
      pingNative: async () => {
        try {
          return await this.apis.invoke<TauriPingResult>('system_ping');
        } catch {
          return null;
        }
      },
      getPreviewBaseUrl: () => this.loopbackConfig?.preview_base_url ?? null,
    };
  }

  private getEffectiveHttpBaseUrl(): string {
    if (this.loopbackConfig?.base_url) {
      return this.loopbackConfig.base_url.replace(/\/+$/, '');
    }
    return resolveDefaultHttpBaseUrl(this.httpBaseUrlOverride);
  }

  private getEffectiveHttpToken(): string {
    if (this.loopbackConfig?.token) {
      return this.loopbackConfig.token;
    }
    return this.getHttpToken();
  }

  private async fetchMediaTicket(docId: string): Promise<string | null> {
    if (!docId || this.disposed) {
      return null;
    }
    const now = this.nowFn();
    const cached = this.ticketCache.get(docId);
    if (cached && cached.expiresAtMs - 5000 > now) {
      return cached.ticket;
    }
    try {
      const res = await this.apis.invoke<TauriMediaTicket>('get_media_ticket', {
        docId,
      });
      if (res && typeof res.ticket === 'string' && res.ticket.length > 0) {
        if (res.base_url) {
          this.loopbackConfig = {
            base_url: res.base_url,
            token: this.loopbackConfig?.token ?? '',
            preview_base_url: this.loopbackConfig?.preview_base_url,
          };
        }
        const expiresAt = typeof res.expires_at_ms === 'number' ? res.expires_at_ms : now + 30000;
        this.ticketCache.set(docId, { ticket: res.ticket, expiresAtMs: expiresAt });
        return res.ticket;
      }
    } catch {
      // Increment 2.3 provides get_media_ticket; return null cleanly during Increment 2.2
    }
    return null;
  }

  private rememberNativePaths(paths: string[]): void {
    const cleaned = paths.filter((p): p is string => typeof p === 'string' && p.length > 0);
    if (cleaned.length === 0) {
      return;
    }
    this.lastDroppedPaths = cleaned;
    for (const fullPath of cleaned) {
      this.droppedPathsByName.set(extractBasename(fullPath), fullPath);
    }
  }

  private getStatusSnapshot(): TransportStatusSnapshot {
    if (this.fallbackWs) {
      const wsSnap = this.fallbackWs.system.getStatus();
      return {
        ...wsSnap,
        backend: 'tauri-hybrid',
        pendingRequests: wsSnap.pendingRequests + this.correlation.pendingCount,
        activeStreams: wsSnap.activeStreams + this.correlation.activeStreamCount,
        lastError: this.lastError ?? wsSnap.lastError,
      };
    }

    return {
      status: this.connectionStatus,
      backend: 'tauri-ipc',
      reconnectAttempt: 0,
      lastConnectedAt: this.lastConnectedAt,
      lastDisconnectedAt: this.lastDisconnectedAt,
      lastError: this.lastError,
      pendingRequests: this.correlation.pendingCount,
      activeStreams: this.correlation.activeStreamCount,
    };
  }

  private isReady(): boolean {
    if (this.disposed) {
      return false;
    }
    if (this.fallbackWs) {
      return this.fallbackWs.system.isReady() || this.nativeReady;
    }
    return this.nativeReady;
  }

  private notifyStatusListeners(): void {
    const snapshot = this.getStatusSnapshot();
    for (const listener of Array.from(this.statusListeners)) {
      try {
        listener(snapshot);
      } catch (err) {
        console.error('[TauriTransport] Error in status listener:', err);
      }
    }
  }

  private fireConnectedListeners(): void {
    for (const listener of Array.from(this.connectedListeners)) {
      try {
        listener();
      } catch (err) {
        console.error('[TauriTransport] Error in onConnected listener:', err);
      }
    }
  }

  connect(): void {
    if (this.disposed) {
      return;
    }
    if (!this.connectInFlight) {
      this.connectInFlight = true;
      void this.bootstrapNativeConnection();
    }
    if (this.fallbackWs) {
      this.fallbackWs.connect();
    } else if (!this.nativeReady) {
      this.connectionStatus = 'CONNECTING';
      this.notifyStatusListeners();
    }
  }

  private async bootstrapNativeConnection(): Promise<void> {
    try {
      await this.attachNativeListeners();
      const ping = await this.apis.invoke<TauriPingResult>('system_ping');
      if (this.disposed) {
        return;
      }
      if (!ping || ping.ok !== true) {
        throw new Error('Native Tauri ping returned unhealthy status');
      }

      try {
        const loopback = await this.apis.invoke<TauriLoopbackConfig>('get_loopback_config');
        if (!this.disposed && loopback && typeof loopback.base_url === 'string') {
          this.loopbackConfig = loopback;
        }
      } catch {
        // Loopback config command is added in Increment 2.3; ignore cleanly in 2.2
      }

      const wasReady = this.nativeReady;
      this.nativeReady = true;
      this.lastError = null;
      if (!this.fallbackWs) {
        this.connectionStatus = 'CONNECTED';
        this.lastConnectedAt = this.nowFn();
      }
      this.notifyStatusListeners();

      if (!this.fallbackWs && !wasReady) {
        this.fireConnectedListeners();
      }
    } catch (err) {
      if (this.disposed) {
        return;
      }
      this.nativeReady = false;
      this.lastError = err instanceof Error ? err.message : String(err);
      if (!this.fallbackWs) {
        this.lastDisconnectedAt = this.nowFn();
        this.connectionStatus = 'OFFLINE';
      }
      this.notifyStatusListeners();
    } finally {
      this.connectInFlight = false;
    }
  }

  private async attachNativeListeners(): Promise<void> {
    if (!this.ipcEventUnlisten && this.apis.listen) {
      this.ipcEventUnlisten = await this.apis.listen(this.ipcEventName, (event) => {
        this.handleIncomingRawMessage(event.payload);
      });
    }
    if (!this.dragDropUnlisten && this.apis.onDragDropEvent) {
      this.dragDropUnlisten = await this.apis.onDragDropEvent((payload) => {
        if ((payload.type === 'enter' || payload.type === 'drop') && payload.paths.length > 0) {
          this.rememberNativePaths(payload.paths);
        }
        if (payload.type === 'drop' && payload.paths.length > 0) {
          for (const listener of Array.from(this.fileDropListeners)) {
            try {
              listener([...payload.paths]);
            } catch (err) {
              console.error('[TauriTransport] Error in file drop listener:', err);
            }
          }
        }
      });
    }
  }

  reconnect(): void {
    if (this.disposed) {
      return;
    }
    this.nativeReady = false;
    this.connectInFlight = false;
    if (this.fallbackWs) {
      this.fallbackWs.reconnect();
    }
    this.connect();
  }

  disconnect(): void {
    this.nativeReady = false;
    this.connectInFlight = false;
    if (this.fallbackWs) {
      this.fallbackWs.disconnect();
    }
    this.correlation.rejectAll(new TransportError('DISCONNECTED', 'Transporte Tauri desligado.'));
    this.connectionStatus = 'OFFLINE';
    this.lastDisconnectedAt = this.nowFn();
    this.notifyStatusListeners();
  }

  dispose(): void {
    if (this.disposed) {
      return;
    }
    this.disposed = true;
    this.nativeReady = false;

    if (this.ipcEventUnlisten) {
      try {
        this.ipcEventUnlisten();
      } catch {
        // Ignore unlisten errors
      }
      this.ipcEventUnlisten = null;
    }
    if (this.dragDropUnlisten) {
      try {
        this.dragDropUnlisten();
      } catch {
        // Ignore unlisten errors
      }
      this.dragDropUnlisten = null;
    }
    if (this.fallbackStatusUnsub) {
      this.fallbackStatusUnsub();
      this.fallbackStatusUnsub = null;
    }
    if (this.fallbackConnectedUnsub) {
      this.fallbackConnectedUnsub();
      this.fallbackConnectedUnsub = null;
    }
    if (this.fallbackAnyUnsub) {
      this.fallbackAnyUnsub();
      this.fallbackAnyUnsub = null;
    }
    if (this.fallbackWs) {
      this.fallbackWs.dispose();
    }

    this.correlation.rejectAll(new TransportError('TRANSPORT_CLOSED', 'Transporte Tauri encerrado.'));
    this.fileDropListeners.clear();
    this.droppedPathsByName.clear();
    this.ticketCache.clear();
    this.typeListeners.clear();
    this.anyListeners.clear();
    this.connectedListeners.clear();
    this.connectionStatus = 'OFFLINE';
    this.notifyStatusListeners();
    this.statusListeners.clear();
  }

  private shouldRouteToNativeIpc(message: ClientMessage): boolean {
    if (!this.fallbackWs) {
      return true;
    }
    return this.nativeRpcCommands.has(message.type);
  }

  send(message: ClientMessage): boolean {
    if (this.disposed) {
      return false;
    }
    if (this.shouldRouteToNativeIpc(message)) {
      if (!this.nativeReady) {
        return false;
      }
      void this.apis.invoke(this.ipcDispatchCommand, { message }).catch((err) => {
        this.lastError = err instanceof Error ? err.message : String(err);
        this.notifyStatusListeners();
      });
      return true;
    }
    return this.fallbackWs ? this.fallbackWs.send(message) : false;
  }

  invoke<TResult = ServerMessage>(
    message: ClientMessage,
    options: InvokeOptions<TResult> = {}
  ): Promise<TResult> {
    if (!this.shouldRouteToNativeIpc(message) && this.fallbackWs) {
      return this.fallbackWs.invoke(message, options);
    }

    return this.correlation.runInvoke(
      message,
      options,
      {
        isDisposed: this.disposed,
        isReady: this.nativeReady,
        disconnectedMessage: 'Transporte Tauri não está ligado para executar pedido.',
      },
      (outboundMessage, requestId, rejectEarly) => {
        void this.apis
          .invoke<unknown>(this.ipcDispatchCommand, { message: outboundMessage })
          .then((directResponse) => {
            if (directResponse !== undefined && directResponse !== null) {
              this.handleIncomingRawMessage(directResponse);
            }
          })
          .catch((err) => {
            rejectEarly(
              err instanceof Error
                ? err
                : new TransportError('UNKNOWN', `Falha IPC Tauri ao enviar ${outboundMessage.type}.`, {
                    requestId,
                    cause: err,
                  })
            );
          });
      }
    );
  }

  openStream<TChunk = ServerMessage>(
    message: ClientMessage,
    options: OpenStreamOptions<TChunk>,
    onChunk: (chunk: TChunk) => void
  ): TransportStreamHandle {
    if (!this.shouldRouteToNativeIpc(message) && this.fallbackWs) {
      return this.fallbackWs.openStream(message, options, onChunk);
    }

    return this.correlation.openStream(
      message,
      options,
      onChunk,
      {
        isDisposed: this.disposed,
        isReady: this.nativeReady,
        disconnectedMessage: 'Transporte Tauri não está ligado para abrir stream.',
      },
      (outboundMessage, requestId, rejectEarly) => {
        void this.apis.invoke(this.ipcDispatchCommand, { message: outboundMessage }).catch((err) => {
          rejectEarly(
            err instanceof Error
              ? err
              : new TransportError(
                  'DISCONNECTED',
                  `Falha ao iniciar stream ${outboundMessage.type}.`,
                  { requestId, cause: err }
                )
          );
        });
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
      console.error('[TauriTransport] Error in initial connection state callback:', err);
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

  cancelPendingRequests(
    predicate: (meta: PendingRequestMeta) => boolean,
    reason = 'Cancelado pelo utilizador'
  ): number {
    let cancelledCount = this.correlation.cancelWhere(predicate, reason);
    if (this.fallbackWs) {
      cancelledCount += this.fallbackWs.cancelPendingRequests(predicate, reason);
    }
    return cancelledCount;
  }

  private dispatchMessageToSubscribers(msg: ServerMessage, parsed: unknown): void {
    const typedHandlers = this.typeListeners.get(msg.type);
    if (typedHandlers) {
      for (const handler of Array.from(typedHandlers)) {
        try {
          handler(msg, parsed);
        } catch (err) {
          console.error(`[TauriTransport] Error in subscriber for '${msg.type}':`, err);
        }
      }
    }

    for (const handler of Array.from(this.anyListeners)) {
      try {
        handler(msg, parsed);
      } catch (err) {
        console.error('[TauriTransport] Error in subscribeAny listener:', err);
      }
    }
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
        console.warn('[TauriTransport] Ignored invalid JSON event:', err);
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
      return;
    }

    const msgReqId = (msg as { request_id?: unknown }).request_id;
    const effectiveRequestId =
      rawRequestId ?? (typeof msgReqId === 'string' && msgReqId.length > 0 ? msgReqId : undefined);

    this.correlation.handleMessage(msg, effectiveRequestId);
    this.dispatchMessageToSubscribers(msg, parsed);
  }
}
