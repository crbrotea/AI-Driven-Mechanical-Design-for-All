import { test, expect } from '@playwright/test'

test('landing shows hero + 3 cards', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  await expect(page.getByText(/Energy Flywheel/i)).toBeVisible()
  await expect(page.getByText(/Hydro Generator/i)).toBeVisible()
  await expect(page.getByText(/Foldable Shelter/i)).toBeVisible()
})

test('clicking Energy Flywheel card navigates to preset', async ({ page }) => {
  await page.goto('/')
  await page.getByText(/Energy Flywheel/i).click()
  await expect(page).toHaveURL(/preset=flywheel/)
})
