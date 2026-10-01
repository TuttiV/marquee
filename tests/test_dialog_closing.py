import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from twisted.internet import defer

try:
    from syncplay.vendor.Qt import QtCore, QtGui, QtTest, QtWidgets
    from syncplay.vendor.Qt.QtCore import Qt
    from syncplay.ui.SubtitleDialog import SubtitleDialog
    from syncplay.ui.TorBoxDialog import TorBoxDialog
    HAVE_QT = True
except Exception:
    HAVE_QT = False


class Client(object):
    class userlist:
        class currentUser:
            file = None

    def hasOpenSubtitlesKey(self):
        return True

    hasTorBoxKey = hasOpenSubtitlesKey

    def openSubtitlesKeyStatus(self):
        return "own", "ABCD"

    def canShareSubtitles(self):
        return False

    def currentSubtitleLanguages(self):
        return "en"

    def savedOpenSubtitlesKey(self):
        return "SAVEDKEY" if self.hasOpenSubtitlesKey() else None

    def saveSubtitleLanguages(self, languages):
        pass

    def autoSubtitlesEnabled(self):
        return False

    def setAutoSubtitles(self, enabled):
        pass

    def searchSubtitles(self, languages=None):
        return defer.succeed([])

    def torboxLibrary(self):
        return defer.succeed([])


@unittest.skipUnless(HAVE_QT, "Qt not available")
class ClosingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def dialogs(self):
        for make in (lambda: SubtitleDialog(Client()), lambda: TorBoxDialog(Client())):
            dialog = make()
            self.addCleanup(dialog.close)
            yield dialog

    def test_close_button_hint_is_present_so_the_x_is_enabled(self):
        for dialog in self.dialogs():
            flags = dialog.windowFlags()
            self.assertTrue(flags & Qt.WindowCloseButtonHint, type(dialog).__name__)
            self.assertTrue(flags & Qt.WindowTitleHint)
            self.assertTrue(flags & Qt.WindowSystemMenuHint)

    def test_x_close_button_and_escape_all_hide_the_window(self):
        for dialog in self.dialogs():
            for how in ("x", "button", "escape"):
                dialog.show()
                self.app.processEvents()
                self.assertTrue(dialog.isVisible())
                if how == "x":
                    dialog.close()
                elif how == "button":
                    next(b for b in dialog.findChildren(QtWidgets.QPushButton) if b.text() == "Close").click()
                else:
                    QtTest.QTest.keyClick(dialog, Qt.Key_Escape)
                self.app.processEvents()
                self.assertFalse(dialog.isVisible(), "{} via {}".format(type(dialog).__name__, how))

    def test_can_be_reopened_after_closing(self):
        for dialog in self.dialogs():
            dialog.show()
            dialog.close()
            dialog.refresh()
            dialog.show()
            self.assertTrue(dialog.isVisible())


if __name__ == "__main__":
    unittest.main()
