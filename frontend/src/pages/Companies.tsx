import { useEffect, useState } from 'react'
import { api, Company } from '../api'
import { EmptyState, useToast } from '../ui'

interface Props {
  activeId: number | null
  onSwitch: (id: number) => void
  onCreate: () => void
  onChanged: () => void
}

export default function Companies({ activeId, onSwitch, onCreate, onChanged }: Props) {
  const [companies, setCompanies] = useState<Company[]>([])
  const [editing, setEditing] = useState<Company | null>(null)
  const [form, setForm] = useState({ name: '', mission: '', default_model: '', monthly_budget: 0 })
  const toast = useToast()

  const refresh = () =>
    api.companies.list(true).then(setCompanies).catch(console.error)

  useEffect(() => {
    refresh()
    const timer = window.setInterval(refresh, 6000)
    return () => window.clearInterval(timer)
  }, [])

  const openEdit = (company: Company) => {
    setEditing(company)
    setForm({
      name: company.name,
      mission: company.mission,
      default_model: company.default_model,
      monthly_budget: company.monthly_budget,
    })
  }

  const save = async () => {
    if (!editing) return
    await api.companies.update(editing.id, form)
    toast('success', `Saved ${form.name}`)
    setEditing(null)
    refresh()
    onChanged()
  }

  const archive = async (company: Company) => {
    if (!confirm(`Archive "${company.name}"? Its autopilot stops and goals pause.`)) return
    await api.companies.archive(company.id)
    toast('info', `${company.name} archived`)
    refresh()
    onChanged()
  }

  const restore = async (company: Company) => {
    await api.companies.restore(company.id)
    toast('success', `${company.name} restored`)
    refresh()
    onChanged()
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Companies</h1>
          <p className="subtitle">
            Every company runs its own crew and autopilot — all at the same time
          </p>
        </div>
        <button className="btn btn-primary" onClick={onCreate}>
          + New company
        </button>
      </div>

      {companies.length === 0 && (
        <EmptyState
          icon="🏢"
          title="No companies yet"
          hint="Describe a company and the CEO builds its crew, skills and first goal."
          action={
            <button className="btn btn-primary" onClick={onCreate}>
              + New company
            </button>
          }
        />
      )}

      <div className="card-grid">
        {companies.map((company) => (
          <div
            key={company.id}
            className={`company-card ${company.id === activeId ? 'active' : ''} ${
              company.archived ? 'archived' : ''
            }`}
          >
            <div className="company-head">
              <span className="switcher-avatar">{company.name.slice(0, 1).toUpperCase()}</span>
              <div>
                <h3>{company.name}</h3>
                <span className="muted small">
                  {company.archived
                    ? 'archived'
                    : company.active_goals > 0
                      ? '● autopilot working'
                      : 'idle'}
                </span>
              </div>
            </div>
            <p className="muted small">{company.mission || 'No mission set'}</p>
            <div className="company-stats">
              <span>{company.agents} agents</span>
              <span>{company.active_goals} active goals</span>
              <span>{company.open_tasks} open tasks</span>
              <span>${company.total_cost.toFixed(4)}</span>
            </div>
            <div className="card-actions">
              {!company.archived && company.id !== activeId && (
                <button className="btn btn-primary" onClick={() => onSwitch(company.id)}>
                  Open
                </button>
              )}
              {company.id === activeId && <span className="chip chip-ok">current</span>}
              <button className="btn btn-ghost" onClick={() => openEdit(company)}>
                Edit
              </button>
              {company.archived ? (
                <button className="btn btn-ok" onClick={() => restore(company)}>
                  Restore
                </button>
              ) : (
                <button className="btn btn-danger" onClick={() => archive(company)}>
                  Archive
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      {editing && (
        <div className="modal-backdrop" onClick={() => setEditing(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>Edit {editing.name}</h2>
            <label>
              Name
              <input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
            </label>
            <label>
              Mission
              <textarea
                value={form.mission}
                onChange={(e) => setForm({ ...form, mission: e.target.value })}
                rows={3}
              />
            </label>
            <label>
              Model override (blank = global default)
              <input
                value={form.default_model}
                onChange={(e) => setForm({ ...form, default_model: e.target.value })}
                placeholder="e.g. deepseek/deepseek-chat:free"
              />
            </label>
            <label>
              Monthly budget cap in USD (0 = unlimited)
              <input
                type="number"
                step="0.01"
                value={form.monthly_budget}
                onChange={(e) => setForm({ ...form, monthly_budget: Number(e.target.value) })}
              />
            </label>
            <div className="modal-actions">
              <button className="btn btn-ghost" onClick={() => setEditing(null)}>
                Cancel
              </button>
              <button className="btn btn-primary" onClick={save}>
                Save
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
