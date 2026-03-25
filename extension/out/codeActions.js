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
exports.ChowkidarCodeActionProvider = void 0;
exports.registerCodeActions = registerCodeActions;
const vscode = __importStar(require("vscode"));
class ChowkidarCodeActionProvider {
    provideCodeActions(document, range, context) {
        const actions = [];
        for (const diag of context.diagnostics) {
            if (diag.source !== "Chowkidar") {
                continue;
            }
            const violation = diag
                .chowkidarViolation;
            if (!violation || !violation.replacement) {
                continue;
            }
            const fix = new vscode.CodeAction(`Replace "${violation.model}" with "${violation.replacement}"`, vscode.CodeActionKind.QuickFix);
            fix.edit = new vscode.WorkspaceEdit();
            fix.edit.replace(document.uri, diag.range, violation.replacement);
            fix.diagnostics = [diag];
            fix.isPreferred = true;
            actions.push(fix);
        }
        return actions;
    }
}
exports.ChowkidarCodeActionProvider = ChowkidarCodeActionProvider;
ChowkidarCodeActionProvider.providedCodeActionKinds = [vscode.CodeActionKind.QuickFix];
function registerCodeActions(context) {
    return vscode.languages.registerCodeActionsProvider({ pattern: "**/.env*" }, new ChowkidarCodeActionProvider(), { providedCodeActionKinds: ChowkidarCodeActionProvider.providedCodeActionKinds });
}
//# sourceMappingURL=codeActions.js.map