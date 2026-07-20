import { FormEvent, useEffect, useState } from 'react'
import { api, Agent, Task } from '../api'
import TaskDrawer from '../components/TaskDrawer'

const COLUMNS: { id: Task['status']; label: string }[] = [
  { id: 'todo', label: 'To do' },
  { id: 'in_progress', label: 'In progress' },
  { id: 'review', label: 'Review' },
  { id: 'done', label: 'Done' },
]

const PRIORITY_ORDER: Record<Task['priority'], number> = {
  urgent: 0,
  high: 1,
  medium: 2,
  low: 3,
}

interface Props {
  openTaskId?: number | null
  onTaskOpened?: () => void
}

export default function Board({ openTaskId, onTaskOpened }: Props) {
  const [tasks, setTasks] = useState<Task[]>([])
  const [agents, setAgents] = useState<Agent[]>([])
  const [selected, setSelected] = useState<Task | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({
    title: '',
    description: '',
    agent_id: '',
    priority: 'medium',
    due_date: '',
  })

  const refresh = () =>
    api.tasks.list().then((list) => {
      setTasks(list)
      setSelected((prev) => list.find((t) => t.id === prev?.id) ?? prev)
    })

  useEffect(() => {
    refresh()
    api.agents.list().then(setAgents)
  }, [])

  useEffect(() => {
    if (openTaskId && tasks.length) {
      const task = tasks.find((t) => t.id === openTaskId)
      if (task) {
        setSelected(task)
        onTaskOpened?.()
      }
    }
  }, [openTaskId, tasks, onTaskOpened])

  const createTask = async (e: FormEvent) => {
    e.preventDefault()
    await api.tasks.create({
      title: form.title,
      description: form.description,
      agent_id: form.agent_id ? Number(form.agent_id) : null,
      priority: form.priority as Task['priority'],
      due_date: form.due_date,
    })
    setForm({ title: '', description: '', agent_id: '', priority: 'medium', due_date: '' })
    setShowForm(false)
    refresh()
  }

  const onDrop = async (e: React.DragEvent, status: Task['status']) => {
    e.preventDefault()
    const id = Number(e.dataTransfer.getData('text/task-id'))
    if (id) {
      await api.tasks.patch(id, { status })
      refresh()
    }
  }

  const overdue = (t: Task) =>
    t.due_date && t.status !== 'done' && new Date(t.due_date) < new Date()

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Task Board</h1>
          <p className="subtitle">Drag cards between columns · click a card to open it</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowForm(true)}>
          + New task
        </button>
      </div>

      <div className="board">
        {COLUMNS.map((col) => (
          <div
            key={col.id}
            className="column"
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => onDrop(e, col.id)}
          >
            <div className="column-header">
              {col.label}
              <span className="count">{tasks.filter((t) => t.status === col.id).length}</span>
            </div>
            {tasks
              .filter((t) => t.status === col.id)
              .sort((a, b) => PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority])
              .map((task) => {
                const agent = agents.find((a) => a.id === task.agent_id)
                return (
                  <div
                    key={task.id}
                    className="task-card"
                    draggable
                    onDragStart={(e) => e.dataTransfer.setData('text/task-id', String(task.id))}
                    onClick={() => setSelected(task)}
                  >
                    <div className="task-title">{task.title}</div>
                    <div className="task-meta">
                      {task.priority !== 'medium' && (
                        <span className={`prio prio-${task.priority}`}>{task.priority}</span>
                      )}
                      {task.depends_on && <span className="chip">⛓ deps</span>}
                      {task.due_date && (
                        <span className={`chip ${overdue(task) ? 'chip-danger' : ''}`}>
                          ⏰ {task.due_date}
                        </span>
                      )}
                    </div>
                    {agent && (
                      <div className="task-agent">
                        <span className="mini-avatar">{agent.name.slice(0, 1)}</span>
                        {agent.name}
                      </div>
                    )}
                  </div>
                )
              })}
          </div>
        ))}
      </div>

      {selected && (
        <TaskDrawer
          task={selected}
          agents={agents}
          allTasks={tasks}
          onClose={() => setSelected(null)}
          onChanged={refresh}
        />
      )}

      {showForm && (
        <div className="modal-backdrop" onClick={() => setShowForm(false)}>
          <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={createTask}>
            <h2>New task</h2>
            <label>
              Title
              <input
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                required
              />
            </label>
            <label>
              Description
              <textarea
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                rows={3}
              />
            </label>
            <label>
              Assign to
              <select
                value={form.agent_id}
                onChange={(e) => setForm({ ...form, agent_id: e.target.value })}
              >
                <option value="">— unassigned —</option>
                {agents.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name} ({a.role})
                  </option>
                ))}
              </select>
            </label>
            <div className="form-row">
              <label>
                Priority
                <select
                  value={form.priority}
                  onChange={(e) => setForm({ ...form, priority: e.target.value })}
                >
                  <option value="low">low</option>
                  <option value="medium">medium</option>
                  <option value="high">high</option>
                  <option value="urgent">urgent</option>
                </select>
              </label>
              <label>
                Due date
                <input
                  type="date"
                  value={form.due_date}
                  onChange={(e) => setForm({ ...form, due_date: e.target.value })}
                />
              </label>
            </div>
            <div className="modal-actions">
              <button type="button" className="btn btn-ghost" onClick={() => setShowForm(false)}>
                Cancel
              </button>
              <button type="submit" className="btn btn-primary">
                Create
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}
