"""Desktop integration checks against the actual local learning service."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication, QEvent, QObject, Qt, Signal
from PySide6.QtWidgets import QApplication, QCheckBox, QPushButton, QTableWidget, QWidget

from vocabulary_app.animations import CelebrationOverlay
from vocabulary_app.core import AppService
from vocabulary_app.ui import MainWindow


class QuietSpeech(QObject):
    stateChanged = Signal(str)
    available = False

    def select_language(self, language):
        self.language = language

    def status(self):
        return "测试档案：本地语音状态单独验证"

    def speak(self, text, language="en-US"):
        return False

    def stop(self):
        pass


class DesktopFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.directory = TemporaryDirectory()
        self.service = AppService(data_dir=self.directory.name)
        self.service.update_profile(estimated_vocabulary=1000, onboarding_complete=True)
        self.service.configure_goal("word_count", baseline=1000, target=5000)
        self.window = MainWindow(self.service, QuietSpeech())

    def tearDown(self):
        self.window.close()
        self.flush()
        self.service.close()
        self.directory.cleanup()

    def flush(self):
        self.app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def click_text(self, text):
        self.flush()
        buttons = [b for b in self.window.findChildren(QPushButton)
                   if b.text() == text and b.isVisibleTo(self.window)]
        self.assertEqual(len(buttons), 1, f"Expected one active button: {text}")
        buttons[0].click()
        self.flush()

    def test_learning_controls_resume_and_settlement_without_network(self):
        with patch("socket.create_connection", side_effect=AssertionError("Unexpected network request")):
            self.window._start_or_continue()
            self.flush()
            session_id = self.window.current_session["id"]
            table = self.window.findChild(QTableWidget, "overviewTable")
            self.assertEqual(table.rowCount(), 20)
            for row in range(5):
                table.cellWidget(row, 3).findChild(QCheckBox).setChecked(True)
            self.click_text(self.window.tr("overview_begin"))
            while self.window.current_session["stage"] == "learn":
                self.window.findChild(QPushButton, "nextWordButton").click()
                self.flush()
            self.window.unknown_button.click()
            self.flush()
            for _ in range(6):
                self.choose_correct()
            saved_question = self.window.current_session["question"]
            self.window.close()
            self.flush()
            self.service = AppService(data_dir=self.directory.name)
            self.assertEqual(self.service.snapshot()["stats"]["net_new_words"], 0)
            self.window = MainWindow(self.service, QuietSpeech())
            self.window._start_or_continue()
            self.flush()
            self.assertEqual(self.window.current_session["question"], saved_question)
            while self.window.current_session["stage"] == "quiz":
                self.choose_correct()
            self.assertEqual(len(self.window.current_session["wrong_ids"]), 1)
            self.click_text(self.window.tr("relearn_mistakes") + "（1）")
            self.window.findChild(QPushButton, "nextWordButton").click()
            self.flush()
            self.assertEqual(len(self.window.answer_buttons), 4)
            self.choose_correct()
            self.click_text(self.window.tr("finish_session"))
            self.assertEqual(self.window.current_session["stage"], "complete")
            self.assertEqual(self.window.current_session["result"]["net_new_words"], 15)
            self.assertEqual(len(self.service.mistakes()), 1)
            self.assertEqual(self.service.snapshot()["goals"][0]["ratio"], 15 / 4000)
            self.service.continue_session(session_id)
            self.assertEqual(self.service.snapshot()["stats"]["net_new_words"], 15)
            for page in ("mistakes", "history", "achievements", "settings", "home"):
                self.window.show_page(page)
                self.flush()
            self.assertFalse(self.service.snapshot()["settings"]["ai_enabled"])

    def choose_correct(self):
        question = self.window.current_session["question"]
        index = next(i for i, option in enumerate(question["options"])
                     if option["id"] == question["correct_option_id"])
        self.window.answer_buttons[index].click()
        self.flush()

    def fresh_window(self):
        self.window.close()
        self.flush()
        self.service.close()
        self.service = AppService(data_dir=Path(self.directory.name) / "first-run")
        self.window = MainWindow(self.service, QuietSpeech())
        self.flush()

    def test_home_modules_are_isolated_and_return_keeps_learning(self):
        self.assertEqual(self.window.page, "home")
        self.assertFalse(any(widget.objectName() == "sidebar" and widget.isVisibleTo(self.window)
                             for widget in self.window.findChildren(QWidget)))
        self.assertTrue(self.window.footer.isVisibleTo(self.window))
        self.assertFalse(self.window.back_button.isVisibleTo(self.window))
        modules = self.window.findChildren(QPushButton, "moduleCard")
        learning = next(button for button in modules if button.accessibleName() == self.window.tr("nav_learning"))
        learning.click()
        self.flush()
        identifier = self.window.current_session["id"]
        self.assertEqual(self.window.page, "learning")
        self.assertFalse(self.window.footer.isVisibleTo(self.window))
        self.assertFalse(self.window.mode_label.isVisibleTo(self.window))
        self.assertFalse(any(button.isVisibleTo(self.window) for button in self.window.findChildren(QPushButton, "moduleCard")))
        self.assertTrue(self.window.back_button.isVisibleTo(self.window))
        self.window.back_button.click()
        self.flush()
        self.assertEqual(self.window.page, "home")
        self.window._start_or_continue()
        self.flush()
        self.assertEqual(self.window.current_session["id"], identifier)
        for page in ("mistakes", "history", "achievements", "goals", "queue", "settings"):
            self.window.show_page("home")
            self.flush()
            button = next(b for b in self.window.findChildren(QPushButton, "moduleCard")
                          if b.isVisibleTo(self.window) and b.accessibleName() == self.window.tr({
                              "mistakes": "nav_mistakes", "history": "nav_history", "achievements": "nav_achievements",
                              "goals": "goals_title", "queue": "queue_title", "settings": "nav_settings"}[page]))
            button.click()
            self.flush()
            self.assertEqual(self.window.page, page)
            self.assertFalse(self.window.footer.isVisibleTo(self.window))
            self.assertFalse(self.window.mode_label.isVisibleTo(self.window))
            self.assertTrue(self.window.back_button.isVisibleTo(self.window))

    def test_first_run_quick_path_requires_goal_before_home(self):
        self.fresh_window()
        self.assertEqual(self.window.page, "onboarding")
        self.assertFalse(self.window.back_button.isVisibleTo(self.window))
        self.window.show_page("settings")
        self.assertEqual(self.window.page, "onboarding")
        self.click_text(self.window.tr("onboarding_quick"))
        self.assertEqual(self.service.snapshot()["profile"]["onboarding_step"], "goal")
        self.assertFalse(self.service.snapshot()["profile"]["onboarding_complete"])
        self.window.baseline_spin.setValue(1000)
        self.window.target_spin.setValue(5000)
        self.click_text(self.window.tr("onboarding_finish"))
        self.assertEqual(self.window.page, "home")
        self.assertTrue(self.service.snapshot()["profile"]["onboarding_complete"])
        self.assertEqual(self.service.snapshot()["goals"][0]["numerator"], 0)

    def test_first_run_assessment_choices_resume_then_set_goal(self):
        self.fresh_window()
        self.click_text(self.window.tr("onboarding_assess"))
        self.assertFalse(self.window.assessment_rating_combo.isVisibleTo(self.window))
        self.assertEqual([self.window.assessment_count_combo.itemData(i) for i in range(5)], [20, 50, 100, 200, 500])
        self.click_text(self.window.tr("assessment_begin"))
        for _ in range(7):
            self.choose_assessment_correct()
        saved = self.window.assessment_record["question"]
        self.window.close()
        self.flush()
        self.service = AppService(data_dir=Path(self.directory.name) / "first-run")
        self.window = MainWindow(self.service, QuietSpeech())
        self.flush()
        self.assertEqual(self.window.page, "onboarding")
        self.assertEqual(self.window.assessment_record["question"], saved)
        while self.window.assessment_record["status"] == "in_progress":
            self.choose_assessment_correct()
        self.assertFalse(self.service.snapshot()["profile"]["onboarding_complete"])
        self.assertEqual(self.service.snapshot()["stats"]["mastered_count"], 0)
        self.assertEqual(self.service.snapshot()["stats"]["practice_words"], 0)
        self.assertFalse(any(a["earned"] for a in self.service.achievements()))
        self.click_text(self.window.tr("assessment_to_goal"))
        self.window.baseline_spin.setValue(1000)
        self.window.target_spin.setValue(5000)
        self.click_text(self.window.tr("onboarding_finish"))
        self.assertEqual(self.window.page, "home")
        self.assertEqual(self.service.snapshot()["profile"]["estimated_vocabulary"], 1000)
        self.assertEqual(self.service.snapshot()["stats"]["net_new_words"], 0)
        self.window._open_reassessment()
        self.flush()
        self.assertTrue(self.window.assessment_rating_combo.isVisibleTo(self.window))

    def choose_assessment_correct(self):
        question = self.window.assessment_record["question"]
        index = next(i for i, option in enumerate(question["options"])
                     if option["id"] == question["correct_option_id"])
        self.window.answer_buttons[index].click()
        self.flush()

    def test_high_assessment_baseline_gets_valid_initial_goal_target(self):
        self.fresh_window()
        self.window.onboarding_rating_combo.setCurrentText("专业英语学习人")
        self.click_text(self.window.tr("onboarding_assess"))
        self.click_text(self.window.tr("assessment_begin"))
        while self.window.assessment_record["status"] == "in_progress":
            self.choose_assessment_correct()
        self.click_text(self.window.tr("assessment_to_goal"))
        baseline = self.window.baseline_spin.value()
        target = self.window.target_spin.value()
        self.assertGreater(baseline, 5000)
        self.assertEqual(target, min(1000000, max(5000, (baseline // 1000 + 1) * 1000)))
        self.assertGreater(target, baseline)
        self.window.baseline_spin.setValue(target)
        self.assertEqual(self.window.target_spin.value(), target)
        self.window.baseline_spin.setValue(baseline)
        self.click_text(self.window.tr("onboarding_finish"))
        self.assertEqual(self.window.page, "home")
        goal = self.service.snapshot()["goals"][0]
        self.assertEqual((goal["baseline"], goal["target"]), (baseline, target))

    def test_animation_has_collisions_finite_lifetime_and_reduced_option(self):
        overlay = self.window.effects
        overlay.start(words=["apple"])
        self.assertTrue(overlay.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents))
        particle = overlay.particles[0]
        particle.update(x=-10, y=overlay.height() + 10, vx=-100, vy=100)
        overlay._tick()
        self.assertGreater(particle["vx"], 0)
        self.assertLess(particle["vy"], 0)
        self.assertIsNotNone(particle["floor_at"])
        overlay.started -= 6
        overlay._tick()
        self.assertFalse(overlay.timer.isActive())
        self.assertTrue(overlay.isHidden())
        overlay.start(words=["apple"], reduced=True)
        self.assertFalse(overlay.timer.isActive())
        self.assertEqual(overlay.particles, [])


if __name__ == "__main__":
    unittest.main()
