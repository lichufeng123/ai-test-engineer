# 跨客户端 Skill 与插件分发

## 唯一源码

`ai-test-engineer` 的工作流能力统一维护在：

```text
.agents/skills/<skill-name>/SKILL.md
```

Agent Skills 规范定义 Skill 内部的 `SKILL.md`、`scripts/`、`references/` 和 `assets/`，不强制安装路径。`.agents/skills/` 是用于跨客户端互认的共享约定。项目级目录随仓库版本控制；用户级 `~/.agents/skills/` 让同一用户的兼容客户端共享安装结果。

不要在 `.codex/skills`、`.claude/skills` 或插件的 `skills/` 中独立修改同名内容。客户端专用目录只是兼容入口，插件目录只是构建产物。

## 当前 Skill

| Skill | 作用 |
|---|---|
| `ai-test-workflow` | 根据任务阶段选择完整测试工作流 |
| `requirement-spec-generate` | 把原型和零散材料整理成审核需求 |
| `generate-business-assertions` | 生成业务流程和原子断言 |
| `test-case-generate` | 生成、审核和反哺唯一正式用例基线 |
| `requirement-grounded-functional-testing` | 执行需求驱动的跨端功能测试 |
| `test-execution-asset-retrospective` | 沉淀执行资产和提速经验 |

## 项目级使用

兼容客户端打开仓库后直接扫描 `.agents/skills/`。这是最适合协作仓库的方式，不需要修改用户目录。

## 用户级安装

先校验，再安装到共享用户目录：

```bash
ai-test skills-check --root .
ai-test skills-install --root . --client universal
```

部分客户端暂时只扫描自己的目录，可以同时创建兼容入口：

```bash
ai-test skills-install --root . --client universal --client codex
```

默认使用符号链接，确保修改仓库源码后所有入口读取同一内容。使用 `--mode copy` 时会形成安装副本，需要重新运行安装命令才能更新。

已有同名目录时，命令返回 `blocked`，不会覆盖。确认迁移后使用 `--replace`；原目录先移动到：

```text
~/.agents/backups/ai-test-engineer/<UTC时间戳>/
```

回滚时删除新链接，并把备份移回原位置。

## 插件构建

插件格式要求包内存在 `.codex-plugin/plugin.json` 和 `skills/`。源码仓库不维护这份 `skills/`，而是按需生成：

```bash
ai-test plugin-build --root . --output ./dist/ai-test-engineer
```

构建器先执行 Skill 安全与格式校验，再复制 `.agents/skills/`。发布前还应使用目标客户端的插件校验器验证生成目录。插件使用新的 `ai-test-engineer` 标识，不升级或覆盖团队旧插件；只有主动安装的人受到影响。

## 旧插件退役

退役旧插件前必须建立能力映射，确认其每项独有能力已经迁移并完成等价验证。顺序为：

1. 校验六个跨客户端 Skill。
2. 安装 universal 与当前客户端兼容入口。
3. 用真实的需求、规则、用例和执行场景分别完成冒烟。
4. 保存旧插件版本与本地备份位置。
5. 只卸载当前用户明确指定的旧插件。
6. 重新启动客户端，确认新入口可发现且旧入口消失。

旧插件包含的私有知识库、文档平台或组织脚本属于适配器能力。通用 Skill 可以定义接口和门禁，但不能假装这些私有连接已经迁移；对应适配器未就绪时保留旧插件或把相关步骤标为阻塞。

## English summary

`.agents/skills/` is the single maintained source. Compatible clients discover it directly. Client-specific folders are links or managed copies, and plugin `skills/` directories are generated artifacts. Removing an older plugin is allowed only after every unique private adapter and workflow has an equivalent, verified replacement.
