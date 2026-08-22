class Workspace {
	name = "coding"; // This will be displayed in the .qml
	apps = ['nvim', 'terminal', 'claude']; // Abbreviations of the apps that hyprland will open
	// TODO: Audit examine whether apps should be the entire string already, or if this name should be a dictionary key that links to an exec command 
	widget = 0; // Should be an icon 
	shortcut = "Super+1"; // The omarchy level shortcut to open the specified window


	constructor(name, apps, widget, shortcut) {
		this.name = name;
		this.apps = apps;
		this.widget = widget;
		this.shortcut = shortcut;
	}

	static fromCapture() {
		return new Item();
	}
}
