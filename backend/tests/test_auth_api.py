from __future__ import annotations

import os
from pathlib import Path
import unittest


TEST_DB_PATH = Path(__file__).resolve().parents[1] / "test_auth_api.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH.as_posix()}"

if TEST_DB_PATH.exists():
    TEST_DB_PATH.unlink()

from fastapi.testclient import TestClient

from backend.app import app
from backend.database import ensure_database_ready


class AuthApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        ensure_database_ready()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls) -> None:
        if TEST_DB_PATH.exists():
            try:
                TEST_DB_PATH.unlink()
            except PermissionError:
                pass

    def test_register_login_and_reset_password_flow(self) -> None:
        register_payload = {
            "full_name": "Auth Test User",
            "email": "auth-test@example.com",
            "password": "Password123!",
        }

        register_response = self.client.post("/auth/register", json=register_payload)
        self.assertEqual(200, register_response.status_code)
        self.assertEqual("Account created successfully.", register_response.json()["message"])

        login_response = self.client.post(
            "/auth/login",
            json={"email": register_payload["email"], "password": register_payload["password"]},
        )
        self.assertEqual(200, login_response.status_code)
        login_body = login_response.json()
        self.assertEqual("bearer", login_body["token_type"])
        self.assertTrue(login_body["access_token"])

        forgot_response = self.client.post(
            "/auth/forgot-password",
            json={"email": register_payload["email"]},
        )
        self.assertEqual(200, forgot_response.status_code)
        reset_token = forgot_response.json()["reset_token"]

        reset_response = self.client.post(
            "/auth/reset-password",
            json={"token": reset_token, "new_password": "NewPassword123!"},
        )
        self.assertEqual(200, reset_response.status_code)
        self.assertEqual("Password updated successfully.", reset_response.json()["message"])

        relogin_response = self.client.post(
            "/auth/login",
            json={"email": register_payload["email"], "password": "NewPassword123!"},
        )
        self.assertEqual(200, relogin_response.status_code)
        self.assertTrue(relogin_response.json()["access_token"])


if __name__ == "__main__":
    unittest.main()
