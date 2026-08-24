#!/usr/bin/python3
"""Save a definition to ~/.config/oma-space/workspaces.

The step capture deliberately leaves to the user (prd.md F3): capture only
reads, and this decides where — and whether — the result lands.

Interface:  docs/save.md

Stdlib only — the helper layer must run on a stock Omarchy machine.
"""

import json
import os
import sys

import capture
import store
from workspace import Workspace

# A refusal the caller can act on: the definition is fine, the workspace is
# taken. The widget turns this into "Save again to replace" rather than an error.
EXISTS = 3

USAGE = """usage: oma-space save <name> [options]

  --index N       capture workspace N now, instead of reading stdin
  --icon GLYPH    the icon the panel shows beside the name
  --force         replace whatever this workspace already holds

  oma-space save --index 1 "Coding"          capture and save in one action
  oma-space capture 1 | oma-space save "Coding"
  oma-space save "Coding" < reviewed.json    save a definition you edited
"""


def fail(msg):
    print(f"save: {msg}", file=sys.stderr)


def parse(argv):
    """(options, errors). Hand-rolled to match capture and live."""
    options = {"name": None, "index": None, "icon": None, "force": False}
    errors = []
    args = iter(argv[1:])
    for arg in args:
        if arg == "--force":
            options["force"] = True
        elif arg in ("--index", "--icon"):
            value = next(args, None)
            if value is None:
                errors.append(f"{arg} needs a value")
                continue
            if arg == "--icon":
                options["icon"] = value
                continue
            try:
                options["index"] = int(value)
            except ValueError:
                errors.append(f"--index must be an integer, got {value!r}")
        elif arg.startswith("--"):
            errors.append(f"unknown option {arg}")
        elif options["name"] is None:
            options["name"] = arg
        else:
            errors.append(f"unexpected argument {arg!r}")
    if not (options["name"] or "").strip():
        errors.append("a definition needs a name")
    return options, errors


def from_stdin(name, icon):
    """(workspace, errors) for a definition piped in — capture's stdout, or a
    file the user edited in between."""
    if sys.stdin.isatty():
        return None, ["nothing on stdin; pipe a capture in, or pass --index N"]
    raw = sys.stdin.read()
    if not raw.strip():
        return None, ["nothing on stdin; pipe a capture in, or pass --index N"]
    return Workspace.from_capture(raw, name=name, icon=icon)


def main(argv):
    options, errors = parse(argv)
    if errors:
        for error in errors:
            fail(error)
        print(USAGE, file=sys.stderr)
        return 2

    name, icon = options["name"], options["icon"]
    if options["index"] is None:
        workspace, errors = from_stdin(name, icon)
    else:
        try:
            # No exec, no JSON round-trip: capture is a module, and this is the
            # same object it hands restore.
            workspace = capture.workspace(options["index"], name=name, icon=icon)
        except RuntimeError as e:
            fail(str(e))
            return 1
        errors = workspace.validate()

    if workspace is None or errors:
        for error in errors:
            fail(error)
        return 1

    existed = store.exists(workspace.index)
    path, errors = store.save(workspace, overwrite=options["force"])
    if errors:
        for error in errors:
            fail(error)
        if existed and not options["force"]:
            fail("pass --force to replace it")
            return EXISTS
        return 1

    if existed:
        fail(f"replaced what was on workspace {workspace.index}")
    # The path is the whole machine-readable answer, so it is all stdout carries.
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main(["save", *sys.argv[1:]]))
