<!-- FRAMEWORK_VERSION: 0.13.0a5 -->

# AI 测试工程框架完整手册

## 1. 适用范围

本框架用于从需求接收到SIT首轮、预发布回归、正式环境验证和资产反哺的完整测试工作。支持Web、App、H5、小程序、接口和数据回读，并允许不同AI工具或人工测试工程师执行同一套流程。

框架的核心目标是：首次测试产生的理解、数据、定位、自动化和证据计划能够继续复用；后续执行先校验资产，只重新探索发生变化的部分。

### 1.1 跨客户端能力入口

框架把 `.agents/skills/` 作为工作流 Skill 的唯一源码。兼容 Agent Skills 的客户端读取该目录；客户端仅支持专用目录时，由 `ai-test skills-install` 创建指向同一源码的兼容链接或受控副本。

插件是可选分发形式。`ai-test plugin-build` 从 `.agents/skills/` 生成符合插件目录要求的临时包；生成的 `skills/` 只是发布产物，不是第二套维护源。完整安装、替换、回滚和旧插件退役规则见 [跨客户端 Skill 与插件分发](skill-and-plugin-distribution.md)。

`AGENTS.md` 是测试工程师思维宪法与任务路由索引，不只是 Skill 列表。每项任务还必须按 [测试上下文索引](TEST_CONTEXT_INDEX.md) 查找项目本地系统地图、已审核业务知识、测试遗漏风险、唯一正式用例基线、执行资产和当前运行回执；适用 Skill 只负责流程，不代替这些内容。共同思考协议见 [测试工程师思维协议](TEST_ENGINEER_REASONING.md)；从系统辨识、可观测性、反馈和稳定性角度改进测试流程时，参考[《工程控制论》工作流映射](ENGINEERING_CYBERNETICS_WORKFLOW.md)。

## 2. 协作角色

产品经理负责提供需求材料、环境、账号、业务决策和最终验收。AI测试工程师负责主动提问、探索、用例设计、数据生成、自动化、执行、问题定性、证据、报告和资产更新。

AI提出业务问题时使用：当前理解、具体疑点、影响范围、建议口径、需要确认内容。问题分为阻塞和非阻塞；非阻塞问题不妨碍继续进行独立工作。所有模式执行前先按 [测试工程师思维协议](TEST_ENGINEER_REASONING.md) 建立测试意图、风险假设、断言、Fixture、独立Oracle和证据计划。

独立复核者或子Agent承担需求/用例复核以及报告证据复核。复核者发现缺失后推动补拍、补传、归位和再次校验，不能只宣布报告不合格。

完整契约见 [协作契约](collaboration-contract.md)。

## 3. 入口判断

每次任务先判断属于哪种模式：

| 模式 | 触发条件 | 探索范围 |
|---|---|---|
| 首次接入 | 没有系统探索资产 | 提醒并执行系统全局探索，再做功能探索 |
| 手动全局探索 | 用户明确要求 | 重新执行系统全局探索 |
| 新需求首测 | 系统资产有效、功能资产缺失 | 轻量系统校验，加目标功能深度探索 |
| 新环境/平台 | 已有功能资产，但环境或平台未覆盖 | 只探索新增环境或平台差异 |
| 版本变更回归 | 资产版本不一致 | 校验变更影响并增量探索 |
| 稳定回归 | 环境、平台、版本和资产均有效 | 直接执行回归，保留轻量资产校验 |
| 快速测试 | 用户确认需要先测，正式需求/规则/用例产物尚未准备完成 | 仅暂缓正式需求说明、BF/A审核与正式用例生成；仍加载项目知识并执行思考协议和逐探针断言/Fixture/独立Oracle冻结，结论为临时 |
| 一站式测试（`one_pass`） | 用户要求一次完成临时用例设计、执行和报告且不逐阶段等待审核 | 先展示来源绑定的 `OP-*` 用例，再连续执行已就绪场景并逐例报告；业务预期未确认的场景单项阻塞，结论仍为临时 |

接手指定功能时，先查功能地图/别名、工作项索引与历史测试和缺陷；已有记录则快速复核本轮 SIT 入口、角色、数据和版本差异，从上次未验证之处继续，不把历史通过直接带进本轮。功能地图无记录时只做目标功能的增量探索。见 [系统与功能探索](system-and-feature-discovery.md)。

系统全局探索不是每次必跑。目标功能探索也不是每次从零开始：已有L3/L4资产时，只验证入口、核心控件、数据前置和版本兼容。

快速测试用于尚未完成正式产物的试点。它暂缓正式需求说明、BF/A审核与正式用例生成，仍加载适用知识、风险规则，冻结本轮关键断言/Fixture/独立Oracle并取证；结果标临时。一站式测试同样保留这些执行底线，并把设计、测试和报告合并为同一轮：在动作前冻结有角色、唯一Fixture、逐步操作/预期/独立Oracle/证据的 `OP-*` 临时用例，运行 `one-pass-check` 并展示可见用例，然后直接执行已就绪项、逐项回填结果再检查与报告。未审临时用例不得当作唯一正式基线；CLI 检查只验证本地身份/哈希/结果结构，不能证明产品通过。用户已指定 SIT 功能测试时，范围内隔离 Fixture 的常规导入提交、刷新回读和 UI 导出无需逐次确认，也不因“发生写入”本身升级标准流程；真正用于发布/验收、重复正式回归、关键规则争议或缺陷时再跟进标准流程。生产、真实结算、真实通知和超范围不可逆操作单独判断。


SIT新任务先按功能地图与历史运行恢复功能，再从已审核账号/Fixture 台账选定唯一账号别名、角色、组织和登录方式；有匹配会话直接复用。缺账号或多候选时在打开登录页之前一次问清，登录后现场回读实际身份。SIT 测试范围已获授权时不要为正常登录逐次请求许可；只有缺运行时凭据、需要验证码/人工登录或用户持有浏览器控制权时才走 Ego Lite 的 handoff。只有工具返回交接成功才请用户在任务空间操作；`UI not available` 是工具交接失败，不能让用户在不可见窗口登录。完整分支见 [Web AI浏览器工具栈](web-ai-browser-stack.md)。

每个新测试任务在首个页面/API/设备动作前都必须生成并保存测试计划包。标准模式使用批准的需求/用例范围、自动化准备度计划和执行前确认；快速模式使用临时测试章程与版本化探针；一站式模式使用来源绑定的可见临时用例计划及单独的逐步结果文件。计划至少包含目标、范围/排除、知识和预期来源、环境/平台、角色、Fixture、覆盖/断言、独立Oracle、证据、风险、写入/清理/停止条件与完成标准。范围、基线或关键前置改变时重新冻结版本/哈希；缺少有效计划时不得开始正式执行。一站式运行示例：

```bash
ai-test work-item-create --root . --requirement-id REQ-XXX --title "功能测试" \
  --feature "目标功能" --environment sit --platform web --scope "本轮隔离数据范围" \
  --test-mode one_pass
ai-test one-pass-check --input runs/RUN-XXX/one-pass-plan.json --root . \
  --output runs/RUN-XXX/preflight.json
# 向用户展示 case_preview，然后执行已就绪的OP-*临时用例并逐步记录当轮证据
ai-test one-pass-check --input runs/RUN-XXX/one-pass-plan.json \
  --results runs/RUN-XXX/one-pass-results.json --root . \
  --output runs/RUN-XXX/closure.json
```

已存在的需求可用 `work-item-update --test-mode one_pass` 将后续运行切到此模式；此前快速运行仍保留其历史身份。`CASE_DESIGN` 的正式准备计划、规则审核及 Current 处置门禁不因模式变化而放宽。

## 4. 系统全局探索

系统全局探索的目标是建立系统地图，不是深入测试每个菜单。执行内容：

1. 记录系统标识、环境、域名、版本和发布时间。
2. 识别登录角色及登录后的分支页面。
3. 遍历一级至三级菜单，记录入口和页面关系。
4. 比较管理员、普通账号、受限账号和无权限账号的页面及数据范围。
5. 建立业务实体及上下游关系。
6. 记录更新版本、首次引导、公告、下载中心等瞬态页面。
7. 标记删除、覆盖、批量写入、资金和真实通知等风险动作。
8. 记录Web、App、H5、小程序和设备端之间的联动。

完成后至少产生：

```text
assets/system/system_profile.json
assets/system/environment_matrix.json
assets/system/navigation_map.json
assets/system/role_permission_matrix.json
assets/system/entity_model.json
assets/system/transient_ui_catalog.json
assets/system/risk_action_catalog.json
assets/system/execution_asset_register.json
```

只有菜单遍历完成时，成熟度是L1；理解主要角色、实体和数据范围后为L2。

## 5. 目标功能探索

功能探索需要回答：谁在什么前置状态下，通过什么入口操作哪个实体，产生什么状态变化，保存到哪里，哪些下游会读取，失败时如何恢复。

至少覆盖：

- 新增、查看、编辑、删除、启停、导入和导出。
- 默认值、必填、格式、长度、数量和组合约束。
- 状态机、缓存、刷新、重新登录和异步任务。
- 角色权限、数据范围、跨店/跨组织越权和服务端鉴权。
- 重复提交、幂等、并发和失败回滚。
- Web配置后，App、H5、小程序或设备端的数据回读。
- 测试数据创建、复用、隔离和清理方式。
- 每条核心断言需要的截图、视频、接口和数据证据。

功能达到L3的标准：业务路径、状态、数据、角色、断言、证据点、测试数据和恢复方式均已确定。经过至少两个环境验证并形成稳定自动化资产后为L4。

### 5.1 探索不是长期执行器

首次功能探索前，以后续正式资产为目标列具体未知：稳定业务身份/定位、页面与接口状态、等待条件、独立Oracle、Fixture、幂等/停止点、视频和瞬态错误截图触发点。逐项记录 `implemented`（绑定存在且哈希匹配的资产）、带原因的 `blocked` 或带原因的 `not_applicable`。一个问题探明后先实现并验证正式包中的脚本/Oracle，不得在下一次rapid中重新自由探索同一问题；无法实现时登记负责人/期限，明确继续仅限探索。

重复执行前用 `ai-test exploration-handoff-check --input ... --root ... --output ...` 执行 [交接契约](../schemas/exploration-handoff.schema.json)：验证可执行runner文件和哈希、同代码的通过测试回执、独立Oracle、远端备份修订与连续录屏/错误提示截图计划。没有正式审核基线时仍允许临时探针，但不允许把run-local Ego步骤当正式回归。收口阶段要求实际视频文件、技术/语义复核状态及每个计划断言对应的截图语义复核；图片存在和在对的章节不等于错误文字真的出现在图中。未知任务终态时不因缺片重传业务文件，先停止并取得安全处置。检查器只验证提交的文件/哈希和复核声明，不能独立证明复核人诚实、视频内容正确、业务授权或正式验收；技术视频质量继续用 `video-check` 验证。

详见 [系统与功能探索](system-and-feature-discovery.md)。

## 6. 多环境和多平台

环境按项目配置，不写死名称。常见发布链路为SIT首测、预发布回归、指定正式环境验证。

SIT负责：探索新功能、生成测试数据、建设自动化、发现主要缺陷、冻结证据计划。预发布和正式环境负责：校验部署版本、登录分支、配置差异、数据差异和适用用例，不重复完整学习系统。

App提供H5页面时，H5作为独立探索面。H5验证业务字段、状态和接口；App仍需验证容器登录、权限授权、系统返回、页面唤起、文件/相机/麦克风能力和兼容性。H5通过不能替代App验证。

详见 [环境与平台](environment-and-platforms.md)。

## 7. 需求、规则和用例

框架不复制测试用例管理能力。正式用例由团队选定的评审流程产生，并作为唯一用例基线。框架负责把该基线、需求、业务规则、产品决策和执行资产绑定为 `automation_execution_bundle`。

当用户明确不需要需求说明书时，可以不生成对外需求文档，但仍要在内部区分：已确认事实、AI推断、待确认问题和历史信息。

涉及角色权限、数据范围或关联操作时，必须建立权限矩阵，并验证页面权限和服务端鉴权。

### 7.1 先判定业务拓扑，再生成规则和用例

需求前置分析必须先判断目标功能属于以下哪类：

| 类型 | 含义 | 强制产物 |
|---|---|---|
| `isolated` | 只在当前模块内完成，没有已知上下游消费 | 一条本地业务流程和原子断言 |
| `linked_confirmed` | 已确认存在跨模块、角色、平台或异步链路 | 全量业务流程、步骤断言和端到端用例 |
| `linked_candidate` | 系统地图提示可能有关联，但证据还不足 | 候选链路、依据和定向确认问题 |
| `pending` | 现有材料无法判定 | 阻塞项、影响和建议口径 |

AI不能只问“是否有关联”。提问前先读取系统导航、实体模型、角色权限、既有流程、接口与当前上下文，列出推导出的候选模块、角色和平台，再请产品经理确认、排除或补充。已确认的排除项也要记录，避免后续重复追问。

业务规则分成两层：

- `BF-*` 业务流程规则：描述触发条件、参与者、平台、前置状态、步骤、跨模块状态变化、可观察结果和失败分支。
- `A-*` 原子断言：描述单一可验证行为。每个流程步骤必须引用一个或多个原子断言。

正式用例通过 `covered_flow_ids` 和 `covered_rule_ids` 同时建立追踪。每条已确认业务流程至少有一条完整端到端用例，该用例必须覆盖流程所有步骤引用的断言；局部功能用例继续覆盖字段、边界、异常、权限和幂等。

规则覆盖率和业务流程覆盖率通过后，还必须校验执行粒度。端到端用例用于证明完整链路，不能替代可单独准备数据、执行、判定、取证和重跑的功能、边界、异常、权限矩阵及一致性用例。同一字段的等价边界可以参数化；不同角色、平台、状态迁移、失败机制、服务端越权或副作用必须拆分。若大量规则只挂在大体量端到端用例中，`case-granularity-check` 阻止其成为完整执行基线。

使用 `ai-test flow-check` 执行确定性门禁，并保存流程到断言、流程到用例覆盖矩阵。完整操作见 [业务流程建模 Playbook](../playbooks/modeling-business-flows/PLAYBOOK.md)。

使用 `ai-test case-granularity-check --cases <用例JSON>` 检查规则是否主要依赖端到端用例间接覆盖。默认情况下，具有十条以上规则且存在端到端用例时，仅由端到端用例覆盖的规则比例不得超过 35%；语义审核仍需确认独立用例具有精确起始状态、完整动作、逐步预期、确定证据源和针对性清理。

### 7.2 权限测试设计门禁

需求、规则、用例和执行 Skill 在权限类任务中加载统一[权限测试设计规范](../.agents/skills/test-case-generate/references/permission-testing.md)。以配置层、配置对象、角色、访问视角、组织范围、动作和生效策略建立矩阵。测试角色开关时先开放上级资格；测试上级开关时固定下级授权。浏览权限不能代替编辑权限，组织范围不能与功能开关混为一谈。

权限修改后的生效动作由项目适配器或审核需求定义；浏览/编辑仅编辑组合的依赖策略未决时阻塞正式接收。授权、撤权、页面间跳转、直接地址、接口拒绝且数据不变、筛选和视角切换均需独立用例入口。

运行 `ai-test permission-check --matrix rules/permission_matrix.json --cases cases/review-draft.json --output runs/latest/permission_design_receipt.json`。它检查声明的组合与检查点及生效步骤，并要求未知依赖决策关闭。元数据不能代替具体步骤、逐步预期和证据；角色矩阵是否全量和业务语义仍由独立复核验证。示范草稿不得覆盖或并行建立正式用例基线。

### 7.3 自动化准备度提前规划

需求说明书审核完成后，不等待正式执行才临时寻找账号和数据。AI根据已审核需求、系统地图、业务拓扑、角色权限和平台关系，生成 `automation_readiness_plan`，至少包含：

- 可自动化范围、人工专属范围、目标环境和平台。
- 预计覆盖的业务流程和候选用例类别。
- 所需账号角色及用途；不得记录账号、密码、Cookie或Token。
- fixture、生成或取得方式、适用环境、关联用例和清理策略。
- 核心结果截图、核心流程录屏和接口或数据回读计划。
- 风险动作、排除项和需要产品确认的问题。

需求阶段还没有正式用例ID时先记录候选用例类别。用例审核完成后，把稳定用例ID逐条绑定到角色、fixture、环境和证据点，重新生成计划哈希。执行前再创建 `pre_execution_confirmation`，确认当前功能、版本、环境、用例范围、账号角色、数据和排除项。`readiness-check` 校验计划哈希并输出已就绪、阻塞和排除用例。

新增或大幅改写自动化脚本前，先检索功能目录、Page Object、共享 helper、包命令、执行资产登记和历史运行脚本。每个发现的候选必须记录覆盖能力、`reuse`／`extend`／`reject`／`supersede` 决策及依据；新资产还必须声明既有资产无法覆盖的具体缺口和复用基础。使用 `templates/automation-asset-reuse-review.example.json` 形成审计输入并执行：

```bash
ai-test automation-asset-reuse-check \
  --input runs/latest/automation-asset-reuse-review.json \
  --root . \
  --output runs/latest/automation-asset-reuse-receipt.json
```

门禁会实际展开声明的文件匹配模式；发现但未处置的资产、缺失文件、无复用基础的新脚本或未确认审计都会阻塞。`work-item-artifact-register` 在登记 `automation_script` 时还会校验同一运行已有 `validated` 或 `approved` 的复用回执，缺失时拒绝登记。运行编排、收据格式或报告格式不同不构成复制业务流程的理由，应把差异放在共享适配层或既有正式脚本的增量扩展中。

缺少角色或fixture只阻塞关联用例。移动端和硬件在环测试还要声明 `execution_target_requirements`、`hardware_fixture_requirements` 以及逐用例的执行目标和硬件依赖。执行目标只有在指定执行器完成doctor和capabilities校验后才能进入 `available_execution_target_ids`；提前绑定的耳机、工牌或其他外设只有人工准备和自动状态回读同时完成后才能进入 `ready_hardware_fixture_ids`。每个缺口用前置指纹登记到 `missing_prerequisites`；相同指纹未变化前，不得通过重新登录、刷新、重复点击或反复运行来碰运气。收到补充数据、账号角色、环境、执行目标或硬件后重新确认，只恢复前置发生变化的用例。完整操作见 [自动化准备度 Playbook](../playbooks/planning-automation-readiness/PLAYBOOK.md)。

### 7.4 列表结果完整性与一致性

列表、搜索、筛选、分页与写入后列表回读用例必须加载[列表一致性设计检查](../.agents/skills/test-case-generate/references/list-result-consistency.md)。对齐组织、角色权限、日期、状态与匹配规则，用运行时预期记录集合检查漏记录、重复、错误混入、全分页完整性及新增/编辑/导入/关联后的可查询性。HTTP200或非空结果不足以证明业务正确，同一个接口与UI一致也不能代替独立业务预期。

用例审核逐项记录已覆盖、不适用依据或具体缺数据；这是设计与语义复核清单，不宣称新增了机器覆盖门禁。缺陷章节直接附实际结果与必要对照截图，保留快照时间及ID差异。执行中新增的派生检查需反哺同一正式用例基线，不能静默改已审核预期。

写入后规则不仅验证回显：新增、编辑、导入、关联、改派、取消关联或状态修改后，应按受影响的新旧查询条件与筛选属性验证记录纳入/排除、身份及关键属性一致、持久化和适用组合。业务规则阶段即把这些步骤纳入 `BF-*`，拆分对应 `A-*`，再生成独立用例入口。显示可能来自联表或前端补全，不能代替搜索属性同步的证明；不规定数据库实现，未经证据确认的根因不得当作事实。

## 8. 测试数据工厂

AI默认自主生成确定性测试数据，包括正常、异常、边界、重复、混合、空文件、损坏文件、数量边界和跨环境唯一名称。生成过程必须产生fixture清单和哈希。

以下情况需要额外确认：使用真实客户/员工数据、真实资金或结算、真实通知、生产批量写入、超范围的删除覆盖，以及无法从当前需求推导的业务语义。已指定 SIT 试点范围内的隔离测试 Fixture、文件导入和 UI 导出无需按每个动作再次确认。

SIT生成的数据模板可以跨环境复用；数据库ID、Cookie和密码不能复用或写入资产。详见 [测试数据策略](test-data-strategy.md)。

合成测试录音使用 `.agents/skills/test-recording-generate/SKILL.md`：离线生成语音/静音音频与逐文件哈希、`ffprobe` 元数据清单，输出目录不可覆盖。当前语音依赖 macOS `say`，编码/校验依赖 `ffmpeg`/`ffprobe`；无依赖时阻塞，不使用真实客户声音或隐式在线服务。录音可播放不等于发音、转写或标签语义正确；经独立复核与已审核规则确认之前，标签预期只能标记为待确认。音频上传及业务写入仍受执行计划、权限和环境门禁约束。[本次变更回执](RECORDING_SKILL_MIGRATION.md)记录了验证与回滚边界。

## 9. 自动化执行器

Web正式回归只使用Playwright Test。核心业务流程的Playwright录屏须设为 `video: on` 并在测试动作前启动；`retain-on-failure` 会丢掉通过场景的连续证据。新功能首轮由Ego Lite完成观察、动作和回读；Jev仅在已配置时从有限只读候选中建议，建议器故障不阻断可用的执行工具。若浏览器控制权确实不可用，记录连接错误、只阻塞依赖 UI 的步骤，继续功能地图/历史运行/Fixture/Oracle 等工作；不能要求用户把既定 SIT 导入导出范围改为只读。Playwright MCP只按需生成或复核Playwright定位器，不是编写脚本的前置条件，没有安装时可使用Ego Lite语义快照、DOM/CDP、Playwright Inspector/Codegen、浏览器DevTools或现有Test ID完成定位；Chrome DevTools MCP负责网络、Console、性能与浏览器现场诊断；Stagehand只允许提出定位器、等待条件和已知瞬态弹窗修复候选。所有候选必须经过代码审查，并由Playwright执行单用例验证与影响回归。任何AI工具不得修改正式预期、业务规则、权限边界、Case ID或基线哈希，也不能成为正式回归的自由决策回退。

项目使用 `templates/web-executor-routing.example.json` 声明工具状态和分工，运行 `ai-test web-executor-check` 保存路由门禁回执。已可用工具必须锁定精确版本；凭据、Cookie、Token、storage state和模型Key只允许运行时安全注入。完整流程见[Web AI浏览器工具栈](web-ai-browser-stack.md)。坐标点击只允许作为探索或临时恢复证据，不进入稳定Playwright脚本。

App通过工具无关的移动执行器契约接入。执行目标由 `execution-target-profile` 描述，业务外设由 `hardware-fixture` 描述，跨App、API、Web步骤由 `cross-platform-run-plan` 编排，每一步输出统一 `execution-step-receipt`。业务动作使用 `mobile.openApp`、`mobile.startRecording` 等语义名称，不把具体CLI或绝对坐标写入正式用例。

首个AI-first适配器为agent-device。交互探索由当前AI Agent通过MCP或CLI执行 `open → snapshot → act → verify`；审核后的稳定步骤固化为`.ad`或Node API并锁定精确版本。无人值守回归不允许模型临时改变业务预期；写操作使用 `none` 或 `verify_before_retry`，不得盲目重试。真机标识、Bundle ID、私有地址和凭据只允许运行时提供。完整约束见 [agent-device Adapter](../adapters/agent-device/README.md)。

同一手机或硬件fixture必须独占租用。设备中断后先保存现场和步骤回执，再判断安全恢复点；App重启不得掩盖已经发生的创建、关联、提交或录音结束。新工具通过新的执行器适配器接入，业务用例、正式基线和跨端动作名称保持不变。

小程序可使用 Minium 覆盖核心业务、异常、权限、幂等和一致性；云真机工具可覆盖兼容性、性能、版本回归和 CI 门禁；随机测试只覆盖崩溃、卡死和页面可达性冒烟。带本地实体外设的链路默认使用本地真机节点，普通云真机不能推定能访问现场硬件。

接口监听、数据库只读回读、日志和curl用于补强UI结论。出现接口报错时，应保存脱敏响应和可复现curl到约定的错误日志目录。

### 9.1 团队分层样板与逐断言收口

对新项目运行 `ai-test playwright-scaffold --root <project>` 可安装无需业务连接的 PO/Flow/Oracle/Test 示例；已有文件时不覆盖。详情见[团队自动化架构](TEAM_AUTOMATION_ARCHITECTURE.md)。Page Object 只包含页面动作和结构化读取；业务预期来自审核规则与独立 Fixture，由纯 Oracle 计算；断言失败必须传递给正式执行器，不能被日志器捕获后仍宣称 Playwright 用例通过。

真实执行后，用 `ai-test automation-outcome-check --input <result.json> --root <project> --output <receipt.json>` 将稳定 Case/Assertion ID、预期来源、Fixture、独立 Oracle、逐断言证据与 Playwright JSON reporter 对账。它仅阻断局部回执矛盾或证据缺失，不自动证明权威基线、页面内容、执行时源代码哈希或产品缺陷成立；仍须人工/受控语义复核及原执行日志。离线故障注入和真实 UI 回归分别登记，不能互相替代。

## 10. 受控自愈

AI可修复定位器、DOM层级、等待条件、已知弹窗、浏览器重新绑定和报告媒体缺失。Web定位修复可由Stagehand生成最小候选，但必须保留原失败证据，经过代码审查并由Playwright完成单用例验证和影响回归。AI不得修改预期结果、业务规则、权限边界、金额与状态断言，也不得通过删除断言让用例通过。

单步超过2分钟没有页面、接口、下载、日志或状态进展时立即停止等待，保存证据并报告卡点。

每次自愈产生：失败证据、原因分类、补丁、单用例验证、影响回归和资产更新回执。

## 11. 证据与报告

执行前为每个稳定用例ID生成证据计划，至少覆盖操作前、关键操作和结果。保存、刷新、重新登录、异步完成、下游回读等独立主张需要独立证据。

Web默认截图宽度为1920，复杂横向页面可使用2560；低于1600需要补拍。小程序和移动端保留真实设备尺寸。核心流程可录制视频，但视频不替代关键结果截图。

### 11.1 视频证据技术质量门禁（第一阶段）

录屏不能只校验文件存在。上传或交付前，使用 `schemas/video-check-input.schema.json` 为每段视频声明稳定证据ID、用例ID、相对路径、预期最短/最长时长及可选阈值，再执行：

```bash
ai-test video-check \
  --input templates/video-check-input.example.json \
  --root <run-dir> \
  --output <run-dir>/video_quality_receipt.json
```

`video-check` 使用 `ffprobe` 获取真实时长和分辨率，使用 `ffmpeg` 的 `blackdetect` 与 `freezedetect` 识别黑帧和静止区间。默认门禁如下，项目可以在输入的全局默认值或单视频配置中收紧或放宽：

- 黑帧：检测最短0.5秒的片段；总占比超过5%或单段超过2秒时不通过；占比达到50%时建议补录。
- 静止：检测最短3秒的片段；总占比超过25%或单段超过10秒时不通过；占比达到80%时建议补录。
- 时长：低于声明下限时建议补录；高于声明上限时建议先裁剪无意义等待。

机器回执符合 `schemas/video-quality-receipt.schema.json`，通过输入 SHA-256 和视频文件 SHA-256 绑定本次检查对象，并逐段给出探测元数据、命中区间、总时长、最长区间、占比、问题代码和建议动作。处置结果只使用：

- `passed`：三项技术检查均通过。
- `trim_required`：存在局部黑帧、静止等待或时长超限，可复核后裁剪。
- `rerecord_required`：视频过短、黑屏或静止比例严重，需重新录制。
- `blocked`：视频缺失、越出受限根目录、不可读取，或 `ffprobe`/`ffmpeg` 不可用。

命令整体状态为 `passed`、`repair_required` 或 `blocked`；后两者返回非零退出码。输入视频只能使用运行根目录内的相对路径，防止意外读取私有文件。

第一阶段只判断技术质量，不识别页面、任务名称、操作步骤、轮次、得分或最终结果是否符合用例。`step_labels` 仅作为后续语义审查的追踪元数据，回执固定写明 `semantic_content_check: not_performed`，不得据此宣称视频内容审核通过。流程语义仍需人工或后续受控能力复核。

报告采用修复优先流程：本地证据归位和补拍、发布前检查、发布到团队的报告系统、媒体补传和归位、发布后回读、独立语义复核。只有无法修复时才阻塞交付。

报告前两章固定为“核心功能与业务流程录屏清单”和“产品确认暂不处理问题”。详见 [证据与报告](evidence-and-reporting.md)。

### 11.2 自动化执行历史

每次自动化运行必须使用同一个稳定 `automation_id` 和唯一 `run_id` 留下时间与用途记录。通过执行门禁后、首个UI或接口测试动作前运行：

```bash
ai-test execution-log-start \
  --root . --automation-id fictional-catalog-web --run-id RUN-SYNTH-001 \
  --feature "虚构目录查询 Web" --environment sit --platform web \
  --purpose "发布前回归门禁" --objective "确认核心流程可进入下一环境" \
  --scope "搜索、筛选、分页和页面跳转" --baseline "approved-cases@sha256:..."
```

报告媒体修复、发布后回读和执行资产反哺完成后运行：

```bash
ai-test execution-log-finish \
  --root . --run-id RUN-SYNTH-001 --status passed \
  --summary "纳入范围全部通过" --report reports/sit.md \
  --evidence runs/RUN-20260920-001/evidence-manifest.json \
  --asset-change "更新新版入口定位"
```

项目根目录 `AUTOMATION_EXECUTION_HISTORY.md` 是固定人工查看入口，展示每套自动化的首次执行时间、最近执行时间、累计次数以及历次执行的作用、目的、范围、耗时和结果。`.ai-test/execution_history.json` 是防重复和计算用机器状态；同一 `run_id` 重复开始不会增加次数。中断、阻塞和失败也必须收口，不能只记录成功运行。

开始和结束时间默认取当前本地时区，也可显式传入带时区的ISO-8601时间。日志不得包含账号、密码、Cookie、Token、私有接口参数或客户隐私数据。

## 12. 问题定性

页面异常先记为候选问题。根据需求依据、前置状态、缓存、旧数据、异步任务、权限、操作顺序、复现率、接口、日志和数据回读判断属于：产品缺陷、环境问题、测试数据问题、自动化脚本问题、设计如此、待优化、忽略或证据不足。

通过必须覆盖用例全部断言。部分执行不能标记通过，应标记阻塞或未执行。

## 13. 多会话协作

默认一个需求使用一个任务。聊天记录不作为运行状态。用户说“接手需求 REQ-XXX”后，Agent 必须运行 `ai-test work-item-show --root . --requirement-id REQ-XXX`，按返回顺序读取工作项文件，再继续执行。

项目使用 `.ai-test/work-items/index.json` 维护机器索引，使用 `TEST_WORK_ITEMS.md` 提供人类总览。每个需求在 `.ai-test/work-items/<requirement-id>/` 中独立保存 `manifest.json`、`workflow-state.json`、`handoff.json`、`decisions.md`、`asset-links.json` 和 `artifacts.json`。`artifacts.json` 把需求ID、运行ID、基线ID、稳定产物ID、类型、路径、SHA-256、审核状态和阶段绑定起来；不同需求不得共享一个可写状态文件，同一需求、同一阶段只能有一个写入者。

任何需求、规则、用例、执行包或报告产物生成后，必须立即运行 `work-item-artifact-register`。登记的有效产物阶段高于当前状态时，工作项自动推进；审核页生成只能推进到等待审核，不能等同于审核通过。切换会话、进入正式用例设计或怀疑状态过期时运行 `work-item-reconcile`，检查文件缺失、哈希变化、状态落后、历史目录中的未登记产物和用例设计门禁，并保存 `reconciliation-receipt.json`。聊天中的完成声明不能替代产物登记与回执。

需求、流程、断言和用例审核可以对当前筛选结果执行带二次确认的批量通过；导出仍须按稳定ID逐项记录决定并允许单项修正。需修改、不适用、待决策、删除、依赖范围和完整性审批保持逐项操作，不能通过批量功能省略理由或跨过门禁。

同一需求跨 SIT、预发布和正式环境时沿用同一工作项，但每个环境保留独立运行记录与报告。新需求、新正式用例基线或需要真正并行的独立目标创建新的工作项。详细使用方式见 [一需求一任务使用说明](ONE_REQUIREMENT_ONE_CONVERSATION.zh-CN.md)。

事实优先级：产品经理最新明确决定、已审核正式基线、当前运行证据、已验证资产、已审核测试方法/遗漏风险、AI推断、跨工具记忆与历史聊天。知识路径按 [测试上下文索引](TEST_CONTEXT_INDEX.md) 路由；检索命中不能代替读取，知识索引也不代替来源权威性判断。详见 [多会话协作](multi-session-coordination.md)。

## 14. 固定状态链

```text
INTAKE
SYSTEM_DISCOVERY（按条件）
FEATURE_DISCOVERY
REQUIREMENT_FREEZE
AUTOMATION_READINESS_PLANNING
CURRENT_VALIDATION
BUSINESS_TOPOLOGY_ANALYSIS
ASSERTION_DESIGN
BUSINESS_ASSERTION_REVIEW
RULE_CURRENT_SYNC
CASE_DESIGN
FLOW_COVERAGE_GATE
DATA_BUILD
AUTOMATION_HANDOFF
ASSET_VALIDATION
PRE_EXECUTION_CONFIRMATION
EXECUTION_GATE
EXECUTION_LOG_START
TEST_EXECUTION
ISSUE_TRIAGE
OMISSION_RISK_RETROSPECTIVE
RESULT_WRITEBACK
REPORT_REPAIR
ASSET_FEEDBACK
EXECUTION_LOG_FINISH
COMPLETE
```

`SYSTEM_DISCOVERY`可以按条件跳过，其他阶段如果不适用也必须留下带原因的回执，不能静默消失。`ASSERTION_DESIGN` 表示业务拓扑、流程和原子断言已经生成并通过机器校验；审核页生成后进入 `BUSINESS_ASSERTION_REVIEW`；只有人工审核导出通过校验并形成 `rule_review_receipt` 后才能进入 `RULE_CURRENT_SYNC`。进入 `CASE_DESIGN` 前，`work-item-reconcile` 必须确认自动化准备度计划、规则审核回执，以及“规则 Current 已同步”或“本轮明确不适用”的处置回执均已登记且状态有效。

## 15. 资产反哺

业务事实和产品决策进入受控业务知识库；缺陷暴露的漏测、用户纠正和测试误判进入《测试遗漏风险规则库》；导航、页面、定位、测试数据、环境经验、证据计划和自动化动作进入执行资产。风险规则是测试设计经验，不能代替当前已审核业务预期。账号、密码、Cookie、Token和一次性敏感数据不进入任何资产。

每次正式用例生成都要在当前知识检索阶段查询《测试遗漏风险规则库》，产出 `omission_risk_audit.json`。命中项必须映射到独立用例，或以有依据的不适用、阻塞、待审状态处置。对于同时存在连锁和门店范围的搜索、筛选、选择器及关联功能，必须分别评估两个视角；顾客和员工还要按组织归属或关联状态准备可区分的数据。

资产必须记录来源、环境、平台、产品版本、最后验证时间、状态、文件哈希和备份回执。只有本地文件且无版本或备份时，状态为 `local_unbacked`，不能宣称闭环完成。

## 16. 框架变更规则

任何影响用户入口、执行流程、CLI、Schema、目录、平台支持、报告门禁或安全规则的修改，都必须：

1. 修改对应测试并先观察失败。
2. 修改代码或Playbook。
3. 同步更新本手册与根README。
4. 更新 `framework-manifest.json` 版本。
5. 执行全量测试与 `docs-check`。
6. 在迁移或发布回执中记录变化。

## 17. 开源与内部资产边界

公开仓库包含框架、Schema、模板、脱敏示例和通用适配器。真实账号、内部域名、私有协作文档、真实截图、业务数据和未脱敏历史执行资产应保存在私有仓库或受控文件空间。公开前执行敏感信息扫描和示例脱敏。

### 17.1 私有资产仓库的创建与接入

团队首次接入时用脚手架生成受控私有仓库，不要手工拼目录：

```bash
ai-test private-scaffold --root ./my-private-assets \
  --name "Example Products" --system-id example-products \
  --environment sit --platform web
```

脚手架写入项目画像、`knowledge/` 注册中心、参考 `scripts/knowledge_registry.py`、`.gitignore` 与接入说明；生成时写入真实 SHA-256，因此立即可通过 `validate`。既有文件一律不覆盖。

私有仓库是 `ai-test` 命令的项目根（`--root <private-repo>`），工作项状态写入其 `.ai-test/`。跨边界读取只有三个只读命令：

| 命令 | 作用 |
|---|---|
| `ai-test knowledge-audit --private-root <repo> --feature F --stage S` | 先 `validate` 再 `load`，并逐条复算返回路径与哈希 |
| `ai-test baseline-snapshot --private-root <repo> --requirement-id REQ-X` | 复算工作项本地基线的身份与哈希 |
| `ai-test doctor --root <repo> --private-root <repo>` | 离线安装健康检查加知识 manifest 哈希预检 |

契约见 `schemas/knowledge-registry-manifest.schema.json` 与 `schemas/knowledge-registry-load.schema.json`，流程说明见 [私有资产仓库接入](PRIVATE_REPOSITORY_INTEGRATION.md)。

知识注册中心只做路由与哈希绑定：它不证明 Agent 已读或理解文件，不代表远端 Current，也不授权任何业务写入。只有 `reviewed` 与 `approved_test_method` 条目可作为 `required_reads`；`pending_review` 候选永远不进入正式预期。私有仓库不得提交账号、密码、Cookie、Token、客户数据、截图、视频、下载文件或运行证据。
