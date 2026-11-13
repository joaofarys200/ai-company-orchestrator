import type { ClientMessage, ServerMessage } from '../protocol/websocket';

export const TRANSPORT_MIN_TIMEOUT_MS = 5000;
export const TRANSPORT_MAX_TIMEOUT_MS = 900000;
export const TRANSPORT_DEFAULT_TIMEOUT_MS = 30000;

export const WS_READY_STATE_CONNECTING = 0;
export const WS_READY_STATE_OPEN = 1;
export const WS_READY_STATE_CLOSING = 2;
export const WS_READY_STATE_CLOSED = 3;

export interface NativeDesktopBridge {
  send: (message: unknown) => void;
  onMessage: (callback: (data: unknown) => void) => () => void;
  getPathForFile?: (file: File) => string;
  selectFolder?: () => Promise<string | null>;
  openPath?: (targetPath: string) => Promise<{ ok: boolean; error?: string } | null>;
  isNativeIPC: boolean;
}

declare global {
  interface Window {
    jarvisIPC?: NativeDesktopBridge;
    __JARVIS_HTTP_TOKEN__?: string;
  }
}

export type TransportConnectionStatus =
  | 'CONNECTING'
  | 'CONNECTED'
  | 'RECONNECTING'
  | 'DISCONNECTED'
  | 'OFFLINE';

export type TransportBackendKind =
  | 'websocket'
  | 'electron-ipc'
  | 'tauri-ipc'
  | 'tauri-hybrid'
  | 'custom';

export interface TauriSelectFileFilter {
  name: string;
  extensions: string[];
}

export interface TauriSelectFileOptions {
  title?: string;
  multiple?: boolean;
  directory?: boolean;
  defaultPath?: string;
  filters?: TauriSelectFileFilter[];
}

export interface TauriPingResult {
  ok: boolean;
  runtime: string;
  timestamp_ms?: number;
}

export interface TauriLoopbackConfig {
  base_url: string;
  token: string;
  preview_base_url?: string;
}

export interface TauriMediaTicket {
  ticket: string;
  base_url?: string;
  expires_at_ms?: number;
}

export interface TransportStatusSnapshot {
  status: TransportConnectionStatus;
  backend: TransportBackendKind;
  reconnectAttempt: number;
  lastConnectedAt: number | null;
  lastDisconnectedAt: number | null;
  lastError: string | null;
  pendingRequests: number;
  activeStreams: number;
}

export type TransportErrorCode =
  | 'DISCONNECTED'
  | 'TIMEOUT'
  | 'ABORTED'
  | 'REMOTE_ERROR'
  | 'SERIALIZATION_ERROR'
  | 'TRANSPORT_CLOSED'
  | 'DUPLICATE_REQUEST_ID'
  | 'UNKNOWN';

export interface TransportErrorOptions {
  requestId?: string;
  details?: unknown;
  cause?: unknown;
}

export class TransportError extends Error {
  readonly code: TransportErrorCode;
  readonly requestId?: string;
  readonly details?: unknown;

  constructor(code: TransportErrorCode, message: string, options?: TransportErrorOptions) {
    super(message, options?.cause !== undefined ? { cause: options.cause } : undefined);
    this.name = 'TransportError';
    this.code = code;
    this.requestId = options?.requestId;
    this.details = options?.details;
  }
}

export type ResponseDecision<TResult> =
  | { kind: 'ignore' }
  | { kind: 'resolve'; value: TResult }
  | { kind: 'reject'; error: Error };

export type StreamDecision<TChunk> =
  | { kind: 'ignore' }
  | { kind: 'chunk'; chunk: TChunk; done?: boolean }
  | { kind: 'complete'; chunk?: TChunk }
  | { kind: 'error'; error: Error };

export interface PendingRequestMeta {
  requestId: string;
  messageType: string;
  tag?: string;
  startedAt: number;
}

export interface InvokeOptions<TResult = ServerMessage> {
  requestId?: string;
  timeoutMs?: number;
  signal?: AbortSignal;
  tag?: string;
  requireReady?: boolean;
  rejectOnDisconnect?: boolean;
  attachRequestId?: boolean;
  matchResponse?: (message: ServerMessage, requestId: string) => ResponseDecision<TResult>;
  legacyMatchResponse?: (message: ServerMessage) => ResponseDecision<TResult>;
  cancelMessage?: ClientMessage | ((requestId: string) => ClientMessage);
  timeoutMessage?: string;
}

export interface OpenStreamOptions<TChunk = ServerMessage> {
  correlationId?: string;
  timeoutMs?: number;
  signal?: AbortSignal;
  tag?: string;
  requireReady?: boolean;
  attachRequestId?: boolean;
  matchChunk: (message: ServerMessage, correlationId: string) => StreamDecision<TChunk>;
  legacyMatchChunk?: (message: ServerMessage) => StreamDecision<TChunk>;
  cancelMessage?: ClientMessage | ((correlationId: string) => ClientMessage);
  timeoutMessage?: string;
}

export interface TransportStreamHandle {
  readonly requestId: string;
  readonly done: Promise<void>;
  cancel: (reason?: string) => void;
}

export interface ReconnectPolicy {
  initialDelayMs: number;
  maxDelayMs: number;
  multiplier: number;
  jitterFactor: number;
}

export interface TransportSystemCapabilities {
  getStatus: () => TransportStatusSnapshot;
  isReady: () => boolean;
  isNativeDesktop: () => boolean;
  connect: () => void;
  reconnect: () => void;
  disconnect: () => void;
  selectFolder: () => Promise<string | null>;
  selectFile?: (options?: TauriSelectFileOptions) => Promise<string | string[] | null>;
  openPath: (targetPath: string) => Promise<{ ok: boolean; error?: string } | null>;
  getPathForFile: (file: File) => string;
  getHttpBaseUrl: () => string;
  resolveMediaUrl: (pathOrUrl: string, options?: { appendToken?: boolean; ticket?: string }) => string;
  getMediaCandidateUrls: (relativePaths: string[], options?: { appendToken?: boolean; ticket?: string }) => string[];
  getMediaTicket?: (docId: string) => Promise<string | null>;
  resolveMediaUrlAsync?: (
    pathOrUrl: string,
    options?: { appendToken?: boolean; docId?: string }
  ) => Promise<string>;
  getMediaCandidateUrlsAsync?: (
    relativePaths: string[],
    options?: { appendToken?: boolean; docId?: string }
  ) => Promise<string[]>;
  onFileDrop?: (handler: (paths: string[]) => void) => () => void;
  getLastDroppedPaths?: () => string[];
  pingNative?: () => Promise<TauriPingResult | null>;
  getPreviewBaseUrl?: () => string | null;
}

export interface WebSocketCloseEventLike {
  code?: number;
  reason?: string;
  wasClean?: boolean;
}

export interface WebSocketMessageEventLike {
  data: unknown;
}

export interface WebSocketLike {
  readonly readyState: number;
  send: (data: string) => void;
  close: (code?: number, reason?: string) => void;
  onopen: ((event: unknown) => void) | null;
  onclose: ((event: WebSocketCloseEventLike) => void) | null;
  onerror: ((event: unknown) => void) | null;
  onmessage: ((event: WebSocketMessageEventLike) => void) | null;
}

export function normalizeTransportTimeout(
  timeoutMs?: number,
  bounds?: { min?: number; max?: number }
): number {
  const min = bounds?.min ?? TRANSPORT_MIN_TIMEOUT_MS;
  const max = bounds?.max ?? TRANSPORT_MAX_TIMEOUT_MS;
  if (timeoutMs === undefined || !Number.isFinite(timeoutMs)) {
    return Math.min(max, Math.max(min, TRANSPORT_DEFAULT_TIMEOUT_MS));
  }
  return Math.min(max, Math.max(min, Math.trunc(timeoutMs)));
}

