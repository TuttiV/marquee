import os
import shutil
import tempfile
import unittest

from syncplay import resume


class ResumeTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.store = resume.ResumeStore(self.dir)
        self.file = {"name": "Show.S01E01.mkv", "size": 1000, "duration": 2940.0}

    def test_key_is_stable_and_distinguishes_files_and_streams(self):
        self.assertEqual(resume.key(self.file), resume.key(dict(self.file, name="SHOW.S01E01.MKV")))
        self.assertNotEqual(resume.key(self.file), resume.key(dict(self.file, size=1001)))
        self.assertNotEqual(resume.key(self.file), resume.key(dict(self.file, duration=2000.0)))
        a, b = {"name": "https://x.example/a.mp4"}, {"name": "https://x.example/b.mp4"}
        self.assertNotEqual(resume.key(a), resume.key(b))
        self.assertEqual(resume.key(dict(a, size=5, duration=9)), resume.key(a))  # Streams are keyed by address alone

    def test_remembers_position_and_survives_a_restart(self):
        self.assertIsNone(self.store.get(self.file))
        self.store.remember(self.file, 1930.5)
        self.assertEqual(self.store.get(self.file), 1930.5)
        self.assertEqual(resume.ResumeStore(self.dir).get(self.file), 1930.5)

    def test_barely_started_and_finished_videos_are_not_offered(self):
        self.store.remember(self.file, 30.0)
        self.assertIsNone(self.store.get(self.file))
        self.store.remember(self.file, 1500.0)
        self.assertEqual(self.store.get(self.file), 1500.0)
        self.store.remember(self.file, 2940.0 - 40)  # Nearly at the end: finished, forget it
        self.assertIsNone(self.store.get(self.file))
        self.store.remember(self.file, 1500.0)
        self.store.remember(self.file, None)
        self.assertIsNone(self.store.get(self.file))

    def test_tiny_moves_do_not_rewrite_the_file_and_the_store_is_capped(self):
        self.store.remember(self.file, 1000.0)
        path = os.path.join(self.dir, resume.FILE_NAME)
        first = os.path.getmtime(path)
        os.utime(path, (first - 100, first - 100))
        self.store.remember(self.file, 1002.0)
        self.assertLess(os.path.getmtime(path), first)  # Not rewritten
        for i in range(resume.MAX_ENTRIES + 25):
            self.store.remember({"name": "f{}.mkv".format(i), "size": i, "duration": 5000.0}, 500.0, now=i)
        self.assertLessEqual(len(self.store._load()), resume.MAX_ENTRIES)
        self.assertIsNone(self.store.get({"name": "f0.mkv", "size": 0, "duration": 5000.0}))  # Oldest dropped first
        self.assertEqual(self.store.get({"name": "f{}.mkv".format(resume.MAX_ENTRIES + 24), "size": resume.MAX_ENTRIES + 24, "duration": 5000.0}), 500.0)

    def test_a_damaged_file_is_just_empty(self):
        with open(os.path.join(self.dir, resume.FILE_NAME), "w") as f:
            f.write("{not json")
        self.assertIsNone(resume.ResumeStore(self.dir).get(self.file))
        with open(os.path.join(self.dir, resume.FILE_NAME), "w") as f:
            f.write('{"%s": {"position": "soon"}}' % resume.key(self.file))
        self.assertIsNone(resume.ResumeStore(self.dir).get(self.file))


if __name__ == "__main__":
    unittest.main()
