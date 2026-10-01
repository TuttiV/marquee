
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from functools import wraps
from platform import python_version

from twisted.internet import task

from syncplay import utils, constants, version, revision, release_number
from syncplay.messages import getMessage
from syncplay.ui.consoleUI import ConsoleUI
from syncplay import branding, updater, instance, secrets, install, playlistfile, voice, links, resume, emoji, subdelay
from syncplay import invite as inviteLinks
from syncplay.private_build import BUILD
from syncplay.ui import icons, theme
from syncplay.ui.SubtitleDialog import SubtitleDialog
from syncplay.ui.TorBoxDialog import TorBoxDialog
from syncplay.ui.UpdateLogDialog import UpdateLogDialog
from syncplay.ui.panels import ProgressStrip, ClickableLabel, ReadyButton, EmojiPicker
from syncplay.utils import resourcespath
from syncplay.utils import isLinux, isWindows, isMacOS
from syncplay.utils import formatTime, sameFilename, sameFilesize, sameFileduration, RoomPasswordProvider, formatSize, isURL
from syncplay.utils import getCorrectedPathForFile
from syncplay.vendor import Qt
from syncplay.vendor.Qt import QtCore, QtWidgets, QtGui, __binding__, __binding_version__, __qt_version__, IsPySide, IsPySide2, IsPySide6
from syncplay.vendor.Qt.QtCore import Qt, QSettings, QSize, QPoint, QUrl, QLine, QDateTime
applyDPIScaling = True
if isLinux():
    applyDPIScaling = False
else:
    applyDPIScaling = True
if not IsPySide6:
    try:
        if hasattr(QtCore.Qt, 'AA_EnableHighDpiScaling'):
            QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, applyDPIScaling)
    except AttributeError:
        pass  # To ignore error "Attribute Qt::AA_EnableHighDpiScaling must be set before QCoreApplication is created"
    if hasattr(QtCore.Qt, 'AA_UseHighDpiPixmaps'):
        QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, applyDPIScaling)
if IsPySide6:
    from PySide6.QtCore import QStandardPaths
elif IsPySide2:
    from PySide2.QtCore import QStandardPaths
if isMacOS() and IsPySide:
    from Foundation import NSURL
    from Cocoa import NSString, NSUTF8StringEncoding
lastCheckedForUpdates = None
from syncplay.vendor import darkdetect
if isMacOS() or isWindows():
    isDarkMode = darkdetect.isDark()
else:
    isDarkMode = None


def menuIcon(stem):
    """The themed line icon that replaces the old PNG called `stem` (falls back to the PNG itself if there is none)."""
    dark = theme.isDarkPalette(QtWidgets.QApplication.palette())
    replacement = icons.legacy(stem, theme.tokens(dark)["text"], 16)
    return replacement if replacement is not None else QtGui.QIcon(resourcespath + stem + ".png")


class ElidedLabel(QtWidgets.QLabel):
    """A one-line label that shortens its text in the middle to whatever width it is given (the full text is the tooltip)."""
    def __init__(self, *args):
        super(ElidedLabel, self).__init__(*args)
        self._full = ""
        self.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)

    def setFullText(self, text):
        self._full = text
        self.setToolTip(text)
        self._elide()

    def _elide(self):
        self.setText(self.fontMetrics().elidedText(self._full, Qt.ElideMiddle, max(self.width(), 20)))

    def resizeEvent(self, event):
        super(ElidedLabel, self).resizeEvent(event)
        self._elide()


class ConsoleInGUI(ConsoleUI):
    def showMessage(self, message, noTimestamp=False, isMotd=False):
        self._syncplayClient.ui.showMessage(message, noTimestamp=True, isMotd=isMotd)

    def showDebugMessage(self, message):
        self._syncplayClient.ui.showDebugMessage(message)

    def showErrorMessage(self, message, criticalerror=False):
        self._syncplayClient.ui.showErrorMessage(message, criticalerror)

    def updateRoomName(self, room=""): #bob
        self._syncplayClient.ui.updateRoomName(room)

    def getUserlist(self):
        self._syncplayClient.showUserList(self)


class UserlistItemDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, view=None):
        self.view = view
        QtWidgets.QStyledItemDelegate.__init__(self)

    def sizeHint(self, option, index):
        size = QtWidgets.QStyledItemDelegate.sizeHint(self, option, index)
        if (index.column() == constants.USERLIST_GUI_USERNAME_COLUMN):
            size.setWidth(size.width() + constants.USERLIST_GUI_USERNAME_OFFSET)
        return size

    def paint(self, itemQPainter, optionQStyleOptionViewItem, indexQModelIndex):
        column = indexQModelIndex.column()
        midY = int((optionQStyleOptionViewItem.rect.y() + optionQStyleOptionViewItem.rect.bottomLeft().y()) / 2)
        if column == constants.USERLIST_GUI_USERNAME_COLUMN:
            currentQAbstractItemModel = indexQModelIndex.model()
            itemQModelIndex = currentQAbstractItemModel.index(indexQModelIndex.row(), constants.USERLIST_GUI_USERNAME_COLUMN, indexQModelIndex.parent())
            controlIconQPixmap = QtGui.QPixmap(resourcespath + "user_key.png")
            tickIconQPixmap = QtGui.QPixmap(resourcespath + "tick.png")
            crossIconQPixmap = QtGui.QPixmap(resourcespath + "cross.png")
            roomController = currentQAbstractItemModel.data(itemQModelIndex, Qt.UserRole + constants.USERITEM_CONTROLLER_ROLE)
            userReady = currentQAbstractItemModel.data(itemQModelIndex, Qt.UserRole + constants.USERITEM_READY_ROLE)
            isUserRow = indexQModelIndex.parent() != indexQModelIndex.parent().parent()
            bkgColor = self.view.palette().color(QtGui.QPalette.Base)
            if isUserRow and (isMacOS() or isLinux()):
                blankRect = QtCore.QRect(0, optionQStyleOptionViewItem.rect.y(), optionQStyleOptionViewItem.rect.width(), optionQStyleOptionViewItem.rect.height())
                itemQPainter.fillRect(blankRect, bkgColor)

            if roomController and not controlIconQPixmap.isNull():
                itemQPainter.drawPixmap(
                    optionQStyleOptionViewItem.rect.x()+6,
                    midY-8,
                    controlIconQPixmap.scaled(16, 16, Qt.KeepAspectRatio))

            if userReady and not tickIconQPixmap.isNull():
                itemQPainter.drawPixmap(
                    (optionQStyleOptionViewItem.rect.x()-10),
                    midY - 8,
                    tickIconQPixmap.scaled(16, 16, Qt.KeepAspectRatio))

            elif userReady == False and not crossIconQPixmap.isNull():
                itemQPainter.drawPixmap(
                    (optionQStyleOptionViewItem.rect.x()-10),
                    midY - 8,
                    crossIconQPixmap.scaled(16, 16, Qt.KeepAspectRatio))
            if isUserRow:
                optionQStyleOptionViewItem.rect.setX(optionQStyleOptionViewItem.rect.x()+constants.USERLIST_GUI_USERNAME_OFFSET)
        if column == constants.USERLIST_GUI_FILENAME_COLUMN:
            currentQAbstractItemModel = indexQModelIndex.model()
            itemQModelIndex = currentQAbstractItemModel.index(indexQModelIndex.row(), constants.USERLIST_GUI_FILENAME_COLUMN, indexQModelIndex.parent())
            fileSwitchRole = currentQAbstractItemModel.data(itemQModelIndex, Qt.UserRole + constants.FILEITEM_SWITCH_ROLE)
            if fileSwitchRole == constants.FILEITEM_SWITCH_FILE_SWITCH:
                fileSwitchIconQPixmap = icons.pixmap("play", theme.tokens(theme.isDarkPalette(self.view.palette()))["muted"], 16, scale=1.0)
                itemQPainter.drawPixmap(
                    (optionQStyleOptionViewItem.rect.x()),
                    midY - 8,
                    fileSwitchIconQPixmap.scaled(16, 16, Qt.KeepAspectRatio))
                optionQStyleOptionViewItem.rect.setX(optionQStyleOptionViewItem.rect.x()+16)

            elif fileSwitchRole == constants.FILEITEM_SWITCH_STREAM_SWITCH:
                streamSwitchIconQPixmap = icons.pixmap("globe", theme.tokens(theme.isDarkPalette(self.view.palette()))["muted"], 16, scale=1.0)
                itemQPainter.drawPixmap(
                    (optionQStyleOptionViewItem.rect.x()),
                    midY - 8,
                    streamSwitchIconQPixmap.scaled(16, 16, Qt.KeepAspectRatio))
                optionQStyleOptionViewItem.rect.setX(optionQStyleOptionViewItem.rect.x()+16)
        QtWidgets.QStyledItemDelegate.paint(self, itemQPainter, optionQStyleOptionViewItem, indexQModelIndex)


class ModernUserlistDelegate(UserlistItemDelegate):
    """The people table: a round ready / not-ready badge before each name and an operator star after it. The other columns
    (size, length, file) are ordinary muted cells that turn red when they differ from yours."""
    INSET = 12

    def _isUserRow(self, index):
        return index.parent() != index.parent().parent()

    def sizeHint(self, option, index):
        size = QtWidgets.QStyledItemDelegate.sizeHint(self, option, index)
        user = self._isUserRow(index)
        size.setHeight(max(size.height(), 34 if user else 30))
        if index.column() == constants.USERLIST_GUI_USERNAME_COLUMN and user:
            size.setWidth(size.width() + self.INSET + 100)
        return size

    def paint(self, painter, option, index):
        if index.column() != constants.USERLIST_GUI_USERNAME_COLUMN or not self._isUserRow(index):
            return UserlistItemDelegate.paint(self, painter, option, index)
        model = index.model()
        dark = theme.isDarkPalette(self.view.palette())
        tokens = theme.tokens(dark)
        rect = option.rect
        name = index.data() or ""
        isController = model.data(index, Qt.UserRole + constants.USERITEM_CONTROLLER_ROLE)
        userReady = model.data(index, Qt.UserRole + constants.USERITEM_READY_ROLE)

        # Hover / selection background without text; the name is drawn below
        background = QtWidgets.QStyleOptionViewItem(option)
        self.initStyleOption(background, index)
        background.text = ""
        background.icon = QtGui.QIcon()
        (option.widget.style() if option.widget else QtWidgets.QApplication.style()).drawControl(
            QtWidgets.QStyle.CE_ItemViewItem, background, painter, option.widget)

        painter.save()
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        nameFont = QtGui.QFont(index.data(Qt.FontRole) or option.font)
        metrics = QtGui.QFontMetrics(nameFont)
        foreground = index.data(Qt.ForegroundRole)
        painter.setFont(nameFont)
        painter.setPen(foreground.color() if hasattr(foreground, "color") else QtGui.QColor(tokens["text"]))
        # A word, not a symbol: "Ready" on a green pill or "Not ready" on a muted red one, at the right of the cell
        pillWidth = 0
        if userReady is not None:
            word = getMessage("ready-state-on" if userReady else "ready-state-off")
            pillFont = QtGui.QFont(option.font)
            pillFont.setPointSizeF(max(option.font.pointSizeF() - 1.0, 7.0))
            pillFont.setWeight(QtGui.QFont.DemiBold)
            pillMetrics = QtGui.QFontMetrics(pillFont)
            pillWidth = pillMetrics.horizontalAdvance(word) + 18
            pill = QtCore.QRectF(rect.right() - pillWidth - 6, rect.center().y() - 10, pillWidth, 20)
            color = QtGui.QColor(tokens["ready"] if userReady else tokens["danger"])
            soft = QtGui.QColor(color)
            soft.setAlpha(46)
            painter.setPen(Qt.NoPen)
            painter.setBrush(soft)
            painter.drawRoundedRect(pill, 10, 10)
            painter.setFont(pillFont)
            painter.setPen(color)
            painter.drawText(pill, Qt.AlignCenter, word)
            pillWidth += 12
        painter.setFont(nameFont)
        painter.setPen(foreground.color() if hasattr(foreground, "color") else QtGui.QColor(tokens["text"]))
        left = rect.x() + self.INSET
        nameRect = QtCore.QRect(left, rect.y(), max(rect.right() - left - pillWidth - (20 if isController else 4), 0), rect.height())
        painter.drawText(nameRect, Qt.AlignLeft | Qt.AlignVCenter, metrics.elidedText(name, Qt.ElideRight, nameRect.width()))
        if isController:
            painter.drawPixmap(min(left + metrics.horizontalAdvance(name) + 6, rect.right() - pillWidth - 18), int(rect.center().y()) - 7,
                               icons.pixmap("star", tokens["warn"], 14))
        painter.restore()


class ToggleSwitch(QtWidgets.QAbstractButton):
    """A small on/off switch with a text label, for settings (as opposed to actions)."""
    TRACK_W, TRACK_H = 34, 20

    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self.setText(text)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)

    def sizeHint(self):
        metrics = self.fontMetrics()
        return QSize(self.TRACK_W + 10 + metrics.horizontalAdvance(self.text()) + 4, max(self.TRACK_H, metrics.height()) + 8)

    def paintEvent(self, event):
        tokens = theme.tokens(theme.isDarkPalette(self.palette()))
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        enabled = self.isEnabled()
        track = QtCore.QRectF(1, (self.height() - self.TRACK_H) / 2, self.TRACK_W, self.TRACK_H)
        on = self.isChecked()
        trackColor = QtGui.QColor(tokens["ready"] if on else tokens["border"])
        if not enabled:
            trackColor.setAlpha(110)
        painter.setPen(Qt.NoPen)
        painter.setBrush(trackColor)
        painter.drawRoundedRect(track, self.TRACK_H / 2, self.TRACK_H / 2)
        knobSize = self.TRACK_H - 6
        knobX = track.right() - knobSize - 3 if on else track.left() + 3
        painter.setBrush(QtGui.QColor("#ffffff"))
        painter.drawEllipse(QtCore.QRectF(knobX, track.top() + 3, knobSize, knobSize))
        if self.hasFocus():
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QtGui.QPen(QtGui.QColor(tokens["accent"]), 1.5))
            painter.drawRoundedRect(track.adjusted(-1, -1, 1, 1), self.TRACK_H / 2 + 1, self.TRACK_H / 2 + 1)
        painter.setPen(QtGui.QColor(tokens["text"] if enabled else tokens["muted"]))
        painter.drawText(QtCore.QRectF(self.TRACK_W + 12, 0, self.width() - self.TRACK_W - 12, self.height()),
                         Qt.AlignVCenter | Qt.AlignLeft, self.text())


class AboutDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(AboutDialog, self).__init__(parent)
        if isMacOS():
            self.setWindowTitle("")
            self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint | Qt.CustomizeWindowHint)
        else:
            self.setWindowTitle(getMessage("about-dialog-title"))
            if isWindows():
                if IsPySide6:
                    self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowSystemMenuHint | Qt.WindowCloseButtonHint  | Qt.CustomizeWindowHint                        )
                else:
                    self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setWindowIcon(QtGui.QPixmap(resourcespath + 'syncplay.png'))
        tokens = theme.tokens(theme.isDarkPalette(QtWidgets.QApplication.palette()))
        logo = QtWidgets.QLabel()
        logo.setPixmap(QtGui.QIcon(resourcespath + "syncplayAbout.png").pixmap(72, 72))
        logo.setAlignment(Qt.AlignCenter)
        nameLabel = QtWidgets.QLabel(branding.NAME)
        nameLabel.setAlignment(Qt.AlignCenter)
        nameLabel.setStyleSheet("font-size: 22px; font-weight: 700;")
        tagline = QtWidgets.QLabel(branding.TAGLINE)
        tagline.setAlignment(Qt.AlignCenter)
        tagline.setStyleSheet("color: {};".format(tokens["muted"]))
        versionLabel = QtWidgets.QLabel("Build {}\nPython {} \u00b7 {} {} \u00b7 Qt {}".format(
            BUILD, python_version(), __binding__, __binding_version__, __qt_version__))
        versionLabel.setAlignment(Qt.AlignCenter)
        versionLabel.setStyleSheet("color: {}; font-size: 12px;".format(tokens["muted"]))
        licenseLabel = QtWidgets.QLabel("{}\n\n{}".format(branding.BASED_ON, getMessage("about-dialog-license-text").replace("&nbsp;", " ")))
        licenseLabel.setAlignment(Qt.AlignCenter)
        licenseLabel.setWordWrap(True)
        licenseLabel.setMinimumWidth(380)
        licenseLabel.setStyleSheet("color: {}; font-size: 12px;".format(tokens["muted"]))
        aboutLayout = QtWidgets.QVBoxLayout()
        aboutLayout.setContentsMargins(28, 24, 28, 20)
        aboutLayout.setSpacing(6)
        for widget in (logo, nameLabel, tagline):
            aboutLayout.addWidget(widget)
        aboutLayout.addSpacing(6)
        aboutLayout.addWidget(versionLabel)
        aboutLayout.addSpacing(10)
        aboutLayout.addWidget(licenseLabel)
        aboutLayout.addSpacing(14)
        buttons = QtWidgets.QHBoxLayout()
        buttons.setSpacing(8)
        licenseButton = QtWidgets.QPushButton(getMessage("about-dialog-license-button"))
        licenseButton.setAutoDefault(False)
        licenseButton.clicked.connect(self.openLicense)
        dependenciesButton = QtWidgets.QPushButton(getMessage("about-dialog-dependencies"))
        dependenciesButton.setAutoDefault(False)
        dependenciesButton.clicked.connect(self.openDependencies)
        self.updateLogButton = QtWidgets.QPushButton(getMessage("update-log-menu-label").replace("&", "").rstrip("."))
        self.updateLogButton.setAutoDefault(False)
        self.updateLogButton.clicked.connect(self._openUpdateLog)
        for button in (licenseButton, dependenciesButton, self.updateLogButton):
            buttons.addWidget(button)
        aboutLayout.addLayout(buttons)
        aboutLayout.setSizeConstraint(QtWidgets.QLayout.SetFixedSize)
        self.setSizeGripEnabled(False)
        self.setLayout(aboutLayout)

    def _openUpdateLog(self):
        parent = self.parent()
        if parent is not None and hasattr(parent, "showUpdateLog"):
            self.close()
            parent.showUpdateLog()

    def openLicense(self):
        if isWindows():
                QtGui.QDesktopServices.openUrl(QUrl("file:///" + resourcespath + "license.rtf"))
        else:
                QtGui.QDesktopServices.openUrl(QUrl("file://" + resourcespath + "license.rtf"))

    def openDependencies(self):
        if isWindows():
            QtGui.QDesktopServices.openUrl(QUrl("file:///" + resourcespath + "third-party-notices.txt"))
        else:
            QtGui.QDesktopServices.openUrl(QUrl("file://" + resourcespath + "third-party-notices.txt"))


class CertificateDialog(QtWidgets.QDialog):
    def __init__(self, tlsData, parent=None):
        super(CertificateDialog, self).__init__(parent)
        if isMacOS():
            self.setWindowTitle("")
            self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint | Qt.CustomizeWindowHint)
        else:
            self.setWindowTitle(getMessage("tls-information-title"))
            if isWindows():
                if IsPySide6:
                    self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowSystemMenuHint | Qt.WindowCloseButtonHint  | Qt.CustomizeWindowHint                        )
                else:
                    self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setWindowIcon(QtGui.QPixmap(resourcespath + 'syncplay.png'))
        statusLabel = QtWidgets.QLabel(getMessage("tls-dialog-status-label").format(tlsData["subject"]))
        descLabel = QtWidgets.QLabel(getMessage("tls-dialog-desc-label").format(tlsData["subject"]))
        connDataLabel = QtWidgets.QLabel(getMessage("tls-dialog-connection-label").format(tlsData["protocolVersion"], tlsData["cipher"]))
        certDataLabel = QtWidgets.QLabel(getMessage("tls-dialog-certificate-label").format(tlsData["issuer"], tlsData["expires"]))
        if isMacOS():
            statusLabel.setFont(QtGui.QFont("Helvetica", 12))
            descLabel.setFont(QtGui.QFont("Helvetica", 12))
            connDataLabel.setFont(QtGui.QFont("Helvetica", 12))
            certDataLabel.setFont(QtGui.QFont("Helvetica", 12))
        lockIcon = QtGui.QIcon()
        lockIcon.addFile(resourcespath + "lock_green_dialog.png")
        lockIconLabel = QtWidgets.QLabel()
        lockIconLabel.setPixmap(lockIcon.pixmap(64, 64))
        certLayout = QtWidgets.QGridLayout()
        certLayout.addWidget(lockIconLabel, 1, 0, 3, 1, Qt.AlignLeft | Qt.AlignTop)
        certLayout.addWidget(statusLabel, 0, 1, 1, 3)
        certLayout.addWidget(descLabel, 1, 1, 1, 3)
        certLayout.addWidget(connDataLabel, 2, 1, 1, 3)
        certLayout.addWidget(certDataLabel, 3, 1, 1, 3)
        closeButton = QtWidgets.QPushButton("Close")
        closeButton.setFixedWidth(100)
        closeButton.setAutoDefault(False)
        closeButton.clicked.connect(self.closeDialog)
        certLayout.addWidget(closeButton, 4, 3, 1, 1)
        certLayout.setVerticalSpacing(10)
        certLayout.setSizeConstraint(QtWidgets.QLayout.SetFixedSize)
        self.setSizeGripEnabled(False)
        self.setLayout(certLayout)

    def closeDialog(self):
        self.close()


class MainWindow(QtWidgets.QMainWindow):
    insertPosition = None
    playlistState = []
    updatingPlaylist = False
    playlistIndex = None
    sslInformation = "N/A"
    sslMode = False


    def setPlaylistInsertPosition(self, newPosition):
        if not self.playlist.isEnabled():
            return
        if MainWindow.insertPosition != newPosition:
            MainWindow.insertPosition = newPosition
            self.playlist.forceUpdate()

    class PlaylistItemDelegate(QtWidgets.QStyledItemDelegate):
        def paint(self, itemQPainter, optionQStyleOptionViewItem, indexQModelIndex):
            itemQPainter.save()
            currentQAbstractItemModel = indexQModelIndex.model()
            currentlyPlayingFile = currentQAbstractItemModel.data(indexQModelIndex, Qt.UserRole + constants.PLAYLISTITEM_CURRENTLYPLAYING_ROLE)
            if currentlyPlayingFile:
                currentlyplayingIconQPixmap = icons.pixmap("chevron", theme.tokens(theme.isDarkPalette(QtWidgets.QApplication.palette()))["accent"], 16, scale=1.0)
                midY = int((optionQStyleOptionViewItem.rect.y() + optionQStyleOptionViewItem.rect.bottomLeft().y()) / 2)
                itemQPainter.drawPixmap(
                    (optionQStyleOptionViewItem.rect.x()+4),
                    midY-8,
                    currentlyplayingIconQPixmap.scaled(8, 16, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                optionQStyleOptionViewItem.rect.setX(optionQStyleOptionViewItem.rect.x()+10)

            QtWidgets.QStyledItemDelegate.paint(self, itemQPainter, optionQStyleOptionViewItem, indexQModelIndex)

            lineAbove = False
            lineBelow = False
            if MainWindow.insertPosition == 0 and indexQModelIndex.row() == 0:
                lineAbove = True
            elif MainWindow.insertPosition and indexQModelIndex.row() == MainWindow.insertPosition-1:
                lineBelow = True
            if lineAbove:
                line = QLine(optionQStyleOptionViewItem.rect.topLeft(), optionQStyleOptionViewItem.rect.topRight())
                itemQPainter.drawLine(line)
            elif lineBelow:
                line = QLine(optionQStyleOptionViewItem.rect.bottomLeft(), optionQStyleOptionViewItem.rect.bottomRight())
                itemQPainter.drawLine(line)
            itemQPainter.restore()

    class PlaylistGroupBox(QtWidgets.QGroupBox):

        def dragEnterEvent(self, event):
            data = event.mimeData()
            urls = data.urls()
            window = self.parent().parent().parent().parent().parent()
            if urls and urls[0].scheme() == 'file':
                event.acceptProposedAction()
                window.setPlaylistInsertPosition(window.playlist.count())
            else:
                super(MainWindow.PlaylistGroupBox, self).dragEnterEvent(event)

        def dragLeaveEvent(self, event):
            window = self.parent().parent().parent().parent().parent()
            window.setPlaylistInsertPosition(None)

        def dropEvent(self, event):
            window = self.parent().parent().parent().parent().parent()
            if not window.playlist.isEnabled():
                return
            window.setPlaylistInsertPosition(None)
            if QtGui.QDropEvent.proposedAction(event) == Qt.MoveAction:
                QtGui.QDropEvent.setDropAction(event, Qt.CopyAction)  # Avoids file being deleted
            data = event.mimeData()
            urls = data.urls()

            if urls and urls[0].scheme() == 'file':
                indexRow = window.playlist.count() if window.clearedPlaylistNote else 0

                for url in urls[::-1]:
                    if isMacOS() and IsPySide:
                        macURL = NSString.alloc().initWithString_(str(url.toString()))
                        pathString = macURL.stringByAddingPercentEscapesUsingEncoding_(NSUTF8StringEncoding)
                        dropfilepath = os.path.abspath(NSURL.URLWithString_(pathString).filePathURL().path())
                    else:
                        dropfilepath = os.path.abspath(str(url.toLocalFile()))
                    if os.path.isfile(dropfilepath):
                        window.addFileToPlaylist(dropfilepath, indexRow)
                    elif os.path.isdir(dropfilepath):
                        window.addFolderToPlaylist(dropfilepath)
            else:
                super(MainWindow.PlaylistWidget, self).dropEvent(event)

    class PlaylistWidget(QtWidgets.QListWidget):
        selfWindow = None
        playlistIndexFilename = None

        def setPlaylistIndexFilename(self, filename):
            if filename != self.playlistIndexFilename:
                self.playlistIndexFilename = filename
            self.updatePlaylistIndexIcon()

        def updatePlaylistIndexIcon(self):
            playlistItems = [self.item(i).text() for i in range(self.count())]
            if constants.SHOW_PLAYLIST_SKIP_WARNINGS:
                playlistSkipWarnings = self.selfWindow._syncplayClient.watched.getPlaylistSkipWarnings(playlistItems)
            else:
                playlistSkipWarnings = {}
            if constants.SHOW_PLAYLIST_ORDER_WARNINGS:
                playlistOrderWarnings = self.selfWindow._syncplayClient.watched.getPlaylistOrderWarnings(playlistItems)
            else:
                playlistOrderWarnings = {}
            for item in range(self.count()):
                itemFilename = self.item(item).text()
                isPlayingFilename = itemFilename == self.playlistIndexFilename
                self.item(item).setData(Qt.UserRole + constants.PLAYLISTITEM_CURRENTLYPLAYING_ROLE, isPlayingFilename)
                fileIsAvailable = self.selfWindow.isFileAvailable(itemFilename)
                fileIsUntrusted = self.selfWindow.isItemUntrusted(itemFilename)
                if fileIsUntrusted:
                    if isDarkMode:
                        self.item(item).setForeground(QtGui.QBrush(QtGui.QColor(constants.STYLE_DARK_UNTRUSTEDITEM_COLOR)))
                        self.item(item).setBackground(QtGui.QBrush(self.selfWindow.palette().color(QtGui.QPalette.Base)))
                    else:
                        self.item(item).setForeground(QtGui.QBrush(QtGui.QColor(constants.STYLE_UNTRUSTEDITEM_COLOR)))
                        self.item(item).setBackground(QtGui.QBrush(self.selfWindow.palette().color(QtGui.QPalette.Base)))
                elif fileIsAvailable:
                    filePath = self.selfWindow._syncplayClient.fileSwitch.findFilepath(itemFilename)
                    if self.selfWindow._syncplayClient.watched.isWatchedFile(filePath):
                        self.item(item).setBackground(QtGui.QBrush(QtGui.QColor("grey")))
                        self.item(item).setForeground(QtGui.QBrush(QtGui.QColor("black")))
                        pass
                    else:
                        self.item(item).setForeground(QtGui.QBrush(self.selfWindow.palette().color(QtGui.QPalette.Text)))
                        self.item(item).setBackground(QtGui.QBrush(self.selfWindow.palette().color(QtGui.QPalette.Base)))
                else:
                    if isDarkMode:
                        self.item(item).setForeground(QtGui.QBrush(QtGui.QColor(constants.STYLE_DARK_DIFFERENTITEM_COLOR)))
                        self.item(item).setBackground(QtGui.QBrush(self.selfWindow.palette().color(QtGui.QPalette.Base)))
                    else:
                        self.item(item).setForeground(QtGui.QBrush(QtGui.QColor(constants.STYLE_DIFFERENTITEM_COLOR)))
                        self.item(item).setBackground(QtGui.QBrush(self.selfWindow.palette().color(QtGui.QPalette.Base)))

                tooltip = self._getPlaylistItemTooltip(item, itemFilename, playlistSkipWarnings, playlistOrderWarnings)
                self.item(item).setToolTip(tooltip or "")
                if item in playlistSkipWarnings or item in playlistOrderWarnings:
                    self.item(item).setIcon(self._getPlaylistWarningIcon())
                else:
                    self.item(item).setIcon(QtGui.QIcon())
            self.selfWindow._syncplayClient.fileSwitch.setFilenameWatchlist(self.selfWindow.newWatchlist)
            self.forceUpdate()

        def _getPlaylistWarningIcon(self):
            if not hasattr(self, "_playlistWarningIcon"):
                self._playlistWarningIcon = self.style().standardIcon(QtWidgets.QStyle.SP_MessageBoxWarning)
            return self._playlistWarningIcon

        def viewportEvent(self, event):
            if event.type() == QtCore.QEvent.ToolTip:
                item = self.itemAt(event.pos())
                if item:
                    tooltip = self._getPlaylistItemTooltip(self.row(item), item.text())
                    item.setToolTip(tooltip or "")
            return super(MainWindow.PlaylistWidget, self).viewportEvent(event)

        def _getPlaylistItemTooltip(self, itemIndex, itemFilename, playlistSkipWarnings=None, playlistOrderWarnings=None):
            tooltipParts = []
            filePath = self.selfWindow._syncplayClient.fileSwitch.findFilepath(itemFilename)
            watchedTooltip = self._getWatchedTooltipForFilePath(filePath)
            if watchedTooltip:
                tooltipParts.append(watchedTooltip)

            if playlistSkipWarnings is None or playlistOrderWarnings is None:
                playlistItems = [self.item(i).text() for i in range(self.count())]
                if constants.SHOW_PLAYLIST_SKIP_WARNINGS:
                    playlistSkipWarnings = self.selfWindow._syncplayClient.watched.getPlaylistSkipWarnings(playlistItems)
                else:
                    playlistSkipWarnings = {}
                if constants.SHOW_PLAYLIST_ORDER_WARNINGS:
                    playlistOrderWarnings = self.selfWindow._syncplayClient.watched.getPlaylistOrderWarnings(playlistItems)
                else:
                    playlistOrderWarnings = {}

            orderWarning = playlistOrderWarnings.get(itemIndex)
            if constants.SHOW_PLAYLIST_ORDER_WARNINGS and orderWarning:
                tooltipParts.append(
                    getMessage("playlist-out-of-order-warning-tooltip").format(
                        orderWarning["episode"], orderWarning["previousEpisode"], orderWarning["expectedEpisode"]))

            skipWarning = playlistSkipWarnings.get(itemIndex)
            if constants.SHOW_PLAYLIST_SKIP_WARNINGS and skipWarning:
                tooltipParts.append(
                    getMessage("playlist-skip-warning-tooltip").format(skipWarning["missingEpisode"]))
                previousWatchedTooltip = self._getWatchedTooltipForMetadata(skipWarning.get("previousWatchedMeta"))
                previousWatchedFilename = skipWarning.get("previousWatchedFilename")
                if previousWatchedTooltip and previousWatchedFilename:
                    tooltipParts.append("'{}': {}".format(previousWatchedFilename, previousWatchedTooltip))

            return "\n".join(tooltipParts)

        def _getWatchedTooltipForFilePath(self, filePath):
            if not filePath:
                return None
            meta = self.selfWindow._syncplayClient.watched.getWatchedMetadata(filePath)
            return self._getWatchedTooltipForMetadata(meta)

        def _getWatchedTooltipForMetadata(self, meta):
            if not meta or not meta.get("lastWatchedAt"):
                return None
            try:
                dtUtc = datetime.strptime(meta["lastWatchedAt"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                delta = datetime.now(timezone.utc) - dtUtc
                seconds = int(delta.total_seconds())
                if seconds < 3600:
                    age = getMessage("watched-ago-minutes").format(max(1, seconds // 60))
                elif seconds < 86400:
                    age = getMessage("watched-ago-hours").format(seconds // 3600)
                else:
                    age = getMessage("watched-ago-days").format(delta.days)
                room = meta.get("lastRoom") or meta.get("lastWatchedRoom") or ""
                return getMessage("watched-last-watched-tooltip").format(
                    age, room, dtUtc.astimezone().strftime(getMessage("watched-datetime-format")))
            except Exception:
                return None

        def setWindow(self, window):
            self.selfWindow = window

        def dragLeaveEvent(self, event):
            window = self.parent().parent().parent().parent().parent().parent()
            window.setPlaylistInsertPosition(None)

        def forceUpdate(self):
            root = self.rootIndex()
            self.dataChanged(root, root)

        def keyPressEvent(self, event):
            if event.key() == Qt.Key_Delete:
                self.remove_selected_items()
            else:
                super(MainWindow.PlaylistWidget, self).keyPressEvent(event)

        def updatePlaylist(self, newPlaylist):
            for index in range(self.count()):
                self.takeItem(0)
            uniquePlaylist = []
            for item in newPlaylist:
                if item not in uniquePlaylist:
                    uniquePlaylist.append(item)
            self.insertItems(0, uniquePlaylist)
            self.updatePlaylistIndexIcon()

        def remove_selected_items(self):
            for item in self.selectedItems():
                self.takeItem(self.row(item))

        def dragEnterEvent(self, event):
            data = event.mimeData()
            urls = data.urls()
            if urls and urls[0].scheme() == 'file':
                event.acceptProposedAction()
            else:
                super(MainWindow.PlaylistWidget, self).dragEnterEvent(event)

        def dragMoveEvent(self, event):
            data = event.mimeData()
            urls = data.urls()
            if urls and urls[0].scheme() == 'file':
                event.acceptProposedAction()
                indexRow = self.indexAt(event.pos()).row()
                window = self.parent().parent().parent().parent().parent().parent()
                if indexRow == -1 or not window.clearedPlaylistNote:
                    indexRow = window.playlist.count()
                window.setPlaylistInsertPosition(indexRow)
            else:
                super(MainWindow.PlaylistWidget, self).dragMoveEvent(event)

        def dropEvent(self, event):
            window = self.parent().parent().parent().parent().parent().parent()
            if not window.playlist.isEnabled():
                return
            window.setPlaylistInsertPosition(None)
            if QtGui.QDropEvent.proposedAction(event) == Qt.MoveAction:
                QtGui.QDropEvent.setDropAction(event, Qt.CopyAction)  # Avoids file being deleted
            data = event.mimeData()
            urls = data.urls()

            if urls and urls[0].scheme() == 'file':
                indexRow = self.indexAt(event.pos()).row()
                if not window.clearedPlaylistNote:
                    indexRow = 0
                if indexRow == -1:
                    indexRow = window.playlist.count()
                for url in urls[::-1]:
                    if isMacOS() and IsPySide:
                        macURL = NSString.alloc().initWithString_(str(url.toString()))
                        pathString = macURL.stringByAddingPercentEscapesUsingEncoding_(NSUTF8StringEncoding)
                        dropfilepath = os.path.abspath(NSURL.URLWithString_(pathString).filePathURL().path())
                    else:
                        dropfilepath = os.path.abspath(str(url.toLocalFile()))
                    if os.path.isfile(dropfilepath):
                        window.addFileToPlaylist(dropfilepath, indexRow)
                    elif os.path.isdir(dropfilepath):
                        window.addFolderToPlaylist(dropfilepath)
            else:
                super(MainWindow.PlaylistWidget, self).dropEvent(event)

    class topSplitter(QtWidgets.QSplitter):
        def createHandle(self):
            return self.topSplitterHandle(self.orientation(), self)

        class topSplitterHandle(QtWidgets.QSplitterHandle):
            def mouseReleaseEvent(self, event):
                QtWidgets.QSplitterHandle.mouseReleaseEvent(self, event)
                self.parent().parent().parent().updateListGeometry()

            def mouseMoveEvent(self, event):
                QtWidgets.QSplitterHandle.mouseMoveEvent(self, event)
                self.parent().parent().parent().updateListGeometry()

    def needsClient(f):  # @NoSelf
        @wraps(f)
        def wrapper(self, *args, **kwds):
            if not self._syncplayClient:
                self.showDebugMessage("Tried to use client before it was ready!")
                return
            return f(self, *args, **kwds)
        return wrapper

    def fillRoomsCombobox(self):
        previousRoomSelection = self.roomsCombobox.currentText()
        self.roomsCombobox.clear()
        for roomListValue in self.config['roomList']:
            self.roomsCombobox.addItem(roomListValue)
        for room in self.currentRooms:
            if room not in self.config['roomList']:
                self.roomsCombobox.addItem(room)
        self.roomsCombobox.setEditText(previousRoomSelection)

    def addRoomToList(self, newRoom=None):
        if newRoom is None:
            newRoom = self.roomsCombobox.currentText()
        if not newRoom:
            return
        roomList = self.config['roomList']
        if newRoom not in roomList:
            roomList.append(newRoom)
        self.config['roomList'] = roomList
        roomList = sorted(roomList)
        self._syncplayClient.setRoomList(roomList)
        self.relistRoomList(roomList)

    def showUpdateLog(self, newerThan=None):
        dialog = getattr(self, "_updateLogDialog", None)
        if dialog is None:
            dialog = self._updateLogDialog = UpdateLogDialog(self, newerThan)
        else:
            dialog.refresh(newerThan)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _announceUpdateResult(self):
        """Right after an update: say which build is now running, or that the update was undone or couldn't be installed."""
        appDir = updater.appFolder()
        QtCore.QTimer.singleShot(4000, lambda: updater.confirmHealthy(appDir))  # The window is up: keep the update
        for entry in updater.unseenHistory(appDir):
            if entry.get("event") == "rolled-back":
                self.showMessage(getMessage("update-rolled-back-notification").format(entry.get("to") or "?", entry.get("from") or "?"))
        result = updater.consumeUpdateResult(appDir)
        if not result:
            return
        kind, before, after = result
        if kind == "updated":
            self.showMessage(getMessage("update-installed-notification").format(after))
            QtCore.QTimer.singleShot(700, lambda: self.showUpdateLog(newerThan=before))  # What's new, once, right after updating
        else:
            self.showMessage(getMessage("update-not-installed-notification"))

    def addClient(self, client):
        self._syncplayClient = client
        if self.console:
            self.console.addClient(client)
        self.config = self._syncplayClient.getConfig()
        self.roomsCombobox.setEditText(self._syncplayClient.getRoom())
        self.fillRoomsCombobox()
        self.pauseOnDropoutChanged(self.config.get('pauseOnLeave') in (True, 'True'))
        self.skipStartAction.blockSignals(True)
        self.skipStartAction.setChecked(self.config.get('skipStartWindow') in (True, 'True'))
        self.skipStartAction.blockSignals(False)
        if self.config.get('startWindowNowSkipped'):
            self.showMessage(getMessage("startwindow-skipped-notification"))
        try:
            on = secrets.load("notifications", self.config.get("configDir")) != "off" if self.config.get("configDir") else True
        except (OSError, TypeError):
            on = True
        self._notificationsOn = on
        self.notificationsAction.blockSignals(True)
        self.notificationsAction.setChecked(on)
        self.notificationsAction.blockSignals(False)
        self._announceUpdateResult()
        startupFile = self.config.get("loadPlaylistFromFile") or (secrets.load(playlistfile.SETTING, self.config.get("configDir"))
                                                                  if self.config.get("configDir") else None)
        self._lastPlaylistFile = startupFile if startupFile and os.path.isfile(startupFile) else None
        self.reloadPlaylistAction.setEnabled(bool(self._lastPlaylistFile))
        if self.config.get("loadPlaylistFromFile") and self._lastPlaylistFile and self.config.get("configDir"):
            self._rememberPlaylistFile(self._lastPlaylistFile)
        self._startInstanceWatch()
        QtCore.QTimer.singleShot(2500, self._offerShortcuts)
        self._progressTimer = QtCore.QTimer(self)
        self._progressTimer.timeout.connect(self._tickProgress)
        self._progressTimer.start(500)
        self.playlist.model().rowsInserted.connect(self._fitPlaylist)
        self.playlist.model().rowsRemoved.connect(self._fitPlaylist)
        self._fitPlaylist()
        self._setUpInviteLinks()
        try:
            if self.config.get("configDir"):
                theme.setConfigDir(self.config["configDir"])
                for themeName, action in getattr(self, "themeActions", {}).items():
                    action.setChecked(themeName == theme.chosenTheme())
                if theme.chosenTheme() != "system":
                    QtCore.QTimer.singleShot(0, lambda: self.switchTheme(theme.chosenTheme()))
            self.playlistGroup.blockSignals(True)
            self.playlistGroup.setChecked(self.config['sharedPlaylistEnabled'])
            self.playlistGroup.blockSignals(False)
            self._syncplayClient.fileSwitch.setMediaDirectories(self.config["mediaSearchDirectories"])
            self.updateReadyState(self.config['readyAtStart'] or self.config.get('alwaysReady'))
            self.alwaysReadyChanged(self.config.get('alwaysReady'))
            autoplayInitialState = self.config['autoplayInitialState']
            if autoplayInitialState is not None:
                self.autoplayPushButton.blockSignals(True)
                self.autoplayPushButton.setChecked(autoplayInitialState)
                self.autoplayPushButton.blockSignals(False)
            if self.config['autoplayMinUsers'] > 1:
                self.autoplayThresholdSpinbox.blockSignals(True)
                self.autoplayThresholdSpinbox.setValue(self.config['autoplayMinUsers'])
                self.autoplayThresholdSpinbox.blockSignals(False)
            self.changeAutoplayState()
            self.changeAutoplayThreshold()
            self.updateAutoPlayIcon()
        except:
            self.showErrorMessage("Failed to load some settings.")
        self.automaticUpdateCheck()

    def promptFor(self, prompt=">", message=""):
        # TODO: Prompt user
        return None

    def setFeatures(self, featureList):
        if not featureList["readiness"]:
            self._readinessSupported = False
            self.readyPushButton.setEnabled(False)
            self.alwaysReadyButton.setEnabled(False)
            self.alwaysReadyAction.setEnabled(False)
        if not featureList["chat"]:
            self.chatFrame.setEnabled(False)
            self.chatInput.setReadOnly(True)
        if not featureList["sharedPlaylists"]:
            self.playlistGroup.setEnabled(False)
        self.chatInput.setMaxLength(constants.MAX_CHAT_MESSAGE_LENGTH)
        #self.roomsCombobox.setMaxLength(constants.MAX_ROOM_NAME_LENGTH)

    def setSSLMode(self, sslMode, sslInformation):
        self.sslMode = sslMode
        self.sslInformation = sslInformation
        self.sslButton.setVisible(sslMode)

    def getSSLInformation(self):
        return self.sslInformation

    def showMessage(self, message, noTimestamp=False, isMotd=False):
        message = str(message)
        username = None
        messageWithUsername = re.match(constants.MESSAGE_WITH_USERNAME_REGEX, message, re.UNICODE)
        if messageWithUsername:
            username = messageWithUsername.group("username")
            message = messageWithUsername.group("message")
        plain = message
        message = message.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")
        message = message.replace("\n", "<br />")
        if username:
            self._noticeChat(username, plain)
            message = links.linkify(message)
            if emoji.isOnlyEmoji(plain):
                message = '<span style="font-size: 26px;">{}</span>'.format(message)  # A lone emoji reads as a reaction
            self._feedChat(username, message)
        elif isMotd:
            # A MOTD is monospace with escaped spaces so ASCII art keeps its shape
            self._feedBlock("<code>{}</code>".format(message.replace(" ", "&nbsp;")))
        else:
            self._feedEvent(message)

    def _feedTokens(self):
        return theme.tokens(getattr(self, "_dark", theme.isDarkPalette(QtWidgets.QApplication.palette())))

    def _feedBlock(self, html):
        self._lastChatter = None
        self.newMessage(html)

    def _feedEvent(self, html):
        """Quiet one-line entry for joins, leaves, readiness and other room events."""
        self._feedBlock('<div style="color: {}; font-size: 12px; margin-top: 3px; margin-bottom: 3px;">\u2022 {}</div>'.format(
            self._feedTokens()["muted"], html))

    def _feedChat(self, username, html):
        """Chat grouped Discord-style: a coloured name + time header, then that person's consecutive lines."""
        now = time.time()
        tokens = self._feedTokens()
        last = getattr(self, "_lastChatter", None)
        if last and last[0] == username and now - last[1] < 300:
            self.newMessage('<div style="margin-top: 1px; margin-bottom: 1px;">{}</div>'.format(html))
        else:
            color = theme.userColor(username, getattr(self, "_dark", False))
            self.newMessage(
                '<div style="margin-top: 10px; margin-bottom: 1px;"><span style="color: {}; font-weight: 600;">{}</span>'
                ' <span style="color: {}; font-size: 11px;">{}</span></div><div style="margin-top: 1px; margin-bottom: 1px;">{}</div>'.format(
                    color, username, tokens["muted"], time.strftime("%H:%M", time.localtime()), html))
        self._lastChatter = (username, now)

    @needsClient
    def getFileSwitchState(self, filename):
        if filename:
            if filename == getMessage("nofile-note"):
                return constants.FILEITEM_SWITCH_NO_SWITCH
            if self._syncplayClient.userlist.currentUser.file and utils.sameFilename(filename, self._syncplayClient.userlist.currentUser.file['name']):
                return constants.FILEITEM_SWITCH_NO_SWITCH
            if isURL(filename):
                return constants.FILEITEM_SWITCH_STREAM_SWITCH
            elif filename not in self.newWatchlist:
                if self._syncplayClient.fileSwitch.findFilepath(filename):
                    return constants.FILEITEM_SWITCH_FILE_SWITCH
                else:
                    self.newWatchlist.extend([filename])
        return constants.FILEITEM_SWITCH_NO_SWITCH

    @needsClient
    def isItemUntrusted(self, filename):
        return isURL(filename) and not self._syncplayClient.isURITrusted(filename)

    @needsClient
    def isFileAvailable(self, filename):
        if filename:
            if filename == getMessage("nofile-note"):
                return None
            if isURL(filename):
                return True
            elif filename not in self.newWatchlist:
                if self._syncplayClient.fileSwitch.findFilepath(filename):
                    return True
                else:
                    self.newWatchlist.extend([filename])
        return False

    @needsClient
    def showUserList(self, currentUser, rooms):
        self._usertreebuffer = QtGui.QStandardItemModel()
        self._usertreebuffer.setHorizontalHeaderLabels(
            (
                getMessage("roomuser-heading-label"), getMessage("size-heading-label"),
                getMessage("duration-heading-label"), getMessage("filename-heading-label"),
                getMessage("subtitles-heading-label")
            ))
        usertreeRoot = self._usertreebuffer.invisibleRootItem()
        if (
            self._syncplayClient.userlist.currentUser.file and
            self._syncplayClient.userlist.currentUser.file and
            os.path.isfile(self._syncplayClient.userlist.currentUser.file["path"])
        ):
            self._syncplayClient.fileSwitch.setCurrentDirectory(os.path.dirname(self._syncplayClient.userlist.currentUser.file["path"]))

        self.currentRooms = []
        self._columnNeeds = set()  # Which of "size", "duration", "name" (file column) someone in your room needs shown
        for room in rooms:
            self.currentRooms.append(room)
            if self.hideEmptyRooms:
                foundEmptyRooms = False
                for user in rooms[room]:
                    if user.username.strip() == "":
                        foundEmptyRooms = True
                if foundEmptyRooms:
                    continue
            self.newWatchlist = []
            roomitem = QtGui.QStandardItem(room)
            font = QtGui.QFont()
            font.setItalic(True)
            if room == currentUser.room:
                font.setWeight(QtGui.QFont.Bold)
            roomitem.setFont(font)
            roomitem.setFlags(roomitem.flags() & ~Qt.ItemIsEditable)
            usertreeRoot.appendRow(roomitem)
            isControlledRoom = RoomPasswordProvider.isControlledRoom(room)

            if isControlledRoom:
                if room == currentUser.room and currentUser.isController():
                    roomitem.setIcon(menuIcon("lock_open"))
                else:
                    roomitem.setIcon(menuIcon("lock"))
            else:
                if room == currentUser.room:
                    roomitem.setIcon(QtGui.QIcon(resourcespath + "syncplay.png"))  # The logo marks the room you are in
                else:
                    roomitem.setIcon(QtGui.QIcon())

            for user in rooms[room]:
                if user.username.strip() == "":
                    continue
                useritem = QtGui.QStandardItem(user.username)
                isController = user.isController()
                sameRoom = room == currentUser.room
                if sameRoom:
                    isReadyWithFile = user.isReadyWithFile()
                else:
                    isReadyWithFile = None
                useritem.setData(isController, Qt.UserRole + constants.USERITEM_CONTROLLER_ROLE)
                useritem.setData(isReadyWithFile, Qt.UserRole + constants.USERITEM_READY_ROLE)
                mismatches = []
                tokens = theme.tokens(getattr(self, "_dark", False))
                if user.file:
                    filesizeitem = QtGui.QStandardItem(formatSize(user.file['size']))
                    filedurationitem = QtGui.QStandardItem("({})".format(formatTime(user.file['duration'])))
                    for quietItem in (filesizeitem, filedurationitem):
                        quietItem.setForeground(QtGui.QBrush(QtGui.QColor(tokens["muted"])))
                    filename = user.file['name']
                    if isURL(filename):
                        filename = urllib.parse.unquote(filename)
                    filenameitem = QtGui.QStandardItem(filename)
                    fileSwitchState = self.getFileSwitchState(user.file['name']) if room == currentUser.room else None
                    if fileSwitchState != constants.FILEITEM_SWITCH_NO_SWITCH:
                        filenameTooltip = getMessage("switch-to-file-tooltip").format(filename)
                    else:
                        filenameTooltip = filename
                    filenameitem.setToolTip(filenameTooltip)
                    filenameitem.setData(fileSwitchState, Qt.UserRole + constants.FILEITEM_SWITCH_ROLE)
                    if currentUser.file:
                        sameName = sameFilename(user.file['name'], currentUser.file['name'])
                        sameSize = sameFilesize(user.file['size'], currentUser.file['size'])
                        sameDuration = sameFileduration(user.file['duration'], currentUser.file['duration'])
                        differentItemColor = tokens["warn"]
                        if sameRoom:
                            if not sameName:
                                mismatches.append("name")
                                filenameitem.setForeground(QtGui.QBrush(QtGui.QColor(differentItemColor)))
                            if not sameSize:
                                mismatches.append("size")
                                if formatSize(user.file['size']) == formatSize(currentUser.file['size']):
                                    filesizeitem = QtGui.QStandardItem(formatSize(user.file['size'], precise=True))
                                filesizeitem.setForeground(QtGui.QBrush(QtGui.QColor(differentItemColor)))
                            if not sameDuration:
                                mismatches.append("duration")
                                filedurationitem.setForeground(QtGui.QBrush(QtGui.QColor(differentItemColor)))
                else:
                    filenameitem = QtGui.QStandardItem(getMessage("nofile-note"))
                    filedurationitem = QtGui.QStandardItem("")
                    filesizeitem = QtGui.QStandardItem("")
                    if room == currentUser.room:
                        filenameitem.setForeground(QtGui.QBrush(QtGui.QColor(tokens["muted"])))
                font = QtGui.QFont()
                if currentUser.username == user.username:
                    font.setWeight(QtGui.QFont.Bold)
                    self.updateReadyState(currentUser.isReadyWithFile())
                if isControlledRoom and not isController:
                    useritem.setForeground(QtGui.QBrush(QtGui.QColor(constants.STYLE_NOTCONTROLLER_COLOR)))
                useritem.setFont(font)
                useritem.setData(mismatches, Qt.UserRole + constants.USERITEM_MISMATCH_ROLE)
                if sameRoom:
                    self._columnNeeds.update(mismatches)
                    if not user.file:
                        self._columnNeeds.add("name")
                useritem.setData(
                    " \u00b7 ".join(filter(None, [filenameitem.text(), filedurationitem.text().strip("()"), filesizeitem.text()]))
                    if user.file else None, Qt.UserRole + constants.USERITEM_FILEINFO_ROLE)
                if mismatches:
                    detail = ", ".join(getMessage("people-different-" + kind) for kind in mismatches).capitalize()
                    useritem.setToolTip(detail)
                    filenameitem.setForeground(QtGui.QBrush(QtGui.QColor(tokens["warn"])))
                    filenameitem.setToolTip("{}\n{}".format(filenameitem.toolTip(), detail))
                useritem.setFlags(useritem.flags() & ~Qt.ItemIsEditable)
                filenameitem.setFlags(filenameitem.flags() & ~Qt.ItemIsEditable)
                filesizeitem.setFlags(filesizeitem.flags() & ~Qt.ItemIsEditable)
                filedurationitem.setFlags(filedurationitem.flags() & ~Qt.ItemIsEditable)
                subtitleText = self._syncplayClient.subtitleFor(user.username) if sameRoom and user.file else None
                subtitleitem = QtGui.QStandardItem(subtitleText if isinstance(subtitleText, str) else "")
                subtitleitem.setForeground(QtGui.QBrush(QtGui.QColor(tokens["muted"])))
                subtitleitem.setToolTip(subtitleitem.text())
                subtitleitem.setFlags(subtitleitem.flags() & ~Qt.ItemIsEditable)
                roomitem.appendRow((useritem, filesizeitem, filedurationitem, filenameitem, subtitleitem))
        self.listTreeModel = self._usertreebuffer
        self.listTreeView.setModel(self.listTreeModel)
        self.listTreeView.setItemDelegate(ModernUserlistDelegate(view=self.listTreeView))
        self.listTreeView.setItemsExpandable(False)
        self.listTreeView.setRootIsDecorated(False)
        self.listTreeView.expandAll()
        self.listTreeView.setTextElideMode(Qt.ElideMiddle)
        header = self.listTreeView.header()
        header.show()
        header.setStretchLastSection(False)
        header.setSectionsMovable(False)
        if hasattr(header, "setSectionResizeMode"):
            resize = QtWidgets.QHeaderView
            header.setSectionResizeMode(0, resize.Interactive)
            header.setSectionResizeMode(1, resize.ResizeToContents)
            header.setSectionResizeMode(2, resize.ResizeToContents)
            header.setSectionResizeMode(3, resize.Stretch)
            header.setSectionResizeMode(4, resize.Stretch)
        if not getattr(self, "_nameColumnSized", False):
            header.resizeSection(0, 190)
            self._nameColumnSized = True
        self.updateListGeometry()
        self._applyFileColumns()
        self._updateFileLine(currentUser, rooms)
        self._welcomeNote(currentUser, rooms)
        self._syncplayClient.fileSwitch.setFilenameWatchlist(self.newWatchlist)
        self.fillRoomsCombobox()
        self.updateStatusBar(currentUser, rooms)

    def editRoom(self):
        """Show the room box to type another room; it folds away again once you join."""
        self.roomLink.hide()
        self.roomFrame.show()
        self.roomsCombobox.setFocus()
        self.roomsCombobox.lineEdit().selectAll()

    def _showRoomLink(self, room):
        self.roomFrame.hide()
        self.roomLink.setText(getMessage("chip-room-link").format(room) if room else "")
        self.roomLink.show()

    _MENU_ICONS = (
        ("openAction", "folder"), ("openPlaylistAction", "list"), ("reloadPlaylistAction", "refresh"), ("torboxAction", "library"),
        ("connectionSettingsAction", "tune"), ("skipStartAction", "skip"), ("reconnectAction", "refresh"), ("exitAction", "power"),
        ("syncCheckAction", "clock"), ("shareSubtitleFileAction", "plus"), ("loadSharedSubtitleAction", "link"),
        ("editroomsAction", "list"), ("updateSourceAction", "link"), ("updateLogAction", "list"), ("shortcutsAction", "plus"),
        ("uninstallAction", "trash"), ("userguideAction", "help"), ("updateAction", "download"),
        ("reopenPlayerAction", "refresh"), ("diagnosticsAction", "info"), ("subDelayEarlierAction", "chevron"), ("subDelayLaterAction", "chevron"),
        ("subDelayResetAction", "undo"),
    )

    def _iconAllMenuItems(self, window):
        """One icon language across the menus: every plain item gets a line icon in the text colour (ticked switches keep their tick)."""
        tokens = theme.tokens(theme.isDarkPalette(QtWidgets.QApplication.palette()))
        for attribute, name in self._MENU_ICONS:
            action = getattr(window, attribute, None)
            if action is not None and not action.isCheckable():
                action.setIcon(icons.icon(name, tokens["text"], 16))

    def _welcomeNote(self, currentUser, rooms):
        """Once per start: say who is already in your room (so joining from a link feels like arriving somewhere)."""
        if getattr(self, "_welcomed", False):
            return
        others = [user.username for user in rooms.get(currentUser.room, []) if user.username.strip() and user.username != currentUser.username]
        self._welcomed = True
        if others:
            self.showMessage(getMessage("welcome-others-here").format(", ".join(others[:4]) + (" and {} more".format(len(others) - 4) if len(others) > 4 else "")))
        else:
            self.showMessage(getMessage("welcome-first-here"))

    def _applyFileColumns(self):
        """Who is on which file and subtitle is always shown; size and length only appear when someone's differs, and a
        narrow window keeps just the people, their file and their ready state."""
        needs = getattr(self, "_columnNeeds", set())
        narrow = bool(getattr(self, "_narrow", False))
        self.listTreeView.setColumnHidden(1, True)   # A different size or length turns the file amber instead (details in its tooltip)
        self.listTreeView.setColumnHidden(2, True)
        self.listTreeView.setColumnHidden(3, False)
        self.listTreeView.setColumnHidden(4, narrow)
        self.listTreeView.header().setVisible(True)

    def subtitleInfoChanged(self):
        """Someone announced a subtitle (or it stopped applying): redraw the table."""
        client = self._syncplayClient
        if client:
            try:
                client.showUserList()
            except Exception:
                pass

    def _updateFileLine(self, currentUser, rooms):
        """The table names every file itself, so the line above it stays empty."""
        self._fileLineText = ""
        self._elideFileLine()

    def _elideFileLine(self):
        text = getattr(self, "_fileLineText", "")
        self.listlabel.setFullText(text)
        self.listlabel.setVisible(bool(text))

    @needsClient
    def undoPlaylistChange(self):
        self._syncplayClient.playlist.undoPlaylistChange()

    @needsClient
    def shuffleRemainingPlaylist(self):
        self._syncplayClient.playlist.shuffleRemainingPlaylist()

    @needsClient
    def shuffleEntirePlaylist(self):
        self._syncplayClient.playlist.shuffleEntirePlaylist()

    def _markFileWatchedViaContext(self, filePath: str) -> None:
        self._markFilesWatchedViaContext([filePath])

    def _markFileUnwatchedViaContext(self, filePath: str) -> None:
        self._markFilesUnwatchedViaContext([filePath])

    def _markFilesWatchedViaContext(self, filePaths) -> None:
        self._syncplayClient.watched.userMarkFilesWatched(filePaths)
        self.playlist.updatePlaylistIndexIcon()

    def _markFilesUnwatchedViaContext(self, filePaths) -> None:
        self._syncplayClient.watched.userMarkFilesUnwatched(filePaths)
        self.playlist.updatePlaylistIndexIcon()

    def _addFileToPlaylistAtIndexViaContext(self, filePath: str, index: int) -> None:
        self.addFileToPlaylist(filePath, index=index)
        self.playlistChangeCheck()
        self.playlist.updatePlaylistIndexIcon()

    def _getPreviousFileMenuFilenameLabel(self, menu, filename):
        try:
            return menu.fontMetrics().elidedText(filename, Qt.ElideMiddle, 320)
        except Exception:
            if len(filename) <= 70:
                return filename
            return "{}...{}".format(filename[:40], filename[-27:])

    def _getPreviousFileSubmenu(self, menu, filenameLabel):
        return menu.addMenu(getMessage("previous-file-menu-section-label").format(filenameLabel))

    @needsClient
    def openPlaylistMenu(self, position):
        def addSeenUnseenItems(pathFound, menu):
            pathFound = getCorrectedPathForFile(pathFound)
            if self._syncplayClient.watched.canMarkAsUnwatched(pathFound):
                menu.addAction(menuIcon("no_eye"), getMessage("mark-as-unwatched-menu-label"), lambda p=pathFound: self._markFileUnwatchedViaContext(p))  # TODO: Move to language
            elif self._syncplayClient.watched.canMarkAsWatched(pathFound):
                menu.addAction(menuIcon("yes_eye"), getMessage("mark-as-watched-menu-label"), lambda p=pathFound: self._markFileWatchedViaContext(p))  # TODO: Move to language

        def addSkippedFileItems(itemIndex, menu):
            playlistItems = [self.playlist.item(i).text() for i in range(self.playlist.count())]
            playlistSkipWarnings = self._syncplayClient.watched.getPlaylistSkipWarnings(playlistItems)
            skipWarning = playlistSkipWarnings.get(itemIndex)
            if not skipWarning:
                return
            skippedFilePath = self._syncplayClient.watched.findSkippedFilePath(skipWarning)
            if not skippedFilePath:
                return

            skippedFilename = os.path.basename(skippedFilePath)
            skippedFilenameLabel = self._getPreviousFileMenuFilenameLabel(menu, skippedFilename)
            previousFileMenu = self._getPreviousFileSubmenu(menu, skippedFilenameLabel)
            previousFileMenu.addAction(menuIcon("film_go"), getMessage("openmedia-menu-label"), lambda p=skippedFilePath: self.openFile(p, resetPosition=True, fromUser=True))
            previousFileMenu.addAction(menuIcon("folder_film"), getMessage("open-containing-folder"), lambda p=skippedFilePath: utils.open_system_file_browser(p))

            if not self._syncplayClient.watched.playlistContainsSkippedFile(playlistItems, skipWarning):
                if not self.isItemInPlaylist(skippedFilename):
                    previousFileMenu.addAction(menuIcon("film_add"), getMessage("add-previous-file-to-playlist-menu-label"), lambda p=skippedFilePath, i=itemIndex: self._addFileToPlaylistAtIndexViaContext(p, i))

            if self._syncplayClient.watched.canMarkAsWatched(skippedFilePath):
                previousFileMenu.addAction(menuIcon("yes_eye"), getMessage("mark-previous-file-as-watched-menu-label"), lambda p=skippedFilePath: self._markFileWatchedViaContext(p))

        indexes = self.playlist.selectedIndexes()
        selectedRows = sorted(set(index.row() for index in indexes))
        if selectedRows:
            item = indexes[0]
        else:
            item = None
        menu = QtWidgets.QMenu()

        if item:
            firstFile = item.sibling(item.row(), 0).data()
            pathFound = self._syncplayClient.fileSwitch.findFilepath(firstFile) if not isURL(firstFile) else None
            if self._syncplayClient.userlist.currentUser.file is None or firstFile != self._syncplayClient.userlist.currentUser.file["name"]:
                if isURL(firstFile):
                    menu.addAction(menuIcon("world_go"), getMessage("openstreamurl-menu-label"), lambda: self.openFile(firstFile, resetPosition=True, fromUser=True))
                elif pathFound:
                        menu.addAction(menuIcon("film_go"), getMessage("openmedia-menu-label"), lambda: self.openFile(pathFound, resetPosition=True, fromUser=True))
            if pathFound:
                menu.addAction(menuIcon("folder_film"),
                               getMessage('open-containing-folder'),
                               lambda: utils.open_system_file_browser(pathFound))
                if len(selectedRows) == 1:
                    addSeenUnseenItems(pathFound, menu)
            if len(selectedRows) > 1:
                selectedFilePaths = []
                for row in selectedRows:
                    filename = self.playlist.item(row).text()
                    selectedPath = self._syncplayClient.fileSwitch.findFilepath(filename) if not isURL(filename) else None
                    if selectedPath:
                        selectedFilePaths.append(getCorrectedPathForFile(selectedPath))
                if any(self._syncplayClient.watched.canMarkAsWatched(path) for path in selectedFilePaths):
                    menu.addAction(menuIcon("yes_eye"), getMessage("mark-as-watched-menu-label"), lambda paths=selectedFilePaths: self._markFilesWatchedViaContext(paths))
                if any(self._syncplayClient.watched.canMarkAsUnwatched(path) for path in selectedFilePaths):
                    menu.addAction(menuIcon("no_eye"), getMessage("mark-as-unwatched-menu-label"), lambda paths=selectedFilePaths: self._markFilesUnwatchedViaContext(paths))
            else:
                addSkippedFileItems(item.row(), menu)
            if self._syncplayClient.isUntrustedTrustableURI(firstFile):
                domain = utils.getDomainFromURL(firstFile)
                if domain:
                    menu.addAction(menuIcon("shield_add"), getMessage("addtrusteddomain-menu-label").format(domain), lambda: self.addTrustedDomain(domain))
            menu.addAction(menuIcon("delete"), getMessage("removefromplaylist-menu-label"), lambda: self.deleteSelectedPlaylistItems())
            menu.addSeparator()
        menu.addAction(menuIcon("arrow_switch"), getMessage("shuffleremainingplaylist-menu-label"), lambda: self.shuffleRemainingPlaylist())
        menu.addAction(menuIcon("arrow_switch"), getMessage("shuffleentireplaylist-menu-label"), lambda: self.shuffleEntirePlaylist())
        menu.addAction(menuIcon("arrow_undo"), getMessage("undoplaylist-menu-label"), lambda: self.undoPlaylistChange())
        menu.addAction(menuIcon("film_edit"), getMessage("editplaylist-menu-label"), lambda: self.openEditPlaylistDialog())
        menu.addAction(menuIcon("film_add"), getMessage("addfilestoplaylist-menu-label"), lambda: self.OpenAddFilesToPlaylistDialog())
        menu.addAction(menuIcon("world_add"), getMessage("addurlstoplaylist-menu-label"), lambda: self.OpenAddURIsToPlaylistDialog())
        menu.addSeparator()
        lineColor = theme.tokens(theme.isDarkPalette(QtWidgets.QApplication.palette()))["text"]
        menu.addAction(icons.icon("list", lineColor, 16), getMessage("loadplaylistfromfile-menu-label"), lambda: self.OpenLoadPlaylistFromFileDialog())
        menu.addAction(icons.icon("shuffle", lineColor, 16), getMessage("loadshuffleplaylistfromfile-menu-label"), lambda: self.OpenLoadPlaylistFromFileDialog(shuffle=True))
        menu.addAction(icons.icon("download", lineColor, 16), getMessage("saveplaylisttofile-menu-label"), lambda: self.OpenSavePlaylistToFileDialog())
        menu.addSeparator()
        menu.addAction(menuIcon("film_folder_edit"), getMessage("setmediadirectories-menu-label"), lambda: self.openSetMediaDirectoriesDialog())
        menu.addAction(menuIcon("shield_edit"), getMessage("settrusteddomains-menu-label"), lambda: self.openSetTrustedDomainsDialog())
        menu.exec_(self.playlist.viewport().mapToGlobal(position))

    def openRoomMenu(self, position):
        # TODO: Deselect items after right click
        indexes = self.listTreeView.selectedIndexes()
        if len(indexes) > 0:
            item = self.listTreeView.selectedIndexes()[0]
        else:
            return

        menu = QtWidgets.QMenu()
        username = item.sibling(item.row(), 0).data()

        if len(username) < 15:
            shortUsername = username
        else:
            shortUsername = "{}...".format(username[0:12])

        if username == self._syncplayClient.userlist.currentUser.username:
            addUsersFileToPlaylistLabelText = getMessage("addyourfiletoplaylist-menu-label")
            addUsersStreamToPlaylistLabelText = getMessage("addyourstreamstoplaylist-menu-label")
        else:
            addUsersFileToPlaylistLabelText = getMessage("addotherusersfiletoplaylist-menu-label").format(shortUsername)
            addUsersStreamToPlaylistLabelText = getMessage("addotherusersstreamstoplaylist-menu-label").format(shortUsername)

        filename = item.sibling(item.row(), 3).data()
        isUserRow = item.parent().row() != -1
        while item.parent().row() != -1:
            item = item.parent()
        roomToJoin = item.sibling(item.row(), 0).data()
        if roomToJoin != self._syncplayClient.getRoom():
            menu.addAction(getMessage("joinroom-menu-label").format(roomToJoin), lambda: self.joinRoom(roomToJoin))
        elif username and filename and filename != getMessage("nofile-note"):
            if self.config['sharedPlaylistEnabled'] and not self.isItemInPlaylist(filename):
                if isURL(filename):
                    menu.addAction(menuIcon("world_add"), addUsersStreamToPlaylistLabelText, lambda: self.addStreamToPlaylist(filename))
                else:
                    menu.addAction(menuIcon("film_add"), addUsersFileToPlaylistLabelText, lambda: self.addStreamToPlaylist(filename))

            if self._syncplayClient.userlist.currentUser.file is None or filename != self._syncplayClient.userlist.currentUser.file["name"]:
                if isURL(filename):
                    menu.addAction(menuIcon("world_go"), getMessage("openusersstream-menu-label").format(shortUsername), lambda: self.openFile(filename, resetPosition=False, fromUser=True))
                else:
                    pathFound = self._syncplayClient.fileSwitch.findFilepath(filename)
                    if pathFound:
                        menu.addAction(menuIcon("film_go"), getMessage("openusersfile-menu-label").format(shortUsername), lambda: self.openFile(pathFound, resetPosition=False, fromUser=True))
            if self._syncplayClient.isUntrustedTrustableURI(filename):
                domain = utils.getDomainFromURL(filename)
                if domain:
                    menu.addAction(menuIcon("shield_add"), getMessage("addtrusteddomain-menu-label").format(domain), lambda: self.addTrustedDomain(domain))

            if not isURL(filename) and filename != getMessage("nofile-note"):
                path = self._syncplayClient.fileSwitch.findFilepath(filename)
                if path:
                    menu.addAction(menuIcon("folder_film"), getMessage('open-containing-folder'), lambda: utils.open_system_file_browser(path))

        if isUserRow and roomToJoin == self._syncplayClient.getRoom() and self._syncplayClient.userlist.currentUser.canControl() and self._syncplayClient.userlist.isReadinessSupported(requiresOtherUsers=False) and self._syncplayClient.serverFeatures["setOthersReadiness"]:
            if self._syncplayClient.userlist.isReady(username):
                addSetUserAsReadyText = getMessage("setasnotready-menu-label").format(shortUsername)
                menu.addAction(menuIcon("cross"), addSetUserAsReadyText, lambda: self._syncplayClient.setOthersReadiness(username, False))
            else:
                addSetUserAsNotReadyText = getMessage("setasready-menu-label").format(shortUsername)
                menu.addAction(menuIcon("tick"), addSetUserAsNotReadyText, lambda: self._syncplayClient.setOthersReadiness(username, True))
        menu.exec_(self.listTreeView.viewport().mapToGlobal(position))

    NARROW_WIDTH = 860  # Below the width the two-pane layout needs

    def resizeEvent(self, event):
        super(MainWindow, self).resizeEvent(event)
        self._applyNarrowMode(event.size().width() < self.NARROW_WIDTH)

    def _applyNarrowMode(self, narrow):
        """In a narrow window (docked beside the video) chat stacks above the people, the header buttons shrink to
        icons and the size/length columns hide, so everything stays usable."""
        if not hasattr(self, "libraryChip") or narrow == getattr(self, "_narrow", None):
            return
        self._narrow = narrow
        self.topSplit.setOrientation(Qt.Vertical if narrow else Qt.Horizontal)
        if narrow:
            self.topSplit.setSizes([210, 500])
        for chip, key in ((self.subtitlesChip, "chip-subtitles-label"), (self.libraryChip, "chip-library-label"),
                          (self.inviteChip, "chip-invite-label"), (self.privateChip, "chip-private-label")):
            chip.setText("" if narrow else getMessage(key))
        self._updateVoiceChip()
        self._applyFileColumns()
        self._elideFileLine()
        QtCore.QTimer.singleShot(60, self._fitPlaylist)  # Once the new layout has its real size

    def updateListGeometry(self):
        try:
            roomtocheck = 0
            while self.listTreeModel.item(roomtocheck):
                self.listTreeView.setFirstColumnSpanned(roomtocheck, self.listTreeView.rootIndex(), True)
                roomtocheck += 1
            self.listTreeView.expandAll()
            return
            if IsPySide6 or IsPySide2:
                self.listTreeView.header().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
                self.listTreeView.header().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
                self.listTreeView.header().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
                self.listTreeView.header().setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
            if IsPySide:
                self.listTreeView.header().setResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
                self.listTreeView.header().setResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
                self.listTreeView.header().setResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
                self.listTreeView.header().setResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
            NarrowTabsWidth = self.listTreeView.header().sectionSize(0)+self.listTreeView.header().sectionSize(1)+self.listTreeView.header().sectionSize(2)
            if self.listTreeView.header().width() < (NarrowTabsWidth+self.listTreeView.header().sectionSize(3)):
                self.listTreeView.header().resizeSection(3, self.listTreeView.header().width()-NarrowTabsWidth)
            else:
                if IsPySide6 or IsPySide2:
                    self.listTreeView.header().setSectionResizeMode(3, QtWidgets.QHeaderView.Stretch)
                if IsPySide:
                    self.listTreeView.header().setResizeMode(3, QtWidgets.QHeaderView.Stretch)
            self.listTreeView.expandAll()
        except:
            pass

    def updateReadyState(self, newState):
        oldState = self.readyPushButton.isChecked()
        if newState != oldState and newState is not None:
            self.readyPushButton.blockSignals(True)
            self.readyPushButton.setChecked(newState)
            self.readyPushButton.blockSignals(False)
        self.updateReadyIcon()

    @needsClient
    def playlistItemClicked(self, item):
        # TODO: Integrate into client.py code
        filename = item.data()
        if self._isTryingToChangeToCurrentFile(filename):
            return
        if isURL(filename):
            self._syncplayClient.openFile(filename, resetPosition=True)
        else:
            pathFound = self._syncplayClient.fileSwitch.findFilepath(filename, highPriority=True)
            if pathFound:
                self._syncplayClient.openFile(pathFound, resetPosition=True)
            else:
                self._syncplayClient.ui.showErrorMessage(getMessage("cannot-find-file-for-playlist-switch-error").format(filename))

    def _isTryingToChangeToCurrentFile(self, filename):
        if self._syncplayClient.userlist.currentUser.file and filename == self._syncplayClient.userlist.currentUser.file["name"]:
            self.showDebugMessage("File change request ignored (Syncplay should not be asked to change to current filename)")
            return True
        else:
            return False

    def roomClicked(self, item):
        username = item.sibling(item.row(), 0).data()
        filename = item.sibling(item.row(), 3).data()
        while item.parent().row() != -1:
            item = item.parent()
        roomToJoin = item.sibling(item.row(), 0).data()
        if roomToJoin != self._syncplayClient.getRoom():
            self.joinRoom(item.sibling(item.row(), 0).data())
        elif username and filename and username != self._syncplayClient.userlist.currentUser.username:
            if self._isTryingToChangeToCurrentFile(filename):
                return
            if isURL(filename):
                self._syncplayClient.openFile(filename)
            else:
                pathFound = self._syncplayClient.fileSwitch.findFilepath(filename, highPriority=True)
                if pathFound:
                    self._syncplayClient.openFile(pathFound)
                else:
                    self._syncplayClient.fileSwitch.updateInfo()
                    self.showErrorMessage(getMessage("switch-file-not-found-error").format(filename))

    @needsClient
    def userListChange(self):
        self._syncplayClient.showUserList()

    def fileSwitchFoundFiles(self):
        self._syncplayClient.showUserList()
        self.playlist.updatePlaylistIndexIcon()

    def updateRoomName(self, room=""):
        self.roomsCombobox.setEditText(room)
        try:
            if self.config['autosaveJoinsToList']:
                self.addRoomToList(room)
        except:
            pass

    def showDebugMessage(self, message):
        print(message)

    def showErrorMessage(self, message, criticalerror=False):
        message = str(message)
        if criticalerror:
            QtWidgets.QMessageBox.critical(self, branding.NAME, message)
        message = message.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")
        message = message.replace("&lt;a href=&quot;https://syncplay.pl/trouble&quot;&gt;", '<a href="https://syncplay.pl/trouble">').replace("&lt;/a&gt;", "</a>")
        message = message.replace("&lt;a href=&quot;https://mpv.io/&quot;&gt;", '<a href="https://mpv.io/">').replace("&lt;/a&gt;", "</a>")
        message = message.replace("&lt;a href=&quot;https://github.com/stax76/mpv.net/&quot;&gt;", '<a href="https://github.com/stax76/mpv.net/">').replace("&lt;/a&gt;", "</a>")
        message = message.replace("\n", "<br />")
        self._feedBlock('<div style="color: {}; margin-top: 4px; margin-bottom: 4px;"><b>!</b> {}</div>'.format(
            self._feedTokens()["danger"], message))

    @needsClient
    def joinRoom(self, room=None):
        if room is None:
            room = self.roomsCombobox.currentText()
        if room == "":
            if self._syncplayClient.userlist.currentUser.file:
                room = self._syncplayClient.userlist.currentUser.file["name"]
            else:
                room = self._syncplayClient.defaultRoom
        self.roomsCombobox.setEditText(room)
        if room != self._syncplayClient.getRoom():
            self._syncplayClient.setRoom(room, resetAutoplay=True)
            self._syncplayClient.sendRoom()
            if self.config['autosaveJoinsToList']:
                self.addRoomToList(room)
        self._showRoomLink(room)

    def seekPositionDialog(self):
        seekTime, ok = QtWidgets.QInputDialog.getText(
            self, getMessage("seektime-menu-label"),
            getMessage("seektime-msgbox-label"), QtWidgets.QLineEdit.Normal,
            "0:00")
        if ok and seekTime != '':
            self.seekPosition(seekTime)

    def seekFromButton(self):
        self.seekPosition(self.seekInput.text())

    @needsClient
    def seekPosition(self, seekTime):
        s = re.match(constants.UI_SEEK_REGEX, seekTime)
        if s:
            sign = self._extractSign(s.group('sign'))
            t = utils.parseTime(s.group('time'))
            if t is None:
                return
            if sign:
                t = self._syncplayClient.getGlobalPosition() + sign * t
            self._syncplayClient.setPosition(t)
        else:
            self.showErrorMessage(getMessage("invalid-seek-value"))

    @needsClient
    def undoSeek(self):
        tmp_pos = self._syncplayClient.getPlayerPosition()
        self._syncplayClient.setPosition(self._syncplayClient.playerPositionBeforeLastSeek)
        self._syncplayClient.playerPositionBeforeLastSeek = tmp_pos

    @needsClient
    def togglePause(self):
        self._syncplayClient.setPaused(not self._syncplayClient.getPlayerPaused())

    @needsClient
    def play(self):
        self._syncplayClient.setPaused(False)

    @needsClient
    def pause(self):
        self._syncplayClient.setPaused(True)

    @needsClient
    def reconnectToServer(self):
        """
        Trigger a manual reconnection using the client's built-in retry mechanism.
        This is simpler and more reliable than doing a complete restart.
        """
        try:
            if self._syncplayClient:
                self._syncplayClient.manualReconnect()
            else:
                self.showErrorMessage(getMessage("connection-failed-notification"))
        except Exception as e:
            self.showErrorMessage(getMessage("reconnect-failed-error").format(str(e)))

    def exitSyncplay(self):
        self._syncplayClient.stop()

    def closeEvent(self, event):
        configDir = getattr(self, "config", {}).get("configDir")  # No config yet if the window closes before a client attaches
        if configDir:
            instance.release(configDir)
        self.exitSyncplay()
        self.saveSettings()

    def loadMediaBrowseSettings(self):
        settings = QSettings("Syncplay", "MediaBrowseDialog")
        settings.beginGroup("MediaBrowseDialog")
        self.mediadirectory = settings.value("mediadir", "")
        settings.endGroup()

    def saveMediaBrowseSettings(self):
        settings = QSettings("Syncplay", "MediaBrowseDialog")
        settings.beginGroup("MediaBrowseDialog")
        settings.setValue("mediadir", self.mediadirectory)
        settings.endGroup()

    def getInitialMediaDirectory(self, includeUserSpecifiedDirectories=True):
        if IsPySide:
            if self.config["mediaSearchDirectories"] and os.path.isdir(self.config["mediaSearchDirectories"][0]) and includeUserSpecifiedDirectories:
                defaultdirectory = self.config["mediaSearchDirectories"][0]
            elif includeUserSpecifiedDirectories and os.path.isdir(self.mediadirectory):
                defaultdirectory = self.mediadirectory
            elif os.path.isdir(QtGui.QDesktopServices.storageLocation(QtGui.QDesktopServices.MoviesLocation)):
                defaultdirectory = QtGui.QDesktopServices.storageLocation(QtGui.QDesktopServices.MoviesLocation)
            elif os.path.isdir(QtGui.QDesktopServices.storageLocation(QtGui.QDesktopServices.HomeLocation)):
                defaultdirectory = QtGui.QDesktopServices.storageLocation(QtGui.QDesktopServices.HomeLocation)
            else:
                defaultdirectory = ""
        elif IsPySide6 or IsPySide2:
            if self.config["mediaSearchDirectories"] and os.path.isdir(self.config["mediaSearchDirectories"][0]) and includeUserSpecifiedDirectories:
                defaultdirectory = self.config["mediaSearchDirectories"][0]
            elif includeUserSpecifiedDirectories and os.path.isdir(self.mediadirectory):
                defaultdirectory = self.mediadirectory
            elif os.path.isdir(QStandardPaths.standardLocations(QStandardPaths.MoviesLocation)[0]):
                defaultdirectory = QStandardPaths.standardLocations(QStandardPaths.MoviesLocation)[0]
            elif os.path.isdir(QStandardPaths.standardLocations(QStandardPaths.HomeLocation)[0]):
                defaultdirectory = QStandardPaths.standardLocations(QStandardPaths.HomeLocation)[0]
            else:
                defaultdirectory = ""
        return defaultdirectory

    @needsClient
    def browseMediapath(self):
        if self._syncplayClient._player.customOpenDialog == True:
            self._syncplayClient._player.openCustomOpenDialog()
            return

        self.loadMediaBrowseSettings()
        if isMacOS() and IsPySide:
            options = QtWidgets.QFileDialog.Options(QtWidgets.QFileDialog.DontUseNativeDialog)
        else:
            options = QtWidgets.QFileDialog.Options()
        self.mediadirectory = ""
        currentdirectory = os.path.dirname(self._syncplayClient.userlist.currentUser.file["path"]) if self._syncplayClient.userlist.currentUser.file else None
        if currentdirectory and os.path.isdir(currentdirectory):
            defaultdirectory = currentdirectory
        else:
            defaultdirectory = self.getInitialMediaDirectory()
        browserfilter = "All files (*)"
        fileName, filtr = QtWidgets.QFileDialog.getOpenFileName(
            self, getMessage("browseformedia-label"), defaultdirectory,
            browserfilter, "", options)
        if fileName:
            if isWindows():
                fileName = fileName.replace("/", "\\")
            self.mediadirectory = os.path.dirname(fileName)
            self._syncplayClient.fileSwitch.setCurrentDirectory(self.mediadirectory)
            self.saveMediaBrowseSettings()
            self._syncplayClient.openFile(fileName, resetPosition=False, fromUser=True)

    @needsClient
    def OpenAddFilesToPlaylistDialog(self):
        if self._syncplayClient._player.customOpenDialog == True:
            self._syncplayClient._player.openCustomOpenDialog()
            return

        self.loadMediaBrowseSettings()
        if isMacOS() and IsPySide:
            options = QtWidgets.QFileDialog.Options(QtWidgets.QFileDialog.DontUseNativeDialog)
        else:
            options = QtWidgets.QFileDialog.Options()
        self.mediadirectory = ""
        currentdirectory = os.path.dirname(self._syncplayClient.userlist.currentUser.file["path"]) if self._syncplayClient.userlist.currentUser.file else None
        if currentdirectory and os.path.isdir(currentdirectory):
            defaultdirectory = currentdirectory
        else:
            defaultdirectory = self.getInitialMediaDirectory()
        browserfilter = "All files (*)"
        fileNames, filtr = QtWidgets.QFileDialog.getOpenFileNames(
            self, getMessage("browseformedia-label"), defaultdirectory,
            browserfilter, "", options)
        self.updatingPlaylist = True
        if fileNames:
            for fileName in fileNames:
                if isWindows():
                    fileName = fileName.replace("/", "\\")
                self.mediadirectory = os.path.dirname(fileName)
                self._syncplayClient.fileSwitch.setCurrentDirectory(self.mediadirectory)
                self.saveMediaBrowseSettings()
                self.addFileToPlaylist(fileName)
        self.updatingPlaylist = False
        self.playlist.updatePlaylist(self.getPlaylistState())

    @needsClient
    def OpenLoadPlaylistFromFileDialog(self, shuffle=False):
        self.loadMediaBrowseSettings()
        if isMacOS() and IsPySide:
            options = QtWidgets.QFileDialog.Options(QtWidgets.QFileDialog.DontUseNativeDialog)
        else:
            options = QtWidgets.QFileDialog.Options()
        self.mediadirectory = ""
        currentdirectory = os.path.dirname(self._syncplayClient.userlist.currentUser.file["path"]) if self._syncplayClient.userlist.currentUser.file else None
        if currentdirectory and os.path.isdir(currentdirectory):
            defaultdirectory = currentdirectory
        else:
            defaultdirectory = self.getInitialMediaDirectory()
        browserfilter = "Playlists (*.txt *.m3u8)"
        filepath, filtr = QtWidgets.QFileDialog.getOpenFileName(
            self, "Load playlist from file", defaultdirectory,
            browserfilter, "", options) # TODO: Note Shuffle and move to messages_en
        if os.path.isfile(filepath):
            self._syncplayClient.playlist.loadPlaylistFromFile(filepath, shuffle=shuffle)
            self.playlist.updatePlaylist(self.getPlaylistState())
            self._rememberPlaylistFile(filepath)

    def _rememberPlaylistFile(self, filepath):
        """So "Reload playlist file" knows which file to read again (also after a restart)."""
        self._lastPlaylistFile = filepath
        try:
            secrets.save(playlistfile.SETTING, filepath, self.config.get("configDir"))
        except (OSError, TypeError):
            pass
        self.reloadPlaylistAction.setEnabled(True)

    @needsClient
    def reloadPlaylistFile(self):
        """Read the last playlist file again (handy when another program rewrites it) and replace the shared playlist."""
        path = getattr(self, "_lastPlaylistFile", None)
        if not path:
            self.showMessage(getMessage("playlist-reload-none-notification"))
            return
        found = playlistfile.entries(path)
        if found is None:
            self.showMessage(getMessage("playlist-reload-missing-notification").format(path))
            return
        if not found:
            self.showMessage(getMessage("playlist-reload-empty-notification").format(os.path.basename(path)))
            return
        self._syncplayClient.playlist.loadPlaylistFromFile(path)
        self.playlist.updatePlaylist(self.getPlaylistState())
        self.showMessage(getMessage("playlist-reloaded-notification").format(len(found), os.path.basename(path)))

    @needsClient
    def OpenSavePlaylistToFileDialog(self):
        self.loadMediaBrowseSettings()
        if isMacOS() and IsPySide:
            options = QtWidgets.QFileDialog.Options(QtWidgets.QFileDialog.DontUseNativeDialog)
        else:
            options = QtWidgets.QFileDialog.Options()
        self.mediadirectory = ""
        currentdirectory = os.path.dirname(self._syncplayClient.userlist.currentUser.file["path"]) if self._syncplayClient.userlist.currentUser.file else None
        if currentdirectory and os.path.isdir(currentdirectory):
            defaultdirectory = currentdirectory
        else:
            defaultdirectory = self.getInitialMediaDirectory()
        browserfilter = "Playlist (*.txt)"
        filepath, filtr = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save playlist to file", defaultdirectory,
            browserfilter, "", options) # TODO: Move to messages_en
        if filepath:
            self._syncplayClient.playlist.savePlaylistToFile(filepath)

    @needsClient
    def OpenAddURIsToPlaylistDialog(self):
        URIsDialog = QtWidgets.QDialog()
        URIsDialog.setWindowTitle(getMessage("adduris-msgbox-label"))
        URIsLayout = QtWidgets.QGridLayout()
        URIsLabel = QtWidgets.QLabel(getMessage("adduris-msgbox-label"))
        URIsLayout.addWidget(URIsLabel, 0, 0, 1, 1)
        URIsTextbox = QtWidgets.QPlainTextEdit()
        URIsTextbox.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)
        URIsLayout.addWidget(URIsTextbox, 1, 0, 1, 1)
        URIsButtonBox = QtWidgets.QDialogButtonBox()
        URIsButtonBox.setOrientation(Qt.Horizontal)
        URIsButtonBox.setStandardButtons(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        URIsButtonBox.accepted.connect(URIsDialog.accept)
        URIsButtonBox.rejected.connect(URIsDialog.reject)
        URIsLayout.addWidget(URIsButtonBox, 2, 0, 1, 1)
        URIsDialog.setLayout(URIsLayout)
        URIsDialog.setModal(True)
        if isWindows() and IsPySide6:
            URIsDialog.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowSystemMenuHint | Qt.WindowCloseButtonHint | Qt.CustomizeWindowHint)
        else:
            URIsDialog.setWindowFlags(URIsDialog.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        URIsDialog.show()
        result = URIsDialog.exec_()
        if result == QtWidgets.QDialog.Accepted:
            URIsToAdd = utils.convertMultilineStringToList(URIsTextbox.toPlainText())
            self.updatingPlaylist = True
            for URI in URIsToAdd:
                URI = URI.rstrip()
                if URI != "":
                    self.addStreamToPlaylist(URI)
            self.updatingPlaylist = False

    def openEditRoomsDialog(self):
        RoomsDialog = QtWidgets.QDialog()
        RoomsLayout = QtWidgets.QGridLayout()
        RoomsTextbox = QtWidgets.QPlainTextEdit()
        RoomsDialog.setWindowTitle(getMessage("roomlist-msgbox-label"))
        RoomsPlaylistLabel = QtWidgets.QLabel(getMessage("roomlist-msgbox-label"))
        RoomsTextbox.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)
        RoomsTextbox.setPlainText(utils.getListAsMultilineString(self.config['roomList']))
        RoomsLayout.addWidget(RoomsPlaylistLabel, 0, 0, 1, 1)
        RoomsLayout.addWidget(RoomsTextbox, 1, 0, 1, 1)
        RoomsButtonBox = QtWidgets.QDialogButtonBox()
        RoomsButtonBox.setOrientation(Qt.Horizontal)
        RoomsButtonBox.setStandardButtons(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        RoomsButtonBox.accepted.connect(RoomsDialog.accept)
        RoomsButtonBox.rejected.connect(RoomsDialog.reject)
        RoomsLayout.addWidget(RoomsButtonBox, 2, 0, 1, 1)
        RoomsDialog.setLayout(RoomsLayout)
        RoomsDialog.setModal(True)
        if isWindows() and IsPySide6:
            RoomsDialog.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowSystemMenuHint | Qt.WindowCloseButtonHint | Qt.CustomizeWindowHint)
        else:
            RoomsDialog.setWindowFlags(RoomsDialog.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        RoomsDialog.show()
        result = RoomsDialog.exec_()
        if result == QtWidgets.QDialog.Accepted:
            newRooms = utils.convertMultilineStringToList(RoomsTextbox.toPlainText())
            newRooms = sorted(newRooms)
            self.relistRoomList(newRooms)
            self._syncplayClient.setRoomList(newRooms)

    def relistRoomList(self, newRooms):
        filteredNewRooms = [room for room in newRooms if room and not room.isspace()]
        self.config['roomList'] = filteredNewRooms
        self.fillRoomsCombobox()

    @needsClient
    def openEditPlaylistDialog(self):
        oldPlaylist = utils.getListAsMultilineString(self.getPlaylistState())
        editPlaylistDialog = QtWidgets.QDialog()
        editPlaylistDialog.setWindowTitle(getMessage("editplaylist-msgbox-label"))
        editPlaylistLayout = QtWidgets.QGridLayout()
        editPlaylistLabel = QtWidgets.QLabel(getMessage("editplaylist-msgbox-label"))
        editPlaylistLayout.addWidget(editPlaylistLabel, 0, 0, 1, 1)
        editPlaylistTextbox = QtWidgets.QPlainTextEdit(oldPlaylist)
        editPlaylistTextbox.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)
        editPlaylistLayout.addWidget(editPlaylistTextbox, 1, 0, 1, 1)
        editPlaylistButtonBox = QtWidgets.QDialogButtonBox()
        editPlaylistButtonBox.setOrientation(Qt.Horizontal)
        editPlaylistButtonBox.setStandardButtons(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        editPlaylistButtonBox.accepted.connect(editPlaylistDialog.accept)
        editPlaylistButtonBox.rejected.connect(editPlaylistDialog.reject)
        editPlaylistLayout.addWidget(editPlaylistButtonBox, 2, 0, 1, 1)
        editPlaylistDialog.setLayout(editPlaylistLayout)
        editPlaylistDialog.setModal(True)
        editPlaylistDialog.setMinimumWidth(600)
        editPlaylistDialog.setMinimumHeight(500)
        if isWindows() and IsPySide6:
            editPlaylistDialog.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowSystemMenuHint | Qt.WindowCloseButtonHint | Qt.CustomizeWindowHint)
        else:
            editPlaylistDialog.setWindowFlags(editPlaylistDialog.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        editPlaylistDialog.show()
        result = editPlaylistDialog.exec_()
        if result == QtWidgets.QDialog.Accepted:
            newPlaylist = utils.convertMultilineStringToList(editPlaylistTextbox.toPlainText())
            if newPlaylist != self.playlistState and self._syncplayClient and not self.updatingPlaylist:
                self.setPlaylist(newPlaylist)
                self._syncplayClient.playlist.changePlaylist(newPlaylist)
                self._syncplayClient.fileSwitch.updateInfo()

    def switchTheme(self, name):
        """Window > Theme: change the look right now and remember it for next time."""
        theme.chooseTheme(name)
        self.applyTheme()
        self._iconAllMenuItems(self)
        self.updateReadyIcon()
        try:
            self.outputbox.document().setDefaultStyleSheet("a {{color: {}; }}".format(theme.tokens(self._dark)["link"]))
            self._tickProgress()
            if self._syncplayClient:
                self._syncplayClient.showUserList()
        except Exception:
            pass
        for themeName, action in self.themeActions.items():
            action.setChecked(themeName == theme.chosenTheme())

    def applyTheme(self):
        self._dark = theme.applyApplicationTheme(QtWidgets.QApplication.instance())
        tokens = theme.tokens(self._dark)
        self.chatButton.setObjectName("sendButton")
        self.chatButton.setIcon(icons.icon("send", tokens["accentText"], 16))
        self.roomButton.setIcon(icons.icon("join", tokens["text"], 16))
        self.subtitlesChip.setIcon(icons.icon("subtitles", tokens["text"], 14))
        self.inviteChip.setIcon(icons.icon("invite", tokens["text"], 14))
        self.privateChip.setIcon(icons.icon("lock", tokens["text"], 14))
        self.sslButton.setIcon(icons.icon("lock", tokens["ready"], 16))
        self.libraryChip.setIcon(icons.icon("library", tokens["text"], 14))
        self.voiceChip.setIcon(icons.icon("mic", tokens["text"], 14))
        self.moreChip.setIcon(icons.icon("more", tokens["text"], 16))
        self.tuneButton.setIcon(icons.icon("tune", tokens["text"], 16))
        self.emojiButton.setIcon(icons.icon("smile", tokens["text"], 18))
        self.style().unpolish(self.chatButton)
        self.style().polish(self.chatButton)
        self.updateReadyIcon()
        self.updateAutoPlayIcon()
        # Frames were sized to their unstyled hints when built; let them grow to fit the themed controls
        self.roomButton.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Preferred)
        self.roomButton.setFixedWidth(self.roomButton.sizeHint().width() + 3)
        for frame in (self.roomFrame, self.chatFrame, self.autoplayFrame):
            frame.ensurePolished()
            frame.setMaximumHeight(16777215)
            frame.setMaximumHeight(frame.sizeHint().height())

    def buildStatusBar(self):
        bar = self.statusBar()
        bar.setSizeGripEnabled(False)
        self._connState, self._dotBright = "connecting", True
        self._dotTimer = QtCore.QTimer(self)
        self._dotTimer.timeout.connect(self._pulseStatusDot)
        self.connectionBanner = QtWidgets.QFrame()
        self.connectionBanner.setObjectName("banner")
        bannerLayout = QtWidgets.QHBoxLayout(self.connectionBanner)
        bannerLayout.setContentsMargins(12, 6, 8, 6)
        self.bannerLabel = QtWidgets.QLabel(getMessage("banner-lost"))
        self.bannerLabel.setObjectName("bannerText")
        self.bannerButton = QtWidgets.QPushButton(getMessage("banner-reconnect-button"))
        self.bannerButton.clicked.connect(self.reconnectToServer)
        bannerLayout.addWidget(self.bannerLabel, 1)
        bannerLayout.addWidget(self.bannerButton)
        self.connectionBanner.hide()
        self.updateBar = QtWidgets.QFrame()
        self.updateBar.setObjectName("updateBar")
        self.updateBar.setFixedHeight(42)
        updateLayout = QtWidgets.QHBoxLayout(self.updateBar)
        updateLayout.setContentsMargins(12, 4, 8, 4)
        self.updateBarLabel = QtWidgets.QLabel("")
        self.updateBarLabel.setObjectName("resumeText")
        self.updateRestartButton = QtWidgets.QPushButton(getMessage("update-bar-restart-button"))
        self.updateRestartButton.setProperty("tone", "blue")
        self.updateLaterButton = QtWidgets.QPushButton(getMessage("update-bar-later-button"))
        for button in (self.updateRestartButton, self.updateLaterButton):
            button.setFixedHeight(28)
            button.setCursor(Qt.PointingHandCursor)
            button.setStyleSheet("padding: 0 14px; min-height: 0;")
        self.updateRestartButton.clicked.connect(self.restartForUpdate)
        self.updateLaterButton.clicked.connect(self.updateBar.hide)
        updateLayout.addWidget(self.updateBarLabel, 1)
        updateLayout.addWidget(self.updateRestartButton)
        updateLayout.addWidget(self.updateLaterButton)
        self.updateBar.hide()
        self.mainLayout.insertWidget(1, self.updateBar)
        self._updateDownloading = False
        self.mainLayout.insertWidget(0, self.connectionBanner)
        self.resumeBar = QtWidgets.QFrame()
        self.resumeBar.setObjectName("resumeBar")
        self.resumeBar.setFixedHeight(42)
        resumeLayout = QtWidgets.QHBoxLayout(self.resumeBar)
        resumeLayout.setContentsMargins(12, 4, 8, 4)
        self.resumeLabel = QtWidgets.QLabel("")
        self.resumeLabel.setObjectName("resumeText")
        self.resumeContinue = QtWidgets.QPushButton(getMessage("resume-continue-button"))
        self.resumeContinue.setProperty("tone", "blue")
        self.resumeContinue.clicked.connect(self.continueResume)
        self.resumeStartOver = QtWidgets.QPushButton(getMessage("resume-start-over-button"))
        self.resumeStartOver.clicked.connect(self.dismissResume)
        for button in (self.resumeContinue, self.resumeStartOver):
            button.setFixedHeight(28)
            button.setStyleSheet("padding: 0 14px; min-height: 0;")
            button.setCursor(Qt.PointingHandCursor)
        resumeLayout.addWidget(self.resumeLabel, 1)
        resumeLayout.addWidget(self.resumeContinue)
        resumeLayout.addWidget(self.resumeStartOver)
        self.resumeBar.hide()
        self.mainLayout.insertWidget(1, self.resumeBar)
        self._resumeTimer = QtCore.QTimer(self)
        self._resumeTimer.setSingleShot(True)
        self._resumeTimer.timeout.connect(self.dismissResume)
        self.statusDot = QtWidgets.QLabel("\u25CF")
        self.statusDot.setObjectName("statusDot")
        self.statusServerLabel = QtWidgets.QLabel(getMessage("status-connecting"))
        self.statusServerLabel.setObjectName("statusText")
        self.statusRoomLabel = QtWidgets.QLabel("")
        self.statusRoomLabel.setObjectName("statusText")
        self.statusUsersLabel = QtWidgets.QLabel("")
        self.statusUsersLabel.setObjectName("statusText")
        bar.addWidget(self.statusDot)
        bar.addWidget(self.statusServerLabel)
        self.statusSyncLabel = ClickableLabel("")
        self.statusSyncLabel.setObjectName("statusText")
        self.statusSyncLabel.setToolTip(getMessage("sync-label-tooltip"))
        self.statusSyncLabel.clicked.connect(self.startSyncCheck)
        bar.addWidget(self.statusSyncLabel)
        self.statusSubtitleLabel = QtWidgets.QLabel("")
        self.statusSubtitleLabel.setObjectName("statusText")
        bar.addPermanentWidget(self.statusSubtitleLabel)
        bar.addPermanentWidget(self.sslButton)
        self._setConnectionState("connecting")

    def _setStatusDot(self, connected):
        self._setConnectionState("connected" if connected else "connecting")

    def _setConnectionState(self, state):
        """connecting / connected / lost: the dot in the status bar (it pulses while waiting) and the reconnect banner."""
        self._connState = state
        self._dotBright = True
        self._paintStatusDot()
        if state == "connected":
            self.statusServerLabel.setText(getMessage("status-connected") if getattr(self, "config", None) else getMessage("status-connecting"))
            self.statusServerLabel.setToolTip("{}:{}".format(self.config.get("host"), self.config.get("port")) if getattr(self, "config", None) else "")
        else:
            self.statusServerLabel.setText(getMessage("status-lost" if state == "lost" else "status-connecting"))
        self.connectionBanner.setVisible(state == "lost")
        if state == "connected":
            self._dotTimer.stop()
        elif not self._dotTimer.isActive():
            self._dotTimer.start(550)

    def _paintStatusDot(self):
        tokens = theme.tokens(getattr(self, "_dark", False))
        color = {"connected": tokens["ready"], "lost": tokens["warn"], "connecting": tokens["muted"]}[self._connState]
        if self._connState != "connected" and not self._dotBright:
            color = tokens["border"]
        self.statusDot.setStyleSheet("color: {};".format(color))

    def _pulseStatusDot(self):
        self._dotBright = not self._dotBright
        self._paintStatusDot()

    def connectionLost(self):
        self._setConnectionState("lost")

    def updateStatusBar(self, currentUser, rooms):
        host, port = self.config.get("host"), self.config.get("port")
        self.statusServerLabel.setText(getMessage("status-connected"))
        self.statusServerLabel.setToolTip("{}:{}".format(host, port))
        self._setStatusDot(True)
        self.updateNowCard(currentUser, rooms)
        if not self.roomFrame.isVisibleTo(self):
            self._showRoomLink(currentUser.room)

    # --- Voice -----------------------------------------------------------------------------------------------------

    def _currentVoiceUrl(self):
        entry = getattr(self, "_voiceEntry", None)
        client = self._syncplayClient
        return entry[1] if entry and client and entry[0] == client.getRoom() else None

    def _updateVoiceChip(self):
        self.voiceChip.setText("" if getattr(self, "_narrow", False) else getMessage("chip-voice-join-label" if self._currentVoiceUrl() else "chip-voice-label"))
        self.voiceChip.setVisible(bool(self._currentVoiceUrl()))  # Until someone starts a call, Voice lives in the "..." menu

    @needsClient
    def startVoiceCall(self):
        """Join the room's voice call (started by someone earlier), or start one: a random Jitsi link goes into the chat."""
        url = self._currentVoiceUrl()
        if not url:
            url = voice.newUrl()
            self._voiceEntry = (self._syncplayClient.getRoom(), url)
            self._syncplayClient.sendChat(getMessage("voice-chat-line").format(url))
            self.showMessage(getMessage("voice-started-notification"))
            self._updateVoiceChip()
        QtGui.QDesktopServices.openUrl(QUrl(url))

    # --- Desktop notifications --------------------------------------------------------------------------------------

    def _setUpTray(self):
        self._tray = None
        self._lastNotified = {}
        self._notificationsOn = True
        if not QtWidgets.QSystemTrayIcon.isSystemTrayAvailable():
            return
        icon = QtGui.QIcon()
        for name in ("icon.ico", "syncplay.png"):
            icon.addFile(os.path.join(resourcespath, name))
        self._tray = QtWidgets.QSystemTrayIcon(icon, self)
        self._tray.setToolTip(branding.NAME)
        menu = self._buildTrayMenu()
        self._trayMenu = menu
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(lambda reason: self._showFromTray() if reason == QtWidgets.QSystemTrayIcon.Trigger else None)
        self._tray.show()

    def _buildTrayMenu(self):
        menu = QtWidgets.QMenu()
        lineColor = theme.tokens(theme.isDarkPalette(QtWidgets.QApplication.palette()))["text"]
        menu.addAction(icons.icon("play", lineColor, 16), getMessage("tray-show-label"), self._showFromTray)
        menu.addAction(icons.icon("power", lineColor, 16), getMessage("exit-menu-label"), self.close)
        return menu

    def _showFromTray(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def setNotifications(self, enabled):
        self._notificationsOn = bool(enabled)
        try:
            secrets.save("notifications", "on" if enabled else "off", self.config.get("configDir"))
        except (OSError, TypeError):
            pass

    def notifyEvent(self, kind, text):
        """A quiet desktop notification for room events, only while this window isn't the one you're looking at."""
        if not getattr(self, "_notificationsOn", False) or not getattr(self, "_tray", None) or self.isActiveWindow():
            return
        now = time.time()
        if now - self._lastNotified.get(kind, 0) < 3:
            return
        self._lastNotified[kind] = now
        self._tray.showMessage(branding.NAME, text[:200], QtWidgets.QSystemTrayIcon.Information, 4000)

    def _noticeChat(self, username, plain):
        """Chat from somebody else: pick up a voice-call link, and notify when they mention your name."""
        client = self._syncplayClient
        url = voice.find(plain)
        if url and client:
            self._voiceEntry = (client.getRoom(), url)
            self._updateVoiceChip()
        me = client.getUsername() if client else None
        if me and username != me and re.search(r"(?<!\w)@?" + re.escape(me) + r"(?!\w)", plain, re.IGNORECASE):
            self.notifyEvent("mention", "{}: {}".format(username, plain))

    # --- Resume position and the sync note ---------------------------------------------------------------------------

    def offerResume(self, position):
        self._resumePosition = position
        self.resumeLabel.setText(getMessage("resume-offer").format(formatTime(position)))
        self.resumeBar.show()
        self._resumeTimer.start(25000)

    def continueResume(self):
        self.resumeBar.hide()
        self._resumeTimer.stop()
        if self._syncplayClient and getattr(self, "_resumePosition", None):
            self._syncplayClient.setPosition(self._resumePosition)

    def dismissResume(self):
        self.resumeBar.hide()
        self._resumeTimer.stop()

    def _syncNote(self):
        """(text, kind) for the status bar: how far you are from the room and your ping."""
        client = self._syncplayClient
        try:
            status = client.syncStatus()
        except Exception:
            return "", ""
        offset = status.get("offset") if isinstance(status, dict) else None
        if not isinstance(offset, (int, float)):
            return "", ""
        rtt = status.get("rtt")
        if abs(offset) < 0.5:
            return (getMessage("sync-in-sync-ping").format(rtt) if rtt is not None else getMessage("sync-in-sync")), "ok"
        return getMessage("sync-ahead" if offset > 0 else "sync-behind").format(abs(offset)), "warn"

    @needsClient
    def startSyncCheck(self):
        self._syncplayClient.startSyncCheck()

    def _subtitleStatusText(self):
        """Which subtitle is on for the current video (empty when there is none and automatic loading is off)."""
        client = self._syncplayClient
        try:
            file_ = client.userlist.currentUser.file
            applied = getattr(client, "_subtitleAppliedFor", None)
            if file_ and applied and applied == file_.get("name") and client.lastSharedSubtitle:
                return getMessage("status-subtitles-loaded").format(client.lastSharedSubtitle[0])
            if client.autoSubtitlesEnabled() is True:
                return getMessage("status-subtitles-auto")
        except Exception:
            pass
        return ""

    def _tickProgress(self):
        """Refresh the shared progress bar (and the subtitle note) from the client, twice a second."""
        client = self._syncplayClient
        if not client:
            return
        text = self._subtitleStatusText()
        if text != self.statusSubtitleLabel.text():
            self.statusSubtitleLabel.setText(text)
        note, kind = self._syncNote()
        if note != self.statusSyncLabel.text() or self.statusSyncLabel.property("kind") != kind:
            self.statusSyncLabel.setText(note)
            self.statusSyncLabel.setProperty("kind", kind)
            self.statusSyncLabel.style().unpolish(self.statusSyncLabel)
            self.statusSyncLabel.style().polish(self.statusSyncLabel)
        try:
            file_ = client.userlist.currentUser.file
            duration = file_.get("duration") if file_ else 0
            self.progressStrip.setState(client.getGlobalPosition(), duration, client.getGlobalPaused(), getattr(self, "_dark", False))
        except Exception:
            self.progressStrip.setState(0, 0, True, getattr(self, "_dark", False))

    def _fitPlaylist(self, *ignored):
        """The shared playlist is a slim strip until something is in it, then it grows."""
        try:
            empty = self.playlist.count() <= 1 and (self.playlist.count() == 0 or self.playlist.item(0).text() == getMessage("playlist-instruction-item-message"))
            self.playlistGroup.setVisible(not (getattr(self, "_narrow", False) and empty))  # No room for an empty playlist in a narrow window
            total = max(sum(self.listSplit.sizes()), 400)
            self.playlist.setVisible(not empty)  # An empty playlist is just its title row; dropping a file on it still works
            self.playlistGroup.setMaximumHeight(32 if empty else 16777215)
            self.playlistGroup.setProperty("collapsed", bool(empty))
            self.playlistGroup.style().unpolish(self.playlistGroup)
            self.playlistGroup.style().polish(self.playlistGroup)
            bottom = 32 if empty else max(200, int(total * 0.4))
            self.listSplit.setSizes([total - bottom, bottom])
        except Exception:
            pass

    def updateNowCard(self, currentUser, rooms):
        inRoom = [user for user in rooms.get(currentUser.room, []) if user.username.strip()]
        self.aloneCard.setVisible(len(inRoom) <= 1)
        parts = [branding.NAME, currentUser.room] if currentUser.room else [branding.NAME]
        if len(inRoom) > 1:
            parts.append(getMessage("now-ready").format(sum(1 for user in inRoom if user.isReadyWithFile()), len(inRoom)))
        parts.append("build {}".format(BUILD))
        self.setWindowTitle(" \u00b7 ".join(parts))  # The title bar and taskbar say where you are and who is ready
        ready = sum(1 for user in inRoom if user.isReadyWithFile())
        self.nowRoomLabel.setText(currentUser.room or getMessage("now-no-room"))
        self.nowPeoplePill.setText(getMessage("now-people").format(len(inRoom)))
        self.nowReadyPill.setText(getMessage("now-ready").format(ready, len(inRoom)))
        self.nowReadyPill.setProperty("kind", "ready" if inRoom and ready == len(inRoom) else "waiting")
        self.nowReadyPill.style().unpolish(self.nowReadyPill)
        self.nowReadyPill.style().polish(self.nowReadyPill)
        file_ = currentUser.file
        if file_ and file_.get("name"):
            details = [file_["name"]]
            if file_.get("duration"):
                details.append(formatTime(file_["duration"]))
            if file_.get("size"):
                details.append(formatSize(file_["size"]))
            self.nowFileLabel.setText("  \u00b7  ".join(details))
            self.nowFileLabel.setToolTip(file_["name"])
        else:
            self.nowFileLabel.setText(getMessage("now-no-file"))
            self.nowFileLabel.setToolTip("")

    @needsClient
    def inviteText(self, room=None):
        """What "Copy invite" puts on the clipboard: a link that opens the app in the room, plus the plain details."""
        client = self._syncplayClient
        room = room or client.getRoom()
        host, port = self.config.get("host"), self.config.get("port")
        lines = [getMessage("invite-heading"), inviteLinks.make(host, port, room), getMessage("invite-link-note"), "",
                 getMessage("invite-server").format(host, port), getMessage("invite-room").format(room)]
        if self.config.get("password"):
            lines.append(getMessage("invite-password-note"))
        return "\n".join(lines)

    def copyInvite(self):
        QtWidgets.QApplication.clipboard().setText(self.inviteText())
        self.statusBar().showMessage(getMessage("invite-copied-notification"), 4000)

    @needsClient
    def newPrivateRoom(self):
        """A brand-new room with a random name nobody can guess; the invite for it is copied straight away."""
        room = inviteLinks.randomRoomName()
        self.joinRoom(room)
        QtWidgets.QApplication.clipboard().setText(self.inviteText(room))
        self.statusBar().showMessage(getMessage("private-room-created-notification"), 6000)

    def handleInvite(self, raw):
        """An invite link reached this running copy (from another launch): join that room if it's on the same server."""
        link = inviteLinks.parse(raw)
        self.raise_()
        self.activateWindow()
        if not link:
            self.showMessage(getMessage("invite-invalid-notification"))
        elif not inviteLinks.sameServer(link, self.config.get("host"), self.config.get("port")):
            self.showMessage(getMessage("invite-other-server-notification").format(link.host, link.port))
        else:
            self.joinRoom(link.room)
            self.showMessage(getMessage("invite-joined-notification").format(link.room))

    def addShortcuts(self, announce=False):
        """Start menu and desktop shortcuts for the app."""
        try:
            for kind in install.KINDS:
                install.createShortcut(kind)
        except OSError as e:
            QtWidgets.QMessageBox.warning(self, branding.NAME, str(e))
            return False
        if announce:
            self.showMessage(getMessage("shortcuts-added-notification"))
        return True

    def _offerShortcuts(self):
        """Once, shortly after the first start of the single-file app: offer shortcuts (whatever the answer, never ask again)."""
        configDir = self.config.get("configDir")
        if not configDir or not install.isPackaged() or secrets.load(install.FLAG, configDir):
            return
        try:
            secrets.save(install.FLAG, "yes", configDir)
        except OSError:
            return
        box = QtWidgets.QMessageBox(self)
        box.setWindowTitle(branding.NAME)
        box.setText(getMessage("shortcuts-offer"))
        box.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if box.exec_() == QtWidgets.QMessageBox.Yes:
            self.addShortcuts(True)

    def uninstallApp(self):
        """Remove the app from this PC (its own folder, shortcuts and link handler), optionally with the person's settings."""
        box = QtWidgets.QMessageBox(self)
        box.setWindowTitle(branding.NAME)
        box.setIcon(QtWidgets.QMessageBox.Warning)
        box.setText(getMessage("uninstall-confirm"))
        settingsBox = QtWidgets.QCheckBox(getMessage("uninstall-settings-checkbox"))
        box.setCheckBox(settingsBox)
        box.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.Cancel)
        box.setDefaultButton(QtWidgets.QMessageBox.Cancel)
        if box.exec_() != QtWidgets.QMessageBox.Yes:
            return
        try:
            install.uninstall(self.config.get("configDir"), settingsBox.isChecked())
        except (OSError, ValueError) as e:
            QtWidgets.QMessageBox.warning(self, branding.NAME, str(e))
            return
        QtWidgets.QMessageBox.information(self, branding.NAME, getMessage("uninstall-done"))
        if self._syncplayClient:
            self._syncplayClient.stop()

    def _instanceTick(self):
        """Every couple of seconds: tell other launches this copy is running, and open any invite links they handed over."""
        configDir = self.config.get("configDir")
        if not configDir:
            return
        try:
            instance.beat(configDir)
            for raw in instance.takeInbox(configDir):
                self.handleInvite(raw)
        except OSError:
            pass

    def _startInstanceWatch(self):
        self._instanceTimer = QtCore.QTimer(self)
        self._instanceTimer.timeout.connect(self._instanceTick)
        self._instanceTimer.start(instance.HEARTBEAT_SECONDS * 1000)
        self._instanceTick()

    def _setUpInviteLinks(self):
        """Register syncplay-marquee:// with Windows for this user (unless they turned it off)."""
        if not self.config.get("configDir"):
            return
        try:
            available = inviteLinks.handlerAvailable()
            self.inviteLinksAction.setVisible(available)  # Only meaningful for the Windows single-file app
            off = secrets.load(inviteLinks.SETTING, self.config.get("configDir")) == "off"
            self.inviteLinksAction.blockSignals(True)
            self.inviteLinksAction.setChecked(not off)
            self.inviteLinksAction.blockSignals(False)
            if not available or off:
                return
            command = inviteLinks.handlerCommand()
            if not inviteLinks.isHandlerRegistered(command):
                inviteLinks.registerHandler(command, os.path.join(resourcespath, "icon.ico"))
        except Exception as e:
            self.showDebugMessage("Could not register invite links: {}".format(e))

    def toggleInviteLinks(self, enabled):
        try:
            secrets.save(inviteLinks.SETTING, "on" if enabled else "off", self.config.get("configDir"))
            if enabled:
                inviteLinks.registerHandler(inviteLinks.handlerCommand(), os.path.join(resourcespath, "icon.ico"))
            else:
                inviteLinks.unregisterHandler()
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, branding.NAME, str(e))

    def openConnectionSettings(self):
        """Reopen the app with the connection window showing."""
        if self._syncplayClient:
            try:
                self._syncplayClient.reopenWithStartWindow()
            except OSError as e:
                QtWidgets.QMessageBox.warning(self, branding.NAME, str(e))

    def toggleSkipStartWindow(self, checked):
        if self._syncplayClient:
            self._syncplayClient.setSkipStartWindow(checked)

    def togglePauseOnDropout(self, checked):
        if self._syncplayClient:
            self._syncplayClient.setPauseOnLeave(checked)

    def pauseOnDropoutChanged(self, enabled):
        self.dropoutSwitch.blockSignals(True)
        self.dropoutSwitch.setChecked(bool(enabled))
        self.dropoutSwitch.blockSignals(False)

    def toggleAlwaysReady(self, checked):
        if self._syncplayClient:
            self._syncplayClient.setAlwaysReady(checked)
        else:
            self.showDebugMessage("Tried to change always ready too soon.")

    def alwaysReadyChanged(self, enabled):
        """Called by the client (and at startup) so the buttons and menu mirror the always-ready setting."""
        for widget in (self.alwaysReadyButton, self.alwaysReadyAction):
            widget.blockSignals(True)
            widget.setChecked(bool(enabled))
            widget.blockSignals(False)
        if enabled:
            self.updateReadyState(True)
        self.readyPushButton.setEnabled(self._readinessSupported and not enabled)
        self.updateReadyIcon()

    @needsClient
    def openTorBoxDialog(self):
        dialog = getattr(self, "_torboxDialog", None)
        if dialog is None:
            dialog = self._torboxDialog = TorBoxDialog(self._syncplayClient, self)
        else:
            dialog.refresh()
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    @needsClient
    def openSubtitleDialog(self):
        dialog = getattr(self, "_subtitleDialog", None)
        if dialog is None:
            dialog = self._subtitleDialog = SubtitleDialog(self._syncplayClient, self)
        else:
            dialog.refresh()
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    @needsClient
    def shareSubtitleFile(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, getMessage("sharesubtitlefile-dialog-title"), "", getMessage("sharesubtitlefile-dialog-filter"))
        if path:
            self._syncplayClient.shareSubtitle(path)

    @needsClient
    def loadSharedSubtitle(self):
        self._syncplayClient.loadSharedSubtitle()

    @needsClient
    def openSetMediaDirectoriesDialog(self):
        MediaDirectoriesDialog = QtWidgets.QDialog()
        MediaDirectoriesDialog.setWindowTitle(getMessage("syncplay-mediasearchdirectories-title"))  # TODO: Move to messages_*.py
        MediaDirectoriesLayout = QtWidgets.QGridLayout()
        MediaDirectoriesLabel = QtWidgets.QLabel(getMessage("syncplay-mediasearchdirectories-label"))
        MediaDirectoriesLayout.addWidget(MediaDirectoriesLabel, 0, 0, 1, 2)
        MediaDirectoriesTextbox = QtWidgets.QPlainTextEdit()
        MediaDirectoriesTextbox.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)
        MediaDirectoriesTextbox.setPlainText(utils.getListAsMultilineString(self.config["mediaSearchDirectories"]))
        MediaDirectoriesLayout.addWidget(MediaDirectoriesTextbox, 1, 0, 1, 1)
        MediaDirectoriesButtonBox = QtWidgets.QDialogButtonBox()
        MediaDirectoriesButtonBox.setOrientation(Qt.Horizontal)
        MediaDirectoriesButtonBox.setStandardButtons(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        MediaDirectoriesButtonBox.accepted.connect(MediaDirectoriesDialog.accept)
        MediaDirectoriesButtonBox.rejected.connect(MediaDirectoriesDialog.reject)
        MediaDirectoriesLayout.addWidget(MediaDirectoriesButtonBox, 2, 0, 1, 1)
        MediaDirectoriesAddFolderButton = QtWidgets.QPushButton(getMessage("addfolder-label"))
        MediaDirectoriesAddFolderButton.pressed.connect(lambda: self.openAddMediaDirectoryDialog(MediaDirectoriesTextbox, MediaDirectoriesDialog))
        MediaDirectoriesLayout.addWidget(MediaDirectoriesAddFolderButton, 1, 1, 1, 1, Qt.AlignTop)
        MediaDirectoriesDialog.setLayout(MediaDirectoriesLayout)
        if isWindows() and IsPySide6:
            MediaDirectoriesDialog.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowSystemMenuHint | Qt.WindowCloseButtonHint | Qt.CustomizeWindowHint)
        else:
            MediaDirectoriesDialog.setWindowFlags(MediaDirectoriesDialog.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        MediaDirectoriesDialog.setModal(True)
        MediaDirectoriesDialog.show()
        result = MediaDirectoriesDialog.exec_()
        if result == QtWidgets.QDialog.Accepted:
            newMediaDirectories = utils.convertMultilineStringToList(MediaDirectoriesTextbox.toPlainText())
            self._syncplayClient.fileSwitch.changeMediaDirectories(newMediaDirectories)

    @needsClient
    def openSetTrustedDomainsDialog(self):
        TrustedDomainsDialog = QtWidgets.QDialog()
        TrustedDomainsDialog.setWindowTitle(getMessage("syncplay-trusteddomains-title"))
        TrustedDomainsLayout = QtWidgets.QGridLayout()
        TrustedDomainsLabel = QtWidgets.QLabel(getMessage("trusteddomains-msgbox-label"))
        TrustedDomainsLayout.addWidget(TrustedDomainsLabel, 0, 0, 1, 1)
        TrustedDomainsTextbox = QtWidgets.QPlainTextEdit()
        TrustedDomainsTextbox.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)
        TrustedDomainsTextbox.setPlainText(utils.getListAsMultilineString(self.config["trustedDomains"]))
        TrustedDomainsLayout.addWidget(TrustedDomainsTextbox, 1, 0, 1, 1)
        TrustedDomainsButtonBox = QtWidgets.QDialogButtonBox()
        TrustedDomainsButtonBox.setOrientation(Qt.Horizontal)
        TrustedDomainsButtonBox.setStandardButtons(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        TrustedDomainsButtonBox.accepted.connect(TrustedDomainsDialog.accept)
        TrustedDomainsButtonBox.rejected.connect(TrustedDomainsDialog.reject)
        TrustedDomainsLayout.addWidget(TrustedDomainsButtonBox, 2, 0, 1, 1)
        TrustedDomainsDialog.setLayout(TrustedDomainsLayout)
        if isWindows() and IsPySide6:
            TrustedDomainsDialog.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowSystemMenuHint | Qt.WindowCloseButtonHint | Qt.CustomizeWindowHint)
        else:
            TrustedDomainsDialog.setWindowFlags(TrustedDomainsDialog.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        TrustedDomainsDialog.setModal(True)
        TrustedDomainsDialog.show()
        result = TrustedDomainsDialog.exec_()
        if result == QtWidgets.QDialog.Accepted:
            newTrustedDomains = utils.convertMultilineStringToList(TrustedDomainsTextbox.toPlainText())
            self._syncplayClient.setTrustedDomains(newTrustedDomains)

    @needsClient
    def addTrustedDomain(self, newDomain):
        trustedDomains = self.config["trustedDomains"][:]
        if newDomain:
            trustedDomains.append(newDomain)
            self._syncplayClient.setTrustedDomains(trustedDomains)

    @needsClient
    def openAddMediaDirectoryDialog(self, MediaDirectoriesTextbox, MediaDirectoriesDialog):
        if isMacOS() and IsPySide:
            options = QtWidgets.QFileDialog.Options(QtWidgets.QFileDialog.ShowDirsOnly | QtWidgets.QFileDialog.DontUseNativeDialog)
        else:
            options = QtWidgets.QFileDialog.Options(QtWidgets.QFileDialog.ShowDirsOnly)
        folderName = str(QtWidgets.QFileDialog.getExistingDirectory(
            self, None, self.getInitialMediaDirectory(includeUserSpecifiedDirectories=False), options))

        if folderName:
            existingMediaDirs = MediaDirectoriesTextbox.toPlainText()
            if existingMediaDirs == "":
                newMediaDirList = folderName
            else:
                newMediaDirList = existingMediaDirs + "\n" + folderName
            MediaDirectoriesTextbox.setPlainText(newMediaDirList)
        MediaDirectoriesDialog.raise_()
        MediaDirectoriesDialog.activateWindow()

    @needsClient
    def promptForStreamURL(self):
        streamURL, ok = QtWidgets.QInputDialog.getText(
            self, getMessage("promptforstreamurl-msgbox-label"),
            getMessage("promptforstreamurlinfo-msgbox-label"), QtWidgets.QLineEdit.Normal, "")
        if ok and streamURL != '':
            self._syncplayClient.openFile(streamURL, resetPosition=False, fromUser=True)

    @needsClient
    def createControlledRoom(self):
        controlroom, ok = QtWidgets.QInputDialog.getText(
            self, getMessage("createcontrolledroom-msgbox-label"),
            getMessage("controlledroominfo-msgbox-label"), QtWidgets.QLineEdit.Normal,
            utils.stripRoomName(self._syncplayClient.getRoom()))
        if ok and controlroom != '':
            self._syncplayClient.createControlledRoom(controlroom)

    @needsClient
    def identifyAsController(self):
        msgboxtitle = getMessage("identifyascontroller-msgbox-label")
        msgboxtext = getMessage("identifyinfo-msgbox-label")
        controlpassword, ok = QtWidgets.QInputDialog.getText(self, msgboxtitle, msgboxtext, QtWidgets.QLineEdit.Normal, "")
        if ok and controlpassword != '':
            self._syncplayClient.identifyAsController(controlpassword)

    def _extractSign(self, m):
        if m:
            if m == "-":
                return -1
            else:
                return 1
        else:
            return None

    @needsClient
    def setOffset(self):
        oldoffset = str(self._syncplayClient.getUserOffset())
        newoffset, ok = QtWidgets.QInputDialog.getText(
            self, getMessage("setoffset-msgbox-label"),
            getMessage("offsetinfo-msgbox-label"), QtWidgets.QLineEdit.Normal, oldoffset)
        if ok and newoffset != '':
            o = re.match(constants.UI_OFFSET_REGEX, "o " + newoffset)
            if o:
                sign = self._extractSign(o.group('sign'))
                t = utils.parseTime(o.group('time'))
                if t is None:
                    return
                if o.group('sign') == "/":
                    t = self._syncplayClient.getPlayerPosition() - t
                elif sign:
                    t = self._syncplayClient.getUserOffset() + sign * t
                self._syncplayClient.setUserOffset(t)
            else:
                self.showErrorMessage(getMessage("invalid-offset-value"))

    def openUserGuide(self):
        if isLinux():
            self.QtGui.QDesktopServices.openUrl(QUrl("https://syncplay.pl/guide/linux/"))
        elif isWindows():
            self.QtGui.QDesktopServices.openUrl(QUrl("https://syncplay.pl/guide/windows/"))
        else:
            self.QtGui.QDesktopServices.openUrl(QUrl("https://syncplay.pl/guide/"))

    def drop(self):
        self.close()

    def getPlaylistState(self):
        playlistItems = []
        for playlistItem in range(self.playlist.count()):
            playlistItemText = self.playlist.item(playlistItem).text()
            if playlistItemText != getMessage("playlist-instruction-item-message"):
                playlistItems.append(playlistItemText)
        return playlistItems

    def playlistChangeCheck(self):
        if self.updatingPlaylist:
            return
        newPlaylist = self.getPlaylistState()
        if newPlaylist != self.playlistState and self._syncplayClient and not self.updatingPlaylist:
            self.playlistState = newPlaylist
            self._syncplayClient.playlist.changePlaylist(newPlaylist)
            self._syncplayClient.fileSwitch.updateInfo()

    def executeCommand(self, command):
        self.showMessage("/{}".format(command))
        self.console.executeCommand(command)

    @needsClient
    def nudgeSubtitleDelay(self, by):
        """Subtitles > earlier / later / reset: everyone's subtitle delay moves together."""
        if by is None:
            self._syncplayClient.changeSharedSubtitleDelay(seconds=0.0)
        else:
            self._syncplayClient.changeSharedSubtitleDelay(by=by)

    def subtitleDelayChanged(self, seconds, applied):
        self._statusSubDelay = seconds
        if getattr(self, "_subDelayShownFor", None) != seconds:
            self._subDelayShownFor = seconds
            self.showMessage(getMessage("subdelay-now").format(subdelay.describe(seconds)))

    @needsClient
    def reopenPlayer(self):
        try:
            self._syncplayClient.reopenPlayer()
        except OSError as e:
            QtWidgets.QMessageBox.information(self, branding.NAME, str(e) or getMessage("reopenplayer-failed"))

    @needsClient
    def copyDiagnostics(self):
        text = self._syncplayClient.diagnosticsText()
        QtWidgets.QApplication.clipboard().setText(text)
        self.showMessage(getMessage("diagnostics-copied").format(len(text.splitlines())))

    def showEmojiPicker(self):
        picker = EmojiPicker(emoji.PICKER, self)
        picker.picked.connect(self._insertEmoji)
        self._emojiPicker = picker
        picker.adjustSize()
        anchor = self.emojiButton.mapToGlobal(QtCore.QPoint(self.emojiButton.width(), 0))
        picker.move(anchor.x() - picker.width(), anchor.y() - picker.height() - 6)
        picker.show()

    def _insertEmoji(self, symbol):
        self.chatInput.insert(symbol)
        self.chatInput.setFocus()

    def sendChatMessage(self):
        chatText = self.chatInput.text()
        self.chatInput.setText("")
        if chatText != "":
            if chatText[:1] == "/" and chatText != "/":
                command = chatText[1:]
                if command and command[:1] == "/":
                    chatText = chatText[1:]
                else:
                    self.executeCommand(command)
                    return
            self._syncplayClient.sendChat(emoji.expand(chatText))

    def addTopLayout(self, window):
        window.topSplit = self.topSplitter(Qt.Horizontal, self)

        window.outputLayout = QtWidgets.QVBoxLayout()
        window.outputbox = QtWidgets.QTextBrowser()
        window.outputbox.document().setDefaultStyleSheet(
            "a {{color: {}; }}".format(theme.tokens(theme.isDarkPalette(QtWidgets.QApplication.palette()))["link"]))
        window.outputbox.setReadOnly(True)
        window.outputbox.setTextInteractionFlags(window.outputbox.textInteractionFlags() | Qt.TextSelectableByKeyboard)
        window.outputbox.setOpenExternalLinks(True)
        window.outputbox.unsetCursor()
        window.outputbox.moveCursor(QtGui.QTextCursor.End)
        window.outputbox.insertHtml('<div style="color: gray; font-size: 12px;">{}</div><br />'.format(getMessage("welcome-chat-line")))
        window.outputbox.moveCursor(QtGui.QTextCursor.End)
        window.outputbox.setCursorWidth(0)
        if not isMacOS(): window.outputbox.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

        window.outputlabel = QtWidgets.QLabel(getMessage("chat-heading-label"))
        window.outputlabel.setObjectName("sectionLabel")
        window.outputlabel.setMinimumHeight(27)
        window.chatInput = QtWidgets.QLineEdit()
        window.chatInput.setPlaceholderText(getMessage("chat-placeholder"))
        window.chatInput.setMaxLength(constants.MAX_CHAT_MESSAGE_LENGTH)
        window.chatInput.returnPressed.connect(self.sendChatMessage)
        window.chatButton = QtWidgets.QPushButton(
            menuIcon("email_go"),
            getMessage("sendmessage-label"))
        window.chatButton.pressed.connect(self.sendChatMessage)
        window.chatLayout = QtWidgets.QHBoxLayout()
        window.chatFrame = QtWidgets.QFrame()
        window.chatFrame.setLayout(self.chatLayout)
        window.chatFrame.setContentsMargins(0, 0, 0, 0)
        window.chatFrame.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        window.chatLayout.setContentsMargins(0, 0, 0, 0)
        self.chatButton.setToolTip(getMessage("sendmessage-tooltip"))
        window.emojiButton = QtWidgets.QToolButton()
        window.emojiButton.setObjectName("moreButton")
        window.emojiButton.setToolTip(getMessage("emoji-button-tooltip"))
        window.emojiButton.clicked.connect(self.showEmojiPicker)
        window.chatLayout.addWidget(window.chatInput)
        window.chatLayout.addWidget(window.emojiButton)
        window.chatLayout.addWidget(window.chatButton)
        window.chatFrame.setMaximumHeight(window.chatFrame.sizeHint().height())
        window.outputFrame = QtWidgets.QFrame()
        window.outputFrame.setLineWidth(0)
        window.outputFrame.setMidLineWidth(0)
        if isMacOS(): window.outputLayout.setSpacing(8)
        window.outputLayout.setContentsMargins(0, 0, 0, 0)
        window.outputlabel.hide()  # The chat is obviously the chat
        window.outputLayout.addWidget(window.outputbox)
        window.outputLayout.addWidget(window.chatFrame)
        window.outputFrame.setLayout(window.outputLayout)

        window.listLayout = QtWidgets.QVBoxLayout()
        window.listTreeModel = QtGui.QStandardItemModel()
        window.listTreeView = QtWidgets.QTreeView()
        window.listTreeView.setModel(window.listTreeModel)
        window.listTreeView.setIndentation(4)
        window.listTreeView.doubleClicked.connect(self.roomClicked)
        self.listTreeView.setContextMenuPolicy(Qt.CustomContextMenu)
        self.listTreeView.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.listTreeView.customContextMenuRequested.connect(self.openRoomMenu)
        window.listlabel = ElidedLabel("")
        window.listlabel.setObjectName("fileLine")
        if isMacOS():
            window.listlabel.setMinimumHeight(21)
            window.sslButton = QtWidgets.QPushButton(QtGui.QPixmap(resourcespath + 'lock_green.png').scaled(14, 14),"")
            window.sslButton.setVisible(False)
            window.sslButton.setFixedHeight(21)
            window.sslButton.setFixedWidth(21)
            window.sslButton.setMinimumSize(21, 21)
            window.sslButton.setStyleSheet("QPushButton:!hover{border: 1px solid gray;} QPushButton:hover{border:2px solid black;}")
        else:
            window.listlabel.setMinimumHeight(27)
            window.sslButton = QtWidgets.QPushButton(QtGui.QPixmap(resourcespath + 'lock_green.png'),"")
            window.sslButton.setVisible(False)
            window.sslButton.setFixedHeight(27)
            window.sslButton.setFixedWidth(27)
        window.sslButton.pressed.connect(self.openSSLDetails)
        window.sslButton.setToolTip(getMessage("sslconnection-tooltip"))
        window.listFrame = QtWidgets.QFrame()
        window.listFrame.setLineWidth(0)
        window.listFrame.setMidLineWidth(0)
        window.listFrame.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        window.listLayout.setContentsMargins(0, 0, 0, 0)
        if isMacOS(): window.listLayout.setSpacing(8)

        window.userlistLayout = QtWidgets.QGridLayout()
        window.userlistFrame = QtWidgets.QFrame()
        window.userlistFrame.setLineWidth(0)
        window.userlistFrame.setMidLineWidth(0)
        window.userlistFrame.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        window.userlistLayout.setContentsMargins(0, 0, 0, 0)
        window.userlistFrame.setLayout(window.userlistLayout)
        window.userlistLayout.addWidget(window.listlabel, 0, 0)
        window.userlistLayout.setColumnStretch(0, 1)
        window.quickActionsLayout = QtWidgets.QHBoxLayout()
        window.quickActionsLayout.setContentsMargins(0, 0, 0, 0)
        window.quickActionsLayout.setSpacing(6)
        window.subtitlesChip = QtWidgets.QPushButton(getMessage("chip-subtitles-label"))
        window.subtitlesChip.setObjectName("chipButton")
        window.subtitlesChip.setToolTip(getMessage("findsubtitles-menu-label").replace("&", "").rstrip("."))
        window.subtitlesChip.clicked.connect(self.openSubtitleDialog)
        window.inviteChip = QtWidgets.QPushButton(getMessage("chip-invite-label"))
        window.inviteChip.setObjectName("chipButton")
        window.inviteChip.setToolTip(getMessage("chip-invite-tooltip"))
        window.inviteChip.clicked.connect(self.copyInvite)
        window.privateChip = QtWidgets.QPushButton(getMessage("chip-private-label"))
        window.privateChip.setObjectName("chipButton")
        window.privateChip.setToolTip(getMessage("chip-private-tooltip"))
        window.privateChip.clicked.connect(self.newPrivateRoom)
        window.libraryChip = QtWidgets.QPushButton(getMessage("chip-library-label"))
        window.libraryChip.setObjectName("chipButton")
        window.libraryChip.setToolTip(getMessage("torbox-menu-label").replace("&", "").rstrip("."))
        window.libraryChip.clicked.connect(self.openTorBoxDialog)
        window.voiceChip = QtWidgets.QPushButton(getMessage("chip-voice-label"))
        window.voiceChip.setObjectName("chipButton")
        window.voiceChip.setToolTip(getMessage("chip-voice-tooltip"))
        window.voiceChip.clicked.connect(self.startVoiceCall)
        window.moreChip = QtWidgets.QToolButton()
        window.moreChip.setObjectName("moreButton")
        window.moreChip.setToolTip(getMessage("chip-more-tooltip"))
        window.moreChip.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        moreMenu = QtWidgets.QMenu(window.moreChip)
        for label, slot in (("chip-subtitles-label", self.openSubtitleDialog), ("chip-library-label", self.openTorBoxDialog),
                            ("chip-voice-label", self.startVoiceCall), ("chip-private-label", self.newPrivateRoom)):
            moreMenu.addAction(getMessage(label), slot)
        window.moreChip.setMenu(moreMenu)
        for chip in (window.subtitlesChip, window.libraryChip, window.privateChip):
            chip.hide()  # Still there for the code and shortcuts that use them; the "..." menu is how you reach them now
        window.voiceChip.hide()
        window.quickActionsLayout.addWidget(window.voiceChip)
        window.quickActionsLayout.addWidget(window.inviteChip)
        window.quickActionsLayout.addWidget(window.moreChip)
        window.userlistLayout.addLayout(window.quickActionsLayout, 0, 1, Qt.AlignRight)
        window.progressStrip = ProgressStrip()
        window.userlistLayout.addWidget(window.progressStrip, 1, 0, 1, 3)
        window.listTreeView.setObjectName("members")
        window.userlistLayout.addWidget(window.listTreeView, 2, 0, 1, 3)
        window.aloneCard = QtWidgets.QFrame()
        aloneLayout = QtWidgets.QHBoxLayout(window.aloneCard)
        aloneLayout.setContentsMargins(4, 2, 4, 2)
        window.aloneLabel = QtWidgets.QLabel(getMessage("alone-hint"))
        window.aloneLabel.setObjectName("hint")
        window.aloneButton = QtWidgets.QPushButton(getMessage("chip-invite-label"))
        window.aloneButton.setObjectName("chipButton")
        window.aloneButton.clicked.connect(self.copyInvite)
        aloneLayout.addWidget(window.aloneLabel, 1)
        aloneLayout.addWidget(window.aloneButton)
        window.aloneCard.hide()
        window.userlistLayout.addWidget(window.aloneCard, 3, 0, 1, 3)
        if isMacOS(): window.userlistLayout.setContentsMargins(3, 0, 3, 0)

        window.listSplit = QtWidgets.QSplitter(Qt.Vertical, self)
        window.listSplit.setHandleWidth(6)
        window.listSplit.setStyle(QtWidgets.QStyleFactory.create("fusion"))
        window.listSplit.addWidget(window.userlistFrame)
        window.nowCard = QtWidgets.QFrame()
        window.nowCard.setObjectName("nowCard")
        nowLayout = QtWidgets.QVBoxLayout(window.nowCard)
        nowLayout.setContentsMargins(16, 12, 16, 12)
        nowLayout.setSpacing(4)
        titleRow = QtWidgets.QHBoxLayout()
        titleRow.setSpacing(8)
        window.nowRoomLabel = QtWidgets.QLabel(getMessage("now-no-room"))
        window.nowRoomLabel.setObjectName("roomTitle")
        window.nowPeoplePill = QtWidgets.QLabel("")
        window.nowPeoplePill.setObjectName("nowPill")
        window.nowReadyPill = QtWidgets.QLabel("")
        window.nowReadyPill.setObjectName("nowPill")
        titleRow.addWidget(window.nowRoomLabel, 1)
        titleRow.addWidget(window.nowPeoplePill)
        titleRow.addWidget(window.nowReadyPill)
        window.nowFileLabel = QtWidgets.QLabel(getMessage("now-no-file"))
        window.nowFileLabel.setObjectName("nowFile")
        nowLayout.addLayout(titleRow)
        nowLayout.addWidget(window.nowFileLabel)
        window.listLayout.addWidget(window.nowCard)
        window.nowCard.hide()  # The people table and the progress strip say it all; the labels stay for the code that fills them
        window.listLayout.addWidget(window.listSplit)
        window.roomsCombobox = QtWidgets.QComboBox(self)
        window.roomsCombobox.setEditable(True)
        caseSensitiveCompleter = QtWidgets.QCompleter(self)
        caseSensitiveCompleter.setCaseSensitivity(Qt.CaseSensitive)
        window.roomsCombobox.setCompleter(caseSensitiveCompleter)
        #window.roomsCombobox.setMaxLength(constants.MAX_ROOM_NAME_LENGTH)
        window.roomButton = QtWidgets.QPushButton(
            menuIcon("door_in"),
            getMessage("joinroom-label"))
        window.roomButton.pressed.connect(self.joinRoom)
        window.roomButton.setFixedWidth(window.roomButton.sizeHint().width()+3)
        window.roomLayout = QtWidgets.QHBoxLayout()
        window.roomFrame = QtWidgets.QFrame()
        window.roomFrame.setLayout(self.roomLayout)
        window.roomFrame.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        if isMacOS():
            window.roomLayout.setSpacing(8)
            window.roomLayout.setContentsMargins(3, 0, 0, 0)
        else:
            window.roomFrame.setContentsMargins(0, 0, 0, 0)
            window.roomLayout.setContentsMargins(0, 0, 0, 0)
        self.roomButton.setToolTip(getMessage("joinroom-tooltip"))
        window.roomLayout.addWidget(window.roomsCombobox)
        window.roomLayout.addWidget(window.roomButton)
        window.tuneButton = QtWidgets.QToolButton()
        window.tuneButton.setObjectName("moreButton")
        window.tuneButton.setToolTip(getMessage("chip-tune-tooltip"))
        window.tuneButton.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        tuneMenu = QtWidgets.QMenu(window.tuneButton)
        window._tuneActions = []
        for label, switchName in (("always-ready-label", "alwaysReadyButton"), ("dropout-switch-label", "dropoutSwitch")):
            action = tuneMenu.addAction(getMessage(label))
            action.setCheckable(True)
            action.triggered.connect(lambda checked, n=switchName: getattr(self, n).setChecked(checked))
            window._tuneActions.append((action, switchName))
        window.roomLink = QtWidgets.QPushButton("")
        window.roomLink.setObjectName("roomLink")
        window.roomLink.setFlat(True)
        window.roomLink.setCursor(Qt.PointingHandCursor)
        window.roomLink.setToolTip(getMessage("chip-room-change-tooltip"))
        window.roomLink.clicked.connect(self.editRoom)
        tuneMenu.aboutToShow.connect(lambda: [a.setChecked(getattr(self, n).isChecked()) for a, n in self._tuneActions])
        window.tuneButton.setMenu(tuneMenu)
        window.roomBar = QtWidgets.QHBoxLayout()
        window.roomBar.setContentsMargins(0, 0, 0, 0)
        window.roomBar.addWidget(window.roomLink, 1, Qt.AlignLeft)
        window.roomBar.addWidget(window.tuneButton)
        window.roomFrame.setMaximumHeight(window.roomFrame.sizeHint().height())
        window.roomFrame.hide()
        window.listLayout.addLayout(window.roomBar)
        window.listLayout.addWidget(window.roomFrame, Qt.AlignRight)

        window.listFrame.setLayout(window.listLayout)
        if isMacOS(): window.listFrame.setMinimumHeight(window.outputFrame.height())

        window.topSplit.addWidget(window.outputFrame)
        window.topSplit.addWidget(window.listFrame)
        window.topSplit.setHandleWidth(6)
        window.topSplit.setStretchFactor(0, 4)
        window.topSplit.setStretchFactor(1, 5)
        window.topSplit.setStyle(QtWidgets.QStyleFactory.create("fusion"))
        window.mainLayout.addWidget(window.topSplit)
        window.topSplit.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Expanding)

    def addBottomLayout(self, window):
        window.bottomLayout = QtWidgets.QHBoxLayout()
        window.bottomFrame = QtWidgets.QFrame()
        window.bottomFrame.setLayout(window.bottomLayout)
        window.bottomLayout.setContentsMargins(0, 0, 0, 0)
        if isMacOS(): window.bottomLayout.setSpacing(0)

        self.addPlaybackLayout(window)

        window.playlistGroup = self.PlaylistGroupBox(getMessage("sharedplaylistenabled-label"))
        window.playlistGroup.setCheckable(True)
        window.playlistGroup.toggled.connect(self.changePlaylistEnabledState)
        window.playlistLayout = QtWidgets.QHBoxLayout()
        window.playlistGroup.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        window.playlistGroup.setAcceptDrops(True)
        window.playlist = self.PlaylistWidget()
        window.playlist.setWindow(window)
        window.playlist.setItemDelegate(self.PlaylistItemDelegate())
        window.playlist.setDragEnabled(True)
        window.playlist.setAcceptDrops(True)
        window.playlist.setDropIndicatorShown(True)
        window.playlist.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        window.playlist.setDefaultDropAction(Qt.MoveAction)
        window.playlist.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        window.playlist.doubleClicked.connect(self.playlistItemClicked)
        window.playlist.setContextMenuPolicy(Qt.CustomContextMenu)
        window.playlist.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        window.playlist.customContextMenuRequested.connect(self.openPlaylistMenu)
        self.playlistUpdateTimer = task.LoopingCall(self.playlistChangeCheck)
        self.playlistUpdateTimer.start(0.1, True)
        noteFont = QtGui.QFont()
        noteFont.setItalic(True)
        playlistItem = QtWidgets.QListWidgetItem(getMessage("playlist-instruction-item-message"))
        playlistItem.setFont(noteFont)
        window.playlist.addItem(playlistItem)
        window.playlistLayout.addWidget(window.playlist)
        window.playlistLayout.setAlignment(Qt.AlignTop)
        window.playlistGroup.setLayout(window.playlistLayout)
        window.listSplit.addWidget(window.playlistGroup)
        window.listSplit.setStretchFactor(0, 5)  # People get most of the space, the playlist the rest
        window.listSplit.setStretchFactor(1, 2)
        window.listSplit.setSizes([320, 140])

        window.readyPushButton = ReadyButton()
        readyFont = QtGui.QFont()
        readyFont.setWeight(QtGui.QFont.Bold)
        window.readyPushButton.setText(getMessage("ready-guipushbuttonlabel"))
        window.readyPushButton.setCheckable(True)
        window.readyPushButton.setAutoExclusive(False)
        window.readyPushButton.toggled.connect(self.changeReadyState)
        window.readyPushButton.setFont(readyFont)
        window.readyPushButton.setObjectName("readyButton")
        window.readyPushButton.setToolTip(getMessage("ready-tooltip"))
        window.alwaysReadyButton = ToggleSwitch(getMessage("always-ready-label"))
        window.alwaysReadyButton.setObjectName("alwaysReadyButton")
        window.alwaysReadyButton.setToolTip(getMessage("always-ready-tooltip"))
        window.alwaysReadyButton.toggled.connect(self.toggleAlwaysReady)
        window.readyRow = QtWidgets.QVBoxLayout()
        window.readyRow.setContentsMargins(0, 0, 0, 0)
        window.readyRow.setSpacing(6)
        window.readyRow.addWidget(window.readyPushButton)
        window.readyRow.addWidget(window.alwaysReadyButton, 0, Qt.AlignLeft)
        window.alwaysReadyButton.hide()  # Reached from the sliders menu next to Join room
        window.dropoutSwitch = ToggleSwitch(getMessage("dropout-switch-label"))
        window.dropoutSwitch.setObjectName("dropoutSwitch")
        window.dropoutSwitch.setToolTip(getMessage("dropout-switch-tooltip"))
        window.dropoutSwitch.toggled.connect(self.togglePauseOnDropout)
        window.readyRow.addWidget(window.dropoutSwitch, 0, Qt.AlignLeft)
        window.dropoutSwitch.hide()
        window.listLayout.addLayout(window.readyRow)
        if isMacOS(): window.listLayout.setContentsMargins(0, 0, 0, 10)

        window.autoplayLayout = QtWidgets.QHBoxLayout()
        window.autoplayFrame = QtWidgets.QFrame()
        window.autoplayFrame.setVisible(False)

        window.autoplayFrame.setLayout(window.autoplayLayout)
        window.autoplayPushButton = QtWidgets.QPushButton()
        autoPlayFont = QtGui.QFont()
        autoPlayFont.setWeight(QtGui.QFont.Bold)
        window.autoplayPushButton.setText(getMessage("autoplay-guipushbuttonlabel"))
        window.autoplayPushButton.setCheckable(True)
        window.autoplayPushButton.setAutoExclusive(False)
        window.autoplayPushButton.toggled.connect(self.changeAutoplayState)
        window.autoplayPushButton.setFont(autoPlayFont)
        if isMacOS():
            window.autoplayFrame.setMinimumWidth(window.listFrame.sizeHint().width())
            window.autoplayLayout.setSpacing(15)
            window.autoplayLayout.setContentsMargins(0, 8, 3, 3)
            window.autoplayPushButton.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        else:
            window.autoplayLayout.setContentsMargins(0, 0, 0, 0)
            window.autoplayPushButton.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        window.autoplayPushButton.setObjectName("autoplayButton")
        window.autoplayPushButton.setToolTip(getMessage("autoplay-tooltip"))
        window.autoplayLabel = QtWidgets.QLabel(getMessage("autoplay-minimum-label"))
        window.autoplayLabel.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        window.autoplayLabel.setMaximumWidth(window.autoplayLabel.minimumSizeHint().width())
        window.autoplayLabel.setToolTip(getMessage("autoplay-tooltip"))
        window.autoplayThresholdSpinbox = QtWidgets.QSpinBox()
        window.autoplayThresholdSpinbox.setMaximumWidth(window.autoplayThresholdSpinbox.minimumSizeHint().width())
        window.autoplayThresholdSpinbox.setMinimum(2)
        window.autoplayThresholdSpinbox.setMaximum(99)
        window.autoplayThresholdSpinbox.setToolTip(getMessage("autoplay-tooltip"))
        window.autoplayThresholdSpinbox.valueChanged.connect(self.changeAutoplayThreshold)
        window.autoplayLayout.addWidget(window.autoplayPushButton, Qt.AlignRight)
        window.autoplayLayout.addWidget(window.autoplayLabel, Qt.AlignRight)
        window.autoplayLayout.addWidget(window.autoplayThresholdSpinbox, Qt.AlignRight)

        window.listLayout.addWidget(window.autoplayFrame, Qt.AlignLeft)
        window.autoplayFrame.setMaximumHeight(window.autoplayFrame.sizeHint().height())
        window.mainLayout.addWidget(window.bottomFrame, Qt.AlignLeft)
        window.bottomFrame.setMaximumHeight(window.bottomFrame.minimumSizeHint().height())

    def addPlaybackLayout(self, window):
        window.playbackFrame = QtWidgets.QFrame()
        window.playbackFrame.setVisible(False)
        window.playbackFrame.setContentsMargins(0, 0, 0, 0)
        window.playbackLayout = QtWidgets.QHBoxLayout()
        window.playbackLayout.setAlignment(Qt.AlignLeft)
        window.playbackLayout.setContentsMargins(0, 0, 0, 0)
        window.playbackFrame.setLayout(window.playbackLayout)
        window.seekInput = QtWidgets.QLineEdit()
        window.seekInput.returnPressed.connect(self.seekFromButton)
        window.seekButton = QtWidgets.QPushButton(menuIcon("clock_go"), "")
        window.seekButton.setToolTip(getMessage("seektime-menu-label"))
        window.seekButton.pressed.connect(self.seekFromButton)
        window.seekInput.setText("0:00")
        window.seekInput.setFixedWidth(60)
        window.playbackLayout.addWidget(window.seekInput)
        window.playbackLayout.addWidget(window.seekButton)
        window.unseekButton = QtWidgets.QPushButton(menuIcon("arrow_undo"), "")
        window.unseekButton.setToolTip(getMessage("undoseek-menu-label"))
        window.unseekButton.pressed.connect(self.undoSeek)

        window.miscLayout = QtWidgets.QHBoxLayout()
        window.playbackLayout.addWidget(window.unseekButton)
        window.playButton = QtWidgets.QPushButton(menuIcon("control_play_blue"), "")
        window.playButton.setToolTip(getMessage("play-menu-label"))
        window.playButton.pressed.connect(self.play)
        window.playbackLayout.addWidget(window.playButton)
        window.pauseButton = QtWidgets.QPushButton(menuIcon("control_pause_blue"), "")
        window.pauseButton.setToolTip(getMessage("pause-menu-label"))
        window.pauseButton.pressed.connect(self.pause)
        window.playbackLayout.addWidget(window.pauseButton)
        window.playbackFrame.setMaximumHeight(window.playbackFrame.sizeHint().height())
        window.playbackFrame.setMaximumWidth(window.playbackFrame.sizeHint().width())
        window.outputLayout.addWidget(window.playbackFrame)

    def loadMenubar(self, window, passedBar):
        if passedBar is not None:
            window.menuBar = passedBar['bar']
            window.editMenu = passedBar['editMenu']
        else:
            window.menuBar = QtWidgets.QMenuBar()
            window.editMenu = None

    def populateMenubar(self, window):
        # File menu

        window.fileMenu = QtWidgets.QMenu(getMessage("file-menu-label"), self)
        window.openAction = window.fileMenu.addAction(menuIcon("folder_explore"),
                                                      getMessage("openmedia-menu-label"))
        window.openAction.triggered.connect(self.browseMediapath)
        window.openAction = window.fileMenu.addAction(menuIcon("world_explore"),
                                                      getMessage("openstreamurl-menu-label"))
        window.openAction.triggered.connect(self.promptForStreamURL)
        window.openAction = window.fileMenu.addAction(menuIcon("film_folder_edit"),
                                                      getMessage("setmediadirectories-menu-label"))
        window.openAction.triggered.connect(self.openSetMediaDirectoriesDialog)

        window.openPlaylistAction = window.fileMenu.addAction(menuIcon("folder_explore"), getMessage("openplaylistfile-menu-label"))
        window.openPlaylistAction.setShortcut(QtGui.QKeySequence("Ctrl+Shift+O"))
        window.openPlaylistAction.triggered.connect(lambda checked=False: self.OpenLoadPlaylistFromFileDialog())
        window.reloadPlaylistAction = window.fileMenu.addAction(menuIcon("reconnect"), getMessage("reloadplaylistfile-menu-label"))
        window.reloadPlaylistAction.setShortcut(QtGui.QKeySequence("Ctrl+Shift+L"))
        window.reloadPlaylistAction.triggered.connect(self.reloadPlaylistFile)

        window.torboxAction = window.fileMenu.addAction(menuIcon("world_explore"),
                                                        getMessage("torbox-menu-label"))
        window.torboxAction.setShortcut(QtGui.QKeySequence("Ctrl+Shift+T"))
        window.torboxAction.triggered.connect(self.openTorBoxDialog)

        window.connectionSettingsAction = window.fileMenu.addAction(menuIcon("help"), getMessage("connectionsettings-menu-label"))
        window.connectionSettingsAction.triggered.connect(self.openConnectionSettings)
        window.skipStartAction = window.fileMenu.addAction(getMessage("skipstart-menu-label"))
        window.skipStartAction.setCheckable(True)
        window.skipStartAction.toggled.connect(self.toggleSkipStartWindow)
        window.reconnectAction = window.fileMenu.addAction(menuIcon("reconnect"), getMessage("reconnect-menu-label"))
        window.reconnectAction.triggered.connect(self.reconnectToServer)
        window.reopenPlayerAction = window.fileMenu.addAction(getMessage("reopenplayer-menu-label"))
        window.reopenPlayerAction.setShortcut("Ctrl+Shift+R")
        window.reopenPlayerAction.triggered.connect(self.reopenPlayer)

        window.exitAction = window.fileMenu.addAction(getMessage("exit-menu-label"))
        if isMacOS():
            window.exitAction.setMenuRole(QtWidgets.QAction.QuitRole)
        else:
            window.exitAction.setIcon(menuIcon("cross"))
        window.exitAction.triggered.connect(self.exitSyncplay)

        if(window.editMenu is not None):
            window.menuBar.insertMenu(window.editMenu.menuAction(), window.fileMenu)
        else:
            window.menuBar.addMenu(window.fileMenu)

        # Playback menu

        window.playbackMenu = QtWidgets.QMenu(getMessage("playback-menu-label"), self)
        window.playAction = window.playbackMenu.addAction(
            menuIcon("control_play_blue"),
            getMessage("play-menu-label"))
        window.playAction.triggered.connect(self.play)
        window.pauseAction = window.playbackMenu.addAction(
            menuIcon("control_pause_blue"),
            getMessage("pause-menu-label"))
        window.pauseAction.triggered.connect(self.pause)
        window.seekAction = window.playbackMenu.addAction(
            menuIcon("clock_go"),
            getMessage("seektime-menu-label"))
        window.seekAction.triggered.connect(self.seekPositionDialog)
        window.unseekAction = window.playbackMenu.addAction(
            menuIcon("arrow_undo"),
            getMessage("undoseek-menu-label"))
        window.unseekAction.triggered.connect(self.undoSeek)

        window.syncCheckAction = window.playbackMenu.addAction(getMessage("synccheck-menu-label"))
        window.syncCheckAction.setShortcut(QtGui.QKeySequence("Ctrl+Shift+Y"))
        window.syncCheckAction.triggered.connect(lambda checked=False: self.startSyncCheck())
        window.menuBar.addMenu(window.playbackMenu)

        # Subtitles menu

        window.subtitlesMenu = QtWidgets.QMenu(getMessage("subtitles-menu-label"), self)
        window.findSubtitlesAction = window.subtitlesMenu.addAction(
            menuIcon("film_go"), getMessage("findsubtitles-menu-label"))
        window.findSubtitlesAction.setShortcut(QtGui.QKeySequence("Ctrl+Shift+S"))
        window.findSubtitlesAction.triggered.connect(self.openSubtitleDialog)
        window.shareSubtitleFileAction = window.subtitlesMenu.addAction(
            menuIcon("film_add"), getMessage("sharesubtitlefile-menu-label"))
        window.shareSubtitleFileAction.triggered.connect(self.shareSubtitleFile)
        window.loadSharedSubtitleAction = window.subtitlesMenu.addAction(
            menuIcon("film_link"), getMessage("loadsharedsubtitle-menu-label"))
        window.loadSharedSubtitleAction.triggered.connect(self.loadSharedSubtitle)
        window.subtitlesMenu.addSeparator()
        window.subDelayEarlierAction = window.subtitlesMenu.addAction(getMessage("subdelay-earlier-menu-label"))
        window.subDelayEarlierAction.setShortcut("Ctrl+Shift+[")
        window.subDelayEarlierAction.triggered.connect(lambda checked=False: self.nudgeSubtitleDelay(-subdelay.STEP))
        window.subDelayLaterAction = window.subtitlesMenu.addAction(getMessage("subdelay-later-menu-label"))
        window.subDelayLaterAction.setShortcut("Ctrl+Shift+]")
        window.subDelayLaterAction.triggered.connect(lambda checked=False: self.nudgeSubtitleDelay(subdelay.STEP))
        window.subDelayResetAction = window.subtitlesMenu.addAction(getMessage("subdelay-reset-menu-label"))
        window.subDelayResetAction.triggered.connect(lambda checked=False: self.nudgeSubtitleDelay(None))

        window.menuBar.addMenu(window.subtitlesMenu)

        # Advanced menu

        window.advancedMenu = QtWidgets.QMenu(getMessage("advanced-menu-label"), self)
        window.setoffsetAction = window.advancedMenu.addAction(
            menuIcon("timeline_marker"),
            getMessage("setoffset-menu-label"))
        window.setoffsetAction.triggered.connect(self.setOffset)
        window.setTrustedDomainsAction = window.advancedMenu.addAction(
            menuIcon("shield_edit"),
            getMessage("settrusteddomains-menu-label"))
        window.setTrustedDomainsAction.triggered.connect(self.openSetTrustedDomainsDialog)
        window.createcontrolledroomAction = window.advancedMenu.addAction(
            menuIcon("page_white_key"), getMessage("createcontrolledroom-menu-label"))
        window.createcontrolledroomAction.triggered.connect(self.createControlledRoom)
        window.identifyascontroller = window.advancedMenu.addAction(menuIcon("key_go"),
                                                                    getMessage("identifyascontroller-menu-label"))
        window.identifyascontroller.triggered.connect(self.identifyAsController)

        window.menuBar.addMenu(window.advancedMenu)

        # Window menu

        window.windowMenu = QtWidgets.QMenu(getMessage("window-menu-label"), self)

        window.editroomsAction = window.windowMenu.addAction(menuIcon("door_open_edit"), getMessage("roomlist-msgbox-label"))
        window.editroomsAction.triggered.connect(self.openEditRoomsDialog)
        window.menuBar.addMenu(window.windowMenu)

        window.alwaysReadyAction = window.windowMenu.addAction(getMessage("always-ready-menu-label"))
        window.alwaysReadyAction.setCheckable(True)
        window.alwaysReadyAction.triggered.connect(self.toggleAlwaysReady)

        window.notificationsAction = window.windowMenu.addAction(getMessage("notifications-menu-label"))
        window.notificationsAction.setCheckable(True)
        window.notificationsAction.setChecked(True)
        window.notificationsAction.toggled.connect(self.setNotifications)
        window.themeMenu = window.windowMenu.addMenu(getMessage("theme-menu-label"))
        window.themeActions = {}
        for themeName in theme.THEME_ORDER:
            action = window.themeMenu.addAction(getMessage("theme-" + themeName + "-label"))
            action.setCheckable(True)
            action.setChecked(themeName == theme.chosenTheme())
            action.triggered.connect(lambda checked=False, n=themeName: self.switchTheme(n))
            window.themeActions[themeName] = action
        window.playbackAction = window.windowMenu.addAction(getMessage("playbackbuttons-menu-label"))
        window.playbackAction.setCheckable(True)
        window.playbackAction.triggered.connect(self.updatePlaybackFrameVisibility)

        window.autoplayAction = window.windowMenu.addAction(getMessage("autoplay-menu-label"))
        window.autoplayAction.setCheckable(True)
        window.autoplayAction.triggered.connect(self.updateAutoplayVisibility)

        window.hideEmptyRoomsAction = window.windowMenu.addAction(getMessage("hideemptyrooms-menu-label"))
        window.hideEmptyRoomsAction.setCheckable(True)
        window.hideEmptyRoomsAction.triggered.connect(self.updateEmptyRoomVisiblity)

        # Help menu

        window.helpMenu = QtWidgets.QMenu(getMessage("help-menu-label"), self)

        window.userguideAction = window.helpMenu.addAction(
            menuIcon("help"),
            getMessage("userguide-menu-label"))
        window.userguideAction.triggered.connect(self.openUserGuide)
        window.updateAction = window.helpMenu.addAction(
            menuIcon("application_get"),
            getMessage("update-menu-label"))
        window.updateAction.triggered.connect(self.userCheckForUpdates)
        window.updateSourceAction = window.helpMenu.addAction(getMessage("update-source-menu-label"))
        window.updateSourceAction.triggered.connect(self.setUpdateSource)
        window.inviteLinksAction = window.helpMenu.addAction(getMessage("invite-links-menu-label"))
        window.inviteLinksAction.setCheckable(True)
        window.inviteLinksAction.setChecked(True)
        window.inviteLinksAction.toggled.connect(self.toggleInviteLinks)
        window.shortcutsAction = window.helpMenu.addAction(getMessage("shortcuts-menu-label"))
        window.shortcutsAction.triggered.connect(lambda checked=False: self.addShortcuts(True))
        window.uninstallAction = window.helpMenu.addAction(getMessage("uninstall-menu-label"))
        window.uninstallAction.triggered.connect(self.uninstallApp)
        for action in (window.shortcutsAction, window.uninstallAction):
            action.setVisible(install.isPackaged())  # Only the single-file app has anything to install or remove
        window.diagnosticsAction = window.helpMenu.addAction(getMessage("diagnostics-menu-label"))
        window.diagnosticsAction.triggered.connect(self.copyDiagnostics)
        window.updateLogAction = window.helpMenu.addAction(getMessage("update-log-menu-label"))
        window.updateLogAction.triggered.connect(lambda checked=False: self.showUpdateLog())

        if not isMacOS():
            window.helpMenu.addSeparator()
            window.about = window.helpMenu.addAction(
                menuIcon("syncplay"),
                getMessage("about-menu-label"))
        else:
            window.about = window.helpMenu.addAction("&About")
            window.about.setMenuRole(QtWidgets.QAction.AboutRole)
        window.about.triggered.connect(self.openAbout)
        self._iconAllMenuItems(window)

        window.menuBar.addMenu(window.helpMenu)
        window.mainLayout.setMenuBar(window.menuBar)

    @needsClient
    def openSSLDetails(self):
        sslDetailsBox = CertificateDialog(self.getSSLInformation())
        sslDetailsBox.exec_()
        self.sslButton.setDown(False)

    def openAbout(self):
        aboutMsgBox = AboutDialog()
        aboutMsgBox.exec_()

    def addMainFrame(self, window):
        window.mainFrame = QtWidgets.QFrame()
        window.mainFrame.setObjectName("mainFrame")
        window.mainFrame.setLineWidth(0)
        window.mainFrame.setMidLineWidth(0)
        window.mainFrame.setContentsMargins(0, 0, 0, 0)
        window.mainFrame.setLayout(window.mainLayout)

        window.mainFrame.setMinimumWidth(360)  # The window may shrink this far; the layout switches to stacked well before that
        window.setCentralWidget(window.mainFrame)

    def newMessage(self, message):
        # append() starts a new block for every message, so grouped chat lines and events stack instead of running on
        self.outputbox.append(message)
        self.outputbox.moveCursor(QtGui.QTextCursor.End)

    def resetList(self):
        self.listbox.setText("")

    def newListItem(self, item):
        self.listbox.moveCursor(QtGui.QTextCursor.End)
        self.listbox.insertHtml(item)
        self.listbox.moveCursor(QtGui.QTextCursor.End)

    def updatePlaybackFrameVisibility(self):
        self.playbackFrame.setVisible(self.playbackAction.isChecked())

    def updateAutoplayVisibility(self):
        self.autoplayFrame.setVisible(self.autoplayAction.isChecked())

    def updateEmptyRoomVisiblity(self):
        self.hideEmptyRooms = self.hideEmptyRoomsAction.isChecked()
        if self._syncplayClient:
            self._syncplayClient.getUserList()

    def changeReadyState(self):
        self.updateReadyIcon()
        if self._syncplayClient:
            self._syncplayClient.changeReadyState(self.readyPushButton.isChecked())
        else:
            self.showDebugMessage("Tried to change ready state too soon.")

    def changePlaylistEnabledState(self):
        self._syncplayClient.changePlaylistEnabledState(self.playlistGroup.isChecked())

    @needsClient
    def changeAutoplayThreshold(self, source=None):
        self._syncplayClient.changeAutoPlayThrehsold(self.autoplayThresholdSpinbox.value())

    def updateAutoPlayState(self, newState):
        oldState = self.autoplayPushButton.isChecked()
        if newState != oldState and newState is not None:
            self.autoplayPushButton.blockSignals(True)
            self.autoplayPushButton.setChecked(newState)
            self.autoplayPushButton.blockSignals(False)
        self.updateAutoPlayIcon()

    @needsClient
    def changeAutoplayState(self, source=None):
        self.updateAutoPlayIcon()
        if self._syncplayClient:
            self._syncplayClient.changeAutoplayState(self.autoplayPushButton.isChecked())
        else:
            self.showDebugMessage("Tried to set AutoplayState too soon")

    def updateReadyIcon(self):
        """The button says where you stand: a quiet "Not ready" with an empty circle, or a soft green "Ready" with a tick."""
        ready = self.readyPushButton.isChecked()
        tokens = theme.tokens(getattr(self, "_dark", False))
        always = getattr(self, "alwaysReadyButton", None) is not None and self.alwaysReadyButton.isChecked()
        self.readyPushButton.setText(getMessage("always-ready-status" if always else "ready-state-on" if ready else "ready-state-off"))
        self.readyPushButton.setIcon(icons.icon("check" if ready else "circle", tokens["ready"] if ready else tokens["muted"], 18))
        self.readyPushButton.setIconSize(QtCore.QSize(18, 18))

    def updateAutoPlayIcon(self):
        ready = self.autoplayPushButton.isChecked()
        if ready:
            self.autoplayPushButton.setIcon(icons.icon("check", theme.tokens(getattr(self, "_dark", False))["accent"], 16))
        else:
            self.autoplayPushButton.setIcon(QtGui.QIcon())

    def automaticUpdateCheck(self):
        currentDateTimeValue = QDateTime.currentDateTime()
        privateUpdates = bool(self._syncplayClient.privateUpdateRepo())  # Builds that update from GitHub always check
        try:  # An update that was downloaded earlier and not yet installed: offer it right away
            staged = updater.stagedBuild(updater.appFolder())
            if privateUpdates and staged > BUILD:
                self._showUpdateReady("Build {}".format(staged))
        except Exception:
            pass
        if not self.config['checkForUpdatesAutomatically'] and not privateUpdates:
            return
        frequency = constants.PRIVATE_UPDATE_CHECK_FREQUENCY if privateUpdates else constants.AUTOMATIC_UPDATE_CHECK_FREQUENCY
        try:
            if self.config['lastCheckedForUpdates']:
                configLastChecked = datetime.strptime(self.config["lastCheckedForUpdates"], "%Y-%m-%d %H:%M:%S.%f")
                if self.lastCheckedForUpdates is None or configLastChecked > self.lastCheckedForUpdates.toPython():
                    self.lastCheckedForUpdates = QDateTime.fromString(self.config["lastCheckedForUpdates"], 'yyyy-MM-dd HH-mm-ss')
            if self.lastCheckedForUpdates is None:
                self.checkForUpdates()
            else:
                timeDelta = currentDateTimeValue.toPython() - self.lastCheckedForUpdates.toPython()
                if timeDelta.total_seconds() > frequency:
                    self.checkForUpdates()
        except Exception as e:
            self.showDebugMessage("Automatic check for updates failed. An update check was manually trigggered. Reason: {}".format(str(e)))
            self.checkForUpdates()

    def userCheckForUpdates(self):
        self.checkForUpdates(userInitiated=True)

    def _checkPrivateUpdate(self, userInitiated):
        """Update button for builds that update from their own GitHub releases: click, and it updates."""
        client = self._syncplayClient
        if userInitiated:
            self.showMessage(getMessage("private-update-checking"))

        def found(release):
            if not updater.isNewer(release, appDir=updater.appFolder()):
                message = getMessage("private-update-uptodate").format(BUILD)
                if userInitiated:
                    QtWidgets.QMessageBox.information(self, branding.NAME, message)
                else:
                    self.showMessage(message)
                return
            if userInitiated:
                self._installPrivateUpdate(release)  # They clicked Update: no questions, just do it
            else:  # Startup check: never interrupt with a popup; fetch it quietly and offer a restart
                self._downloadUpdateQuietly(release)

        def failed(failure):
            reason = str(failure.value) if failure.check(updater.UpdateError) else getMessage("subtitle-search-failed-error")
            message = getMessage("private-update-failed").format(reason)
            if userInitiated:
                QtWidgets.QMessageBox.warning(self, branding.NAME, message)
            else:
                self.showDebugMessage(message)

        client.checkPrivateUpdate().addCallbacks(found, failed)

    def _downloadUpdateQuietly(self, release):
        """Download and stage the update in the background, then show a slim bar offering to restart. Nothing is
        interrupted; if you ignore the bar the update is installed the next time the app starts."""
        client = self._syncplayClient
        appDir = updater.appFolder()
        if updater.stagedBuild(appDir) >= release.build:
            self._showUpdateReady(release.name)
            return
        if self._updateDownloading:
            return
        self._updateDownloading = True

        def staged(count):
            self._updateDownloading = False
            self._showUpdateReady(release.name)

        def failed(failure):
            self._updateDownloading = False
            self.showDebugMessage("Background update download failed: {}".format(failure.getErrorMessage()))

        client.installPrivateUpdate(release, None).addCallbacks(staged, failed)

    def _showUpdateReady(self, name):
        self.updateBarLabel.setText(getMessage("update-bar-ready").format(name))
        self.updateBar.show()

    def restartForUpdate(self):
        try:
            self._syncplayClient.restartSyncplay()
        except OSError:
            QtWidgets.QMessageBox.information(self, branding.NAME, getMessage("private-update-restart-manually"))

    def _installPrivateUpdate(self, release):
        progress = QtWidgets.QProgressDialog(getMessage("private-update-installing").format(release.name), None, 0, 100, self)
        progress.setWindowTitle(branding.NAME)
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setValue(0)

        def report(done, total):  # Runs in the download thread, so hop back to the UI thread
            if total:
                from twisted.internet import reactor
                reactor.callFromThread(progress.setValue, min(99, int(done * 100 / total)))

        def installed(count):
            progress.setLabelText(getMessage("private-update-restarting"))
            progress.setValue(100)
            try:
                self._syncplayClient.restartSyncplay()
            except OSError:
                progress.close()
                QtWidgets.QMessageBox.information(self, branding.NAME, getMessage("private-update-restart-manually"))
            else:
                progress.close()

        def failed(failure):
            progress.close()
            reason = str(failure.value) if failure.check(updater.UpdateError) else getMessage("subtitle-search-failed-error")
            QtWidgets.QMessageBox.warning(self, branding.NAME, getMessage("private-update-failed").format(reason))

        self._syncplayClient.installPrivateUpdate(release, report).addCallbacks(installed, failed)

    @needsClient
    def checkForUpdates(self, userInitiated=False):
        self.lastCheckedForUpdates = QDateTime.currentDateTime()
        if self._syncplayClient.privateUpdateRepo():
            return self._checkPrivateUpdate(userInitiated)
        # No update source yet: ask for one (never phone the original Syncplay update server from this edition)
        if userInitiated:
            self.setUpdateSource(thenCheck=True)
        return

    @needsClient
    def setUpdateSource(self, thenCheck=False):
        current = self._syncplayClient.privateUpdateRepo() or ""
        text, ok = QtWidgets.QInputDialog.getText(
            self, branding.NAME, getMessage("update-source-prompt"), QtWidgets.QLineEdit.Normal, current)
        if not ok or not text.strip():
            return
        try:
            repo = self._syncplayClient.saveUpdateRepo(text)
        except (ValueError, OSError) as e:
            QtWidgets.QMessageBox.warning(self, branding.NAME, str(e))
            return
        self.showMessage(getMessage("update-source-saved").format(repo))
        if thenCheck:
            self.checkForUpdates(userInitiated=True)

    def dragEnterEvent(self, event):
        data = event.mimeData()
        urls = data.urls()
        if urls and urls[0].scheme() == 'file':
            event.acceptProposedAction()

    def dropEvent(self, event):
        rewindFile = False
        if QtGui.QDropEvent.proposedAction(event) == Qt.MoveAction:
            QtGui.QDropEvent.setDropAction(event, Qt.CopyAction)  # Avoids file being deleted
            rewindFile = True
        data = event.mimeData()
        urls = data.urls()
        if urls and urls[0].scheme() == 'file':
            url = event.mimeData().urls()[0]
            if isMacOS() and IsPySide:
                macURL = NSString.alloc().initWithString_(str(url.toString()))
                pathString = macURL.stringByAddingPercentEscapesUsingEncoding_(NSUTF8StringEncoding)
                dropfilepath = os.path.abspath(NSURL.URLWithString_(pathString).filePathURL().path())
            else:
                dropfilepath = os.path.abspath(str(url.toLocalFile()))
            if rewindFile == False:
                self._syncplayClient.openFile(dropfilepath, resetPosition=False, fromUser=True)
            else:
                self._syncplayClient.setPosition(0)
                self._syncplayClient.openFile(dropfilepath, resetPosition=True, fromUser=True)
                self._syncplayClient.setPosition(0)

    def setPlaylist(self, newPlaylist, newIndexFilename=None):
        if self.updatingPlaylist:
            self.ui.showDebugMessage("Trying to set playlist while it is already being updated")
        if newPlaylist == self.playlistState:
            if newIndexFilename:
                self.playlist.setPlaylistIndexFilename(newIndexFilename)
            self.updatingPlaylist = False
            return
        self.updatingPlaylist = True
        if newPlaylist and len(newPlaylist) > 0:
            self.clearedPlaylistNote = True
        self.playlistState = newPlaylist
        self.playlist.updatePlaylist(newPlaylist)
        if newIndexFilename:
            self.playlist.setPlaylistIndexFilename(newIndexFilename)
        self.updatingPlaylist = False
        self._syncplayClient.fileSwitch.updateInfo()

    def setPlaylistIndexFilename(self, filename):
        self.playlist.setPlaylistIndexFilename(filename)

    def addFileToPlaylist(self, filePath, index=-1):
        if not isURL(filePath):
            self.removePlaylistNote()
            filename = os.path.basename(filePath)
            if self.noPlaylistDuplicates(filename):
                if self.playlist == -1 or index == -1:
                    self.playlist.addItem(filename)
                else:
                    self.playlist.insertItem(index, filename)
                self._syncplayClient.fileSwitch.notifyUserIfFileNotInMediaDirectory(filename, filePath)
        else:
            self.removePlaylistNote()
            if self.noPlaylistDuplicates(filePath):
                if self.playlist == -1 or index == -1:
                    self.playlist.addItem(filePath)
                else:
                    self.playlist.insertItem(index, filePath)

    def openFile(self, filePath, resetPosition=False, fromUser=False):
        self._syncplayClient.openFile(filePath, resetPosition, fromUser=fromUser)

    def noPlaylistDuplicates(self, filename):
        if self.isItemInPlaylist(filename):
            self.showErrorMessage(getMessage("cannot-add-duplicate-error").format(filename))
            return False
        else:
            return True

    def isItemInPlaylist(self, filename):
        for playlistindex in range(self.playlist.count()):
            if self.playlist.item(playlistindex).text() == filename:
                return True
        return False

    def addStreamToPlaylist(self, streamURI):
        self.removePlaylistNote()
        if self.noPlaylistDuplicates(streamURI):
            self.playlist.addItem(streamURI)

    def removePlaylistNote(self):
        if not self.clearedPlaylistNote:
            for index in range(self.playlist.count()):
                self.playlist.takeItem(0)
            self.clearedPlaylistNote = True

    def addFolderToPlaylist(self, folderPath):
        self.showErrorMessage("You tried to add the folder '{}' to the playlist. Syncplay only currently supports adding files to the playlist.".format(folderPath))  # TODO: Implement "add folder to playlist"

    def deleteSelectedPlaylistItems(self):
        self.playlist.remove_selected_items()

    def saveSettings(self):
        settings = QSettings("Syncplay", "MainWindow")
        settings.beginGroup("MainWindow")
        settings.setValue("size", self.size())
        settings.setValue("pos", self.pos())
        settings.setValue("showPlaybackButtons", self.playbackAction.isChecked())
        settings.setValue("showAutoPlayButton", self.autoplayAction.isChecked())
        settings.setValue("hideEmptyRooms", self.hideEmptyRoomsAction.isChecked())
        settings.setValue("autoplayChecked", self.autoplayPushButton.isChecked())
        settings.setValue("autoplayMinUsers", self.autoplayThresholdSpinbox.value())
        settings.endGroup()
        settings = QSettings("Syncplay", "Interface")
        settings.beginGroup("Update")
        settings.setValue("lastCheckedQt", self.lastCheckedForUpdates)
        settings.endGroup()
        settings.beginGroup("PublicServerList")
        if self.publicServerList:
            settings.setValue("publicServers", self.publicServerList)
        settings.endGroup()

    def loadSettings(self):
        settings = QSettings("Syncplay", "MainWindow")
        settings.beginGroup("MainWindow")
        self.resize(settings.value("size", QSize(700, 500)))
        movePos = settings.value("pos", QPoint(200, 200))
        if not IsPySide6:
            windowGeometry = QtWidgets.QApplication.desktop().availableGeometry(self)
        else:
            windowGeometry = QtWidgets.QApplication.primaryScreen().geometry()
        posIsOnScreen = windowGeometry.contains(QtCore.QRect(movePos.x(), movePos.y(), 1, 1))
        if not posIsOnScreen:
            movePos = QPoint(200,200)
        self.move(movePos)
        if settings.value("showPlaybackButtons", "false") == "true":
            self.playbackAction.setChecked(True)
            self.updatePlaybackFrameVisibility()
        if settings.value("showAutoPlayButton", "false") == "true":
            self.autoplayAction.setChecked(True)
            self.updateAutoplayVisibility()
        if settings.value("hideEmptyRooms", "false") == "true":
            self.hideEmptyRooms = True
            self.hideEmptyRoomsAction.setChecked(True)
        if settings.value("autoplayChecked", "false") == "true":
            self.updateAutoPlayState(True)
            self.autoplayPushButton.setChecked(True)
        self.autoplayThresholdSpinbox.blockSignals(True)
        self.autoplayThresholdSpinbox.setValue(int(settings.value("autoplayMinUsers", 2)))
        self.autoplayThresholdSpinbox.blockSignals(False)
        settings.endGroup()
        settings = QSettings("Syncplay", "Interface")
        settings.beginGroup("Update")
        self.lastCheckedForUpdates = settings.value("lastCheckedQt", None)
        settings.endGroup()
        settings.beginGroup("PublicServerList")
        self.publicServerList = settings.value("publicServers", None)

    def __init__(self, passedBar=None):
        super(MainWindow, self).__init__()
        self.console = ConsoleInGUI()
        self.console.setDaemon(True)
        self.newWatchlist = []
        self.publicServerList = []
        self.lastCheckedForUpdates = None
        self._syncplayClient = None
        self.folderSearchEnabled = True
        self.hideEmptyRooms = False
        self.currentRooms = []
        self.QtGui = QtGui
        if isMacOS():
            self.setWindowFlags(self.windowFlags())
        elif not (isWindows() and IsPySide6):
            try:    
                self.setWindowFlags(self.windowFlags() & Qt.AA_DontUseNativeMenuBar)
            except TypeError:
                self.setWindowFlags(self.windowFlags())
        self.setWindowTitle("{} \u2013 build {}".format(branding.NAME, BUILD))
        self.mainLayout = QtWidgets.QVBoxLayout()
        self.mainLayout.setContentsMargins(16, 8, 16, 12)
        self.mainLayout.setSpacing(12)
        self._readinessSupported = True
        self.addTopLayout(self)
        self.addBottomLayout(self)
        self.loadMenubar(self, passedBar)
        self.populateMenubar(self)
        self.addMainFrame(self)
        self._setUpTray()
        self.buildStatusBar()
        self.loadSettings()
        self.applyTheme()
        self.setWindowIcon(QtGui.QPixmap(resourcespath + "syncplay.png"))
        if isWindows() and IsPySide6:
            self.setWindowFlags(Qt.Window | Qt.WindowTitleHint | Qt.WindowSystemMenuHint | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint | Qt.CustomizeWindowHint)
        else:
            self.setWindowFlags(self.windowFlags() & Qt.WindowCloseButtonHint & Qt.WindowMinimizeButtonHint & ~Qt.WindowContextHelpButtonHint)
        self.show()
        self.setAcceptDrops(True)
        self.clearedPlaylistNote = False
        self.uiMode = constants.GRAPHICAL_UI_MODE