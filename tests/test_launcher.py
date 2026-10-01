import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAUNCHER = os.path.join(ROOT, "bundle", "program", "launch-syncplay.pyw")


class LauncherTests(unittest.TestCase):
    """Runs the real program/launch-syncplay.pyw against a throw-away app folder with a staged update waiting."""

    def setUp(self):
        self.app = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.app, True)
        for relative in ("syncplay/__init__.py", "syncplay/secrets.py", "syncplay/updater.py"):
            self.put(relative, open(os.path.join(ROOT, *relative.split("/")), encoding="utf-8").read())
        self.put("program/launch-syncplay.pyw", open(LAUNCHER, encoding="utf-8").read())
        self.put("syncplay/private_build.py", "BUILD = 1\n")
        self.put("syncplayClient.py", "from syncplay.private_build import BUILD\nprint('CLIENT BUILD', BUILD)\n")

    def put(self, relative, text, root=None):
        path = os.path.join(root or self.app, *relative.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    def stage(self, files):
        staging = os.path.join(self.app, "update-staging")
        for relative, text in files.items():
            self.put(relative, text, staging)
        self.put("READY", "ok", staging)

    def launch(self):
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        process = subprocess.run([sys.executable, os.path.join(self.app, "program", "launch-syncplay.pyw")], cwd=self.app,
                                 env=env, capture_output=True, text=True, timeout=60)
        log = os.path.join(self.app, "syncplay.log")
        return process, open(log, encoding="utf-8").read() if os.path.exists(log) else ""

    def test_staged_update_is_applied_before_the_app_loads_and_new_modules_are_importable(self):
        self.stage({
            "syncplay/private_build.py": "BUILD = 2\n",
            "syncplay/brand_new_module.py": "VALUE = 'fresh'\n",
            "syncplayClient.py": "from syncplay.private_build import BUILD\nfrom syncplay import brand_new_module\n"
                                 "print('CLIENT BUILD', BUILD, brand_new_module.VALUE)\n",
        })
        process, log = self.launch()
        self.assertIn("CLIENT BUILD 2 fresh", log, log)
        self.assertIn("Applied downloaded update", log)
        self.assertFalse(os.path.exists(os.path.join(self.app, "update-staging")))

    def test_without_an_update_it_just_starts_the_current_build(self):
        process, log = self.launch()
        self.assertIn("CLIENT BUILD 1", log, log)
        self.assertNotIn("Applying", log)

    def test_a_locked_file_is_retried_and_the_update_still_lands(self):
        # Simulate a virus scanner holding the file for a moment: the first apply attempt fails, a later one succeeds
        self.stage({"syncplay/private_build.py": "BUILD = 3\n", "syncplayClient.py": "from syncplay.private_build import BUILD\nprint('CLIENT BUILD', BUILD)\n"})
        text = open(LAUNCHER, encoding="utf-8").read().replace(
            "from syncplay import updater\n",
            "from syncplay import updater\n    _real = updater.applyStaged\n    _calls = []\n"
            "    def _flaky(*a, **k):\n        _calls.append(1)\n        if len(_calls) < 3:\n            raise PermissionError('locked')\n"
            "        return _real(*a, **k)\n    updater.applyStaged = _flaky\n", 1)
        self.put("program/launch-syncplay.pyw", text)
        process, log = self.launch()
        self.assertIn("Could not apply the update yet: locked", log, log)
        self.assertIn("CLIENT BUILD 3", log, log)

    def test_an_update_that_crashes_on_start_is_undone_and_the_old_version_starts_instead(self):
        self.stage({"syncplay/private_build.py": "BUILD = 2\n", "syncplayClient.py": "raise RuntimeError('new version is broken')\n"})
        process, log = self.launch()
        deadline = time.time() + 20
        while "CLIENT BUILD 1" not in log and time.time() < deadline:  # The previous version is started as a fresh process
            time.sleep(0.2)
            log = open(os.path.join(self.app, "syncplay.log"), encoding="utf-8").read()
        self.assertIn("new version is broken", log)
        self.assertIn("Rolled back the update", log)
        self.assertIn("CLIENT BUILD 1", log)
        with open(os.path.join(self.app, "syncplay", "private_build.py")) as f:
            self.assertIn("BUILD = 1", f.read())
        self.assertFalse(os.path.exists(os.path.join(self.app, "update-pending.json")))

    def test_an_update_that_starts_but_never_confirms_is_undone_on_the_next_start(self):
        self.stage({"syncplay/private_build.py": "BUILD = 2\n"})
        process, log = self.launch()
        self.assertIn("CLIENT BUILD 2", log)
        pendingPath = os.path.join(self.app, "update-pending.json")
        with open(pendingPath) as f:
            pending = json.load(f)
        self.assertIsNotNone(pending["started"])
        pending["started"] -= 600  # The user closed it long ago without it ever showing a working window
        with open(pendingPath, "w") as f:
            json.dump(pending, f)
        process, log = self.launch()
        self.assertIn("previous version was restored", log)
        self.assertTrue(log.rstrip().endswith("CLIENT BUILD 1"), log)

    def test_a_confirmed_update_stays(self):
        self.stage({"syncplay/private_build.py": "BUILD = 2\n"})
        self.launch()
        subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, sys.argv[1]); from syncplay import updater; updater.confirmHealthy(sys.argv[1])", self.app], check=True)
        process, log = self.launch()
        self.assertTrue(log.rstrip().endswith("CLIENT BUILD 2"), log)


if __name__ == "__main__":
    unittest.main()
