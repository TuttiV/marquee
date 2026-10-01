"""Colour tokens and the application stylesheet for the main window (light and dark)."""

# Flat neutral greys with one restrained blue accent (taken from the logo's own blues): a modern take on Syncplay's classic two-pane window.
# bg (window) < panel/surface (chat, tables, cards) < surface2 (controls, hovered rows); header = table header strips.
# Muted text is >= 4.5:1 against panel and surface (WCAG AA).
LIGHT = {
    "bg": "#eceef1", "panel": "#ffffff", "surface": "#ffffff", "surface2": "#e6e8ec", "header": "#f3f4f6", "border": "#d5d8de",
    "text": "#24272d", "muted": "#5d636e", "accent": "#2b62d6", "accentHover": "#2050b8", "accentText": "#ffffff", "link": "#1f5fcf",
    "ready": "#238650", "readyHover": "#1c6e41", "readyText": "#ffffff", "readySoft": "rgba(35, 134, 80, 0.14)",
    "danger": "#d0454c", "selection": "rgba(43, 98, 214, 0.16)", "hover": "rgba(0, 0, 0, 0.045)", "warn": "#a86a00",
}
DARK = {
    "bg": "#1f2024", "panel": "#26272c", "surface": "#26272c", "surface2": "#34363d", "header": "#2a2c31", "border": "#3b3e46",
    "text": "#e3e5e9", "muted": "#9da2ac", "accent": "#3871e0", "accentHover": "#5a91f3", "accentText": "#ffffff", "link": "#6db3ff",
    "ready": "#3fb874", "readyHover": "#55c98a", "readyText": "#06210f", "readySoft": "rgba(63, 184, 116, 0.18)",
    "danger": "#ef6b6b", "selection": "rgba(59, 120, 234, 0.28)", "hover": "rgba(255, 255, 255, 0.05)", "warn": "#e0a040",
}

# Extra looks. Each follows the same rules as DARK/LIGHT: text on bg/panel >= 7:1, muted >= 4.5:1, accentText on accent >= 4.5:1.
# Cinema: a dark theatre (warm black, marquee-bulb gold). Midnight: true-black for OLED screens with a cool cyan accent.
# Sand: a warm paper-like light theme with a terracotta accent.
CINEMA = {
    "bg": "#16110e", "panel": "#1f1915", "surface": "#1f1915", "surface2": "#2d241d", "header": "#241d17", "border": "#3d3228",
    "text": "#f0e7dc", "muted": "#ad9f90", "accent": "#d8a24a", "accentHover": "#e9b765", "accentText": "#1c1306", "link": "#f0bb6a",
    "ready": "#5cbb7d", "readyHover": "#74cc93", "readyText": "#07210f", "readySoft": "rgba(92, 187, 125, 0.18)",
    "danger": "#ec6a5e", "selection": "rgba(216, 162, 74, 0.26)", "hover": "rgba(255, 240, 220, 0.05)", "warn": "#ec8a52",
}
MIDNIGHT = {
    "bg": "#000000", "panel": "#0b0d12", "surface": "#0b0d12", "surface2": "#171b24", "header": "#0f121a", "border": "#232936",
    "text": "#e2e8f4", "muted": "#8f9bb2", "accent": "#26c6e8", "accentHover": "#5bdaf1", "accentText": "#001a20", "link": "#5bdaf1",
    "ready": "#3fd18a", "readyHover": "#62dfa2", "readyText": "#03210f", "readySoft": "rgba(63, 209, 138, 0.18)",
    "danger": "#ff6b81", "selection": "rgba(38, 198, 232, 0.24)", "hover": "rgba(255, 255, 255, 0.06)", "warn": "#f0b34a",
}
SAND = {
    "bg": "#f1eadf", "panel": "#fbf8f2", "surface": "#fbf8f2", "surface2": "#e7dece", "header": "#f6f1e7", "border": "#d6c9b3",
    "text": "#2e2921", "muted": "#675e50", "accent": "#b4541e", "accentHover": "#963f12", "accentText": "#ffffff", "link": "#a24410",
    "ready": "#2f7f49", "readyHover": "#276b3e", "readyText": "#ffffff", "readySoft": "rgba(47, 127, 73, 0.14)",
    "danger": "#c23b3b", "selection": "rgba(180, 84, 30, 0.16)", "hover": "rgba(0, 0, 0, 0.045)", "warn": "#955d00",
}

# name -> (tokens, is it dark). "system" follows Windows (dark or light) and is not listed here.
THEMES = {"dark": (DARK, True), "light": (LIGHT, False), "cinema": (CINEMA, True), "midnight": (MIDNIGHT, True), "sand": (SAND, False)}
THEME_ORDER = ("system", "dark", "light", "cinema", "midnight", "sand")
_chosen = "system"
_configDir = None
_systemPalette = None


def setConfigDir(configDir):
    """Where the choice is remembered (the same folder as the other small settings); loads what was saved there."""
    global _chosen, _configDir
    _configDir = configDir
    try:
        from syncplay import secrets
        saved = secrets.load("theme", configDir) if configDir else None
    except Exception:
        saved = None
    if saved in THEME_ORDER:
        _chosen = saved


def chosenTheme():
    return _chosen


def chooseTheme(name, remember=True):
    """Pick a theme by name (unknown names mean "system"); remembered for the next start."""
    global _chosen
    _chosen = name if name in THEME_ORDER else "system"
    if remember and _configDir:
        try:
            from syncplay import secrets
            secrets.save("theme", _chosen, _configDir)
        except Exception:
            pass
    return _chosen


def _paletteFor(t):
    from syncplay.vendor.Qt import QtGui
    palette = QtGui.QPalette()
    Q = QtGui.QColor
    for role, key in ((QtGui.QPalette.Window, "bg"), (QtGui.QPalette.WindowText, "text"), (QtGui.QPalette.Base, "panel"),
                      (QtGui.QPalette.AlternateBase, "surface2"), (QtGui.QPalette.Text, "text"), (QtGui.QPalette.Button, "surface2"),
                      (QtGui.QPalette.ButtonText, "text"), (QtGui.QPalette.Highlight, "accent"), (QtGui.QPalette.HighlightedText, "accentText"),
                      (QtGui.QPalette.ToolTipBase, "header"), (QtGui.QPalette.ToolTipText, "text"), (QtGui.QPalette.Link, "link"),
                      (QtGui.QPalette.PlaceholderText, "muted")):
        palette.setColor(role, Q(t[key]))
    for role in (QtGui.QPalette.Text, QtGui.QPalette.ButtonText, QtGui.QPalette.WindowText):
        palette.setColor(QtGui.QPalette.Disabled, role, Q(t["muted"]))
    return palette


# Accessible name/avatar colours (each is readable as text on both light and dark surfaces when lightened/darkened)
_USER_COLORS_LIGHT = ("#4f5bd5", "#0f7c8f", "#a23bb8", "#c2410c", "#2f7d32", "#b4306d", "#7a5af8", "#8a6d00")
_USER_COLORS_DARK = ("#8b96ff", "#4fd0e3", "#d78cf0", "#ff9a6b", "#7fd48a", "#ff8fb9", "#b6a1ff", "#e6c65a")


def userColor(name, dark):
    """A stable colour for a person, used for their avatar and their name in chat."""
    palette = _USER_COLORS_DARK if dark else _USER_COLORS_LIGHT
    return palette[sum(ord(c) * (i + 1) for i, c in enumerate(name or "?")) % len(palette)]


def initialOf(name):
    for ch in (name or "").strip():
        if ch.isalnum():
            return ch.upper()
    return "?"


def isDarkPalette(palette):
    """True when the window background is dark (works on every platform, unlike OS dark-mode detection)."""
    return palette.window().color().lightness() < 128


def tokens(dark):
    """The colours of the chosen theme (callers say whether the window is dark; the chosen theme's own darkness wins
    only when it agrees, so stale callers never get light text on a light window)."""
    picked = THEMES.get(_chosen)
    if picked and picked[1] == bool(dark):
        return picked[0]
    return DARK if dark else LIGHT


def styleSheet(dark):
    t = tokens(dark)
    return """
QWidget { font-family: "Segoe UI Variable Text", "Segoe UI", "Inter", "SF Pro Text", "Noto Sans", "Helvetica Neue", sans-serif; font-size: 13px; }
QMainWindow, QDialog { background: %(bg)s; }
QMainWindow > QWidget#mainFrame { background: %(bg)s; }
QToolTip { background: %(header)s; color: %(text)s; border: 1px solid %(border)s; padding: 4px 6px; }

QMenuBar { background: %(bg)s; color: %(text)s; padding: 1px 4px; }
QMenuBar::item { padding: 4px 9px; border-radius: 3px; background: transparent; }
QMenuBar::item:selected { background: %(selection)s; }
QMenu { background: %(panel)s; color: %(text)s; border: 1px solid %(border)s; border-radius: 4px; padding: 4px; }
QMenu::item { padding: 5px 24px 5px 10px; border-radius: 3px; }
QMenu::item:selected { background: %(accent)s; color: %(accentText)s; }
QMenu::separator { height: 1px; background: %(border)s; margin: 4px 6px; }

QLabel { color: %(text)s; }
QLabel#fileLine { color: %(muted)s; font-size: 12px; font-weight: 600; }
QPushButton#roomLink { background: transparent; border: none; color: %(muted)s; text-align: left; padding: 4px 2px; font-size: 12px; }
QPushButton#roomLink:hover { color: %(text)s; }
QGroupBox[collapsed="true"] { background: transparent; border: none; padding: 0; }
QPushButton[tone="blue"] { background: %(accent)s; color: %(accentText)s; font-weight: 700; border: none; border-radius: 6px; min-height: 30px; }
QPushButton[tone="blue"]:hover { background: %(accentHover)s; }
QLabel#sectionLabel { color: %(muted)s; font-size: 11px; font-weight: 700; }

QTextBrowser, QTreeView, QListWidget {
    background: %(surface)s; color: %(text)s; border: 1px solid %(border)s; border-radius: 8px; padding: 4px;
    selection-background-color: %(selection)s; selection-color: %(text)s;
}
QTreeView::item { padding: 3px 2px; border-radius: 3px; }
QTreeView::item:hover { background: %(hover)s; }
QTreeView::item:selected { background: %(selection)s; color: %(text)s; }
QListWidget::item { padding: 4px 6px; border-radius: 3px; }
QListWidget::item:hover { background: %(hover)s; }
QListWidget::item:selected { background: %(selection)s; color: %(text)s; }
QHeaderView { background: %(header)s; border: none; }
QHeaderView::section { background: %(header)s; color: %(muted)s; border: none; border-bottom: 1px solid %(border)s;
    padding: 7px 10px; font-size: 11px; font-weight: 600; }
QTreeView#members { padding: 0; }
QTreeView#members::item { padding: 5px 4px; border-bottom: 1px solid %(header)s; border-radius: 0; }
QGroupBox QListWidget { border: 1px dashed %(border)s; background: transparent; }
QLabel#hint { color: %(muted)s; font-size: 12px; }
QLabel#chatTip { color: %(muted)s; }

QLineEdit, QComboBox, QSpinBox {
    background: %(surface2)s; color: %(text)s; border: 1px solid transparent; border-radius: 6px; padding: 8px 12px;
    selection-background-color: %(accent)s; selection-color: %(accentText)s;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border-color: %(accent)s; }
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView { background: %(panel)s; color: %(text)s; border: 1px solid %(border)s;
    selection-background-color: %(accent)s; selection-color: %(accentText)s; }

QPushButton {
    background: %(surface2)s; color: %(text)s; border: 1px solid transparent; border-radius: 6px; padding: 7px 14px;
}
QPushButton:hover { background: %(border)s; }
QPushButton:pressed { background: %(surface2)s; }
QPushButton:disabled { color: %(muted)s; }
QPushButton#sendButton { background: %(accent)s; color: %(accentText)s; font-weight: 600; }
QPushButton#sendButton:hover { background: %(accentHover)s; }
QPushButton[primary="true"] { background: %(accent)s; color: %(accentText)s; font-size: 14px; font-weight: 700; min-height: 38px; border-radius: 6px; }
QPushButton[primary="true"]:hover { background: %(accentHover)s; }
QLabel[notice="error"] { background: rgba(239, 107, 107, 0.16); color: %(danger)s; border-radius: 6px; padding: 8px 12px; font-weight: 600; }
QLabel[notice="success"] { background: %(readySoft)s; color: %(ready)s; border-radius: 6px; padding: 8px 12px; font-weight: 600; }
QPushButton#chipButton { padding: 3px 10px 3px 8px; border-radius: 5px; font-size: 12px; }

/* The Ready button paints itself (animated); the stylesheet only gives it its size and keeps the app's generic button box off it */
QPushButton#readyButton, QPushButton#readyButton:hover, QPushButton#readyButton:pressed, QPushButton#readyButton:checked, QPushButton#readyButton:disabled {
    min-height: 34px; background: transparent; border: none; padding: 0 16px;
}
QPushButton#autoplayButton { min-height: 28px; font-weight: 600; }
QPushButton#autoplayButton:checked { background: %(selection)s; color: %(link)s; border-color: %(accent)s; }

QGroupBox { background: %(panel)s; border: 1px solid %(border)s; border-radius: 8px; margin-top: 0; padding: 30px 10px 10px 10px; color: %(text)s; font-weight: 600; }
QGroupBox::title { subcontrol-origin: padding; subcontrol-position: top left; left: 12px; top: 8px; padding: 0; color: %(text)s; background: transparent; }

QFrame#statusPill { background: %(surface2)s; border-radius: 9px; }
QStatusBar { background: %(bg)s; color: %(muted)s; }
QStatusBar::item { border: none; }
QLabel#statusText { color: %(muted)s; padding: 0 6px; font-size: 12px; }
QLabel#statusDot { font-size: 12px; padding-left: 8px; }

QFrame#emojiPicker { background: %(panel)s; border: 1px solid %(border)s; border-radius: 8px; }
QFrame#updateBar { background: %(selection)s; border: none; border-radius: 0; }
QFrame#resumeBar { background: %(surface2)s; border: none; border-radius: 0; }
QToolButton#moreButton { background: transparent; border: none; border-radius: 6px; padding: 4px 6px; }
QToolButton#moreButton:hover { background: %(surface2)s; }
QToolButton#moreButton::menu-indicator { image: none; width: 0; }
QLabel#resumeText { color: %(text)s; font-weight: 600; }
QLabel#statusText[kind="warn"] { color: %(warn)s; }
QLabel#statusText[kind="ok"] { color: %(muted)s; }
QFrame#banner { background: rgba(224, 160, 64, 0.16); border: none; border-radius: 0; }
QLabel#bannerText { color: %(warn)s; font-weight: 600; }
QProgressBar { background: %(surface2)s; border: none; border-radius: 4px; min-height: 8px; max-height: 8px; text-align: center; color: transparent; }
QProgressBar::chunk { background: %(accent)s; border-radius: 4px; }
QProgressDialog QLabel { color: %(text)s; }
QMessageBox QLabel { color: %(text)s; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: %(border)s; border-radius: 4px; min-height: 28px; }
QScrollBar::handle:vertical:hover { background: %(muted)s; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: %(border)s; border-radius: 4px; min-width: 28px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QSplitter::handle { background: transparent; }
""" % t


def checkboxStyleSheet(dark, checkImagePath):
    """Boxed checkboxes (also used for the playlist group's toggle) with a crisp check mark."""
    t = tokens(dark)
    return """
QGroupBox::indicator, QCheckBox::indicator { width: 15px; height: 15px; border: 1px solid %(border)s; border-radius: 3px; background: %(surface2)s; }
QRadioButton::indicator { width: 14px; height: 14px; border: 1px solid %(border)s; border-radius: 8px; background: %(surface2)s; }
QRadioButton::indicator:hover { border-color: %(accent)s; }
QRadioButton::indicator:checked { background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5, stop:0 %(accentText)s, stop:0.38 %(accentText)s, stop:0.42 %(accent)s, stop:1 %(accent)s); border-color: %(accent)s; }
QGroupBox::indicator:hover, QCheckBox::indicator:hover { border-color: %(accent)s; }
QGroupBox::indicator:checked, QCheckBox::indicator:checked { background: %(accent)s; border-color: %(accent)s; image: url("%(check)s"); }
""" % dict(t, check=checkImagePath.replace("\\", "/"))


class _MessageBoxIcons(object):
    """Gives every message box the same line icons as the rest of the app (instead of the system's coloured pictures)."""
    _filter = None

    @classmethod
    def install(cls, app):
        from syncplay.vendor.Qt import QtCore, QtWidgets

        class Filter(QtCore.QObject):
            def eventFilter(self, obj, event):
                if event.type() == QtCore.QEvent.Show and isinstance(obj, QtWidgets.QMessageBox) and not obj.property("themedIcon"):
                    obj.setProperty("themedIcon", True)
                    cls.apply(obj)
                return False
        cls._filter = Filter(app)
        app.installEventFilter(cls._filter)

    @staticmethod
    def apply(box):
        from syncplay.ui import icons
        from syncplay.vendor.Qt import QtWidgets
        kinds = {QtWidgets.QMessageBox.Warning: ("alert", "warn"), QtWidgets.QMessageBox.Critical: ("alert", "danger"),
                 QtWidgets.QMessageBox.Information: ("info", "accent"), QtWidgets.QMessageBox.Question: ("help", "accent")}
        picked = kinds.get(box.icon())
        if picked:
            box.setIconPixmap(icons.pixmap(picked[0], tokens(isDarkPalette(box.palette()))[picked[1]], 36))


def applyApplicationTheme(app):
    """Fusion style + the shared stylesheet on the whole application, so every window and dialog matches.

    Returns True when the theme is dark."""
    import os
    import tempfile
    from syncplay.ui import icons
    try:
        app.setStyle("Fusion")  # Same widget rendering on every OS, so the stylesheet looks identical
    except Exception:
        pass
    global _systemPalette
    if _systemPalette is None:
        _systemPalette = app.palette()  # Whatever Windows (or the start-up code) gave us: what "System" means
    picked = THEMES.get(_chosen)
    try:
        app.setPalette(_paletteFor(picked[0]) if picked else _systemPalette)
    except Exception:
        pass
    dark = isDarkPalette(app.palette())
    extra = ""
    try:  # The check mark lives in a small cached .svg because stylesheets reference images by path
        cacheDir = os.path.join(tempfile.gettempdir(), "syncplay-theme")
        os.makedirs(cacheDir, exist_ok=True)
        checkPath = os.path.join(cacheDir, "check-{}.svg".format(_chosen if picked else ("dark" if dark else "light")))
        icons.writeSvg("check", tokens(dark)["accentText"], checkPath)
        extra = checkboxStyleSheet(dark, checkPath)
    except OSError:
        pass
    app.setStyleSheet(styleSheet(dark) + extra)
    if _MessageBoxIcons._filter is None:
        try:
            _MessageBoxIcons.install(app)
        except Exception:
            pass
    try:  # One multi-size icon for every window (taskbar, Alt+Tab, dialogs)
        from syncplay.utils import resourcespath
        from syncplay.vendor.Qt import QtGui
        appIcon = QtGui.QIcon()
        for name in ("icon.ico", "syncplay.png"):
            appIcon.addFile(os.path.join(resourcespath, name))
        app.setWindowIcon(appIcon)
    except Exception:
        pass
    return dark
