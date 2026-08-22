import QtQuick
import QtQuick.Layouts
import Quickshell

// F1 · Workspace preview panel: every workspace and the windows open in it
// (icon, app name, window title) — not thumbnails, see prd.md F1.
Scope {
    id: panel

    property var shell: null
    property var workspaces: []

    RowLayout {
        spacing: 8

        Repeater {
            model: panel.workspaces

            ColumnLayout {
                Text { text: modelData.name; font.bold: true }

                Repeater {
                    model: modelData.windows

                    Text { text: modelData.title }
                }
            }
        }
    }
}
