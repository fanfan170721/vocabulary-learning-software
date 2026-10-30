"""Assessment evidence, onboarding transitions and archive recovery."""

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from vocabulary_app.assessment import QUESTION_COUNTS, RATINGS, RATING_LEVELS, estimate
from vocabulary_app.core import AppService


class AssessmentTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.resources = self.root / "resources"
        self.resources.mkdir()
        words = [{
            "id": f"fixture-{index:04d}", "lemma": f"fixtureword{index}", "language": "en",
            "phonetic": "/test/", "level": index // 40 + 1,
            "senses": [{"id": f"fixture-sense-{index}", "pos": "noun", "definition": f"Test definition {index:04d}", "language": "en"}],
            "source": "Independent test fixture", "license": "test-only",
        } for index in range(600)]
        self.content = {"version": "fixture-600", "words": words, "word_sets": []}
        self.levels = {"version": "fixture-levels", "levels": [
            {"level": level, "estimated_range": [(level - 1) * 1000, level * 1000]} for level in range(1, 16)
        ], "self_ratings": [{"label": label, "level": level} for label, level in zip(RATINGS, RATING_LEVELS)]}
        (self.resources / "content.json").write_text(json.dumps(self.content), encoding="utf-8")
        (self.resources / "levels.json").write_text(json.dumps(self.levels), encoding="utf-8")
        self.service = AppService(self.root / "profile", self.resources)

    def tearDown(self):
        self.service.close()
        self.directory.cleanup()

    def finish_assessment(self, record, correct=True):
        while record["status"] == "in_progress":
            option = record["question"]["correct_option_id"] if correct else None
            record = self.service.answer_assessment(record["id"], option)
        return record

    def finish_learning(self):
        session = self.service.start_session()
        session = self.service.begin_learning(session["id"])
        while session["stage"] != "complete":
            if session["stage"] in ("learn", "relearn"):
                session = self.service.next_word(session["id"])
            elif session["stage"] == "quiz":
                session = self.service.answer(session["id"], session["question"]["correct_option_id"])
            else:
                session = self.service.continue_session(session["id"])
        return session

    def test_all_five_question_counts_create_real_distinct_assessments(self):
        self.assertEqual(QUESTION_COUNTS, (20, 50, 100, 200, 500))
        for count in QUESTION_COUNTS:
            service = AppService(self.root / f"count-{count}", self.resources)
            record = service.start_assessment("Beginner", count)
            self.assertEqual(record["question_count"], count)
            self.assertEqual(record["answered_count"], 0)
            self.assertEqual(len(record["question"]["options"]), 4)
            self.assertEqual(len(record["word_bank"]), 600)
            service.close()

    def test_fast_assessment_has_anchors_then_adaptive_questions_without_learning_credit(self):
        self.service.set_onboarding_rating("Beginner", use_assessment=True)
        before = self.service.snapshot()
        record = self.finish_assessment(self.service.start_assessment("Beginner", 20))
        phases = [q["selection_phase"] for q in record["questions"]]
        self.assertEqual(phases.count("anchor"), 6)
        self.assertEqual(phases.count("adaptive"), 14)
        self.assertEqual([q["level"] for q in record["questions"][:6]], [1, 4, 7, 10, 13, 15])
        self.assertEqual(len({q["word_id"] for q in record["questions"]}), 20)
        self.assertEqual(self.service.snapshot()["stats"], before["stats"])
        self.assertEqual(self.service.achievements(), before["achievements"])
        self.assertFalse(record["result"]["standardized"])
        self.assertTrue(record["result"]["recognition_only"])
        self.assertEqual(self.service.snapshot()["profile"]["onboarding_step"], "assessment_result")

    def test_500_question_assessment_resumes_exactly_and_completes_without_repeats(self):
        self.service.set_onboarding_rating("Intermediate")
        record = self.service.start_assessment("Intermediate", 500)
        for index in range(237):
            record = self.service.answer_assessment(record["id"], None if index % 7 == 0 else record["question"]["correct_option_id"])
        pending = deepcopy(record["question"])
        self.service.close()
        self.service = AppService(self.root / "profile", self.resources)
        self.assertEqual(self.service.assessment()["question"], pending)
        self.assertEqual(self.service.assessment()["answered_count"], 237)
        self.assertEqual(self.service.snapshot()["stats"]["mastered_count"], 0)
        archive = self.root / "500-partial.json"
        self.service.export_data(archive)
        self.service.import_data(archive)
        self.assertEqual(self.service.assessment()["question"], pending)
        record = self.finish_assessment(self.service.assessment())
        self.assertEqual(record["answered_count"], 500)
        self.assertEqual(len({q["word_id"] for q in record["questions"]}), 500)
        self.assertEqual(record["result"]["covered_levels"], list(range(1, 16)))
        self.assertTrue(record["completed_at"])
        self.assertEqual(self.service.snapshot()["stats"]["practice_words"], 0)
        self.service.export_data(archive)
        self.service.import_data(archive)
        self.assertEqual(self.service.assessment()["result"], record["result"])

    def test_small_bank_refuses_to_repeat_questions(self):
        self.content["words"] = self.content["words"][:100]
        (self.resources / "content.json").write_text(json.dumps(self.content), encoding="utf-8")
        service = AppService(self.root / "small", self.resources)
        with self.assertRaisesRegex(ValueError, "fewer than 200"):
            service.start_assessment("Beginner", 200)
        self.assertIsNone(service.assessment())
        service.close()

    def test_quick_self_rating_can_resume_goal_step_and_finish_atomically(self):
        self.assertEqual(self.service.snapshot()["profile"]["onboarding_step"], "self_rating")
        profile = self.service.set_onboarding_rating("Native speaker", name="Test learner", use_assessment=False)
        self.assertEqual(profile["onboarding_step"], "goal")
        self.assertEqual(profile["difficulty"], 12)
        self.assertIsNone(profile["abilities"]["listening"]["value"])
        self.service.close()
        self.service = AppService(self.root / "profile", self.resources)
        self.assertEqual(self.service.snapshot()["profile"]["onboarding_step"], "goal")
        with self.assertRaises(ValueError):
            self.service.finish_onboarding("word_count", baseline=5000, target=1000)
        self.assertFalse(self.service.snapshot()["profile"]["onboarding_complete"])
        self.assertEqual(self.service.snapshot()["goals"], [])
        state = self.service.finish_onboarding("word_count", baseline=1234, target=5000)
        self.assertTrue(state["profile"]["onboarding_complete"])
        self.assertEqual(state["profile"]["onboarding_step"], "complete")
        self.assertEqual(state["profile"]["estimate_source"], "self_report")
        self.assertEqual(state["stats"]["estimated_vocabulary"], 1234)
        self.assertEqual(state["goals"][0]["numerator"], 0)

    def test_completed_assessment_requires_acceptance_and_user_confirmed_starting_count(self):
        self.service.set_onboarding_rating("Beginner")
        record = self.finish_assessment(self.service.start_assessment("Beginner", 20), correct=False)
        self.assertEqual(self.service.snapshot()["profile"]["onboarding_step"], "assessment_result")
        with self.assertRaises(ValueError):
            self.service.finish_onboarding("word_count", baseline=100, target=5000)
        profile = self.service.accept_assessment(record["id"])
        self.assertEqual(profile["onboarding_step"], "goal")
        self.assertEqual(profile["difficulty"], record["result"]["recommended_level"])
        self.assertEqual(profile["estimated_vocabulary"], 0)
        state = self.service.finish_onboarding("word_count", baseline=275, target=5000)
        self.assertEqual(state["profile"]["estimate_source"], "user_confirmed_assessment")
        self.assertEqual(state["profile"]["estimate_assessment_id"], record["id"])
        self.assertEqual(state["stats"]["estimated_vocabulary"], 275)

    def test_existing_user_can_adopt_only_recommended_difficulty(self):
        self.service.set_onboarding_rating("Beginner", use_assessment=False)
        self.service.finish_onboarding("word_count", baseline=1000, target=5000)
        self.finish_learning()
        before = self.service.snapshot()
        history = self.service.history()
        record = self.finish_assessment(self.service.start_assessment("Advanced", 20), correct=False)
        profile = self.service.accept_assessment(record["id"])
        after = self.service.snapshot()
        self.assertTrue(profile["onboarding_complete"])
        self.assertEqual(profile["onboarding_step"], "complete")
        self.assertEqual(profile["self_rating"], before["profile"]["self_rating"])
        self.assertEqual(after["stats"], before["stats"])
        self.assertEqual(after["goals"], before["goals"])
        self.assertEqual(after["achievements"], before["achievements"])
        self.assertEqual(self.service.history(), history)
        self.assertIsNone(profile["abilities"]["speaking"]["value"])
        with self.assertRaises(ValueError):
            self.service.finish_onboarding("word_count", baseline=0, target=100)

    def test_one_wrong_answer_does_not_halve_the_recommendation(self):
        record = self.service.start_assessment("Intermediate", 20)
        for _ in range(12):
            record = self.service.answer_assessment(record["id"], record["question"]["correct_option_id"])
        previous = estimate(record)["recommended_level"]
        record = self.service.answer_assessment(record["id"], None)
        current = estimate(record)["recommended_level"]
        self.assertLessEqual(previous - current, 3)

    def test_archive_rejects_forged_assessment_and_preserves_current_answers(self):
        record = self.service.start_assessment("Beginner", 20)
        self.service.answer_assessment(record["id"], None)
        archive = self.root / "assessment.json"
        self.service.export_data(archive)
        original = json.loads(archive.read_text(encoding="utf-8"))
        for field, value in (("answered_count", 20), ("status", "complete"), ("result", {"recommended_level": 15})):
            bad = deepcopy(original)
            assessment = next(r["data"] for r in bad["records"] if r["kind"] == "assessment")
            assessment[field] = value
            archive.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaises(ValueError):
                self.service.import_data(archive)
        self.assertEqual(self.service.assessment()["answered_count"], 1)

    def test_previous_language_assessment_archive_keeps_scores_and_shows_english_results(self):
        record = self.finish_assessment(self.service.start_assessment("Beginner", 20), correct=False)
        expected_result = deepcopy(record["result"])
        archive = self.root / "legacy-assessment.json"
        self.service.export_data(archive)
        payload = json.loads(archive.read_text(encoding="utf-8"))
        archived = next(item["data"] for item in payload["records"] if item["kind"] == "assessment")
        archived["self_rating"] = "\u521d\u7ea7"
        for answer in archived["answers"]:
            answer["choice_text"] = "\u6211\u4e0d\u4f1a"
        recommended = archived["result"]["recommended_level"]
        levels = archived["available_levels"]
        archived["result"]["confidence"] = "\u8f83\u4f4e"
        archived["result"]["summary"] = (
            f"\u672c\u6b21\u6d4b\u8bc4\u63d0\u4f9b L{recommended} \u7684\u8bcd\u4e49\u8bc6\u522b\u96be\u5ea6\u53c2\u8003\uff1b"
            f"\u5b9e\u9645\u9898\u5e93\u8986\u76d6 L{min(levels)}\u2014L{max(levels)}\uff0c\u5c1a\u672a\u6807\u51c6\u5316\u6821\u51c6\u3002"
            "\u8bcd\u91cf\u533a\u95f4\u4ec5\u4f5c\u8bbe\u7f6e\u8d77\u70b9\u7684\u53c2\u8003\uff0c\u5176\u4ed6\u6280\u80fd\u5c1a\u672a\u6d4b\u91cf\u3002"
        )
        archive.write_text(json.dumps(payload), encoding="utf-8")
        self.service.import_data(archive)
        view = self.service.assessment(record["id"])
        self.assertEqual(view["self_rating"], "Beginner")
        self.assertEqual(view["result"], expected_result)
        self.assertEqual(view["answers"][0]["choice_text"], "I don't know")
        with self.service.store.connect() as connection:
            stored = self.service.store.get(connection, "assessment", record["id"])
        self.assertEqual(stored["result"], archived["result"])
        self.assertEqual(stored["answers"], archived["answers"])
        self.service.accept_assessment(record["id"])
        self.assertEqual(self.service.snapshot()["profile"]["abilities"]["recognition"]["confidence"], "Low")

    def test_legacy_export_without_onboarding_step_remains_compatible(self):
        self.service.update_profile(onboarding_complete=True, estimated_vocabulary=1000)
        archive = self.root / "legacy.json"
        self.service.export_data(archive)
        payload = json.loads(archive.read_text(encoding="utf-8"))
        profile = next(r["data"] for r in payload["records"] if r["kind"] == "profile")
        for key in ("onboarding_step", "onboarding_assessment_id", "estimate_source"):
            profile.pop(key, None)
        archive.write_text(json.dumps(payload), encoding="utf-8")
        self.service.import_data(archive)
        profile = self.service.snapshot()["profile"]
        self.assertTrue(profile["onboarding_complete"])
        self.assertEqual(profile["onboarding_step"], "complete")
        self.assertEqual(profile["estimated_vocabulary"], 1000)

    def test_legacy_used_profile_missing_onboarding_flag_resumes_saved_learning(self):
        self.service.update_profile(estimated_vocabulary=1000)
        goal = self.service.configure_goal("word_count", baseline=1000, target=5000)
        session = self.service.start_session()
        session = self.service.begin_learning(session["id"])
        while session["stage"] == "learn":
            session = self.service.next_word(session["id"])
        session = self.service.answer(session["id"], session["question"]["correct_option_id"])
        pending = deepcopy(session["question"])
        with self.service.store.transaction() as connection:
            profile = self.service.store.get(connection, "profile", "local")
            for key in ("onboarding_complete", "onboarding_step", "onboarding_assessment_id", "estimate_source"):
                profile.pop(key, None)
            self.service.store.put(connection, "profile", "local", profile)
        self.service.close()
        self.service = AppService(self.root / "profile", self.resources)
        snapshot = self.service.snapshot()
        self.assertTrue(snapshot["profile"]["onboarding_complete"])
        self.assertEqual(snapshot["profile"]["onboarding_step"], "complete")
        self.assertEqual(snapshot["profile"]["estimated_vocabulary"], 1000)
        self.assertEqual(snapshot["goals"][0], goal)
        self.assertEqual(self.service.session()["question"], pending)
        with self.assertRaises(ValueError):
            self.service.finish_onboarding("word_count", baseline=0, target=100)

    def test_import_migrates_missing_flag_only_when_real_usage_records_exist(self):
        self.service.configure_goal("word_count", baseline=1000, target=5000)
        saved = self.service.start_session()
        archive = self.root / "old-used-profile.json"
        self.service.export_data(archive)
        payload = json.loads(archive.read_text(encoding="utf-8"))
        profile = next(record["data"] for record in payload["records"] if record["kind"] == "profile")
        for key in ("onboarding_complete", "onboarding_step", "onboarding_assessment_id", "estimate_source"):
            profile.pop(key, None)
        archive.write_text(json.dumps(payload), encoding="utf-8")
        destination = AppService(self.root / "legacy-import", self.resources)
        destination.import_data(archive)
        state = destination.snapshot()
        self.assertTrue(state["profile"]["onboarding_complete"])
        self.assertEqual(state["profile"]["onboarding_step"], "complete")
        self.assertEqual(state["profile"]["estimated_vocabulary"], 1000)
        self.assertEqual(state["active_session"]["id"], saved["id"])
        self.assertEqual(state["goals"], self.service.snapshot()["goals"])
        with destination.store.connect() as connection:
            persisted = destination.store.get(connection, "profile", "local")
            self.assertTrue(persisted["onboarding_complete"])
        destination.close()

    def test_empty_legacy_profile_still_requires_onboarding(self):
        archive = self.root / "old-empty-profile.json"
        self.service.export_data(archive)
        payload = json.loads(archive.read_text(encoding="utf-8"))
        profile = next(record["data"] for record in payload["records"] if record["kind"] == "profile")
        for key in ("onboarding_complete", "onboarding_step", "onboarding_assessment_id", "estimate_source"):
            profile.pop(key, None)
        archive.write_text(json.dumps(payload), encoding="utf-8")
        self.service.import_data(archive)
        self.assertFalse(self.service.snapshot()["profile"]["onboarding_complete"])
        self.assertEqual(self.service.snapshot()["profile"]["onboarding_step"], "self_rating")
        self.service.close()
        self.service = AppService(self.root / "profile", self.resources)
        self.assertFalse(self.service.snapshot()["profile"]["onboarding_complete"])

    def test_explicit_unfinished_onboarding_is_not_inferred_complete_from_usage(self):
        self.service.set_onboarding_rating("Beginner", use_assessment=False)
        self.service.configure_goal("word_count", baseline=1000, target=5000)
        self.service.start_session()
        archive = self.root / "explicit-false.json"
        self.service.export_data(archive)
        self.service.close()
        self.service = AppService(self.root / "profile", self.resources)
        self.assertFalse(self.service.snapshot()["profile"]["onboarding_complete"])
        self.assertEqual(self.service.snapshot()["profile"]["onboarding_step"], "goal")
        self.service.import_data(archive)
        self.assertFalse(self.service.snapshot()["profile"]["onboarding_complete"])
        self.assertEqual(self.service.snapshot()["profile"]["onboarding_step"], "goal")


class BundledAssessmentTests(unittest.TestCase):
    def test_all_question_counts_complete_using_actual_distributed_content(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for count in QUESTION_COUNTS:
                with self.subTest(question_count=count):
                    service = AppService(root / str(count))
                    record = service.start_assessment("Beginner", count)
                    self.assertEqual(record["available_levels"], list(range(1, 16)))
                    while record["status"] == "in_progress":
                        if count == 500 and record["answered_count"] == 237:
                            pending = deepcopy(record["question"])
                            service.close()
                            service = AppService(root / str(count))
                            self.assertEqual(service.assessment()["question"], pending)
                            archive = root / "actual-500-partial.json"
                            service.export_data(archive)
                            service.import_data(archive)
                            record = service.assessment()
                            self.assertEqual(record["question"], pending)
                        record = service.answer_assessment(record["id"], record["question"]["correct_option_id"])
                    self.assertEqual(record["answered_count"], count)
                    self.assertEqual(len({question["word_id"] for question in record["questions"]}), count)
                    self.assertEqual(record["result"]["covered_levels"], sorted({question["level"] for question in record["questions"]}))
                    self.assertFalse(record["result"]["standardized"])
                    self.assertEqual(service.snapshot()["stats"]["mastered_count"], 0)
                    self.assertFalse(any(item["earned"] for item in service.achievements()))
                    service.close()


if __name__ == "__main__":
    unittest.main()
