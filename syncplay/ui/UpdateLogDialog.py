from syncplay import changelog, updater
from syncplay.private_build import BUILD
from syncplay.messages import getMessage
from syncplay.ui import theme
from syncplay.ui.SubtitleDialog import applyDialogFlags
from syncplay.vendor.Qt import QtWidgets


class UpdateLogDialog(QtWidgets.QDialog):
    """What changed in each build, plus recent update activity (updates installed, updates undone)."""

    def __init__(self, parent=None, newerThan=None):
        super().__init__(parent)
        self.setWindowTitle(getMessage("update-log-title"))
        applyDialogFlags(self)
        self.resize(560, 560)
        layout = QtWidgets.QVBoxLayout(self)
        self.view = QtWidgets.QTextBrowser()
        self.view.setOpenExternalLinks(False)
        layout.addWidget(self.view)
        buttons = QtWidgets.QHBoxLayout()
        buttons.addStretch(1)
        close = QtWidgets.QPushButton(getMessage("update-log-close"))
        close.clicked.connect(self.close)
        buttons.addWidget(close)
        layout.addLayout(buttons)
        self.refresh(newerThan)

    def refresh(self, newerThan=None):
        dark = theme.isDarkPalette(self.palette())
        self.view.setHtml(changelog.render(changelog.load(), BUILD, updater.history(updater.appFolder()), newerThan, dark))
