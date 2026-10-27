"""Versioned adaptive word-meaning assessment, separate from learning credit."""

from __future__ import annotations

from copy import deepcopy
import math
import random
import re
import uuid


ALGORITHM_VERSION = "anchored-logistic-1"
QUESTION_COUNTS = (20, 50, 100, 200, 500)
RATINGS = ("刚开始学", "只会一点", "初级", "中级", "高级", "熟练", "本地人", "专业英语学习人")
RATING_LEVELS = (1, 2, 3, 5, 8, 11, 12, 12)


def _tokens(text):
    return {re.sub(r"\s+", "", value).casefold() for value in re.split(r"[;；,，、/（）()\n]", text) if value.strip()}


def _eligible_words(words):
    current = list(words)
    while current:
        pool = [(word["id"], _tokens(sense["definition"]), sense.get("synonym_group"))
                for word in current for sense in word["senses"]]
        eligible = []
        for word in current:
            seen = set().union(*(_tokens(sense["definition"]) for sense in word["senses"]))
            groups = {sense["synonym_group"] for sense in word["senses"] if sense.get("synonym_group")}
            count = 0
            for identifier, tokens, group in pool:
                if identifier != word["id"] and tokens and not tokens & seen and group not in groups:
                    count += 1
                    seen.update(tokens)
                    if count == 3:
                        eligible.append(word)
                        break
        if len(eligible) == len(current):
            return eligible
        current = eligible
    return []


def _posterior(record):
    levels = record["available_levels"]
    low, high = min(levels) - 1.0, max(levels) + 0.75
    grid = [low + (high - low) * index / 120 for index in range(121)]
    center = min(max(record["self_rating_level"], min(levels)), max(levels))
    spread = max(2.0, (max(levels) - min(levels)) / 2)
    scores = []
    for ability in grid:
        score = -0.5 * ((ability - center) / spread) ** 2
        for answer in record["answers"]:
            probability = 0.25 + 0.75 / (1 + math.exp(max(-50, min(50, 1.05 * (answer["level"] - ability)))))
            score += math.log(probability if answer["correct"] else 1 - probability)
        scores.append(score)
    maximum = max(scores)
    weights = [math.exp(score - maximum) for score in scores]
    total = sum(weights)
    return grid, [weight / total for weight in weights]


def _quantile(grid, weights, probability):
    cumulative = 0.0
    for value, weight in zip(grid, weights):
        cumulative += weight
        if cumulative >= probability:
            return value
    return grid[-1]


def estimate(record):
    """Return an internal reference range, never a standardized ability score."""
    grid, weights = _posterior(record)
    median = _quantile(grid, weights, 0.5)
    lower = _quantile(grid, weights, 0.1)
    upper = _quantile(grid, weights, 0.9)
    levels = record["available_levels"]
    recommended = min(levels, key=lambda level: (abs(level - median), level))
    lower_level = min(levels, key=lambda level: abs(level - lower))
    upper_level = min(levels, key=lambda level: abs(level - upper))
    ranges = record["level_ranges"]
    estimated_range = [ranges[str(lower_level)][0], ranges[str(upper_level)][1]]
    answered = len(record["answers"])
    confidence = "较低" if answered < 50 or upper - lower > 3 else "一般"
    limited = min(levels) > 1 or max(levels) < 15 or upper >= max(levels)
    covered = sorted({answer["level"] for answer in record["answers"]})
    return {
        "recommended_level": recommended, "estimated_range": estimated_range,
        "suggested_baseline": round(sum(estimated_range) / 2),
        "confidence": confidence, "covered_levels": covered,
        "available_levels": list(levels), "limited_by_content": limited,
        "standardized": False, "answered_count": answered,
        "recognition_only": True,
        "summary": (f"本次测评提供 L{recommended} 的词义识别难度参考；"
                    f"实际题库覆盖 L{min(levels)}—L{max(levels)}，尚未标准化校准。"
                    "词量区间仅作设置起点的参考，其他技能尚未测量。"),
    }


def _anchor_schedule(record):
    levels = record["available_levels"]
    if record["question_count"] == 20:
        count = min(6, len(levels))
        if count == 1:
            return levels[:]
        return [levels[math.ceil(index * (len(levels) - 1) / (count - 1))] for index in range(count)]
    budget = min(15, len(levels) * 2) if record["question_count"] == 50 else len(levels) * 2
    return (levels * 2)[:budget]


def _next_level(record):
    levels = record["available_levels"]
    used = {question["word_id"] for question in record["questions"]}
    available = {level for level in levels if any(word["level"] == level and word["id"] not in used for word in record["word_bank"])}
    if not available:
        raise ValueError("独立题库已用完，不能重复题目补足测评数量。")
    anchors = _anchor_schedule(record)
    if len(record["answers"]) < len(anchors):
        desired = anchors[len(record["answers"])]
        return min(available, key=lambda level: (abs(level - desired), level))
    grid, weights = _posterior(record)
    center = _quantile(grid, weights, 0.5)
    counts = {level: sum(answer["level"] == level for answer in record["answers"]) for level in available}
    return min(available, key=lambda level: (abs(level - center) + 0.08 * counts[level], counts[level], level))


def next_question(record, question_factory):
    level = _next_level(record)
    used = {question["word_id"] for question in record["questions"]}
    choices = [word for word in record["word_bank"] if word["level"] == level and word["id"] not in used]
    random.SystemRandom().shuffle(choices)
    for word in choices:
        try:
            question = question_factory(record["word_bank"], word["id"])
            question["level"] = word["level"]
            question["sequence"] = len(record["questions"]) + 1
            question["selection_phase"] = "anchor" if len(record["answers"]) < len(_anchor_schedule(record)) else "adaptive"
            return question
        except ValueError:
            continue
    raise ValueError("当前难度的词条无法组成清楚的四选一题目，请完善词库。")


def create(words, content_version, self_rating, question_count, level_config, question_factory, timestamp):
    if self_rating not in RATINGS:
        raise ValueError("请选择可用的自评选项。")
    if type(question_count) is not int or question_count not in QUESTION_COUNTS:
        raise ValueError("测评题量请选择 20、50、100、200 或 500。")
    eligible = deepcopy(_eligible_words(words))
    if len(eligible) < question_count:
        raise ValueError(f"当前有 {len(eligible)} 个独立有效词条，不足 {question_count} 题。请先安装更多题库；不会重复题目凑数。")
    levels = sorted({word["level"] for word in eligible})
    configured_ranges = {int(item["level"]): list(item["estimated_range"]) for item in level_config.get("levels", [])}
    ranges = {str(level): configured_ranges.get(level, [max(0, (level - 1) * 500), level * 500]) for level in levels}
    rating_level = next((item["level"] for item in level_config.get("self_ratings", []) if item.get("label") == self_rating), RATING_LEVELS[RATINGS.index(self_rating)])
    record = {
        "id": str(uuid.uuid4()), "status": "in_progress", "self_rating": self_rating,
        "self_rating_level": rating_level, "question_count": question_count, "answered_count": 0,
        "question": None, "questions": [], "answers": [], "result": {},
        "word_bank": eligible, "available_levels": levels, "level_ranges": ranges,
        "bank_version": content_version, "algorithm_version": ALGORITHM_VERSION,
        "level_config_version": level_config.get("version", "internal-unversioned"),
        "created_at": timestamp, "updated_at": timestamp, "completed_at": None,
    }
    question = next_question(record, question_factory)
    record["questions"].append(question)
    record["question"] = deepcopy(question)
    return record


def answer(record, option_id, question_factory, timestamp):
    if record["status"] == "complete":
        return deepcopy(record)
    question = record["question"]
    choices = {option["id"]: option["text"] for option in question["options"]}
    if option_id is not None and option_id not in choices:
        raise ValueError("测评题目已经变化，请按当前题目作答。")
    updated = deepcopy(record)
    correct = option_id == question["correct_option_id"]
    updated["answers"].append({
        "id": str(uuid.uuid4()), "question_id": question["id"], "word_id": question["word_id"],
        "level": question["level"], "option_id": option_id, "correct": correct,
        "kind": "correct" if correct else "unknown" if option_id is None else "wrong",
        "choice_text": choices.get(option_id, "我不会"),
        "answer_text": choices[question["correct_option_id"]], "at": timestamp,
    })
    updated["answered_count"] = len(updated["answers"])
    updated["updated_at"] = timestamp
    if updated["answered_count"] == updated["question_count"]:
        updated["status"] = "complete"
        updated["question"] = None
        updated["completed_at"] = timestamp
        updated["result"] = estimate(updated)
    else:
        question = next_question(updated, question_factory)
        updated["questions"].append(question)
        updated["question"] = deepcopy(question)
    return updated


def validate(record, validate_content):
    """Reject inconsistent archives before they can change local records."""
    def fail():
        raise ValueError("测评档案的题目、作答或完成结果不一致。")
    if record.get("algorithm_version") != ALGORITHM_VERSION or record.get("self_rating") not in RATINGS:
        fail()
    if type(record.get("question_count")) is not int or record["question_count"] not in QUESTION_COUNTS:
        fail()
    if type(record.get("self_rating_level")) is not int or not 1 <= record["self_rating_level"] <= 15:
        fail()
    validate_content({"version": record["bank_version"], "words": record["word_bank"]})
    bank = {word["id"]: word for word in record["word_bank"]}
    if len(bank) < record["question_count"] or record["available_levels"] != sorted({w["level"] for w in bank.values()}):
        fail()
    for level in record["available_levels"]:
        values = record["level_ranges"][str(level)]
        if not isinstance(values, list) or len(values) != 2 or any(type(v) is not int for v in values) or not 0 <= values[0] < values[1] <= 1000000:
            fail()
    questions, answers = record["questions"], record["answers"]
    if not isinstance(questions, list) or not isinstance(answers, list) or not 0 <= len(answers) <= record["question_count"] or record["answered_count"] != len(answers):
        fail()
    if len({question["word_id"] for question in questions}) != len(questions) or len({question["id"] for question in questions}) != len(questions):
        fail()
    pool = {sense["definition"] for word in bank.values() for sense in word["senses"]}
    prefix = dict(record, questions=[], answers=[])
    for index, question in enumerate(questions):
        word = bank.get(question["word_id"])
        if not word or question["lemma"] != word["lemma"] or question["level"] != word["level"] or question["sequence"] != index + 1:
            fail()
        if question["level"] != _next_level(prefix):
            fail()
        expected_phase = "anchor" if index < len(_anchor_schedule(record)) else "adaptive"
        if question.get("selection_phase") != expected_phase:
            fail()
        sense = next((s for s in word["senses"] if s["id"] == question["sense_id"]), None)
        options = {option["id"]: option["text"] for option in question["options"]}
        if len(question["options"]) != 4 or len(options) != 4 or len(set(options.values())) != 4 or not set(options.values()) <= pool:
            fail()
        if not sense or question["pos"] != sense["pos"] or options.get(question["correct_option_id"]) != sense["definition"]:
            fail()
        seen = set().union(*(_tokens(s["definition"]) for s in word["senses"]))
        for option_id, text in options.items():
            if option_id != question["correct_option_id"]:
                tokens = _tokens(text)
                if not tokens or tokens & seen:
                    fail()
                seen.update(tokens)
        prefix["questions"].append(question)
        if index < len(answers):
            response = answers[index]
            if response["question_id"] != question["id"] or response["word_id"] != word["id"] or response["level"] != word["level"]:
                fail()
            option_id = response["option_id"]
            if option_id is not None and option_id not in options:
                fail()
            correct = option_id == question["correct_option_id"]
            kind = "correct" if correct else "unknown" if option_id is None else "wrong"
            if type(response["correct"]) is not bool or response["correct"] != correct or response["kind"] != kind or response["choice_text"] != options.get(option_id, "我不会") or response["answer_text"] != sense["definition"]:
                fail()
            prefix["answers"].append(response)
    if record["status"] == "complete":
        if len(answers) != record["question_count"] or len(questions) != len(answers) or record["question"] is not None or not record["completed_at"] or record["result"] != estimate(record):
            fail()
    elif record["status"] == "in_progress":
        if len(answers) >= record["question_count"] or len(questions) != len(answers) + 1 or record["question"] != questions[-1] or record["completed_at"] is not None or record["result"]:
            fail()
    else:
        fail()
