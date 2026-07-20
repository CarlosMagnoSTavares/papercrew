import { FormEvent, useEffect, useState } from 'react'
import { api, Settings } from '../api'
import { useToast } from '../ui'

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null)
  const [apiKey, setApiKey] = useState('')
  const [model, setModel] = useState('')
  const [company, setCompany] = useState('')
  const [mission, setMission] = useState('')
  const [price, setPrice] = useState('0')
  const [budget, setBudget] = useState('0')
  const [saved, setSaved] = useState(false)
  const toast = useToast()

  useEffect(() => {
    api.settings.get().then((s) => {
      setSettings(s)
      setModel(s.default_model)
      setCompany(s.company_name)
      setMission(s.company_mission)
      setPrice(s.price_per_1k_tokens)
      setBudget(s.monthly_budget)
    })
  }, [])

  const save = async (e: FormEvent) => {
    e.preventDefault()
    const updated = await api.settings.update({
      ...(apiKey ? { openrouter_api_key: apiKey } : {}),
      default_model: model,
      company_name: company,
      company_mission: mission,
      price_per_1k_tokens: price,
      monthly_budget: budget,
    })
    setSettings(updated)
    setApiKey('')
    setSaved(true)
    toast('success', 'Settings saved')
    setTimeout(() => setSaved(false), 2500)
  }

  if (!settings) return <p className="muted">Loading…</p>

  return (
    <div>
      <h1>Settings</h1>
      <p className="subtitle">Company profile and OpenRouter connection</p>

      {settings.fake_llm && (
        <div className="banner">
          Demo mode active (PAPERCREW_FAKE_LLM=1) — runs are simulated, no tokens spent.
        </div>
      )}

      <form className="settings-form" onSubmit={save}>
        <label>
          Company name
          <input value={company} onChange={(e) => setCompany(e.target.value)} />
        </label>
        <label>
          Company mission
          <textarea value={mission} onChange={(e) => setMission(e.target.value)} rows={2} />
        </label>
        <label>
          OpenRouter API key{' '}
          {settings.openrouter_api_key_set && <span className="chip chip-ok">configured</span>}
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder={settings.openrouter_api_key_set ? '•••••••• (leave empty to keep)' : 'sk-or-...'}
          />
        </label>
        <label>
          Default model
          <input value={model} onChange={(e) => setModel(e.target.value)} />
        </label>
        <div className="form-row">
          <label>
            Price per 1k tokens (USD, 0 = free)
            <input value={price} onChange={(e) => setPrice(e.target.value)} />
          </label>
          <label>
            Monthly budget cap (USD, 0 = unlimited)
            <input value={budget} onChange={(e) => setBudget(e.target.value)} />
          </label>
        </div>
        <p className="muted small">
          Free models: meta-llama/llama-3.3-70b-instruct:free · deepseek/deepseek-chat:free ·
          full list at openrouter.ai/models?q=free
        </p>
        <button type="submit" className="btn btn-primary">
          Save
        </button>
        {saved && <span className="chip chip-ok">Saved ✓</span>}
      </form>
    </div>
  )
}
