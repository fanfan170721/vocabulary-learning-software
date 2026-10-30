# Requirements checklist

This iteration fills earlier gaps in phases 0 and 1 and adds first-use assessment and complete 15-level content. Reading, writing, actual AI, and a 3D achievement cabinet remain planned for later modules and are not presented as complete.

| Original or additional requirement | Implementation and acceptance |
|---|---|
| Windows, local offline use, double-click launch | Python/PySide6/SQLite; Windows bundle includes runtimes. Clean-machine and physical-disconnection verification are recorded separately. |
| White background, black text, blue/pink emphasis, continued editing | Centralized theme and text configuration; in-app text editing; no copied third-party branding or promotional assets. |
| Home opens independent modules | Home entry cards; removed sidebar; each module shows its own content and "Back to home". Goal bar appears only at home. |
| Ask for level on first use | Separate onboarding with eight self-ratings and quick-start or assessment paths. |
| Select 20/50/100/200/500 questions | Five actual sizes; questions and answers saved; entries or questions are not copied to fill a quota. |
| Narrow difficulty similarly to binary search without a large jump after one error | Initial difficulty anchors followed by focused selection; combine evidence from multiple answers and guessing probability; save algorithm version and estimation uncertainty. |
| Progressive L1–L15 content | L1 basic communication, L15 specialist terms by field; frequency, abstraction, and specialization inform editable content versions and levels. |
| Multiple skill variables and reassignment | Meaning recognition evidence is saved separately. Untested skills remain unknown. Reassess and explicitly adopt the recommended difficulty. |
| Set a first goal before entering home | Self-rating or completed assessment leads to a separate goal step. Onboarding completes only after a successful save. |
| Ordinary vocabulary and CET-4 goals | Main ratio uses the gained interval. Exact mastered words remain separate. An absent official CET-4 list is pending installation; only a complete, nonempty set at 100% can complete. |
| Complete 20-word cycle | Overview, already-known markers, individual definitions/POS/phonetics/local speech, four choices/unknown, relearning and retesting, all-correct completion. |
| Original 20-word distractor pool and multiple senses | Retests keep the original pool and exclude other correct target senses, duplicate definitions, and marked synonym groups. |
| Missed words still count toward progress and retain records | Completion registers all valid words; mistakes, unknown responses, answers, and retries remain separate. |
| Restore after exit; prevent duplicate accounting | Save each step, stable session and question snapshots, transactions, and unique completion events; test restart and repeated completion. |
| History, deliberate replay, achievements | History retains original content. Replay creates a new record without unique-word or practice-achievement gains. First use and practice milestones remain separate. |
| Confetti and flight to mistake collection | Gravity, collisions, fading, no blocked input, reduced motion; collection indicator stays in learning, with the mistake module accessed after returning home. |
| Maintainable data and backups | Import/export, validation, backup, and compatible legacy profiles; content upgrades do not change historical study snapshots or goal denominators. |
| Separate network policy and AI | Save three network policies; core learning is currently offline; AI is not integrated or callable, with no developer-quota fallback. |
| Web and additional languages | Separate business rules, content, storage, and interface, with independent language fields. No current public deployment. |
| English information throughout | English interface text, prompts, definitions, configuration descriptions, and documentation. |

See VALIDATION.md for actual results, passed checks, and environments still awaiting verification. See CONTENT.md for content counts, the pinned upstream revision, licenses, and level criteria.
