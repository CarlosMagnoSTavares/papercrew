import { useCallback, useEffect, useRef, useState } from 'react'
import { api, Company, getActiveCompanyId, Goal, setActiveCompanyId } from './api'
import { useToast } from './ui'
import CompanySwitcher from './components/CompanySwitcher'
import Onboarding from './pages/Onboarding'
import Companies from './pages/Companies'
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
  | 'companies'
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
  { id: 'companies', label: 'Companies', icon: '🏢' },
  { id: 'settings', label: 'Settings', icon: '⚙' },
]

export default function App() {
  const [page, setPage] = useState<Page>('dashboard')
  const [companies, setCompanies] = useState<Company[] | null>(null)
  const [activeId, setActiveId] = useState<number | null>(getActiveCompanyId())
  const [creating, setCreating] = useState(false)
  const [inboxCount, setInboxCount] = useState(0)
  const [openTaskId, setOpenTaskId] = useState<number | null>(null)
  const [activeGoal, setActiveGoal] = useState<Goal | null>(null)
  const toast = useToast()
  const lastEventId = useRef<number | null>(null)

  const loadCompanies = useCallback(async () => {
    const list = await api.companies.list()
    setCompanies(list)
    setActiveId((current) => {
      const stillThere = list.some((c) => c.id === current)
      const next = stillThere ? current : (list[0]?.id ?? null)
      setActiveCompanyId(next)
      return next
    })
    return list
  }, [])

  useEffect(() => {
    loadCompanies().catch(() => setCompanies([]))
  }, [loadCompanies])

  const refreshBadge = useCallback(() => {
    if (!activeId) return
    api.inbox()
      .then((items) => setInboxCount(items.length))
      .catch(() => undefined)
  }, [activeId])

  useEffect(() => {
    refreshBadge()
    const timer = window.setInterval(refreshBadge, 10000)
    return () => window.clearInterval(timer)
  }, [page, refreshBadge])

  // Live company pulse: surface autopilot/goal/hire events of the active
  // company as toasts, and keep the sidebar goal widget fresh.
  useEffect(() => {
    if (!activeId) return
    const NOTIFY = new Set(['autopilot', 'goal', 'hire', 'company'])
    lastEventId.current = null
    const pulse = async () => {
      try {
        const [events, goals] = await Promise.all([api.events(), api.goals.list()])
        setActiveGoal(goals.find((g) => g.status === 'active') ?? null)
        if (lastEventId.current === null) {
          lastEventId.current = events[0]?.id ?? 0
          return
        }
        const fresh = events.filter((e) => e.id > (lastEventId.current ?? 0)).reverse()
        lastEventId.current = events[0]?.id ?? lastEventId.current
        for (const event of fresh.slice(-3)) {
          if (!NOTIFY.has(event.kind)) continue
          toast(event.message.startsWith('🎯') ? 'success' : 'info', event.message)
        }
      } catch {
        /* backend briefly unreachable — skip this pulse */
      }
    }
    pulse()
    const timer = window.setInterval(pulse, 6000)
    return () => window.clearInterval(timer)
  }, [toast, activeId])

  const switchCompany = (id: number) => {
    setActiveCompanyId(id)
    setActiveId(id)
    setActiveGoal(null)
    setInboxCount(0)
    setPage('dashboard')
    const name = companies?.find((c) => c.id === id)?.name
    if (name) toast('info', `Switched to ${name}`)
  }

  const openTask = (taskId: number) => {
    setOpenTaskId(taskId)
    setPage('board')
  }

  if (companies === null) return null

  // First run, or the user explicitly asked for another company.
  if (creating || companies.length === 0) {
    return (
      <Onboarding
        canCancel={companies.length > 0}
        onCancel={() => setCreating(false)}
        onDone={async (newCompanyId) => {
          setCreating(false)
          await loadCompanies()
          setActiveCompanyId(newCompanyId)
          setActiveId(newCompanyId)
          setPage('goals')
        }}
      />
    )
  }

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="logo">
          <span className="logo-mark">📎</span>
          <span className="logo-text">PaperCrew</span>
        </div>
        <CompanySwitcher
          companies={companies}
          activeId={activeId}
          onSwitch={switchCompany}
          onCreate={() => setCreating(true)}
        />
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
        {activeGoal && (
          <button className="sidebar-goal" onClick={() => setPage('goals')}>
            <span className="small">🎯 {activeGoal.title}</span>
            <div className="progress-track slim">
              <div className="progress-fill" style={{ width: `${activeGoal.progress}%` }} />
            </div>
            <span className="muted small">{activeGoal.progress}% · autopilot on</span>
          </button>
        )}
        <div className="sidebar-footer">
          CrewAI + OpenRouter
          <br />
          native token optimizer
        </div>
      </aside>
      {/* keyed by company so every page refetches when you switch */}
      <main className="content" key={activeId ?? 'none'}>
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
        {page === 'companies' && (
          <Companies
            activeId={activeId}
            onSwitch={switchCompany}
            onCreate={() => setCreating(true)}
            onChanged={loadCompanies}
          />
        )}
        {page === 'settings' && <SettingsPage />}
      </main>
    </div>
  )
}
