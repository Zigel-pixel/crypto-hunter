from __future__ import annotations

from pathlib import Path
import unittest


class DeploymentScriptAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = Path("scripts/windows")
        cls.scripts = {path.name: path.read_text(encoding="utf-8") for path in cls.directory.glob("*.template.ps1")}

    def test_templates_contain_no_secret_values_or_user_profiles(self):
        combined = "\n".join(self.scripts.values())
        self.assertNotIn("C:\\Users\\", combined)
        self.assertNotRegex(combined, r"\d{8,}:[A-Za-z0-9_-]{20,}")
        self.assertNotIn("E2E_TELEGRAM_API_HASH=", combined)

    def test_auto_deploy_verifies_before_stopping(self):
        source = self.scripts["auto_deploy.template.ps1"]
        verification = source.index('Invoke-Checked "pytest"')
        production_stop = source.index("\n    Stop-ProductionBot", verification)
        self.assertLess(verification, production_stop)
        self.assertIn("git merge-base --is-ancestor", source)
        self.assertIn("git merge --ff-only", source)
        self.assertNotIn("git reset --hard", source)
        self.assertIn("Candidate directory must be outside", source)
        self.assertIn("CryptoHunterDeployCandidate", source)
        self.assertIn("run smoke", source)
        self.assertIn("failed_commit", source)
        self.assertIn("Maximum deployment duration exceeded", source)

    def test_task_installer_uses_xml_repetition_and_ignore_new(self):
        source = self.scripts["install_tasks.template.ps1"]
        self.assertIn("<Interval>PT5M</Interval>", source)
        self.assertIn("<MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>", source)
        self.assertIn("schtasks.exe /Create", source)
        self.assertNotIn(".RepetitionInterval", source)

    def test_setup_backs_up_and_does_not_touch_sensitive_files(self):
        source = self.scripts["setup_local.template.ps1"]
        self.assertIn(".bak", source); self.assertIn("ConfirmSetup", source)
        self.assertNotIn(".env", source); self.assertNotIn("crypto.db", source)

    def test_runtime_paths_are_ignored(self):
        ignore = Path(".gitignore").read_text(encoding="utf-8")
        for value in ("deployment/state.json", "deployment/reports/", ".deployment/", "deployment/*.lock"):
            self.assertIn(value, ignore)

    def test_no_codex_or_arbitrary_command_execution(self):
        combined = "\n".join(self.scripts.values()).casefold()
        self.assertNotIn("codex", combined)
        self.assertNotIn("invoke-expression", combined)
        self.assertNotIn("iex ", combined)

    def test_qa_deployment_commands_are_read_only_and_authorized(self):
        source = Path("qa_bot/handlers.py").read_text(encoding="utf-8")
        for command in ("deploy_status", "deploy_last", "deploy_reports", "deploy_failed_commit"):
            self.assertIn(f'Command("{command}")', source)
        self.assertGreaterEqual(source.count("if not await authorized(message): return"), 4)
        for forbidden in ("deploy_force", "deploy_run", "subprocess", "Start-Process", "Invoke-Expression"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__": unittest.main()
