---
name: test-omission-risk-retrospective
description: Use when completed testing or defect regression exposes missed scenarios, user corrections, false positives, or recurring defect patterns that future test-case generation must retrieve as reviewed omission-risk rules.
license: MIT
metadata:
  author: ai-test-engineer
  version: "0.1.0"
---

# 测试遗漏风险复盘

把一次执行中暴露的漏测、误判和用户纠正，沉淀为可检索的测试设计经验。统一知识文档名为《测试遗漏风险规则库》。它用于提醒后续生成用例检查高风险维度，不能替代已审核需求、业务规则或正式用例基线。

## 触发时机

在 `ISSUE_TRIAGE` 完成后、`RESULT_WRITEBACK` 前执行 `OMISSION_RISK_RETROSPECTIVE`。以下任一情况必须触发：

- 实际缺陷暴露出原用例遗漏的角色、范围、状态、数据关系、入口或下游回读。
- 用户明确指出漏测、误判、无效场景或错误预期。
- 缺陷修复回归发现同一模式可能影响其他模块或环境。
- 执行资产解决了操作问题，但仍有可复用的测试设计经验需要反哺。

## 分类

逐项保留证据和来源，并分类为：

1. `confirmed_omission_risk`：已证实会造成漏测的设计风险，后续必须评估适用性。
2. `confirmed_product_rule`：已有审核口径支持的业务事实，可引用对应稳定规则 ID。
3. `false_positive_exclusion`：测试误判或用户明确排除的场景，防止再次误报。
4. `pending_product_decision`：只有现象或推测，不能成为正式预期。

缺陷现象不能自动升级为产品规则。用例的预期结果仍以当前已审核需求和业务规则为准。

## 复盘步骤

1. 读取本轮用例、执行结果、缺陷、回归证据、用户纠正和已有风险规则。
2. 把根因拆成可复用条件：功能类型、角色、组织范围、数据关系、状态、环境、入口和下游。
3. 与现有规则按稳定 ID 去重；同一模式更新原条目，不能重复追加近义规则。
4. 为每条风险写明：触发条件、遗漏后果、生成用例要求、所需数据、证据、适用/不适用边界和来源。
5. 生成 `omission_risk_change_set.json` 与人审摘要。通过审核后更新《测试遗漏风险规则库》同一 current 文档。
6. 对本轮已漏用例生成同一正式用例基线的补充差异；执行状态不能偷偷改变预期。

## 强制规则示例

当功能包含搜索、筛选、选择器或关联候选，且系统存在连锁与门店两个数据范围时，必须分别评估连锁和门店视角。顾客还要覆盖是否关联连锁；员工还要覆盖连锁归属、门店归属和授权范围。若某视角明确不支持该能力，仍需在审计中记录 `not_applicable` 及依据，不能静默省略。

涉及按难度、等级或策略分档的训练流程时，每档必须独立覆盖配置保存、下发、运行态参数、提前达标和最大轮次未达标。回答质量属于测试数据；全用高质量回答不能证明最大轮次终止正确。

## 产物契约

`omission_risk_change_set.json` 至少包含：

- `risk_id`、标题、分类和状态。
- 触发条件与适用平台、角色、组织、数据关系、状态和环境。
- 漏测后果、要求生成的测试场景及数据准备。
- 对应需求/规则/用例/缺陷/证据 ID。
- `source_run_id`、`last_verified_at`、审核结果和不适用依据。

知识文档和本地产物不得保存账号、密码、Cookie、Token、真实客户明细或一次性敏感标识。

## 下轮用例生成

`test-case-generate` 在 `CURRENT_RETRIEVAL` 内必须检索《测试遗漏风险规则库》，输出 `omission_risk_audit.json`。每条命中规则只能处于以下状态之一：

- `covered`：已映射到本轮独立用例 ID。
- `not_applicable`：有审核依据。
- `blocked`：缺业务口径或测试数据，已形成一次性待办。
- `pending_review`：需要产品确认，不能进入正式预期。

适用风险没有用例映射或有效处置时，正式用例审核不能通过。
