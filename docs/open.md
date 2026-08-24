# open

`oma-space open [index]` — the workspace you are on becomes whatever was saved
for it. `restore` with the index defaulted to where you are standing, so one
keybind serves all ten workspaces. Rationale lives in prd.md F6; this is the
interface.

With no argument it acts on the active workspace, which is what a keybind wants.

## Contract

- Restore's summary on **stdout**, single line; the same shape `docs/restore.md`
  documents, because this verb *is* restore with the name looked up for you.
- Diagnostics to **stderr**. Exit `0`, `1` when there is nothing saved for this
  workspace or an app failed to open, `2` on usage.
- **Fills gaps, never demands an empty workspace.** The press is deliberate, so a
  workspace holding one stray terminal is completed rather than refused. Nothing
  is duplicated, so pressing it twice does nothing the second time.
- **Says so when it does nothing.** A keybind whose failure lands on stderr has
  no failure the user can see, so "nothing saved for workspace 3" goes to
  `omarchy-notification-send` when it is on PATH. Success stays silent — the
  windows are the feedback.

## Which definition

The one saved for this workspace, and there can only be one: the store is the ten
workspaces, so a second configuration for the same number cannot be written in the
first place (prd.md Architecture). An empty slot is answered — "nothing saved for
workspace 3" — rather than treated as a failure.

## The keybind

Not shipped, not generated. Omarchy owns the keymap (prd.md F6), so oma-space
suggests a line for `~/.config/hypr/bindings.lua` and the user adds it:

```lua
o.bind("SUPER + R", "Rebuild this workspace (oma-space)",
  "python3 ~/.config/omarchy/plugins/io.github.teapot.oma-space/oma-space open")
```

`python3` explicitly rather than the shebang, for the same reason `Service.qml`
does it: a plugin directory copied rather than cloned arrives without the exec
bit.

**Why not a second press of `SUPER+3`.** It is the obvious gesture and it cannot
be detected: re-focusing the workspace you are already on emits **no** `workspace`
event on `.socket2.sock` — only an `activewindow` refocus — so nothing outside the
keymap can see the second press. Catching it would mean oma-space taking over
`SUPER+1`…`0`, which is exactly what F6 says it does not do. A key of its own
costs one line of config and no Omarchy binds.

## Checks

```bash
oma-space open        | jq -e .      # summary for the active workspace
oma-space open 3      | jq -e .      # ... or a named one
oma-space open 9; echo $?            # 1 + a toast when nothing is saved there
```
