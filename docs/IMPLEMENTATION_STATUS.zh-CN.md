<!-- FRAMEWORK_VERSION: 0.13.0a5 -->

# AI Test Engineer 实现状态与跨客户端交接

更新日期：2026-10-06
框架版本：0.13.0a5
默认分支：`main`
公开仓库：`lichufeng123/ai-test-engineer`

> 本文件与 `README.md`、`README.zh-CN.md`、`docs/FRAMEWORK.md` 一同受 `ai-test docs-check` 的版本标记校验；版本不一致会使文档检查失败。

## 1. 项目目标

本项目是一套跨客户端的 AI 测试工程框架。它把需求理解、系统探索、业务流程规则、原子断言、正式测试用例、自动化准备度、测试数据、Web/App/H5/小程序执行、证据、报告和执行资产反哺连接成可审计的流程。

核心使用 Python 标准库、Markdown、JSON 和可移植 Agent Skills，不绑定单一 AI 客户端。工具相关能力通过适配器接入。

## 2. 仓库与安全边界

- 本仓库是通用公开框架的开发仓库，只包含框架、Schema、模板、脱敏示例和通用适配器。
- 团队历史测试仓库不属于本项目，不得修改、改名、提交或调整远程配置。
- 公开仓库不得包含内部域名、账号、密码、Cookie、Token、真实客户数据、内部协作文档链接、未脱敏截图、私有业务规则或内部执行报告。
- 真实业务资产保存在**私有资产仓库**或受控文件空间；框架通过 `ai-test knowledge-audit`、`ai-test baseline-snapshot` 和 `ai-test doctor --private-root` 只读桥接，不复制私有内容。

## 3. 当前架构

### 3.1 可移植 Skills

唯一源码目录为 `.agents/skills/`，当前 11 个 Skill：

1. `ai-test-workflow`：完整测试生命周期路由。
2. `requirement-spec-generate`：需求说明、业务拓扑候选和自动化准备度输入。
3. `generate-business-assertions`：`BF-*` 业务流程与 `A-*` 原子断言。
4. `test-case-generate`：唯一正式用例基线、覆盖映射和执行包。
5. `requirement-grounded-functional-testing`：受控执行、证据、问题定性与报告。
6. `test-execution-asset-retrospective`：执行结束后的页面、数据、环境和自动化资产反哺。
7. `rapid-test`：尚无正式基线时的有边界临时探针。
8. `one-pass-test`：一轮内生成可见临时 `OP-*` 用例、执行已就绪场景并报告。
9. `test-data-and-account-fixture-management`：测试数据和账号 Fixture 的受控生命周期。
10. `test-omission-risk-retrospective`：遗漏风险规则的审查受控反哺。
11. `test-recording-generate`：离线合成语音/静音录音与清单。

用户可选用 `skills-install` 将通用 Skill 安装到用户级目录；仓库 `.agents/skills` 是唯一源码。插件包由 `plugin-build` 临时生成，不维护第二套 Skill 源码。

### 3.2 核心 CLI

`ai-test` 当前提供 32 个子命令：

- **项目与分发**：`init`、`private-scaffold`、`playwright-scaffold`、`skills-check`、`skills-install`、`plugin-build`、`docs-check`、`doctor`。
- **探索与需求**：`discovery-plan`、`flow-check`、`case-granularity-check`、`permission-check`。
- **准备度与执行**：`readiness-plan`、`readiness-check`、`probe-check`、`env-resolve`、`write-intent-reserve`、`execution-log-start`、`execution-log-finish`。
- **自动化资产**：`automation-asset-reuse-check`、`automation-outcome-check`、`synthetic-run-prepare`、`guarded-web-run`、`playwright-receipts-check`。
- **证据与报告**：`evidence-check`、`video-check`、`privacy-check`、`report-promotion-check`、`adapter-trace-check`、`web-executor-check`。
- **数据与知识**：`data-generate`、`knowledge-audit`、`baseline-snapshot`。
- **工作项**：`work-item-create`、`work-item-show`、`work-item-list`、`work-item-update`、`work-item-artifact-register`、`work-item-reconcile`。
- **一站式**：`one-pass-check`。

### 3.3 私有资产仓库接入（0.13.0a5 新增）

- `ai-test private-scaffold --root <dir>` 安装受控私有仓库骨架：项目画像、`knowledge/` 注册中心、参考 `scripts/knowledge_registry.py`、`.gitignore` 与接入说明；不覆盖既有文件。
- 骨架写入真实 SHA-256，因此生成后立即可通过 `knowledge_registry.py validate`。
- 契约文档化为 `schemas/knowledge-registry-manifest.schema.json` 与 `schemas/knowledge-registry-load.schema.json`。
- 说明见 [私有资产仓库接入](PRIVATE_REPOSITORY_INTEGRATION.md)。
- 桥接回执只证明本地路径与哈希一致；不证明 Agent 已读或理解，不代表远端 Current，不授权任何业务写入。

### 3.4 执行适配器

- Playwright Test：Web 正式回归、接口监听、下载、截图、视频和 Trace。
- Ego Lite：新需求首轮语义/视觉探索、人工登录态复用和失败现场复核。
- Jev（可选）：仅从有限只读候选动作中建议下一步，`advisory_only`。
- Playwright MCP：可选的定位器生成与复核，不作为脚本编写前置条件。
- Chrome DevTools MCP：网络、Console、性能和浏览器现场诊断。
- Stagehand：受控生成定位器、等待条件和已知瞬态弹窗修复候选，必须回到 Playwright 验证。
- agent-device：AI-first 移动设备执行器适配器。
- Minium：小程序关键业务、异常、权限、幂等和一致性。

## 4. 已完成能力

- 一需求一任务：`work-item-*` 独立状态、产物登记与对账；`TEST_WORK_ITEMS.md` 人类总览。
- 系统与功能探索：`discovery-plan` 区分全局探索、增量探索与轻量资产校验。
- 需求与业务规则：业务拓扑四分类、`BF-*` / `A-*` 双层规则、`flow-check` 覆盖率门禁。
- 测试用例质量：唯一正式基线、端到端覆盖校验、`case-granularity-check` 防止规则被压缩进少量大用例。
- 自动化准备度：`readiness-plan` / `readiness-check` 冻结环境、角色、数据、证据与排除项。
- 测试数据：声明式生成、fixture 清单、SHA-256、预期与清理策略。
- 执行与证据：截图、视频、接口、日志、下载与下游回读；问题定性八分类。
- 视频证据技术门禁：`video-check` 使用 ffprobe/ffmpeg 检测时长、黑帧与静止区间。
- 报告门禁：`evidence-check`、`privacy-check`、`report-promotion-check` 阻断证据缺失或隐私越界。
- 一站式模式：`one-pass-check` 在执行前校验冻结计划，在收口时校验逐步结果。
- 私有仓库接入：`private-scaffold` 脚手架、两份知识注册中心 Schema 与接入文档。
- 离线合成录音：`test-recording-generate`（依赖 ffmpeg/ffprobe，macOS `say`）。

## 5. 仍需增强的能力

### 5.1 报告证据门禁

已能校验图片尺寸、文件存在性与 Markdown 引用；仍需把团队报告平台的自动修复做成正式的通用 Provider 接口。

### 5.2 执行资产反哺

已有 Skill、目录模型和回执要求；仍需自动化脚本质量评分、资产失效检测、远程版本回执和跨项目索引。

### 5.3 小程序自动化

已有 Minium 职责划分和适配说明；仍需可直接运行的项目模板、连接诊断、云真机执行回执和 CI 示例。

### 5.4 受控自愈

已定义允许修复定位、等待和兼容分支；仍需标准补丁回执、影响范围计算和失败聚类工具。

### 5.5 私有仓库桥接

已提供骨架与契约；仍需：知识注册中心的平台/角色过滤在既有私有实现中落地、`baseline-snapshot` 的远端 Current 适配器、以及把既有私有仓库对齐到当前契约的迁移命令。

## 6. 待优化事项

### P0：通用报告平台 Provider

定义 `ReportProvider` 协议，本地 Markdown Provider 作为参考实现，组织内部适配放在私有层；输出发布修订号、正文哈希、媒体数量和修复动作回执。

### P0：测试资产检索和有效性检查

定义本地 JSON 资产索引格式；新增 `asset-index`、`asset-search`、`asset-validate`；按系统、功能、环境、平台、版本和状态检索。

### P1：视频内容语义检查（第二阶段）

复用 `step_labels`，增加可审核的期望页面与关键步骤契约；抽取关键帧并把模型结论与时间点、帧哈希和人工复核状态绑定；区分"技术质量通过"与"内容流程通过"。

### P1：缺陷提交 Provider

定义 `defect_draft.schema.json`；聚合标题、严重程度、版本、步骤、实际、预期、截图、视频、cURL 和响应；默认只生成草稿和 dry-run 回执。

### P1：测试数据生命周期

新增 fixture 健康检查和前置指纹；输出 `reuse`、`regenerate`、`repair`、`blocked`、`cleanup_required`。

### P1：研发变更影响输入

定义 `change_impact_input.schema.json`；生成需求规则、历史用例和变更项之间的影响矩阵。

## 7. 推荐接手顺序

1. 评审并合并本分支的私有仓库接入与文档修复。
2. 实现**测试资产索引和有效性检查**（P0）。
3. 实现**缺陷草稿 Schema 和 dry-run**（P1），正式提交适配器放私有层。
4. 评审**视频内容语义检查第二阶段**的输入契约与人工复核边界。

每项实现必须：

1. 先阅读 `README.md`、`README.zh-CN.md`、`docs/FRAMEWORK.md`、本文件和相关 Skill。
2. 不建立第二套需求、规则或测试用例基线。
3. 更新 CLI、Schema、模板、Playbook、README 和完整手册。
4. 增加必要的单元测试和脱敏示例。
5. 运行：

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
./bin/ai-test docs-check --root .
./bin/ai-test skills-check --root .
```

6. 使用中文提交信息。
7. 不写入内部资料或敏感信息。

## 8. 当前验证基线

- 框架版本：0.13.0a5。
- 单元测试：195 项以上（含 `private-scaffold` 与知识注册中心契约测试），全部通过。
- `docs-check`：通过，且已覆盖本文件的版本标记。
- `skills-check`：通过，11 个 Skill。
- `video-check` 与 `test-recording-generate` 依赖运行环境提供 ffprobe/ffmpeg；缺失时输出 `blocked`，不静默跳过。
- 后续开发开始前应重新执行 `git status`、单元测试、文档检查和 Skill 检查，以当前分支输出为准。
