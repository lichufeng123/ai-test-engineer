---
name: generate-business-assertions
description: Use when reviewed requirements and current business knowledge must be converted into traceable business-flow rules, atomic assertions, change sets, and a human review gate before test-case generation.
license: MIT
metadata:
  author: ai-test-engineer
  version: "0.4.0"
---

# 生成业务流程与原子断言

建立两层规则模型：`BF-*` 描述参与者、平台、顺序、状态迁移和下游回读；`A-*` 描述一条可独立验证的业务预期。系统地图和AI推导只能产生候选，不能自动升级为已确认规则。

## 输入门禁

- 使用审核通过且带哈希的需求说明或用户明确认可的等价来源。
- 加载当前规则基线、系统地图、角色、实体、平台、接口和已有产品决策。
- 记录来源版本、适用范围和冲突；检索结果未经权威基线校验时只作为风险线索。

## 建模

1. 将功能拓扑标为 `isolated`、`linked_confirmed`、`linked_candidate` 或 `pending`。
2. 已确认关联功能建立完整 `BF-<DOMAIN>-NNN`；孤立功能也建立模块内流程。流程包含触发、参与者、平台、前置、起止状态、顺序步骤、可观察输出和失败分支。
3. 每个流程步骤引用一个或多个 `A-*`。断言采用“在前置状态下，当角色或系统触发动作时，系统必须/不得产生可观察结果”的单一语义。
4. 字段、公式、权限、状态、范围、幂等、并发和失败回滚能够独立失败时拆开。
5. 更新当前基线时标记 `ADD/MODIFY/REMOVE/UNCHANGED`；修改保留稳定ID和旧值，删除保留审核记录，不能从“本次没提到”推断删除。
6. 来源冲突、关键参数缺失和候选关系保留为待确认项，不自行选边。

## 审核与门禁

审核入口先展示业务流程，再展示原子断言、来源、变更、冲突和覆盖审计。产品经理对流程和规则分别做最终审核。

审核后保存：

- `business_topology.json`
- `business_flows.json`
- `atomic_assertions.json`
- `rule_change_set.json`
- `flow_assertion_matrix.json`
- `rule_review_receipt.json`

使用以下门禁验证流程引用：

```bash
ai-test flow-check --input rules/business-flows.json
```

任何已确认流程缺少步骤、步骤引用不存在的断言或P0问题未关闭时，不得进入正式用例生成。通过后把稳定流程ID、断言ID、来源和审核摘要交给 `test-case-generate`。
