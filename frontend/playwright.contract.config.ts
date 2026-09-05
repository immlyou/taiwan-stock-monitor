import { defineConfig, devices } from '@playwright/test'

const port = Number(process.env.PLAYWRIGHT_CONTRACT_PORT ?? 41737)
const apiPort = Number(process.env.PLAYWRIGHT_API_PORT ?? 41738)
const python = process.env.PLAYWRIGHT_PYTHON ?? 'python3'
const authEnv = {
  AUTH_SECRET: 'contract-only-secret-contract-only-secret',
  AUTH_GOOGLE_ID: 'contract-google-id',
  AUTH_GOOGLE_SECRET: 'contract-google-secret',
  AUTH_ALLOWED_EMAIL: 'contract@example.test',
  STOCK_API_KEY: 'contract-only-api-key',
  NEXT_PUBLIC_API_URL: `http://127.0.0.1:${apiPort}`,
  ENABLE_SCHEDULER: '0',
  FINLAB_API_TOKEN: '',
}

export default defineConfig({
  testDir: './e2e-contract',
  workers: 1,
  retries: 0,
  timeout: 60000,
  expect: { timeout: 15000 },
  reporter: 'list',
  use: { baseURL: `http://localhost:${port}`, trace: 'retain-on-failure' },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: `cd .. && ${python} -m uvicorn tests.e2e_api_server:app --host 127.0.0.1 --port ${apiPort} --lifespan off`,
      url: `http://127.0.0.1:${apiPort}/health`, env: authEnv,
      reuseExistingServer: false, timeout: 60000,
    },
    {
      command: `npm run dev -- --port ${port}`,
      url: `http://localhost:${port}`, env: authEnv,
      reuseExistingServer: false, timeout: 120000,
    },
  ],
})
