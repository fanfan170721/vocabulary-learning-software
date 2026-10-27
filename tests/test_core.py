"""State transitions, counting, recovery and archive validation."""

from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from vocabulary_app.core import AppService
from vocabulary_app.storage import Store


class LearningRulesTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.content_dir = self.root / "resources"
        self.content_dir.mkdir()
        self.words = [{
            "id": f"test-{index}", "lemma": f"testword{index}", "language": "en",
            "phonetic": "/test/", "level": 2,
            "senses": [{"id": f"sense-{index}", "pos": "noun", "definition": f"测试含义{index}", "language": "zh-CN"}],
            "source": "test fixture", "license": "test-only",
        } for index in range(80)]
        self.content = {"version": "test-1", "words": self.words, "word_sets": [
            {"id": "test-set", "name": "测试词集", "kind": "test", "version": "test-1", "complete": True,
             "word_ids": [word["id"] for word in self.words[:40]]},
            {"id": "empty", "name": "空词集", "version": "test-1", "complete": True, "word_ids": []},
            {"id": "partial", "name": "不完整词集", "version": "test-1", "complete": False,
             "word_ids": [self.words[0]["id"]]},
            {"id": "missing", "name": "缺词词集", "version": "test-1", "complete": True,
             "word_ids": [self.words[0]["id"], "absent"]},
        ]}
        self.write_content()
        self.service = AppService(self.root / "data", self.content_dir)

    def tearDown(self):
        self.service.close()
        self.temporary.cleanup()

    def write_content(self):
        (self.content_dir / "content.json").write_text(json.dumps(self.content, ensure_ascii=False), encoding="utf-8")

    def reopen(self):
        self.service.close()
        self.service = AppService(self.root / "data", self.content_dir)
        return self.service

    def finish(self, session, wrong_once=()):
        wrong_once = set(wrong_once)
        while session["stage"] != "complete":
            stage = session["stage"]
            if stage == "overview":
                session = self.service.begin_learning(session["id"])
            elif stage in ("learn", "relearn"):
                session = self.service.next_word(session["id"])
            elif stage == "quiz":
                question = session["question"]
                option_id = question["correct_option_id"]
                if question["word_id"] in wrong_once and session["round_no"] == 1:
                    option_id = None
                session = self.service.answer(session["id"], option_id)
            elif stage == "round_result":
                session = self.service.continue_session(session["id"])
            else:
                self.fail(stage)
        return session

    def to_quiz(self, session):
        if session["stage"] == "overview":
            session = self.service.begin_learning(session["id"])
        while session["stage"] in ("learn", "relearn"):
            session = self.service.next_word(session["id"])
        return session

    def test_five_previously_known_only_add_fifteen_new_words(self):
        goal = self.service.configure_goal("word_count", baseline=1000, target=5000)
        session = self.service.start_session()
        for word in session["words"][:5]:
            session = self.service.mark_known(session["id"], word["id"], True)
        extra = session["words"][5]["id"]
        self.service.mark_known(session["id"], extra, True)
        session = self.service.mark_known(session["id"], extra, False)
        before = self.service.snapshot()
        self.assertEqual(before["stats"]["mastered_count"], 0)
        self.assertEqual(before["goals"][0]["numerator"], 0)
        session = self.finish(session)
        self.assertEqual(session["result"]["net_new_words"], 15)
        snapshot = self.service.snapshot()
        self.assertEqual(snapshot["stats"]["mastered_count"], 20)
        self.assertEqual(snapshot["stats"]["estimated_vocabulary"], 1015)
        self.assertEqual(snapshot["goals"][0]["id"], goal["id"])
        self.assertEqual(snapshot["goals"][0]["numerator"], 15)
        self.assertEqual(snapshot["goals"][0]["denominator"], 4000)
        self.assertAlmostEqual(snapshot["goals"][0]["ratio"], 0.00375)

    def test_half_round_reopens_at_exact_question_without_settlement(self):
        session = self.to_quiz(self.service.start_session())
        session = self.service.answer(session["id"], session["question"]["correct_option_id"])
        question = deepcopy(session["question"])
        self.reopen()
        recovered = self.service.session()
        self.assertEqual(recovered["question"], question)
        self.assertEqual(recovered["quiz_index"], 1)
        self.assertEqual(self.service.snapshot()["stats"]["mastered_count"], 0)
        self.assertEqual(self.service.snapshot()["stats"]["practice_words"], 0)
        self.assertEqual(self.service.history(), [])
        self.assertEqual(self.service.snapshot()["stats"]["achievement_practice_words"], 0)

    def test_single_wrong_word_keeps_four_options_and_error_history(self):
        session = self.to_quiz(self.service.start_session())
        wrong_word = session["question"]["word_id"]
        session = self.service.answer(session["id"], None)
        while session["stage"] == "quiz":
            session = self.service.answer(session["id"], session["question"]["correct_option_id"])
        self.assertEqual(session["stage"], "round_result")
        self.assertEqual(session["wrong_ids"], [wrong_word])
        self.assertEqual(self.service.snapshot()["stats"]["mastered_count"], 0)
        session = self.service.continue_session(session["id"])
        self.assertEqual(session["learn_ids"], [wrong_word])
        session = self.to_quiz(session)
        options = session["question"]["options"]
        self.assertEqual(len(options), 4)
        self.assertEqual(len({o["text"] for o in options}), 4)
        pool = {s["definition"] for word in session["words"] for s in word["senses"]}
        self.assertTrue({o["text"] for o in options} <= pool)
        complete = self.finish(session)
        self.assertEqual(complete["result"]["net_new_words"], 20)
        self.reopen()
        errors = self.service.mistakes()
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["id"], wrong_word)
        self.assertEqual(errors[0]["error_count"], 1)
        self.assertEqual(errors[0]["unknown_count"], 1)
        self.assertEqual(errors[0]["retry_count"], 1)
        self.assertEqual(errors[0]["answer_count"], 2)

    def test_final_settlement_is_idempotent_after_restart(self):
        session = self.finish(self.service.start_session())
        before = self.service.snapshot()["stats"]
        self.service.continue_session(session["id"])
        self.reopen()
        self.service.continue_session(session["id"])
        self.assertEqual(self.service.snapshot()["stats"], before)
        self.assertEqual(len(self.service.history()), 1)

    def test_review_uses_snapshot_and_does_not_inflate_achievements(self):
        original = self.finish(self.service.start_session())
        reviewed = self.finish(self.service.start_session(review_of=original["id"]))
        self.assertEqual(reviewed["words"], original["words"])
        self.assertNotEqual(reviewed["id"], original["id"])
        self.assertEqual(reviewed["result"]["net_new_words"], 0)
        snapshot = self.service.snapshot()
        self.assertEqual(snapshot["stats"]["practice_words"], 40)
        self.assertEqual(snapshot["stats"]["achievement_practice_words"], 20)
        self.assertEqual(snapshot["stats"]["net_new_words"], 20)

    def test_mastered_words_cannot_be_added_to_new_word_queue(self):
        completed = self.finish(self.service.start_session())
        with self.assertRaisesRegex(ValueError, "该词已掌握"):
            self.service.enqueue(completed["words"][0]["id"])
        self.assertEqual(self.service.queue(), [])

    def test_set_goal_counts_known_words_but_not_words_outside_set(self):
        goal = self.service.configure_goal("word_set", word_set_id="test-set")
        for word in self.words[:20]:
            self.service.enqueue(word["id"])
        first = self.service.start_session()
        self.service.mark_known(first["id"], self.words[0]["id"], True)
        self.finish(self.service.session(first["id"]))
        current = self.service.snapshot()["goals"][0]
        self.assertEqual(current["numerator"], 20)
        self.assertEqual(current["remaining"], 20)
        self.assertFalse(current["completed"])
        for word in self.words[40:60]:
            self.service.enqueue(word["id"])
        self.finish(self.service.start_session())
        current = self.service.snapshot()["goals"][0]
        self.assertEqual(current["numerator"], 20)
        for word in self.words[20:40]:
            self.service.enqueue(word["id"])
        self.finish(self.service.start_session())
        current = self.service.snapshot()["goals"][0]
        self.assertEqual(current["id"], goal["id"])
        self.assertEqual(current["numerator"], 40)
        self.assertEqual(current["ratio"], 1)
        self.assertTrue(current["completed"])

    def test_goal_remaining_one_does_not_complete(self):
        self.content["word_sets"].append({"id": "twenty-one", "name": "21词测试", "version": "test-1", "kind": "test", "complete": True,
                                          "word_ids": [w["id"] for w in self.words[:21]]})
        self.write_content()
        self.reopen()
        self.service.configure_goal("word_set", word_set_id="twenty-one")
        for word in self.words[:20]:
            self.service.enqueue(word["id"])
        self.finish(self.service.start_session())
        goal = self.service.snapshot()["goals"][0]
        self.assertEqual(goal["remaining"], 1)
        self.assertFalse(goal["completed"])
        self.assertLess(goal["ratio"], 1)

    def test_missing_incomplete_and_empty_sets_never_complete(self):
        for word_set in ("empty", "partial", "missing"):
            goal = self.service.configure_goal("word_set", word_set_id=word_set)
            self.assertFalse(goal["available"])
            self.assertFalse(goal["completed"])
            self.assertEqual(goal["ratio"], 0)
        goal = self.service.configure_goal("cet4")
        self.assertFalse(goal["available"])
        self.assertFalse(goal["completed"])

    def test_other_valid_meanings_are_never_distractors(self):
        self.words[0]["senses"].append({"id": "alternate", "pos": "verb", "definition": "测试含义1", "language": "zh-CN"})
        self.write_content()
        self.reopen()
        self.service.enqueue("test-0")
        self.service.enqueue("test-1")
        session = self.service.start_session()
        question = next(q for q in session["questions"] if q["word_id"] == "test-0")
        distractors = {o["text"] for o in question["options"] if o["id"] != question["correct_option_id"]}
        self.assertNotIn("测试含义1", distractors)
        self.assertNotIn("测试含义0", distractors)

    def test_content_update_does_not_rewrite_history_or_goal_version(self):
        self.service.configure_goal("word_set", word_set_id="test-set")
        original = self.finish(self.service.start_session())
        self.content["version"] = "test-2"
        self.words[0]["senses"][0]["definition"] = "新版释义"
        self.content["word_sets"][0]["version"] = "test-2"
        self.content["word_sets"][0]["word_ids"] = [word["id"] for word in self.words]
        self.write_content()
        self.reopen()
        self.assertEqual(self.service.session(original["id"])["words"], original["words"])
        self.assertEqual(self.service.snapshot()["goals"][0]["denominator"], 40)
        self.assertEqual(self.service.snapshot()["goals"][0]["word_set_version"], "test-1")

    def test_export_import_recovers_answers_and_saves_backup(self):
        first = self.service.start_session()
        self.finish(first, wrong_once=[first["words"][0]["id"]])
        unfinished = self.to_quiz(self.service.start_session())
        unfinished = self.service.answer(unfinished["id"], None)
        self.service.configure_goal("word_count", 1000, 5000)
        export_path = self.root / "archive.json"
        self.service.export_data(export_path)
        expected = self.service.snapshot()
        destination = AppService(self.root / "restored", self.content_dir)
        result = destination.import_data(export_path)
        self.assertTrue(Path(result["backup_path"]).exists())
        self.assertEqual(destination.snapshot(), expected)
        self.assertEqual(destination.mistakes(), self.service.mistakes())
        self.assertEqual(destination.session()["question"], unfinished["question"])
        destination.close()

    def test_export_preserves_queue_goal_and_history_order(self):
        self.finish(self.service.start_session())
        self.finish(self.service.start_session())
        self.service.configure_goal("word_count", 1000, 2000)
        self.service.configure_goal("word_count", 1000, 3000)
        mastered = {w["id"] for session in self.service.history() for w in session["words"]}
        remaining = [word["id"] for word in self.words if word["id"] not in mastered]
        for identifier in (remaining[2], remaining[0], remaining[1]):
            self.service.enqueue(identifier)
        before_history = [s["id"] for s in self.service.history()]
        before_goals = [g["id"] for g in self.service.snapshot()["goals"]]
        before_queue = [w["id"] for w in self.service.queue()]
        path = self.root / "ordered.json"
        self.service.export_data(path)
        destination = AppService(self.root / "ordered-destination", self.content_dir)
        destination.import_data(path)
        self.assertEqual([s["id"] for s in destination.history()], before_history)
        self.assertEqual([g["id"] for g in destination.snapshot()["goals"]], before_goals)
        self.assertEqual([w["id"] for w in destination.queue()], before_queue)
        destination.close()

    def test_active_round_progress_cannot_be_invented_by_import(self):
        session = self.to_quiz(self.service.start_session())
        self.service.answer(session["id"], None)
        path = self.root / "active.json"
        self.service.export_data(path)
        original = json.loads(path.read_text(encoding="utf-8"))
        for field, value in (("round_results", []), ("wrong_ids", [session["words"][0]["id"]]),
                             ("quiz_index", 0), ("round_no", 2)):
            data = deepcopy(original)
            record = next(r["data"] for r in data["records"] if r["kind"] == "session")
            record[field] = value
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(ValueError, msg=field):
                self.service.import_data(path)
        self.assertEqual(self.service.session()["quiz_index"], 1)

    def test_relearn_and_final_round_can_be_exported_and_resumed(self):
        session = self.to_quiz(self.service.start_session())
        session = self.service.answer(session["id"], None)
        while session["stage"] == "quiz":
            session = self.service.answer(session["id"], session["question"]["correct_option_id"])
        session = self.service.continue_session(session["id"])
        path = self.root / "relearn.json"
        self.service.export_data(path)
        self.service.import_data(path)
        self.assertEqual(self.service.session()["stage"], "relearn")
        session = self.to_quiz(self.service.session())
        session = self.service.answer(session["id"], session["question"]["correct_option_id"])
        self.service.export_data(path)
        self.service.import_data(path)
        session = self.service.continue_session(session["id"])
        self.assertEqual(session["stage"], "complete")
        self.assertEqual(session["result"]["net_new_words"], 20)

    def test_import_rejects_false_completion_foreign_mastery_and_secrets(self):
        complete = self.finish(self.service.start_session())
        path = self.root / "archive.json"
        self.service.export_data(path)
        original = json.loads(path.read_text(encoding="utf-8"))
        mutations = []
        bad = deepcopy(original)
        next(r["data"] for r in bad["records"] if r["kind"] == "mastered")["first_session"] = "nonexistent"
        mutations.append(bad)
        bad = deepcopy(original)
        next(r["data"] for r in bad["records"] if r["kind"] == "profile")["api_key"] = "must-never-import"
        mutations.append(bad)
        bad = deepcopy(original)
        session = next(r["data"] for r in bad["records"] if r["kind"] == "session")
        session["attempts"][0]["correct"] = False
        mutations.append(bad)
        bad = deepcopy(original)
        next(r["data"] for r in bad["records"] if r["kind"] == "settings")["api_key"] = "must-never-import"
        mutations.append(bad)
        bad = deepcopy(original)
        bad["schemaVersion"] = 999
        mutations.append(bad)
        bad = deepcopy(original)
        next(r["data"] for r in bad["records"] if r["kind"] == "earned")["definition"]["threshold"] = 99999
        mutations.append(bad)
        bad = deepcopy(original)
        next(r["data"] for r in bad["records"] if r["kind"] == "event")["kind"] = "invalid_event"
        mutations.append(bad)
        for bad in mutations:
            path.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaises(ValueError):
                self.service.import_data(path)
            self.assertEqual(self.service.snapshot()["stats"]["net_new_words"], 20)
            self.assertEqual(self.service.session(complete["id"])["stage"], "complete")

    def test_configured_achievement_counts_original_rounds_only(self):
        definitions = {"version": "test", "definitions": [
            {"id": "configured.first", "title": "开始", "description": "首次建轮", "metric": "started_sessions", "threshold": 1},
            {"id": "configured.twenty", "title": "20词", "description": "完成新轮次", "metric": "achievement_practice_words", "threshold": 20},
            {"id": "configured.forty", "title": "40词", "description": "完成两轮", "metric": "achievement_practice_words", "threshold": 40},
        ]}
        path = self.content_dir / "achievements.json"
        path.write_text(json.dumps(definitions), encoding="utf-8")
        first = self.service.start_session()
        earned = {item["id"] for item in self.service.achievements() if item["earned"]}
        self.assertEqual(earned, {"configured.first"})
        first = self.finish(first)
        self.finish(self.service.start_session(review_of=first["id"]))
        earned = {item["id"] for item in self.service.achievements() if item["earned"]}
        self.assertEqual(earned, {"configured.first", "configured.twenty"})
        self.finish(self.service.start_session())
        self.assertTrue(all(item["earned"] for item in self.service.achievements()))
        definitions["definitions"] = definitions["definitions"][:1]
        path.write_text(json.dumps(definitions), encoding="utf-8")
        self.assertEqual(len([a for a in self.service.achievements() if a["earned"]]), 3)

    def test_cet4_cannot_use_a_small_test_set(self):
        with self.assertRaisesRegex(ValueError, "测试词集"):
            self.service.configure_goal("cet4", word_set_id="test-set")

    def test_invalid_goal_completion_import_is_rejected(self):
        self.service.configure_goal("cet4")
        path = self.root / "archive.json"
        self.service.export_data(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        goal = next(r["data"] for r in data["records"] if r["kind"] == "goal")
        goal["completed_at"] = "2026-01-01"
        path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(ValueError):
            self.service.import_data(path)
        self.assertFalse(self.service.snapshot()["goals"][0]["completed"])

    def test_legacy_compatible_schema_is_backed_up_before_migration(self):
        legacy_path = self.root / "legacy.sqlite3"
        with sqlite3.connect(legacy_path) as connection:
            connection.execute("CREATE TABLE records(kind TEXT, id TEXT, data TEXT, PRIMARY KEY(kind,id))")
            connection.execute("INSERT INTO records VALUES('test','one','{\"value\":1}')")
        connection.close()
        store = Store(legacy_path)
        self.assertEqual(len(list((self.root / "backups").glob("before-schema-1-*.sqlite3"))), 1)
        with store.connect() as connection:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 1)
            self.assertEqual(store.get(connection, "test", "one"), {"value": 1})

    def test_invalid_or_unsupported_state_changes_are_rejected(self):
        session = self.service.start_session()
        with self.assertRaises(ValueError):
            self.service.start_session()
        with self.assertRaises(ValueError):
            self.service.continue_session(session["id"])
        with self.assertRaises(ValueError):
            self.service.answer(session["id"], None)
        with self.assertRaises(ValueError):
            self.service.update_settings(ai_enabled=True)
        self.assertFalse(self.service.snapshot()["settings"]["ai_enabled"])
        with self.assertRaises(ValueError):
            self.service.export_data(self.service.db_path)
        with self.assertRaises(ValueError):
            self.service.configure_goal("word_count", baseline=5000, target=1000)

    def test_used_pool_exhaustion_never_repeats_to_fill_twenty(self):
        self.content["words"] = self.words[:19]
        self.write_content()
        self.reopen()
        with self.assertRaisesRegex(ValueError, "不足 20"):
            self.service.start_session()
        self.assertIsNone(self.service.snapshot()["active_session"])


class BundledContentTests(unittest.TestCase):
    def test_bundled_definitions_and_multiple_rounds(self):
        with tempfile.TemporaryDirectory() as directory:
            service = AppService(directory)
            snapshot = service.snapshot()
            self.assertGreaterEqual(snapshot["content"]["word_count"], 500)
            self.assertEqual(snapshot["content"]["levels"], list(range(1, 16)))
            for level in range(1, 16):
                self.assertGreaterEqual(sum(word["level"] == level for word in service.word_catalog()), 20)
            session = service.start_session()
            achievements = {item["id"]: item for item in service.achievements()}
            self.assertTrue(achievements["twenty.first_use"]["earned"])
            self.assertFalse(achievements["twenty.practice.100"]["earned"])
            for round_index in range(3):
                if round_index:
                    session = service.start_session()
                if session["stage"] == "overview":
                    session = service.begin_learning(session["id"])
                while session["stage"] != "complete":
                    if session["stage"] in ("learn", "relearn"):
                        session = service.next_word(session["id"])
                    elif session["stage"] == "quiz":
                        session = service.answer(session["id"], session["question"]["correct_option_id"])
                    else:
                        session = service.continue_session(session["id"])
            self.assertEqual(service.snapshot()["stats"]["mastered_count"], 60)
            self.assertEqual(service.snapshot()["stats"]["achievement_practice_words"], 60)
            self.assertFalse(next(a for a in service.achievements() if a["id"] == "twenty.practice.100")["earned"])
            service.close()


if __name__ == "__main__":
    unittest.main()
