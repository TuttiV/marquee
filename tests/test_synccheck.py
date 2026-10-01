import unittest

from syncplay import synccheck


class TextTests(unittest.TestCase):
    def test_request_and_reply_round_trip(self):
        self.assertEqual(synccheck.parseRequest(synccheck.requestText("k3x9")), "k3x9")
        self.assertEqual(synccheck.parseReply(synccheck.replyText("k3x9", 1234.0, 0.3)), ("k3x9", 0.0, True))  # 0.3 s counts as in sync
        self.assertEqual(synccheck.parseReply(synccheck.replyText("k3x9", 1234.0, 2.14)), ("k3x9", 2.1, True))
        self.assertEqual(synccheck.parseReply(synccheck.replyText("k3x9", 1234.0, -4.0)), ("k3x9", -4.0, True))
        self.assertEqual(synccheck.parseReply(synccheck.replyText("k3x9")), ("k3x9", None, False))
        self.assertEqual(synccheck.parseReply(synccheck.replyText("k3x9", 61.0, None)), ("k3x9", 0.0, True))

    def test_ordinary_chat_is_never_mistaken_for_a_check(self):
        for text in (None, "", "hello", "[sync] hello #k3x9", "[sync check] #k3x9", "sync check #k3x9", "[sync] 12:00 (in sync) #TOOLONG",
                     "[sync] 12:00 (9999999s ahead) #k3x9", "x" * 500):
            self.assertIsNone(synccheck.parseRequest(text) if "check" in (text or "") else None)
            self.assertIsNone(synccheck.parseReply(text), text)

    def test_ids_are_short_and_varied(self):
        ids = {synccheck.newId() for _ in range(300)}
        self.assertGreater(len(ids), 250)
        self.assertTrue(all(len(i) == 4 and i.isalnum() for i in ids))

    def test_describe(self):
        self.assertEqual(synccheck.describe(None), "no video open")
        self.assertEqual(synccheck.describe(0.2), "in sync")
        self.assertEqual(synccheck.describe(3.04), "3.0 s ahead")
        self.assertEqual(synccheck.describe(-1.26), "1.3 s behind")


class FlowTests(unittest.TestCase):
    def make(self, me="Me", state=(100.0, 0.2), users=("Ann", "Bo", "Cy")):
        self.sent, self.said, self.scheduled = [], [], []
        self.now = [1000.0]
        self.state = state
        self.check = synccheck.SyncCheck(me, self.sent.append, lambda: self.state, lambda: list(users), self.said.append,
                                         lambda delay, fn, *a: self.scheduled.append((delay, fn, a)), clock=lambda: self.now[0])
        return self.check

    def run_later(self):
        for delay, fn, args in list(self.scheduled):
            fn(*args)
        self.scheduled.clear()

    def test_asking_posts_one_line_and_summarises_after_the_window(self):
        check = self.make()
        checkId = check.start()
        self.assertEqual(self.sent, [synccheck.requestText(checkId)])
        self.assertEqual(self.scheduled[0][0], synccheck.REPLY_WINDOW)
        self.assertTrue(check.handle("Ann", synccheck.replyText(checkId, 100.0, 2.4)))
        self.assertTrue(check.handle("Bo", synccheck.replyText(checkId, 100.0, -0.1)))
        self.run_later()
        self.assertEqual(len(self.said), 1)
        self.assertIn("Sync check: You: in sync; Ann: 2.4 s ahead; Bo: in sync.", self.said[0])
        self.assertIn("No answer from Cy", self.said[0])

    def test_someone_elses_request_is_answered_once_with_our_position(self):
        check = self.make(state=(754.0, -2.6))
        checkId = "abcd"
        self.assertTrue(check.handle("Ann", synccheck.requestText(checkId)))
        self.run_later()
        self.assertEqual(self.sent, [synccheck.replyText(checkId, 754.0, -2.6)])
        check.handle("Ann", synccheck.requestText(checkId))  # Same id again: no second answer
        self.run_later()
        self.assertEqual(len(self.sent), 1)

    def test_no_video_means_a_no_video_reply(self):
        check = self.make(state=(None, None))
        check.handle("Ann", synccheck.requestText("zzzz"))
        self.run_later()
        self.assertEqual(self.sent, ["[sync] no video #zzzz"])

    def test_our_own_request_is_not_answered_and_requests_are_rate_limited_per_person(self):
        check = self.make()
        check.handle("Me", synccheck.requestText("aaaa"))
        self.run_later()
        self.assertEqual(self.sent, [])
        check.handle("Ann", synccheck.requestText("bbbb"))
        self.run_later()
        self.now[0] += 2  # Too soon after her last one
        check.handle("Ann", synccheck.requestText("cccc"))
        self.run_later()
        self.assertEqual(len(self.sent), 1)
        self.now[0] += synccheck.MIN_REQUEST_GAP
        check.handle("Ann", synccheck.requestText("dddd"))
        self.run_later()
        self.assertEqual(len(self.sent), 2)

    def test_replies_are_staggered_and_unrelated_chat_is_left_alone(self):
        check = self.make()
        check.handle("Ann", synccheck.requestText("eeee"))
        delay = self.scheduled[0][0]
        self.assertTrue(0.0 <= delay <= 0.6)
        self.assertFalse(check.handle("Ann", "just chatting"))
        self.assertTrue(check.handle("Bo", synccheck.replyText("unknown1"[:4], 5.0, 0.0)))  # A reply to a check we didn't start is swallowed quietly


if __name__ == "__main__":
    unittest.main()
