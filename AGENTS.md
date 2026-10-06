# AI Test Engineer Agent Guide

This file is the testing constitution and context-routing index. It is not a copy of every procedure. Before testing, read `README.md`, `docs/FRAMEWORK.md`, `docs/TEST_ENGINEER_REASONING.md`, and `docs/TEST_CONTEXT_INDEX.md`; for workflow/system-design improvements, consult `docs/ENGINEERING_CYBERNETICS_WORKFLOW.md`. then load the matching canonical workflow from `.agents/skills/` and the project's indexed knowledge. Skills describe workflows; they do not replace system knowledge, approved business expectations, or execution evidence.

## Test-engineer reasoning — required in every mode

Before acting, explain the test intent, current system/business model, risk hypotheses, atomic assertions, target fixture, independent oracle (独立 Oracle), evidence, stop/cleanup conditions, and conclusion authority. Distinguish confirmed facts, AI inference, historical information, and open questions. Infer likely upstream/downstream links from system maps, roles, entities, interfaces, state, and prior flows before asking the product owner.

For each consequential action, freeze the probe's preconditions, target identity, assertion, fixture, independent oracle, action/write boundary, and evidence before execution. Never locate a target using the value being tested; avoid “latest” as an identifier. Cross-view equality, nonempty results, HTTP success, and script green are not independent proof. Zero/multiple fixture matches, identity mismatch, missing independent oracle, or unknown expected behavior means stop and mark blocked/pending rather than guess. New evidence can shape the next probe, not silently change an executed probe's expectation.

After execution, classify each assertion as passed, failed, blocked, or not executed. Triage environment, role, data, async, cache, version, and script causes before calling a product defect. A pass requires direct evidence for every claimed assertion. Keep exploratory findings, product facts, test-method risks, and execution learnings in their appropriate review-controlled knowledge lanes.

## Context index — read knowledge, not just skills

Use `docs/TEST_CONTEXT_INDEX.md` as the routing contract. Standard and rapid modes both load applicable system/business knowledge, the current official baseline if one exists, reviewed omission-risk rules, and reusable assets. In the private business repository, run its knowledge registry `validate` and `load`, then actually read every `required_reads`; rapid mode is not an exception. In particular, do not omit `knowledge/test-risks/omission-risk-rules.json` because the task is time-boxed. Pending candidates are retrieved only as candidates, never treated as approved expectations.

For each task, locate and actually read applicable sources in this order:

1. Work-item state, handoff, decisions, artifacts, reconciliation, and run receipts.
2. Project `knowledge/INDEX.md` and `knowledge/manifest.json`, if present: validate hashes/status, load by feature/stage/platform/role, then read every required path. If absent, search repository system maps, domain rules, permissions, decisions, risk rules, and asset registers; absence of an index is not proof that no knowledge exists.
3. Latest approved requirements/business assertions and the single official case baseline, checking IDs and hashes.
4. Reviewed omission-risk rules (测试遗漏风险规则) and applicable test methods; risks inform coverage but do not define product expectations. Pending candidates are not facts.
5. Reusable feature/system assets, fixtures, page objects, helpers, package commands, execution receipts, and historical runs.
6. Executor capabilities, environment/version, authorization and privacy constraints.

For each task, first locate the feature in the system/feature map and existing work-item index, then read prior run receipts, defects, fixtures and execution assets. Reuse applicable understanding and verify only environment/version/role changes before continuing untested cases. If no feature entry exists, make a targeted discovery entry; do not repeat a full system exploration by default. Historical passes do not count as evidence for the current run. Record what was loaded, applicable rules, conflicts, exclusions, and unreadable/missing sources. Resolve conflicts by source authority, not retrieval rank or model confidence. Read-only knowledge routers are supported; their path list is not proof of understanding.

For SIT execution, select the account before opening the login page: use the approved account/fixture registry and prior run only to identify a unique non-secret alias, role and organization scope. If the target account is missing or ambiguous, ask once at task intake; if a matching authenticated session is available, reuse it after checking the actual role/scope. An existing SIT test authorization is not a request to ask permission for every login. Credentials must remain in approved runtime sources or a completed user handoff. A browser handoff succeeds only when the tool confirms completion; `UI not available` is a tool failure, not an invitation to ask the user to log in to an inaccessible window. If the user owns the task space, stop browser work until they explicitly return control; do not take it back on your own.

## Mode routing

Select and load the canonical skill; do not blend incompatible authority levels:

- Scattered source material or requirement review: `.agents/skills/requirement-spec-generate/SKILL.md`.
- Business flows, assertions, current business knowledge: `.agents/skills/generate-business-assertions/SKILL.md`.
- Formal cases, regression impact, test closure: `.agents/skills/test-case-generate/SKILL.md`.
- Time-boxed testing before formal requirement/case artifacts: `.agents/skills/rapid-test/SKILL.md`.
- 一站式测试（一次生成可见临时用例、执行已就绪场景并报告，不逐阶段等待审核）：`.agents/skills/one-pass-test/SKILL.md`。
- 首轮 Web 语义/视觉探索：Ego Lite负责观察、执行和回读；若 Jev advisor 已配置，它只能从有限只读候选动作中建议下一步。建议器不可用不阻断实际可用的执行器；实际浏览器控制缺失时只阻塞依赖 UI 的步骤，留下尝试与错误证据，继续功能地图/历史运行/Fixture/Oracle 等独立工作。按 `docs/web-ai-browser-stack.md` 和 `ai-test web-executor-check` 路由。
- Offline synthetic test recordings (speech/silence): `.agents/skills/test-recording-generate/SKILL.md`; business Fixture creation and cleanup remain under `test-data-and-account-fixture-management`.
- Test data and account fixtures (creation, isolation, permissions, cleanup, credential sourcing): `.agents/skills/test-data-and-account-fixture-management/SKILL.md`.
- Web/API/App/H5/mini-app execution: `.agents/skills/requirement-grounded-functional-testing/SKILL.md`.
- Missed scenarios, user corrections, false positives: `.agents/skills/test-omission-risk-retrospective/SKILL.md`.
- Reusable navigation, fixture, locator, recovery, environment or evidence learning: `.agents/skills/test-execution-asset-retrospective/SKILL.md`.
- End-to-end lifecycle or unclear stage: `.agents/skills/ai-test-workflow/SKILL.md`.

Rapid mode only temporarily defers the time-consuming formal requirement-specification, reviewed BF/A rule, and formal case-generation steps. One-pass mode (`test_mode=one_pass`) builds on the same knowledge/evidence safeguards and in one run generates visible provisional `OP-*` cases, executes ready cases and reports every case/step without repeated formal review. Neither mode skips knowledge loading (including omission-risk rules), risk-based design, action-before assertion/fixture/oracle freeze, evidence, triage, privacy, or execution logs. Neither creates an approved case baseline or release-gate result; both keep confirmed business expectations, independent Oracle, pre-action fixture/identity freeze, evidence and safety boundaries. One-pass cases with unresolved expected behavior remain blocked while ready cases proceed. Confirm mode entry only when the user's task does not already establish it. A request to test import/export in SIT includes ordinary test-fixture preparation, UI import submission, readback and UI export in that stated scope; do not narrow it to read-only or seek repeated confirmation. Production, real notifications, irreversible deletion, financial settlement or writes outside the test scope retain a separate authorization gate. A defect, critical rule gap, release decision or repeated regression triggers standard-flow follow-up. One-off exploration may close with an explicit technical-debt owner and due date.

## Test plan before execution — mandatory for every new test task

Before the first page/API/device action for a new test task, create and save a test-plan package in that requirement's work item/run directory. This applies to standard and rapid tasks and is an execution gate, not an optional summary. At minimum record purpose/objective, feature and scope/exclusions, mode, environment/platform/version, knowledge and baseline sources (or explicitly unavailable), coverage, roles, fixtures and their sourcing/uniqueness, assertions and independent Oracle, evidence, write/cleanup boundary, risks/open questions, stop conditions, and completion criteria. Re-freeze the plan when scope, baseline, environment, roles, fixtures, or risk changes; immediately before execution, verify its revision/hash and prerequisites.

Use existing contracts rather than creating a competing plan format: standard tasks use the work-item's reviewed scope, the approved case baseline when available, automation-readiness plan, and pre-execution confirmation; bind stable case IDs and freeze the plan hash after case approval. If standard-flow discovery begins before a baseline exists, first save an initial discovery plan that marks the baseline unavailable and limits actions to its approved safe scope; update the plan when requirements/cases are approved. Rapid tasks use the rapid-test charter as the provisional test plan plus separately versioned probes; these probes are not formal test cases. One-pass tasks use a frozen one-pass plan containing source-linked provisional `OP-*` cases and a separate results receipt; show the readable case list before action, run `ai-test one-pass-check` before execution and after result writeback, then deliver a scenario-level report. If no valid plan exists, no test execution may begin.

## Standard workflow and gates

Treat approved requirements and the reviewed test-case baseline as the source of truth. After requirement review, create an automation readiness plan before detailed execution knowledge is lost; include automatable/manual scope, environments/platforms, roles, fixture sourcing, evidence, risks, and open questions. Bind stable case IDs and freeze the plan hash after case approval. Before execution, reconfirm feature, environment, approved scope, roles, ready fixtures and exclusions against that hash; missing prerequisites block only dependent cases and unchanged gaps are not retried.

Before rule/case generation, classify topology as isolated, linked-confirmed, linked-candidate, or pending. Model confirmed behavior as stable `BF-*` flows with atomic `A-*` assertions; each flow step references assertions, and each confirmed flow has a complete E2E case declaring `covered_flow_ids` and `covered_rule_ids`. Run `ai-test flow-check` before accepting a baseline.

Use one task per requirement. When the user says `接手需求 <ID>`, run `ai-test work-item-show --root . --requirement-id <ID>` and read every path in `read_first` before proposing/executing work. Reconcile at takeover and before `CASE_DESIGN`. Every generated test plan, requirement, rule, case, handoff, report, or script artifact is registered with stable ID, path, SHA-256, review status, and stage. A generated review page without a validated review receipt is still pending. Never write a new requirement into another requirement's state.

## Automation, execution, and safety

Before creating or substantially rewriting an automation script, search the feature directory, page objects, shared helpers, package commands, execution asset registers, and prior run artifacts. Record every candidate as `reuse`, `extend`, `reject`, or `supersede`, with rationale, then run `ai-test automation-asset-reuse-check`. A blocked/missing receipt prohibits adding a competing script; extend the official asset unless the receipt proves a concrete gap.

Before the first test action of every automation run, call `ai-test execution-log-start` with stable automation ID, unique run ID, environment, platform, purpose, objective, scope, and the applicable approved baseline (or explicitly provisional rapid-test charter reference). After reporting and asset feedback, call `ai-test execution-log-finish`. Keep `AUTOMATION_EXECUTION_HISTORY.md` as the fixed human-readable history; preserve blocked/interrupted runs.

Never put passwords, tokens, cookies, keys, personal/customer data, or private endpoints in project assets or reports. Use runtime secure references. Confirm authorization before destructive production actions, bulk writes, real notifications, or other irreversible operations. Stop a UI step after two minutes without page/network/download/log/state progress; save available evidence and report the blocker.
