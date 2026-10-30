"""English defaults and compatibility with personalized interface text."""

import json
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from PySide6.QtWidgets import QApplication, QLabel

from vocabulary_app.core import AppService, localize_record
from vocabulary_app.ui import MainWindow
from test_desktop import QuietSpeech


RESOURCES = Path(__file__).resolve().parents[1] / "vocabulary_app" / "resources"
HAN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


class EnglishDefaultsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_all_bundled_content_and_interface_text_are_english(self):
        for path in RESOURCES.glob("*.json"):
            with self.subTest(resource=path.name):
                data = json.loads(path.read_text(encoding="utf-8"))
                self.assertIsNone(HAN.search(json.dumps(data, ensure_ascii=False)))
        content = json.loads((RESOURCES / "content.json").read_text(encoding="utf-8"))
        self.assertEqual(len(content["words"]), 1080)
        self.assertEqual(sum(len(word["senses"]) for word in content["words"]), 1274)
        for word in content["words"]:
            for sense in word["senses"]:
                with self.subTest(sense=sense["id"]):
                    self.assertEqual(sense["language"], "en")
                    self.assertTrue(re.search(r"[a-zA-Z]", sense["definition"]))
                    self.assertNotEqual(sense["definition"].casefold(), word["lemma"].casefold())

    def test_application_entrypoint_starts_with_english_locale(self):
        script = '''
import sys
from PySide6.QtCore import QLocale, QTimer
from PySide6 import QtWidgets
class TimedApplication(QtWidgets.QApplication):
    def exec(self):
        QTimer.singleShot(0, self.quit)
        return super().exec()
QtWidgets.QApplication = TimedApplication
from vocabulary_app.__main__ import main
sys.argv = ['vocabulary_app', '--data-dir', sys.argv[1]]
result = main()
assert QLocale().name() == 'en_US'
raise SystemExit(result)
'''
        with TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, "-c", script, directory],
                                    cwd=RESOURCES.parents[1], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_saved_old_defaults_upgrade_and_personal_edits_remain(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "ui_texts.json"
            custom = {"app_title": "\u5355\u8bcd\u5b66\u4e60", "nav_home": "My dashboard"}
            path.write_text(json.dumps(custom), encoding="utf-8")
            original = path.read_bytes()
            service = AppService(data_dir=directory)
            window = MainWindow(service, QuietSpeech())
            try:
                self.assertEqual(window.tr("app_title"), "Vocabulary Learning")
                self.assertEqual(window.tr("nav_home"), "My dashboard")
                self.assertEqual(path.read_bytes(), original)
            finally:
                window.close()
                service.close()
                self.app.processEvents()

    def test_long_english_answers_remain_readable_at_minimum_window_size(self):
        with TemporaryDirectory() as directory:
            service = AppService(directory)
            service.update_profile(onboarding_complete=True)
            words = sorted(service.word_catalog(),
                           key=lambda word: max(len(sense["definition"]) for sense in word["senses"]),
                           reverse=True)
            for word in words[:20]:
                service.enqueue(word["id"])
            session = service.start_session()
            session = service.begin_learning(session["id"])
            while session["stage"] == "learn":
                session = service.next_word(session["id"])
            window = MainWindow(service, QuietSpeech())
            try:
                window.resize(900, 660)
                window.current_session = session
                window.show_page("learning")
                window.show()
                for _ in range(5):
                    self.app.processEvents()
                self.assertEqual(len(window.answer_buttons), 4)
                self.assertEqual(window.scroll.horizontalScrollBar().maximum(), 0)
                for button in window.answer_buttons:
                    caption = button.findChild(QLabel)
                    self.assertGreaterEqual(caption.height(), caption.heightForWidth(caption.width()))
            finally:
                window.close()
                service.close()
                self.app.processEvents()

    def test_old_record_display_is_english_without_rewriting_evidence(self):
        data = {
            "profile": {"name": "\u82f9\u679c", "self_rating": "\u521d\u7ea7"},
            "senses": [{"id": "en.apple.n1", "definition": "\u82f9\u679c", "language": "zh-CN"}],
            "choice_text": "\u6211\u4e0d\u4f1a",
            "title": "\u638c\u63e1 5000 \u8bcd",
        }
        original = json.dumps(data)
        shown = localize_record(data)
        self.assertEqual(shown["profile"]["name"], data["profile"]["name"])
        self.assertEqual(shown["profile"]["self_rating"], "Beginner")
        self.assertIsNone(HAN.search(shown["senses"][0]["definition"]))
        self.assertEqual(shown["senses"][0]["language"], "en")
        self.assertEqual(shown["choice_text"], "I don't know")
        self.assertEqual(shown["title"], "Master 5000 words")
        self.assertEqual(json.dumps(data), original)


if __name__ == "__main__":
    unittest.main()
