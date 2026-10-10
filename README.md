# 合同初审工具

基于 FastAPI、SQLite、React 和 Vite 的本地合同初审演示项目。只接受 UTF-8 TXT 文本；规则使用 `backend/rules.json` 配置，默认只运行关键词和正则规则。

## 环境与启动

需要 Python 3.9+、Node.js 20+、npm。首次分别安装依赖：

```bash
python3 -m pip install -r requirements.txt
cd frontend && npm install
```

在项目根目录开两个终端：

```bash
python3 -m uvicorn backend.app:app --reload --port 8000
```

```bash
cd frontend && npm run dev
```

浏览器打开 <http://localhost:5173>。SQLite 数据库默认位于 `data/reviews.sqlite3`，也可用 `CONTRACT_DB` 指定路径。FastAPI 文档在 <http://localhost:8000/docs>。

## Docker 一键启动

需要 Docker Desktop（含 Compose）。在项目根目录运行：

```bash
docker compose up --build
```

浏览器打开 <http://localhost:8080>。SQLite 文件保存在 Compose 命名卷 `contract-data` 中。服务只绑定本机回环地址。停止运行用 `docker compose down`；删除持久化审查记录时再执行 `docker compose down -v`。

## 可选 DeepSeek 语义兜底

只有在页面勾选“启用 DeepSeek 语义兜底”后，未命中且在规则 JSON 中设置了 `"llm_fallback": true` 的规则才会请求模型。每次将整份合同文本和待判断的规则描述发送到 DeepSeek；请勿对未经授权外发的合同启用此选项。模型建议永远显示为“AI 判断，需人工复核”，最终结论仍须由审核人修改。证据只有在模型返回的引用与原文精确匹配时才会展示。

配置时先创建一个新的 API Key（不要使用已粘贴到聊天中的旧 Key），复制 `.env.example` 为 `.env`，将新 Key 放入 `DEEPSEEK_API_KEY`。`.env` 已加入 `.gitignore`；密钥不会写进前端、数据库、审计或报告。开发模式需在启动 FastAPI 前导出 `DEEPSEEK_API_KEY`；Docker Compose 会从 `.env` 读取。默认模型为 `deepseek-flash`，可通过 `DEEPSEEK_MODEL` 选择 `deepseek-v4-pro`。没有配置 Key 时，核心功能照常运行，LLM 兜底显示为不可用。

## 使用与样例

选择 UTF-8 `.txt` 文件或点内置样例，再点“开始审查”。页面展示逐条状态及精确证据，点击证据会定位并选中原文。填审核人姓名后可改最终结论，修改会由服务端写入 SQLite 审计记录。导出按钮生成 Markdown 或 JSON 报告，内容从数据库读取。

- `samples/all_pass.txt`：四项约定均明确，违约金为 20%。
- `samples/two_risks.txt`：同一条违约金规则中有 40% 和 50% 两个风险证据；这是**两处风险**，不是两条风险规则，另外三项均满足。

偏移为 Python 字符串索引的 Unicode 码点，左闭右开。浏览器定位时将码点偏移转换为 JavaScript UTF-16 代码单元，因此包含中文和 emoji 的合同也不会错位。证据文本由原文切片生成。

## 规则扩展

规则列表在 `backend/rules.json`。每条包含 `id`、`name`、`description`、`operator`（`keyword` 或 `regex`）、`config`、`on_match`、`on_no_match`。关键词配置例：`"config":{"keywords":["明确表述"]}`。正则配置例：`"config":{"pattern":"违约金\\D*(\\d+(?:\\.\\d+)?)%","capture_group":1,"evidence_group":0}`；可选 `compare` 支持 `gt/gte/lt/lte/eq` 与 `value`，数字满足条件时使用 `on_condition_true`，否则用 `on_condition_false`。没有命中使用 `on_no_match`，默认建议需人工确认。保存 JSON 后下一次审查即生效，无需改代码。规则 id 应保持唯一。

## 测试

```bash
python3 -m unittest discover -s tests -v
cd frontend && npm run build
```

## API

- `POST /review`：JSON `{ "text": "...", "filename": "contract.txt", "use_llm": false }`，创建并保存审查；`use_llm` 默认关闭。
- `GET /capabilities`：返回 LLM 是否已配置和模型名称，不返回 API Key。
- `GET /reviews/{review_id}`：读取原文、最新结论和审计。
- `PATCH /reviews/{review_id}/rules/{rule_id}`：JSON `{ "actor": "审核人姓名", "conclusion": "风险" }`；结论接受通过/风险/不适用。旧值由服务端读取，同值提交不会写审计。
- `POST /report`：JSON `{ "review_id": "...", "format": "markdown" }` 或 `json`，以附件下载。

## 限制

这是规则匹配演示，不构成法律意见；表达方式复杂或规则未命中的条款需人工判断。姓名为审核人在页面自行填写的自报身份，不是登录认证。暂不支持 PDF/Word、扫描件 OCR 或多用户权限。LLM 兜底需要联网、有效的 DeepSeek API Key，并可能产生费用。
