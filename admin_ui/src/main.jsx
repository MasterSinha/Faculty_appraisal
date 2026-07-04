import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import './styles/global'
import App from './App'
import { ThemeProvider } from './context/ThemeContext'

// ── Anti-tamper guards ─────────────────────────────────────────────────────────
;(function () {
  // 1. Disable right-click context menu
  document.addEventListener('contextmenu', e => e.preventDefault())

  // 2. Block DevTools keyboard shortcuts
  document.addEventListener('keydown', e => {
    const ctrl  = e.ctrlKey  || e.metaKey
    const shift = e.shiftKey
    const key   = e.key

    // F12
    if (key === 'F12') { e.preventDefault(); return }

    // Ctrl+Shift+I / Ctrl+Shift+J / Ctrl+Shift+C  (DevTools panels)
    if (ctrl && shift && ['I','J','C'].includes(key.toUpperCase())) { e.preventDefault(); return }

    // Ctrl+U  (View Source)
    if (ctrl && key.toUpperCase() === 'U') { e.preventDefault(); return }

    // Ctrl+S  (Save page)
    if (ctrl && key.toUpperCase() === 'S') { e.preventDefault(); return }

    // Ctrl+P  (Print — exposes DOM)
    if (ctrl && key.toUpperCase() === 'P') { e.preventDefault(); return }
  })

  // 3. Disable text selection on non-input elements (makes DOM scraping harder)
  document.addEventListener('selectstart', e => {
    const tag = e.target?.tagName?.toLowerCase()
    if (!['input', 'textarea'].includes(tag)) e.preventDefault()
  })

  // 4. DevTools size-change detection — temporarily disabled for debugging
  /*
  const threshold = 160
  const detect = () => {
    const widthDiff  = window.outerWidth  - window.innerWidth
    const heightDiff = window.outerHeight - window.innerHeight
    if (widthDiff > threshold || heightDiff > threshold) {
      document.body.innerHTML = ''
      window.location.replace('/panel/login')
    }
  }
  setInterval(detect, 1000)
  */
})()

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ThemeProvider>
      <BrowserRouter basename="/panel">
        <App />
      </BrowserRouter>
    </ThemeProvider>
  </React.StrictMode>
)
