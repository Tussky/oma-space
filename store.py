"""oma-space · the ten workspace slots on disk.

A workspace has one configuration or it has none. Every definition hooks onto one
of Omarchy's ten workspaces (prd.md F6), so the workspace *is* the identity:
slot N lives at N.json, which makes a second configuration for the same
workspace unrepresentable rather than merely discouraged.

The name is a label, not a key. Renaming a workspace moves no file, and two
slots may carry the same name without anything breaking — nothing is ever looked
up by it.

Nothing here raises: every entry point returns its errors alongside its result,
the same contract workspace.py keeps.

Stdlib only — the helper layer must run on a stock Omarchy machine.
"""

import json
import os
import tempfile

from workspace import WORKSPACE_COUNT, Workspace

SUFFIX = ".json"

# The slots, once, so a caller never writes range(1, 11) itself.
INDICES = tuple(range(1, WORKSPACE_COUNT + 1))


def workspaces_dir():
    """Read from the environment per call, not at import: the helper is a
    long-lived process on the QML side."""
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(
        os.path.expanduser("~"), ".config"
    )
    return os.path.join(base, "oma-space", "workspaces")


def is_slot(index):
    return (
        isinstance(index, int)
        and not isinstance(index, bool)
        and index in INDICES
    )


def path_for(index):
    """Where this workspace's configuration lives, or None if there is no such
    workspace. An int filename cannot escape the directory the way a name could."""
    return os.path.join(workspaces_dir(), f"{index}{SUFFIX}") if is_slot(index) else None


def exists(index):
    path = path_for(index)
    return bool(path) and os.path.exists(path)


# --- write ------------------------------------------------------------------


def save(workspace, overwrite=False):
    """(path, errors). `path` is the slot this belongs in, so a caller can name
    it in its own message; nothing is written unless errors is empty.

    Replacing is still the user's call. The slot model removes the question of
    *where* a definition goes — it goes where its workspace is — but not the one
    F3 cares about: capture never merges into what is on disk, so a replace
    discards whatever was there, and that stays a thing the user asks for twice.
    """
    if not isinstance(workspace, Workspace):
        return None, ["not a workspace definition"]
    errors = workspace.validate()
    if errors:
        return None, errors

    path = path_for(workspace.index)
    if path is None:
        return None, [f"there is no workspace {workspace.index}"]
    if os.path.exists(path) and not overwrite:
        held, _ = load(workspace.index)
        holder = f'"{held.name}"' if held else "a definition"
        return path, [f"workspace {workspace.index} already holds {holder}"]

    # Written whole or not at all: a slot half on disk would fail to parse for
    # every reader of the directory, not just this one.
    temp = None
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        fd, temp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".", suffix=SUFFIX)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            # Indented, unlike the single-line stdout the QML side parses: this
            # file is meant to be opened and edited by hand.
            json.dump(workspace.to_json(), f, indent=2)
            f.write("\n")
        os.replace(temp, path)
        temp = None
    except OSError as e:
        if temp:
            try:
                os.unlink(temp)
            except OSError:
                pass
        return path, [f"could not write {path}: {e}"]
    return path, []


def clear(index):
    """Empty a slot. (path, errors); an already-empty slot is not an error."""
    path = path_for(index)
    if path is None:
        return None, [f"there is no workspace {index}"]
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
    except OSError as e:
        return path, [f"could not remove {path}: {e}"]
    return path, []


# --- read -------------------------------------------------------------------


def load(index):
    """(workspace, errors) for one slot. An **empty slot is (None, [])** — a
    workspace nobody has saved yet is the normal state, not a failure."""
    path = path_for(index)
    if path is None:
        return None, [f"there is no workspace {index}"]
    try:
        with open(path, encoding="utf-8") as f:
            raw = f.read()
    except FileNotFoundError:
        return None, []
    except OSError as e:
        return None, [f"could not read {path}: {e}"]

    workspace, errors = Workspace.from_json(raw)
    if workspace is None:
        return None, [f"{index}{SUFFIX}: {error}" for error in errors]
    if workspace.index != index:
        # The filename is the identity; a hand-edited index field disagreeing
        # with it would otherwise be a second configuration for one workspace,
        # which is the thing this layout exists to prevent.
        errors = [
            f"{index}{SUFFIX}: says index {workspace.index}; using {index}"
        ] + [e for e in errors if "hook onto" not in e]
        workspace.index = index
        workspace.shortcut = Workspace({"index": index}).shortcut
        errors.extend(workspace.validate())
    return workspace, errors


def slots():
    """All ten, in order: (workspaces, errors) where each entry is a Workspace
    or None for an empty slot. The store is always ten workspaces — saving fills
    one, it never adds one."""
    workspaces, errors = [], []
    for index in INDICES:
        workspace, problems = load(index)
        errors.extend(problems)
        workspaces.append(workspace)
    return workspaces, errors


def saved():
    """Only the occupied slots, in index order."""
    workspaces, errors = slots()
    return [w for w in workspaces if w is not None], errors
