# Playwright Adapter

Playwright负责Web稳定回归、接口监听、下载、截图、视频和Trace。执行前使用框架探索计划和资产门禁；结果使用稳定Case-ID写入运行目录。

浏览器默认正常视口1920×1080。系统弹窗通过 `transient_ui_catalog` 处理。坐标点击只允许作为探索或临时恢复方式。
