import * as vscode from "vscode";
import { findChowkidar, clearCache } from "./chowkidarBridge";
import {
  createDiagnosticCollection,
  scheduleDiagnosticRefresh,
  refreshAllDiagnostics,
} from "./diagnostics";
import { registerCodeActions } from "./codeActions";
import { createStatusBar, updateStatusBar } from "./statusBar";
import { registerCommands } from "./commands";
import { ChowkidarSidebarProvider } from "./sidebarProvider";

export function activate(context: vscode.ExtensionContext): void {
  const diagnostics = createDiagnosticCollection();
  context.subscriptions.push(diagnostics);

  const statusBar = createStatusBar();
  context.subscriptions.push(statusBar);

  const sidebarProvider = new ChowkidarSidebarProvider(context.extensionUri);
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(
      ChowkidarSidebarProvider.viewType,
      sidebarProvider
    )
  );

  context.subscriptions.push(registerCodeActions(context));
  registerCommands(context);

  context.subscriptions.push(
    vscode.commands.registerCommand("chowkidar.showDashboard", () => {
      vscode.commands.executeCommand("chowkidar.dashboard.focus");
    })
  );

  context.subscriptions.push(
    vscode.workspace.onDidSaveTextDocument((doc) => {
      const config = vscode.workspace.getConfiguration("chowkidar");
      if (config.get<boolean>("diagnosticsOnSave", true)) {
        scheduleDiagnosticRefresh(doc);
        updateStatusBar();
      }
    })
  );

  context.subscriptions.push(
    vscode.workspace.onDidChangeConfiguration((e) => {
      if (e.affectsConfiguration("chowkidar")) {
        clearCache();
        refreshAllDiagnostics();
        updateStatusBar();
      }
    })
  );

  if (!findChowkidar()) {
    promptInstall();
  } else {
    const config = vscode.workspace.getConfiguration("chowkidar");
    if (config.get<boolean>("autoSyncOnStartup", false)) {
      vscode.commands.executeCommand("chowkidar.sync");
    }
    refreshAllDiagnostics();
  }
}

function promptInstall(): void {
  vscode.window
    .showWarningMessage(
      "Chowkidar CLI not found. Install it to enable LLM deprecation warnings.",
      "Install via pip",
      "Install via pipx",
      "Configure Path"
    )
    .then((choice) => {
      if (choice === "Install via pip") {
        const terminal = vscode.window.createTerminal("Chowkidar Install");
        terminal.show();
        terminal.sendText("pip install chowkidar && chowkidar setup --skip-slm");
      } else if (choice === "Install via pipx") {
        const terminal = vscode.window.createTerminal("Chowkidar Install");
        terminal.show();
        terminal.sendText("pipx install chowkidar && chowkidar setup --skip-slm");
      } else if (choice === "Configure Path") {
        vscode.commands.executeCommand(
          "workbench.action.openSettings",
          "chowkidar.pythonPath"
        );
      }
    });
}

export function deactivate(): void {}
