---
name: test-data-and-account-fixture-management
description: Use when planning, creating, maintaining, reading back, isolating, or cleaning test accounts, employee/customer records, roles, configuration, payments, orders, or other reusable business fixtures.
license: MIT
metadata:
  author: ai-test-engineer
  version: "1.0.0"
---

# 测试账号与业务Fixture管理

目标：为测试建立明确用途、可区分、可回读、可追溯、可重复运行的合成账号和业务数据。数据只服务于声明的测试范围，不把不同用途、状态或环境的Fixture混用。

## 安全红线

- 不在仓库、Skill、账号台账、测试报告、截图、日志、Nowledge Mem或聊天中记录密码、验证码、Cookie、Token、Authorization、私钥、storageState或完整认证载荷。
- 不设置、建议或复用公开固定密码（包括常见默认密码）。密码只能通过组织批准的密码库或受保护运行时变量注入。台账只写变量名/密钥引用、责任人或轮换说明，不写值。
- 不从仓库、历史报告、浏览器日志或对话中“找回”密码。用户在目标环境/角色/组织范围内已授权自主登录时，先检查工作项已有的非敏感账号别名和安全运行时引用，在当前执行器按批准方式获取凭据、登录并回读身份；会话过期不要求用户重新许可或手动登录。Ego Lite与Playwright各自校验登录前置，不跨执行器复用Cookie或storageState。安全引用确实缺失/不可用、身份范围无法核对或需要用户亲自完成MFA/验证码时，才阻塞依赖项并说明具体安全注入缺口；口头授权不等于凭据已可用，不猜测或泄露凭据。
- 手机号、顾客资料、员工隐私与支付凭证使用环境提供的合成/测试数据；不得自行编造可能属于真实个人的号码，也不得复制真实顾客数据。若系统强制手机号，使用组织明确批准的测试号段或安全Fixture供应器，并以环境变量引用保存。
- 生产写入、不可逆操作、真实通知、金额/库存变更或批量动作必须单独确认授权和影响范围。SIT写入仍须确认目标环境、门店、角色和具体操作。

## 先分类用途，再命名和创建

每个Fixture创建前，为其记录唯一`fixture_id`、用途、实体类型、目标环境/组织/门店、状态、拥有需求/用例、创建方式、依赖、回读断言和清理策略。显示名使用自然、可读的业务名称；场景性很强时直接表达状态。机器键与显示名分开，旧前缀作为历史别名保留，不为美化名称直接改正在被用例引用的数据。例如：

- `commission.base.*`（显示名如“舒缓肩颈护理”）：批量导入的稳定基础服务、职位、规则基线。
- `commission.export.excluded.*`（显示名如“停用服务·导出排除”）：禁用、草稿、无规则等仅用于导出范围断言的对象。
- `commission.order.before.*` / `commission.order.after.*`：用于验证历史订单不变和新订单规则生效。
- `commission.role.editor` / `commission.role.readonly` / `commission.role.denied`：隔离权限账号与对象。

名称应表达用途和状态；不同用途不能只靠备注区分，也不得让排除范围的对象进入正式导入基线。数据需求变化时优先建立新的隔离Fixture，不把旧Fixture静默改造成另一用途。

## 账号设计与台账

- 按最小权限建立独立账号：Fixture管理员只负责造数/恢复/清理，不作为权限测试结论；业务编辑、只读和无权限角色分别验证。
- 每个账号限定环境、组织/门店、角色、用途、允许动作、登录变量引用、创建状态、验证日期和停用/回收策略。
- 台账仅记录非敏感显示标识或稳定测试账号别名及密钥引用，例如`SBA_USERNAME`、`SBA_PASSWORD`；禁止记录变量值、完整手机号和真实人员身份。
- 角色授权变化后退出并重登验证；分别检查菜单、页面、直达地址/导航和拒绝后数据未变。管理员成功不能证明受限角色权限正确。
- 员工密码由专用运行时变量注入；员工手机号按每个Fixture的环境变量引用提供。变更后做最小范围回读，避免在日志/错误截图中留下输入内容。

## 本地数据工厂入口与跨环境交接

已安装业务 Fixture 模块的项目，先读 `docs/business-fixtures.md` 的协议，再由项目知识索引定位私有 `shared/fixtures/` 中的能力目录、版本化蓝图/首次绑定、迁移清单与账号数据手册。不存在时明确缺口；不把示例值或其它项目的目录当成当前数据。

| 环节 | 现有入口与必需输入 |
| --- | --- |
| 发现 | `ai-test fixture catalog --root <private-root>`，并读项目登记的 Provider 能力表；只读临时会员通过该项目既有查询入口获取，再冻结唯一身份 |
| 运行中记录 | `ai-test fixture record-need --root <private-root> --input <need.json>`；输入 `run_id` 及 `need`，need 含 `requirement_id, case_id, fixture_key, version, usage` |
| SIT 结束 | `ai-test fixture freeze-needs --root <private-root> --input <run.json> --output <frozen.json>`；输入 `run_id`；不再改变已冻结清单 |
| 切到 99 | `ai-test fixture prepare-target --root <private-root> --input <handoff.json> --output <prepared.json>`；输入 `source_run_id,target_ref,capabilities`，capabilities 来自已核实 Provider；冻结源 needs、解析目标并输出依赖计划与逐 Case 当前准备度 |
| 领取/续租/释放 | `ai-test fixture acquire/heartbeat/release --root <private-root> --input <lease-operation.json>`；完整影响集、run_id 和租约所有者遵循协议；动作前用 `Registry.assert_lease` 复核健康与指纹 |
| 人用手册 | `ai-test fixture handbook --root <private-root> --output <handbook.md>`；私有项目可使用已登记的增强导出器，按同一登记源和本次回执更新 Notion 阅读副本并回读 |

用户在当前任务说“SIT 测完”或“测 99”时执行交接，不另开后台任务。prepare-target 是离线计划，不隐式创建；缺项由项目已登记的工厂按现有授权和冻结计划执行，随后健康回读、语义对齐和准备度检查。SIT/99 自主登录授权沿用，不重复询问已有密码；写入仍绑定具体目标和作用范围。

旧用例迁移逐消费者保存 old→key/version→target/local_id 映射，保留原 Case、独立 Oracle、定位依赖与副作用。运行时 ID 以本地登记库为准，静态绑定仅用于首次导入。未迁移或未实跑的脚本标明未完成；基础包检查不代表原功能通过。

同机 worktree 使用 Git common-dir 内唯一 SQLite；先查健康再原子申请完整影响集，基础/共享场景池只读，可变实例进入 run 池。冲突只阻塞依赖 Case，不能另建数据库、换别名或直接使用旧硬编码 ID 绕开占用。过期租约保持阻塞直至核清未知效果，不自动回收。手册和 Notion 是阅读副本，均不作为锁源。

## 创建、回读与生命周期

1. 阅读已审核需求、业务规则、系统地图、角色模型、现有Fixture契约和历史运行状态；列出reuse/extend/reject/supersede候选。先查重。零命中先区分“应已存在的绑定丢失”和“计划允许创建且尚未绑定的缺项”：前者对账阻塞，后者按已授权工厂补缺；多命中、名字或组织冲突均停止核实。
2. 建立依赖图并按上游到下游创建；创建前写明原状态、断言、独立Oracle、权限、证据、停止条件和恢复范围。
3. 写入必须由经批准的UI/正式自动化入口执行，使用幂等“查找→确认唯一→仅补缺项”；不以隐藏接口、数据库或临时脚本绕过UI业务规则。
4. 写后用独立列表/详情/重新进入页面回读关键字段、对象归属、关联、状态和数量。脚本绿灯或同一表单回显不单独作为完整通过证明。
5. 失败、部分完成或前置缺失时记录现场、已验证范围、阻塞和准确续跑阶段；未变化的缺口只登记一次，不反复尝试。
6. 清理必须按反向依赖顺序，范围仅限该Fixture命名空间；对账号、服务步骤、关系等关键子对象先删除并回读，再删除父对象。关键子对象删除/回读失败时停止下游删除。破坏性清理必须有独立命令和显式双重确认。
7. 运行结束记录状态、证据位置、数据变化和资产哈希；成功闭环前不得标记Fixture或执行资产为validated。

## 财务、订单和导入导出Fixture

- 顾客、卡金、疗程、订单与规则Fixture使用合成且唯一的标识；按“导入前历史”与“导入后新建”分开，不用同一订单同时验证历史不变和新规则生效。
- 交易Fixture记录支付方式、服务、员工职位、指定状态、订单阶段、规则版本、预期来源和清理策略；不记录真实顾客信息或支付敏感数据。
- 正式导入基线只能来自系统正式导出文件；附件模板只作结构参考。所有异常文件从正式基线派生，逐项说明变更，登记源文件与变体SHA-256。
- 导出范围验证使用独立命名空间准备启用、禁用、草稿、无规则等候选对象；这些对象不得混入基础导入/导出正向Fixture。当前具体范围仍以已审核产品规则为准。

## 必需产物与门禁

按项目工作项登记Fixture计划、账号/数据台账引用、执行收据、状态清单、证据清单和执行资产；均不得含敏感值。测试项目应在其受控私有目录维护非敏感账号与Fixture索引，通用Skill只定义方法，不保存某项目账号。

执行前核对：需求/规则/用例基线、准备计划哈希、环境、目标组织/门店、角色、Fixture唯一性/状态、写入/清理授权、Oracle、排除项和证据。自动化开始前运行`ai-test execution-log-start`；结束后运行`execution-log-finish`。有账号或Fixture缺口时只阻塞依赖用例，其余独立工作继续。
