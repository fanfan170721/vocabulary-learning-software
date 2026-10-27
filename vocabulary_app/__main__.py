"""Application entry point."""

import argparse
import os
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Vocabulary Learning")
    parser.add_argument("--data-dir", type=Path, help="Use a separate local profile directory")
    args = parser.parse_args()

    from PySide6.QtCore import QLockFile, QStandardPaths
    from PySide6.QtWidgets import QApplication, QMessageBox

    from vocabulary_app.core import AppService
    from vocabulary_app.speech import LocalSpeech
    from vocabulary_app.ui import MainWindow

    app = QApplication(sys.argv[:1])
    app.setApplicationName("VocabularyLearning")
    app.setOrganizationName("VocabularyLearning")
    app.setApplicationVersion("0.2.0")
    data_dir = args.data_dir or Path(os.environ.get("LOCALAPPDATA", QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation))) / "VocabularyLearning"
    data_dir.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(data_dir / "application.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        QMessageBox.information(None, "单词学习", "这个学习档案已经打开。请使用已打开的窗口。")
        return 0
    try:
        service = AppService(data_dir=data_dir)
        speech = LocalSpeech()
        window = MainWindow(service, speech)
        window.show()
        app.aboutToQuit.connect(speech.stop)
        app.aboutToQuit.connect(service.close)
        return app.exec()
    except Exception as error:
        QMessageBox.critical(None, "无法启动", str(error))
        return 1
    finally:
        lock.unlock()


if __name__ == "__main__":
    raise SystemExit(main())

