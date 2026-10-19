"""Chat arriving at an awkward moment must never knock you off the server (others would see you leave and rejoin)."""
import io
import unittest
from unittest import mock

from syncplay.client import UiManager
from syncplay.protocols import SyncClientProtocol


class Window(object):
    def __init__(self):
        self.shown = []

    def showMessage(self, message, noTimestamp=False, isMotd=False):
        self.shown.append(message)


def _manager(player):
    client = mock.Mock()
    client._player = player
    client._config = {"chatOutputEnabled": True}
    manager = UiManager.__new__(UiManager)
    manager._client = client
    manager._UiManager__ui = Window()
    manager.lastNotificationOSDEndTime = None
    manager.lastAlertOSDEndTime = None
    return manager


class ChatBeforePlayerTests(unittest.TestCase):
    def test_chat_before_the_player_connects_still_reaches_the_window(self):
        manager = _manager(player=None)
        manager.showChatMessage("Tutti", "f")  # Used to raise AttributeError, which dropped the connection
        self.assertEqual(manager._UiManager__ui.shown, ["<Tutti> f"])

    def test_chat_goes_to_the_player_once_it_is_there(self):
        player = mock.Mock(chatOSDSupported=True)
        manager = _manager(player)
        manager.showChatMessage("Tutti", "f")
        player.displayChatMessage.assert_called_once_with("Tutti", "f")
        self.assertEqual(manager._UiManager__ui.shown, ["<Tutti> f"])


class ProtocolErrorTests(unittest.TestCase):
    def _protocol(self):
        protocol = SyncClientProtocol.__new__(SyncClientProtocol)
        protocol._client = mock.Mock()
        protocol.drop = mock.Mock()
        return protocol

    def test_an_error_in_one_message_is_logged_and_the_connection_stays(self):
        protocol = self._protocol()
        protocol.handleChat = mock.Mock(side_effect=AttributeError("boom"))
        protocol.handleSet = mock.Mock()
        with mock.patch("sys.stderr", new_callable=io.StringIO) as err:
            protocol.handleMessages({"Chat": {"username": "Tutti", "message": "f"}, "Set": {"ready": {}}})
        self.assertIn("AttributeError: boom", err.getvalue())
        protocol.handleSet.assert_called_once_with({"ready": {}})  # The rest of the line is still handled
        protocol.drop.assert_not_called()

    def test_a_line_whose_handler_fails_does_not_reach_twisted(self):
        protocol = self._protocol()
        protocol.showDebugMessage = mock.Mock()
        protocol.handleChat = mock.Mock(side_effect=KeyError("message"))
        with mock.patch("sys.stderr", new_callable=io.StringIO):
            protocol.lineReceived(b'{"Chat": {"username": "Tutti", "message": "f"}}')  # Must not raise
        protocol.drop.assert_not_called()

    def test_unknown_commands_still_drop_with_an_error(self):
        protocol = self._protocol()
        protocol.handleMessages({"Nonsense": {}})
        protocol._client.ui.showErrorMessage.assert_called_once()
        protocol.drop.assert_called_once()


if __name__ == "__main__":
    unittest.main()
