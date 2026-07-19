import { FormEvent, useEffect, useState } from 'react'
import { api, Settings } from '../api'

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null)
  const [apiKey, setApiKey] = useState('')
  const [model, setModel] = useState('')
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    api.settings.get().then((s) => {
      setSettings(s)
      setModel(s.default_model)
    })
  }, [])

  const save = async (e: FormEvent) => {
    e.preventDefault()
    const updated = await api.settings.update({
      ...(apiKey ? { openrouter_api_key: apiKey } : {}),
      default_model: model,
    })
    setSettings(updated)
    setApiKey('')
    setSaved(true)
    setTimeout(() => setSaved(false), 2500)
  }

  if (!settings) return <p className="muted">Loading…</p>

  return (
    <div>
      <h1>Settings</h1>
      <p className="subtitle">OpenRouter connection — free model by default</p>

      {settings.fake_llm && (
        <div className="banner">
          Demo mode active (PAPERCREW_FAKE_LLM=1) — runs are simulated, no tokens spent.
        </div>
      )}

      <form className="settings-form" onSubmit={save}>
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
