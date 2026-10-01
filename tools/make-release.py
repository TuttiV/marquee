#!/usr/bin/env python3
"""Builds the release zip that the in-app Update button installs.

    python tools/make-release.py --build 7

1. Sets BUILD = 7 in syncplay/private_build.py (the tag you publish must end in the same number, e.g. v7).
2. Zips the tracked source + the bundle/ launchers into dist/Syncplay-Marquee-v7.zip.
3. Prints the release steps. GitHub records a SHA-256 for every uploaded file and the updater checks the download against
   it; the printed sha256 line is only a fallback for releases GitHub didn't checksum.

Never includes syncplay-defaults.json or syncplay-secrets.json (your API keys), and refuses to build if any key from your
local syncplay-defaults.json appears anywhere in the zip."""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOLDER = "Syncplay-Marquee"
NEVER = {"syncplay-defaults.json", "syncplay-secrets.json", "syncplay.log"}


def trackedFiles():
    out = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=ROOT, check=True, capture_output=True, text=True).stdout.split("\n")
    keep = []
    for path in filter(None, out):
        top = path.split("/")[0]
        if top == "syncplay" or (("/" not in path) and re.match(
                r"^(?:[^/]+\.(?:py|txt|md|in)|LICENSE|Makefile|GNUmakefile)$", path)):
            keep.append(path)
    return keep


def bundleFiles():
    base = os.path.join(ROOT, "bundle")
    for root, _, files in os.walk(os.path.join(base, "program")):  # Only program/ is installed by the updater
        for name in files:
            full = os.path.join(root, name)
            relative = os.path.relpath(full, base).replace(os.sep, "/")
            if name.endswith(".example.json") or name in NEVER:
                continue
            yield full, relative


def localSecrets():
    try:
        with open(os.path.join(ROOT, "syncplay-defaults.json"), encoding="utf-8") as f:
            return [v for v in json.load(f).values() if isinstance(v, str) and len(v) >= 12]
    except (OSError, ValueError):
        return []


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--build", type=int, required=True, help="Build number; the release tag must end with it")
    parser.add_argument("--out", default=os.path.join(ROOT, "dist"))
    args = parser.parse_args()

    with open(os.path.join(ROOT, "syncplay", "private_build.py"), "w", encoding="utf-8") as f:
        f.write("# Build number of this private Syncplay bundle. The release script (tools/make-release.py) bumps it for each\n"
                "# release; \"Update\" installs a GitHub release whose tag ends in a larger number (for example v7 or build-7).\n"
                "BUILD = {}\n".format(args.build))
    os.makedirs(args.out, exist_ok=True)
    zipPath = os.path.join(args.out, "{}-v{}.zip".format(FOLDER, args.build))
    entries = {}
    for path in trackedFiles():
        entries[path] = os.path.join(ROOT, path)
    for full, relative in bundleFiles():
        entries[relative] = full  # Bundle files (launchers, START-HERE, Syncplay.exe) sit at the top of the zip
    with zipfile.ZipFile(zipPath, "w", zipfile.ZIP_DEFLATED) as z:
        for relative, full in sorted(entries.items()):
            if os.path.basename(relative).lower() in NEVER or not os.path.isfile(full):
                continue
            info = zipfile.ZipInfo.from_file(full, "{}/{}".format(FOLDER, relative))
            if relative.endswith(".sh"):
                info.external_attr = 0o755 << 16
            with open(full, "rb") as fh:
                z.writestr(info, fh.read(), zipfile.ZIP_DEFLATED)
    secrets = localSecrets()
    with zipfile.ZipFile(zipPath) as z:
        for name in z.namelist():
            data = z.read(name)
            for secret in secrets:
                if secret.encode() in data:
                    os.remove(zipPath)
                    sys.exit("REFUSING: a key from your syncplay-defaults.json appears in {} - remove it from the code.".format(name))
    digest = hashlib.sha256(open(zipPath, "rb").read()).hexdigest()
    print("Built {} ({} KiB)\n".format(zipPath, os.path.getsize(zipPath) // 1024))
    print("On GitHub: Releases > Draft a new release")
    print("  Tag:    v{}".format(args.build))
    print("  Attach: {}".format(os.path.basename(zipPath)))
    print("  Description (the sha256 line is a fallback the updater uses if GitHub shows no digest for the file):\n")
    notes = ""
    sys.path.insert(0, ROOT)
    from syncplay import changelog
    entry = next((e for e in changelog.load(os.path.join(ROOT, "syncplay", "CHANGELOG.md")) if e[0] == args.build), None)
    if entry:
        notes = "\n".join("- " + bullet for bullet in entry[2])
    else:
        print("WARNING: syncplay/CHANGELOG.md has no '## Build {}' section - add one so the Update log describes this release.\n".format(args.build))
    print("{}\n\nsha256: {}".format(notes or "What's new: ...", digest))
    print("\nThen click Publish release. Every copy of the app updates itself the next time someone clicks Help > Update.")


if __name__ == "__main__":
    main()
