// Captures UI evidence screenshots. Requires a FRESH backend (fake LLM, no seed,
// no companies) + the frontend dev server.
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

const fillCompany = async (name, mission, goal) => {
  await page.waitForSelector('.onboard-card')
  await page.fill('input[placeholder*="Nimbus"]', name)
  await page.fill('textarea', mission)
  await page.fill('input[placeholder*="campaign"]', goal)
}

// 1. First run: onboarding wizard
await page.goto(BASE)
await fillCompany(
  'Nimbus Media',
  'We help small brands grow with AI-generated content, campaigns and market research.',
  'Launch the first client campaign',
)
await shot('01-onboarding')
await page.click('.btn-big')
await page.waitForSelector('.onboard-agents', { timeout: 20000 })
await shot('02-company-ready')
await page.click('button:has-text("Watch")')

// 2. Autopilot working the first company's goal
await page.waitForSelector('.goal-card')
for (let i = 0; i < 3; i++) {
  await tick()
  await page.waitForTimeout(1000)
}
await page.waitForSelector('.toast', { timeout: 15000 })
await shot('03-goals-live-toast')

// 3. Create a SECOND company from the switcher
await page.click('.switcher-trigger')
await page.waitForSelector('.switcher-menu')
await shot('04-company-switcher')
await page.click('.switcher-new')
await fillCompany(
  'Vertex Labs',
  'We build developer tools and technical documentation for API-first startups.',
  'Ship the developer docs portal',
)
await page.click('.btn-big')
await page.waitForSelector('.onboard-agents', { timeout: 20000 })
await page.click('button:has-text("Watch")')
await page.waitForSelector('.goal-card')

// 4. Both companies working at the same time
for (let i = 0; i < 6; i++) {
  await tick()
  await page.waitForTimeout(900)
}
await nav('Companies')
await page.waitForSelector('.company-card')
await shot('05-companies-parallel')

// 5. Drive every company's autopilot to completion
for (let i = 0; i < 60; i++) {
  await tick()
  await page.waitForTimeout(700)
  const allDone = await page.evaluate(async () => {
    const companies = await fetch('/api/companies').then((r) => r.json())
    const goals = await Promise.all(
      companies.map((c) =>
        fetch('/api/goals', { headers: { 'X-Company-Id': String(c.id) } }).then((r) => r.json()),
      ),
    )
    return goals.every((list) => list.every((g) => g.status === 'achieved'))
  })
  if (allDone) break
}
await page.reload()
await nav('Companies')
await page.waitForSelector('.company-card')
await shot('06-companies-achieved')

// 6. Second company's own goal history and dashboard
await nav('Goals')
await page.waitForSelector('.goal-card')
await shot('07-goal-achieved')

await nav('Dashboard')
await page.waitForSelector('.feed-row')
await shot('08-dashboard')

await nav('Agents')
await page.waitForSelector('.skill-chips')
await shot('09-agents-skills')

await nav('Task Board')
await page.waitForSelector('.task-card')
await page.click('.task-card')
await page.waitForSelector('.drawer')
await shot('10-task-drawer')
await page.click('.drawer-header .btn-ghost')

await nav('Settings')
await page.waitForSelector('.settings-form')
await shot('11-settings')

await browser.close()
console.log('Screenshots saved to', OUT)
