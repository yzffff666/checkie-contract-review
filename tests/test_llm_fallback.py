import unittest

from backend.engine import review_text
from backend.llm_fallback import parse_assessments


def rule(rule_id, operator="keyword", **extra):
    return {"id": rule_id, "name": rule_id, "description": "检查" + rule_id,
            "operator": operator, "config": {"keywords": ["命中词"]},
            "on_match": "通过", "on_no_match": "需人工确认", "llm_fallback": True, **extra}


class LLMFallbackTests(unittest.TestCase):
    def test_fallback_only_receives_unmatched_opted_in_rules(self):
        seen = []
        rules = [rule("matched"), rule("missing"), rule("no_fallback", llm_fallback=False)]
        rules[1]["config"]["keywords"] = ["另一种词"]

        def fallback(text, candidates):
            seen.extend(item["id"] for item in candidates)
            return {}

        review_text("這里有命中词", rules=rules, llm_fallback=fallback)
        self.assertEqual(seen, ["missing"])

    def test_ai_suggestion_stays_manual_and_exact_quote_is_evidence(self):
        rules = [rule("payment")]
        results = review_text("经双方协商确定，付款期限为收到发票后30日内。", rules=rules,
                              llm_fallback=lambda text, candidates: {"payment": {
                                  "suggested_status": "通过", "reason": "明确说明付款期限",
                                  "evidence_quote": "收到发票后30日内"}})
        result = results[0]
        self.assertEqual(result["automatic_status"], "需人工确认")
        self.assertEqual(result["conclusion"], "需人工确认")
        self.assertEqual(result["llm_assessment"]["suggested_status"], "通过")
        self.assertTrue(result["llm_assessment"]["label"].startswith("AI 判断，需人工复核"))
        self.assertEqual(result["evidence"], [{"text": "收到发票后30日内", "start": 13, "end": 22}])

    def test_fabricated_quote_is_discarded(self):
        result = review_text("合同没有付款约定。", rules=[rule("payment")], llm_fallback=lambda *_: {
            "payment": {"suggested_status": "风险", "reason": "似乎没有付款期限",
                        "evidence_quote": "合同约定收到发票后付款"}})[0]
        self.assertEqual(result["evidence"], [])
        self.assertEqual(result["conclusion"], "需人工确认")

    def test_parse_assessments_rejects_unknown_ids_and_invalid_statuses(self):
        parsed = parse_assessments('{"results":['
            '{"rule_id":"r1","suggested_status":"风险","reason":"发现风险","evidence_quote":"原文证据"},'
            '{"rule_id":"other","suggested_status":"风险","reason":"x","evidence_quote":"原文证据"},'
            '{"rule_id":"r1","suggested_status":"自动通过","reason":"x","evidence_quote":"原文证据"}]}',
            [{"id": "r1"}], "原文证据位于本合同")
        self.assertEqual(parsed["r1"]["suggested_status"], "风险")
        self.assertEqual(set(parsed), {"r1"})


if __name__ == "__main__":
    unittest.main()
