import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
// Bundled with the app and served by us, so no request goes to a font service (KVKK).
import '@fontsource-variable/bricolage-grotesque'
import './index.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
