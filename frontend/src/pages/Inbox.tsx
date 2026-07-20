import { useEffect, useState } from 'react'
import { api, InboxItem } from '../api'

const KIND_META: Record<InboxItem['kind'], { label: string; badge: string }> = {
  review: { label: 'Needs review', badge: 'badge-review' },
  hire: { label: 'Hire request', badge: 'badge-in_progress' },
  failure: { label: 'Run failed', badge: 'badge-failed' },
  unassigned: { label: 'Unassigned', badge: 'badge-todo' },
}

export default function Inbox({ onOpenTask }: { onOpenTask: (taskId: number) => void }) {
  const [items, setItems] = useState<InboxItem[]>([])
  const [error, setError] = useState('')

  const refresh = () => api.inbox().then(setItems).catch(console.error)
  useEffect(() => {
    refresh()
  }, [])

  const act = async (fn: () => Promise<unknown>) => {
    setError('')
    try {
      await fn()
      refresh()
    } catch (err) {
      setError(String(err))
    }
  }

  return (
    <div>
      <h1>Inbox</h1>
      <p className="subtitle">Everything that needs your attention</p>
      {error && <div className="error">{error}</div>}
      {items.length === 0 && (
        <p className="muted">Inbox zero — nothing needs you right now. 🎉</p>
      )}
      <div className="run-list">
        {items.map((item, i) => (
          <div key={`${item.kind}-${item.ref_id}-${i}`} className="run-row">
            <span className={`badge ${KIND_META[item.kind].badge}`}>
              {KIND_META[item.kind].label}
            </span>
            <span className="run-title">
              {item.title}
              <div className="muted small">{item.detail}</div>
            </span>
            {item.kind === 'hire' ? (
              <>
                <button
                  className="btn btn-ok"
                  onClick={() => act(() => api.hires.approve(item.ref_id))}
                >
                  Approve hire
                </button>
                <button
                  className="btn btn-danger"
                  onClick={() => act(() => api.hires.reject(item.ref_id))}
                >
                  Reject
                </button>
              </>
            ) : (
              <button className="btn btn-ghost" onClick={() => onOpenTask(item.ref_id)}>
                Open task →
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
