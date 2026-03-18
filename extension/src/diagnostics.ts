import * as vscode from "vscode";
import { runGate, Violation, findChowkidar } from "./chowkidarBridge";

let diagnosticCollection: vscode.DiagnosticCollection;
let debounceTimer: ReturnType<typeof setTimeout> | undefined;

const DEBOUNCE_MS = 500;

export function createDiagnosticCollection(): vscode.DiagnosticCollection {
  diagnosticCollection =
    vscode.languages.createDiagnosticCollection("chowkidar");
  return diagnosticCollection;
}

export function getDiagnosticCollection(): vscode.DiagnosticCollection {
  return diagnosticCollection;
}

export function scheduleDiagnosticRefresh(document: vscode.TextDocument): void {
  if (!isEnvFile(document)) {
    return;
  }
  if (debounceTimer) {
    clearTimeout(debounceTimer);
  }
  debounceTimer = setTimeout(() => {
    refreshDiagnostics(document);
  }, DEBOUNCE_MS);
}

export async function refreshAllDiagnostics(): Promise<void> {
  if (!findChowkidar()) {
    return;
  }
  diagnosticCollection.clear();

  const envFiles = await vscode.workspace.findFiles(
    "**/.env*",
    "**/node_modules/**"
  );
  for (const uri of envFiles) {
    const doc = await vscode.workspace.openTextDocument(uri);
    if (isEnvFile(doc)) {
      await refreshDiagnostics(doc);
    }
  }
}

export async function refreshDiagnostics(
  document: vscode.TextDocument
): Promise<void> {
  if (!findChowkidar()) {
    return;
  }

  const workspaceFolder = vscode.workspace.getWorkspaceFolder(document.uri);
  if (!workspaceFolder) {
    return;
  }

  const config = vscode.workspace.getConfiguration("chowkidar");
  const severity = config.get<string>("severity", "block-all");

  let gateResult;
  try {
    gateResult = await runGate(workspaceFolder.uri.fsPath, severity);
  } catch {
    return;
  }

  const fileDiagnostics: vscode.Diagnostic[] = [];
  const text = document.getText();
  const docPath = document.uri.fsPath;

  for (const v of gateResult.violations) {
    if (!isViolationInFile(v, docPath)) {
      continue;
    }
    const range = findViolationRange(text, v);
    if (!range) {
      continue;
    }

    const diag = new vscode.Diagnostic(
      range,
      buildMessage(v),
      mapSeverity(v.days_until)
    );
    diag.source = "Chowkidar";
    diag.code = v.canonical;
    if (v.replacement) {
      diag.tags = [];
      (diag as any).chowkidarViolation = v;
    }
    fileDiagnostics.push(diag);
  }

  diagnosticCollection.set(document.uri, fileDiagnostics);
}

function isEnvFile(document: vscode.TextDocument): boolean {
  const name = document.fileName.split("/").pop() || "";
  return (
    name.startsWith(".env") &&
    !name.endsWith(".bak") &&
    !name.endsWith(".lock") &&
    !name.endsWith(".tmp")
  );
}

function isViolationInFile(v: Violation, docPath: string): boolean {
  const normViolation = v.file.replace(/\\/g, "/");
  const normDoc = docPath.replace(/\\/g, "/");
  return normDoc.endsWith(normViolation) || normViolation.endsWith(normDoc) || normViolation === normDoc;
}

function findViolationRange(
  text: string,
  v: Violation
): vscode.Range | null {
  const lines = text.split("\n");
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (line.startsWith("#") || line.trim() === "") {
      continue;
    }
    const eqIndex = line.indexOf("=");
    if (eqIndex < 0) {
      continue;
    }
    const key = line.substring(0, eqIndex).trim();
    if (key === v.variable) {
      const valueStart = eqIndex + 1;
      let value = line.substring(valueStart).trim();
      if (
        (value.startsWith('"') && value.endsWith('"')) ||
        (value.startsWith("'") && value.endsWith("'"))
      ) {
        value = value.slice(1, -1);
      }
      const modelIdx = line.indexOf(value, valueStart);
      if (modelIdx >= 0) {
        return new vscode.Range(i, modelIdx, i, modelIdx + value.length);
      }
      return new vscode.Range(i, valueStart, i, line.length);
    }
  }
  return null;
}

function buildMessage(v: Violation): string {
  const parts: string[] = [];
  if (v.days_until <= 0) {
    parts.push(`Model "${v.model}" has been sunset.`);
  } else if (v.days_until <= 7) {
    parts.push(`Model "${v.model}" sunsets in ${v.days_until} day(s)!`);
  } else if (v.days_until <= 30) {
    parts.push(
      `Model "${v.model}" is being deprecated (${v.days_until} days).`
    );
  } else {
    parts.push(
      `Model "${v.model}" has a sunset date: ${v.sunset_date} (${v.days_until}d).`
    );
  }
  if (v.replacement) {
    parts.push(`Recommended replacement: ${v.replacement}`);
  }
  return parts.join(" ");
}

function mapSeverity(daysUntil: number): vscode.DiagnosticSeverity {
  if (daysUntil <= 0) {
    return vscode.DiagnosticSeverity.Error;
  }
  if (daysUntil <= 30) {
    return vscode.DiagnosticSeverity.Warning;
  }
  return vscode.DiagnosticSeverity.Information;
}
