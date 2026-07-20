import { FormEvent, useEffect, useRef, useState } from 'react'
import { api, ChatMessage } from '../api'
import { Spinner } from '../ui'

export default function Chat() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const endRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    api.chat.history().then(setMessages).catch(console.error)
    inputRef.current?.focus()
  }, [])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const send = async (e: FormEvent) => {
    e.preventDefault()
    if (!input.trim() || busy) return
    const text = input
    setInput('')
    setBusy(true)
    setError('')
    setMessages((prev) => [
      ...prev,
      { id: -1, role: 'user', body: text, created_at: new Date().toISOString() },
    ])
    try {
      const res = await api.chat.send(text)
      setMessages((prev) => [
        ...prev.filter((m) => m.id !== -1),
        { id: Date.now(), role: 'user', body: text, created_at: new Date().toISOString() },
        { id: Date.now() + 1, role: 'ceo', body: res.reply, created_at: new Date().toISOString() },
      ])
    } catch (err) {
      setError(String(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="chat-page">
      <h1>CEO Chat</h1>
      <p className="subtitle">
        Tell the CEO an objective — it plans, creates tasks and delegates to the crew
      </p>
      <div className="chat-window">
        {messages.length === 0 && (
          <div className="chat-suggestions">
            <p className="muted">
              Give the CEO an objective — it plans, creates dependency-chained tasks and delegates
              by specialty. Try one:
            </p>
            {[
              'Launch a weekly newsletter about AI agents',
              'Create a go-to-market plan for our new product',
              'Research our top 5 competitors and summarize gaps',
            ].map((s) => (
              <button key={s} className="chip chip-suggest" onClick={() => setInput(s)}>
                {s}
              </button>
            ))}
          </div>
        )}
        {messages.map((m) => (
          <div key={m.id} className={`chat-msg ${m.role}`}>
            <div className="chat-author">{m.role === 'ceo' ? '📎 Atlas (CEO)' : 'You'}</div>
            <pre className="chat-body">{m.body}</pre>
          </div>
        ))}
        {busy && (
          <div className="chat-msg ceo">
            <div className="chat-author">📎 Atlas (CEO)</div>
            <div className="chat-body">
              <Spinner label="planning…" />
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>
      {error && <div className="error">{error}</div>}
      <form className="chat-input" onSubmit={send}>
        <input
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Describe an objective for your company…"
        />
        <button className="btn btn-primary" disabled={busy || !input.trim()}>
          Send
        </button>
      </form>
    </div>
  )
}
