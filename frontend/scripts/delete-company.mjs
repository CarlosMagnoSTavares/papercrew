// Verifies the destructive delete flow end to end against the running app.
// Requires a fresh backend (fake LLM, no companies) + the dev server.
import { chromium } from 'playwright'
import { mkdirSync } from 'fs'

const BASE = 'http://localhost:5173'
const OUT = '../docs/evidence'
mkdirSync(OUT, { recursive: true })

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
const shot = (name) => page.screenshot({ path: `${OUT}/${name}.png` })

const api = (path, opts) =>
  page.evaluate(
    ([p, o]) =>
      fetch(p, { headers: { 'Content-Type': 'application/json' }, ...o }).then((r) =>
        r.status === 204 ? null : r.json(),
      ),
    [path, opts ?? {}],
  )

await page.goto(BASE)
await page.waitForSelector('.onboard-card')

// Two companies so we can delete one and prove the other survives.
for (const [name, mission, goal] of [
  ['Nimbus Media', 'AI content for small brands.', 'Launch the first client campaign'],
  ['Vertex Labs', 'Developer tools and docs.', 'Ship the developer docs portal'],
]) {
  await api(
    '/api/companies',
    { method: 'POST', body: JSON.stringify({ company_name: name, mission, first_goal: goal }) },
  )
}
await page.reload()
await page.waitForSelector('.nav-item')
await page.click('.nav-item:has-text("Companies")')
await page.waitForSelector('.company-card')

const before = await api('/api/companies')
console.log('before:', before.map((c) => c.name).join(', '))

// Open the delete dialog on Vertex Labs
await page.click('.company-card:has-text("Vertex Labs") .btn-danger')
await page.waitForSelector('.danger-box')
await shot('12-delete-company')

// The button stays disabled until the typed name matches exactly
const disabledBefore = await page.isDisabled('button:has-text("Delete permanently")')
await page.fill('.modal input', 'Vertex')
const disabledPartial = await page.isDisabled('button:has-text("Delete permanently")')
await page.fill('.modal input', 'Vertex Labs')
const disabledAfter = await page.isDisabled('button:has-text("Delete permanently")')
console.log('guard — empty:', disabledBefore, 'partial:', disabledPartial, 'exact:', disabledAfter)

await page.click('button:has-text("Delete permanently")')
await page.waitForTimeout(1500)
await shot('13-after-delete')

const after = await api('/api/companies?include_archived=true')
console.log('after:', after.map((c) => c.name).join(', ') || '(none)')

const agents = await api('/api/agents')
console.log('surviving company agents:', agents.length, '→', agents.map((a) => a.name).join(', '))

await browser.close()
