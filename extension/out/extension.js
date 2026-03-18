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
exports.activate = activate;
exports.deactivate = deactivate;
const vscode = __importStar(require("vscode"));
const chowkidarBridge_1 = require("./chowkidarBridge");
const diagnostics_1 = require("./diagnostics");
const codeActions_1 = require("./codeActions");
const statusBar_1 = require("./statusBar");
const commands_1 = require("./commands");
const sidebarProvider_1 = require("./sidebarProvider");
function activate(context) {
    const diagnostics = (0, diagnostics_1.createDiagnosticCollection)();
    context.subscriptions.push(diagnostics);
    const statusBar = (0, statusBar_1.createStatusBar)();
    context.subscriptions.push(statusBar);
    const sidebarProvider = new sidebarProvider_1.ChowkidarSidebarProvider(context.extensionUri);
    context.subscriptions.push(vscode.window.registerWebviewViewProvider(sidebarProvider_1.ChowkidarSidebarProvider.viewType, sidebarProvider));
    context.subscriptions.push((0, codeActions_1.registerCodeActions)(context));
    (0, commands_1.registerCommands)(context);
    context.subscriptions.push(vscode.commands.registerCommand("chowkidar.showDashboard", () => {
        vscode.commands.executeCommand("chowkidar.dashboard.focus");
    }));
    context.subscriptions.push(vscode.workspace.onDidSaveTextDocument((doc) => {
        const config = vscode.workspace.getConfiguration("chowkidar");
        if (config.get("diagnosticsOnSave", true)) {
            (0, diagnostics_1.scheduleDiagnosticRefresh)(doc);
            (0, statusBar_1.updateStatusBar)();
        }
    }));
    context.subscriptions.push(vscode.workspace.onDidChangeConfiguration((e) => {
        if (e.affectsConfiguration("chowkidar")) {
            (0, chowkidarBridge_1.clearCache)();
            (0, diagnostics_1.refreshAllDiagnostics)();
            (0, statusBar_1.updateStatusBar)();
        }
    }));
    if (!(0, chowkidarBridge_1.findChowkidar)()) {
        promptInstall();
    }
    else {
        const config = vscode.workspace.getConfiguration("chowkidar");
        if (config.get("autoSyncOnStartup", false)) {
            vscode.commands.executeCommand("chowkidar.sync");
        }
        (0, diagnostics_1.refreshAllDiagnostics)();
    }
}
function promptInstall() {
    vscode.window
        .showWarningMessage("Chowkidar CLI not found. Install it to enable LLM deprecation warnings.", "Install via pip", "Install via pipx", "Configure Path")
        .then((choice) => {
        if (choice === "Install via pip") {
            const terminal = vscode.window.createTerminal("Chowkidar Install");
            terminal.show();
            terminal.sendText("pip install chowkidar && chowkidar setup --skip-slm");
        }
        else if (choice === "Install via pipx") {
            const terminal = vscode.window.createTerminal("Chowkidar Install");
            terminal.show();
            terminal.sendText("pipx install chowkidar && chowkidar setup --skip-slm");
        }
        else if (choice === "Configure Path") {
            vscode.commands.executeCommand("workbench.action.openSettings", "chowkidar.pythonPath");
        }
    });
}
function deactivate() { }
//# sourceMappingURL=extension.js.map