import hashlib
import io
import json
import os
import shutil
import tempfile
import unittest
import urllib.error
import zipfile

from syncplay import secrets, updater


def makeZip(files, top="Syncplay-Marquee"):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr("{}/{}".format(top, name) if top else name, data)
    return buffer.getvalue()


GOOD = {
    "syncplay/__init__.py": "version = 'new'\n",
    "syncplay/private_build.py": "BUILD = 2\n",
    "program/launch-syncplay.pyw": "# new launcher\n",
    "syncplayClient.py": "# new client\n",
    "requirements.txt": "twisted\n",
    "START-HERE.txt": "new docs\n",
}


class FakeResponse(io.BytesIO):
    def __init__(self, data, url="https://api.github.com/x"):
        super().__init__(data)
        self._url = url

    def geturl(self):
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def releaseJson(tag="v2", assetUrl="https://github.com/o/r/releases/download/v2/Syncplay-Marquee-v2.zip", sha="a" * 64, body=None,
                assets=True, digest=None):
    asset = {"name": "Syncplay-Marquee-v2.zip", "browser_download_url": assetUrl, "size": 1234}
    if digest:
        asset["digest"] = digest
    return json.dumps({
        "tag_name": tag, "name": "Build 2", "body": body if body is not None else "Shiny things\n\nsha256: {}".format(sha),
        "assets": [asset] if assets else [],
    }).encode()


class ParsingTests(unittest.TestCase):
    def test_build_is_the_trailing_number_of_the_tag(self):
        for tag, expected in (("v7", 7), ("build-12", 12), ("release 3", 3), ("v1.2", 2), ("nightly", None), ("", None)):
            self.assertEqual(updater.parseBuild(tag), expected, tag)

    def test_repo_comes_from_the_defaults_file_and_must_look_like_owner_slash_name(self):
        directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, directory, True)
        self.assertIsNone(updater.configuredRepo(directory))
        for value, expected in (("me/my-repo", "me/my-repo"), ("Some-Org/repo.name_1", "Some-Org/repo.name_1"), ("../evil", None), ("me/..", None), ("me/.", None), ("-me/x", None), ("a b/c", None), ("noslash", None), ("", None)):
            with open(os.path.join(directory, secrets.DEFAULTS_FILE_NAME), "w") as f:
                json.dump({"updateRepo": value}, f)
            self.assertEqual(updater.configuredRepo(directory), expected, value)


class ReleaseTests(unittest.TestCase):
    def test_latest_release_reads_tag_notes_asset_and_checksum(self):
        info = updater.latestRelease("o/r", urlopen=lambda request, timeout=None: FakeResponse(releaseJson()))
        self.assertEqual((info.build, info.name, info.size, info.sha256), (2, "Build 2", 1234, "a" * 64))
        self.assertTrue(updater.isNewer(info, currentBuild=1))
        self.assertFalse(updater.isNewer(info, currentBuild=2))

    def test_github_asset_digest_is_the_checksum_so_no_description_line_is_needed(self):
        payload = releaseJson(body="Just release notes", digest="sha256:" + "B" * 64)
        info = updater.latestRelease("o/r", urlopen=lambda request, timeout=None: FakeResponse(payload))
        self.assertEqual(info.sha256, "b" * 64)

    def test_asset_digest_wins_over_the_description_and_junk_digests_are_ignored(self):
        payload = releaseJson(sha="a" * 64, digest="sha256:" + "c" * 64)
        self.assertEqual(updater.latestRelease("o/r", urlopen=lambda request, timeout=None: FakeResponse(payload)).sha256, "c" * 64)
        for junk in ("md5:abcd", "sha256:short", "sha1:" + "d" * 40):
            payload = releaseJson(body="No checksum here", digest=junk)
            self.assertIsNone(updater.latestRelease("o/r", urlopen=lambda request, timeout=None, p=payload: FakeResponse(p)).sha256, junk)

    def test_highest_build_wins_whatever_order_github_lists_them_in(self):
        old, new = json.loads(releaseJson(tag="v4")), json.loads(releaseJson(tag="v6"))
        draft, pre = json.loads(releaseJson(tag="v9")), json.loads(releaseJson(tag="v8"))
        draft["draft"], pre["prerelease"] = True, True
        junk = json.loads(releaseJson(tag="nightly"))
        for listing in ([old, new, draft, pre, junk], [junk, draft, new, old, pre]):
            payload = json.dumps(listing).encode()
            info = updater.latestRelease("o/r", urlopen=lambda request, timeout=None, p=payload: FakeResponse(p))
            self.assertEqual((info.tag, info.build), ("v6", 6))

    def test_only_drafts_or_unnumbered_tags_is_a_friendly_error(self):
        for listing in ([], [dict(json.loads(releaseJson()), draft=True)], [json.loads(releaseJson(tag="nightly"))]):
            payload = json.dumps(listing).encode()
            with self.assertRaises(updater.UpdateError):
                updater.latestRelease("o/r", urlopen=lambda request, timeout=None, p=payload: FakeResponse(p))

    def test_bad_releases_are_refused_with_friendly_errors(self):
        cases = [releaseJson(tag="nightly"), releaseJson(assets=False), releaseJson(assetUrl="https://evil.example/x.zip"),
                 releaseJson(assetUrl="http://github.com/x.zip")]
        for payload in cases:
            with self.assertRaises(updater.UpdateError):
                updater.latestRelease("o/r", urlopen=lambda request, timeout=None, p=payload: FakeResponse(p))

    def test_http_errors_and_redirects_to_other_hosts(self):
        def notFound(request, timeout=None):
            raise urllib.error.HTTPError("u", 404, "nf", {}, io.BytesIO(b""))
        with self.assertRaises(updater.UpdateError) as ctx:
            updater.latestRelease("o/r", urlopen=notFound)
        self.assertIn("no release", str(ctx.exception))
        with self.assertRaises(updater.UpdateError):
            updater.latestRelease("o/r", urlopen=lambda request, timeout=None: FakeResponse(releaseJson(), url="https://evil.example/"))


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.zip = makeZip(GOOD)
        self.release = updater.ReleaseInfo("v2", 2, "Build 2", "", "https://github.com/o/r/releases/download/v2/a.zip",
                                           len(self.zip), hashlib.sha256(self.zip).hexdigest())

    def fetch(self, data=None, release=None, progress=None):
        path = os.path.join(self.dir, "u.zip")
        updater.download(release or self.release, path, progress,
                         urlopen=lambda request, timeout=None: FakeResponse(data if data is not None else self.zip, "https://github.com/o/r/a.zip"))
        return path

    def test_verified_download_is_saved_and_reports_progress(self):
        seen = []
        path = self.fetch(progress=lambda done, total: seen.append((done, total)))
        self.assertEqual(open(path, "rb").read(), self.zip)
        self.assertEqual(seen[-1][0], len(self.zip))

    def test_wrong_checksum_is_discarded_and_missing_checksum_is_refused(self):
        with self.assertRaises(updater.UpdateError):
            self.fetch(data=self.zip + b"tampered")
        self.assertFalse(os.path.exists(os.path.join(self.dir, "u.zip")))
        self.release.sha256 = None
        with self.assertRaises(updater.UpdateError) as ctx:
            self.fetch()
        self.assertIn("checksum", str(ctx.exception))


class StageAndApplyTests(unittest.TestCase):
    def setUp(self):
        self.app = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.app, True)
        for name, text in {"syncplay/__init__.py": "version = 'old'\n", "syncplay/private_build.py": "BUILD = 1\n",
                           "syncplayClient.py": "# old client\n", "requirements.txt": "twisted\n",
                           "syncplay-defaults.json": '{"openSubtitlesApiKey": "MINE"}', "syncplay.log": "keep me",
                           ".venv/marker.txt": "env"}.items():
            path = os.path.join(self.app, *name.split("/"))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, "w").write(text)
        self.zipPath = os.path.join(self.app, "release.zip")

    def write(self, files, top="Syncplay-Marquee"):
        open(self.zipPath, "wb").write(makeZip(files, top))

    def read(self, name):
        return open(os.path.join(self.app, *name.split("/"))).read()

    def test_stage_then_apply_replaces_app_files_and_keeps_user_data(self):
        self.write(GOOD)
        self.assertGreater(updater.stage(self.zipPath, self.app), 4)
        self.assertTrue(updater.hasStagedUpdate(self.app))
        self.assertEqual(self.read("syncplayClient.py"), "# old client\n")  # Nothing changes until applied
        pipCalls = []
        updater.applyStaged(self.app, pip=lambda appDir, log: pipCalls.append(appDir))
        self.assertEqual(self.read("syncplayClient.py"), "# new client\n")
        self.assertEqual(self.read("syncplay/private_build.py"), "BUILD = 2\n")
        self.assertEqual(self.read("program/launch-syncplay.pyw"), "# new launcher\n")
        self.assertEqual(self.read("syncplay-defaults.json"), '{"openSubtitlesApiKey": "MINE"}')
        self.assertEqual(self.read("syncplay.log"), "keep me")
        self.assertTrue(os.path.exists(os.path.join(self.app, ".venv", "marker.txt")))
        self.assertFalse(os.path.exists(os.path.join(self.app, updater.STAGING)))
        self.assertEqual(pipCalls, [])  # requirements.txt unchanged

    def test_applying_an_update_moves_the_exe_build_marker_forward_but_never_back(self):
        marker = os.path.join(self.app, ".marquee-build")
        open(marker, "w").write("1")
        self.write(GOOD)  # BUILD = 2
        updater.stage(self.zipPath, self.app)
        updater.applyStaged(self.app, pip=lambda *a: None)
        self.assertEqual(open(marker).read(), "2")
        updater.confirmHealthy(self.app)  # Build 2 proved itself
        older = dict(GOOD, **{"syncplay/private_build.py": "BUILD = 1\n"})
        self.write(older)
        updater.stage(self.zipPath, self.app)
        updater.applyStaged(self.app, pip=lambda *a: None)
        self.assertEqual(open(marker).read(), "2")

    def test_no_marker_file_is_created_outside_the_single_file_edition(self):
        self.write(GOOD)
        updater.stage(self.zipPath, self.app)
        updater.applyStaged(self.app, pip=lambda *a: None)
        self.assertFalse(os.path.exists(os.path.join(self.app, ".marquee-build")))

    def test_pip_runs_only_when_requirements_changed(self):
        self.write(dict(GOOD, **{"requirements.txt": "twisted\nnew-lib\n"}))
        updater.stage(self.zipPath, self.app)
        calls = []
        updater.applyStaged(self.app, pip=lambda appDir, log: calls.append(1))
        self.assertEqual(calls, [1])

    def test_protected_unsafe_and_unknown_entries_are_never_installed(self):
        evil = dict(GOOD, **{
            "syncplay-defaults.json": '{"openSubtitlesApiKey": "STOLEN"}', ".venv/evil.py": "x", "Syncplay Marquee.exe": "binary",
            "../escape.txt": "x", "syncplay/../../escape2.txt": "x", "random/other.txt": "x", "program/../../escape3.txt": "x",
            "malware.exe": "x", "C:/windows/x.py": "x",
        })
        self.write(evil)
        updater.stage(self.zipPath, self.app)
        updater.applyStaged(self.app, pip=lambda *a: None)
        self.assertEqual(self.read("syncplay-defaults.json"), '{"openSubtitlesApiKey": "MINE"}')
        parent = os.path.dirname(self.app)
        for leaked in ("escape.txt", "escape2.txt", "escape3.txt"):
            self.assertFalse(os.path.exists(os.path.join(parent, leaked)), leaked)
        for name in ("malware.exe", "Syncplay Marquee.exe", "random", os.path.join(".venv", "evil.py")):
            self.assertFalse(os.path.exists(os.path.join(self.app, name)), name)

    def test_zip_without_a_top_folder_works_and_junk_zips_are_rejected(self):
        self.write(GOOD, top="")
        self.assertGreater(updater.stage(self.zipPath, self.app), 0)
        shutil.rmtree(os.path.join(self.app, updater.STAGING))
        self.write({"readme.txt": "not a syncplay bundle"})
        with self.assertRaises(updater.UpdateError):
            updater.stage(self.zipPath, self.app)
        open(self.zipPath, "wb").write(b"not a zip at all")
        with self.assertRaises(updater.UpdateError):
            updater.stage(self.zipPath, self.app)
        self.assertFalse(updater.hasStagedUpdate(self.app))

    def test_nothing_staged_means_nothing_applied(self):
        self.assertEqual(updater.applyStaged(self.app), 0)
        self.assertEqual(self.read("syncplayClient.py"), "# old client\n")


if __name__ == "__main__":
    unittest.main()


class RestartTests(unittest.TestCase):
    def test_start_dialog_is_skipped_once_after_a_restart(self):
        env = {updater.RESTARTED_ENV: "1"}
        self.assertTrue(updater.restartedWithoutPrompt(env))
        self.assertFalse(updater.restartedWithoutPrompt(env))  # Consumed: a later manual start shows the dialog again
        self.assertFalse(updater.restartedWithoutPrompt({}))

    def test_update_result_says_updated_failed_or_nothing(self):
        app = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, app, True)
        self.assertIsNone(updater.consumeUpdateResult(app, {}, currentBuild=8))
        self.assertIsNone(updater.consumeUpdateResult(app, {updater.UPDATED_FROM_ENV: "junk"}, currentBuild=8))
        env = {updater.UPDATED_FROM_ENV: "7"}
        self.assertEqual(updater.consumeUpdateResult(app, env, currentBuild=8), ("updated", 7, 8))
        self.assertNotIn(updater.UPDATED_FROM_ENV, env)
        self.assertIsNone(updater.consumeUpdateResult(app, {updater.UPDATED_FROM_ENV: "8"}, currentBuild=8))  # Nothing waiting
        os.makedirs(os.path.join(app, updater.STAGING))
        open(os.path.join(app, updater.STAGING, updater.READY_MARKER), "w").write("ok")
        self.assertEqual(updater.consumeUpdateResult(app, {updater.UPDATED_FROM_ENV: "8"}, currentBuild=8), ("failed", 8, 8))

    def test_relaunch_waits_for_the_old_process_to_exit_then_starts_the_new_one(self):
        import subprocess
        import sys
        import time
        app = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, app, True)
        out = os.path.join(app, "started.txt")
        script = os.path.join(app, "fake_launcher.py")
        with open(script, "w") as f:
            f.write("import os, sys, time\nopen(sys.argv[1], 'w').write('{}|{}|{}|{}'.format(os.environ.get('MARQUEE_RESTARTED'), "
                    "os.environ.get('MARQUEE_UPDATED_FROM'), os.getcwd() == os.path.realpath(sys.argv[2]), sys.argv[3]))\n")
        import threading
        old = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(1.5)"])
        threading.Thread(target=old.wait, daemon=True).start()  # Reap it when it exits, like the real parent would
        started = time.time()
        updater.relaunch(old.pid, sys.executable, [script, out, app, "extra"], app, fromBuild=7)
        time.sleep(0.6)
        self.assertFalse(os.path.exists(out), "started while the old copy was still running")
        deadline = time.time() + 15
        while not os.path.exists(out) and time.time() < deadline:
            time.sleep(0.1)
        time.sleep(0.3)
        self.assertGreaterEqual(time.time() - started, 1.5)
        self.assertEqual(open(out).read(), "1|7|True|extra")

    def test_relaunch_can_ask_for_the_start_window_by_not_marking_the_restart(self):
        import subprocess
        import sys
        import time
        app = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, app, True)
        out = os.path.join(app, "started.txt")
        script = os.path.join(app, "fake_launcher.py")
        with open(script, "w") as f:
            f.write("import os, sys\nopen(sys.argv[1], 'w').write(str(os.environ.get('MARQUEE_RESTARTED')))\n")
        old = subprocess.Popen([sys.executable, "-c", "pass"])
        old.wait()
        updater.relaunch(10 ** 9, sys.executable, [script, out], app, skipStartWindow=False)
        deadline = time.time() + 15
        while not os.path.exists(out) and time.time() < deadline:
            time.sleep(0.1)
        time.sleep(0.3)
        self.assertEqual(open(out).read(), "None")


class RollbackTests(unittest.TestCase):
    def setUp(self):
        self.app = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.app, True)
        for name, text in {"syncplay/__init__.py": "version = 'old'\n", "syncplay/private_build.py": "BUILD = 1\n",
                           "syncplayClient.py": "# old client\n", ".marquee-build": "1"}.items():
            self.put(name, text)
        self.zipPath = os.path.join(self.app, "release.zip")

    def put(self, name, text):
        path = os.path.join(self.app, *name.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(text)

    def read(self, name):
        with open(os.path.join(self.app, *name.split("/"))) as f:
            return f.read()

    def exists(self, name):
        return os.path.exists(os.path.join(self.app, *name.split("/")))

    def install(self, extra=None):
        files = dict(GOOD, **(extra or {}))
        with open(self.zipPath, "wb") as f:
            f.write(makeZip(files))
        updater.stage(self.zipPath, self.app)
        updater.applyStaged(self.app, pip=lambda *a: None)

    def test_apply_leaves_a_backup_and_a_pending_record(self):
        self.install()
        self.assertEqual(self.read("syncplayClient.py"), "# new client\n")
        pending = updater.pendingUpdate(self.app)
        self.assertEqual((pending["state"], pending["from"], pending["to"]), ("applied", 1, 2))
        self.assertIn("syncplayClient.py", pending["replaced"])
        self.assertIn("program/launch-syncplay.pyw", pending["created"])
        self.assertEqual(self.read("update-backup/syncplayClient.py"), "# old client\n")

    def test_roll_back_restores_old_files_removes_new_ones_and_blocks_the_bad_build(self):
        self.install()
        self.assertTrue(updater.rollBack(self.app, "test", block=True))
        self.assertEqual(self.read("syncplayClient.py"), "# old client\n")
        self.assertEqual(self.read("syncplay/private_build.py"), "BUILD = 1\n")
        self.assertFalse(self.exists("program/launch-syncplay.pyw"))
        self.assertEqual(self.read(".marquee-build"), "1")
        self.assertFalse(self.exists("update-backup"))
        self.assertIsNone(updater.pendingUpdate(self.app))
        self.assertEqual(updater.blockedBuild(self.app), 2)
        release = updater.ReleaseInfo("v2", 2, "Build 2", "", "https://github.com/o/r/a.zip", 1, "a" * 64)
        self.assertFalse(updater.isNewer(release, currentBuild=1, appDir=self.app))
        newer = updater.ReleaseInfo("v3", 3, "Build 3", "", "https://github.com/o/r/a.zip", 1, "a" * 64)
        self.assertTrue(updater.isNewer(newer, currentBuild=1, appDir=self.app))
        self.assertEqual(updater.history(self.app)[-1]["event"], "rolled-back")
        self.assertFalse(updater.rollBack(self.app, "again"))  # Nothing pending any more

    def test_confirming_keeps_the_update_and_drops_the_backup(self):
        self.install()
        self.assertTrue(updater.confirmHealthy(self.app))
        self.assertEqual(self.read("syncplayClient.py"), "# new client\n")
        self.assertFalse(self.exists("update-backup"))
        self.assertIsNone(updater.pendingUpdate(self.app))
        self.assertEqual([h["event"] for h in updater.history(self.app)], ["updated"])
        self.assertFalse(updater.confirmHealthy(self.app))

    def test_recovery_only_undoes_starts_that_never_confirmed_and_ran_long_enough(self):
        self.assertFalse(updater.recoverFromFailedUpdate(self.app))
        self.install()
        self.assertFalse(updater.recoverFromFailedUpdate(self.app))  # Never started yet
        updater.markStarted(self.app)
        self.assertFalse(updater.recoverFromFailedUpdate(self.app))  # Just started: may still be coming up (or a second window)
        pending = updater.pendingUpdate(self.app)
        pending["started"] -= updater.SETTLE_SECONDS + 5
        with open(os.path.join(self.app, updater.PENDING), "w") as f:
            json.dump(pending, f)
        self.assertTrue(updater.recoverFromFailedUpdate(self.app))
        self.assertEqual(self.read("syncplayClient.py"), "# old client\n")
        self.assertEqual(updater.blockedBuild(self.app), 2)

    def test_an_interrupted_apply_is_undone(self):
        self.install()
        pending = updater.pendingUpdate(self.app)
        pending["state"] = "applying"
        with open(os.path.join(self.app, updater.PENDING), "w") as f:
            json.dump(pending, f)
        self.assertTrue(updater.recoverFromFailedUpdate(self.app))
        self.assertEqual(self.read("syncplayClient.py"), "# old client\n")
        self.assertEqual(updater.blockedBuild(self.app), 0)  # Interrupted is not the release's fault

    def test_a_second_update_never_stacks_on_an_unconfirmed_one(self):
        self.install()
        with open(self.zipPath, "wb") as f:
            f.write(makeZip(dict(GOOD, **{"syncplay/private_build.py": "BUILD = 3\n"})))
        updater.stage(self.zipPath, self.app)
        updater.applyStaged(self.app, pip=lambda *a: None)
        pending = updater.pendingUpdate(self.app)
        self.assertEqual((pending["from"], pending["to"]), (1, 3))  # Backup is of the original, not of build 2
        updater.rollBack(self.app, "test")
        self.assertEqual(self.read("syncplay/private_build.py"), "BUILD = 1\n")

    def test_updates_cannot_touch_the_recovery_files(self):
        for name in (updater.PENDING, updater.HISTORY, updater.BLOCKED, ".marquee-build", updater.BACKUP + "/x.py"):
            self.assertFalse(updater._wanted(name), name)

    def test_a_release_with_a_syntax_error_is_refused_and_nothing_changes(self):
        with open(self.zipPath, "wb") as f:
            f.write(makeZip(dict(GOOD, **{"syncplay/oops.py": "def broken(:\n"})))
        with self.assertRaises(updater.UpdateError) as ctx:
            updater.stage(self.zipPath, self.app)
        self.assertIn("oops.py", str(ctx.exception))
        self.assertFalse(updater.hasStagedUpdate(self.app))
        self.assertEqual(self.read("syncplayClient.py"), "# old client\n")

    def test_unseen_history_is_reported_once(self):
        self.install()
        updater.rollBack(self.app, "boom")
        self.assertEqual(len(updater.unseenHistory(self.app)), 1)
        self.assertEqual(updater.unseenHistory(self.app), [])


class StagedBuildTests(unittest.TestCase):
    def test_the_staged_build_number_is_read_from_the_staged_files(self):
        app = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, app, True)
        self.assertEqual(updater.stagedBuild(app), 0)
        staging = os.path.join(app, updater.STAGING, "syncplay")
        os.makedirs(staging)
        with open(os.path.join(staging, "private_build.py"), "w") as f:
            f.write("# comment\nBUILD = 31\n")
        self.assertEqual(updater.stagedBuild(app), 0)  # Not complete until it is marked ready
        with open(os.path.join(app, updater.STAGING, updater.READY_MARKER), "w") as f:
            f.write("ok")
        self.assertEqual(updater.stagedBuild(app), 31)
