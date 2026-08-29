import contextlib
import io
import os
import tempfile
import unittest

from cronlint.cli import main


class CliTests(unittest.TestCase):
    def _write(self, dir_path, name, content):
        path = os.path.join(dir_path, name)
        with open(path, "w") as handle:
            handle.write(content)
        return path

    def test_valid_file_reports_ok_and_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, "crontab", "0 2 * * * /usr/local/bin/backup.sh\n")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = main([path])
            self.assertEqual(code, 0)
            self.assertIn("OK", out.getvalue())
            self.assertIn("1 entry", out.getvalue())

    def test_invalid_file_reports_error_and_exits_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, "crontab", "*/5 8-25 * * 1-5 /usr/local/bin/check.sh\n")
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                code = main([path])
            self.assertEqual(code, 1)
            self.assertIn("25 is out of range for hour", err.getvalue())

    def test_missing_file_reports_error_and_exits_one(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = main(["/nonexistent/path/to/crontab"])
        self.assertEqual(code, 1)
        self.assertTrue(err.getvalue().strip())

    def test_multiple_files_are_all_validated(self):
        with tempfile.TemporaryDirectory() as tmp:
            good = self._write(tmp, "good", "0 2 * * * /bin/one.sh\n")
            bad = self._write(tmp, "bad", "60 * * * * /bin/two.sh\n")
            out = io.StringIO()
            err = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = main([good, bad])
            self.assertEqual(code, 1)
            self.assertIn("OK", out.getvalue())
            self.assertIn("60 is out of range", err.getvalue())

    def test_invalid_file_reports_every_bad_line_not_just_the_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(
                tmp,
                "crontab",
                "60 * * * * /bin/one.sh\n0 2 * * * /bin/good.sh\n* * * * 8 /bin/two.sh\n",
            )
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                code = main([path])
            self.assertEqual(code, 1)
            output = err.getvalue()
            self.assertIn("60 is out of range for minute", output)
            self.assertIn("8 is out of range for day of week", output)

    def test_multiple_entries_pluralize_the_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(
                tmp,
                "crontab",
                "0 2 * * * /bin/one.sh\n30 3 * * * /bin/two.sh\n",
            )
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = main([path])
            self.assertEqual(code, 0)
            self.assertIn("2 entries", out.getvalue())


if __name__ == "__main__":
    unittest.main()
