from __future__ import annotations

import importlib
import os
from pathlib import Path
import unittest
from unittest.mock import patch


TEST_DB_PATH = Path(__file__).resolve().parents[1] / "test_persistent_api.db"
JOB_DESCRIPTION = "Python FastAPI developer with SQL, APIs, AWS, and backend skills."


class PersistentRankApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH.as_posix()}"

        if TEST_DB_PATH.exists():
            TEST_DB_PATH.unlink()

        import ai.ai_pipeline as pipeline_module
        import backend.app as app_module
        import backend.database as database_module
        import backend.models as models_module

        cls.pipeline = pipeline_module
        cls.database_module = importlib.reload(database_module)
        cls.models_module = importlib.reload(models_module)
        cls.app_module = importlib.reload(app_module)
        cls.database_module.ensure_database_ready()
        cls.app = cls.app_module.app
        cls.sample_pdf = Path(__file__).resolve().parents[2] / "ai" / "sample_resume.pdf"

    @classmethod
    def tearDownClass(cls) -> None:
        os.environ.pop("DATABASE_URL", None)
        if TEST_DB_PATH.exists():
            try:
                TEST_DB_PATH.unlink()
            except PermissionError:
                pass

    def test_rank_persists_across_app_restarts(self) -> None:
        from fastapi.testclient import TestClient

        with (
            TestClient(self.app) as client,
            self.sample_pdf.open("rb") as resume_file,
            patch.object(self.pipeline, "_load_embedding_model", return_value=None),
        ):
            upload_response = client.post(
                "/upload-resume",
                files={"file": ("sample_resume.pdf", resume_file, "application/pdf")},
                data={"job_description": JOB_DESCRIPTION},
            )

            self.assertEqual(200, upload_response.status_code)
            rank_response = client.get("/rank")
            self.assertEqual(200, rank_response.status_code)
            first_rank = rank_response.json()
            self.assertEqual(1, len(first_rank["ranked_resumes"]))

        restarted_app_module = importlib.reload(self.app_module)
        with TestClient(restarted_app_module.app) as restarted_client:
            rank_after_restart = restarted_client.get("/rank")

        self.assertEqual(200, rank_after_restart.status_code)
        ranked_resumes = rank_after_restart.json()["ranked_resumes"]
        self.assertEqual(1, len(ranked_resumes))
        self.assertEqual("sample_resume.pdf", ranked_resumes[0]["filename"])


if __name__ == "__main__":
    unittest.main()
