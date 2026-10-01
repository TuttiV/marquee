import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from syncplay.vendor.Qt import QtWidgets
    from syncplay.ui.SubtitleDialog import SubtitleDialog
    HAVE_QT = True
except Exception:  # No Qt binding or system libraries available
    HAVE_QT = False

from twisted.internet import defer

from syncplay import opensubtitles

R = opensubtitles.SubtitleResult
RESULTS = [R(1, "a.srt", "Show", "Show.1080p", "en", 500, True, False),
           R(2, "b.srt", "Show", "Show.720p", "en", 100, False, True)]


class FakeClient(object):
    class userlist:
        class currentUser:
            file = {"name": "Show.mkv"}

    def __init__(self, configured=True, canShare=True, search=None):
        self.configured, self.canShare = configured, canShare
        self.searchResult = search or (lambda: defer.succeed(RESULTS))
        self.searches, self.downloads, self.saved = [], [], []

    def hasOpenSubtitlesKey(self):
        return self.configured

    def openSubtitlesKeyStatus(self):
        return ("own", "ABCD") if self.configured else ("none", "")

    def forgetOpenSubtitlesSettings(self):
        self.configured = False

    def canShareSubtitles(self):
        return self.canShare

    def currentSubtitleLanguages(self):
        return "en"

    def savedOpenSubtitlesKey(self):
        return "SAVEDKEY" if self.hasOpenSubtitlesKey() else None

    def saveSubtitleLanguages(self, languages):
        self.savedLanguages = getattr(self, "savedLanguages", []) + [languages]

    def autoSubtitlesEnabled(self):
        return getattr(self, "auto", False)

    def setAutoSubtitles(self, enabled):
        self.auto = enabled

    def saveOpenSubtitlesSettings(self, *args):
        self.saved.append(args)
        self.configured = True

    def searchSubtitles(self, languages=None):
        self.searches.append(languages)
        return self.searchResult()

    def downloadSubtitle(self, result, share=True):
        self.downloads.append((result.fileId, share))
        return defer.succeed("a.srt")


@unittest.skipUnless(HAVE_QT, "Qt not available")
class SubtitleDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def make(self, **kwargs):
        client = FakeClient(**kwargs)
        dialog = SubtitleDialog(client)
        self.addCleanup(dialog.close)
        return client, dialog

    def test_searches_on_open_and_selects_best_result(self):
        client, dialog = self.make()
        self.assertEqual(client.searches, ["en"])
        self.assertEqual(dialog._table.rowCount(), 2)
        self.assertEqual(dialog._selectedResult().fileId, 1)
        self.assertTrue(dialog._useButton.isEnabled())

    def test_searching_remembers_the_language_and_the_auto_checkbox_drives_the_client(self):
        client, dialog = self.make()
        dialog._languageEdit.setText("sv, en")
        dialog.search()
        self.assertEqual(client.savedLanguages[-1], "sv,en")
        self.assertFalse(dialog._autoCheck.isChecked())
        dialog._autoCheck.setChecked(True)
        self.assertTrue(client.auto)
        dialog._autoCheck.setChecked(False)
        self.assertFalse(client.auto)
        client.auto = True
        self.assertTrue(SubtitleDialog(client)._autoCheck.isChecked())  # Reflects the saved setting when opened

    def test_blank_key_keeps_the_saved_one_when_only_the_account_changes(self):
        client, dialog = self.make()
        dialog._userEdit.setText("me")
        dialog._passEdit.setText("pw")
        dialog._saveSettings()
        self.assertEqual(client.saved[-1][0], "SAVEDKEY")
        self.assertIn("saved", dialog._keyEdit.placeholderText())

    def test_use_downloads_selected_and_shares_by_default(self):
        client, dialog = self.make()
        dialog._table.selectRow(1)
        dialog.useSelected()
        self.assertEqual(client.downloads, [(2, True)])
        self.assertIn("everyone", dialog._status.text())

    def test_share_checkbox_off_or_unsupported_loads_only_locally(self):
        client, dialog = self.make()
        dialog._shareCheck.setChecked(False)
        dialog.useSelected()
        self.assertEqual(client.downloads, [(1, False)])
        client, dialog = self.make(canShare=False)
        self.assertFalse(dialog._shareCheck.isEnabled())
        dialog.useSelected()
        self.assertEqual(client.downloads, [(1, False)])

    def test_works_without_an_api_key_and_hints_at_the_upgrade(self):
        client, dialog = self.make(configured=False)
        self.assertEqual(client.searches, ["en"])  # Keyless public catalogue is used straight away
        self.assertFalse(dialog._searchCard.isHidden())
        self.assertTrue(dialog._setupCard.isHidden())
        self.assertFalse(dialog._providerHint.isHidden())
        _, keyed = self.make(configured=True)
        self.assertTrue(keyed._providerHint.isHidden())

    def test_account_settings_are_optional_and_saving_re_searches(self):
        client, dialog = self.make(configured=False)
        dialog._settingsButton.click()
        self.assertFalse(dialog._setupCard.isHidden())
        self.assertTrue(dialog._searchCard.isHidden())
        dialog._saveSettings()  # No key entered
        self.assertEqual(client.saved, [])
        dialog._keyEdit.setText(" KEY ")
        dialog._saveSettings()
        self.assertEqual(client.saved, [("KEY", "", "")])
        self.assertTrue(dialog._setupCard.isHidden())
        self.assertEqual(client.searches, ["en", "en"])  # Old provider's results are discarded

    def test_back_leaves_settings_without_saving(self):
        client, dialog = self.make(configured=False)
        dialog._settingsButton.click()
        dialog._closeSettings()
        self.assertEqual(client.saved, [])
        self.assertFalse(dialog._searchCard.isHidden())

    def test_errors_are_shown_inline(self):
        _, dialog = self.make(search=lambda: defer.fail(opensubtitles.OpenSubtitlesError("Invalid API key")))
        self.assertEqual(dialog._status.text(), "Invalid API key")
        self.assertEqual(dialog._table.rowCount(), 0)

    def test_stale_results_are_ignored_after_close(self):
        pending = defer.Deferred()
        client, dialog = self.make(search=lambda: pending)
        dialog.close()
        pending.callback(RESULTS)
        self.assertEqual(dialog._table.rowCount(), 0)


@unittest.skipUnless(HAVE_QT, "Qt not available")
class AccountStatusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_shows_which_key_is_in_use_and_offers_forget_only_for_your_own(self):
        client = FakeClient(configured=True)
        dialog = SubtitleDialog(client)
        self.addCleanup(dialog.close)
        self.assertIn("ABCD", dialog._accountStatus.text())
        self.assertFalse(dialog._forgetButton.isHidden())
        dialog._forgetSettings()
        self.assertFalse(client.configured)
        self.assertTrue(dialog._forgetButton.isHidden())

    def test_a_failed_save_stays_on_the_form_and_shows_the_reason(self):
        client = FakeClient(configured=False)
        client.saveOpenSubtitlesSettings = lambda *a: (_ for _ in ()).throw(OSError("Could not save your OpenSubtitles key: disk full"))
        dialog = SubtitleDialog(client)
        self.addCleanup(dialog.close)
        dialog._settingsButton.click()
        dialog._keyEdit.setText("KEY")
        dialog._saveSettings()
        self.assertIn("disk full", dialog._status.text())
        self.assertFalse(dialog._setupCard.isHidden())
        self.assertEqual(dialog._keyEdit.text(), "KEY")  # Not wiped, so the user can retry


if __name__ == "__main__":
    unittest.main()
