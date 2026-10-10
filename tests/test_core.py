import json
import tempfile
import unittest
from pathlib import Path

from backend import engine
from backend.engine import review_text


ROOT = Path(__file__).resolve().parents[1]


class ReviewEngineTests(unittest.TestCase):
    def result(self, name):
        text = (ROOT / "samples" / name).read_text(encoding="utf-8")
        return text, {r["rule_id"]: r for r in review_text(text)}

    def test_complete_sample_passes_all_four_rules(self):
        text, result = self.result("all_pass.txt")
        self.assertEqual(len(result), 4)
        self.assertTrue(all(r["automatic_status"] == "通过" for r in result.values()))
        self.assertTrue(all(text[e["start"]:e["end"]] == e["text"] for r in result.values() for e in r["evidence"]))

    def test_two_penalty_breaches_are_both_evidenced(self):
        text, result = self.result("two_risks.txt")
        penalty = result["penalty_ratio"]
        self.assertEqual(penalty["automatic_status"], "风险")
        self.assertEqual(len(penalty["evidence"]), 2)
        self.assertTrue(all(text[e["start"]:e["end"]] == e["text"] for e in penalty["evidence"]))

    def test_threshold_is_strictly_greater_than_30(self):
        self.assertEqual(review_text("违约金为30%", rules=self.one_penalty())[0]["automatic_status"], "通过")
        self.assertEqual(review_text("违约金为30.1%", rules=self.one_penalty())[0]["automatic_status"], "风险")

    def test_unrelated_percentages_do_not_trigger_penalty(self):
        result = review_text("付款金额为合同总价的40%", rules=self.one_penalty())[0]
        self.assertNotEqual(result["automatic_status"], "风险")

    def test_payment_percentage_near_penalty_mention_is_not_a_penalty_ratio(self):
        result = review_text("违约金为1000元，付款金额按合同总价的40%支付", rules=self.one_penalty())[0]
        self.assertNotEqual(result["automatic_status"], "风险")

    def test_evidence_slices_stay_exact_with_emoji_and_chinese(self):
        text = "😀中文违约金为31%"
        for result in review_text(text, rules=self.one_penalty()):
            for evidence in result["evidence"]:
                self.assertEqual(text[evidence["start"]:evidence["end"]], evidence["text"])

    def test_all_two_risks_sample_evidence_is_an_exact_source_slice(self):
        text, results = self.result("two_risks.txt")
        self.assertTrue(all(text[e["start"]:e["end"]] == e["text"] for r in results.values() for e in r["evidence"]))

    def test_missing_key_terms_need_manual_review(self):
        results = {r["rule_id"]: r for r in review_text("本合同自双方签署后生效。")}
        self.assertEqual(results["ip_ownership"]["automatic_status"], "需人工确认")
        self.assertEqual(results["payment_deadline"]["automatic_status"], "需人工确认")
        self.assertEqual(results["confidentiality"]["automatic_status"], "需人工确认")

    def test_rules_are_loaded_from_json_and_new_rule_runs_without_code_change(self):
        rules = json.loads((ROOT / "backend" / "rules.json").read_text(encoding="utf-8"))
        rules.append({"id":"new_phrase", "name":"新规则", "description":"扩展验证", "operator":"keyword", "config":{"keywords":["新增条款"]}, "on_match":"通过", "on_no_match":"需人工确认"})
        with tempfile.TemporaryDirectory() as temp:
            config_path = Path(temp) / "rules.json"
            config_path.write_text(json.dumps(rules, ensure_ascii=False), encoding="utf-8")
            original_path = engine.RULES_PATH
            try:
                engine.RULES_PATH = config_path
                results = review_text("新增条款有效")
            finally:
                engine.RULES_PATH = original_path
        self.assertEqual(results[-1]["automatic_status"], "通过")

    def test_empty_text_rejected(self):
        with self.assertRaises(ValueError):
            review_text("  ")

    @staticmethod
    def one_penalty():
        rules = json.loads((ROOT / "backend" / "rules.json").read_text(encoding="utf-8"))
        return [rules[0]]


if __name__ == "__main__":
    unittest.main()
