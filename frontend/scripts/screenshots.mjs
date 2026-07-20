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

// 1. Onboarding wizard
await page.goto(BASE)
await page.waitForSelector('.onboard-card')
await page.fill('input[placeholder*="Nimbus"]', 'Nimbus Media')
await page.fill(
  'textarea',
  'We help small brands grow with AI-generated content, campaigns and market research.',
)
await page.fill('input[placeholder*="campaign"]', 'Launch the first client campaign')
await shot('01-onboarding')
await page.click('.btn-big')
await page.waitForSelector('.onboard-agents', { timeout: 20000 })
await shot('02-company-ready')

// 2. Goals page — watch autopilot work
await page.click('button:has-text("Watch your company work")')
await page.waitForSelector('.goal-card')
for (let i = 0; i < 5; i++) {
  await tick()
  await page.waitForTimeout(1400)
}
await page.waitForTimeout(1000)
await shot('03-goals-autopilot')

// drive autopilot until the goal is achieved
for (let i = 0; i < 40; i++) {
  await tick()
  await page.waitForTimeout(1200)
  const achieved = await page.evaluate(() =>
    fetch('/api/goals')
      .then((r) => r.json())
      .then((gs) => gs.some((g) => g.status === 'achieved')),
  )
  if (achieved) break
}
await page.waitForTimeout(2000)
await shot('04-goal-achieved')

// 3. Dashboard full of autopilot activity
await nav('Dashboard')
await page.waitForSelector('.feed-row')
await shot('05-dashboard')

// 4. Agents with distributed skills
await nav('Agents')
await page.waitForSelector('.skill-chips')
await shot('06-agents-skills')

// 5. Board, runs, deliverables produced autonomously
await nav('Task Board')
await page.waitForSelector('.task-card')
await shot('07-board')

await nav('Run History')
await page.waitForSelector('.run-row')
await shot('08-runs')

await nav('Deliverables')
await page.waitForSelector('.agent-card')
await shot('09-deliverables')

await browser.close()
console.log('Screenshots saved to', OUT)
