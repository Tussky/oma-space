# edit

`oma-space edit <index>` — a workspace's name and icon, in place.
Rationale lives in prd.md F6; this is the interface.

Save captures: it replaces a definition with what is on the workspace right now.
That is what you want when the arrangement changed, and exactly what you do not
want when only the name did — a workspace that happens to be empty while you rename
it would come back holding no apps at all. So the labels get a verb of their own.

## Contract

- The path it wrote on **stdout**, once. Nothing else on stdout, ever.
- Diagnostics to **stderr**. Exit `0`, `1` on failure, `2` on usage.
- **Only `name` and `icon` are touched.** Apps, layout, sizes, working directories
  and any hand-edited field are loaded and written back unchanged.
- **An empty slot is refused**, not filled: there is nothing to rename until
  something has been captured. Exit `1`.
- The write is the store's own — atomic, whole or not at all.
- An omitted flag leaves that field alone; `--icon ""` takes the icon off.

```bash
oma-space edit 3 --name "Coding"
oma-space edit 3 --icon ""             # take the icon off
oma-space edit 3 --name "Coding" --icon 󰅴
```

## Options

| option | notes |
|---|---|
| `--name NAME` | what the panel and the tab call this workspace |
| `--icon GLYPH` | the icon it wears. Empty takes it off. The panel offers fifteen; this takes any string |

## In Python

```python
import edit

workspace, path, errors = edit.labels(3, name="Coding", icon="󰅴")
```

Both fields are optional and `None` means "leave it". The panel calls the verb
rather than this function only because QML cannot import a module (prd.md
constraint 2).
