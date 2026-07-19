export interface Agent {
  id: number
  name: string
  role: string
  goal: string
  backstory: string
  model: string
  created_at: string
}

export interface Task {
  id: number
  title: string
  description: string
  expected_output: string
  status: 'todo' | 'in_progress' | 'review' | 'done'
  agent_id: number | null
  created_at: string
}

export interface Run {
  id: number
  task_id: number
  status: 'running' | 'completed' | 'failed'
  output: string
  log: string
  error: string
  started_at: string
  finished_at: string
}

export interface Settings {
  openrouter_api_key_set: boolean
  default_model: string
  fake_llm: boolean
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    const body = await res.text()
    throw new Error(`${res.status}: ${body}`)
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

export const api = {
  agents: {
    list: () => request<Agent[]>('/api/agents'),
    create: (data: Partial<Agent>) =>
      request<Agent>('/api/agents', { method: 'POST', body: JSON.stringify(data) }),
    update: (id: number, data: Partial<Agent>) =>
      request<Agent>(`/api/agents/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    remove: (id: number) => request<void>(`/api/agents/${id}`, { method: 'DELETE' }),
  },
  tasks: {
    list: () => request<Task[]>('/api/tasks'),
    create: (data: Partial<Task>) =>
      request<Task>('/api/tasks', { method: 'POST', body: JSON.stringify(data) }),
    patch: (id: number, data: Partial<Task>) =>
      request<Task>(`/api/tasks/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
    remove: (id: number) => request<void>(`/api/tasks/${id}`, { method: 'DELETE' }),
    run: (id: number) => request<Run>(`/api/tasks/${id}/run`, { method: 'POST' }),
    runs: (id: number) => request<Run[]>(`/api/tasks/${id}/runs`),
  },
  runs: {
    list: () => request<Run[]>('/api/runs'),
    get: (id: number) => request<Run>(`/api/runs/${id}`),
  },
  settings: {
    get: () => request<Settings>('/api/settings'),
    update: (data: { openrouter_api_key?: string; default_model?: string }) =>
      request<Settings>('/api/settings', { method: 'PUT', body: JSON.stringify(data) }),
  },
}
