import React from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import AlertsPage from './pages/AlertsPage'
import AlertDetail from './pages/AlertDetail'
import './index.css'

function App(){
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<AlertsPage/>} />
        <Route path="/alerts/:id" element={<AlertDetail/>} />
      </Routes>
    </BrowserRouter>
  )
}

createRoot(document.getElementById('root')).render(<App />)
