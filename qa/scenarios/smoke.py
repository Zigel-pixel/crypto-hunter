from __future__ import annotations

import importlib
import ast
import tempfile
from pathlib import Path
from unittest.mock import patch

from qa_bot.models import Scenario, Severity


async def imports_check():
    for name in ("app.utils.i18n", "app.services.asset_service", "app.services.alert_formatter", "qa_bot.main", "qa_bot.reporting"):
        importlib.import_module(name)
    for path in (Path("main.py"), *Path("app/handlers").glob("*.py")):
        ast.parse(path.read_text(encoding="utf-8"))
    return True, "Pure application and QA modules imported; startup/routers parsed without execution", ""


async def isolated_database_check():
    from app.database.database import init_db
    with tempfile.TemporaryDirectory() as directory:
        path = str(Path(directory) / "qa-isolated.db")
        with patch("app.database.database.DB_NAME", path):
            await init_db(); await init_db()
        return Path(path).exists() and Path(path).name != "crypto.db", "Temporary schema initialized twice", path.replace(directory, "<temp>")


async def qa_token_boundary_check():
    source = Path("qa_bot/main.py").read_text(encoding="utf-8") + Path("qa_bot/config.py").read_text(encoding="utf-8")
    ok = 'os.getenv("BOT_TOKEN"' not in source and "from app.utils.config import BOT_TOKEN" not in source
    return ok, "QA startup does not read main BOT_TOKEN" if ok else "QA startup references BOT_TOKEN", "Static source boundary check"


async def project_audit_check():
    oversized: list[str] = []
    for path in Path("app").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.keyword) and node.arg == "callback_data" and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str) and len(node.value.value.encode()) > 64:
                oversized.append(str(path))
    start_source = Path("app/handlers/start.py").read_text(encoding="utf-8")
    ignored = "qa/reports/" in Path(".gitignore").read_text(encoding="utf-8")
    owners = start_source.count("CommandStart()") == 1 and start_source.count('Command("restart")') == 1 and start_source.count('Command("stop")') == 1
    ok = not oversized and ignored and owners
    return ok, f"oversized={len(oversized)}, reports_ignored={ignored}, command_owners={owners}", "Static callback, Git ignore, and command-owner audit"


def scenarios():
    return (
        Scenario("smoke.imports", "Safe module imports", "smoke", "Import application and QA modules without polling.", "All modules import safely", imports_check, Severity.CRITICAL, related_modules=("main.py", "qa_bot/main.py")),
        Scenario("smoke.database", "Isolated idempotent database", "smoke", "Initialize schema in a temporary directory twice.", "Temporary database initializes idempotently", isolated_database_check, Severity.CRITICAL, related_modules=("app/database/database.py",)),
        Scenario("smoke.token_boundary", "QA token boundary", "smoke", "Ensure QA startup never reads BOT_TOKEN.", "Only QA_BOT_TOKEN is used", qa_token_boundary_check, Severity.CRITICAL, related_modules=("qa_bot/config.py", "qa_bot/main.py")),
        Scenario("smoke.project_audits", "Project safety audits", "smoke", "Audit callback lengths, generated-report ignore rules, and command owners.", "All static safety checks pass", project_audit_check, Severity.HIGH, related_modules=(".gitignore", "app/handlers/start.py")),
    )
