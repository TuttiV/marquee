import unittest

from syncplay.client import UiManager


class ForwardingTests(unittest.TestCase):
    def test_connection_loss_reaches_the_window_and_is_ignored_by_uis_without_it(self):
        calls = []

        class Window(object):
            def connectionLost(self):
                calls.append("lost")
        manager = UiManager.__new__(UiManager)
        manager._UiManager__ui = Window()
        manager.connectionLost()
        self.assertEqual(calls, ["lost"])
        manager._UiManager__ui = object()  # The console UI has no such method
        manager.connectionLost()


if __name__ == "__main__":
    unittest.main()
