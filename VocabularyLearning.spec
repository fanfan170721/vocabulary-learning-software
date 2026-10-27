from pathlib import Path
import os

root = Path(SPECPATH)
a = Analysis(
    [str(root / 'launch.py')],
    pathex=[str(root)],
    binaries=[],
    datas=[(str(root / 'vocabulary_app' / 'resources'), 'vocabulary_app/resources')],
    hiddenimports=['PySide6.QtTextToSpeech'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.QtPdf', 'PySide6.QtQml', 'PySide6.QtQuick'],
    noarchive=False,
)
# Windows supplies the ICU ABI used by Qt. A different ICU from PATH can shadow it.
# The desktop application only uses the installed Windows SAPI voices.
a.binaries = [entry for entry in a.binaries if Path(entry[0]).name.lower() not in {
    'qtexttospeech_mock.dll', 'qtexttospeech_winrt.dll', 'icuuc.dll', 'icudt78.dll'
}]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='VocabularyLearning', debug=False,
          bootloader_ignore_signals=False, strip=False, upx=False,
          console=os.environ.get('VOCAB_BUILD_CONSOLE') == '1')
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='VocabularyLearning')

