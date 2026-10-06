# 私有资产仓库接入

本文说明如何为团队创建并接入一个受控的**私有测试资产仓库**，以及通用框架与私有仓库之间的边界。公开框架只提供流程、Schema、模板、Playbook 和脱敏示例；真实账号、内部域名、业务规则、私有协作文档和未脱敏证据必须留在私有仓库或受控文件空间。

## 1. 为什么要分开

| 仓库 | 保存 | 禁止 |
| --- | --- | --- |
| 通用框架（公开） | 工作流 Skill、CLI、Schema、模板、Playbook、脱敏示例、单元测试 | 内部域名、账号、真实证据、业务专用脚本 |
| 私有资产仓库（受控） | 业务自动化、页面模型、fixture 契约、用例绑定、知识注册中心、执行资产登记 | 密码、Cookie、Token、登录状态、客户数据、单次运行证据 |

运行证据不建立第三个仓库，统一进入外部归档或被 `.gitignore` 忽略的 `runs/`。

## 2. 创建私有仓库

不要手工拼目录。用脚手架生成骨架：

```bash
ai-test private-scaffold --root ./my-private-assets \
  --name "Example Products" --system-id example-products \
  --environment sit --platform web
```

生成内容：

```text
my-private-assets/
├── ai-test.json                       # 项目画像（已存在时不覆盖）
├── .gitignore                         # 默认排除凭据与运行证据
├── docs/PRIVATE_REPOSITORY.md         # 接入说明副本
├── knowledge/
│   ├── INDEX.md                       # 人类可读知识入口
│   ├── manifest.json                  # 生成时写入真实 SHA-256
│   ├── system/ecosystem-map.md
│   ├── modules/example-module/business-topology.md
│   └── test-risks/omission-risk-rules.json
└── scripts/
    └── knowledge_registry.py          # validate / load / refresh，local-only
```

规则：

- **不覆盖**任何既有文件。若目标文件已存在，命令返回 `blocked` 并列出冲突路径。
- 若 `ai-test.json` 已存在，直接沿用，只补知识层；不存在时要求提供 `--name` 与 `--system-id`。
- 生成后立即可用：`python3 scripts/knowledge_registry.py validate` 应返回 `passed`。
- 骨架内容全部是**占位**，必须替换为已审核的真实知识后重新 `refresh`。

若已有历史私有仓库（手工维护），可先用脚手架在临时目录生成骨架，再把 `knowledge/manifest.json` 的结构与 `scripts/knowledge_registry.py` 对齐到本文契约，逐条补齐既有知识的哈希。

## 3. 框架如何连接

私有仓库是 `ai-test` 命令的项目根：

```bash
ai-test work-item-create --root ./my-private-assets --requirement-id REQ-XXX ...
```

工作项状态写入 `<private-repo>/.ai-test/work-items/<requirement-id>/`。

跨仓库边界只有三个**只读**命令：

| 命令 | 作用 | 不做什么 |
| --- | --- | --- |
| `ai-test knowledge-audit --private-root <repo> --feature F --stage S [--platform P] [--role R] [--module-id M]` | 先运行注册器 `validate`，再运行 `load`，然后逐条复算返回路径与 SHA-256 | 不证明 Agent 已读或理解文件；不代表远端 Current |
| `ai-test baseline-snapshot --private-root <repo> --requirement-id REQ-X` | 复算工作项本地基线的身份与哈希 | 不认证远端正式基线；不授权执行 |
| `ai-test doctor --root <repo> --framework-root <framework> --private-root <repo>` | 离线安装健康检查加知识 manifest 哈希预检 | 不安装依赖、不打开浏览器、不读取凭据 |

三个命令都可能返回 `passed`，但 `passed` 只表示本地文件与哈希自洽。业务执行仍需要当前知识、已审核基线或临时章程、运行时身份、授权和逐动作门禁。

## 4. 知识注册中心契约

注册器脚本由私有仓库自己提供，路径固定为 `<private-repo>/scripts/knowledge_registry.py`。框架只调用两个子命令并解析 stdout。

### 4.1 `validate`

```bash
python3 scripts/knowledge_registry.py validate
```

成功时必须输出：

```json
{"status": "passed", "mode": "local_only"}
```

失败时返回非零退出码。

### 4.2 `load`

```bash
python3 scripts/knowledge_registry.py load --feature smart-earphone --stage execution
```

输出必须符合 `schemas/knowledge-registry-load.schema.json`，关键字段：

| 字段 | 要求 |
| --- | --- |
| `status` | 固定 `passed` |
| `mode` | 固定 `local_only` |
| `request.feature` / `request.stage` / `request.platform` / `request.role` | 必须原样回显调用参数 |
| `request.include_candidates` | 必须为 `false`；为 `true` 时框架门禁阻塞 |
| `required_read_count` | 必须等于 `required_reads` 长度 |
| `required_reads[].entry_id` | 稳定标识，不得重复 |
| `required_reads[].path` | 仓库内相对路径，不得绝对路径、不得含 `..` |
| `required_reads[].absolute_path` | 必须等于该相对路径解析后的绝对路径 |
| `required_reads[].sha256` | 与磁盘文件实际哈希一致 |
| `required_reads[].status` | 只能是 `reviewed` 或 `approved_test_method` |

框架会独立复算每条路径与哈希，任一不一致即阻塞并给出 `error_codes`。

### 4.3 manifest

`<private-repo>/knowledge/manifest.json` 必须符合 `schemas/knowledge-registry-manifest.schema.json`。要点：

- `mode` 固定 `local_only`；`remote_sync.enabled` 固定 `false`。
- 每条 `entry` 必须有 `entry_id`、`path`、`kind`、`status`、`modules`、`sha256`。
- `status` 为 `pending_review` 的条目是候选，**不会**作为 `required_reads` 返回，也不得作为正式预期。
- `always_load: true` 或 `modules` 含 `global` 的条目对任何功能都加载；其余按 `modules`、`keywords` 与 `load_when` 路由。
- 可选 `platforms` / `roles` 用于进一步收窄；为空表示不限制。

### 4.4 `refresh`

修改已审核知识后：

```bash
python3 scripts/knowledge_registry.py refresh
python3 scripts/knowledge_registry.py validate
```

`refresh` 只重算哈希，不改变任何业务结论。

## 5. 桥接回执的效力

`knowledge-audit` 的返回固定包含：

- `scope: "local_registry_hashes_only"`
- `content_interpreted: false`
- `authoritative_current_verified: false`

这三项是刻意的：哈希一致不等于规则被理解，本地镜像不等于官方 Current。任何报告、用例或结论都不得把该回执当作业务正确性或发布放行的证据。

## 6. 最小自检清单

新私有仓库接入后按顺序执行：

```bash
python3 scripts/knowledge_registry.py validate
ai-test knowledge-audit --private-root . --feature example-module --stage execution
ai-test doctor --root . --framework-root ../ai-test-engineer --private-root .
ai-test work-item-create --root . --requirement-id REQ-DEMO-001 \
  --title "接入自检" --feature example-module --environment sit --platform web \
  --scope "只读接入自检"
git status --short --ignored
```

最后一步用于确认凭据与运行证据确实被忽略。
