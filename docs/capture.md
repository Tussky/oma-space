# capture

`./capture.py <workspace-index>` — one workspace, as a definition on stdout.
Rationale lives in prd.md F3; this is the interface and the field sources.

## Contract

- One JSON object on **stdout**, single line. Nothing else on stdout, ever.
- Diagnostics to **stderr**. Exit `0`, or non-zero if the workspace can't be read.
- A window it cannot fully resolve is still emitted, unknown fields at their
  defaults. Skipping windows silently is worse than emitting partial ones.
- `name` is always `""` — the user supplies it at save time, so a correct capture
  fails validation with exactly `["workspace has no name"]`.

Single-line matters: `Service.qml` reads stdout with `SplitParser`, which fires per
line, so a pretty-printed document would reach `JSON.parse` as fragments — inside
the process that owns the lock screen.

```json
{"index":1,"name":"","icon":"","layout":"scrolling","apps":[
  {"exec":"foot -e nvim","matchClass":"foot","label":"nvim",
   "cwd":"/home/teapot/Projects/oma-space","floating":false,
   "fullscreen":false,"size":[0.47,0.96]}]}
```

Keys are read by name and fall back to a default when missing, so a typo does not
error — `"matchclass"` yields an empty `matchClass`, `"Size"` loses the sizing with
no error at all. Copy the names from the table.

## Field sources

| field | source |
|---|---|
| `index` | `clients[].workspace.id` |
| `layout` | `workspaces[].tiledLayout` — per-workspace, **not** `general:layout` |
| `matchClass` | `clients[].initialClass` — the class at map time, which is what `openwindow` carries |
| `exec` | `.desktop` `Exec=`, `omarchy-launch-tui <program>` for Omarchy TUIs, else `/proc/<pid>/cmdline` |
| `label` | the program inside a terminal, else `.desktop` `Name=` |
| `cwd` | the shell child's cwd — **not** `/proc/<pid>/cwd` |
| `floating` | `clients[].floating` |
| `fullscreen` | `clients[].fullscreen` — an **int**, `0` means no |
| `size` | `clients[].size` ÷ usable area, as fractions in `(0, 1]` |

Usable area is the logical monitor size (`width / scale`) minus `reserved`:
`1920x1080 scale=1.6 reserved=[0,26,0,0]` → `1200 x 649`.

## What bites — all verified on Hyprland 0.56.2

**Terminals don't report their own cwd.** Foot reports `/`. Read the cwd of its
shell child instead. The `--working-directory` flag in cmdline is where the
terminal *started*, not where the user has since `cd`'d.

**A terminal's class is not its app.** Every foot window is class `foot`. The
process tree separates them, and only durable programs count — a shell is usually
running *something* (`uv`, `git`, a build) that isn't why the window is open.
`TUI_PROGRAMS` in capture.py is that list; unlisted programs are descended through,
so `uv run claude` still resolves to `claude`.

**Some TUIs need their subcommand.** Bare `dua` aggregates and exits; `dua interactive`
is the TUI. `TUI_COMMANDS` maps the few programs whose name alone would restore a
window that closes immediately, and applies to both launch paths — `foot -e dua
interactive` and `omarchy-launch-tui dua interactive`. The launcher reads its app-id
from the first word, so the class is still `org.omarchy.dua`. Everything else keeps
the rule that arguments are dropped; `dust` and `duf` are deliberately absent from
`TUI_PROGRAMS` because they print and exit no matter what you pass them.

**Omarchy TUIs wear their own class.** `omarchy-launch-tui btop` runs
`foot --app-id=org.omarchy.btop -e btop`, so the window's class is `org.omarchy.btop`
rather than the terminal's — no `.desktop` entry matches it, and every other lookup
falls through to the terminal's cmdline. Read the program back out of the class and
relaunch the same way: that reproduces the app-id, so `matchClass` still matches on
restore. `omarchy-launch-editor` takes the same path (`org.omarchy.nvim`). A custom
`--app-id` is indistinguishable from any other class.

**A program with file capabilities hides its cwd.** btop ships
`cap_dac_read_search,cap_perfmon`, which clears the process's dumpable flag and makes
`/proc/<pid>/cwd` root-only. The field comes back null; nothing to be done.

**Read every thread's children.** `/proc/<pid>/task/<pid>/children` covers one
thread. Foot forks its shell from the main thread, ghostty from a worker — so
ghostty's main-thread list is empty and the window resolves to a bare terminal.
Union `/proc/<pid>/task/*/children`.

**One pid can own several windows, and then per-window state is unknowable.**
Chromium shares a process across windows; so does `ghostty --gtk-single-instance`
(its `.desktop` sets it) and `footclient` against `foot --server`. Every window's
shell hangs off the one process as a sibling with nothing tying it to a window, so
capture emits the bare terminal and warns rather than guessing a directory.

**cmdline is not a relaunch command for shared-process apps.** The WhatsApp
window's cmdline is the whole chromium invocation. Resolve the `.desktop` entry by
class instead: native apps via `StartupWMClass=`, Omarchy webapps via the host
chromium encodes into the class — `chrome-<host>__<path>-<Profile>`, split on `__`,
since hosts, paths and profile names all contain hyphens.

**Browser tabs are invisible, permanently.** Hyprland reports windows, not tabs.
This costs little: `--app=` webapps are standalone windows with their own class.

## Checks

```bash
./capture.py 1 | jq -e . >/dev/null                       # valid, single JSON doc
./capture.py 1 | jq -e '[.apps[].size|select(.!=null)|.[]] | all(.>0 and .<=1)'
./capture.py 1 | jq -e '.apps | all(.exec!="" and .matchClass!="" and .label!="")'
test "$(./capture.py 1 | wc -l)" = 1                      # SplitParser needs one line
```
