import { defineConfig } from '@playwright/test'

export default defineConfig({
  testMatch: '**/*.e2e.ts',
  use: {
    baseURL: process.env.LENSBRIEF_BASE_URL ?? 'http://127.0.0.1:8080',
    viewport: { width: 1440, height: 1000 },
    channel: process.env.LENSBRIEF_BROWSER || undefined,
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
})
