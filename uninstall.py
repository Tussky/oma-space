#!/usr/bin/python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Take the tabs off the bar and give Omarchy its strip back (prd.md F6).

The other half of install, and not optional: install removes `omarchy.workspaces`
from the bar layout, and `omarchy plugin remove` will not put it back. Worse, it
drops a single layout entry per plugin — with a tab per workspace that leaves the
rest of them behind as dead slots. So uninstalling is ours to do.

Interface:  docs/uninstall.md

Nothing here raises: every entry point returns its errors alongside its result,
the same contract store.py keeps.

Stdlib only — the helper layer must run on a stock Omarchy machine.
"""

import os
import shutil
import sys

import install
import store
from install import (
    DEFAULT_SECTION,
    OMARCHY_WORKSPACES,
    SECTIONS,
    entry_id,
)

USAGE = """usage: oma-space uninstall [options]

  --no-omarchy   leave omarchy.workspaces off the bar as well
  --purge        also delete the installed plugin directory
  --dry-run      print what would be written and change nothing

Definitions in ~/.config/oma-space/workspaces are never touched.
"""


def fail(msg):
    print(f"uninstall: {msg}", file=sys.stderr)


def restore_layout(layout, pid, restore_omarchy=True):
    """(layout, notes). Every tab out, and Omarchy's own strip back where they
    stood — the position is the point: putting it back at the end of the section
    would leave the bar rearranged by a plugin the user just removed."""
    notes = []
    next_layout = {}
    for name in SECTIONS:
        next_layout[name] = list(layout.get(name) or [])
    for name, value in layout.items():
        if name not in next_layout:
            next_layout[name] = value

    anchor_section = None
    anchor_at = None
    removed = 0

    for name in SECTIONS:
        kept = []
        for entry in next_layout[name]:
            if entry_id(entry) == pid:
                if anchor_section is None:
                    anchor_section, anchor_at = name, len(kept)
                removed += 1
                continue
            kept.append(entry)
        next_layout[name] = kept

    notes.append(f"removed {removed} tab{'' if removed == 1 else 's'}")

    already = any(
        entry_id(entry) == OMARCHY_WORKSPACES
        for name in SECTIONS
        for entry in next_layout[name]
    )
    if restore_omarchy and not already:
        target = anchor_section or DEFAULT_SECTION
        at = anchor_at if anchor_at is not None else len(next_layout[target])
        next_layout[target].insert(at, {"id": OMARCHY_WORKSPACES})
        notes.append(f"put {OMARCHY_WORKSPACES} back in {target}")
    elif already:
        notes.append(f"{OMARCHY_WORKSPACES} was already on the bar")

    return next_layout, notes


def purge(source, target, dry_run=False):
    """(removed, note, error). Never the directory this is running from: the
    modules are loaded, but the user asked to uninstall a plugin, not to delete
    the checkout they are working in."""
    if not os.path.isdir(target) and not os.path.islink(target):
        return False, f"nothing installed at {target}", None
    if os.path.realpath(source) == os.path.realpath(target):
        return False, None, (
            f"refusing to delete {target}: it is the directory this is running "
            "from. Run uninstall from your checkout, or remove it by hand."
        )
    if dry_run:
        return True, f"would delete {target}", None
    try:
        if os.path.islink(target):
            os.unlink(target)
        else:
            shutil.rmtree(target)
    except OSError as error:
        return False, None, f"could not delete {target}: {error}"
    return True, f"deleted {target}", None


def parse(argv):
    """(options, errors). Hand-rolled to match the other verbs."""
    options = {"omarchy": True, "purge": False, "dry_run": False}
    errors = []
    for arg in argv[1:]:
        if arg == "--no-omarchy":
            options["omarchy"] = False
        elif arg == "--purge":
            options["purge"] = True
        elif arg == "--dry-run":
            options["dry_run"] = True
        else:
            errors.append(f"unknown option {arg!r}")
    return options, errors


def main(argv):
    options, errors = parse(argv)
    if errors:
        for error in errors:
            fail(error)
        print(USAGE, file=sys.stderr)
        return 2

    source = install.source_dir()
    pid, error = install.plugin_id(source)
    if error or not pid:
        fail(error or "manifest.json has no id")
        return 1

    path = install.shell_config_path()
    config, seeded, error = install.read_config(path)
    if error:
        fail(error)
        return 1
    if seeded:
        fail(f"no user shell config; nothing of ours is on the bar in {seeded}")
        return 0

    bar = config.get("bar")
    layout = bar.get("layout") if isinstance(bar, dict) else None
    if not isinstance(bar, dict) or not isinstance(layout, dict):
        fail("this shell config has no bar layout; nothing to take off it")
        return 0

    layout, notes = restore_layout(layout, pid, options["omarchy"])
    bar["layout"] = layout
    for note in notes:
        print(f"uninstall: {note}", file=sys.stderr)

    if not options["dry_run"]:
        error = install.write_config(path, config)
        if error:
            fail(error)
            return 1
        print(f"uninstall: wrote {path}", file=sys.stderr)

    if options["purge"]:
        target = os.path.join(install.plugins_dir(), pid)
        _, note, error = purge(source, target, options["dry_run"])
        if error:
            fail(error)
            return 1
        print(f"uninstall: {note}", file=sys.stderr)

    print(
        f"uninstall: your definitions are untouched in {store.workspaces_dir()}",
        file=sys.stderr,
    )

    if options["dry_run"]:
        return 0
    if not install.reload_shell():
        print(
            "uninstall: could not reach the shell — run `omarchy restart shell`",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main([os.path.basename(sys.argv[0]), *sys.argv[1:]]))
