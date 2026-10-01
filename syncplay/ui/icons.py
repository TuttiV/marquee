"""Crisp, theme-tinted vector icons (drawn from simple SVG strokes) for the modern client look."""
from syncplay.vendor.Qt import QtCore, QtGui

try:
    from syncplay.vendor.Qt import QtSvg
except Exception:  # QtSvg missing: buttons simply show without icons
    QtSvg = None

# 24x24 line icons. Shapes are simple geometric strokes.
_PATHS = {
    "send": '<path d="M22 2 11 13"/><path d="M22 2 15 22l-4-9-9-4z"/>',
    "join": '<path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/><path d="m10 17 5-5-5-5"/><path d="M15 12H3"/>',
    "subtitles": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M7 12h4M13 12h4M7 15.5h6"/>',
    "invite": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M19 8v6M22 11h-6"/>',
    "library": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="m10 9 5 3-5 3z"/>',
    "chat": '<path d="M21 12a8 8 0 0 1-11.6 7.1L3 21l1.9-5.4A8 8 0 1 1 21 12z"/>',
    "alert": '<path d="M12 3l10 18H2z"/><path d="M12 10v5M12 18h.01"/>',
    "skip": '<path d="M5 4l10 8-10 8zM19 5v14"/>',
    "list": '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 16v-4M12 8h.01"/>',
    "power": '<path d="M12 3v9"/><path d="M6.3 6.3a8 8 0 1 0 11.4 0"/>',
    "circle": '<circle cx="12" cy="12" r="9"/>',
    "more": '<circle cx="5" cy="12" r="1.3"/><circle cx="12" cy="12" r="1.3"/><circle cx="19" cy="12" r="1.3"/>',
    "tune": '<path d="M4 7h10M18 7h2M4 17h2M10 17h10"/><circle cx="16" cy="7" r="2"/><circle cx="8" cy="17" r="2"/>',
    "lock": '<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
    "mic": '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "link": '<path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7"/><path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7"/>',
    "edit": '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>',
    "folder": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
    "eye": '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/>',
    "eye-off": '<path d="M3 3l18 18"/><path d="M10.6 6.1A10 10 0 0 1 12 5c6.4 0 10 7 10 7a17 17 0 0 1-3.2 4.1M6.6 6.7A17 17 0 0 0 2 12s3.6 7 10 7a10 10 0 0 0 4.3-1"/>',
    "shield": '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/>',
    "trash": '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/>',
    "shuffle": '<path d="M3 7h3c5 0 7 10 12 10h3M3 17h3c1.5 0 2.7-.8 3.7-2M14 9c1-1.2 2.3-2 4-2h3M18 4l3 3-3 3M18 14l3 3-3 3"/>',
    "undo": '<path d="M9 14L4 9l5-5"/><path d="M4 9h10a6 6 0 0 1 0 12h-3"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "play": '<path d="M7 4l13 8-13 8z"/>',
    "pause": '<path d="M8 5v14M16 5v14"/>',
    "x": '<path d="M6 6l12 12M18 6L6 18"/>',
    "help": '<circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 0 1 5 .5c0 1.7-2.5 2-2.5 3.5M12 17h.01"/>',
    "download": '<path d="M12 4v11M7 11l5 5 5-5M5 20h14"/>',
    "key": '<circle cx="8" cy="15" r="4"/><path d="M11 12l9-9M16 7l3 3"/>',
    "unlock": '<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 7.5-2"/>',
    "chevron": '<path d="M9 6l6 6-6 6"/>',
    "chevrons": '<path d="M7 7l5 5-5 5M13 7l5 5-5 5"/>',
    "door": '<path d="M5 21V4a1 1 0 0 1 1-1h9a1 1 0 0 1 1 1v17M3 21h18M12 12h.01"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "refresh": '<path d="M21 12a9 9 0 1 1-3-6.7"/><path d="M21 4v5h-5"/>',
}
_STAR = '<path d="m12 2 3.1 6.3 6.9 1-5 4.9 1.2 6.8L12 17.8 5.8 21l1.2-6.8-5-4.9 6.9-1z"/>'


def _svg(body, color, filled=False):
    fill = color if filled else "none"
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="{f}" stroke="{c}" stroke-width="2" '
            'stroke-linecap="round" stroke-linejoin="round">{b}</svg>').format(f=fill, c=color, b=body)


def pixmap(name, color, size=18, scale=2.0):
    """A sharp pixmap of the named icon in the given colour (transparent pixmap if icons are unavailable)."""
    pm = QtGui.QPixmap(int(size * scale), int(size * scale))
    pm.fill(QtCore.Qt.transparent)
    if QtSvg is None:
        return pm
    body, filled = (_STAR, True) if name == "star" else (_PATHS[name], False)
    renderer = QtSvg.QSvgRenderer(_svg(body, color, filled).encode("utf-8"))
    painter = QtGui.QPainter(pm)
    renderer.render(painter, QtCore.QRectF(0, 0, pm.width(), pm.height()))
    painter.end()
    pm.setDevicePixelRatio(scale)
    return pm


def icon(name, color, size=18):
    return QtGui.QIcon(pixmap(name, color, size))


def writeSvg(name, color, path):
    """Write an icon as an .svg file (stylesheets can only reference images by file path)."""
    body, filled = (_STAR, True) if name == "star" else (_PATHS[name], False)
    with open(path, "w", encoding="utf-8") as f:
        f.write(_svg(body, color, filled))


# The old Syncplay PNG icons and the line icons that replace them (so menus, tables and playlists share one look)
LEGACY = {
    "film_go": "play", "film_add": "plus", "film_link": "link", "film_edit": "edit", "folder_film": "folder", "film_folder_edit": "folder",
    "folder_explore": "folder", "world_go": "globe", "world_add": "globe", "world_explore": "globe", "yes_eye": "eye", "no_eye": "eye-off",
    "shield_add": "shield", "shield_edit": "shield", "delete": "trash", "arrow_switch": "shuffle", "arrow_undo": "undo", "clock_go": "clock",
    "timeline_marker": "clock", "control_play_blue": "play", "control_pause_blue": "pause", "cross": "x", "tick": "check", "reconnect": "refresh",
    "help": "help", "application_get": "download", "door_in": "join", "door_open_edit": "door", "email_go": "send", "page_white_key": "key",
    "key_go": "key", "lock": "lock", "lock_open": "unlock", "lock_green": "lock", "user_key": "key", "bullet_right_grey": "chevron",
    "chevrons_right": "chevrons", "bullet_edit_centered": "edit", "cog_delete": "trash", "accept": "check",
}


def legacy(stem, color, size=16):
    """A line icon standing in for the old PNG called `stem` (None if there is no replacement)."""
    name = LEGACY.get(stem)
    return icon(name, color, size) if name else None


def badge(name, color, background, size=22, scale=2.0):
    """An icon on a filled circle (used for the tick on the ready button)."""
    pm = QtGui.QPixmap(int(size * scale), int(size * scale))
    pm.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(pm)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    painter.setPen(QtCore.Qt.NoPen)
    painter.setBrush(QtGui.QColor(background))
    painter.drawEllipse(0, 0, pm.width(), pm.height())  # background may be a QColor with alpha
    inner = int(pm.width() * 0.9)
    offset = (pm.width() - inner) // 2
    glyph = pixmap(name, color, size * 0.9, scale)
    painter.drawPixmap(QtCore.QRectF(offset, offset, inner, inner), glyph, QtCore.QRectF(glyph.rect()))  # Device pixels, whatever the ratio
    painter.end()
    pm.setDevicePixelRatio(scale)
    return QtGui.QIcon(pm)
