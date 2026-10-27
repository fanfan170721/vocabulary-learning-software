"""Windows local speech. No network engine is selected."""

import sys

from PySide6.QtCore import QLocale, QObject, Signal
from PySide6.QtTextToSpeech import QTextToSpeech


class LocalSpeech(QObject):
    stateChanged = Signal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.available = False
        self._message = "未安装可用的本地英语语音，可继续文字学习。"
        self._engine: QTextToSpeech | None = None
        self._language = "en-US"
        self._voices = {}
        if sys.platform != "win32" or "sapi" not in QTextToSpeech.availableEngines():
            return
        try:
            self._engine = QTextToSpeech("sapi", self)
            self._engine.errorOccurred.connect(self._on_error)
            self._engine.stateChanged.connect(self._on_state)
            self._engine.setRate(-0.15)
            self._refresh_voices()
        except (RuntimeError, ValueError) as error:
            self._message = f"本地语音不可用：{error}"

    def _refresh_voices(self):
        if self._engine is None:
            return
        for locale in self._engine.availableLocales():
            tag = locale.name().replace("_", "-")
            if tag in ("en-US", "en-GB"):
                self._engine.setLocale(locale)
                voices = self._engine.availableVoices()
                if voices:
                    self._voices[tag] = voices[0]
        self.select_language(self._language)

    def select_language(self, language: str):
        self._language = language if language in ("en-US", "en-GB") else "en-US"
        self.available = self._language in self._voices
        accent = "美式" if self._language == "en-US" else "英式"
        if self.available and self._engine is not None:
            self._engine.stop()
            self._engine.setLocale(QLocale(self._language))
            self._engine.setVoice(self._voices[self._language])
            self._message = f"本地{accent}英语 · {self._voices[self._language].name()}"
        else:
            self._message = f"未安装本地{accent}英语语音。请在 Windows 语音设置安装对应语言的语音组件，可继续文字学习。"
        self.stateChanged.emit(self._message)

    def status(self) -> str:
        return self._message

    def speak(self, text: str, language: str = "en-US") -> bool:
        if language != self._language:
            self.select_language(language)
        if not self.available or self._engine is None:
            self.stateChanged.emit(self._message)
            return False
        self._engine.stop()
        self._engine.say(text)
        return True

    def stop(self):
        if self._engine is not None:
            self._engine.stop()

    def _on_state(self, state):
        if state == QTextToSpeech.State.Ready:
            self.stateChanged.emit(self._message)

    def _on_error(self, reason, message: str):
        self._message = f"本地语音暂不可用：{message}"
        self.stateChanged.emit(self._message)

