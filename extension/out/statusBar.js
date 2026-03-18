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
exports.createStatusBar = createStatusBar;
exports.updateStatusBar = updateStatusBar;
const vscode = __importStar(require("vscode"));
const chowkidarBridge_1 = require("./chowkidarBridge");
let statusBarItem;
function createStatusBar() {
    statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
    statusBarItem.command = "chowkidar.showDashboard";
    statusBarItem.tooltip = "Chowkidar — LLM Deprecation Watchdog";
    statusBarItem.show();
    updateStatusBar();
    return statusBarItem;
}
async function updateStatusBar() {
    if (!(0, chowkidarBridge_1.findChowkidar)()) {
        statusBarItem.text = "$(shield) Chowkidar: Not installed";
        statusBarItem.backgroundColor = new vscode.ThemeColor("statusBarItem.warningBackground");
        return;
    }
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
    if (!workspaceFolder) {
        statusBarItem.text = "$(shield) Chowkidar";
        statusBarItem.backgroundColor = undefined;
        return;
    }
    try {
        const result = await (0, chowkidarBridge_1.runGate)(workspaceFolder, "block-all");
        const count = result.violation_count;
        if (count === 0) {
            statusBarItem.text = "$(shield) Chowkidar: All clear";
            statusBarItem.backgroundColor = undefined;
        }
        else {
            statusBarItem.text = `$(warning) Chowkidar: ${count} model${count > 1 ? "s" : ""} at risk`;
            statusBarItem.backgroundColor = new vscode.ThemeColor("statusBarItem.warningBackground");
        }
    }
    catch {
        statusBarItem.text = "$(shield) Chowkidar";
        statusBarItem.backgroundColor = undefined;
    }
}
//# sourceMappingURL=statusBar.js.map