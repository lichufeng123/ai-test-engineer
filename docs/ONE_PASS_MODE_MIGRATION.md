# 一站式测试模式迁移回执（0.13.0a4）

## 变化

- 工作项新增 `test_mode=one_pass`；人类总览单独展示当前和历史一站式测试。现有 `standard`、`rapid`、`unclassified` 不自动改类；在同一工作项内显式 `work-item-update --test-mode one_pass` 只影响后续运行，历史回执保留原身份。
- `.agents/skills/one-pass-test/SKILL.md` 定义同一轮“恢复知识 → 生成并展示来源绑定临时 `OP-*` 用例 → 执行已就绪项 → 逐步结果 → 报告”。普通已授权 SIT 行为不再按阶段索要例行审核，但用户未确认的产品预期/目标唯一性/独立 Oracle 只阻塞受影响场景。
- `ai-test one-pass-check` 新增执行前和收口结构检查，计划/结果分别由 `schemas/one-pass-test-plan.schema.json`、`schemas/one-pass-test-results.schema.json` 描述；预检展示 case_preview，结果检查逐ID/逐步状态、计划 SHA、当轮本地证据文件。它不访问产品、不取得用户授权、不证明知识 Current 或语义正确，成功状态 `ready`／`checked` 不表示产品通过。
- `CASE_DESIGN` 的正式准备计划、规则审核与 Current 处置回执门禁不变，`OP-*` 不注册为正式 `TC-*` 或唯一用例基线；一站式结论始终 provisional。正式验收和发布仍走标准流程。

## 验证

1. `tests/test_one_pass_mode.py` 先因缺少模块失败，再实现模式/门禁，覆盖模式创建与切换、CASE_DESIGN 不被绕过、已确认与未知预期分流、计划/结果哈希、遗漏步骤/证据及风险规则读取。
2. 运行 `python3 -m unittest discover -s tests -p 'test_*.py'`：195项通过。
3. `bin/ai-test docs-check --root .` 和 `bin/ai-test skills-check --root .` 均通过；`git diff --check` 无问题。

## 发布边界与回滚

此目录 `ai-test-engineer-integration` 已具备本机 `bin/ai-test`。相邻日常框架目录 `../ai-test-engineer` 仍是较旧版本且有未提交工作，未覆盖或推送；伊智私有项目在本机执行一站式时已明确对整个工作项使用集成版 CLI，不能混用旧版工作项索引。将模式发布到另一机器或正式框架分支时，应通过受控迁移同步该增量并先跑上述测试；未迁移时禁止把它说成已可用。回滚时停止选择 `one_pass`，保留已生成计划/结果与日志；已有 one_pass 工作项不可直接交给旧 CLI 读取，以免被重分类。
