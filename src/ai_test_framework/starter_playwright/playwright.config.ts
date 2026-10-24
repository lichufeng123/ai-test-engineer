import path from 'node:path';
import { defineConfig } from '@playwright/test';

// The sample is synthetic and contains no authentication. Real projects must
// supply a fresh run ID, secret adapter and a reviewed evidence/privacy policy.
const runId = process.env.AI_TEST_RUN_ID ?? 'local-synthetic-only';
if (!/^[a-zA-Z0-9_-]+$/.test(runId)) throw new Error('Invalid AI_TEST_RUN_ID');
const runDir = path.resolve(__dirname, 'runs', runId);

export default defineConfig({
  testDir: './tests',
  workers: 1,
  retries: 0,
  reporter: [['list'], ['json', { outputFile: path.join(runDir, 'playwright-results.json') }]],
  outputDir: path.join(runDir, 'artifacts'),
  use: { ...(process.env.AI_TEST_BROWSER_CHANNEL === 'msedge' ? { channel: 'msedge' as const } : {}),
    video: 'on', screenshot: 'only-on-failure', trace: 'off' },
});
