# Oma-space — Product Requirement Document

**v0.3** · 23 Aug 2026 · the bar widget becomes the workspace strip (F6)

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

Every workspace and the **windows** open in it — app icon, app name, window title. One workspace's worth of that list is what a bar tab shows on hover (F6), and the tab's panel lists all ten with what each holds. A dedicated side panel is deferred: with a tab per workspace, the strip *is* the map, and the surface that was going to hold it would duplicate the panel that already exists.

Not thumbnails in v1. Live previews require per-client screencopy on Wayland, which is expensive and awkward to drive from QML. An icon-and-title list is ~90% of the usefulness at ~10% of the cost, and is arguably what you want at a glance anyway. Thumbnails are a v2 spike.

**Live state gets its own verb.** What is open right now is not a definition and never becomes one, so `oma-space live` reports it separately: every workspace and its windows, with no `exec`, `cwd` or `size` to mistake for something saved. It resolves a window's name and icon exactly as capture resolves its exec line, so a window reads identically in the panel and in a definition taken from it. Interface: `docs/live.md`.

`list --json` is the other half and stays distinct: all ten workspaces and what is saved for each, whether or not anything of theirs is running. Ten entries always — an empty slot is a workspace nobody has saved yet, not a missing record, so the panel renders a map of the ten rather than a list of however many exist. The live half is what a workspace tab hovers (F6), one workspace at a time; the saved half is what its panel opens.

### F2 · Workspace definitions

A named, saved description of a working context. A definition holds:

- the workspace it belongs to — one of Omarchy's ten, and its identity
- a name and an icon, both labels — the icon from the fifteen the panel offers (F6), or any string if hand-edited
- a layout
- a list of apps, each with an exec line, a **working directory**, and optional floating/size hints

The working directory is not a detail — it's what turns "a coding workspace" into "the coding workspace _for this project_", which is the thing worth a keybind.

JSON on disk, a `Workspace` class in memory — `workspace.py`. Never executable `.js` — see constraint 2.

**A definition can be deleted, and deleting it is not closing anything.** `oma-space delete <index>` empties the slot; the workspace keeps every window open on it. The two are worth separating precisely because the plugin's whole subject is the description of a workspace rather than the workspace itself — throwing away a saved arrangement you no longer want should never be a reason to lose the windows you are using. Interface: `docs/delete.md`.

A slot is emptied, never removed: the store is the ten workspaces, so a deleted definition leaves workspace N with no configuration rather than leaving a gap where N used to be. Deleting twice is the same as deleting once.

In the panel it is asked for twice — the button becomes `Delete?` and the status line says what goes and what stays. The same shape as replacing an existing definition, and for the same reason: a destructive write is a thing the user says, not a thing a dialog asks.

### F3 · Capture — save the current workspace

One action: **save what I have right now as a definition.**

This is the feature that makes the product stick, and it was missing from v0.1. Nobody wants to hand-author a config file describing apps they already have open. Capture reads the live state and writes the definition for them.

It's also the onboarding story (see F7) and the opening beat of the demo.

**Capture only reads.** It observes the current workspace and produces a definition. It never decides where that definition goes — the user does: new file, overwrite an existing one, or discard. So capture never reads the definition already on disk and never merges into it, which means hand-edited fields are only ever lost by an overwrite the user asked for.

Changing a definition's *labels* is not this verb's business: `oma-space edit` renames and re-icons in place, so a name is never a reason to re-read a workspace (F6).

Concretely, `oma-space capture <index>` writes JSON to stdout, and `oma-space save <name>` is the step that puts it on disk — under a filename derived from the name, refusing to overwrite an existing definition unless the user says so. The definition can be piped straight from capture or reviewed in between; both are the same command.

Inside Python nothing is piped and nothing is parsed twice: `capture.workspace(index)` returns the `Workspace` that save validates and restore will read. Serialisation happens once, at the process boundary QML reads, because QML is the one caller that cannot import a module (constraint 2). Interfaces: `docs/capture.md`, `docs/save.md`.

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

`oma-space restore <name>` does this, filling gaps rather than duplicating: an app already on the workspace is left alone, and the count decides, so a definition holding two terminals against one already open launches one more. Interface: `docs/restore.md`.

**Arriving on an empty workspace fills it.** You pick a context and the machine assembles around you — the core principle, made automatic. The trigger is *focus*, not the tab, so Omarchy's own `Super+N` gets the behaviour without oma-space owning the bind (F6), and so does anything else that switches workspaces.

Three conditions, all of them necessary: the workspace holds no windows, it has a definition, and that definition has apps in it. A workspace with anything at all in it is left alone — arriving is not asking for gaps to be filled, and the deliberate gap-fill is still `oma-space open` and the panel's Open button. It is attempted once per arrival: a definition whose apps fail to launch leaves the workspace empty, and retrying that on every settle would be worse than not trying at all.

The store is re-read on arrival rather than trusted from startup, because a definition saved from a terminal since startup is exactly the one you are about to walk into. Only the service the shell mounted does this; a tab that fell back to a service of its own would otherwise restore the same workspace once per tab.

It is on by default and has no setting yet. That is a deliberate omission rather than an oversight — a workspace that fills itself is the product's sentence, and a switch for it is worth adding when someone wants it off, not before.

**Tiled sizes are not restored yet.** A floating window gets its exact size back; a tiled one is placed by the layout, because Hyprland takes no absolute size for a tiled window — dwindle wants a `splitratio` against its parent node, scrolling a column width. The fraction is captured and kept, so this is a gap in restore rather than in the definition; restore says on stderr when it skipped one.

### F5 · Per-workspace layout

Each definition names a layout, applied on open. Valid values: `dwindle`, `master`, `monocle`, `scrolling`.

Applied as a workspace rule evaluated live — `hl.workspace_rule({ workspace = "1", layout = "dwindle" })`. Omarchy's own layout toggle persists its choice into `~/.local/state/omarchy/workspace-layouts/`; oma-space does not write there. That state belongs to Omarchy exactly as its keybinds do (F6), so restore sets the layout for the session it is restoring into and leaves the file alone.

### F6 · Entry points — the workspace strip

**Oma-space takes the workspace strip over.** The bar widget is not an indicator standing beside Omarchy's workspace numbers; it *is* the numbers. Each instance is one workspace — click it to go there, hover it to see what that workspace is called and what is open in it. Ten of them make the strip, and `omarchy.workspaces` comes off the bar.

Hover rather than click because of what it costs to be wrong. "What is on that workspace" is a glance, asked constantly and answered in under a second; making it a click puts a decision in front of an idle question, and a panel you have to dismiss is worse than no panel. It is also the question the strip it replaces cannot answer at all: Omarchy's numbers say which workspaces exist and which one you are on, never what is in them.

**Click is navigation; the tab itself launches nothing.** It focuses the workspace, the same `hl.dsp.focus` call `omarchy.workspaces` makes. What may follow is not the click's doing: arriving on an empty workspace that has something saved fills it (F4), and that is true however you arrived — by tab, by `Super+N`, or from a script. The tab has no second gesture that writes, so the strip stays something you can use absent-mindedly.

**Where you are is said twice.** Omarchy marks the focused workspace by swapping its number for a glyph, which an icon has already taken the place of — so the focused tab is drawn in the bar's accent colour and underlined. A strip whose tabs come and go has to answer "where am I" without being counted along.

**One widget instance per workspace, not one widget drawing ten.** `allowMultiple` is true and each instance carries its own `index`, so the strip is assembled in the bar layout like everything else on the bar: dragged into order, spaced, split around another widget, and configured per tab in Omarchy's own settings — which tab shows a name instead of a number, which one stays put when its workspace empties. A single widget owning ten pills would own that arrangement too, and none of it would be reachable from the bar's own gestures.

**Tabs come and go with the work.** A tab is on the bar while its workspace holds windows or is focused; when the last window closes and you leave, it collapses out of the strip. The rule has no exceptions — an empty workspace is not on the bar — so `pinned` is the one way to keep a tab standing, and it is per tab and off by default. The strip is therefore a picture of what is actually going on rather than ten permanent numbers — and a saved workspace that is not running is reached by its Omarchy bind or from the panel, not from a placeholder standing in for it.

**One tab holds no configuration at all: the scratch tab.** It is pinned to workspace 10 and refuses to be saved. It comes and goes like every other tab: an empty workspace is off the bar whether or not it is the scratch one, because a permanent slot for a workspace with nothing in it is the placeholder this strip exists to avoid. `pinned` brings it back for anyone who wants it standing there. Every other tab is somewhere you have arranged; the scratch tab is where the thing you have *not* arranged goes, so an experiment never grows a definition by accident and never has to be cleaned out of one.

**Both writes live behind a button in the hover card.** The card carries `Open <name>` for a workspace that has something saved, and a button that opens the panel: a field to name what is on this workspace and save it, and the saved definitions, each one click from being rebuilt. Capture, name, open again — the demo's ninety seconds, on the bar. The panel opens on the workspace whose tab you came from, and edits any of the ten from there (below).

**Fifteen icons, so a tab can be read without being read.** A definition carries an icon, and until now nothing could set one — the field existed and no surface wrote to it. The capture panel offers fifteen: Code, Terminal, Chat, Web, Mail, Writing, Notes, Reading, Design, Music, Video, Games, Files, System, Agents. Clicking the chosen one again takes it off, so "no icon" needs no cell of its own.

**The tab wears it instead of its number.** That is the default, because a number on a bar says only where a workspace sits in a row you already know the order of, while an icon says what it is for. The number is the fallback, not the norm: a workspace with nothing saved has nothing to draw, so it shows its number until it does.

They are the archetypes people actually name workspaces after, not a palette: the point is that a strip of icons is scannable at a glance where a strip of names is not, and a workspace you can recognise by shape is one you stop reading. Material Design glyphs, which every Nerd Font patch carries — and a fixed set in the render layer rather than a picker over the whole font, because a font browser is a different product. `icon` on a definition stays any string, so an editor or `save --icon` is not held to the fifteen.

**Install is a verb, because Omarchy has no hook for one.** `omarchy plugin add` clones a directory and stops; nothing runs afterwards, so a plugin cannot place itself. `oma-space install` is that step made explicit: it puts the directory in `~/.config/omarchy/plugins/`, takes `omarchy.workspaces` out of the bar layout, and stands the tabs at its exact position in its section, so nothing else on the bar moves. Idempotent, backed up, and atomic — it is rewriting the user's whole bar, and the failure mode of getting that wrong is a shell with no bar at all. Interface: `docs/install.md`.

It also replaces a development symlink with a real directory. That is not tidiness: the shell's own validator refuses a plugin folder containing symlinks, and the watcher behind live reload is `inotifywait -r`, which does not follow one — so a symlinked checkout is both unpublishable and unreloadable.

The two surfaces are split by what a hover card *can* be, not by taste. A hover card is a passive overlay with no focus grab — pointer events reach it, keystrokes never do — so a name could not be typed into one. The panel takes keyboard focus, which is also why it cannot be the thing that opens on hover: a glance that steals focus from what you were typing is worse than no glance. Hover keeps the glance, a button gets the keyboard.

**Any tab edits any workspace.** A tab is only on the bar while its workspace is running, so the workspaces most in need of a name — the empty ones, the ones you have not arranged yet — are exactly the ones with no tab to hover. Editing is therefore addressed by *subject*, not by tab: the panel opens on the workspace whose tab you came from, and every one of the ten is one click away in the list below it. Nothing is reachable only from a particular tab, and nothing has to be reached through the scratch tab.

**Renaming is not capturing, and the panel says which is which.** `save` replaces a definition with what is open right now; that is the point of it, and it is the wrong thing to do to a workspace whose name you are only correcting — an empty one would come back with no apps. So labels get their own verb, `oma-space edit`, which loads the definition and changes two fields. The panel's button is named for what it does to the apps on disk: **Capture** for a workspace with nothing saved, **Save** for the name and icon alone, **Re-capture** for the deliberate act of throwing the old apps away. Interface: `docs/edit.md`.

**Right-click a tab to open its panel.** Hover-then-click is the discoverable path; a right-click is the one you use once you know where you are going. Left click stays navigation and nothing else.

**And the panel answers to the shell.** A bar widget is only treated as owning a panel if it exposes `open()`, `close()` and `opened`, so it does: `omarchy-shell shell toggle io.github.tussky.oma-space` opens it from a keybind or a script, `togglePanelAt` reaches it by bar position, and Omarchy's arrow navigation moves between it and the panels beside it. The panel itself is built the first time it opens — ten tabs each holding a panel window from startup is a cost for something most of them never show.

**Rebuilt rather than hijacked.** Bar widgets register under their manifest id, and `omarchy.workspaces` is a first-party manifest inside `/usr/share/omarchy/shell`. A plugin claiming that id would clobber Omarchy's widget by scan order — nondeterministically, and for every bar on the machine. So the takeover is by placement, not by name: oma-space's tabs go into the bar layout and Omarchy's widget comes out of it.

**A definition hooks onto an Omarchy workspace; it does not create a new one.** Omarchy already has ten workspaces, reachable with `Super+1`…`Super+0`. Every oma-space definition maps onto one of those ten. Those binds already exist and belong to Omarchy — oma-space does not own, generate, or rewrite them.

**And onto exactly one, from exactly one.** A workspace holds one configuration or none. Two things called "Coding" and "Writing" both claiming `Super+3` would make the bind mean two things, which is the one thing a positional entry point cannot survive — so the store is shaped to make it impossible rather than checked for it afterwards (see Architecture). Everything downstream is addressed by index because of it: `restore 3` needs no disambiguation, and the panel is a map of the ten rather than a list.

**One bind of its own: fill this workspace.** `oma-space open` rebuilds whatever was saved for the workspace you are standing on — restore addressed by index, so a single key serves all ten. It fills gaps rather than requiring an empty workspace, because the press is deliberate, and it duplicates nothing, so a second press does nothing. Suggested rather than shipped: `SUPER+R` is a line the user adds to their own `bindings.lua`, and Omarchy's ten stay Omarchy's. Interface: `docs/open.md`.

The gesture this replaces is pressing `Super+3` a second time, which is the one everybody reaches for and is not available: re-focusing the workspace you are already on emits **no** `workspace` event, so nothing outside the keymap can see the second press. Having it would mean owning `Super+1`…`0` — the whole of what the paragraph above rules out — to buy a keystroke that a key of its own already provides.

The `shortcut` field on a definition is therefore a **reference** to the Omarchy bind that reaches this workspace, held so the panel and menu can show the user how to get there. It is descriptive, not authoritative.

This gives every workspace two entry points, and they are complementary rather than redundant: the Omarchy bind reaches it **by position** (`Super+1`), and the oma-space menu reaches the same workspace **by name** ("Coding"). Positional access is faster once memorised; access by name is what makes a saved context discoverable in the first place.

### F7 · First-run: capture, not presets

**No presets, and no automatic first capture.** The onboarding is the install itself: `oma-space install` finishes by saying nothing is saved yet and where to start, and the panel's list of ten shows nine empty rows the moment it opens — the empty state teaches the mechanic without writing anything on the user's behalf.

The offer-to-capture-on-first-run flow from v0.1 is **deferred**: capture is one click from every tab already, and a plugin that writes to the store before being asked is the wrong first impression. Presets stay out for the reason they always were — a workspace is personal, and a speculative "Coding" that opens the wrong editor in the wrong directory is worse than an empty slot.

---

## Technical constraints

These are load-bearing. Design around them from the start.

### 1 · `exec [workspace N silent]` is unreliable

Hyprland's exec rules track spawned windows via **process environment variables**. Chromium-family browsers clear their environment for security, so the rule finds nothing and the window opens on the current workspace. Ghostty has the same problem; Firefox and Alacritty work — an inconsistency that will break a live demo.

The rules also cannot work for an **already-running** app: a new window spawned by an existing process was not spawned by our dispatch, so nothing attaches.

**Use spawn-then-claim instead:**

1. Subscribe to `$XDG_RUNTIME_DIR/hypr/$HYPRLAND_INSTANCE_SIGNATURE/.socket2.sock` **before** launching. Subscribing afterwards races the window: a fast app maps before the subscription lands.
2. Launch the app — **ourselves**, not through Hyprland. `hl.dsp.exec_cmd` exists, but it takes a command string and nothing else: no working directory. A definition exists for its `cwd`; routing the launch through the compositor would throw it away.
3. Read `openwindow>>address,workspace,class,title` until the class matches `matchClass`.
4. Match with a timeout, so a failed launch doesn't hang the sequence.
5. Move that address onto the workspace, silently.

More code, but it works for every app including already-running ones.

**The dispatcher names above are gone.** Hyprland 0.56 parses a Lua API and nothing else: `hyprctl dispatch workspace 1`, `movetoworkspacesilent` and `hyprctl keyword` all fail on a current Omarchy machine. The calls that replace them — and the traps in them, starting with `ok` being no evidence a call did anything — are in `docs/restore.md`. Omarchy's own scripts drive it the same way, which is where the shapes were read from.

### 2 · Plugins run unsandboxed in the shell process

QML runs in the same long-lived process as the bar, notifications and the **lock screen**. An uncaught throw is not a cosmetic bug. All parsing and process handling stays in the helper, in Python; QML only renders. This is the reason the model is not a `.js` file loaded into the shell — see Architecture.

---
---

## Lifecycle — decisions that must not stay open

Undefined lifecycle behaviour is the main reason tools in this category get uninstalled. Committing now:

| Event | Behaviour |
|---|---|
| **Open a workspace** | Switch to it, apply layout, launch only apps not already present. |
| **Arrive on an empty one** | It has a definition with apps: restore it, once. Anything already open means it is left alone. |
| **Open one already populated** | No-op for running apps; fill gaps only. Never duplicate. |
| **Switch away** | Apps keep running. Leaving is not closing. |
| **Close a workspace** | Explicit action only, never automatic. Offers to capture before closing. |
| **App launch fails** | Log, skip, continue the sequence. Never block the rest of the workspace. |

---

## Architecture

Three layers, two languages. QML draws; Python does everything else — the model included. Files below are the current instances of each layer, not a fixed manifest; adding a surface or a module doesn't change the architecture.

```
oma-space/
├── manifest.json          kinds: ["bar-widget", "service"]
│                          the bar widget is allowMultiple — one instance per workspace
│
├── *.qml                  render layer — one file per surface
│                            BarWidget.qml   one workspace on the bar; hover shows F1 for it
│                            Service.qml     live state, subscribes to Hyprland events
│
├── oma-space              helper layer — one executable, subcommand per verb
│                            capture <index>   the workspace -> a definition, on stdout
│                            save <name>       a definition -> ~/.config/oma-space/workspaces
│                            edit <index>      a definition's name and icon, in place
│                            delete <index>    empty a workspace's slot
│                            live              every workspace and its windows, on stdout
│                            restore <index>   a workspace -> whatever is saved for it
│                            open [index]      the same, defaulting to where you are
│                            list [--json]     all ten workspaces, normalised
│                            install           the tabs onto the bar, in Omarchy's place
│
└── *.py                   the modules the executable dispatches into
                             workspace.py    model — schema, defaults, validation, JSON I/O
                             capture.py      F3 — reads; returns a Workspace
                             save.py         F3 — writes; the step capture leaves to the user
                             edit.py         F6 — labels only; the write that is not a capture
                             delete.py       F2 — empties a slot; the workspace is untouched
                             live.py         F1 — what is open now
                             list.py         F1 — what is saved
                             restore.py      F4
                             open.py         F4 by index — what the keybind runs
                             store.py        the ten slots in ~/.config/oma-space/workspaces
                             install.py      F6 — the tabs onto the bar; rewrites shell.json
                             uninstall.py    F6 — the tabs off it, and Omarchy's strip back
```

**The model is Python, not QML JavaScript.** A `.js` model file is loaded *into* the shell process, which is the side of constraint 2 that owns the lock screen — and it would be a second implementation of the schema, drifting against the one capture and restore already need. One `workspace.py`, on the same side of the boundary as the code that produces and consumes definitions — and the verbs hand each other that object rather than JSON, so a definition is parsed at most once on its way to disk.

QML therefore never constructs a `Workspace`. It receives plain JSON over a `Process` stdout and renders it, which is why `list --json` emits definitions **normalised** — round-tripped through the model, every key present at its default — so the panel never guards against a missing field.

**One service, however many tabs.** A bar surface exists per monitor and a tab per workspace, so a tab reads live state off the shared `service` instance rather than holding its own — otherwise ten tabs on two screens would be twenty helper processes answering the same question. Nothing is kept fresh while nobody is looking: the widget registers as a watcher when its popup opens, and only then does a Hyprland event cost a refresh.

JavaScript survives only inside `.qml` files, for presentation: formatting, small handlers, binding glue. The moment it parses helper output or touches a file, constraint 2 is back.

`oma-space` is a thin dispatcher: it puts its own directory on `sys.path` and hands `argv` to the subcommand, importing one module per verb so a verb that fails to import cannot take the others down. Flat rather than a package, because the plugin directory *is* the unit Omarchy installs — a package folder inside it would be a second nesting for no gain. It also turns off bytecode writing: the plugin lives under the user's config, and a `__pycache__` appearing there on every bar refresh is litter.

**Two kinds of configuration, on two sides of the boundary.** What a *tab* is — which workspace it points at, what it draws, whether it stays on the bar when that workspace empties — is bar layout, and lives in its `shell.json` entry beside every other widget's settings. What a *workspace* is — name, icon, layout, apps — is a definition, and lives in the store. Neither file knows about the other: a tab with no definition behind it is a plain number that still navigates, and a definition with no tab on the bar is still reachable by its Omarchy bind and from any tab's panel.

Definitions live outside the plugin so they survive reinstalling it, in `~/.config/oma-space/workspaces/`. **The store is the ten workspaces**: slot N is `N.json`, occupied or empty. Saving fills a slot; it never adds one.

A workspace has one configuration or none, so the workspace is the identity and a second configuration for the same workspace is unrepresentable rather than merely discouraged. `name` is a label: renaming a workspace moves no file, two slots may carry the same name, and nothing is ever looked up by one. A hand-edited `index` that disagrees with its filename loses to the filename, which is the only way the invariant can be attacked once the shape enforces it.

Capture and restore are testable from a terminal before any QML exists, which de-risks the hard half first and keeps a parsing bug out of the process that owns the lock screen.

It also lands Oma-space in `service`, one of the least-used plugin kinds in the Omarchy registry — a shared, long-lived reader is the right shape for state ten tabs and a panel all render, and it happens to be uncommon.

**No `panel` kind.** A dedicated side surface was declared before it was written, and declaring it cost more than the stub was worth: the shell treats any plugin carrying `panel`, `overlay` or `menu` as owned by the panel loader, which takes the bar widget out of `summon`'s reach. Dropping the kind is what makes `omarchy-shell shell toggle <id>` open the real panel. The all-ten view lives in the tab's own panel (F6); a separate side surface is a v2 question.

---

## Licensing

GPL-3.0-or-later. Copyleft rather than permissive: this is a plugin people are meant to read, copy and adapt — the architecture is half the point of it — and the licence that keeps adaptations readable is the one that matches. Omarchy itself is MIT, which is not a conflict: oma-space is distributed on its own and loaded by the shell, not merged into it.

## Success criteria

The competition demo, in about ninety seconds:

1. Arrange a real workspace — editor, browser, terminal. Right-click its tab, name it "Coding", give it the code icon. The tab stops being a number.
2. Close everything on it. The tab leaves the bar. Press `Super+3` and watch the workspace rebuild itself — right apps, right directories, right layout — without another keystroke.
3. Walk the strip: every tab says what is open in the workspace under the cursor, and the one you are on is the one that is lit.

---

## Known limits

**Multi-monitor is single-output in v1, and says so.** Definitions record no output, and the focused mark comes from `Hyprland.focusedWorkspace`, which is global — so on a second monitor every strip marks the same tab, whichever screen it is on. Restore puts a workspace's apps wherever that workspace currently lives. This is stated in the README rather than left to be discovered.

**Tiled sizes are captured but not restored** (F4). The fraction is on disk; Hyprland takes no absolute size for a tiled window, and restore says on stderr when it skipped one.

**Browser tabs are out of scope, permanently** (F3).

## Open questions

1. **Multi-monitor.** Does a workspace remember which output it belonged to, and should a strip show only its own screen's workspaces? Both are v2 questions.
