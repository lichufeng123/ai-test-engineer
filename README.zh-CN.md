<!-- FRAMEWORK_VERSION: 0.4.0 -->

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

```bash
ai-test flow-check \
  --input ./rules/business-flows.json \
  --cases ./cases/approved-baseline.json \
  --matrix-output ./runs/latest/flow-coverage.json
```

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

## 完整工作方式

框架按以下主链路工作：

```text
需求接收
→ 系统与功能探索
→ 需求冻结与当前知识校验
→ 业务拓扑分析与流程评审
→ 原子断言和正式用例设计
→ 数据与自动化交接
→ 资产校验和测试执行
→ 问题定性与回归
→ 证据化报告
→ 执行资产及知识反哺
```

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
