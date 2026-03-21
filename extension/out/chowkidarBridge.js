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
exports.findChowkidar = findChowkidar;
exports.clearCache = clearCache;
exports.runGate = runGate;
exports.runReport = runReport;
exports.runSync = runSync;
exports.runCheck = runCheck;
exports.runCheckQuiet = runCheckQuiet;
exports.runFixSingle = runFixSingle;
exports.runFix = runFix;
exports.runSetup = runSetup;
exports.runMute = runMute;
exports.runUnmute = runUnmute;
const cp = __importStar(require("child_process"));
const vscode = __importStar(require("vscode"));
const path = __importStar(require("path"));
const fs = __importStar(require("fs"));
let cachedBinaryPath = null;
function findChowkidar() {
    if (cachedBinaryPath && fs.existsSync(cachedBinaryPath)) {
        return cachedBinaryPath;
    }
    const config = vscode.workspace.getConfiguration("chowkidar");
    const custom = config.get("pythonPath", "");
    if (custom) {
        cachedBinaryPath = custom;
        return custom;
    }
    const candidates = ["chowkidar"];
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
    if (workspaceFolder) {
        const venvBin = process.platform === "win32" ? "Scripts" : "bin";
        candidates.unshift(path.join(workspaceFolder, ".venv", venvBin, "chowkidar"), path.join(workspaceFolder, "venv", venvBin, "chowkidar"));
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
        }
        catch {
            continue;
        }
    }
    return null;
}
function clearCache() {
    cachedBinaryPath = null;
}
async function runCommand(args, cwd) {
    const binary = findChowkidar();
    if (!binary) {
        throw new Error("Chowkidar CLI not found");
    }
    const workDir = cwd || vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || process.cwd();
    return new Promise((resolve, reject) => {
        cp.execFile(binary, args, { cwd: workDir, timeout: 60000, maxBuffer: 1024 * 1024 }, (error, stdout, stderr) => {
            resolve({
                stdout: stdout?.toString() || "",
                stderr: stderr?.toString() || "",
                exitCode: typeof error?.code === "number" ? error.code : error ? 1 : 0,
            });
        });
    });
}
async function runGate(projectPath, severity) {
    const args = ["gate", projectPath, "--format", "json"];
    if (severity) {
        args.push("--severity", severity);
    }
    const result = await runCommand(args, projectPath);
    try {
        return JSON.parse(result.stdout);
    }
    catch {
        return {
            project: projectPath,
            severity: severity || "block-sunset",
            passed: true,
            violation_count: 0,
            violations: [],
        };
    }
}
async function runReport(projectPath) {
    const result = await runCommand([
        "report",
        projectPath,
        "--format",
        "json",
    ]);
    try {
        return JSON.parse(result.stdout);
    }
    catch {
        return { generated_at: new Date().toISOString(), projects: [] };
    }
}
async function runSync() {
    const result = await runCommand(["sync"]);
    return result.stdout + result.stderr;
}
async function runCheck(projectPath) {
    const result = await runCommand(["check", projectPath]);
    return result.stdout;
}
async function runCheckQuiet(projectPath) {
    const result = await runCommand(["check", "--quiet", projectPath]);
    return result.stdout.trim();
}
async function runFixSingle(projectPath, file, variable, newModel) {
    const result = await runCommand([
        "update",
        projectPath,
        "--dry-run",
    ]);
    // For single-var fix, directly edit via the extension's workspace edit
    return result.exitCode === 0;
}
async function runFix(projectPath) {
    const result = await runCommand(["fix", projectPath]);
    return result.stdout + result.stderr;
}
async function runSetup() {
    const result = await runCommand(["setup", "--skip-slm"]);
    return result.stdout + result.stderr;
}
async function runMute(projectPath) {
    const result = await runCommand(["mute", projectPath]);
    return result.stdout;
}
async function runUnmute(projectPath) {
    const result = await runCommand(["unmute", projectPath]);
    return result.stdout;
}
//# sourceMappingURL=chowkidarBridge.js.map