# 多会话协作

每个会话开始时读取 `ai-test.json`、`.ai-test/workflow_state.json`、正式基线、资产登记表和最近运行回执。会话结束时更新阶段、已完成项、阻塞、下一步、文件哈希和负责人。

建议目录：

```text
.ai-test/
  workflow_state.json
  locks/
  receipts/
runs/<environment>/<run-id>/
assets/system/
assets/features/<feature-id>/
```

同一阶段只有一个写入者。其他会话可以读取和审核，但不能同时覆盖同一状态或报告。聊天和跨工具记忆用于检索背景，运行文件才是执行状态源。
