// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import Quickshell
import Quickshell.Hyprland
import qs.Ui
import qs.Commons

// One workspace on the bar (prd.md F6). Ten instances make the strip that
// replaces omarchy.workspaces: click focuses, hover says what is open there.
//
// Nothing here parses live state — the widget reads what Service.qml holds.
BarWidget {
  id: root

  readonly property string pluginId: "io.github.tussky.oma-space"

  // The shell mounts one Service for the whole session. A bar surface exists
  // per monitor and a tab per workspace, so sharing it keeps one helper
  // process rather than one each.
  readonly property var sharedService: bar && bar.shell && typeof bar.shell.serviceFor === "function"
    ? bar.shell.serviceFor(pluginId) : null
  readonly property var service: sharedService || ownService.item

  // --- what this tab is attached to ------------------------------------------

  readonly property bool scratch: setting("scratch", false) === true
  readonly property int index: scratch ? 10
    : Math.max(1, Math.min(10, Math.round(Number(setting("index", 1))) || 1))
  readonly property bool pinned: setting("pinned", false) === true
  readonly property string labelMode: String(setting("label", "Icon")).toLowerCase()

  readonly property var hyprWorkspace: {
    var values = Hyprland.workspaces ? Hyprland.workspaces.values : []
    for (var i = 0; i < values.length; i++) if (values[i].id === root.index) return values[i]
    return null
  }
  // Straight off Hyprland rather than out of the helper: a tab should appear
  // the moment a window opens on it, not a subprocess later. An empty workspace
  // is off the bar — scratch included — unless it is the one you are standing on
  // or the tab asked to be pinned.
  readonly property int windowCount: hyprWorkspace ? hyprWorkspace.toplevels.values.length : 0
  readonly property bool focused: Hyprland.focusedWorkspace !== null
    && Hyprland.focusedWorkspace.id === root.index
  readonly property bool shown: windowCount > 0 || focused || pinned

  readonly property var definition: service && !scratch ? service.slotAt(root.index) : null
  readonly property bool saved: definition !== null && definition.name !== ""
  readonly property var savedApps: saved && definition.apps ? definition.apps : []

  readonly property string numberText: root.index === 10 ? "0" : String(root.index)
  readonly property string title: scratch ? "Scratch"
    : (saved ? definition.name : "Workspace " + root.index)
  readonly property string shortcut: saved && definition.shortcut !== ""
    ? definition.shortcut : "SUPER+" + numberText

  readonly property var windows: service ? service.windowsFor(root.index) : []
  readonly property string layoutName: {
    if (service) {
      for (var i = 0; i < service.workspaces.length; i++) {
        if (service.workspaces[i].index === root.index) return service.workspaces[i].layout
      }
    }
    return saved ? definition.layout : ""
  }

  // Codepoint rather than the glyph itself: a Private Use Area character does
  // not survive every editor and reads as a blank in a diff. Omarchy's own
  // focused-workspace mark, so a bar of these reads as the bar it replaces.
  readonly property string pillText: {
    if (labelMode === "name" && saved) return definition.name
    if (labelMode === "icon" && saved && definition.icon !== "") return definition.icon
    return focused ? String.fromCodePoint(0xF14FB) : numberText
  }

  // --- surfaces ---------------------------------------------------------------

  property bool popupOpen: false

  // The capture/open panel. Separate from the hover card because typing needs
  // keyboard focus, and a hover card is a passive overlay that never has it.
  property bool panelOpen: false
  property string panelStatus: ""
  // The workspace the running verb concerns: the panel opens any of the ten,
  // so a status line from another tab's action is not this tab's to render.
  property int actionIndex: 0
  property bool replacePending: false
  // Deleting is asked for twice, like replacing: the button says so in between
  // rather than a dialog saying it somewhere else.
  property bool deletePending: false
  // The icon the panel will save with the name. Empty is a workspace with no icon.
  property string pickedIcon: ""

  // The workspace the panel is editing — any of the ten, not only this tab's.
  // A workspace with nothing open has no tab to hover, so editing it has to be
  // reachable from a tab that is on the bar (prd.md F6).
  property int subject: 0
  readonly property var subjectSlot: service && subject > 0 ? service.slotAt(subject) : null
  readonly property bool subjectSaved: subjectSlot !== null && subjectSlot.name !== ""
  readonly property string subjectNumber: subject === 10 ? "0" : String(subject)
  readonly property var subjectWindows: service && subject > 0 ? service.windowsFor(subject) : []

  readonly property var iconChoices: service ? service.iconChoices : []

  readonly property var slots: service ? service.savedSlots : []
  readonly property bool busy: service ? service.busy : false

  // open(), close() and opened are what the bar looks for before it will treat a
  // widget as owning a panel: they carry `omarchy-shell shell toggle <id>`, the
  // by-position togglePanelAt, and arrow navigation between open bar panels.
  readonly property bool opened: panelOpen

  function open() { if (!panelOpen) openPanel() }

  // The bar hands one popout slot around and closes the last holder by name.
  // Without this it closes the card directly, breaking its binding to popupOpen.
  function close() { popupOpen = false; panelOpen = false }

  function focusWorkspace() {
    // Hyprland 0.56 parses a Lua API and nothing else; this is the call
    // omarchy.workspaces makes, so navigation behaves identically.
    if (bar) bar.run("hyprctl dispatch "
      + Util.shellQuote("hl.dsp.focus({ workspace = \"" + root.index + "\" })"))
  }

  // The panel is built the first time it is opened: ten tabs would otherwise
  // each hold a panel window nobody has asked for.
  property bool panelEverOpened: false

  function panelName() {
    return panelHost.item ? String(panelHost.item.nameText).trim() : ""
  }

  function selectSubject(index) {
    root.subject = index
    var slot = service ? service.slotAt(index) : null
    // The field opens holding what the workspace is already called, so editing
    // it is Save, not retyping its name.
    if (panelHost.item) panelHost.item.nameText = slot ? slot.name : ""
    root.pickedIcon = slot ? slot.icon : ""
    root.replacePending = false
    root.deletePending = false
    root.panelStatus = ""
    root.actionIndex = 0
  }

  function openPanel() {
    root.panelEverOpened = true
    // A scratch tab writes nothing, so it opens on no workspace at all.
    root.selectSubject(root.scratch ? 0 : root.index)
    if (service) service.refreshSlots()
    root.popupOpen = false
    root.panelOpen = true
  }

  // Labels only when the workspace already holds a definition: capture replaces
  // what is on disk with what is open now, which is the one thing a rename must
  // not do.
  function saveSubject() {
    var name = root.panelName()
    if (!service || root.subject <= 0 || name === "") return
    // Capture reads the workspace: with nothing on it there is nothing to read,
    // and the helper refuses. Labels on an existing definition are always fine.
    if (!root.subjectSaved && root.subjectWindows.length === 0) {
      root.panelStatus = "Workspace " + root.subjectNumber + " has nothing open to capture"
      return
    }
    root.panelStatus = ""
    root.actionIndex = root.subject
    if (root.subjectSaved && !root.replacePending) {
      service.editWorkspace(root.subject, name, root.pickedIcon)
    } else {
      service.saveWorkspace(root.subject, name, root.pickedIcon, root.replacePending)
    }
  }

  // The deliberate other half: take what is on the workspace now and replace the
  // apps this definition holds, keeping the name and icon in the fields.
  function recaptureSubject() {
    var name = root.panelName()
    if (!service || root.subject <= 0 || name === "") return
    if (root.subjectWindows.length === 0) {
      root.panelStatus = "Workspace " + root.subjectNumber + " has nothing open to capture"
      return
    }
    root.panelStatus = ""
    root.actionIndex = root.subject
    service.saveWorkspace(root.subject, name, root.pickedIcon, true)
  }

  function deleteSubject() {
    if (!service || root.subject <= 0 || !root.subjectSaved) return
    if (!root.deletePending) {
      root.deletePending = true
      root.panelStatus = "Delete “" + root.subjectSlot.name + "”? Press again. "
        + "The workspace keeps its windows."
      return
    }
    root.deletePending = false
    root.panelStatus = ""
    root.actionIndex = root.subject
    service.deleteWorkspace(root.subject)
  }

  function openSaved(index) {
    if (!service) return
    root.actionIndex = index
    root.panelStatus = "Opening " + service.slotName(index) + "…"
    service.openWorkspace(index)
  }

  readonly property bool pointerInside: pill.tooltipHovered || popup.containsMouse

  onPointerInsideChanged: {
    // While the panel is up it owns the tab; a card sliding back under it on a
    // stray hover would cover the thing being typed into.
    if (panelOpen) return
    if (pointerInside) {
      closeTimer.stop()
      popupOpen = true
    } else {
      closeTimer.restart()
    }
  }

  // A gap between the tab and the popup card the cursor has to cross.
  Timer {
    id: closeTimer
    interval: 200
    onTriggered: root.popupOpen = false
  }

  readonly property bool watching: popupOpen || panelOpen
  // Held rather than looked up again: `service` can change identity (a tab that
  // fell back to its own picks up the shared one when it mounts), and the count
  // has to come off whichever instance it went on to.
  property var watchedService: null

  onWatchingChanged: {
    if (watching) {
      watchedService = service
      if (watchedService) watchedService.watchers += 1
    } else if (watchedService) {
      watchedService.watchers -= 1
      watchedService = null
    }
  }

  Component.onDestruction: if (watchedService) watchedService.watchers -= 1

  Connections {
    target: root.service

    function onActionFinished(verb, index, ok, message) {
      if (index !== root.actionIndex) return
      root.panelStatus = message
      root.replacePending = false
      root.deletePending = false
      if (!ok) return
      // The slot is empty now, so the panel is looking at a workspace with
      // nothing saved: the fields have to say so before the store comes back.
      if (verb === "delete" && index === root.subject) {
        if (panelHost.item) panelHost.item.nameText = ""
        root.pickedIcon = ""
      }
      // A restore switched workspace and launched windows; the panel has done
      // its job and is in the way of what just opened.
      if (verb === "restore") root.panelOpen = false
    }

    function onSaveNeedsReplace(index) {
      if (index !== root.index) return
      root.replacePending = true
      root.panelStatus = "Workspace " + index + " holds “" + root.service.slotName(index)
        + "” — save again to replace it"
    }
  }

  // Only reached when the plugin is on the bar but its service kind was not
  // mounted; the tab still works, on its own helper process.
  Loader {
    id: ownService
    active: root.sharedService === null
    sourceComponent: Component { Service {} }
  }

  visible: shown
  implicitWidth: shown ? pill.implicitWidth : 0
  implicitHeight: shown ? pill.implicitHeight : 0

  Behavior on implicitWidth {
    enabled: !root.vertical
    NumberAnimation { duration: 140; easing.type: Easing.OutCubic }
  }

  WidgetButton {
    id: pill
    anchors.centerIn: parent
    bar: root.bar
    text: root.pillText
    // An icon replaces the glyph Omarchy swaps in for the focused workspace, so
    // where you are has to be said in colour and a mark instead.
    active: root.focused
    opacity: root.windowCount > 0 || root.focused ? 1 : 0.5
    horizontalMargin: 6
    verticalPadding: 6
    // Name mode is as wide as the name; every other mode keeps the fixed cell
    // omarchy.workspaces uses, so a strip of tabs stays a grid.
    fixedWidth: root.vertical ? root.barSize
      : (root.labelMode === "name" && root.saved ? -1 : Style.space(20))
    fixedHeight: root.barSize
    // Left navigates. Right is the shortcut past hover-then-click for the panel.
    onPressed: function(button) {
      if (button === Qt.LeftButton) root.focusWorkspace()
      else if (button === Qt.RightButton) root.panelOpen ? root.close() : root.openPanel()
    }

    Rectangle {
      visible: root.focused
      color: root.bar ? root.bar.urgent : Color.urgent
      radius: height / 2
      width: root.vertical ? Style.space(2) : Style.space(10)
      height: root.vertical ? Style.space(10) : Style.space(2)
      anchors.horizontalCenter: root.vertical ? undefined : parent.horizontalCenter
      anchors.verticalCenter: root.vertical ? parent.verticalCenter : undefined
      anchors.bottom: root.vertical ? undefined : parent.bottom
      anchors.bottomMargin: root.vertical ? 0 : Style.space(2)
      anchors.left: root.vertical ? parent.left : undefined
    }
  }

  PopupCard {
    id: popup
    anchorItem: root
    bar: root.bar
    owner: root
    open: root.popupOpen && !root.panelOpen && root.shown
    triggerMode: "hover"
    contentWidth: popup.fittedContentWidth(Style.space(340))
    contentHeight: popup.fittedContentHeight(column.implicitHeight)

    Column {
      id: column
      anchors.fill: parent
      spacing: Style.space(8)

      Item {
        width: parent.width
        height: header.implicitHeight

        Text {
          id: header
          anchors.left: parent.left
          width: parent.width - shortcutLabel.implicitWidth - Style.space(8)
          text: (root.saved && root.definition.icon !== "" ? root.definition.icon + "  " : "") + root.title
          color: root.bar ? root.bar.foreground : Color.foreground
          font.family: root.bar ? root.bar.fontFamily : Style.font.family
          font.pixelSize: Style.font.subtitle
          font.bold: true
          elide: Text.ElideRight
        }

        Text {
          id: shortcutLabel
          anchors.right: parent.right
          anchors.baseline: header.baseline
          // Descriptive only — the bind belongs to Omarchy (prd.md F6).
          text: root.shortcut
          color: Color.muted
          font.family: root.bar ? root.bar.fontFamily : Style.font.family
          font.pixelSize: Style.font.caption
        }
      }

      Text {
        width: parent.width
        text: {
          var parts = []
          if (root.layoutName !== "") parts.push(root.layoutName)
          if (root.windows.length > 0)
            parts.push(root.windows.length === 1 ? "1 window" : root.windows.length + " windows")
          else if (root.savedApps.length > 0)
            parts.push(root.savedApps.length === 1 ? "1 app saved" : root.savedApps.length + " apps saved")
          return parts.join(" · ")
        }
        visible: text !== ""
        color: Color.muted
        font.family: root.bar ? root.bar.fontFamily : Style.font.family
        font.pixelSize: Style.font.caption
      }

      Text {
        width: parent.width
        visible: root.windows.length === 0 && root.savedApps.length === 0
        text: root.service && !root.service.loaded ? "Reading…"
          : (root.service && root.service.lastError !== "" ? root.service.lastError : "Nothing open here")
        color: Color.muted
        font.family: root.bar ? root.bar.fontFamily : Style.font.family
        font.pixelSize: Style.font.bodySmall
      }

      Repeater {
        model: root.windows

        Row {
          id: entry
          required property var modelData

          width: column.width
          spacing: Style.space(8)

          Image {
            id: appIcon
            width: Style.space(18)
            height: Style.space(18)
            anchors.verticalCenter: parent.verticalCenter
            fillMode: Image.PreserveAspectFit
            asynchronous: true
            sourceSize.width: Style.space(36)
            sourceSize.height: Style.space(36)
            source: {
              var found = Quickshell.iconPath(String(entry.modelData.icon || ""), true)
              return found.length > 0 ? found : Quickshell.iconPath("application-x-executable", true)
            }
          }

          Column {
            width: entry.width - appIcon.width - entry.spacing
            spacing: 0

            Text {
              width: parent.width
              text: entry.modelData.label || entry.modelData.class
              color: root.bar ? root.bar.foreground : Color.foreground
              font.family: root.bar ? root.bar.fontFamily : Style.font.family
              font.pixelSize: Style.font.body
              elide: Text.ElideRight
            }

            Text {
              width: parent.width
              visible: text.length > 0
              text: entry.modelData.title || ""
              color: Color.muted
              font.family: root.bar ? root.bar.fontFamily : Style.font.family
              font.pixelSize: Style.font.bodySmall
              elide: Text.ElideRight
            }
          }
        }
      }

      // Nothing is running, but something is saved: the hover says what this
      // workspace would come back as.
      Repeater {
        model: root.windows.length === 0 ? root.savedApps : []

        Row {
          id: savedEntry
          required property var modelData

          width: column.width
          spacing: Style.space(8)
          opacity: 0.6

          Image {
            id: savedIcon
            width: Style.space(18)
            height: Style.space(18)
            anchors.verticalCenter: parent.verticalCenter
            fillMode: Image.PreserveAspectFit
            asynchronous: true
            sourceSize.width: Style.space(36)
            sourceSize.height: Style.space(36)
            source: {
              var found = Quickshell.iconPath(String(savedEntry.modelData.matchClass || ""), true)
              return found.length > 0 ? found : Quickshell.iconPath("application-x-executable", true)
            }
          }

          Column {
            width: savedEntry.width - savedIcon.width - savedEntry.spacing
            spacing: 0

            Text {
              width: parent.width
              text: savedEntry.modelData.label || savedEntry.modelData.matchClass
              color: root.bar ? root.bar.foreground : Color.foreground
              font.family: root.bar ? root.bar.fontFamily : Style.font.family
              font.pixelSize: Style.font.body
              elide: Text.ElideRight
            }

            Text {
              width: parent.width
              visible: text.length > 0
              text: savedEntry.modelData.cwd || ""
              color: Color.muted
              font.family: root.bar ? root.bar.fontFamily : Style.font.family
              font.pixelSize: Style.font.bodySmall
              elide: Text.ElideLeft
            }
          }
        }
      }

      // Both writes live behind a click: the hover stays a glance (prd.md F6).
      Row {
        width: parent.width
        spacing: Style.space(6)

        Button {
          visible: root.saved
          text: "Open " + root.title
          bordered: true
          fontSize: Style.font.bodySmall
          foreground: root.bar ? root.bar.foreground : Color.foreground
          enabled: !root.busy
          onClicked: root.openSaved(root.index)
        }

        Button {
          text: root.scratch ? "Workspaces…" : (root.saved ? "Edit…" : "Capture…")
          bordered: true
          fontSize: Style.font.bodySmall
          foreground: root.bar ? root.bar.foreground : Color.foreground
          onClicked: root.openPanel()
        }
      }
    }
  }

  // The coordinator closes the last popout holder by calling close() on its
  // key. Registering the panel under its own means a card closing beside it
  // never takes the panel down with it.
  QtObject {
    id: panelKey
    function close() { root.panelOpen = false }
  }

  // Built on first open. Ten tabs times two popup windows is a cost the bar
  // pays at startup for panels most of them will never show.
  Loader {
    id: panelHost
    active: root.panelEverOpened
    sourceComponent: panelComponent
  }

  Component {
    id: panelComponent

    KeyboardPanel {
      id: panel

      // The field lives in here, and here only exists once the panel has been
      // opened — so the tab reads and writes it through this.
      property alias nameText: nameField.text

      anchorItem: root
      bar: root.bar
      owner: panelKey
      // A tab that leaves the bar under its own panel takes the panel with it:
      // nothing is left anchored to an item with no width.
      open: root.panelOpen && root.shown
      focusTarget: root.scratch ? null : nameField
      contentWidth: panel.fittedContentWidth(Style.space(320))
      contentHeight: panel.fittedContentHeight(panelColumn.implicitHeight)

      Column {
        id: panelColumn
        anchors.fill: parent
        spacing: Style.space(6)

        // A scratch tab writes nothing (prd.md F6), so it offers the store
        // without the fields that write into it.
        readonly property bool editing: !root.scratch && root.subject > 0

        PanelSectionHeader {
          width: parent.width
          visible: panelColumn.editing
          text: (root.subjectSaved ? "EDIT WORKSPACE " : "CAPTURE WORKSPACE ") + root.subjectNumber
          foreground: root.bar ? root.bar.foreground : Color.foreground
          fontFamily: root.bar ? root.bar.fontFamily : Style.font.family
        }

        Item {
          width: parent.width
          visible: panelColumn.editing
          height: visible ? Math.max(nameField.implicitHeight, saveButton.implicitHeight) : 0

          TextField {
            id: nameField
            width: parent.width - saveButton.width - Style.space(6)
            anchors.verticalCenter: parent.verticalCenter
            placeholderText: "Name this workspace"
            foreground: root.bar ? root.bar.foreground : Color.foreground
            enabled: !root.busy
            onAccepted: root.saveSubject()
            Keys.onEscapePressed: root.close()
          }

          Button {
            id: saveButton
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            // Three different writes, named for what each one does to the apps on
            // disk: none, all of them, all of them over something that was there.
            text: root.replacePending ? "Replace" : (root.subjectSaved ? "Save" : "Capture")
            bordered: true
            fontSize: Style.font.bodySmall
            foreground: root.bar ? root.bar.foreground : Color.foreground
            enabled: !root.busy && nameField.text.trim() !== ""
            onClicked: root.saveSubject()
          }
        }

        // The fifteen (prd.md F6). Clicking the one already chosen clears it, so
        // "no icon" needs no cell of its own.
        Grid {
          width: parent.width
          visible: panelColumn.editing
          columns: 8
          spacing: Style.space(2)

          Repeater {
            model: root.iconChoices

            Button {
              required property var modelData

              iconText: modelData.glyph
              tooltipText: modelData.name
              selected: root.pickedIcon === modelData.glyph
              foreground: root.bar ? root.bar.foreground : Color.foreground
              enabled: !root.busy
              onClicked: root.pickedIcon = selected ? "" : modelData.glyph
            }
          }
        }

        Row {
          width: parent.width
          spacing: Style.space(6)
          visible: panelColumn.editing && root.subjectSaved

          Button {
            text: "Open"
            bordered: true
            fontSize: Style.font.bodySmall
            foreground: root.bar ? root.bar.foreground : Color.foreground
            enabled: !root.busy
            onClicked: root.openSaved(root.subject)
          }

          Button {
            // Named for the damage it does: this is the one that throws away the
            // apps on disk for whatever is open now.
            text: "Re-capture"
            bordered: true
            fontSize: Style.font.bodySmall
            foreground: root.bar ? root.bar.foreground : Color.foreground
            enabled: !root.busy && nameField.text.trim() !== ""
            onClicked: root.recaptureSubject()
          }

          Button {
            // Asked for twice, and the button is where it is asked: a dialog
            // for this would be a second surface for a one-word question.
            text: root.deletePending ? "Delete?" : "Delete"
            bordered: true
            fontSize: Style.font.bodySmall
            foreground: root.deletePending
              ? (root.bar ? root.bar.urgent : Color.urgent)
              : (root.bar ? root.bar.foreground : Color.foreground)
            enabled: !root.busy
            onClicked: root.deleteSubject()
          }
        }

        Text {
          width: parent.width
          text: {
            if (root.panelStatus !== "") return root.panelStatus
            if (root.busy) return "Working…"
            if (root.scratch) return "Workspace " + root.numberText + " is never saved"
            if (!root.subjectSaved) {
              return root.subject === root.index
                ? "Capture takes the " + root.windows.length + " window"
                  + (root.windows.length === 1 ? "" : "s") + " open here"
                : "Workspace " + root.subjectNumber + " has nothing saved"
            }
            return "Save writes the name and icon only"
          }
          color: Color.muted
          font.family: root.bar ? root.bar.fontFamily : Style.font.family
          font.pixelSize: Style.font.bodySmall
          wrapMode: Text.WordWrap
        }

        PanelSeparator { width: parent.width }

        PanelSectionHeader {
          width: parent.width
          text: root.scratch ? "WORKSPACES" : "WORKSPACES — PICK ONE TO EDIT"
          foreground: root.bar ? root.bar.foreground : Color.foreground
          fontFamily: root.bar ? root.bar.fontFamily : Style.font.family
        }

        Text {
          width: parent.width
          visible: root.slots.length === 0
          text: root.service && root.service.slotsLoaded ? "Could not read the store" : "Reading…"
          color: Color.muted
          font.family: root.bar ? root.bar.fontFamily : Style.font.family
          font.pixelSize: Style.font.bodySmall
        }

        // All ten, empties included. A workspace holds one configuration or none,
        // so this is the whole map: what each number is for, which are free, and
        // the only way to reach one whose tab is off the bar while it is empty.
        Repeater {
          model: root.slots

          Item {
            id: savedRow
            required property var modelData

            readonly property bool occupied: savedRow.modelData.name !== ""
            readonly property bool current: savedRow.modelData.index === root.subject

            width: panelColumn.width
            height: rowButton.implicitHeight

            Button {
              id: rowButton
              width: parent.width
              leftAlign: true
              iconText: savedRow.modelData.icon || ""
              // The number leads: it is what the Omarchy bind reaches, and on an
              // empty row it is the whole of what there is to say.
              text: (savedRow.modelData.index === 10 ? "0" : savedRow.modelData.index)
                + "   " + (savedRow.occupied ? savedRow.modelData.name : "—")
              foreground: root.bar ? root.bar.foreground : Color.foreground
              opacity: savedRow.occupied ? 1 : 0.55
              selected: savedRow.current && !root.scratch
              // An empty row is still worth picking: capture is how it stops being
              // empty. On a scratch tab, which never writes, a row only opens.
              enabled: !root.busy && (!root.scratch || savedRow.occupied)
              onClicked: root.scratch
                ? root.openSaved(savedRow.modelData.index)
                : root.selectSubject(savedRow.modelData.index)
            }

            Text {
              anchors.right: parent.right
              anchors.rightMargin: Style.space(10)
              anchors.verticalCenter: parent.verticalCenter
              // Descriptive only — the bind belongs to Omarchy (prd.md F6).
              text: savedRow.occupied ? (savedRow.modelData.shortcut || "") : ""
              color: Color.muted
              font.family: root.bar ? root.bar.fontFamily : Style.font.family
              font.pixelSize: Style.font.caption
            }
          }
        }
      }
    }
  }
}
