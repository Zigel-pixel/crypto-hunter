from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys

from qa_bot.reporting import telegram_summary
from qa_e2e.auth import AuthorizationError, authorize
from qa_e2e.client import TelegramE2EClient
from qa_e2e.config import E2EConfigError, load_e2e_config
from qa_e2e.runner import E2ERunner, exit_code
from qa_e2e.scenarios import build_scenarios
from qa_e2e.storage import E2EStorage
from app.utils.single_instance import InstanceAlreadyRunning, SingleInstanceLock

SUITES = ("smoke", "localization", "live", "favorites", "alerts", "ai", "wallets", "all")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="python -m qa_e2e", description="Crypto Hunter real Telegram E2E QA")
    commands = result.add_subparsers(dest="command", required=True)
    commands.add_parser("auth"); commands.add_parser("status"); commands.add_parser("list"); commands.add_parser("reports")
    run = commands.add_parser("run"); run.add_argument("suite", choices=SUITES)
    commands.add_parser("clear-reports"); commands.add_parser("clear-artifacts")
    return result


async def execute(args: argparse.Namespace) -> int:
    config = load_e2e_config()
    storage = E2EStorage(config.reports_dir, config.artifacts_dir)
    if args.command == "auth":
        success = await authorize(config)
        print("Telegram E2E authorization complete." if success else "Telegram E2E authorization did not complete.")
        return 0 if success else 1
    if args.command == "status":
        ready = await TelegramE2EClient(config).authorized()
        print("E2E enabled; local Telethon session is authorized." if ready else "E2E enabled; local console authorization is required.")
        return 0 if ready else 1
    if args.command == "list":
        client = TelegramE2EClient(config, client=object())
        print("\n".join(f"{item.id} · {item.suite} · {item.title}" for item in build_scenarios(client, config)))
        return 0
    if args.command == "reports":
        print("\n".join(path.name for path in storage.reports()) or "No E2E reports.")
        return 0
    if args.command in {"clear-reports", "clear-artifacts"}:
        answer = input(f"Type CLEAR to confirm {args.command}: ").strip()
        if answer != "CLEAR": print("Cleanup cancelled."); return 1
        count = storage.clear_reports() if args.command == "clear-reports" else storage.clear_artifacts()
        print(f"Cleared {count} generated E2E files."); return 0
    runner = E2ERunner(config)
    try:
        report = await runner.run(args.suite)
    except KeyboardInterrupt:
        await runner.cancel(); print("E2E run cancelled."); return 130
    paths = storage.save(report)
    print(telegram_summary(report))
    print("Reports:", ", ".join(path.name for path in paths if path))
    return exit_code(report)


def main(argv: list[str] | None = None) -> int:
    try:
        args = parser().parse_args(argv)
        if args.command == "run":
            with SingleInstanceLock(Path(__file__).resolve().parent.parent / ".crypto-hunter-e2e.lock"):
                return asyncio.run(execute(args))
        return asyncio.run(execute(args))
    except InstanceAlreadyRunning:
        print("Another Telegram E2E run is already active.", file=sys.stderr)
        return 3
    except (E2EConfigError, AuthorizationError) as exc:
        print(f"E2E command refused ({type(exc).__name__}).", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("E2E command cancelled.", file=sys.stderr)
        return 130
