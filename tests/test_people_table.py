import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from unittest.mock import MagicMock
    from syncplay.vendor.Qt import QtGui, QtWidgets
    from syncplay.vendor.Qt.QtCore import Qt
    from syncplay.client import SyncplayUser
    from syncplay.ui import theme
    from syncplay.ui.gui import MainWindow, ModernUserlistDelegate
    from syncplay.ui.panels import ProgressStrip
    HAVE_QT = True
except Exception:
    HAVE_QT = False

CONFIG = {"host": "h", "port": 1, "password": "", "sharedPlaylistEnabled": True, "mediaSearchDirectories": ["/x"], "readyAtStart": False,
          "alwaysReady": False, "autoplayInitialState": None, "autoplayMinUsers": -1, "roomList": [], "chatOutputEnabled": True,
          "checkForUpdatesAutomatically": False, "lastCheckedForUpdates": ""}


def person(name, ready, file_=("Show.mkv", 300.0, 10 * 1024 * 1024)):
    user = SyncplayUser(name, "r")
    if file_:
        user.setFile(*file_, path="/x/f")
    user.setReady(ready)
    return user


@unittest.skipUnless(HAVE_QT, "Qt not available")
class TableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def setUp(self):
        self.window = MainWindow()
        self.addCleanup(self.window.close)
        self.me = person("Me", True)
        self.client = MagicMock()
        self.client.getConfig.return_value = dict(CONFIG)
        self.client.getRoom.return_value = "r"
        self.client.userlist.currentUser = self.me
        self.client.getGlobalPosition.return_value = 75.0
        self.client.getGlobalPaused.return_value = False
        self.window.addClient(self.client)
        self.window.getFileSwitchState = lambda name: None
        self.window.resize(1000, 640)
        self.window.show()

    def show(self, others):
        self.window.showUserList(self.me, {"r": [self.me] + others})
        self.window.updateNowCard(self.me, {"r": [self.me] + others})
        self.app.processEvents()

    def test_the_table_shows_who_has_which_file_and_subtitle(self):
        self.client.subtitleFor.side_effect = lambda name: {"Ann": "Show.en.srt"}.get(name)
        self.show([person("Ann", False)])
        view = self.window.listTreeView
        self.assertFalse(view.header().isHidden())
        self.assertEqual([view.isColumnHidden(c) for c in range(5)], [False, True, True, False, False])
        self.assertIsInstance(view.itemDelegate(), ModernUserlistDelegate)
        room = view.model().item(0)
        self.assertEqual(room.rowCount(), 2)
        self.assertEqual(room.child(1, 0).text(), "Ann")
        self.assertEqual(room.child(1, 3).text(), self.me.file["name"])
        self.assertEqual(room.child(1, 4).text(), "Show.en.srt")
        self.assertEqual(room.child(0, 4).text(), "")  # Nothing known for you
        self.assertTrue(self.window.listlabel.isHidden())

    def test_a_different_file_turns_amber_with_the_reason_in_its_tooltip(self):
        self.show([person("Cy", True, ("Other.mkv", 999.0, 5))])
        room = self.window.listTreeView.model().item(0)
        tokens = theme.tokens(self.window._dark)
        item = room.child(1, 3)
        self.assertEqual(item.foreground().color().name(), QtGui.QColor(tokens["warn"]).name())
        self.assertIn("different", item.toolTip().lower())

    def test_rows_paint_in_every_state_in_both_themes(self):
        self.show([person("Ann", False), person("Bo", None, None), person("Cy", True, ("Other.mkv", 999.0, 5))])
        view = self.window.listTreeView
        for dark in (True, False):
            palette = view.palette()
            palette.setColor(QtGui.QPalette.Window, QtGui.QColor("#101010" if dark else "#f0f0f0"))
            view.setPalette(palette)
            pixmap = view.viewport().grab()  # Paints every visible row through the delegate
            self.assertFalse(pixmap.isNull())

    def test_the_room_shows_as_a_link_that_opens_the_box_and_folds_away_after_joining(self):
        self.show([person("Ann", True)])
        self.me.room = "r"
        self.window.updateStatusBar(self.me, {"r": [self.me]})
        self.assertFalse(self.window.roomLink.isHidden())
        self.assertIn("r", self.window.roomLink.text())
        self.assertTrue(self.window.roomFrame.isHidden())
        self.window.roomLink.click()
        self.assertFalse(self.window.roomFrame.isHidden())
        self.assertTrue(self.window.roomLink.isHidden())
        self.window.config["autosaveJoinsToList"] = False
        self.window.roomsCombobox.setEditText("other")
        self.window.joinRoom()
        self.assertTrue(self.window.roomFrame.isHidden())
        self.assertIn("other", self.window.roomLink.text())

    def test_room_options_live_in_a_menu_and_drive_the_switches(self):
        menu = self.window.tuneButton.menu()
        self.assertEqual(len(menu.actions()), 2)
        self.window.alwaysReadyButton.setChecked(False)
        menu.actions()[1].trigger()
        self.assertTrue(self.window.dropoutSwitch.isChecked())

    def test_alone_in_the_room_offers_an_invite_and_it_goes_away_with_company(self):
        self.show([])
        self.assertFalse(self.window.aloneCard.isHidden())
        self.show([person("Ann", True)])
        self.assertTrue(self.window.aloneCard.isHidden())

    def test_progress_strip_follows_the_room_position(self):
        self.window._tickProgress()
        self.assertAlmostEqual(self.window.progressStrip.fraction(), 75.0 / 300.0)
        self.client.getGlobalPosition.side_effect = RuntimeError("no client yet")
        self.window._tickProgress()  # Must never raise inside the timer
        self.assertEqual(self.window.progressStrip.fraction(), 0.0)
        strip = ProgressStrip()
        strip.setState(500, 200, False, True)
        self.assertEqual(strip.fraction(), 1.0)
        strip.setState(None, 0, True, False)
        self.assertEqual(strip.fraction(), 0.0)
        strip.grab()

    def test_the_status_bar_carries_the_padlock_and_the_header_has_the_library_button(self):
        self.assertTrue(self.window.statusBar().isAncestorOf(self.window.sslButton))
        self.window.libraryChip.click()  # Opens the TorBox window (the dialog itself is tested elsewhere)
        self.assertTrue(self.window._torboxDialog.isVisible())
        self.window._torboxDialog.close()

    def test_narrow_windows_stack_chat_over_people_and_shrink_the_header(self):
        self.window.resize(1000, 700)
        self.app.processEvents()
        self.assertEqual(self.window.topSplit.orientation(), Qt.Horizontal)
        self.assertEqual(self.window.subtitlesChip.text(), "Subtitles")
        self.window.resize(420, 760)
        self.app.processEvents()
        self.assertLess(self.window.width(), self.window.NARROW_WIDTH)
        self.assertEqual(self.window.topSplit.orientation(), Qt.Vertical)
        self.assertEqual(self.window.subtitlesChip.text(), "")
        self.assertTrue(self.window.subtitlesChip.toolTip())  # Icon-only buttons keep their tooltips
        self.show([person("Ann", True, ("Other.mkv", 999.0, 5))])
        self.assertTrue(self.window.listTreeView.isColumnHidden(1))  # Still hidden after the table is rebuilt
        self.assertFalse(self.window.listTreeView.isColumnHidden(3))
        self.assertTrue(self.window.listTreeView.isColumnHidden(4))  # The subtitle column gives way in a narrow window
        self.window.resize(1000, 700)
        self.app.processEvents()
        self.assertEqual(self.window.topSplit.orientation(), Qt.Horizontal)
        self.assertEqual(self.window.subtitlesChip.text(), "Subtitles")
        self.assertFalse(self.window.listTreeView.isColumnHidden(4))

    def test_the_window_can_shrink_to_a_companion_width(self):
        self.window.resize(380, 700)
        self.app.processEvents()
        self.assertLessEqual(self.window.width(), 420)

    def test_the_subtitle_note_says_what_is_loaded_or_that_automatic_is_on(self):
        self.client.lastSharedSubtitle = ("Show.S01E01.srt", "/tmp/x.srt")
        self.client._subtitleAppliedFor = "Show.mkv"
        self.client.autoSubtitlesEnabled.return_value = False
        self.window._tickProgress()
        self.assertEqual(self.window.statusSubtitleLabel.text(), "Subtitles: Show.S01E01.srt")
        self.client._subtitleAppliedFor = "Another.mkv"  # Loaded for some other video
        self.window._tickProgress()
        self.assertEqual(self.window.statusSubtitleLabel.text(), "")
        self.client.autoSubtitlesEnabled.return_value = True
        self.window._tickProgress()
        self.assertEqual(self.window.statusSubtitleLabel.text(), "Subtitles: automatic")

    def test_the_ready_button_states_where_you_stand(self):
        button = self.window.readyPushButton
        button.setChecked(False)
        self.window.updateReadyIcon()
        self.assertEqual(button.text(), "Not ready")
        self.assertFalse(button.icon().isNull())
        button.setChecked(True)
        self.window.updateReadyIcon()
        self.assertEqual(button.text(), "Ready")
        self.window.alwaysReadyChanged(True)
        self.assertEqual(button.text(), "You're always ready")
        button.grab()

    def test_the_playlist_strip_grows_when_something_is_queued(self):
        self.window._fitPlaylist()
        emptyBottom = self.window.listSplit.sizes()[1]
        self.window.playlist.addItem("Show.S01E01.mkv")
        self.app.processEvents()
        self.assertGreater(self.window.listSplit.sizes()[1], emptyBottom)


if __name__ == "__main__":
    unittest.main()
