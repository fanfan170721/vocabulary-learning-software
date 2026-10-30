# Content and configuration

## Current scope

`vocabulary_app/resources/content.json`, version `content-0.2.1-en`, contains **1,080 distinct English lemmas and 1,274 senses**. It retains all 180 original project seed lemmas and adds 900 ECDICT lemmas. Every level from L1 through L15 contains actual content. The interface and bundled definitions are in English. English localization preserves the bundled words, sense IDs, levels, parts of speech, synonym groups, and source records.

| Internal level | Lemmas | Content direction |
| --- | ---: | --- |
| L1 | 90 | Greetings, everyday communication, concrete objects |
| L2–L6 | 90 each | Basic expressions through general abstract expressions |
| L7–L14 | 60 each | Advanced words selected using frequency and abstraction heuristics |
| L15 | 60 | Specialist terminology in medicine, physics, chemistry, engineering, mathematics |

L1 adds basic communication words including hi, hello, yes, no, please, thanks, goodbye, and welcome. `how are you` is a phrase and is not counted as a newly assembled word. Existing multiple-sense words such as bank, light, and right still count as one stable lemma each.

The catalog supplies 500 distinct lemmas for actual assessment questions and enough content for multiple 20-word sessions. This does not establish a standardized English proficiency assessment. Every session must use 20 distinct lemmas. If there are insufficient candidates, report the need to adjust difficulty or expand content rather than duplicating entries.

## Sources, pinned revision, and licenses

The original 180 words use `project-original-seed`, an internal content license identifier for local development, learning, and demos. Before public distribution, the project author must choose and record an external content license. This identifier is not an alias for MIT.

The added entries come from the [official ECDICT repository](https://github.com/skywind3000/ECDICT) under the MIT license supplied with the pinned revision. The complete license is retained in `vocabulary_app/resources/licenses/ECDICT-MIT.txt` and distributed with app resources. Its copyright notice is `Copyright (c) 2025 Linwei`. Content and code licenses are managed separately. The ECDICT entries' license does not rewrite the license of the original 180 words.

Recorded source acquisition:

- Retrieval date: 2026-10-24.
- Pinned commit: `ab22ad36302cafc6349a050e2b60894855208055`.
- [Full CSV](https://raw.githubusercontent.com/skywind3000/ECDICT/ab22ad36302cafc6349a050e2b60894855208055/ecdict.csv): 770,611 rows, 66,009,548 bytes.
- CSV SHA-256: `d1ecbdf9ee2b920afb6f430ca6b6bb9f559588cf0dff86e04bd255f9390843cc`.
- [License at that commit](https://raw.githubusercontent.com/skywind3000/ECDICT/ab22ad36302cafc6349a050e2b60894855208055/LICENSE) SHA-256: `f8552dd246f61a4e064569eae6194a01c6b3d63b03bf27c6ca863593c549ed0f`.

The same revision's `ecdict.mini.csv` has only 53 rows, including many affixes and chemistry terms, and was not used to imply sufficient assessment coverage. Full downloads are kept in the ignored `artifacts/content-sources/` directory. The app carries only selected JSON and license text. No upstream programs were downloaded or executed.

`sources` records URLs, revision, SHA-256, licenses, and retrieval date. Each added word records `provenance`, its source lemma, frequency source, and license. No commercial dictionary content, examples, articles, or audio was imported. Source phonetics can contain older notation and still require review. Bundled English definitions were curated during localization. Continue reviewing language quality before public release and correct content by stable ID with a content version update.

## Import and regeneration

From the project root:

```powershell
.\.venv\Scripts\python.exe scripts\import_ecdict.py --download
```

Rebuild offline after downloading:

```powershell
.\.venv\Scripts\python.exe scripts\import_ecdict.py
```

Report selection without writing resources:

```powershell
.\.venv\Scripts\python.exe scripts\import_ecdict.py --dry-run
```

The script pins the revision and both hashes and verifies them before parsing. It does not follow upstream branch changes automatically. By default, it adds 60 words per level. It retains the current content file's original 180 `project-original-seed` objects and target word sets. Do not use it to overwrite an unrelated content pack of unknown origin. Everyday app use needs neither the CSV nor a network connection.

The importer uses ECDICT's English `definition` field and English filters and curated overrides. The earlier selection was originally generated using another source language; English definition coverage and parts-of-speech coverage differ. A fresh import can therefore select different added entries or senses from those in the bundled, individually localized catalog. Review regenerated content and compatibility before replacing a released catalog. Stable ID formats remain the same; rerunning the same importer and inputs should give the same selection.

A verified dry run against the full pinned, hash-checked source produced 1,080 words and 1,180 senses, with 90 words per level at L1–L6 and 60 at L7–L15. It reported no missing basic words, missing specialist terms, or level shortages. This is the regeneration result; the bundled curated English catalog retains the original 1,274 senses.

Selection requires lowercase word forms, valid lemmas, clear parts of speech, and usable concise definitions. It filters proper names, purely inflected forms, affixes, incomplete definitions, and similar unsuitable entries. Ordinary additions use `frq`, falling back to `bnc`; ordinary candidates without valid frequency data are excluded. Curated specialist terms can lack frequency data, but their source and field remain recorded. Reselecting content does not change the original 180 entries' IDs, senses, levels, or existing synonym tags.

## Levels and self-ratings

`levels.json` defines 15 internal levels and retains `calibrated: false`.

- L1 deliberately includes basic everyday communication and is not simply the most frequent words in a corpus.
- L2–L14 use frequency and abstraction heuristics. Ordinary frequency thresholds use 1,000, 1,700, 2,600, 3,800, 5,400, 7,500, 10,000, 14,000, 20,000, 28,000, 36,000, and 44,000 before reaching L14. English abstract-noun heuristics can raise a candidate's level. These are initial selection rules, not a calibrated difficulty model.
- L15 independently selects specialist terminology: currently 20 medical, 14 physics, 13 chemistry, 6 engineering, and 7 mathematics words. A word can span fields; configuration records one primary field.

Examples from L15:

| Field | Lemma | Meaning |
| --- | --- | --- |
| Medicine | electroencephalography | Recording electrical activity of the brain |
| Medicine | immunohistochemistry | Identifying substances in tissue using antibodies |
| Physics | magnetohydrodynamics | Study of conducting fluids in magnetic fields |
| Physics | antiferromagnetism | Magnetism with opposing adjacent magnetic moments |
| Chemistry | spectrophotometry | Measuring light intensity at selected wavelengths |
| Chemistry | transesterification | Exchanging an ester's alcohol component |
| Engineering | photolithography | Patterning a surface using light |
| Engineering | tribology | Study of friction, wear, and lubrication |
| Mathematics | cohomology | An algebraic method for studying topological spaces |
| Mathematics | orthogonality | Perpendicularity or a corresponding independent relation |

Field knowledge affects actual difficulty; specialists may know some L15 words well. These are not claimed to be the world's hardest words. Original seed levels may not exactly match the frequency bands of additions. Their levels are retained for compatibility with existing study records. Every level has real content, but each remains a small selection rather than a complete level list.

`estimated_range` is an adjustable initial estimate, recorded separately from `frequency_rank_max`. A corpus frequency rank is not an individual's exact mastered word count. `self_ratings` retains eight onboarding options used only for initial recommendations. Native speakers and professional English learners are not strictly ordered. Untested listening, speaking, reading, and writing remain unknown. Meaning-question results do not guarantee passing an exam.

## Entries, pronunciation, and questions

Entries contain `id`, `lemma`, language, phonetics, level, senses, forms, tags, sources, and licenses. Added lemma IDs use `en.<lemma>` and sense IDs use `en.<lemma>.ecdict.<part-of-speech-tag>`. Other senses or parts of speech of the same word do not increase the distinct word count. `forms` stores only source-confirmed forms and does not automatically merge derived words into a lemma.

Original seed phonetics mostly use common broad American notation. ECDICT phonetics retain the source, mostly British and some older notation, and have not been unified into modern IPA. Missing phonetics stay empty rather than being invented. No audio recordings are included. Local pronunciation is provided by the application adapter; a missing corresponding English voice must show an actual unavailable state while preserving text learning.

Definitions are concise English explanations. Questions must identify parts of speech clearly. Other correct senses of the same word cannot be used as wrong answers.

Different wording can still express similar meanings. The original seed has `synonym_group` hints across 11 groups and 27 senses. Added entries also retain synonym groups. Question construction excludes overlapping synonyms and duplicate meanings. Different group names alone do not guarantee unambiguous questions forever; content revisions must still review meaning and context. If four unambiguous options cannot be formed, choose another word or report the problem instead of inventing a false definition.

The prior catalog verification covered 500 four-choice questions using distinct lemmas and 100 random 20-word pools per level, totaling 30,000 graded questions. Each could form four options from its own original pool. This checks source size and structure, not human language quality. English localization requires its own verification; prior results do not by themselves verify the revised definitions.

## Target word sets and content upgrades

The official `cet4` list remains uninstalled: `complete: false` and empty `word_ids`. It cannot show 100% or award completion. ECDICT's `cet4` tags were not used as an official target list, and no selected subset is described as complete CET-4 coverage.

`sample-basic` retains the original 20 stable lemmas and tests only set coverage and accounting rules. Its name explicitly identifies it as an unofficial sample, rather than an official CET-4 list. Creating a goal saves its version and denominator snapshots; content updates cannot change existing goals. CET-4 completes only when every distinct valid lemma in a nonempty complete set is mastered. Internal difficulty L4 is not CET-4.

Keep stable IDs when changing spelling, definitions, icons, or display order. Merging lemmas needs an old-to-new ID migration. The study database and content resources are separate; replacing resources must not clear sessions, mistakes, mastered words, goals, or achievements. Old sessions keep their own word and question snapshots, preserving the evidence of what appeared at the time.

Legacy stock definitions, prompts, and result text are translated only when presented. The saved originals, answers, scoring, and completion records remain intact, including during export and import validation. Exact stock-text mappings provide English display without altering historical evidence. Personal names and user-written content are retained. The interface text loader recognizes saved copies of old defaults and adopts the corresponding English defaults while preserving personal edits.

## Achievements and future content

`achievements.json` retains the first learning start and milestones for 100, 200, 500, 1,000, 2,000, and 3,000 word practices in newly completed sessions. Replaying old sessions can add practice history without increasing this achievement metric. Practice word counts are not net new words. Keep achievement IDs when editing titles and descriptions. Replacing icons or models must not delete earned records.

Articles, reading questions, writing prompts, historical facts, and other language content are outside this catalog expansion. Later content must separately record stable IDs, versions, answers and evidence, sources, licenses, and required attribution. Placeholder entry points do not count as implemented features.
