import { FormEvent, useEffect, useState } from 'react'
import { api, Agent, AgentStats, Skill } from '../api'
import { useToast } from '../ui'

const EMPTY = { name: '', role: '', goal: '', backstory: '', model: '', specialty: '' }

export default function Agents() {
  const [agents, setAgents] = useState<Agent[]>([])
  const [editing, setEditing] = useState<Agent | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState(EMPTY)
  const [error, setError] = useState('')
  const [stats, setStats] = useState<{ agent: Agent; data: AgentStats } | null>(null)
  const toast = useToast()

  const showStats = async (agent: Agent) => {
    const data = await api.agents.stats(agent.id)
    setStats({ agent, data })
  }

  const [skillsByAgent, setSkillsByAgent] = useState<Record<number, Skill[]>>({})

  const refresh = async () => {
    const list = await api.agents.list()
    setAgents(list)
    const entries = await Promise.all(
      list.map(async (a) => [a.id, await api.agents.skills(a.id)] as const),
    )
    setSkillsByAgent(Object.fromEntries(entries))
  }
  useEffect(() => {
    refresh().catch(console.error)
  }, [])

  const generateSkills = async (agent: Agent) => {
    const created = await api.agents.generateSkills(agent.id)
    toast(
      created.length ? 'success' : 'info',
      created.length ? `${agent.name} gained ${created.length} new skill(s)` : `${agent.name} already has these skills`,
    )
    refresh()
  }

  const openCreate = () => {
    setEditing(null)
    setForm(EMPTY)
    setShowForm(true)
  }

  const openEdit = (agent: Agent) => {
    setEditing(agent)
    setForm({
      name: agent.name,
      role: agent.role,
      goal: agent.goal,
      backstory: agent.backstory,
      model: agent.model,
      specialty: agent.specialty,
    })
    setShowForm(true)
  }

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    try {
      if (editing) await api.agents.update(editing.id, form)
      else await api.agents.create(form)
      toast('success', editing ? `Updated ${form.name}` : `Hired ${form.name}`)
      setShowForm(false)
      refresh()
    } catch (err) {
      setError(String(err))
    }
  }

  const remove = async (agent: Agent) => {
    if (!confirm(`Delete agent "${agent.name}"?`)) return
    await api.agents.remove(agent.id)
    toast('info', `${agent.name} left the company`)
    refresh()
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Agents</h1>
          <p className="subtitle">Your crew — each agent is a CrewAI worker</p>
        </div>
        <button className="btn btn-primary" onClick={openCreate}>
          + Hire agent
        </button>
      </div>

      <div className="org-chart">
        <div className="org-row">
          {agents
            .filter((a) => a.is_ceo)
            .map((a) => (
              <div key={a.id} className="org-node org-ceo">
                <span className="mini-avatar">{a.name.slice(0, 1)}</span> {a.name}
                <div className="muted small">{a.role}</div>
              </div>
            ))}
        </div>
        <div className="org-connector" />
        <div className="org-row">
          {agents
            .filter((a) => !a.is_ceo)
            .map((a) => (
              <div key={a.id} className="org-node">
                <span className="mini-avatar">{a.name.slice(0, 1)}</span> {a.name}
                <div className="muted small">{a.specialty || a.role}</div>
              </div>
            ))}
        </div>
      </div>

      <div className="card-grid">
        {agents.map((agent) => (
          <div key={agent.id} className="agent-card">
            <div className="agent-avatar">{agent.name.slice(0, 1).toUpperCase()}</div>
            <h3>
              {agent.name} {agent.is_ceo && <span className="chip chip-ok">CEO</span>}
            </h3>
            <div className="agent-role">
              {agent.role}
              {agent.specialty && <span className="muted small"> · {agent.specialty}</span>}
            </div>
            <p className="muted small">{agent.goal || 'No goal set'}</p>
            <div className="skill-chips">
              {(skillsByAgent[agent.id] ?? []).map((s) => (
                <span key={s.id} className="chip chip-skill" title={s.description}>
                  ⚡ {s.name}
                </span>
              ))}
              <button
                className="chip chip-add"
                title="CEO distributes skills fitting this agent"
                onClick={() => generateSkills(agent)}
              >
                + skills
              </button>
            </div>
            {agent.model && <div className="chip">{agent.model}</div>}
            <div className="card-actions">
              <button className="btn btn-ghost" onClick={() => showStats(agent)}>
                Stats
              </button>
              <button className="btn btn-ghost" onClick={() => openEdit(agent)}>
                Edit
              </button>
              <button className="btn btn-danger" onClick={() => remove(agent)}>
                Fire
              </button>
            </div>
          </div>
        ))}
      </div>

      {stats && (
        <div className="modal-backdrop" onClick={() => setStats(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="page-header">
              <h2>{stats.agent.name} — performance</h2>
              <button className="btn btn-ghost" onClick={() => setStats(null)}>
                ✕
              </button>
            </div>
            <div className="stat-grid">
              <div className="stat-card">
                <div className="stat-value">{stats.data.tasks_done}/{stats.data.tasks_total}</div>
                <div className="stat-label">Tasks done</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{stats.data.runs_total}</div>
                <div className="stat-label">Runs</div>
              </div>
              <div className="stat-card">
                <div className="stat-value dim">{stats.data.tokens.toLocaleString()}</div>
                <div className="stat-label">Tokens</div>
              </div>
              <div className="stat-card">
                <div className="stat-value ok">${stats.data.cost.toFixed(4)}</div>
                <div className="stat-label">Cost</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {showForm && (
        <div className="modal-backdrop" onClick={() => setShowForm(false)}>
          <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={submit}>
            <h2>{editing ? 'Edit agent' : 'Hire agent'}</h2>
            {error && <div className="error">{error}</div>}
            <label>
              Name
              <input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                required
              />
            </label>
            <label>
              Role
              <input
                value={form.role}
                onChange={(e) => setForm({ ...form, role: e.target.value })}
                required
                placeholder="e.g. Researcher"
              />
            </label>
            <label>
              Goal
              <textarea
                value={form.goal}
                onChange={(e) => setForm({ ...form, goal: e.target.value })}
                rows={2}
              />
            </label>
            <label>
              Backstory
              <textarea
                value={form.backstory}
                onChange={(e) => setForm({ ...form, backstory: e.target.value })}
                rows={2}
              />
            </label>
            <label>
              Specialty
              <input
                value={form.specialty}
                onChange={(e) => setForm({ ...form, specialty: e.target.value })}
                placeholder="research · writing · engineering · analysis"
              />
            </label>
            <label>
              Model override (optional)
              <input
                value={form.model}
                onChange={(e) => setForm({ ...form, model: e.target.value })}
                placeholder="empty = default free model"
              />
            </label>
            <div className="modal-actions">
              <button type="button" className="btn btn-ghost" onClick={() => setShowForm(false)}>
                Cancel
              </button>
              <button type="submit" className="btn btn-primary">
                Save
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}
