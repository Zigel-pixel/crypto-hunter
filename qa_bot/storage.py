from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re

from qa_bot.models import RunReport
from qa_bot.reporting import codex_prompt, json_report, markdown_report

REPORT_PATTERN = re.compile(r"^qa-report-\d{8}-\d{6}\.(md|json)$")
PROMPT_PATTERN = re.compile(r"^codex-prompt-\d{8}-\d{6}\.md$")


class ReportStorage:
    def __init__(self, directory: Path) -> None:
        self.directory = directory.resolve()

    def save(self, report: RunReport) -> tuple[Path, Path]:
        self.directory.mkdir(parents=True, exist_ok=True)
        stamp = report.finished_at.strftime("%Y%m%d-%H%M%S")
        markdown = self.directory / f"qa-report-{stamp}.md"
        json_path = self.directory / f"qa-report-{stamp}.json"
        markdown.write_text(markdown_report(report), encoding="utf-8")
        json_path.write_text(json_report(report), encoding="utf-8")
        return markdown, json_path

    def save_codex_prompt(self, report: RunReport) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / f"codex-prompt-{report.finished_at.strftime('%Y%m%d-%H%M%S')}.md"
        path.write_text(codex_prompt(report), encoding="utf-8")
        return path

    def list_reports(self) -> list[Path]:
        if not self.directory.exists():
            return []
        return sorted((path for path in self.directory.iterdir() if path.is_file() and REPORT_PATTERN.fullmatch(path.name)), key=lambda path: path.stat().st_mtime, reverse=True)

    def last_markdown(self) -> Path | None:
        return next((path for path in self.list_reports() if path.suffix == ".md"), None)

    def clear_reports(self) -> int:
        count = 0
        for path in self.list_reports():
            path.unlink()
            count += 1
        return count

    def safe_path(self, name: str) -> Path:
        if not (REPORT_PATTERN.fullmatch(name) or PROMPT_PATTERN.fullmatch(name)):
            raise ValueError("Invalid report filename")
        path = (self.directory / name).resolve()
        if path.parent != self.directory:
            raise ValueError("Report path escapes configured directory")
        return path
