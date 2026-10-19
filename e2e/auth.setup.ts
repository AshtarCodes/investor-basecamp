import { expect, test as setup } from '@playwright/test'

setup('create an account through the sign-in page', async ({ page }) => {
  await page.goto('/sign-in')
  await page.waitForLoadState('networkidle')
  await page.getByRole('button', { name: /create one/i }).click()
  await page.getByLabel('Email').fill('e2e@example.com')
  await page.getByLabel('Password').fill('e2e-password-123')
  await page.getByRole('button', { name: 'Create account' }).click()

  await expect(page.getByText('Signed in as e2e@example.com')).toBeVisible()
  await page.context().storageState({ path: 'e2e/.auth/user.json' })
})
