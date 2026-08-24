// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import Quickshell.Hyprland
import Quickshell.Io

// Live workspace state for the bar widget and the panel to render.
//
// Everything that reads Hyprland or /proc happens in the `oma-space` helper,
// in Python (prd.md constraint 2). This holds what the helper returned and
// decides when to ask again.
Item {
  id: root

  // Injected by the shell when this is mounted as the plugin's service.
  property var shell: null
  property var manifest: null

  // python3 explicitly rather than the shebang: a plugin directory copied
  // rather than cloned arrives without the exec bit.
  readonly property string helper: String(Qt.resolvedUrl("oma-space")).replace(/^file:\/\//, "")

  // [{ index, layout, windows: [{ address, label, class, title, icon, floating, fullscreen }] }]
  // Shape: docs/live.md.
  property var workspaces: []
  property bool loaded: false
  property string lastError: ""

  // Straight off Hyprland rather than out of the helper: the widget's label
  // should not wait for a subprocess to redraw on a workspace switch.
  readonly property var focusedWorkspace: Hyprland.focusedWorkspace
  readonly property int active: focusedWorkspace ? focusedWorkspace.id : 0
  readonly property int activeWindows: focusedWorkspace && focusedWorkspace.toplevels
    ? focusedWorkspace.toplevels.values.length : 0

  // Nobody looking means nothing to keep fresh. Each open surface holds one.
  property int watchers: 0

  readonly property var watchedEvents: [
    "openwindow", "closewindow", "movewindow", "movewindowv2",
    "windowtitle", "windowtitlev2", "fullscreen", "changefloatingmode",
    "workspace", "workspacev2"
  ]

  function windowsFor(index) {
    for (var i = 0; i < workspaces.length; i++) {
      if (workspaces[i].index === index) return workspaces[i].windows
    }
    return []
  }

  function refresh() {
    if (liveProcess.running) refreshAgain = true
    else liveProcess.running = true
  }

  property bool refreshAgain: false

  function apply(text) {
    // The one place helper output becomes objects. A throw here lands in the
    // process that owns the lock screen, so it never leaves this function.
    try {
      var state = JSON.parse(text)
      root.workspaces = (state && state.workspaces) || []
      root.lastError = ""
    } catch (e) {
      root.lastError = "could not read helper output"
      console.warn("oma-space: " + e)
    }
    root.loaded = true
  }

  Process {
    id: liveProcess
    command: ["python3", root.helper, "live"]

    stdout: StdioCollector { id: liveOut; waitForEnd: true }
    stderr: StdioCollector { id: liveErr; waitForEnd: true }

    onExited: function(code) {
      if (code === 0) {
        root.apply(liveOut.text)
      } else {
        root.lastError = liveErr.text.trim() || ("helper exited " + code)
        root.loaded = true
      }
      if (root.refreshAgain) {
        root.refreshAgain = false
        if (root.watchers > 0) liveProcess.running = true
      }
    }
  }

  // Events arrive in bursts — a window opening moves every tiled sibling — so
  // one refresh settles the burst rather than one per line.
  Timer {
    id: settle
    interval: 120
    onTriggered: root.refresh()
  }

  Connections {
    target: Hyprland

    function onRawEvent(event) {
      if (root.watchers <= 0) return
      if (root.watchedEvents.indexOf(event.name) === -1) return
      settle.restart()
    }
  }

  onWatchersChanged: if (watchers > 0) refresh()

  // --- arriving on an empty workspace fills it --------------------------------
  //
  // The product's own sentence: you pick a context and the machine assembles
  // around you. Focus is the trigger, so a tab click and Omarchy's own Super+N
  // both reach it and the bind stays Omarchy's (prd.md F4).

  property bool autoFill: true

  // Only the service the shell mounted. A tab that fell back to one of its own
  // would otherwise restore the same workspace once per tab.
  readonly property bool primary: shell !== null

  // The workspace this last tried to fill: a definition whose apps fail to
  // launch leaves the workspace empty, and must not be retried on a timer.
  property int filled: 0

  // The workspace waiting on a fresh read of the store. What is saved can change
  // from a terminal or another surface between arrivals, so arriving is where
  // the store is re-read rather than at startup only.
  property int fillPending: 0

  onActiveChanged: {
    if (filled !== 0 && filled !== active) filled = 0
    if (autoFill && primary) fillSettle.restart()
  }

  // Windows already on their way arrive after the workspace event; filling
  // before they land would launch a second copy of what is opening.
  Timer {
    id: fillSettle
    interval: 400
    onTriggered: root.fillActive()
  }

  function fillActive() {
    if (!autoFill || !primary || busy) return
    var index = root.active
    if (index <= 0 || index === filled) return
    // Only a workspace with nothing in it: restore fills gaps, but arriving is
    // not asking for gaps to be filled — it is asking for a workspace that is
    // not there yet.
    if (root.activeWindows > 0) return
    fillPending = index
    refreshSlots()
  }

  // Called once the store has been read: everything is re-checked, because the
  // read took a subprocess and the user may have moved on or opened something.
  function fillIfSaved(index) {
    if (!autoFill || !primary || busy) return
    if (index !== root.active || index === filled) return
    if (root.activeWindows > 0) return
    var slot = slotAt(index)
    if (!slot || slot.name === "" || !slot.apps || slot.apps.length === 0) return
    filled = index
    openWorkspace(index)
  }

  // --- definitions, and the verbs that write ---------------------------------
  //
  // Same rule as live: QML asks the helper and holds the answer. Nothing here
  // touches the filesystem or Hyprland directly (prd.md constraint 2).

  // The fifteen a workspace can wear (prd.md F6). Codepoints rather than the
  // glyphs themselves: a Private Use Area character does not survive every
  // editor and reads as a blank in a diff. All fifteen are Material Design
  // glyphs every Nerd Font patch carries.
  readonly property var iconChoices: [
    { name: "Code",     glyph: String.fromCodePoint(0xF0174) },
    { name: "Terminal", glyph: String.fromCodePoint(0xF018D) },
    { name: "Chat",     glyph: String.fromCodePoint(0xF0361) },
    { name: "Web",      glyph: String.fromCodePoint(0xF059F) },
    { name: "Mail",     glyph: String.fromCodePoint(0xF01EE) },
    { name: "Writing",  glyph: String.fromCodePoint(0xF03EB) },
    { name: "Notes",    glyph: String.fromCodePoint(0xF082E) },
    { name: "Reading",  glyph: String.fromCodePoint(0xF00BD) },
    { name: "Design",   glyph: String.fromCodePoint(0xF03D8) },
    { name: "Music",    glyph: String.fromCodePoint(0xF0387) },
    { name: "Video",    glyph: String.fromCodePoint(0xF0381) },
    { name: "Games",    glyph: String.fromCodePoint(0xF0EB5) },
    { name: "Files",    glyph: String.fromCodePoint(0xF024B) },
    { name: "System",   glyph: String.fromCodePoint(0xF0493) },
    { name: "Agents",   glyph: String.fromCodePoint(0xF06A9) }
  ]

  // Always ten, in order: the store is the ten workspaces (prd.md F6), so an
  // empty slot arrives as a normalised Workspace with no name rather than as a
  // gap the renderer has to handle.
  property var savedSlots: []
  property bool slotsLoaded: false

  // Read once at startup: a tab shows its workspace's name on the bar, so the
  // store is needed before any surface opens.
  Component.onCompleted: refreshSlots()

  function slotAt(index) {
    return index >= 1 && index <= savedSlots.length ? savedSlots[index - 1] : null
  }

  function slotName(index) {
    var slot = slotAt(index)
    return slot ? slot.name : ""
  }

  // One write at a time. Two captures of the same workspace would race for the
  // same filename, and a restore launching apps has no business overlapping a
  // second restore of the same workspace.
  property bool busy: false

  // Which workspace the running verb concerns, so a watchdog firing reports it
  // to the surface that asked rather than to every idle tab.
  property int busyIndex: 0

  // A helper that never exits would otherwise hold `busy` for the session and
  // every surface with it. Restore is the slow one — a window has ten seconds
  // to appear, per app — so this is long enough not to cut a real one short.
  Timer {
    id: watchdog
    interval: 120000
    running: root.busy
    onTriggered: {
      saveProcess.running = false
      editProcess.running = false
      deleteProcess.running = false
      restoreProcess.running = false
      root.busy = false
      root.actionFinished("", root.busyIndex, false, "the helper stopped responding")
    }
  }

  // (verb, index, ok, message) — the workspace rides along because a tab only
  // renders the status of an action it started, and the panel opens any of the ten.
  signal actionFinished(string verb, int index, bool ok, string message)
  // Saving refused because this workspace already holds a configuration (helper
  // exit 3). Not an error: the widget offers to save again and replace it. The
  // holder's name is already in savedSlots, so it is not repeated here.
  signal saveNeedsReplace(int index)

  // Queued rather than dropped: a read asked for while one is in flight is
  // asking about a store that may have changed since that one started.
  property bool slotsAgain: false

  function refreshSlots() {
    if (listProcess.running) slotsAgain = true
    else listProcess.running = true
  }

  function saveWorkspace(index, name, icon, force) {
    var trimmed = String(name || "").trim()
    if (busy || index <= 0 || trimmed === "") return
    var argv = ["python3", helper, "save", trimmed, "--index", String(index)]
    if (icon && icon !== "") argv.push("--icon", icon)
    if (force) argv.push("--force")
    saveProcess.pendingName = trimmed
    saveProcess.pendingIndex = index
    busyIndex = index
    saveProcess.command = argv
    busy = true
    saveProcess.running = true
  }

  // Labels only: the definition on disk keeps its apps, its layout and every
  // hand-edited field. Renaming is not capturing (prd.md F6).
  function editWorkspace(index, name, icon) {
    var trimmed = String(name || "").trim()
    if (busy || index <= 0 || trimmed === "") return
    editProcess.pendingName = trimmed
    editProcess.pendingIndex = index
    busyIndex = index
    editProcess.command = ["python3", helper, "edit", String(index),
      "--name", trimmed, "--icon", String(icon || "")]
    busy = true
    editProcess.running = true
  }

  // The write that takes something away. The workspace keeps its windows: this
  // empties its slot, it does not close anything (prd.md F2).
  function deleteWorkspace(index) {
    if (busy || index <= 0) return
    deleteProcess.pendingName = slotName(index) || ("workspace " + index)
    deleteProcess.pendingIndex = index
    busyIndex = index
    deleteProcess.command = ["python3", helper, "delete", String(index)]
    busy = true
    deleteProcess.running = true
  }

  // By index, because a workspace holds one configuration or none — there is
  // nothing else to address it by (prd.md F6).
  function openWorkspace(index) {
    if (busy || !(index >= 1)) return
    restoreProcess.pendingName = slotName(index) || ("workspace " + index)
    restoreProcess.pendingIndex = index
    busyIndex = index
    restoreProcess.command = ["python3", helper, "restore", String(index)]
    busy = true
    restoreProcess.running = true
  }

  // The last line of stderr: the helper prefixes every diagnostic with its verb
  // and the last one is the one that decided the exit code.
  function lastLine(text) {
    var lines = String(text || "").trim().split("\n")
    return lines.length > 0 ? lines[lines.length - 1] : ""
  }

  Process {
    id: listProcess
    command: ["python3", root.helper, "list", "--json"]

    stdout: StdioCollector { id: listOut; waitForEnd: true }

    onExited: function(code) {
      // Same guard as apply(): a throw here lands in the process that owns the
      // lock screen.
      try {
        root.savedSlots = code === 0 ? (JSON.parse(listOut.text) || []) : []
      } catch (e) {
        root.savedSlots = []
        console.warn("oma-space: " + e)
      }
      root.slotsLoaded = true

      if (root.slotsAgain) {
        // A pending fill waits for the fresher read rather than deciding on this one.
        root.slotsAgain = false
        listProcess.running = true
        return
      }

      if (root.fillPending > 0) {
        var pending = root.fillPending
        root.fillPending = 0
        root.fillIfSaved(pending)
      }
    }
  }

  Process {
    id: saveProcess
    property string pendingName: ""
    property int pendingIndex: 0

    stderr: StdioCollector { id: saveErr; waitForEnd: true }

    onExited: function(code) {
      root.busy = false
      if (code === 0) {
        root.refreshSlots()
        root.actionFinished("save", saveProcess.pendingIndex, true, "Saved " + saveProcess.pendingName)
      } else if (code === 3) {
        root.saveNeedsReplace(saveProcess.pendingIndex)
      } else {
        root.actionFinished("save", saveProcess.pendingIndex, false,
          root.lastLine(saveErr.text) || ("helper exited " + code))
      }
    }
  }

  Process {
    id: editProcess
    property string pendingName: ""
    property int pendingIndex: 0

    stderr: StdioCollector { id: editErr; waitForEnd: true }

    onExited: function(code) {
      root.busy = false
      if (code === 0) {
        root.refreshSlots()
        root.actionFinished("edit", editProcess.pendingIndex, true,
          "Saved " + editProcess.pendingName)
      } else {
        root.actionFinished("edit", editProcess.pendingIndex, false,
          root.lastLine(editErr.text) || ("helper exited " + code))
      }
    }
  }

  Process {
    id: deleteProcess
    property string pendingName: ""
    property int pendingIndex: 0

    stderr: StdioCollector { id: deleteErr; waitForEnd: true }

    onExited: function(code) {
      root.busy = false
      if (code === 0) {
        root.refreshSlots()
        root.actionFinished("delete", deleteProcess.pendingIndex, true,
          "Deleted " + deleteProcess.pendingName)
      } else {
        root.actionFinished("delete", deleteProcess.pendingIndex, false,
          root.lastLine(deleteErr.text) || ("helper exited " + code))
      }
    }
  }

  Process {
    id: restoreProcess
    property string pendingName: ""
    property int pendingIndex: 0

    stderr: StdioCollector { id: restoreErr; waitForEnd: true }

    onExited: function(code) {
      root.busy = false
      // Exit 1 means some app did not come back, not that nothing did — the
      // sequence never stops on one failure (prd.md lifecycle).
      if (code === 0) {
        root.actionFinished("restore", restoreProcess.pendingIndex, true, "Opened " + restoreProcess.pendingName)
      } else {
        root.actionFinished("restore", restoreProcess.pendingIndex, false,
          root.lastLine(restoreErr.text) || ("helper exited " + code))
      }
    }
  }
}
