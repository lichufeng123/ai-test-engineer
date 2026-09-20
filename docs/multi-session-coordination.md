# 多会话协作

默认采用“一需求一任务”。用户只需说“接手需求 REQ-XXX”；Agent 先运行 `ai-test work-item-show --root . --requirement-id REQ-XXX`，再按返回顺序读取需求清单、独立状态、交接摘要、决策和资产链接。会话结束时更新阶段、已完成项、阻塞、下一步、正式基线和负责人。

建议目录：

```text
.ai-test/
  work-items/
    index.json
    <requirement-id>/
      manifest.json
      workflow-state.json
      handoff.json
      decisions.md
      asset-links.json
  locks/
  receipts/
runs/<environment>/<run-id>/
assets/system/
assets/features/<feature-id>/
```

每个需求只写自己的状态文件，不再共享根级 `.ai-test/workflow_state.json`。同一需求、同一阶段只有一个写入者；其他会话可以读取和审核，但不能同时覆盖同一状态或报告。聊天和跨工具记忆用于检索背景，运行文件才是执行状态源。

完整的人类使用说明见 [`ONE_REQUIREMENT_ONE_CONVERSATION.zh-CN.md`](ONE_REQUIREMENT_ONE_CONVERSATION.zh-CN.md)。
