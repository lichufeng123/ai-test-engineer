// Pure oracle: derived from the reviewed exercise rule and independent fixture,
// never from the value rendered after clicking the button.
export function expectedAfterIncrement(before: number): number {
  if (!Number.isSafeInteger(before)) throw new Error('Fixture is not an integer');
  return before + 1;
}

export function assertCounter(actual: number, expected: number): void {
  if (actual !== expected) throw new Error(`A-EXAMPLE-001: expected ${expected}, got ${actual}`);
}
