import { useEffect, useState } from 'react'
import { api, Agent, Run, Task } from '../api'

export default function Dashboard() {
  const [agents, setAgents] = useState<Agent[]>([])
  const [tasks, setTasks] = useState<Task[]>([])
  const [runs, setRuns] = useState<Run[]>([])

  useEffect(() => {
    api.agents.list().then(setAgents).catch(console.error)
    api.tasks.list().then(setTasks).catch(console.error)
    api.runs.list().then(setRuns).catch(console.error)
  }, [])

  const byStatus = (s: Task['status']) => tasks.filter((t) => t.status === s).length

  return (
    <div>
      <h1>Dashboard</h1>
      <p className="subtitle">Your AI company at a glance</p>
      <div className="stat-grid">
        <StatCard label="Agents" value={agents.length} />
        <StatCard label="To do" value={byStatus('todo')} />
        <StatCard label="In progress" value={byStatus('in_progress')} />
        <StatCard label="In review" value={byStatus('review')} />
        <StatCard label="Done" value={byStatus('done')} />
        <StatCard label="Total runs" value={runs.length} />
      </div>
      <h2>Recent runs</h2>
      {runs.length === 0 && <p className="muted">No runs yet. Run a task from the board.</p>}
      <div className="run-list">
        {runs.slice(0, 8).map((run) => {
          const task = tasks.find((t) => t.id === run.task_id)
          return (
            <div key={run.id} className="run-row">
              <span className={`badge badge-${run.status}`}>{run.status}</span>
              <span className="run-title">{task?.title ?? `Task #${run.task_id}`}</span>
              <span className="muted">{new Date(run.started_at).toLocaleString()}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="stat-card">
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  )
}
