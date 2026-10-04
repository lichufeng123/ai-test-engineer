# 一需求一任务使用说明

这份说明面向测试工程师、产品经理和使用 Codex、WorkBuddy 或其他 Agent 的同事。日常使用不需要背工作流命令。

## 最简单的使用方式

### 新需求第一次开始

告诉 Agent：

```text
为需求 REQ-XXX 建立测试任务，功能是……，环境是……，平台是……，本轮范围是……。
```

Agent 负责创建独立工作项、确认范围、读取已有系统资产，并说明当前阶段和缺少的前置。

### 换一个任务或换一个 AI 客户端继续

只需告诉 Agent：

```text
接手需求 REQ-XXX
```

Agent 必须自动运行：

```bash
ai-test work-item-show --root . --requirement-id REQ-XXX
```

然后依次读取命令返回的 `manifest.json`、`workflow-state.json`、`handoff.json`、`decisions.md` 和 `asset-links.json`。用户无需复制旧任务记录，也无需背完整提示词。

### 同一需求测试多个环境

SIT、99区、1区等属于同一个需求时，可以继续使用同一个任务和同一个需求ID。每个环境仍生成独立运行记录和测试报告。只有需求目标或正式用例基线已经变成另一项工作时，才创建新的需求ID和任务。

### 缺陷修复后回归

同一需求的缺陷修复可继续原任务，也可新建任务并说“接手需求 REQ-XXX，执行缺陷回归”。两种方式都必须读取同一工作项，不得重新探索已经验证且仍有效的系统入口和页面资产。

## 当前、历史与快速测试索引

`TEST_WORK_ITEMS.md` 是从完整 `.ai-test/work-items/index.json` 自动生成的项目总目录，不只展示当前任务。它按状态和 `test_mode` 分为当前标准需求、当前快速测试、当前模式待分类、历史标准需求、历史快速测试和历史模式待分类；完成/取消的历史项保留可搜索，不因归档删除。旧任务缺少 `test_mode` 时标为待分类，不根据标题或聊天内容猜测其是否快速执行；确认后可通过 `work-item-update --test-mode rapid|standard` 补标。

快速测试仍建立独立工作项，可在创建时使用 `--test-mode rapid`。章程、探针冻结版本、证据和临时结论都登记到该工作项；它只暂缓正式需求说明、规则审核和用例生成，不替代标准测试工程师思考。若不指定，默认 `standard`。

## Agent 自动执行的动作

用户说“建立测试任务”后，Agent 运行：

```bash
ai-test work-item-create \
  --root . \
  --requirement-id REQ-XXX \
  --title "需求标题" \
  --feature "被测功能" \
  --environment sit \
  --platform web \
  --scope "本轮纳入和排除范围"
```

每个需求会得到独立目录：

```text
.ai-test/work-items/REQ-XXX/
├── manifest.json       # 需求身份、功能、环境、平台、范围和正式基线
├── workflow-state.json # 当前阶段、完成项、阻塞、下一步和负责人
├── handoff.json        # 新任务快速接手摘要
├── decisions.md        # 已确认且影响测试的业务决策
├── asset-links.json    # 系统、功能、自动化、报告和证据资产引用
├── artifacts.json      # 产物ID、类型、路径、哈希、审核状态和对应阶段
└── reconciliation-receipt.json # 最近一次状态与产物对账回执（运行对账后生成）
```

项目根目录的 `TEST_WORK_ITEMS.md` 是给人看的总览，`.ai-test/work-items/index.json` 是给工具读取的总索引。两者由命令自动更新，不手工维护两份状态。

工作有进展时，Agent 使用 `work-item-update` 更新阶段、完成项、阻塞和下一步。任何需求、规则、用例、执行包或报告产物生成后，还必须使用 `work-item-artifact-register` 登记稳定产物ID、路径、SHA-256、审核状态和对应阶段；登记的阶段高于当前状态时，工作项自动推进。新任务接手时先读这些文件，聊天历史和长期记忆只用于补充背景，不能替代运行状态。

切换会话、准备生成正式用例或发现状态与实际文件不一致时，运行 `work-item-reconcile`。该命令检查文件缺失、哈希变化、状态落后、未登记产物和用例设计门禁，并写出 `reconciliation-receipt.json`。审核页“已生成”只表示进入 `BUSINESS_ASSERTION_REVIEW`；只有审核导出通过校验并登记 `rule_review_receipt`，同时登记规则 Current 已同步或明确不适用的处置回执后，才允许进入 `CASE_DESIGN`。

## 一个需求一个任务的边界

适合继续同一任务：

- 同一需求从 SIT 推进到预发布和正式环境。
- 同一正式用例基线的缺陷修复与复测。
- 同一功能新增Web、App、H5、小程序或实体设备联动验证。

应该新开任务：

- 新需求具有独立目标或新的正式用例基线。
- 旧任务内容过多，已经影响执行和复核。
- 需要并行执行两个互不依赖的测试需求。

每个任务只能写自己的 `workflow-state.json`。不同任务可以并行读取公共系统地图和自动化资产，但不得同时修改同一报告或同一运行记录。

## 常用命令速查

```bash
# 查看全部需求
ai-test work-item-list --root .

# 接手一个需求
ai-test work-item-show --root . --requirement-id REQ-XXX

# 更新进度
ai-test work-item-update --root . --requirement-id REQ-XXX \
  --stage TEST_EXECUTION --status active \
  --summary "SIT核心流程执行中" \
  --completed "用例审核" \
  --next-step "完成剩余权限场景"

# 同一需求增量扩展到App和新环境，不创建第二个工作项
ai-test work-item-update --root . --requirement-id REQ-XXX \
  --add-platform app --add-environment pre \
  --scope "Web、App、服务端和实体设备联动"

# 业务断言审核页生成后立即登记；阶段自动推进到等待审核
ai-test work-item-artifact-register --root . --requirement-id REQ-XXX \
  --artifact-id ART-REQ-XXX-RULE-REVIEW \
  --artifact-type business_assertion_review_page \
  --path runs/latest/business_assertions_review.html \
  --status review_pending --stage BUSINESS_ASSERTION_REVIEW \
  --baseline-id BL-REQ-XXX-001

# 对账状态、哈希、孤立产物和CASE_DESIGN门禁
ai-test work-item-reconcile --root . --requirement-id REQ-XXX \
  --discover-root ../legacy-project/.knowledge_work --apply
```

账号、密码、Cookie、Token和真实客户数据不得写入这些文件。账号只记录角色和运行时引用，实际凭据通过本机环境变量或安全凭据管理提供。
