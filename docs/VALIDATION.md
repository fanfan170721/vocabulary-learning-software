# Phase 1 and version 0.2 validation record

This document translates the validation evidence recorded for the original 0.2 implementation. Those historical results do not by themselves verify a rebuilt English-localized release. Any new localization checks should be recorded separately with their actual results.

## English localization checks

- English catalog version: `content-0.2.1-en`. The interface and all 1,274 bundled definitions have been translated while retaining the 1,080 lemma IDs and existing sense identities.
- Six desktop integration tests passed for the English interface. This result is separate from the original release's 44-check historical record below.
- Four English importer regression tests passed. A dry run using the full pinned source after SHA-256 verification produced 1,080 words and 1,180 senses with the intended per-level counts and no missing basic words, missing specialist terms, or level shortages. The bundled curated catalog retains 1,274 senses; regeneration uses different English source coverage.
- A real profile generated with the original version retained all 27 non-profile records byte for byte. Its presentation contained no Han characters after localization. Original answers and scoring evidence were preserved rather than rewritten.
- Stock legacy interface text adopts English defaults; personal names and custom text remain intact. Saved historical definitions, options, and responses are translated for display while their original records remain available for validation.
- Native Windows Qt checks at 900×660 and 1,220×850 showed no horizontal scrolling on the home page. The long professional-learner self-rating and profile metric captions remained readable.
- The final suite passed all **55 tests** on 2026-10-29, including all five assessment lengths, old archive compatibility, actual English startup, and readable long answers at the minimum window size. The startup test also verifies the English locale with the pinned PySide6 runtime.
- The English Windows application was rebuilt with `scripts/build.ps1` and launched with a separate smoke-test profile. It stayed running, created an English profile, and included JSON resources matching the source byte for byte. The package includes the legacy translation resources. Historical bundle results below apply to the original build.
- A representative review of 165 words across all 15 levels found no glaring translation errors against the original meanings. This sampling does not replace ongoing review of every definition.

## Environment and deliverables

- Windows 11 x64 (10.0.26200), Python 3.12.14, PySide6 6.12.0, PyInstaller 6.22.3.
- App folder: `dist/VocabularyLearning/VocabularyLearning.exe`. Version 0.2 was actually built and launched on the original machine. The bundled content file's SHA-256 matched the final source used for that build.
- Includes the Python runtime, SQLite, Qt Widgets, Windows platform plugin, local SAPI speech adapter, and all core content resources.
- App folder approximately 148 MB; keep the entire folder to launch by double-clicking. It is not an installation wizard and has not been code-signed.
- The build excluded same-named ICU libraries brought into PATH by other tools and used Windows system ICU. Simulated and unused speech engines were also excluded.

## Previously completed verification

Running `.venv\Scripts\python.exe -m unittest discover -s tests -v` before the final original build passed **all 44 checks**, including high-level goal forms and compatibility with the earliest legacy profiles. After adding the missing-phonetics state, all six desktop integration tests passed again.

Additional version 0.2 verification:

- Home module cards opened learning, mistakes, history, achievements, goals, the queue, and settings. Modules had no sidebar, other module cards, global status, or home goal bar. Returning home allowed continuation of the same learning session.
- New profiles had separate onboarding: quick self-rating directly to goal setup, or a selected assessment followed by result confirmation and goal setup. Onboarding steps and actual answers resumed after exit. The home page stayed locked until goal setup completed.
- All five assessment sizes (20/50/100/200/500) in the distributed catalog were completed. The 500-question assessment was closed at question 237, reopened, exported/imported, and continued without repeated lemmas.
- The native Windows Qt interface completed 500 questions. After closing at question 250 and rebuilding the window, the same question and options returned. Final score was 500/500 across 15 levels. Assessment added no mastered words, practice count, mistakes, or learning achievements.
- Starting the 500-question assessment took about 77 ms. Per-question processing averaged 111 ms, with P95 about 149 ms and maximum 186 ms. Total including painting and one reopen was about 70.5 seconds. These measurements came from automated local operation, not human answering time.
- Previously onboarded profiles continued home. Adopting reassessment difficulty left existing goals, estimated baseline, and learning records unchanged.
- Earliest schema 1 profiles lacking all onboarding fields but already containing learning/goals migrated as onboarded and resumed the original question. All non-profile records were preserved byte for byte. Direct legacy import and export/reimport both passed separate retesting. Explicitly saved False and empty legacy profiles still entered onboarding.
- When a high-level assessment suggested a baseline above 5,000, the goal form defaulted to a reasonable higher target. Later manual baseline edits did not silently change the target.
- Content contained 1,080 lemmas and 1,274 senses across all 15 levels: 90 each at L1–L6, 60 each at L7–L15. L15 had 60 specialist terms labeled by field. Original 180-word IDs, senses, and legacy record relationships were retained.
- Final original content also passed 500 independent four-choice questions and 30,000 questions from random 20-word pools across levels. Every question had four structurally valid options; language quality still required ongoing review.
- In a separate demo profile, the final original 0.2 bundle resumed at 19/20 assessment progress. Completing the final question → results → goal confirmation → home → 20-word module → home worked. Separate modules showed no settings, global status, or goal bar. Returning preserved the same unfinished session. Assessment itself added no mastered or practice words.

| Check | Recorded result |
|---|---|
| Complete 20-word cycle | Real business logic and Qt widgets ran the overview, word learning, 20 questions, results, relearning, retesting, and completion. |
| 5 already known + 15 newly learned | Net new 15, exact mastered set 20, estimated vocabulary increased from 1,000 to 1,015. |
| One missed word remaining | Four valid answer/distractor options plus "I don't know", drawn from the original 20-word pool. |
| Resume midway | Closing the window and rebuilding the service/window restored the original question and actual options. Unfinished sessions did not complete. |
| Idempotence and historical replay | Repeated completion and restart did not add words. Replay retained original snapshots and did not increase unique words or practice achievements. |
| Mistakes | Previously unknown words stayed in the notebook after eventual correct answers, with unknown and retry counts retained. |
| Goal boundaries | Regression checks covered outside words, one missing word, empty sets, incomplete lists, and a sample set used for CET. |
| Export/import | Active sessions, relearning, and final results resumed; backups were saved first; order was preserved. Invalid progress, forged completion, credential fields, and invalid goals/achievements were rejected. |
| Versions | Content upgrades did not alter historical questions or word set denominators. Compatible schema 0 migration backed up first. |
| Achievements | Definitions were read from configuration. First start was separate. Completed word practices accumulated; replays did not count. |
| First-use setup | Separate self-rating or assessment → goal onboarding. Users confirmed baselines; unconfirmed estimates were not treated as mastered words. |
| Text and input | Editing text in the app immediately updated titles, subtitles, navigation, and goal buttons. Numeric inputs were not affected by quiz shortcuts. Holding a digit did not repeatedly answer questions. |
| Animation | Gravity, side/bottom collisions, finite lifetime, flight toward the mistake collection. Reduced motion suppressed effects, and effects did not block mouse input. |

The actual original packaged app also completed "resume missed words → retest → all-correct completion" in a separate demo profile. The interface showed 15 newly learned, 5 already known, and 20 practiced words. Reopening the final original bundle retained estimated vocabulary 1,015, 20 mastered words, 15 net new words, and mistake records. The demo profile was in `artifacts/bundle-smoke` and did not write to the default personal profile.

## Pronunciation and networking

- Microsoft Zira Desktop American English was available through Windows SAPI on the original machine, and actual Qt calls succeeded. A separate local synthesis of "vocabulary" produced a 75,644-byte WAV, confirming real playback rather than a placeholder.
- The original machine lacked a British English voice. Selecting British English showed the missing local voice state instead of substituting another accent, downloading online, or playing remotely.
- The complete Qt flow ran with Python network connections blocked. No TCP connections were observed for the local bundled process. The initial release has no HTTP client, model calls, synchronization, or remote pronunciation implementation.
- **Manual acceptance after physically disconnecting the network had not been performed.** The checks above do not replace verifying a full session, reopen, and pronunciation with the network turned off.

## Limitations and release tasks

- No verification on another Windows machine without a development environment had been performed. Only the original machine had launched the runtime-inclusive bundle. Before release, verify startup, offline learning, saving, and reopening on an independent machine.
- The official complete CET-4 list is not installed, so no official CET-4 goal may be shown complete. Original 180-word content uses an internal license identifier; the additional 900 words record the pinned ECDICT MIT license. Continue content review and license checks before public release.
- The source did not supply phonetics for 29 added entries. The interface reports "Phonetics not available", while local speech can still be used. Pronunciations are not invented. Original seed phonetics and the source's British/older notation still need consistency review.
- All 15 levels contain selected real words but are configurable, uncalibrated internal levels. Five adaptive assessment sizes are supported. Standardized calibration, other skill measurements, reading, writing, 3D, and AI requests remain on the roadmap.
- Current network policies save preferences and explicitly show local operation. Concrete online services must later implement availability and Wi-Fi policy. Connectivity does not substitute for AI authorization.
- Estimated vocabulary cannot be directly reset after learning records or goals exist. Effects of reassessment and baseline resets on active goals remain a phase 2 decision.
- The original code, build, and verification were kept locally without Git commits, pushes, or public deployment. This is historical evidence, rather than a statement about subsequent repository actions.

## Manual acceptance steps

1. Turn off networking, double-click the app, and set a learning baseline and goal.
2. Mark 5 words as already known in the overview, study words individually, and deliberately choose "I don't know" once in the first quiz.
3. Exit midway and reopen. Confirm the question and options return, then relearn and retest missed words.
4. Complete with all answers correct. Check net new 15, mistakes, and goal progress. Reopen again and confirm completion is not counted twice.
5. Export records in Settings and verify importing them into a separate profile. Do not overwrite a personal study profile with demo data.
