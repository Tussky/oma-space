#!/usr/bin/python3
"""Every workspace and the windows in it, right now, as JSON on stdout.

What the panel and the bar widget render (prd.md F1) — icon, app name, window
title. Live state, never a definition: nothing here is saved, and restore never
reads it.

Interface:  docs/live.md

Stdlib only — the helper layer must run on a stock Omarchy machine.
"""

import json
import os
import sys

import capture


def entry_icon(entry, fallback):
    return (entry or {}).get("Icon") or fallback


def describe(client, by_class, by_host, shared_pids):
    """(label, icon) for one live window.

    capture.resolve's order without the exec line: an omarchy-launch-tui window
    names its program in its class, a terminal is the program inside it, a webapp
    is the .desktop entry its class points back to.
    """
    cls = client.get("initialClass") or client.get("class") or ""
    pid = client.get("pid") or 0
    entry = by_class.get(cls)

    program = capture.omarchy_program(cls)
    if program:
        return program, program

    if capture.is_terminal(cls, entry):
        if pid not in shared_pids:
            program, _ = capture.terminal_contents(pid)
            if program:
                return program, entry_icon(entry, cls)
        return (entry or {}).get("Name") or cls, entry_icon(entry, cls)

    host = capture.class_host(cls)
    if host:
        entry = by_host.get(host)
        if entry:
            return entry.get("Name") or host, entry_icon(entry, host)
        return host, host

    if entry:
        return entry.get("Name") or cls, entry_icon(entry, cls)

    return cls, cls


def _sort_key(window):
    # Reading order on screen, so the list matches what the eye is looking at.
    return (window["_at"][1], window["_at"][0])


def live():
    capture.QUIET = True

    # One snapshot, same as capture: re-reading mid-run would describe a state
    # that never existed.
    clients = capture.hyprctl("clients")
    workspaces = capture.hyprctl("workspaces")
    active = capture.hyprctl("activeworkspace")

    by_class, by_host = capture.desktop_index()

    counts = {}
    for client in clients:
        counts[client.get("pid")] = counts.get(client.get("pid"), 0) + 1
    shared_pids = frozenset(pid for pid, n in counts.items() if pid and n > 1)

    grouped = {}
    for client in clients:
        index = (client.get("workspace") or {}).get("id")
        # Special workspaces carry negative ids; they are not one of the ten.
        if not isinstance(index, int) or index < 1:
            continue
        label, icon = describe(client, by_class, by_host, shared_pids)
        at = client.get("at") or [0, 0]
        grouped.setdefault(index, []).append(
            {
                "address": client.get("address") or "",
                "label": label or "",
                "class": client.get("initialClass") or client.get("class") or "",
                "title": client.get("title") or "",
                "icon": icon or "",
                "floating": bool(client.get("floating")),
                "fullscreen": client.get("fullscreen", 0) != 0,
                "_at": at if len(at) == 2 else [0, 0],
            }
        )

    layouts = {}
    for workspace in workspaces:
        index = workspace.get("id")
        if isinstance(index, int) and index >= 1:
            layouts[index] = workspace.get("tiledLayout") or ""

    windows = {}
    for index, items in grouped.items():
        items.sort(key=_sort_key)
        for item in items:
            item.pop("_at")
        windows[index] = items

    active_index = active.get("id")
    return {
        "active": active_index if isinstance(active_index, int) else 0,
        "workspaces": [
            {
                "index": index,
                "layout": layouts.get(index, ""),
                "windows": windows.get(index, []),
            }
            for index in sorted(set(layouts) | set(windows))
        ],
    }


def main(argv):
    if len(argv) != 1:
        print(f"usage: {os.path.basename(argv[0])}", file=sys.stderr)
        return 2

    try:
        state = live()
    except RuntimeError as e:
        print(f"live: {e}", file=sys.stderr)
        return 1

    # Single line: safe for both StdioCollector and a SplitParser.
    json.dump(state, sys.stdout, separators=(",", ":"))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
