# AI 使用说明

- **使用工具：** OpenAI Codex 桌面端（本次结对开发助手）与本地 shell。未使用 Cursor、Claude Code 或外部 API。
- **关键 prompt：** 用户提供的完整任务要求，核心包括“使用 FastAPI + SQLite、React + Vite 与 JSON 规则”“实现逐条审查、人工结论、持久化审计和报告导出”“编写并实际执行测试、前端构建及 /review → 修改 → /report 验证”。
- **AI 生成内容：** 项目骨架、规则引擎、接口与 SQLite 逻辑、React 页面、样例和文档均由 AI 根据上述要求编写。
- **人工修改内容：** 待候选人补充。
- **验证实际结果：** `python3 -m unittest discover -s tests -v`：14 项通过；`cd frontend && npm run build`：Vite 生产构建通过；运行 Uvicorn 后通过本地 HTTP 实际完成 `/review → PATCH → /report`，检查两个风险证据切片、审计旧值/新值和 Markdown/JSON 报告。使用 Codex 内置浏览器实际操作风险样例、证据定位、人工修改、导出请求和刷新恢复。
