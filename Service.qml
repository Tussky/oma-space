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
  readonly property int active: Hyprland.focusedWorkspace ? Hyprland.focusedWorkspace.id : 0

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
}
