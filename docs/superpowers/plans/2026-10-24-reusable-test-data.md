# 通用测试数据能力实现计划（待审草案）

> 执行者须先取得需求与本计划的审核结论，再按任务实施；当前所有复选框均未执行。采用当前框架的执行计划/TDD/复用审核流程，不因本文存在而授权运行业务写入。

**Goal：** 让新旧功能优先共享稳定数据定义，按环境准备独立实例，通过统一入口查询、领取、补齐与对账。

**Architecture：** 公共Python核心管理协议、索引、计划与门禁；私有Provider复用现有API工厂、只读查询和Page Object/E2E。复用已有readiness/work-item/知识索引，不新建平行正式用例或模型编排系统。

**Tech Stack：** 现有Python标准库、SQLite（单机共享协调库）、JSON Schema、Markdown；私有Node/Bun/Python/Minium/Playwright按既有资产使用，不为统一语言重写工厂。

**Spec：** [SPEC-TEST-DATA-001](../specs/2026-10-24-reusable-test-data-design.md)；关联[AI路由设计](../specs/2026-10-24-ai-assisted-test-routing-design.md)。

状态：review_pending；工作项REQ-FRAMEWORK-TEST-DATA-20261024-001。本轮用户要求先好好想、先不实现；以下路径、接口和命令均为实施建议，未发布能力。

## 全局约束与阶段

- 新CLI/Schema向后兼容；`data-generate`继续负责离线文件，不偷偷变为业务造数。
- 公共仓库不保存业务端点、真实ID、账号安全引用值、客户资料或题目答案正文。真实映射/输入/Oracle归私有项目。
- 同一蓝图分别部署到经过核实的目标；99不能按区域名称推断stage或直接使用SIT写授权。
- 默认query/plan零业务写入；apply按计划目标、动作、数量与批准范围执行；cleanup独立。
- 代码实现、离线验证、历史回执、当前现场验收分别记录；部分环境未验收只能partial。
- 不重写历史报告；脚本迁移不修改预期；输入答案不作为评分Oracle。

建议顺序：M0历史/现状盘点与目标冻结 → M1统一登记+查询 → M2稳定基础包+受控工厂+SIT/99对齐 → M3历史脚本迁移+小程序专项包 → M4默认工作流与持续治理。各阶段均有能独立交付的成果；小程序包模型从M0/M1并行考虑，部署与迁移依赖M2能力。前置不足仅阻塞受影响的实体/环境。

## 文件与职责建议

| 位置 | 职责与复用方式 |
| --- | --- |
| `src/ai_test_framework/fixtures/models.py`、`registry.py` | 新业务Fixture蓝图、环境实例、使用绑定；现有文件manifest不替换 |
| `fixtures/provider.py`、`query.py` | 新Provider协议与只读结果验证；不含任何业务路由 |
| `fixtures/planner.py`、`executor.py` | 依赖计划、dry-run、写意图/幂等/未知态续跑；适配既有工厂，不形成第二套实际创建代码 |
| `fixtures/health.py`、`leases.py`、`reconcile.py` | 健康与指纹、读写原子租约、语义字段对齐/隔离 |
| `schemas/business-fixture-*.schema.json`、`templates/business-fixtures/` | 蓝图/绑定/计划/回执与纯虚构示例；使用新文件避免破坏旧`fixture-manifest` |
| `src/ai_test_framework/cli.py`、`execution_readiness.py`与`schemas/automation-readiness.schema.json` | 薄命令路由、新契约可选版本与准备度绑定，历史版不追溯改写 |
| `.agents/skills/`与`docs/test-data-strategy.md` | 更新已有Fixture管理/准备度/执行路由，统一引用规范，不复制规则正文 |
| 私有项目`shared/fixtures/`、`shared/queries/`、`shared/environments/` | 扩展既有目录/查询/安全目标解析；真实业务映射和能力表，不复制进公共核心 |
| 私有项目`features/<feature>/`的工厂/脚本 | 逐消费点适配；题库/陪练/答案包在原feature内维护；保留旧Runner |

内部文件划分可遵循项目规模调整；上述职责边界、向后兼容与唯一数据源不可省略。

## Task 1 / M0：历史功能与消费脚本盘点（TD-014/015/016）

- [ ] 按完整工作项索引遍历历史与当前功能，不仅扫描活跃功能；检索Fixture、脚本参数/硬编码ID、环境目标、角色、readiness、执行资产注册和非敏感运行回执。
- [ ] 交叉扫描实际仓库目录、脚本、包命令与配置入口，对账“已登记且有文件、有文件无登记、有登记无文件、未能读取”，记录扫描根、排除项及理由；补足未登记历史消费者。
- [ ] 私有项目新增`shared/fixtures/migration-inventory.json`及对应知识索引条目，逐消费者记录`feature_id, script_ref, old_fixture_ref, entity, target_ref, operation, state_dependencies, proposed_fixture_key, disposition, blocker, verification_ref`。
- [ ] 不读取历史凭据、不复制真实数据；身份/状态只记候选，未现场回读不升级validated。
- [ ] 按复用率候选、执行频率证据、人工查ID等待、迁移风险形成优先队列；缺统计则标unknown，不编造频次。
- [ ] 冻结首批蓝图建议：3个只读合成会员、2个服务、1个疗程及4层角色profile；数量是首批验证样本建议，权限组合/异店反例按需求追加，不能据此认为覆盖完整。小程序题库/陪练包列为首批专项。

产出/验收：所有已登记消费者都有migrate/defer/retain/retire决策与依据；用户能看到哪些旧功能会迁移、先后顺序及缺口。重复脚本不直接删除。

## Task 2 / M1：统一协议与可发现目录（TD-001/002/003/012）

接口草案：`load_blueprint(path) -> Blueprint`、`resolve_binding(fixture_key, version_constraint, target_ref) -> Binding`。实例记录和能力catalog通过项目已有索引发现，不能出现两份竞争台账。

- [ ] 先写`tests/test_fixture_registry.py`：合法蓝图/引用、重复key、多环境不同ID、依赖环、缺角色映射、敏感字段拒绝、旧文件清单兼容、旧消费者不追随latest、蓝图多版本共存与显式迁移。
- [ ] 运行专项确认失败，再最小实现Schema/registry及虚构模板。
- [ ] 扩展既有私有catalog/台账，保留原asset_id与适用边界；每能力按实体×目标×query/create/verify/restore列ready/pending/blocked。
- [ ] 只增建议命令`ai-test fixture catalog/resolve/health`及JSON契约，帮助文本明确零业务写入；现有版本命令不改语义。
- [ ] 专项通过后验证文档、Schema与敏感扫描，提交可审查增量。

验收：两个虚构功能解析同一稳定蓝图，各目标绑定不同本地ID；私有未映射目标报具体缺口，不回落其他区。

## Task 3 / M1：Provider与快速只读查数（TD-005/008/012）

协议建议：`capabilities(target) -> CapabilitySet`、`query(request) -> QueryResult`、`detail(binding) -> Observation`；Provider由项目登记的固定入口绑定，禁止从不受信任蓝图执行任意shell/任意URL。

- [ ] 先写`tests/test_fixture_query.py`，覆盖分页完整性/服务端缩页、重复ID、精确0/多命中、任一合格对象的确定排序、HTTP/业务拒绝、超时、跨店/错环境、脱敏与未知字段。
- [ ] 薄适配现有只读CLI/库，保持同会话凭据、环境白名单、稳定JSON与退出码；不另写会员列表API。
- [ ] 输出`fixture_key/target_ref/local_id_ref/checked_at/eligibility/evidence_ref`，运行动作前冻结选中身份；任意候选不满足写场景条件。
- [ ] 本地假Provider验证通过后，再按已冻结只读计划验证实际目标；无凭据仅阻塞对应目标。

验收：满足“临时要一个合格会员即可”时无需用户查ID/UI查找；需要特定身份时精确匹配，不用任意选择绕过唯一性。

## Task 4 / M2：健康、租约与场景隔离（TD-007/008/011）

接口建议：`check_health(binding, requirements) -> HealthReceipt`、`acquire_lease(binding, mode, run_id, ttl) -> Lease`、`release_lease(lease, observation) -> Disposition`。

- [ ] 先写`tests/test_fixture_lifecycle.py`：读读共享、读写互斥、并发领取、进程中断、过期不自动健康、版本/权限漂移、不可恢复数据进入consumed/quarantined。
- [ ] 单机共享目录采用原子事务/锁；跨机器共享Provider未建设前明确拒绝跨机同池写操作，不宣称团队全局锁。
- [ ] Provider按实际目标/组织+实体类型+物理ID归一锁键，别名key不能绕开锁；动作声明read_set/write_set及依赖副作用，跨实体影响集原子领取。副作用不明保守排他或阻塞。测试订单消费与会员读/写冲突、两逻辑key映射同一物理对象。
- [ ] 检查关键状态/依赖/权限，租约绑定版本与指纹，写动作前再次校验；不替代服务端鉴权。
- [ ] 释放时核实际状态，恢复/清理独立受控；恢复不支持时生成新实例建议，不能覆盖公共池。

验收：两个并发任务不能同时改变同一共享对象；脚本超时不会把半成品数据返还基础池。

## Task 5 / M2：受控工厂与跨环境对齐（TD-004/006/011）

接口建议：`plan(blueprints, targets, observations) -> FixturePlan`、`apply(plan, authorization_ref) -> RunReceipt`、`reconcile(intent, observations) -> Reconciliation`。实际create/verify/restore由登记的现有Provider负责。

- [ ] 先写`tests/test_fixture_planner.py`与`test_fixture_executor.py`：仅补缺、幂等、身份错配、计划哈希变化、依赖失败、未知提交禁重发、同名多命中、无通知、额度与权限不超范围。
- [ ] 对现有会员/员工/服务/商品工厂做复用评审，参数化扩展原资产；疗程/授权缺合同单独采集，不创建竞争实现。
- [ ] `plan --dry-run`只生成差异/授权需求；默认纯离线输入观察快照，如需在线观察显式走只读query。`apply`校验目标阶段、角色、动作/数量和批准范围，再落意图并逐项执行。
- [ ] 同一蓝图分别部署SIT与99；每目标保存本地映射与回执。关键字段must_equal，ID/组织/角色本地映射按语义比对；允许差异必须有来源。
- [ ] 先冻结实际造数计划/原子断言、唯一Fixture、独立Oracle与恢复边界，再分目标现场验收。目标缺前置时保留partial，不回滚另一目标无关数据。

验收：重复运行创建数0；中断可只读对账续跑；两目标均验收后才声称跨环境对齐。不以名字后缀一致判同步通过。

## Task 6 / M3：旧脚本分批迁移（TD-014/015）

- [ ] 新增私有统一resolver/binding包装，旧Runner只换数据消费边界，保留Case、Oracle、动作/恢复状态机和运行协议。
- [ ] 首批选两个纯读取/可重复功能证明同包复用，再按M0风险清单迁移服务/疗程配置、会员消费、订单/关联、权限等脚本。
- [ ] 每脚本增加契约测试：按目标取正确绑定、缺映射拒绝、旧硬编码不会静默回落、锁冲突拒绝、动作前状态漂移停止。
- [ ] 经批准在各目标按原用例预期回归，记录代码版本、run_id、实例映射、结果和证据；未运行环境明确blocked/not_executed。
- [ ] 更新原资产注册/包命令/知识索引；历史报告保持原文件/哈希。旧入口弃用列出消费者覆盖和兼容截止，未迁移入口不能直接删除。

验收：迁移清单逐消费者闭环，扫描与实际调用回执相互验证；“删完硬编码”不单独作为完成证据。回退代码不重发未知业务写入。

## Task 7 / M3：小程序题库/陪练专用包（TD-017）

依赖AI路由设计的资产与readiness契约；若该设计尚未实现，先通过接口约定/假Provider测试推进，不复制实现第二套能力路由。

- [ ] 定义私有题库、题目、场景、approved_reference、answer_blueprint、练习员工/分配与独立评分Oracle资源的稳定ID、来源、审核和哈希绑定。
- [ ] 先写漂移/路由测试：改题使旧答案失效；未审答案不能确定性作答；blueprint不保证纯确定性；输入答案不能绑定产品结果Oracle；旧ANSWER_REQUIRED token/超时/单次消费保留。
- [ ] 在用户指定且现场核实的SIT 99目标按计划创建专用配置；跨环境同包部署仍走Task5，不混用其他模块生产z99目标。
- [ ] 将现有小程序Runner切换到统一包解析；配置长期复用、练习会话/结果每run独立；后台配置与小程序消费分别验证权限/组织/状态与报告。
- [ ] 评分语义只有独立金标/rubric/人工回执就绪才验收；结构/状态通过不能填成语义质量通过。

验收：可重复启动同版专用题库/陪练，知道本次题目/输入/场景/Oracle版本；随机内容不会使脚本任意换目标或反复运行筛选想要分数。

## Task 8 / M4：准备度默认路由、主动建设与治理（TD-009/010/013/016）

- [ ] 先写`tests/test_fixture_readiness.py`：历史契约兼容、新版缺实例/健康/租约/内容资源只阻塞依赖Case，其他用例继续；原Case缺AI/Oracle不缩小口径冒充ready。
- [ ] readiness source引用fixture需求、资产ID、版本/哈希与testability_assessments；执行回读写入fixture_resource_checks，复用AI路由设计同名语义，不另设平行资源检查。
- [ ] 每个新/实质修改功能主动分析高频复用、可建设稳定输入、观测点、金标、AI分工、成本与维护责任；无法自动化先列可测性建设方案及具体缺口。
- [ ] 更新canonical Fixture管理/用例设计/执行Skill、准备度模板、手册与示例，确保标准/快速模式都先查数据目录；不强制把历史计划追认新版。
- [ ] 登记复用率、数据准备耗时、人工查ID次数、重复建数、跨目标差异、漂移/租约冲突和未知态。先测基线，再给提升幅度，不预填节省百分比。

验收：新Agent不依赖旧聊天就能找目录、查询、绑定/补缺、输出差异和停止原因；历史再次执行时按迁移表升级，历史结果不被改写。

## 验证与发布顺序

每任务：失败测试 → 最小实现 → 专项测试 → 适配/Schema/隐私检查 → 独立代码复核 → 必要现场验收。离线与现场分开。

公共集成验证：`python3 -m unittest discover -s tests -p 'test_*.py'`、`./bin/ai-test docs-check --root .`、`./bin/ai-test skills-check --root .`及项目现有隐私检查。只有文档本轮不运行这些全量产品/业务测试，实施时再执行。

私有项目登记复用评审、计划哈希、execution-log-start/finish、逐场景证据、原账号与数据台账及knowledge/manifest选择性哈希更新。UI通道同时遵守当前窗口版本门禁和六维交互体验检查；API成功不能替代UI体验通过。

灰度：先虚构Provider → 单目标只读 → 已批准最小写入包 → 双目标对齐 → 低风险旧脚本 → 高风险/AI专项 → 默认新功能入口。全程可回退数据消费适配；历史证据与未知写意图不可回退删除。

## 阻塞与不阻塞项

99目标身份/阶段/安全引用、批准的测试号段、疗程/授权创建合同、可恢复语义、独立金标与跨机器存储是现场推进前置。它们不阻塞通用协议、静态历史盘点、假Provider测试或已就绪目标只读实现。具体缺口与建议见需求B1..B8；此阶段不向用户索要普通SIT操作的重复授权，也不把本方案当作99生产写入许可。

工作量以M0盘点、适配器数量与缺合同数后估算，当前不承诺固定工期。开发优先级P0，先做数据复用/查询与原资产接入，避免一开始建设集中平台。


## v0.2评审增补：实施顺序与完成门槛

- [ ] M0之前：框架和业务脚本做独立Git回溯分支/标签，记录提交、排除项、离线验证；保存当前可复现的配置引用，凭据及运行数据库不入Git。
- [ ] Task1增补：按Case和实际消费者双向盘点原数据、显示名、登录标识、定位器/导入文件依赖，生成旧→新映射和覆盖差距；逐行决定rename/rebind/recreate/keep/defer，不批量盲改。
- [ ] Task2增补：自然中文显示名、稳定机器键、别名表、账户登录规则、用途/权限/可消耗状态；增加中文目录生成器，公开仓仅虚构模板，私有项目保存真实目标导航。
- [ ] Task4增补：标准库sqlite3实现单机跨进程/worktree协调，唯一库路径、短事务、完整影响集、心跳与代次；增加多进程竞争/崩溃/旧worker续写/数据库不可用/人工污染负控。过期租约须对账后释放。
- [ ] Task5增补：SIT运行增量输出版本化data-needs，结束冻结；“SIT测完”或“测99”触发prepare-target，复用健康对象、补缺、按目标重算时间与周期、输出逐Case准备结果。自动触发只在用户当前任务回合执行。
- [ ] Task5/7增补：新增recipe协议和组合provider，先预约陪练、目标陪练两条，再按需求文档11.4与历史Case使用频度排序；逐步复用原工厂，独立构建缺合同的步骤，不复制整条Runner。
- [ ] Task6增补：先建替代数据并回读，按函数/配置统一resolver，更新Case前置绑定但不变预期；登录名可改性、跨端登录与权限单独验证；迁移成功后退役旧数据，不提前清理。
- [ ] Task6验收：旧Case完整映射且适用脚本在SIT/99分别实跑；加入并发和组合流程失败续跑场景。报告按脚本/Case列passed/failed/blocked/not_executed，不用本地单测代替业务回归。
- [ ] Task8增补：从同一登记源导出人工测试手册及Notion副本；包含账号别名、环境/店、数据用途、状态、准备入口、占用说明和验证时间；上传后回读版本/内容，失败本地记pending_sync，不影响独立测试。
- [ ] Task8增补：私有账号政策持久化SIT/99自主登录及用户指定统一凭据的安全引用；登录失败查引用/状态/身份，不重复索要已有密码或权限；改密码仍逐账号验证，不把保存引用称为已经重置成功。

新增需求TD-018..024均纳入P0完成检查。首期不依赖远端数据库/服务，Notion不作为事务协调库。本轮新增内容均为计划，未执行迁移、改名、账号重置和现场回归。
