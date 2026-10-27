# AI参与测试的识别与路由

自动化准备度先回答“需要什么能力、谁负责动作、谁能判定”，再选择执行器。按测试目标及正式断言判断，不能按功能名称是否含AI判断。既有v1计划保持原行为；新增或实质修改的动态功能使用v2。项目能力目录是测试方法，不是产品预期或第二套用例基线。

## 建设可回归对象

先读取项目知识目录和历史资产。对每条新增／实质变更Case建立testability_assessments：不稳定性来源、可复用或拟建设资产、环境、负责人或owner_pending、成本收益、前置、冻结与漂移检测、保留／清理、Oracle缺口和下一步。不能直接永久标manual_only而省略分析。需要建设时主动提出隔离Fixture、版本化审核答案或blueprint、独立金标／审计和可观测接口方案；该建议不扩大业务写权限。

## 生成计划与建议

```bash
ai-test readiness-plan --input templates/automation-readiness-v2.example.json --output /tmp/practice-readiness.json
# 也可明确传 --ai-capability-catalog；与source引用冲突时拒绝
ai-test readiness-check --plan /tmp/practice-readiness.json --confirmation /tmp/practice-confirmation.json --output /tmp/practice-gate.json
```

目录参考[公共示例](../templates/ai-test-capability-catalog.example.json)与[Schema](../schemas/ai-test-capability-catalog.schema.json)。source的catalog_ref记录目录ID、相对source目录的路径、文件原始字节SHA-256；CLI冻结真实绝对路径，执行前重新只读核对文件哈希。目录丢失、漂移、重复或未知能力、source与目录不兼容均拒绝。仅复制source到另一目录时须同步调整路径并重新冻结；不要手改执行后的计划。

每条Case声明execution_strategy：deterministic、ai_assisted、hybrid_required或human_semantic_review；ai_capability_bindings按Case声明required／recommended／optional。计划只冻结被引用的能力，目录可同时收录其他功能。每项能力声明角色、输入输出契约、超时、停止条件、降级和结论权限。

execution_recommendations逐Case列出AI职责、确定性执行平台、完整断言与Oracle及实际命中的确定性参考输入。正式执行建议应据此说明具体组合，例如“AI逐轮回答＋Minium操作／API状态回读”，不要只报Minium。required缺失阻塞整条相关Case；recommended缺失只减少非门禁诊断并告警，不能承载正式断言；optional缺失记录但不阻塞。无模型不阻塞独立的确定性Case。

## 当前能力检查

目录的configured只是配置提示。每次运行的ai_capability_checks须包含capability_id、status（available／unavailable／unknown）、checked_at、target_environment、catalog_sha256、非敏感evidence_ref。缺项、无证据、环境／哈希不匹配、未来或过期时间都不算可用。confirmed_at也必须新鲜；默认最长300秒，可在计划中冻结1至3600秒。输出未知时停止依赖动作，不提交固定无关话术。

AI超时、Provider失败、低置信、输出契约不符或请求身份不符，继续按原运行器的停止／一次性消费规则处理，不自动重发业务请求。现有ANSWER_REQUIRED文件交接继续使用，公共框架不调用模型、不替换Runner、不读取密钥。

## 输入和正式结论分开

AI能力的input_provider、advisory_only、evidence_reviewer、human_required都是权限上限，不能直接满足正式断言。human_required仍必须取得独立人工复核回执。

每条正式断言在assertion_oracle_bindings绑定稳定assertion_id、required_conclusion_authority、oracle_refs及用途（结果／语义质量／副作用／鉴权／持久化）。oracle_resources冻结资源ID、版本、哈希、kind和独立性依据。执行确认的oracle_resource_checks必须匹配版本／哈希／kind，状态available、审核approved、独立性true、时间／环境／证据有效。语义金标或人工资源还须review_receipt_ref。composite同时要求两个以上不同authority及全部声明的资源，不能任选一项。

审核参考答案和answer blueprint是输入Fixture，不能注册成产品／语义Oracle，也不能用生成答案的AI自评证明评分正确。语义质量必须使用独立审核金标或正式人工回执；没有时阻塞相应Case，只能执行原已审核、具有独立ID及完整预期的状态／结构子Case，不得临场缩减原Case断言。

## 题库与开放式陪练

- 固定题库：deterministic_fallbacks只能使用approved_reference，绑定同一Case／能力、题目ID及题干哈希、输入资产ID／版本／哈希、完整Case范围。reference_answer_checks逐项匹配并提供新鲜证据后，ai_assisted Case才可走确定性回答。候选答案、题目变化、未审核或缺证不得使用。
- 开放式陪练：blueprint约束场景、禁区和回答要点，逐轮仍根据真实问题生成相关答案。hybrid_required和answer_blueprint_rendering不支持“有blueprint就不需要运行时AI”的降级。
- 页面、权限、题数等独立Case可确定性执行，不能把未完成语义目标写成完整陪练通过。

## 迁移和证据

旧计划、失败和运行记录保持当时范围；首次再次执行已登记动态功能时重新生成v2计划。正式用例基线、角色权限、输入租约、业务授权和原执行日志门禁仍适用。准备度通过只证明前置声明满足合同，不证明模型输出／产品结果正确；实际执行还须校验交接身份、完整证据及独立Oracle。
