from pathlib import Path
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import ai.ai_pipeline as pipeline
from backend.app import app


JOB_DESCRIPTION = "Python FastAPI developer with SQL, APIs, AWS, and backend skills."
FAKE_TEMPLATE_TEXT = """First Name Last Name
123 Maple Dr. 617-555-1234
Anywhere, MA 02116 email@email.com
Profile
This is where you write what work you'd like to do and what motivates you.
Experience
Describe the tasks and responsibilities of the job.
Be specific and use numbers to show growth or accomplishments.
List your jobs in reverse chronological order starting with most recent.
Use bullet points, but don't end your sentence with punctuation.
Include volunteer or internships that you've had that might be relevant to the job.
Interest
Other interests you might have that give them an idea of who you are.
"""


class AnalyzeResumeApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)
        cls.sample_pdf = Path(__file__).resolve().parents[2] / "ai" / "sample_resume.pdf"

    def test_fake_resume_flow_returns_unranked_result(self) -> None:
        with (
            self.sample_pdf.open("rb") as resume_file,
            patch.object(pipeline, "extract_text_from_pdf", return_value=FAKE_TEMPLATE_TEXT),
            patch.object(pipeline, "_load_embedding_model", return_value=None),
        ):
            response = self.client.post(
                "/analyze-resume",
                files={"resume": ("Fake-Resume.pdf", resume_file, "application/pdf")},
                data={"job_description": JOB_DESCRIPTION},
            )

        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertTrue(body["is_fake"])
        self.assertEqual("fake", body["resume_status"])
        self.assertFalse(body["ranked"])
        self.assertEqual(0.0, body["final_score"])
        self.assertIn("authenticity_score", body)

    def test_real_resume_flow_returns_rankable_result(self) -> None:
        with (
            self.sample_pdf.open("rb") as resume_file,
            patch.object(pipeline, "_load_embedding_model", return_value=None),
        ):
            response = self.client.post(
                "/analyze-resume",
                files={"resume": ("sample_resume.pdf", resume_file, "application/pdf")},
                data={"job_description": JOB_DESCRIPTION},
            )

        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertFalse(body["is_fake"])
        self.assertEqual("real", body["resume_status"])
        self.assertTrue(body["ranked"])
        self.assertGreater(body["match_score"], 0.0)
        self.assertGreater(body["final_score"], 0.0)
        self.assertIn("skills", body)


if __name__ == "__main__":
    unittest.main()
