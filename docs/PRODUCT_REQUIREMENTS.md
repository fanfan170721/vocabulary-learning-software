# Product requirements

An English vocabulary learning app with an English interface and English definitions. The initial Windows desktop release uses Python, PySide6, and SQLite. Business rules, content, and interface are separate to allow additional native languages, learning languages, and a web interface later. The project is nonprofit, with no advertising, subscriptions, or in-app purchases.

## Interface and content maintenance

Use a predominantly white background, black body text, blue emphasis for actions and selection, and pink for new words. Modules may have small independent color and icon accents without large decorative areas. Maintain interface text, themes, vocabulary, levels, and achievements as separate configurations. Text can be edited in Settings.

The home page opens modules. Learning, mistakes, history, goals, achievements, and settings each use a separate scene; return home to switch modules. Other module navigation is absent during learning. Current goal progress remains at the bottom of the home page.

## Level and first-use onboarding

On first launch, choose a level: Just starting, Know a little, Beginner, Intermediate, Advanced, Proficient, Native speaker, or Professional English learner. Start quickly from a self-rating, or choose a meaning recognition assessment of 20, 50, 100, 200, or 500 questions, then confirm a learning baseline and goal.

Assessments have four choices and a separate "I don't know" option, with no repeated entry in a single assessment. Every answer is saved. Difficulty adapts to answers. Results give a recommended content level and estimated vocabulary range rather than standardized certification of listening, speaking, reading, or writing. Assessments do not add learned words, completed sessions, or practice achievements. Existing profiles can reassess and explicitly adopt the result to adjust recommended difficulty without automatically resetting goals, history, or achievements.

Content spans L1–L15. L1 begins with basic communication such as hi and hello. Frequency rarity, abstraction, and specialization increase toward L15 specialist terms labeled by field. Every level must have actual content. Level criteria can be calibrated over time and do not claim a universal ranking of the world's hardest words.

## 20-word learning

1. Select 20 distinct entries per session. The overview shows words, English senses, and levels, with markers for words already known.
2. Word-by-word learning shows forms, available phonetics, parts of speech, and multiple senses. It automatically reads the English word and allows replay. Users can choose local American or British English. Missing voices or phonetics are explicitly identified.
3. Each quiz question has four definition options from the original session's word pool, plus "I don't know". Other valid senses of the target entry cannot be used as wrong answers.
4. Count correct, wrong, and unknown responses. Relearn missed words and retest only those words until all are correct. Four valid options remain even when only one missed word needs retesting.
5. Complete and account for the entire session at once. Exiting midway saves progress without recording completion. A session of 5 already known words and 15 newly learned words registers all 20 as mastered and adds 15 net new words.
6. Previously missed or unknown words retain mistake records after eventual success, including answer, error, unknown, and retry counts. Save original word, option, and answer snapshots for historical replays. Replaying an old session does not add unique new words or practice achievements.
7. Completion can show confetti with gravity, edge collisions, and fading. Missed words can fly toward a collection indicator. Animations must not block interaction and must support reduced motion.

## Goals and progress

Vocabulary count goals use net gains after the baseline. For example, a baseline of 1,000 and target of 5,000 starts at 0%, advancing to 15/4,000 after 15 new words. Estimated vocabulary and individually recorded mastery are shown separately.

A CET-4 goal must cover 100% of the selected complete, versioned list. Outside words cannot substitute. A missing, incomplete, or empty official list cannot be declared complete. Content updates do not rewrite old goals or historical snapshots.

Later phases will support intermediate goals, chosen rewards, and a final reward. Three playful progress directions are retained: travel from Beijing to Toronto, a 42.195 km marathon, and a historical timeline from AD 1 to the current year. They use the same actual primary progress. Locations and historical events need reliable content sources. After the final goal, configured online functionality may generate a separate congratulatory letter.

## Achievements and records

The first start of learning is recorded separately. Practice achievements accumulate word practices from newly completed sessions, with milestones at 100, 200, 500, 1,000, 2,000, and 3,000. Replaying old sessions does not count. A basic achievement interface is available now. An actual 3D cabinet that can be rotated by dragging, with increasingly elaborate appearances, is planned for a later phase.

Locally record profiles, settings, the study queue, learning and assessment progress, mistakes, goals, achievements, and content versions. Support complete exports, validated imports, and backups before replacement. Credentials must not enter study data exports. Saving and completion accounting must be recoverable and idempotent.

## Future reading and writing

Reading content will include lawfully available classics, popular science, and social topics. Support resuming book chapters and random unread articles, recommend by level, and keep random reading to about 20 minutes. Hover lookup shows definitions, phonetics, and parts of speech; clicking can add a word to the study queue. Post-reading choice questions, fill-in questions, and explanations adapt to length. Confirm exact completion rules in that phase.

Writing will offer prompts by level, save originals, revisions, and feedback, and explain grammar errors. The earlier design allowed native-language placeholders for unknown English words, with an online service recommending context-appropriate expressions. Difficult catalog words independently used in an original draft can count as mastery evidence. Placeholders and generated suggestions that have not been learned do not count as previously known words.

## Offline, online, and costs

Core learning uses local content. Network policy and the AI switch are separate. The current version does not call model services. Future online features use each user's own provider configuration and quota, with credentials stored separately. Ordinary offline learning remains available if configuration is missing, invalid, or out of quota. Developer keys must not enter source code, app bundles, or public download configuration.

If private demo quota is introduced, it requires separate explicit authorization, expiry and revocation, budget controls, and concurrency limits. It cannot serve as fallback when a user's own configuration fails. Public deployment and service activation are separate decisions.

## Implementation scope

Phases 0 and 1 are currently complete: rules and architecture, the offline 20-word cycle, separate modules, first-use onboarding and all five assessment sizes, 15 content levels, profiles, goals, mistakes and history, basic achievements, pronunciation, and import/export. Reading, writing, AI services, actual 3D graphics, milestone rewards, and playful progress views will follow the [roadmap](ROADMAP.md). See the [validation record](VALIDATION.md) for actual verification scope and known limitations.
