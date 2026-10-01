from syncplay import constants, torbox
from syncplay.messages import getMessage
from syncplay.ui import theme
from syncplay.ui.SubtitleDialog import applyDialogFlags, dialogStyleSheet, _setKind
from syncplay.utils import formatSize
from syncplay.vendor.Qt import QtCore, QtGui, QtWidgets
from syncplay.vendor.Qt.QtCore import Qt

TORBOX_SETTINGS_URL = "https://torbox.app/settings"
MB = 1024 * 1024
SIZE_STEPS = (100 * MB, 500 * MB, 1024 * MB, 2048 * MB, 5120 * MB, 10240 * MB, 20480 * MB, 51200 * MB)
RESOLUTIONS = ("2160p", "1080p", "720p", "480p")
CODECS = ("AV1", "HEVC", "H.264", "VP9", "XviD")
LANGUAGES = ("English", "German", "French", "Spanish", "Italian", "Japanese", "Swedish", "Multi")
FILE_ROLE = Qt.UserRole + 1


class TorBoxDialog(QtWidgets.QDialog):
    """Browse and search the user's own TorBox library and play a file for themselves or the room."""

    def __init__(self, client, parent=None):
        super().__init__(parent)
        self._client = client
        self._items = []
        self._requestId = 0
        self._showSetup = False
        self.setWindowTitle(getMessage("torbox-dialog-title"))
        self.setMinimumSize(760, 560)
        self.setStyleSheet(dialogStyleSheet(theme.isDarkPalette(QtWidgets.QApplication.palette())))
        applyDialogFlags(self)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)
        title = QtWidgets.QLabel(getMessage("torbox-dialog-title"))
        title.setObjectName("title")
        root.addWidget(title)
        self._setupCard = self._buildSetupCard()
        root.addWidget(self._setupCard)
        self._libraryCard = self._buildLibraryCard()
        root.addWidget(self._libraryCard, 100)
        root.addStretch(1)
        root.addLayout(self._buildFooter())
        self.refresh()

    # --- construction -------------------------------------------------------------------------------------------

    def _buildSetupCard(self):
        card = QtWidgets.QFrame()
        card.setObjectName("card")
        layout = QtWidgets.QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)
        heading = QtWidgets.QLabel(getMessage("torbox-setup-title"))
        heading.setObjectName("title")
        explain = QtWidgets.QLabel(getMessage("torbox-setup-explanation"))
        explain.setObjectName("hint")
        explain.setWordWrap(True)
        self._keyEdit = QtWidgets.QLineEdit()
        self._keyEdit.setPlaceholderText(getMessage("torbox-key-placeholder"))
        self._keyEdit.setEchoMode(QtWidgets.QLineEdit.Password)
        self._keyEdit.returnPressed.connect(self._saveKey)
        openButton = QtWidgets.QPushButton(getMessage("torbox-get-key-button"))
        openButton.clicked.connect(lambda: QtGui.QDesktopServices.openUrl(QtCore.QUrl(TORBOX_SETTINGS_URL)))
        self._backButton = QtWidgets.QPushButton(getMessage("torbox-back-button"))
        self._backButton.clicked.connect(self._closeSetup)
        self._forgetButton = QtWidgets.QPushButton(getMessage("torbox-forget-button"))
        self._forgetButton.clicked.connect(self._forgetKey)
        saveButton = QtWidgets.QPushButton(getMessage("torbox-save-button"))
        saveButton.setObjectName("primary")
        saveButton.clicked.connect(self._saveKey)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(openButton)
        row.addWidget(self._forgetButton)
        row.addStretch(1)
        row.addWidget(self._backButton)
        row.addWidget(saveButton)
        for widget in (heading, explain, self._keyEdit):
            layout.addWidget(widget)
        layout.addLayout(row)
        return card

    def _combo(self, label, options, layout, column):
        box = QtWidgets.QVBoxLayout()
        caption = QtWidgets.QLabel(getMessage(label))
        caption.setObjectName("hint")
        combo = QtWidgets.QComboBox()
        combo.addItem(getMessage("torbox-filter-any"), None)
        for text, data in options:
            combo.addItem(text, data)
        combo.currentIndexChanged.connect(self._applyFilters)
        box.addWidget(caption)
        box.addWidget(combo)
        layout.addLayout(box, 0, column)
        return combo

    def _buildLibraryCard(self):
        card = QtWidgets.QFrame()
        card.setObjectName("card")
        layout = QtWidgets.QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 8)
        layout.setSpacing(8)

        bar = QtWidgets.QHBoxLayout()
        self._searchEdit = QtWidgets.QLineEdit()
        self._searchEdit.setPlaceholderText(getMessage("torbox-search-placeholder"))
        self._searchEdit.setClearButtonEnabled(True)
        self._searchEdit.textChanged.connect(self._applyFilters)
        refreshButton = QtWidgets.QPushButton(getMessage("torbox-refresh-button"))
        refreshButton.clicked.connect(self.loadLibrary)
        keyButton = QtWidgets.QPushButton(getMessage("torbox-key-button"))
        keyButton.clicked.connect(self._openSetup)
        bar.addWidget(self._searchEdit, 1)
        bar.addWidget(refreshButton)
        bar.addWidget(keyButton)
        layout.addLayout(bar)

        filters = QtWidgets.QGridLayout()
        filters.setHorizontalSpacing(8)
        self._resolution = self._combo("torbox-filter-resolution", [(r, r) for r in RESOLUTIONS], filters, 0)
        self._codec = self._combo("torbox-filter-codec", [(c, c) for c in CODECS], filters, 1)
        self._hdr = self._combo("torbox-filter-hdr", [("HDR / Dolby Vision", True), ("SDR", False)], filters, 2)
        self._language = self._combo("torbox-filter-language", [(l, l) for l in LANGUAGES], filters, 3)
        sizes = [(formatSize(s), s) for s in SIZE_STEPS]
        self._minSize = self._combo("torbox-filter-minsize", sizes, filters, 4)
        self._maxSize = self._combo("torbox-filter-maxsize", sizes, filters, 5)
        layout.addLayout(filters)

        self._busy = QtWidgets.QProgressBar()
        self._busy.setRange(0, 0)
        self._busy.setTextVisible(False)
        self._busy.hide()
        layout.addWidget(self._busy)

        self._tree = QtWidgets.QTreeWidget()
        self._tree.setColumnCount(3)
        self._tree.setHeaderLabels(["", "Size", "Tags"])
        self._tree.setRootIsDecorated(True)
        self._tree.setAlternatingRowColors(False)
        self._tree.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        header = self._tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        self._tree.itemSelectionChanged.connect(self._updateButtons)
        self._tree.itemDoubleClicked.connect(lambda *_: self.playSelected(forRoom=False))
        self._tree.hide()
        layout.addWidget(self._tree, 1)

        self._empty = QtWidgets.QLabel(getMessage("torbox-empty"))
        self._empty.setObjectName("hint")
        self._empty.setAlignment(Qt.AlignCenter)
        self._empty.setWordWrap(True)
        layout.addWidget(self._empty)
        return card

    def _buildFooter(self):
        layout = QtWidgets.QVBoxLayout()
        layout.setSpacing(8)
        self._status = QtWidgets.QLabel()
        self._status.setObjectName("status")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)
        row = QtWidgets.QHBoxLayout()
        self._roomButton = QtWidgets.QPushButton(getMessage("torbox-room-button"))
        self._roomButton.setToolTip(getMessage("torbox-share-tooltip"))
        self._roomButton.clicked.connect(lambda: self.playSelected(forRoom=True))
        self._playButton = QtWidgets.QPushButton(getMessage("torbox-play-button"))
        self._playButton.setObjectName("primary")
        self._playButton.clicked.connect(lambda: self.playSelected(forRoom=False))
        closeButton = QtWidgets.QPushButton(getMessage("subtitle-dialog-close-button"))
        closeButton.clicked.connect(self.close)
        row.addStretch(1)
        row.addWidget(closeButton)
        row.addWidget(self._roomButton)
        row.addWidget(self._playButton)
        layout.addLayout(row)
        return layout

    # --- state --------------------------------------------------------------------------------------------------

    def refresh(self):
        configured = self._client.hasTorBoxKey()
        showSetup = self._showSetup or not configured
        self._setupCard.setVisible(showSetup)
        self._backButton.setVisible(configured)
        self._forgetButton.setVisible(configured)
        self._libraryCard.setVisible(not showSetup)
        self._playButton.setVisible(not showSetup)
        self._roomButton.setVisible(not showSetup)
        if not showSetup and not self._items:
            self.loadLibrary()
        self._updateButtons()

    def _setStatus(self, text="", kind=None):
        self._status.setText(text)
        _setKind(self._status, kind or "")

    def _setBusy(self, busy):
        self._busy.setVisible(busy)
        self._tree.setEnabled(not busy)
        self._updateButtons(busy)

    def _selectedFile(self):
        for treeItem in self._tree.selectedItems():
            data = treeItem.data(0, FILE_ROLE)
            if data is not None:
                return data
        return None

    def _updateButtons(self, busy=False):
        enabled = not busy and self._selectedFile() is not None
        self._playButton.setEnabled(enabled)
        self._roomButton.setEnabled(enabled)

    # --- actions ------------------------------------------------------------------------------------------------

    def _openSetup(self):
        self._showSetup = True
        self.refresh()

    def _closeSetup(self):
        self._showSetup = False
        self._setStatus("")
        self.refresh()

    def _saveKey(self):
        key = self._keyEdit.text().strip()
        if not key:
            return
        try:
            self._client.saveTorBoxKey(key)
        except OSError as e:
            self._setStatus(str(e), "error")  # Never fail silently: the app has no console to show errors in
            return
        self._keyEdit.clear()
        self._showSetup = False
        self._items = []
        self.refresh()
        self._setStatus(getMessage("torbox-key-saved"), "success")

    def _forgetKey(self):
        try:
            self._client.saveTorBoxKey("")
        except OSError as e:
            self._setStatus(str(e), "error")
            return
        self._items = []
        self._showSetup = False
        self._tree.clear()
        self._setStatus("")
        self.refresh()

    def loadLibrary(self):
        self._requestId += 1
        requestId = self._requestId
        self._setStatus(getMessage("torbox-loading"))
        self._setBusy(True)
        d = self._client.torboxLibrary()
        d.addCallbacks(lambda items: self._libraryLoaded(requestId, items), lambda f: self._failed(requestId, f))

    def _libraryLoaded(self, requestId, items):
        if requestId != self._requestId:
            return
        self._items = items
        self._setBusy(False)
        self._applyFilters()

    def _currentFilters(self):
        return torbox.LibraryFilters(
            query=self._searchEdit.text(), resolution=self._resolution.currentData(), codec=self._codec.currentData(),
            hdr=self._hdr.currentData(), language=self._language.currentData(),
            minSize=self._minSize.currentData(), maxSize=self._maxSize.currentData())

    def _applyFilters(self, *_):
        filters = self._currentFilters()
        groups = torbox.filterLibrary(self._items, filters)
        self._tree.clear()
        total = 0
        for item, files in groups:
            parent = QtWidgets.QTreeWidgetItem([item.name, "", ""])
            font = parent.font(0)
            font.setBold(True)
            parent.setFont(0, font)
            parent.setFirstColumnSpanned(True)
            self._tree.addTopLevelItem(parent)
            for file_ in files:
                quality = torbox.parseQuality(file_.name)
                tags = " · ".join(filter(None, [quality["resolution"], quality["codec"], "HDR" if quality["hdr"] else None]))
                row = QtWidgets.QTreeWidgetItem([file_.shortName, formatSize(file_.size), tags])
                row.setData(0, FILE_ROLE, (item, file_))
                row.setToolTip(0, file_.name)
                row.setTextAlignment(1, Qt.AlignRight | Qt.AlignVCenter)
                parent.addChild(row)
                total += 1
            parent.setExpanded(True)
        hasLibrary = bool(self._items)
        self._tree.setVisible(bool(groups))
        self._empty.setVisible(not groups)
        self._empty.setText(getMessage("torbox-no-match" if hasLibrary else "torbox-empty"))
        if groups:
            self._setStatus(getMessage("torbox-found").format(total))
            firstFile = self._tree.topLevelItem(0).child(0)
            self._tree.setCurrentItem(firstFile)
        elif hasLibrary:
            self._setStatus("")
        self._updateButtons()

    def playSelected(self, forRoom=False):
        selected = self._selectedFile()
        if selected is None:
            return
        item, file_ = selected
        self._requestId += 1
        requestId = self._requestId
        self._setStatus(getMessage("torbox-fetching-link").format(file_.shortName))
        self._setBusy(True)
        d = self._client.openTorBoxFile(item, file_, forRoom=forRoom)
        d.addCallbacks(lambda name: self._played(requestId, name, forRoom), lambda f: self._failed(requestId, f))

    def _played(self, requestId, name, forRoom):
        if requestId != self._requestId:
            return
        self._setBusy(False)
        self._setStatus(getMessage("torbox-playing-room" if forRoom else "torbox-playing").format(name), "success")

    def _failed(self, requestId, failure):
        if requestId != self._requestId:
            return
        self._setBusy(False)
        if failure.check(torbox.TorBoxError):
            self._setStatus(str(failure.value), "error")
        else:
            self._setStatus(getMessage("torbox-no-key-error") if not self._client.hasTorBoxKey() else "TorBox request failed", "error")

    def closeEvent(self, event):
        self._requestId += 1  # Also covers closing a window that was never shown
        super().closeEvent(event)

    def hideEvent(self, event):
        self._requestId += 1  # Ignore anything still in flight, however the window was closed (X, Close, Esc)
        super().hideEvent(event)
