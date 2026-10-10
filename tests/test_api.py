import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from backend import app as api


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original_db = api.DB_PATH
        api.DB_PATH = Path(self.tmp.name) / "test.sqlite3"
        api.initialize()
        self.review = api.create_review(api.ReviewRequest(text="违约金为20%。知识产权归甲方所有。收到发票后30日内付款。承担保密义务。", filename="契约.txt"))

    def tearDown(self):
        api.DB_PATH = self.original_db
        self.tmp.cleanup()

    def test_patch_persists_values_and_audit_with_server_time(self):
        result = api.update_rule(self.review["review_id"], "penalty_ratio", api.PatchRequest(actor="审核员", conclusion="风险"))
        self.assertEqual(result["results"][0]["conclusion"], "风险")
        self.assertEqual(len(result["audit"]), 1)
        entry = result["audit"][0]
        self.assertEqual((entry["old_value"], entry["new_value"], entry["actor"]), ("通过", "风险", "审核员"))
        self.assertTrue(entry["changed_at"])
        self.assertEqual(api.get_review(self.review["review_id"])["audit"], result["audit"])

    def test_same_value_does_not_add_audit(self):
        api.update_rule(self.review["review_id"], "penalty_ratio", api.PatchRequest(actor="审核员", conclusion="通过"))
        self.assertEqual(api.get_review(self.review["review_id"])["audit"], [])

    def test_report_uses_saved_latest_state_and_audit(self):
        api.update_rule(self.review["review_id"], "penalty_ratio", api.PatchRequest(actor="审核员", conclusion="风险"))
        report = api.export_report(api.ReportRequest(review_id=self.review["review_id"], format="markdown"))
        self.assertIn("最终结论：风险", report.body.decode())
        self.assertIn("审核员", report.body.decode())
        as_json = api.export_report(api.ReportRequest(review_id=self.review["review_id"], format="json"))
        self.assertEqual(json.loads(as_json.body)["results"][0]["conclusion"], "风险")

    def test_invalid_review_rule_and_conclusion_have_appropriate_errors(self):
        with self.assertRaises(HTTPException) as missing:
            api.get_review("missing")
        self.assertEqual(missing.exception.status_code, 404)
        with self.assertRaises(HTTPException) as bad_rule:
            api.update_rule(self.review["review_id"], "missing", api.PatchRequest(actor="审核员", conclusion="风险"))
        self.assertEqual(bad_rule.exception.status_code, 404)
        with self.assertRaises(HTTPException) as bad_value:
            api.update_rule(self.review["review_id"], "penalty_ratio", api.PatchRequest(actor="审核员", conclusion="待确认"))
        self.assertEqual(bad_value.exception.status_code, 422)
        with self.assertRaises(HTTPException) as bad_format:
            api.export_report(api.ReportRequest(review_id=self.review["review_id"], format="pdf"))
        self.assertEqual(bad_format.exception.status_code, 422)

    def test_llm_fallback_without_key_degrades_to_manual_review(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": ""}):
            result = api.create_review(api.ReviewRequest(text="本合同经双方签署后生效。", use_llm=True))
        missing = next(item for item in result["results"] if item["rule_id"] == "payment_deadline")
        self.assertEqual(missing["conclusion"], "需人工确认")
        self.assertIn("AI 兜底暂不可用", missing["reason"])

    def test_capabilities_never_exposes_api_key(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-only-secret"}):
            result = api.capabilities()
        self.assertTrue(result["llm_available"])
        self.assertNotIn("test-only-secret", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
