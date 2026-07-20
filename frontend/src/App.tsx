import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import Onboarding from './pages/Onboarding'
import Goals from './pages/Goals'
import Dashboard from './pages/Dashboard'
import Inbox from './pages/Inbox'
import Chat from './pages/Chat'
import Plans from './pages/Plans'
import Agents from './pages/Agents'
import Board from './pages/Board'
import Routines from './pages/Routines'
import RunsPage from './pages/RunsPage'
import WorkProducts from './pages/WorkProducts'
import SettingsPage from './pages/Settings'

type Page =
  | 'dashboard'
  | 'goals'
  | 'inbox'
  | 'chat'
  | 'plans'
  | 'agents'
  | 'board'
  | 'routines'
  | 'runs'
  | 'products'
  | 'settings'

const NAV: { id: Page; label: string; icon: string }[] = [
  { id: 'dashboard', label: 'Dashboard', icon: '◧' },
  { id: 'goals', label: 'Goals', icon: '🎯' },
  { id: 'inbox', label: 'Inbox', icon: '◈' },
  { id: 'chat', label: 'CEO Chat', icon: '💬' },
  { id: 'plans', label: 'Plans', icon: '☰' },
  { id: 'board', label: 'Task Board', icon: '▤' },
  { id: 'agents', label: 'Agents', icon: '◉' },
  { id: 'routines', label: 'Routines', icon: '↻' },
  { id: 'runs', label: 'Run History', icon: '▶' },
  { id: 'products', label: 'Deliverables', icon: '⬡' },
  { id: 'settings', label: 'Settings', icon: '⚙' },
]

export default function App() {
  const [page, setPage] = useState<Page>('dashboard')
  const [company, setCompany] = useState('PaperCrew')
  const [onboarded, setOnboarded] = useState<boolean | null>(null)
  const [inboxCount, setInboxCount] = useState(0)
  const [openTaskId, setOpenTaskId] = useState<number | null>(null)

  const refreshBadge = useCallback(() => {
    api.inbox()
      .then((items) => setInboxCount(items.length))
      .catch(() => undefined)
  }, [])

  useEffect(() => {
    api.company
      .get()
      .then((c) => {
        setOnboarded(c.onboarded)
        if (c.onboarded && c.company_name) setCompany(c.company_name)
      })
      .catch(() => setOnboarded(true))
    refreshBadge()
    const timer = window.setInterval(refreshBadge, 10000)
    return () => window.clearInterval(timer)
  }, [page, refreshBadge])

  if (onboarded === null) return null
  if (!onboarded) {
    return (
      <Onboarding
        onDone={() => {
          setOnboarded(true)
          setPage('goals')
        }}
      />
    )
  }

  const openTask = (taskId: number) => {
    setOpenTaskId(taskId)
    setPage('board')
  }

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
              {item.id === 'inbox' && inboxCount > 0 && (
                <span className="nav-badge">{inboxCount}</span>
              )}
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
        {page === 'goals' && <Goals />}
        {page === 'inbox' && <Inbox onOpenTask={openTask} />}
        {page === 'chat' && <Chat />}
        {page === 'plans' && <Plans />}
        {page === 'agents' && <Agents />}
        {page === 'board' && (
          <Board openTaskId={openTaskId} onTaskOpened={() => setOpenTaskId(null)} />
        )}
        {page === 'routines' && <Routines />}
        {page === 'runs' && <RunsPage />}
        {page === 'products' && <WorkProducts />}
        {page === 'settings' && <SettingsPage />}
      </main>
    </div>
  )
}
