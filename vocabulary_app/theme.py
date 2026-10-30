"""Shared colors, typography and widget styles."""

import json
from pathlib import Path


def load_theme(resource_dir=None):
    path = Path(resource_dir or Path(__file__).parent / "resources") / "theme.json"
    return json.loads(path.read_text(encoding="utf-8"))


def stylesheet(theme):
    t = theme
    module_styles = "\n".join(
        f'''
        QPushButton#moduleCard[module="{module}"]:hover {{
            background: {t['module_tints'][module]}; border-color: {accent};
        }}
        QPushButton#moduleCard[module="{module}"]:focus {{ border: 2px solid {accent}; }}
        QPushButton#moduleCard[module="{module}"]:pressed {{
            background: {t['module_tints'][module]}; border-color: {accent};
        }}
        '''
        for module, accent in t.get("module_accents", {}).items()
    )
    return f"""
    QWidget {{ color: {t['text']}; font-family: '{t['font_family']}'; font-size: {t['font_size']}px; }}
    QMainWindow, QWidget#appRoot, QScrollArea, QScrollArea > QWidget > QWidget {{ background: {t['background']}; }}
    QFrame#topbar, QFrame#footer {{ background: {t['surface']}; border: none; }}
    QFrame#topbar {{ border-bottom: 1px solid {t['border']}; }}
    QFrame#footer {{ border-top: 1px solid {t['border']}; }}
    QFrame#card {{ background: {t['surface']}; border: 1px solid {t['border']}; border-radius: {t['radius']}px; }}
    QFrame#profileCard {{ background: {t['surface']}; border: 1px solid {t['border']}; border-radius: 14px; }}
    QFrame#notebookIndicator {{ background: {t['surface']}; border: 1px solid #F3DDE5; border-radius: 9px; }}
    QLabel {{ background: transparent; }}
    QLabel#muted {{ color: {t['muted']}; }}
    QLabel#pageTitle {{ font-size: 26px; font-weight: 600; }}
    QLabel#sectionTitle {{ font-size: 18px; font-weight: 600; }}
    QLabel#brand {{ color: {t['text']}; font-size: 22px; font-weight: 700; }}
    QLabel#eyebrow {{ color: {t['muted']}; font-size: 12px; }}
    QLabel#heroTitle {{ color: {t['text']}; font-size: 30px; font-weight: 700; }}
    QLabel#heroAction {{ color: white; background: {t['blue_dark']}; border-radius: 8px; padding: 9px 15px; font-weight: 600; }}
    QLabel#homeMetric {{ color: {t['text']}; font-size: 25px; font-weight: 600; }}
    QLabel#profileLevel {{ color: {t['blue_dark']}; font-size: 28px; font-weight: 600; }}
    QLabel#cardDetail {{ color: {t['muted']}; font-size: 13px; }}
    QLabel#moduleTitle {{ color: {t['text']}; font-size: 16px; font-weight: 600; }}
    QLabel#modePill {{ color: #54776D; background: #EFF7F3; border-radius: 10px; padding: 5px 10px; font-size: 12px; }}
    QLabel#avatarPill {{ color: #9F526E; background: {t['pink_light']}; border-radius: 10px; padding: 6px 12px; font-size: 13px; }}
    QLabel#stepPill {{ color: {t['muted']}; background: #EFF2F6; border-radius: 12px; padding: 6px 12px; font-size: 12px; }}
    QLabel#stepPill[state="active"] {{ color: {t['blue_dark']}; background: {t['blue_light']}; font-weight: 600; }}
    QLabel#stepPill[state="complete"] {{ color: #477E6D; background: #EFF7F3; }}
    QLabel#stepPill[state="pending"] {{ color: #7A838F; background: #EFF2F6; }}
    QLabel#statValue {{ color: {t['blue_dark']}; font-size: 27px; font-weight: 600; }}
    QLabel#word {{ font-size: 46px; font-weight: 600; }}
    QLabel#phonetic {{ color: {t['muted']}; font-size: 18px; }}
    QLabel#meaning {{ font-size: 21px; }}
    QLabel#moduleSymbol {{ color: {t['blue_dark']}; font-size: 31px; font-weight: 600; min-width: 40px; }}
    QLabel#moduleArrow {{ color: #A7AFBB; font-size: 23px; }}
    QLabel#pinkTag {{ color: #AB345D; background: {t['pink_light']}; border-radius: 5px; padding: 4px 9px; }}
    QLabel#neutralTag {{ color: {t['muted']}; background: {t['background']}; border-radius: 5px; padding: 4px 9px; }}
    QLabel#error {{ color: {t['error']}; }}
    QLabel#success {{ color: {t['success']}; }}
    QPushButton {{ background: white; border: 1px solid #DDE3E9; border-radius: 8px; padding: 9px 17px; min-height: 20px; }}
    QPushButton:hover {{ background: {t['blue_light']}; border-color: {t['blue']}; }}
    QPushButton:pressed {{ background: #DBF2FB; }}
    QPushButton:focus {{ border: 2px solid {t['blue_dark']}; }}
    QPushButton:disabled {{ color: #A6ADB7; background: #F4F5F7; border-color: {t['border']}; }}
    QPushButton#primary {{ background: {t['blue_dark']}; border-color: {t['blue_dark']}; color: white; font-weight: 600; }}
    QPushButton#primary:hover {{ background: #00688E; }}
    QPushButton#moduleCard {{ background: {t['surface']}; border: 1px solid {t['border']}; border-radius: 14px; padding: 0; text-align: left; }}
    QPushButton#moduleCard:hover {{ background: #FAFCFE; border-color: #C9D8E3; }}
    QPushButton#moduleCard:focus {{ border: 2px solid {t['blue_dark']}; }}
    QPushButton#moduleCard[featured="true"] {{ background: #FAFDFE; border-color: #D9EDF5; }}
    QPushButton#moduleCard[featured="true"]:hover {{ background: #F3FBFE; border-color: #9DD8ED; }}
    QPushButton#answer {{ text-align: left; padding: 0; font-size: 18px; }}
    QPushButton#quiet {{ border: none; color: {t['blue_dark']}; background: transparent; padding: 5px 7px; }}
    QPushButton#quiet:hover {{ background: {t['blue_light']}; }}
    QPushButton#quiet:focus {{ border: 1px solid {t['blue_dark']}; }}
    QPushButton#backHomeButton {{ color: #5D6877; border-color: {t['border']}; background: white; padding: 7px 12px; }}
    QPushButton#backHomeButton:hover {{ color: {t['blue_dark']}; border-color: #B9DFED; background: #F4FBFE; }}
    QLineEdit, QSpinBox, QComboBox, QPlainTextEdit {{ border: 1px solid #DDE3E9; border-radius: 7px; background: white; padding: 8px; selection-background-color: {t['blue_dark']}; }}
    QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus {{ border-color: {t['blue_dark']}; }}
    QComboBox::drop-down {{ width: 25px; border: none; }}
    QCheckBox {{ spacing: 9px; }}
    QCheckBox::indicator {{ width: 17px; height: 17px; }}
    QProgressBar {{ border: none; background: #EAF0F4; border-radius: 3px; text-align: center; min-height: 6px; max-height: 6px; }}
    QProgressBar::chunk {{ background: {t['blue']}; border-radius: 3px; }}
    QTableWidget {{ background: white; border: none; gridline-color: {t['border']}; selection-background-color: {t['blue_light']}; selection-color: {t['text']}; alternate-background-color: #FAFCFD; }}
    QTableWidget::item {{ padding: 7px; }}
    QHeaderView::section {{ background: #F8FAFC; color: #677282; border: none; border-bottom: 1px solid {t['border']}; padding: 10px 8px; font-weight: 400; }}
    QListWidget {{ border: 1px solid {t['border']}; border-radius: 6px; background: white; outline: none; }}
    QListWidget::item {{ padding: 9px 10px; }}
    QListWidget::item:selected {{ background: {t['blue_light']}; color: {t['blue_dark']}; }}
    QScrollArea {{ border: none; }}
    QScrollBar:vertical {{ border: none; background: transparent; width: 9px; margin: 1px; }}
    QScrollBar::handle:vertical {{ background: #D9DFE6; border-radius: 4px; min-height: 30px; }}
    QScrollBar::handle:vertical:hover {{ background: #BDC8D4; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QToolTip {{ background: white; border: 1px solid {t['border']}; padding: 8px; }}
    QDialog {{ background: {t['background']}; }}
    {module_styles}
    """
