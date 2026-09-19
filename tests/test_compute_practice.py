import unittest

from pydantic import ValidationError

from compute_models import (
    ComputePracticeGenerateRequest,
    ComputeRevisionGenerateRequest,
    ContextChunk,
    UserProfilePayload,
    exam_body_hint,
    practice_system_prompt,
)


class PracticeGenerateSchemaTests(unittest.TestCase):
    def _valid_kwargs(self, **overrides):
        data = {
            "subject": "Mathematics",
            "class_id": "SSS1",
            "topics": "Quadratic Equations",
            "week": 5,
            "term": "First Term",
            "country": "Nigeria",
            "difficulty": 0.3,
            "context_chunks": [ContextChunk(source="Curriculum 1", content="ax^2+bx+c=0.")],
            "user_profile": UserProfilePayload(
                full_name="Ada Lovelace",
                class_id="SSS1",
                subjects="Mathematics",
                learning_method="visual analogies",
                country="Nigeria",
            ),
            "exclude_stems": ["What is the discriminant?"],
        }
        data.update(overrides)
        return data

    def test_defaults_are_mcq_only(self):
        payload = ComputePracticeGenerateRequest(**self._valid_kwargs(exclude_stems=None))
        self.assertEqual(payload.mcq_count, 10)
        self.assertEqual(payload.theory_count, 0)
        self.assertEqual(payload.exclude_stems, [])

    def test_accepts_nest_term_string_and_int(self):
        string_term = ComputePracticeGenerateRequest(**self._valid_kwargs())
        self.assertEqual(string_term.term, "First Term")
        int_term = ComputePracticeGenerateRequest(**self._valid_kwargs(term=1))
        self.assertEqual(int_term.term, "1")

    def test_empty_context_chunks_rejected(self):
        with self.assertRaises(ValidationError):
            ComputePracticeGenerateRequest(**self._valid_kwargs(context_chunks=[]))

    def test_whitespace_only_chunks_rejected(self):
        with self.assertRaises(ValidationError):
            ComputePracticeGenerateRequest(
                **self._valid_kwargs(
                    context_chunks=[ContextChunk(source="Curriculum 1", content="   ")]
                )
            )

    def test_difficulty_bounds(self):
        with self.assertRaises(ValidationError):
            ComputePracticeGenerateRequest(**self._valid_kwargs(difficulty=0.09))
        with self.assertRaises(ValidationError):
            ComputePracticeGenerateRequest(**self._valid_kwargs(difficulty=1.01))
        ComputePracticeGenerateRequest(**self._valid_kwargs(difficulty=0.1))
        ComputePracticeGenerateRequest(**self._valid_kwargs(difficulty=1.0))

    def test_revision_generate_schema_unchanged(self):
        payload = ComputeRevisionGenerateRequest(subject="Biology")
        self.assertEqual(payload.mcq_count, 5)
        self.assertEqual(payload.theory_count, 2)
        self.assertEqual(payload.context_chunks, [])
        self.assertFalse(hasattr(payload, "difficulty"))
        self.assertFalse(hasattr(payload, "exclude_stems"))
        self.assertFalse(hasattr(payload, "week"))
        self.assertFalse(hasattr(payload, "term"))
        self.assertFalse(hasattr(payload, "country"))


class ExamBodyHintTests(unittest.TestCase):
    def test_nigeria_waec_neco(self):
        self.assertEqual(exam_body_hint("Nigeria"), "Write items in WAEC/NECO style.")

    def test_ghana_waec(self):
        self.assertEqual(exam_body_hint("ghana"), "Write items in WAEC style.")

    def test_unknown_country_is_generic(self):
        hint = exam_body_hint("France")
        self.assertIn("France", hint)
        self.assertNotIn("WAEC", hint)

    def test_missing_country_is_generic(self):
        self.assertIn("national secondary-school exam style", exam_body_hint(None))


class PracticePromptTests(unittest.TestCase):
    def test_prompt_uses_learning_method_not_full_name(self):
        payload = ComputePracticeGenerateRequest(
            subject="Mathematics",
            class_id="SSS1",
            topics="Quadratic Equations",
            week=5,
            term="First Term",
            country="Nigeria",
            difficulty=0.3,
            context_chunks=[ContextChunk(source="Curriculum 1", content="ax^2+bx+c=0.")],
            user_profile=UserProfilePayload(
                full_name="Ada Lovelace",
                learning_method="visual analogies",
            ),
            exclude_stems=["Solve {x}^2 = 4", "What is the discriminant?"],
        )
        prompt = practice_system_prompt(payload)
        self.assertIn("visual analogies", prompt)
        self.assertNotIn("Ada Lovelace", prompt)
        self.assertNotIn("full_name", prompt)
        self.assertIn("type' ('mcq')", prompt)
        self.assertIn("MCQ-only", prompt)
        self.assertIn("0.1 recall", prompt)
        self.assertIn("1.0 exam-hard", prompt)
        self.assertIn("WAEC/NECO", prompt)
        self.assertIn("Generate 10 MCQs", prompt)
        self.assertIn("First Term", prompt)
        self.assertIn("SSS1", prompt)
        self.assertIn("Quadratic Equations", prompt)
        self.assertIn("What is the discriminant?", prompt)
        self.assertIn("Solve {{x}}^2 = 4", prompt)
        self.assertNotIn("{x}", prompt.replace("{{x}}", ""))
        self.assertNotIn("Theory", prompt)
        self.assertEqual(prompt.count("{context}"), 1)


if __name__ == "__main__":
    unittest.main()
