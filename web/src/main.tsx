import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import './neat-annotations.css'
import App from './App.tsx'

function renderRoot() {
  const root = document.getElementById('root')!;
  root.innerHTML = '';
  createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
  );
}

renderRoot();
// Re-render on browser navigation (back/forward).
window.addEventListener('popstate', renderRoot);
