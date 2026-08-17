const { contextBridge, ipcRenderer } = require('electron');

/**
 * JARVIS OS - Electron Preload Script
 * Expõe uma API de transporte IPC segura e bidirecional para a UI (Renderer),
 * respeitando o isolamento estrito de contexto (contextIsolation: true, nodeIntegration: false).
 */

contextBridge.exposeInMainWorld('jarvisIPC', {
  send: (message) => {
    if (typeof message === 'object') {
      ipcRenderer.send('jarvis-to-backend', message);
    } else if (typeof message === 'string') {
      try {
        ipcRenderer.send('jarvis-to-backend', JSON.parse(message));
      } catch (e) {
        console.error('[preload] Failed to parse message string for IPC:', e);
      }
    }
  },

  onMessage: (callback) => {
    const handler = (event, data) => callback(data);
    ipcRenderer.on('jarvis-from-backend', handler);
    // Retorna função de desinscrição para evitar vazamento de memória
    return () => {
      ipcRenderer.removeListener('jarvis-from-backend', handler);
    };
  },

  isNativeIPC: true,
});
