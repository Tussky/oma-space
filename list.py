#!/usr/bin/python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""The ten workspaces and what is saved for each (prd.md F1, Architecture).

The other half of `live`: what is *saved*, whether or not anything of theirs is
running. Always ten entries — the store is the ten workspaces, and an empty one
is a workspace nobody has saved yet, not a missing record.

Stdlib only — the helper layer must run on a stock Omarchy machine.
"""

import json
import os
import sys

import store
from workspace import Workspace


def slot_json(index, workspace):
    """Every slot is a Workspace on the wire, so the panel renders ten rows
    without a second shape to handle. An empty one is the model's defaults with
    no name — which is exactly what an unsaved workspace is."""
    return (workspace or Workspace({"index": index})).to_json()


def main(argv):
    as_json = False
    for arg in argv[1:]:
        if arg == "--json":
            as_json = True
        else:
            print(f"usage: {os.path.basename(argv[0])} [--json]", file=sys.stderr)
            return 2

    workspaces, errors = store.slots()
    for error in errors:
        print(f"list: {error}", file=sys.stderr)

    if as_json:
        # Single line: safe for both StdioCollector and a SplitParser.
        json.dump(
            [slot_json(i, w) for i, w in zip(store.INDICES, workspaces)],
            sys.stdout,
            separators=(",", ":"),
        )
        sys.stdout.write("\n")
        return 0

    for index, workspace in zip(store.INDICES, workspaces):
        if workspace is None:
            print(f"{index:>3}  {'—':<16}  empty")
            continue
        apps = len(workspace.apps)
        print(
            f"{index:>3}  {workspace.name:<16}  "
            f"{apps} app{'' if apps == 1 else 's'}  {workspace.layout}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main(["list", *sys.argv[1:]]))
