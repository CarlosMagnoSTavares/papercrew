// Captures UI evidence screenshots. Requires FRESH backend (fake LLM, no seed,
// not onboarded) + frontend dev servers.
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
const tick = () =>
  page.evaluate(() => fetch('/api/goals/tick', { method: 'POST' }).then((r) => r.json()))

// 1. Onboarding wizard with the example-fill chip (UX: one-click demo data)
await page.goto(BASE)
await page.waitForSelector('.onboard-card')
await page.click('button:has-text("Fill with an example")')
await shot('01-onboarding')
await page.click('.btn-big')
await page.waitForSelector('.onboard-agents', { timeout: 20000 })
await shot('02-company-ready')

// 2. Goals + sidebar live widget + toast from autopilot activity
await page.click('button:has-text("Watch your company work")')
await page.waitForSelector('.goal-card')
await page.waitForSelector('.sidebar-goal', { timeout: 15000 })
for (let i = 0; i < 3; i++) {
  await tick()
  await page.waitForTimeout(1200)
}
await page.waitForSelector('.toast', { timeout: 15000 })
await shot('03-goals-live-toast')

// drive autopilot to completion
for (let i = 0; i < 40; i++) {
  await tick()
  await page.waitForTimeout(1000)
  const achieved = await page.evaluate(() =>
    fetch('/api/goals')
      .then((r) => r.json())
      .then((gs) => gs.some((g) => g.status === 'achieved')),
  )
  if (achieved) break
}
await page.waitForTimeout(1500)
await shot('04-goal-achieved')

// 3. Empty state — Routines page before any routine exists
await nav('Routines')
await page.waitForSelector('.empty-state')
await shot('05-empty-state')

// 4. Task drawer with spinner + optimizer + timeago
await nav('Task Board')
await page.waitForSelector('.task-card')
const firstTitle = await page.$eval('.task-card .task-title', (el) => el.textContent)
await page.click('.task-card')
await page.waitForSelector('.drawer')
await shot('06-task-drawer')
await page.click('.drawer-header .btn-ghost')
void firstTitle

// 5. CEO chat with suggestion chips (empty state UX)
await nav('CEO Chat')
await page.waitForSelector('.chat-suggestions')
await shot('07-chat-suggestions')

// 6. Agents with skill chips + generate button
await nav('Agents')
await page.waitForSelector('.skill-chips')
await shot('08-agents-skills')

// 7. Dashboard — goal banner + activity with relative time
await nav('Dashboard')
await page.waitForSelector('.feed-row')
await shot('09-dashboard')

await browser.close()
console.log('Screenshots saved to', OUT)
