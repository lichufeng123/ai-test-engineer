# Playwright Adapter

Playwright Test是Web稳定回归、批量执行和CI的唯一正式执行器。它负责业务断言、接口监听、下载、截图、视频和Trace；结果使用稳定Case ID与已审核基线哈希写入运行目录。

新需求优先由Ego Lite执行语义/视觉探索并发现稳定Test ID、Role、Label、DOM和等待条件；Playwright MCP只在需要时辅助生成或复核定位器，不是编写Playwright脚本的依赖。失败诊断使用Chrome DevTools MCP；Stagehand只生成定位器、等待条件和已知瞬态弹窗的修复候选。所有候选最终必须由Playwright Test执行单用例验证和影响回归。

浏览器默认正常视口1920×1080。系统弹窗通过 `transient_ui_catalog` 处理。坐标点击只允许作为探索或临时恢复方式，不进入稳定回归脚本。

禁止任何AI工具修改正式预期、业务规则、权限边界、Case ID或基线哈希，也不得通过删除断言、静默跳过或盲目重试写操作使测试通过。执行前使用框架探索计划、`web-executor-check`、准备度和执行门禁。
