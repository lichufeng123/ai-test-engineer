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

Record what was loaded, applicable rules, conflicts, exclusions, and unreadable/missing sources. Resolve conflicts by source authority, not retrieval rank or model confidence. Read-only knowledge routers are supported; their path list is not proof of understanding.

## Mode routing

Select and load the canonical skill; do not blend incompatible authority levels:

- Scattered source material or requirement review: `.agents/skills/requirement-spec-generate/SKILL.md`.
- Business flows, assertions, current business knowledge: `.agents/skills/generate-business-assertions/SKILL.md`.
- Formal cases, regression impact, test closure: `.agents/skills/test-case-generate/SKILL.md`.
- Time-boxed testing before formal requirement/case artifacts: `.agents/skills/rapid-test/SKILL.md`.
- 首轮 Web 语义/视觉探索：Ego Lite负责观察、执行和回读；Jev advisor 参与从有限只读候选动作中建议下一步。Jev 不得生成任意脚本/选择器/URL、执行写入、选择业务目标、改变预期或裁决结果；无配置、低置信、无进展及 Provider 错误均需显式阻塞/安全停止，按 `docs/web-ai-browser-stack.md` 和 `ai-test web-executor-check` 路由。
- Web/API/App/H5/mini-app execution: `.agents/skills/requirement-grounded-functional-testing/SKILL.md`.
- 首轮 Web 语义/视觉探索：默认由 Ego Lite 观察执行；若 Jev advisor 已配置，按 `docs/web-ai-browser-stack.md` 让 Jev 仅从本地生成的有限只读候选动作中建议下一步，Ego Lite 负责执行、回读并留存 advisory 收据。Jev 不得生成任意命令/选择器/URL、执行写入、挑选业务目标或裁定测试结果；不可用/低置信/无进展/Provider错误时安全停止。
- Missed scenarios, user corrections, false positives: `.agents/skills/test-omission-risk-retrospective/SKILL.md`.
- Reusable navigation, fixture, locator, recovery, environment or evidence learning: `.agents/skills/test-execution-asset-retrospective/SKILL.md`.
- End-to-end lifecycle or unclear stage: `.agents/skills/ai-test-workflow/SKILL.md`.

Rapid mode only temporarily defers the time-consuming formal requirement-specification, reviewed BF/A rule, and formal case-generation steps. It does not skip knowledge loading (including omission-risk rules), risk-based test design, action-before assertion/fixture/oracle freeze, evidence, triage, privacy, or execution logs. Rapid testing creates a temporary charter and versioned probes/assertions, not formal test cases or a new approved baseline; do not silently register probe lists as test cases. Its results are provisional and cannot claim full formal-baseline, acceptance, or release-gate coverage. An explicit user choice of rapid mode satisfies mode entry; do not block rapid SIT probes on the standard `CASE_DESIGN` gate, rule-review receipt, Current synchronization, or a formal case baseline. When the user has authorized necessary isolated SIT fixture creation and the named test actions, carry those authorized writes forward without asking again; freeze each probe's unique target, expected observation, independent oracle, side effects and cleanup before acting. Production, bulk, real notifications and unapproved irreversible financial effects retain their separate authorization gate. A defect, critical rule gap, release decision, repeated regression, or material side effect triggers standard-flow follow-up without retroactively invalidating the rapid probe evidence. One-off exploration may close with an explicit technical-debt owner and due date.

## Test plan before execution — mandatory for every new test task

Before the first page/API/device action for a new test task, create and save a test-plan package in that requirement's work item/run directory. This applies to standard and rapid tasks and is an execution gate, not an optional summary. At minimum record purpose/objective, feature and scope/exclusions, mode, environment/platform/version, knowledge and baseline sources (or explicitly unavailable), coverage, roles, fixtures and their sourcing/uniqueness, assertions and independent Oracle, evidence, write/cleanup boundary, risks/open questions, stop conditions, and completion criteria. Re-freeze the plan when scope, baseline, environment, roles, fixtures, or risk changes; immediately before execution, verify its revision/hash and prerequisites.

Use existing contracts rather than creating a competing plan format: standard tasks use the work-item's reviewed scope, the approved case baseline when available, automation-readiness plan, and pre-execution confirmation; bind stable case IDs and freeze the plan hash after case approval. If standard-flow discovery begins before a baseline exists, first save an initial discovery plan that marks the baseline unavailable and limits actions to its approved safe scope; update the plan when requirements/cases are approved. Rapid tasks use the rapid-test charter as the provisional test plan plus separately versioned probes; these probes are not formal test cases. If no valid plan exists, no test execution may begin.

## Standard workflow and gates

Treat approved requirements and the reviewed test-case baseline as the source of truth. After requirement review, create an automation readiness plan before detailed execution knowledge is lost; include automatable/manual scope, environments/platforms, roles, fixture sourcing, evidence, risks, and open questions. Bind stable case IDs and freeze the plan hash after case approval. Before execution, reconfirm feature, environment, approved scope, roles, ready fixtures and exclusions against that hash; missing prerequisites block only dependent cases and unchanged gaps are not retried.

Before rule/case generation, classify topology as isolated, linked-confirmed, linked-candidate, or pending. Model confirmed behavior as stable `BF-*` flows with atomic `A-*` assertions; each flow step references assertions, and each confirmed flow has a complete E2E case declaring `covered_flow_ids` and `covered_rule_ids`. Run `ai-test flow-check` before accepting a baseline.

Use one task per requirement. When the user says `接手需求 <ID>`, run `ai-test work-item-show --root . --requirement-id <ID>` and read every path in `read_first` before proposing/executing work. Reconcile at takeover and before `CASE_DESIGN`. Every generated test plan, requirement, rule, case, handoff, report, or script artifact is registered with stable ID, path, SHA-256, review status, and stage. A generated review page without a validated review receipt is still pending. Never write a new requirement into another requirement's state.

## Automation, execution, and safety

每次打开、恢复或重新连接浏览器窗口后，以及切换账号、组织或浏览器上下文后，必须在首个业务动作前重新核验当前界面版本，不能沿用另一窗口或上次运行的结论。目标为新版时，先核对环境、账号与组织，再打开当前账号的原生菜单；如显示“切换到新版”，必须通过该入口切换，并回读“切换到旧版”作为新版证据。记录界面版本、构建版本和原图/回执；构建版本号、URL、页面外观或登录成功均不能单独证明已进入新版。门店无切换菜单时使用已审核的门店身份/版本合同。未通过时仅阻塞依赖该版本的动作；误在旧版执行的异常保留为历史观察，切到正确版本复核前不得定为新版缺陷。复用已有 `ensureNewInterface` / `ensure_new_interface` 与 `ai-test web-interface-check`，不要只口头确认。

Before creating or substantially rewriting an automation script, search the feature directory, page objects, shared helpers, package commands, execution asset registers, and prior run artifacts. Record every candidate as `reuse`, `extend`, `reject`, or `supersede`, with rationale, then run `ai-test automation-asset-reuse-check`. A blocked/missing receipt prohibits adding a competing script; extend the official asset unless the receipt proves a concrete gap.

Before the first test action of every automation run, call `ai-test execution-log-start` with stable automation ID, unique run ID, environment, platform, purpose, objective, scope, and the applicable approved baseline (or explicitly provisional rapid-test charter reference). After reporting and asset feedback, call `ai-test execution-log-finish`. Keep `AUTOMATION_EXECUTION_HISTORY.md` as the fixed human-readable history; preserve blocked/interrupted runs.

Never put passwords, tokens, cookies, keys, personal/customer data, or private endpoints in project assets or reports. Use runtime secure references. When login is already authorized for the task's environment, role, and organization, expired SIT sessions trigger a check of existing secure runtime references and an autonomous login attempt in the affected executor, followed by identity readback; do not ask for renewed login permission or default to manual login. Ego Lite and Playwright have separate auth prerequisites. Only missing/unusable secure references, identity mismatch, or user-only MFA/CAPTCHA block dependent cases; name the precise missing prerequisite without exposing values and continue independent work. Login authorization does not approve new business writes or unknown expectations. Confirm authorization before destructive production actions, bulk writes, real notifications, or other irreversible operations. Stop a UI step after two minutes without page/network/download/log/state progress; save available evidence and report the blocker.

## 历史会话归档（2026-10-20 从 WorkTony/pi 迁移）

历史协作记录已导出为 Markdown：~/Documents/codex-handoff/pi-archive/

- 索引：pi-archive/INDEX.md
- 本项目历史：pi-archive/test-tool__ai-test-engineer/
- 原始事件日志：pi-archive/_raw/

使用规则：
1. 需要继承历史决策、约定、未完成事项时，先读 INDEX.md，再读相关会话 md，不要凭记忆推测。
2. 全文检索：grep -ril "关键词" ~/Documents/codex-handoff/pi-archive --include="*.md"
3. 归档是历史证据，不是当前事实。与当前仓库冲突时以仓库为准，并明确说明冲突点。
4. 归档可能含旧口令、token、客户信息，不要复述或提交。


## 交互体验检查：每轮 UI 测试必需

标准、快速、一站式测试、用例设计及缺陷回归都要主动检查交互体验，不能只验证最终数据或接口成功。执行前按 [交互体验检查](.agents/skills/requirement-grounded-functional-testing/references/interaction-experience.md) 将加载与状态一致性、布局/滚动、控件反馈、输入/上下文保留、异常恢复、可读可达六个维度纳入既有计划；收口逐项回填已检查及结论、不适用及原因、阻塞或未执行，并保留动态过程证据。有具体影响且依据明确的问题主动按既有提单流程提报；可复现的误导、阻断、无反馈或额外寻找等实际影响本身可作为体验问题依据，不因缺书面需求而漏报；产品口径有冲突或影响不确定时带证据向用户确认，不等用户逐个指出。先核对 Demo HTML/原型/需求和用户说明，严格区分预期参考与实际现场；不把个人审美或某个页面的统一 loading 要求推广成全局产品规则。


## 验收后的台账回写：必需

用户于 2026-10-24 要求：每条 Bug 验收完成，无论通过或失败，都必须立即更新项目配置的协作台账并回读确认，不等整批收尾。按实际安装的 `resolved-bug-acceptance` Skill 中 `references/acceptance-ledger-writeback.md` 执行；主项目没有本地验收 Skill 时读取 `~/.codex/skills/resolved-bug-acceptance/SKILL.md`，不得跳过。源状态和验收结果分离，阻塞/未执行不得写成通过/失败；写回失败保留待同步回执，向用户说明，继续独立验收。未完成台账回读不能宣称闭环完成。


## 多端权限组合覆盖：必需

涉及权限时，先按当前需求/原型盘点配置端与消费端，逐端建立角色/组织 × 权限组合矩阵；两个独立查看权限必须逐端评估无权限、仅自己、仅全部、双权限。每格绑定稳定用例和预期来源，执行后分别回填 run_id、状态与证据。门店 Web、商家版、App/H5/小程序等适用端不得互相替代，未执行或阻塞明确列出，不适用要有依据。按本项目 `.agents/skills/test-case-generate/references/permission-testing.md` 执行；设计工具只检查已声明矩阵，不证明端盘点完整或真实执行通过。
