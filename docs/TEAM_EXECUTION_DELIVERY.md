# 团队执行链：本地交付、复现和剩余门禁（2026-10-04）

本文件说明当前公开框架源码的能力，不宣称正式业务回归或产品验收。`pyproject.toml` 当前为 0.13.0a1。此文档记录公开预览分支的能力；只有远端 commit、Actions 和受保护分支回执齐全后才能声称相应阶段完成。预览分支不等于默认分支或正式 Release。需求/Case 的 Current、私有环境和写入授权仍须由团队提供；不得从记忆、历史 99 画像或虚构例子推断。

## 现在已有的公开部件

| 阶段 | 新增命令/文件 | 实际检查 | 尚未证明 |
| --- | --- | --- | --- |
| M0 盘点 | `plan/2026-10-04_m0-local-baseline.md` | 标明本地未提交版本及前后测试数量 | 私有资产签收、版本发布 |
| M1 克隆健康 | `ai-test doctor`、`team_doctor.py` | 离线检查公开 clone、项目配置、Node/npm、样板、Playwright 依赖；可选本地知识 manifest 路径/哈希；本机虚构项目正控实跑 | 浏览器/CI/Windows 的跨机可用性、知识内容的审核权威、实际业务准备度。`--require-business` 必阻塞 |
| M2 环境能力 | `ai-test env-resolve`、`environment_profile.py`、Schema/虚构画像 | `stage × zone × platform × organization_view × role × build` 三方精确比对；Capability、审查时间、过期与 120 秒观测有效期；无 fallback，`write_authorized=false` | 观测来源真伪、远端 Current 或用户授权；团队私有画像分发尚未决定 |
| M2 本地知识接入 | `ai-test knowledge-audit`、`baseline-snapshot`、`knowledge_adapter.py` | 只读运行已授权本地仓库的 `validate/load`，核对 `required_reads` 数量、路径、状态、SHA-256；核对单工作项本地基线 ID/哈希。不输出规则正文或凭据 | 哈希读取不是 AI 语义理解；本地基线一致不证明远端正式 Current，仍需人审和权威来源校验 |
| M3 Probe 冻结 | `ai-test probe-check`、`execution_contract.py`、Schema | 原单一 baseline/临时 charter、运行日志、计划/准备度、Case/A IDs、Oracle 文件哈希、唯一目标、写前快照与本轮环境回执对账；不建第二套用例 | 人工审查回执真实性、业务 Oracle 是否真的独立、现场身份是否真的被可信执行器读取 |
| 通用只读适配器合同 | `ai-test adapter-trace-check`、`adapter_trace.py`、`schemas/adapter-trace.schema.json` | 对任意项目自身的 Case/A/Fixture/平台核对六阶段前序哈希链、只读动作和逐断言 Oracle/证据引用；用两个互不相关的虚构查询模型作正负控，完整材料仍只得 `review_required` | 已额外提供仅限 local/synthetic 的显式 Python 只读 SDK 和两个实际读取不同静态状态的示例；CLI 本身仍不动态执行源码，写动作及产品晋升不开放，阶段哈希可被本地写者伪造，真实执行仍需受保护 runner 接线。见 `docs/ADAPTER_CONTRACT.md` |
| M3→M5 虚构执行纵切 | `ai-test synthetic-run-prepare`、`guarded-web-run`、`synthetic_prepare.py`、`guarded_run.py` | 已开始的 run 与临时 charter、计划/Oracle/Fixture/环境回执和官方 Starter 完整源码/配置/依赖哈希冻结；本地 Edge/Chromium 单次运行且只接纳同 run 的全新单测 reporter，逐断言对账后自动写技术报告、待审资产反馈并以 `partial`/`blocked` 结束日志。重复 run、源码漂移或额外用例阻塞；reporter 一致仍返回 `review_required`（CLI 退出码 1） | 目前严格只支持官方 local/synthetic 计数器，非真实业务执行编排；本地回执可被篡改，进程/依赖真实性、逐次真实写授权及媒体语义仍需可信适配和独立审核；外部 runner 仍可绕过，须 CI/交付门禁拒绝无回执的正式报告 |
| M4 写边界 | `ai-test write-intent-reserve` | 仅 `local/synthetic` 虚构画像可创建原子独占写意图；错键/写前漂移/观测陈旧/审批声明不匹配/重复写均阻塞；未知状态不释放保留文件 | 非合成环境的授权适配与现场读回尚未实现，因此真实业务写入由代码明确阻塞；Playwright 用例还未统一调用本门禁 |
| M5 结果与隐私 | `ai-test playwright-receipts-check`、`checkWithReceipt`、`ai-test privacy-check`、`ai-test report-promotion-check` | 断言失败必须抛给 Playwright；从实际 JSON reporter 附件自动对账每个 A ID、run/case/fixture/Oracle/probe 哈希，拦截吞失败/缺附件/重试；隐私扫描不输出匹配值，未经逐文件语义审查阻塞 | 人工审核声明可被伪造；浏览器动作真实性/报告源码版本真实性/媒体语义不能由当前代码证明，不能把 gate `passed` 解释成产品通过 |
| M5 合成报告交付前核验 | `report_promotion.py`、`schemas/report-promotion-request.schema.json` | 要求已收口的受控 run、原探针/源码/计划/Reporter/Marker/执行历史/资产反馈同一身份且哈希仍一致；逐媒体及报告文件被隐私审核清单完整覆盖。缺录像、缺人工复核声明、直接运行 Playwright 或交叉 run 均阻塞。即使合成材料一致也仅 `review_required`（退出码 1），不产生产品通过 | `standard` 模式当前始终返回 `trusted_business_promotion_adapter_missing`，不接受输入中的 `current_verified` 自声明；本地审核声明不可验证审核人身份。还须在组织 CI/报告系统真正强制调用，外部脚本可绕过 CLI |
| M6 性能与推广 | Starter 的 `PhaseTiming`，本机一条正控阶段计时 | 记录 fixture/navigation/action/assertion 本机样本 | 两个独立合成项目已在本机隔离安装中验证；仍需远端多系统 CI 与另一台机器的克隆验收；任何具体组织的真实业务试点属于使用方接入验收，不是公开框架交付的先决条件 |

## 私有知识只读适配入口（不随公开仓库分发私有数据）

取得本地仓库只读权限后，可运行 `ai-test knowledge-audit --private-root <authorized-clone> --feature <feature> --stage readiness --module-id <reviewed-module-id>`；试点须提供 `--module-id`，没有任何该模块的已路由条目时阻塞，不能把仅命中全局文件误认为有模块 Current。该命令先调用仓库原有 `scripts/knowledge_registry.py validate`、再调用 `load`，逐份校验必读文件的路径、状态和哈希，只输出条目 ID 与哈希。调用者仍必须实际阅读 `required_reads`，并在正式测试前独立取得 Current 审核证据。`ai-test baseline-snapshot --private-root <authorized-clone> --requirement-id <REQ-ID>` 只核对本地工作项的唯一引用文件，若路径越界、基线缺失或哈希漂移则阻塞。两命令均不连接飞书、不修改私有仓库、不授权测试或业务写入。

## 安全边界与操作流程

1. 已审核单一业务基线/快速临时 charter 与当前知识须先由原有工作项/私有注册器检查及必读，先保存测试计划；准备度命令先给出就绪 Case。CLI 无法证明已实读来源，更不能自行采纳历史归档。
2. 从经审核的本地环境画像、真实观察及请求执行 `ai-test env-resolve --profile <profile.json> --observation <observation.json> --request <request.json>`；只有精确比对与短时有效的能力回执才继续。这不是写入许可证。
3. `execution-log-start` 必须在首次动作前调用。生成 per-Case 绑定（`schemas/execution-probe.schema.json`），运行 `ai-test probe-check --input <probe.json> --root <project>`；复制原用例基线及规则 IDs，不另造正式用例。变更计划/Oracle/目标必须新 probe，不倒填旧执行。
4. 首轮只读探索由 Ego Lite 执行，Jev 仅限候选建议；已审核 Web 用例只由 Playwright 正式运行。`write-intent-reserve` 只适用于纯本地虚构演示，其 `reserved` 绝不表示真实业务写入被批准。非合成环境返回 `business_authorization_adapter_missing`。真实动作适配接入前，不运行真实写用例。
5. Playwright 每项断言通过 `checkWithReceipt` 包裹实际断言函数；报错时回执为 failed 且仍将错误抛给 Playwright。运行后 `ai-test playwright-receipts-check --input <binding.json> --root <project>` 对账真实 reporter，输出的 `passed` 仅指本地回执一致。若 reporter 被替换，绑定的 SHA 必重算且仍无法证明其真实性，因此代码/CI/审查仍必需。
6. 每项证据做内容及隐私审核，运行 `ai-test privacy-check --input <manifest.json> --root <project>` 和现有 `evidence-check`/`video-check`；原始请求头、客户数据及未经审核的 Trace 不可落盘。逐断言结论分通过/失败/阻塞/未执行，失败先分诊版本、环境、角色、数据、异步和脚本，最终报告经人审后 `execution-log-finish` 收口。发布/晋升前还须由受控交付入口运行 `ai-test report-promotion-check`；目前只读核验合成运行，正式业务报告被显式阻塞，不能拿静态 `passed` 回执跳过 Current 与权限门禁。

## 通用适配器接口（与单一样板分开）

[`docs/ADAPTER_CONTRACT.md`](ADAPTER_CONTRACT.md) 规定 Web/API/App 等团队项目均可提交的只读步骤回执及安全边界；`ai-test adapter-trace-check` 不硬编码领域 Case ID，不导入项目插件，也不据回执颁发产品通过；`synthetic_adapter_runner.py` 可由调用方显式传入 Python 适配器，在本地虚构画像下实际调用只读回调并生成同一合同的回执。原 `guarded-web-run` 仍只是单一官方虚构样板的真实浏览器纵切；二者不是同一个已经接线的正式业务执行器。

## 虚构纵切使用边界

在项目 `automation/web` 使用受审随包锁文件做 `npm ci --offline`（缓存不可用时须团队批准的依赖供应链），保存并审核 [`templates/synthetic-run-test-plan.example.md`](../templates/synthetic-run-test-plan.example.md) 到 `<project>/runs/<RUN-ID>/test-plan.v1.md`。依次运行 `ai-test synthetic-run-prepare --root <project> --run-id <RUN-ID> --browser-channel msedge` 和 `ai-test guarded-web-run --root <project> --input <project>/runs/<RUN-ID>/guarded-bundle.json`。首个命令只生成虚构临时 charter、短时环境回执、准备度、探针、bundle、已开始的执行日志，不启动浏览器；第二个命令才做一次本地合成 Playwright 动作。准备到执行间若观测超过 120 秒必须另建 run，不能改写旧运行。`ai-test guarded-web-run --input <project>/runs/<RUN-ID>/guarded-bundle.json --root <project>`；bundle 合同见 [`schemas/guarded-synthetic-web-run.schema.json`](../schemas/guarded-synthetic-web-run.schema.json)，只含 `schema_version=1`、已通过 `probe-check` 的 `probe`、`test_plan`/`runner`/`config`/`package` 的相对路径与 SHA-256、`web_root=automation/web`、`test_title=TC-EXAMPLE-001 counter increments once`、明确 `browser_channel`。要求已运行 `execution-log-start`、保存 run 目录下的计划、新 run ID、干净 reporter 输出目录、官方 Starter 完整源码哈希、已安装的 Playwright 精确版本；不允许任意命令、URL 或真实业务环境。结果 `review_required`/退出码 1 表示本机 reporter 对账一致但尚缺媒体/隐私语义复核，不得转成产品通过；`blocked` 保留回执且同 run 不重试。尚无自动化生成受审核业务 bundle 的团队工具，也尚无真实业务授权适配。OS POSIX 进程隔离以外（含 Windows）当前安全阻塞。

## 报告晋升的现有边界

[`schemas/report-promotion-request.schema.json`](../schemas/report-promotion-request.schema.json) 要求新 run 的 `guarded_receipt` 与 `privacy_manifest` 两个相对路径/SHA引用。`privacy_manifest` 必须位于该 run 下且逐一覆盖 JSON reporter 和所有媒体文件；每项人工复核声明须绑定文件 SHA。`ai-test report-promotion-check --root <project> --input <project>/runs/<RUN-ID>/report-promotion-request.json` 对照原 guarded bundle、marker、当轮 reporter、执行历史和资产反馈重新核验，不依赖请求方声称的结果。真实 `RUN-20261004-GUARDED-SYNTH-006` 缺媒体人工审查，得到 `blocked/semantic_privacy_review_missing`、退出码 1；该原始运行仍是 `partial`，未回填任何假审核。

即使技术材料齐全，合成门禁只返回 `review_required` / 退出码 1；`mode=standard` 无可信 Current/正式业务授权适配时始终阻塞。公开仓库 `.github/workflows/ci.yml` 已增 `report-contract-static`：单独跑晋升门禁负控、离线打包及隔离安装 CLI，要求安装后的标准报告输入必须阻塞；本机等效验证通过，但尚未取得 GitHub Actions 远端运行回执、设置分支保护必需状态，也没有组织私有 CI 接线。接入清单见 [`docs/CI_REPORT_GATE_ADOPTION.md`](CI_REPORT_GATE_ADOPTION.md)。必须在组织正式报告/私有仓库的受保护 CI 及提交入口强制调用可信适配器后，才有资格讨论“不可绕过”。审核声明在本地可伪造，单纯回执哈希不能证明真实浏览器动作、产品预期或审核人身份。

## 本机可复判证据

- 公开单测：`python3 -m unittest discover -s tests -p 'test_*.py' -q`，当前 175 项通过；无真实业务执行。
- 公开样板通过离线 npm 缓存安装，使用本机 Microsoft Edge 实际运行两轮，每轮 2 项虚构正负控通过。计划和原始产物在 ignored `runs/RUN-20261004-FRAMEWORK-SYNTH-001/`、`runs/RUN-20261004-FRAMEWORK-SYNTH-002/`；第二轮准备脚本 `prepare.py` 保存所有哈希绑定。第二轮真实 reporter 的 `playwright-receipts-check` 为 `passed`；对副本篡改断言状态后为 `blocked/assertion_not_passed`，原始报告未修改。两个 run 都以 `partial` 收口，因为媒体语义隐私审查尚未完成，且没有业务预期/真实环境。
- `RUN-20261004-GUARDED-SYNTH-001`（浏览器前 CLI 路径错误、随后标题锚定导致 No tests found）以 `blocked` 保留；独立 `-002`～`-004` 均由本机 Edge 单次运行产生仅 1 项真实 reporter 测试通过。`RUN-20261004-GUARDED-SYNTH-005` 首次无需修改旧脚本：通过 `synthetic-run-prepare` 当场生成新 run 包，接着 `guarded-web-run` 驱动 Edge，仅 1 项 reporter 通过，含 A-EXAMPLE-001 附件与视频。最终独立 `-006` 同样经两条公开命令运行，额外绑定随包锁文件，reporter SHA-256 为 `b95f98000a35f6250d2ba1631377cba2792d6e4be209112e443360c21bd8a47f`；退出码 1 / `review_required`，执行日志 `partial`，`product_verdict=not_evaluated`。计划、原始 reporter、技术报告和待审核资产反馈均在 ignored 虚构项目 run 目录。失败运行不覆盖、未知状态不重跑。
- `privacy-check` 对前期第二轮媒体/报告给出 `blocked/semantic_privacy_review_missing`；阶段计时仅一条样本（fixture 0ms、navigation 31ms、action 38ms、assertion 1ms），不构成整体性能结论。新的纵切媒体仍未完成人工审查。
- `pip wheel . --no-deps --no-build-isolation --no-index --no-cache-dir` 离线打包，确认 `guarded_run.py`、`synthetic_prepare.py`、`report_promotion.py`、官方 Starter TypeScript 与 `package-lock.json` 均包含在 wheel；未做发布、Windows 或干净机安装签收。

## 公开框架本身尚未完成

1. 通用适配器已具备仅本地虚构项目的只读回调执行和离线回执核验，但缺真实平台受控运行器的动作时身份/StepReceipt 接线。官方计数器只是合成浏览器示例，外部脚本仍可绕过本地 CLI；下一步应做不含领域规则的通用适配器注册、执行边界与反例验收。
2. 缺可信执行/审核回执的通用扩展协议及正式报告入口的受保护 CI 接法。公开 `report-contract-static` 需等真实 Actions 和 branch-protection 回执；本地哈希链与人工审核声明不具签名或来源认证。
3. 已有本机隔离环境安装与两个独立合成项目的测试，仍缺远端 Windows/设备和其他同事的干净机器克隆签收、正式版本发布与升级/回滚签收。这些是框架工程交付项，不依赖任何指定业务资料。

## 使用方接入时才需要的输入（不是公开框架交付阻塞）

每个团队项目在运行自己的正式用例时，另提供其已审核需求/规则/唯一基线、知识读取适配、环境与身份、Fixture、独立 Oracle、逐动作授权（若有写入）、媒体审核人与受保护报告入口；缺项只阻塞那次具体运行。公开框架既不内置这些内容，也不以某个业务领域的资料完备作为发布自身的门槛。
