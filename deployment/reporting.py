from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
import re

from deployment.models import DeploymentReport
from qa_bot.security import redact

REPORT_RE = re.compile(r"^deployment-report-\d{8}-\d{6}\.(md|json)$")


class DeploymentReportStorage:
    def __init__(self, directory: Path) -> None:
        self.directory = directory.resolve()

    def save(self, report: DeploymentReport) -> tuple[Path, Path]:
        self.directory.mkdir(parents=True, exist_ok=True)
        stamp = (report.finished_at or report.started_at).strftime("%Y%m%d-%H%M%S")
        markdown = self.directory / f"deployment-report-{stamp}.md"
        json_path = self.directory / f"deployment-report-{stamp}.json"
        markdown.write_text(markdown_report(report), encoding="utf-8")
        json_path.write_text(json_report(report), encoding="utf-8")
        return markdown, json_path

    def reports(self) -> list[Path]:
        if not self.directory.exists():
            return []
        return sorted((path for path in self.directory.iterdir() if path.is_file() and REPORT_RE.fullmatch(path.name)), key=lambda item: item.stat().st_mtime, reverse=True)

    def latest(self) -> Path | None:
        return next((path for path in self.reports() if path.suffix == ".md"), None)


def markdown_report(report: DeploymentReport) -> str:
    finished = report.finished_at or report.started_at
    duration = (finished - report.started_at).total_seconds()
    lines = ["# Crypto Hunter Deployment Report", "", f"- Branch: {redact(report.branch)}", f"- Old commit: {redact(report.old_commit)}", f"- New commit: {redact(report.new_commit)}", f"- Status: {report.status.value}", f"- Started: {report.started_at.isoformat()}", f"- Finished: {finished.isoformat()}", f"- Duration: {duration:.2f}s", "", "## Stages", "", "| Stage | Result | Summary | Duration |", "| --- | --- | --- | ---: |"]
    lines.extend(f"| {redact(stage.name)} | {'passed' if stage.passed else 'failed'} | {redact(stage.summary)} | {stage.duration_seconds:.2f}s |" for stage in report.stages)
    lines.extend(["", "## Post-deployment", "", f"- Health: {report.health.status.value if report.health else 'not_run'}", f"- Smoke E2E: {redact(report.smoke_e2e)}", f"- Full E2E: {redact(report.full_e2e)}", f"- Rollback: {redact(report.rollback)}"])
    if report.error:
        lines.extend(["", "## Safe error summary", "", redact(report.error)])
    return redact("\n".join(lines))


def json_report(report: DeploymentReport) -> str:
    return json.dumps(_sanitize(asdict(report)), ensure_ascii=False, indent=2, default=_default)


def _sanitize(value):
    if isinstance(value, dict): return {str(key): _sanitize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)): return [_sanitize(item) for item in value]
    if isinstance(value, str): return redact(value)
    return value


def _default(value: object) -> str:
    return value.isoformat() if isinstance(value, datetime) else str(value)
