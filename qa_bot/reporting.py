from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import json

from qa_bot.models import RunReport, ScenarioResult, Status
from qa_bot.security import redact


def telegram_summary(report: RunReport) -> str:
    duration = (report.finished_at - report.started_at).total_seconds()
    return "\n".join((
        "🧪 Crypto Hunter QA complete", "", f"Commit: {report.commit}", f"Suite: {report.run_type}", f"Duration: {duration:.1f}s", "",
        f"✅ Passed: {report.count(Status.PASSED)}", f"❌ Failed: {report.count(Status.FAILED)}", f"⚠️ Errors: {report.count(Status.ERROR)}", f"⏭ Skipped: {report.count(Status.SKIPPED)}", f"⛔ Cancelled: {report.count(Status.CANCELLED)}",
    ))


def markdown_report(report: RunReport) -> str:
    duration = (report.finished_at - report.started_at).total_seconds()
    lines = ["# Crypto Hunter QA Report", "", f"- Branch: {report.branch}", f"- Commit: {report.commit}", f"- Run type: {report.run_type}", f"- Environment: {redact(report.environment)}", f"- Started: {report.started_at.isoformat()}", f"- Finished: {report.finished_at.isoformat()}", f"- Duration: {duration:.2f}s", "", "## Summary", "", "| Status | Count |", "| --- | ---: |"]
    lines.extend(f"| {status.value} | {report.count(status)} |" for status in Status)
    lines.extend(["", "## Scenarios", "", "| Scenario | Suite | Status | Severity | Duration |", "| --- | --- | --- | --- | ---: |"])
    lines.extend(f"| {redact(item.title)} | {item.suite} | {item.status.value} | {item.severity.value} | {item.duration:.2f}s |" for item in report.results)
    failures = [item for item in report.results if item.status in {Status.FAILED, Status.ERROR}]
    if failures:
        lines.extend(["", "## Detailed failures", ""])
        for item in failures:
            lines.append(format_bug_report(item, report))
    lines.extend(["", "## Known limitations", "", "This internal runner exercises application services and mocked Telegram interactions. It does not act as a Telegram user or click the production bot."])
    return redact("\n".join(lines))


def json_report(report: RunReport) -> str:
    payload = _sanitize(asdict(report))
    return json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default)


def format_bug_report(result: ScenarioResult, report: RunReport) -> str:
    steps = result.reproduction_steps or ("Run the named QA scenario.",)
    return "\n".join((
        f"### [QA][{result.suite}] {result.title}", "", "#### Environment", f"- Branch: {report.branch}", f"- Commit: {report.commit}", f"- Platform: {report.environment}", f"- Run type: {report.run_type}", "", "#### Severity", result.severity.value.title(), "", "#### Steps to reproduce", *(f"{i}. {redact(step)}" for i, step in enumerate(steps, 1)), "", "#### Expected", redact(result.expected), "", "#### Actual", redact(result.actual), "", "#### Evidence", redact("; ".join(result.evidence) or result.assertion_details or "No additional evidence"), "", "#### Suspected area", ", ".join(result.related_modules) or "Unknown", "", "#### Recommended investigation", redact(result.recommended_investigation), "",
    ))


def codex_prompt(report: RunReport) -> str:
    failures = [item for item in report.results if item.status in {Status.FAILED, Status.ERROR}]
    lines = ["# Crypto Hunter verified QA failures", "", f"Branch: `{report.branch}`", f"Commit: `{report.commit}`", "", "Inspect the current repository state and preserve unrelated work. Fix only the verified failures below, add regression tests, run the full suite, do not read or modify the real `.env` or database, do not launch polling, and do not change Task Scheduler. Commit and push safely only after verification.", ""]
    if not failures:
        lines.append("No failed scenarios were recorded in the latest report.")
    for item in failures:
        lines.extend((f"## {item.title}", f"- Severity: {item.severity.value}", f"- Expected: {redact(item.expected)}", f"- Actual: {redact(item.actual)}", f"- Suspected modules: {', '.join(item.related_modules) or 'unknown'}", "- Reproduction:", *(f"  {i}. {redact(step)}" for i, step in enumerate(item.reproduction_steps or ("Run the scenario.",), 1)), ""))
    return redact("\n".join(lines))


def _json_default(value: object) -> str:
    return value.isoformat() if isinstance(value, datetime) else str(value)


def _sanitize(value):
    if isinstance(value, dict):
        return {str(key): _sanitize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize(item) for item in value]
    if isinstance(value, str):
        return redact(value)
    return value
