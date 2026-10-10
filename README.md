# 合同初审工具

基于 FastAPI、SQLite、React 和 Vite 的本地合同初审演示项目。只接受 UTF-8 TXT 文本；规则使用 `backend/rules.json` 配置，不调用 LLM 或外部 API。

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

- `POST /review`：JSON `{ "text": "...", "filename": "contract.txt" }`，创建并保存审查。
- `GET /reviews/{review_id}`：读取原文、最新结论和审计。
- `PATCH /reviews/{review_id}/rules/{rule_id}`：JSON `{ "actor": "审核人姓名", "conclusion": "风险" }`；结论接受通过/风险/不适用。旧值由服务端读取，同值提交不会写审计。
- `POST /report`：JSON `{ "review_id": "...", "format": "markdown" }` 或 `json`，以附件下载。

## 限制

这是规则匹配演示，不构成法律意见；表达方式复杂或规则未命中的条款需人工判断。姓名为审核人在页面自行填写的自报身份，不是登录认证。暂不支持 PDF/Word、扫描件 OCR、多用户权限或 LLM 语义判断。
