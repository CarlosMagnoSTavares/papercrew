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

await page.goto(BASE)
await page.waitForSelector('.stat-card')

// Seed a demo task via API (through vite proxy) and run it
const agents = await page.evaluate(() => fetch('/api/agents').then((r) => r.json()))
const task = await page.evaluate(
  (agentId) =>
    fetch('/api/tasks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: 'Write launch blog post',
        description: 'Draft a launch announcement for PaperCrew covering features and setup.',
        agent_id: agentId,
      }),
    }).then((r) => r.json()),
  agents[0].id,
)

await nav('Agents')
await shot('02-agents')

await nav('Task Board')
await page.waitForSelector('.task-card')
await shot('03-board')

// Open task, run it, wait for completion
await page.click(`.task-card:has-text("${task.title}")`)
await page.waitForSelector('.drawer')
await page.click('button:has-text("Run with CrewAI")')
await page.waitForSelector('.badge-completed', { timeout: 30000 })
await page.waitForTimeout(400)
await shot('04-task-run')
await page.click('.drawer-header .btn-ghost')

await nav('Settings')
await page.waitForSelector('.settings-form')
await shot('05-settings')

await nav('Dashboard')
await page.waitForSelector('.run-row')
await shot('01-dashboard')

await browser.close()
console.log('Screenshots saved to', OUT)
