import QtQuick
import Quickshell.Io

// Holds workspace state and subscribes to Hyprland events (see prd.md
// Architecture). All capture/restore logic lives in the `oma-space` helper
// script; this only tracks state for the bar widget and panel to render.
Scope {
    id: service

    property var workspaces: []

    function refresh() {
        listWorkspaces.running = true
    }

    Process {
        id: listWorkspaces
        command: ["oma-space", "list", "--json"]
        stdout: SplitParser {
            onRead: data => {
                service.workspaces = JSON.parse(data).workspaces
            }
        }
    }
}
