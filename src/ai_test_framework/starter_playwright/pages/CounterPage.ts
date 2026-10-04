import { expect, type Page } from '@playwright/test';

// A Page Object exposes user-facing actions and typed observations only.
// It must not know the business expected value or generate a report verdict.
export class CounterPage {
  constructor(private readonly page: Page) {}

  async increment() {
    await this.page.getByRole('button', { name: 'Increase' }).click();
  }

  async readValue(): Promise<number> {
    const field = this.page.getByTestId('counter-value');
    await expect(field).toBeVisible();
    const value = Number(await field.innerText());
    if (!Number.isSafeInteger(value)) throw new Error('Counter UI not an integer');
    return value;
  }
}
