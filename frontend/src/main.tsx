import './polyfills'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { TransportProvider } from './transport'
import { AppSessionProvider } from './context/AppSessionContext.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <TransportProvider>
      <AppSessionProvider>
        <App />
      </AppSessionProvider>
    </TransportProvider>
  </StrictMode>,
)
