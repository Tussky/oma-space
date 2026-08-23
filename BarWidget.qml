import QtQuick
import Quickshell
import qs.Ui
import qs.Commons

// The active workspace on the bar; hovering it shows what is open there
// (prd.md F6, rendering the F1 list for one workspace).
//
// Nothing here parses live state — the widget reads what Service.qml holds.
BarWidget {
  id: root

  readonly property string pluginId: "io.github.teapot.oma-space"

  // The shell mounts one Service for the whole session. A bar surface exists
  // per monitor, so sharing it keeps one helper process rather than one each.
  readonly property var sharedService: bar && bar.shell && typeof bar.shell.serviceFor === "function"
    ? bar.shell.serviceFor(pluginId) : null
  readonly property var service: sharedService || ownService.item

  readonly property int activeIndex: service ? service.active : 0
  readonly property var windows: service && activeIndex > 0 ? service.windowsFor(activeIndex) : []
  readonly property string layoutName: {
    if (!service) return ""
    for (var i = 0; i < service.workspaces.length; i++) {
      if (service.workspaces[i].index === root.activeIndex) return service.workspaces[i].layout
    }
    return ""
  }

  // Codepoint rather than the glyph itself: a Private Use Area character does
  // not survive every editor and reads as a blank in a diff.
  readonly property string glyph: String(setting("icon", "")) || String.fromCodePoint(0xF0570)
  readonly property bool showNumber: setting("number", true) !== false

  property bool popupOpen: false

  // The bar hands one popout slot around and closes the last holder by name.
  // Without this it closes the card directly, breaking its binding to popupOpen.
  function close() { popupOpen = false }

  readonly property bool pointerInside: hoverArea.containsMouse || popup.containsMouse

  onPointerInsideChanged: {
    if (pointerInside) {
      closeTimer.stop()
      popupOpen = true
    } else {
      closeTimer.restart()
    }
  }

  // A gap between the widget and the popup card the cursor has to cross.
  Timer {
    id: closeTimer
    interval: 200
    onTriggered: root.popupOpen = false
  }

  onPopupOpenChanged: if (service) service.watchers += popupOpen ? 1 : -1
  Component.onDestruction: if (service && popupOpen) service.watchers -= 1

  // Only reached when the plugin is on the bar but its service kind was not
  // mounted; the widget still works, on its own helper process.
  Loader {
    id: ownService
    active: root.sharedService === null
    sourceComponent: Component { Service {} }
  }

  implicitWidth: vertical ? barSize : content.implicitWidth + Style.space(14)
  implicitHeight: vertical ? content.implicitHeight + Style.space(10) : barSize

  Grid {
    id: content
    anchors.centerIn: parent
    columns: root.vertical ? 1 : 2
    columnSpacing: Style.space(5)
    rowSpacing: Style.space(2)

    Text {
      text: root.glyph
      color: root.bar ? root.bar.barForeground : Color.foreground
      font.family: root.bar ? root.bar.fontFamily : Style.font.family
      font.pixelSize: Style.font.icon
      horizontalAlignment: Text.AlignHCenter
    }

    Text {
      visible: root.showNumber && root.activeIndex > 0
      text: root.activeIndex === 10 ? "0" : String(root.activeIndex)
      color: root.bar ? root.bar.barForeground : Color.foreground
      font.family: root.bar ? root.bar.fontFamily : Style.font.family
      font.pixelSize: Style.font.body
      horizontalAlignment: Text.AlignHCenter
    }
  }

  MouseArea {
    id: hoverArea
    anchors.fill: parent
    hoverEnabled: true
    acceptedButtons: Qt.NoButton
  }

  PopupCard {
    id: popup
    anchorItem: root
    bar: root.bar
    owner: root
    open: root.popupOpen
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
          text: root.activeIndex > 0 ? "Workspace " + root.activeIndex : "No workspace"
          color: root.bar ? root.bar.foreground : Color.foreground
          font.family: root.bar ? root.bar.fontFamily : Style.font.family
          font.pixelSize: Style.font.subtitle
          font.bold: true
        }

        Text {
          anchors.right: parent.right
          anchors.baseline: header.baseline
          text: root.layoutName
          color: Color.muted
          font.family: root.bar ? root.bar.fontFamily : Style.font.family
          font.pixelSize: Style.font.caption
        }
      }

      Text {
        width: parent.width
        visible: root.windows.length === 0
        text: root.service && !root.service.loaded ? "Reading…"
          : (root.service && root.service.lastError !== "" ? root.service.lastError : "No windows open")
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
    }
  }
}
