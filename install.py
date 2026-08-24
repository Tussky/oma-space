#!/usr/bin/python3
"""Put the tabs on the bar and take Omarchy's strip off it (prd.md F6).

Omarchy has no install hook — `omarchy plugin add` clones a directory and stops
there — so the takeover is a verb the user runs. It does two things: installs the
plugin directory itself, and rewrites the bar layout in shell.json so the tabs
stand exactly where `omarchy.workspaces` stood.

Interface:  docs/install.md

Nothing here raises: every entry point returns its errors alongside its result,
the same contract store.py keeps.

Stdlib only — the helper layer must run on a stock Omarchy machine.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

from workspace import WORKSPACE_COUNT

OMARCHY_WORKSPACES = "omarchy.workspaces"
SECTIONS = ("left", "center", "right")
DEFAULT_SECTION = "left"

# The scratch tab is workspace 10, so a numbered tab for 10 would be a second
# tab on the same workspace. Nine numbered tabs plus scratch is the whole strip.
DEFAULT_TABS = WORKSPACE_COUNT - 1

# A copied plugin directory is the published shape: no symlinks (the shell's own
# validator refuses them), no working-tree noise.
SKIP = shutil.ignore_patterns(
    ".git", ".gitignore", ".venv", "__pycache__", "*.pyc", ".claude", ".python-version"
)

USAGE = """usage: oma-space install [options]

  --tabs N        numbered tabs to place, 1-10 (default 9, leaving 10 to scratch)
  --no-scratch    place no scratch tab
  --section S     left, center or right (default: where omarchy.workspaces was)
  --keep-omarchy  leave omarchy.workspaces on the bar beside the tabs
  --layout-only   rewrite the bar layout; do not install the directory
  --dry-run       print what would be written and change nothing
"""


def fail(msg):
    print(f"install: {msg}", file=sys.stderr)


def config_home():
    return os.environ.get("XDG_CONFIG_HOME") or os.path.join(
        os.path.expanduser("~"), ".config"
    )


def plugins_dir():
    return os.path.join(config_home(), "omarchy", "plugins")


def shell_config_path():
    return os.path.join(config_home(), "omarchy", "shell.json")


def omarchy_path():
    return os.environ.get("OMARCHY_PATH") or "/usr/share/omarchy"


def default_config_path():
    """What the shell reads when the user has no config of their own."""
    return os.path.join(omarchy_path(), "config", "omarchy", "shell.json")


def source_dir():
    """The plugin directory this helper belongs to."""
    return os.path.dirname(os.path.abspath(__file__))


def plugin_id(source):
    """The id the shell registers this plugin under, read from the manifest so
    it is stated once."""
    try:
        with open(os.path.join(source, "manifest.json"), encoding="utf-8") as handle:
            return str(json.load(handle).get("id") or ""), None
    except (OSError, ValueError) as error:
        return "", f"could not read manifest.json: {error}"


# --- the directory ----------------------------------------------------------


def install_files(source, target, dry_run=False):
    """Copy the plugin into the Omarchy plugins directory, replacing a symlink
    left by a development checkout. Returns (installed, note, error)."""
    if os.path.realpath(source) == os.path.realpath(target) and not os.path.islink(
        target
    ):
        return False, f"already installed at {target}", None

    if dry_run:
        return True, f"would install {source} -> {target}", None

    try:
        if os.path.islink(target):
            # Only the link goes; what it points at is the source being copied.
            os.unlink(target)
        elif os.path.isdir(target):
            if not os.path.exists(os.path.join(target, "manifest.json")):
                return False, None, f"{target} exists and is not a plugin directory"
            shutil.rmtree(target)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copytree(source, target, ignore=SKIP, symlinks=False)
    except OSError as error:
        return False, None, f"could not install into {target}: {error}"
    return True, f"installed {source} -> {target}", None


# --- the bar layout ---------------------------------------------------------


def entry_id(entry):
    if isinstance(entry, str):
        return entry
    if isinstance(entry, dict):
        return str(entry.get("id") or "")
    return ""


def tab_entries(pid, tabs=DEFAULT_TABS, scratch=True):
    """The strip: one entry per workspace, in order, then the scratch tab."""
    entries = [{"id": pid, "index": index} for index in range(1, tabs + 1)]
    if scratch:
        entries.append({"id": pid, "scratch": True})
    return entries


def rewrite_layout(layout, pid, entries, section=None, keep_omarchy=False):
    """The tabs where Omarchy's strip stood. Returns (layout, notes).

    Idempotent: tabs already placed are taken out and re-placed, so running
    install twice leaves one strip rather than two."""
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
    replaced = 0

    for name in SECTIONS:
        kept = []
        for entry in next_layout[name]:
            current = entry_id(entry)
            is_anchor = current == pid or (
                current == OMARCHY_WORKSPACES and not keep_omarchy
            )
            if is_anchor and anchor_section is None:
                anchor_section, anchor_at = name, len(kept)
            if current == pid:
                replaced += 1
                continue
            if current == OMARCHY_WORKSPACES and not keep_omarchy:
                removed += 1
                continue
            kept.append(entry)
        next_layout[name] = kept

    target = section or anchor_section or DEFAULT_SECTION
    at = anchor_at if (anchor_section == target and anchor_at is not None) else len(
        next_layout[target]
    )
    next_layout[target][at:at] = entries

    if removed:
        notes.append(
            f"removed {removed} {OMARCHY_WORKSPACES} "
            f"entr{'y' if removed == 1 else 'ies'}"
        )
    if replaced:
        notes.append(f"replaced {replaced} existing tab{'' if replaced == 1 else 's'}")
    notes.append(f"placed {len(entries)} tabs in {target}")
    return next_layout, notes


def read_json(path):
    try:
        with open(path, encoding="utf-8") as handle:
            config = json.load(handle)
    except FileNotFoundError:
        return None, f"no shell config at {path}"
    except (OSError, ValueError) as error:
        return None, f"could not read {path}: {error}"
    if not isinstance(config, dict):
        return None, f"{path} is not a shell config"
    return config, None


def read_config(path):
    """(config, seeded_from, error). A stock Omarchy has no user shell.json —
    the file appears the first time something is customised — so the defaults
    the shell itself falls back to are what a first install starts from."""
    config, error = read_json(path)
    if config is not None:
        return config, None, None
    if not os.path.exists(path):
        default = default_config_path()
        config, default_error = read_json(default)
        if config is not None:
            return config, default, None
        return None, None, f"{error}, and no defaults at {default}: {default_error}"
    return None, None, error


def write_config(path, config):
    """Atomic, and never without a backup: this is the user's whole bar.

    The backup is written once and then left alone. The state worth keeping is
    the bar as it was before oma-space first touched it, and a second run would
    otherwise overwrite it with a copy of what install itself wrote. A machine
    with no user config yet has nothing to back up — the shell's own defaults
    are still on disk where it found them."""
    backup = path + ".bak"
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if os.path.exists(path) and not os.path.exists(backup):
            shutil.copyfile(path, backup)
        handle = tempfile.NamedTemporaryFile(
            "w", dir=os.path.dirname(path), delete=False, encoding="utf-8"
        )
        with handle:
            json.dump(config, handle, indent=2)
            handle.write("\n")
        os.replace(handle.name, path)
    except OSError as error:
        return f"could not write {path}: {error}"
    return None


def reload_shell():
    """Best effort: the layout is on disk either way, and a shell that is not
    running is not an install failure."""
    for method in ("rescanPlugins", "reloadConfig"):
        try:
            subprocess.run(
                ["omarchy-shell", "-q", "shell", method],
                check=False,
                capture_output=True,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            return False
    return True


# --- the verb ---------------------------------------------------------------


def parse(argv):
    """(options, errors). Hand-rolled to match capture, save and live."""
    options = {
        "tabs": DEFAULT_TABS,
        "scratch": True,
        "section": None,
        "keep_omarchy": False,
        "layout_only": False,
        "dry_run": False,
    }
    errors = []
    args = iter(argv[1:])
    for arg in args:
        if arg == "--no-scratch":
            options["scratch"] = False
        elif arg == "--keep-omarchy":
            options["keep_omarchy"] = True
        elif arg == "--layout-only":
            options["layout_only"] = True
        elif arg == "--dry-run":
            options["dry_run"] = True
        elif arg in ("--tabs", "--section"):
            value = next(args, None)
            if value is None:
                errors.append(f"{arg} needs a value")
                continue
            if arg == "--section":
                if value not in SECTIONS:
                    errors.append(f"--section must be one of {', '.join(SECTIONS)}")
                else:
                    options["section"] = value
                continue
            try:
                count = int(value)
            except ValueError:
                errors.append(f"--tabs must be an integer, got {value!r}")
                continue
            if not 1 <= count <= WORKSPACE_COUNT:
                errors.append(f"--tabs must be 1-{WORKSPACE_COUNT}, got {count}")
            else:
                options["tabs"] = count
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

    source = source_dir()
    pid, error = plugin_id(source)
    if error or not pid:
        fail(error or "manifest.json has no id")
        return 1

    # Read the bar before touching the filesystem: a config this cannot parse
    # should not leave a half-installed plugin directory behind.
    path = shell_config_path()
    config, seeded, error = read_config(path)
    if error:
        fail(error)
        return 1
    if seeded:
        print(f"install: no config of your own yet; starting from {seeded}", file=sys.stderr)

    target = os.path.join(plugins_dir(), pid)
    if not options["layout_only"]:
        _, note, error = install_files(source, target, options["dry_run"])
        if error:
            fail(error)
            return 1
        print(f"install: {note}", file=sys.stderr)

    bar = config.get("bar")
    if not isinstance(bar, dict):
        bar = {}
        config["bar"] = bar
    layout = bar.get("layout")
    if not isinstance(layout, dict):
        layout = {}

    entries = tab_entries(pid, options["tabs"], options["scratch"])
    layout, notes = rewrite_layout(
        layout, pid, entries, options["section"], options["keep_omarchy"]
    )
    bar["layout"] = layout

    for note in notes:
        print(f"install: {note}", file=sys.stderr)

    if options["dry_run"]:
        json.dump(layout, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    had_config = os.path.exists(path)
    error = write_config(path, config)
    if error:
        fail(error)
        return 1
    print(
        f"install: wrote {path}"
        + (f" (bar as it was: {path}.bak)" if had_config else ""),
        file=sys.stderr,
    )

    if not reload_shell():
        print(
            "install: could not reach the shell — run `omarchy restart shell`",
            file=sys.stderr,
        )
    print(target)
    return 0


if __name__ == "__main__":
    sys.exit(main(["install", *sys.argv[1:]]))
