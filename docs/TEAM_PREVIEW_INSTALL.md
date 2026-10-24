# 0.13.0a1 团队预览包：离线安装与复核

该包是本地构建的公开框架预览候选，不是已推送的 Git 版本、远端 CI 结果或正式业务验收。只包含显式列出的公开源码、文档、两个虚构只读适配器和同版本 wheel；无运行日志、私有账号或业务资料。

1. 从可信渠道取得版本为 `0.13.0a1` 的预览 ZIP，对比随交付记录给出的 ZIP SHA-256，解压到一个新目录。查看 `SHA256SUMS.json`，逐项复核 `framework/` 与 `wheel/` 文件 SHA-256；不要从聊天/仓库填写密码。
2. macOS/Linux（Python ≥3.9，目标机须有 `venv` 和 `pip`）：

```bash
unzip /path/to/preview-kit.zip -d ai-test-preview
cd ai-test-preview
python3 -m venv .venv
.venv/bin/python -m pip install --no-index --no-deps wheel/ai_test_engineer-0.13.0a1-py3-none-any.whl
.venv/bin/python -c 'import ai_test_framework; print(ai_test_framework.__version__, ai_test_framework.__file__)'
.venv/bin/ai-test docs-check --root framework
.venv/bin/python -m unittest discover -s framework/tests -p test_adapter_trace.py -q
.venv/bin/python -m unittest discover -s framework/tests -p 'test_*.py' -q
```

`docs-check` 应为 `passed/0.13.0a1`；适配合同测试含两个互不相关的虚构项目、实际调用本地只读 Python 适配器及错误目标/漂移/重复动作反例。测试中的断言由虚构本地状态给出，不代表产品通过。若从 0.12.1 升级，请在独立虚拟环境先安装预览包并核对版本及路径，不覆盖已有团队环境；保留原 wheel 与环境供回滚。Windows 需单独验收，不要据此声称通过。

`framework/` 为交接与源码审查材料，Python 命令实际来自独立安装的 wheel；若在 `framework/` 内以源码启动测试，Python 可能优先导入本地 `src/`，因此必须额外在目录外运行上述 `-c` 核对 site-packages 路径。公开浏览器样板需要另外安装锁定的 Node/Playwright 依赖与浏览器，离线基础检查不等于真实浏览器已就绪。

不运行真实业务环境，不写入任何产品系统；正式业务适配器、来源授信、动作时授权、媒体审核与受保护报告发布尚未接线。若要推送 Git、创建 Release、给同事发送文件或启用远端 CI，须由仓库/发布负责人批准并提供真实回执，不能用本地 SHA 或离线测试替代。
