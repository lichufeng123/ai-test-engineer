---
name: test-case-generate
description: Use when approved requirements and business rules must become reviewed functional test cases, regression impact, execution handoff, or test-discovered case updates without creating a competing baseline.
license: MIT
metadata:
  author: ai-test-engineer
  version: "0.8.0"
---

# 测试用例生成与反哺

正式测试用例只有一个团队审核基线。本Skill负责生成或更新该基线，并为自动化派生执行包；自动化脚本不得另建一套预期。

## 开始前

1. 冻结已审核需求、业务拓扑、`BF-*`流程、`A-*`断言、当前用例、产品决策和来源哈希。
2. 运行 `ai-test work-item-reconcile --root <project-root> --requirement-id <REQ-ID>`。只有 `case_design_gate.status=passed`，且已登记的自动化准备度计划、`rule_review_receipt`，以及规则 Current 已同步或本轮明确不适用的处置回执均存在、哈希一致、状态有效时，才能进入正式用例设计。
3. 若需求材料已表明跨模块、角色、平台或异步联动，必须生成端到端链路用例。材料只描述单页时，先根据系统地图推导候选上下游，再定向确认。
4. 规则审核、P0问题、冲突、当前基线校验或工作项产物对账未完成时，不生成可执行的正式版本。业务断言审核页存在但没有审核导出和审核回执时，仍属于 `BUSINESS_ASSERTION_REVIEW`。
5. 在 `CURRENT_RETRIEVAL` 内检索当前《测试遗漏风险规则库》，按功能、角色、组织范围、数据关系、状态和平台评估命中项，生成 `omission_risk_audit.json`。风险规则用于补充测试维度；正式预期仍来自已审核需求和业务规则。

## 用例设计

含权限开关、角色或数据范围时，必须先读取 [权限测试设计规范](references/permission-testing.md)。先隔离配置层与访问视角，再生成权限矩阵和用例；浏览/编辑联动、授权范围、生效动作、撤权、跳转及接口绕过不能只靠通用角色标签覆盖。运行 `ai-test permission-check` 保存设计覆盖回执，随后执行独立语义复核；未决契约不得变成正式预期。

涉及列表、搜索、筛选、分页或写入后的列表回读时，必须读取 [列表结果完整性与一致性检查](references/list-result-consistency.md)。按适用范围生成独立用例，检查漏记录、重复记录、错误匹配、分页完整性及新增/编辑/关联后的可查询性；仅返回成功或出现一行数据不足以证明查询正确。审核时逐项说明已覆盖、不适用或缺数据，不适用要有依据。

写入链路按参考中的“写入后搜索与筛选生效规则”，为新条件命中、旧条件结果、关联身份/名称一致和受影响筛选组合建立独立检查；不能将列表回显作为搜索或筛选正确的替代证明。

存在连锁与门店数据范围的搜索、筛选、选择器或关联候选，必须分别评估两个视角。顾客覆盖连锁关联/未关联，员工覆盖连锁归属、门店归属和授权范围；明确不支持的视角也要在 `omission_risk_audit.json` 中记录 `not_applicable` 及依据，不能静默省略。

用例审核前逐条核对风险命中。每条必须映射到独立用例 ID，或记录带依据的 `not_applicable`、缺口阻塞或待产品审核。适用风险没有用例映射时门禁失败。

每条用例包含稳定ID、标题、前置、数据、步骤、逐步预期、优先级、环境/平台/角色、`covered_rule_ids`、`covered_flow_ids`、证据计划和清理策略。

覆盖以下适用维度：

- 正常、异常、必填、格式、长度、数量、组合和边界。
- 新增、编辑、删除、启停、导入、导出、刷新、重登和历史兼容。
- 页面与服务端权限、数据范围、参数篡改和跨组织访问。
- 状态迁移、幂等、重复提交、并发、失败回滚和异步完成。
- 列表、详情、统计、接口、App、H5、小程序或设备端回读一致性。

每条已确认 `BF-*` 至少有一条完整端到端用例，并引用流程所有步骤涉及的 `A-*`。局部用例不能代替业务链路。

端到端用例也不能代替细粒度执行层。每个适用规则或紧密耦合规则簇至少要有一个可单独准备数据、执行、判定、取证和重跑的用例入口。字段等价边界可以参数化；不同角色、平台、状态迁移、失败机制、服务端越权或副作用必须拆开。规则覆盖率达到 100% 后仍须执行粒度门禁：

```bash
ai-test case-granularity-check --cases cases/review-draft.json
```

门禁失败时保留端到端核心套件，补充独立功能、边界、异常、权限矩阵和数据一致性用例后重新审核；不得用省略原子层来修正模板质量问题。

```bash
ai-test flow-check \
  --input rules/business-flows.json \
  --cases cases/approved-baseline.json \
  --matrix-output runs/latest/flow-coverage.json
```

## 审核与执行交接

先进行独立语义复核，再交产品经理终审。审核修改必须落回相同稳定ID；删除需明确依据，不能通过省略实现。

审核通过后，用稳定用例ID补全需求阶段的 `automation_readiness_plan`，把每条用例绑定到所需角色、fixture、环境和证据点，重新冻结计划哈希；再生成 `automation_execution_bundle`，绑定运行ID、基线ID、需求/规则/用例哈希、适用环境、测试数据计划、证据计划和执行资产引用。账号、密码、Cookie与Token只从安全运行配置读取。

测试发现遗漏时，先判断需要补需求、规则、用例还是执行资产，再生成可审核差异并更新同一基线。执行状态和报告不能偷偷改变用例预期。
