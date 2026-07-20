import { FormEvent, useState } from 'react'
import { api, OnboardResult } from '../api'

export default function Onboarding({ onDone }: { onDone: () => void }) {
  const [form, setForm] = useState({ company_name: '', mission: '', first_goal: '' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<OnboardResult | null>(null)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      setResult(await api.company.onboard(form))
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
          <h1>🎉 {form.company_name} is live</h1>
          <p className="subtitle">
            The CEO built your team, distributed skills and planned the first goal. Autopilot is
            already working toward it.
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
          <button className="btn btn-primary" onClick={onDone}>
            Watch your company work →
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
        <h1>Create your AI company</h1>
        <p className="subtitle">
          Describe your company once. The CEO hires the right agents, gives each one skills, sets
          your first goal and puts the whole crew to work — autonomously.
        </p>
        {error && <div className="error">{error}</div>}
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
          What does your company do? (mission)
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
          {busy ? 'CEO building your company…' : '🚀 Build my company'}
        </button>
      </form>
    </div>
  )
}
