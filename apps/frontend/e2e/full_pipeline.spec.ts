// Full-pipeline E2E for the flywheel preset.
//
// This test exercises the entire S1→S5 pipeline through the UI:
//   interpret (SSE) → generate (S2) → analyze (S3) → explain (S4) → document (S5).
//
// It REQUIRES a live backend. Run it manually against either:
//   - Local: `uvicorn apps.backend.main:app --reload` + `pnpm dev` (default baseURL http://localhost:3000)
//   - Cloud Run: set PLAYWRIGHT_BASE_URL and NEXT_PUBLIC_API_BASE_URL appropriately, then `playwright test`
//
// Not part of the default CI smoke run — invoke explicitly:
//   ./node_modules/.bin/playwright test e2e/full_pipeline.spec.ts

import { expect, test } from '@playwright/test'

test.describe('full pipeline', () => {
  test('preset flywheel completes analyze, explain, document', async ({ page }) => {
    await page.goto('/design?preset=flywheel')

    // Wait for the form to render with the preset prompt populated.
    const prompt = page.locator('textarea')
    await expect(prompt).toBeVisible()

    // Click Send (interpret)
    await page.getByRole('button', { name: /send/i }).click()

    // After the SSE finishes, the form should show some tri-state markers.
    await page.waitForTimeout(2000)

    // Fill any clearly missing dimension fields if visible (best-effort).
    const outerInput = page.locator('input[name="outer_diameter_m"]')
    if (await outerInput.count()) await outerInput.fill('0.5')
    const innerInput = page.locator('input[name="inner_diameter_m"]')
    if (await innerInput.count()) await innerInput.fill('0.1')
    const thickInput = page.locator('input[name="thickness_m"]')
    if (await thickInput.count()) await thickInput.fill('0.05')

    // Click Generate
    await page.getByRole('button', { name: /^generate$/i }).click()
    await page.waitForSelector('canvas', { timeout: 30_000 })

    // Click Analyze
    await page.getByRole('button', { name: /^analyze$/i }).click()
    await expect(page.locator('text=/PASS|WARN|FAIL/')).toBeVisible({ timeout: 15_000 })

    // Click Explain
    await page.getByRole('button', { name: /^explain$/i }).click()
    await expect(page.locator('text=Facts cited:')).toBeVisible({ timeout: 30_000 })

    // Click Generate documents
    await page.getByRole('button', { name: /generate documents/i }).click()
    await expect(page.locator('iframe[title="report preview"]')).toBeVisible({ timeout: 30_000 })
  })
})
