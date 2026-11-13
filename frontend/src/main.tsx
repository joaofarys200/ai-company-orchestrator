import './polyfills'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { TransportProvider } from './transport'
import { WebSocketProvider } from './context/WebSocketContext.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <TransportProvider>
      <WebSocketProvider>
        <App />
      </WebSocketProvider>
    </TransportProvider>
  </StrictMode>,
)
