import { test, expect, type Page } from '@playwright/test';
import { CounterPage } from '../pages/CounterPage';
import { incrementOnce } from '../flows/counterFlow';
import { assertCounter, expectedAfterIncrement } from '../oracles/counter';
import { PhaseTiming } from '../evidence/phaseTiming';
import { checkWithReceipt } from '../evidence/assertionReceipt';

// Fictional, isolated sample only: not an approved business baseline.
const fixture = { id: 'FX-EXAMPLE-001', startingValue: 2 };

// This fake UI is deliberately local; no remote service or business write.
async function openSyntheticCounter(page: Page) {
  await page.setContent(`
    <output data-testid="counter-value">${fixture.startingValue}</output>
    <button type="button" onclick="document.querySelector('[data-testid=counter-value]').textContent =
      String(Number(document.querySelector('[data-testid=counter-value]').textContent) + 1)">Increase</button>
  `);
}

test('TC-EXAMPLE-001 counter increments once', async ({ page }, testInfo) => {
  const timing = new PhaseTiming();
  const expected = expectedAfterIncrement(fixture.startingValue);
  timing.mark('fixture');
  await openSyntheticCounter(page);
  const model = new CounterPage(page);
  expect(await model.readValue()).toBe(fixture.startingValue);
  timing.mark('navigation');
  const actual = await incrementOnce(model);
  timing.mark('action');
  await checkWithReceipt(testInfo, {
    run_id: process.env.AI_TEST_RUN_ID ?? 'local-synthetic-only',
    case_id: 'TC-EXAMPLE-001', assertion_id: 'A-EXAMPLE-001', fixture_id: fixture.id,
    probe_sha256: process.env.AI_TEST_PROBE_SHA256 ?? '0'.repeat(64),
    oracle_sha256: process.env.AI_TEST_ORACLE_SHA256 ?? '0'.repeat(64),
  }, () => assertCounter(actual, expected)); // MUST throw into Playwright when wrong.
  timing.mark('assertion');
  await timing.attach(testInfo);
  await testInfo.attach('A-EXAMPLE-001-result', {
    body: Buffer.from(JSON.stringify({ fixture_id: fixture.id, expected, actual })),
    contentType: 'application/json',
  });
});

test('TC-EXAMPLE-NEG-001 wrong outcome is rejected by the oracle', async () => {
  expect(() => assertCounter(99, expectedAfterIncrement(fixture.startingValue)))
    .toThrow('A-EXAMPLE-001');
});
