# 本地测试知识注册中心

本目录是私有测试资产仓库的本地、可版本化知识入口。跨会话检索工具只用于召回和定位；正式工作必须读取本目录登记的规则文件，不能只依赖聊天或记忆摘要。

> 这是 `ai-test private-scaffold` 生成的占位骨架。请用真实、已审核的业务知识替换示例条目，并在每次修改后运行 `refresh` 与 `validate`。

## 当前边界

- 当前模式：`local_only`。
- 不连接、不读取、不写入任何外部知识库。
- 正式业务事实仍以产品经理最新明确决定、已审核需求、已审核业务断言和现有正式用例基线为准。
- 本目录保存本地规则镜像、测试方法、遗漏风险和执行经验入口，不创建第二套正式用例基线。
- 页面现象、接口返回、AI 推断和单次执行经验不能自动升级为正式业务规则。

## 知识分层

1. `system/`：系统生态、角色、权限和跨模块关系。
2. `modules/`：各业务模块的拓扑、已审核规则索引和测试模型。
3. `test-risks/`：缺陷、漏测、误判和用户纠正形成的可复用测试设计规则。
4. `learning-inbox/`：执行中新发现但尚未审核的候选知识。
5. `manifest.json`：所有受控文件的路径、适用范围、加载阶段和 SHA-256。

## 新任务强制加载

先校验注册中心：

```bash
python3 scripts/knowledge_registry.py validate
```

再按功能和阶段获取必读文件：

```bash
python3 scripts/knowledge_registry.py load \
  --feature example-module \
  --stage execution \
  --platform web \
  --role store-account
```

输出只是一组必读路径和元数据。Agent 必须实际读取文件，不能把"路由命中"当成"已理解规则"。

## 状态约定

- `reviewed`：已有审核需求、业务断言或产品明确决定支持。
- `approved_test_method`：已确认的测试设计方法，不定义产品预期。
- `pending_review`：待审核候选，不能进入正式预期，也不会被 `load` 返回。
- `conflict_open`：存在新旧口径冲突，正式用例变更前必须处理。
- `deprecated`：已被新规则替代，仅保留追溯。

## 维护要求

修改知识文件后执行：

```bash
python3 scripts/knowledge_registry.py refresh
python3 scripts/knowledge_registry.py validate
```

规则文件不得包含账号、密码、Cookie、Token、私有认证参数、客户明细、完整手机号或一次性运行标识。
