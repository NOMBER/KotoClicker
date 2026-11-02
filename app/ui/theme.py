"""KotoClick colours and styles: a warm dark "evening by the fireplace" plus ginger accents."""

BG = "#2a1f1d"
BG2 = "#2b1f2b"          # violet tint for the gradient
PANEL = "#33262a"
CARD = "#3a2c2c"
CARD_HI = "#443331"
BORDER = "#4d3a36"
TEXT = "#f6e9df"
MUTED = "#b9a49a"
FAINT = "#8a766e"
ORANGE = "#ff9a3c"
ORANGE_DARK = "#e5761c"
ORANGE_SOFT = "#ffb877"
PURPLE = "#9b7ae0"
RED = "#ff6b6b"
GREEN = "#7bd88f"
FIELD = "#2a1f1f"

FONT_FAMILY = "Nunito"

STYLESHEET = f"""
* {{
    font-family: "{FONT_FAMILY}", "Segoe UI", sans-serif;
    color: {TEXT};
    font-size: 14px;
}}
QMainWindow, QDialog {{ background: {BG}; }}
QToolTip {{
    background: {CARD_HI}; color: {TEXT}; border: 1px solid {BORDER};
    border-radius: 8px; padding: 6px 8px;
}}

/* ---------- cards ---------- */
#card {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 18px;
}}
#leftPanel {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3a2a2c, stop:1 #2e2128);
    border: 1px solid {BORDER};
    border-radius: 24px;
}}
#bubble {{
    background: {CARD_HI};
    border: 1px solid #5a443e;
    border-radius: 16px;
}}
#cardTitle {{ font-size: 15px; font-weight: 800; }}
#cardHint {{ color: {MUTED}; font-size: 12px; }}
#appTitle {{ color: {ORANGE}; font-size: 26px; font-weight: 900; }}
#appSubtitle {{ color: {MUTED}; font-size: 12px; }}
#statusTitle {{ font-size: 16px; font-weight: 900; color: {TEXT}; }}
#statusLore {{ color: {MUTED}; font-size: 12px; }}
#counter {{ color: {ORANGE_SOFT}; font-size: 13px; font-weight: 700; }}
#hint {{ color: {FAINT}; font-size: 12px; }}
#sectionTitle {{ font-size: 19px; font-weight: 900; }}
#mouseSays {{ color: {MUTED}; font-size: 12px; }}

/* ---------- buttons ---------- */
QPushButton {{
    background: {CARD_HI};
    border: 1px solid {BORDER};
    border-radius: 12px;
    padding: 8px 14px;
    font-weight: 700;
}}
QPushButton:hover {{ background: #4f3b38; border-color: #6a4f47; }}
QPushButton:pressed {{ background: #3a2b2a; }}
QPushButton:disabled {{ color: {FAINT}; background: #352828; }}

QPushButton#accent {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {ORANGE_SOFT}, stop:1 {ORANGE});
    color: #3a1f0e; border: none;
}}
QPushButton#accent:hover {{ background: {ORANGE_SOFT}; }}
QPushButton#danger[recording="true"] {{
    background: {RED}; color: #2a1010; border: none;
}}

/* "Press a key" button */
QPushButton#keyCap {{
    background: {FIELD};
    border: 1px solid {BORDER};
    border-bottom: 3px solid #1c1414;
    border-radius: 12px;
    font-size: 16px; font-weight: 900;
    padding: 5px 14px;
    min-width: 66px;
}}
QPushButton#keyCap:hover {{ border-color: {ORANGE}; border-bottom-color: {ORANGE_DARK}; }}
QPushButton#keyCap[capturing="true"] {{
    color: {ORANGE}; border: 2px solid {ORANGE}; font-size: 13px;
}}

/* Segments (option switch) */
QPushButton#seg {{
    background: {FIELD};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 7px 12px;
    color: {MUTED};
}}
QPushButton#seg:hover {{ color: {TEXT}; border-color: #6a4f47; }}
QPushButton#seg:checked {{
    background: {ORANGE}; color: #3a1f0e; border-color: {ORANGE};
}}

/* Tabs at the top */
QPushButton#tab {{
    background: transparent; border: none; border-radius: 14px;
    padding: 8px 18px; font-size: 15px; font-weight: 800; color: {MUTED};
}}
QPushButton#tab:hover {{ color: {TEXT}; background: rgba(255,255,255,0.04); }}
QPushButton#tab:checked {{ color: #3a1f0e; background: {ORANGE}; }}
/* RU | EN language switch */
QPushButton#lang {{
    background: transparent; border: 1px solid {BORDER}; border-radius: 9px;
    padding: 4px 9px; font-size: 12px; font-weight: 900; color: {MUTED};
}}
QPushButton#lang:hover {{ color: {TEXT}; border-color: #6a4f47; }}
QPushButton#lang:checked {{ background: {CARD_HI}; color: {ORANGE}; border-color: {ORANGE}; }}
#tabBar {{
    background: {PANEL}; border: 1px solid {BORDER}; border-radius: 18px;
}}

/* ---------- input fields ---------- */
QSpinBox, QDoubleSpinBox, QLineEdit {{
    background: {FIELD};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 6px 10px;
    font-size: 15px; font-weight: 700;
    selection-background-color: {ORANGE}; selection-color: #2a1505;
}}
/* the spin box's inner field: no own padding, otherwise Qt clips the text */
QAbstractSpinBox QLineEdit {{
    padding: 0px 8px; border: none; background: transparent;
}}
QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{ width: 0px; border: none; subcontrol-origin: border; }}
QAbstractSpinBox::up-arrow, QAbstractSpinBox::down-arrow {{ width: 0px; height: 0px; }}
QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus {{ border-color: {ORANGE}; }}
QSpinBox:disabled, QDoubleSpinBox:disabled {{ color: {FAINT}; }}

/* ---------- steps table ---------- */
QTableWidget {{
    background: {FIELD};
    alternate-background-color: #30232300;
    border: 1px solid {BORDER};
    border-radius: 12px;
    gridline-color: transparent;
    selection-background-color: rgba(255,154,60,0.28);
    selection-color: {TEXT};
    font-size: 13px;
    outline: 0;
}}
QTableWidget::item {{ padding: 4px 8px; border-bottom: 1px solid #3a2b2a; }}
QHeaderView::section {{
    background: {FIELD}; color: {FAINT};
    border: none; border-bottom: 1px solid {BORDER};
    padding: 6px 8px; font-size: 12px; font-weight: 800;
}}
QTableCornerButton::section {{ background: {FIELD}; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px 2px; }}
QScrollBar::handle:vertical {{ background: #5a443e; border-radius: 3px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {ORANGE_DARK}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QScrollBar:horizontal {{ height: 0; }}

QMessageBox QLabel {{ font-size: 14px; }}
QInputDialog QLabel {{ font-size: 14px; }}

/* ---------- macro list ---------- */
QComboBox {{
    background: {FIELD};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 6px 12px;
    font-size: 15px; font-weight: 800;
}}
QComboBox:hover {{ border-color: #6a4f47; }}
QComboBox:focus {{ border-color: {ORANGE}; }}
QComboBox:disabled {{ color: {FAINT}; }}
QComboBox::drop-down {{ border: none; width: 26px; }}
QComboBox::down-arrow {{ image: none; width: 0; height: 0; }}   /* ChevronCombo draws the arrow */
QPushButton::menu-indicator {{ image: none; width: 0px; }}
QComboBox QAbstractItemView {{
    background: {CARD_HI}; border: 1px solid {BORDER}; border-radius: 8px;
    selection-background-color: rgba(255,154,60,0.30); selection-color: {TEXT};
    outline: 0; padding: 4px;
}}

/* ---------- "More" menu ---------- */
QMenu {{
    background: {CARD_HI}; border: 1px solid {BORDER}; border-radius: 10px; padding: 6px;
}}
QMenu::item {{ padding: 7px 18px 7px 14px; border-radius: 7px; font-weight: 700; }}
QMenu::item:selected {{ background: rgba(255,154,60,0.28); }}
QMenu::item:disabled {{ color: {FAINT}; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 5px 8px; }}

/* ---------- volume slider ---------- */
QSlider::groove:horizontal {{ height: 6px; background: {FIELD}; border: 1px solid {BORDER}; border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: {ORANGE}; border-radius: 3px; }}
QSlider::handle:horizontal {{
    background: {ORANGE_SOFT}; border: 2px solid {ORANGE_DARK};
    width: 14px; height: 14px; margin: -6px 0; border-radius: 9px;
}}

/* ---------- settings ---------- */
#soundRow {{ background: {FIELD}; border: 1px solid {BORDER}; border-radius: 12px; }}
#soundName {{ font-size: 14px; font-weight: 800; }}
#soundFile {{ color: {FAINT}; font-size: 12px; }}
QPushButton#small {{ padding: 5px 10px; font-size: 13px; border-radius: 9px; }}
QPushButton#play {{ padding: 5px 0px; font-size: 13px; border-radius: 9px; min-width: 34px; max-width: 34px; }}

/* ---------- the cat's Telegram bot bubble ---------- */
#promo {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #4a3530, stop:1 #3d2f45);
    border: 2px solid {ORANGE}; border-radius: 16px;
}}
#promoText {{ font-size: 14px; font-weight: 800; }}
#promoText a {{ color: {ORANGE_SOFT}; }}
QPushButton#promoClose {{
    background: transparent; border: none; padding: 0px; font-size: 16px; color: {MUTED};
    min-width: 22px; max-width: 22px; min-height: 22px; max-height: 22px;
}}
QPushButton#promoClose:hover {{ color: {TEXT}; }}
"""
