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

await page.goto(BASE)
await page.waitForSelector('.stat-card')

// 1. CEO chat: objective -> plan of dependency-chained tasks
await nav('CEO Chat')
await page.fill('.chat-input input', 'Launch a weekly newsletter about AI agents')
await page.click('.chat-input .btn')
await page.waitForSelector('.chat-msg.ceo', { timeout: 15000 })
await page.waitForTimeout(400)
await shot('02-ceo-chat')

// 2. Board with the planned tasks
await nav('Task Board')
await page.waitForSelector('.task-card')
await shot('03-board')

// Complete first task via API so the second has dependency context
const tasks = await apiCall('/api/tasks')
const [first, second] = tasks
await apiCall(`/api/tasks/${first.id}/run`, { method: 'POST' })
await page.waitForTimeout(2500)
await apiCall(`/api/tasks/${first.id}/approve`, { method: 'POST' })

// 3. Run the dependent task from the UI — drawer shows optimizer savings
await page.reload()
await page.waitForSelector('.stat-card')
await nav('Task Board')
await page.waitForSelector('.task-card')
await page.click(`.task-card:has-text("${second.title.slice(0, 30)}")`)
await page.waitForSelector('.drawer')
await page.click('button:has-text("Run with CrewAI")')
await page.waitForSelector('.run-panel .badge-completed', { timeout: 30000 })
await page.fill('.comment-form input', 'Great result, shipping it.')
await page.click('.comment-form .btn')
await page.waitForTimeout(500)
await shot('04-task-run')
await page.click('.drawer-header .btn-ghost')

// 4. Routines
await apiCall('/api/routines', {
  method: 'POST',
  body: JSON.stringify({
    title: 'Daily activity digest',
    description: 'Summarize yesterday and plan today',
    agent_id: tasks[0].agent_id,
    interval_minutes: 1440,
  }),
})
await nav('Routines')
await page.waitForSelector('.run-row')
await shot('05-routines')

// 5. Agents
await nav('Agents')
await page.waitForSelector('.agent-card')
await shot('06-agents')

// 6. Settings
await nav('Settings')
await page.waitForSelector('.settings-form')
await shot('07-settings')

// 7. Dashboard last: populated stats + activity feed
await nav('Dashboard')
await page.waitForSelector('.feed-row')
await shot('01-dashboard')

await browser.close()
console.log('Screenshots saved to', OUT)
