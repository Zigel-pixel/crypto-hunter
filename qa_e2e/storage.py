from __future__ import annotations

from pathlib import Path
import re

from qa_bot.models import RunReport
from qa_bot.reporting import codex_prompt, json_report, markdown_report

REPORT_RE = re.compile(r"^e2e-report-\d{8}-\d{6}\.(md|json)$")
PROMPT_RE = re.compile(r"^e2e-codex-prompt-\d{8}-\d{6}\.md$")
ARTIFACT_RE = re.compile(r"^e2e-[A-Za-z0-9_-]+-\d{8}-\d{6}\.(png|jpg|json|txt)$")


class E2EStorage:
    def __init__(self, reports_dir: Path, artifacts_dir: Path) -> None:
        self.reports_dir, self.artifacts_dir = reports_dir.resolve(), artifacts_dir.resolve()

    def save(self, report: RunReport) -> tuple[Path, Path, Path | None]:
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        stamp = report.finished_at.strftime("%Y%m%d-%H%M%S")
        markdown = self.reports_dir / f"e2e-report-{stamp}.md"
        json_path = self.reports_dir / f"e2e-report-{stamp}.json"
        markdown.write_text(_e2e_markdown(report), encoding="utf-8")
        json_path.write_text(json_report(report), encoding="utf-8")
        prompt = None
        if any(item.status.value in {"failed", "error"} for item in report.results):
            prompt = self.reports_dir / f"e2e-codex-prompt-{stamp}.md"
            prompt.write_text(codex_prompt(report), encoding="utf-8")
        return markdown, json_path, prompt

    def reports(self) -> list[Path]:
        return self._list(self.reports_dir, (REPORT_RE, PROMPT_RE))

    def last_report(self) -> Path | None:
        return next((path for path in self.reports() if REPORT_RE.fullmatch(path.name) and path.suffix == ".md"), None)

    def artifact_summaries(self) -> tuple[str, ...]:
        return tuple(f"{path.name} · {path.stat().st_size} bytes" for path in self._list(self.artifacts_dir, (ARTIFACT_RE,)))

    def clear_reports(self) -> int:
        return self._clear(self.reports_dir, (REPORT_RE, PROMPT_RE))

    def clear_artifacts(self) -> int:
        return self._clear(self.artifacts_dir, (ARTIFACT_RE,))

    @staticmethod
    def _list(directory: Path, patterns: tuple[re.Pattern[str], ...]) -> list[Path]:
        if not directory.exists(): return []
        return sorted((path for path in directory.iterdir() if path.is_file() and any(pattern.fullmatch(path.name) for pattern in patterns)), key=lambda path: path.stat().st_mtime, reverse=True)

    @classmethod
    def _clear(cls, directory: Path, patterns: tuple[re.Pattern[str], ...]) -> int:
        files = cls._list(directory, patterns)
        for path in files: path.unlink()
        return len(files)

    @staticmethod
    def safe_filename(name: str, patterns: tuple[re.Pattern[str], ...]) -> str:
        if Path(name).name != name or not any(pattern.fullmatch(name) for pattern in patterns):
            raise ValueError("Unsafe E2E filename")
        return name


def _e2e_markdown(report: RunReport) -> str:
    text = markdown_report(report)
    return text.replace("# Crypto Hunter QA Report", "# Crypto Hunter Telegram E2E Report", 1).replace("This internal runner exercises application services and mocked Telegram interactions. It does not act as a Telegram user or click the production bot.", "This run interacted with the configured production bot through a dedicated Telethon user session. Public-provider and Telegram conditions can affect timings.")
