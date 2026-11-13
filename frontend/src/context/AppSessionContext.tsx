// Transport-agnostic application session context facade.
// All transport operations route through JarvisTransport (TauriTransportAdapter or WebSocketTransportAdapter).
export {
  WebSocketProvider as AppSessionProvider,
  useWebSocket as useAppSession,
} from './WebSocketContext';
