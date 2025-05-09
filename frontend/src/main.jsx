// Import tailwind first
import './index.css'    // Then custom base styles
// import './App.css'   // Then component styles if needed

import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
