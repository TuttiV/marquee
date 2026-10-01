import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from syncplay import constants, instance, invite

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class LinkTests(unittest.TestCase):
    def test_round_trip_including_awkward_room_names(self):
        for host, port, room in (("syncplay.pl", 8997, "room-abc"), ("example.org", 9000, "Movie Night #1 & more"),
                                 ("192.168.1.5", 8999, "r\u00e4ksm\u00f6rg\u00e5s"), ("::1", 8999, "v6 room"), ("a-b.example.com", 1, "x")):
            link = invite.make(host, port, room)
            self.assertNotIn(" ", link)
            self.assertEqual(invite.parse(link), (host, port, room), link)

    def test_port_defaults_and_scheme_is_case_insensitive(self):
        self.assertEqual(invite.parse("Syncplay-Marquee://example.org/room"), ("example.org", constants.DEFAULT_PORT, "room"))

    def test_anything_odd_is_refused(self):
        S = invite.SCHEME
        bad = [None, "", "hello", "https://example.org:80/room", "syncplay://example.org:8999/room", S + "://", S + ":///room",
               S + "://example.org:8999", S + "://example.org:8999/", S + "://example.org:8999/%20%20", S + "://exa mple.org/room",
               S + "://example.org:99999/room", S + "://example.org:abc/room", S + "://-bad.example/room", S + "://example.org:8999/a%00b",
               S + "://example.org:8999/" + "x" * (constants.MAX_ROOM_NAME_LENGTH + 1), S + "://example.org:8999/room\nsecond", S + "://" + "a" * 500 + "/r",
               S + "://user:pass@example.org:8999/room" + "\x07"]
        for text in bad:
            self.assertIsNone(invite.parse(text), repr(text))

    def test_surrounding_whitespace_is_ignored(self):
        self.assertEqual(invite.parse("  " + invite.make("h.example", 1234, "r") + " \n"), ("h.example", 1234, "r"))

    def test_random_rooms_are_unique_short_enough_and_unambiguous(self):
        names = {invite.randomRoomName() for _ in range(2000)}
        self.assertEqual(len(names), 2000)
        for name in list(names)[:100]:
            self.assertLessEqual(len(name), constants.MAX_ROOM_NAME_LENGTH)
            self.assertTrue(name.startswith("room-"))
            self.assertFalse(set(name[5:]) & set("0oO1lI"))

    def test_host_argument_and_same_server_and_fitting_setup(self):
        link = invite.Invite("example.org", 9000, "r")
        self.assertEqual(invite.hostArgument(link), "example.org:9000")
        self.assertEqual(invite.hostArgument(invite.Invite("::1", 8999, "r")), "[::1]:8999")
        self.assertTrue(invite.sameServer(link, "EXAMPLE.org", "9000"))
        self.assertFalse(invite.sameServer(link, "example.org", 9001))
        self.assertFalse(invite.sameServer(link, None, 9000))
        self.assertTrue(invite.fitsSavedSetup(link, "Tutti", "example.org", 9000))
        self.assertFalse(invite.fitsSavedSetup(link, "", "example.org", 9000))  # No name yet: show the start dialog
        self.assertFalse(invite.fitsSavedSetup(link, "Tutti", "other.example", 9000))  # New server: let them check it
        self.assertFalse(invite.fitsSavedSetup(link, "Tutti", None, None))


class FakeWinreg(object):
    HKEY_CURRENT_USER = "HKCU"
    KEY_WRITE = 2
    REG_SZ = 1

    def __init__(self):
        self.values = {}

    class _Key(object):
        def __init__(self, path):
            self.path = path

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def CreateKeyEx(self, root, path, reserved, access):
        return self._Key(path)

    def OpenKey(self, root, path):
        if not any(k[0] == path for k in self.values):
            raise FileNotFoundError(path)
        return self._Key(path)

    def SetValueEx(self, key, name, reserved, kind, value):
        self.values[(key.path, name)] = value

    def QueryValueEx(self, key, name):
        return (self.values[(key.path, name)], 1)

    def DeleteKey(self, root, path):
        if not any(k[0] == path for k in self.values):
            raise FileNotFoundError(path)
        for k in [k for k in self.values if k[0] == path]:
            del self.values[k]


class RegistrationTests(unittest.TestCase):
    def test_register_detect_change_and_remove(self):
        reg = FakeWinreg()
        command = invite.handlerCommand(r"C:\app\python\pythonw.exe", r"C:\app\program\launch-syncplay.pyw")
        self.assertEqual(command, '"C:\\app\\python\\pythonw.exe" "C:\\app\\program\\launch-syncplay.pyw" "%1"')
        self.assertFalse(invite.isHandlerRegistered(command, reg))
        invite.registerHandler(command, r"C:\app\icon.ico", reg)
        self.assertTrue(invite.isHandlerRegistered(command, reg))
        self.assertEqual(reg.values[(r"Software\Classes\syncplay-marquee", "URL Protocol")], "")
        self.assertIn(r"C:\app\icon.ico", reg.values[(r"Software\Classes\syncplay-marquee\DefaultIcon", "")])
        self.assertFalse(invite.isHandlerRegistered(command.replace("python", "other"), reg))  # A moved runtime is noticed
        invite.unregisterHandler(reg)
        self.assertEqual(reg.values, {})
        invite.unregisterHandler(reg)  # Removing twice is harmless

    def test_not_available_without_windows_registry_or_launcher(self):
        if os.name != "nt":
            self.assertFalse(invite.handlerAvailable())
        self.assertFalse(invite.handlerAvailable(launcher=os.path.join(tempfile.gettempdir(), "nope.pyw"), reg=FakeWinreg()))


class InstanceTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)

    def writeLock(self, pid, age):
        with open(os.path.join(self.dir, "instance.json"), "w") as f:
            json.dump({"pid": pid, "time": time.time() - age}, f)

    def test_another_live_copy_is_detected_and_a_stale_or_own_one_is_not(self):
        self.assertFalse(instance.primaryRunning(self.dir))
        self.writeLock(os.getpid() + 1, 1)
        self.assertTrue(instance.primaryRunning(self.dir))
        self.writeLock(os.getpid() + 1, instance.STALE_SECONDS + 5)
        self.assertFalse(instance.primaryRunning(self.dir))  # It crashed without cleaning up
        instance.beat(self.dir)
        self.assertFalse(instance.primaryRunning(self.dir))  # That's me
        with open(os.path.join(self.dir, "instance.json"), "w") as f:
            f.write("garbage")
        self.assertFalse(instance.primaryRunning(self.dir))

    def test_links_are_handed_over_once(self):
        instance.handOff(self.dir, "syncplay-marquee://h:1/a")
        instance.handOff(self.dir, "syncplay-marquee://h:1/b\nevil")
        self.assertEqual(instance.takeInbox(self.dir), ["syncplay-marquee://h:1/a", "syncplay-marquee://h:1/b evil"])
        self.assertEqual(instance.takeInbox(self.dir), [])
        self.assertEqual([n for n in os.listdir(self.dir) if "taking" in n or "inbox" in n], [])

    def test_release_removes_only_my_own_lock(self):
        self.writeLock(os.getpid() + 1, 0)
        instance.release(self.dir)
        self.assertTrue(os.path.exists(os.path.join(self.dir, "instance.json")))
        instance.beat(self.dir)
        instance.release(self.dir)
        self.assertFalse(os.path.exists(os.path.join(self.dir, "instance.json")))


class StartupTests(unittest.TestCase):
    """The real ConfigurationGetter, run in a scratch home with the console front end."""

    def run_getter(self, *arguments, before=None):
        home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, home, True)
        player = os.path.join(home, "vlc")
        with open(player, "w") as f:
            f.write("#!/bin/sh\n")
        os.chmod(player, 0o755)
        if before:
            before(home)
        script = ("import sys, json\nsys.path.insert(0, %r)\nsys.argv = ['syncplay'] + sys.argv[1:]\n"
                  "from syncplay.ui.ConfigurationGetter import ConfigurationGetter\nc = ConfigurationGetter().getConfiguration()\n"
                  "print('RESULT', json.dumps({k: c.get(k) for k in ('host', 'port', 'room', 'file', 'name')}))\n") % ROOT
        env = dict(os.environ, HOME=home, XDG_CONFIG_HOME=home, QT_QPA_PLATFORM="offscreen")
        done = subprocess.run([sys.executable, "-c", script, "--no-gui", "--no-store", "-n", "Tester", "--player-path", player] + list(arguments),
                              env=env, capture_output=True, text=True, timeout=90)
        lines = [line for line in done.stdout.splitlines() if line.startswith("RESULT ")]
        return json.loads(lines[-1][7:]) if lines else {"error": done.stdout + done.stderr}, home

    def test_an_invite_link_sets_server_and_room_and_is_not_treated_as_a_file(self):
        result, _ = self.run_getter(invite.make("example.org", 9000, "room-abc123"))
        self.assertEqual((result["host"], result["port"], result["room"], result["file"]), ("example.org", 9000, "room-abc123", None))

    def test_no_room_means_a_random_private_one_but_a_chosen_room_is_kept(self):
        first, _ = self.run_getter("-a", "syncplay.pl:8997")
        second, _ = self.run_getter("-a", "syncplay.pl:8997")
        self.assertTrue(first["room"].startswith("room-"))
        self.assertNotEqual(first["room"], second["room"])
        chosen, _ = self.run_getter("-a", "syncplay.pl:8997", "-r", "Jonas123")
        self.assertEqual(chosen["room"], "Jonas123")

    def test_a_running_copy_gets_the_link_and_this_launch_exits_without_starting(self):
        link = invite.make("example.org", 9000, "room-handoff")
        home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, home, True)
        # The config folder is the folder holding the ini file (HOME on Linux); pretend another copy is running there
        with open(os.path.join(home, "instance.json"), "w") as f:
            json.dump({"pid": 10 ** 9, "time": time.time()}, f)  # Some other process (not the child's pid, which is often ours + 1)
        player = os.path.join(home, "vlc")
        with open(player, "w") as f:
            f.write("#!/bin/sh\n")
        os.chmod(player, 0o755)
        script = ("import sys\nsys.path.insert(0, %r)\nsys.argv = ['syncplay'] + sys.argv[1:]\n"
                  "from syncplay.ui.ConfigurationGetter import ConfigurationGetter\nConfigurationGetter().getConfiguration()\nprint('STARTED')\n") % ROOT
        env = dict(os.environ, HOME=home, XDG_CONFIG_HOME=home, QT_QPA_PLATFORM="offscreen")
        done = subprocess.run([sys.executable, "-c", script, "--no-gui", "--no-store", "-n", "T", "-a", "syncplay.pl", "--player-path", player, link],
                              env=env, capture_output=True, text=True, timeout=90)
        self.assertNotIn("STARTED", done.stdout, done.stdout + done.stderr)
        self.assertEqual(done.returncode, 0)
        self.assertEqual(instance.takeInbox(home), [link])


class StartWindowTests(unittest.TestCase):
    """Whether the start window (lobby) opens, using the real ConfigurationGetter with the lobby replaced by a marker."""

    def run_getter(self, ini, *arguments):
        home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, home, True)
        player = os.path.join(home, "vlc")
        with open(player, "w") as f:
            f.write("#!/bin/sh\n")
        os.chmod(player, 0o755)
        if ini is not None:
            with open(os.path.join(home, ".syncplay"), "w") as f:
                f.write("[server_data]\nhost = example.org\nport = 8999\n[client_settings]\nname = Tester\nroom = mine\nplayerpath = %s\n%s" % (player, ini))
        script = ("import sys, json\nsys.path.insert(0, %r)\nsys.argv = ['syncplay'] + sys.argv[1:]\n"
                  "from syncplay.ui.ConfigurationGetter import ConfigurationGetter\n"
                  "ConfigurationGetter._forceGuiPrompt = lambda self: print('LOBBY')\n"
                  "c = ConfigurationGetter().getConfiguration()\n"
                  "print('RESULT', json.dumps({k: str(c.get(k)) for k in ('skipStartWindow', 'startWindowAsked', 'startWindowNowSkipped')}))\n") % ROOT
        env = dict(os.environ, HOME=home, XDG_CONFIG_HOME=home, QT_QPA_PLATFORM="offscreen")
        done = subprocess.run([sys.executable, "-c", script, "--no-store", "--player-path", player] + list(arguments),
                              env=env, capture_output=True, text=True, timeout=90)
        lines = [line for line in done.stdout.splitlines() if line.startswith("RESULT ")]
        self.assertTrue(lines, done.stdout + done.stderr)
        return "LOBBY" in done.stdout, json.loads(lines[-1][7:])

    def test_a_saved_room_with_skipping_on_opens_straight_into_it(self):
        lobby, _ = self.run_getter("skipstartwindow = True\nstartwindowasked = True\n")
        self.assertFalse(lobby)

    def test_the_flag_forces_the_start_window_back(self):
        lobby, _ = self.run_getter("skipstartwindow = True\nstartwindowasked = True\n", "--force-gui-prompt")
        self.assertTrue(lobby)

    def test_with_skipping_off_the_start_window_shows(self):
        lobby, result = self.run_getter("skipstartwindow = False\nstartwindowasked = True\n")
        self.assertTrue(lobby)
        self.assertEqual(result["skipStartWindow"], "False")

    def test_an_invite_link_with_a_player_and_name_joins_without_the_start_window(self):
        link = invite.make("example.org", 9000, "room-quick")
        lobby, result = self.run_getter("", link)
        self.assertFalse(lobby)
        self.assertEqual((result["skipStartWindow"], result["startWindowAsked"]), ("True", "True"))

    def test_the_flag_still_brings_the_window_back_for_a_link(self):
        link = invite.make("example.org", 9000, "room-quick")
        lobby, _ = self.run_getter("", link, "--force-gui-prompt")
        self.assertTrue(lobby)

    def test_the_first_setup_turns_skipping_on_and_says_so_once(self):
        lobby, result = self.run_getter("")
        self.assertTrue(lobby)
        self.assertEqual((result["skipStartWindow"], result["startWindowAsked"], result["startWindowNowSkipped"]), ("True", "True", "True"))


try:
    from unittest.mock import MagicMock
    from syncplay.vendor.Qt import QtWidgets
    from syncplay.ui.gui import MainWindow
    HAVE_QT = True
except Exception:
    HAVE_QT = False

CONFIG = {"host": "example.org", "port": 9000, "password": "", "sharedPlaylistEnabled": True, "mediaSearchDirectories": ["/x"],
          "readyAtStart": False, "alwaysReady": False, "autoplayInitialState": None, "autoplayMinUsers": -1, "roomList": [],
          "chatOutputEnabled": True, "checkForUpdatesAutomatically": False, "lastCheckedForUpdates": "", "autosaveJoinsToList": False}


@unittest.skipUnless(HAVE_QT, "Qt not available")
class WindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.window = MainWindow()
        self.addCleanup(self.window.close)
        self.client = MagicMock()
        self.client.getConfig.return_value = dict(CONFIG, configDir=self.dir)
        self.client.getRoom.return_value = "current-room"
        self.window.addClient(self.client)
        self.window.showMessage = MagicMock()

    def clipboard(self):
        return QtWidgets.QApplication.clipboard().text()

    def test_copy_invite_has_a_link_and_the_plain_details(self):
        self.window.copyInvite()
        text = self.clipboard()
        self.assertIn("syncplay-marquee://example.org:9000/current-room", text)
        self.assertIn("Room: current-room", text)
        self.assertIn("example.org", text)

    def test_new_private_room_joins_a_random_room_and_copies_its_invite(self):
        self.window.privateChip.click()
        self.client.setRoom.assert_called_once()
        room = self.client.setRoom.call_args[0][0]
        self.assertTrue(room.startswith("room-"))
        self.client.sendRoom.assert_called_once()
        self.assertIn(invite.make("example.org", 9000, room), self.clipboard())

    def test_a_link_from_another_launch_joins_that_room_on_the_same_server(self):
        self.window.handleInvite(invite.make("EXAMPLE.org", 9000, "friends-room"))
        self.client.setRoom.assert_called_once_with("friends-room", resetAutoplay=True)
        self.assertIn("friends-room", self.window.showMessage.call_args[0][0])

    def test_a_link_for_another_server_or_a_bad_link_changes_nothing(self):
        self.window.handleInvite(invite.make("other.example", 9000, "x"))
        self.assertIn("other.example", self.window.showMessage.call_args[0][0])
        self.window.handleInvite("syncplay-marquee://???")
        self.assertIn("isn't valid", self.window.showMessage.call_args[0][0])
        self.client.setRoom.assert_not_called()

    def test_the_running_window_picks_up_handed_over_links_and_keeps_its_heartbeat(self):
        instance.handOff(self.dir, invite.make("example.org", 9000, "via-inbox"))
        self.window._instanceTick()
        self.client.setRoom.assert_called_once_with("via-inbox", resetAutoplay=True)
        self.assertTrue(os.path.exists(os.path.join(self.dir, "instance.json")))
        self.window.close()
        self.assertFalse(os.path.exists(os.path.join(self.dir, "instance.json")))


if __name__ == "__main__":
    unittest.main()
