import unittest
from unittest.mock import patch

from backend.auth_utils import create_token, decode_token
from backend.llm_schemas import (
    validate_poison_pill_sweep_payload,
    validate_rfp_extraction_payload,
)
from scoring.criterion_scorer import _score_batch_payload


class ReliabilityPassTests(unittest.TestCase):
    def test_rfp_validation_accepts_expected_shape(self):
        validated = validate_rfp_extraction_payload(
            {
                "rfp_id": "RFP-1",
                "issuer": "City",
                "gates": [
                    {
                        "gate_id": "g1",
                        "name": "Technical",
                        "type": "scored",
                        "criteria": [
                            {
                                "id": "c1",
                                "name": "Methodology",
                                "max_points": 10,
                                "checklist_signals": ["timeline"],
                                "evidence_required": ["proposal"],
                            }
                        ],
                    }
                ],
                "poison_pill_clauses": [],
                "submission_rules": ["submit before noon"],
                "wps_formula": "",
            }
        )
        self.assertEqual(validated.gates[0].criteria[0].id, "c1")

    def test_poison_pill_sweep_requires_clause_text_when_found(self):
        with self.assertRaises(ValueError):
            validate_poison_pill_sweep_payload({"found": True, "reason": "missing clause"})

    @patch("scoring.criterion_scorer.create_json_completion")
    def test_batch_scoring_boolean_signals(self, mocked_completion):
        """
        Verify the boolean-decoupling schema: the LLM emits explicit true/false
        per checklist signal; Python derives matched/gap lists without any fuzzy
        string normalisation.  A signal marked false is a gap; a signal absent
        from the LLM output is also conservatively treated as a gap.
        """
        mocked_completion.return_value = (
            '{"c1": {"signals": {"Timeline": true, "Budget": false}}, '
            ' "c2": {"signals": {"CVs": false}}}'
        )
        batch = [
            {
                "criterion_id": "c1",
                "name": "Methodology",
                "description": "Approach",
                "checklist_signals": ["Timeline", "Budget"],
            },
            {
                "criterion_id": "c2",
                "name": "Team",
                "description": "Staffing",
                "checklist_signals": ["CVs"],
            },
        ]

        scored = _score_batch_payload(batch, lambda _query, top_k=3: ["doc chunk"], 3, None)

        self.assertEqual(scored[0]["matched_signals"], ["Timeline"])
        self.assertEqual(scored[0]["gap_signals"], ["Budget"])
        self.assertEqual(scored[1]["matched_signals"], [])
        self.assertEqual(scored[1]["gap_signals"], ["CVs"])

    @patch("scoring.criterion_scorer.create_json_completion")
    def test_batch_scoring_rejects_unknown_ids(self, mocked_completion):
        mocked_completion.return_value = '{"unexpected": {"signals": {}}}'
        batch = [
            {
                "criterion_id": "c1",
                "name": "Methodology",
                "description": "Approach",
                "checklist_signals": ["Timeline"],
            }
        ]

        with self.assertRaises(ValueError):
            _score_batch_payload(batch, lambda _query, top_k=3: ["doc chunk"], 3, None)

    def test_token_contains_version_claim(self):
        token = create_token(7, "user@example.com", token_version=3)
        payload = decode_token(token)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["ver"], 3)


if __name__ == "__main__":
    unittest.main()
