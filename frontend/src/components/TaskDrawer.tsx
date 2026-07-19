import { useEffect, useRef, useState } from 'react'
import { api, Agent, Run, Task } from '../api'

interface Props {
  task: Task
  agents: Agent[]
  onClose: () => void
  onChanged: () => void
}

export default function TaskDrawer({ task, agents, onClose, onChanged }: Props) {
  const [runs, setRuns] = useState<Run[]>([])
  const [error, setError] = useState('')
  const pollRef = useRef<number | null>(null)

  const latest = runs[0]

  const loadRuns = () => api.tasks.runs(task.id).then(setRuns).catch(console.error)

  useEffect(() => {
    loadRuns()
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

  const runTask = async () => {
    setError('')
    try {
      const run = await api.tasks.run(task.id)
      setRuns((prev) => [run, ...prev])
      onChanged()
    } catch (err) {
      setError(String(err))
    }
  }

  const assign = async (value: string) => {
    await api.tasks.patch(task.id, { agent_id: value ? Number(value) : null })
    onChanged()
  }

  const removeTask = async () => {
    if (!confirm(`Delete task "${task.title}"?`)) return
    await api.tasks.remove(task.id)
    onClose()
    onChanged()
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
        <span className={`badge badge-${task.status}`}>{task.status}</span>
        <p className="muted">{task.description || 'No description'}</p>

        <label>
          Assigned agent
          <select value={task.agent_id ?? ''} onChange={(e) => assign(e.target.value)}>
            <option value="">— unassigned —</option>
            {agents.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name} ({a.role})
              </option>
            ))}
          </select>
        </label>

        {error && <div className="error">{error}</div>}
        <div className="drawer-actions">
          <button
            className="btn btn-primary"
            onClick={runTask}
            disabled={latest?.status === 'running'}
          >
            {latest?.status === 'running' ? 'Running…' : '▶ Run with CrewAI'}
          </button>
          <button className="btn btn-danger" onClick={removeTask}>
            Delete
          </button>
        </div>

        {latest && (
          <div className="run-panel">
            <div className="run-panel-header">
              Latest run <span className={`badge badge-${latest.status}`}>{latest.status}</span>
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
        {runs.length > 1 && <p className="muted small">{runs.length} runs total</p>}
      </div>
    </div>
  )
}
