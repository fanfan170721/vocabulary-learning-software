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
VERSION = "content-0.2.1-en"
FREQUENCY_MAX = (500, 1000, 1700, 2600, 3800, 5400, 7500, 10000, 14000, 20000, 28000, 36000, 44000, None)
POS = {"n": "noun", "vt": "verb", "vi": "verb", "v": "verb", "a": "adjective", "s": "adjective", "adj": "adjective", "ad": "adverb", "r": "adverb", "adv": "adverb", "interj": "interjection", "num": "numeral"}
POS_ID = {"noun": "n", "verb": "v", "adjective": "a", "adverb": "ad", "interjection": "int", "numeral": "num"}
BAD_DEFINITION = re.compile(r"personal name|given name|surname|past tense|past participle|present participle|plural (?:form )?of|comparative of|superlative of|abbreviation|acronym|prefix|suffix|vulgar|sexual intercourse|penis|vagina", re.IGNORECASE)
PROPER_NOTE = re.compile(r"\([^)]*(?:city|university|capital|dynasty|county|harbor)[^)]*\)", re.IGNORECASE)
EXCLUDED_LEMMAS = {"york", "harrow", "positivistic", "genetically", "biologically"}
BASIC_WORDS = """hi hello yes no please thanks goodbye welcome sorry okay morning afternoon night today friend man woman boy girl child mother father sister brother name home room bed table desk teacher student class food rice soup tea coffee meat fruit red blue green yellow black white one two three four five ten small big hot cold happy sad come go eat drink sit stand walk sleep help look see hear know read write love like open day week year""".split()
# These brief everyday senses are curated explicitly, rather than selecting an
# unrelated noun sense of a greeting because it happens to appear first upstream.
BASIC_SENSES = {
    "hi": ("interjection", "an informal greeting"), "hello": ("interjection", "a greeting used when meeting someone or answering the telephone"),
    "yes": ("adverb", "used to express agreement or an affirmative answer"), "no": ("adverb", "used to give a negative answer"),
    "please": ("adverb", "used to make a request more polite"), "thanks": ("interjection", "an expression of gratitude"),
    "goodbye": ("interjection", "an expression used when leaving someone"), "welcome": ("interjection", "a greeting expressing pleasure at someone's arrival"),
    "sorry": ("adjective", "feeling sadness or regret"), "okay": ("adjective", "acceptable or satisfactory"),
}
SPECIALIST_TERMS = {
    "medicine": """electroencephalography immunohistochemistry immunofluorescence immunopathology hematopoiesis erythropoiesis thrombocytopenia leukocytosis glomerulonephritis encephalomyelitis neurophysiology electrophysiology pharmacokinetics pharmacodynamics pathophysiology histopathology anastomosis bronchoscopy endarterectomy cholecystectomy""".split(),
    "physics": """magnetohydrodynamics superconductivity ferromagnetism antiferromagnetism paramagnetism electrodynamics magnetoresistance magnetostriction birefringence anisotropy electroluminescence thermoluminescence renormalization quantization""".split(),
    "chemistry": """spectrophotometry spectrofluorometry chemiluminescence thermogravimetry microencapsulation polarography stereochemistry polycondensation transesterification isomerization hydroxyapatite immunoelectrophoresis ultracentrifugation""".split(),
    "engineering": """photolithography microfabrication micromachining optoelectronics photogrammetry tribology""".split(),
    "math": """automorphism homeomorphism homomorphism cohomology differentiability integrability orthogonality""".split(),
}
TERM_DOMAINS = {word: domain for domain, words in SPECIALIST_TERMS.items() for word in words}
# Curated English glosses also cover specialist entries whose English source
# field is empty. Keep these aligned with the bundled specialist meanings.
TERM_DEFINITIONS = {
    "electroencephalography": "the recording of electrical activity in the brain",
    "immunohistochemistry": "the detection of tissue components using antibodies and chemical markers",
    "immunofluorescence": "a technique using fluorescent antibodies to detect particular substances",
    "immunopathology": "the study of diseases caused by or involving immune responses",
    "hematopoiesis": "the formation of blood cells",
    "erythropoiesis": "the production of red blood cells",
    "thrombocytopenia": "an abnormally low number of blood platelets",
    "leukocytosis": "an abnormally high number of white blood cells",
    "glomerulonephritis": "inflammation of the kidney's filtering structures",
    "encephalomyelitis": "inflammation of the brain and spinal cord",
    "neurophysiology": "the study of how the nervous system functions",
    "electrophysiology": "the study of electrical properties and activity in living tissues",
    "pharmacokinetics": "the study of how a drug is absorbed, distributed, metabolized, and eliminated",
    "pharmacodynamics": "the study of the effects and mechanisms of drugs in the body",
    "pathophysiology": "the study of functional changes caused by disease",
    "histopathology": "the microscopic study of diseased tissues",
    "anastomosis": "a connection between vessels or passages; surgery to create such a connection",
    "bronchoscopy": "examination of the airways using a viewing instrument",
    "endarterectomy": "surgical removal of the inner lining of an artery",
    "cholecystectomy": "surgical removal of the gallbladder",
    "magnetohydrodynamics": "the study of electrically conducting fluids interacting with magnetic fields",
    "superconductivity": "the ability to conduct electricity without resistance under certain conditions",
    "ferromagnetism": "strong magnetism caused by aligned magnetic moments",
    "antiferromagnetism": "magnetic ordering in which neighboring moments align in opposite directions",
    "paramagnetism": "weak attraction to an applied magnetic field",
    "electrodynamics": "the study of electric charges in motion and their interactions",
    "magnetoresistance": "a change in electrical resistance caused by a magnetic field",
    "magnetostriction": "a change in a material's dimensions caused by magnetization",
    "birefringence": "the splitting of light into two rays with different refractive indices",
    "anisotropy": "variation of physical properties with direction",
    "electroluminescence": "the emission of light in response to an electric current or field",
    "thermoluminescence": "the emission of light when a previously irradiated material is heated",
    "renormalization": "a mathematical procedure for redefining parameters to handle infinities in physical theories",
    "quantization": "the restriction of a physical quantity to discrete values",
    "spectrophotometry": "measurement of light absorption or transmission at different wavelengths",
    "spectrofluorometry": "measurement of fluorescent light intensity across wavelengths",
    "chemiluminescence": "the emission of light as a result of a chemical reaction",
    "thermogravimetry": "measurement of changes in mass as temperature changes",
    "microencapsulation": "the enclosure of substances within microscopic capsules",
    "polarography": "an electrochemical analysis method measuring current at a mercury electrode",
    "stereochemistry": "the study of the spatial arrangement of atoms in molecules",
    "polycondensation": "polymer formation through repeated condensation reactions",
    "transesterification": "a reaction that exchanges the alcohol-derived group of an ester",
    "isomerization": "conversion of a compound into another with the same formula but a different structure",
    "hydroxyapatite": "a calcium phosphate mineral forming much of bone and tooth enamel",
    "immunoelectrophoresis": "a technique combining electrophoretic separation with antibody reactions",
    "ultracentrifugation": "separation using exceptionally high-speed centrifugal rotation",
    "photolithography": "a process using light to transfer microscopic patterns onto a surface",
    "microfabrication": "the manufacture of structures on a microscopic scale",
    "micromachining": "precision shaping or cutting at a microscopic scale",
    "optoelectronics": "the study and use of electronic devices that interact with light",
    "photogrammetry": "measurement and mapping using photographs",
    "tribology": "the study of friction, wear, and lubrication",
    "automorphism": "a structure-preserving mapping of a mathematical object onto itself",
    "homeomorphism": "a continuous one-to-one mapping with a continuous inverse",
    "homomorphism": "a mapping that preserves algebraic operations or structure",
    "cohomology": "an algebraic-topological system assigning groups to spaces using cochains",
    "differentiability": "the property of having a derivative",
    "integrability": "the property of admitting an integral",
    "orthogonality": "the property of being perpendicular or having a zero inner product",
}
SYNONYMS = (
    ("large", "big", "huge", "gigantic"), ("small", "little", "tiny"),
    ("begin", "start", "commence"), ("finish", "complete", "end", "terminate"),
    ("speak", "talk", "say"), ("beautiful", "pretty", "good-looking"),
    ("quick", "rapid", "fast"), ("happy", "glad", "joyful", "cheerful"),
    ("sad", "sorrowful", "unhappy"), ("learn", "study"),
    ("ask", "inquire", "question"), ("answer", "reply", "respond"),
    ("obtain", "get", "acquire"), ("buy", "purchase"), ("help", "assist", "aid"),
    ("work", "labor", "labour"), ("position", "post", "job"), ("mistake", "error"),
    ("important", "significant"), ("difficult", "hard"), ("easy", "simple"),
    ("clever", "smart", "intelligent"), ("child", "kid"),
    ("woman", "female adult"), ("man", "male adult"),
    ("room", "chamber"), ("home", "residence", "dwelling"), ("road", "street"),
    ("gift", "present"), ("ability", "talent", "capacity"), ("strong", "robust"),
    ("gather", "collect", "assemble"), ("maintain", "keep", "retain"),
    ("recover", "restore", "repair"), ("accurate", "correct", "precise"),
    ("demonstrate", "show", "reveal"), ("explain", "clarify"),
    ("goodbye", "farewell"), ("hello", "hi"), ("thanks", "gratitude"),
    ("reliable", "dependable", "trustworthy"),
)
ALIASES = {token: group[0] for group in SYNONYMS for token in group}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tokens(definition):
    return {part.strip().lower() for part in re.split(r"[;,/]", definition) if part.strip()}


def canonical(definition):
    return {ALIASES.get(part, part) for part in tokens(definition)}


def short_definition(text, *, specialist=False):
    if BAD_DEFINITION.search(text) or PROPER_NOTE.search(text):
        return None
    text = re.sub(r"\[[^\]]*\]", "", text).strip()
    text = re.sub(r"\s+", " ", text.replace("_", " ")).strip()
    if not re.search(r"[A-Za-z]", text) or re.search(r"[\u3400-\u9fff]", text):
        return None
    # Keep a complete gloss rather than cutting an English clause mid-sentence.
    if len(text) > 240:
        first_clause = text.split(";", 1)[0].strip()
        if len(first_clause) > 240:
            return None
        text = first_clause
    return text if len(text) >= 3 else None


def source_senses(row, *, specialist=False):
    result = []
    seen_pos = set()
    # ECDICT provides English glosses separately from Chinese translations.
    # WordNet-derived entries also use r/s and sometimes omit the period.
    for line in re.split(r"\\+n|\r?\n", row.get("definition", "")):
        match = re.match(r"^\s*(interj|num|adj|adv|vt|vi|ad|n|v|a|r|s)\b\s*\.?\s+(.+)$", line)
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
        for line in re.split(r"\\+n|\r?\n", row.get("definition", "")):
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
                                        "language": "en"} for pos, definition in senses],
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
    if any(sense.get("language") != "en" for word in seed for sense in word["senses"]):
        raise ValueError("Seed content must already contain English definitions before importing.")
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
            if any(pos == "noun" for pos, _ in senses) and lemma.endswith(("ity", "ism", "ization", "isation", "ology")):
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
    output = {"version": VERSION, "source": "Project seed entries and a curated selection from a pinned ECDICT revision", "license": "mixed-see-sources",
              "sources": [
                  {"id": "project-original-seed", "url": "", "revision": "seed-0.1.0", "sha256": hashlib.sha256(json.dumps(seed, ensure_ascii=False, sort_keys=True).encode()).hexdigest(), "license": "project-original-seed"},
                  {"id": "ecdict", "url": SOURCE_URL, "revision": REVISION, "sha256": CSV_SHA256, "license": "MIT", "license_url": LICENSE_URL, "license_sha256": LICENSE_SHA256, "retrieved_on": SOURCE_DATE}],
              "selection": {"algorithm": "frequency-concrete-abstract-specialist-en-0.1", "calibrated": False,
                            "source_rows": total_rows, "general_candidates": {str(k): len(v) for k, v in sorted(candidates.items())},
                            "requested_additions_per_level": per_level, "shortages": shortages,
                            "missing_basic": missing_basic, "missing_specialists": specialist_missing},
              "words": words, "word_sets": original_sets}
    if re.search(r"[\u3400-\u9fff]", json.dumps(output, ensure_ascii=False)):
        raise ValueError("Generated content must contain English text only.")
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
        levels["classification"] = "Curated everyday communication, frequency and abstraction heuristics, and specialist terms; not standardized or calibrated"
        for item in levels["levels"]:
            level = item["level"]
            item["seed_available"] = bool(counts[level])
            item["content_word_count"] = counts[level]
            if level == 1:
                item["description"] = "Greetings, everyday communication, and concrete objects; an initial internal level, not standardized or calibrated."
            elif level == 15:
                item["title"] = "Specialist terms"
                item["description"] = "Selected terms from medicine, physics, chemistry, engineering, and mathematics; not a certification of the world's hardest vocabulary, and not standardized or calibrated."
            else:
                item["description"] = "An internal recommendation based on frequency and abstraction; field and personal background affect actual difficulty. Not standardized or calibrated."
                item["frequency_rank_max"] = FREQUENCY_MAX[level - 1]
        for rating in levels["self_ratings"]:
            if rating["id"] == "advanced":
                rating["notes"] = "User self-rating for the initial recommendation only; it does not establish specific known words or unmeasured skills."
        levels_path.write_text(json.dumps(levels, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"version": VERSION, "words": len(output["words"]), "senses": sum(len(w["senses"]) for w in output["words"]), "levels": dict(sorted(Counter(w["level"] for w in output["words"]).items())), "selection": output["selection"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
