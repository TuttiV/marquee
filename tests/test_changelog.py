import os
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from syncplay import changelog

SAMPLE = """# Ignored heading
## Build 3 - Third thing
- one
* two <b>bold</b>
some prose that is ignored
## Build 10
- ten
## Build 2 – Second
- older
## Not a build
- ignored
"""


class ParseTests(unittest.TestCase):
    def test_sections_bullets_and_junk(self):
        self.assertEqual(changelog.parse(SAMPLE), [
            (3, "Third thing", ["one", "two <b>bold</b>"]), (10, "", ["ten"]), (2, "Second", ["older"])])
        self.assertEqual(changelog.parse(""), [])
        self.assertEqual(changelog.parse(None), [])

    def test_missing_file_is_just_empty(self):
        self.assertEqual(changelog.load(os.path.join(tempfile.gettempdir(), "definitely-not-here.md")), [])

    def test_shipped_changelog_parses_and_is_newest_first_by_number(self):
        entries = changelog.load()
        self.assertGreaterEqual(len(entries), 4)
        self.assertTrue(all(bullets for _, _, bullets in entries))
        self.assertEqual([b for b, _, _ in entries], sorted((b for b, _, _ in entries), reverse=True))


class RenderTests(unittest.TestCase):
    def test_newest_first_new_tags_and_not_installed_and_escaping(self):
        html = changelog.render(changelog.parse(SAMPLE), installedBuild=3, newerThan=2)
        self.assertLess(html.index("Build 10"), html.index("Build 3"))
        self.assertLess(html.index("Build 3"), html.index("Build 2"))
        self.assertIn("&lt;b&gt;bold&lt;/b&gt;", html)
        self.assertNotIn("<b>bold</b>", html)
        self.assertEqual(html.count("NEW"), 1)  # Only build 3 is newer than 2 and installed
        self.assertIn("not installed", html)  # Build 10 is ahead of what's running
        self.assertIn("You're on build 3", html)

    def test_activity_lines_and_empty_state(self):
        activity = [{"event": "updated", "from": 7, "to": 9, "time": 0},
                    {"event": "rolled-back", "from": 9, "to": 10, "time": 0}, {"event": "weird"}]
        html = changelog.render([], 9, activity)
        self.assertIn("Updated to build 9", html)
        self.assertIn("Build 10 didn&#x27;t start properly, so the app went back to build 9", html)
        self.assertIn("No release notes", html)
        self.assertEqual(html.count("<li>"), 2)


try:
    from unittest.mock import MagicMock
    from syncplay.vendor.Qt import QtWidgets
    from syncplay.ui.gui import MainWindow
    from syncplay.ui.UpdateLogDialog import UpdateLogDialog
    HAVE_QT = True
except Exception:
    HAVE_QT = False


@unittest.skipUnless(HAVE_QT, "Qt not available")
class DialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_dialog_shows_the_release_notes_and_can_be_closed(self):
        dialog = UpdateLogDialog(newerThan=0)
        self.addCleanup(dialog.close)
        text = dialog.view.toPlainText()
        self.assertIn("Update log", text)
        self.assertIn("Build 9", text)
        self.assertIn("First version", text)
        dialog.show()
        self.assertTrue(dialog.windowFlags() & dialog.windowFlags().__class__.WindowCloseButtonHint)

    def test_help_menu_has_the_entry_and_it_opens_the_dialog(self):
        window = MainWindow()
        self.addCleanup(window.close)
        client = MagicMock()
        client.getConfig.return_value = {"host": "h", "port": 1, "password": "", "sharedPlaylistEnabled": True, "mediaSearchDirectories": ["/x"],
                                         "readyAtStart": False, "alwaysReady": False, "autoplayInitialState": None, "autoplayMinUsers": -1,
                                         "roomList": [], "chatOutputEnabled": True, "checkForUpdatesAutomatically": False, "lastCheckedForUpdates": ""}
        client.getRoom.return_value = "room"
        window.addClient(client)
        self.assertEqual(window.updateLogAction.text().replace("&", ""), "Update log...")
        window.updateLogAction.trigger()
        self.assertTrue(window._updateLogDialog.isVisible())
        window._updateLogDialog.close()


if __name__ == "__main__":
    unittest.main()
