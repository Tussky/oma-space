import capture
from workspace import Workspace, WorkspaceApp

def get_current_workspace():
    active = capture.hyprctl("activeworkspace")["id"]
    captured_workspace = capture.capture(active)
    return captured_workspace

def get_list_workspace_apps():
    



