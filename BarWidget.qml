import QtQuick
import Quickshell

// Trigger + active-workspace indicator (see prd.md F6). All parsing and
// process handling stays in the `oma-space` helper script; this only renders.
Scope {
    id: barWidget

    property var shell: null
    property string activeWorkspace: ""

    signal togglePanel()

    Rectangle {
        implicitWidth: label.implicitWidth + 16
        implicitHeight: label.implicitHeight + 8
        radius: 4
        color: "transparent"

        Text {
            id: label
            anchors.centerIn: parent
            text: barWidget.activeWorkspace.length > 0 ? barWidget.activeWorkspace : "Workspaces"
        }

        MouseArea {
            anchors.fill: parent
            onClicked: barWidget.togglePanel()
        }
    }
}
