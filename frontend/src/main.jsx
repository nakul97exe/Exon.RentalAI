import esriConfig from '@arcgis/core/config.js'
// Must match the installed @arcgis/core version — bump this string on upgrade.
esriConfig.assetsPath = "https://js.arcgis.com/4.31/@arcgis/core/assets";

import '@arcgis/core/assets/esri/themes/dark/main.css';
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
