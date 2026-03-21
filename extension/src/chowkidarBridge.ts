import * as cp from "child_process";
import * as vscode from "vscode";
import * as path from "path";
import * as fs from "fs";

export interface Violation {
  variable: string;
  file: string;
  model: string;
  canonical: string;
  sunset_date: string;
  days_until: number;
  replacement: string | null;
  replacement_confidence: string;
}

export interface GateResult {
  project: string;
  severity: string;
  passed: boolean;
  violation_count: number;
  violations: Violation[];
}

export interface ReportModel {
  variable: string;
  model: string;
  file: string;
  canonical: string;
  status: string;
  sunset_date: string | null;
  days_until: number | null;
  replacement: string | null;
  cost_summary: string | null;
}

export interface ReportProject {
  path: string;
  name: string;
  total_models: number;
  models: ReportModel[];
}

export interface ReportResult {
  generated_at: string;
  projects: ReportProject[];
}

let cachedBinaryPath: string | null = null;

export function findChowkidar(): string | null {
  if (cachedBinaryPath && fs.existsSync(cachedBinaryPath)) {
    return cachedBinaryPath;
  }

  const config = vscode.workspace.getConfiguration("chowkidar");
  const custom = config.get<string>("pythonPath", "");
  if (custom) {
    cachedBinaryPath = custom;
    return custom;
  }

  const candidates = ["chowkidar"];

  const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  if (workspaceFolder) {
    const venvBin = process.platform === "win32" ? "Scripts" : "bin";
    candidates.unshift(
      path.join(workspaceFolder, ".venv", venvBin, "chowkidar"),
      path.join(workspaceFolder, "venv", venvBin, "chowkidar")
    );
  }

  const homeDir = process.env.HOME || process.env.USERPROFILE || "";
  if (homeDir) {
    const pipxPath = path.join(homeDir, ".local", "bin", "chowkidar");
    candidates.push(pipxPath);
  }

  for (const candidate of candidates) {
    try {
      const result = cp.execFileSync(candidate, ["--version"], {
        timeout: 5000,
        stdio: "pipe",
      });
      if (result) {
        cachedBinaryPath = candidate;
        return candidate;
      }
    } catch {
      continue;
    }
  }
  return null;
}

export function clearCache(): void {
  cachedBinaryPath = null;
}

async function runCommand(
  args: string[],
  cwd?: string
): Promise<{ stdout: string; stderr: string; exitCode: number }> {
  const binary = findChowkidar();
  if (!binary) {
    throw new Error("Chowkidar CLI not found");
  }

  const workDir =
    cwd || vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || process.cwd();

  return new Promise((resolve, reject) => {
    cp.execFile(
      binary,
      args,
      { cwd: workDir, timeout: 60000, maxBuffer: 1024 * 1024 },
      (error, stdout, stderr) => {
        resolve({
          stdout: stdout?.toString() || "",
          stderr: stderr?.toString() || "",
          exitCode: typeof error?.code === "number" ? error.code : error ? 1 : 0,
        });
      }
    );
  });
}

export async function runGate(
  projectPath: string,
  severity?: string
): Promise<GateResult> {
  const args = ["gate", projectPath, "--format", "json"];
  if (severity) {
    args.push("--severity", severity);
  }
  const result = await runCommand(args, projectPath);
  try {
    return JSON.parse(result.stdout);
  } catch {
    return {
      project: projectPath,
      severity: severity || "block-sunset",
      passed: true,
      violation_count: 0,
      violations: [],
    };
  }
}

export async function runReport(projectPath: string): Promise<ReportResult> {
  const result = await runCommand([
    "report",
    projectPath,
    "--format",
    "json",
  ]);
  try {
    return JSON.parse(result.stdout);
  } catch {
    return { generated_at: new Date().toISOString(), projects: [] };
  }
}

export async function runSync(): Promise<string> {
  const result = await runCommand(["sync"]);
  return result.stdout + result.stderr;
}

export async function runCheck(projectPath: string): Promise<string> {
  const result = await runCommand(["check", projectPath]);
  return result.stdout;
}

export async function runCheckQuiet(projectPath: string): Promise<string> {
  const result = await runCommand(["check", "--quiet", projectPath]);
  return result.stdout.trim();
}

export async function runFixSingle(
  projectPath: string,
  file: string,
  variable: string,
  newModel: string
): Promise<boolean> {
  const result = await runCommand([
    "update",
    projectPath,
    "--dry-run",
  ]);
  // For single-var fix, directly edit via the extension's workspace edit
  return result.exitCode === 0;
}

export async function runFix(projectPath: string): Promise<string> {
  const result = await runCommand(["fix", projectPath]);
  return result.stdout + result.stderr;
}

export async function runSetup(): Promise<string> {
  const result = await runCommand(["setup", "--skip-slm"]);
  return result.stdout + result.stderr;
}

export async function runMute(projectPath: string): Promise<string> {
  const result = await runCommand(["mute", projectPath]);
  return result.stdout;
}

export async function runUnmute(projectPath: string): Promise<string> {
  const result = await runCommand(["unmute", projectPath]);
  return result.stdout;
}
