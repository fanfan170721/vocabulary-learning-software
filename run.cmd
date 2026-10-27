@echo off
cd /d "%~dp0"
if exist "dist\VocabularyLearning\VocabularyLearning.exe" (
  start "" "dist\VocabularyLearning\VocabularyLearning.exe"
  exit /b
)
if exist ".venv\Scripts\pythonw.exe" (
  start "" ".venv\Scripts\pythonw.exe" -m vocabulary_app
  exit /b
)
echo Please follow README.md to create the Python environment first.
pause

