#!/usr/bin/python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Empty a workspace's slot (prd.md F2).

The third write, after capture and edit, and the only one that takes something
away. A slot is emptied, never removed: the store is the ten workspaces, so
deleting a definition leaves workspace N with no configuration rather than
leaving a gap where workspace N used to be.

The workspace itself is untouched — whatever is open on it stays open. This
deletes the description, not the desk.

Interface:  docs/delete.md

Nothing here raises: every entry point returns its errors alongside its result,
the same contract store.py keeps.

Stdlib only — the helper layer must run on a stock Omarchy machine.
"""

import os
import sys

import store

USAGE = """usage: oma-space delete <workspace-index>

  oma-space delete 3        empty workspace 3's slot

The workspace keeps its windows; only what is saved for it goes.
"""


def fail(msg):
    print(f"delete: {msg}", file=sys.stderr)


def parse(argv):
    """(index, errors). Hand-rolled to match the other verbs."""
    index = None
    errors = []
    for arg in argv[1:]:
        if arg.startswith("--"):
            errors.append(f"unknown option {arg!r}")
        elif index is None:
            try:
                index = int(arg)
            except ValueError:
                errors.append(f"workspace index must be an integer, got {arg!r}")
        else:
            errors.append(f"unexpected argument {arg!r}")
    if index is None:
        errors.append("which workspace?")
    return index, errors


def main(argv):
    index, errors = parse(argv)
    if errors:
        for error in errors:
            fail(error)
        print(USAGE, file=sys.stderr)
        return 2

    # Read it first so the message can name what went, and so an empty slot is
    # reported as the no-op it is rather than as a deletion that did nothing.
    held, problems = store.load(index)
    for problem in problems:
        fail(problem)

    path, problems = store.clear(index)
    if problems:
        for problem in problems:
            fail(problem)
        return 1

    if held is None:
        fail(f"workspace {index} held no configuration")
    else:
        fail(f"deleted “{held.name}” from workspace {index}")

    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main([os.path.basename(sys.argv[0]), *sys.argv[1:]]))
