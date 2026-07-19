import { FormEvent, useEffect, useRef, useState } from 'react'
import { api, Agent, Comment, Run, Task } from '../api'

interface Props {
  task: Task
  agents: Agent[]
  allTasks: Task[]
  onClose: () => void
  onChanged: () => void
}

export default function TaskDrawer({ task, agents, allTasks, onClose, onChanged }: Props) {
  const [runs, setRuns] = useState<Run[]>([])
  const [comments, setComments] = useState<Comment[]>([])
  const [newComment, setNewComment] = useState('')
  const [rejectFeedback, setRejectFeedback] = useState('')
  const [showReject, setShowReject] = useState(false)
  const [error, setError] = useState('')
  const pollRef = useRef<number | null>(null)

  const latest = runs[0]
  const depIds = task.depends_on.split(',').filter(Boolean).map(Number)

  const loadAll = () => {
    api.tasks.runs(task.id).then(setRuns).catch(console.error)
    api.tasks.comments(task.id).then(setComments).catch(console.error)
  }

  useEffect(() => {
    loadAll()
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [task.id])

  useEffect(() => {
    if (latest?.status === 'running' && pollRef.current === null) {
      pollRef.current = window.setInterval(async () => {
        const updated = await api.runs.get(latest.id)
        setRuns((prev) => [updated, ...prev.slice(1)])
        if (updated.status !== 'running' && pollRef.current) {
          window.clearInterval(pollRef.current)
          pollRef.current = null
          onChanged()
        }
      }, 1000)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [latest?.id, latest?.status])

  const act = async (fn: () => Promise<unknown>) => {
    setError('')
    try {
      await fn()
      loadAll()
      onChanged()
    } catch (err) {
      setError(String(err))
    }
  }

  const runTask = () =>
    act(async () => {
      const run = await api.tasks.run(task.id)
      setRuns((prev) => [run, ...prev])
    })

  const submitComment = (e: FormEvent) => {
    e.preventDefault()
    if (!newComment.trim()) return
    act(() => api.tasks.addComment(task.id, newComment)).then(() => setNewComment(''))
  }

  const submitReject = (e: FormEvent) => {
    e.preventDefault()
    if (!rejectFeedback.trim()) return
    act(() => api.tasks.reject(task.id, rejectFeedback, true)).then(() => {
      setShowReject(false)
      setRejectFeedback('')
    })
  }

  const removeTask = async () => {
    if (!confirm(`Delete task "${task.title}"?`)) return
    await api.tasks.remove(task.id)
    onClose()
    onChanged()
  }

  const toggleDep = (depId: number) => {
    const next = depIds.includes(depId)
      ? depIds.filter((d) => d !== depId)
      : [...depIds, depId]
    act(() => api.tasks.patch(task.id, { depends_on: next.join(',') }))
  }

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <div className="drawer" onClick={(e) => e.stopPropagation()}>
        <div className="drawer-header">
          <h2>{task.title}</h2>
          <button className="btn btn-ghost" onClick={onClose}>
            ✕
          </button>
        </div>
        <div>
          <span className={`badge badge-${task.status}`}>{task.status}</span>{' '}
          <span className="chip">{task.crew_mode}</span>
        </div>
        <p className="muted">{task.description || 'No description'}</p>
        {task.feedback && (
          <div className="banner">Pending feedback: {task.feedback}</div>
        )}

        <label>
          Assigned agent
          <select
            value={task.agent_id ?? ''}
            onChange={(e) =>
              act(() =>
                api.tasks.patch(task.id, {
                  agent_id: e.target.value ? Number(e.target.value) : null,
                }),
              )
            }
          >
            <option value="">— unassigned —</option>
            {agents.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name} ({a.role})
              </option>
            ))}
          </select>
        </label>

        <label>
          Crew mode
          <select
            value={task.crew_mode}
            onChange={(e) => act(() => api.tasks.patch(task.id, { crew_mode: e.target.value as Task['crew_mode'] }))}
          >
            <option value="solo">solo — assigned agent only</option>
            <option value="hierarchical">hierarchical — CEO delegates to whole crew</option>
          </select>
        </label>

        <div>
          <div className="field-label">Dependencies (must be done before running)</div>
          <div className="dep-list">
            {allTasks
              .filter((t) => t.id !== task.id)
              .map((t) => (
                <label key={t.id} className="dep-item">
                  <input
                    type="checkbox"
                    checked={depIds.includes(t.id)}
                    onChange={() => toggleDep(t.id)}
                  />
                  #{t.id} {t.title} <span className={`badge badge-${t.status}`}>{t.status}</span>
                </label>
              ))}
            {allTasks.length <= 1 && <span className="muted small">No other tasks</span>}
          </div>
        </div>

        {error && <div className="error">{error}</div>}
        <div className="drawer-actions">
          <button
            className="btn btn-primary"
            onClick={runTask}
            disabled={latest?.status === 'running'}
          >
            {latest?.status === 'running' ? 'Running…' : '▶ Run with CrewAI'}
          </button>
          {task.status === 'review' && (
            <>
              <button className="btn btn-ok" onClick={() => act(() => api.tasks.approve(task.id))}>
                ✔ Approve
              </button>
              <button className="btn btn-warn" onClick={() => setShowReject(!showReject)}>
                ✎ Request changes
              </button>
            </>
          )}
          <button className="btn btn-danger" onClick={removeTask}>
            Delete
          </button>
        </div>

        {showReject && (
          <form onSubmit={submitReject} className="reject-form">
            <textarea
              value={rejectFeedback}
              onChange={(e) => setRejectFeedback(e.target.value)}
              placeholder="What should change? The agent re-runs with this feedback."
              rows={2}
            />
            <button className="btn btn-warn">Send feedback & re-run</button>
          </form>
        )}

        {latest && (
          <div className="run-panel">
            <div className="run-panel-header">
              Latest run <span className={`badge badge-${latest.status}`}>{latest.status}</span>
              <span className="muted small">
                {latest.prompt_tokens + latest.completion_tokens} tok
                {latest.tokens_saved > 0 && ` · optimizer saved ~${latest.tokens_saved}`}
                {latest.cost > 0 && ` · $${latest.cost}`}
              </span>
            </div>
            {latest.log && <pre className="log">{latest.log}</pre>}
            {latest.output && (
              <>
                <h4>Output</h4>
                <pre className="output">{latest.output}</pre>
              </>
            )}
            {latest.error && <div className="error">{latest.error}</div>}
          </div>
        )}

        <div>
          <div className="field-label">Comments</div>
          <div className="comment-list">
            {comments.map((c) => (
              <div key={c.id} className="comment">
                <span className="comment-author">{c.author}</span> {c.body}
              </div>
            ))}
            {comments.length === 0 && <span className="muted small">No comments yet</span>}
          </div>
          <form onSubmit={submitComment} className="comment-form">
            <input
              value={newComment}
              onChange={(e) => setNewComment(e.target.value)}
              placeholder="Add a comment…"
            />
            <button className="btn btn-ghost">Post</button>
          </form>
        </div>
      </div>
    </div>
  )
}
