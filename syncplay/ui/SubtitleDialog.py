from syncplay import constants, opensubtitles
from syncplay.messages import getMessage
from syncplay.ui import theme
from syncplay.vendor.Qt import QtCore, QtGui, QtWidgets
from syncplay.vendor.Qt.QtCore import Qt

def dialogStyleSheet(dark):
    t = theme.tokens(dark)
    return """
QDialog { background: %(bg)s; }
QLabel { color: %(text)s; }
QFrame#card { background: %(surface)s; border: 1px solid %(border)s; border-radius: 10px; }
QLabel#title { font-size: 17px; font-weight: 600; }
QLabel#fileName { font-size: 12px; color: %(muted)s; }
QLabel#hint { color: %(muted)s; }
QLabel#status { padding: 2px 0; }
QLabel#status[kind="error"] { color: %(danger)s; }
QLabel#status[kind="success"] { color: %(ready)s; }
QLabel#pill { border-radius: 9px; padding: 2px 10px; font-size: 11px; background: %(surface2)s;
    border: 1px solid %(border)s; color: %(text)s; }
QLabel#pill[kind="room"] { background: %(readySoft)s; border-color: %(ready)s; }
QLabel#pill[kind="solo"] { background: rgba(214, 140, 45, 0.18); border-color: rgba(214, 140, 45, 0.7); }
QLineEdit, QComboBox { padding: 6px 8px; border-radius: 6px; border: 1px solid %(border)s; background: %(surface)s;
    color: %(text)s; selection-background-color: %(accent)s; selection-color: %(accentText)s; }
QLineEdit:focus, QComboBox:focus { border-color: %(accent)s; }
QComboBox QAbstractItemView { background: %(surface)s; color: %(text)s; border: 1px solid %(border)s;
    selection-background-color: %(selection)s; selection-color: %(text)s; }
QCheckBox { color: %(text)s; }
QCheckBox:disabled { color: %(muted)s; }
QPushButton { padding: 6px 16px; border-radius: 6px; border: 1px solid %(border)s; background: %(surface2)s; color: %(text)s; }
QPushButton:hover { border-color: %(accent)s; }
QPushButton:disabled { color: %(muted)s; background: %(surface)s; }
QPushButton#primary { background: %(ready)s; color: %(readyText)s; border-color: %(ready)s; font-weight: 600; }
QPushButton#primary:hover { background: %(readyHover)s; border-color: %(readyHover)s; }
QPushButton#primary:disabled { background: %(surface2)s; color: %(muted)s; border-color: %(border)s; }
QTableWidget, QTreeWidget { border: none; background: transparent; color: %(text)s; gridline-color: transparent;
    alternate-background-color: %(surface2)s; selection-background-color: %(selection)s; selection-color: %(text)s; }
QTableWidget::item, QTreeWidget::item { padding: 6px 8px; border: none; }
QTableWidget::item:selected, QTreeWidget::item:selected { background: %(selection)s; color: %(text)s; }
QHeaderView::section { background: transparent; border: none; border-bottom: 1px solid %(border)s; padding: 6px 8px;
    font-weight: 600; color: %(muted)s; }
QProgressBar { border: none; background: %(border)s; max-height: 3px; border-radius: 1px; }
QProgressBar::chunk { background: %(accent)s; border-radius: 1px; }
""" % t


EXACT_MATCH_COLOR = QtGui.QColor(46, 158, 91)


def applyDialogFlags(dialog):
    """Explicit window flags, as Syncplay's own dialogs use on Windows. Deriving them with
    `windowFlags() & ~Qt.WindowContextHelpButtonHint` drops the close-button hint under PySide6, greying out the X."""
    dialog.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowSystemMenuHint | Qt.WindowCloseButtonHint
                          | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint | Qt.CustomizeWindowHint)


def _setKind(widget, kind):
    widget.setProperty("kind", kind)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class SubtitleDialog(QtWidgets.QDialog):
    """Search OpenSubtitles for the file being played, and load the chosen subtitle for the room."""

    COLUMNS = ("", "release", "language", "downloads", "tags")

    def __init__(self, client, parent=None):
        super().__init__(parent)
        self._client = client
        self._results = []
        self._requestId = 0
        self._showSetup = False
        self.setWindowTitle(getMessage("subtitle-dialog-title"))
        self.setMinimumSize(620, 520)
        self.setStyleSheet(dialogStyleSheet(theme.isDarkPalette(QtWidgets.QApplication.palette())))
        applyDialogFlags(self)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        root.addLayout(self._buildHeader())
        self._setupCard = self._buildSetupCard()
        root.addWidget(self._setupCard)
        self._searchCard = self._buildSearchCard()
        root.addWidget(self._searchCard, 100)
        root.addStretch(1)  # Only takes space while the search card is hidden (setup screen)
        root.addLayout(self._buildFooter())

        self.refresh()

    # --- construction -------------------------------------------------------------------------------------------

    def _buildHeader(self):
        layout = QtWidgets.QVBoxLayout()
        layout.setSpacing(2)
        row = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel(getMessage("subtitle-dialog-title"))
        title.setObjectName("title")
        self._pill = QtWidgets.QLabel()
        self._pill.setObjectName("pill")
        self._pill.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Fixed)
        row.addWidget(title)
        row.addStretch(1)
        row.addWidget(self._pill)
        self._fileLabel = QtWidgets.QLabel()
        self._fileLabel.setObjectName("fileName")
        layout.addLayout(row)
        layout.addWidget(self._fileLabel)
        return layout

    def _buildSetupCard(self):
        card = QtWidgets.QFrame()
        card.setObjectName("card")
        layout = QtWidgets.QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)
        heading = QtWidgets.QLabel(getMessage("subtitle-dialog-setup-title"))
        heading.setObjectName("title")
        explain = QtWidgets.QLabel(getMessage("subtitle-dialog-setup-explanation"))
        explain.setObjectName("hint")
        explain.setWordWrap(True)
        self._keyEdit = QtWidgets.QLineEdit()
        self._keyEdit.setPlaceholderText(getMessage("subtitle-dialog-api-key-placeholder"))
        self._userEdit = QtWidgets.QLineEdit()
        self._userEdit.setPlaceholderText(getMessage("subtitle-dialog-username-placeholder"))
        self._passEdit = QtWidgets.QLineEdit()
        self._passEdit.setPlaceholderText(getMessage("subtitle-dialog-password-placeholder"))
        self._passEdit.setEchoMode(QtWidgets.QLineEdit.Password)
        self._saveButton = QtWidgets.QPushButton(getMessage("subtitle-dialog-save-button"))
        self._saveButton.setObjectName("primary")
        self._saveButton.clicked.connect(self._saveSettings)
        backButton = QtWidgets.QPushButton(getMessage("subtitle-dialog-back-button"))
        backButton.clicked.connect(self._closeSettings)
        self._keyEdit.returnPressed.connect(self._saveSettings)
        self._accountStatus = QtWidgets.QLabel()
        self._accountStatus.setObjectName("hint")
        self._accountStatus.setWordWrap(True)
        self._forgetButton = QtWidgets.QPushButton(getMessage("subtitle-dialog-forget-button"))
        self._forgetButton.clicked.connect(self._forgetSettings)
        buttonRow = QtWidgets.QHBoxLayout()
        buttonRow.addStretch(1)
        buttonRow.addWidget(self._saveButton)
        getKeyButton = QtWidgets.QPushButton(getMessage("subtitle-dialog-get-key-button"))
        getKeyButton.clicked.connect(lambda: QtGui.QDesktopServices.openUrl(QtCore.QUrl(constants.OPENSUBTITLES_CONSUMERS_URL)))
        buttonRow.insertWidget(0, getKeyButton)
        buttonRow.insertWidget(1, self._forgetButton)
        buttonRow.insertWidget(2, backButton)
        for widget in (heading, explain, self._accountStatus, self._keyEdit, self._userEdit, self._passEdit):
            layout.addWidget(widget)
        layout.addLayout(buttonRow)
        return card

    def _buildSearchCard(self):
        card = QtWidgets.QFrame()
        card.setObjectName("card")
        layout = QtWidgets.QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 8)
        layout.setSpacing(8)

        bar = QtWidgets.QHBoxLayout()
        self._languageEdit = QtWidgets.QLineEdit()
        self._languageEdit.setPlaceholderText(getMessage("subtitle-dialog-language-placeholder"))
        self._languageEdit.setToolTip(getMessage("subtitle-dialog-language-tooltip"))
        self._languageEdit.setMaximumWidth(150)
        self._languageEdit.returnPressed.connect(self.search)
        self._searchButton = QtWidgets.QPushButton(getMessage("subtitle-dialog-search-button"))
        self._searchButton.clicked.connect(self.search)
        self._settingsButton = QtWidgets.QPushButton(getMessage("subtitle-dialog-settings-button"))
        self._settingsButton.setToolTip(getMessage("subtitle-dialog-settings-tooltip"))
        self._settingsButton.clicked.connect(self._openSettings)
        bar.addWidget(QtWidgets.QLabel(getMessage("subtitle-dialog-language-label")))
        bar.addWidget(self._languageEdit)
        bar.addStretch(1)
        bar.addWidget(self._settingsButton)
        bar.addWidget(self._searchButton)
        layout.addLayout(bar)
        self._autoCheck = QtWidgets.QCheckBox(getMessage("subtitle-dialog-auto-label"))
        self._autoCheck.setToolTip(getMessage("subtitle-dialog-auto-tooltip"))
        self._autoCheck.setChecked(self._client.autoSubtitlesEnabled())
        self._autoCheck.toggled.connect(self._client.setAutoSubtitles)
        layout.addWidget(self._autoCheck)
        self._providerHint = QtWidgets.QLabel(getMessage("subtitle-dialog-public-hint"))
        self._providerHint.setObjectName("hint")
        self._providerHint.setWordWrap(True)
        layout.addWidget(self._providerHint)

        self._busy = QtWidgets.QProgressBar()
        self._busy.setRange(0, 0)
        self._busy.setTextVisible(False)
        self._busy.hide()
        layout.addWidget(self._busy)

        self._table = QtWidgets.QTableWidget(0, len(self.COLUMNS))
        self._table.setHorizontalHeaderLabels([
            "", getMessage("subtitle-dialog-column-release"), getMessage("subtitle-dialog-column-language"),
            getMessage("subtitle-dialog-column-downloads"), ""])
        self._table.verticalHeader().hide()
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self._table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self._table.setFocusPolicy(Qt.StrongFocus)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeToContents)
        header.setHighlightSections(False)
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._table.horizontalHeaderItem(3).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._table.hide()  # Shown once there are results
        self._table.itemSelectionChanged.connect(self._updateButtons)
        self._table.itemDoubleClicked.connect(lambda _item: self.useSelected())
        layout.addWidget(self._table, 1)

        self._empty = QtWidgets.QLabel(getMessage("subtitle-dialog-empty"))
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
        self._shareCheck = QtWidgets.QCheckBox(getMessage("subtitle-dialog-share-checkbox"))
        self._shareCheck.setChecked(True)
        self._useButton = QtWidgets.QPushButton(getMessage("subtitle-dialog-use-button"))
        self._useButton.setObjectName("primary")
        self._useButton.setDefault(False)
        self._useButton.clicked.connect(self.useSelected)
        closeButton = QtWidgets.QPushButton(getMessage("subtitle-dialog-close-button"))
        closeButton.clicked.connect(self.close)
        row.addWidget(self._shareCheck)
        row.addStretch(1)
        row.addWidget(closeButton)
        row.addWidget(self._useButton)
        layout.addLayout(row)
        return layout

    # --- state --------------------------------------------------------------------------------------------------

    def refresh(self):
        """Re-read client state (current file, sharing support, API key) and search if we can."""
        searching = not self._showSetup
        self._setupCard.setVisible(self._showSetup)
        self._searchCard.setVisible(searching)
        self._pill.setVisible(searching)
        self._shareCheck.setVisible(searching)
        self._useButton.setVisible(searching)
        self._providerHint.setVisible(not self._client.hasOpenSubtitlesKey())
        self._updateAccountStatus()

        file_ = self._client.userlist.currentUser.file
        self._fileLabel.setText(file_["name"] if file_ and file_.get("name") else getMessage("subtitle-dialog-no-file"))
        self._fileLabel.setToolTip(self._fileLabel.text())

        canShare = self._client.canShareSubtitles()
        self._shareCheck.setEnabled(canShare)
        if not canShare:
            self._shareCheck.setChecked(False)
        self._pill.setText(getMessage("subtitle-dialog-pill-room" if canShare else "subtitle-dialog-pill-solo"))
        _setKind(self._pill, "room" if canShare else "solo")

        if searching:
            if not self._languageEdit.text():
                self._languageEdit.setText(self._client.currentSubtitleLanguages().replace(",", ", "))
            if file_ and not self._results:
                self.search()
        self._updateButtons()

    def _setStatus(self, text="", kind=None):
        self._status.setText(text)
        _setKind(self._status, kind or "")

    def _setBusy(self, busy):
        self._busy.setVisible(busy)
        self._searchButton.setEnabled(not busy)
        self._languageEdit.setEnabled(not busy)
        self._table.setEnabled(not busy)
        self._updateButtons(busy)

    def _updateButtons(self, busy=False):
        self._useButton.setEnabled(not busy and bool(self._table.selectedItems()))

    # --- actions ------------------------------------------------------------------------------------------------

    def _saveSettings(self):
        key = self._keyEdit.text().strip() or self._client.savedOpenSubtitlesKey()  # Blank = keep the saved key
        if not key:
            self._setStatus(getMessage("subtitle-dialog-key-required"), "error")
            return
        try:
            self._client.saveOpenSubtitlesSettings(key, self._userEdit.text(), self._passEdit.text())
        except OSError as e:
            self._setStatus(str(e), "error")  # Never fail silently: the app has no console to show errors in
            return
        self._passEdit.clear()
        self._keyEdit.clear()
        self._results = []  # Results from the other provider are stale
        self._showSetup = False
        self.refresh()
        self._setStatus(getMessage("opensubtitles-key-saved"), "success")

    def _forgetSettings(self):
        try:
            self._client.forgetOpenSubtitlesSettings()
        except OSError as e:
            self._setStatus(str(e), "error")
            return
        self._results = []
        self._keyEdit.clear()
        self._userEdit.clear()
        self._passEdit.clear()
        self.refresh()
        self._updateAccountStatus()

    def _updateAccountStatus(self):
        source, tail = self._client.openSubtitlesKeyStatus()
        self._accountStatus.setText(getMessage("opensubtitles-source-" + source).format(tail))
        self._forgetButton.setVisible(source == "own")
        self._keyEdit.setPlaceholderText(getMessage("subtitle-dialog-api-key-saved-placeholder").format(tail) if source == "own"
                                         else getMessage("subtitle-dialog-api-key-placeholder"))

    def _openSettings(self):
        self._showSetup = True
        self.refresh()

    def _closeSettings(self):
        self._showSetup = False
        self._setStatus("")
        self.refresh()

    def search(self):
        languages = ",".join(part for part in self._languageEdit.text().replace(" ", "").split(",") if part) or None
        if languages:
            self._client.saveSubtitleLanguages(languages)  # Next time (and for automatic loading) it's already your language
        self._requestId += 1
        requestId = self._requestId
        self._setStatus(getMessage("subtitle-search-started-notification"))
        self._setBusy(True)
        d = self._client.searchSubtitles(languages)
        d.addCallbacks(lambda results: self._searchFinished(requestId, results),
                       lambda failure: self._requestFailed(requestId, failure))

    def _searchFinished(self, requestId, results):
        if requestId != self._requestId:
            return
        self._setBusy(False)
        self._results = results
        self._fillTable()
        if results:
            self._table.selectRow(0)
            self._setStatus(getMessage("subtitle-dialog-found").format(len(results)))
        else:
            self._setStatus(getMessage("subtitle-search-none-notification"))

    def _requestFailed(self, requestId, failure):
        if requestId != self._requestId:
            return
        self._setBusy(False)
        if failure.check(opensubtitles.OpenSubtitlesError):
            self._setStatus(str(failure.value), "error")
        else:
            self._setStatus(getMessage("subtitle-search-failed-error"), "error")

    def _fillTable(self):
        self._table.setRowCount(0)
        self._empty.setVisible(not self._results)
        self._table.setVisible(bool(self._results))
        for result in self._results:
            row = self._table.rowCount()
            self._table.insertRow(row)
            badge = QtWidgets.QTableWidgetItem("★" if result.hashMatch else "")
            badge.setForeground(QtGui.QBrush(EXACT_MATCH_COLOR))
            badge.setToolTip(getMessage("subtitle-dialog-exact-tooltip") if result.hashMatch else "")
            badge.setTextAlignment(Qt.AlignCenter)
            release = QtWidgets.QTableWidgetItem(result.release or result.fileName or str(result.fileId))
            release.setToolTip(result.fileName or "")
            language = QtWidgets.QTableWidgetItem((result.language or "").upper())
            downloads = QtWidgets.QTableWidgetItem("{:,}".format(result.downloads))
            downloads.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            tags = QtWidgets.QTableWidgetItem("HI" if result.hearingImpaired else "")
            tags.setToolTip(getMessage("subtitle-dialog-hi-tooltip") if result.hearingImpaired else "")
            for column, item in enumerate((badge, release, language, downloads, tags)):
                self._table.setItem(row, column, item)

    def _selectedResult(self):
        rows = self._table.selectionModel().selectedRows()
        if not rows or rows[0].row() >= len(self._results):
            return None
        return self._results[rows[0].row()]

    def useSelected(self):
        result = self._selectedResult()
        if result is None:
            return
        share = self._shareCheck.isChecked() and self._shareCheck.isEnabled()
        self._requestId += 1
        requestId = self._requestId
        self._setStatus(getMessage("subtitle-download-started-notification").format(result.release or result.fileName or result.fileId))
        self._setBusy(True)
        d = self._client.downloadSubtitle(result, share=share)
        d.addCallbacks(lambda name: self._downloadFinished(requestId, name, share),
                       lambda failure: self._requestFailed(requestId, failure))

    def _downloadFinished(self, requestId, name, shared):
        if requestId != self._requestId:
            return
        self._setBusy(False)
        key = "subtitle-dialog-loaded-room" if shared else "subtitle-dialog-loaded-solo"
        self._setStatus(getMessage(key).format(name), "success")

    def closeEvent(self, event):
        self._requestId += 1  # Also covers closing a window that was never shown
        super().closeEvent(event)

    def hideEvent(self, event):
        self._requestId += 1  # Ignore anything still in flight, however the window was closed (X, Close, Esc)
        super().hideEvent(event)
