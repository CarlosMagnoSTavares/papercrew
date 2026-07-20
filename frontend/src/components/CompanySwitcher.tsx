import { useEffect, useRef, useState } from 'react'
import { Company } from '../api'

interface Props {
  companies: Company[]
  activeId: number | null
  onSwitch: (id: number) => void
  onCreate: () => void
}

export default function CompanySwitcher({ companies, activeId, onSwitch, onCreate }: Props) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const active = companies.find((c) => c.id === activeId)

  useEffect(() => {
    const close = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])

  return (
    <div className="switcher" ref={ref}>
      <button className="switcher-trigger" onClick={() => setOpen(!open)}>
        <span className="switcher-avatar">{(active?.name ?? '?').slice(0, 1).toUpperCase()}</span>
        <span className="switcher-name">
          {active?.name ?? 'Select company'}
          {active && active.active_goals > 0 && (
            <span className="switcher-live" title="autopilot working">
              ●
            </span>
          )}
        </span>
        <span className="switcher-caret">{open ? '▴' : '▾'}</span>
      </button>
      {open && (
        <div className="switcher-menu">
          {companies.map((c) => (
            <button
              key={c.id}
              className={`switcher-item ${c.id === activeId ? 'active' : ''}`}
              onClick={() => {
                onSwitch(c.id)
                setOpen(false)
              }}
            >
              <span className="switcher-avatar small">{c.name.slice(0, 1).toUpperCase()}</span>
              <span className="switcher-item-body">
                {c.name}
                <span className="muted small">
                  {c.agents} agents · {c.active_goals} active goal
                  {c.active_goals === 1 ? '' : 's'}
                </span>
              </span>
              {c.active_goals > 0 && <span className="switcher-live">●</span>}
            </button>
          ))}
          <button
            className="switcher-item switcher-new"
            onClick={() => {
              onCreate()
              setOpen(false)
            }}
          >
            + New company
          </button>
        </div>
      )}
    </div>
  )
}
