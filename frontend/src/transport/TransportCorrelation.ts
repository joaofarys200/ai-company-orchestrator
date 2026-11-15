import type { ClientMessage, ServerMessage } from '../protocol/websocket';
import { createTransportRequestId } from './JarvisTransport.ts';
import {
  normalizeTransportTimeout,
  TransportError,
  type InvokeOptions,
  type OpenStreamOptions,
  type PendingRequestMeta,
  type ResponseDecision,
  type StreamDecision,
  type TransportStreamHandle,
} from './TransportTypes.ts';

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

export interface TransportCorrelationConfig {
  nowFn: () => number;
  maxSettledHistory: number;
  timeoutBounds?: { min?: number; max?: number };
  sendCancel: (message: ClientMessage) => boolean;
  onPendingChanged: () => void;
}

export class TransportCorrelationRegistry {
  private readonly nowFn: () => number;
  private readonly maxSettledHistory: number;
  private readonly timeoutBounds?: { min?: number; max?: number };
  private readonly sendCancel: (message: ClientMessage) => boolean;
  private readonly onPendingChanged: () => void;

  private readonly pendingInvokes = new Map<string, PendingInvokeEntry<unknown>>();
  private readonly activeStreams = new Map<string, ActiveStreamEntry<unknown>>();
  private readonly settledRequestIds = new Map<string, number>();

  constructor(config: TransportCorrelationConfig) {
    this.nowFn = config.nowFn;
    this.maxSettledHistory = config.maxSettledHistory;
    this.timeoutBounds = config.timeoutBounds;
    this.sendCancel = config.sendCancel;
    this.onPendingChanged = config.onPendingChanged;
  }

  get pendingCount(): number {
    return this.pendingInvokes.size;
  }

  get activeStreamCount(): number {
    return this.activeStreams.size;
  }

  private markSettled(requestId: string): void {
    this.settledRequestIds.set(requestId, this.nowFn());
    while (this.settledRequestIds.size > this.maxSettledHistory) {
      const oldestKey = this.settledRequestIds.keys().next().value;
      if (oldestKey === undefined) break;
      this.settledRequestIds.delete(oldestKey);
    }
  }

  private sendCancellation(
    cancelMessage: ClientMessage | ((id: string) => ClientMessage) | undefined,
    requestId: string
  ): void {
    if (!cancelMessage) return;
    const payload = typeof cancelMessage === 'function' ? cancelMessage(requestId) : cancelMessage;
    this.sendCancel(payload);
  }

  runInvoke<TResult>(
    message: ClientMessage,
    options: InvokeOptions<TResult>,
    checks: { isDisposed: boolean; isReady: boolean; disconnectedMessage: string },
    dispatch: (
      outboundMessage: ClientMessage,
      requestId: string,
      rejectEarly: (err: Error) => void
    ) => void
  ): Promise<TResult> {
    if (checks.isDisposed) {
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
        new TransportError('DUPLICATE_REQUEST_ID', `Request ID duplicado ainda em curso: ${requestId}`, {
          requestId,
        })
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
    if (requireReady && !checks.isReady) {
      return Promise.reject(
        new TransportError('DISCONNECTED', checks.disconnectedMessage, { requestId })
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
        if (!entry) return null;
        this.pendingInvokes.delete(requestId);
        clearTimeout(entry.timer);
        if (entry.abortCleanup) {
          entry.abortCleanup();
        }
        this.markSettled(requestId);
        this.onPendingChanged();
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
          this.sendCancellation(entry.cancelMessage, requestId);
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
      this.onPendingChanged();

      dispatch(outboundMessage, requestId, (err) => {
        if (cleanupEntry()) {
          reject(err);
        }
      });
    });
  }

  openStream<TChunk>(
    message: ClientMessage,
    options: OpenStreamOptions<TChunk>,
    onChunk: (chunk: TChunk) => void,
    checks: { isDisposed: boolean; isReady: boolean; disconnectedMessage: string },
    dispatch: (
      outboundMessage: ClientMessage,
      requestId: string,
      rejectEarly: (err: Error) => void
    ) => void
  ): TransportStreamHandle {
    const requestId =
      options.correlationId ??
      (typeof (message as { request_id?: unknown }).request_id === 'string' &&
      (message as { request_id: string }).request_id.length > 0
        ? (message as { request_id: string }).request_id
        : createTransportRequestId(`stream_${message.type}`));

    if (checks.isDisposed) {
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
    if (requireReady && !checks.isReady) {
      return {
        requestId,
        done: Promise.reject(
          new TransportError('DISCONNECTED', checks.disconnectedMessage, { requestId })
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
        this.onPendingChanged();
        return entry;
      };

      const startTimer = () =>
        setTimeout(() => {
          const entry = cleanupStream();
          if (!entry) return;
          this.sendCancellation(entry.cancelMessage, requestId);
          rejectDone(new TransportError('TIMEOUT', timeoutMessage, { requestId }));
        }, timeoutMs);

      const handleCancel = (reason?: string, cause?: unknown) => {
        const entry = cleanupStream();
        if (!entry) return;
        this.sendCancellation(entry.cancelMessage, requestId);
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
        const onAbort = () =>
          handleCancel(`Stream ${requestId} cancelado via AbortSignal.`, options.signal?.reason);
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
      this.onPendingChanged();

      dispatch(outboundMessage, requestId, (err) => {
        if (cleanupStream()) {
          rejectDone(err);
        }
      });
    });

    return {
      requestId,
      done,
      cancel: cancelStream,
    };
  }

  handleMessage(msg: ServerMessage, effectiveRequestId?: string): void {
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
      // Guard: tagged request_id messages never fall through to legacy untagged matching
      return;
    }

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

  rejectDisconnected(error: TransportError): void {
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
      this.onPendingChanged();
    }
  }

  rejectAll(error: TransportError): void {
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
      this.onPendingChanged();
    }
  }

  cancelWhere(predicate: (meta: PendingRequestMeta) => boolean, reason: string): number {
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
      this.onPendingChanged();
    }
    return cancelledCount;
  }

  private settlePendingInvoke<TResult>(
    requestId: string,
    entry: PendingInvokeEntry<TResult>,
    decision: ResponseDecision<TResult>
  ): boolean {
    if (decision.kind === 'ignore') {
      return false;
    }
    if (this.pendingInvokes.get(requestId) !== entry) {
      return true;
    }
    this.pendingInvokes.delete(requestId);
    clearTimeout(entry.timer);
    if (entry.abortCleanup) {
      entry.abortCleanup();
    }
    this.markSettled(requestId);
    this.onPendingChanged();

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
          this.sendCancellation(stream.cancelMessage, stream.meta.requestId);
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
}
