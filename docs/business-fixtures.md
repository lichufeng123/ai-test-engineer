# 本地业务测试数据

本模块从 2026-10-25 开始实施。它提供本地登记、健康检查、读写租约、需求记录、离线准备与可信 Provider 编排。业务接口和真实映射放在私有项目。当前只是已验证的首批能力，完整历史脚本迁移、小程序配置创建和全量双环境回归尚未完成。

## 三层数据

- 蓝图固定 `fixture_key + version`，名称采用自然业务用语，如“舒缓肩颈护理”。有明确状态要求时直接表达“停用会员”。旧脚本不跟随 `latest`。
- 目标固定阶段、区域、品牌、门店、角色、平台和接口版本；SIT、99 各自保存本地 ID。名称相同不能证明业务状态一致。
- `base` 与 `scenario` 共享池只读；会改变状态的实例放 `run` 池。消费后标记 consumed，漂移标记 quarantined，不能通过再查一次自动洗成健康。

蓝图是测试前置定义，不是产品正确性 Oracle。独立预期、权限和各端验证仍由原用例决定。

## 入口

`ai-test fixture --help` 列出命令。所有公共 CLI 命令仅操作本地登记或生成计划，不隐式登录或造业务数据。

```sh
ai-test fixture inventory --root /path/to/private-project --registry-root /path/to/main-worktree --output /tmp/inventory.json
ai-test fixture register --root /path/to/private-project --input catalog.json
ai-test fixture catalog --root /path/to/private-project
ai-test fixture resolve --root /path/to/private-project --key member.smoke --version 1 --target demo-sit-shop
ai-test fixture handbook --root /path/to/private-project --output /tmp/test-data.md
```

样例见 `templates/business-fixtures/catalog.example.json`，全部是虚构值。登记不代表实例已存在。`bind` 绑定后仍为 unknown，只有可信 Provider 按固定身份读取详情、核对属性后调用 `observe` 才可领取。

`acquire` 的 JSON 输入包含 `run_id` 和 `requests`；每个请求包含 `fixture_key, version, target_ref, mode`。必须列出完整影响集，不能只锁最后一步的订单而遗漏会改变的会员。未知副作用阻塞写入。`heartbeat` 与 `release` 都验证租约所有者；释放必须有实际回读。

数据库位于所属 Git 仓库的 common dir 下 `ai-test-fixtures/registry.sqlite3`，同机多个 worktree 使用同一库。非 Git 项目在 `.ai-test/fixtures/`。不要复制数据库到另一个路径后声称仍共用锁，也不要放在网络共享盘。协调范围为此机器、此库且接入协议的执行器；未迁移脚本和人工业务操作不会被自动拦截。

租约过期不会自动解锁，防止旧进程继续写入；崩溃任务保持阻塞。当前没有自动强制解锁/恢复或删除命令。核清执行器已停止及业务状态后再实施受控恢复；不能删库绕过占用。读锁共享，写锁与读写均互斥。框架不能替代服务端事务和鉴权。

## SIT 记录，99 准备

`record-need` 输入 `run_id` 和 `need`；need 固定 `requirement_id, case_id, fixture_key, version, usage`。重复记录幂等，同 Case 同 key 的版本/用途冲突会阻塞。`freeze-needs` 结束记录并输出哈希。修改需求使用新 run/revision，不能改已冻结清单。

用户说“SIT 测完”或“测 99”时，当前任务使用 `prepare-target`（输入 `source_run_id,target_ref,capabilities`）冻结 SIT needs、生成 99 依赖计划和逐 Case 当前准备度；也可分步调用 freeze-needs 与 prepare。prepare 输入为 `needs,target_ref,capabilities`，依赖按拓扑排序；缺 Provider 能力标 blocked。公共 prepare 是离线能力计划，真正“已有则复用、没有则创建”由可信 Provider 的 `find/detail/create` 完成，不能把 planned 写为 ready 实例。

Provider 代码直接使用 `executor.prepare/apply/reconcile`，不从 JSON 加载可执行命令。apply 冻结目标、蓝图、依赖和 Provider recipe 合同；写前持久化意图。创建超时不重发，`reconcile` 只读确认唯一实例后才能续跑。仍在 executing 的旧进程不允许被对账抢占；查不到实例也不视为允许重发。工厂准备保守按区域和品牌串行，避免同品牌多门店重复创建。

`align` 显式比较相同 key/version 两目标的字段。只比较声明字段，不自动映射权限、分类、时间周期或独立 Oracle。已有同名对象的价格/时长不一致时保留差异，不擅自改价。

## 执行准备度与证据

原 `readiness-plan` 可增加 `business_fixture_needs` 和 `business_fixture_target_refs`（环境名到目标引用）。`readiness-check --root` 从本地登记核对健康与版本，输出 `fixture_resource_checks`，检查当前冲突/过期租约，仅阻塞依赖的 Case；准备度不预占资源，动作前仍须原子领取。旧计划不补认新版，不改变原账号、设备、Oracle 与业务断言。

健康检查有 TTL；每次执行前应重新通过 Provider 回读。领取后、动作前检查租约；执行器应定期心跳。一个 `readiness` passed 不是完整功能通过，运行仍须 execution-log、原用例断言、实际证据和 cleanup。

## 当前交付边界

已实现：历史源码/台账交叉扫描、不可变版本登记、目标隔离、三类池、健康/租约、本地跨进程事务、needs、离线依赖计划、未知写对账、语义字段对齐、手册生成和准备度集成。

私有首批接入：既有查询工具、历史服务目录 check/ensure。现场已验证双环境服务只读准备；后续在已核实的品牌造数身份下完成一条SIT隔离服务创建、消费端独立回读与再次ensure零新增。真实中断未知写对账和99创建尚未现场验收。

尚未完成：全部历史 Case 的语义映射、账号/会员改名、所有实体创建合同、预约/目标组合的真实创建、小程序题库与独立金标接入、历史 UI/设备用例的完整双环境回归。历史扫描的 `defer` 必须继续逐项处理，不能用扫描总数作为迁移完成数。


## 2026-10-25 复核修正

观察回执必须携带 Provider 实际完成读取的 `observed_at`、固定目标、详情证据引用和属性。登记时仅接受最近 60 秒的读取，TTL 从读取时刻起算；原样重放和倒序回执拒绝续期。公共 `observe` 接收的是可信适配器回执，不验证第三方伪造时间戳，不能把任意手填 JSON 当成现场证明。

动作前 `assert_lease` 和心跳同时复核全部资源的健康有效期与领取时属性指纹；业务写入前执行器仍须通过 Provider 做新鲜回读。释放要求晚于领取证据的读取。品牌共享服务在不同门店仍是同一物理对象；当前所有实体统一保守按阶段、区、品牌、实体、ID 加锁，可能让门店局部同 ID 发生额外等待。此行为优先避免并发漏锁，后续须凭已验证的实体作用域合同才能缩小范围。

数据库 v1→v2 仅在无活动租约时迁移锁键，同时使旧健康证据过期，不自动释放未知租约。工厂互斥范围仍为品牌，步骤意图另含门店，避免混淆同品牌多店实例。已绑定对象查询消失时，创建前就阻塞；不得先新建再发现不可变绑定冲突。实例 ID 以 SQLite 为权威，私有静态表只用于首次导入。


## 自然名称与旧脚本接入的后续检查点

私有适配增加自然中文别名、会员/员工版本目录和Node→Python薄桥；本地别名、未来计划、实际系统创建分别登记。历史员工通过原账号/姓名/工号/组织登录及另一身份详情核验后显式迁移到新版本：旧账号ID不再冒充员工ID，旧版本保留。原员工Fixture UI用例已在SIT通过原生新版门禁、固定门店与身份回读，持有读租约至使用后独立回读。99员工及完整业务功能未据此验收。

后续双环境工程检查24项：20通过、4阻塞；其中原六服务共12项全部通过。新增SIT专项服务及同语义冒烟会员可解析；99专项缺映射和品牌造数身份，预约/目标写入恢复合同、系统改名迁移仍待接入。上述数量不是正式业务用例覆盖率。具体账号和数据仅记私有手册与Notion阅读副本。

## 显式恢复已消费的运行实例

公共Provider API新增 `Registry.restore_consumed(key, version, target, lease_id, run_id, observation)`。仅接受该实例最近一次由同run持有、已正常释放的写租约；池必须是run，状态consumed，且新鲜回读晚于释放、全部属性精确等于写前快照。活动（含已过期但未对账）的租约、quarantined、物理别名、错目标和重放证据均拒绝。业务恢复仍由已登记的私有Provider执行；本方法只登记已证明的恢复结果，不执行恢复、强制解锁或清理。Provider回执与observe同属本地信任边界，不是远端签名证明。

私有月度目标适配已完成一个SIT顾客目标输入的真实创建、重复复用、受控数量变化及精确恢复；遇到未知提交后，先只读对账，原阻塞运行保留。另一个原生按项目目标没有顾客陪练项，不能标成顾客场景ready。消费侧保存动态子目标ID的每run快照，持有完整依赖读租约；原Runner只新增可选准备入口。子ID改变必须阻塞，不自动重选。

当前验证新增的是目标输入生命周期与原Runner准备，未执行Minium/评分/全部权限；99目标写账号/员工绑定、预约通知副作用合同仍是具体缺口。公共核心不保存这些业务ID/账号/路由。旧当月或弱项Case不得因新的未来月数据可用而改变预期。多端权限组合继续按各需求正式基线验证，成功写入和局部守卫不能替代权限验收。
