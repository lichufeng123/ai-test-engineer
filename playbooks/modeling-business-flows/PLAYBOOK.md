# Modeling Business Flows

Use this playbook before formal business-rule and test-case generation. Its purpose is to prevent a page-level requirement from losing its upstream trigger, downstream consumer, role boundary, or cross-platform result.

## 1. Build the topology hypothesis

Read the available requirement, system navigation map, entity model, role-permission matrix, known platform links, interfaces, current business rules, and conversation decisions. From those sources, list:

- the action's upstream trigger;
- the entity or state written by the action;
- modules, roles, jobs, reports, App, H5, mini-app, or devices that may read it;
- known exclusions and their evidence.

Do this before asking the product owner. If evidence is incomplete, ask a focused question that includes the inferred candidates and their source, impact, recommended interpretation, and requested confirmation.

## 2. Classify the feature

Choose one topology classification:

- `isolated`: confirmed local-only behavior;
- `linked_confirmed`: one or more links are confirmed;
- `linked_candidate`: candidates exist but are not yet confirmed;
- `pending`: evidence is insufficient to proceed.

An isolated feature still needs one local flow from trigger to observable result. A linked feature needs every confirmed cross-module or cross-platform path.

## 3. Write reviewed flow rules

Assign stable `BF-<DOMAIN>-NNN` IDs. Each flow records:

- trigger, actors, platforms, preconditions, start and end states;
- ordered steps with owning and related modules;
- the state transition and observable output at each step;
- atomic `A-*` assertions referenced by each step;
- failure branches and source references.

Keep inferred or disputed paths as candidates. Do not publish them as confirmed rules until reviewed.

## 4. Generate cases from both layers

Generate local functional cases from the atomic assertions. For every confirmed flow, generate at least one end-to-end case whose `covered_flow_ids` contains the flow ID and whose `covered_rule_ids` contains every assertion referenced by that flow's steps.

Add separate cases where role changes, asynchronous work, retries, rollback, data scope, or platform boundaries create materially different paths.

## 5. Run the gate

```bash
ai-test flow-check \
  --input ./rules/business-flows.json \
  --cases ./cases/approved-baseline.json \
  --matrix-output ./runs/latest/flow-coverage.json
```

Do not accept the baseline while the command reports a confirmed flow without a complete end-to-end case, a missing step assertion, or an unknown reference.

## 6. Feed discoveries back

During execution, keep observed product behavior separate from approved rules. Confirm any new business decision, then update the flow, atomic assertion, formal case baseline, and execution asset together. Preserve stable IDs when meaning is unchanged.
