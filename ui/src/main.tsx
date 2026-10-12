import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { initializeAuthentication } from './auth/keycloak'
import { ToastProvider } from './components/toast/ToastProvider.tsx'

const root = createRoot(document.getElementById('root')!)

const start = async () => {
  try {
    await initializeAuthentication()
    // Keycloak handles its callback URL before React Router reads it.
    const { default: App } = await import('./App.tsx')
    root.render(<StrictMode><ToastProvider><App /></ToastProvider></StrictMode>)
  } catch {
    root.render(<main role="alert"><p>Unable to connect to sign-in.</p>
      <button onClick={() => window.location.reload()}>Try again</button></main>)
  }
}

void start()
