// Minimal JS-compatible file so no build step is needed. TS types are not required
// since we ship plain JS to the openvscode server extensions directory.
// eslint-disable-next-line @typescript-eslint/no-var-requires
const vscode = require('vscode');

function activate(context) {
    const config = vscode.workspace.getConfiguration();
    const target = vscode.ConfigurationTarget.Global;

    config.update('workbench.colorTheme', 'Default Dark+', target);
    config.update('editor.fontSize', 14, target);
    config.update('editor.tabSize', 4, target);
    config.update('files.autoSave', 'afterDelay', target);
    config.update('files.autoSaveDelay', 1000, target);
    config.update('update.mode', 'none', target);
    config.update('telemetry.telemetryLevel', 'off', target);
    config.update('extensions.autoCheckUpdates', false, target);
    config.update('extensions.autoUpdate', false, target);
}

function deactivate() {}

module.exports = { activate, deactivate };
