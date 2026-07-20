// Captures UI evidence from whatever companies already exist in the running
// backend. Requires a configured OpenRouter key and the dev server.
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
  await page.waitForTimeout(900)
}

await page.goto(BASE)
await page.waitForSelector('.nav-item', { timeout: 20000 })

await nav('Dashboard')
await page.waitForSelector('.stat-card')
await shot('01-dashboard')

await nav('Goals')
await page.waitForSelector('.goal-card')
await shot('02-goal-achieved')

await nav('Agents')
await page.waitForSelector('.agent-card')
await shot('03-agents-tailored')

await nav('Task Board')
await page.waitForSelector('.task-card')
await shot('04-board')

// open a finished task to show the real crew output
await page.click('.column:has-text("Done") .task-card')
await page.waitForSelector('.drawer')
await page.waitForTimeout(700)
await shot('05-task-output')
await page.click('.drawer-header .btn-ghost')

await nav('Deliverables')
await page.waitForSelector('.agent-card, .empty-state')
await shot('06-deliverables')

await nav('Run History')
await page.waitForSelector('.run-row')
await shot('07-runs')

await nav('Companies')
await page.waitForSelector('.company-card')
await shot('08-companies')

await nav('Settings')
await page.waitForSelector('.settings-form')
await shot('09-settings')

await browser.close()
console.log('Screenshots saved to', OUT)
