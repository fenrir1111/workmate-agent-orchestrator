# Changelog

## 0.1.0
- 初版：可视化流程画布（JSON 定义）、工具注册中心、流/步骤/工具三级角色白名单。
- 状态机驱动执行：失败重试（max_attempts/backoff）、超时控制、条件分支（condition 门）。
- 人工介入（HITL）：`requires_approval` 节点挂起为 `WAITING_APPROVAL`，支持 `approve`/`reject`。
- 全链路执行日志、任务快照（`snapshot`/`restore`，可跨进程恢复）、流级 SLA 判定。
- Agent 方案包导出（`export-plan`，JSON / Markdown），可直接交付 POC。
- FastAPI 服务 + Streamlit 可视化后台 + 内置确定性工具（离线可跑、可单测）。
- examples 提供 `enterprise-rag-gateway`、`semantic-sql-guard` 的 HTTP 工具适配器。
