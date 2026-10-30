"""English content import regression coverage without downloading source data."""

import importlib.util
from pathlib import Path
import unittest


SPEC = importlib.util.spec_from_file_location(
    "import_ecdict", Path(__file__).resolve().parents[1] / "scripts" / "import_ecdict.py"
)
import_ecdict = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(import_ecdict)


class EnglishContentImportTests(unittest.TestCase):
    def test_source_uses_english_glosses_with_wordnet_pos_and_escaped_lines(self):
        row = {
            "word": "sample",
            "definition": r"n. a representative part\nn. a second noun sense\nv. to examine a small part",
            "translation": "n. \u4e2d\u6587\u91ca\u4e49",
        }
        self.assertEqual(import_ecdict.source_senses(row), [
            ("noun", "a representative part"),
            ("verb", "to examine a small part"),
        ])
        self.assertEqual(import_ecdict.source_senses({"definition": "a. bright\nr. brightly"}), [
            ("adjective", "bright"), ("adverb", "brightly"),
        ])
        self.assertEqual(import_ecdict.source_senses({"definition": "n a flowering plant"}), [
            ("noun", "a flowering plant"),
        ])
        self.assertEqual(import_ecdict.source_senses({"definition": "s. very small"}), [
            ("adjective", "very small"),
        ])

    def test_missing_english_never_falls_back_to_chinese_translation(self):
        row = {"definition": "", "translation": "n. \u4e2d\u6587\u91ca\u4e49"}
        self.assertEqual(import_ecdict.source_senses(row), [])
        self.assertEqual(import_ecdict.source_senses(row, specialist=True), [])
        self.assertIsNone(import_ecdict.short_definition("\u4e2d\u6587\u91ca\u4e49"))

    def test_specialist_terms_have_curated_english_when_source_is_missing(self):
        self.assertEqual(set(import_ecdict.TERM_DEFINITIONS), set(import_ecdict.TERM_DOMAINS))
        for lemma, definition in import_ecdict.TERM_DEFINITIONS.items():
            with self.subTest(lemma=lemma):
                self.assertIsNotNone(import_ecdict.short_definition(definition, specialist=True))
                self.assertNotEqual(definition.lower(), lemma)

    def test_imported_word_retains_stable_ids_and_declares_english_senses(self):
        word = import_ecdict.make_word(
            {"word": "sample", "frq": "300", "bnc": "200", "phonetic": ""},
            2, [("noun", "a representative part")],
        )
        self.assertEqual(word["id"], "en.sample")
        self.assertEqual(word["senses"][0], {
            "id": "en.sample.ecdict.n", "pos": "noun",
            "definition": "a representative part", "language": "en",
        })
        self.assertEqual(word["provenance"]["revision"], import_ecdict.REVISION)


if __name__ == "__main__":
    unittest.main()
