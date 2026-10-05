# 开发线整合与后续发布流（0.13 系列）

当前开发分支为 `lucifer/ai-test-engineer`，跟踪公司 GitLab `gitlab.meimeifa.com:yz-testing/tests-tools.git` 的同名分支；本机工作树 `/Users/chenhao/Documents/test-tool/ai-test-engineer-integration` 是唯一开发位置。GitLab 是今后的权威远端，GitHub `origin` 只保留为历史来源，新提交默认推送 GitLab，GitHub 的 Actions 结果不算 GitLab CI 结果。

该分支以通过多系统合成 CI 的框架发行提交 `7593b4a` 为基底，其历史与 tests-tools 的 `release` 分支没有共同祖先，因此不能向 `release`/默认分支发 MR；那样会整体替换公司仓库内容。若要把框架正式并入 tests-tools，先定目录位置，再在 `release` 之上以新增子目录的提交方式做，不使用强推或历史合并。

整合盘点：旧 `feat/ego-lite-e2e-benchmark` 工作树展开后有 105 个变更/未跟踪文件；88 个字节与预览分支一致，7 个是发布分支已修正的旧版 CI/说明及 1 个测试文件末尾空行，1 个是通用 `uv.lock`（已按原 SHA-256 迁入），其余 9 个为待单独审核的本地材料，没有带入开发分支或发布分支。原工作树未 stash、未覆盖、未提交或删除；详细逐文件 OID/分类在原仓库 ignored run 的 `RUN-20261004-DEVELOPMENT-INTEGRATION-001/inventory.v1.json`。因此不是把脏工作树整体 merge 过来。

后续工作约定：

1. 在开发分支新建短寿命功能分支。先检查该功能的需求、知识与风险输入，再提交公开代码；私有业务资料、`.env*`、运行录像/报告、令牌与本地账号不提交。重复/冲突资产先审查，不用 `git add .`。
2. 功能分支通过单测、文档/Schema、打包与适配器反例后汇入开发集成分支；任一正式发布分支发生修复，要在开发线上通过受审 merge/cherry-pick 回流并重跑测试，避免发布线和开发线持续分叉。
3. GitLab 目前只有个人分支承载框架，尚无项目级 CI、分支保护和受保护的正式发布入口。团队要长期维护，建议在 GitLab 新建独立的框架项目，或与仓库负责人商定 `tests-tools` 内的正式目录与受保护分支；在此之前不要把该个人分支当正式发布渠道。GitLab 跨平台流水线和 required checks 须单独验收。
4. 推送前用 `git push`（已设置 upstream）确认目标为 `gitlab`；不得向 `release` 或默认分支推送，不新增 GitHub 远端推送。
5. 版本变化同步 `pyproject.toml`、`setup.cfg`、模块 `__version__`、manifest/plugin、`uv.lock`、文档版本标记与 CI；发布 tag/默认分支合入由另一次授权与实际验收回执决定。预览分支上的测试通过不授权产品业务写入或正式报告晋升。

本地开发检验：`python3 -m unittest discover -s tests -p 'test_*.py' -q`、`./bin/ai-test docs-check --root .`、`./bin/ai-test skills-check --root .`、`python3 -m pip wheel . --no-deps --no-build-isolation --no-index --wheel-dir dist/validation`。构建物由 `.gitignore` 排除，不属于源码提交。
