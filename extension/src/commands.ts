import * as vscode from "vscode";
import {
  findChowkidar,
  runSync,
  runCheck,
  runFix,
  runReport,
} from "./chowkidarBridge";
import { refreshAllDiagnostics } from "./diagnostics";
import { updateStatusBar } from "./statusBar";

function requireCli(): boolean {
  if (!findChowkidar()) {
    vscode.window
      .showWarningMessage(
        "Chowkidar CLI is not installed.",
        "Install Now"
      )
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

export function registerCommands(
  context: vscode.ExtensionContext
): void {
  context.subscriptions.push(
    vscode.commands.registerCommand("chowkidar.sync", cmdSync),
    vscode.commands.registerCommand("chowkidar.check", cmdCheck),
    vscode.commands.registerCommand("chowkidar.report", cmdReport),
    vscode.commands.registerCommand("chowkidar.fixAll", cmdFixAll),
    vscode.commands.registerCommand("chowkidar.refresh", cmdRefresh)
  );
}

async function cmdSync(): Promise<void> {
  if (!requireCli()) return;

  await vscode.window.withProgress(
    {
      location: vscode.ProgressLocation.Notification,
      title: "Chowkidar: Syncing deprecation registry…",
      cancellable: false,
    },
    async () => {
      try {
        const output = await runSync();
        vscode.window.showInformationMessage("Chowkidar: Registry synced.");
        await refreshAllDiagnostics();
        await updateStatusBar();
      } catch (e: any) {
        vscode.window.showErrorMessage(
          `Chowkidar sync failed: ${e.message}`
        );
      }
    }
  );
}

async function cmdCheck(): Promise<void> {
  if (!requireCli()) return;

  const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  if (!workspaceFolder) {
    vscode.window.showWarningMessage("No workspace folder open.");
    return;
  }

  await vscode.window.withProgress(
    {
      location: vscode.ProgressLocation.Notification,
      title: "Chowkidar: Checking project…",
      cancellable: false,
    },
    async () => {
      try {
        const output = await runCheck(workspaceFolder);
        const doc = await vscode.workspace.openTextDocument({
          content: output,
          language: "plaintext",
        });
        vscode.window.showTextDocument(doc);
      } catch (e: any) {
        vscode.window.showErrorMessage(
          `Chowkidar check failed: ${e.message}`
        );
      }
    }
  );
}

async function cmdReport(): Promise<void> {
  if (!requireCli()) return;

  const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  if (!workspaceFolder) {
    vscode.window.showWarningMessage("No workspace folder open.");
    return;
  }

  const format = await vscode.window.showQuickPick(
    ["html", "markdown", "json"],
    { placeHolder: "Select report format" }
  );
  if (!format) return;

  await vscode.window.withProgress(
    {
      location: vscode.ProgressLocation.Notification,
      title: "Chowkidar: Generating report…",
      cancellable: false,
    },
    async () => {
      try {
        const reportData = await runReport(workspaceFolder);
        const content = JSON.stringify(reportData, null, 2);
        const lang = format === "html" ? "html" : format === "json" ? "json" : "markdown";
        const doc = await vscode.workspace.openTextDocument({
          content: content,
          language: lang,
        });
        vscode.window.showTextDocument(doc);
      } catch (e: any) {
        vscode.window.showErrorMessage(
          `Chowkidar report failed: ${e.message}`
        );
      }
    }
  );
}

async function cmdFixAll(): Promise<void> {
  if (!requireCli()) return;

  const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  if (!workspaceFolder) {
    vscode.window.showWarningMessage("No workspace folder open.");
    return;
  }

  const confirm = await vscode.window.showWarningMessage(
    "This will update all deprecated models in .env files. Continue?",
    { modal: true },
    "Fix All"
  );
  if (confirm !== "Fix All") return;

  await vscode.window.withProgress(
    {
      location: vscode.ProgressLocation.Notification,
      title: "Chowkidar: Fixing deprecated models…",
      cancellable: false,
    },
    async () => {
      try {
        const output = await runFix(workspaceFolder);
        vscode.window.showInformationMessage("Chowkidar: Fixes applied.");
        await refreshAllDiagnostics();
        await updateStatusBar();
      } catch (e: any) {
        vscode.window.showErrorMessage(
          `Chowkidar fix failed: ${e.message}`
        );
      }
    }
  );
}

async function cmdRefresh(): Promise<void> {
  if (!requireCli()) return;

  await refreshAllDiagnostics();
  await updateStatusBar();
  vscode.window.showInformationMessage("Chowkidar: Diagnostics refreshed.");
}
