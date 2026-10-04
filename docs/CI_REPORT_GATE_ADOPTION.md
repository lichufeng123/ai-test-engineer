# 报告门禁接入组织 CI：权限与验收清单

本文件是公开框架的接入契约，不包含私有仓库地址、客户数据、业务规则或密钥。当前实现只能核验纯合成的本地运行材料，不能批准业务报告；`ai-test report-promotion-check` 的 `mode=standard` 必须阻塞为 `trusted_business_promotion_adapter_missing`。本地通过门禁负控、wheel 构建或附件哈希相等都不是组织 CI 已启用或产品已验收的证据。

## 公开仓库已接的静态检查

`.github/workflows/ci.yml` 的 `test` 工作运行全量单测和 `docs-check`。还配置了 `portable-adapter-smoke` 在 Ubuntu/Windows/macOS 上分别运行虚构适配器及 API-only 入门测试、离线 wheel 构建和安装后模块加载；该矩阵尚无远端运行回执。新增 `report-contract-static` 独立工作：运行报告门禁负控、两个独立虚构只读适配器的合同正反控、禁止联网构建 wheel、从隔离目录调用安装后的报告与适配器 CLI，并要求标准业务输入因缺可信适配而退出非零。它不下载私有运行证据、不登录产品，也不执行真实 Playwright。仓库管理员须在推送后实际检查 Actions 运行结果，并把应强制的 `test`、`portable-adapter-smoke`、`report-contract-static` 工作设为受保护分支的 required status checks；提交前本地成功不等于已设置分支保护。

## 私有报告入口要由有权限的维护者接线（当前未完成）

1. 选择唯一正式报告发布/写回入口及负责团队。所有正式报告和发布门禁必须经同一个受保护 CI job/服务调用，不允许另一路脚本直接上传、改状态或用 `automation-outcome-check passed` 代替授权。锁定框架 wheel 的已审核版本/commit/SHA；明确 GitLab/GitHub 权限与可访问私有知识的独立工作区。
2. CI 从受控工作项恢复需求 ID、唯一 Current 基线、审核签收、工作项与 Case/A ID；通过可信只读来源实时校验 Current 与业务权限/冲突状态，不接收待发布者传来的 `current_verified=true` 或自签 JSON。缺 Current/登记、权限冲突未裁定、报告适用环境/版本不一致时失败关闭。
3. 运行ID和原始 reporter/媒体必须来自同一受控执行任务；固定输入、源代码、计划、环境观测、角色、Fixture、Oracle 和 write approval 的 SHA，并验证执行日志、逐断言回执及状态。直接上传 reporter、跨 run 借视频、重新生成本地 hash 不能替代可信动作来源。真正的写操作必须由独立授权服务按 run/Case/目标/输入签收，环境画像本身不是许可。
4. 人工复核人在受控身份系统中审核报告/视频的语义及隐私，回执应能与 reviewer 身份、时间、文件 SHA 和业务 scope 复核；当前 `privacy-check` 的 `human_review` 字段只是本地声明，不能直接晋升。秘密仅在运行时注入，禁止把原始请求头/个人数据上传为公共 artifacts。
5. 在发布入口强制拒绝业务门禁的 `blocked`、`review_required`、缺收据和未知状态；只在可信 Current/授权/证据/审核全部独立通过后，才由组织负责人决定何时引入可晋升状态。最小正/负控：跨 run、改源码/Oracle、缺媒体/人工审核、假 Current/旧基线、错误角色/区域/版本、一次写结果未知、直接上传报告，全部必须阻断。模拟平台/设备差异和回滚流程，再做双独立业务域试点。

## 当前责任划分与未签收项

- 公开框架维护者：测试代码、Schema、离线 wheel 和 GitHub Actions 的静态门禁；此部分仍需真实 Actions 与受保护分支配置验收。
- 私有知识/产品负责人：正式 Current 的权威状态、审核回执和开放冲突处置；本仓库没有该授信。
- 环境与执行负责人：经审核画像、安全账号引用、角色/Fixture 生命周期、Action-time 观测与单次写批准；目前不具备真实业务权限适配。
- 报告平台/CI 管理员：受保护的唯一交付入口、不可绕过的 required status、保密运行器与独立人工复核；当前没有修改该系统的权限或安装回执。

任何缺项维持阻塞。正式能力不得通过改 `status` 字段、跳过 job、从旧运行复制回执或在报告中口头标“人工已审”来启用。
