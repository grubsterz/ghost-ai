"""Premium graphite theme with violet/cyan accents (dark) and a matching light theme."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    bg: str
    sidebar: str
    card: str
    card_hover: str
    border: str
    text: str
    muted: str
    violet: str
    cyan: str
    danger: str
    ok: str
    warn: str
    input: str


DARK = Palette(bg="#14151a", sidebar="#0f1014", card="#1c1e25", card_hover="#23262f", border="#2b2e39",
               text="#ecedf3", muted="#9a9db0", violet="#8b5cf6", cyan="#22d3ee", danger="#f87171",
               ok="#34d399", warn="#fbbf24", input="#16181e")
LIGHT = Palette(bg="#f4f5f9", sidebar="#ebedf3", card="#ffffff", card_hover="#f7f7fb", border="#dfe1ea",
                text="#1a1b22", muted="#5d6175", violet="#6d3fe0", cyan="#0e8fa6", danger="#c62828",
                ok="#0f8a5f", warn="#a46200", input="#ffffff")


def palette(theme: str) -> Palette:
    return LIGHT if theme == "light" else DARK


def build_qss(theme: str, scale: float = 1.0) -> str:
    p = palette(theme)
    fs = round(10 * scale, 1)

    def px(v: float) -> int:
        return max(1, round(v * scale))

    return f"""
* {{ font-family: "Segoe UI Variable", "Segoe UI", "SF Pro Text", "Inter", "Helvetica Neue", Arial; font-size: {fs}pt; color: {p.text}; }}
QMainWindow, QDialog, #Page {{ background: {p.bg}; }}
QWidget#Sidebar {{ background: {p.sidebar}; border-right: 1px solid {p.border}; }}
QLabel#Brand {{ font-size: {round(15*scale,1)}pt; font-weight: 700; letter-spacing: 2px; }}
QLabel#BrandAccent {{ font-size: {round(15*scale,1)}pt; font-weight: 700; color: {p.cyan}; letter-spacing: 2px; }}
QLabel#Tagline, QLabel.muted, QLabel#Muted {{ color: {p.muted}; }}
QPushButton#Nav {{
    text-align: left; padding: {px(9)}px {px(14)}px; border: none; border-radius: {px(10)}px;
    background: transparent; color: {p.muted}; font-weight: 600;
}}
QPushButton#Nav:hover {{ background: {p.card}; color: {p.text}; }}
QPushButton#Nav:checked {{ background: {p.card_hover}; color: {p.text}; border-left: 3px solid {p.violet}; }}
QLabel#H1 {{ font-size: {round(20*scale,1)}pt; font-weight: 700; }}
QLabel#H2 {{ font-size: {round(13*scale,1)}pt; font-weight: 700; }}
QLabel#Big {{ font-size: {round(24*scale,1)}pt; font-weight: 700; color: {p.text}; }}
QFrame#Card {{ background: {p.card}; border: 1px solid {p.border}; border-radius: {px(14)}px; }}
QFrame#Card:hover {{ border-color: {p.violet}; }}
QFrame#Banner {{ background: {p.card}; border: 1px solid {p.warn}; border-radius: {px(12)}px; }}
QFrame#RecBanner {{ background: {p.card}; border: 2px solid {p.danger}; border-radius: {px(12)}px; }}
QLabel#Pill {{ border-radius: {px(9)}px; padding: {px(3)}px {px(10)}px; font-weight: 600; }}
QLabel#PillOk {{ border-radius: {px(9)}px; padding: {px(3)}px {px(10)}px; font-weight: 600; color: {p.ok}; border: 1px solid {p.ok}; }}
QLabel#PillWarn {{ border-radius: {px(9)}px; padding: {px(3)}px {px(10)}px; font-weight: 600; color: {p.warn}; border: 1px solid {p.warn}; }}
QLabel#PillMuted {{ border-radius: {px(9)}px; padding: {px(3)}px {px(10)}px; color: {p.muted}; border: 1px solid {p.border}; }}
QLabel#PillDanger {{ border-radius: {px(9)}px; padding: {px(3)}px {px(10)}px; font-weight: 700; color: {p.danger}; border: 1px solid {p.danger}; }}
QPushButton {{
    background: {p.card_hover}; border: 1px solid {p.border}; border-radius: {px(10)}px;
    padding: {px(8)}px {px(16)}px; font-weight: 600;
}}
QPushButton:hover {{ border-color: {p.violet}; }}
QPushButton:focus {{ border: 2px solid {p.cyan}; }}
QPushButton:disabled {{ color: {p.muted}; background: {p.card}; }}
QPushButton#Primary {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {p.violet}, stop:1 {p.cyan});
    border: none; color: white;
}}
QPushButton#Primary:hover {{ background: {p.violet}; }}
QPushButton#Primary:disabled {{ background: {p.border}; color: {p.muted}; }}
QPushButton#Danger {{ color: {p.danger}; border-color: {p.danger}; }}
QPushButton#Ghost {{ background: transparent; border: none; text-align: left; color: {p.cyan}; padding: {px(4)}px {px(6)}px; }}
QPushButton#Ghost:hover {{ text-decoration: underline; }}
QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background: {p.input}; border: 1px solid {p.border}; border-radius: {px(8)}px; padding: {px(7)}px {px(9)}px;
    selection-background-color: {p.violet};
}}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{ border: 1px solid {p.cyan}; }}
QComboBox QAbstractItemView {{ background: {p.card}; border: 1px solid {p.border}; selection-background-color: {p.violet}; }}
QCheckBox, QRadioButton {{ spacing: {px(8)}px; }}
QTableWidget, QListWidget, QTreeWidget {{
    background: {p.card}; border: 1px solid {p.border}; border-radius: {px(10)}px; gridline-color: {p.border};
    alternate-background-color: {p.card_hover};
}}
QListWidget::item, QTableWidget::item {{ padding: {px(6)}px; }}
QListWidget::item:selected, QTableWidget::item:selected {{ background: {p.violet}; color: white; }}
QHeaderView::section {{ background: {p.card_hover}; color: {p.muted}; border: none; padding: {px(6)}px; font-weight: 600; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: {px(10)}px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {p.border}; border-radius: {px(4)}px; min-height: 30px; }}
QScrollBar:horizontal {{ background: transparent; height: {px(10)}px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {p.border}; border-radius: {px(4)}px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QToolTip {{ background: {p.card}; color: {p.text}; border: 1px solid {p.border}; padding: 6px; }}
QProgressBar {{ background: {p.input}; border: none; border-radius: 4px; height: 6px; text-align: center; }}
QProgressBar::chunk {{ background: {p.violet}; border-radius: 4px; }}
QStatusBar {{ background: {p.sidebar}; color: {p.muted}; }}
"""
