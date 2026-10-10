import json
import re
from pathlib import Path

RULES_PATH = Path(__file__).with_name("rules.json")


def load_rules():
    return json.loads(RULES_PATH.read_text(encoding="utf-8"))


def review_text(text, rules=None, llm_fallback=None):
    if not isinstance(text, str) or not text.strip():
        raise ValueError("合同文本不能为空")
    rules = load_rules() if rules is None else rules
    output = []
    for rule in rules:
        operator, config = rule["operator"], rule["config"]
        hits = []
        if operator == "keyword":
            for word in config["keywords"]:
                pos = 0
                while True:
                    start = text.find(word, pos)
                    if start < 0:
                        break
                    hits.append((start, start + len(word)))
                    pos = start + max(1, len(word))
        elif operator == "regex":
            for match in re.finditer(config["pattern"], text):
                group = int(config.get("evidence_group", 0))
                start, end = match.span(group)
                if start >= 0:
                    hits.append((start, end))
        else:
            raise ValueError("不支持的规则算子: " + str(operator))
        # Preserve match order and remove exact duplicate spans.
        hits = list(dict.fromkeys(sorted(hits)))
        status = rule.get("on_match", "通过") if hits else rule.get("on_no_match", "需人工确认")
        reasons = []
        if hits and operator == "regex" and "compare" in config:
            compare = config["compare"]
            group = int(config.get("capture_group", 0))
            values = []
            for match in re.finditer(config["pattern"], text):
                try:
                    values.append(float(match.group(group)))
                except (ValueError, IndexError):
                    continue
            op, threshold = compare["operator"], float(compare["value"])
            compare_fn = {"gt": lambda n: n > threshold, "gte": lambda n: n >= threshold, "lt": lambda n: n < threshold, "lte": lambda n: n <= threshold, "eq": lambda n: n == threshold}.get(op)
            if compare_fn is None:
                raise ValueError("不支持的数值比较操作")
            risky = any(compare_fn(value) for value in values)
            status = rule.get("on_condition_true" if risky else "on_condition_false", status)
            reasons.append("识别数值：" + "、".join(str(int(v)) if v.is_integer() else str(v) for v in values) + "%；阈值条件 " + op + " " + str(threshold) + (" 成立" if risky else "不成立"))
        evidences = [{"text": text[start:end], "start": start, "end": end} for start, end in hits]
        reason = "; ".join(reasons) if reasons else ("发现配置的匹配内容" if hits else "未找到明确约定，建议人工确认")
        output.append({"rule_id": rule["id"], "rule_name": rule["name"], "description": rule["description"], "automatic_status": status, "conclusion": status, "reason": reason, "evidence": evidences})
    if llm_fallback is not None:
        candidates = [rule for rule, result in zip(rules, output)
                      if rule.get("llm_fallback") is True and not result["evidence"]]
        if candidates:
            try:
                assessments = llm_fallback(text, candidates)
                if not isinstance(assessments, dict):
                    raise ValueError("invalid LLM result")
                for rule, result in zip(rules, output):
                    if rule not in candidates:
                        continue
                    assessment = assessments.get(rule["id"])
                    if not isinstance(assessment, dict) or assessment.get("suggested_status") not in {"通过", "风险", "需人工确认"}:
                        continue
                    quote = assessment.get("evidence_quote", "")
                    if not isinstance(quote, str) or quote not in text:
                        quote = ""
                    evidence = []
                    if quote:
                        offset = 0
                        while True:
                            start = text.find(quote, offset)
                            if start < 0:
                                break
                            evidence.append({"text": text[start:start + len(quote)], "start": start, "end": start + len(quote)})
                            offset = start + max(1, len(quote))
                    result["automatic_status"] = "需人工确认"
                    result["conclusion"] = "需人工确认"
                    result["llm_assessment"] = {
                        "label": "AI 判断，需人工复核",
                        "suggested_status": assessment["suggested_status"],
                        "reason": assessment.get("reason", ""),
                    }
                    result["evidence"] = evidence
                    result["reason"] = "AI 判断建议“" + assessment["suggested_status"] + "”，需人工复核；" + assessment.get("reason", "")
                    if not evidence:
                        result["reason"] += "；没有与原文精确匹配的证据片段"
            except Exception:
                for rule, result in zip(rules, output):
                    if rule in candidates:
                        result["llm_error"] = "AI 兜底暂不可用，仍需人工确认"
                        result["reason"] += "；AI 兜底暂不可用，仍需人工确认"
    return output
