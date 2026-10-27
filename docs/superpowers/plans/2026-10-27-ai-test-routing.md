# AI Test Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing readiness gate with explicit AI roles, independent Oracle resources and testability assessments while retaining v1 behavior.

**Architecture:** A focused ai_test_routing module validates/freeze v2 contracts and evaluates per-Case prerequisites; execution_readiness keeps existing role/fixture/environment gates and merges routing results. The existing CLI loads/fingerprints a controlled catalog. No model runtime, business write or second Runner.

**Tech Stack:** Python standard library, JSON Schema, unittest.

**Spec:** docs/superpowers/specs/2026-10-24-ai-assisted-test-routing-design.md (user approved; implementation already authorized).

## Global Constraints

- Version1 plans without AI fields preserve existing results. Version2 requires a strategy, assertion Oracle bindings and testability coverage for every Case.
- Required capability absence blocks the whole dependent Case; recommended/optional absence never trims its assertions. Only reviewed, independently identified child Cases execute separately.
- AI authority is input/advisory/review only. Reference answers and blueprints are inputs, never product/semantic Oracle.
- Catalog bytes/path/id/hash are frozen; fresh checks carry identity, time and evidence. Configuration alone does not establish availability.
- Public examples are fictional. Private functionality catalog is method knowledge, with no credentials or product expectations.
- Existing ANSWER_REQUIRED handoff is retained. No new model orchestration, private endpoint or business write.

## Review Focus

- Forged or stale resource checks, duplicate identities, mismatched environment and catalog drift fail closed.
- Composite Oracle requires every stated authority and every referenced resource, not any one match.
- Deterministic fallback must be an approved reference bound to the same question/version/hash and full Case scope; an open-dialogue blueprint never removes a runtime AI dependency.
- Recommended AI cannot carry a formal assertion; human_required still needs an independent human review receipt.
- Invalid v2 data or hidden AI fields in v1 cannot bypass the gate; unrelated v1 readiness remains unchanged.

### Task 1: Validate and freeze v2 readiness

**Files:** new src/ai_test_framework/ai_test_routing.py, tests/test_ai_test_routing.py; modify execution_readiness.py and cli.py.

**Interfaces:** build_readiness_plan(source, *, ai_capability_catalog=None, catalog_provenance=None) freezes catalog_ref and ai_capabilities. validate_routing_plan(plan,catalog,provenance) validates controlled input; CLI --ai-capability-catalog resolves and hashes bytes relative to source parent. Source catalog_ref contains path/catalog_id/sha256.

- [ ] Write tests for v1 compatibility, v2 missing catalog/hash mismatch, duplicate/unknown/unbound capabilities, strategies, role/authority restrictions, Oracle/input separation, composite rules and all-Case testability coverage.
- [ ] Run `PYTHONPATH=src python -m unittest discover -s tests -p test_ai_test_routing.py` and observe failure on unsupported v2.
- [ ] Implement deterministic validation and immutable copies; no discovery/model invocation.
- [ ] Run targeted readiness/routing tests; expect all green.
- [ ] Commit validated contract.

### Task 2: Gate fresh resource checks without changing Case scope

**Files:** ai_test_routing.py, execution_readiness.py, tests/test_ai_test_routing.py.

**Interfaces:** evaluate_routing(plan,confirmation) returns per-Case missing_ai_capability_ids/missing_oracle_ids, warnings and execution_recommendations. Merge into the original readiness receipt and missing-prerequisite fingerprints. CLI readonly verifies frozen catalog bytes before readiness-check.

- [ ] Write tests for required/recommended/optional missing, available recovery, stale/missing/duplicate/wrong-identity checks, independent approved/human/composite Oracle, stable child Case isolation, reviewed reference fallback and blueprint rejection.
- [ ] Run tests RED, implement exact-ID/time/environment/resource contracts, then GREEN.
- [ ] Run whole unittest suite; expect old results retained and all new scope checks passing.
- [ ] Commit routing gate.

### Task 3: Schemas, examples, knowledge and usage

**Files:** schemas/ai-test-capability-catalog.schema.json, automation-readiness.schema.json, pre-execution-confirmation.schema.json; templates/ai-test-capability-catalog.example.json, automation-readiness-v2.example.json; docs/AI_ASSISTED_TESTING_ROUTING.zh-CN.md; README.md, README.zh-CN.md, docs/FRAMEWORK.md and three canonical Skills. Private knowledge/test-methods/ai-assisted-feature-catalog.json plus manifest.

**Interfaces:** CLI uses the same files as direct builder, example catalog SHA is the actual serialized-byte SHA. Seven roles and ten initial feature method entries do not assert business acceptance.

- [ ] Add schema/CLI fixture tests including real catalog-file drift and deterministic no-AI cases; observe RED.
- [ ] Implement schemas/examples/docs and controlled private method registration.
- [ ] Run all tests, schema/example JSON validation, docs/skills/privacy checks and knowledge validation. Read complete output, register artifact hashes, then one fresh review of the new routing range. Address Important findings once with RED/GREEN; record minors.
- [ ] Commit and push authorized checkpoint; update the existing work item/handbook without declaring the whole historical migration complete.
