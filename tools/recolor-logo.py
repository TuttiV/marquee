#!/usr/bin/env python3
"""Recolours the original Syncplay logo (kept unchanged in tools/original-logo/, Apache License 2.0) by rotating its hue,
and writes the icon files used by the app and the Windows launcher. Needs PySide6.

    python tools/recolor-logo.py            # default rotation
    python tools/recolor-logo.py --shift 150  # try another colour (degrees around the colour wheel)"""
import argparse
import os
import struct
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6 import QtCore, QtGui  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORIGINAL = os.path.join(ROOT, "tools", "original-logo")
DEFAULT_SHIFT = 205  # Orange -> blue, pink -> cyan


def recolor(image, shift):
    image = image.convertToFormat(QtGui.QImage.Format_ARGB32)
    for y in range(image.height()):
        for x in range(image.width()):
            color = image.pixelColor(x, y)
            if color.alpha() == 0:
                continue
            hue, saturation, lightness, alpha = color.getHslF()
            if hue < 0:  # Greys have no hue - leave them (the white ring and play button)
                continue
            color.setHslF((hue + shift / 360.0) % 1.0, saturation, lightness, alpha)
            image.setPixelColor(x, y, color)
    return image


def png_bytes(image):
    buffer = QtCore.QBuffer()
    buffer.open(QtCore.QIODevice.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(buffer.data())


def write_ico(path, source, sizes=(16, 24, 32, 48, 64, 128, 256)):
    blobs = []
    for size in sizes:
        scaled = source.scaled(size, size, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        blobs.append((size, png_bytes(scaled)))
    header = struct.pack("<HHH", 0, 1, len(blobs))
    offset = 6 + 16 * len(blobs)
    entries, data = b"", b""
    for size, blob in blobs:
        entries += struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(blob), offset)
        offset += len(blob)
        data += blob
    with open(path, "wb") as f:
        f.write(header + entries + data)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--shift", type=float, default=DEFAULT_SHIFT)
    args = parser.parse_args()
    app = QtGui.QGuiApplication.instance() or QtGui.QGuiApplication(sys.argv)  # noqa: F841
    resources = os.path.join(ROOT, "syncplay", "resources")
    for name in ("syncplay.png", "syncplayAbout.png", "syncplayAbout@2x.png"):
        recolor(QtGui.QImage(os.path.join(ORIGINAL, name)), args.shift).save(os.path.join(resources, name))
    big = recolor(QtGui.QImage(os.path.join(ORIGINAL, "syncplay.png")), args.shift)
    write_ico(os.path.join(resources, "icon.ico"), big)
    write_ico(os.path.join(ROOT, "bundle", "launcher", "icon.ico"), big)
    big.scaled(512, 512, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation).save(os.path.join(ROOT, "tools", "logo-preview.png"))
    print("Recoloured logo written (hue shift {} degrees)".format(args.shift))


if __name__ == "__main__":
    main()
