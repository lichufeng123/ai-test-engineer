# 同事从 Git 克隆与安装（0.13.0a1 公开预览分支）

在获得仓库读取权限且机器有 Python ≥3.9、pip 和批准的 Python 构建依赖源后，使用下面的独立预览分支；不要误以为直接 clone 默认分支就有同一版本。真实远端提交与 CI 状态应先由发布负责人核对。

```bash
git clone --branch release/ai-test-engineer-0.13.0a1 --single-branch git@github.com:lichufeng123/ai-test-engineer.git
cd ai-test-engineer
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/python -c 'import ai_test_framework; print(ai_test_framework.__version__)'
.venv/bin/ai-test docs-check --root .
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -q
.venv/bin/ai-test init ../ai-test-catalog-demo --name fictional-catalog --system-id SYNTH-CATALOG --platform api
.venv/bin/ai-test doctor --root ../ai-test-catalog-demo --framework-root .
```

预期：版本 `0.13.0a1`，`docs-check` 和纯 API 项目 `doctor` 为 `passed`，本分支公开单测全部通过。以上 `init` 仅在全新目录执行（命令不会替你保护一个已有同名目录）；不填写账号/密码，不连接真实业务系统。两个独立虚构适配器的实际本地只读回调及错误目标反例位于 `examples/synthetic_adapter_projects/`、`tests/test_adapter_trace.py`，验证结果最多为 `review_required`，不代表产品通过。

如所在环境不允许 pip 从公网获取构建依赖，使用团队批准的包镜像，或向发布负责人领取与本分支 SHA 匹配的已审核 wheel；不可因安装失败跳过校验。Windows PowerShell 把 `.venv/bin/python`、`.venv/bin/ai-test` 分别替换为 `.venv\\Scripts\\python.exe`、`.venv\\Scripts\\ai-test.exe`，并等远端 Windows CI 真正通过后再宣称跨系统可用。需要真实浏览器执行时还须单独按锁文件安装 Playwright 与浏览器，当前 `doctor` 不会凭静态文件证明浏览器可用。

这条预览分支不是正式业务报告/写入入口，也不是默认分支上的稳定版本。新版本或正式 Release 以对应 tag、签收与远端 required checks 为准，禁止把本地材料当远端结果。
