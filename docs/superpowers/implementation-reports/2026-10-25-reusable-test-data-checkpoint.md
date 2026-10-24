# 通用测试数据：首批实施检查点

完整 v0.2 尚未完成。当前交付范围、修正、验证和全部决策记录如下；保留工作区以继续后续任务。独立复核针对初始代码，最终修正由执行者以失败测试再转通过验证，没有声称第二轮独立复核。

# SDD ledger — plan: docs/superpowers/plans/2026-10-24-reusable-test-data.md

Approval: user explicitly approved v0.2 implementation, historical inventory, factories, migration, SIT/99 regression and Notion synchronization on 2026-10-25.
Baseline: framework 0f37ec8 (204 tests pass); business cb9a090; isolated feat/reusable-fixtures worktrees.
Pre-flight interfaces: Task1 consumer inventory feeds Task2 bindings and Task6 migration. Task2 explicit versioned target binding feeds Task3 health, Task4 physical locks, Task5 recipe execution and Task8 readiness. Task5 environment-local outputs feed Task7 content packages. No alternate business runner or independent case baseline.
Ruling: retain same work item and record user approval; CASE_DESIGN is not the gate for framework unit development, original business baselines remain authoritative for later live regression. Cost if wrong: business-only gates could be bypassed; mitigate with separately frozen live plans.
Ruling: use git worktree fallback for the second repository because the native worktree tool only targets this chat's framework repository. Do not copy runtime credentials.
Task 1: in_progress. Read original main work item registry (25 manifests) as well as isolated source tree; imported runtime evidence is not a current business pass.

2026-10-25 implementation checkpoint: Tasks 1-5 and 8 partially implemented; Tasks 6-7 remain partial/pending. No task marked complete without full acceptance.
Task 2: Ruling: combine small model/health/lease implementation in registry.py and keep provider adapters in private repository; same contracts, fewer files. Cost if wrong: later module split needed, no business semantic change.
Task 5: Ruling: conservative factory lock spans zone+brand because service names belong to the brand across stores. Cost if wrong: unrelated same-brand preparations wait unnecessarily; avoids duplicate creation.
Task 6: Ruling: migrate the existing six-service catalog check/ensure first; retain all other consumers with explicit defer until their state and Oracle contracts are mapped. Cost if wrong: remaining scripts still bypass new locks, so no global concurrency guarantee.
Evidence: public core tests RED then GREEN; private adapter tests RED then GREEN; live service check 6 SIT + 6 z99 passed in RUN-FIXTURE-SERVICES-20261025-001. This is fixture-contract regression only.

2026-10-25 checkpoint review and fix pass:
Final: fixed runtime-created binding consumption and pre-create missing-binding guard — new regression failures observed, then GREEN; full public suite 241 and private fixture suite 9 passed.
Final: fixed observation replay — test_old_observation_cannot_refresh_health RED→GREEN; actual observed_at controls TTL.
Final: fixed lease resource validation — test_lease_checks_health_expiry_and_fingerprint RED→GREEN; quarantine, expiry and attribute drift reject action/heartbeat.
Final: fixed cross-store alias lock — test_cross_store_alias_cannot_bypass_lock_or_quarantine RED→GREEN.
Final: fixed store-specific intent — test_distinct_store_instances_have_distinct_intents RED→GREEN.
Final: regraded handbook receipt mismatch from Minor to Important because it can falsely label unverified data passed; version/target/catalog negative tests RED→GREEN. No deferred minor from this review.
Final: fixed release report after quarantine and readiness lease conflict via additional RED→GREEN tests.
Ruling: conservatively lock every entity ID at brand scope until verified entity-scope contracts exist — prevents cross-store shared-object bypass — cost: unrelated store-local equal IDs can wait unnecessarily.
Ruling: preserve schema-v1 active leases and refuse migration while any is active; otherwise migrate physical keys and expire health — avoids stale locks becoming invisible — cost: recovery remains manually reconciled.
Ruling: observations are trusted local Provider receipts, not cryptographically authenticated remote attestations — timestamps prevent accidental stale replay, not a malicious local writer — cost: callers must not hand-fabricate evidence.
Ruling: separate current data readiness from create capability; missing brand writer identity blocks creates while verified existing objects remain usable — cost: caller must read both statuses.
Final: Ruling: full historical Case/consumer migration, account/login rename and password reset are unfinished — keep old assets and mark not executed — cost: legacy scripts remain outside locks.
Final: Ruling: appointment/goal/order/recording composite adapters and miniapp content/independent scoring Oracle remain pending — missing verified creation/state contracts are not inferred — cost: those workflows still need dedicated preparation.
Final: Ruling: UI/device/permission regression and legacy classification/code business semantics are not established by service detail checks — retain original Case gates — cost: broader acceptance cannot be claimed.
Final: Ruling: real writer compatibility is blocked by live brand guard and historical admin identity mismatch — do not weaken identity checks or guess a new account — cost: creation waits for correct writer mapping.
Final: Ruling: remote fencing, cross-machine coordination, manual/unmigrated bypass, automatic crash recovery, and alternate-database detection are not provided — expired/unknown effects stay blocked — cost: operator reconciliation and external changes remain outside guarantees.
Final: Ruling: independent reviewer ran only 28 public fixture and 7 private tests on initial commits; final executor ran full 241 public, 26 query and 9 private tests and live 12 service checks — evidence attribution stays explicit — cost: final fixes have TDD verification, no second reviewer.
Final: Ruling: Notion is checked by executor readback, not independently by reviewer — publication evidence stored per run — cost: no claim of independent external review.
Workflow reference test: fresh baseline agent found all five entrypoint gaps (directory, needs, target prepare, lease, handbook); updated canonical fixture Skill; second fresh agent correctly recovered all five and rejected planned-as-ready / hardcoded-ID bypass. Pure reference update, microtest wording variants not applicable.
Validation: docs-check, skills-check passed; final live RUN-FIXTURE-SERVICES-20261025-003 has 6 SIT + 6 z99, frozen needs, aligned fields and readonly readiness. Business writes zero. Earlier 002 log registration order deviation retained; 003 correctly logged before actions.
All Tasks remain in_progress/partial; this is a checkpoint, not whole-plan completion. Keep workspace for continuation. Notion handbook/design synchronized; final readback follows.
