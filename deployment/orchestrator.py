from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

from deployment.models import DeploymentReport, DeploymentState, DeploymentStatus, StageResult


class DeploymentOperations(Protocol):
    def validate(self) -> tuple[str, str]: ...
    def remote_commit(self) -> str: ...
    def verify_candidate(self, commit: str) -> tuple[bool, str]: ...
    def deploy(self, commit: str) -> tuple[bool, str]: ...
    def restart_and_health(self) -> tuple[bool, str]: ...
    def run_e2e(self, suite: str) -> tuple[bool, str]: ...
    def rollback(self, commit: str) -> tuple[bool, str]: ...


class DeploymentOrchestrator:
    def __init__(self, operations: DeploymentOperations, *, branch: str = "feat/market-core", rollback_on_smoke: bool = True, rollback_on_full: bool = True) -> None:
        self.operations, self.branch = operations, branch
        self.rollback_on_smoke, self.rollback_on_full = rollback_on_smoke, rollback_on_full

    def run(self, state: DeploymentState) -> DeploymentReport:
        report = DeploymentReport(self.branch, "", "")
        try:
            old_commit, validated_branch = self.operations.validate()
            report.old_commit, report.branch = old_commit, validated_branch
            if validated_branch != self.branch:
                return self._blocked(report, "Unexpected production branch")
            remote = self.operations.remote_commit(); report.new_commit = remote
            state.last_checked_remote_commit = remote
            if remote == old_commit:
                report.status = DeploymentStatus.NO_UPDATE
                return self._finish(report, state)
            if state.failed_commit == remote:
                return self._blocked(report, "This commit is suppressed after a previous blocking failure", state)
            verified, summary = self.operations.verify_candidate(remote)
            report.stages.append(StageResult("candidate_verification", verified, summary))
            if not verified:
                state.failed_commit = remote; state.failure_count += 1
                return self._blocked(report, summary, state)
            deployed, summary = self.operations.deploy(remote)
            report.stages.append(StageResult("production_update", deployed, summary))
            if not deployed:
                return self._rollback(report, state, old_commit, summary)
            healthy, summary = self.operations.restart_and_health()
            report.stages.append(StageResult("process_health", healthy, summary))
            if not healthy:
                return self._rollback(report, state, old_commit, summary)
            smoke, report.smoke_e2e = self.operations.run_e2e("smoke")
            if not smoke and self.rollback_on_smoke:
                return self._rollback(report, state, old_commit, report.smoke_e2e)
            full, report.full_e2e = self.operations.run_e2e("all") if smoke else (False, "skipped_after_smoke_failure")
            if not full and self.rollback_on_full:
                return self._rollback(report, state, old_commit, report.full_e2e)
            report.status = DeploymentStatus.DEPLOYED if smoke and full else DeploymentStatus.DEPLOYED_WITH_E2E_FAILURES
            report.final_active_commit = remote
            state.previous_working_commit = old_commit
            state.last_successfully_deployed_commit = remote
            state.failed_commit = ""
            return self._finish(report, state)
        except Exception as exc:
            state.failure_count += 1
            return self._blocked(report, f"{type(exc).__name__}: {exc}", state)

    def _rollback(self, report: DeploymentReport, state: DeploymentState, old_commit: str, reason: str) -> DeploymentReport:
        restored, summary = self.operations.rollback(old_commit)
        report.rollback = summary; report.error = reason
        report.status = DeploymentStatus.ROLLED_BACK if restored else DeploymentStatus.ROLLBACK_FAILED
        report.final_active_commit = old_commit if restored else "unknown"
        report.blocking_predicate = "rollback_health_verified" if not restored else "deployment_stage_passed"
        if not restored: state.failure_count += 1
        state.failed_commit = report.new_commit
        return self._finish(report, state)

    def _blocked(self, report: DeploymentReport, reason: str, state: DeploymentState | None = None) -> DeploymentReport:
        report.status = DeploymentStatus.BLOCKED; report.error = reason
        report.final_active_commit = report.old_commit
        report.blocking_predicate = "pre_activation_validation_passed"
        return self._finish(report, state)

    @staticmethod
    def _finish(report: DeploymentReport, state: DeploymentState | None) -> DeploymentReport:
        report.finished_at = datetime.now(timezone.utc)
        if not report.final_active_commit and report.status is DeploymentStatus.NO_UPDATE:
            report.final_active_commit = report.old_commit
        if state is not None:
            state.last_deployment_timestamp = report.finished_at.isoformat()
            state.last_deployment_status = report.status.value
            state.last_smoke_e2e_status = report.smoke_e2e
            state.last_full_e2e_status = report.full_e2e
        return report
