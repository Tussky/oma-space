# OmaZoom — Product Requirement Document

**v0.2** · 22 Aug 2026 · revised after technical audit

---

## Why OmaZoom? Two reasons

1. OmaZoom was created to compete in the Omarchy plugins competition.
2. OmaZoom is a handy idea originally inspired by GNOME's own window management. Hyprland is an amazing product that sorts and visualises an individual workspace, but neither it nor Omarchy brings cohesive organisation to _workspaces_ (with an s).

## The one-sentence version

**Arrange a workspace the way you like it, save it, and rebuild it on demand — and see every workspace at a glance while you work.**

Everything below serves that sentence. If a feature doesn't, it's deferred.

---

## Core principle: the workspace is the unit, not the app

v0.1 described three different products at once — app-driven routing ("open Chrome and go to the Chrome workspace"), lazy workspace creation, and batch launching. They conflict. The unanswered question was: _I'm in the Coding workspace and I press the Chrome shortcut — what happens?_

**OmaZoom is workspace-driven.** You choose a context; the machine assembles around you. You are never moved somewhere involuntarily.

- **Workspace-driven (this product):** you pick "Coding" → the workspace opens, the layout applies, the apps come to you.
- **App-driven (not this product):** you open an app → you get pulled to wherever that app lives, losing the thing you were doing.

App-driven routing is deferred, not deleted — see below. It's also already solved by Hyprland `windowrule`, so it was never the differentiator.

---

## Features — v1

### F1 · Workspace preview panel

A side panel listing every workspace and the **windows** open in it — app icon, app name, window title.

Not thumbnails in v1. Live previews require per-client screencopy on Wayland, which is expensive and awkward to drive from QML. An icon-and-title list is ~90% of the usefulness at ~10% of the cost, and is arguably what you want at a glance anyway. Thumbnails are a v2 spike.

### F2 · Workspace definitions

A named, saved description of a working context. Stored as JSON (see Data model). A definition holds:

- a name and an icon
- a layout
- a list of apps, each with an exec line, a **working directory**, and optional floating/size hints

The working directory is not a detail — it's what turns "a coding workspace" into "the coding workspace _for this project_", which is the thing worth a keybind.

### F3 · Capture — save the current workspace

One action: **save what I have right now as a definition.**

This is the feature that makes the product stick, and it was missing from v0.1. Nobody wants to hand-author a config file describing apps they already have open. Capture reads the live state and writes the definition for them.

It's also the onboarding story (see F7) and the opening beat of the demo.

### F4 · Restore — rebuild a definition

Open a definition: create/switch to the workspace, apply the layout, launch every app into it with the right working directory.

Three requirements the v0.1 wording missed:

- **Reliability.** Must not use Hyprland `exec` workspace rules — they silently fail for Chromium-family apps and for anything already running. See Technical constraints.
- **Idempotency.** Re-opening an already-populated workspace must not spawn a second copy of everything. Check what's running first.
- **Stagger.** A short delay between launches so tiling settles before the next window lands.

### F5 · Per-workspace layout

Each definition names a layout, applied on open. Valid values: `dwindle`, `master`, `monocle`, `scrolling`.

### F6 · Entry points

A keybind and an Omarchy menu entry to pick a workspace. A bar widget showing the active workspace and opening the panel.

### F7 · First-run: capture, not presets

**On first run, offer to save the user's current setup as a workspace.** It's personalised, it's instantly correct, and it teaches the core mechanic in a single action. Ship at most one illustrative preset (Coding), not four speculative ones.

---

## Explicitly out of scope

**Tabs.** v0.1 described previewing "the tabs open" and recovering "where a tab or session" was. Hyprland exposes _windows_, not their contents — a browser window with forty tabs is one entry with one title. Reading real tab data requires a browser extension talking to the plugin over a local socket: a separate product, per-browser, with its own install and permissions story.

The user need behind that wording is real and F1 + F3 address most of it. But the PRD must not promise tabs.

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

### 5 · Plugins run unsandboxed in the shell process

QML runs in the same long-lived process as the bar, notifications and the **lock screen**. An uncaught throw is not a cosmetic bug. All parsing and process handling stays in the helper script; QML only renders.

---

## Data model

```json
{
  "version": 1,
  "workspaces": [
    {
      "name": "Coding",
      "icon": "󰅩",
      "layout": "dwindle",
      "apps": [
        { "exec": "alacritty -e nvim", "cwd": "~/Projects/omazoom" },
        { "exec": "alacritty",         "cwd": "~/Projects/omazoom" },
        { "exec": "chromium",          "cwd": "~" }
      ]
    }
  ]
}
```

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

Two pieces. The shell script does all real work; QML only draws.

```
omazoom/
├── manifest.json          kinds: ["bar-widget", "panel", "service"]
├── BarWidget.qml          trigger + active-workspace indicator
├── Panel.qml              the side preview
├── Service.qml            holds state, subscribes to Hyprland events
└── omazoom                the helper script
                             omazoom capture <name>
                             omazoom restore <name>
                             omazoom list --json
```

Capture and restore are testable from a terminal before any QML exists, which de-risks the hard half first and keeps a parsing bug out of the process that owns the lock screen.

This also lands OmaZoom in `panel` and `service` — two of the least-used plugin kinds in the Omarchy registry (54 and 198 of 872), which is free positioning against a crowded `bar-widget` field.

## Build order

1. `omazoom capture` — pure shell, testable immediately.
2. `omazoom restore` with spawn-then-claim. **Test against Chrome first** — it's the hard case, and if Chrome works everything works.
3. Bar widget + keybind — smallest possible UI over a working CLI.
4. The side preview panel — built last, on top of something that already functions.

Building the panel first is the tempting mistake: it looks like progress, works fine standalone, and teaches nothing about whether the hard half is achievable.

---

## Success criteria

The competition demo, in about ninety seconds:

1. Arrange a real workspace — editor, browser, terminal. Press capture. Name it "Coding."
2. Wipe it. Open a fresh workspace, hit the shortcut, watch it rebuild — right apps, right layout, right directories.
3. Open the side panel to show every workspace at a glance.

---

## Open questions

1. **Multi-monitor.** Definitions currently assume one output. Does a workspace remember which monitor it belonged to? Deferring, but it will come up.
