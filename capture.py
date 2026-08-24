#!/usr/bin/python3
"""Capture one Hyprland workspace as a definition.

`workspace(index)` returns a Workspace; Python callers — save, restore — take
that and never parse anything. main() is the CLI wrapper QML reads, and exists
only because QML must not do this work itself (prd.md constraint 2).

Interface and field sources:  docs/capture.md

Stdlib only — the helper layer must run on a stock Omarchy machine.
"""

import json
import os
import subprocess
import sys

from workspace import Workspace

SHELLS = {"bash", "zsh", "fish", "sh", "dash", "ksh", "tcsh", "csh", "nu", "elvish"}

# What a terminal window is *for*. Anything else a shell is running — uv, git, a
# build — is a command in flight at capture time, not the window's purpose, and
# restoring it would be as wrong as restoring nvim's file argument (prd.md F3).
# Unlisted programs aren't lost: the window captures as a terminal in its cwd.
TUI_PROGRAMS = {
    # editors
    "nvim",
    "vim",
    "vi",
    "hx",
    "helix",
    "emacs",
    "nano",
    "micro",
    "kak",
    "fresh",
    # AI agents
    "claude",
    "codex",
    "gemini",
    "aider",
    "goose",
    "opencode",
    "crush",
    "amp",
    "cursor-agent",
    "qwen",
    "copilot",
    "gptme",
    # system monitors
    "btop",
    "htop",
    "top",
    "btm",
    "bottom",
    "nvtop",
    "glances",
    "atop",
    # Omarchy's own TUI menu entries and keybinds
    "impala",
    "bluetuith",
    "wiremix",
    "cliamp",
    "lazydocker",
    "fastfetch",
    # files, git, containers
    "yazi",
    "ranger",
    "lf",
    "nnn",
    "mc",
    "lazygit",
    "tig",
    "gitui",
    "k9s",
    # disk usage — dua ships with Omarchy; dust and duf are left out on purpose,
    # they print and exit rather than opening anything
    "dua",
    "ncdu",
    "gdu",
    "diskonaut",
    # multiplexers — the session is the point, even if its panes are invisible
    "tmux",
    "zellij",
    "screen",
    # chat, mail, media
    "weechat",
    "irssi",
    "neomutt",
    "aerc",
    "newsboat",
    "ncmpcpp",
    "cmus",
}

# A couple of these are a mode of a command-line tool rather than a tool of their
# own, so the bare name restores to something that prints and exits. The
# subcommand is the program's identity here, not a document, which is the one
# reason an argument survives (prd.md F3).
TUI_COMMANDS = {"dua": "dua interactive"}

# A console script runs as `python3 /usr/bin/aider`, so the interpreter is never
# the answer — the script it was handed is.
INTERPRETERS = {"python", "python3", "node", "bun", "deno", "ruby", "perl"}

SCRIPT_SUFFIXES = (".py", ".js", ".mjs", ".cjs", ".ts", ".rb", ".pl")

# Fallback when a terminal has no .desktop entry to declare TerminalEmulator.
KNOWN_TERMINALS = {
    "foot",
    "Alacritty",
    "kitty",
    "com.mitchellh.ghostty",
    "org.wezfurlong.wezterm",
}

EXEC_FIELD_CODES = {
    "%f",
    "%F",
    "%u",
    "%U",
    "%d",
    "%D",
    "%n",
    "%N",
    "%i",
    "%c",
    "%k",
    "%v",
    "%m",
}

MAX_TREE_DEPTH = 4


# The live verb re-resolves every window on every hover, and these warnings are
# about the fidelity of a definition it never writes. It sets QUIET.
QUIET = False


def warn(msg):
    if not QUIET:
        print(f"capture: {msg}", file=sys.stderr)


# --- Hyprland ---------------------------------------------------------------


def hyprctl(*args):
    """One hyprctl -j call. --batch is not usable here: with -j it emits
    concatenated JSON documents rather than one."""
    try:
        proc = subprocess.run(
            ["hyprctl", "-j", *args], capture_output=True, text=True, timeout=10
        )
    except (OSError, subprocess.SubprocessError) as error:
        # Same shape as the failures below: this module's callers already
        # handle RuntimeError, and a None here would surface as a TypeError.
        raise RuntimeError(f"hyprctl {' '.join(args)}: {error}")
    if proc.returncode != 0:
        raise RuntimeError(f"hyprctl {' '.join(args)} failed: {proc.stderr.strip()}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"hyprctl {' '.join(args)} returned invalid JSON: {e}")


def usable_area(monitor):
    """Logical monitor size minus the reserved strip the bar occupies."""
    scale = monitor.get("scale") or 1
    left, top, right, bottom = (monitor.get("reserved") or [0, 0, 0, 0])[:4]
    width = monitor.get("width", 0) / scale - left - right
    height = monitor.get("height", 0) / scale - top - bottom
    return width, height


# --- /proc ------------------------------------------------------------------


def proc_read(pid, *parts):
    try:
        with open(os.path.join("/proc", str(pid), *parts), "rb") as f:
            return f.read()
    except OSError:
        return None


def proc_comm(pid):
    raw = proc_read(pid, "comm")
    return raw.decode(errors="replace").strip() if raw else None


def proc_cmdline(pid):
    raw = proc_read(pid, "cmdline")
    if not raw:
        return []
    return [a for a in raw.decode(errors="replace").split("\0") if a]


def proc_cwd(pid):
    try:
        return os.readlink(f"/proc/{pid}/cwd")
    except OSError:
        return None


def proc_children(pid):
    """Children of every thread, not just the main one. Ghostty forks
    the shell off a worker thread, leaving /proc/<pid>/task/<pid>/children empty."""
    try:
        tids = sorted(os.listdir(os.path.join("/proc", str(pid), "task")), key=int)
    except (OSError, ValueError):
        tids = [str(pid)]
    children, seen = [], set()
    for tid in tids:
        raw = proc_read(pid, "task", tid, "children")
        for token in raw.split() if raw else []:
            child = int(token)
            if child not in seen:
                seen.add(child)
                children.append(child)
    return children


def interpreted_name(argv):
    """The script an interpreter was handed: python3 /usr/bin/aider -> aider."""
    args = iter(argv[1:])
    for arg in args:
        if arg == "-c":
            return None  # inline code has no name to report
        if arg == "-m":
            arg = next(args, "")
        elif arg.startswith("-"):
            continue
        name = os.path.basename(arg)
        for suffix in SCRIPT_SUFFIXES:
            if name.endswith(suffix):
                name = name[: -len(suffix)]
                break
        return name or None
    return None


def tui_command(program):
    """The command that opens this program's TUI, which is not always its name."""
    return TUI_COMMANDS.get(program, program)


def program_name(pid):
    """comm is truncated at 15 chars; prefer argv[0]'s basename when it agrees."""
    comm = proc_comm(pid)
    argv = proc_cmdline(pid)
    name = comm
    if argv:
        base = os.path.basename(argv[0])
        if base and comm and base.startswith(comm):
            name = base
    if name in INTERPRETERS:
        return interpreted_name(argv) or name
    return name


def terminal_contents(pid):
    """(program, cwd) for a terminal window: the shallowest descendant worth
    restoring, and the cwd of the shell it runs under. Either may be None.

    A transient command is descended through rather than stopped at, so an agent
    behind a wrapper — `uv run claude` — is still the program the window is for."""
    cwd, ignored = None, []
    frontier = [(child, 1) for child in proc_children(pid)]
    while frontier:
        current, depth = frontier.pop(0)
        name = proc_comm(current)
        if name is None:
            continue
        program = program_name(current)
        if program in TUI_PROGRAMS:
            return program, cwd or proc_cwd(current)
        if name in SHELLS:
            if cwd is None:
                cwd = proc_cwd(current)
        elif program:
            ignored.append(program)
        if depth < MAX_TREE_DEPTH:
            frontier.extend((c, depth + 1) for c in proc_children(current))
    if ignored:
        warn(
            f"ignoring {', '.join(dict.fromkeys(ignored))}; capturing the terminal and its directory"
        )
    return None, cwd


# --- .desktop entries -------------------------------------------------------


def data_dirs():
    home = os.environ.get(
        "XDG_DATA_HOME", os.path.join(os.path.expanduser("~"), ".local", "share")
    )
    system = os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share")
    seen, dirs = set(), []
    for base in [home, *system.split(":")]:
        path = os.path.join(base, "applications")
        if base and path not in seen and os.path.isdir(path):
            seen.add(path)
            dirs.append(path)
    return dirs


def parse_desktop(path):
    """Keys of the [Desktop Entry] group only — trailing [Desktop Action *]
    groups carry their own Name and Exec and would otherwise overwrite them."""
    entry, in_group = {}, False
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if line.startswith("["):
                    if in_group:
                        break
                    in_group = line == "[Desktop Entry]"
                    continue
                if in_group and "=" in line and not line.startswith("#"):
                    key, _, value = line.partition("=")
                    entry.setdefault(key.strip(), value.strip())
    except OSError:
        return None
    return entry or None


def clean_exec(line):
    """Drop field codes; a definition relaunches an app with no document."""
    if not line:
        return ""
    return " ".join(a for a in line.split() if a not in EXEC_FIELD_CODES)


def webapp_host(exec_line):
    parts = exec_line.split()
    if len(parts) < 2 or os.path.basename(parts[0]) != "omarchy-launch-webapp":
        return None
    url = parts[1]
    host = url.split("://", 1)[-1].split("/", 1)[0]
    return host or None


def desktop_index():
    """class -> entry, plus webapp host -> entry. Earlier data dirs win, so a
    user override shadows the system copy."""
    by_class, by_host = {}, {}
    for directory in data_dirs():
        try:
            names = sorted(os.listdir(directory))
        except OSError:
            continue
        for name in names:
            if not name.endswith(".desktop"):
                continue
            entry = parse_desktop(os.path.join(directory, name))
            if not entry:
                continue
            wm_class = entry.get("StartupWMClass")
            if wm_class:
                by_class.setdefault(wm_class, entry)
            host = webapp_host(entry.get("Exec", ""))
            if host:
                by_host.setdefault(host, entry)
    return by_class, by_host


# omarchy-launch-tui stamps --app-id=org.omarchy.<program> onto the terminal it
# opens, so the class names the program and the terminal itself is incidental.
OMARCHY_APP_ID = "org.omarchy."


def omarchy_program(cls):
    """org.omarchy.btop -> btop. A custom --app-id is indistinguishable from any
    other class, so only Omarchy's own default is recognised."""
    if not cls.startswith(OMARCHY_APP_ID):
        return None
    return cls[len(OMARCHY_APP_ID) :] or None


def class_host(cls):
    """chrome-<host>__<path>-<Profile> -> host. Split on __, not the last
    hyphen: hosts, paths and profile names all contain hyphens."""
    if not cls.startswith("chrome-"):
        return None
    host = cls[len("chrome-") :].split("__", 1)[0]
    return host or None


# --- resolution -------------------------------------------------------------


def is_terminal(cls, entry):
    if entry:
        categories = entry.get("Categories", "")
        if "TerminalEmulator" in categories.split(";"):
            return True
    return cls in KNOWN_TERMINALS


def resolve(client, by_class, by_host, shared_pids=frozenset()):
    """(exec, label, cwd) for one window."""
    cls = client.get("initialClass") or client.get("class") or ""
    pid = client.get("pid") or 0
    entry = by_class.get(cls)

    program = omarchy_program(cls)
    if program:
        # Relaunching the same way reproduces this app-id, so matchClass still
        # matches on restore — which spawn-then-claim depends on (prd.md 1).
        _, cwd = terminal_contents(pid) if pid not in shared_pids else (None, None)
        # The launcher takes its app-id from the first word, so a subcommand
        # after it does not change the class matchClass has to match.
        return f"omarchy-launch-tui {tui_command(program)}", program, cwd

    if is_terminal(cls, entry):
        base = clean_exec(entry.get("Exec")) if entry else cls
        if pid in shared_pids:
            # Every window's shell is a sibling under the one process,
            # with nothing tying one to this window. A guess misfiles the cwd.
            warn(
                f"{cls} serves several windows from pid {pid}; capturing the terminal only"
            )
            return base, (entry or {}).get("Name", cls), None
        program, cwd = terminal_contents(pid)
        if program:
            arg = (entry or {}).get("X-TerminalArgExec", "-e")
            return f"{base} {arg} {tui_command(program)}", program, cwd
        # A plain shell: the terminal itself is the app. prd.md F3 keeps the
        # directory, which is the durable half.
        return base, (entry or {}).get("Name", cls), cwd

    host = class_host(cls)
    if host:
        # Chromium windows share one pid and one cmdline, so the class
        # is the only route back to the app.
        entry = by_host.get(host)
        if entry:
            return clean_exec(entry.get("Exec")), entry.get("Name", host), None
        warn(f"no webapp entry for host {host}; reconstructing from class")
        return f"omarchy-launch-webapp https://{host}/", host, None

    if entry:
        return clean_exec(entry.get("Exec")), entry.get("Name", cls), None

    argv = proc_cmdline(pid)
    if argv:
        warn(f"no .desktop entry for class {cls!r}; falling back to cmdline")
        return argv[0], cls, None

    warn(f"could not resolve class {cls!r}; emitting partial entry")
    return cls, cls, None


def app_size(client, monitors):
    monitor = monitors.get(client.get("monitor"))
    if not monitor:
        return None
    width, height = usable_area(monitor)
    size = client.get("size") or []
    if width <= 0 or height <= 0 or len(size) != 2:
        return None
    # A fullscreen window covers the reserved strip too, so the raw ratio can
    # exceed 1. The contract requires fractions in (0, 1].
    return [
        round(min(1.0, max(size[0] / width, 0.0001)), 4),
        round(min(1.0, max(size[1] / height, 0.0001)), 4),
    ]


# --- capture ----------------------------------------------------------------


def _definition(index):
    # One snapshot: re-reading mid-run would describe a state that never existed.
    clients = hyprctl("clients")
    workspaces = hyprctl("workspaces")
    monitors = hyprctl("monitors")

    target = next((w for w in workspaces if w.get("id") == index), None)
    if target is None:
        raise RuntimeError(f"workspace {index} does not exist or holds no windows")

    monitors_by_id = {m.get("id"): m for m in monitors}
    by_class, by_host = desktop_index()

    # Across every workspace: a daemon terminal's other windows are just as
    # ambiguous whether or not they sit on the one being captured.
    counts = {}
    for c in clients:
        counts[c.get("pid")] = counts.get(c.get("pid"), 0) + 1
    shared_pids = frozenset(pid for pid, n in counts.items() if pid and n > 1)

    apps = []
    for client in clients:
        if (client.get("workspace") or {}).get("id") != index:
            continue
        exec_line, label, cwd = resolve(client, by_class, by_host, shared_pids)
        apps.append(
            {
                "exec": exec_line,
                "matchClass": client.get("initialClass") or client.get("class") or "",
                "label": label or "",
                "cwd": cwd,
                "floating": bool(client.get("floating")),
                # The source is an int, not a bool.
                "fullscreen": client.get("fullscreen", 0) != 0,
                "size": app_size(client, monitors_by_id),
            }
        )

    return {
        "index": index,
        "name": "",
        "icon": "",
        "layout": target.get("tiledLayout") or "",
        "apps": apps,
    }


def workspace(index, name=None, icon=None):
    """The workspace as a Workspace — what every Python caller wants.

    Validation is the caller's, not ours: an unnamed capture is unfinished by
    design (prd.md F3), so a fresh one fails validate() with exactly
    ["workspace has no name"] until a name is supplied here or at save time.
    """
    definition, _ = Workspace.from_capture(_definition(index), name=name, icon=icon)
    return definition


def main(argv):
    if len(argv) != 2:
        print(f"usage: {os.path.basename(argv[0])} <workspace-index>", file=sys.stderr)
        return 2
    try:
        index = int(argv[1])
    except ValueError:
        warn(f"workspace index must be an integer, got {argv[1]!r}")
        return 2

    try:
        definition = workspace(index)
    except RuntimeError as e:
        warn(str(e))
        return 1

    # Single line: safe for both StdioCollector and Service.qml's SplitParser.
    json.dump(definition.to_json(), sys.stdout, separators=(",", ":"))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
