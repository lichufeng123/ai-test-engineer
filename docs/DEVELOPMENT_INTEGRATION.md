# 开发线整合与后续发布流（0.13 系列）

当前本地开发分支 `integration/framework-0.13.0a1` 以已发布且通过多系统合成 CI 的 `release/ai-test-engineer-0.13.0a1` 为基底；新的通用框架开发在这个隔离 worktree 继续。它不是 GitLab 远端分支，不能把 GitHub Actions 的结果当作未来 GitLab CI 结果。

整合盘点：旧 `feat/ego-lite-e2e-benchmark` 工作树展开后有 105 个变更/未跟踪文件；88 个字节与预览分支一致，7 个是发布分支已修正的旧版 CI/说明及 1 个测试文件末尾空行，1 个是通用 `uv.lock`（已按原 SHA-256 迁入），其余 9 个为待单独审核的本地材料，没有带入开发分支或发布分支。原工作树未 stash、未覆盖、未提交或删除；详细逐文件 OID/分类在原仓库 ignored run 的 `RUN-20261004-DEVELOPMENT-INTEGRATION-001/inventory.v1.json`。因此不是把脏工作树整体 merge 过来。

后续工作约定：

1. 在开发分支新建短寿命功能分支。先检查该功能的需求、知识与风险输入，再提交公开代码；私有业务资料、`.env*`、运行录像/报告、令牌与本地账号不提交。重复/冲突资产先审查，不用 `git add .`。
2. 功能分支通过单测、文档/Schema、打包与适配器反例后汇入开发集成分支；任一正式发布分支发生修复，要在开发线上通过受审 merge/cherry-pick 回流并重跑测试，避免发布线和开发线持续分叉。
3. 正式 GitLab 仓库开通后，先只读核对 URL、默认分支、历史是否同源、权限和 CI 入口，再设定 GitLab 的开发/候选/发布 MR 流程。不得对未知历史使用强推或假定 GitHub `main` 是正式来源。GitLab 跨平台流水线和 required checks 须独立验收。
4. 版本变化同步 `pyproject.toml`、`setup.cfg`、模块 `__version__`、manifest/plugin、`uv.lock`、文档版本标记与 CI；发布 tag/默认分支合入由另一次授权与实际验收回执决定。预览分支上的测试通过不授权产品业务写入或正式报告晋升。

本地开发检验：`python3 -m unittest discover -s tests -p 'test_*.py' -q`、`./bin/ai-test docs-check --root .`、`./bin/ai-test skills-check --root .`、`python3 -m pip wheel . --no-deps --no-build-isolation --no-index --wheel-dir dist/validation`。构建物由 `.gitignore` 排除，不属于源码提交。
