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

### F5 · Per-workspace layout

Each definition names a layout, applied on open. Valid values: `dwindle`, `master`, `monocle`, `scrolling`.

### F6 · Entry points

A keybind and an Omarchy menu entry to pick a workspace. A bar widget showing the active workspace and opening the panel.

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

### 5 · Plugins run unsandboxed in the shell process

QML runs in the same long-lived process as the bar, notifications and the **lock screen**. An uncaught throw is not a cosmetic bug. All parsing and process handling stays in the helper script; QML only renders.

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

Two pieces. The shell script does all real work; QML only draws.

```
oma-space/
├── manifest.json          kinds: ["bar-widget", "panel", "service"]
├── BarWidget.qml          trigger + active-workspace indicator
├── Panel.qml              the side preview
├── Service.qml            holds state, subscribes to Hyprland events
└── oma-space              the helper script
                             oma-space capture <name>
                             oma-space restore <name>
                             oma-space list --json
```

Capture and restore are testable from a terminal before any QML exists, which de-risks the hard half first and keeps a parsing bug out of the process that owns the lock screen.

This also lands Oma-space in `panel` and `service` — two of the least-used plugin kinds in the Omarchy registry (54 and 198 of 872), which is free positioning against a crowded `bar-widget` field
---

## Success criteria

The competition demo, in about ninety seconds:

1. Arrange a real workspace — editor, browser, terminal. Press capture. Name it "Coding."
2. Wipe it. Open a fresh workspace, hit the shortcut, watch it rebuild — right apps, right layout, right directories.
3. Open the side panel to show every workspace at a glance.

---

## Open questions

1. **Multi-monitor.** Definitions currently assume one output. Does a workspace remember which monitor it belonged to? Deferring, but it will come up.
