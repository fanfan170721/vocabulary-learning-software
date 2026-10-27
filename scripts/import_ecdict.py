"""Build a small, reproducible learning collection from pinned ECDICT CSV data."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import re
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
RESOURCES = ROOT / "vocabulary_app" / "resources"
REVISION = "ab22ad36302cafc6349a050e2b60894855208055"
SOURCE_URL = f"https://raw.githubusercontent.com/skywind3000/ECDICT/{REVISION}/ecdict.csv"
LICENSE_URL = f"https://raw.githubusercontent.com/skywind3000/ECDICT/{REVISION}/LICENSE"
CSV_SHA256 = "d1ecbdf9ee2b920afb6f430ca6b6bb9f559588cf0dff86e04bd255f9390843cc"
LICENSE_SHA256 = "f8552dd246f61a4e064569eae6194a01c6b3d63b03bf27c6ca863593c549ed0f"
SOURCE_DATE = "2026-10-24"
VERSION = "content-0.2.0"
FREQUENCY_MAX = (500, 1000, 1700, 2600, 3800, 5400, 7500, 10000, 14000, 20000, 28000, 36000, 44000, None)
POS = {"n": "noun", "vt": "verb", "vi": "verb", "v": "verb", "a": "adjective", "adj": "adjective", "ad": "adverb", "adv": "adverb", "interj": "interjection", "num": "numeral"}
POS_ID = {"noun": "n", "verb": "v", "adjective": "a", "adverb": "ad", "interjection": "int", "numeral": "num"}
BAD_DEFINITION = re.compile(r"人名|地名|姓氏|男子名|女子名|过去式|过去分词|现在分词|复数形式|的复数|比较级|最高级|缩写|略语|字母|词尾|前缀|后缀|国人|美国|英国|人种|脏话|性交|阴茎|阴道")
PROPER_NOTE = re.compile(r"[（(][^）)]*(?:城市|大学|首都|王朝|州名|郡名|港口)[^）)]*[）)]")
EXCLUDED_LEMMAS = {"york", "harrow", "positivistic", "genetically", "biologically"}
BASIC_WORDS = """hi hello yes no please thanks goodbye welcome sorry okay morning afternoon night today friend man woman boy girl child mother father sister brother name home room bed table desk teacher student class food rice soup tea coffee meat fruit red blue green yellow black white one two three four five ten small big hot cold happy sad come go eat drink sit stand walk sleep help look see hear know read write love like open day week year""".split()
# These brief everyday senses are curated explicitly, rather than selecting an
# unrelated noun sense of a greeting because it happens to appear first upstream.
BASIC_SENSES = {
    "hi": ("interjection", "嗨；你好"), "hello": ("interjection", "喂；你好"),
    "yes": ("adverb", "是；对"), "no": ("adverb", "不"),
    "please": ("adverb", "请"), "thanks": ("interjection", "谢谢；谢谢你"),
    "goodbye": ("interjection", "再见"), "welcome": ("interjection", "欢迎"),
    "sorry": ("adjective", "难过的；遗憾的"), "okay": ("adjective", "好；可以；行"),
}
SPECIALIST_TERMS = {
    "medicine": """electroencephalography immunohistochemistry immunofluorescence immunopathology hematopoiesis erythropoiesis thrombocytopenia leukocytosis glomerulonephritis encephalomyelitis neurophysiology electrophysiology pharmacokinetics pharmacodynamics pathophysiology histopathology anastomosis bronchoscopy endarterectomy cholecystectomy""".split(),
    "physics": """magnetohydrodynamics superconductivity ferromagnetism antiferromagnetism paramagnetism electrodynamics magnetoresistance magnetostriction birefringence anisotropy electroluminescence thermoluminescence renormalization quantization""".split(),
    "chemistry": """spectrophotometry spectrofluorometry chemiluminescence thermogravimetry microencapsulation polarography stereochemistry polycondensation transesterification isomerization hydroxyapatite immunoelectrophoresis ultracentrifugation""".split(),
    "engineering": """photolithography microfabrication micromachining optoelectronics photogrammetry tribology""".split(),
    "math": """automorphism homeomorphism homomorphism cohomology differentiability integrability orthogonality""".split(),
}
TERM_DOMAINS = {word: domain for domain, words in SPECIALIST_TERMS.items() for word in words}
# A few source entries contain optional characters or a long parenthetical
# explanation. These concise readings retain the documented source meaning.
TERM_DEFINITIONS = {
    "anastomosis": "吻合；吻合术",
    "immunopathology": "免疫病理学", "bronchoscopy": "支气管镜检查",
    "thermogravimetry": "热重分析法", "photolithography": "光刻法",
    "homeomorphism": "同胚", "homomorphism": "同态",
    "orthogonality": "正交性", "microencapsulation": "微囊包封",
    "transesterification": "酯交换反应", "pharmacokinetics": "药动学",
}
SYNONYMS = (
    ("大", "大的", "巨大的", "巨人般的"), ("小", "小的", "微小的"),
    ("开始", "起始", "开头", "开端"), ("结束", "完成", "终结", "终止"),
    ("说", "说话", "讲话", "交谈", "谈话", "谈论"),
    ("美丽的", "漂亮的", "好看的"), ("快速的", "迅速的", "快的"),
    ("高兴的", "快乐的", "愉快的", "开心的"), ("悲伤的", "伤心的", "难过的", "悲哀的"),
    ("学习", "研习"), ("询问", "问", "提问"), ("回答", "答复", "回应"),
    ("得到", "获得", "取得"), ("购买", "买", "购入"), ("帮助", "协助", "援助"),
    ("工作", "劳动"), ("职位", "职务", "岗位"), ("错误", "差错", "过失"),
    ("重要的", "重大的", "要紧的"), ("困难的", "艰难的", "难的"),
    ("容易的", "简单的", "简易的"), ("聪明的", "机智的", "明智的"),
    ("孩子", "儿童", "小孩"), ("女人", "妇女", "女性"), ("男人", "男性", "男子"),
    ("屋子", "房间", "室"), ("住所", "住宅", "住处"), ("道路", "路", "街道"),
    ("书", "书籍"), ("食物", "食品"), ("礼物", "赠品"),
    ("能力", "才能", "才干"), ("强壮的", "强健的", "健壮的"),
    ("聚集", "集合", "收集"), ("维持", "保持", "保留"),
    ("恢复", "康复", "恢复原状", "修复", "修理"), ("准确的", "正确的", "精确的"),
    ("演示", "表明", "揭示"), ("解释", "阐明", "说明", "澄清"),
    ("再见", "告别"), ("你好", "嗨", "喂", "嘿"), ("谢谢", "感谢", "谢意", "谢谢你"),
    ("可靠", "可靠性", "信度", "可信度", "可信赖", "可信用", "确实性"),
)
ALIASES = {token: group[0] for group in SYNONYMS for token in group}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tokens(definition):
    return {part.strip() for part in re.split(r"[;；,，、/]", definition) if part.strip()}


def canonical(definition):
    return {ALIASES.get(part, part) for part in tokens(definition)}


def short_definition(text, *, specialist=False):
    if BAD_DEFINITION.search(text) or PROPER_NOTE.search(text):
        return None
    text = re.sub(r"\[[^\]]*\]", "", text).strip()
    text = re.sub(r"\([^)]*\)|（[^）]*）", "", text)
    if BAD_DEFINITION.search(text):
        return None
    pieces = re.split(r"[,，;；、]", text)
    result = []
    for piece in pieces:
        piece = piece.strip()
        if not re.fullmatch(r"[\u3400-\u9fff]{1,12}", piece):
            if not result:
                return None
            break
        if piece in {"使", "表示", "指", "为", "从", "对", "关于", "用", "及", "等", "的", "和"}:
            return None
        if piece not in result:
            result.append(piece)
        if len(result) == (2 if specialist else 3):
            break
    return "；".join(result) if result and len("；".join(result)) <= 30 else None


def source_senses(row, *, specialist=False):
    result = []
    seen_pos = set()
    for line in re.split(r"\\+n|\r?\n", row["translation"]):
        match = re.match(r"^\s*(n|vt|vi|v|a|adj|ad|adv|interj|num)\s*\.\s*(.+)$", line)
        if not match:
            continue
        pos = POS[match[1]]
        definition = short_definition(match[2], specialist=specialist)
        if definition and pos not in seen_pos:
            result.append((pos, definition))
            seen_pos.add(pos)
        if len(result) == 2:
            break
    if specialist and not result:
        # The curated list contains named scientific entities/processes, nouns.
        # Upstream sometimes supplies just a subject label instead of "n.".
        for line in re.split(r"\\+n|\r?\n", row["translation"]):
            definition = short_definition(line, specialist=True)
            if definition:
                result.append(("noun", definition))
                break
    return result


def frequency(row):
    values = {key: int(row.get(key) or 0) for key in ("frq", "bnc")}
    return values["frq"] or values["bnc"], values


def near_seed_conflict(senses, seed_senses):
    for _, definition in senses:
        raw = tokens(definition)
        normalized = canonical(definition)
        for seed in seed_senses:
            # Exact shared tokens are already rejected by the question builder.
            # Avoid introducing a differently worded synonym of an immutable
            # original seed sense that has no synonym-group annotation.
            if normalized & canonical(seed["definition"]) and not raw & tokens(seed["definition"]) and not seed.get("synonym_group"):
                return True
    return False


def make_word(row, level, senses, *, domain=None):
    lemma = row["word"]
    rank, ranks = frequency(row)
    exchange = dict(piece.split(":", 1) for piece in row.get("exchange", "").split("/") if ":" in piece)
    forms = sorted({form for key, value in exchange.items() if key in {"p", "d", "i", "3", "r", "t", "s"}
                    for form in value.split("/") if re.fullmatch(r"[a-z]+", form) and form != lemma})
    word = {"id": f"en.{lemma}", "lemma": lemma, "language": "en", "phonetic": row.get("phonetic", "").strip(),
            "level": level, "senses": [{"id": f"en.{lemma}.ecdict.{POS_ID[pos]}", "pos": pos, "definition": definition,
                                        "language": "zh-CN"} for pos, definition in senses],
            "forms": forms, "tags": ["ecdict", "specialist" if domain else "general"] + ([domain] if domain else []),
            "source": "ECDICT / skywind3000", "license": "MIT",
            "provenance": {"source_id": "ecdict", "revision": REVISION, "source_word": lemma},
            "frequency": {"rank": rank, "basis": "frq" if ranks["frq"] else "bnc", **ranks}}
    if domain:
        word["domain"] = domain
    return word


def annotate_synonyms(seed, additions):
    senses = [sense for word in seed + additions for sense in word["senses"]]
    parents = list(range(len(senses)))
    def find(index):
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index
    owners = {}
    for index, sense in enumerate(senses):
        for token in canonical(sense["definition"]):
            if token in owners:
                parents[find(index)] = find(owners[token])
            else:
                owners[token] = index
    components = defaultdict(list)
    for index, sense in enumerate(senses):
        components[find(index)].append(sense)
    original_ids = {sense["id"] for word in seed for sense in word["senses"]}
    for component in components.values():
        if len(component) < 2:
            continue
        existing = sorted({sense["synonym_group"] for sense in component if sense.get("synonym_group")})
        group = existing[0] if existing else "ecdict-overlap-" + hashlib.sha256("|".join(sorted(s["id"] for s in component)).encode()).hexdigest()[:12]
        for sense in component:
            if sense["id"] not in original_ids:
                sense["synonym_group"] = group


def build(csv_path, content_path, per_level):
    current = json.loads(content_path.read_text(encoding="utf-8-sig"))
    seed = [word for word in current["words"] if word.get("license") == "project-original-seed"]
    if len(seed) != 180:
        raise ValueError("Expected the original 180 stable seed words; do not overwrite unknown content.")
    seed_lemmas = {word["lemma"] for word in seed}
    seed_senses = [sense for word in seed for sense in word["senses"]]
    candidates = defaultdict(list)
    special_rows, basic_rows = {}, {}
    total_rows = 0
    with csv_path.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            total_rows += 1
            lemma = row["word"]
            if lemma in TERM_DOMAINS:
                special_rows[lemma] = row
            if lemma in BASIC_WORDS:
                basic_rows[lemma] = row
            if not re.fullmatch(r"[a-z]{2,22}", lemma) or lemma in seed_lemmas or lemma in TERM_DOMAINS or lemma in BASIC_WORDS or lemma in EXCLUDED_LEMMAS:
                continue
            exchange = dict(piece.split(":", 1) for piece in row.get("exchange", "").split("/") if ":" in piece)
            if exchange.get("0") and exchange["0"] != lemma:
                continue
            if exchange.get("1"):
                continue
            rank, _ = frequency(row)
            senses = source_senses(row)
            if not rank or not senses or near_seed_conflict(senses, seed_senses):
                continue
            level = next((i + 1 for i, maximum in enumerate(FREQUENCY_MAX) if maximum is None or rank <= maximum), 14)
            level = max(2, level)
            if any(len(part) >= 3 and part.endswith(("性", "学", "化")) for _, definition in senses for part in tokens(definition)):
                level = min(14, level + 1)
            candidates[level].append((rank, lemma, row, senses))
    additions = []
    missing_basic = []
    for lemma in BASIC_WORDS:
        if lemma in seed_lemmas:
            continue
        row = basic_rows.get(lemma)
        if not row:
            missing_basic.append(lemma)
            continue
        senses = [BASIC_SENSES[lemma]] if lemma in BASIC_SENSES else source_senses(row)
        if senses and len([w for w in additions if w["level"] == 1]) < per_level:
            additions.append(make_word(row, 1, senses))
    shortages = {}
    for level in range(2, 15):
        selected = sorted(candidates[level], key=lambda item: (item[0], item[1]))[:per_level]
        if len(selected) < per_level:
            shortages[level] = len(selected)
        additions.extend(make_word(row, level, senses) for _, _, row, senses in selected)
    specialist_missing = []
    for lemma, domain in TERM_DOMAINS.items():
        row = special_rows.get(lemma)
        if not row:
            specialist_missing.append(lemma)
            continue
        senses = source_senses(row, specialist=True)
        if lemma in TERM_DEFINITIONS:
            senses = [("noun", TERM_DEFINITIONS[lemma])]
        if not senses:
            specialist_missing.append(lemma)
            continue
        additions.append(make_word(row, 15, senses[:1], domain=domain))
    annotate_synonyms(seed, additions)
    words = seed + additions
    if len({word["lemma"] for word in words}) != len(words):
        raise ValueError("Duplicate lemma in selected collection.")
    original_sets = current["word_sets"]
    output = {"version": VERSION, "source": "项目基础词条与固定版本 ECDICT 精选", "license": "mixed-see-sources",
              "sources": [
                  {"id": "project-original-seed", "url": "", "revision": "seed-0.1.0", "sha256": hashlib.sha256(json.dumps(seed, ensure_ascii=False, sort_keys=True).encode()).hexdigest(), "license": "project-original-seed"},
                  {"id": "ecdict", "url": SOURCE_URL, "revision": REVISION, "sha256": CSV_SHA256, "license": "MIT", "license_url": LICENSE_URL, "license_sha256": LICENSE_SHA256, "retrieved_on": SOURCE_DATE}],
              "selection": {"algorithm": "frequency-concrete-abstract-specialist-0.1", "calibrated": False,
                            "source_rows": total_rows, "general_candidates": {str(k): len(v) for k, v in sorted(candidates.items())},
                            "requested_additions_per_level": per_level, "shortages": shortages,
                            "missing_basic": missing_basic, "missing_specialists": specialist_missing},
              "words": words, "word_sets": original_sets}
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=ROOT / "artifacts/content-sources/ecdict.csv")
    parser.add_argument("--license", type=Path, default=ROOT / "artifacts/content-sources/ECDICT-LICENSE.txt")
    parser.add_argument("--output", type=Path, default=RESOURCES / "content.json")
    parser.add_argument("--per-level", type=int, default=60)
    parser.add_argument("--download", action="store_true", help="Download only the two pinned data/license files.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not 40 <= args.per_level <= 100:
        parser.error("--per-level must be between 40 and 100")
    if args.download:
        for url, path in ((SOURCE_URL, args.csv), (LICENSE_URL, args.license)):
            path.parent.mkdir(parents=True, exist_ok=True)
            request = urllib.request.Request(url, headers={"User-Agent": "VocabularyLearning-content-import"})
            with urllib.request.urlopen(request, timeout=60) as response:
                path.write_bytes(response.read())
    if digest(args.csv) != CSV_SHA256 or digest(args.license) != LICENSE_SHA256:
        raise ValueError("Pinned ECDICT CSV or license SHA-256 mismatch.")
    output = build(args.csv, args.output, args.per_level)
    if not args.dry_run:
        args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        license_target = RESOURCES / "licenses/ECDICT-MIT.txt"
        license_target.parent.mkdir(parents=True, exist_ok=True)
        license_target.write_bytes(args.license.read_bytes())
        levels_path = RESOURCES / "levels.json"
        levels = json.loads(levels_path.read_text(encoding="utf-8-sig"))
        counts = Counter(word["level"] for word in output["words"])
        levels["version"] = "levels-0.2.0"
        levels["calibrated"] = False
        levels["classification"] = "日常交流精选、词频与抽象性启发式、专业术语精选；未标准化校准"
        for item in levels["levels"]:
            level = item["level"]
            item["seed_available"] = bool(counts[level])
            item["content_word_count"] = counts[level]
            if level == 1:
                item["description"] = "问候、日常交流及具体事物；项目内初始档位，未标准化校准。"
            elif level == 15:
                item["title"] = "专业术语"
                item["description"] = "跨医学、物理、化学、工程与数学的精选专业术语；并非全球最难词汇认证，未标准化校准。"
            else:
                item["description"] = "结合词频与抽象性划分的项目内推荐档；领域与个人背景会影响实际难度，未标准化校准。"
                item["frequency_rank_max"] = FREQUENCY_MAX[level - 1]
        for rating in levels["self_ratings"]:
            if rating["id"] == "advanced":
                rating["notes"] = "用户自评；只用于初始推荐，不能据此推断具体已会词或未测技能。"
        levels_path.write_text(json.dumps(levels, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"version": VERSION, "words": len(output["words"]), "senses": sum(len(w["senses"]) for w in output["words"]), "levels": dict(sorted(Counter(w["level"] for w in output["words"]).items())), "selection": output["selection"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
