"""Learning rules independent of the desktop UI and speech engine."""

from __future__ import annotations

from copy import deepcopy
from contextlib import nullcontext
from datetime import datetime, timezone
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
            re.split(r"[;；,，、/（）()\n]", text) if part.strip()}


def _with_onboarding_defaults(profile, has_learning_records):
    profile = deepcopy(profile)
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
                    "id": "local", "name": "学习者", "self_rating": "初级", "difficulty": 2,
                    "estimated_vocabulary": 0, "estimate_new_baseline": 0, "onboarding_complete": False,
                    "onboarding_step": "self_rating", "onboarding_assessment_id": None, "estimate_source": "unset",
                    "interface_language": "zh-CN", "meaning_language": "zh-CN",
                    "learning_language": "en", "updated_at": now(),
                    "abilities": {key: {"value": None, "confidence": "未知", "evidence": 0}
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
            raise ValueError("词库缺少版本信息。")
        words = content.get("words")
        if not isinstance(words, list) or not words:
            raise ValueError("词库没有可用词条。")
        ids, lemmas = set(), set()
        for word in words:
            if not isinstance(word, dict):
                raise ValueError("词条格式不正确。")
            identifier, lemma = word.get("id"), word.get("lemma")
            if not isinstance(identifier, str) or not identifier or identifier in ids:
                raise ValueError("词条 ID 不能为空或重复。")
            key = (word.get("language", "en"), unicodedata.normalize("NFKC", str(lemma)).strip().casefold())
            if not isinstance(lemma, str) or not lemma.strip() or lemma != lemma.strip() or key in lemmas:
                raise ValueError("同一语言不能用重复词元凑词库数量。")
            if type(word.get("level")) is not int or not 1 <= word["level"] <= 15:
                raise ValueError("词条难度必须在 L1—L15。")
            senses = word.get("senses")
            if not isinstance(senses, list) or not senses:
                raise ValueError("每个词条至少需要一个义项。")
            for sense in senses:
                if not isinstance(sense, dict) or not all(
                    isinstance(sense.get(field), str) and sense[field].strip()
                    for field in ("id", "pos", "definition")
                ):
                    raise ValueError("词条义项缺少 ID、词性或释义。")
            if len({s["id"] for s in senses}) != len(senses):
                raise ValueError("同一词条内的义项 ID 不能重复。")
            ids.add(identifier)
            lemmas.add(key)
        if not isinstance(content.get("word_sets", []), list):
            raise ValueError("目标词集格式不正确。")

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
            return {
                "profile": self._profile(connection),
                "settings": self.store.get(connection, "settings", "local"),
                "stats": self._stats(connection), "active_session": self._present(active),
                "active_assessment": next((deepcopy(a) for a in reversed(self.store.all(connection, "assessment")) if a["status"] == "in_progress"), None),
                "goals": [self._goal_view(connection, goal) for goal in self.store.all(connection, "goal")],
                "achievements": self._achievements(connection),
                "content": {"version": self.content["version"], "word_count": len(self.words),
                            "levels": sorted({w["level"] for w in self.words.values()}),
                            "word_sets": deepcopy(self.content.get("word_sets", []))},
            }

    def update_profile(self, **kwargs):
        allowed = {"name", "self_rating", "difficulty", "estimated_vocabulary", "onboarding_complete"}
        if set(kwargs) - allowed:
            raise ValueError("不支持的档案字段。")
        with self.store.transaction() as connection:
            profile = self._profile(connection)
            if "name" in kwargs:
                name = kwargs["name"]
                if not isinstance(name, str) or not 1 <= len(name.strip()) <= 60:
                    raise ValueError("名字请填写 1—60 个字符。")
                profile["name"] = name.strip()
            if "self_rating" in kwargs:
                value = kwargs["self_rating"]
                if value not in ("刚开始学", "只会一点", "初级", "中级", "高级", "熟练", "本地人", "专业英语学习人"):
                    raise ValueError("请选择可用的自评选项。")
                profile["self_rating"] = value
            if "difficulty" in kwargs:
                if type(kwargs["difficulty"]) is not int or not 1 <= kwargs["difficulty"] <= 15:
                    raise ValueError("难度必须在 L1—L15。")
                profile["difficulty"] = kwargs["difficulty"]
            if "estimated_vocabulary" in kwargs:
                value = kwargs["estimated_vocabulary"]
                if type(value) is not int or not 0 <= value <= 1000000:
                    raise ValueError("估计词量应为 0—1000000 的整数。")
                if value != profile["estimated_vocabulary"]:
                    if self._stats(connection)["completed_sessions"] or self.store.all(connection, "goal"):
                        raise ValueError("已有学习记录或目标。重设估计基线需确认对目标的影响，当前版本暂不重设。")
                    profile["estimated_vocabulary"] = value
            if "onboarding_complete" in kwargs:
                if type(kwargs["onboarding_complete"]) is not bool:
                    raise ValueError("起点设置状态必须为布尔值。")
                profile["onboarding_complete"] = kwargs["onboarding_complete"]
                profile["onboarding_step"] = "complete" if kwargs["onboarding_complete"] else "self_rating"
            profile["updated_at"] = now()
            self.store.put(connection, "profile", "local", profile)
            return deepcopy(profile)

    def _level_config(self):
        path = self.content_dir / "levels.json"
        return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else {}

    def set_onboarding_rating(self, self_rating, name=None, use_assessment=True):
        if self_rating not in assessment_rules.RATINGS or type(use_assessment) is not bool:
            raise ValueError("请选择可用的自评选项。")
        if name is not None and (not isinstance(name, str) or not 1 <= len(name.strip()) <= 60):
            raise ValueError("名字请填写 1—60 个字符。")
        with self.store.transaction() as connection:
            profile = self._profile(connection)
            if profile.get("onboarding_complete"):
                raise ValueError("档案已完成初始设置。可在设置页修改自评，或单独重新测评。")
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
        with self.store.transaction() as connection:
            profile = self._profile(connection)
            pending = next((a for a in reversed(self.store.all(connection, "assessment")) if a["status"] == "in_progress"), None)
            if pending:
                if pending["question_count"] != question_count:
                    raise ValueError(f"还有一份未完成的 {pending['question_count']} 题测评，请先继续原测评。")
                if not profile.get("onboarding_complete"):
                    profile.update(onboarding_assessment_id=pending["id"], onboarding_step="assessment")
                    self.store.put(connection, "profile", "local", profile)
                return deepcopy(pending)
            record = assessment_rules.create(list(self.words.values()), self.content["version"], self_rating, question_count,
                                             self._level_config(), self._assessment_question, now())
            self.store.put(connection, "assessment", record["id"], record)
            if not profile.get("onboarding_complete"):
                profile.update(onboarding_assessment_id=record["id"], onboarding_step="assessment", self_rating=self_rating)
                self.store.put(connection, "profile", "local", profile)
            return deepcopy(record)

    def assessment(self, assessment_id=None):
        with self.store.connect() as connection:
            if assessment_id:
                record = self.store.get(connection, "assessment", assessment_id)
                if record is None:
                    raise ValueError("没有找到该测评记录。")
                return deepcopy(record)
            records = self.store.all(connection, "assessment")
            profile = self._profile(connection)
            linked = self.store.get(connection, "assessment", profile.get("onboarding_assessment_id", ""))
            if linked and (not profile.get("onboarding_complete") or linked["status"] == "in_progress"):
                return deepcopy(linked)
            return deepcopy(next((a for a in reversed(records) if a["status"] == "in_progress"), records[-1] if records else None))

    def answer_assessment(self, assessment_id, option_id=None):
        with self.store.transaction() as connection:
            record = self.store.get(connection, "assessment", assessment_id)
            if record is None:
                raise ValueError("没有找到该测评记录。")
            updated = assessment_rules.answer(record, option_id, self._assessment_question, now())
            self.store.put(connection, "assessment", assessment_id, updated)
            profile = self._profile(connection)
            if not profile.get("onboarding_complete") and profile.get("onboarding_assessment_id") == assessment_id and updated["status"] == "complete":
                profile["onboarding_step"] = "assessment_result"
                self.store.put(connection, "profile", "local", profile)
            return deepcopy(updated)

    def accept_assessment(self, assessment_id):
        with self.store.transaction() as connection:
            record = self.store.get(connection, "assessment", assessment_id)
            if record is None or record["status"] != "complete":
                raise ValueError("请先完整完成测评，再采用推荐难度。")
            profile = self._profile(connection)
            result = record["result"]
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
            raise ValueError("起点词量应为 0—1000000 的整数，并由你确认。")
        with self.store.transaction() as connection:
            profile = self._profile(connection)
            if profile.get("onboarding_complete"):
                raise ValueError("初始设置已经完成。请在目标页面添加目标，不会重置原学习记录。")
            if profile.get("onboarding_step") != "goal":
                raise ValueError("请先完成自评，或完成测评并确认推荐难度。")
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
            raise ValueError("不支持的设置字段。")
        if kwargs.get("ai_enabled"):
            raise ValueError("当前版本尚未接入 AI，普通学习可离线使用。")
        if "network_mode" in kwargs and kwargs["network_mode"] not in ("offline", "auto", "online_first"):
            raise ValueError("请选择离线、自动或在线优先。")
        for field in ("ai_enabled", "reduced_motion", "speak_chinese"):
            if field in kwargs and type(kwargs[field]) is not bool:
                raise ValueError("开关值必须为布尔值。")
        if kwargs.get("speak_chinese"):
            raise ValueError("当前版本仅朗读英语，不朗读中文释义。")
        if "english_variant" in kwargs and kwargs["english_variant"] not in ("en-US", "en-GB"):
            raise ValueError("当前仅预留英式或美式英语口音。")
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
            raise ValueError("目标类型必须是词数或指定词集。")
        with (self.store.transaction() if connection is None else nullcontext(connection)) as connection:
            goal = {"id": new_id(), "kind": kind, "created_at": now(), "completed_at": None,
                    "threshold": 1, "baseline_new_words": self._stats(connection)["net_new_words"]}
            if kind == "word_count":
                if type(baseline) is not int or type(target) is not int or not 0 <= baseline < target <= 1000000:
                    raise ValueError("目标词数必须大于起点，且不超过 1000000。")
                goal.update(baseline=baseline, target=target, title=f"掌握 {target} 词")
                if not self._stats(connection)["completed_sessions"] and not self.store.all(connection, "goal"):
                    profile = self._profile(connection)
                    profile["estimated_vocabulary"] = baseline
                    self.store.put(connection, "profile", "local", profile)
            else:
                sets = self.content.get("word_sets", [])
                selected = next((s for s in sets if s.get("id") == word_set_id), None) if word_set_id else None
                if selected is None and kind == "cet4":
                    selected = next((s for s in sets if s.get("kind") in ("cet4", "cet-4", "CET-4")), None)
                selected = deepcopy(selected or {"id": word_set_id or "cet4", "name": "英语四级" if kind == "cet4" else "指定词集",
                                                  "version": "", "complete": False, "kind": "cet4" if kind == "cet4" else "custom", "word_ids": []})
                if kind == "cet4" and selected.get("kind") not in ("cet4", "cet-4", "CET-4"):
                    raise ValueError("测试词集不能用作正式四级目标。")
                ids = selected.get("word_ids", [])
                if not isinstance(ids, list) or any(not isinstance(i, str) for i in ids):
                    raise ValueError("目标词集格式不正确。")
                ids = list(dict.fromkeys(ids))
                goal.update(word_set_id=selected["id"], word_set_version=selected.get("version", ""),
                            word_ids=ids, target=len(ids), baseline=0,
                            loaded_complete=bool(selected.get("complete") and selected.get("version") and ids and all(i in self.words for i in ids)),
                            title=selected.get("name", "指定词集"),
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
                        remaining=max(0, denominator - numerator), message="按起点之后净新增的不同词计数")
        else:
            ids = set(goal["word_ids"])
            numerator, denominator = len(mastered & ids), len(ids)
            available = bool(goal.get("loaded_complete") and denominator)
            view.update(current=numerator, available=available, remaining=max(0, denominator - numerator),
                        remaining_words=[word for word in goal.get("word_snapshots", []) if word["id"] not in mastered],
                        message="仅检查该版本词库的词汇覆盖，不代表考试一定通过" if available else "完整合法词表待安装；暂不计算达成比例")
        view.update(numerator=numerator, denominator=denominator,
                    ratio=min(1.0, numerator / denominator) if denominator and view["available"] else 0.0,
                    completed=bool(goal.get("completed_at")))
        return view

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
            raise ValueError("没有找到该词条。")
        with self.store.transaction() as connection:
            if self.store.get(connection, "mastered", word_id):
                raise ValueError("该词已掌握，可从学习历史重新挑战原轮。")
            self.store.put(connection, "queue", word_id, {"id": word_id, "added_at": now()})
        return self.queue()

    def remove_from_queue(self, word_id):
        with self.store.transaction() as connection:
            self.store.delete(connection, "queue", word_id)
        return self.queue()

    def start_session(self, review_of=None):
        with self.store.transaction() as connection:
            if any(s["stage"] != "complete" for s in self.store.all(connection, "session")):
                raise ValueError("还有一轮未完成，请先继续该轮学习。")
            mastered = {w["id"] for w in self.store.all(connection, "mastered")}
            if review_of:
                old = self.store.get(connection, "session", review_of)
                if not old or old["stage"] != "complete":
                    raise ValueError("只能重新挑战已经完成的历史轮次。")
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
                    raise ValueError(f"当前难度附近仅剩 {len(ordered)} 个未学词，不足 20 个。请调整难度、扩充词库或重做历史轮次。")
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
                raise ValueError(f"{word['lemma']} 无法从本轮词池组成四个清楚的选项，请调整词库或换一轮。")
            correct_id = options[0]["id"]
            rng.shuffle(options)
            questions.append({"id": new_id(), "word_id": identifier, "lemma": word["lemma"],
                              "sense_id": sense["id"], "pos": sense["pos"], "prompt": "请选择该词性对应的中文含义",
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
        return result

    def _get_session(self, connection, session_id=None):
        if session_id:
            result = self.store.get(connection, "session", session_id)
        else:
            result = next((s for s in reversed(self.store.all(connection, "session")) if s["stage"] != "complete"), None)
        if result is None:
            raise ValueError("没有找到学习轮次。")
        return result

    def session(self, session_id=None):
        with self.store.connect() as connection:
            return self._present(self._get_session(connection, session_id))

    def mark_known(self, session_id, word_id, known):
        with self.store.transaction() as connection:
            session = self._get_session(connection, session_id)
            if session["stage"] != "overview" or word_id not in {w["id"] for w in session["words"]} or type(known) is not bool:
                raise ValueError("只能在本轮总览中修改已会标记。")
            marked = set(session["known_before"])
            marked.add(word_id) if known else marked.discard(word_id)
            session["known_before"] = sorted(marked)
            self.store.put(connection, "session", session_id, session)
            return self._present(session)

    def begin_learning(self, session_id):
        with self.store.transaction() as connection:
            session = self._get_session(connection, session_id)
            if session["stage"] != "overview":
                raise ValueError("该轮已经开始。")
            session["stage"] = "learn"
            self.store.put(connection, "session", session_id, session)
            return self._present(session)

    def next_word(self, session_id):
        with self.store.transaction() as connection:
            session = self._get_session(connection, session_id)
            if session["stage"] not in ("learn", "relearn"):
                raise ValueError("当前不是逐词学习阶段。")
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
                raise ValueError("当前没有等待作答的题目。")
            question = session["questions"][session["quiz_index"]]
            choices = {o["id"]: o["text"] for o in question["options"]}
            if option_id is not None and option_id not in choices:
                raise ValueError("题目已变化，请按当前题目作答。")
            correct = option_id == question["correct_option_id"]
            identifier = question["word_id"]
            attempt = {"id": new_id(), "question_id": question["id"], "word_id": identifier,
                       "sense_id": question["sense_id"], "round_no": session["round_no"],
                       "option_id": option_id, "correct": correct, "kind": "correct" if correct else "unknown" if option_id is None else "wrong",
                       "choice_text": choices.get(option_id, "我不会"), "answer_text": choices[question["correct_option_id"]], "at": now(),
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
                raise ValueError("请先完成当前测验。")
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
            raise ValueError("该轮结算记录不一致，请从备份恢复。")
        if not session["round_results"] or any(not a["correct"] for a in session["round_results"]):
            raise ValueError("尚有未通过的词，不能结算。")
        latest = {a["word_id"]: a["correct"] for a in session["attempts"]}
        if len(latest) != 20 or not all(latest.values()):
            raise ValueError("必须完成全部 20 个词的测验。")
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
        return [{"id": "first_use", "title": "首次使用", "description": "开始第一轮学习", "threshold": 1, "metric": "started_sessions"}] + [
            {"id": f"practice_{n}", "title": f"完成 {n} 词练习", "description": "累计完成新轮次；重做历史不计入", "threshold": n, "metric": "achievement_practice_words"}
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
        return result

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
            raise ValueError("导出文件不能覆盖正在使用的学习数据库。")
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
            raise ValueError("导入文件超过 50 MB，请使用较小的学习档案。")
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"), parse_constant=lambda value: (_ for _ in ()).throw(ValueError("不支持的数字")))
        except (json.JSONDecodeError, UnicodeDecodeError, RecursionError) as error:
            raise ValueError("学习档案不是有效的 JSON 文件。") from error
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
            raise ValueError("学习档案结构不完整或数据不一致，未修改本地记录。") from error

    @staticmethod
    def _validate_import_payload(payload):
        def fail(message="学习档案结构不完整或数据不一致，未修改本地记录。"):
            raise ValueError(message)
        if not isinstance(payload, dict) or payload.get("application") != "VocabularyLearning":
            fail("这不是本应用导出的学习档案。")
        pending = [payload]
        credential_fields = {"apikey", "password", "secret", "accesstoken", "refreshtoken", "authorization", "credentials", "token"}
        while pending:
            value = pending.pop()
            if isinstance(value, dict):
                if any(str(key).casefold().replace("_", "").replace("-", "") in credential_fields for key in value):
                    fail("学习档案中不能包含密钥或凭据。")
                pending.extend(value.values())
            elif isinstance(value, list):
                pending.extend(value)
        if type(payload.get("schemaVersion")) is not int or payload["schemaVersion"] != SCHEMA_VERSION:
            fail("学习档案版本不受支持，请使用兼容的软件版本。")
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
            fail("档案含不支持的连接设置；当前版本不导入密钥或启用 AI。")
        if set(settings) - {"id", "network_mode", "ai_enabled", "reduced_motion", "english_variant", "speak_chinese"}:
            fail("学习档案包含不支持的设置字段。")
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
                    if attempt["kind"] != expected_kind or attempt["choice_text"] != options.get(attempt["option_id"], "我不会") or attempt["answer_text"] != options[question["correct_option_id"]]:
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
                        fail("测试词集不能冒充正式四级目标。")
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
