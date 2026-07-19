import { FormEvent, useEffect, useState } from 'react'
import { api, Agent, Routine } from '../api'

const EMPTY = { title: '', description: '', agent_id: '', interval_minutes: 60 }

export default function Routines() {
  const [routines, setRoutines] = useState<Routine[]>([])
  const [agents, setAgents] = useState<Agent[]>([])
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState(EMPTY)

  const refresh = () => api.routines.list().then(setRoutines).catch(console.error)
  useEffect(() => {
    refresh()
    api.agents.list().then(setAgents)
  }, [])

  const create = async (e: FormEvent) => {
    e.preventDefault()
    await api.routines.create({
      title: form.title,
      description: form.description,
      agent_id: form.agent_id ? Number(form.agent_id) : null,
      interval_minutes: form.interval_minutes,
    })
    setForm(EMPTY)
    setShowForm(false)
    refresh()
  }

  const toggle = async (r: Routine) => {
    await api.routines.update(r.id, { ...r, enabled: !r.enabled })
    refresh()
  }

  const remove = async (r: Routine) => {
    if (!confirm(`Delete routine "${r.title}"?`)) return
    await api.routines.remove(r.id)
    refresh()
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Routines</h1>
          <p className="subtitle">Recurring work — fires a task automatically on schedule</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowForm(true)}>
          + New routine
        </button>
      </div>

      <div className="run-list">
        {routines.map((r) => {
          const agent = agents.find((a) => a.id === r.agent_id)
          return (
            <div key={r.id} className="run-row">
              <span className={`badge ${r.enabled ? 'badge-completed' : 'badge-todo'}`}>
                {r.enabled ? 'active' : 'paused'}
              </span>
              <span className="run-title">
                {r.title}
                <span className="muted small">
                  {' '}
                  · every {r.interval_minutes}m · {agent ? agent.name : 'unassigned'}
                </span>
              </span>
              <span className="muted small">next: {new Date(r.next_run_at).toLocaleTimeString()}</span>
              <button className="btn btn-ghost" onClick={() => toggle(r)}>
                {r.enabled ? 'Pause' : 'Resume'}
              </button>
              <button className="btn btn-danger" onClick={() => remove(r)}>
                Delete
              </button>
            </div>
          )
        })}
        {routines.length === 0 && <p className="muted">No routines yet.</p>}
      </div>

      {showForm && (
        <div className="modal-backdrop" onClick={() => setShowForm(false)}>
          <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={create}>
            <h2>New routine</h2>
            <label>
              Title
              <input
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                required
              />
            </label>
            <label>
              Description
              <textarea
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                rows={2}
              />
            </label>
            <label>
              Agent
              <select
                value={form.agent_id}
                onChange={(e) => setForm({ ...form, agent_id: e.target.value })}
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
              Interval (minutes)
              <input
                type="number"
                min={1}
                value={form.interval_minutes}
                onChange={(e) => setForm({ ...form, interval_minutes: Number(e.target.value) })}
              />
            </label>
            <div className="modal-actions">
              <button type="button" className="btn btn-ghost" onClick={() => setShowForm(false)}>
                Cancel
              </button>
              <button type="submit" className="btn btn-primary">
                Create
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}
