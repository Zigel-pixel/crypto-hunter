from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from app.utils.single_instance import InstanceAlreadyRunning
from deployment.health import ProcessInfo, evaluate_health
from deployment.models import DeploymentReport, DeploymentState, DeploymentStatus, HealthStatus, StageResult
from deployment.notifications import send_admin_notification
from deployment.orchestrator import DeploymentOrchestrator
from deployment.reporting import DeploymentReportStorage, json_report, markdown_report
from deployment.state import DeploymentStateStore, deployment_lock


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


class DeploymentHealthTests(unittest.TestCase):
    def test_health_outcomes(self):
        root = Path.cwd()
        self.assertEqual(evaluate_health([], root, "").status, HealthStatus.FAILED_START)
        process = ProcessInfo(1, f"python {root}\\main.py")
        self.assertEqual(evaluate_health([process, ProcessInfo(2, process.command_line)], root, "polling").status, HealthStatus.DUPLICATE_PROCESS)
        self.assertEqual(evaluate_health([process], root, "Traceback (most recent call last)").status, HealthStatus.LOG_ERROR)
        self.assertEqual(evaluate_health([process], root, "Starting Crypto Hunter").status, HealthStatus.HEALTHY)


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
