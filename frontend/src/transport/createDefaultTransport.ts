import { isTauriRuntime, type JarvisTransport } from './JarvisTransport.ts';
import {
  TauriTransportAdapter,
  type TauriTransportAdapterConfig,
} from './TauriTransportAdapter.ts';
import {
  WebSocketTransportAdapter,
  type WebSocketTransportAdapterConfig,
} from './WebSocketTransportAdapter.ts';

export type DefaultTransportConfig = WebSocketTransportAdapterConfig &
  TauriTransportAdapterConfig & {
    forceBackend?: 'auto' | 'tauri' | 'websocket';
  };

export function createDefaultTransport(config: DefaultTransportConfig = {}): JarvisTransport {
  const mode = config.forceBackend ?? 'auto';
  const useTauri = mode === 'tauri' || (mode === 'auto' && isTauriRuntime());
  if (useTauri) {
    return new TauriTransportAdapter({
      preferHybridFallback: config.preferHybridFallback ?? false,
      ...config,
    });
  }
  return new WebSocketTransportAdapter(config);
}
