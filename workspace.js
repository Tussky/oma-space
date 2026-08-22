// oma-space · workspace definition data model
// JSON on disk, Workspace in memory. Nothing here throws — prd.md constraint 2.

const LAYOUTS = ["dwindle", "master", "monocle", "scrolling"];
const DEFAULT_LAYOUT = "dwindle";
const WORKSPACE_COUNT = 10;

function shortcutForIndex(index) {
	if (!Number.isInteger(index) || index < 1 || index > WORKSPACE_COUNT) return null;
	return `Super+${index % 10}`;
}

function isFraction(n) {
	return typeof n === "number" && n > 0 && n <= 1;
}

class WorkspaceApp {
	constructor(opts = {}) {
		this.exec = opts.exec ?? "";
		this.matchClass = opts.matchClass ?? ""; // Hyprland window class, not the command
		this.cwd = opts.cwd ?? null;
		this.floating = opts.floating ?? false;
		this.fullscreen = opts.fullscreen ?? false;
		this.size = opts.size ?? null; // [w, h] as fractions of usable workspace area
	}

	// A bare string is shorthand for exec, assuming the class matches it. Capture
	// should always write both fields; the assumption is often wrong.
	static from(value) {
		if (value instanceof WorkspaceApp) return value;
		if (typeof value === "string") return new WorkspaceApp({ exec: value, matchClass: value });
		return new WorkspaceApp(value ?? {});
	}

	validate() {
		const errors = [];
		if (!this.exec) errors.push("app is missing an exec line");
		if (!this.matchClass) errors.push(`app "${this.exec}" is missing matchClass`);
		if (this.size !== null && !(Array.isArray(this.size) && this.size.length === 2 && this.size.every(isFraction))) {
			errors.push(`app "${this.exec}" size must be [w, h] fractions in (0, 1]`);
		}
		return errors;
	}

	toJSON() {
		return {
			exec: this.exec,
			matchClass: this.matchClass,
			cwd: this.cwd,
			floating: this.floating,
			fullscreen: this.fullscreen,
			size: this.size,
		};
	}
}

class Workspace {
	constructor(opts = {}) {
		this.index = opts.index ?? null; // the Omarchy workspace this hooks onto, 1–10
		this.name = opts.name ?? "";
		this.icon = opts.icon ?? "";
		this.layout = opts.layout ?? DEFAULT_LAYOUT;
		this.shortcut = opts.shortcut ?? shortcutForIndex(this.index); // reference only
		this.apps = (opts.apps ?? []).map(WorkspaceApp.from);
	}

	validate() {
		const errors = [];
		if (!this.name) errors.push("workspace has no name");
		if (!Number.isInteger(this.index) || this.index < 1 || this.index > WORKSPACE_COUNT) {
			errors.push(`workspace "${this.name}" must hook onto an Omarchy workspace 1–${WORKSPACE_COUNT}, got ${this.index}`);
		}
		if (!LAYOUTS.includes(this.layout)) {
			errors.push(`workspace "${this.name}" has unknown layout "${this.layout}"; expected one of ${LAYOUTS.join(", ")}`);
		}
		for (const app of this.apps) errors.push(...app.validate());
		return errors;
	}

	get isValid() {
		return this.validate().length === 0;
	}

	// Returns { workspace, errors }; workspace is null only if raw isn't an object.
	static fromJSON(raw) {
		let data = raw;
		if (typeof raw === "string") {
			try {
				data = JSON.parse(raw);
			} catch (e) {
				return { workspace: null, errors: [`definition is not valid JSON: ${e.message}`] };
			}
		}
		if (data === null || typeof data !== "object" || Array.isArray(data)) {
			return { workspace: null, errors: ["definition is not an object"] };
		}
		const workspace = new Workspace(data);
		return { workspace, errors: workspace.validate() };
	}

	toJSON() {
		return {
			index: this.index,
			name: this.name,
			icon: this.icon,
			layout: this.layout,
			shortcut: this.shortcut,
			apps: this.apps.map((app) => app.toJSON()),
		};
	}

	// TODO: next — build a definition from live Hyprland state (prd.md F3).
	static fromCapture() {
		return new Workspace();
	}
}
