import os
import tempfile
import unittest

from app import create_app
from app.db import init_db


class LifePathTestCase(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE": self.db_path,
                "SECRET_KEY": "test",
            }
        )
        with self.app.app_context():
            init_db()

        self.client = self.app.test_client()

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_home_page_loads(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Life Path", response.data)

    def test_create_goal_and_complete(self):
        self.client.get("/")
        with self.client.session_transaction() as sess:
            token = sess["csrf_token"]

        self.client.post(
            "/people/add",
            data={"name": "Alex", "role": "Manager", "csrf_token": token},
        )

        with self.app.app_context():
            from app.db import get_db

            db = get_db()
            person = db.execute(
                "SELECT id FROM people WHERE name = 'Alex'"
            ).fetchone()

        self.client.post(
            "/goals/new",
            data={
                "person_id": person["id"],
                "title": "Launch product",
                "description": "Prepare launch plan",
                "resources": "Team and assets",
                "goal_notes": "Critical",
                "csrf_token": token,
            },
            follow_redirects=True,
        )

        with self.app.app_context():
            from app.db import get_db

            db = get_db()
            goal = db.execute(
                "SELECT id FROM goals WHERE title = 'Launch product'"
            ).fetchone()

        self.client.post(
            f"/goals/{goal['id']}/complete",
            data={"csrf_token": token},
            follow_redirects=True,
        )
        history = self.client.get("/history")
        self.assertIn(b"Launch product", history.data)

    def test_checkout_invalid_plan(self):
        self.client.get("/")
        with self.client.session_transaction() as sess:
            token = sess["csrf_token"]
        response = self.client.post(
            "/create-checkout-session",
            data={"plan": "free", "csrf_token": token},
        )
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
