import { expect, test } from '@playwright/test'

test('a signed-in session survives a reload', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText('Signed in as e2e@example.com')).toBeVisible()

  await page.reload()

  await expect(page).toHaveURL('/')
  await expect(page.getByText('Signed in as e2e@example.com')).toBeVisible()
})
