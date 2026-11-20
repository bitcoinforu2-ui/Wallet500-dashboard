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


    def test_private_source_auth_failures_are_explicit_and_secret_safe(self):
        # Stub the HTTP layer; never use or print a real credential in CI.
        for http_status, marker in (
            (401, "DASHBOARD_SOURCE_TOKEN_REJECTED_HTTP_401"),
            (403, "DASHBOARD_SOURCE_ACCESS_DENIED_HTTP_403"),
            (404, "DASHBOARD_SOURCE_INACCESSIBLE_HTTP_404"),
        ):
            with self.subTest(http_status=http_status):
                env = dict(os.environ)
                env["SOURCE_TOKEN"] = "test-secret-never-print"
                env["GITHUB_EVENT_NAME"] = "schedule"
                program = (
                    "import runpy, urllib.request, urllib.error\n"
                    "def reject(request, timeout=30):\n"
                    f"    raise urllib.error.HTTPError(request.full_url, {http_status}, 'Denied', None, None)\n"
                    "urllib.request.urlopen = reject\n"
                    f"runpy.run_path({str(SCRIPT)!r}, run_name='__main__')\n"
                )
                with tempfile.TemporaryDirectory() as cwd:
                    result = subprocess.run(
                        [sys.executable, "-c", program], cwd=cwd, env=env,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        text=True, timeout=8, check=False,
                    )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(marker, result.stdout)
                self.assertNotIn("test-secret-never-print", result.stdout)

    def test_health_requires_cadence_not_just_recent_timestamp(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("const cadenceHealthy=d.last_interval_meets_target===true;", html)
        self.assertIn("(cadenceHealthy?'green':'yellow')", html)

    def test_missing_pool_provider_status_does_not_fake_zero_pools(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("const npAllFailed=", html)
        self.assertIn("np.networks_failed.length>=3", html)


if __name__ == "__main__":
    unittest.main()
