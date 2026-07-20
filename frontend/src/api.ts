export interface Agent {
  id: number
  name: string
  role: string
  goal: string
  backstory: string
  model: string
  specialty: string
  is_ceo: boolean
  created_at: string
}

export interface Task {
  id: number
  title: string
  description: string
  expected_output: string
  status: 'todo' | 'in_progress' | 'review' | 'done'
  agent_id: number | null
  depends_on: string
  crew_mode: 'solo' | 'hierarchical'
  priority: 'low' | 'medium' | 'high' | 'urgent'
  due_date: string
  feedback: string
  created_at: string
}

export interface Hire {
  id: number
  name: string
  role: string
  goal: string
  backstory: string
  specialty: string
  model: string
  reason: string
  status: 'pending' | 'approved' | 'rejected'
  created_at: string
}

export interface Plan {
  id: number
  title: string
  objective: string
  content: string
  status: 'draft' | 'converted'
  created_at: string
}

export interface InboxItem {
  kind: 'review' | 'hire' | 'failure' | 'unassigned'
  ref_id: number
  title: string
  detail: string
}

export interface AgentStats {
  agent_id: number
  tasks_total: number
  tasks_done: number
  runs_total: number
  tokens: number
  cost: number
}

export interface Skill {
  id: number
  agent_id: number
  name: string
  description: string
  created_at: string
}

export interface Goal {
  id: number
  title: string
  description: string
  status: 'active' | 'achieved' | 'paused'
  progress: number
  autopilot: boolean
  cycle: number
  created_at: string
}

export interface Company {
  onboarded: boolean
  company_name: string
  company_mission: string
}

export interface OnboardResult {
  agents: { id: number; name: string; role: string; skills: string[] }[]
  goal: { id: number; title: string }
  tasks: { id: number; title: string; agent: string }[]
}

export interface WorkProduct {
  task_id: number
  title: string
  agent: string
  output: string
  approved_at: string
}

export interface Run {
  id: number
  task_id: number
  status: 'running' | 'completed' | 'failed'
  output: string
  log: string
  error: string
  prompt_tokens: number
  completion_tokens: number
  tokens_saved: number
  cost: number
  started_at: string
  finished_at: string
}

export interface Comment {
  id: number
  task_id: number
  author: string
  body: string
  created_at: string
}

export interface Routine {
  id: number
  title: string
  description: string
  agent_id: number | null
  interval_minutes: number
  enabled: boolean
  auto_run: boolean
  next_run_at: string
  created_at: string
}

export interface AppEvent {
  id: number
  kind: string
  message: string
  created_at: string
}

export interface ChatMessage {
  id: number
  role: 'user' | 'ceo'
  body: string
  created_at: string
}

export interface Stats {
  total_runs: number
  prompt_tokens: number
  completion_tokens: number
  tokens_saved: number
  total_cost: number
}

export interface Settings {
  openrouter_api_key_set: boolean
  default_model: string
  company_name: string
  company_mission: string
  price_per_1k_tokens: string
  monthly_budget: string
  fake_llm: boolean
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    let detail = await res.text()
    try {
      detail = JSON.parse(detail).detail ?? detail
    } catch {
      /* keep raw text */
    }
    throw new Error(detail)
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

const post = (body: unknown) => ({ method: 'POST', body: JSON.stringify(body) })

export const api = {
  agents: {
    list: () => request<Agent[]>('/api/agents'),
    create: (data: Partial<Agent>) => request<Agent>('/api/agents', post(data)),
    update: (id: number, data: Partial<Agent>) =>
      request<Agent>(`/api/agents/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    remove: (id: number) => request<void>(`/api/agents/${id}`, { method: 'DELETE' }),
    stats: (id: number) => request<AgentStats>(`/api/agents/${id}/stats`),
    skills: (id: number) => request<Skill[]>(`/api/agents/${id}/skills`),
    addSkill: (id: number, data: { name: string; description: string }) =>
      request<Skill>(`/api/agents/${id}/skills`, post(data)),
    generateSkills: (id: number) =>
      request<Skill[]>(`/api/agents/${id}/skills/generate`, { method: 'POST' }),
    removeSkill: (agentId: number, skillId: number) =>
      request<void>(`/api/agents/${agentId}/skills/${skillId}`, { method: 'DELETE' }),
  },
  company: {
    get: () => request<Company>('/api/company'),
    onboard: (data: { company_name: string; mission: string; first_goal: string }) =>
      request<OnboardResult>('/api/company/onboard', post(data)),
  },
  goals: {
    list: () => request<Goal[]>('/api/goals'),
    create: (data: { title: string; description?: string }) =>
      request<Goal>('/api/goals', post(data)),
    tasks: (id: number) => request<Task[]>(`/api/goals/${id}/tasks`),
    pause: (id: number) => request<Goal>(`/api/goals/${id}/pause`, { method: 'POST' }),
    resume: (id: number) => request<Goal>(`/api/goals/${id}/resume`, { method: 'POST' }),
    tick: () => request<{ actions: number }>('/api/goals/tick', { method: 'POST' }),
  },
  hires: {
    list: () => request<Hire[]>('/api/hires'),
    create: (data: Partial<Hire>) => request<Hire>('/api/hires', post(data)),
    approve: (id: number) => request<Agent>(`/api/hires/${id}/approve`, { method: 'POST' }),
    reject: (id: number) => request<Hire>(`/api/hires/${id}/reject`, { method: 'POST' }),
    remove: (id: number) => request<void>(`/api/hires/${id}`, { method: 'DELETE' }),
  },
  plans: {
    list: () => request<Plan[]>('/api/plans'),
    create: (data: { title: string; objective: string; content?: string; draft_with_ceo?: boolean }) =>
      request<Plan>('/api/plans', post(data)),
    convert: (id: number) =>
      request<{ tasks: { id: number; title: string; agent: string }[] }>(
        `/api/plans/${id}/convert`,
        { method: 'POST' },
      ),
    remove: (id: number) => request<void>(`/api/plans/${id}`, { method: 'DELETE' }),
  },
  inbox: () => request<InboxItem[]>('/api/inbox'),
  workProducts: () => request<WorkProduct[]>('/api/work-products'),
  tasks: {
    list: () => request<Task[]>('/api/tasks'),
    create: (data: Partial<Task>) => request<Task>('/api/tasks', post(data)),
    patch: (id: number, data: Partial<Task>) =>
      request<Task>(`/api/tasks/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
    remove: (id: number) => request<void>(`/api/tasks/${id}`, { method: 'DELETE' }),
    run: (id: number) => request<Run>(`/api/tasks/${id}/run`, { method: 'POST' }),
    runs: (id: number) => request<Run[]>(`/api/tasks/${id}/runs`),
    approve: (id: number) => request<Task>(`/api/tasks/${id}/approve`, { method: 'POST' }),
    reject: (id: number, feedback: string, rerun: boolean) =>
      request<Task>(`/api/tasks/${id}/reject`, post({ feedback, rerun })),
    comments: (id: number) => request<Comment[]>(`/api/tasks/${id}/comments`),
    addComment: (id: number, body: string) =>
      request<Comment>(`/api/tasks/${id}/comments`, post({ body, author: 'You' })),
  },
  runs: {
    list: () => request<Run[]>('/api/runs'),
    get: (id: number) => request<Run>(`/api/runs/${id}`),
  },
  routines: {
    list: () => request<Routine[]>('/api/routines'),
    create: (data: Partial<Routine>) => request<Routine>('/api/routines', post(data)),
    update: (id: number, data: Partial<Routine>) =>
      request<Routine>(`/api/routines/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    remove: (id: number) => request<void>(`/api/routines/${id}`, { method: 'DELETE' }),
  },
  chat: {
    history: () => request<ChatMessage[]>('/api/chat'),
    send: (message: string) =>
      request<{ reply: string; tasks: { id: number; title: string; agent: string }[] }>(
        '/api/chat',
        post({ message }),
      ),
  },
  events: () => request<AppEvent[]>('/api/events'),
  stats: () => request<Stats>('/api/stats'),
  settings: {
    get: () => request<Settings>('/api/settings'),
    update: (data: Partial<Record<string, string>>) =>
      request<Settings>('/api/settings', { method: 'PUT', body: JSON.stringify(data) }),
  },
}
