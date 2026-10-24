# Pi to Codex Requirement Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate a redacted, traceable 63-session archive and create 14 requirement-named Codex tasks for unfinished October work.

**Architecture:** A deterministic migration manifest maps immutable Pi session files to requirement work items. A generator produces one sanitized summary per session plus project and requirement indexes; current work-item state remains authoritative. Codex tasks receive only the synthesized handoff and start in read-only takeover mode.

**Tech Stack:** Python 3 standard library, Markdown, JSON, ai-test work-item CLI, Codex task APIs.

**Spec:** `docs/superpowers/specs/2026-10-20-pi-to-codex-migration.md`

## Global Constraints

- Process only `/Users/chenhao/Documents/codex-handoff/pi-archive/test-tool__ai-test-engineer/`.
- Generate exactly 63 summaries and identify exactly 42 October sessions.
- Task titles must match `需求: 需求名`; requirement IDs are metadata, not titles.
- Never copy credentials, tokens, cookies, customer data, business IDs, or private endpoints.
- Do not execute tests or business writes from newly created tasks.
- Preserve existing dirty worktrees; changes are additive and no commit, reset, checkout, merge, or push is authorized.

## Review Focus

- Duplicate Pi exports must remain separate summaries keyed by full session ID.
- A historical conversation containing several requirements must link to each requirement without merging their states.
- Missing or legacy-worktree-only work items must be restored without claiming unreviewed facts.
- Redaction must catch credential labels, bearer/API tokens, phone numbers, long business IDs, and URLs.
- Codex task creation must be idempotent enough to avoid duplicate titles on a rerun.

---

### Task 1: Freeze inventory and migration manifest

**Files:**
- Create: `docs/history/pi-migration/migration-manifest.json`
- Create: `/Users/chenhao/Documents/codex-handoff/generate-ai-test-engineer-summaries.py`

**Interfaces:**
- Consumes: immutable Pi Markdown archive and current work-item JSON files.
- Produces: normalized session records keyed by full session ID and requirement mappings keyed by stable requirement ID.

- [ ] Implement archive parsing, metadata extraction and explicit requirement mapping.
- [ ] Add `--check` assertions for 63 total sessions, 42 October sessions and unique full session IDs.
- [ ] Run the checks and confirm all three counts.

### Task 2: Generate and validate session summaries

**Files:**
- Create: `docs/history/pi-migration/INDEX.md`
- Create: `docs/history/pi-migration/PROJECT_HANDOFF.md`
- Create: `docs/history/pi-migration/sessions/YYYY-MM/<session-id>.md` (63 files)
- Create: `docs/history/pi-migration/migration-receipt.json`

**Interfaces:**
- Consumes: Task 1 normalized records and redaction rules.
- Produces: one sanitized summary per session, a global index and machine-readable validation receipt.

- [ ] Generate summaries with source, classification, requirement links, user intent, result and open items.
- [ ] Redact credentials, personal/customer data, business IDs, URLs and attachment paths.
- [ ] Run count, broken-link and forbidden-pattern checks; write their results to the receipt.

### Task 3: Restore requirement handoff coverage

**Files:**
- Create or update: `/Users/chenhao/Documents/test-tool/yizhi-test-assets/.ai-test/work-items/<requirement-id>/`
- Create: each selected work item's `migration/pi-2026-10-context.md`
- Update: work-item indexes and artifact registers only through framework commands where safe.

**Interfaces:**
- Consumes: Task 2 summaries, current main asset state, two legacy worktree states and the opportunity prototype draft.
- Produces: 14 independently resumable requirement contexts with explicit authority labels.

- [ ] Preserve the 11 current work items and add their migration context.
- [ ] Restore the member-card and smart-followup work items from legacy state without overwriting newer main assets.
- [ ] Create an intake-stage work item for smart-earphone opportunity recognition from the prototype draft.
- [ ] Reconcile indexes and verify all 14 contexts are discoverable.

### Task 4: Create and organize Codex tasks

**Files:**
- Create: `docs/history/pi-migration/codex-task-receipt.json`

**Interfaces:**
- Consumes: 14 requirement contexts and saved Codex project inventory.
- Produces: 14 uniquely titled Codex tasks and their thread IDs.

- [ ] Resolve the saved `ai-test-engineer` project and inspect existing task titles to prevent duplicates.
- [ ] Create each task with title `需求: 需求名` and a read-only takeover prompt.
- [ ] Wait for each task to finish its initial takeover response or request user input.
- [ ] Record task IDs, titles, requirement IDs and creation status in the receipt.
- [ ] Put created tasks in one `ai-test-engineer｜10月迁移` sidebar section when supported.

### Task 5: End-to-end verification

**Files:**
- Update: `docs/history/pi-migration/migration-receipt.json`

**Interfaces:**
- Consumes: all generated files and Codex task receipt.
- Produces: final pass/fail evidence for the migration.

- [ ] Re-run generator `--check` and forbidden-pattern scans.
- [ ] Verify 63 summary files, 42 October entries, 14 requirement contexts and 14 non-code task titles.
- [ ] Verify every task prompt links to an existing work item and migration context.
- [ ] Report any source conflicts or restored legacy states without claiming they are reviewed current facts.

## Self-review

- Spec coverage: every approved output and the three newly discovered requirements map to Tasks 1–5.
- Step scan: each step has a concrete filesystem or Codex result.
- Interface consistency: session IDs feed summaries; requirement IDs feed contexts; context paths feed Codex prompts.
- Review focus: covered by manifest checks, redaction scan, legacy restoration rules and duplicate-title inspection.
- Proportion: the plan describes decisions and checks without embedding generator implementation.
