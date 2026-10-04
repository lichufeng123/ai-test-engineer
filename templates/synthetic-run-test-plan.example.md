# 本机虚构测试计划：<RUN-ID>

目的：验证公开框架完整合成执行链，不检验任何产品行为或业务数据。模式 rapid，仅 local/synthetic、官方 counter Starter，macOS/Linux POSIX；真实业务页面/API、客户数据、外部通知和业务写入均不在范围。

Fixture FX-EXAMPLE-001 为当前浏览器内唯一计数器，初始 2。临时 Case TC-EXAMPLE-001 绑定原子断言 A-EXAMPLE-001：从独立 `2+1` 得到预期 3；点击一次后读取页面值。单一官方 Starter 源码和 Playwright JSON reporter 是执行材料，不能用 UI 值反推预期。

执行前：保存本计划至 `runs/<RUN-ID>/test-plan.v1.md`，确认环境画像 local/synthetic 与当前 build/角色示例相符、无同 ID 历史运行及 reporter；`synthetic-run-prepare` 创建临时 charter/短时环境观察/准备度/探针/日志/一次性 bundle。准备后尽快调用 `guarded-web-run`，避免 120 秒现场观察过期。只允许官方样板的单个内存按钮点击，不能用本命令作真实业务授权。

证据和停止：唯一 run reporter、逐断言附件、视频、技术报告与资产反馈；源码/计划/Oracle 漂移、Fixture 不唯一、浏览器失效、超过120秒无进展、reporter 缺失或异常退出立即阻塞，同 run 不自动重试。脚本一致仅为局部技术证据，媒体内容和隐私待人工复核；产品结论始终未评价。
