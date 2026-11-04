# 贡献指南 · workmate-agent-orchestrator

感谢你愿意参与这个项目。这个仓库的设计取向很明确：
**不做花哨的多智能体，优先保证可控、可审计、可人工接管。**

所以任何改动，都要先回答：**这个改动会不会让高风险动作绕过人工审批，或者让执行过程无法追溯？**

## 快速开始

```bash
git clone https://github.com/fenrir1111/workmate-agent-orchestrator.git
cd workmate-agent-orchestrator

uv venv .venv
uv pip install --python .venv/bin/python -r requirements.txt
uv pip install --python .venv/bin/python -e .

.venv/bin/python -m agent_orchestrator.demo    # 全链路 demo
.venv/bin/python -m pytest -q                   # 跑测试
.venv/bin/python -m uvicorn agent_orchestrator.main:app --port 8000
```

## 提交前必做

```bash
.venv/bin/python -m pytest -q --basetemp="$PWD/.pytest-tmp"   # 必须全绿
.venv/bin/python -m agent_orchestrator.demo                   # 必须退出码 0
```

CI 会自动跑上面两步，再加 FastAPI `/health` 与 Streamlit 控制台冒烟（Python 3.10 / 3.12 双版本）。

## 哪些改动受欢迎

| 类型 | 例子 |
|---|---|
| 流程模板 | 发票报销、报表生成、安全生产巡检等可复用流程 |
| 真实工具适配 | 把 handler 换成真实的 SQL / RAG / HTTP / 通知实现 |
| 编排能力 | 并行分支、状态外置（Redis）、定时触发、补偿事务 |
| 企业集成 | 对接 OA / 工单 / 审批系统的适配器 |
| 可观测性 | 指标上报、链路追踪、失败告警 |

## 哪些改动不会被接受

- **让高风险步骤可以跳过人工审批的**：审批节点必须是显式状态，不能被配置绕过
- **移除或弱化三级权限白名单的**：流程级 / 步骤级 / 工具级三层缺一不可
- **把执行日志变成可选项的**：审计留痕是核心能力，不是附加功能
- **引入隐式的自动重试语义**：重试次数与超时必须是显式配置，且要在执行记录里可见

## 代码约定

- **Python ≥3.10**，`from __future__ import annotations` 开头，类型标注齐全
- **行宽 100 以内**，命名 `snake_case`，公开 API 用 docstring 说明「为什么」
- **相对导入用绝对导入**：`streamlit_app.py` 会被 Streamlit 当独立脚本执行，
  相对导入会直接 `ImportError` —— 统一写成 `from agent_orchestrator.xxx import ...`。
  **包括 `if` 分支 / 函数里的延迟导入** —— 那类 bug 首屏正常，只有用户点到该分支才炸，
  AppTest 初始渲染和 HTTP 200 都看不出来。`tests/test_streamlit_app.py` 用 AST 全量扫描 +
  点击主按钮的交互冒烟，在 CI 里守住这条。
- **状态机改动必须配状态迁移测试**：每个状态、每个终态都要有断言
- **执行记录字段只增不改**：已发布的字段语义不能变，否则历史审计记录会失效

## 提交信息

```
feat: 新增安全生产巡检流程模板
fix: 修复人工审批通过后流程未从快照点恢复的问题
docs: 补充流程定义 YAML 字段说明
```

## Issue

提 Issue 时请尽量带上：

1. 复现步骤或最小样例
2. 期望行为 vs 实际行为
3. 运行环境（Python 版本、流程定义）
4. 相关执行日志片段（**注意脱敏**）

## 致谢

有效贡献会在 README 的致谢栏署名。

## License

贡献即视为同意以 MIT 协议授权你的改动。
