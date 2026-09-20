<!-- FRAMEWORK_VERSION: 0.9.0 -->

# AI Test Engineer

[English](README.md) | 简体中文

AI Test Engineer 是一套可移植、以证据为先的 AI 测试工程框架。它把需求理解、系统与功能探索、已审核测试用例、测试数据、自动化执行、证据复核、测试报告和执行资产反哺连接为一条稳定流程。

核心仅依赖 Python 标准库、Markdown 和 JSON Schema，可供不同 AI 助手及人工测试工程师共同使用。Codex、Playwright、Minium 等能力通过适配器接入，不改变正式需求、业务规则和测试用例的唯一基线。

## 跨客户端 Skill 与可选插件

所有工作流 Skill 的唯一源码位于 `.agents/skills/`。这是兼容 Agent Skills 的客户端共享的发现目录；客户端打开本仓库后，可以直接发现项目级 Skill。需要安装到当前用户时运行：

```bash
ai-test skills-check --root .
ai-test skills-install --root . --client universal
```

当前客户端仍只扫描专用目录时，可以追加 `--client codex` 建立 Codex 兼容链接。安装器默认不覆盖同名 Skill；显式传入 `--replace` 时，也会先移动到带时间戳的备份目录。

仓库同时支持构建可选的 Codex/ChatGPT 插件。插件包从同一份 `.agents/skills/` 临时生成，不维护第二份源码：

```bash
ai-test plugin-build --root . --output ./dist/ai-test-engineer
```

生成目录包含插件要求的 `.codex-plugin/plugin.json` 和 `skills/`。其他客户端继续直接使用 `.agents/skills/`，无需安装插件。完整边界见[跨客户端 Skill 与插件分发](docs/skill-and-plugin-distribution.md)。

## 快速开始

```bash
python3 -m pip install -e .
ai-test init ./my-test-project \
  --name "会员门户" \
  --system-id member-portal \
  --environment test \
  --platform web
```

### 一需求一任务

测试项目默认按需求隔离状态。第一次开始新需求时创建工作项：

```bash
ai-test work-item-create --root ./my-test-project \
  --requirement-id REQ-XXX --title "需求标题" --feature "被测功能" \
  --environment sit --platform web --scope "本轮测试范围"
```

之后即使更换 Codex、WorkBuddy 或其他 Agent，也只需说“接手需求 REQ-XXX”。Agent 应自动运行 `ai-test work-item-show --root . --requirement-id REQ-XXX` 并恢复当前阶段、已完成内容、阻塞、下一步、正式基线和已有资产。根目录的 `TEST_WORK_ITEMS.md` 提供全部需求的人类可读总览。

完整说明见[一需求一任务使用说明](docs/ONE_REQUIREMENT_ONE_CONVERSATION.zh-CN.md)，普通使用者无需背诵工作流和长提示词。

首次接入且没有系统资产时，先生成系统探索计划：

```bash
ai-test discovery-plan \
  --project ./my-test-project/ai-test.json \
  --environment test \
  --platform web \
  --product-version 1.0.0
```

正式测试用例以团队审核通过的基线为唯一事实来源。自动化执行包记录稳定用例 ID、来源和内容哈希，UI 自动化脚本只负责执行，不另建一套用例。

## 业务流程与原子断言

生成规则和用例前，先根据系统地图、角色权限、实体关系、既有流程、接口和当前上下文推导可能的上下游，再判断目标功能属于孤立功能、已确认关联、候选关联或待确认。不能在尚未分析现有信息时，只向产品经理询问一个没有上下文的“是否有关联”。

已确认行为分成两层：

- `BF-*`：业务流程规则，描述触发、参与者、平台、步骤、状态变化、下游结果和失败分支。
- `A-*`：原子业务断言，描述单一、可验证的预期结果。

每个流程步骤必须引用原子断言；每条已确认流程至少需要一条覆盖完整步骤的端到端用例。用例通过 `covered_flow_ids` 和 `covered_rule_ids` 建立追踪。

完整用例基线还要通过执行粒度门禁。端到端用例用于证明整条业务链路，不能替代可单独准备数据、执行、判定、取证和重跑的功能、边界、异常、权限矩阵及数据一致性用例。同一字段的等价边界可以参数化；不同角色、平台、状态迁移、失败机制、服务端越权或副作用必须拆分。

```bash
ai-test flow-check \
  --input ./rules/business-flows.json \
  --cases ./cases/approved-baseline.json \
  --matrix-output ./runs/latest/flow-coverage.json

ai-test case-granularity-check \
  --cases ./cases/review-draft.json
```

## 权限测试设计

涉及权限开关时，现有 Skill 自动加载[权限测试设计规范](.agents/skills/test-case-generate/references/permission-testing.md)。区分上级功能资格、角色权限、门店/组织范围和访问视角，覆盖浏览/编辑联动、授权撤权、生效动作、跳转绕过和服务端鉴权。使用 `ai-test permission-check --matrix rules/permission_matrix.json --cases cases/review-draft.json --output runs/latest/permission_design_receipt.json` 保存设计检查回执。该门禁只验证已声明矩阵的设计覆盖，不能证明业务预期正确或实际测试通过。

## 自动化准备度规划与执行前复核

需求说明书审核通过后，立即梳理可自动化范围、人工专属范围、目标环境和平台、所需账号角色、测试数据、证据点与风险动作。此时还没有正式用例ID的，先记录候选用例类别；正式用例审核后绑定稳定ID并重新冻结哈希。

```bash
ai-test readiness-plan \
  --input ./runs/latest/automation-readiness-source.json \
  --output ./runs/latest/automation_readiness_plan.json

ai-test readiness-check \
  --plan ./runs/latest/automation_readiness_plan.json \
  --confirmation ./runs/latest/pre_execution_confirmation.json \
  --output ./runs/latest/execution_readiness_receipt.json
```

实际执行前重新确认功能、环境、适用用例、账号角色、fixture和排除项。缺账号或数据只阻塞受影响用例并登记一次；相同前置指纹未变化前不重复尝试，其他已就绪用例继续执行。

## 自动化执行历史

每次自动化执行都要登记开始和结束。开始记录保存稳定自动化ID、本次运行ID、环境、平台、执行作用、目的、范围和用例基线；结束记录补齐耗时、结果、报告、证据与资产变化。项目根目录固定生成 `AUTOMATION_EXECUTION_HISTORY.md`，其中首次执行时间保持不变，后续每次回归均追加记录。

```bash
ai-test execution-log-start \
  --root . --automation-id smart-earphone-web --run-id RUN-20260920-001 \
  --feature "智能耳机 Web" --environment sit --platform web \
  --purpose "发布前回归门禁" --objective "确认核心流程可进入下一环境" \
  --scope "搜索、筛选、分页和页面跳转" --baseline "approved-cases@sha256:..."

ai-test execution-log-finish \
  --root . --run-id RUN-20260920-001 --status passed \
  --summary "纳入范围全部通过" --report reports/sit.md \
  --evidence runs/RUN-20260920-001/evidence-manifest.json \
  --asset-change "更新新版入口定位"
```

命令默认使用当前本地时间，也可传入带时区的ISO-8601时间。机器状态保存在 `.ai-test/execution_history.json`，不得写入账号、密码、Cookie、Token或客户隐私数据。

## 测试数据与证据

框架可以按声明生成确定性的正常、异常、边界、重复、混合、空文件、损坏文件和数量边界数据，并记录清单与哈希：

```bash
ai-test data-generate \
  --spec templates/fixture-spec.example.json \
  --output ./fixtures/generated
```

测试前为稳定用例 ID 制定证据计划。报告中的关键结论必须有截图、视频、接口、日志或数据回读支持。截图和媒体发布后还要重新读取报告，确认图片块真实存在且位于对应章节。

```bash
ai-test evidence-check \
  --manifest ./runs/2026-09-12/evidence_manifest.json \
  --root ./runs/2026-09-12 \
  --report ./runs/2026-09-12/report.md
```

视频证据在发布前还要通过第一阶段技术质量门禁。每段视频在脱敏输入 JSON 中声明预期时长和可选阈值；命令使用 `ffprobe`、`ffmpeg` 检查时长、黑帧和静止区间，并写出机器可读回执：

```bash
ai-test video-check \
  --input templates/video-check-input.example.json \
  --root ./runs/2026-09-12 \
  --output ./runs/2026-09-12/video_quality_receipt.json
```

回执逐段输出 `passed`、`trim_required`、`rerecord_required` 或 `blocked`，并保留命中的时间区间、占比、规则和建议动作。第一阶段不校验录制页面、标题、操作步骤及结果是否与用例语义一致，仍需进行内容审核；视频也不能替代关键结果截图。`video-check` 是可选核心工具，运行环境需提供 `ffprobe` 和 `ffmpeg`，也可通过 `--ffprobe`、`--ffmpeg` 指定路径。

## 完整工作方式

框架按以下主链路工作：

```text
需求接收
→ 系统与功能探索
→ 需求冻结与当前知识校验
→ 自动化准备度规划
→ 业务拓扑分析与流程评审
→ 原子断言和正式用例设计
→ 数据与自动化交接
→ 执行前范围、环境、账号角色和数据复核
→ 执行日志开始登记
→ 资产校验和测试执行
→ 问题定性与回归
→ 测试遗漏风险复盘
→ 证据化报告
→ 执行资产及知识反哺
→ 执行日志结束登记
```

缺陷暴露的漏测、用户纠正和测试误判统一沉淀到《测试遗漏风险规则库》。后续每次正式用例生成都要检索这份 current 文档并生成 `omission_risk_audit.json`；适用规则必须映射到用例，或记录有依据的不适用、阻塞或待审。风险规则用于提醒设计维度，不能替代已审核业务预期。

首次执行负责学习并沉淀；后续回归先加载资产，只校验入口、关键控件、数据前置和版本差异。单个 UI 操作超过两分钟没有页面、接口、下载、日志或状态进展时，应保存已有证据并报告卡点。

完整规范见[框架手册](docs/FRAMEWORK.md)，具体步骤见 [Playbooks](playbooks/README.md)。

## 项目结构

- `src/ai_test_framework/`：CLI 和可复用的确定性校验能力。
- `.agents/skills/`：跨客户端测试工作流 Skill 的唯一源码。
- `plugin/plugin.json`：构建可选插件包时使用的元数据。
- `playbooks/`：不依赖特定 AI 产品的操作流程。
- `adapters/`：测试用例基线和工具接入说明。
- `schemas/`、`templates/`：机器可读契约和安全示例。
- `examples/`：经过脱敏的数据样例。

## 开发与校验

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
ai-test docs-check --root .
```

只要框架行为、CLI、Schema、目录、平台支持、报告门禁或安全规则变化，就必须同步更新本文件、英文 README、`docs/FRAMEWORK.md` 和 `framework-manifest.json`，并通过全部测试。

## 安全与隐私

禁止提交账号密码、Token、Cookie、密钥、内部地址、客户数据、真实截图、录屏、下载文件、缓存和生产导出。详见 [SECURITY.md](SECURITY.md)。

## 许可证

MIT，详见 [LICENSE](LICENSE)。

## 列表查询一致性用例设计

涉及列表、搜索、筛选、分页和写入后回读时，生成用例须检查漏记录、重复、错误匹配、全分页完整性以及新增或关联后可查询性；对齐角色、组织、日期和状态，并按已确认需求判断适用项。审核明确覆盖、不适用或缺数据。详见[列表设计检查](.agents/skills/test-case-generate/references/list-result-consistency.md)。失败章节直接附实际截图及必要对照。

修改数据后，除列表/详情回显外，还要核对新条件搜索和筛选命中、旧条件结果以及关联对象身份与名称一致；将这些步骤前置为业务流程规则和独立断言，不等执行才补充。旧条件排除和同步时机依审核需求，不强制特定数据库实现。
