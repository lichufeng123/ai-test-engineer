# 规划并复核自动化测试准备度

## 需求审核后

1. 读取已审核需求、业务拓扑、角色权限、平台地图和系统探索资产。
2. 梳理可自动化范围、人工专属范围、候选业务流程、环境和平台。
3. 按用途列出账号角色，不记录账号、密码或登录态。
4. 按稳定标识列出测试数据，说明生成方式、环境复用方式、清理策略和关联用例。
5. App、桌面或硬件在环测试声明执行目标、执行器、真机/模拟器类型和必需能力；外设单独声明人工准备、自动状态校验、租约和清理。
6. 为核心结论安排操作前、关键操作、结果截图和连续录屏。
7. 生成 `automation_readiness_plan.json`。此时没有正式用例ID的，先写候选用例类别；用例审核后绑定稳定用例ID并重新冻结哈希。

```bash
ai-test readiness-plan \
  --input ./runs/latest/automation-readiness-source.json \
  --output ./runs/latest/automation_readiness_plan.json
```

## 执行前复核

1. 对照当前版本和目标环境，重新确认功能、范围、用例基线及排除项。
2. 只确认账号角色是否可用，凭据从安全运行配置读取。
3. 检查每项fixture是否已经存在或能由数据工厂生成。
4. 对移动执行目标运行doctor和capabilities检查；只把能力满足且已获得独占租约的目标加入 `available_execution_target_ids`。
5. 对耳机、工牌等硬件确认人工预置，并通过App或服务端状态回读后加入 `ready_hardware_fixture_ids`。
6. 生成 `pre_execution_confirmation.json`，引用准备计划哈希。
7. 运行准备度门禁，把用例拆成已就绪、缺前置阻塞和明确排除三组。

```bash
ai-test readiness-check \
  --plan ./runs/latest/automation_readiness_plan.json \
  --confirmation ./runs/latest/pre_execution_confirmation.json \
  --output ./runs/latest/execution_readiness_receipt.json
```

`passed_with_case_blocks` 允许执行已就绪用例。缺账号角色、数据、执行目标或硬件的用例登记到 `missing_prerequisites.json` 后直接跳过；相同前置指纹未变化前不得重复进入UI或接口尝试。产品补充数据、账号角色、环境、手机或外设后重新生成确认文件，只有前置指纹发生变化的用例才恢复执行。
