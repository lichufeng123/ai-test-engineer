import type { TestInfo } from '@playwright/test';

export type AssertionBinding = Readonly<{
  run_id: string;
  case_id: string;
  assertion_id: string;
  fixture_id: string;
  probe_sha256: string;
  oracle_sha256: string;
}>;

// Attach the outcome from inside the actual assertion callback; a failure must
// still reject the Playwright test. The reporter reconciliation checks this
// attachment, but cannot prove a malicious runner really called the oracle.
export async function checkWithReceipt(
  testInfo: TestInfo,
  binding: AssertionBinding,
  assertResult: () => void | Promise<void>,
): Promise<void> {
  let error: unknown;
  let failed = false;
  try {
    await assertResult();
  } catch (caught) {
    error = caught;
    failed = true;
  }
  await testInfo.attach(`ai-test-assertion-${binding.assertion_id}`, {
    body: Buffer.from(JSON.stringify({
      ...binding,
      status: failed ? 'failed' : 'passed',
    })),
    contentType: 'application/vnd.ai-test.assertion+json',
  });
  if (failed) throw error;
}
