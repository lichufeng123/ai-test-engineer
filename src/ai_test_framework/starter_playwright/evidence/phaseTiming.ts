import type { TestInfo } from '@playwright/test';

// Measure waits rather than replacing them with larger fixed sleeps. Timing
// records are local-only and must never include credentials or customer data.
export class PhaseTiming {
  private last = performance.now();
  private readonly durations: Record<string, number> = {};

  mark(phase: 'fixture' | 'navigation' | 'action' | 'assertion'): void {
    const now = performance.now();
    this.durations[phase] = Math.round(now - this.last);
    this.last = now;
  }

  async attach(info: TestInfo): Promise<void> {
    await info.attach('phase-timing-ms', {
      body: Buffer.from(JSON.stringify(this.durations)), contentType: 'application/json',
    });
  }
}
