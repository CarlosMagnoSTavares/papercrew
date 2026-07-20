import { useEffect, useState } from 'react'
import { api, Run, Task } from '../api'
import { EmptyState, timeAgo } from '../ui'

type Filter = 'all' | 'running' | 'completed' | 'failed'

export default function RunsPage() {
  const [runs, setRuns] = useState<Run[]>([])
  const [tasks, setTasks] = useState<Task[]>([])
  const [filter, setFilter] = useState<Filter>('all')
  const [open, setOpen] = useState<Run | null>(null)

  useEffect(() => {
    api.runs.list().then(setRuns).catch(console.error)
    api.tasks.list().then(setTasks).catch(console.error)
  }, [])

  const visible = runs.filter((r) => filter === 'all' || r.status === filter)
  const taskTitle = (id: number) => tasks.find((t) => t.id === id)?.title ?? `Task #${id}`

  return (
    <div>
      <h1>Run History</h1>
      <p className="subtitle">Every crew execution with tokens, savings and cost</p>
      <div className="filter-bar">
        {(['all', 'running', 'completed', 'failed'] as Filter[]).map((f) => (
          <button
            key={f}
            className={`btn ${filter === f ? 'btn-primary' : 'btn-ghost'}`}
            onClick={() => setFilter(f)}
          >
            {f} ({f === 'all' ? runs.length : runs.filter((r) => r.status === f).length})
          </button>
        ))}
      </div>
      <div className="run-list">
        {visible.map((run) => (
          <div key={run.id} className="run-row clickable" onClick={() => setOpen(run)}>
            <span className={`badge badge-${run.status}`}>{run.status}</span>
            <span className="run-title">
              #{run.id} · {taskTitle(run.task_id)}
            </span>
            <span className="muted small">
              {run.prompt_tokens + run.completion_tokens} tok
              {run.tokens_saved > 0 && ` · saved ${run.tokens_saved}`}
              {run.cost > 0 && ` · $${run.cost}`}
            </span>
            <span className="muted small" title={new Date(run.started_at).toLocaleString()}>
              {timeAgo(run.started_at)}
            </span>
          </div>
        ))}
        {visible.length === 0 && runs.length === 0 && (
          <EmptyState icon="▶" title="No runs yet" hint="Run a task to see its history here." />
        )}
        {visible.length === 0 && runs.length > 0 && (
          <p className="muted">No runs match this filter.</p>
        )}
      </div>

      {open && (
        <div className="modal-backdrop" onClick={() => setOpen(null)}>
          <div className="modal modal-wide" onClick={(e) => e.stopPropagation()}>
            <div className="page-header">
              <h2>
                Run #{open.id} <span className={`badge badge-${open.status}`}>{open.status}</span>
              </h2>
              <button className="btn btn-ghost" onClick={() => setOpen(null)}>
                ✕
              </button>
            </div>
            <p className="muted small">
              {taskTitle(open.task_id)} · {open.prompt_tokens} prompt + {open.completion_tokens}{' '}
              completion tokens · optimizer saved ~{open.tokens_saved} · ${open.cost}
            </p>
            {open.log && <pre className="log">{open.log}</pre>}
            {open.output && <pre className="output">{open.output}</pre>}
            {open.error && <div className="error">{open.error}</div>}
          </div>
        </div>
      )}
    </div>
  )
}
