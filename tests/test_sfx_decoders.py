"""Checks the C decoders used by the self-extracting exe (inflate + LZMA) against Python's zlib/lzma, natively."""
import lzma
import os
import random
import shutil
import struct
import subprocess
import tempfile
import unittest
import zipfile
import zlib

SFX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bundle", "sfx")


@unittest.skipUnless(shutil.which("gcc"), "gcc not available")
class DecoderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        cls.exe = os.path.join(cls.dir, "test_decoders")
        subprocess.run(["gcc", "-O2", "-Wall", "-Wno-unused-function", "-o", cls.exe, os.path.join(SFX, "test_decoders.c")], check=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, ignore_errors=True)

    def run_decoder(self, mode, compressed, original):
        source = os.path.join(self.dir, "in.bin")
        result = os.path.join(self.dir, "out.bin")
        with open(source, "wb") as f:
            f.write(compressed)
        done = subprocess.run([self.exe, mode, source, str(len(original)), result], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stdout)
        with open(result, "rb") as f:
            self.assertEqual(f.read(), original)
        self.assertIn("crc={:08x}".format(zlib.crc32(original)), done.stdout)

    def samples(self):
        rnd = random.Random(7)
        yield b"a"
        yield b"hello hello hello hello " * 500
        yield bytes(range(256)) * 300
        yield os.urandom(50000)  # Incompressible: stored blocks / literals
        yield bytes(rnd.choice(b"ab") for _ in range(20000))
        yield open(__file__, "rb").read() * 40
        for name in ("syncplay/client.py", "syncplay/messages_en.py", "syncplay/vendor/Qt.py"):
            yield open(os.path.join(os.path.dirname(SFX), "..", name), "rb").read()
        python = shutil.which("python3")
        yield open(python, "rb").read()  # A real executable

    def test_inflate_matches_zlib_at_every_level(self):
        for data in self.samples():
            for level in (0, 1, 6, 9):
                c = zlib.compressobj(level, zlib.DEFLATED, -15)
                self.run_decoder("inflate", c.compress(data) + c.flush(), data)

    def test_lzma_zip_entries_match_pythons_zipfile(self):
        for data in self.samples():
            for name in ("a.bin",):
                path = os.path.join(self.dir, "t.zip")
                with zipfile.ZipFile(path, "w", zipfile.ZIP_LZMA) as z:
                    z.writestr(name, data)
                with zipfile.ZipFile(path) as z:
                    info = z.infolist()[0]
                raw = open(path, "rb").read()
                nameLen, extraLen = struct.unpack("<HH", raw[26:30])
                start = 30 + nameLen + extraLen
                self.run_decoder("zipentry", raw[start:start + info.compress_size], data)

    def test_damaged_input_fails_cleanly(self):
        data = b"some data " * 1000
        c = zlib.compressobj(9, zlib.DEFLATED, -15)
        good = c.compress(data) + c.flush()
        source = os.path.join(self.dir, "bad.bin")
        with open(source, "wb") as f:
            f.write(good[: len(good) // 2])  # Truncated
        done = subprocess.run([self.exe, "inflate", source, str(len(data)), os.path.join(self.dir, "o")], capture_output=True, text=True)
        self.assertNotEqual(done.returncode, 0)


if __name__ == "__main__":
    unittest.main()
