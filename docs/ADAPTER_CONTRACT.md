# 可移植的只读执行适配器回执合同

公开框架不内置任何组织的 Case ID、业务规则、地址、账号或 Fixture。接入团队用现有正式基线/临时探针生成 `probe`，在自己的受控项目实现 Web/API/App 等执行器；此合同只规定跨平台可以共同核验的阶段、身份和证据，不导入或运行调用方提供的代码。

## 合同与命令

输入 [`schemas/adapter-trace.schema.json`](../schemas/adapter-trace.schema.json)：`schema_version=1`、已冻结的 `probe`、`adapter={id,platform,source:{path,sha256}}`、严格依序的六个 `steps`。调用 `ai-test adapter-trace-check --input <run-trace.json> --root <project>`；没有产品通过返回值，材料完整时为 `review_required` / 退出码 1。`source` 指向团队项目中已审核的 Python/TS/JS 文件，仅检查内容哈希；框架绝不据此执行任意脚本。直接调团队 runner 而不产生回执，不会被该检查器认定为受控执行。

每步必须绑定 `run_id`、`case_id`、`fixture_id`、`probe_sha256`、`adapter_sha256`，并用 `previous_sha256` 链接前一步。起点为 `digest({run_id,case_id,probe_sha256,adapter_sha256})`；后续为 `digest(previous_step)`。JSON 摘要复用框架现有 `execution_contract.digest` 的规范序列化；不是数字签名，拥有工作区写入权限者能重写整条链。

| 阶段 | 最低载荷 | 不得推断 |
| --- | --- | --- |
| `OBSERVED` | 唯一 fixture 的 ID、稳定业务键、写前状态 SHA、match_count=1 | 不得用待验证的结果值选取目标 |
| `ACTION_GUARDED` | 与 probe 完全一致的只读 action ID/kind/input SHA 及 profile SHA | 不给业务写入授权；目前 `write` 必阻塞 |
| `EXECUTED_ONCE` | 同一 action ID、attempt_count=1、result=observed | 用户提供的回执不证明动作真的发生 |
| `READBACK` | 同一 Fixture ID/业务键，match_count=1，64位状态 SHA | 同源页面相等不是独立 Oracle |
| `VERDICT` | 与 probe A IDs 严格一致的逐断言状态、原 Oracle 文件哈希及本 run 证据引用；未执行/阻塞必须有原因 | 本地断言声明不等于产品事实 |
| `EVIDENCE_REPORT` | 精确覆盖逐断言证据的文件引用，`review_status=pending` | 视频存在不等于语义/隐私审核通过 |

校验缺/多阶段、跨 run/Case/Fixture、前序链漂移、错误业务键、重复断言、Oracle/证据被替换、非本 run 的证据、拟写入动作；文件引用必须处于项目根目录且哈希一致。测试 `tests/test_adapter_trace.py` 用两个完全独立的虚构查询模型验证相同框架合同，不承载任何真实产品预期。

## 可执行的本地合成 SDK

`ai_test_framework.synthetic_adapter_runner.run_synthetic_readonly_adapter(probe, adapter, project_root)` 是调用方显式构造适配器对象的可执行接口（不会从 CLI 动态加载插件）。它先做 `probe-check`，强制 `stage=local, zone=synthetic, kind=read`，核对适配器类的实际 Python 源文件与 `source` 引用一致；按观察唯一目标 → 临动作前重验 probe → 调用一次 `read` → 回读身份 → 逐 A 评估 → 独占写入本 run 原始结果与六阶段回执执行。回调抛错时返回 `blocked/adapter_outcome_unknown_no_retry`，不自动重试；重复 run 也阻塞。两个互不依赖的可运行虚构示例源码在 `examples/synthetic_adapter_projects/catalog/adapter.py` 和 `examples/synthetic_adapter_projects/tasks/adapter.py`，验收见 `tests/test_adapter_trace.py`。这些例子读各自 TempDirectory 内的静态状态，而非网站或业务 API。

调用方 Python 回调不是沙箱，可能产生非预期副作用：该 SDK 只允许本地虚构项目，不能作为真实业务的读写授权或可信身份验证。`source` 哈希、阶段回执、断言状态也不是代码签名或审核人认证。浏览器真实执行仍由既有合成 Starter 单独展示，不能把这两个内存适配器称为 Web 产品回归。

## 信任边界与后续扩展

这是离线材料一致性门禁，不是执行器沙箱、源码真实性证明、业务 Oracle 审核、授权适配或正式报告晋升。只读 Adapter 仍须由调用方在实际执行前校验受控身份/组织/版本、唯一目标与来源权限；真实写入需另外的逐动作授权/恢复接口，不会因本合同中提供 `kind=write` 而被允许。媒体隐私与报告另走 `privacy-check` / `report-promotion-check`；后者当前不接受标准业务报告。要得到无法轻易绕开的团队链路，必须把接收器放到组织受保护 runner/报告入口，而不是要求 agent 自觉调用 CLI。
