from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from app.utils.single_instance import InstanceAlreadyRunning
from deployment.health import ProcessInfo, evaluate_health, matching_production_processes
from deployment.models import DeploymentReport, DeploymentState, DeploymentStatus, HealthStatus, RollbackResult, StageResult
from deployment.notifications import send_admin_notification
from deployment.orchestrator import DeploymentOrchestrator
from deployment.reporting import DeploymentReportStorage, json_report, markdown_report
from deployment.state import DeploymentStateStore, deployment_lock
from deployment.windows import LauncherAction, launcher_action, resolve_restore_python, select_bootstrap_python
from deployment.atomic_files import atomic_replace


class FakeOperations:
    def __init__(self, *, old="a" * 40, remote="b" * 40):
        self.old, self.remote = old, remote
        self.calls: list[str] = []
        self.candidate = (True, "compile and pytest passed")
        self.deployment = (True, "fast-forward complete")
        self.health = (True, "healthy")
        self.e2e = {"smoke": (True, "8 passed"), "all": (True, "8 passed")}
        self.rollback_result = (True, "old commit restored and healthy")
        self.validation_error: Exception | None = None
        self.branch = "feat/market-core"

    def validate(self):
        self.calls.append("validate")
        if self.validation_error: raise self.validation_error
        return self.old, self.branch
    def remote_commit(self): self.calls.append("remote"); return self.remote
    def verify_candidate(self, commit): self.calls.append("verify"); return self.candidate
    def deploy(self, commit): self.calls.append("deploy"); return self.deployment
    def restart_and_health(self): self.calls.append("restart"); return self.health
    def run_e2e(self, suite): self.calls.append(f"e2e:{suite}"); return self.e2e[suite]
    def rollback(self, commit): self.calls.append("rollback"); return self.rollback_result


class DeploymentOrchestratorTests(unittest.TestCase):
    def test_no_update_does_not_restart_or_run_e2e(self):
        operations = FakeOperations(remote="a" * 40)
        report = DeploymentOrchestrator(operations).run(DeploymentState())
        self.assertEqual(report.status, DeploymentStatus.NO_UPDATE)
        self.assertEqual(operations.calls, ["validate", "remote"])

    def test_verification_precedes_deploy_and_restart(self):
        operations = FakeOperations(); state = DeploymentState()
        report = DeploymentOrchestrator(operations).run(state)
        self.assertEqual(report.status, DeploymentStatus.DEPLOYED)
        self.assertLess(operations.calls.index("verify"), operations.calls.index("deploy"))
        self.assertLess(operations.calls.index("deploy"), operations.calls.index("restart"))

    def test_candidate_failure_preserves_running_version_and_suppresses_retry(self):
        operations = FakeOperations(); operations.candidate = (False, "pytest failed"); state = DeploymentState()
        report = DeploymentOrchestrator(operations).run(state)
        self.assertEqual(report.status, DeploymentStatus.BLOCKED)
        self.assertNotIn("deploy", operations.calls); self.assertEqual(state.failed_commit, operations.remote)
        retry = FakeOperations(); DeploymentOrchestrator(retry).run(state)
        self.assertNotIn("verify", retry.calls)

    def test_dirty_wrong_origin_and_diverged_validation_failures_are_nonfatal(self):
        for reason in ("dirty production tree", "wrong origin", "diverged history"):
            operations = FakeOperations(); operations.validation_error = RuntimeError(reason)
            report = DeploymentOrchestrator(operations).run(DeploymentState())
            self.assertEqual(report.status, DeploymentStatus.BLOCKED)
            self.assertIn(reason, report.error)
            self.assertEqual(operations.calls, ["validate"])

    def test_wrong_branch_blocks_before_remote_check(self):
        operations = FakeOperations(); operations.branch = "main"
        report = DeploymentOrchestrator(operations).run(DeploymentState())
        self.assertEqual(report.status, DeploymentStatus.BLOCKED)
        self.assertNotIn("remote", operations.calls)

    def test_dependency_compile_and_pytest_failures_never_stop_production(self):
        for reason in ("dependency install failed", "compile failed", "pytest failed", "pytest unavailable"):
            operations = FakeOperations(); operations.candidate = (False, reason)
            report = DeploymentOrchestrator(operations).run(DeploymentState())
            self.assertEqual(report.status, DeploymentStatus.BLOCKED)
            self.assertNotIn("deploy", operations.calls); self.assertNotIn("restart", operations.calls)

    def test_new_commit_clears_previous_retry_suppression(self):
        state = DeploymentState(failed_commit="b" * 40)
        operations = FakeOperations(remote="c" * 40)
        report = DeploymentOrchestrator(operations).run(state)
        self.assertEqual(report.status, DeploymentStatus.DEPLOYED); self.assertEqual(state.failed_commit, "")

    def test_health_and_smoke_failures_roll_back(self):
        for stage in ("health", "smoke"):
            operations = FakeOperations()
            if stage == "health": operations.health = (False, "failed start")
            else: operations.e2e["smoke"] = (False, "smoke failed")
            report = DeploymentOrchestrator(operations).run(DeploymentState())
            self.assertEqual(report.status, DeploymentStatus.ROLLED_BACK)
            self.assertIn("rollback", operations.calls)

    def test_full_e2e_failure_keeps_deployment_by_default(self):
        operations = FakeOperations(); operations.e2e["all"] = (False, "provider unavailable")
        report = DeploymentOrchestrator(operations).run(DeploymentState())
        self.assertEqual(report.status, DeploymentStatus.DEPLOYED_WITH_E2E_FAILURES)
        self.assertNotIn("rollback", operations.calls)

    def test_rollback_failure_is_critical(self):
        operations = FakeOperations(); operations.health = (False, "failed"); operations.rollback_result = (False, "rollback unhealthy")
        report = DeploymentOrchestrator(operations).run(DeploymentState())
        self.assertEqual(report.status, DeploymentStatus.ROLLBACK_FAILED)


class DeploymentStateTests(unittest.TestCase):
    def test_atomic_round_trip_and_corruption_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"; store = DeploymentStateStore(path)
            store.save(DeploymentState(failed_commit="abc"))
            self.assertEqual(store.load().failed_commit, "abc")
            self.assertFalse(list(Path(directory).glob("*.tmp")))
            path.write_text("not json", encoding="utf-8")
            self.assertEqual(store.load(), DeploymentState())

    def test_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(ValueError): DeploymentStateStore(root / "nested" / "state.json", root)

    def test_deployment_lock_rejects_overlap(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "deploy.lock"
            with deployment_lock(path):
                with self.assertRaises(InstanceAlreadyRunning), deployment_lock(path): pass


class AtomicFileReplacementTests(unittest.TestCase):
    def test_destination_missing_moves_and_verifies(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); temporary = root / "state.tmp"; destination = root / "state.json"
            temporary.write_text("new", encoding="utf-8")
            atomic_replace(temporary, destination)
            self.assertEqual(destination.read_text(encoding="utf-8"), "new")
            self.assertFalse(temporary.exists())

    def test_existing_destination_replaced_and_backup_cleaned(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); temporary = root / "state.tmp"; destination = root / "state.json"; backup = root / "state.json.atomic-backup"
            temporary.write_text("new", encoding="utf-8"); destination.write_text("old", encoding="utf-8"); backup.write_text("stale", encoding="utf-8")
            atomic_replace(temporary, destination)
            self.assertEqual(destination.read_text(encoding="utf-8"), "new")
            self.assertFalse(backup.exists())

    def test_missing_temporary_refuses_without_touching_original(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "state.json"; destination.write_text("old", encoding="utf-8")
            with self.assertRaises(FileNotFoundError): atomic_replace(Path(directory) / "missing.tmp", destination)
            self.assertEqual(destination.read_text(encoding="utf-8"), "old")

    def test_replacement_failure_restores_original_and_cleans_temporary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); temporary = root / "state.tmp"; destination = root / "state.json"; backup = root / "state.json.atomic-backup"
            temporary.write_text("candidate", encoding="utf-8"); destination.write_text("original", encoding="utf-8")
            def fail_after_backup(source, target, operation_backup):
                os.replace(target, operation_backup)
                raise OSError("simulated replace failure")
            with self.assertRaises(OSError): atomic_replace(temporary, destination, fail_after_backup)
            self.assertEqual(destination.read_text(encoding="utf-8"), "original")
            self.assertFalse(temporary.exists()); self.assertFalse(backup.exists())

    def test_partial_candidate_is_removed_before_original_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); temporary = root / "pointer.tmp"; destination = root / "pointer.txt"
            temporary.write_text("candidate", encoding="utf-8"); destination.write_text("previous", encoding="utf-8")
            def fail_after_candidate(source, target, backup):
                os.replace(target, backup); os.replace(source, target); raise OSError("verification failure")
            with self.assertRaises(OSError): atomic_replace(temporary, destination, fail_after_candidate)
            self.assertEqual(destination.read_text(encoding="utf-8"), "previous")


class DeploymentHealthTests(unittest.TestCase):
    def test_health_outcomes(self):
        root = Path.cwd()
        self.assertEqual(evaluate_health([], root, "").status, HealthStatus.FAILED_START)
        process = ProcessInfo(1, f"python {root}\\main.py")
        self.assertEqual(evaluate_health([process, ProcessInfo(2, process.command_line)], root, "polling").status, HealthStatus.DUPLICATE_PROCESS)
        self.assertEqual(evaluate_health([process], root, "Traceback (most recent call last)").status, HealthStatus.LOG_ERROR)
        self.assertEqual(evaluate_health([process], root, "Starting Crypto Hunter").status, HealthStatus.HEALTHY)

    def test_process_matching_is_exact_and_path_scoped(self):
        root = Path.cwd()
        exact = ProcessInfo(10, f'python "{root / "main.py"}"')
        unrelated = ProcessInfo(11, f'python "{root.parent / (root.name + "-copy") / "main.py"}"')
        worker = ProcessInfo(12, f'python "{root / "worker.py"}"')
        self.assertEqual(matching_production_processes((exact, unrelated, worker), root), (exact,))


class RollbackResultTests(unittest.TestCase):
    def test_complete_rollback_requires_every_substage(self):
        complete = RollbackResult(True, True, True, True)
        self.assertTrue(complete.succeeded)
        for result in (
            RollbackResult(True, False, True, True),
            RollbackResult(True, True, True, False),
            RollbackResult(False, True, True, True),
            RollbackResult(True, True, False, True),
        ):
            self.assertFalse(result.succeeded)
            self.assertIn("failed", result.summary)

    def test_restore_pointer_existing_missing_and_invalid(self):
        previous = Path("C:/venvs/previous/python.exe")
        default = Path("C:/production/.venv/python.exe")
        self.assertEqual(resolve_restore_python(previous, default, lambda path: path == previous), previous.resolve())
        self.assertEqual(resolve_restore_python(None, default, lambda path: path == default), default.resolve())
        self.assertEqual(resolve_restore_python(Path("C:/missing/python.exe"), default, lambda path: path == default), default.resolve())
        with self.assertRaises(RuntimeError): resolve_restore_python(previous, default, lambda path: False)


class WindowsInterpreterAndLauncherTests(unittest.TestCase):
    def test_python_314_and_arbitrary_full_path_are_supported(self):
        production = Path("C:/production/.venv/Scripts/python.exe")
        configured = Path("D:/Tools/Python/python.exe")
        selected = select_bootstrap_python(production, configured, None, lambda path: "Python 3.14.5" if path == configured else None)
        self.assertEqual(selected.path, configured.resolve()); self.assertEqual(selected.version, "Python 3.14.5")

    def test_valid_production_python_is_preferred(self):
        production = Path("C:/production/.venv/Scripts/python.exe")
        configured = Path("D:/Tools/Python/python.exe")
        selected = select_bootstrap_python(production, configured, None, lambda path: "Python 3.14.5")
        self.assertEqual(selected.path, production.resolve())

    def test_native_nonzero_exit_is_preserved_for_restart_policy(self):
        self.assertEqual(launcher_action(7, 30, 0), LauncherAction.RESTART)
        self.assertEqual(launcher_action(1, 2, 0), LauncherAction.EXIT_DUPLICATE)
        self.assertEqual(launcher_action(9, 2, 2), LauncherAction.EXIT_CRASH_LOOP)


class DeploymentReportingTests(unittest.TestCase):
    def test_reports_are_sanitized_and_scoped(self):
        report = DeploymentReport("feat/market-core", "a", "b", finished_at=datetime.now(timezone.utc), status=DeploymentStatus.BLOCKED, stages=[StageResult("pytest", False, "token=secret")], error="password=hunter2")
        self.assertNotIn("secret", markdown_report(report)); self.assertNotIn("hunter2", json_report(report))
        with tempfile.TemporaryDirectory() as directory:
            storage = DeploymentReportStorage(Path(directory)); md, js = storage.save(report)
            self.assertEqual(storage.latest(), md); self.assertTrue(js.exists())


class _Response:
    status = 200
    async def __aenter__(self): return self
    async def __aexit__(self, *args): return None


class _Session:
    last_json = None
    def __init__(self, *args, **kwargs): self.payload = None
    async def __aenter__(self): return self
    async def __aexit__(self, *args): return None
    def post(self, url, json): self.payload = json; type(self).last_json = json; return _Response()


class DeploymentNotificationTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_configuration_is_nonfatal(self):
        with patch.dict("os.environ", {}, clear=True): self.assertFalse(await send_admin_notification("test"))

    async def test_notification_sanitizes_content(self):
        with patch("deployment.notifications.aiohttp.ClientSession", _Session):
            self.assertTrue(await send_admin_notification("token=supersecret", token="bot-token", admin_id="1"))
        self.assertNotIn("supersecret", _Session.last_json["text"])

    async def test_notification_failure_does_not_raise(self):
        with patch("deployment.notifications.aiohttp.ClientSession", side_effect=RuntimeError("offline")):
            self.assertFalse(await send_admin_notification("test", token="x", admin_id="1", retries=1))
