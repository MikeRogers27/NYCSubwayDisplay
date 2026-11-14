"""Check timestamps on redirected output, logging records, and tracebacks."""

import io
import subprocess
import sys
import unittest

from console_logging import TimestampedStream

TIMESTAMP = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2} "


class ConsoleLoggingTests(unittest.TestCase):
    def test_partial_and_multiline_writes_preserve_output_and_flush(self) -> None:
        output = io.StringIO()
        stream = TimestampedStream(output)
        self.assertEqual(stream.write("first"), 5)
        self.assertTrue(output.getvalue().endswith("first"))
        stream.write(" line\nsecond line\n")
        stream.flush()
        lines = output.getvalue().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertRegex(lines[0], rf"^{TIMESTAMP}first line$")
        self.assertRegex(lines[1], rf"^{TIMESTAMP}second line$")

    def test_stdout_stderr_logging_and_unhandled_exception(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import logging, sys\n"
                    "from console_logging import configure_console_logging\n"
                    "configure_console_logging(logging.WARNING)\n"
                    "configure_console_logging(logging.WARNING)\n"
                    "print('status', flush=True)\n"
                    "print('error output', file=sys.stderr, flush=True)\n"
                    "logging.info('hidden info')\n"
                    "logging.warning('visible warning')\n"
                    "raise RuntimeError('test failure')\n"
                ),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 1)
        self.assertRegex(result.stdout.strip(), rf"^{TIMESTAMP}status$")
        self.assertNotIn("hidden info", result.stderr)
        self.assertIn("WARNING:visible warning", result.stderr)
        self.assertIn("Traceback (most recent call last):", result.stderr)
        self.assertIn("RuntimeError: test failure", result.stderr)
        for line in result.stderr.splitlines():
            self.assertRegex(line, rf"^{TIMESTAMP}")
            self.assertNotRegex(line, rf"^{TIMESTAMP}{TIMESTAMP}")
