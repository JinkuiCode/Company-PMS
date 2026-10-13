"""Feedback inputs follow the approved A mockup, independent of any database."""
import importlib
import importlib.util
import sys
import unittest
from pathlib import Path

from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class FeedbackInputContract(unittest.TestCase):
    def setUp(self):
        module = importlib.util.find_spec("app.schemas.feedback")
        self.assertIsNotNone(module, "approved feedback input validation is not implemented")
        self.schemas = importlib.import_module("app.schemas.feedback")
        self.issue = dict(submission_id='11111111-1111-4111-8111-111111111111', type_id=1, module_id=1, category_id=1, impact_id=1,
                          title="查询异常", description="点击查询未显示结果",
                          expected_result="正常显示数据", steps="进入列表点击查询")

    def test_every_required_submit_field_must_be_explicit(self):
        for field in self.issue:
            with self.subTest(field=field):
                payload = {key: value for key, value in self.issue.items() if key != field}
                with self.assertRaises(ValidationError):
                    self.schemas.FeedbackCreate(**payload)

    def test_blank_text_is_not_a_completed_input(self):
        for field in ("title", "description", "expected_result", "steps"):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                self.schemas.FeedbackCreate(**{**self.issue, field: " \t\n "})

    def test_request_can_omit_reproduction_steps(self):
        request = {**self.issue, "type_id": 2}
        request.pop("steps")
        parsed = self.schemas.FeedbackCreate(**request)
        self.assertEqual(parsed.steps, "")
        self.assertEqual(parsed.type_id, 2)

    def test_user_cannot_supply_author_status_or_notification_email(self):
        for field, value in (("author_id", 2), ("status_id", 5), ("email", "fixture@example.invalid")):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                self.schemas.FeedbackCreate(**{**self.issue, field: value})

    def test_stable_enum_values_are_positive_integers_not_names_or_booleans(self):
        for field in ("type_id", "module_id", "category_id", "impact_id"):
            for invalid in (True, "1", "问题", 0, None):
                with self.subTest(field=field, value=invalid), self.assertRaises(ValidationError):
                    self.schemas.FeedbackCreate(**{**self.issue, field: invalid})

    def test_fact_text_is_trimmed_without_changing_meaning(self):
        parsed = self.schemas.FeedbackCreate(**{**self.issue, "title": "  查询异常  "})
        self.assertEqual(parsed.title, "查询异常")

    def test_terminal_state_requires_outcome_cause_and_opinion(self):
        for status, outcome in ((5, 1), (6, 5)):
            valid = dict(version=1, status_id=status, outcome_id=outcome, cause_id=1, opinion="处理说明")
            self.schemas.FeedbackHandle(**valid)
            for field in ("outcome_id", "cause_id", "opinion", "version"):
                with self.subTest(status=status, field=field), self.assertRaises(ValidationError):
                    self.schemas.FeedbackHandle(**{key: value for key, value in valid.items() if key != field})

    def test_completed_and_closed_outcomes_cannot_be_confused(self):
        for status, outcomes in ((5, (5, 6)), (6, (1, 2, 3, 4))):
            for outcome in outcomes:
                with self.subTest(status=status, outcome=outcome), self.assertRaises(ValidationError):
                    self.schemas.FeedbackHandle(version=1, status_id=status,
                                                outcome_id=outcome, cause_id=1, opinion="处理说明")

    def test_nonterminal_followup_still_requires_opinion_and_version(self):
        parsed = self.schemas.FeedbackHandle(version=1, status_id=2, opinion="正在排查")
        self.assertIsNone(parsed.outcome_id)
        for updates in ({"opinion": "  "}, {"version": 0}, {"status_id": 7}):
            with self.subTest(updates=updates), self.assertRaises(ValidationError):
                self.schemas.FeedbackHandle(**{**dict(version=1, status_id=2, opinion="正在排查"), **updates})

    def test_supplement_needs_nonblank_content_and_current_version(self):
        self.schemas.FeedbackSupplement(version=1, description="补充操作截图")
        for payload in ({"version": 1, "description": "  "}, {"description": "补充"},
                        {"version": True, "description": "补充"}):
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                self.schemas.FeedbackSupplement(**payload)


if __name__ == "__main__":
    unittest.main()
