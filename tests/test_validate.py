"""Artifact validation must fail loudly, including under python -O."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from complaint_intelligence.validate import ArtifactValidationError, validate_artifacts

ROOT = Path(__file__).resolve().parent.parent


class ArtifactValidationTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        for folder in ('artifacts', 'web'):
            shutil.copytree(ROOT/folder, self.root/folder)

    def tearDown(self):
        self._tmp.cleanup()

    def edit_report(self, change):
        path = self.root/'artifacts/report.json'
        report = json.loads(path.read_text())
        change(report)
        path.write_text(json.dumps(report))

    def test_committed_copy_passes(self):
        self.assertTrue(validate_artifacts(self.root))

    def test_inconsistent_counts_are_rejected(self):
        self.edit_report(lambda r: r['summary'].__setitem__('complaints', r['summary']['complaints'] + 1))
        with self.assertRaisesRegex(ArtifactValidationError, 'Weekly count mismatch'):
            validate_artifacts(self.root)

    def test_leaked_narrative_is_rejected(self):
        self.edit_report(lambda r: r['records'][0].__setitem__('narrative', 'raw text'))
        with self.assertRaisesRegex(ArtifactValidationError, 'narrative leaked'):
            validate_artifacts(self.root)

    def test_stale_browser_copy_is_rejected(self):
        (self.root/'web/data.js').write_text('window.REPORT = {};\n')
        with self.assertRaisesRegex(ArtifactValidationError, 'data.js stale'):
            validate_artifacts(self.root)

    def test_checks_still_run_with_python_optimizations(self):
        # `python -O` strips assert statements; the validator must not depend on them.
        self.edit_report(lambda r: r['summary'].__setitem__('alerts', r['summary']['alerts'] + 1))
        code = (
            'import sys; from complaint_intelligence.validate import validate_artifacts, '
            'ArtifactValidationError\n'
            'try:\n    validate_artifacts(sys.argv[1])\n'
            'except ArtifactValidationError as exc:\n    print(exc); sys.exit(3)\n'
        )
        env = {**os.environ, 'PYTHONPATH': str(ROOT)}
        result = subprocess.run([sys.executable, '-O', '-c', code, str(self.root)],
                                capture_output=True, text=True, env=env, check=False)
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertIn('Alert count mismatch', result.stdout)

    def test_cli_reports_failure_without_traceback(self):
        self.edit_report(lambda r: r['summary'].__setitem__('alerts', r['summary']['alerts'] + 1))
        code = (
            'import functools, sys\n'
            'import complaint_intelligence.validate as v\n'
            'v.validate_artifacts = functools.partial(v.validate_artifacts, sys.argv[1])\n'
            'from complaint_intelligence.cli import main\n'
            'sys.argv = ["complaint-intelligence", "validate"]\n'
            'main()\n'
        )
        result = subprocess.run([sys.executable, '-c', code, str(self.root)],
                                capture_output=True, text=True, cwd=ROOT, check=False)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('Artifact validation failed: Alert count mismatch', result.stderr)
        self.assertNotIn('Traceback', result.stderr)

if __name__ == '__main__':
    unittest.main()
