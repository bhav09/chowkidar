"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.registerCommands = registerCommands;
const vscode = __importStar(require("vscode"));
const chowkidarBridge_1 = require("./chowkidarBridge");
const diagnostics_1 = require("./diagnostics");
const statusBar_1 = require("./statusBar");
function requireCli() {
    if (!(0, chowkidarBridge_1.findChowkidar)()) {
        vscode.window
            .showWarningMessage("Chowkidar CLI is not installed.", "Install Now")
            .then((choice) => {
            if (choice === "Install Now") {
                const terminal = vscode.window.createTerminal("Chowkidar Install");
                terminal.show();
                terminal.sendText("pip install chowkidar && chowkidar setup --skip-slm");
            }
        });
        return false;
    }
    return true;
}
function registerCommands(context) {
    context.subscriptions.push(vscode.commands.registerCommand("chowkidar.sync", cmdSync), vscode.commands.registerCommand("chowkidar.check", cmdCheck), vscode.commands.registerCommand("chowkidar.report", cmdReport), vscode.commands.registerCommand("chowkidar.fixAll", cmdFixAll), vscode.commands.registerCommand("chowkidar.refresh", cmdRefresh), vscode.commands.registerCommand("chowkidar.muteWorkspace", cmdMuteWorkspace), vscode.commands.registerCommand("chowkidar.unmuteWorkspace", cmdUnmuteWorkspace));
}
async function cmdSync() {
    if (!requireCli())
        return;
    await vscode.window.withProgress({
        location: vscode.ProgressLocation.Notification,
        title: "Chowkidar: Syncing deprecation registry…",
        cancellable: false,
    }, async () => {
        try {
            const output = await (0, chowkidarBridge_1.runSync)();
            vscode.window.showInformationMessage("Chowkidar: Registry synced.");
            await (0, diagnostics_1.refreshAllDiagnostics)();
            await (0, statusBar_1.updateStatusBar)();
        }
        catch (e) {
            vscode.window.showErrorMessage(`Chowkidar sync failed: ${e.message}`);
        }
    });
}
async function cmdCheck() {
    if (!requireCli())
        return;
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
    if (!workspaceFolder) {
        vscode.window.showWarningMessage("No workspace folder open.");
        return;
    }
    await vscode.window.withProgress({
        location: vscode.ProgressLocation.Notification,
        title: "Chowkidar: Checking project…",
        cancellable: false,
    }, async () => {
        try {
            const output = await (0, chowkidarBridge_1.runCheck)(workspaceFolder);
            const doc = await vscode.workspace.openTextDocument({
                content: output,
                language: "plaintext",
            });
            vscode.window.showTextDocument(doc);
        }
        catch (e) {
            vscode.window.showErrorMessage(`Chowkidar check failed: ${e.message}`);
        }
    });
}
async function cmdReport() {
    if (!requireCli())
        return;
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
    if (!workspaceFolder) {
        vscode.window.showWarningMessage("No workspace folder open.");
        return;
    }
    const format = await vscode.window.showQuickPick(["html", "markdown", "json"], { placeHolder: "Select report format" });
    if (!format)
        return;
    await vscode.window.withProgress({
        location: vscode.ProgressLocation.Notification,
        title: "Chowkidar: Generating report…",
        cancellable: false,
    }, async () => {
        try {
            const reportData = await (0, chowkidarBridge_1.runReport)(workspaceFolder);
            const content = JSON.stringify(reportData, null, 2);
            const lang = format === "html" ? "html" : format === "json" ? "json" : "markdown";
            const doc = await vscode.workspace.openTextDocument({
                content: content,
                language: lang,
            });
            vscode.window.showTextDocument(doc);
        }
        catch (e) {
            vscode.window.showErrorMessage(`Chowkidar report failed: ${e.message}`);
        }
    });
}
async function cmdFixAll() {
    if (!requireCli())
        return;
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
    if (!workspaceFolder) {
        vscode.window.showWarningMessage("No workspace folder open.");
        return;
    }
    const confirm = await vscode.window.showWarningMessage("This will update all deprecated models in .env files. Continue?", { modal: true }, "Fix All");
    if (confirm !== "Fix All")
        return;
    await vscode.window.withProgress({
        location: vscode.ProgressLocation.Notification,
        title: "Chowkidar: Fixing deprecated models…",
        cancellable: false,
    }, async () => {
        try {
            const output = await (0, chowkidarBridge_1.runFix)(workspaceFolder);
            vscode.window.showInformationMessage("Chowkidar: Fixes applied.");
            await (0, diagnostics_1.refreshAllDiagnostics)();
            await (0, statusBar_1.updateStatusBar)();
        }
        catch (e) {
            vscode.window.showErrorMessage(`Chowkidar fix failed: ${e.message}`);
        }
    });
}
async function cmdRefresh() {
    if (!requireCli())
        return;
    await (0, diagnostics_1.refreshAllDiagnostics)();
    await (0, statusBar_1.updateStatusBar)();
    vscode.window.showInformationMessage("Chowkidar: Diagnostics refreshed.");
}
async function cmdMuteWorkspace() {
    if (!requireCli())
        return;
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
    if (!workspaceFolder) {
        vscode.window.showWarningMessage("No workspace folder open.");
        return;
    }
    await vscode.window.withProgress({
        location: vscode.ProgressLocation.Notification,
        title: "Chowkidar: Muting Workspace…",
        cancellable: false,
    }, async () => {
        try {
            const { runMute } = await Promise.resolve().then(() => __importStar(require("./chowkidarBridge")));
            await runMute(workspaceFolder);
            vscode.window.showInformationMessage("Chowkidar: Workspace muted successfully.");
            await (0, diagnostics_1.refreshAllDiagnostics)();
        }
        catch (e) {
            vscode.window.showErrorMessage(`Mute failed: ${e.message}`);
        }
    });
}
async function cmdUnmuteWorkspace() {
    if (!requireCli())
        return;
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
    if (!workspaceFolder) {
        vscode.window.showWarningMessage("No workspace folder open.");
        return;
    }
    await vscode.window.withProgress({
        location: vscode.ProgressLocation.Notification,
        title: "Chowkidar: Unmuting Workspace…",
        cancellable: false,
    }, async () => {
        try {
            const { runUnmute } = await Promise.resolve().then(() => __importStar(require("./chowkidarBridge")));
            await runUnmute(workspaceFolder);
            vscode.window.showInformationMessage("Chowkidar: Workspace unmuted successfully.");
            await (0, diagnostics_1.refreshAllDiagnostics)();
        }
        catch (e) {
            vscode.window.showErrorMessage(`Unmute failed: ${e.message}`);
        }
    });
}
//# sourceMappingURL=commands.js.map