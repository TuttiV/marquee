import os
import shutil
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from syncplay.ui import theme

try:
    from syncplay.vendor.Qt import QtWidgets
    HAVE_QT = True
except Exception:
    HAVE_QT = False


def luminance(color):
    color = color.lstrip("#")
    channels = [int(color[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    channels = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


class TokenTests(unittest.TestCase):
    def test_every_theme_has_every_colour(self):
        for name, (tokens, dark) in theme.THEMES.items():
            self.assertEqual(set(tokens), set(theme.DARK), name)

    def test_text_is_readable_in_every_theme(self):
        for name, (t, dark) in theme.THEMES.items():
            for surface in ("bg", "panel", "surface2"):
                self.assertGreaterEqual(contrast(t["text"], t[surface]), 7.0, (name, surface))
            self.assertGreaterEqual(contrast(t["muted"], t["panel"]), 4.5, name)
            self.assertGreaterEqual(contrast(t["muted"], t["bg"]), 4.5, name)
            self.assertGreaterEqual(contrast(t["accentText"], t["accent"]), 4.5, name)
            self.assertGreaterEqual(contrast(t["readyText"], t["ready"]), 4.5, name)
            self.assertGreaterEqual(contrast(t["link"], t["panel"]), 4.5, name)
            self.assertEqual(luminance(t["bg"]) < 0.18, dark, name)  # Declared darkness matches the background

    def test_the_choice_is_remembered_and_unknown_names_mean_system(self):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder, True)
        self.addCleanup(theme.chooseTheme, "system", False)
        theme.setConfigDir(folder)
        theme.chooseTheme("cinema")
        theme._chosen = "system"
        theme.setConfigDir(folder)
        self.assertEqual(theme.chosenTheme(), "cinema")
        self.assertEqual(theme.chooseTheme("nonsense"), "system")
        self.assertEqual(theme.tokens(True), theme.DARK)

    def test_tokens_follow_the_chosen_theme_only_when_it_agrees_with_the_window(self):
        self.addCleanup(theme.chooseTheme, "system", False)
        theme.chooseTheme("sand", False)
        self.assertEqual(theme.tokens(False), theme.SAND)
        self.assertEqual(theme.tokens(True), theme.DARK)


@unittest.skipUnless(HAVE_QT, "Qt not available")
class ApplyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def tearDown(self):
        theme.chooseTheme("system", False)
        theme.applyApplicationTheme(self.app)

    def test_each_theme_sets_a_matching_palette_and_system_restores_the_original(self):
        theme.chooseTheme("system", False)
        theme.applyApplicationTheme(self.app)
        original = self.app.palette().window().color().name()
        for name, (tokens, dark) in theme.THEMES.items():
            theme.chooseTheme(name, False)
            self.assertEqual(theme.applyApplicationTheme(self.app), dark, name)
            self.assertEqual(self.app.palette().window().color().name(), tokens["bg"], name)
            self.assertIn(tokens["accent"], self.app.styleSheet(), name)
        theme.chooseTheme("system", False)
        theme.applyApplicationTheme(self.app)
        self.assertEqual(self.app.palette().window().color().name(), original)
