import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from aiohttp.test_utils import TestClient, TestServer
from aiohttp import web

import worker


class FakeResponse:
    def __init__(self, status, body):
        self.status, self.body = status, body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def json(self):
        return self.body


class FakeSession:
    branch_sha = "a" * 40

    def __init__(self, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    def get(self, *args, **kwargs):
        return FakeResponse(200, {"commit": {"sha": self.branch_sha}})

    def post(self, *args, **kwargs):
        return FakeResponse(201, {"html_url": "https://github.com/example/pr/1"})


class PRTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.jobs = Path(self.temp.name)
        self.job_id = "b" * 32
        self.path = self.jobs / (self.job_id + ".json")
        self.path.write_text(json.dumps({"base_commit": "a" * 40, "base_branch": "main", "task": "test", "diff": "example", "test_summary": "ok"}))
        app = web.Application()
        app.router.add_post("/pr", worker.create_pr)
        self.client = TestClient(TestServer(app))
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()
        self.temp.cleanup()

    async def test_invalid_id_and_missing_token(self):
        with patch.object(worker, "JOBS_DIR", self.jobs), patch.dict(os.environ, {"GITHUB_TOKEN": ""}):
            self.assertEqual((await self.client.post("/pr", json={"job_id": "../bad"})).status, 400)
            self.assertEqual((await self.client.post("/pr", json={"job_id": self.job_id})).status, 400)

    async def test_stale_base_does_not_push(self):
        with patch.object(worker, "JOBS_DIR", self.jobs), patch.dict(os.environ, {"GITHUB_TOKEN": "test"}), patch.object(worker, "ClientSession", FakeSession), patch.object(worker, "command", new_callable=AsyncMock) as command:
            FakeSession.branch_sha = "c" * 40
            response = await self.client.post("/pr", json={"job_id": self.job_id})
            self.assertEqual(response.status, 409)
            command.assert_not_awaited()
            FakeSession.branch_sha = "a" * 40

    async def test_create_and_repeat(self):
        async def fake_command(*args, **kwargs):
            if "rev-parse" in args:
                return 0, "a" * 40 + "\n"
            return 0, ""

        with patch.object(worker, "JOBS_DIR", self.jobs), patch.dict(os.environ, {"GITHUB_TOKEN": "test"}), patch.object(worker, "ClientSession", FakeSession), patch.object(worker, "command", side_effect=fake_command):
            response = await self.client.post("/pr", json={"job_id": self.job_id})
            self.assertEqual(response.status, 200)
            self.assertEqual(json.loads(self.path.read_text())["pr_url"], "https://github.com/example/pr/1")
            response = await self.client.post("/pr", json={"job_id": self.job_id})
            self.assertIn("이미 생성된 PR", (await response.json())["message"])


if __name__ == "__main__":
    unittest.main()
