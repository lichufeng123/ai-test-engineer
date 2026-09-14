# Playbooks

Playbook是跨 Agent、跨工具的操作说明，不依赖任何特定 AI 客户端的技能机制。执行顺序由 `docs/FRAMEWORK.md` 定义。

- `system-discovery`：首次或手动系统全局探索。
- `feature-discovery`：目标功能深度探索。
- `modeling-business-flows`：从系统地图推导上下游，评审业务流程并校验端到端用例覆盖。
- `building-test-data`：声明式测试数据生成。
- `planning-automation-readiness`：需求后提前规划自动化范围、账号角色和数据，并在执行前复核。
- `running-regression`：SIT、预发布和正式环境回归。
- `repairing-test-reports`：截图、视频和团队报告修复。
