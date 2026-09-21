<!-- FRAMEWORK_VERSION: 0.11.0 -->

# AI Test Engineer

English | [简体中文](README.zh-CN.md)

AI Test Engineer is a portable, evidence-first framework for guiding an AI agent through software testing. It connects requirement understanding, system and feature discovery, approved test-case baselines, fixture generation, execution, evidence review, reporting, and reusable execution assets.

The core uses Python's standard library, Markdown, and JSON Schema. It works with any AI assistant; adapters describe optional integrations for Playwright Test, Playwright MCP, Chrome DevTools MCP, Ego Lite, Stagehand, agent-device, and Minium.

## Portable skills and optional plugin

The canonical workflow skills live in `.agents/skills/`, the cross-client discovery location used by Agent Skills-compatible tools. Opening this repository makes the project-scoped skills available to compatible agents. To install them for the current user:

```bash
ai-test skills-check --root .
ai-test skills-install --root . --client universal
```

Add `--client codex` to create a Codex compatibility link as well. Existing skills are never overwritten unless `--replace` is provided; replacement first moves them to a timestamped backup.

The repository is also an optional Codex/ChatGPT plugin source. The plugin package is generated from the same canonical skills, so it does not maintain a second copy:

```bash
ai-test plugin-build --root . --output ./dist/ai-test-engineer
```

The generated package contains `.codex-plugin/plugin.json` and the plugin-required `skills/` directory. Other clients can continue using `.agents/skills/` without installing the plugin. See [skill and plugin distribution](docs/skill-and-plugin-distribution.md).

## Quick start

```bash
python3 -m pip install -e .
ai-test init ./my-test-project \
  --name "Member Portal" \
  --system-id member-portal \
  --environment test \
  --platform web
```

### One requirement, one task

Create an isolated work item before starting a new testing requirement:

```bash
ai-test work-item-create --root ./my-test-project \
  --requirement-id REQ-XXX --title "Requirement title" --feature "Feature" \
  --environment sit --platform web --scope "Approved test scope"
```

In a new Codex, WorkBuddy, or other agent task, the user only needs to say `接手需求 REQ-XXX`. The agent runs `ai-test work-item-show --root . --requirement-id REQ-XXX` and restores the current stage, completed work, blockers, next steps, approved baseline, and reusable assets. `TEST_WORK_ITEMS.md` is the human-readable project index. Extend an existing requirement to a new environment or platform with `work-item-update --add-environment <env> --add-platform app --scope <incremental-scope>` instead of creating a second work item.

Every generated requirement, rule, case, handoff, or report artifact is registered with `work-item-artifact-register`, including its stable artifact ID, path, SHA-256, review status, and workflow stage. `work-item-reconcile` detects missing or changed files, state that lags behind artifacts, unregistered legacy outputs, and attempts to enter `CASE_DESIGN` without an automation-readiness plan and validated rule-review receipt. See the [Chinese user guide](docs/ONE_REQUIREMENT_ONE_CONVERSATION.zh-CN.md).

For a new system, plan discovery before testing a feature:

```bash
ai-test discovery-plan \
  --project ./my-test-project/ai-test.json \
  --environment test \
  --platform web \
  --product-version 1.0.0
```

Use a reviewed test-case baseline as the single source of truth. The framework records its stable case IDs and hash in an execution handoff; UI automation is not a second case-management system.

Before generating cases, classify the feature as isolated, linked, or pending. Infer likely upstream and downstream links from the system map, role model, entity model, and existing context before asking the product owner. Confirmed flows receive stable `BF-*` IDs and reference atomic `A-*` assertions; every confirmed flow must have at least one complete end-to-end case.

Requirement, business-flow, assertion, and case review pages may batch-approve the current filtered set after explicit confirmation. Every batch decision is still stored per stable ID and remains individually editable. Changes, exclusions, pending decisions, removals, dependency scope, and other high-risk decisions stay item-by-item so batch actions cannot bypass required rationale or gates.

The complete baseline must also pass an execution-granularity gate. End-to-end cases prove the whole business flow; they do not replace cases that can be prepared, executed, judged, evidenced, and rerun independently. Equivalent boundaries for one field may be parameterized, while different roles, platforms, state transitions, failure mechanisms, server-side authorization checks, or side effects remain separate.

Validate this contract with:

```bash
ai-test flow-check \
  --input ./rules/business-flows.json \
  --cases ./cases/approved-baseline.json \
  --matrix-output ./runs/latest/flow-coverage.json

ai-test case-granularity-check \
  --cases ./cases/review-draft.json
```

After requirement review, plan the automation scope, required account roles, fixtures, environments, and evidence before case execution details are forgotten. Bind stable case IDs after case approval, then reconfirm the current environment and available prerequisites immediately before execution:

```bash
ai-test readiness-plan \
  --input ./runs/latest/automation-readiness-source.json \
  --output ./runs/latest/automation_readiness_plan.json

ai-test readiness-check \
  --plan ./runs/latest/automation_readiness_plan.json \
  --confirmation ./runs/latest/pre_execution_confirmation.json \
  --output ./runs/latest/execution_readiness_receipt.json
```

The readiness receipt separates ready cases from cases blocked by missing roles, fixtures, execution targets, or hardware fixtures. Mobile and hardware-in-the-loop plans declare `execution_target_requirements` and `hardware_fixture_requirements`; only targets with a completed capability check are confirmed as available. Blocked cases are recorded once and are not retried until their prerequisite fingerprint changes; ready cases continue.

## Guarded AI browser stack

Web regression keeps Playwright Test as the only formal executor. Ego Lite is the default first-pass discovery tool and handles authenticated or visual exploration; Playwright MCP is optional assistance for generating or validating locators, not a prerequisite for writing Playwright scripts; Chrome DevTools MCP diagnoses network, console, and performance failures; Stagehand may only propose locator, wait-condition, or known-dialog repairs. Every agentic result returns to Playwright for a focused verification and impact regression, and no tool may change approved expectations.

Validate the project routing contract before using the stack:

```bash
ai-test web-executor-check \
  --input ./runs/latest/web-executor-routing.json \
  --output ./runs/latest/web-executor-routing-receipt.json
```

Copy [the routing template](templates/web-executor-routing.example.json) and read the [Web AI browser stack guide](docs/web-ai-browser-stack.md). Available tools must pin exact versions; credentials and browser authentication state remain runtime-only.

## AI-first mobile execution

The framework models mobile automation through provider-neutral targets and step receipts. The first AI-first adapter is [agent-device](adapters/agent-device/README.md): an AI agent explores through MCP or CLI, reviewed actions become `.ad` or typed Node.js workflows, and formal regression continues to reference the single approved case baseline. `schemas/execution-target-profile.schema.json` describes phones and simulators, `schemas/hardware-fixture.schema.json` describes pre-bound peripherals, and the cross-platform run-plan and step-receipt schemas connect app, API, and web evidence.

Pin an exact agent-device version. Device identifiers, app identifiers, endpoints, and credentials remain runtime-only. AI may explore, diagnose, and propose repairs, but it must not change approved expectations or blindly retry irreversible writes.

## Automation execution history

Every automation run is registered before its first test action and closed after reporting and asset feedback. The fixed human-readable ledger is `AUTOMATION_EXECUTION_HISTORY.md`; it preserves the first execution time and every later run with its purpose, objective, scope, duration, outcome, report, evidence, and asset changes.

```bash
ai-test execution-log-start \
  --root . --automation-id smart-earphone-web --run-id RUN-20260920-001 \
  --feature "Smart Earphone Web" --environment sit --platform web \
  --purpose "release gate" --objective "validate the core workflow" \
  --scope "search, filters, pagination, and navigation"

ai-test execution-log-finish \
  --root . --run-id RUN-20260920-001 --status passed \
  --summary "approved scope passed" --report reports/sit.md \
  --evidence runs/RUN-20260920-001/evidence-manifest.json
```

The machine state lives in `.ai-test/execution_history.json`. Never include credentials, cookies, tokens, or customer data in either record.

After issue triage, distill missed scenarios, user corrections, and false positives into the reviewed **Test Omission Risk Rule Library**. Every formal case-generation run retrieves that current document and writes `omission_risk_audit.json`; each applicable hit maps to an independent case or a reviewed not-applicable, blocked, or pending disposition. These rules guide test design and never replace approved product expectations.

Generate deterministic test fixtures:

```bash
ai-test data-generate \
  --spec templates/fixture-spec.example.json \
  --output ./fixtures/generated
```

Check evidence and embedded report media:

```bash
ai-test evidence-check \
  --manifest ./runs/2026-09-12/evidence_manifest.json \
  --root ./runs/2026-09-12 \
  --report ./runs/2026-09-12/report.md
```

Before publishing video evidence, run the phase-one technical quality gate. Each video declares its expected duration and optional thresholds in a sanitized input JSON. The command uses `ffprobe` and `ffmpeg` to detect duration violations, black segments, and static intervals, then writes a machine-readable receipt:

```bash
ai-test video-check \
  --input templates/video-check-input.example.json \
  --root ./runs/2026-09-12 \
  --output ./runs/2026-09-12/video_quality_receipt.json
```

The receipt classifies each item as `passed`, `trim_required`, `rerecord_required`, or `blocked` and reports exact intervals and ratios. Phase one does not verify that recorded screens, titles, steps, or outcomes semantically match the test case; those still require content review. Video never replaces required result screenshots. `video-check` is optional core tooling and requires `ffprobe` and `ffmpeg` on `PATH` (or explicit `--ffprobe` and `--ffmpeg` paths).

Read the [framework handbook](docs/FRAMEWORK.md) for the complete workflow and the [playbooks](playbooks/README.md) for operational guidance.

## List result consistency

For list, search, filter, pagination, and post-write readback features, case generation checks result completeness and identity, not merely HTTP success or a nonempty list. Cover missing/duplicate/unexpected records, all-page reconciliation, and visibility after applicable writes under aligned scopes and confirmed matching rules. Review coverage, exclusions, fixtures, and paired failure evidence using the [list result design reference](.agents/skills/test-case-generate/references/list-result-consistency.md). After applicable edits, imports, links, reassignment, unlinking, or status changes, verify both display persistence and search/filter membership under new and prior conditions. Model these steps in business flows and atomic assertions; correct display does not prove searchable attributes were persisted or synchronized. This is a design checklist, not an automated coverage gate.

## Permission test design

Permission-controlled features automatically load the permission design reference in the existing skills. Separate upstream eligibility, role permissions, organization scope and access surfaces; verify browse/edit combinations, activation, revocation, navigation bypasses and server authorization. Run `ai-test permission-check --matrix rules/permission_matrix.json --cases cases/review-draft.json --output runs/latest/permission_design_receipt.json`. This validates declared design coverage only, not business correctness or executed results. See [permission design](.agents/skills/test-case-generate/references/permission-testing.md).

## Project layout

- `src/ai_test_framework/`: CLI and reusable framework primitives.
- `.agents/skills/`: the single cross-client source for testing workflow skills.
- `plugin/plugin.json`: metadata used to build the optional plugin package.
- `playbooks/`: tool-independent testing procedures.
- `adapters/`: optional integrations and baseline guidance.
- `schemas/` and `templates/`: machine-readable contracts and safe examples.
- `examples/`: sanitized fixture examples.

## Development

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
ai-test docs-check --root .
```

Framework behavior, CLI commands, repository layout, or quality gates must update this README, `docs/FRAMEWORK.md`, and `framework-manifest.json` together.

## Security and privacy

Do not commit credentials, private endpoints, customer data, execution recordings, screenshots, downloads, caches, or production exports. See [SECURITY.md](SECURITY.md).

## License

MIT. See [LICENSE](LICENSE).
