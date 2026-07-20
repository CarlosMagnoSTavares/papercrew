import { FormEvent, useEffect, useState } from 'react'
import { api, Goal, Task } from '../api'
import { EmptyState, useToast } from '../ui'

export default function Goals() {
  const [goals, setGoals] = useState<Goal[]>([])
  const [tasksByGoal, setTasksByGoal] = useState<Record<number, Task[]>>({})
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ title: '', description: '' })
  const toast = useToast()

  const refresh = async () => {
    const list = await api.goals.list()
    setGoals(list)
    const entries = await Promise.all(
      list.map(async (g) => [g.id, await api.goals.tasks(g.id)] as const),
    )
    setTasksByGoal(Object.fromEntries(entries))
  }

  useEffect(() => {
    refresh().catch(console.error)
    const timer = window.setInterval(() => refresh().catch(() => undefined), 4000)
    return () => window.clearInterval(timer)
  }, [])

  const create = async (e: FormEvent) => {
    e.preventDefault()
    await api.goals.create(form)
    setForm({ title: '', description: '' })
    setShowForm(false)
    toast('success', `Goal created: ${form.title} — autopilot will start planning`)
    refresh()
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Goals</h1>
          <p className="subtitle">
            Autopilot works toward each active goal — running, reviewing and planning
            complementary tasks until it's achieved
          </p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowForm(true)}>
          + New goal
        </button>
      </div>

      {goals.length === 0 && (
        <EmptyState
          icon="🎯"
          title="No goals yet"
          hint="Create a goal and the autopilot will plan and work toward it on its own."
          action={
            <button className="btn btn-primary" onClick={() => setShowForm(true)}>
              + New goal
            </button>
          }
        />
      )}
      <div className="goal-list">
        {goals.map((goal) => {
          const tasks = tasksByGoal[goal.id] ?? []
          const done = tasks.filter((t) => t.status === 'done').length
          return (
            <div key={goal.id} className="goal-card">
              <div className="goal-head">
                <h3>
                  🎯 {goal.title}{' '}
                  <span
                    className={`badge ${
                      goal.status === 'achieved'
                        ? 'badge-completed'
                        : goal.status === 'active'
                          ? 'badge-in_progress'
                          : 'badge-todo'
                    }`}
                  >
                    {goal.status}
                  </span>
                </h3>
                <div className="card-actions">
                  {goal.status === 'active' && (
                    <button className="btn btn-warn" onClick={() => api.goals.pause(goal.id).then(refresh)}>
                      Pause
                    </button>
                  )}
                  {goal.status === 'paused' && (
                    <button className="btn btn-ok" onClick={() => api.goals.resume(goal.id).then(refresh)}>
                      Resume
                    </button>
                  )}
                </div>
              </div>
              {goal.description && <p className="muted small">{goal.description}</p>}
              <div className="progress-track">
                <div
                  className={`progress-fill ${goal.status === 'achieved' ? 'done' : ''}`}
                  style={{ width: `${goal.progress}%` }}
                />
              </div>
              <div className="muted small">
                {goal.progress}% · {done}/{tasks.length} tasks done · planning cycle {goal.cycle}
                {goal.status === 'active' && ' · autopilot working…'}
              </div>
              <div className="goal-tasks">
                {tasks.map((t) => (
                  <span key={t.id} className={`chip goal-task-${t.status}`}>
                    {t.status === 'done' ? '✔' : t.status === 'in_progress' ? '▶' : '○'} {t.title}
                  </span>
                ))}
              </div>
            </div>
          )
        })}
      </div>

      {showForm && (
        <div className="modal-backdrop" onClick={() => setShowForm(false)}>
          <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={create}>
            <h2>New goal</h2>
            <p className="muted small">
              The autopilot will plan tasks toward this goal on its next cycle.
            </p>
            <label>
              Goal
              <input
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                required
              />
            </label>
            <label>
              Context
              <textarea
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                rows={2}
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
