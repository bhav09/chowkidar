"""Local deployment signal detection.

Local files can only provide evidence that a project may be deployed. A target
is confirmed only when a cloud adapter authenticates and verifies it remotely.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class DeploymentSignal:
    adapter: str
    evidence: str
    file_path: str
    strength: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DeploymentAssessment:
    state: str
    confidence: float
    signals: list[DeploymentSignal] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "state": self.state,
            "confidence": self.confidence,
            "signals": [signal.to_dict() for signal in self.signals],
        }


SIGNAL_PATTERNS: list[tuple[str, tuple[str, ...], str, int]] = [
    ("vercel", ("vercel.json", ".vercel/project.json"), "Vercel project metadata", 4),
    ("kubernetes", ("deployment.yaml", "deployment.yml", "service.yaml", "service.yml"), "Kubernetes manifest", 3),
    ("kubernetes", ("kustomization.yaml", "kustomization.yml", "Chart.yaml"), "Kubernetes Kustomize/Helm config", 3),
    ("aws", ("serverless.yml", "serverless.yaml"), "AWS/serverless deployment config", 3),
    ("gcp", ("app.yaml", "cloudbuild.yaml"), "GCP deployment config", 3),
    ("azure", ("azure-pipelines.yml", "azure-pipelines.yaml"), "Azure pipeline config", 3),
    ("docker", ("Dockerfile", "docker-compose.yml", "docker-compose.yaml"), "Container deployment config", 2),
]

CONTENT_PATTERNS: list[tuple[str, str, str, int]] = [
    ("aws", "aws secretsmanager", "AWS Secrets Manager reference", 3),
    ("aws", "ssm:", "AWS SSM reference", 3),
    ("gcp", "secretmanager.googleapis.com", "GCP Secret Manager reference", 3),
    ("azure", "keyvault", "Azure Key Vault reference", 3),
    ("kubernetes", "kind: secret", "Kubernetes Secret manifest", 4),
    ("kubernetes", "kind: configmap", "Kubernetes ConfigMap manifest", 3),
    ("vercel", "vercel --prod", "Vercel deployment workflow", 4),
]


def detect_deployment(project_path: str | Path) -> DeploymentAssessment:
    project = Path(project_path).resolve()
    signals: list[DeploymentSignal] = []

    for adapter, names, evidence, strength in SIGNAL_PATTERNS:
        for name in names:
            for path in _candidate_paths(project, name):
                if path.exists() and path.is_file():
                    signals.append(DeploymentSignal(adapter, evidence, str(path), strength))

    for path in _scannable_files(project):
        try:
            text = path.read_text(errors="ignore").lower()
        except OSError:
            continue
        for adapter, needle, evidence, strength in CONTENT_PATTERNS:
            if needle in text:
                signals.append(DeploymentSignal(adapter, evidence, str(path), strength))

    if not signals:
        return DeploymentAssessment("none", 0.0, [])

    total_strength = sum(signal.strength for signal in signals)
    confidence = min(0.95, total_strength / 10)
    state = "likely" if confidence >= 0.6 else "possible"
    return DeploymentAssessment(state, round(confidence, 2), signals)


def _candidate_paths(project: Path, name: str) -> list[Path]:
    if "/" in name:
        return [project / name]
    return [project / name, project / ".github" / "workflows" / name]


def _scannable_files(project: Path) -> list[Path]:
    skip = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build"}
    files: list[Path] = []
    for path in project.rglob("*"):
        if any(part in skip for part in path.parts):
            continue
        if path.is_file() and path.suffix.lower() in {".yml", ".yaml", ".json", ".tf", ".toml"}:
            files.append(path)
    return files
