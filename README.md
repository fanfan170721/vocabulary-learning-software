# vocabulary-learning-website

A Windows vocabulary learning app with offline 20-word sessions, first-use self-rating or assessment, relearning and retesting of missed words, a mistake notebook, history, goals, basic achievements, and local backups. The project retains its original repository name; the current deliverable is a desktop app. The interface and vocabulary definitions are in English.

The home page opens each module. Learning and other modules show their own content and a "Back to home" action. The goal progress bar stays at the bottom of the home page.

On first launch, choose your current level. Start quickly with a self-rating, or take a meaning assessment with 20, 50, 100, 200, or 500 questions, then set a goal. Each assessment answer is saved so you can resume after closing the app. Results provide a recommended difficulty and an estimated vocabulary range, rather than an assessment of every language skill. Existing profiles do not have to repeat onboarding. After reassessment, you can explicitly adopt the recommended difficulty while keeping your goals and records.

## Run the app

After building, double-click `dist\VocabularyLearning\VocabularyLearning.exe` or the root `run.cmd`. The app bundle includes the Python and Qt runtimes; keep the entire `VocabularyLearning` folder together.

Study records are stored in `%LOCALAPPDATA%\VocabularyLearning`. Keep this directory when updating the app, and export records regularly in Settings. The initial release requires neither an account nor a network connection.

## Development

The app uses Python 3.12, PySide6 6.12.0, and SQLite. Python 3.12–3.14 are supported; the recorded build environment uses Python 3.12.14.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe -m vocabulary_app
```

In PyCharm, open this directory, select `.venv\Scripts\python.exe` as the interpreter, and run the `vocabulary_app` module. You can also use the commands above in a terminal.

```powershell
# Use a separate demo profile without changing personal study records
.\.venv\Scripts\python.exe -m vocabulary_app --data-dir .\artifacts\demo-profile

# Verify learning rules and desktop integration
.\.venv\Scripts\python.exe -m unittest discover -s tests -v

# Build the Windows app folder for double-click launch
powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1
```

The app folder is not an installation wizard. The current version is unsigned. See the [validation record](docs/VALIDATION.md) for verified environments, packaging status, and limitations. An untested clean Windows environment is not considered verified.

## Learning rules

- Each session contains 20 different words and completes only when all have eventually been answered correctly. You can resume an interrupted session; every answer is saved.
- Mark words you already know in the overview. If you already know 5 words and learn 15 for the first time, the net gain is 15. All 20 are recorded as mastered on completion.
- Previously missed or unknown words stay in the mistake notebook after you answer them correctly. Even when only one missed word remains, four valid options come from the original 20-word pool.
- Ordinary vocabulary goals show progress through the words gained after the baseline. Estimated vocabulary and individually recorded mastered words remain separate.
- CET-4 completion requires 100% coverage of the complete, specified version of its target word set. The official CET-4 list is not installed. The small sample set only tests the rules.
- Achievements count word practices from newly completed sessions. Replaying a historical session preserves the new record without adding unique words or practice achievement progress.

## Edit content and appearance

- Text: Settings → Edit interface text. Personal edits are saved as `ui_texts.json` in the study data directory. Defaults are in `vocabulary_app/resources/ui_texts.json`.
- Colors, fonts, and spacing: `vocabulary_app/resources/theme.json`.
- Vocabulary, levels, and achievements: `vocabulary_app/resources/content.json`, `levels.json`, and `achievements.json`. See the [content guide](docs/CONTENT.md) for expansion details.
- Restart after editing resources and rebuild release bundles. Changing display text must not change stable entry IDs.

The English catalog `content-0.2.1-en` contains 1,080 distinct lemmas and 1,274 senses: 90 words at each of L1–L6 and 60 at each of L7–L15. L1 starts with basic communication such as hi and hello. L15 covers specialist terminology in medicine, physics, chemistry, engineering, and mathematics. Levels combine frequency, abstraction, and specialization. They are configurable and have not been standardized or calibrated; this is not a complete exam word list. Added entries were selected from a pinned MIT-licensed ECDICT revision, with source and license records retained. Pronunciation uses only the local Windows SAPI engine. American and British English are selectable, with a message when the corresponding local voice is unavailable.

Existing profiles can display the original stock definitions, prompts, and history text in English without rewriting saved answers or changing scoring. Personal names and edits are preserved. Saved copies of the old default interface text adopt the English defaults; text you customized stays as you wrote it.

## Scope and roadmap

[Product requirements](docs/PRODUCT_REQUIREMENTS.md) · [Requirements checklist](docs/REQUIREMENTS_CHECKLIST.md) · [Implementation plan and confirmed decisions](docs/PLAN.md) · [Architecture and data](docs/ARCHITECTURE.md) · [Roadmap](docs/ROADMAP.md) · [Dependencies and assets](docs/THIRD_PARTY.md)

The current adaptive meaning assessment uses versioned content levels as a reference; it is not a standardized language proficiency exam. Reading, writing, actual 3D graphics, milestone rewards, playful progress views, and AI requests remain on the roadmap. Network policy and AI status are separate. The current version makes no model requests and stores no API keys. A future public release will use each user's own provider configuration. There is no public deployment, paid service, or automatic synchronization.
