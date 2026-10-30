"""Learning rules independent of the desktop UI and speech engine."""

from __future__ import annotations

from copy import deepcopy
from contextlib import nullcontext
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import random
import re
import unicodedata
import uuid

from .storage import SCHEMA_VERSION, Store
from . import assessment as assessment_rules


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id() -> str:
    return str(uuid.uuid4())


def _meaning_tokens(text: str) -> set[str]:
    return {re.sub(r"\s+", "", part).casefold() for part in
            re.split(r"[;\uff1b,\uff0c\u3001/\uff08\uff09()\n]", text) if part.strip()}


@lru_cache(maxsize=1)
def _legacy_english_texts():
    path = Path(__file__).parent / "resources" / "legacy_english_texts.json"
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else {}


@lru_cache(maxsize=16384)
def _localized_text(text):
    return _legacy_english_texts().get(hashlib.sha256(text.encode("utf-8")).hexdigest(), text)


def localize_record(data):
    """Translate stock legacy display text without rewriting historical evidence."""
    if isinstance(data, str):
        return _localized_text(data)
    if isinstance(data, list):
        return [localize_record(value) for value in data]
    if isinstance(data, dict):
        result = {key: value if key == "name" and "self_rating" in data else localize_record(value)
                  for key, value in data.items()}
        if "definition" in data and result["definition"] != data["definition"]:
            result["language"] = "en"
        if "self_rating" in result:
            result["self_rating"] = assessment_rules.normalize_rating(result["self_rating"])
        if result.get("choice_text") == assessment_rules.LEGACY_UNKNOWN_ANSWER:
            result["choice_text"] = assessment_rules.UNKNOWN_ANSWER
        title = result.get("title")
        if isinstance(title, str):
            match = re.fullmatch(r"\u638c\u63e1 (\d+) \u8bcd", title)
            if match:
                result["title"] = f"Master {match[1]} words"
        return result
    return deepcopy(data)


def _with_onboarding_defaults(profile, has_learning_records):
    profile = deepcopy(profile)
    profile["self_rating"] = assessment_rules.normalize_rating(profile.get("self_rating", "Beginner"))
    if profile.get("name") == "\u5b66\u4e60\u8005":
        profile["name"] = "Learner"
    profile.update(interface_language="en", meaning_language="en")
    confidence_labels = {"\u672a\u77e5": "Unknown", "\u8f83\u4f4e": "Low", "\u4e00\u822c": "Moderate"}
    for ability in profile.get("abilities", {}).values():
        if isinstance(ability, dict) and ability.get("confidence") in confidence_labels:
            ability["confidence"] = confidence_labels[ability["confidence"]]
    if "onboarding_complete" not in profile:
        profile["onboarding_complete"] = has_learning_records
        profile["onboarding_step"] = "complete" if has_learning_records else "self_rating"
    profile.setdefault("onboarding_step", "complete" if profile["onboarding_complete"] else "self_rating")
    profile.setdefault("onboarding_assessment_id", None)
    profile.setdefault("estimate_source", "self_report" if profile["onboarding_complete"] else "unset")
    return profile


class AppService:
    """One local profile and its versioned learning records."""

    def __init__(self, data_dir=None, content_dir=None):
        self.data_dir = Path(data_dir) if data_dir is not None else (
            Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local" / "share"))
            / "VocabularyLearning"
        )
        self.content_dir = Path(content_dir) if content_dir else Path(__file__).parent / "resources"
        self.content = json.loads((self.content_dir / "content.json").read_text(encoding="utf-8-sig"))
        self._validate_content(self.content)
        self.words = {word["id"]: word for word in self.content["words"]}
        self.db_path = self.data_dir / "learning.sqlite3"
        self.store = Store(self.db_path)
        with self.store.transaction() as connection:
            if not self.store.get(connection, "profile", "local"):
                self.store.put(connection, "profile", "local", {
                    "id": "local", "name": "Learner", "self_rating": "Beginner", "difficulty": 2,
                    "estimated_vocabulary": 0, "estimate_new_baseline": 0, "onboarding_complete": False,
                    "onboarding_step": "self_rating", "onboarding_assessment_id": None, "estimate_source": "unset",
                    "interface_language": "en", "meaning_language": "en",
                    "learning_language": "en", "updated_at": now(),
                    "abilities": {key: {"value": None, "confidence": "Unknown", "evidence": 0}
                                  for key in ("recognition", "active_use", "reading", "writing", "listening", "speaking")},
                })
                self.store.put(connection, "settings", "local", {
                    "id": "local", "network_mode": "offline", "ai_enabled": False,
                    "reduced_motion": False, "english_variant": "en-US", "speak_chinese": False,
                })
            else:
                profile = self._profile(connection)
                self.store.put(connection, "profile", "local", profile)

    @staticmethod
    def _validate_content(content):
        if not isinstance(content, dict) or not isinstance(content.get("version"), str):
            raise ValueError("The vocabulary pack is missing version information.")
        words = content.get("words")
        if not isinstance(words, list) or not words:
            raise ValueError("The vocabulary pack has no usable entries.")
        ids, lemmas = set(), set()
        for word in words:
            if not isinstance(word, dict):
                raise ValueError("The vocabulary entry format is invalid.")
            identifier, lemma = word.get("id"), word.get("lemma")
            if not isinstance(identifier, str) or not identifier or identifier in ids:
                raise ValueError("Vocabulary entry IDs must be nonempty and unique.")
            key = (word.get("language", "en"), unicodedata.normalize("NFKC", str(lemma)).strip().casefold())
            if not isinstance(lemma, str) or not lemma.strip() or lemma != lemma.strip() or key in lemmas:
                raise ValueError("Duplicate lemmas in the same language cannot count as separate entries.")
            if type(word.get("level")) is not int or not 1 <= word["level"] <= 15:
                raise ValueError("Vocabulary entry difficulty must be between L1 and L15.")
            senses = word.get("senses")
            if not isinstance(senses, list) or not senses:
                raise ValueError("Each vocabulary entry needs at least one sense.")
            for sense in senses:
                if not isinstance(sense, dict) or not all(
                    isinstance(sense.get(field), str) and sense[field].strip()
                    for field in ("id", "pos", "definition")
                ):
                    raise ValueError("A word sense is missing its ID, part of speech, or definition.")
            if len({s["id"] for s in senses}) != len(senses):
                raise ValueError("Sense IDs must be unique within each vocabulary entry.")
            ids.add(identifier)
            lemmas.add(key)
        if not isinstance(content.get("word_sets", []), list):
            raise ValueError("The target word set format is invalid.")

    def close(self):
        """Connections are scoped to each operation; retained for caller convenience."""

    def _profile(self, connection):
        profile = self.store.get(connection, "profile", "local")
        if profile:
            used = connection.execute(
                "SELECT 1 FROM records WHERE kind IN ('session','goal','mastered','earned') LIMIT 1"
            ).fetchone() is not None
            profile = _with_onboarding_defaults(profile, used)
        return profile

    def _stats(self, connection):
        mastered = self.store.all(connection, "mastered")
        complete = [s for s in self.store.all(connection, "session") if s["stage"] == "complete"]
        net = sum(bool(word.get("net_new")) for word in mastered)
        profile = self._profile(connection)
        return {
            "estimated_vocabulary": profile["estimated_vocabulary"] + max(0, net - profile.get("estimate_new_baseline", 0)),
            "mastered_count": len(mastered), "net_new_words": net,
            "practice_words": sum(len(s["words"]) for s in complete),
            "completed_sessions": len(complete),
            "achievement_practice_words": sum(len(s["words"]) for s in complete if not s.get("review_of")),
        }

    def snapshot(self):
        with self.store.connect() as connection:
            sessions = self.store.all(connection, "session")
            active = next((s for s in sessions if s["stage"] != "complete"), None)
            return localize_record({
                "profile": self._profile(connection),
                "settings": self.store.get(connection, "settings", "local"),
                "stats": self._stats(connection), "active_session": self._present(active),
                "active_assessment": next((self._present_assessment(a) for a in reversed(self.store.all(connection, "assessment")) if a["status"] == "in_progress"), None),
                "goals": [self._goal_view(connection, goal) for goal in self.store.all(connection, "goal")],
                "achievements": self._achievements(connection),
                "content": {"version": self.content["version"], "word_count": len(self.words),
                            "levels": sorted({w["level"] for w in self.words.values()}),
                            "word_sets": deepcopy(self.content.get("word_sets", []))},
            })

    def update_profile(self, **kwargs):
        allowed = {"name", "self_rating", "difficulty", "estimated_vocabulary", "onboarding_complete"}
        if set(kwargs) - allowed:
            raise ValueError("Unsupported profile field.")
        with self.store.transaction() as connection:
            profile = self._profile(connection)
            if "name" in kwargs:
                name = kwargs["name"]
                if not isinstance(name, str) or not 1 <= len(name.strip()) <= 60:
                    raise ValueError("Enter a name containing 1 to 60 characters.")
                profile["name"] = name.strip()
            if "self_rating" in kwargs:
                value = assessment_rules.normalize_rating(kwargs["self_rating"])
                if value not in assessment_rules.RATINGS:
                    raise ValueError("Choose one of the available self-ratings.")
                profile["self_rating"] = value
            if "difficulty" in kwargs:
                if type(kwargs["difficulty"]) is not int or not 1 <= kwargs["difficulty"] <= 15:
                    raise ValueError("Difficulty must be between L1 and L15.")
                profile["difficulty"] = kwargs["difficulty"]
            if "estimated_vocabulary" in kwargs:
                value = kwargs["estimated_vocabulary"]
                if type(value) is not int or not 0 <= value <= 1000000:
                    raise ValueError("Estimated vocabulary must be an integer from 0 to 1,000,000.")
                if value != profile["estimated_vocabulary"]:
                    if self._stats(connection)["completed_sessions"] or self.store.all(connection, "goal"):
                        raise ValueError("Learning records or goals already exist. This version cannot reset the estimated baseline because doing so would affect existing goals.")
                    profile["estimated_vocabulary"] = value
            if "onboarding_complete" in kwargs:
                if type(kwargs["onboarding_complete"]) is not bool:
                    raise ValueError("The starting-point setup status must be a boolean.")
                profile["onboarding_complete"] = kwargs["onboarding_complete"]
                profile["onboarding_step"] = "complete" if kwargs["onboarding_complete"] else "self_rating"
            profile["updated_at"] = now()
            self.store.put(connection, "profile", "local", profile)
            return deepcopy(profile)

    def _level_config(self):
        path = self.content_dir / "levels.json"
        return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else {}

    def set_onboarding_rating(self, self_rating, name=None, use_assessment=True):
        self_rating = assessment_rules.normalize_rating(self_rating)
        if self_rating not in assessment_rules.RATINGS or type(use_assessment) is not bool:
            raise ValueError("Choose one of the available self-ratings.")
        if name is not None and (not isinstance(name, str) or not 1 <= len(name.strip()) <= 60):
            raise ValueError("Enter a name containing 1 to 60 characters.")
        with self.store.transaction() as connection:
            profile = self._profile(connection)
            if profile.get("onboarding_complete"):
                raise ValueError("Initial profile setup is complete. Change your self-rating in Settings or take another assessment.")
            profile["self_rating"] = self_rating
            if name is not None:
                profile["name"] = name.strip()
            config = self._level_config()
            profile["difficulty"] = next((item["level"] for item in config.get("self_ratings", []) if item.get("label") == self_rating),
                                         assessment_rules.RATING_LEVELS[assessment_rules.RATINGS.index(self_rating)])
            profile["onboarding_step"] = "assessment" if use_assessment else "goal"
            profile["onboarding_assessment_id"] = None
            profile["updated_at"] = now()
            self.store.put(connection, "profile", "local", profile)
            return deepcopy(profile)

    @staticmethod
    def _assessment_question(words, word_id):
        return AppService._questions({"words": words, "round_no": 1}, [word_id])[0]

    def start_assessment(self, self_rating, question_count=20):
        self_rating = assessment_rules.normalize_rating(self_rating)
        with self.store.transaction() as connection:
            profile = self._profile(connection)
            pending = next((a for a in reversed(self.store.all(connection, "assessment")) if a["status"] == "in_progress"), None)
            if pending:
                if pending["question_count"] != question_count:
                    raise ValueError(f"An unfinished {pending['question_count']}-question assessment exists. Resume it first.")
                if not profile.get("onboarding_complete"):
                    profile.update(onboarding_assessment_id=pending["id"], onboarding_step="assessment")
                    self.store.put(connection, "profile", "local", profile)
                return self._present_assessment(pending)
            record = assessment_rules.create(list(self.words.values()), self.content["version"], self_rating, question_count,
                                             self._level_config(), self._assessment_question, now())
            self.store.put(connection, "assessment", record["id"], record)
            if not profile.get("onboarding_complete"):
                profile.update(onboarding_assessment_id=record["id"], onboarding_step="assessment", self_rating=self_rating)
                self.store.put(connection, "profile", "local", profile)
            return self._present_assessment(record)

    @staticmethod
    def _present_assessment(record):
        if record is None:
            return None
        result = localize_record(record)
        if record["status"] == "complete":
            result["result"] = assessment_rules.estimate(record)
        return result

    def assessment(self, assessment_id=None):
        with self.store.connect() as connection:
            if assessment_id:
                record = self.store.get(connection, "assessment", assessment_id)
                if record is None:
                    raise ValueError("The assessment record was not found.")
                return self._present_assessment(record)
            records = self.store.all(connection, "assessment")
            profile = self._profile(connection)
            linked = self.store.get(connection, "assessment", profile.get("onboarding_assessment_id", ""))
            if linked and (not profile.get("onboarding_complete") or linked["status"] == "in_progress"):
                return self._present_assessment(linked)
            return self._present_assessment(next((a for a in reversed(records) if a["status"] == "in_progress"), records[-1] if records else None))

    def answer_assessment(self, assessment_id, option_id=None):
        with self.store.transaction() as connection:
            record = self.store.get(connection, "assessment", assessment_id)
            if record is None:
                raise ValueError("The assessment record was not found.")
            updated = assessment_rules.answer(record, option_id, self._assessment_question, now())
            self.store.put(connection, "assessment", assessment_id, updated)
            profile = self._profile(connection)
            if not profile.get("onboarding_complete") and profile.get("onboarding_assessment_id") == assessment_id and updated["status"] == "complete":
                profile["onboarding_step"] = "assessment_result"
                self.store.put(connection, "profile", "local", profile)
            return self._present_assessment(updated)

    def accept_assessment(self, assessment_id):
        with self.store.transaction() as connection:
            record = self.store.get(connection, "assessment", assessment_id)
            if record is None or record["status"] != "complete":
                raise ValueError("Complete the assessment before adopting its recommended difficulty.")
            profile = self._profile(connection)
            result = assessment_rules.estimate(record)
            profile["difficulty"] = result["recommended_level"]
            profile["difficulty_assessment_id"] = assessment_id
            profile["last_assessment_id"] = assessment_id
            profile.setdefault("abilities", {})["recognition"] = {
                "value": result["recommended_level"], "confidence": result["confidence"],
                "evidence": record["answered_count"], "assessment_id": assessment_id,
                "scale": "internal_content_level", "standardized": False, "updated_at": now(),
            }
            if not profile.get("onboarding_complete"):
                profile["onboarding_step"] = "goal"
                profile["onboarding_assessment_id"] = assessment_id
            profile["updated_at"] = now()
            self.store.put(connection, "profile", "local", profile)
            return deepcopy(profile)

    def finish_onboarding(self, kind="word_count", baseline=0, target=5000, word_set_id=None):
        if type(baseline) is not int or not 0 <= baseline <= 1000000:
            raise ValueError("Confirm a starting vocabulary count that is an integer from 0 to 1,000,000.")
        with self.store.transaction() as connection:
            profile = self._profile(connection)
            if profile.get("onboarding_complete"):
                raise ValueError("Initial setup is complete. Add goals on the Goals page to retain your existing learning records.")
            if profile.get("onboarding_step") != "goal":
                raise ValueError("Complete your self-rating, or finish an assessment and confirm its recommended difficulty first.")
            goal = self._configure_goal(connection, kind, baseline, target, word_set_id)
            profile = self._profile(connection)
            linked = self.store.get(connection, "assessment", profile.get("onboarding_assessment_id", ""))
            profile.update(onboarding_complete=True, onboarding_step="complete", onboarding_goal_id=goal["id"],
                           estimated_vocabulary=baseline, estimate_new_baseline=self._stats(connection)["net_new_words"],
                           estimate_source="user_confirmed_assessment" if linked else "self_report", updated_at=now())
            if linked:
                profile["estimate_assessment_id"] = linked["id"]
            self.store.put(connection, "profile", "local", profile)
        return self.snapshot()

    def update_settings(self, **kwargs):
        allowed = {"network_mode", "ai_enabled", "reduced_motion", "english_variant", "speak_chinese"}
        if set(kwargs) - allowed:
            raise ValueError("Unsupported settings field.")
        if kwargs.get("ai_enabled"):
            raise ValueError("AI is not connected in this version. Regular study is available offline.")
        if "network_mode" in kwargs and kwargs["network_mode"] not in ("offline", "auto", "online_first"):
            raise ValueError("Choose Offline, Automatic, or Online first.")
        for field in ("ai_enabled", "reduced_motion", "speak_chinese"):
            if field in kwargs and type(kwargs[field]) is not bool:
                raise ValueError("Toggle values must be booleans.")
        if kwargs.get("speak_chinese"):
            raise ValueError("This version only pronounces headwords; definition narration is unavailable.")
        if "english_variant" in kwargs and kwargs["english_variant"] not in ("en-US", "en-GB"):
            raise ValueError("Only British and American English accents are supported.")
        with self.store.transaction() as connection:
            settings = self.store.get(connection, "settings", "local")
            settings.update(kwargs)
            settings["ai_enabled"] = False
            self.store.put(connection, "settings", "local", settings)
            return deepcopy(settings)

    def configure_goal(self, kind, baseline=1000, target=5000, word_set_id=None):
        return self._configure_goal(None, kind, baseline, target, word_set_id)

    def _configure_goal(self, connection, kind, baseline=1000, target=5000, word_set_id=None):
        kind = {"count": "word_count", "cet-4": "cet4", "cet_4": "cet4"}.get(kind, kind)
        if kind not in ("word_count", "word_set", "cet4"):
            raise ValueError("The goal type must be a word count or a specific word set.")
        with (self.store.transaction() if connection is None else nullcontext(connection)) as connection:
            goal = {"id": new_id(), "kind": kind, "created_at": now(), "completed_at": None,
                    "threshold": 1, "baseline_new_words": self._stats(connection)["net_new_words"]}
            if kind == "word_count":
                if type(baseline) is not int or type(target) is not int or not 0 <= baseline < target <= 1000000:
                    raise ValueError("The target word count must exceed the baseline and be no greater than 1,000,000.")
                goal.update(baseline=baseline, target=target, title=f"Master {target} words")
                if not self._stats(connection)["completed_sessions"] and not self.store.all(connection, "goal"):
                    profile = self._profile(connection)
                    profile["estimated_vocabulary"] = baseline
                    self.store.put(connection, "profile", "local", profile)
            else:
                sets = self.content.get("word_sets", [])
                selected = next((s for s in sets if s.get("id") == word_set_id), None) if word_set_id else None
                if selected is None and kind == "cet4":
                    selected = next((s for s in sets if s.get("kind") in ("cet4", "cet-4", "CET-4")), None)
                selected = deepcopy(selected or {"id": word_set_id or "cet4", "name": "CET-4" if kind == "cet4" else "Specific word set",
                                                  "version": "", "complete": False, "kind": "cet4" if kind == "cet4" else "custom", "word_ids": []})
                if kind == "cet4" and selected.get("kind") not in ("cet4", "cet-4", "CET-4"):
                    raise ValueError("A test word set cannot be used as an official CET-4 goal.")
                ids = selected.get("word_ids", [])
                if not isinstance(ids, list) or any(not isinstance(i, str) for i in ids):
                    raise ValueError("The target word set format is invalid.")
                ids = list(dict.fromkeys(ids))
                goal.update(word_set_id=selected["id"], word_set_version=selected.get("version", ""),
                            word_ids=ids, target=len(ids), baseline=0,
                            loaded_complete=bool(selected.get("complete") and selected.get("version") and ids and all(i in self.words for i in ids)),
                            title=selected.get("name", "Specific word set"),
                            word_set_metadata=deepcopy(selected),
                            word_snapshots=[deepcopy(self.words[i]) for i in ids if i in self.words])
            for old in self.store.all(connection, "goal"):
                equivalent = (old["kind"] == goal["kind"] and old.get("baseline") == goal.get("baseline")
                              and old.get("target") == goal.get("target") and old.get("word_set_id") == goal.get("word_set_id")
                              and old.get("word_set_version") == goal.get("word_set_version")
                              and old.get("baseline_new_words") == goal.get("baseline_new_words"))
                if equivalent:
                    return self._goal_view(connection, old)
            self.store.put(connection, "goal", goal["id"], goal)
            self._refresh_goals(connection)
            return self._goal_view(connection, self.store.get(connection, "goal", goal["id"]))

    def _goal_view(self, connection, goal):
        view = deepcopy(goal)
        mastered = {w["id"] for w in self.store.all(connection, "mastered")}
        if goal["kind"] == "word_count":
            numerator = max(0, self._stats(connection)["net_new_words"] - goal["baseline_new_words"])
            denominator = goal["target"] - goal["baseline"]
            view.update(current=goal["baseline"] + numerator, available=True,
                        remaining=max(0, denominator - numerator), message="Counts distinct newly learned words after the baseline")
        else:
            ids = set(goal["word_ids"])
            numerator, denominator = len(mastered & ids), len(ids)
            available = bool(goal.get("loaded_complete") and denominator)
            view.update(current=numerator, available=available, remaining=max(0, denominator - numerator),
                        remaining_words=[word for word in goal.get("word_snapshots", []) if word["id"] not in mastered],
                        message="Measures vocabulary coverage for this version of the word set; it does not guarantee passing the exam" if available else "A complete licensed word list must be installed before progress can be calculated")
        view.update(numerator=numerator, denominator=denominator,
                    ratio=min(1.0, numerator / denominator) if denominator and view["available"] else 0.0,
                    completed=bool(goal.get("completed_at")))
        return localize_record(view)

    def _refresh_goals(self, connection):
        for goal in self.store.all(connection, "goal"):
            view = self._goal_view(connection, goal)
            if view["available"] and view["denominator"] > 0 and view["numerator"] >= view["denominator"] and not goal.get("completed_at"):
                goal["completed_at"] = now()
                self.store.put(connection, "goal", goal["id"], goal)
                self.store.put(connection, "event", "goal:" + goal["id"], {
                    "id": "goal:" + goal["id"], "kind": "goal_completed", "goal_id": goal["id"], "at": now()})

    def word_catalog(self):
        return deepcopy(list(self.words.values()))

    def queue(self):
        with self.store.connect() as connection:
            return [deepcopy(self.words[item["id"]]) for item in self.store.all(connection, "queue") if item["id"] in self.words]

    def enqueue(self, word_id):
        if word_id not in self.words:
            raise ValueError("The vocabulary entry was not found.")
        with self.store.transaction() as connection:
            if self.store.get(connection, "mastered", word_id):
                raise ValueError("This word is already mastered. Retry its original session from Study history.")
            self.store.put(connection, "queue", word_id, {"id": word_id, "added_at": now()})
        return self.queue()

    def remove_from_queue(self, word_id):
        with self.store.transaction() as connection:
            self.store.delete(connection, "queue", word_id)
        return self.queue()

    def start_session(self, review_of=None):
        with self.store.transaction() as connection:
            if any(s["stage"] != "complete" for s in self.store.all(connection, "session")):
                raise ValueError("An unfinished session exists. Resume it first.")
            mastered = {w["id"] for w in self.store.all(connection, "mastered")}
            if review_of:
                old = self.store.get(connection, "session", review_of)
                if not old or old["stage"] != "complete":
                    raise ValueError("Only completed sessions can be retried.")
                words = deepcopy(old["words"])
            else:
                difficulty = self._profile(connection)["difficulty"]
                target_ids = set()
                for goal in self.store.all(connection, "goal"):
                    if goal.get("loaded_complete") and not goal.get("completed_at"):
                        target_ids.update(set(goal.get("word_ids", [])) - mastered)
                queued = [q["id"] for q in self.store.all(connection, "queue") if q["id"] in self.words and q["id"] not in mastered]
                candidates = [w for w in self.words.values() if w["id"] not in mastered and abs(w["level"] - difficulty) <= 1]
                random.SystemRandom().shuffle(candidates)
                candidates.sort(key=lambda w: (0 if w["id"] in queued else 1 if w["id"] in target_ids else 2,
                                               queued.index(w["id"]) if w["id"] in queued else abs(w["level"] - difficulty)))
                ordered = list(dict.fromkeys(queued + [w["id"] for w in candidates]))
                if len(ordered) < 20:
                    raise ValueError(f"Only {len(ordered)} unlearned words remain near the current difficulty; at least 20 are required. Change the difficulty, expand the vocabulary pack, or retry a previous session.")
                words = deepcopy([self.words[identifier] for identifier in ordered[:20]])
            ids = [word["id"] for word in words]
            session = {"id": new_id(), "stage": "overview", "words": words, "known_before": [],
                       "prior_mastered": sorted(mastered & set(ids)), "learn_ids": ids, "learn_index": 0,
                       "quiz_ids": ids, "quiz_index": 0, "round_no": 1, "round_results": [],
                       "wrong_ids": [], "result": {}, "attempts": [], "review_of": review_of,
                       "created_at": now(), "completed_at": None, "content_version": self.content["version"],
                       "word_stats": {identifier: {"answer_count": 0, "error_count": 0, "unknown_count": 0, "retry_count": 0} for identifier in ids}}
            session["questions"] = self._questions(session, ids)
            self.store.put(connection, "session", session["id"], session)
            self._award_achievements(connection)
            return self._present(session)

    @staticmethod
    def _questions(session, ids):
        words = {w["id"]: w for w in session["words"]}
        pool = [(word, sense) for word in session["words"] for sense in word["senses"]]
        questions = []
        rng = random.SystemRandom()
        for identifier in ids:
            word = words[identifier]
            sense = word["senses"][0]
            forbidden = set().union(*(_meaning_tokens(s["definition"]) for s in word["senses"]))
            synonym_groups = {s["synonym_group"] for s in word["senses"] if s.get("synonym_group")}
            candidates = list(pool)
            rng.shuffle(candidates)
            options = [{"id": new_id(), "text": sense["definition"]}]
            seen = set(forbidden)
            for candidate_word, candidate_sense in candidates:
                tokens = _meaning_tokens(candidate_sense["definition"])
                same_group = candidate_sense.get("synonym_group") in synonym_groups
                if candidate_word["id"] == identifier or tokens & seen or same_group:
                    continue
                options.append({"id": new_id(), "text": candidate_sense["definition"]})
                seen.update(tokens)
                if len(options) == 4:
                    break
            if len(options) != 4:
                raise ValueError(f"Four distinct answer options for {word['lemma']} cannot be formed from this session. Update the vocabulary pack or choose another session.")
            correct_id = options[0]["id"]
            rng.shuffle(options)
            questions.append({"id": new_id(), "word_id": identifier, "lemma": word["lemma"],
                              "sense_id": sense["id"], "pos": sense["pos"], "prompt": "Choose the definition that matches this part of speech",
                              "options": options, "correct_option_id": correct_id, "round_no": session["round_no"]})
        return questions

    @staticmethod
    def _present(session):
        if session is None:
            return None
        result = deepcopy(session)
        result["question"] = (deepcopy(session["questions"][session["quiz_index"]])
                              if session["stage"] == "quiz" and session["quiz_index"] < len(session["questions"]) else None)
        lookup = {w["id"]: w for w in session["words"]}
        result["current_word"] = (deepcopy(lookup[session["learn_ids"][session["learn_index"]]])
                                  if session["stage"] in ("learn", "relearn") and session["learn_index"] < len(session["learn_ids"]) else None)
        return localize_record(result)

    def _get_session(self, connection, session_id=None):
        if session_id:
            result = self.store.get(connection, "session", session_id)
        else:
            result = next((s for s in reversed(self.store.all(connection, "session")) if s["stage"] != "complete"), None)
        if result is None:
            raise ValueError("The study session was not found.")
        return result

    def session(self, session_id=None):
        with self.store.connect() as connection:
            return self._present(self._get_session(connection, session_id))

    def mark_known(self, session_id, word_id, known):
        with self.store.transaction() as connection:
            session = self._get_session(connection, session_id)
            if session["stage"] != "overview" or word_id not in {w["id"] for w in session["words"]} or type(known) is not bool:
                raise ValueError("Already-known marks can only be changed in the session overview.")
            marked = set(session["known_before"])
            marked.add(word_id) if known else marked.discard(word_id)
            session["known_before"] = sorted(marked)
            self.store.put(connection, "session", session_id, session)
            return self._present(session)

    def begin_learning(self, session_id):
        with self.store.transaction() as connection:
            session = self._get_session(connection, session_id)
            if session["stage"] != "overview":
                raise ValueError("This session has already started.")
            session["stage"] = "learn"
            self.store.put(connection, "session", session_id, session)
            return self._present(session)

    def next_word(self, session_id):
        with self.store.transaction() as connection:
            session = self._get_session(connection, session_id)
            if session["stage"] not in ("learn", "relearn"):
                raise ValueError("The session is not currently in the word-by-word study stage.")
            session["learn_index"] += 1
            if session["learn_index"] == len(session["learn_ids"]):
                session["stage"] = "quiz"
                session["quiz_index"] = 0
            self.store.put(connection, "session", session_id, session)
            return self._present(session)

    def answer(self, session_id, option_id=None):
        with self.store.transaction() as connection:
            session = self._get_session(connection, session_id)
            if session["stage"] != "quiz":
                raise ValueError("No question is waiting for an answer.")
            question = session["questions"][session["quiz_index"]]
            choices = {o["id"]: o["text"] for o in question["options"]}
            if option_id is not None and option_id not in choices:
                raise ValueError("The question has changed. Answer the current question.")
            correct = option_id == question["correct_option_id"]
            identifier = question["word_id"]
            attempt = {"id": new_id(), "question_id": question["id"], "word_id": identifier,
                       "sense_id": question["sense_id"], "round_no": session["round_no"],
                       "option_id": option_id, "correct": correct, "kind": "correct" if correct else "unknown" if option_id is None else "wrong",
                       "choice_text": choices.get(option_id, assessment_rules.UNKNOWN_ANSWER), "answer_text": choices[question["correct_option_id"]], "at": now(),
                       "question": deepcopy(question)}
            session["attempts"].append(attempt)
            session["round_results"].append(deepcopy(attempt))
            counts = session["word_stats"][identifier]
            counts["answer_count"] += 1
            counts["error_count"] += int(not correct)
            counts["unknown_count"] += int(option_id is None)
            counts["retry_count"] += int(session["round_no"] > 1)
            session["quiz_index"] += 1
            if session["quiz_index"] == len(session["quiz_ids"]):
                session["stage"] = "round_result"
                session["wrong_ids"] = [a["word_id"] for a in session["round_results"] if not a["correct"]]
            self.store.put(connection, "session", session_id, session)
            return self._present(session)

    def continue_session(self, session_id):
        with self.store.transaction() as connection:
            session = self._get_session(connection, session_id)
            if session["stage"] == "complete":
                return self._present(session)
            if session["stage"] != "round_result":
                raise ValueError("Complete the current quiz first.")
            if session["wrong_ids"]:
                session["stage"] = "relearn"
                session["round_no"] += 1
                session["learn_ids"] = list(session["wrong_ids"])
                session["learn_index"] = 0
                session["quiz_ids"] = list(session["wrong_ids"])
                session["quiz_index"] = 0
                session["round_results"] = []
                session["questions"] = self._questions(session, session["quiz_ids"])
            else:
                self._finalize(connection, session)
            self.store.put(connection, "session", session_id, session)
            if session["stage"] == "complete":
                self._refresh_goals(connection)
                self._award_achievements(connection)
            return self._present(session)

    def _finalize(self, connection, session):
        event_id = "complete:" + session["id"]
        if self.store.get(connection, "event", event_id):
            raise ValueError("The session completion records are inconsistent. Restore from a backup.")
        if not session["round_results"] or any(not a["correct"] for a in session["round_results"]):
            raise ValueError("The session cannot be completed while some words remain unpassed.")
        latest = {a["word_id"]: a["correct"] for a in session["attempts"]}
        if len(latest) != 20 or not all(latest.values()):
            raise ValueError("Complete the quiz for all 20 words.")
        new_words = []
        for word in session["words"]:
            old = self.store.get(connection, "mastered", word["id"])
            if old is None:
                learned = word["id"] not in session["known_before"] and not session.get("review_of")
                record = {"id": word["id"], "word": deepcopy(word), "net_new": learned,
                          "source": "known_before" if word["id"] in session["known_before"] else "learning",
                          "first_session": session["id"], "mastered_at": now()}
                self.store.put(connection, "mastered", word["id"], record)
                if learned:
                    new_words.append(word["id"])
            self.store.delete(connection, "queue", word["id"])
        session["stage"] = "complete"
        session["completed_at"] = now()
        session["result"] = {
            "net_new_words": len(new_words), "new_word_ids": new_words,
            "known_before_count": len(session["known_before"]), "practice_words": 20,
            "achievement_practice_words": 0 if session.get("review_of") else 20,
            "error_count": sum(v["error_count"] for v in session["word_stats"].values()),
            "retry_count": sum(v["retry_count"] for v in session["word_stats"].values()),
            "unknown_count": sum(v["unknown_count"] for v in session["word_stats"].values()),
            "ever_wrong_ids": [identifier for identifier, v in session["word_stats"].items() if v["error_count"]],
        }
        self.store.put(connection, "event", event_id, {"id": event_id, "kind": "session_completed", "session_id": session["id"], "at": now()})

    def _achievement_definitions(self):
        path = self.content_dir / "achievements.json"
        if path.exists():
            raw = json.loads(path.read_text(encoding="utf-8-sig"))
            definitions = raw if isinstance(raw, list) else raw.get("definitions", raw.get("achievements", []))
            if definitions:
                return definitions
        return [{"id": "first_use", "title": "First session", "description": "Start your first study session", "threshold": 1, "metric": "started_sessions"}] + [
            {"id": f"practice_{n}", "title": f"Practice {n} words", "description": "Accumulates completed new sessions; retries of previous sessions do not count", "threshold": n, "metric": "achievement_practice_words"}
            for n in (100, 200, 500, 1000, 2000, 3000)]

    def _award_achievements(self, connection):
        practice = self._stats(connection)["achievement_practice_words"]
        started = len(self.store.all(connection, "session"))
        for definition in self._achievement_definitions():
            threshold = definition.get("threshold", 0)
            metric = definition.get("metric", "achievement_practice_words")
            progress = started if metric == "started_sessions" else practice if metric == "achievement_practice_words" else -1
            if type(threshold) is int and threshold > 0 and progress >= threshold and not self.store.get(connection, "earned", definition["id"]):
                self.store.put(connection, "earned", definition["id"], {
                    "id": definition["id"], "earned_at": now(), "definition": deepcopy(definition)})

    def _achievements(self, connection):
        earned = {item["id"]: item for item in self.store.all(connection, "earned")}
        result = []
        for definition in self._achievement_definitions():
            item = deepcopy(definition)
            record = earned.get(item["id"])
            item.update(earned=bool(record), earned_at=record.get("earned_at") if record else None)
            result.append(item)
        shown = {item["id"] for item in result}
        for identifier, record in earned.items():
            if identifier not in shown and record.get("definition"):
                item = deepcopy(record["definition"])
                item.update(earned=True, earned_at=record["earned_at"])
                result.append(item)
        return localize_record(result)

    def achievements(self):
        with self.store.connect() as connection:
            return self._achievements(connection)

    def history(self):
        with self.store.connect() as connection:
            return [self._present(s) for s in reversed(self.store.all(connection, "session")) if s["stage"] == "complete"]

    def mistakes(self):
        aggregate = {}
        for session in reversed(self.history()):
            for word in session["words"]:
                counts = session["word_stats"][word["id"]]
                entry = aggregate.setdefault(word["id"], {
                    "id": word["id"], "word": deepcopy(word), "answer_count": 0,
                    "error_count": 0, "unknown_count": 0, "retry_count": 0, "session_ids": [], "last_seen": session["completed_at"]})
                for field in ("answer_count", "error_count", "unknown_count", "retry_count"):
                    entry[field] += counts[field]
                entry["session_ids"].append(session["id"])
                entry["last_seen"] = session["completed_at"]
        return sorted((entry for entry in aggregate.values() if entry["error_count"]), key=lambda x: x["last_seen"], reverse=True)

    def export_data(self, path):
        path = Path(path)
        if path.resolve() == self.db_path.resolve():
            raise ValueError("The export file cannot overwrite the active learning database.")
        with self.store.connect() as connection:
            records = [{"kind": row[0], "id": row[1], "data": json.loads(row[2])}
                       for row in connection.execute("SELECT kind,id,data FROM records ORDER BY rowid")]
        payload = {"schemaVersion": SCHEMA_VERSION, "application": "VocabularyLearning", "exported_at": now(),
                   "content_version": self.content["version"], "records": records}
        temporary = path.with_name(path.name + ".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
        temporary.replace(path)
        return {"path": str(path), "record_count": len(records)}

    def import_data(self, path):
        path = Path(path)
        if path.stat().st_size > 50 * 1024 * 1024:
            raise ValueError("The import file exceeds 50 MB. Use a smaller learning archive.")
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"), parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Unsupported numeric value")))
        except (json.JSONDecodeError, UnicodeDecodeError, RecursionError) as error:
            raise ValueError("The learning archive is not a valid JSON file.") from error
        self._validate_import(payload)
        backup = self.store.backup("before-import")
        with self.store.transaction() as connection:
            connection.execute("DELETE FROM records")
            for record in payload["records"]:
                self.store.put(connection, record["kind"], record["id"], record["data"])
            self.store.put(connection, "profile", "local", self._profile(connection))
        return {"path": str(path), "backup_path": str(backup), "record_count": len(payload["records"])}

    @staticmethod
    def _validate_import(payload):
        try:
            AppService._validate_import_payload(payload)
        except (KeyError, TypeError, IndexError, AttributeError, RecursionError) as error:
            raise ValueError("The learning archive is incomplete or inconsistent. Local records were not changed.") from error

    @staticmethod
    def _validate_import_payload(payload):
        def fail(message="The learning archive is incomplete or inconsistent. Local records were not changed."):
            raise ValueError(message)
        if not isinstance(payload, dict) or payload.get("application") != "VocabularyLearning":
            fail("This learning archive was not exported by this application.")
        pending = [payload]
        credential_fields = {"apikey", "password", "secret", "accesstoken", "refreshtoken", "authorization", "credentials", "token"}
        while pending:
            value = pending.pop()
            if isinstance(value, dict):
                if any(str(key).casefold().replace("_", "").replace("-", "") in credential_fields for key in value):
                    fail("Learning archives cannot contain keys or credentials.")
                pending.extend(value.values())
            elif isinstance(value, list):
                pending.extend(value)
        if type(payload.get("schemaVersion")) is not int or payload["schemaVersion"] != SCHEMA_VERSION:
            fail("This learning archive version is unsupported. Use a compatible application version.")
        records = payload.get("records")
        if not isinstance(records, list) or len(records) > 100000:
            fail()
        allowed = {"profile", "settings", "session", "mastered", "goal", "earned", "queue", "event", "assessment"}
        lookup = {}
        for record in records:
            if not isinstance(record, dict) or set(record) != {"kind", "id", "data"}:
                fail()
            kind, identifier, data = record["kind"], record["id"], record["data"]
            if kind not in allowed or not isinstance(identifier, str) or not identifier or len(identifier) > 200 or not isinstance(data, dict) or data.get("id") != identifier:
                fail()
            if (kind, identifier) in lookup:
                fail()
            lookup[kind, identifier] = data
        profile = lookup.get(("profile", "local"))
        settings = lookup.get(("settings", "local"))
        if not profile or not settings or sum(k[0] == "profile" for k in lookup) != 1 or sum(k[0] == "settings" for k in lookup) != 1:
            fail()
        profile = _with_onboarding_defaults(profile, any(kind in ("session", "goal", "mastered", "earned") for kind, _ in lookup))
        if type(profile.get("estimated_vocabulary")) is not int or not 0 <= profile["estimated_vocabulary"] <= 1000000 or type(profile.get("difficulty")) is not int or not 1 <= profile["difficulty"] <= 15:
            fail()
        if settings.get("ai_enabled") is not False or settings.get("network_mode") not in ("offline", "auto", "online_first"):
            fail("The archive contains unsupported connection settings. This version cannot import keys or enable AI.")
        if set(settings) - {"id", "network_mode", "ai_enabled", "reduced_motion", "english_variant", "speak_chinese"}:
            fail("The learning archive contains unsupported settings fields.")
        if type(settings.get("reduced_motion")) is not bool or settings.get("english_variant") not in ("en-US", "en-GB") or settings.get("speak_chinese", False) is not False:
            fail()
        assessments = {identifier: record for (kind, identifier), record in lookup.items() if kind == "assessment"}
        for record in assessments.values():
            assessment_rules.validate(record, AppService._validate_content)
        if sum(record["status"] == "in_progress" for record in assessments.values()) > 1:
            fail()
        step = profile.get("onboarding_step")
        if step is not None:
            if step not in ("self_rating", "assessment", "assessment_result", "goal", "complete"):
                fail()
            if bool(profile.get("onboarding_complete")) != (step == "complete"):
                fail()
        for field in ("onboarding_assessment_id", "difficulty_assessment_id", "last_assessment_id", "estimate_assessment_id"):
            identifier = profile.get(field)
            if identifier is not None and identifier not in assessments:
                fail()
            if field != "onboarding_assessment_id" and identifier is not None and assessments[identifier]["status"] != "complete":
                fail()
        linked_id = profile.get("onboarding_assessment_id")
        if step == "assessment_result" and (linked_id is None or assessments[linked_id]["status"] != "complete"):
            fail()
        if step == "goal" and linked_id is not None and assessments[linked_id]["status"] != "complete":
            fail()
        if profile.get("onboarding_goal_id") is not None and ("goal", profile["onboarding_goal_id"]) not in lookup:
            fail()
        active = 0
        completed = {}
        for (kind, identifier), session in lookup.items():
            if kind != "session":
                continue
            try:
                AppService._validate_content({"version": session["content_version"], "words": session["words"]})
                ids = {w["id"] for w in session["words"]}
                if len(ids) != 20 or session["stage"] not in ("overview", "learn", "quiz", "round_result", "relearn", "complete"):
                    fail()
                if type(session.get("round_no")) is not int or not 1 <= session["round_no"] <= 100000:
                    fail()
                if not isinstance(session["known_before"], list) or not set(session["known_before"]) <= ids:
                    fail()
                if not set(session["learn_ids"]) <= ids or not set(session["quiz_ids"]) <= ids or set(session["word_stats"]) != ids:
                    fail()
                if not session["learn_ids"] or not session["quiz_ids"] or len(session["questions"]) != len(session["quiz_ids"]):
                    fail()
                if len(session["learn_ids"]) != len(set(session["learn_ids"])) or len(session["quiz_ids"]) != len(set(session["quiz_ids"])):
                    fail()
                if type(session["learn_index"]) is not int or not 0 <= session["learn_index"] <= len(session["learn_ids"]) or type(session["quiz_index"]) is not int or not 0 <= session["quiz_index"] <= len(session["quiz_ids"]):
                    fail()
                if session["stage"] == "quiz" and session["quiz_index"] >= len(session["quiz_ids"]) or session["stage"] in ("learn", "relearn") and session["learn_index"] >= len(session["learn_ids"]):
                    fail()
                word_lookup = {w["id"]: w for w in session["words"]}
                pool = {sense["definition"] for word in session["words"] for sense in word["senses"]}
                def check_question(question):
                    options = question["options"]
                    if question["word_id"] not in ids or len(options) != 4 or len({o["id"] for o in options}) != 4 or question["correct_option_id"] not in {o["id"] for o in options}:
                        fail()
                    word = word_lookup[question["word_id"]]
                    sense = next((s for s in word["senses"] if s["id"] == question["sense_id"]), None)
                    choices = {o["id"]: o["text"] for o in options}
                    if sense is None or choices[question["correct_option_id"]] != sense["definition"] or question["pos"] != sense["pos"] or not set(choices.values()) <= pool:
                        fail()
                    forbidden = set().union(*(_meaning_tokens(s["definition"]) for s in word["senses"]))
                    seen = set(forbidden)
                    for option in options:
                        if option["id"] != question["correct_option_id"]:
                            tokens = _meaning_tokens(option["text"])
                            if not tokens or tokens & seen:
                                fail()
                            seen.update(tokens)
                for question in session["questions"]:
                    check_question(question)
                if [q["word_id"] for q in session["questions"]] != session["quiz_ids"] or any(q["round_no"] != session["round_no"] for q in session["questions"]):
                    fail()
                derived = {wid: {"answer_count": 0, "error_count": 0, "unknown_count": 0, "retry_count": 0} for wid in ids}
                latest = {}
                grouped = {}
                for attempt in session["attempts"]:
                    wid = attempt["word_id"]
                    question = attempt["question"]
                    check_question(question)
                    options = {option["id"]: option["text"] for option in question["options"]}
                    if wid not in ids or question["word_id"] != wid or question["correct_option_id"] not in options or attempt["option_id"] is not None and attempt["option_id"] not in options:
                        fail()
                    correct = attempt["option_id"] == question["correct_option_id"]
                    if type(attempt["correct"]) is not bool or attempt["correct"] != correct or type(attempt["round_no"]) is not int or attempt["round_no"] < 1:
                        fail()
                    if attempt["round_no"] > session["round_no"] or question["round_no"] != attempt["round_no"] or attempt["question_id"] != question["id"]:
                        fail()
                    expected_kind = "correct" if correct else "unknown" if attempt["option_id"] is None else "wrong"
                    if attempt["kind"] != expected_kind or not assessment_rules.choice_matches(options, attempt["option_id"], attempt["choice_text"]) or attempt["answer_text"] != options[question["correct_option_id"]]:
                        fail()
                    grouped.setdefault(attempt["round_no"], []).append(attempt)
                    latest[wid] = correct
                    derived[wid]["answer_count"] += 1
                    derived[wid]["error_count"] += int(not correct)
                    derived[wid]["unknown_count"] += int(attempt["option_id"] is None)
                    derived[wid]["retry_count"] += int(attempt["round_no"] > 1)
                if derived != session["word_stats"]:
                    fail()
                expected_ids = [w["id"] for w in session["words"]]
                for round_no in range(1, session["round_no"] + 1):
                    answers = grouped.get(round_no, [])
                    if [a["word_id"] for a in answers] != expected_ids[:len(answers)]:
                        fail()
                    if round_no < session["round_no"]:
                        if len(answers) != len(expected_ids):
                            fail()
                        expected_ids = [a["word_id"] for a in answers if not a["correct"]]
                        if not expected_ids:
                            fail()
                current_answers = grouped.get(session["round_no"], [])
                if session["quiz_ids"] != expected_ids or session["learn_ids"] != expected_ids or session["round_results"] != current_answers:
                    fail()
                if len(current_answers) != session["quiz_index"]:
                    fail()
                if session["stage"] in ("overview", "learn", "relearn") and current_answers:
                    fail()
                if session["stage"] in ("overview", "learn") and session["round_no"] != 1 or session["stage"] == "relearn" and session["round_no"] == 1:
                    fail()
                if session["stage"] in ("quiz", "round_result", "complete") and session["learn_index"] != len(expected_ids):
                    fail()
                if session["stage"] in ("round_result", "complete"):
                    if len(current_answers) != len(expected_ids) or session["wrong_ids"] != [a["word_id"] for a in current_answers if not a["correct"]]:
                        fail()
                elif session["wrong_ids"] != ([] if session["round_no"] == 1 else expected_ids):
                    fail()
                if session["stage"] == "complete":
                    if len(latest) != 20 or not all(latest.values()) or not session["completed_at"] or session["wrong_ids"]:
                        fail()
                    result = session["result"]
                    if type(result["net_new_words"]) is not int or result["net_new_words"] != len(set(result["new_word_ids"])) or not set(result["new_word_ids"]) <= ids or result["known_before_count"] != len(session["known_before"]):
                        fail()
                    if result["practice_words"] != 20 or result["achievement_practice_words"] != (0 if session.get("review_of") else 20):
                        fail()
                    if result["error_count"] != sum(v["error_count"] for v in derived.values()) or result["unknown_count"] != sum(v["unknown_count"] for v in derived.values()) or result["retry_count"] != sum(v["retry_count"] for v in derived.values()):
                        fail()
                    if set(result["new_word_ids"]) & set(session["known_before"]):
                        fail()
                    completed[identifier] = session
                else:
                    active += 1
                    if session.get("completed_at") or session.get("result"):
                        fail()
            except (KeyError, TypeError, IndexError, AttributeError):
                fail()
        if active > 1:
            fail()
        total_new = sum(bool(item.get("net_new")) for (kind, _), item in lookup.items() if kind == "mastered")
        if type(profile.get("estimate_new_baseline")) is not int or not 0 <= profile["estimate_new_baseline"] <= total_new or type(profile.get("onboarding_complete", False)) is not bool:
            fail()
        mastered_ids = {identifier for kind, identifier in lookup if kind == "mastered"}
        achievement_practice = sum(20 for session in completed.values() if not session.get("review_of"))
        started = sum(kind == "session" for kind, _ in lookup)
        for (kind, identifier), item in lookup.items():
            if kind == "session" and item.get("review_of") and item["review_of"] not in completed:
                fail()
            if kind == "mastered":
                origin = completed.get(item.get("first_session"))
                if origin is None or item["id"] not in {w["id"] for w in origin["words"]} or type(item.get("net_new")) is not bool:
                    fail()
                if item["net_new"] != (item["id"] in origin["result"]["new_word_ids"]):
                    fail()
                original_word = next(w for w in origin["words"] if w["id"] == identifier)
                if item.get("word") != original_word:
                    fail()
            if kind == "goal":
                if item.get("kind") not in ("word_count", "word_set", "cet4") or item.get("threshold") != 1:
                    fail()
                if item["kind"] == "word_count":
                    if type(item.get("baseline")) is not int or type(item.get("target")) is not int or not 0 <= item["baseline"] < item["target"] <= 1000000 or type(item.get("baseline_new_words")) is not int or not 0 <= item["baseline_new_words"] <= total_new:
                        fail()
                    achieved = total_new - item["baseline_new_words"] >= item["target"] - item["baseline"]
                elif not isinstance(item.get("word_ids"), list) or len(item["word_ids"]) != len(set(item["word_ids"])) or type(item.get("loaded_complete")) is not bool:
                    fail()
                else:
                    metadata = item.get("word_set_metadata", {})
                    ids = set(item["word_ids"])
                    snapshots = item.get("word_snapshots", [])
                    if not isinstance(metadata, dict) or not isinstance(snapshots, list):
                        fail()
                    if item["kind"] == "cet4" and metadata.get("kind") not in ("cet4", "cet-4", "CET-4"):
                        fail("A test word set cannot be represented as an official CET-4 goal.")
                    if item["loaded_complete"] and (not ids or not item.get("word_set_version") or not metadata.get("complete") or {w.get("id") for w in snapshots} != ids):
                        fail()
                    achieved = bool(item["loaded_complete"] and ids and ids <= mastered_ids)
                if bool(item.get("completed_at")) != achieved:
                    fail()
                if achieved:
                    event = lookup.get(("event", "goal:" + identifier))
                    if event is None or event.get("kind") != "goal_completed" or event.get("goal_id") != identifier:
                        fail()
            if kind == "earned":
                definition = item.get("definition")
                if not isinstance(definition, dict) or definition.get("id") != identifier or type(definition.get("threshold")) is not int or definition["threshold"] <= 0 or not isinstance(item.get("earned_at"), str):
                    fail()
                metric = definition.get("metric")
                progress = started if metric == "started_sessions" else achievement_practice if metric == "achievement_practice_words" else -1
                if progress < definition["threshold"]:
                    fail()
            if kind == "event":
                if item.get("kind") == "session_completed":
                    if item.get("session_id") not in completed or identifier != "complete:" + item["session_id"]:
                        fail()
                elif item.get("kind") == "goal_completed":
                    goal = lookup.get(("goal", item.get("goal_id")))
                    if goal is None or not goal.get("completed_at") or identifier != "goal:" + goal["id"]:
                        fail()
                else:
                    fail()
        mastered = {identifier for kind, identifier in lookup if kind == "mastered"}
        for identifier, session in completed.items():
            if not {w["id"] for w in session["words"]} <= mastered or ("event", "complete:" + identifier) not in lookup:
                fail()
            if not set(session["result"]["new_word_ids"]) <= mastered:
                fail()
            event = lookup["event", "complete:" + identifier]
            if event.get("kind") != "session_completed" or event.get("session_id") != identifier:
                fail()
            for word_id in session["result"]["new_word_ids"]:
                record = lookup["mastered", word_id]
                if record["first_session"] != identifier or not record["net_new"] or session.get("review_of"):
                    fail()
