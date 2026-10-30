"""Versioned adaptive word-meaning assessment, separate from learning credit."""

from __future__ import annotations

from copy import deepcopy
import math
import random
import re
import uuid


ALGORITHM_VERSION = "anchored-logistic-1"
QUESTION_COUNTS = (20, 50, 100, 200, 500)
RATINGS = ("Just starting", "Know a little", "Beginner", "Intermediate", "Advanced", "Proficient", "Native speaker", "Professional English learner")
RATING_LEVELS = (1, 2, 3, 5, 8, 11, 12, 12)
LEGACY_RATINGS = dict(zip((
    "\u521a\u5f00\u59cb\u5b66", "\u53ea\u4f1a\u4e00\u70b9", "\u521d\u7ea7", "\u4e2d\u7ea7", "\u9ad8\u7ea7", "\u719f\u7ec3", "\u672c\u5730\u4eba", "\u4e13\u4e1a\u82f1\u8bed\u5b66\u4e60\u4eba",
), RATINGS))
UNKNOWN_ANSWER = "I don't know"
LEGACY_UNKNOWN_ANSWER = "\u6211\u4e0d\u4f1a"


def normalize_rating(value):
    """Keep profiles and archives created before the English interface usable."""
    return LEGACY_RATINGS.get(value, value)


def choice_matches(options, option_id, text):
    if option_id is None:
        return text in (UNKNOWN_ANSWER, LEGACY_UNKNOWN_ANSWER)
    return text == options.get(option_id)


def _legacy_estimate(record):
    """Validate the exact display text stored by the previous release."""
    result = estimate(record)
    result["confidence"] = "\u8f83\u4f4e" if result["confidence"] == "Low" else "\u4e00\u822c"
    recommended, levels = result["recommended_level"], record["available_levels"]
    result["summary"] = (
        f"\u672c\u6b21\u6d4b\u8bc4\u63d0\u4f9b L{recommended} \u7684\u8bcd\u4e49\u8bc6\u522b\u96be\u5ea6\u53c2\u8003\uff1b"
        f"\u5b9e\u9645\u9898\u5e93\u8986\u76d6 L{min(levels)}\u2014L{max(levels)}\uff0c\u5c1a\u672a\u6807\u51c6\u5316\u6821\u51c6\u3002"
        "\u8bcd\u91cf\u533a\u95f4\u4ec5\u4f5c\u8bbe\u7f6e\u8d77\u70b9\u7684\u53c2\u8003\uff0c\u5176\u4ed6\u6280\u80fd\u5c1a\u672a\u6d4b\u91cf\u3002"
    )
    return result


def _tokens(text):
    return {re.sub(r"\s+", "", value).casefold() for value in re.split(r"[;\uff1b,\uff0c\u3001/\uff08\uff09()\n]", text) if value.strip()}


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
    confidence = "Low" if answered < 50 or upper - lower > 3 else "Moderate"
    limited = min(levels) > 1 or max(levels) < 15 or upper >= max(levels)
    covered = sorted({answer["level"] for answer in record["answers"]})
    return {
        "recommended_level": recommended, "estimated_range": estimated_range,
        "suggested_baseline": round(sum(estimated_range) / 2),
        "confidence": confidence, "covered_levels": covered,
        "available_levels": list(levels), "limited_by_content": limited,
        "standardized": False, "answered_count": answered,
        "recognition_only": True,
        "summary": (f"This assessment suggests L{recommended} as a reference difficulty for word-meaning recognition. "
                    f"The available question bank covers L{min(levels)}\u2013L{max(levels)} and has not been standardized. "
                    "The vocabulary range is a reference for choosing a starting point. Other skills have not been measured."),
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
        raise ValueError("No unused questions remain. Questions cannot be repeated to reach the assessment count.")
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
    raise ValueError("The entries at this difficulty cannot produce four distinct answer options. Update the vocabulary pack.")


def create(words, content_version, self_rating, question_count, level_config, question_factory, timestamp):
    self_rating = normalize_rating(self_rating)
    if self_rating not in RATINGS:
        raise ValueError("Choose one of the available self-ratings.")
    if type(question_count) is not int or question_count not in QUESTION_COUNTS:
        raise ValueError("Choose an assessment length of 20, 50, 100, 200, or 500 questions.")
    eligible = deepcopy(_eligible_words(words))
    if len(eligible) < question_count:
        raise ValueError(f"There are {len(eligible)} distinct usable entries, fewer than {question_count} questions. Install more content first; questions will not be repeated.")
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
        raise ValueError("The assessment question has changed. Answer the current question.")
    updated = deepcopy(record)
    correct = option_id == question["correct_option_id"]
    updated["answers"].append({
        "id": str(uuid.uuid4()), "question_id": question["id"], "word_id": question["word_id"],
        "level": question["level"], "option_id": option_id, "correct": correct,
        "kind": "correct" if correct else "unknown" if option_id is None else "wrong",
        "choice_text": choices.get(option_id, UNKNOWN_ANSWER),
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
        raise ValueError("The assessment archive contains inconsistent questions, answers, or results.")
    if record.get("algorithm_version") != ALGORITHM_VERSION or normalize_rating(record.get("self_rating")) not in RATINGS:
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
            if type(response["correct"]) is not bool or response["correct"] != correct or response["kind"] != kind or not choice_matches(options, option_id, response["choice_text"]) or response["answer_text"] != sense["definition"]:
                fail()
            prefix["answers"].append(response)
    if record["status"] == "complete":
        if len(answers) != record["question_count"] or len(questions) != len(answers) or record["question"] is not None or not record["completed_at"] or (record["result"] != estimate(record) and record["result"] != _legacy_estimate(record)):
            fail()
    elif record["status"] == "in_progress":
        if len(answers) >= record["question_count"] or len(questions) != len(answers) + 1 or record["question"] != questions[-1] or record["completed_at"] is not None or record["result"]:
            fail()
    else:
        fail()
