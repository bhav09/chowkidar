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
exports.ChowkidarSidebarProvider = void 0;
const vscode = __importStar(require("vscode"));
const chowkidarBridge_1 = require("./chowkidarBridge");
class ChowkidarSidebarProvider {
    constructor(_extensionUri) {
        this._extensionUri = _extensionUri;
    }
    resolveWebviewView(webviewView, _context, _token) {
        this._view = webviewView;
        webviewView.webview.options = { enableScripts: true };
        webviewView.webview.onDidReceiveMessage(async (msg) => {
            switch (msg.command) {
                case "refresh":
                    await this.refresh();
                    break;
                case "sync":
                    await vscode.commands.executeCommand("chowkidar.sync");
                    await this.refresh();
                    break;
                case "fixAll":
                    await vscode.commands.executeCommand("chowkidar.fixAll");
                    await this.refresh();
                    break;
            }
        });
        this.refresh();
    }
    async refresh() {
        if (!this._view)
            return;
        if (!(0, chowkidarBridge_1.findChowkidar)()) {
            this._view.webview.html = this._getNotInstalledHtml();
            return;
        }
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
        if (!workspaceFolder) {
            this._view.webview.html = this._getNoWorkspaceHtml();
            return;
        }
        try {
            const gateResult = await (0, chowkidarBridge_1.runGate)(workspaceFolder, "block-all");
            this._view.webview.html = this._getDashboardHtml(gateResult.violations, gateResult.passed);
        }
        catch {
            this._view.webview.html = this._getErrorHtml();
        }
    }
    _getDashboardHtml(violations, passed) {
        const rows = violations
            .map((v) => {
            const statusClass = v.days_until <= 0
                ? "sunset"
                : v.days_until <= 7
                    ? "critical"
                    : v.days_until <= 30
                        ? "warning"
                        : "info";
            const statusLabel = v.days_until <= 0
                ? "SUNSET"
                : v.days_until <= 7
                    ? "CRITICAL"
                    : v.days_until <= 30
                        ? "WARNING"
                        : "DEPRECATING";
            const replacement = v.replacement
                ? `<span class="replacement">${this._esc(v.replacement)}</span>`
                : "<span class='na'>—</span>";
            return `<tr>
          <td><code>${this._esc(v.variable)}</code></td>
          <td><code>${this._esc(v.model)}</code></td>
          <td><span class="badge ${statusClass}">${statusLabel}</span></td>
          <td>${v.days_until}d</td>
          <td>${replacement}</td>
        </tr>`;
        })
            .join("\n");
        const summaryClass = passed ? "summary-ok" : "summary-warn";
        const summaryText = passed
            ? "All clear — no deprecated models found."
            : `${violations.length} model${violations.length > 1 ? "s" : ""} at risk.`;
        return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  :root {
    --bg: var(--vscode-sideBar-background);
    --fg: var(--vscode-sideBar-foreground);
    --border: var(--vscode-panel-border);
    --btn-bg: var(--vscode-button-background);
    --btn-fg: var(--vscode-button-foreground);
    --btn-hover: var(--vscode-button-hoverBackground);
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: var(--vscode-font-family);
    font-size: var(--vscode-font-size);
    color: var(--fg);
    background: var(--bg);
    padding: 12px;
  }
  h2 { font-size: 1.1em; margin-bottom: 8px; display: flex; align-items: center; gap: 6px; }
  .summary { padding: 8px 10px; border-radius: 4px; margin-bottom: 12px; font-size: 0.9em; }
  .summary-ok { background: rgba(40, 167, 69, 0.15); color: #28a745; }
  .summary-warn { background: rgba(255, 193, 7, 0.15); color: #ffc107; }
  .toolbar { display: flex; gap: 6px; margin-bottom: 12px; }
  .toolbar button {
    background: var(--btn-bg); color: var(--btn-fg); border: none;
    padding: 4px 10px; border-radius: 3px; cursor: pointer; font-size: 0.85em;
  }
  .toolbar button:hover { background: var(--btn-hover); }
  table { width: 100%; border-collapse: collapse; font-size: 0.85em; }
  th, td { padding: 5px 6px; text-align: left; border-bottom: 1px solid var(--border); }
  th { font-weight: 600; opacity: 0.7; font-size: 0.8em; text-transform: uppercase; }
  code { font-family: var(--vscode-editor-font-family); font-size: 0.95em; }
  .badge {
    display: inline-block; padding: 1px 6px; border-radius: 3px;
    font-size: 0.75em; font-weight: 700; text-transform: uppercase;
  }
  .sunset { background: rgba(220, 53, 69, 0.2); color: #dc3545; }
  .critical { background: rgba(253, 126, 20, 0.2); color: #fd7e14; }
  .warning { background: rgba(255, 193, 7, 0.2); color: #ffc107; }
  .info { background: rgba(108, 117, 125, 0.2); color: #6c757d; }
  .replacement { color: #28a745; }
  .na { opacity: 0.4; }
  .empty { text-align: center; padding: 24px 0; opacity: 0.6; }
</style>
</head>
<body>
  <h2>Chowkidar Dashboard</h2>
  <div class="summary ${summaryClass}">${summaryText}</div>
  <div class="toolbar">
    <button onclick="send('refresh')">Refresh</button>
    <button onclick="send('sync')">Sync Registry</button>
    ${!passed ? '<button onclick="send(\'fixAll\')">Fix All</button>' : ""}
  </div>
  ${violations.length > 0
            ? `<table>
    <thead><tr><th>Variable</th><th>Model</th><th>Status</th><th>Days</th><th>Replace With</th></tr></thead>
    <tbody>${rows}</tbody>
  </table>`
            : '<div class="empty">No deprecation issues found.</div>'}
  <script>
    const vscode = acquireVsCodeApi();
    function send(cmd) { vscode.postMessage({ command: cmd }); }
  </script>
</body>
</html>`;
    }
    _getNotInstalledHtml() {
        return `<!DOCTYPE html><html><body style="padding:20px;font-family:var(--vscode-font-family);color:var(--vscode-foreground);">
      <h3>Chowkidar CLI Not Found</h3>
      <p style="margin:12px 0;">Install the Chowkidar Python package to use this extension.</p>
      <button onclick="send('install')" style="padding:6px 14px;background:var(--vscode-button-background);
        color:var(--vscode-button-foreground);border:none;border-radius:3px;cursor:pointer;">
        Install Chowkidar
      </button>
      <script>
        const vscode = acquireVsCodeApi();
        function send(cmd) { vscode.postMessage({ command: cmd }); }
      </script>
    </body></html>`;
    }
    _getNoWorkspaceHtml() {
        return `<!DOCTYPE html><html><body style="padding:20px;font-family:var(--vscode-font-family);color:var(--vscode-foreground);">
      <h3>No Workspace Open</h3>
      <p>Open a project folder to use Chowkidar.</p>
    </body></html>`;
    }
    _getErrorHtml() {
        return `<!DOCTYPE html><html><body style="padding:20px;font-family:var(--vscode-font-family);color:var(--vscode-foreground);">
      <h3>Error</h3>
      <p>Could not fetch deprecation data. Try refreshing.</p>
      <button onclick="send('refresh')" style="padding:6px 14px;background:var(--vscode-button-background);
        color:var(--vscode-button-foreground);border:none;border-radius:3px;cursor:pointer;">
        Retry
      </button>
      <script>
        const vscode = acquireVsCodeApi();
        function send(cmd) { vscode.postMessage({ command: cmd }); }
      </script>
    </body></html>`;
    }
    _esc(s) {
        return s
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }
}
exports.ChowkidarSidebarProvider = ChowkidarSidebarProvider;
ChowkidarSidebarProvider.viewType = "chowkidar.dashboard";
//# sourceMappingURL=sidebarProvider.js.map