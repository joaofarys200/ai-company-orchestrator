import React, { useEffect, useState } from 'react';
import { normalizeServerMessage } from '../protocol/websocket';
import {
  createDefaultTransport,
  type DefaultTransportConfig,
} from './createDefaultTransport.ts';
import type { JarvisTransport } from './JarvisTransport.ts';
import { TransportReactContext } from './TransportContext.ts';

export interface TransportProviderProps {
  children: React.ReactNode;
  transport?: JarvisTransport;
  config?: DefaultTransportConfig;
  autoConnect?: boolean;
}

export const TransportProvider: React.FC<TransportProviderProps> = ({
  children,
  transport: injectedTransport,
  config,
  autoConnect = true,
}) => {
  const [ownedTransport] = useState<JarvisTransport | null>(() =>
    injectedTransport
      ? null
      : createDefaultTransport({
          normalizeMessage: normalizeServerMessage,
          ...config,
        })
  );

  const activeTransport = injectedTransport ?? ownedTransport!;
  const ownsTransport = !injectedTransport;

  useEffect(() => {
    if (!autoConnect) {
      return;
    }
    activeTransport.system.connect();
    return () => {
      if (ownsTransport) {
        activeTransport.system.disconnect();
      }
    };
  }, [activeTransport, autoConnect, ownsTransport]);

  return (
    <TransportReactContext.Provider value={activeTransport}>
      {children}
    </TransportReactContext.Provider>
  );
};
