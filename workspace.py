"""oma-space · workspace definition data model.

JSON on disk, Workspace in memory. Nothing here raises — prd.md constraint 2.

Shape and field sources:  docs/capture.md

Stdlib only — the helper layer must run on a stock Omarchy machine.
"""

import json
import os

LAYOUTS = ["dwindle", "master", "monocle", "scrolling"]
DEFAULT_LAYOUT = "dwindle"
WORKSPACE_COUNT = 10


def shortcut_for_index(index):
    if not isinstance(index, int) or isinstance(index, bool):
        return None
    if index < 1 or index > WORKSPACE_COUNT:
        return None
    return f"Super+{index % 10}"


def is_fraction(n):
    return isinstance(n, (int, float)) and not isinstance(n, bool) and 0 < n <= 1


def _is_index(value):
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and 1 <= value <= WORKSPACE_COUNT
    )


# --- display ----------------------------------------------------------------
# For a human at a terminal. The wire format is to_json — see docs/capture.md.


def _display_path(path):
    if not isinstance(path, str) or not path:
        return None
    home = os.path.expanduser("~")
    if path == home:
        return "~"
    return "~" + path[len(home) :] if path.startswith(home + os.sep) else path


def _display_size(size):
    if size is None:
        return None
    if not (
        isinstance(size, list) and len(size) == 2 and all(is_fraction(n) for n in size)
    ):
        return f"bad size {size!r}"
    return f"{round(size[0] * 100)}%×{round(size[1] * 100)}%"


def _display_state(app):
    return (
        " ".join(
            state
            for state, on in (
                ("floating", app.floating),
                ("fullscreen", app.fullscreen),
            )
            if on
        )
        or "tiled"
    )


def _cell(value):
    return "-" if value is None or value == "" else str(value)


# Aligns rows into columns: a two-column key/value block, or a header plus app
# rows. The last column is never padded, so a long exec line just runs on.
def _rows(rows, indent=""):
    rows = [[_cell(cell) for cell in row] for row in rows]
    if not rows:
        return []
    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    lines = []
    for row in rows:
        cells = [cell.ljust(widths[i]) for i, cell in enumerate(row[:-1])]
        lines.append((indent + "  ".join(cells + [row[-1]])).rstrip())
    return lines


class WorkspaceApp:
    def __init__(self, opts=None):
        opts = opts or {}
        self.exec = opts.get("exec") or ""
        self.match_class = (
            opts.get("matchClass") or ""
        )  # machine key: claims the window on openwindow
        self.label = (
            opts.get("label") or ""
        )  # human name the panel shows: "nvim", "WhatsApp"
        self.cwd = opts.get("cwd")
        self.floating = bool(opts.get("floating", False))
        self.fullscreen = bool(opts.get("fullscreen", False))
        self.size = opts.get("size")  # [w, h] as fractions of usable workspace area

    # A bare string is shorthand for exec, assuming the class matches it. Capture
    # should always write both fields; the assumption is often wrong.
    @staticmethod
    def from_value(value):
        if isinstance(value, WorkspaceApp):
            return value
        if isinstance(value, str):
            return WorkspaceApp({"exec": value, "matchClass": value})
        return WorkspaceApp(value if isinstance(value, dict) else {})

    def validate(self):
        errors = []
        if not self.exec:
            errors.append("app is missing an exec line")
        if not self.match_class:
            errors.append(f'app "{self.exec}" is missing matchClass')
        if self.size is not None and not (
            isinstance(self.size, list)
            and len(self.size) == 2
            and all(is_fraction(n) for n in self.size)
        ):
            errors.append(f'app "{self.exec}" size must be [w, h] fractions in (0, 1]')
        return errors

    def generate_dispatch_statement(self):
        return

    def to_json(self):
        return {
            "exec": self.exec,
            "matchClass": self.match_class,
            "label": self.label,
            "cwd": self.cwd,
            "floating": self.floating,
            "fullscreen": self.fullscreen,
            "size": self.size,
        }

    # One app on its own: a key/value row per field, keyed as it is on disk.
    def __str__(self):
        return "\n".join(
            _rows(
                [
                    ["label", self.label],
                    ["exec", self.exec],
                    ["matchClass", self.match_class],
                    ["cwd", _display_path(self.cwd)],
                    ["state", _display_state(self)],
                    ["size", _display_size(self.size)],
                ]
            )
        )

    # The columns the app table uses, in header order.
    def _row(self):
        return [
            self.label or self.match_class,
            self.match_class,
            _display_size(self.size),
            _display_state(self),
            _display_path(self.cwd),
            self.exec,
        ]

    def __repr__(self):
        return (
            f"WorkspaceApp(label={self.label!r}, matchClass={self.match_class!r}, "
            f"exec={self.exec!r})"
        )


class Workspace:
    def __init__(self, opts=None):
        opts = opts or {}
        self.index = opts.get("index")  # the Omarchy workspace this hooks onto, 1–10
        self.name = opts.get("name") or ""
        self.icon = opts.get("icon") or ""
        self.layout = opts.get("layout") or DEFAULT_LAYOUT
        self.shortcut = opts.get("shortcut") or shortcut_for_index(
            self.index
        )  # reference only
        apps = opts.get("apps") or []
        self.apps = (
            [WorkspaceApp.from_value(app) for app in apps]
            if isinstance(apps, list)
            else []
        )

    def validate(self):
        errors = []
        if not self.name:
            errors.append("workspace has no name")
        if not _is_index(self.index):
            errors.append(
                f'workspace "{self.name}" must hook onto an Omarchy workspace '
                f"1–{WORKSPACE_COUNT}, got {self.index}"
            )
        if self.layout not in LAYOUTS:
            errors.append(
                f'workspace "{self.name}" has unknown layout "{self.layout}"; '
                f"expected one of {', '.join(LAYOUTS)}"
            )
        for app in self.apps:
            errors.extend(app.validate())
        return errors

    @property
    def is_valid(self):
        return not self.validate()

    # Returns (workspace, errors); workspace is None only if raw isn't an object.
    @staticmethod
    def from_json(raw):
        data = raw
        if isinstance(raw, (str, bytes, bytearray)):
            try:
                data = json.loads(raw)
            except ValueError as e:
                return None, [f"definition is not valid JSON: {e}"]
        if not isinstance(data, dict):
            return None, ["definition is not an object"]
        workspace = Workspace(data)
        return workspace, workspace.validate()

    def to_json(self):
        return {
            "index": self.index,
            "name": self.name,
            "icon": self.icon,
            "layout": self.layout,
            "shortcut": self.shortcut,
            "apps": [app.to_json() for app in self.apps],
        }

    APP_COLUMNS = ["LABEL", "CLASS", "SIZE", "STATE", "CWD", "EXEC"]

    # A key/value block for the workspace, then one indented row per app, then any
    # validation errors as "!" lines — an unnamed capture is meant to show one.
    def __str__(self):
        lines = _rows(
            [
                ["index", self.index],
                ["name", self.name],
                ["icon", self.icon],
                ["layout", self.layout],
                ["shortcut", self.shortcut],
                ["apps", len(self.apps)],
            ]
        )
        if self.apps:
            lines.append("")
            lines.extend(
                _rows(
                    [self.APP_COLUMNS] + [app._row() for app in self.apps], indent="  "
                )
            )
        errors = self.validate()
        if errors:
            lines.append("")
            lines.extend(f"! {error}" for error in errors)
        return "\n".join(lines)

    def __repr__(self):
        return (
            f"Workspace(name={self.name!r}, index={self.index!r}, "
            f"layout={self.layout!r}, apps={len(self.apps)})"
        )

    # capture's stdout, not live state: capture.py owns hyprctl and /proc (prd.md
    # F3), the model only ingests what it wrote. Shape: docs/capture.md.
    #
    # Returns (workspace, errors) like from_json. name and icon are the two fields
    # capture cannot know; pass them at save time. Without a name the definition is
    # unfinished by design, so errors is exactly ["workspace has no name"].
    @staticmethod
    def from_capture(raw, name=None, icon=None):
        workspace, errors = Workspace.from_json(raw)
        if workspace is None:
            return None, errors
        if name is not None:
            workspace.name = name.strip() if isinstance(name, str) else ""
        if icon is not None:
            workspace.icon = icon if isinstance(icon, str) else ""
        # index is authoritative in a capture; a shortcut is only ever derived here.
        workspace.shortcut = shortcut_for_index(workspace.index)
        return workspace, workspace.validate()
