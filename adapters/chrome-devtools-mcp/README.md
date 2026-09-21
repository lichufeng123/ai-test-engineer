# Chrome DevTools MCP Adapter

Chrome DevTools MCP 用于Web失败诊断、网络、Console与性能分析，不独立判定正式业务用例通过。

## 职责

- 获取当前动作时间窗内的网络请求、状态、脱敏响应摘要和关联ID。
- 检查Console错误、资源加载、渲染与性能Trace。
- 在用户授权后连接现有Chrome会话，复核人工现场或Playwright失败现场。
- 为候选问题区分产品、环境、数据、缓存与自动化脚本原因。

## 内部环境安全配置

- 固定精确版本并使用独立测试Profile。
- 开启敏感请求头脱敏，例如 `--redact-network-headers`。
- 内部页面性能分析关闭CrUX，例如 `--no-performance-crux`。
- 能配置URL allowlist时仅开放被测环境及必要静态资源域名。
- 不把Authorization、Cookie、Token、密码、完整手机号或私有响应载荷写入普通日志。

示意配置：

```json
{
  "command": "npx",
  "args": [
    "chrome-devtools-mcp@<exact-version>",
    "--redact-network-headers",
    "--no-performance-crux"
  ]
}
```

连接现有浏览器必须由用户明确允许；远程调试端口只在隔离Profile中短时开放，执行结束立即关闭。

## 输出资产

- 脱敏网络与Console诊断回执。
- 性能Trace结论与采集限制。
- 候选根因及证据，不直接改写正式预期。
- 需要Playwright复现或回归的精确范围。
