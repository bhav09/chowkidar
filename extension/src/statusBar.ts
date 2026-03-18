import * as vscode from "vscode";
import { runGate, findChowkidar } from "./chowkidarBridge";

let statusBarItem: vscode.StatusBarItem;

export function createStatusBar(): vscode.StatusBarItem {
  statusBarItem = vscode.window.createStatusBarItem(
    vscode.StatusBarAlignment.Right,
    100
  );
  statusBarItem.command = "chowkidar.showDashboard";
  statusBarItem.tooltip = "Chowkidar — LLM Deprecation Watchdog";
  statusBarItem.show();
  updateStatusBar();
  return statusBarItem;
}

export async function updateStatusBar(): Promise<void> {
  if (!findChowkidar()) {
    statusBarItem.text = "$(shield) Chowkidar: Not installed";
    statusBarItem.backgroundColor = new vscode.ThemeColor(
      "statusBarItem.warningBackground"
    );
    return;
  }

  const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  if (!workspaceFolder) {
    statusBarItem.text = "$(shield) Chowkidar";
    statusBarItem.backgroundColor = undefined;
    return;
  }

  try {
    const result = await runGate(workspaceFolder, "block-all");
    const count = result.violation_count;
    if (count === 0) {
      statusBarItem.text = "$(shield) Chowkidar: All clear";
      statusBarItem.backgroundColor = undefined;
    } else {
      statusBarItem.text = `$(warning) Chowkidar: ${count} model${count > 1 ? "s" : ""} at risk`;
      statusBarItem.backgroundColor = new vscode.ThemeColor(
        "statusBarItem.warningBackground"
      );
    }
  } catch {
    statusBarItem.text = "$(shield) Chowkidar";
    statusBarItem.backgroundColor = undefined;
  }
}
