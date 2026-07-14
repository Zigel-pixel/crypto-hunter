from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
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
        self.assertNotIn("-3.13", combined)

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
        self.assertIn("will replace local edits", source)

    def test_python_bootstrap_is_configurable_and_minor_version_independent(self):
        source = self.scripts["auto_deploy.template.ps1"]
        self.assertIn('$BasePythonExe = ""', source)
        self.assertIn(".venv\\Scripts\\python.exe", source)
        self.assertIn("Get-Command py", source)
        self.assertIn("$bootstrapPython -m venv", source)
        self.assertIn("Python \\d+\\.\\d+\\.\\d+", source)
        self.assertNotRegex(source, r"py\s+-\d+\.\d+")

    def test_launcher_uses_powershell_51_safe_native_redirection(self):
        source = self.scripts["run_bot.template.ps1"]
        self.assertIn("Start-Process", source)
        self.assertIn("-RedirectStandardOutput", source)
        self.assertIn("-RedirectStandardError", source)
        self.assertIn("-Wait -PassThru", source)
        self.assertIn("$process.ExitCode", source)
        self.assertNotIn("*>>", source)
        deploy = self.scripts["auto_deploy.template.ps1"]
        self.assertIn("Invoke-NativeCode", deploy)
        self.assertIn("$nativeExitCode = $LASTEXITCODE", deploy)
        self.assertIn("Start-Process -FilePath $candidate", deploy)

    def test_powershell_51_json_and_atomic_state_are_used(self):
        combined = "\n".join(self.scripts.values())
        self.assertNotIn("-AsHashtable", combined)
        self.assertIn("ConvertFrom-Json", combined)
        helper = self.scripts["atomic_files.template.ps1"]
        self.assertIn("[IO.File]::Replace($temporary, $destination, $backup)", helper)
        self.assertNotRegex(combined, r"File\]::Replace\([^\r\n]*\$(?:null|\{?null\}?)")
        self.assertNotRegex(combined, r"File\]::Replace\([^\r\n]*,\s*['\"]{2}\s*\)")
        self.assertIn("New-Object Text.UTF8Encoding($false)", combined)

    def test_rollback_restores_pointer_before_start_and_reports_substages(self):
        source = self.scripts["auto_deploy.template.ps1"]
        rollback = source[source.index("function Restore-Production"):source.index("New-Item -ItemType Directory")]
        self.assertLess(rollback.index("Set-ActivePython"), rollback.index("Start-ProductionBot"))
        for field in ("source_restored", "pointer_restored", "processes_cleared", "health_restored"):
            self.assertIn(field, rollback)
        self.assertIn("Get-RestorePython", source)
        self.assertIn("default production Python", source)

    def test_process_reconciliation_uses_one_logical_tree(self):
        source = self.scripts["auto_deploy.template.ps1"]
        self.assertIn("Exact production process trees did not exit before start", source)
        self.assertIn("did not create exactly one valid process tree", source)
        self.assertIn("ParentProcessId", source)
        self.assertIn("ExecutablePath", source)
        self.assertIn("ExpectedRoot", source)
        self.assertIn("Test-SingleBotProcessTree", source)
        self.assertIn("[regex]::Escape", source)
        self.assertNotIn("*CryptoHunter*", source)

    def test_exact_process_tree_cleanup_is_child_first_and_path_scoped(self):
        source = self.scripts["auto_deploy.template.ps1"]
        stop = source[source.index("function Stop-ProductionBot"):source.index("function Start-ProductionBot")]
        self.assertIn("Get-BotProcesses", stop)
        self.assertIn("Sort-Object Depth -Descending", stop)
        self.assertIn("Stop-Process -Id $process.ProcessId", stop)
        self.assertNotIn("Get-Process python", stop)

    def test_success_messages_follow_checked_operations(self):
        install = self.scripts["install_tasks.template.ps1"]
        self.assertLess(install.rindex("if ($LASTEXITCODE -ne 0)"), install.rindex("Installed/updated"))
        clear = self.scripts["clear_failed_deployment.template.ps1"]
        self.assertLess(clear.index("Replace-FileAtomic"), clear.index("retry block cleared"))
        self.assertIn("exit 1", clear)

    def test_atomic_helper_validates_recovers_and_cleans(self):
        helper = self.scripts["atomic_files.template.ps1"]
        for required in ("temporary file is missing", ".atomic-backup", "same directory", "destination verification failed", "[IO.File]::Move($backup, $destination)"):
            self.assertIn(required, helper)
        self.assertLess(helper.index("[IO.File]::Delete($backup)"), helper.index("[IO.File]::Replace"))
        self.assertIn("-not $replacementSucceeded", helper)

    def test_setup_installs_shared_atomic_helper(self):
        setup = self.scripts["setup_local.template.ps1"]
        self.assertIn('"atomic_files.template.ps1" = "atomic_files.ps1"', setup)
        for consumer in ("auto_deploy.template.ps1", "clear_failed_deployment.template.ps1"):
            self.assertIn("atomic_files.ps1", self.scripts[consumer])

    @unittest.skipUnless(shutil.which("powershell.exe"), "Windows PowerShell is required")
    def test_clear_failed_deployment_success_and_failure_exit_codes(self):
        template = self.scripts["clear_failed_deployment.template.ps1"]
        helper = self.scripts["atomic_files.template.ps1"]
        for should_fail in (False, True):
            with self.subTest(should_fail=should_fail), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                runtime = root / ".deployment"
                runtime.mkdir()
                state = runtime / "state.json"
                state.write_text(json.dumps({"failed_commit": "abc", "failure_count": 4}), encoding="utf-8")
                script = root / "clear_failed_deployment.ps1"
                script.write_text(template.replace("C:\\CryptoHunterProd", str(root)), encoding="utf-8")
                atomic_helper = root / "atomic_files.ps1"
                atomic_helper.write_text(
                    'function Replace-FileAtomic { throw "simulated replacement failure" }' if should_fail else helper,
                    encoding="utf-8",
                )
                result = subprocess.run(
                    ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(script), "-ConfirmClear"],
                    capture_output=True, text=True, check=False,
                )
                output = result.stdout + result.stderr
                if should_fail:
                    self.assertNotEqual(result.returncode, 0)
                    self.assertNotIn("retry block cleared", output.casefold())
                    self.assertEqual(json.loads(state.read_text(encoding="utf-8"))["failed_commit"], "abc")
                else:
                    self.assertEqual(result.returncode, 0, output)
                    self.assertIn("retry block cleared", output.casefold())
                    self.assertEqual(json.loads(state.read_text(encoding="utf-8-sig"))["failed_commit"], "")
                    self.assertFalse(state.with_name(state.name + ".atomic-backup").exists())

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
