import { FormEvent, useState } from 'react'
import { api, OnboardResult } from '../api'
import { Spinner } from '../ui'

interface Props {
  onDone: (companyId: number) => void
  canCancel?: boolean
  onCancel?: () => void
}

export default function Onboarding({ onDone, canCancel, onCancel }: Props) {
  const [form, setForm] = useState({ company_name: '', mission: '', first_goal: '' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<OnboardResult | null>(null)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      setResult(await api.companies.create(form))
    } catch (err) {
      setError(String(err))
    } finally {
      setBusy(false)
    }
  }

  if (result) {
    return (
      <div className="onboard-wrap">
        <div className="onboard-card">
          <h1>🎉 {result.company.name} is live</h1>
          <p className="subtitle">
            The CEO built your team, distributed skills and planned the first goal. Autopilot is
            already working toward it — alongside any other company you run.
          </p>
          <h2>Your crew</h2>
          <div className="onboard-agents">
            {result.agents.map((a) => (
              <div key={a.id} className="onboard-agent">
                <span className="mini-avatar">{a.name.slice(0, 1)}</span>
                <div>
                  <strong>{a.name}</strong> <span className="muted small">{a.role}</span>
                  <div className="skill-chips">
                    {a.skills.map((s) => (
                      <span key={s} className="chip">
                        {s}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>
          <h2>First goal</h2>
          <p>
            🎯 <strong>{result.goal.title}</strong> — {result.tasks.length} tasks planned and
            delegated
          </p>
          <button className="btn btn-primary" onClick={() => onDone(result.company.id)}>
            Watch {result.company.name} work →
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="onboard-wrap">
      <form className="onboard-card" onSubmit={submit}>
        <div className="logo onboard-logo">
          <span className="logo-mark">📎</span>
          <span className="logo-text">PaperCrew</span>
        </div>
        <h1>Create {canCancel ? 'another' : 'your'} AI company</h1>
        <p className="subtitle">
          Describe the company once. The CEO hires the right agents, gives each one skills, sets
          the first goal and puts the whole crew to work — autonomously. Every company you create
          runs its own crew in parallel.
        </p>
        {error && <div className="error">{error}</div>}
        <button
          type="button"
          className="chip chip-suggest self-start"
          onClick={() =>
            setForm({
              company_name: 'Nimbus Media',
              mission:
                'We help small brands grow with AI-generated content, campaigns and market research.',
              first_goal: 'Launch the first client campaign',
            })
          }
        >
          ✨ Fill with an example
        </button>
        <label>
          Company name
          <input
            value={form.company_name}
            onChange={(e) => setForm({ ...form, company_name: e.target.value })}
            placeholder="e.g. Nimbus Media"
            required
          />
        </label>
        <label>
          What does this company do? (mission)
          <textarea
            value={form.mission}
            onChange={(e) => setForm({ ...form, mission: e.target.value })}
            rows={3}
            placeholder="e.g. We help small brands grow with AI-generated content and campaigns"
            required
          />
        </label>
        <label>
          First goal
          <input
            value={form.first_goal}
            onChange={(e) => setForm({ ...form, first_goal: e.target.value })}
            placeholder="e.g. Launch the first client campaign"
            required
          />
        </label>
        <button className="btn btn-primary btn-big" disabled={busy}>
          {busy ? <Spinner label="CEO building your company…" /> : '🚀 Build my company'}
        </button>
        {canCancel && (
          <button type="button" className="btn btn-ghost" onClick={onCancel}>
            Cancel
          </button>
        )}
      </form>
    </div>
  )
}
