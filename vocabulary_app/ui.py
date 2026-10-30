"""Desktop pages for local vocabulary learning."""

import json
from datetime import datetime
from hashlib import sha256
from pathlib import Path

from PySide6.QtCore import QPointF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog,
    QDialogButtonBox, QFileDialog, QFormLayout, QFrame, QGridLayout,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton,
    QScrollArea, QSizePolicy, QSpinBox, QTableWidget, QTableWidgetItem,
    QTabWidget, QVBoxLayout, QWidget,
)

from .animations import CelebrationOverlay, notebook_icon
from .assessment import RATINGS
from .theme import load_theme, stylesheet
from .visuals import BadgeIcon, LearningIllustration, ModuleIcon


NETWORKS = [("Offline only", "offline"), ("Automatic", "auto"), ("Online first", "online_first")]
ACCENTS = [("American English", "en-US"), ("British English", "en-GB")]


def meanings(word):
    return "; ".join(
        f"{sense.get('pos', '')}  {sense.get('definition', '')}".strip()
        for sense in word.get("senses", [])
    )


def date_text(value):
    if not value:
        return ""
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone().strftime("%m-%d %H:%M")
    except ValueError:
        return str(value)[:16]


def clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().hide()
            item.widget().deleteLater()
        elif item.layout():
            clear_layout(item.layout())


class WrappedAnswerButton(QPushButton):
    """Keep all lines visible when an English definition wraps."""

    def sizeHint(self):
        hint = super().sizeHint()
        if self.layout():
            hint.setHeight(max(hint.height(), self.layout().sizeHint().height()))
        return hint

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.layout():
            height = self.layout().totalHeightForWidth(event.size().width())
            if height > 0 and height != self.minimumHeight():
                self.setMinimumHeight(height)


class MainWindow(QMainWindow):
    def __init__(self, service, speech):
        super().__init__()
        self.service = service
        self.speech = speech
        self.resource_dir = Path(__file__).parent / "resources"
        self.level_config = json.loads((self.resource_dir / "levels.json").read_text(encoding="utf-8"))
        self.text_path = Path(service.data_dir) / "ui_texts.json"
        self.texts = self._load_texts()
        self.theme = load_theme(self.resource_dir)
        self.page = "home"
        self.current_session = None
        self.current_data = {}
        self.answer_buttons = []
        self.assessment_record = None
        self.assessment_choose_new = False
        self._celebrated = set()
        self.resize(1220, 850)
        self.setMinimumSize(900, 660)
        self.setWindowTitle(self.tr("app_title"))
        self.setStyleSheet(stylesheet(self.theme))
        self._build_shell()
        self.effects = CelebrationOverlay(self.root, self.theme)
        if hasattr(speech, "stateChanged"):
            speech.stateChanged.connect(self._speech_state_changed)
        self.quiz_shortcuts = []
        for number in range(1, 5):
            shortcut = QShortcut(QKeySequence(str(number)), self)
            shortcut.activated.connect(lambda n=number: self._answer_shortcut(n - 1))
            shortcut.setAutoRepeat(False)
            shortcut.setEnabled(False)
            self.quiz_shortcuts.append(shortcut)
        unknown_shortcut = QShortcut(QKeySequence("0"), self)
        unknown_shortcut.activated.connect(self._unknown_shortcut)
        unknown_shortcut.setAutoRepeat(False)
        unknown_shortcut.setEnabled(False)
        self.quiz_shortcuts.append(unknown_shortcut)
        self.show_page("home")

    def _load_texts(self):
        texts = json.loads((self.resource_dir / "ui_texts.json").read_text(encoding="utf-8"))
        if self.text_path.exists():
            try:
                custom = json.loads(self.text_path.read_text(encoding="utf-8"))
                if isinstance(custom, dict) and all(isinstance(k, str) and isinstance(v, str) for k, v in custom.items()):
                    legacy_hashes = json.loads((self.resource_dir / "legacy_ui_text_hashes.json").read_text(encoding="utf-8"))
                    # The editor used to save a full copy of the default text.
                    # Upgrade those stock values while retaining personal edits.
                    texts.update({key: value for key, value in custom.items()
                                  if sha256(value.encode("utf-8")).hexdigest() != legacy_hashes.get(key)})
            except (ValueError, OSError):
                pass
        return texts

    def tr(self, key):
        return self.texts.get(key, key)

    def _label(self, text, style=None, wrap=False):
        label = QLabel(str(text))
        label.setTextFormat(Qt.TextFormat.PlainText)
        if style:
            label.setObjectName(style)
        label.setWordWrap(wrap)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return label

    def _button(self, text, callback, primary=False, quiet=False):
        button = QPushButton(text)
        if primary:
            button.setObjectName("primary")
        elif quiet:
            button.setObjectName("quiet")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(lambda checked=False: callback())
        return button

    def _answer_button(self, index, option, callback):
        button = WrappedAnswerButton()
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(lambda checked=False: callback())
        button.setObjectName("answer")
        button.setProperty("optionId", option["id"])
        button.setAccessibleName(f"Answer {index + 1} {option.get('text', '')}")
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        layout = QHBoxLayout(button)
        layout.setContentsMargins(22, 17, 22, 17)
        label = self._label(f"{index + 1}   {option.get('text', '')}", wrap=True)
        label.setStyleSheet("font-size: 18px;")
        label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        layout.addWidget(label)
        return button

    def _card(self, title=None, parent_layout=None):
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(23, 21, 23, 23)
        layout.setSpacing(16)
        if title:
            layout.addWidget(self._label(title, "sectionTitle"))
        if parent_layout is not None:
            parent_layout.addWidget(card)
        return card, layout

    def _build_shell(self):
        self.root = QWidget()
        self.root.setObjectName("appRoot")
        self.setCentralWidget(self.root)
        outer = QVBoxLayout(self.root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        top = QFrame()
        top.setObjectName("topbar")
        top.setFixedHeight(68)
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(27, 12, 28, 12)
        top_layout.setSpacing(15)
        self.back_button = self._button("←  " + self.tr("back_home"), lambda: self.show_page("home"), quiet=True)
        self.back_button.setObjectName("backHomeButton")
        top_layout.addWidget(self.back_button)
        self.scene_title = self._label("", "sectionTitle")
        top_layout.addWidget(self.scene_title)
        self.brand_icon = ModuleIcon("learning", self.theme, size=34)
        top_layout.addWidget(self.brand_icon)
        self.brand = self._label(self.tr("app_title"), "brand")
        top_layout.addWidget(self.brand)
        self.subtitle_label = self._label(self.tr("app_subtitle"), "muted")
        top_layout.addWidget(self.subtitle_label)
        top_layout.addStretch()
        self.mode_label = self._label("", "modePill")
        top_layout.addWidget(self.mode_label)
        self.user_label = self._label("", "avatarPill")
        top_layout.addSpacing(20)
        top_layout.addWidget(self.user_label)
        outer.addWidget(top)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QHBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(0)
        self.body = QWidget()
        self.body.setMaximumWidth(1240)
        scroll_layout.addWidget(self.body)
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(32, 26, 32, 28)
        self.body_layout.setSpacing(20)
        self.scroll.setWidget(scroll_content)
        outer.addWidget(self.scroll, 1)
        self.footer = QFrame()
        self.footer.setObjectName("footer")
        footer_layout = QHBoxLayout(self.footer)
        footer_layout.setContentsMargins(27, 15, 28, 15)
        footer_layout.setSpacing(20)
        footer_layout.addWidget(ModuleIcon("goals", self.theme, size=34))
        self.footer_title = self._label(self.tr("goals_title"))
        footer_layout.addWidget(self.footer_title)
        footer_middle = QVBoxLayout()
        footer_middle.setSpacing(6)
        self.footer_description = self._label("", "muted")
        self.footer_progress = QProgressBar()
        self.footer_progress.setRange(0, 10000)
        self.footer_progress.setTextVisible(False)
        footer_middle.addWidget(self.footer_description)
        footer_middle.addWidget(self.footer_progress)
        footer_layout.addLayout(footer_middle, 1)
        self.footer_value = self._label("")
        footer_layout.addWidget(self.footer_value)
        self.goal_details_button = self._button(self.tr("goal_details"), self._goal_details, quiet=True)
        footer_layout.addWidget(self.goal_details_button)
        outer.addWidget(self.footer)

    def _error(self, error):
        QMessageBox.warning(self, self.tr("error_title"), str(error))

    def _notice(self, message):
        self.statusBar().showMessage(message, 5000)

    def _run(self, operation, after=None):
        try:
            result = operation()
            if after:
                after(result)
            return result
        except (ValueError, OSError, RuntimeError, KeyError) as error:
            self._error(error)
            return None

    def _refresh_chrome(self):
        self.current_data = self.service.snapshot()
        profile = self.current_data.get("profile", {})
        settings = self.current_data.get("settings", {})
        is_home = self.page == "home"
        is_onboarding = self.page == "onboarding"
        self.brand.setVisible(is_home or is_onboarding)
        self.brand_icon.setVisible(is_home or is_onboarding)
        self.subtitle_label.setVisible(is_home)
        self.mode_label.setVisible(is_home)
        self.user_label.setVisible(is_home)
        self.footer.setVisible(is_home)
        self.back_button.setVisible(not is_home and not is_onboarding)
        self.back_button.setText("←  " + self.tr("back_home"))
        scene_keys = {"learning": "nav_learning", "mistakes": "nav_mistakes", "history": "nav_history",
                      "achievements": "nav_achievements", "settings": "nav_settings", "goals": "goals_title",
                      "queue": "queue_title", "assessment": "assessment_title"}
        self.scene_title.setVisible(not is_home and not is_onboarding)
        self.scene_title.setText(self.tr(scene_keys.get(self.page, "app_title")))
        if hasattr(self.speech, "select_language"):
            self.speech.select_language(settings.get("english_variant", "en-US"))
        self.user_label.setText(profile.get("name") or "Learner")
        network = dict((value, text) for text, value in NETWORKS).get(settings.get("network_mode"), "Offline only")
        self.mode_label.setText("●  " + self.tr("local_learning"))
        self.mode_label.setToolTip(f"{network} · " + self.tr("network_note"))
        goals = self.current_data.get("goals", [])
        if goals:
            goal = goals[-1]
            available = goal.get("available", True)
            ratio = max(0.0, min(1.0, float(goal.get("ratio", 0) or 0)))
            self.footer_title.setText(goal.get("title", self.tr("goals_title")))
            self.footer_description.setText(self._goal_summary(goal))
            self.footer_progress.setValue(int(ratio * 10000) if available else 0)
            self.footer_value.setText(self._ratio_text(goal) if available else "Not installed")
            self.footer.setToolTip(goal.get("message", "") or self._goal_summary(goal))
        else:
            self.footer_title.setText(self.tr("goals_title"))
            self.footer_description.setText(self.tr("goal_empty"))
            self.footer_progress.setValue(0)
            self.footer_value.setText("—")

    @staticmethod
    def _ratio_text(goal):
        ratio = max(0.0, min(1.0, float(goal.get("ratio", 0) or 0)))
        if ratio >= 1 and not goal.get("completed", False):
            return "Incomplete"
        if 0 < ratio < 1 and ratio * 100 >= 99.99:
            return "< 100%"
        percentage = f"{ratio * 100:.3f}".rstrip("0").rstrip(".")
        return percentage + "%"

    def _goal_summary(self, goal):
        if not goal.get("available", True):
            return goal.get("message") or self.tr("word_set_pending")
        numerator = goal.get("numerator", 0)
        denominator = goal.get("denominator", 0)
        remaining = goal.get("remaining", max(0, denominator - numerator))
        if goal.get("kind") in ("word_set", "cet4"):
            return f"{numerator} / {denominator} mastered  ·  {remaining} remaining  ·  100% required"
        return f"{numerator} / {denominator} new words  ·  Estimated total {goal.get('current', 0)} / {goal.get('target', 0)}"

    def show_page(self, page):
        onboarding_complete = self.service.snapshot().get("profile", {}).get("onboarding_complete", False)
        if page != "onboarding" and not onboarding_complete:
            page = "onboarding"
        elif page == "onboarding" and onboarding_complete:
            page = "home"
        if hasattr(self, "effects"):
            self.effects.stop()
        if self.page == "learning" and page != "learning":
            self.speech.stop()
        self.page = page
        self.body.setMaximumWidth(980 if page == "onboarding" else 1240)
        self.answer_buttons = []
        for shortcut in self.quiz_shortcuts:
            shortcut.setEnabled(False)
        self._refresh_chrome()
        clear_layout(self.body_layout)
        handlers = {
            "home": self._home_page, "learning": self._learning_page,
            "mistakes": self._mistakes_page, "history": self._history_page,
            "achievements": self._achievements_page, "settings": self._settings_page,
            "goals": self._goals_page,
            "queue": self._queue_page,
            "onboarding": self._onboarding_page,
            "assessment": self._assessment_page,
        }
        try:
            handlers[page]()
        except (ValueError, OSError, RuntimeError, KeyError) as error:
            self.body_layout.addWidget(self._label(str(error), "error", True))
        self.body_layout.addStretch()
        self.scroll.verticalScrollBar().setValue(0)

    def _page_heading(self, title, description=None, notebook=False):
        row = QHBoxLayout()
        row.setSpacing(14)
        if self.page not in ("home", "onboarding"):
            row.addWidget(ModuleIcon(self.page, self.theme, size=44), 0, Qt.AlignmentFlag.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(8)
        col.addWidget(self._label(title, "pageTitle"))
        if description:
            col.addWidget(self._label(description, "muted", True))
        row.addLayout(col, 1)
        if notebook:
            self.notebook_button = QFrame()
            self.notebook_button.setObjectName("notebookIndicator")
            indicator_layout = QHBoxLayout(self.notebook_button)
            indicator_layout.setContentsMargins(12, 6, 12, 6)
            indicator_layout.setSpacing(8)
            icon = QLabel()
            icon.setPixmap(notebook_icon(self.theme).pixmap(QSize(31, 31)))
            indicator_layout.addWidget(icon)
            indicator_layout.addWidget(self._label(self.tr("mistakes_collection"), "muted"))
            self.notebook_button.setAccessibleName(self.tr("mistakes_collection"))
            self.notebook_button.setToolTip(self.tr("mistakes_collection_hint"))
            self.notebook_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            row.addWidget(self.notebook_button, 0, Qt.AlignmentFlag.AlignTop)
        self.body_layout.addLayout(row)

    def _module_button(self, title, detail, module, callback, featured=False):
        button = self._button("", callback)
        button.setObjectName("moduleCard")
        button.setProperty("featured", featured)
        button.setProperty("module", module)
        button.setAccessibleName(title)
        button.setMinimumHeight(188 if featured else 112)
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        content = QHBoxLayout(button)
        content.setContentsMargins(26 if featured else 20, 18, 22 if featured else 18, 18)
        content.setSpacing(15)
        if not featured:
            content.addWidget(ModuleIcon(module, self.theme, size=48))
        labels = QVBoxLayout()
        labels.setSpacing(7)
        if featured:
            labels.addWidget(self._label(self.tr("daily_practice"), "eyebrow"))
        for text, style in ((title, "heroTitle" if featured else "moduleTitle"), (detail, "cardDetail")):
            label = self._label(text, style, True)
            label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            labels.addWidget(label)
        if featured:
            labels.addSpacing(7)
            action = self._label(self.tr("continue_learning" if self.current_data.get("active_session") else "start_learning") + "   →", "heroAction")
            labels.addWidget(action, 0, Qt.AlignmentFlag.AlignLeft)
        content.addLayout(labels, 1)
        if featured:
            illustration = LearningIllustration(self.theme)
            illustration.setFixedSize(190, 142)
            content.addWidget(illustration)
        else:
            content.addWidget(self._label("›", "moduleArrow"))
        for child in button.findChildren(QWidget):
            child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            child.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            if isinstance(child, QLabel):
                child.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        return button

    def _home_page(self):
        snapshot = self.current_data
        profile = snapshot.get("profile", {})
        stats = snapshot.get("stats", {})
        heading = QHBoxLayout()
        heading_text = QVBoxLayout()
        heading_text.setSpacing(6)
        heading_text.addWidget(self._label(self.tr("home_title"), "pageTitle"))
        heading_text.addWidget(self._label(self.tr("home_subtitle"), "muted", True))
        heading.addLayout(heading_text, 1)
        word_count = snapshot.get("content", {}).get("word_count", 0)
        heading.addWidget(self._label(self.tr("local_catalog") + f"  ·  {word_count:,}", "neutralTag", True))
        self.body_layout.addLayout(heading)
        feature_row = QHBoxLayout()
        feature_row.setSpacing(18)
        feature_row.addWidget(self._module_button(self.tr("nav_learning"), self.tr("home_learning_description"), "learning", self._start_or_continue, featured=True), 2)
        profile_card = QFrame()
        profile_card.setObjectName("profileCard")
        profile_card.setMinimumWidth(254)
        profile_card.setMaximumWidth(300)
        summary = QVBoxLayout(profile_card)
        summary.setContentsMargins(21, 17, 21, 16)
        summary.setSpacing(8)
        level_row = QHBoxLayout()
        level_row.addWidget(self._label(f"L{profile.get('difficulty', 1)}", "profileLevel"))
        labels = QVBoxLayout()
        labels.setSpacing(1)
        labels.addWidget(self._label(self.tr("profile_difficulty"), "eyebrow"))
        labels.addWidget(self._label(profile.get("self_rating", self.tr("setup_unset")), "cardDetail", True))
        level_row.addLayout(labels)
        level_row.addStretch()
        level_row.addWidget(ModuleIcon("assessment", self.theme, size=34))
        summary.addLayout(level_row)
        metrics = QHBoxLayout()
        metrics.setSpacing(18)
        for key, value in (("estimated_vocabulary", stats.get("estimated_vocabulary", 0)), ("recorded_vocabulary", stats.get("mastered_count", 0))):
            metric = QVBoxLayout()
            metric.setSpacing(1)
            metric.addWidget(self._label(f"{value:,}", "homeMetric"))
            metric.addWidget(self._label(self.tr(key), "eyebrow", True))
            metrics.addLayout(metric)
        summary.addLayout(metrics)
        active_assessment = snapshot.get("active_assessment")
        assessment_label = self.tr("assessment_continue" if active_assessment and active_assessment.get("status") == "in_progress" else "assessment_retake")
        summary.addWidget(self._button(assessment_label + "  →", self._open_reassessment, quiet=True), 0, Qt.AlignmentFlag.AlignLeft)
        feature_row.addWidget(profile_card, 1)
        self.body_layout.addLayout(feature_row)
        queue_count = len(self.service.queue())
        mistake_count = len(self.service.mistakes())
        earned_count = sum(bool(item.get("earned")) for item in snapshot.get("achievements", []))
        goals = snapshot.get("goals", [])
        goal_detail = goals[-1].get("title", self.tr("goal_empty")) if goals else self.tr("goal_empty")
        modules = [
            ("mistakes", "nav_mistakes", f"{mistake_count} " + self.tr("word_count_unit")),
            ("history", "nav_history", f"{stats.get('completed_sessions', 0)} " + self.tr("session_count_unit")),
            ("achievements", "nav_achievements", f"{earned_count} " + self.tr("achievement_count_unit")),
            ("queue", "queue_title", f"{queue_count} " + self.tr("word_count_unit")),
            ("goals", "goals_title", goal_detail),
            ("settings", "nav_settings", self.tr("settings_summary")),
        ]
        self.body_layout.addWidget(self._label(self.tr("home_modules"), "sectionTitle"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(16)
        for index, (page, key, detail) in enumerate(modules):
            grid.addWidget(self._module_button(self.tr(key), detail, page, lambda p=page: self.show_page(p)), index // 3, index % 3)
        for column in range(3):
            grid.setColumnStretch(column, 1)
        self.body_layout.addLayout(grid)

    def _level_choices(self, combo, available):
        definitions = {item.get("level"): item for item in self.level_config.get("levels", [])}
        for level in range(1, 16):
            title = definitions.get(level, {}).get("title", "")
            label = f"L{level}  {title}".strip()
            if available and level not in available:
                label += "  ·  No content at this level"
            combo.addItem(label, level)

    def _recommended_level(self, rating):
        choice = next((item for item in self.level_config.get("self_ratings", []) if item.get("label") == rating), None)
        return choice.get("level", 1) if choice else 1

    def _step_strip(self, labels, current, skipped=()):
        strip = QHBoxLayout()
        strip.setSpacing(10)
        for index, text in enumerate(labels):
            if index:
                line = QFrame()
                line.setFixedSize(22, 1)
                line.setStyleSheet(f"background: {self.theme['border']};")
                strip.addWidget(line)
            label = self._label(f"{index + 1}  {text}", "stepPill")
            state = "active" if index == current else "complete" if index < current and index not in skipped else "pending"
            label.setProperty("state", state)
            strip.addWidget(label)
        strip.addStretch()
        self.body_layout.addLayout(strip)

    def _onboarding_page(self):
        profile = self.current_data.get("profile", {})
        step = profile.get("onboarding_step", "self_rating")
        if step == "complete" or profile.get("onboarding_complete", False):
            self.show_page("home")
            return
        current = 2 if step == "goal" else 1 if step in ("assessment", "assessment_result") else 0
        self._step_strip([self.tr("setup_step_level"), self.tr("setup_step_assessment"), self.tr("setup_step_goal")], current,
                         skipped=(1,) if not profile.get("onboarding_assessment_id") else ())
        if step == "goal":
            self._page_heading(self.tr("onboarding_goal_title"), self.tr("onboarding_goal_hint"))
            self._goal_form(onboarding=True)
            return
        if step in ("assessment", "assessment_result"):
            identifier = profile.get("onboarding_assessment_id")
            record = self.service.assessment(identifier) if identifier else None
            if record:
                self._render_assessment(record, onboarding=True)
            else:
                self._assessment_size_card(onboarding=True)
            return
        self._page_heading(self.tr("onboarding_title"), self.tr("onboarding_rating_hint"))
        card, layout = self._card(self.tr("profile_rating"), self.body_layout)
        layout.setContentsMargins(28, 24, 28, 26)
        content = QHBoxLayout()
        content.setSpacing(30)
        fields = QVBoxLayout()
        fields.setSpacing(20)
        form = QFormLayout()
        form.setVerticalSpacing(18)
        self.onboarding_name = QLineEdit(profile.get("name", ""))
        self.onboarding_name.setMaxLength(60)
        self.onboarding_rating_combo = QComboBox()
        self.onboarding_rating_combo.addItems(RATINGS)
        self.onboarding_rating_combo.setCurrentText(profile.get("self_rating", RATINGS[0]))
        form.addRow(self.tr("profile_name"), self.onboarding_name)
        form.addRow(self.tr("profile_rating"), self.onboarding_rating_combo)
        fields.addLayout(form)
        fields.addWidget(self._label(self.tr("onboarding_rating_note"), "muted", True))
        choices = QHBoxLayout()
        choices.setSpacing(18)
        choices.addWidget(self._button(self.tr("onboarding_quick"), lambda: self._choose_onboarding_path(False), primary=True))
        choices.addWidget(self._button(self.tr("onboarding_assess"), lambda: self._choose_onboarding_path(True)))
        choices.addStretch()
        fields.addLayout(choices)
        content.addLayout(fields, 1)
        illustration = LearningIllustration(self.theme)
        illustration.setFixedSize(180, 150)
        content.addWidget(illustration)
        layout.addLayout(content)

    def _choose_onboarding_path(self, use_assessment):
        rating = self.onboarding_rating_combo.currentText()
        name = self.onboarding_name.text().strip() or None
        self._run(lambda: self.service.set_onboarding_rating(rating, name=name, use_assessment=use_assessment), lambda _: self.show_page("onboarding"))

    def _assessment_size_card(self, onboarding=False):
        self._page_heading(self.tr("assessment_title"), self.tr("assessment_save_hint"))
        card, layout = self._card(self.tr("assessment_choose_count"), self.body_layout)
        form = QFormLayout()
        form.setVerticalSpacing(18)
        self.assessment_rating_combo = QComboBox()
        self.assessment_rating_combo.addItems(RATINGS)
        self.assessment_rating_combo.setCurrentText(self.current_data.get("profile", {}).get("self_rating", RATINGS[0]))
        self.assessment_count_combo = QComboBox()
        for count in (20, 50, 100, 200, 500):
            self.assessment_count_combo.addItem(f"{count} " + self.tr("assessment_question_unit"), count)
        if onboarding:
            self.assessment_rating_combo.hide()
        else:
            form.addRow(self.tr("profile_rating"), self.assessment_rating_combo)
        form.addRow(self.tr("assessment_count"), self.assessment_count_combo)
        layout.addLayout(form)
        layout.addWidget(self._label(self.tr("assessment_count_hint"), "muted", True))
        layout.addWidget(self._button(self.tr("assessment_begin"), lambda: self._begin_assessment(onboarding), primary=True), 0, Qt.AlignmentFlag.AlignRight)

    def _begin_assessment(self, onboarding):
        rating = self.assessment_rating_combo.currentText()
        count = self.assessment_count_combo.currentData()
        def started(record):
            self.assessment_record = record
            self.assessment_choose_new = False
            self.show_page("onboarding" if onboarding else "assessment")
        self._run(lambda: self.service.start_assessment(rating, count), started)

    def _open_reassessment(self):
        active = self.service.snapshot().get("active_assessment")
        self.assessment_choose_new = not bool(active and active.get("status") == "in_progress")
        self.show_page("assessment")

    def _assessment_page(self):
        record = None if self.assessment_choose_new else self.service.assessment()
        if record:
            self._render_assessment(record, onboarding=False)
        else:
            self._assessment_size_card(onboarding=False)

    def _render_assessment(self, record, onboarding):
        self.assessment_record = record
        if record.get("status") == "complete":
            self._assessment_result(record, onboarding)
            return
        for shortcut in self.quiz_shortcuts:
            shortcut.setEnabled(True)
        answered = record.get("answered_count", len(record.get("answers", [])))
        count = record.get("question_count", 20)
        self._page_heading(self.tr("assessment_title"), f"{answered + 1} / {count}")
        card, layout = self._card(parent_layout=self.body_layout)
        layout.setContentsMargins(36, 30, 36, 30)
        question = record.get("question") or {}
        word = self._label(question.get("lemma", ""), "word")
        word.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(word)
        prompt = question.get("prompt") or self.tr("quiz_hint")
        if question.get("pos"):
            prompt += f"  ·  {question['pos']}"
        label = self._label(prompt, "muted", True)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        layout.addSpacing(10)
        for index, option in enumerate(question.get("options", [])):
            button = self._answer_button(index, option, lambda option_id=option["id"]: self._answer_assessment(option_id, onboarding))
            self.answer_buttons.append(button)
            layout.addWidget(button)
        self.unknown_button = self._button(self.tr("dont_know"), lambda: self._answer_assessment(None, onboarding))
        self.unknown_button.setObjectName("unknownButton")
        layout.addWidget(self.unknown_button)
        progress = QProgressBar()
        progress.setRange(0, count)
        progress.setValue(answered)
        progress.setTextVisible(False)
        layout.addWidget(progress)
        layout.addWidget(self._label(self.tr("quiz_shortcuts") + "  ·  " + self.tr("assessment_save_hint"), "muted", True))

    def _answer_assessment(self, option_id, onboarding):
        for button in self.answer_buttons:
            button.setEnabled(False)
        self.unknown_button.setEnabled(False)
        identifier = self.assessment_record["id"]
        def answered(record):
            self.assessment_record = record
            self.show_page("onboarding" if onboarding else "assessment")
        result = self._run(lambda: self.service.answer_assessment(identifier, option_id), answered)
        if result is None:
            for button in self.answer_buttons:
                button.setEnabled(True)
            self.unknown_button.setEnabled(True)

    def _assessment_result(self, record, onboarding):
        self._page_heading(self.tr("assessment_result_title"))
        result = record.get("result", {})
        card, layout = self._card(parent_layout=self.body_layout)
        top = QHBoxLayout()
        top.addWidget(self._label(f"L{result.get('recommended_level', 1)}", "statValue"))
        top.addWidget(self._label(self.tr("assessment_recommended_level"), "muted"))
        top.addStretch()
        top.addWidget(self._label(f"{record.get('answered_count', 0)} / {record.get('question_count', 0)} " + self.tr("assessment_question_unit"), "pinkTag"))
        layout.addLayout(top)
        estimated_range = result.get("estimated_range", [])
        if len(estimated_range) == 2:
            layout.addWidget(self._label(self.tr("assessment_estimated_range").format(lower=estimated_range[0], upper=estimated_range[1]), "sectionTitle", True))
        if result.get("summary"):
            layout.addWidget(self._label(result["summary"], None, True))
        if result.get("confidence"):
            layout.addWidget(self._label(self.tr("assessment_confidence") + ": " + str(result["confidence"]), "muted", True))
        layout.addWidget(self._label(self.tr("assessment_result_note"), "muted", True))
        if not onboarding:
            layout.addWidget(self._label(self.tr("assessment_retake_note"), "muted", True))
        controls = QHBoxLayout()
        if onboarding:
            controls.addWidget(self._button(self.tr("assessment_to_goal"), lambda: self._accept_assessment(record, True), primary=True))
        else:
            controls.addWidget(self._button(self.tr("assessment_adopt_difficulty"), lambda: self._accept_assessment(record, False), primary=True))
            controls.addWidget(self._button(self.tr("back_home"), lambda: self.show_page("home")))
        controls.addStretch()
        layout.addLayout(controls)

    def _accept_assessment(self, record, onboarding):
        def accepted(_):
            self.show_page("onboarding" if onboarding else "home")
            if not onboarding:
                self._notice(self.tr("assessment_difficulty_saved"))
        self._run(lambda: self.service.accept_assessment(record["id"]), accepted)

    def _finish_onboarding(self):
        kind, word_set_id = self.goal_combo.currentData()
        baseline, target = self.baseline_spin.value(), self.target_spin.value()
        self._run(lambda: self.service.finish_onboarding(kind, baseline=baseline, target=target, word_set_id=word_set_id), lambda _: self.show_page("home"))

    def _start_or_continue(self):
        if not self.service.snapshot().get("profile", {}).get("onboarding_complete", False):
            self.show_page("onboarding")
            return
        def operation():
            active = self.service.snapshot().get("active_session")
            self.current_session = self.service.session(active["id"]) if active else self.service.start_session()
        self._run(operation, lambda _: self.show_page("learning"))

    def _learning_page(self):
        active = self.current_data.get("active_session")
        if active:
            self.current_session = self.service.session(active["id"])
        elif self.current_session and self.current_session.get("id"):
            self.current_session = self.service.session(self.current_session["id"])
        else:
            self._page_heading(self.tr("nav_learning"))
            self.body_layout.addWidget(self._label(self.tr("no_active_session"), "muted"))
            self.body_layout.addWidget(self._button(self.tr("start_learning"), self._start_or_continue, primary=True))
            return
        stage = self.current_session.get("stage")
        handlers = {
            "overview": self._overview, "learn": self._learn, "relearn": self._learn,
            "quiz": self._quiz, "round_result": self._round_result, "complete": self._complete,
        }
        handlers.get(stage, self._overview)()

    def _session_action(self, method, *args):
        self.speech.stop()
        self._run(lambda: method(self.current_session["id"], *args), self._session_updated)

    def _session_updated(self, session):
        self.current_session = session
        self.show_page("learning")

    def _make_table(self, headers, rows=0):
        table = QTableWidget(rows, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().hide()
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().setDefaultSectionSize(43)
        table.setMinimumHeight(min(580, 48 + rows * 43))
        table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        return table

    def _overview(self):
        session = self.current_session
        self._page_heading(self.tr("overview_title"), self.tr("overview_hint"), notebook=True)
        card, layout = self._card(parent_layout=self.body_layout)
        words = session.get("words", [])
        table = self._make_table([self.tr("table_word"), self.tr("table_meaning"), self.tr("table_level"), self.tr("table_known")], len(words))
        table.setObjectName("overviewTable")
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for row, word in enumerate(words):
            table.setItem(row, 0, QTableWidgetItem(word.get("lemma", "")))
            table.setItem(row, 1, QTableWidgetItem(meanings(word)))
            table.setItem(row, 2, QTableWidgetItem(f"L{word.get('level', 1)}"))
            check = QCheckBox()
            check.setAccessibleName(f"{word.get('lemma', '')} {self.tr('table_known')}")
            check.setChecked(word["id"] in session.get("known_before", []))
            check.toggled.connect(lambda known, word_id=word["id"]: self._mark_known(word_id, known))
            wrapper = QWidget()
            wrapper_layout = QHBoxLayout(wrapper)
            wrapper_layout.setContentsMargins(15, 0, 0, 0)
            wrapper_layout.addWidget(check)
            table.setCellWidget(row, 3, wrapper)
        layout.addWidget(table)
        row = QHBoxLayout()
        row.addWidget(self._label(self.tr("saved_on_exit"), "muted"))
        row.addStretch()
        row.addWidget(self._button(self.tr("overview_begin"), lambda: self._session_action(self.service.begin_learning), primary=True))
        layout.addLayout(row)

    def _mark_known(self, word_id, known):
        result = self._run(lambda: self.service.mark_known(self.current_session["id"], word_id, known))
        if result:
            self.current_session = result

    def _current_word(self):
        session = self.current_session
        if session.get("current_word"):
            return session["current_word"]
        words = {word["id"]: word for word in session.get("words", [])}
        ids = session.get("learn_ids", list(words))
        index = session.get("learn_index", 0)
        return words.get(ids[min(index, len(ids) - 1)], {}) if ids else {}

    def _learn(self):
        session = self.current_session
        word = self._current_word()
        is_retry = session.get("stage") == "relearn"
        ids = session.get("learn_ids", [])
        index = session.get("learn_index", 0)
        self._page_heading(self.tr("relearn_title" if is_retry else "learn_title"), f"{index + 1} / {len(ids)}", notebook=True)
        card, layout = self._card(parent_layout=self.body_layout)
        layout.setContentsMargins(40, 37, 40, 36)
        top = QHBoxLayout()
        top.addWidget(self._label(f"L{word.get('level', 1)}", "muted"))
        top.addStretch()
        if word.get("id") in session.get("known_before", []):
            top.addWidget(self._label(self.tr("table_known"), "neutralTag"))
        elif word.get("id") in session.get("prior_mastered", []):
            top.addWidget(self._label(self.tr("word_review"), "neutralTag"))
        else:
            top.addWidget(self._label(self.tr("word_new"), "pinkTag"))
        layout.addLayout(top)
        lemma = self._label(word.get("lemma", ""), "word")
        lemma.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lemma)
        phonetic = self._label(word.get("phonetic") or self.tr("phonetic_missing"), "phonetic")
        phonetic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(phonetic)
        play_row = QHBoxLayout()
        play_row.addStretch()
        play_row.addWidget(self._button("◖  " + self.tr("pronounce"), lambda: self._speak_word(word)))
        play_row.addStretch()
        layout.addLayout(play_row)
        self.speech_status_label = self._label(self._speech_status(), "muted", True)
        self.speech_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.speech_status_label)
        layout.addSpacing(15)
        for sense in word.get("senses", []):
            sense_row = QHBoxLayout()
            pos = self._label(sense.get("pos", ""), "muted")
            pos.setMinimumWidth(85)
            sense_row.addWidget(pos, 0, Qt.AlignmentFlag.AlignTop)
            sense_row.addWidget(self._label(sense.get("definition", ""), "meaning", True), 1)
            layout.addLayout(sense_row)
        layout.addSpacing(20)
        progress = QProgressBar()
        progress.setRange(0, max(1, len(ids)))
        progress.setValue(index + 1)
        progress.setTextVisible(False)
        layout.addWidget(progress)
        next_label = self.tr("start_quiz") if index + 1 >= len(ids) else self.tr("next_word")
        next_button = self._button(next_label, lambda: self._session_action(self.service.next_word), primary=True)
        next_button.setObjectName("nextWordButton")
        next_button.setProperty("primary", True)
        next_button.setStyleSheet(f"background: {self.theme['blue_dark']}; color: white; border-color: {self.theme['blue_dark']};")
        next_button.setDefault(True)
        layout.addWidget(next_button, 0, Qt.AlignmentFlag.AlignRight)
        self.body_layout.addWidget(self._label("Only common meanings included in this content pack are shown.", "muted"))
        QTimer.singleShot(0, lambda w=word: self._speak_word(w) if self.page == "learning" else None)

    def _speech_status(self):
        try:
            status = self.speech.status()
            return status or self.tr("no_speech")
        except (AttributeError, RuntimeError):
            return self.tr("no_speech")

    def _speech_state_changed(self, status):
        if hasattr(self, "speech_status_label"):
            try:
                self.speech_status_label.setText(str(status))
            except RuntimeError:
                pass

    def _speak_word(self, word):
        accent = self.service.snapshot().get("settings", {}).get("english_variant", "en-US")
        self.speech.speak(word.get("lemma", ""), language=accent)

    def _quiz(self):
        for shortcut in self.quiz_shortcuts:
            shortcut.setEnabled(True)
        session = self.current_session
        question = session.get("question") or {}
        number = session.get("quiz_index", 0) + 1
        count = len(session.get("quiz_ids", []))
        round_no = session.get("round_no", 1)
        self._page_heading(self.tr("quiz_title"), f"Quiz {round_no}  ·  {number} / {count}", notebook=True)
        card, layout = self._card(parent_layout=self.body_layout)
        layout.setContentsMargins(35, 30, 35, 30)
        word = self._label(question.get("lemma", ""), "word")
        word.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(word)
        prompt = question.get("prompt") or self.tr("quiz_hint")
        if question.get("pos"):
            prompt += f"  ·  {question['pos']}"
        hint = self._label(prompt, "muted", True)
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)
        layout.addSpacing(10)
        for index, option in enumerate(question.get("options", [])):
            button = self._answer_button(index, option, lambda option_id=option["id"]: self._answer(option_id))
            self.answer_buttons.append(button)
            layout.addWidget(button)
        self.unknown_button = self._button(self.tr("dont_know"), lambda: self._answer(None))
        self.unknown_button.setObjectName("unknownButton")
        layout.addWidget(self.unknown_button)
        layout.addWidget(self._label(self.tr("quiz_shortcuts"), "muted"))

    def _answer_shortcut(self, index):
        if self.page in ("onboarding", "assessment") and self.assessment_record and self.assessment_record.get("status") == "in_progress":
            if index < len(self.answer_buttons):
                self.answer_buttons[index].click()
            return
        if self.page == "learning" and self.current_session and self.current_session.get("stage") == "quiz":
            if index < len(self.answer_buttons):
                self.answer_buttons[index].click()

    def _unknown_shortcut(self):
        if self.page in ("onboarding", "assessment") and self.assessment_record and self.assessment_record.get("status") == "in_progress":
            self.unknown_button.click()
            return
        if self.page == "learning" and self.current_session and self.current_session.get("stage") == "quiz":
            self._answer(None)

    def _answer(self, option_id):
        for button in self.answer_buttons:
            button.setEnabled(False)
        self.unknown_button.setEnabled(False)
        self._session_action(self.service.answer, option_id)

    def _round_result(self):
        session = self.current_session
        wrong = session.get("wrong_ids", [])
        self._page_heading(self.tr("round_result_title"), f"{len(wrong)} words to review" if wrong else self.tr("all_correct"), notebook=True)
        card, layout = self._card(parent_layout=self.body_layout)
        results = session.get("round_results", [])
        word_map = {word["id"]: word for word in session.get("words", [])}
        table = self._make_table([self.tr("table_word"), self.tr("table_result"), self.tr("table_answer"), self.tr("table_correct_answer")], len(results))
        for row, result in enumerate(results):
            correct = result.get("correct", False)
            unknown = result.get("kind") in ("unknown", "dont_know") or result.get("choice_text") in (None, "\u6211\u4e0d\u4f1a", self.tr("dont_know"))
            status = self.tr("status_correct") if correct else self.tr("status_unknown" if unknown else "status_wrong")
            values = [word_map.get(result.get("word_id"), {}).get("lemma", ""), status,
                      result.get("choice_text") or self.tr("dont_know"), result.get("answer_text", "")]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if col == 1:
                    item.setForeground(QColor(self.theme["success" if correct else "error"]))
                table.setItem(row, col, item)
        layout.addWidget(table)
        button_text = f"{self.tr('relearn_mistakes')} ({len(wrong)})" if wrong else self.tr("finish_session")
        layout.addWidget(self._button(button_text, lambda: self._session_action(self.service.continue_session), primary=True), 0, Qt.AlignmentFlag.AlignRight)

    def _complete(self):
        session = self.current_session
        result = session.get("result") or {}
        self._page_heading(self.tr("complete_title"), self.tr("complete_hint"), notebook=True)
        card, layout = self._card(parent_layout=self.body_layout)
        row = QHBoxLayout()
        for value, label in ((result.get("net_new_words", 0), self.tr("session_new_words")),
                             (result.get("known_before_count", len(session.get("known_before", []))), self.tr("table_known")),
                             (result.get("practice_words", len(session.get("words", []))), self.tr("session_practice_words"))):
            column = QVBoxLayout()
            column.addWidget(self._label(value, "statValue"))
            column.addWidget(self._label(label, "muted"))
            row.addLayout(column, 1)
        layout.addLayout(row)
        unknown_count = result.get("unknown_count", 0)
        wrong_count = max(0, result.get("error_count", 0) - unknown_count)
        layout.addWidget(self._label(f"{wrong_count} incorrect  ·  {unknown_count} unknown  ·  {result.get('retry_count', 0)} retries", "muted"))
        if session.get("review_of"):
            layout.addWidget(self._label(self.tr("history_review_hint"), "muted", True))
        controls = QHBoxLayout()
        controls.addWidget(self._button(self.tr("next_session"), self._new_session, primary=True))
        controls.addWidget(self._button(self.tr("back_home"), lambda: self.show_page("home")))
        controls.addWidget(self._button(self.tr("history_details"), lambda: self._history_details(session)))
        controls.addStretch()
        controls.addWidget(self._button(self.tr("skip_animation"), self.effects.stop, quiet=True))
        layout.addLayout(controls)
        if session["id"] not in self._celebrated:
            self._celebrated.add(session["id"])
            QTimer.singleShot(0, self._start_celebration)

    def _new_session(self):
        self._run(lambda: self.service.start_session(), self._session_updated)

    def _start_celebration(self):
        if self.page != "learning" or self.current_session.get("stage") != "complete":
            return
        word_stats = self.current_session.get("word_stats", {})
        words = []
        for word in self.current_session.get("words", []):
            stats = word_stats.get(word["id"], {}) if isinstance(word_stats, dict) else {}
            if stats.get("error_count", 0) or stats.get("unknown_count", 0):
                words.append(word.get("lemma", ""))
        if not words:
            errors = {item.get("word_id") for item in self.current_session.get("attempts", []) if not item.get("correct", False)}
            words = [word.get("lemma", "") for word in self.current_session.get("words", []) if word["id"] in errors]
        target = QPointF(self.notebook_button.mapTo(self.root, self.notebook_button.rect().center()))
        self.effects.start(words, target, reduced=self.current_data.get("settings", {}).get("reduced_motion", False))

    def _mistakes_page(self):
        self._page_heading(self.tr("mistakes_title"), self.tr("mistakes_hint"))
        mistakes = self.service.mistakes()
        if not mistakes:
            self.body_layout.addWidget(self._label(self.tr("mistakes_empty"), "muted"))
            return
        card, layout = self._card(parent_layout=self.body_layout)
        table = self._make_table([self.tr("table_word"), self.tr("table_meaning"), self.tr("table_errors"), self.tr("table_unknowns"), self.tr("table_retries")], len(mistakes))
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for row, item in enumerate(mistakes):
            word = item.get("word", item)
            values = [word.get("lemma", ""), meanings(word), item.get("error_count", 0), item.get("unknown_count", 0), item.get("retry_count", 0)]
            for col, value in enumerate(values):
                table.setItem(row, col, QTableWidgetItem(str(value)))
        table.cellDoubleClicked.connect(lambda row, col: self._mistake_detail(mistakes[row]))
        layout.addWidget(table)
        layout.addWidget(self._label("Double-click a word to see its definitions, pronunciation and total attempts.", "muted"))

    def _mistake_detail(self, item):
        word = item.get("word", item)
        dialog = QDialog(self)
        dialog.setWindowTitle(word.get("lemma", ""))
        dialog.resize(560, 370)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(30, 25, 30, 25)
        layout.addWidget(self._label(word.get("lemma", ""), "word"))
        layout.addWidget(self._label(word.get("phonetic") or self.tr("phonetic_missing"), "phonetic"))
        layout.addWidget(self._label(meanings(word), "meaning", True))
        layout.addWidget(self._label(f"{item.get('answer_count', 0)} attempts  ·  {item.get('error_count', 0)} incorrect  ·  {item.get('unknown_count', 0)} unknown  ·  {item.get('retry_count', 0)} retries", "muted", True))
        layout.addStretch()
        controls = QHBoxLayout()
        controls.addWidget(self._button(self.tr("pronounce"), lambda: self._speak_word(word)))
        source_sessions = item.get("session_ids", [])
        def review_original():
            def ready(source):
                dialog.accept()
                self._review(source)
            self._run(lambda: self.service.session(source_sessions[-1]), ready)
        review_button = self._button(self.tr("review_original_session"), review_original)
        review_button.setEnabled(bool(source_sessions))
        controls.addWidget(review_button)
        controls.addWidget(self._button(self.tr("close"), dialog.accept))
        layout.addLayout(controls)
        dialog.exec()

    def _history_page(self):
        self._page_heading(self.tr("history_title"), self.tr("history_review_hint"))
        history = self.service.history()
        if not history:
            self.body_layout.addWidget(self._label(self.tr("history_empty"), "muted"))
            return
        for session in history:
            card, layout = self._card(parent_layout=self.body_layout)
            top = QHBoxLayout()
            title = date_text(session.get("completed_at") or session.get("created_at"))
            top.addWidget(self._label(f"{title}  ·  {len(session.get('words', []))} words", "sectionTitle"))
            top.addStretch()
            if session.get("review_of"):
                top.addWidget(self._label("Try again", "pinkTag"))
            layout.addLayout(top)
            layout.addWidget(self._label(" · ".join(word.get("lemma", "") for word in session.get("words", [])[:10]), "muted", True))
            result = session.get("result", {})
            row = QHBoxLayout()
            row.addWidget(self._label(f"{result.get('net_new_words', 0)} new words  ·  {result.get('retry_count', 0)} retries", "muted"))
            row.addStretch()
            row.addWidget(self._button(self.tr("history_details"), lambda s=session: self._history_details(s)))
            row.addWidget(self._button(self.tr("history_review"), lambda s=session: self._review(s), quiet=True))
            layout.addLayout(row)

    def _history_details(self, session):
        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr("history_details"))
        dialog.resize(840, 680)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.addWidget(self._label(f"{date_text(session.get('completed_at'))}  ·  {len(session.get('words', []))} words", "sectionTitle"))
        tabs = QTabWidget()
        stats = session.get("word_stats", {})
        words = session.get("words", [])
        word_table = self._make_table([self.tr("table_word"), self.tr("table_meaning"), self.tr("table_attempts"), self.tr("table_errors"), self.tr("table_unknowns"), self.tr("table_retries")], len(words))
        word_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for row, word in enumerate(words):
            stat = stats.get(word["id"], {}) if isinstance(stats, dict) else {}
            values = [word.get("lemma", ""), meanings(word), stat.get("answer_count", 0), stat.get("error_count", 0), stat.get("unknown_count", 0), stat.get("retry_count", 0)]
            for col, value in enumerate(values):
                word_table.setItem(row, col, QTableWidgetItem(str(value)))
        tabs.addTab(word_table, "Word records")
        attempts = session.get("attempts", [])
        answers = self._make_table(["Word", "Quiz round", "Your answer", "Correct meaning", "Result"], len(attempts))
        word_map = {word["id"]: word for word in words}
        for row, attempt in enumerate(attempts):
            values = [word_map.get(attempt.get("word_id"), {}).get("lemma", ""), attempt.get("round_no", ""),
                      attempt.get("choice_text") or self.tr("dont_know"), attempt.get("answer_text", ""),
                      self.tr("status_correct" if attempt.get("correct") else "status_unknown" if attempt.get("kind") == "unknown" else "status_wrong")]
            for col, value in enumerate(values):
                answers.setItem(row, col, QTableWidgetItem(str(value)))
        tabs.addTab(answers, "Answer records")
        layout.addWidget(tabs, 1)
        layout.addWidget(self._button(self.tr("close"), dialog.accept), 0, Qt.AlignmentFlag.AlignRight)
        dialog.exec()

    def _review(self, session):
        if self.service.snapshot().get("active_session"):
            self._notice("Finish or continue your current session first.")
            self.show_page("learning")
            return
        self._run(lambda: self.service.start_session(review_of=session["id"]), self._session_updated)

    def _achievements_page(self):
        self._page_heading(self.tr("achievements_title"), self.tr("achievements_hint"))
        count = self.current_data.get("stats", {}).get("achievement_practice_words", 0)
        self.body_layout.addWidget(self._label(f"Words practiced toward achievements: {count}", "muted"))
        grid = QGridLayout()
        grid.setSpacing(18)
        for index, achievement in enumerate(self.service.achievements()):
            card, layout = self._card()
            earned = achievement.get("earned", False)
            top = QHBoxLayout()
            star = BadgeIcon(earned, index, self.theme, size=58)
            top.addWidget(star)
            top.addStretch()
            top.addWidget(self._label(self.tr("achievement_earned" if earned else "achievement_locked"), "pinkTag" if earned else "muted"))
            layout.addLayout(top)
            layout.addWidget(self._label(achievement.get("title", ""), "sectionTitle"))
            layout.addWidget(self._label(achievement.get("description", ""), "muted", True))
            if earned:
                layout.addWidget(self._label(date_text(achievement.get("earned_at")), "muted"))
            else:
                threshold = achievement.get("threshold", 0)
                if threshold:
                    progress = QProgressBar()
                    progress.setRange(0, threshold)
                    progress.setValue(min(count, threshold))
                    progress.setTextVisible(False)
                    layout.addWidget(progress)
                    layout.addWidget(self._label(f"{min(count, threshold)} / {threshold}", "muted"))
            grid.addWidget(card, index // 2, index % 2)
        self.body_layout.addLayout(grid)

    def _settings_page(self):
        self._page_heading(self.tr("settings_title"))
        snapshot = self.current_data
        profile = snapshot.get("profile", {})
        settings = snapshot.get("settings", {})
        card, layout = self._card(self.tr("profile_section"), self.body_layout)
        form = QFormLayout()
        form.setVerticalSpacing(15)
        self.name_edit = QLineEdit(profile.get("name", ""))
        self.name_edit.setMaxLength(60)
        self.rating_combo = QComboBox()
        self.rating_combo.addItems(RATINGS)
        self.rating_combo.setCurrentText(profile.get("self_rating", RATINGS[0]))
        self.level_combo = QComboBox()
        available = snapshot.get("content", {}).get("levels", [])
        self._level_choices(self.level_combo, available)
        self.level_combo.setCurrentIndex(max(0, self.level_combo.findData(profile.get("difficulty", 1))))
        form.addRow(self.tr("profile_name"), self.name_edit)
        form.addRow(self.tr("profile_rating"), self.rating_combo)
        form.addRow(self.tr("profile_difficulty"), self.level_combo)
        layout.addLayout(form)
        layout.addWidget(self._label(self.tr("rating_note"), "muted", True))
        layout.addWidget(self._label(self.tr("level_note"), "muted", True))
        layout.addWidget(self._button(self.tr("save_profile"), self._save_profile, primary=True), 0, Qt.AlignmentFlag.AlignRight)
        card, layout = self._card(self.tr("network_section"), self.body_layout)
        form = QFormLayout()
        form.setVerticalSpacing(15)
        self.network_combo = QComboBox()
        for text, code in NETWORKS:
            self.network_combo.addItem(text, code)
        self.network_combo.setCurrentIndex(max(0, self.network_combo.findData(settings.get("network_mode", "offline"))))
        self.settings_accent_combo = QComboBox()
        for text, code in ACCENTS:
            self.settings_accent_combo.addItem(text, code)
        self.settings_accent_combo.setCurrentIndex(max(0, self.settings_accent_combo.findData(settings.get("english_variant", "en-US"))))
        self.motion_check = QCheckBox(self.tr("reduced_motion"))
        self.motion_check.setChecked(settings.get("reduced_motion", False))
        form.addRow(self.tr("network_mode"), self.network_combo)
        form.addRow(self.tr("english_variant"), self.settings_accent_combo)
        form.addRow("", self.motion_check)
        layout.addLayout(form)
        layout.addWidget(self._label(self.tr("network_note"), "muted", True))
        ai_check = QCheckBox(self.tr("ai_disabled"))
        ai_check.setChecked(False)
        ai_check.setEnabled(False)
        layout.addWidget(ai_check)
        layout.addWidget(self._label(self.tr("ai_note"), "muted", True))
        layout.addWidget(self._button(self.tr("save_preferences"), self._save_preferences, primary=True), 0, Qt.AlignmentFlag.AlignRight)
        card, layout = self._card(self.tr("data_section"), self.body_layout)
        row = QHBoxLayout()
        row.addWidget(self._button(self.tr("export_data"), self._export))
        row.addWidget(self._button(self.tr("import_data"), self._import))
        row.addStretch()
        layout.addLayout(row)
        path_label = self._label(str(self.service.data_dir), "muted", True)
        path_label.setToolTip(str(self.service.data_dir))
        layout.addWidget(path_label)
        card, layout = self._card(self.tr("texts_section"), self.body_layout)
        layout.addWidget(self._label(self.tr("texts_description"), "muted", True))
        layout.addWidget(self._button(self.tr("edit_texts"), self._edit_texts), 0, Qt.AlignmentFlag.AlignLeft)
        card, layout = self._card(self.tr("content_section"), self.body_layout)
        content = snapshot.get("content", {})
        layout.addWidget(self._label(f"Version: {content.get('version', '')}  ·  Unique words: {content.get('word_count', 0)}", None, True))
        layout.addWidget(self._label("Interface: English  ·  Definitions: English  ·  Learning: English", "muted", True))

    def _save_profile(self):
        self._run(lambda: self.service.update_profile(name=self.name_edit.text().strip(), self_rating=self.rating_combo.currentText(), difficulty=self.level_combo.currentData()), lambda _: self._notice(self.tr("profile_saved")))
        self._refresh_chrome()

    def _save_preferences(self):
        self._run(lambda: self.service.update_settings(network_mode=self.network_combo.currentData(), english_variant=self.settings_accent_combo.currentData(), reduced_motion=self.motion_check.isChecked(), ai_enabled=False), lambda _: self._notice(self.tr("preferences_saved")))
        self.speech.stop()
        if self.motion_check.isChecked():
            self.effects.stop()
        self._refresh_chrome()

    def _goal_kind_changed(self):
        is_count = self.goal_combo.currentData()[0] == "word_count"
        self.baseline_spin.setEnabled(is_count)
        self.target_spin.setEnabled(is_count)

    def _create_goal(self):
        kind, word_set_id = self.goal_combo.currentData()
        def saved(_):
            self.show_page("goals")
            self._notice(self.tr("goal_created"))
        self._run(lambda: self.service.configure_goal(kind, baseline=self.baseline_spin.value(), target=self.target_spin.value(), word_set_id=word_set_id), saved)

    def _goal_form(self, onboarding=False):
        snapshot = self.current_data
        profile = snapshot.get("profile", {})
        card, layout = self._card(self.tr("goal_section"), self.body_layout)
        form = QFormLayout()
        form.setVerticalSpacing(15)
        self.goal_combo = QComboBox()
        self.goal_combo.addItem(self.tr("ordinary_goal"), ("word_count", None))
        self.goal_combo.addItem(self.tr("word_set_pending"), ("cet4", None))
        if not onboarding:
            for word_set in snapshot.get("content", {}).get("word_sets", []):
                if word_set.get("kind") != "cet4":
                    self.goal_combo.addItem(word_set.get("name", word_set["id"]), ("word_set", word_set["id"]))
        baseline = snapshot.get("stats", {}).get("estimated_vocabulary", profile.get("estimated_vocabulary", 0))
        if onboarding and profile.get("onboarding_assessment_id"):
            assessment = self.service.assessment(profile["onboarding_assessment_id"])
            result = assessment.get("result", {}) if assessment else {}
            estimated_range = result.get("estimated_range", [])
            if len(estimated_range) == 2:
                baseline = int(sum(estimated_range) / 2)
                layout.addWidget(self._label(self.tr("assessment_estimate_reference").format(lower=estimated_range[0], upper=estimated_range[1]), "muted", True))
        self.baseline_spin = QSpinBox()
        self.baseline_spin.setRange(0, 1000000)
        self.baseline_spin.setValue(baseline)
        self.target_spin = QSpinBox()
        self.target_spin.setRange(1, 1000000)
        default_target = max(5000, (baseline // 1000 + 1) * 1000)
        self.target_spin.setValue(min(self.target_spin.maximum(), default_target))
        self.target_spin.setSingleStep(100)
        self.goal_combo.currentIndexChanged.connect(self._goal_kind_changed)
        form.addRow(self.tr("goal_kind"), self.goal_combo)
        form.addRow(self.tr("goal_baseline"), self.baseline_spin)
        form.addRow(self.tr("goal_target"), self.target_spin)
        layout.addLayout(form)
        layout.addWidget(self._label(self.tr("goal_note"), "muted", True))
        callback = self._finish_onboarding if onboarding else self._create_goal
        label = self.tr("onboarding_finish") if onboarding else self.tr("goal_create")
        layout.addWidget(self._button(label, callback, primary=True), 0, Qt.AlignmentFlag.AlignRight)

    def _goals_page(self):
        self._page_heading(self.tr("goals_title"))
        goals = self.current_data.get("goals", [])
        if not goals:
            self.body_layout.addWidget(self._label(self.tr("goal_empty"), "muted"))
        for goal in reversed(goals):
            card, layout = self._card(goal.get("title", self.tr("goals_title")), self.body_layout)
            row = QHBoxLayout()
            row.addWidget(self._label(self._goal_summary(goal), None, True), 1)
            row.addWidget(self._label(self._ratio_text(goal) if goal.get("available", True) else self.tr("goal_not_available"), "pinkTag"))
            layout.addLayout(row)
            progress = QProgressBar()
            progress.setRange(0, 10000)
            progress.setValue(int(float(goal.get("ratio", 0)) * 10000) if goal.get("available", True) else 0)
            progress.setTextVisible(False)
            layout.addWidget(progress)
            if goal.get("message"):
                layout.addWidget(self._label(goal["message"], "muted", True))
            missing = goal.get("missing_words", goal.get("remaining_words", []))
            if isinstance(missing, list) and missing:
                names = [word.get("lemma", word.get("id", "")) if isinstance(word, dict) else str(word) for word in missing]
                layout.addWidget(self._label(self.tr("remaining_words") + ": " + " · ".join(names), "muted", True))
        self._goal_form()

    def _goal_details(self):
        self.show_page("goals")

    def _queue_page(self):
        self._page_heading(self.tr("queue_title"))
        card, layout = self._card(parent_layout=self.body_layout)
        search = QLineEdit()
        search.setPlaceholderText(self.tr("search_words"))
        layout.addWidget(search)
        columns = QHBoxLayout()
        catalog_list = QListWidget()
        catalog_list.setMinimumHeight(380)
        catalog_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        queue_list = QListWidget()
        queue_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        catalog = self.service.word_catalog()
        if isinstance(catalog, dict):
            catalog = list(catalog.values())

        def fill_catalog(query=""):
            catalog_list.clear()
            for word in catalog:
                text = f"{word.get('lemma', '')}  ·  {meanings(word)}"
                if query.casefold() in text.casefold():
                    item = QListWidgetItem(text)
                    item.setData(Qt.ItemDataRole.UserRole, word["id"])
                    catalog_list.addItem(item)

        def fill_queue():
            queue_list.clear()
            for word in self.service.queue():
                item = QListWidgetItem(f"{word.get('lemma', '')}  ·  {meanings(word)}")
                item.setData(Qt.ItemDataRole.UserRole, word["id"])
                queue_list.addItem(item)

        fill_catalog()
        fill_queue()
        search.textChanged.connect(fill_catalog)
        for title, widget in ((self.tr("local_catalog"), catalog_list), (self.tr("queue_title"), queue_list)):
            col = QVBoxLayout()
            col.addWidget(self._label(title, "sectionTitle"))
            col.addWidget(widget)
            columns.addLayout(col, 1)
        layout.addLayout(columns, 1)

        def add_selected():
            identifiers = [item.data(Qt.ItemDataRole.UserRole) for item in catalog_list.selectedItems()]
            if not identifiers:
                self._notice(self.tr("nothing_selected"))
                return
            self._run(lambda: [self.service.enqueue(word_id) for word_id in identifiers])
            fill_queue()

        def remove_selected():
            identifiers = [item.data(Qt.ItemDataRole.UserRole) for item in queue_list.selectedItems()]
            self._run(lambda: [self.service.remove_from_queue(word_id) for word_id in identifiers])
            fill_queue()

        actions = QHBoxLayout()
        actions.addWidget(self._button(self.tr("add_selected"), add_selected, primary=True))
        actions.addWidget(self._button(self.tr("remove"), remove_selected))
        actions.addStretch()
        layout.addLayout(actions)

    def _queue_dialog(self):
        self.show_page("queue")

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(self, self.tr("export_data"), "vocabulary-records.json", "JSON (*.json)",
                                            options=QFileDialog.Option.DontUseNativeDialog)
        if path:
            self._run(lambda: self.service.export_data(path), lambda _: self._notice(self.tr("export_success")))

    def _import(self):
        path, _ = QFileDialog.getOpenFileName(self, self.tr("import_data"), "", "JSON (*.json)",
                                            options=QFileDialog.Option.DontUseNativeDialog)
        if not path:
            return
        answer = QMessageBox.question(self, self.tr("import_confirm_title"), self.tr("import_confirm"), QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        def done(_):
            self.current_session = None
            self.assessment_record = None
            self._celebrated.clear()
            self.show_page("home")
            self._notice(self.tr("import_success"))
        self._run(lambda: self.service.import_data(path), done)

    def _edit_texts(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr("text_editor_title"))
        dialog.resize(830, 680)
        layout = QVBoxLayout(dialog)
        layout.addWidget(self._label(self.tr("text_editor_hint"), "muted", True))
        editor = QPlainTextEdit(json.dumps(self.texts, ensure_ascii=False, indent=2))
        font = QFont("Consolas", 11)
        editor.setFont(font)
        layout.addWidget(editor, 1)
        layout.addWidget(self._label(str(self.text_path), "muted", True))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText(self.tr("save"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(self.tr("cancel"))

        def save():
            try:
                custom = json.loads(editor.toPlainText())
                if not isinstance(custom, dict) or not all(isinstance(k, str) and isinstance(v, str) and len(v) <= 5000 for k, v in custom.items()):
                    raise ValueError("Interface text must be a JSON object mapping keys to strings of at most 5,000 characters each.")
                if not custom.get("app_title", "").strip():
                    raise ValueError("The application name cannot be empty.")
                self.text_path.parent.mkdir(parents=True, exist_ok=True)
                temp_path = self.text_path.with_suffix(".json.tmp")
                temp_path.write_text(json.dumps(custom, ensure_ascii=False, indent=2), encoding="utf-8")
                temp_path.replace(self.text_path)
                self.texts = self._load_texts()
                dialog.accept()
            except (ValueError, OSError) as error:
                QMessageBox.warning(dialog, self.tr("error_title"), str(error))
        buttons.accepted.connect(save)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.setWindowTitle(self.tr("app_title"))
            self.brand.setText(self.tr("app_title"))
            self.subtitle_label.setText(self.tr("app_subtitle"))
            self.goal_details_button.setText(self.tr("goal_details"))
            self.show_page("settings")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "effects"):
            self.effects.setGeometry(self.root.rect())

    def closeEvent(self, event):
        self.speech.stop()
        if hasattr(self, "effects"):
            self.effects.stop()
        super().closeEvent(event)
