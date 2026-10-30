# Product roadmap

See [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md) for feature requirements. Only phases 0 and 1 are currently implemented.

| Phase | Scope | Confirm before starting |
|---|---|---|
| 0 | Decisions, architecture, data relationships, planning, acceptance | Do not ask again about confirmed decisions. |
| 1 | Complete offline 20-word cycle, home module entry points and separate scenes, first-use self-rating/assessment/goal onboarding, 20/50/100/200/500-question assessments, actual entries across 15 levels, local profiles, mistakes/history, goals, basic achievements, import/export, Windows bundle | Ordinary goals, achievement counting, and new onboarding are confirmed. |
| 2 | Calibrate 15 levels and assessment algorithms, reference proficiency conversion, continued content expansion, milestone rewards, three playful progress views, rotatable 3D achievement cabinet | How reassessment affects active goal baselines, milestone rewards, travel route. |
| 3 | Graded library, chapter resumption, random unread articles, valid-word counts throughout texts, lookup and study queue, post-reading choice/fill-in questions, explanations and completion accounting | Whether the 20-minute reading limit includes answering, whether all answers must be correct, which words count. |
| 4 | User-supplied API keys, isolated credentials, connection status, natural-language goal analysis, native-language placeholder suggestions, essay corrections and version history, separate congratulatory letter | Providers, request paths, writing completion events, difficult-word levels. |
| Optional | Private demo authorization, expiry and revocation, atomic budget reservation, concurrency and retry limits | Separate explicit activation; never a fallback when a personal key fails. |
| Later | More languages/modes, content packs, artwork, achievements; web interface and storage adapter | The owner decides accounts, synchronization, hosting, and public deployment. |

Retained directions include travel from Beijing to Toronto, a 42.195 km marathon, and a historical timeline from AD 1 to the current year, all using the same primary progress. Historical content needs sources; do not invent event dates. Reading retains classics, popular science, and social topics. Difficult catalog words independently used in an original draft can count under the rules even when AI is off. Native-language placeholders and generated suggestions that have not been learned are not evidence of already-known words.

A public release uses only each user's own provider quota. Developer keys stay out of the repository, bundles, and download configuration. If AI is missing, invalid, or out of quota, ordinary learning continues without fallback to shared quota.
