// Captures UI evidence screenshots. Requires backend (fake LLM) + frontend dev servers.
import { chromium } from 'playwright'
import { mkdirSync } from 'fs'

const BASE = 'http://localhost:5173'
const OUT = '../docs/evidence'
mkdirSync(OUT, { recursive: true })

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })

const shot = (name) => page.screenshot({ path: `${OUT}/${name}.png` })
const nav = async (label) => {
  await page.click(`.nav-item:has-text("${label}")`)
  await page.waitForTimeout(600)
}
const apiCall = (path, opts) =>
  page.evaluate(
    ([p, o]) =>
      fetch(p, {
        headers: { 'Content-Type': 'application/json' },
        ...o,
      }).then((r) => (r.status === 204 ? null : r.json())),
    [path, opts ?? {}],
  )
const post = (body) => ({ method: 'POST', body: JSON.stringify(body) })

await page.goto(BASE)
await page.waitForSelector('.stat-card')

// CEO chat: objective -> dependency-chained plan
await nav('CEO Chat')
await page.fill('.chat-input input', 'Launch a weekly newsletter about AI agents')
await page.click('.chat-input .btn')
await page.waitForSelector('.chat-msg.ceo', { timeout: 15000 })
await page.waitForTimeout(400)
await shot('03-ceo-chat')

// Plan document drafted by the CEO
await apiCall(
  '/api/plans',
  post({
    title: 'Q3 Growth Plan',
    objective: 'Grow the newsletter to 10k subscribers',
    draft_with_ceo: true,
  }),
)
await nav('Plans')
await page.waitForSelector('.plan-item')
await page.click('.plan-item')
await page.waitForSelector('.plan-detail')
await shot('04-plans')

// Board with planned tasks (priority chips, dependency chains)
const tasks = await apiCall('/api/tasks')
await apiCall(`/api/tasks/${tasks[0].id}`, {
  method: 'PATCH',
  body: JSON.stringify({ priority: 'urgent', due_date: '2026-07-25' }),
})
await nav('Task Board')
await page.waitForSelector('.task-card')
await shot('05-board')

// Complete first task, then run the dependent one from the UI
await apiCall(`/api/tasks/${tasks[0].id}/run`, { method: 'POST' })
await page.waitForTimeout(2500)
await apiCall(`/api/tasks/${tasks[0].id}/approve`, { method: 'POST' })

await page.reload()
await page.waitForSelector('.stat-card')
await nav('Task Board')
await page.waitForSelector('.task-card')
await page.click(`.task-card:has-text("${tasks[1].title.slice(0, 30)}")`)
await page.waitForSelector('.drawer')
await page.click('button:has-text("Run with CrewAI")')
await page.waitForSelector('.run-panel .badge-completed', { timeout: 30000 })
await page.fill('.comment-form input', 'Great result, shipping it.')
await page.click('.comment-form .btn')
await page.waitForTimeout(500)
await shot('06-task-run')
await page.click('.drawer-header .btn-ghost')

// Approve dependent task -> deliverable; file a hire request -> inbox
await apiCall(`/api/tasks/${tasks[1].id}/approve`, { method: 'POST' })
await apiCall(
  '/api/hires',
  post({
    name: 'Pixel',
    role: 'Brand Designer',
    specialty: 'design',
    reason: 'CEO: newsletter needs branded visuals — no design specialty on the crew.',
  }),
)

await nav('Inbox')
await page.waitForSelector('.run-row')
await shot('02-inbox')

await nav('Run History')
await page.waitForSelector('.run-row')
await shot('07-runs')

await nav('Deliverables')
await page.waitForSelector('.agent-card')
await shot('08-deliverables')

// Routine
await apiCall(
  '/api/routines',
  post({
    title: 'Daily activity digest',
    description: 'Summarize yesterday and plan today',
    agent_id: tasks[0].agent_id,
    interval_minutes: 1440,
  }),
)
await nav('Routines')
await page.waitForSelector('.run-row')
await shot('09-routines')

await nav('Agents')
await page.waitForSelector('.org-chart')
await shot('10-agents')

await nav('Settings')
await page.waitForSelector('.settings-form')
await shot('11-settings')

await nav('Dashboard')
await page.waitForSelector('.feed-row')
await shot('01-dashboard')

await browser.close()
console.log('Screenshots saved to', OUT)
