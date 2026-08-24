#!/usr/bin/python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Rebuild a saved definition as a live workspace (prd.md F4).

Interface:  docs/restore.md

Spawn-then-claim, because Hyprland's own `exec` workspace rules track windows by
process environment and chromium-family apps clear theirs (prd.md constraint 1):
subscribe to the event socket first, launch, match the window that appears by
class, then move it. Launching is ours rather than Hyprland's for a second
reason — a definition's whole point is the working directory, and a dispatcher
takes no cwd.

Stdlib only — the helper layer must run on a stock Omarchy machine.
"""

import json
import os
import select
import shlex
import socket
import subprocess
import sys
import time

import capture
import store
from workspace import LAYOUTS

# How long one window has to appear before the sequence moves on. A failed
# launch never blocks the rest of the workspace (prd.md lifecycle).
DEFAULT_TIMEOUT = 10.0

QUIET = False


def note(msg):
    if not QUIET:
        print(f"restore: {msg}", file=sys.stderr)


# --- Hyprland ---------------------------------------------------------------
#
# Hyprland 0.56 parses a Lua API: `hyprctl dispatch workspace 1` and
# `hyprctl keyword` are both gone. Names verified against this build; Omarchy's
# own scripts drive it the same way.


def lua_string(value):
    text = str(value)
    for old, new in (("\\", "\\\\"), ('"', '\\"'), ("\n", "\\n")):
        text = text.replace(old, new)
    return f'"{text}"'


def hypr(verb, source):
    try:
        proc = subprocess.run(
            ["hyprctl", verb, source], capture_output=True, text=True, timeout=10
        )
    except (OSError, subprocess.SubprocessError) as error:
        return False, str(error)
    output = (proc.stdout or "").strip()
    if proc.returncode != 0 or output.startswith("error"):
        return False, output or (proc.stderr or "").strip()
    return True, output


def dispatch(call):
    return hypr("dispatch", call)


def window_ref(address):
    return f"address:{address}"


def focus_workspace(index):
    return dispatch(f"hl.dsp.focus({{ workspace = {lua_string(index)} }})")


def set_layout(index, layout):
    """A workspace rule, evaluated live. Omarchy persists its own layout toggles
    into ~/.local/state/omarchy; oma-space deliberately does not write there —
    that state belongs to Omarchy, the same way its keybinds do (prd.md F6)."""
    return hypr(
        "eval",
        f"hl.workspace_rule({{ workspace = {lua_string(index)}, "
        f"layout = {lua_string(layout)} }})",
    )


def claim(address, index):
    """movetoworkspacesilent's replacement: follow = false is the silent half."""
    return dispatch(
        f"hl.dsp.window.move({{ workspace = {lua_string(index)}, follow = false, "
        f"window = {lua_string(window_ref(address))} }})"
    )


def set_floating(address, floating):
    # No dispatcher sets the state outright — action is a toggle whatever it is
    # handed — so the current state decides whether to send anything at all.
    return dispatch(
        f"hl.dsp.window.float({{ window = {lua_string(window_ref(address))}, "
        f'action = "toggle" }})'
    )


def set_fullscreen(address):
    return dispatch(
        f"hl.dsp.window.fullscreen({{ mode = \"fullscreen\", "
        f"window = {lua_string(window_ref(address))} }})"
    )


def resize(address, width, height):
    return dispatch(
        f"hl.dsp.window.resize({{ window = {lua_string(window_ref(address))}, "
        f"x = {int(width)}, y = {int(height)} }})"
    )


# --- the event socket -------------------------------------------------------


def socket_path():
    signature = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
    if not signature:
        raise RuntimeError("HYPRLAND_INSTANCE_SIGNATURE is unset; not inside Hyprland")
    runtime = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    return os.path.join(runtime, "hypr", signature, ".socket2.sock")


class Windows:
    """openwindow events, subscribed to before anything is launched.

    Opening the socket after the dispatch would race the window: a fast app maps
    before the subscription lands and is never seen.
    """

    def __init__(self):
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.connect(socket_path())
        self.buffer = ""

    def close(self):
        try:
            self.socket.close()
        except OSError:
            pass

    def wait_for(self, match_class, deadline):
        """The address of the next window to map with this class, or None if the
        deadline passes first."""
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            ready, _, _ = select.select([self.socket], [], [], remaining)
            if not ready:
                return None
            try:
                chunk = self.socket.recv(8192).decode(errors="replace")
            except OSError:
                return None
            if not chunk:
                return None
            self.buffer += chunk
            while "\n" in self.buffer:
                line, self.buffer = self.buffer.split("\n", 1)
                address = _opened(line, match_class)
                if address:
                    return address


def _opened(line, match_class):
    """openwindow>>address,workspacename,class,title — the class the event
    carries is the one at map time, which is what matchClass holds."""
    name, _, payload = line.partition(">>")
    if name != "openwindow":
        return None
    parts = payload.split(",", 3)
    if len(parts) < 3:
        return None
    address, _, window_class = parts[0], parts[1], parts[2]
    if window_class != match_class and window_class.lower() != match_class.lower():
        return None
    return f"0x{address}" if not address.startswith("0x") else address


# --- restore ----------------------------------------------------------------


def usable_area(index, monitors, workspaces):
    """The area a size fraction is a fraction of, for the monitor this
    workspace is on."""
    monitor_name = next(
        (w.get("monitor") for w in workspaces if w.get("id") == index), None
    )
    monitor = next(
        (m for m in monitors if m.get("name") == monitor_name),
        next((m for m in monitors if m.get("focused")), None),
    )
    return capture.usable_area(monitor) if monitor else (0, 0)


def client_at(address):
    for client in capture.hyprctl("clients"):
        if client.get("address") == address:
            return client
    return None


def place(address, app, area):
    """Floating, fullscreen and size, in that order: a window has to be floating
    before an exact size means anything."""
    client = client_at(address)
    if client is None:
        note(f"{app.label or app.match_class} vanished before it could be placed")
        return

    if bool(client.get("floating")) != app.floating:
        set_floating(address, app.floating)

    if app.size and area[0] > 0 and area[1] > 0:
        if app.floating:
            resize(address, app.size[0] * area[0], app.size[1] * area[1])
        else:
            # prd.md F3 keeps a tiled window's size as intent — dwindle wants a
            # splitratio and scrolling a column width, neither of which Hyprland
            # takes as an absolute. Saying so beats resizing into the wrong one.
            note(f"{app.label or app.match_class}: tiled sizes are not applied yet")

    if app.fullscreen:
        set_fullscreen(address)


def launch(app):
    """Ours rather than Hyprland's, so the working directory survives."""
    argv = shlex.split(app.exec)
    if not argv:
        return False
    cwd = app.cwd if app.cwd and os.path.isdir(app.cwd) else None
    if app.cwd and cwd is None:
        note(f"{app.cwd} is gone; launching {app.label or argv[0]} without it")
    try:
        subprocess.Popen(
            argv,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as e:
        note(f"could not launch {app.exec!r}: {e}")
        return False
    return True


def missing(apps, clients, index):
    """The apps to launch: what the definition asks for, minus what is already
    on the workspace. Counted rather than set-matched, so a definition with two
    terminals and one open gets one more, never two (prd.md lifecycle)."""
    present = {}
    for client in clients:
        if (client.get("workspace") or {}).get("id") != index:
            continue
        cls = client.get("initialClass") or client.get("class") or ""
        present[cls] = present.get(cls, 0) + 1

    todo = []
    for app in apps:
        if present.get(app.match_class, 0) > 0:
            present[app.match_class] -= 1
            note(f"{app.label or app.match_class} is already here; leaving it alone")
            continue
        todo.append(app)
    return todo


def restore(index, timeout=DEFAULT_TIMEOUT):
    """Rebuild one of the ten workspaces from what is saved for it. A workspace
    holds one configuration or none (prd.md F6), so the index is the whole
    address — there is nothing else to disambiguate."""
    workspace, errors = store.load(index)
    for error in errors:
        note(error)
    if workspace is None:
        raise RuntimeError(f"nothing saved for workspace {index}")
    if workspace.layout in LAYOUTS:
        ok, message = set_layout(index, workspace.layout)
        if not ok:
            note(f"could not set layout {workspace.layout}: {message}")

    focus_workspace(index)

    monitors = capture.hyprctl("monitors")
    workspaces = capture.hyprctl("workspaces")
    area = usable_area(index, monitors, workspaces)
    todo = missing(workspace.apps, capture.hyprctl("clients"), index)

    summary = {"name": workspace.name, "index": index, "launched": [], "failed": []}
    if not todo:
        return summary

    # Subscribed before the first launch, and held open across all of them.
    events = Windows()
    try:
        for app in todo:
            if not app.exec:
                note(f"{app.label or app.match_class} has no exec line; skipping")
                summary["failed"].append(app.label or app.match_class)
                continue
            if not launch(app):
                summary["failed"].append(app.label or app.match_class)
                continue
            address = events.wait_for(app.match_class, time.monotonic() + timeout)
            if address is None:
                note(
                    f"no {app.match_class} window appeared within {timeout:g}s; "
                    "moving on"
                )
                summary["failed"].append(app.label or app.match_class)
                continue
            claim(address, index)
            place(address, app, area)
            summary["launched"].append(app.label or app.match_class)
    finally:
        events.close()

    return summary


def main(argv):
    index, timeout = None, DEFAULT_TIMEOUT
    args = iter(argv[1:])
    for arg in args:
        if arg == "--timeout":
            try:
                timeout = float(next(args, ""))
            except ValueError:
                note("--timeout must be a number of seconds")
                return 2
        elif index is None and not arg.startswith("--"):
            try:
                index = int(arg)
            except ValueError:
                note(f"workspace index must be an integer, got {arg!r}")
                return 2
        else:
            note(f"unexpected argument {arg!r}")
            return 2
    if index is None:
        print(
            f"usage: {os.path.basename(argv[0])} <workspace-index> [--timeout SECONDS]",
            file=sys.stderr,
        )
        return 2

    try:
        summary = restore(index, timeout)
    except RuntimeError as e:
        note(str(e))
        return 1

    json.dump(summary, sys.stdout, separators=(",", ":"))
    sys.stdout.write("\n")
    return 0 if not summary["failed"] else 1


if __name__ == "__main__":
    sys.exit(main(["restore", *sys.argv[1:]]))
