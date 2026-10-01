import os
import shutil
import stat
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from syncplay import secrets
from syncplay.client import SyncplayClient


class SecretsFileTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)

    def test_round_trip_update_and_remove(self):
        self.assertIsNone(secrets.load("k", self.dir))
        secrets.save("k", "  value  ", self.dir)
        self.assertEqual(secrets.load("k", self.dir), "value")
        secrets.save("other", "x", self.dir)
        secrets.save("k", "", self.dir)  # Empty forgets just that entry
        self.assertIsNone(secrets.load("k", self.dir))
        self.assertEqual(secrets.load("other", self.dir), "x")

    def test_creates_missing_folder_and_leaves_no_temp_files(self):
        nested = os.path.join(self.dir, "a", "b")
        secrets.save("k", "v", nested)
        self.assertEqual(os.listdir(nested), [secrets.FILE_NAME])

    @unittest.skipIf(os.name == "nt", "POSIX permissions only")
    def test_file_is_owner_only(self):
        secrets.save("k", "v", self.dir)
        mode = stat.S_IMODE(os.stat(os.path.join(self.dir, secrets.FILE_NAME)).st_mode)
        self.assertEqual(mode, 0o600)

    def test_corrupt_file_reads_as_empty_and_is_replaced_on_save(self):
        with open(os.path.join(self.dir, secrets.FILE_NAME), "w") as f:
            f.write("{not json")
        self.assertIsNone(secrets.load("k", self.dir))
        secrets.save("k", "v", self.dir)
        self.assertEqual(secrets.load("k", self.dir), "v")

    def test_unwritable_location_raises_oserror(self):
        blocker = os.path.join(self.dir, "file")
        open(blocker, "w").close()
        with self.assertRaises(OSError):
            secrets.save("k", "v", os.path.join(blocker, "sub"))  # A file where a folder should be


class FakeUI(object):
    def showDebugMessage(self, *a, **k):
        pass


class ClientKeyTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)

    def client(self, config=None):
        # Never let a test touch the developer's real syncplay.ini
        patcher = mock.patch("syncplay.ui.ConfigurationGetter.ConfigurationGetter.setConfigOption")
        patcher.start()
        self.addCleanup(patcher.stop)
        client = object.__new__(SyncplayClient)
        client.ui = FakeUI()
        client._config = {"configDir": self.dir, **(config or {})}
        return client

    def test_key_survives_a_restart_even_if_the_ini_never_got_it(self):
        first = self.client()
        self.assertFalse(first.hasTorBoxKey())
        first.saveTorBoxKey("  SECRET  ")
        self.assertTrue(first.hasTorBoxKey())
        restarted = self.client({"torboxApiKey": None})  # The ini said nothing
        self.assertTrue(restarted.hasTorBoxKey())
        self.assertEqual(restarted._config["torboxApiKey"], "SECRET")

    def test_forgetting_removes_it_everywhere(self):
        client = self.client()
        client.saveTorBoxKey("SECRET")
        client.saveTorBoxKey("")
        self.assertFalse(client.hasTorBoxKey())
        self.assertFalse(self.client({"torboxApiKey": None}).hasTorBoxKey())

    def test_a_failed_save_is_reported_not_swallowed(self):
        blocker = os.path.join(self.dir, "file")
        open(blocker, "w").close()
        client = self.client({"configDir": os.path.join(blocker, "sub")})
        with self.assertRaises(OSError) as ctx:
            client.saveTorBoxKey("SECRET")
        self.assertIn("Could not save", str(ctx.exception))
        self.assertFalse(client.hasTorBoxKey())  # Not pretending it was saved


try:
    from syncplay.vendor.Qt import QtWidgets
    from syncplay.ui.TorBoxDialog import TorBoxDialog
    HAVE_QT = True
except Exception:
    HAVE_QT = False


class FailingClient(object):
    def hasTorBoxKey(self):
        return False

    def saveTorBoxKey(self, key):
        raise OSError("Could not save your TorBox API key: disk full")


@unittest.skipUnless(HAVE_QT, "Qt not available")
class DialogErrorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_save_failure_shows_in_the_dialog_and_keeps_the_setup_form(self):
        dialog = TorBoxDialog(FailingClient())
        self.addCleanup(dialog.close)
        dialog._keyEdit.setText("KEY")
        dialog._saveKey()
        self.assertIn("disk full", dialog._status.text())
        self.assertFalse(dialog._setupCard.isHidden())
        self.assertEqual(dialog._keyEdit.text(), "KEY")  # Not wiped, so the user can retry


class OpenSubtitlesAccountTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.app = tempfile.mkdtemp()
        for path in (self.dir, self.app):
            self.addCleanup(shutil.rmtree, path, True)
        patcher = mock.patch("syncplay.ui.ConfigurationGetter.ConfigurationGetter.setConfigOption")  # Never touch a real ini
        patcher.start()
        self.addCleanup(patcher.stop)
        original = secrets.bundledDefault
        patcher = mock.patch("syncplay.secrets.bundledDefault", side_effect=lambda name: original(name, self.app))
        patcher.start()
        self.addCleanup(patcher.stop)

    def client(self, config=None):
        client = object.__new__(SyncplayClient)
        client.ui = FakeUI()
        client._config = {"configDir": self.dir, **(config or {})}
        return client

    def bundle(self, key):
        with open(os.path.join(self.app, secrets.DEFAULTS_FILE_NAME), "w") as f:
            f.write('{"openSubtitlesApiKey": "%s"}' % key)

    def test_saved_account_survives_a_restart_without_the_ini(self):
        first = self.client()
        first.saveOpenSubtitlesSettings("  MYKEY1234  ", "me", "pw")
        restarted = self.client({"openSubtitlesApiKey": None})  # The ini remembered nothing
        self.assertTrue(restarted.hasOpenSubtitlesKey())
        self.assertEqual((restarted._config["openSubtitlesApiKey"], restarted._config["openSubtitlesUsername"],
                          restarted._config["openSubtitlesPassword"]), ("MYKEY1234", "me", "pw"))
        self.assertEqual(restarted.openSubtitlesKeyStatus(), ("own", "1234"))

    def test_own_key_beats_the_built_in_default_and_forgetting_falls_back(self):
        self.bundle("BUILTINKEY9999")
        client = self.client()
        self.assertEqual(client.openSubtitlesKeyStatus(), ("builtin", "9999"))
        client.saveOpenSubtitlesSettings("MYKEY1234")
        self.assertEqual(client.openSubtitlesKeyStatus(), ("own", "1234"))
        self.assertEqual(self.client().openSubtitlesKeyStatus(), ("own", "1234"))  # After a restart too
        client.forgetOpenSubtitlesSettings()
        self.assertEqual(client.openSubtitlesKeyStatus(), ("builtin", "9999"))
        self.assertEqual(self.client().openSubtitlesKeyStatus(), ("builtin", "9999"))

    def test_no_key_anywhere(self):
        self.assertEqual(self.client().openSubtitlesKeyStatus(), ("none", ""))

    def test_failed_save_is_reported_and_nothing_is_pretended(self):
        blocker = os.path.join(self.dir, "file")
        open(blocker, "w").close()
        client = self.client({"configDir": os.path.join(blocker, "sub")})
        with self.assertRaises(OSError) as ctx:
            client.saveOpenSubtitlesSettings("MYKEY1234")
        self.assertIn("Could not save", str(ctx.exception))
        self.assertEqual(client.openSubtitlesKeyStatus(), ("none", ""))


class UpdateSourceTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)

    def client(self):
        client = object.__new__(SyncplayClient)
        client.ui = FakeUI()
        client._config = {"configDir": self.dir}
        return client

    def test_repo_names_and_github_links_are_normalised_and_bad_ones_rejected(self):
        from syncplay import updater
        for text, expected in (("me/app", "me/app"), ("  me/app  ", "me/app"), ("https://github.com/me/app", "me/app"),
                               ("github.com/me/app/", "me/app"), ("https://github.com/me/app.git", "me/app"),
                               ("me", None), ("../x", None), ("me/..", None), ("", None), ("a b/c", None)):
            self.assertEqual(updater.validRepo(text), expected, text)

    def test_saved_repo_survives_a_restart_and_beats_the_bundled_default(self):
        client = self.client()
        self.assertIsNone(client.privateUpdateRepo())
        self.assertEqual(client.saveUpdateRepo("https://github.com/Me/My-App"), "Me/My-App")
        self.assertEqual(self.client().privateUpdateRepo(), "Me/My-App")
        with self.assertRaises(ValueError):
            client.saveUpdateRepo("not a repo")
        self.assertEqual(client.privateUpdateRepo(), "Me/My-App")  # A bad entry changes nothing

    def test_unwritable_location_is_reported(self):
        blocker = os.path.join(self.dir, "file")
        open(blocker, "w").close()
        client = self.client()
        client._config["configDir"] = os.path.join(blocker, "sub")
        with self.assertRaises(OSError):
            client.saveUpdateRepo("me/app")


if __name__ == "__main__":
    unittest.main()


class BundledDefaultKeyTests(unittest.TestCase):
    def setUp(self):
        self.app = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.app, True)
        self.client = object.__new__(SyncplayClient)
        self.client.ui = FakeUI()
        self.client._config = {}
        original = secrets.bundledDefault  # Read the defaults from our temp folder instead of the real app folder
        patcher = mock.patch("syncplay.secrets.bundledDefault", side_effect=lambda name: original(name, self.app))
        patcher.start()
        self.addCleanup(patcher.stop)

    def write(self, text):
        with open(os.path.join(self.app, secrets.DEFAULTS_FILE_NAME), "w") as f:
            f.write(text)

    def test_default_is_used_when_the_user_has_no_key(self):
        self.write('{"openSubtitlesApiKey": "  BUNDLED  "}')
        self.assertTrue(self.client.hasOpenSubtitlesKey())
        self.assertEqual(self.client._config["openSubtitlesApiKey"], "BUNDLED")

    def test_the_users_own_key_wins(self):
        self.write('{"openSubtitlesApiKey": "BUNDLED"}')
        self.client._config["openSubtitlesApiKey"] = "MINE"
        self.assertTrue(self.client.hasOpenSubtitlesKey())
        self.assertEqual(self.client._config["openSubtitlesApiKey"], "MINE")

    def test_missing_or_broken_defaults_mean_no_key(self):
        self.assertFalse(self.client.hasOpenSubtitlesKey())
        self.write("{nope")
        self.assertFalse(self.client.hasOpenSubtitlesKey())
        self.write('{"openSubtitlesApiKey": ""}')
        self.assertFalse(self.client.hasOpenSubtitlesKey())


if __name__ == "__main__":
    unittest.main()
