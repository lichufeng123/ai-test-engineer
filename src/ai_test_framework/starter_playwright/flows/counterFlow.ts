import type { CounterPage } from '../pages/CounterPage';

// Flow code orchestrates actions; it does not calculate expected results.
export async function incrementOnce(page: CounterPage) {
  await page.increment();
  return page.readValue();
}
