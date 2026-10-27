$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $projectRoot
try {
    & .\.venv\Scripts\python.exe -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed.' }
    & .\.venv\Scripts\python.exe -m PyInstaller --noconfirm VocabularyLearning.spec
    if ($LASTEXITCODE -ne 0) { throw 'Build failed.' }
    Copy-Item -LiteralPath README.md -Destination dist\VocabularyLearning\README.md
    Copy-Item -LiteralPath docs\CONTENT.md -Destination dist\VocabularyLearning\CONTENT.md
    Copy-Item -LiteralPath docs\THIRD_PARTY.md -Destination dist\VocabularyLearning\THIRD_PARTY.md
    if (Test-Path -LiteralPath docs\VALIDATION.md) {
        Copy-Item -LiteralPath docs\VALIDATION.md -Destination dist\VocabularyLearning\VALIDATION.md
    }
    $bundleDocsPath = Join-Path $projectRoot 'dist\VocabularyLearning\docs'
    New-Item -ItemType Directory -Path $bundleDocsPath -Force | Out-Null
    $publicDocs = @('ARCHITECTURE.md', 'CONTENT.md', 'PLAN.md', 'PRODUCT_REQUIREMENTS.md', 'REQUIREMENTS_CHECKLIST.md', 'ROADMAP.md', 'THIRD_PARTY.md', 'VALIDATION.md')
    foreach ($document in $publicDocs) {
        Copy-Item -LiteralPath (Join-Path 'docs' $document) -Destination $bundleDocsPath -Force
    }
    Write-Output 'Ready: dist\VocabularyLearning\VocabularyLearning.exe'
} finally {
    Pop-Location
}

