# live

`oma-space live` — every workspace and the windows in it right now, on stdout.
Rationale lives in prd.md F1; this is the interface.

Live state, not a definition. Nothing here is saved and restore never reads it,
so none of the definition-only fields — `exec`, `cwd`, `size` — appear.

## Contract

- One JSON object on **stdout**, single line. Nothing else on stdout, ever.
- Exit `0`, or non-zero if Hyprland can't be read at all.
- Silent on stderr. It runs on every hover, and capture's warnings are about the
  fidelity of a definition this verb never writes, so it sets `capture.QUIET`.
- A window it cannot resolve is still emitted, with its class standing in for
  both `label` and `icon`.

```json
{"active":1,"workspaces":[
  {"index":1,"layout":"scrolling","windows":[
    {"address":"0x55fc14de1c60","label":"nvim","class":"foot",
     "title":"nvim ~/Projects/oma-space","icon":"foot",
     "floating":false,"fullscreen":false}]}]}
```

## Fields

| key | type | notes |
|---|---|---|
| `active` | int | the focused workspace, `0` if none |
| `workspaces[].index` | int | 1–10; special workspaces carry negative ids and are dropped |
| `workspaces[].layout` | string | `workspaces -j` → `tiledLayout` |
| `workspaces[].windows` | array | may be empty; ordered top-to-bottom, left-to-right on screen |

| key | type | notes |
|---|---|---|
| `address` | string | Hyprland's window handle — the stable identity across refreshes |
| `label` | string | inner program for terminals, `.desktop` `Name=` otherwise |
| `class` | string | `initialClass` |
| `title` | string | the window title, live |
| `icon` | string | `.desktop` `Icon=`, resolved by the renderer through `Quickshell.iconPath` |
| `floating` | bool | |
| `fullscreen` | bool | `clients[].fullscreen != 0` — the source is an int |

`label` and `icon` resolve the same way capture's `exec` does — terminal, webapp,
native app, class — so a window names itself identically in the panel and in a
definition captured from it. See `docs/capture.md`.

A workspace appears when it exists or holds windows, so an empty one still lists
with `windows: []`.

## Acceptance checks

```bash
oma-space live | jq -e . >/dev/null && echo ok          # valid JSON
test "$(oma-space live | wc -l)" = 1 && echo ok         # single line
test -z "$(oma-space live 2>&1 >/dev/null)" && echo ok  # silent stderr
oma-space live | jq -e '.workspaces | all(.index >= 1)'
```
