# 测试发现缺陷后的可选提单入口

适用于项目已配置 `defect-cli-v1` 本地适配器、且本轮授权包含向缺陷跟踪器提单的场景。配置路径按 `--adapter`、`AI_TEST_DEFECT_ADAPTER`、项目 `.ai-test/defect-adapter.json`、用户 `~/.config/ai-test/defect-adapter.json` 顺序发现；没有配置时保留缺陷草稿并记录提单阻塞，继续其余可执行测试。

命令尚未全局安装时，从框架根目录使用 `./bin/ai-test`，或调用该文件的绝对路径；不要在业务仓库复制框架脚本。

## 测试开始时

先读取已有版本运行文件和回执。新测试范围查询候选版本，展示给用户并等明确选择；不得自动选“最新”。选定后本轮复用，与当前 execution run_id 绑定：

```bash
ai-test defect-versions
ai-test defect-select --run <private-run/defect-run.json> \
  --run-id <current-execution-run-id> --scope <approved-scope> \
  --build <chosen-id> --confirmed-by <actual-reviewer>
```

团队人员路由、候选版本规则、登录与图片/视频上传由项目的私有适配器负责；公开框架不写死业务账号、内部地址或人员分工。

## 问题定性后

生成草稿前，Agent必须实际查看用户截图或本轮证据，主动提取可见的环境/分区、门店名称与ID、会员姓名与手机号、员工名称与ID、业务记录ID、发生时间、筛选条件及错误原文，不把这些信息全部留给用户另写“附带信息”。逐项区分截图可见、用户补充、授权查询及待补充；保留脱敏手机号原样，禁止补全隐藏数字、根据名称猜ID或把历史截图身份套到本次。多图核对是否同一对象；关键身份冲突先澄清，非关键缺项标为待补充并继续已授权提单。仅在受控私有运行目录和获授权的缺陷单保存真实定位信息。

提单前的图片判定顺序固定为：先读取本功能当前适用、可访问的 Demo HTML／原型及其版本来源，结合用户描述逐图对照，判断哪些为预期效果、哪些为实际运行现场。图片用途不能仅凭外观、上传顺序或相似布局猜测；Demo 示例数据不能当作现场事实。已有足够材料时由 Agent 完成判定，不要求用户每次标注。若 Demo／原型不可用、版本冲突或逐图用途仍无法确认，先检查本轮已有材料；仍不确定再向用户提出最小澄清问题，确认前不以猜测用途提交。没有 Demo 的非视觉问题不因此额外阻塞，使用当前已确认的需求或用户明确预期作为依据。新提单图片使用带 role（actual/expected）与 source 的结构化对象，不再主动生成只含路径的旧格式；旧格式仅用于历史兼容。提交后核验图片实际内容与紧邻的用途、来源标题一致。

每张图片必须独立识别用途与来源：实际运行结果、预期效果（原型/Demo HTML/设计稿）或用途未确认；不能根据上传顺序猜用途，也不能把原型列入“现场截图”或作为已复现证据。实际图标为“实际结果截图”，原型标为“预期效果参考（非实际运行截图）”，在图片紧邻位置显示来源。无法确定时保留中性标注，若影响缺陷判断则先澄清。提交后不仅核验图片内容可加载，还核验逐图标题/用途/来源与输入一致；原型中的示例分数与业务对象不能用于推断实际评分错误。

识图和业务判断由调用Agent完成，CLI只校验和提交结构化输入，不具备独立OCR或根据图片自动确认产品缺陷的能力。私有适配器中的`context`/`environment`及说明应承接已提取信息；来源记录格式由项目定义。用户已经明确指定有效版本、负责人时使用其本次选择，不重复追问。

只有已确认为缺陷、且预期有独立Oracle与直接证据时才调用。输入JSON使用 `source=automation`、稳定 `id`、`triage_file`、唯一 `candidate_id`；triage与版本文件、执行日志必须属于同一run_id，目标候选为 `confirmed_defect`。具体需求/规则/正式Case或临时probe字段遵守对应模式及适配器契约，不得伪造正式基线来绕过门禁。当前伊智私有适配器的自动提交仍要求标准执行确认文件；快速缺陷缺少该前置时只保留提单草稿/阻塞并进入标准跟进，不倒推快速测试无效，也不阻塞其余已授权探针。

```bash
ai-test defect-draft --input <private-run/issue.json> --run <private-run/defect-run.json>
ai-test defect-submit --execute --input <private-run/issue.json> \
  --run <private-run/defect-run.json> --output <private-run/issue-receipt.json>
```

`--execute` 记录本轮已有的提单授权，不因每次调用重复要求人工确认。用户只授权测试、未授权提单时生成草稿；用户明确授权本轮已确认缺陷自动提交、且版本已选择时，可持续调用。

## 回读、报告与恢复

- 图片放重现步骤正文，视频放附件；确认正文每张图实际加载，并绕过浏览器缓存重新取得非空图片内容，附件存在/内容核验、标题/版本/指派正确。报告人自身加载成功不能代替接收人访问验证。
- 退出码0且回执 `status=verified` 才标为完整提交；将稳定Case/probe、issue ID、Bug ID及私有回执引用回填本轮报告/工作项。Bug提单成功不代表产品用例通过，`product_verdict=not_evaluated`。
- `needs_owner_confirmation=true` 时保留默认负责人并询问用户，不猜责任。
- 验证失败或未知提交态保留原run、原issue ID和私有适配器回执，恢复同一Bug；禁止换ID或盲目重发创建。
- 只读复核可用 `ai-test defect-verify --input ... --run ...`。未知创建状态经只读确认具体BugID后，使用 `defect-submit --execute ... --resume-bug-id <confirmed-id>`。
- 不将凭据、内部URL、真实截图和个人/顾客数据提交公开仓库。运行回执和媒体留在项目受控私有运行目录；公开报告只引用脱敏稳定编号。
