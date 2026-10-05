# 同事从 GitLab 克隆与安装

从公司 GitLab 的 `lucifer/ai-test-engineer` 分支取得框架；该分支与公司仓库原有的 `release` 历史无共同祖先，不要向原 `release` 发合并请求。安装检查仅证明框架可用，不代表 SIT 业务已测试或浏览器已登录。

在获仓库读取权限、Python ≥3.9 且构建依赖来源获团队批准的机器上执行（macOS/Linux）：

```bash
git clone --branch lucifer/ai-test-engineer --single-branch '<GITLAB_REPO_SSH_URL>' ai-test-engineer
cd ai-test-engineer
git rev-parse --short HEAD
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/python - <<'PY'
import json
import ai_test_framework
expected = json.load(open('framework-manifest.json'))['framework_version']
assert ai_test_framework.__version__ == expected, (ai_test_framework.__version__, expected)
print('framework_version:', expected)
PY
.venv/bin/ai-test docs-check --root .
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -q
.venv/bin/ai-test init ../ai-test-catalog-demo --name fictional-catalog --system-id SYNTH-CATALOG --platform api
.venv/bin/ai-test doctor --root ../ai-test-catalog-demo --framework-root .
```

示例 `init` 仅在新目录执行，不要覆盖已有项目。版本应等于 `framework-manifest.json`，`docs-check` 和纯 API 示例项目 `doctor` 为 `passed`。`doctor` 不读取账号或密码，不证明产品网站可登录；虚构适配器测试也不代表实际业务通过。

开始 SIT 试点前，先从获审核的账号/Fixture 索引选定非敏感账号别名、角色、组织与登录方式；有匹配登录态则复用，没有唯一账号时在进入登录页前一次问清。密码、验证码只通过安全运行时或已成功交接的浏览器空间提供，不能发到聊天或仓库。工具报告 `UI not available` 时并未交接成功，不要要求用户在不可见任务空间登录。

如 pip 无法从公网取得构建依赖，改用团队批准的镜像或与该 Git 提交对应的已审核 wheel。Windows 使用 `.venv\\Scripts\\python.exe` 和 `.venv\\Scripts\\ai-test.exe`，并以实际 Windows CI/设备回执判断可用性。真实浏览器执行还需安装锁定的 Playwright 依赖及浏览器；从 GitHub 取得的历史预览不属于当前 GitLab 发布证据。
