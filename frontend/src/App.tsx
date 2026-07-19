import { useEffect, useState } from 'react'
import { api } from './api'
import Dashboard from './pages/Dashboard'
import Agents from './pages/Agents'
import Board from './pages/Board'
import Chat from './pages/Chat'
import Routines from './pages/Routines'
import SettingsPage from './pages/Settings'

type Page = 'dashboard' | 'chat' | 'agents' | 'board' | 'routines' | 'settings'

const NAV: { id: Page; label: string; icon: string }[] = [
  { id: 'dashboard', label: 'Dashboard', icon: '◧' },
  { id: 'chat', label: 'CEO Chat', icon: '💬' },
  { id: 'agents', label: 'Agents', icon: '◉' },
  { id: 'board', label: 'Task Board', icon: '▤' },
  { id: 'routines', label: 'Routines', icon: '↻' },
  { id: 'settings', label: 'Settings', icon: '⚙' },
]

export default function App() {
  const [page, setPage] = useState<Page>('dashboard')
  const [company, setCompany] = useState('PaperCrew')

  useEffect(() => {
    api.settings
      .get()
      .then((s) => setCompany(s.company_name))
      .catch(() => undefined)
  }, [page])

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="logo">
          <span className="logo-mark">📎</span>
          <span className="logo-text">PaperCrew</span>
        </div>
        <div className="company-name">{company}</div>
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
          native token optimizer
        </div>
      </aside>
      <main className="content">
        {page === 'dashboard' && <Dashboard />}
        {page === 'chat' && <Chat />}
        {page === 'agents' && <Agents />}
        {page === 'board' && <Board />}
        {page === 'routines' && <Routines />}
        {page === 'settings' && <SettingsPage />}
      </main>
    </div>
  )
}
