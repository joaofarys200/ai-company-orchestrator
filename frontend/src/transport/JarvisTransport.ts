import type { ClientMessage, ServerMessage } from '../protocol/websocket';
import type {
  InvokeOptions,
  NativeDesktopBridge,
  OpenStreamOptions,
  PendingRequestMeta,
  TransportStatusSnapshot,
  TransportStreamHandle,
  TransportSystemCapabilities,
} from './TransportTypes.ts';

export interface JarvisTransport {
  readonly system: TransportSystemCapabilities;
  send: (message: ClientMessage) => boolean;
  invoke: <TResult = ServerMessage>(
    message: ClientMessage,
    options?: InvokeOptions<TResult>
  ) => Promise<TResult>;
  openStream: <TChunk = ServerMessage>(
    message: ClientMessage,
    options: OpenStreamOptions<TChunk>,
    onChunk: (chunk: TChunk) => void
  ) => TransportStreamHandle;
  subscribe: <TType extends ServerMessage['type']>(
    eventType: TType,
    handler: (message: Extract<ServerMessage, { type: TType }>, raw?: unknown) => void
  ) => () => void;
  subscribeAny: (handler: (message: ServerMessage, raw?: unknown) => void) => () => void;
  subscribeConnectionState: (handler: (snapshot: TransportStatusSnapshot) => void) => () => void;
  onConnected: (handler: () => void) => () => void;
  cancelPendingRequests: (predicate: (meta: PendingRequestMeta) => boolean, reason?: string) => number;
  dispose: () => void;
}

let requestSequence = 0;

export function createTransportRequestId(prefix = 'req'): string {
  requestSequence = (requestSequence + 1) % Number.MAX_SAFE_INTEGER;
  const randomPart = Math.random().toString(36).slice(2, 7);
  return `${prefix}:${Date.now()}:${requestSequence}:${randomPart}`;
}

export function getWindowNativeBridge(): NativeDesktopBridge | null {
  if (typeof window === 'undefined') {
    return null;
  }
  const bridge = window.jarvisIPC;
  if (!bridge || !bridge.isNativeIPC) {
    return null;
  }
  return bridge;
}

export function getWindowHttpToken(): string {
  if (typeof window === 'undefined') {
    return '';
  }
  const token = window.__JARVIS_HTTP_TOKEN__;
  return typeof token === 'string' ? token : '';
}

export function isTauriRuntime(): boolean {
  if (typeof globalThis === 'undefined') {
    return false;
  }
  const g = globalThis as {
    __TAURI_INTERNALS__?: unknown;
    __TAURI__?: unknown;
    location?: { origin?: string; protocol?: string; hostname?: string };
    window?: {
      __TAURI_INTERNALS__?: unknown;
      __TAURI__?: unknown;
      location?: { origin?: string; protocol?: string; hostname?: string };
    };
  };
  if (
    Boolean(g.__TAURI_INTERNALS__) ||
    Boolean(g.__TAURI__) ||
    Boolean(g.window?.__TAURI_INTERNALS__) ||
    Boolean(g.window?.__TAURI__)
  ) {
    return true;
  }
  const loc = g.window?.location ?? g.location;
  const protocol = loc?.protocol?.toLowerCase() ?? '';
  const hostname = loc?.hostname?.toLowerCase() ?? '';
  if (protocol === 'tauri:' || protocol === 'ipc:') {
    return true;
  }
  return hostname === 'tauri.localhost' || hostname === 'ipc.localhost' || hostname.endsWith('.tauri.localhost');
}

export function isVirtualDesktopOrigin(origin: string | undefined): boolean {
  if (!origin || origin === 'null' || origin.startsWith('file://')) {
    return true;
  }
  const lower = origin.trim().toLowerCase();
  if (lower.startsWith('tauri://') || lower.startsWith('ipc://')) {
    return true;
  }
  try {
    const parsed = new URL(lower);
    const host = parsed.hostname;
    if (
      host === 'tauri.localhost' ||
      host === 'ipc.localhost' ||
      host.endsWith('.tauri.localhost')
    ) {
      return true;
    }
    if ((host === '127.0.0.1' || host === 'localhost') && (parsed.port === '5173' || parsed.port === '1420')) {
      return true;
    }
  } catch {
    return true;
  }
  return false;
}

export function resolveDefaultHttpBaseUrl(overrideBaseUrl?: string): string {
  if (overrideBaseUrl && overrideBaseUrl.trim().length > 0) {
    return overrideBaseUrl.trim().replace(/\/+$/, '');
  }
  if (typeof window !== 'undefined') {
    const origin = window.location?.origin;
    if (origin && !isVirtualDesktopOrigin(origin)) {
      return origin.replace(/\/+$/, '');
    }
    if (window.location?.href && !window.location.href.startsWith('data:')) {
      try {
        const parsed = new URL(window.location.href);
        if (parsed.origin && parsed.origin !== 'null' && !parsed.origin.includes(':5173')) {
          return parsed.origin.replace(/\/+$/, '');
        }
      } catch {
        // Fallback below
      }
    }
  }
  return 'http://127.0.0.1:8000';
}

export function resolveTransportMediaUrl(
  pathOrUrl: string,
  options?: { baseUrl?: string; token?: string; appendToken?: boolean }
): string {
  if (!pathOrUrl) {
    return '';
  }
  const normalized = pathOrUrl.trim();
  const baseUrl = resolveDefaultHttpBaseUrl(options?.baseUrl);
  let resolved: string;

  if (/^https?:\/\//i.test(normalized)) {
    resolved = normalized;
  } else {
    const cleanRel = normalized.startsWith('/') ? normalized : `/${normalized}`;
    resolved = baseUrl ? `${baseUrl}${cleanRel}` : cleanRel;
  }

  if (options?.appendToken && options.token) {
    const sep = resolved.includes('?') ? '&' : '?';
    if (!resolved.includes('token=')) {
      resolved = `${resolved}${sep}token=${encodeURIComponent(options.token)}`;
    }
  }
  return resolved;
}

export function buildMediaCandidateUrls(
  relativePaths: string[],
  options?: { baseUrl?: string; token?: string; appendToken?: boolean }
): string[] {
  const candidates: string[] = [];
  const defaultHttp = resolveDefaultHttpBaseUrl(options?.baseUrl);
  const loopbacks = [defaultHttp, 'http://127.0.0.1:8000', 'http://localhost:8000'];

  for (const rel of relativePaths) {
    if (!rel) continue;
    if (/^https?:\/\//i.test(rel)) {
      candidates.push(resolveTransportMediaUrl(rel, options));
      continue;
    }
    const cleanRel = rel.startsWith('/') ? rel : `/${rel}`;
    candidates.push(
      options?.appendToken && options?.token
        ? `${cleanRel}${cleanRel.includes('?') ? '&' : '?'}token=${encodeURIComponent(options.token)}`
        : cleanRel
    );
    for (const base of loopbacks) {
      if (base) {
        candidates.push(
          resolveTransportMediaUrl(cleanRel, {
            baseUrl: base,
            token: options?.token,
            appendToken: options?.appendToken,
          })
        );
      }
    }
  }

  return Array.from(new Set(candidates.filter(Boolean)));
}

export function createStandaloneSystemCapabilities(options?: {
  nativeBridge?: NativeDesktopBridge | null;
  httpBaseUrl?: string;
  getHttpToken?: () => string;
}): TransportSystemCapabilities {
  const getBridge = () => options?.nativeBridge ?? getWindowNativeBridge();
  const getToken = () => (options?.getHttpToken ? options.getHttpToken() : getWindowHttpToken());

  const snapshot: TransportStatusSnapshot = {
    status: getBridge()?.isNativeIPC ? 'CONNECTED' : 'DISCONNECTED',
    backend: getBridge()?.isNativeIPC ? 'electron-ipc' : 'websocket',
    reconnectAttempt: 0,
    lastConnectedAt: null,
    lastDisconnectedAt: null,
    lastError: null,
    pendingRequests: 0,
    activeStreams: 0,
  };

  return {
    getStatus: () => ({ ...snapshot }),
    isReady: () => Boolean(getBridge()?.isNativeIPC),
    isNativeDesktop: () => Boolean(getBridge()?.isNativeIPC),
    connect: () => {},
    reconnect: () => {},
    disconnect: () => {},
    selectFolder: async () => {
      const bridge = getBridge();
      if (bridge?.selectFolder) {
        return bridge.selectFolder();
      }
      return null;
    },
    openPath: async (targetPath: string) => {
      const bridge = getBridge();
      if (bridge?.openPath) {
        return bridge.openPath(targetPath);
      }
      return null;
    },
    getPathForFile: (file: File) => {
      const bridge = getBridge();
      if (bridge?.getPathForFile) {
        return bridge.getPathForFile(file);
      }
      const fallbackFile = file as File & { path?: string };
      return typeof fallbackFile.path === 'string' ? fallbackFile.path : '';
    },
    getHttpBaseUrl: () => resolveDefaultHttpBaseUrl(options?.httpBaseUrl),
    resolveMediaUrl: (pathOrUrl: string, mediaOpts?: { appendToken?: boolean }) =>
      resolveTransportMediaUrl(pathOrUrl, {
        baseUrl: options?.httpBaseUrl,
        token: getToken(),
        appendToken: mediaOpts?.appendToken,
      }),
    getMediaCandidateUrls: (relativePaths: string[], mediaOpts?: { appendToken?: boolean }) =>
      buildMediaCandidateUrls(relativePaths, {
        baseUrl: options?.httpBaseUrl,
        token: getToken(),
        appendToken: mediaOpts?.appendToken,
      }),
  };
}
