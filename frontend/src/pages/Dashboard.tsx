import { useEffect, useState } from 'react'
import { api, AppEvent, Goal, Run, Stats, Task } from '../api'

export default function Dashboard() {
  const [tasks, setTasks] = useState<Task[]>([])
  const [runs, setRuns] = useState<Run[]>([])
  const [stats, setStats] = useState<Stats | null>(null)
  const [events, setEvents] = useState<AppEvent[]>([])
  const [goals, setGoals] = useState<Goal[]>([])
  const [agentCount, setAgentCount] = useState(0)

  useEffect(() => {
    const load = () => {
      api.agents.list().then((a) => setAgentCount(a.length)).catch(console.error)
      api.tasks.list().then(setTasks).catch(console.error)
      api.runs.list().then(setRuns).catch(console.error)
      api.stats().then(setStats).catch(console.error)
      api.events().then(setEvents).catch(console.error)
      api.goals.list().then(setGoals).catch(console.error)
    }
    load()
    const timer = window.setInterval(load, 5000)
    return () => window.clearInterval(timer)
  }, [])

  const byStatus = (s: Task['status']) => tasks.filter((t) => t.status === s).length

  return (
    <div>
      <h1>Dashboard</h1>
      <p className="subtitle">Your AI company at a glance</p>
      {goals
        .filter((g) => g.status === 'active')
        .map((g) => (
          <div key={g.id} className="goal-banner">
            <span>🎯 {g.title}</span>
            <div className="progress-track slim">
              <div className="progress-fill" style={{ width: `${g.progress}%` }} />
            </div>
            <span className="muted small">{g.progress}% · autopilot working…</span>
          </div>
        ))}
      <div className="stat-grid">
        <StatCard label="Agents" value={agentCount} />
        <StatCard label="To do" value={byStatus('todo')} />
        <StatCard label="In progress" value={byStatus('in_progress')} />
        <StatCard label="In review" value={byStatus('review')} />
        <StatCard label="Done" value={byStatus('done')} />
        <StatCard label="Runs" value={stats?.total_runs ?? 0} />
      </div>
      <div className="stat-grid">
        <StatCard label="Prompt tokens" value={fmt(stats?.prompt_tokens)} accent="dim" />
        <StatCard label="Completion tokens" value={fmt(stats?.completion_tokens)} accent="dim" />
        <StatCard label="Tokens saved (optimizer)" value={fmt(stats?.tokens_saved)} accent="ok" />
        <StatCard label="Total cost" value={`$${(stats?.total_cost ?? 0).toFixed(4)}`} accent="ok" />
      </div>

      <div className="two-col">
        <section>
          <h2>Recent runs</h2>
          {runs.length === 0 && <p className="muted">No runs yet. Run a task from the board.</p>}
          <div className="run-list">
            {runs.slice(0, 8).map((run) => {
              const task = tasks.find((t) => t.id === run.task_id)
              return (
                <div key={run.id} className="run-row">
                  <span className={`badge badge-${run.status}`}>{run.status}</span>
                  <span className="run-title">{task?.title ?? `Task #${run.task_id}`}</span>
                  <span className="muted small">
                    {run.prompt_tokens + run.completion_tokens} tok
                    {run.tokens_saved > 0 && ` · saved ${run.tokens_saved}`}
                  </span>
                </div>
              )
            })}
          </div>
        </section>
        <section>
          <h2>Activity</h2>
          <div className="feed">
            {events.slice(0, 12).map((e) => (
              <div key={e.id} className="feed-row">
                <span className={`dot dot-${e.kind}`} />
                <span>{e.message}</span>
                <span className="muted small">{new Date(e.created_at).toLocaleTimeString()}</span>
              </div>
            ))}
            {events.length === 0 && <p className="muted">No activity yet.</p>}
          </div>
        </section>
      </div>
    </div>
  )
}

const fmt = (n?: number) => (n ?? 0).toLocaleString()

function StatCard({
  label,
  value,
  accent,
}: {
  label: string
  value: number | string
  accent?: 'ok' | 'dim'
}) {
  return (
    <div className="stat-card">
      <div className={`stat-value ${accent === 'ok' ? 'ok' : ''} ${accent === 'dim' ? 'dim' : ''}`}>
        {value}
      </div>
      <div className="stat-label">{label}</div>
    </div>
  )
}
