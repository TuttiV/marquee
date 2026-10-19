"""The install window: where the app lives and which shortcuts it gets. Shown once on the first start of the packaged app
(Windows .exe or the Linux download), and any time from Help > Install and shortcuts."""
import os
import shutil

from syncplay import install
from syncplay.messages import getMessage
from syncplay.utils import resourcespath
from syncplay.vendor.Qt import QtCore, QtGui, QtWidgets
from syncplay.vendor.Qt.QtCore import Qt


class InstallDialog(QtWidgets.QDialog):
    """outcome after closing: "here" (shortcuts set, same folder), "moved" (copied to chosenRoot: start that copy and quit),
    or "skipped" (Not now)."""

    def __init__(self, currentRoot, exePath=None, playerFound=True, parent=None, copier=None, shortcutSetter=None, suggested=None,
                 firstRun=True):
        super().__init__(parent)
        self.firstRun = firstRun
        self.currentRoot = currentRoot
        self.exePath = exePath
        self.chosenRoot = currentRoot
        self.outcome = "skipped"
        self._copier = copier or install.copyInstall
        self._setShortcuts = shortcutSetter or install.setShortcuts
        self.setWindowTitle(getMessage("install-title"))
        self.setWindowIcon(QtGui.QIcon(os.path.join(resourcespath, "syncplay.png")))
        self.setMinimumWidth(520)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 18)
        layout.setSpacing(10)

        header = QtWidgets.QHBoxLayout()
        logo = QtWidgets.QLabel()
        logo.setPixmap(QtGui.QIcon(os.path.join(resourcespath, "syncplay.png")).pixmap(44, 44))
        header.addWidget(logo, 0, Qt.AlignTop)
        titles = QtWidgets.QVBoxLayout()
        title = QtWidgets.QLabel(getMessage("install-title"))
        title.setStyleSheet("font-size: 18px; font-weight: 700;")
        subtitle = QtWidgets.QLabel(getMessage("install-subtitle"))
        subtitle.setObjectName("hint")
        subtitle.setWordWrap(True)
        titles.addWidget(title)
        titles.addWidget(subtitle)
        header.addLayout(titles, 1)
        layout.addLayout(header)
        layout.addSpacing(6)

        layout.addWidget(self._label(getMessage("install-folder-label")))
        row = QtWidgets.QHBoxLayout()
        self.folderEdit = QtWidgets.QLineEdit(suggested or currentRoot or install.targetRoot(install.defaultParent()))
        self.folderEdit.textChanged.connect(self._check)
        self.browseButton = QtWidgets.QPushButton(getMessage("install-browse"))
        self.browseButton.clicked.connect(self.browse)
        row.addWidget(self.folderEdit, 1)
        row.addWidget(self.browseButton)
        layout.addLayout(row)
        # An older .exe doesn't say where it is and doesn't read the chosen folder, so moving needs the new one
        self.canMove = install.LINUX or os.name != "nt" or bool(exePath and os.path.isfile(exePath))
        self.folderHint = QtWidgets.QLabel(getMessage("install-folder-hint" if self.canMove else "install-folder-needs-new-exe"))
        self.folderHint.setObjectName("hint")
        self.folderHint.setWordWrap(True)
        layout.addWidget(self.folderHint)
        if not self.canMove:
            self.folderEdit.setText(currentRoot)
            self.folderEdit.setEnabled(False)
            self.browseButton.setEnabled(False)

        layout.addSpacing(6)
        existing = install.existingShortcuts() if currentRoot else {"menu": False, "desktop": False}
        firstTime = not (existing["menu"] or existing["desktop"])
        self.menuCheck = QtWidgets.QCheckBox(getMessage("install-menu-linux" if install.LINUX else "install-menu-windows"))
        self.menuCheck.setChecked(True if firstTime else existing["menu"])
        self.desktopCheck = QtWidgets.QCheckBox(getMessage("install-desktop"))
        self.desktopCheck.setChecked(False if firstTime else existing["desktop"])
        layout.addWidget(self.menuCheck)
        layout.addWidget(self.desktopCheck)

        self.playerNote = QtWidgets.QLabel(getMessage("install-no-player-linux" if install.LINUX else "install-no-player-windows"))
        self.playerNote.setProperty("notice", "error")
        self.playerNote.setWordWrap(True)
        self.playerNote.setVisible(not playerFound)
        layout.addWidget(self.playerNote)

        self.problem = QtWidgets.QLabel("")
        self.problem.setProperty("notice", "error")
        self.problem.setWordWrap(True)
        self.problem.hide()
        layout.addWidget(self.problem)
        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.hide()
        layout.addWidget(self.progress)

        layout.addSpacing(6)
        buttons = QtWidgets.QHBoxLayout()
        buttons.addStretch(1)
        self.laterButton = QtWidgets.QPushButton(getMessage("install-later"))
        self.laterButton.clicked.connect(self.reject)
        self.installButton = QtWidgets.QPushButton(getMessage("install-button"))
        self.installButton.setProperty("tone", "blue")
        self.installButton.setDefault(True)
        self.installButton.clicked.connect(self.install)
        buttons.addWidget(self.laterButton)
        buttons.addWidget(self.installButton)
        layout.addLayout(buttons)
        self._check()

    @staticmethod
    def _label(text):
        label = QtWidgets.QLabel(text)
        label.setStyleSheet("font-weight: 600;")
        return label

    def target(self):
        return install.targetRoot(self.folderEdit.text())

    def moving(self):
        return not self.currentRoot or os.path.normcase(os.path.abspath(self.target())) != os.path.normcase(os.path.abspath(self.currentRoot))

    def _check(self, *ignored):
        problem = install.checkTarget(self.target(), self.currentRoot) if self.folderEdit.text().strip() else getMessage("install-pick-folder")
        self.problem.setText(problem or "")
        self.problem.setVisible(bool(problem))
        self.installButton.setEnabled(not problem)
        self.installButton.setText(getMessage("install-button" if (self.moving() or self.firstRun) else "install-button-save"))
        return problem

    def browse(self):
        start = os.path.dirname(self.target()) if os.path.isdir(os.path.dirname(self.target())) else os.path.expanduser("~")
        chosen = QtWidgets.QFileDialog.getExistingDirectory(self, getMessage("install-browse-title"), start)
        if chosen:
            self.folderEdit.setText(install.targetRoot(chosen))

    def _report(self, done, total):
        self.progress.setValue(int(done * 100 / max(total, 1)))
        QtWidgets.QApplication.processEvents()

    def install(self):
        if self._check():
            return
        target = self.target()
        for widget in (self.installButton, self.laterButton, self.browseButton, self.folderEdit, self.menuCheck, self.desktopCheck):
            widget.setEnabled(False)
        try:
            if not self.moving() and os.name == "nt" and self.exePath and os.path.isfile(self.exePath):
                kept = os.path.join(target, install.EXE_NAME)  # Shortcuts open the .exe (its icon, and it unpacks if needed)
                if os.path.normcase(os.path.abspath(self.exePath)) != os.path.normcase(os.path.abspath(kept)):
                    shutil.copy2(self.exePath, kept)
            if self.moving():
                self.progress.show()
                self.installButton.setText(getMessage("install-copying"))
                QtWidgets.QApplication.processEvents()
                self._copier(self.currentRoot, target, self.exePath, self._report)
                if os.name == "nt":
                    install.writeInstallDir(target)
            self._setShortcuts(target, self.menuCheck.isChecked(), self.desktopCheck.isChecked())
        except (OSError, ValueError) as e:
            self.progress.hide()
            for widget in (self.installButton, self.laterButton, self.menuCheck, self.desktopCheck):
                widget.setEnabled(True)
            for widget in (self.browseButton, self.folderEdit):
                widget.setEnabled(self.canMove)
            self._check()
            self.problem.setText(getMessage("install-failed").format(e))
            self.problem.show()
            return
        self.chosenRoot = target
        self.outcome = "moved" if self.moving() else "here"
        self.accept()
