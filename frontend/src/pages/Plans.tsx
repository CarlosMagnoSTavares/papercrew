import { FormEvent, useEffect, useState } from 'react'
import { api, Plan } from '../api'
import { EmptyState, Spinner, useToast } from '../ui'

export default function Plans() {
  const [plans, setPlans] = useState<Plan[]>([])
  const [selected, setSelected] = useState<Plan | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ title: '', objective: '' })
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const toast = useToast()

  const refresh = () =>
    api.plans.list().then((list) => {
      setPlans(list)
      setSelected((prev) => list.find((p) => p.id === prev?.id) ?? prev)
    })
  useEffect(() => {
    refresh()
  }, [])

  const create = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const plan = await api.plans.create({ ...form, draft_with_ceo: true })
      setShowForm(false)
      setForm({ title: '', objective: '' })
      await refresh()
      setSelected(plan)
    } catch (err) {
      setError(String(err))
    } finally {
      setBusy(false)
    }
  }

  const convert = async (plan: Plan) => {
    setError('')
    try {
      const res = await api.plans.convert(plan.id)
      const msg = `Converted into ${res.tasks.length} tasks → see Task Board`
      setNotice(msg)
      toast('success', msg)
      setTimeout(() => setNotice(''), 4000)
      refresh()
    } catch (err) {
      setError(String(err))
    }
  }

  const remove = async (plan: Plan) => {
    if (!confirm(`Delete plan "${plan.title}"?`)) return
    await api.plans.remove(plan.id)
    if (selected?.id === plan.id) setSelected(null)
    refresh()
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Plans</h1>
          <p className="subtitle">CEO-drafted execution plans — review, then convert into tasks</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowForm(true)}>
          + New plan
        </button>
      </div>

      {notice && <div className="banner banner-ok">{notice}</div>}
      {error && <div className="error">{error}</div>}

      <div className="plans-layout">
        <div className="plans-list">
          {plans.map((plan) => (
            <div
              key={plan.id}
              className={`plan-item ${selected?.id === plan.id ? 'active' : ''}`}
              onClick={() => setSelected(plan)}
            >
              <div className="task-title">{plan.title}</div>
              <span className={`badge ${plan.status === 'converted' ? 'badge-done' : 'badge-todo'}`}>
                {plan.status}
              </span>
            </div>
          ))}
          {plans.length === 0 && (
            <EmptyState
              icon="☰"
              title="No plans yet"
              hint="Draft one with the CEO, then convert it into tasks."
              action={
                <button className="btn btn-primary" onClick={() => setShowForm(true)}>
                  + New plan
                </button>
              }
            />
          )}
        </div>
        {selected && (
          <div className="plan-detail">
            <div className="page-header">
              <h2>{selected.title}</h2>
              <div className="card-actions">
                {selected.status === 'draft' && (
                  <button className="btn btn-primary" onClick={() => convert(selected)}>
                    Convert to tasks →
                  </button>
                )}
                <button className="btn btn-danger" onClick={() => remove(selected)}>
                  Delete
                </button>
              </div>
            </div>
            <p className="muted small">{selected.objective}</p>
            <pre className="output plan-content">{selected.content}</pre>
          </div>
        )}
      </div>

      {showForm && (
        <div className="modal-backdrop" onClick={() => setShowForm(false)}>
          <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={create}>
            <h2>New plan</h2>
            <p className="muted small">The CEO drafts the plan document from your objective.</p>
            <label>
              Title
              <input
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                required
              />
            </label>
            <label>
              Objective
              <textarea
                value={form.objective}
                onChange={(e) => setForm({ ...form, objective: e.target.value })}
                rows={3}
                required
              />
            </label>
            <div className="modal-actions">
              <button type="button" className="btn btn-ghost" onClick={() => setShowForm(false)}>
                Cancel
              </button>
              <button type="submit" className="btn btn-primary" disabled={busy}>
                {busy ? <Spinner label="CEO drafting…" /> : 'Draft with CEO'}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}
