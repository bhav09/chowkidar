import * as vscode from "vscode";
import { Violation } from "./chowkidarBridge";
import { getDiagnosticCollection } from "./diagnostics";

export class ChowkidarCodeActionProvider implements vscode.CodeActionProvider {
  static readonly providedCodeActionKinds = [vscode.CodeActionKind.QuickFix];

  provideCodeActions(
    document: vscode.TextDocument,
    range: vscode.Range,
    context: vscode.CodeActionContext
  ): vscode.CodeAction[] {
    const actions: vscode.CodeAction[] = [];

    for (const diag of context.diagnostics) {
      if (diag.source !== "Chowkidar") {
        continue;
      }
      const violation: Violation | undefined = (diag as any)
        .chowkidarViolation;
      if (!violation || !violation.replacement) {
        continue;
      }

      const fix = new vscode.CodeAction(
        `Replace "${violation.model}" with "${violation.replacement}"`,
        vscode.CodeActionKind.QuickFix
      );

      fix.edit = new vscode.WorkspaceEdit();
      fix.edit.replace(document.uri, diag.range, violation.replacement);
      fix.diagnostics = [diag];
      fix.isPreferred = true;
      actions.push(fix);
    }

    return actions;
  }
}

export function registerCodeActions(
  context: vscode.ExtensionContext
): vscode.Disposable {
  return vscode.languages.registerCodeActionsProvider(
    { pattern: "**/.env*" },
    new ChowkidarCodeActionProvider(),
    { providedCodeActionKinds: ChowkidarCodeActionProvider.providedCodeActionKinds }
  );
}
