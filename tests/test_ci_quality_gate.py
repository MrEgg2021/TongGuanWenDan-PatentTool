from __future__ import annotations

import unittest
from pathlib import Path

import yaml


class CiQualityGateTests(unittest.TestCase):
    def test_github_actions_runs_compileall_and_unittest_on_windows(self) -> None:
        workflow = yaml.safe_load(Path(".github/workflows/text-integrity.yml").read_text(encoding="utf-8"))
        jobs = workflow.get("jobs", {})

        quality_jobs = [
            job
            for job in jobs.values()
            if str(job.get("runs-on", "")).lower() == "windows-latest"
        ]

        self.assertTrue(quality_jobs, "A Windows quality job is required for PySide6/pywin32 tests")
        all_run_commands = "\n".join(
            str(step.get("run", ""))
            for job in quality_jobs
            for step in job.get("steps", [])
            if isinstance(step, dict)
        )
        self.assertIn("python -m compileall -q .", all_run_commands)
        self.assertIn('python -m unittest discover -s tests -p "test_*.py"', all_run_commands)


if __name__ == "__main__":
    unittest.main()
