import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './styles/indicator.css'
import IndicatorApp from './IndicatorApp'

createRoot(document.getElementById('indicator-root')!).render(
  <StrictMode>
    <IndicatorApp />
  </StrictMode>,
)
