import asyncio
import gc
import importlib
import os
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


def _load_app_modules(db_path: str):
    os.environ["DATABASE_PATH"] = db_path

    import config
    import database
    import main
    import routes.discussions
    import routes.panelists
    import routes.streaming
    import routes.summaries
    import services.consensus
    import services.discussions
    import services.llm
    import services.panelists
    import services.speeches
    import services.summaries

    modules = [
        config,
        database,
        services.llm,
        services.discussions,
        services.panelists,
        services.consensus,
        services.summaries,
        services.speeches,
        routes.discussions,
        routes.panelists,
        routes.streaming,
        routes.summaries,
        main,
    ]

    for module in modules:
        importlib.reload(module)

    return {
        "main": main,
        "panelists": services.panelists,
        "speeches": services.speeches,
        "summaries": services.summaries,
    }


class BackendAppTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "test.db")
        self.modules = _load_app_modules(self.db_path)
        self.client = TestClient(self.modules["main"].app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.modules["summaries"]._summary_cache.clear()
        os.environ.pop("DATABASE_PATH", None)
        gc.collect()
        for _ in range(5):
            try:
                self.temp_dir.cleanup()
                break
            except PermissionError:
                time.sleep(0.2)
        else:
            self.temp_dir.cleanup()

    def _create_discussion(self, title: str = "测试讨论", topic: str = "测试话题") -> dict:
        response = self.client.post(
            "/api/v1/discussions",
            json={"title": title, "topic": topic},
        )
        self.assertEqual(response.status_code, 201)
        return response.json()

    def _add_panelist(self, discussion_id: int, *, name: str, role: str, color: str) -> dict:
        response = self.client.post(
            f"/api/v1/discussions/{discussion_id}/panelists",
            json={
                "name": name,
                "title": f"{name} 的头衔",
                "stance": f"{name} 的立场",
                "color": color,
                "role": role,
                "avatar_url": "",
            },
        )
        self.assertEqual(response.status_code, 201)
        return response.json()

    def _insert_speech(self, discussion_id: int, panelist_id: int, content: str, sequence_num: int = 1):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO speeches (discussion_id, panelist_id, content, sequence_num)
                VALUES (?, ?, ?, ?)
                """,
                (discussion_id, panelist_id, content, sequence_num),
            )
            conn.commit()

    def test_discussion_crud_and_list_flow(self):
        created = self._create_discussion(title="圆桌 A", topic="AI 取代客服")
        self.assertEqual(created["title"], "圆桌 A")
        self.assertEqual(created["topic"], "AI 取代客服")

        list_response = self.client.get("/api/v1/discussions")
        self.assertEqual(list_response.status_code, 200)
        payload = list_response.json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["items"][0]["id"], created["id"])

        patch_response = self.client.patch(
            f"/api/v1/discussions/{created['id']}",
            json={"status": "paused"},
        )
        self.assertEqual(patch_response.status_code, 200)
        self.assertEqual(patch_response.json()["status"], "paused")

        filtered = self.client.get("/api/v1/discussions?status=paused")
        self.assertEqual(filtered.status_code, 200)
        self.assertEqual(filtered.json()["total"], 1)

        delete_response = self.client.delete(f"/api/v1/discussions/{created['id']}")
        self.assertEqual(delete_response.status_code, 204)

        final_list = self.client.get("/api/v1/discussions")
        self.assertEqual(final_list.status_code, 200)
        self.assertEqual(final_list.json()["total"], 0)

    def test_generate_panelists_persists_host_and_experts(self):
        discussion = self._create_discussion()

        fake_panelists = {
            "host": {
                "name": "主持人甲",
                "title": "科技记者",
                "stance": "中立引导",
                "color": "#3366FF",
            },
            "experts": [
                {
                    "name": "专家乙",
                    "title": "AI研究员",
                    "stance": "支持快速采用AI",
                    "color": "#22AA66",
                },
                {
                    "name": "专家丙",
                    "title": "伦理学者",
                    "stance": "强调审慎治理",
                    "color": "#FF6633",
                },
                {
                    "name": "专家丁",
                    "title": "企业CTO",
                    "stance": "关注落地平衡",
                    "color": "#AA33CC",
                },
            ],
        }

        with patch.object(
            self.modules["panelists"],
            "llm_generate_panelists",
            AsyncMock(return_value=fake_panelists),
        ):
            response = self.client.post(
                f"/api/v1/discussions/{discussion['id']}/panelists/generate",
                json={"count": 4},
            )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(len(payload["items"]), 4)
        self.assertEqual(payload["host"]["role"], "host")
        self.assertEqual(len(payload["experts"]), 3)

        list_response = self.client.get(f"/api/v1/discussions/{discussion['id']}/panelists")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.json()["items"]), 4)

    def test_trigger_next_speech_creates_speech_record(self):
        discussion = self._create_discussion()
        host = self._add_panelist(discussion["id"], name="主持人", role="host", color="#3366FF")
        self._add_panelist(discussion["id"], name="专家", role="expert", color="#22AA66")

        async def fake_stream(*args, **kwargs):
            yield "第一句。"
            yield "第二句。"

        with patch.object(
            self.modules["speeches"],
            "decide_next_speaker",
            AsyncMock(return_value={"next_speaker_id": host["id"], "speech_type": "opening", "reason": "测试"}),
        ), patch.object(
            self.modules["speeches"],
            "generate_speech_stream",
            fake_stream,
        ), patch.object(
            self.modules["speeches"],
            "trigger_consensus_analysis",
            AsyncMock(return_value=None),
        ):
            response = self.client.post(f"/api/v1/discussions/{discussion['id']}/speeches/next", json={})
            self.assertEqual(response.status_code, 202)
            time.sleep(0.3)

        speeches = self.client.get(f"/api/v1/discussions/{discussion['id']}/speeches")
        self.assertEqual(speeches.status_code, 200)
        payload = speeches.json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["items"][0]["panelist_id"], host["id"])
        self.assertIn("第一句", payload["items"][0]["content"])

    def test_generate_summary_marks_discussion_completed_and_caches_result(self):
        discussion = self._create_discussion()
        host = self._add_panelist(discussion["id"], name="主持人", role="host", color="#3366FF")
        self._insert_speech(discussion["id"], host["id"], "这是一次有效发言。", sequence_num=1)

        with patch.object(
            self.modules["summaries"],
            "llm_generate_summary",
            AsyncMock(return_value="## 讨论概述\n\n测试总结内容"),
        ):
            response = self.client.post(f"/api/v1/discussions/{discussion['id']}/summary")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("## 讨论概述", payload["content"])

        discussion_detail = self.client.get(f"/api/v1/discussions/{discussion['id']}")
        self.assertEqual(discussion_detail.status_code, 200)
        self.assertEqual(discussion_detail.json()["status"], "completed")

        cached = self.client.get(f"/api/v1/discussions/{discussion['id']}/summary")
        self.assertEqual(cached.status_code, 200)
        self.assertEqual(cached.json()["content"], payload["content"])


if __name__ == "__main__":
    unittest.main()
