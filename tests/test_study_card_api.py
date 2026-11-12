from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import app as app_module
import tools


class StudyCardApiTestCase(unittest.TestCase):
    def setUp(self):
        self.client = app_module.app.test_client()

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)
        self.root = self.base / "study_cards"
        self.root.mkdir()

        self._original_cards_dir = tools.STUDY_CARDS_DIR
        tools.STUDY_CARDS_DIR = self.root
        self.addCleanup(self._restore_cards_dir)

    def _restore_cards_dir(self):
        tools.STUDY_CARDS_DIR = self._original_cards_dir

    def write_card(self, relative, content="# Card\n"):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def delete(self, payload):
        return self.client.delete("/api/study-card", json=payload)


class ListAndDeleteTests(StudyCardApiTestCase):
    def test_lists_then_deletes_a_card(self):
        self.write_card("Note.md")

        listed = self.client.get("/api/study-cards").get_json()
        self.assertEqual([card["path"] for card in listed["cards"]], ["Note.md"])

        response = self.delete({"path": "Note.md"})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["ok"])
        self.assertFalse((self.root / "Note.md").exists())
        self.assertEqual(self.client.get("/api/study-cards").get_json()["cards"], [])

    def test_deletes_a_card_in_a_nested_folder(self):
        self.write_card("sub/Deep Card.md")

        response = self.delete({"path": "sub/Deep Card.md"})

        self.assertEqual(response.status_code, 200)
        self.assertFalse((self.root / "sub" / "Deep Card.md").exists())


class DeleteValidationTests(StudyCardApiTestCase):
    def test_rejects_missing_path(self):
        self.assertEqual(self.delete({}).status_code, 400)
        self.assertEqual(self.delete({"path": "   "}).status_code, 400)
        self.assertEqual(self.delete({"path": 5}).status_code, 400)

    def test_rejects_path_traversal(self):
        outside = self.base / "escape.md"
        outside.write_text("# escape\n", encoding="utf-8")

        response = self.delete({"path": "../escape.md"})

        self.assertEqual(response.status_code, 400)
        self.assertTrue(outside.exists())

    def test_rejects_non_markdown_files(self):
        (self.root / "notes.txt").write_text("secret\n", encoding="utf-8")

        self.assertEqual(self.delete({"path": "notes.txt"}).status_code, 404)
        self.assertTrue((self.root / "notes.txt").exists())

    def test_reports_missing_card(self):
        self.assertEqual(self.delete({"path": "Missing.md"}).status_code, 404)


if __name__ == "__main__":
    unittest.main()
