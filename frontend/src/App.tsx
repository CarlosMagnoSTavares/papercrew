import { useState } from 'react'
import Dashboard from './pages/Dashboard'
import Agents from './pages/Agents'
import Board from './pages/Board'
import SettingsPage from './pages/Settings'

type Page = 'dashboard' | 'agents' | 'board' | 'settings'

const NAV: { id: Page; label: string; icon: string }[] = [
  { id: 'dashboard', label: 'Dashboard', icon: '◧' },
  { id: 'agents', label: 'Agents', icon: '◉' },
  { id: 'board', label: 'Task Board', icon: '▤' },
  { id: 'settings', label: 'Settings', icon: '⚙' },
]

export default function App() {
  const [page, setPage] = useState<Page>('dashboard')

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="logo">
          <span className="logo-mark">📎</span>
          <span className="logo-text">PaperCrew</span>
        </div>
        <nav>
          {NAV.map((item) => (
            <button
              key={item.id}
              className={`nav-item ${page === item.id ? 'active' : ''}`}
              onClick={() => setPage(item.id)}
            >
              <span className="nav-icon">{item.icon}</span>
              {item.label}
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          CrewAI + OpenRouter
          <br />
          open source
        </div>
      </aside>
      <main className="content">
        {page === 'dashboard' && <Dashboard />}
        {page === 'agents' && <Agents />}
        {page === 'board' && <Board />}
        {page === 'settings' && <SettingsPage />}
      </main>
    </div>
  )
}
