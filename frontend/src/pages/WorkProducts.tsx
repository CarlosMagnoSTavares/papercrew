import { useEffect, useState } from 'react'
import { api, WorkProduct } from '../api'
import { EmptyState } from '../ui'

export default function WorkProducts() {
  const [products, setProducts] = useState<WorkProduct[]>([])
  const [open, setOpen] = useState<WorkProduct | null>(null)

  useEffect(() => {
    api.workProducts().then(setProducts).catch(console.error)
  }, [])

  const download = (p: WorkProduct) => {
    const blob = new Blob([`# ${p.title}\n\nBy ${p.agent}\n\n${p.output}`], {
      type: 'text/markdown',
    })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `${p.title.replace(/[^a-z0-9]+/gi, '-').toLowerCase()}.md`
    a.click()
    URL.revokeObjectURL(a.href)
  }

  return (
    <div>
      <h1>Deliverables</h1>
      <p className="subtitle">Approved work products from your crew</p>
      {products.length === 0 && (
        <EmptyState
          icon="⬡"
          title="No deliverables yet"
          hint="Approve a task in review to collect its output here."
        />
      )}
      <div className="card-grid">
        {products.map((p) => (
          <div key={p.task_id} className="agent-card">
            <h3>{p.title}</h3>
            <div className="agent-role">by {p.agent}</div>
            <p className="muted small">{p.output.slice(0, 140)}…</p>
            <div className="card-actions">
              <button className="btn btn-ghost" onClick={() => setOpen(p)}>
                View
              </button>
              <button className="btn btn-primary" onClick={() => download(p)}>
                ⬇ Download .md
              </button>
            </div>
          </div>
        ))}
      </div>

      {open && (
        <div className="modal-backdrop" onClick={() => setOpen(null)}>
          <div className="modal modal-wide" onClick={(e) => e.stopPropagation()}>
            <div className="page-header">
              <h2>{open.title}</h2>
              <button className="btn btn-ghost" onClick={() => setOpen(null)}>
                ✕
              </button>
            </div>
            <p className="muted small">
              by {open.agent} · approved {new Date(open.approved_at).toLocaleString()}
            </p>
            <pre className="output plan-content">{open.output}</pre>
          </div>
        </div>
      )}
    </div>
  )
}
