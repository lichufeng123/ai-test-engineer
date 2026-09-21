---
name: generate-business-assertions
description: Use when reviewed requirements and current business knowledge must be converted into traceable business-flow rules, atomic assertions, change sets, and a human review gate before test-case generation.
license: MIT
metadata:
  author: ai-test-engineer
  version: "0.4.2"
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

涉及新增、编辑、导入、关联/取消关联、改派或状态修改，且结果被列表查询消费时，加载 [写入后搜索与筛选生效规则](../test-case-generate/references/list-result-consistency.md)。在适用 `BF-*` 中纳入写入、回显、新条件查询/筛选、旧条件结果及持久化回读，并拆出对应 `A-*`；回显正确不能替代搜索可达和筛选归属正确。关联后验证对象身份与可查询属性一致，不强制具体存储实现。

## 审核与门禁

涉及权限时读取 [权限测试设计规范](../test-case-generate/references/permission-testing.md)，同时建模授权流程 `BF-*` 和权限原子断言 `A-*`。区分上级资格、角色动作和组织范围；浏览与编辑依赖及生效时机必须有来源，不把系统特例升级为通用业务事实。

审核入口先展示业务流程，再展示原子断言、来源、变更、冲突和覆盖审计。产品经理对流程和规则分别做最终审核。页面必须支持在二次确认后批量通过全部业务流程、当前筛选断言或当前业务域断言，并把批量结果保存为与逐条审核等价的逐项 `approved` 结论；批量后仍可逐条修改。“需修改、待决策、不适用”、删除断言、依赖域与完整性审批不得批量设置，必须逐项填写或确认。

依赖人审不能只展示英文模块编码或 `covered/current_fact` 等机器状态。每个必查业务域必须展示中文业务域名称、具体职责、关联 `BF-*` 业务流程、判断依据、本轮影响、覆盖状态和优先级；英文编码只作为辅助标识。

完整闭环必须在生成时根据已审核需求自动填充 `impact_audit.target_scope` 的中文主需求和主模块。审核页要提供可编辑的主需求输入框、候选主模块多选和自定义模块输入，不能只提示“未填写”却不给填写入口；结构校验必须拒绝空主需求或空主模块。

审核后保存：

- `business_topology.json`
- `business_flows.json`
- `atomic_assertions.json`
- `rule_change_set.json`
- `flow_assertion_matrix.json`
- `rule_review_receipt.json`

审核页生成并通过机器校验后，必须立即登记为待审核产物，不能等到后续会话手工回写：

```bash
ai-test work-item-artifact-register \
  --root <project-root> --requirement-id <REQ-ID> \
  --artifact-id <稳定审核页产物ID> \
  --artifact-type business_assertion_review_page \
  --path <business_assertions_review.html> \
  --status review_pending --stage BUSINESS_ASSERTION_REVIEW \
  --baseline-id <BL-ID>
```

人工审核导出通过校验后，再把 `rule_review_receipt.json` 以 `artifact_type=rule_review_receipt`、`status=review_validated`、`stage=RULE_CURRENT_SYNC` 登记。规则 Current 同步完成后登记 `artifact_type=rule_current_sync_disposition`、`status=synced`；标准生成不写外部 Current 时也必须生成有原因的处置回执并登记为 `status=not_applicable`。登记后运行 `ai-test work-item-reconcile`；没有审核导出和审核回执时，不得把审核页“已生成”表述为规则审核完成。

使用以下门禁验证流程引用：

```bash
ai-test flow-check --input rules/business-flows.json
```

任何已确认流程缺少步骤、步骤引用不存在的断言或P0问题未关闭时，不得进入正式用例生成。通过后把稳定流程ID、断言ID、来源和审核摘要交给 `test-case-generate`。
