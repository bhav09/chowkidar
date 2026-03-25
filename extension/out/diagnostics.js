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
exports.createDiagnosticCollection = createDiagnosticCollection;
exports.getDiagnosticCollection = getDiagnosticCollection;
exports.scheduleDiagnosticRefresh = scheduleDiagnosticRefresh;
exports.refreshAllDiagnostics = refreshAllDiagnostics;
exports.refreshDiagnostics = refreshDiagnostics;
const vscode = __importStar(require("vscode"));
const chowkidarBridge_1 = require("./chowkidarBridge");
let diagnosticCollection;
let debounceTimer;
const DEBOUNCE_MS = 500;
function createDiagnosticCollection() {
    diagnosticCollection =
        vscode.languages.createDiagnosticCollection("chowkidar");
    return diagnosticCollection;
}
function getDiagnosticCollection() {
    return diagnosticCollection;
}
function scheduleDiagnosticRefresh(document) {
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
async function refreshAllDiagnostics() {
    if (!(0, chowkidarBridge_1.findChowkidar)()) {
        return;
    }
    diagnosticCollection.clear();
    const envFiles = await vscode.workspace.findFiles("**/.env*", "**/node_modules/**");
    for (const uri of envFiles) {
        const doc = await vscode.workspace.openTextDocument(uri);
        if (isEnvFile(doc)) {
            await refreshDiagnostics(doc);
        }
    }
}
async function refreshDiagnostics(document) {
    if (!(0, chowkidarBridge_1.findChowkidar)()) {
        return;
    }
    const workspaceFolder = vscode.workspace.getWorkspaceFolder(document.uri);
    if (!workspaceFolder) {
        return;
    }
    const config = vscode.workspace.getConfiguration("chowkidar");
    const severity = config.get("severity", "block-all");
    let gateResult;
    try {
        gateResult = await (0, chowkidarBridge_1.runGate)(workspaceFolder.uri.fsPath, severity);
    }
    catch {
        return;
    }
    const fileDiagnostics = [];
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
        const diag = new vscode.Diagnostic(range, buildMessage(v), mapSeverity(v.days_until));
        diag.source = "Chowkidar";
        diag.code = v.canonical;
        if (v.replacement) {
            diag.tags = [];
            diag.chowkidarViolation = v;
        }
        fileDiagnostics.push(diag);
    }
    diagnosticCollection.set(document.uri, fileDiagnostics);
}
function isEnvFile(document) {
    const name = document.fileName.split("/").pop() || "";
    return (name.startsWith(".env") &&
        !name.endsWith(".bak") &&
        !name.endsWith(".lock") &&
        !name.endsWith(".tmp"));
}
function isViolationInFile(v, docPath) {
    const normViolation = v.file.replace(/\\/g, "/");
    const normDoc = docPath.replace(/\\/g, "/");
    return normDoc.endsWith(normViolation) || normViolation.endsWith(normDoc) || normViolation === normDoc;
}
function findViolationRange(text, v) {
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
            if ((value.startsWith('"') && value.endsWith('"')) ||
                (value.startsWith("'") && value.endsWith("'"))) {
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
function buildMessage(v) {
    const parts = [];
    if (v.days_until <= 0) {
        parts.push(`Model "${v.model}" has been sunset.`);
    }
    else if (v.days_until <= 7) {
        parts.push(`Model "${v.model}" sunsets in ${v.days_until} day(s)!`);
    }
    else if (v.days_until <= 30) {
        parts.push(`Model "${v.model}" is being deprecated (${v.days_until} days).`);
    }
    else {
        parts.push(`Model "${v.model}" has a sunset date: ${v.sunset_date} (${v.days_until}d).`);
    }
    if (v.replacement) {
        parts.push(`Recommended replacement: ${v.replacement}`);
    }
    return parts.join(" ");
}
function mapSeverity(daysUntil) {
    if (daysUntil <= 0) {
        return vscode.DiagnosticSeverity.Error;
    }
    if (daysUntil <= 30) {
        return vscode.DiagnosticSeverity.Warning;
    }
    return vscode.DiagnosticSeverity.Information;
}
//# sourceMappingURL=diagnostics.js.map