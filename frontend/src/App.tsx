// ============================================================
// App — 路由 + 响应式外壳
// ============================================================

import React from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { ResponsiveShell } from './components/base/ResponsiveShell'
import { HomePage } from './pages/HomePage'
import { StudioPage } from './pages/StudioPage'

const App: React.FC = () => {
  return (
    <BrowserRouter>
      <ResponsiveShell>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/studio/:discussionId" element={<StudioPage />} />
        </Routes>
      </ResponsiveShell>
    </BrowserRouter>
  )
}

export default App
