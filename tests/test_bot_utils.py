import unittest

from bot_utils import build_reply_payload


class BotUtilsTests(unittest.TestCase):
    def test_wraps_plain_text_into_answer_payload(self):
        payload = build_reply_payload("What is 2+2?", "4", "https://example.com/run.jsonl")
        self.assertEqual(payload, {"answer": "4", "log_url": "https://example.com/run.jsonl"})

    def test_preserves_answer_field_and_adds_log_url(self):
        payload = build_reply_payload(
            "Return JSON",
            '{"answer": {"state": "Tamil Nadu"}}',
            "https://example.com/run.jsonl",
        )
        self.assertEqual(
            payload,
            {"answer": {"state": "Tamil Nadu"}, "log_url": "https://example.com/run.jsonl"},
        )

    def test_extracts_json_from_wrapped_text(self):
        payload = build_reply_payload(
            "Return JSON",
            'Sure! Here is the answer: {"answer": 42}',
            "https://example.com/run.jsonl",
        )
        self.assertEqual(payload, {"answer": 42, "log_url": "https://example.com/run.jsonl"})

    def test_preserves_direct_json_object(self):
        payload = build_reply_payload(
            "Reply with ONLY a JSON object like {'value': }",
            '{"value": 391}',
            "https://example.com/run.jsonl",
        )
        self.assertEqual(payload, {"value": 391, "log_url": "https://example.com/run.jsonl"})


if __name__ == "__main__":
    unittest.main()
