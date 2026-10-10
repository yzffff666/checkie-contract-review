# AI 使用说明

- **使用工具：** OpenAI Codex 桌面端与本地 shell；查阅了 DeepSeek 官方 API 文档。未实际调用 DeepSeek API，未使用用户粘贴的 API Key。
- **关键 prompt：** 用户提供的完整实现要求；后续追加“都做了吧”，据此增加 Docker Compose 和可选 LLM 语义兜底。
- **AI 生成内容：** 项目骨架、规则引擎、接口与 SQLite 逻辑、React 页面、测试、样例、Docker 配置及文档均由 AI 根据要求编写。
- **人工修改内容：** 待候选人补充。
- **验证实际结果：** `python3 -m unittest discover -s tests -v`：20 项通过；`cd frontend && npm run build`：Vite 构建通过；Compose YAML 解析及本机绑定/SQLite volume 检查通过；本机 HTTP 验证 `/capabilities` 与无 Key 的兜底降级。此前基础流程 `/review → PATCH → /report` 已实际运行验证。当前环境没有 Docker 客户端，未执行容器构建；没有使用有效新 API Key，未发送真实 DeepSeek 请求。
- **模型接口参考：** [DeepSeek 官方 Chat Completions 文档](https://api-docs.deepseek.com/api/create-chat-completion/)。
