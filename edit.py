#!/usr/bin/python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""A workspace's labels, without re-reading the workspace (prd.md F6).

The other half of save. Save captures: it replaces a definition with what is on
the workspace right now, which is what you want when the arrangement changed and
is exactly what you do not want when only the name did. A workspace that happens
to be empty while you rename it would come back with no apps at all.

So renaming and re-iconing load the definition and change two fields. Nothing
else in it is read, written, or re-derived.

Interface:  docs/edit.md

Nothing here raises: every entry point returns its errors alongside its result,
the same contract store.py keeps.

Stdlib only — the helper layer must run on a stock Omarchy machine.
"""

import os
import sys

import store

USAGE = """usage: oma-space edit <workspace-index> [options]

  --name NAME     what the panel and the tab call this workspace
  --icon GLYPH    the icon it wears; empty takes it off

  oma-space edit 3 --name "Coding"
  oma-space edit 3 --icon ""
"""


def fail(msg):
    print(f"edit: {msg}", file=sys.stderr)


def labels(index, name=None, icon=None):
    """(workspace, path, errors). The definition with its labels changed and
    nothing else. `None` leaves a field alone; an empty icon takes it off.

    A warning from load about the file disagreeing with its own filename is
    dropped rather than returned: this rewrites the file, which is what settles
    it."""
    workspace, errors = store.load(index)
    if workspace is None:
        return None, None, errors or [f"workspace {index} holds no configuration"]

    if name is not None:
        workspace.name = name
    if icon is not None:
        workspace.icon = icon

    problems = workspace.validate()
    if problems:
        return None, None, problems

    path, problems = store.save(workspace, overwrite=True)
    if problems:
        return None, path, problems
    return workspace, path, []


def parse(argv):
    """(options, errors). Hand-rolled to match capture, save and live."""
    options = {"index": None, "name": None, "icon": None}
    errors = []
    args = iter(argv[1:])
    for arg in args:
        if arg in ("--name", "--icon"):
            value = next(args, None)
            if value is None:
                errors.append(f"{arg} needs a value")
                continue
            options[arg[2:]] = value
        elif arg.startswith("--"):
            errors.append(f"unknown option {arg!r}")
        elif options["index"] is None:
            try:
                options["index"] = int(arg)
            except ValueError:
                errors.append(f"workspace index must be an integer, got {arg!r}")
        else:
            errors.append(f"unexpected argument {arg!r}")
    if options["index"] is None:
        errors.append("which workspace?")
    if options["name"] is None and options["icon"] is None:
        errors.append("nothing to change: pass --name, --icon, or both")
    return options, errors


def main(argv):
    options, errors = parse(argv)
    if errors:
        for error in errors:
            fail(error)
        print(USAGE, file=sys.stderr)
        return 2

    workspace, path, errors = labels(
        options["index"], options["name"], options["icon"]
    )
    if workspace is None:
        for error in errors:
            fail(error)
        return 1

    # The path it wrote, like save: one line on stdout, nothing else.
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main([os.path.basename(sys.argv[0]), *sys.argv[1:]]))
