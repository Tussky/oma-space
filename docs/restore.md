# restore

`oma-space restore <workspace-index>` — a workspace, rebuilt from what is saved
for it. Rationale lives in prd.md F4; this is the interface and the mechanics.

Addressed by index because that is the identity: a workspace holds one
configuration or none (prd.md F6), so there is nothing to disambiguate and no
name to look up.

## Contract

- One JSON summary on **stdout**, single line: what launched, what did not.
- Diagnostics to **stderr**. Exit `0`, `1` if any app failed to come back (the
  rest still did), `2` on usage.
- **Never duplicates.** Apps already on the workspace are left alone and the
  gaps are filled, counted rather than set-matched: a definition with two
  terminals and one already open launches one more, not two.
- **One failure never stops the sequence.** A launch that dies, or a window that
  never maps, is logged and skipped (prd.md lifecycle).

```json
{"name":"Coding","index":1,"launched":["nvim","WhatsApp"],"failed":[]}
```

`--timeout SECONDS` (default 10) is how long one window has to appear before the
sequence moves on.

## How a window is claimed

Hyprland's own `exec` workspace rules track a spawned window through the
process environment, and chromium-family apps clear theirs — so the rule finds
nothing and the window lands wherever you happen to be (prd.md constraint 1).
Spawn-then-claim instead:

1. Subscribe to `$XDG_RUNTIME_DIR/hypr/$HYPRLAND_INSTANCE_SIGNATURE/.socket2.sock`
   **before** launching anything. Subscribing after the launch races the window:
   a fast app maps before the subscription lands and is never seen.
2. Launch the app.
3. Read `openwindow>>address,workspace,class,title` until the class matches
   `matchClass` — the event carries the class at map time, which is exactly what
   capture stored.
4. Move that address onto the workspace, then apply its state.

**Launching is ours, not Hyprland's.** `hl.dsp.exec_cmd("<command>")` is the
compositor's spawn, and it takes a command string and nothing else — no working
directory, no environment. So apps are spawned directly instead, in a new session,
with `cwd` set. The working directory is what a definition is *for*; routing the
launch through the compositor would lose it.

A cwd that no longer exists is dropped with a warning rather than failing the
launch: the app is still worth having.

## The Lua API — verified on Hyprland 0.56.2

This build parses **only** the Lua dispatch API. `hyprctl dispatch workspace 1`,
`movetoworkspacesilent` and `hyprctl keyword` all fail — the last with
"keyword can't work with non-legacy parsers. Use eval."

| what | call |
|---|---|
| switch workspace | `hl.dsp.focus({ workspace = "1" })` |
| claim a window, silently | `hl.dsp.window.move({ workspace = "1", follow = false, window = "address:0x…" })` |
| float | `hl.dsp.window.float({ window = "address:0x…", action = "toggle" })` |
| exact size | `hl.dsp.window.resize({ window = "address:0x…", x = 400, y = 300 })` |
| fullscreen | `hl.dsp.window.fullscreen({ mode = "fullscreen", window = "address:0x…" })` |
| per-workspace layout | `hyprctl eval 'hl.workspace_rule({ workspace = "1", layout = "dwindle" })'` |

**`ok` is not confirmation.** Every dispatcher above answers `ok` for a window
address that does not exist, so a return value proves the call parsed and nothing
more. Only invalid enum values and unrecognised argument names error — which also
means a probe with a made-up argument still *runs* the dispatcher: `float({action
= "bogus"})` answers `ok` and toggles the focused window. Probe with a fake
address, never a fake argument.

**Nothing sets a state outright.** `action` is a toggle whatever it is handed, so
the window's current `floating` decides whether to send anything at all.

**The layout is applied live, not persisted.** Omarchy's own layout toggle writes
`~/.local/state/omarchy/workspace-layouts/<id>.lua` so its choice survives a
reload; oma-space deliberately does not write there. That state belongs to
Omarchy, the same way its keybinds do (prd.md F6) — restore sets the layout for
the session it is restoring into.

## What is not applied yet

**Tiled sizes.** A captured fraction is real intent (prd.md F3), but Hyprland
takes no absolute size for a tiled window: dwindle wants a `splitratio` relative
to its parent node and scrolling wants a column width. Floating windows get their
exact size; a tiled one is placed by the layout and says so on stderr rather than
being resized into the wrong thing.

**Window order and position.** Windows arrive in definition order; where the
layout puts them is the layout's business.

## Checks

```bash
oma-space restore 1 | jq -e .                   # single-line summary
oma-space restore 1                             # again: everything already there
oma-space restore 9; echo $?                    # 1, nothing saved for workspace 9
```
