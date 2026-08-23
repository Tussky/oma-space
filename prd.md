# Oma-space — Product Requirement Document

**v0.2** · 22 Aug 2026 · revised after technical audit

---

## Why Oma-space? Two reasons

1. Oma-space was created to compete in the Omarchy plugins competition.
2. Oma-space is a handy idea originally inspired by GNOME's own window management. Hyprland is an amazing product that sorts and visualises an individual workspace, but neither it nor Omarchy brings cohesive organisation to _workspaces_ (with an s).

## The one-sentence version

**Arrange a workspace the way you like it, save it, and rebuild it on demand — and see every workspace at a glance while you work.**

Everything below serves that sentence. If a feature doesn't, it's deferred.

---

## Core principle: the workspace is the unit, not the app

**Oma-space is workspace-driven.** You choose a context; the machine assembles around you. You are never moved somewhere involuntarily.

- **Workspace-driven (this product):** you pick "Coding" → the workspace opens, the layout applies, the apps come to you.
- **App-driven (not this product):** you open an app → you get pulled to wherever that app lives, losing the thing you were doing.

Oma-space is not workspace-driven or app-driven, it is a tasteful combination of the two. Once the plugin is fully functional, most users will prefer to navigate by workspace shortcuts which right now are (Super+1, Super+2) but users may wish to switch these two other keybindings. If I want to go to my coding tab, I will do so.

However, it is important to mention that opening a new app will redirect you to the workspace that app would usually be on. This is why it is not suggested to have the same app on multiple workspaces. If the app is on multiple different workspaces, then the using the shortcut will take you nowhere.
---

## Features — v1

### F1 · Workspace preview panel

A side panel listing every workspace and the **windows** open in it — app icon, app name, window title.

Not thumbnails in v1. Live previews require per-client screencopy on Wayland, which is expensive and awkward to drive from QML. An icon-and-title list is ~90% of the usefulness at ~10% of the cost, and is arguably what you want at a glance anyway. Thumbnails are a v2 spike.

**Live state gets its own verb.** What is open right now is not a definition and never becomes one, so `oma-space live` reports it separately: every workspace and its windows, with no `exec`, `cwd` or `size` to mistake for something saved. It resolves a window's name and icon exactly as capture resolves its exec line, so a window reads identically in the panel and in a definition taken from it. Interface: `docs/live.md`.

`list --json` is the other half and stays distinct: saved definitions, whether or not anything of theirs is running. The panel eventually shows both against each other; the live half is what F6 hovers.

### F2 · Workspace definitions

A named, saved description of a working context. A definition holds:

- a name and an icon
- a layout
- a list of apps, each with an exec line, a **working directory**, and optional floating/size hints

The working directory is not a detail — it's what turns "a coding workspace" into "the coding workspace _for this project_", which is the thing worth a keybind.

JSON on disk, a `Workspace` class in memory — `omaspace/workspace.py`. Never executable `.js` — see constraint 2.

### F3 · Capture — save the current workspace

One action: **save what I have right now as a definition.**

This is the feature that makes the product stick, and it was missing from v0.1. Nobody wants to hand-author a config file describing apps they already have open. Capture reads the live state and writes the definition for them.

It's also the onboarding story (see F7) and the opening beat of the demo.

**Capture only reads.** It observes the current workspace and produces a definition. It never decides where that definition goes — the user does: new file, overwrite an existing one, or discard. So capture never reads the definition already on disk and never merges into it, which means hand-edited fields are only ever lost by an overwrite the user asked for.

Concretely, `oma-space capture <index>` writes JSON to stdout. Saving is a separate step. Interface: `docs/capture.md`.

**What capture reads.** None of these are hand-authored:

| field | source |
|---|---|
| `layout` | `workspaces -j` → `tiledLayout` — per-workspace, not the global `general:layout` |
| `matchClass` | `clients -j` → `initialClass` — the class at map time, which is what the `openwindow` event carries |
| `cwd` | the client's `pid`, via `/proc` — but **not** `/proc/<pid>/cwd`, see `docs/capture.md` |
| `floating`, `fullscreen` | `clients -j` — separate states; a fullscreen window is not merely a large one |
| `size` | client `size` ÷ usable area, stored as 0–1 fractions |
| `label` | the shallowest descendant of the window's pid worth restoring for terminals, `.desktop` `Name=` otherwise — the app name F1 renders |

**Sizes are fractions, never pixels.** Client sizes are logical pixels, so a definition captured on a 1920×1080 display at scale 1.6 would restore wrong anywhere else. Usable area is the logical monitor size minus `reserved` (the bar). Hyprland exposes no split-ratio readback, so a derived fraction is the only available signal for how the user sized a tiled window — and it is real intent worth keeping: a code window deliberately larger than the chat window beside it.

Restore applies size best-effort per layout: exact for floating, `splitratio` for dwindle, column width for scrolling.

**Terminals: capture the program and the directory, nothing more.** A terminal's class is `foot` whether it holds a shell, nvim, or Claude Code, so the class is not the app's identity. Capture walks the process tree and records the program running inside it — `nvim`, `claude` — plus the shell's `cwd`. Positional arguments are dropped: `foot -e nvim`, not `foot -e nvim capture_workspace.sh`.

**Only programs a window exists for.** A shell is usually running *something* — `uv`, `git`, a build — and none of it is why the window is open. Capture matches against a list of durable TUI programs: editors, monitors, AI agents, file and git browsers, multiplexers, and Omarchy's own TUI menu entries. Anything unlisted is descended through rather than stopped at, so an agent behind a wrapper (`uv run claude`) is still found, and a window whose command is merely in flight captures as a terminal in its directory — which is the durable half anyway.

This is the same call the paragraph below makes about nvim's file argument, applied one level up: `uv sync` finishes in seconds and restoring it would be meaningless, while the directory it ran in is still the context worth keeping. The cost is that an unlisted TUI captures as a bare terminal; capture names what it skipped on stderr, so the list is extendable from evidence rather than guesswork.

**A subcommand is sometimes the program.** A few TUIs are a mode of a command-line tool rather than a tool of their own — Omarchy ships `dua`, where the bare command aggregates and exits and only `dua interactive` opens anything. Dropping that word restores a window that closes before you see it, so capture holds the launch command for those programs rather than their name. It is a short, explicit list, not argument-keeping in general: the test is whether the word names the program or names a document.

`omarchy-launch-tui` takes its `--app-id` from the first word, so the subcommand rides along without changing the class `matchClass` has to match.

The file you had open is transient; the directory is durable, and a definition describes a context rather than a snapshot. A stale filename also fails badly — nvim silently opens an empty buffer under a name that no longer exists. Apps restore their own sessions better than we can (nvim's shada, `claude --resume`), so v1 gets you into the right directory with the right program and stops there.

**One terminal, one process — or capture abstains.** Walking the process tree needs the window's pid to own that window's shell. Two terminals break the assumption, and in opposite ways: ghostty forks the shell off a worker thread, so only reading every thread's children finds it; and ghostty's `.desktop` runs `--gtk-single-instance=true`, so several windows share one process with every shell as a sibling under it. The second case has no fix — nothing ties a shell to a window — so capture emits the bare terminal and warns, rather than guessing a directory. `footclient` against a `foot --server` behaves the same way. Details in `docs/capture.md`.

Richer interpretation of what a terminal is doing is a v2 question, not a v1 one.

**Omarchy's own TUIs identify themselves.** `omarchy-launch-tui` stamps `--app-id=org.omarchy.<program>` onto the terminal it opens, so a btop window opened from Omarchy's menu has class `org.omarchy.btop` — the program names itself, and the terminal hosting it is incidental. Capture reads the program back out of the class and records `omarchy-launch-tui <program>`, which relaunches it Omarchy's way, styling included, and reproduces the same app-id — so `matchClass` still matches the window on restore.

**Webapps: the class resolves to the launcher.** Omarchy's webapps run through `omarchy-launch-webapp <url>`, which is `chromium --app=<url>`, and chromium encodes the URL into the window class. Capture reads the host back out of the class and joins it to the installed `.desktop` entry, which supplies the app's name, its icon, and the exact relaunch command. Native apps resolve the same way through `StartupWMClass=`. Most windows therefore identify themselves from class alone; the rest need a fallback guess.

**Browser tabs are out of scope, permanently.** Hyprland reports windows, not tabs: a browser window with twelve tabs is one client with one class and one title, and that title names only the active tab. Reading the rest would mean running chromium with a remote-debugging port open to every local process, parsing undocumented session files, or shipping a browser extension. None of those are in this product.

This costs little, because a webapp is not a tab. `--app=` windows are standalone, with their own class and no tab strip, so the browser-based things worth pinning to a workspace — WhatsApp, ChatGPT, GitHub — are already captured by the mechanism above. What's left inside a general browsing window is transient, the same call made on nvim's file argument.

### F4 · Restore — rebuild a definition

Open a definition: create/switch to the workspace, apply the layout, launch every app into it with the right working directory.

### F5 · Per-workspace layout

Each definition names a layout, applied on open. Valid values: `dwindle`, `master`, `monocle`, `scrolling`.

### F6 · Entry points

A keybind and an Omarchy menu entry to pick a workspace. A bar widget showing the active workspace, and **showing what is open in it on hover** — the F1 list, for the one workspace you are on.

Hover rather than click because of what it costs to be wrong. "What is on this workspace" is a glance, asked constantly and answered in under a second; making it a click puts a decision in front of an idle question, and a panel you have to dismiss is worse than no panel. The full panel across every workspace stays a deliberate act.

**A definition hooks onto an Omarchy workspace; it does not create a new one.** Omarchy already has ten workspaces, reachable with `Super+1`…`Super+0`. Every oma-space definition maps onto one of those ten. Those binds already exist and belong to Omarchy — oma-space does not own, generate, or rewrite them.

The `shortcut` field on a definition is therefore a **reference** to the Omarchy bind that reaches this workspace, held so the panel and menu can show the user how to get there. It is descriptive, not authoritative.

This gives every workspace two entry points, and they are complementary rather than redundant: the Omarchy bind reaches it **by position** (`Super+1`), and the oma-space menu reaches the same workspace **by name** ("Coding"). Positional access is faster once memorised; access by name is what makes a saved context discoverable in the first place.

### F7 · First-run: capture, not presets

**On first run, offer to save the user's current setup as a workspace.** It's personalised, it's instantly correct, and it teaches the core mechanic in a single action. Ship at most one illustrative preset (Coding), not four speculative ones.

---

## Technical constraints

These are load-bearing. Design around them from the start.

### 1 · `exec [workspace N silent]` is unreliable

Hyprland's exec rules track spawned windows via **process environment variables**. Chromium-family browsers clear their environment for security, so the rule finds nothing and the window opens on the current workspace. Ghostty has the same problem; Firefox and Alacritty work — an inconsistency that will break a live demo.

The rules also cannot work for an **already-running** app: a new window spawned by an existing process was not spawned by our dispatch, so nothing attaches.

**Use spawn-then-claim instead:**

1. Snapshot current client addresses (`hyprctl clients -j`).
2. `hyprctl dispatch exec <cmd>`.
3. Listen on `$XDG_RUNTIME_DIR/hypr/$HYPRLAND_INSTANCE_SIGNATURE/.socket2.sock` for `openwindow>>address,workspace,class,title`.
4. Match on class, with a timeout so a failed launch doesn't hang the sequence.
5. `hyprctl dispatch movetoworkspacesilent <N>,address:0x<addr>`.

More code, but it works for every app including already-running ones.

### 2 · Plugins run unsandboxed in the shell process

QML runs in the same long-lived process as the bar, notifications and the **lock screen**. An uncaught throw is not a cosmetic bug. All parsing and process handling stays in the helper, in Python; QML only renders. This is the reason the model is not a `.js` file loaded into the shell — see Architecture.

---
---

## Lifecycle — decisions that must not stay open

Undefined lifecycle behaviour is the main reason tools in this category get uninstalled. Committing now:

| Event | Behaviour |
|---|---|
| **Open a workspace** | Switch to it, apply layout, launch only apps not already present. |
| **Open one already populated** | No-op for running apps; fill gaps only. Never duplicate. |
| **Switch away** | Apps keep running. Leaving is not closing. |
| **Close a workspace** | Explicit action only, never automatic. Offers to capture before closing. |
| **App launch fails** | Log, skip, continue the sequence. Never block the rest of the workspace. |

---

## Architecture

Three layers, two languages. QML draws; Python does everything else — the model included. Files below are the current instances of each layer, not a fixed manifest; adding a surface or a module doesn't change the architecture.

```
oma-space/
├── manifest.json          kinds: ["bar-widget", "panel", "service"]
│
├── *.qml                  render layer — one file per surface
│                            BarWidget.qml   active-workspace indicator; hover shows F1 for it
│                            Panel.qml       the side preview
│                            Service.qml     live state, subscribes to Hyprland events
│
├── oma-space              helper layer — one executable, subcommand per verb
│                            capture <index>   the workspace -> a definition, on stdout
│                            live              every workspace and its windows, on stdout
│                            restore <name>    a definition -> a live workspace
│                            list --json       every saved definition, normalised
│
└── omaspace/              the package the executable dispatches into
                             workspace.py    model — schema, defaults, validation, JSON I/O
                             capture.py      F3
                             live.py         F1
                             restore.py      F4
                             store.py        ~/.config/oma-space/workspaces I/O
```

**The model is Python, not QML JavaScript.** A `.js` model file is loaded *into* the shell process, which is the side of constraint 2 that owns the lock screen — and it would be a second implementation of the schema, drifting against the one capture and restore already need. One `workspace.py`, on the same side of the boundary as the code that produces and consumes definitions.

QML therefore never constructs a `Workspace`. It receives plain JSON over a `Process` stdout and renders it, which is why `list --json` emits definitions **normalised** — round-tripped through the model, every key present at its default — so the panel never guards against a missing field.

**One service, however many bars.** A bar surface exists per monitor, so the widget reads live state off the shared `service` instance rather than holding its own — otherwise every screen would spawn its own helper process for the same answer. Nothing is kept fresh while nobody is looking: the widget registers as a watcher when its popup opens, and only then does a Hyprland event cost a refresh.

JavaScript survives only inside `.qml` files, for presentation: formatting, small handlers, binding glue. The moment it parses helper output or touches a file, constraint 2 is back.

`oma-space` is a thin dispatcher: it resolves `omaspace/` relative to its own path and hands `argv` to the subcommand. Nothing outside the package is importable, so the plugin stays a directory you can copy.

Definitions live outside the plugin so they survive reinstalling it — one JSON file each, in `~/.config/oma-space/workspaces/`. The filename is the definition's `name`, lowercased with spaces hyphenated: `"Coding"` → `coding.json`, `"Deep Work"` → `deep-work.json`. `name` is a display string, so it is slugified rather than used raw.

Capture and restore are testable from a terminal before any QML exists, which de-risks the hard half first and keeps a parsing bug out of the process that owns the lock screen.

This also lands Oma-space in `panel` and `service` — two of the least-used plugin kinds in the Omarchy registry (54 and 198 of 872), which is free positioning against a crowded `bar-widget` field.

---

## Success criteria

The competition demo, in about ninety seconds:

1. Arrange a real workspace — editor, browser, terminal. Press capture. Name it "Coding."
2. Wipe it. Open a fresh workspace, hit the shortcut, watch it rebuild — right apps, right layout, right directories.
3. Open the side panel to show every workspace at a glance.

---

## Open questions

1. **Multi-monitor.** Definitions currently assume one output. Does a workspace remember which monitor it belonged to? Deferring, but it will come up.
