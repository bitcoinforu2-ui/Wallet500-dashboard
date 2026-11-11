"""Regression: dashboard sync must never hide a missing private-source credential."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "sync_runtime.py"


class DashboardSourceContractTest(unittest.TestCase):
    def run_without_source_token(self, event):
        env = dict(os.environ)
        env.pop("SOURCE_TOKEN", None)
        env["GITHUB_EVENT_NAME"] = event
        with tempfile.TemporaryDirectory() as cwd:
            return subprocess.run(
                [sys.executable, str(SCRIPT)],
                cwd=cwd, env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, timeout=8, check=False,
            )

    def test_schedule_fails_loudly_without_credential(self):
        result = self.run_without_source_token("schedule")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DASHBOARD_SOURCE_TOKEN_MISSING", result.stdout)

    def test_push_can_deploy_existing_dated_snapshot(self):
        result = self.run_without_source_token("push")
        self.assertEqual(result.returncode, 0)
        self.assertIn("existing dated snapshot", result.stdout)


if __name__ == "__main__":
    unittest.main()
