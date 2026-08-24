#!/usr/bin/python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Fill a workspace from what is saved for it (prd.md F6) — what the keybind runs.

Restore with the index defaulted to wherever you are standing, and with a word
of feedback when there is nothing to do, because a key that silently does
nothing is indistinguishable from a key that is broken.

Interface:  docs/open.md

Stdlib only — the helper layer must run on a stock Omarchy machine.
"""

import json
import shutil
import subprocess
import sys

import capture
import restore
import store


def note(msg):
    print(f"open: {msg}", file=sys.stderr)


def announce(msg):
    """Somewhere the user is looking, which is not stderr — nothing is watching
    the helper's output when a key is what ran it. Success stays silent: the
    windows are the feedback."""
    note(msg)
    if shutil.which("omarchy-notification-send"):
        subprocess.run(["omarchy-notification-send", "-g", "󱂬", msg], capture_output=True)


def active_index():
    index = capture.hyprctl("activeworkspace").get("id")
    if not isinstance(index, int):
        raise RuntimeError("no active workspace")
    return index


def main(argv):
    index = None
    for arg in argv[1:]:
        if index is None and not arg.startswith("--"):
            try:
                index = int(arg)
            except ValueError:
                note(f"workspace index must be an integer, got {arg!r}")
                return 2
        else:
            note(f"unexpected argument {arg!r}")
            return 2

    try:
        if index is None:
            index = active_index()
    except RuntimeError as e:
        note(str(e))
        return 1

    # An empty slot is the normal state of a workspace nobody has saved, so it
    # is answered rather than reported as a failure.
    if not store.exists(index):
        announce(f"Nothing saved for workspace {index}")
        return 1

    try:
        summary = restore.restore(index)
    except RuntimeError as e:
        note(str(e))
        return 1

    if summary["failed"]:
        announce(f"{summary['name']}: {', '.join(summary['failed'])} did not open")

    json.dump(summary, sys.stdout, separators=(",", ":"))
    sys.stdout.write("\n")
    return 0 if not summary["failed"] else 1


if __name__ == "__main__":
    sys.exit(main(["open", *sys.argv[1:]]))
