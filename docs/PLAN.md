# Implementation plan and acceptance

## Confirmed decisions

- A Windows desktop app using Python, PySide6, and SQLite. The initial release does not need Java.
- Core learning works offline. Network policy and the AI switch are separate. Phase 1 has no AI integration.
- Each session has 20 distinct entries and completes only when all have eventually been answered correctly. "Already knew" markers can be changed and are saved with the session; mastery is registered only on completion.
- A session with 5 previously known words and 15 newly learned words adds 15 net new words and registers all 20 as mastered. Previously missed words keep their error records.
- Ordinary word count goals show the gained interval: a baseline of 1,000 and target of 5,000 starts the main bar at 0%. Estimated vocabulary is shown separately from individually recorded mastery.
- CET-4 completion requires 100% coverage of a specified complete, versioned target list. A missing official list is shown as pending installation; sample sets are labeled separately.
- Achievements accumulate completed word practices. Deliberately replaying historical sessions does not advance practice achievements. The first start of learning is recorded separately.
- Local American or British English pronunciation can be selected. Pronunciation reads the English word.
- Interface text, themes, and content resources have centralized configuration and remain editable. The project owner decides whether to deploy publicly.
- The home page is the module entry point. Each module uses a separate scene with "Back to home". Settings and other module navigation are absent during learning.
- First launch uses separate onboarding: a quick self-rating followed by a goal, or a choice of 20/50/100/200/500 assessment questions followed by a goal. Every size uses distinct real entries and supports saving and resuming.
- L1–L15 all contain real content. L1 covers basic communication and everyday words, with increasing difficulty through L15 specialist terms labeled by field. Level criteria can change and do not claim standardized certification.
- A reassessment can explicitly update the recommended learning difficulty without automatically resetting goals, estimated baselines, history, or achievements.
- The interface, prompts, and vocabulary definitions are in English.

## Phase 0

1. Save the complete product requirements and roadmap.
2. Fix business rules, data relationships, technical versions, and the current scope.
3. Record current verification tasks separately from questions for later phases.

## Phase 1

1. Build the business layer, SQLite storage, and separate content packs.
2. Implement the overview, word-by-word learning, four-choice questions, "I don't know", relearning and retesting missed words, and all-correct completion.
3. Integrate local speech. Save every step, restore after exit, and make completion idempotent.
4. Implement home, mistakes, history, achievements, settings, the study queue, and import/export.
5. Complete the goal bar, both goal types, reduced motion, and basic celebrations.
6. Run rule tests, real interface operations, and Windows bundle verification; record limitations.
7. Complete separate module navigation, first-use onboarding, all five assessment sizes, and 15 content levels. See REQUIREMENTS_CHECKLIST.md for individual checks.

## Acceptance priorities

- Complete 20 words offline. Four valid options and "I don't know" remain even when only one missed word needs retesting.
- Exiting midway does not complete a session. Restart restores actual questions, options, and word snapshots.
- Verify 5 known + 15 new words, repeated completion, historical replays, and mistake/retry counts after restart.
- Words outside a target set do not advance coverage. A missing final word, empty set, or incomplete list cannot trigger early completion.
- Validate imports and backups. Content upgrades do not alter old sessions. Credentials cannot enter exports.
- Confetti has gravity, edge collisions, and fading. Animations do not block interaction, and reduced motion works.
- The Windows bundle includes runtimes and core resources. Record checks on the current machine separately from checks on a machine without a development environment.

## Current boundaries

The catalog supports learning and internal meaning recognition assessments; it is not a complete CET-4 list. Assessments of 20–500 questions provide different amounts of unstandardized evidence. More questions do not guarantee accuracy. All 15 levels have real content; see CONTENT.md for counts and sources. 3D, reading, writing, milestone rewards, and actual AI requests remain on the roadmap.
