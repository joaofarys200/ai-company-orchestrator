import { createContext, useContext, useEffect, useState } from 'react';
import {
  createStandaloneSystemCapabilities,
  type JarvisTransport,
} from './JarvisTransport.ts';
import type {
  TransportStatusSnapshot,
  TransportSystemCapabilities,
} from './TransportTypes.ts';

export const TransportReactContext = createContext<JarvisTransport | null>(null);

const fallbackSystemCapabilities = createStandaloneSystemCapabilities();

export function useTransport(): JarvisTransport {
  const ctx = useContext(TransportReactContext);
  if (!ctx) {
    throw new Error('useTransport must be used within a TransportProvider');
  }
  return ctx;
}

export function useOptionalTransport(): JarvisTransport | null {
  return useContext(TransportReactContext);
}

export function useTransportSystem(): TransportSystemCapabilities {
  const ctx = useContext(TransportReactContext);
  return ctx ? ctx.system : fallbackSystemCapabilities;
}

export function useTransportStatus(): TransportStatusSnapshot {
  const ctx = useContext(TransportReactContext);
  const [snapshot, setSnapshot] = useState<TransportStatusSnapshot>(() =>
    ctx ? ctx.system.getStatus() : fallbackSystemCapabilities.getStatus()
  );

  useEffect(() => {
    if (!ctx) {
      return;
    }
    return ctx.subscribeConnectionState((nextSnapshot) => {
      setSnapshot(nextSnapshot);
    });
  }, [ctx]);

  return snapshot;
}

