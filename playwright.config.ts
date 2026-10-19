import { defineConfig, devices } from '@playwright/test'

const port = 3100
const baseURL = `http://localhost:${port}`
const storageState = 'e2e/.auth/user.json'

export default defineConfig({
  testDir: 'e2e',
  use: { baseURL, trace: 'retain-on-failure' },
  projects: [
    { name: 'setup', testMatch: /\.setup\.ts$/ },
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'], storageState },
      dependencies: ['setup'],
    },
  ],
  webServer: {
    command: `rm -f e2e.db && pnpm exec drizzle-kit migrate && pnpm exec vite dev --port ${port} --strictPort`,
    url: baseURL,
    env: {
      DATABASE_URL: 'e2e.db',
      BETTER_AUTH_URL: baseURL,
      BETTER_AUTH_SECRET: 'e2e-only-secret-not-used-anywhere-else',
    },
    reuseExistingServer: false,
  },
})
