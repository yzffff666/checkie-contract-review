import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from .engine import review_text

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = Path(os.environ.get("CONTRACT_DB", ROOT / "data" / "reviews.sqlite3"))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
app = FastAPI(title="合同初审工具", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_methods=["*"], allow_headers=["*"])


def connect():
    db = sqlite3.connect(str(DB_PATH), timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def initialize():
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS reviews (
          id TEXT PRIMARY KEY, filename TEXT NOT NULL, source_text TEXT NOT NULL,
          reviewed_at TEXT NOT NULL, results_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS audit (
          id INTEGER PRIMARY KEY AUTOINCREMENT, review_id TEXT NOT NULL REFERENCES reviews(id),
          rule_id TEXT NOT NULL, actor TEXT NOT NULL, changed_at TEXT NOT NULL,
          old_value TEXT NOT NULL, new_value TEXT NOT NULL
        );
        """)


initialize()


class ReviewRequest(BaseModel):
    text: str
    filename: str = "contract.txt"


class PatchRequest(BaseModel):
    actor: str
    conclusion: str


class ReportRequest(BaseModel):
    review_id: str
    format: str


def fetch_review(db, review_id):
    row = db.execute("SELECT * FROM reviews WHERE id=?", (review_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="审查记录不存在")
    results = json.loads(row["results_json"])
    audit = [dict(r) for r in db.execute("SELECT review_id, rule_id, actor, changed_at, old_value, new_value FROM audit WHERE review_id=? ORDER BY id", (review_id,))]
    return {"review_id": row["id"], "filename": row["filename"], "text": row["source_text"], "reviewed_at": row["reviewed_at"], "results": results, "audit": audit, "offset_unit": "Unicode code point (Python string index); UI converts to UTF-16 indices for browser selection."}


@app.post("/review")
def create_review(payload: ReviewRequest):
    try:
        results = review_text(payload.text)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    review_id = str(uuid.uuid4())
    reviewed_at = datetime.now(timezone.utc).isoformat()
    with connect() as db:
        db.execute("INSERT INTO reviews VALUES (?, ?, ?, ?, ?)", (review_id, payload.filename or "contract.txt", payload.text, reviewed_at, json.dumps(results, ensure_ascii=False)))
    with connect() as db:
        return fetch_review(db, review_id)


@app.get("/reviews/{review_id}")
def get_review(review_id: str):
    with connect() as db:
        return fetch_review(db, review_id)


@app.patch("/reviews/{review_id}/rules/{rule_id}")
def update_rule(review_id: str, rule_id: str, payload: PatchRequest):
    allowed = {"通过", "风险", "不适用"}
    if payload.conclusion not in allowed:
        raise HTTPException(status_code=422, detail="结论须为通过、风险或不适用")
    actor = payload.actor.strip()
    if not actor:
        raise HTTPException(status_code=422, detail="审核人姓名不能为空")
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT results_json FROM reviews WHERE id=?", (review_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="审查记录不存在")
        results = json.loads(row["results_json"])
        target = next((result for result in results if result["rule_id"] == rule_id), None)
        if target is None:
            raise HTTPException(status_code=404, detail="规则不存在")
        old_value = target["conclusion"]
        if old_value != payload.conclusion:
            target["conclusion"] = payload.conclusion
            db.execute("UPDATE reviews SET results_json=? WHERE id=?", (json.dumps(results, ensure_ascii=False), review_id))
            db.execute("INSERT INTO audit(review_id, rule_id, actor, changed_at, old_value, new_value) VALUES (?, ?, ?, ?, ?, ?)", (review_id, rule_id, actor, datetime.now(timezone.utc).isoformat(), old_value, payload.conclusion))
    with connect() as db:
        data = fetch_review(db, review_id)
    return data


@app.post("/report")
def export_report(payload: ReportRequest):
    if payload.format not in {"markdown", "json"}:
        raise HTTPException(status_code=422, detail="format 须为 markdown 或 json")
    with connect() as db:
        data = fetch_review(db, payload.review_id)
    if payload.format == "json":
        body, media, suffix = json.dumps(data, ensure_ascii=False, indent=2), "application/json; charset=utf-8", "json"
    else:
        lines = ["# 合同审查报告", "", "- 文件名：" + data["filename"], "- 审查时间：" + data["reviewed_at"], "", "## 规则审查", ""]
        for item in data["results"]:
            lines.extend(["### " + item["rule_name"], "- 自动状态：" + item["automatic_status"], "- 最终结论：" + item["conclusion"], "- 判断原因：" + item["reason"], "- 证据：" + ("；".join("`" + e["text"].replace("`", "\\`") + "`（" + str(e["start"]) + "–" + str(e["end"]) + "）" for e in item["evidence"]) or "无"), ""])
        lines.extend(["## 人工审计记录", ""])
        if data["audit"]:
            lines.extend(["| 规则 | 审核人（自报） | 时间 | 原值 | 新值 |", "|---|---|---|---|---|"])
            for a in data["audit"]:
                lines.append("| " + " | ".join(a[k].replace("|", "\\|") for k in ("rule_id", "actor", "changed_at", "old_value", "new_value")) + " |")
        else:
            lines.append("无人工修改记录。")
        body, media, suffix = "\n".join(lines), "text/markdown; charset=utf-8", "md"
    filename = "review-" + data["review_id"] + "." + suffix
    return Response(content=body, media_type=media, headers={"Content-Disposition": "attachment; filename*=UTF-8''" + filename})
