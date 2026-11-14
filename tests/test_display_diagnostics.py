"""Verify stall dumps, intentional waits, and watchdog cleanup."""

import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

import main
from display_control import DisplayMode
from display_diagnostics import DisplayDiagnostics


class DisplayDiagnosticsTests(unittest.TestCase):
    def test_wait_extends_deadline_and_progress_restores_it(self) -> None:
        diagnostics = DisplayDiagnostics()
        display = main.RunMatrix.__new__(main.RunMatrix)
        display._diagnostics = diagnostics
        display.display_control = Mock()
        display.display_control.wait.return_value = True
        with (
            patch("display_diagnostics.faulthandler.dump_traceback_later") as arm,
            patch("display_diagnostics.faulthandler.cancel_dump_traceback_later") as cancel,
        ):
            with diagnostics.mode("off"):
                self.assertTrue(display.wait_for_display_interrupt(600))
                self.assertEqual([call.args[0] for call in arm.call_args_list], [120, 720, 120])
            cancel.assert_called_once_with()
            display.display_control.wait.assert_called_once_with(600)
            self.assertFalse(diagnostics.active)

    def test_exception_cancels_timer(self) -> None:
        diagnostics = DisplayDiagnostics()
        with (
            patch("display_diagnostics.faulthandler.dump_traceback_later"),
            patch("display_diagnostics.faulthandler.cancel_dump_traceback_later") as cancel,
        ):
            with (
                self.assertRaisesRegex(RuntimeError, "render failed"),
                diagnostics.mode("weather"),
            ):
                raise RuntimeError("render failed")
            cancel.assert_called_once_with()
            self.assertFalse(diagnostics.active)

    def test_rotation_failure_logs_mode_and_traceback(self) -> None:
        display = main.RunMatrix.__new__(main.RunMatrix)
        display._diagnostics = DisplayDiagnostics()
        display.matrix = Mock()
        display.display_control = Mock()
        display.display_control.interrupt.is_set.return_value = False
        display.what_should_we_display = Mock(return_value=([DisplayMode("sports")], [3]))
        display.display_sports = Mock(side_effect=RuntimeError("fetch failed"))
        with (
            patch.object(main, "GracefulKiller", return_value=Mock(kill_now=False)),
            self.assertLogs("NYCSubwayDisplay", level="ERROR") as logs,
            self.assertRaisesRegex(RuntimeError, "fetch failed"),
        ):
            display._run_rotation()
        self.assertIn("sports", logs.output[0])
        self.assertIn("Traceback", logs.output[0])
        self.assertIsNotNone(logs.records[0].exc_info)

    def test_real_stall_dumps_stack_and_recovery_cancels_timer(self) -> None:
        # A subprocess keeps the process-wide native watchdog isolated from tests.
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "from display_diagnostics import DisplayDiagnostics\n"
                    "from time import sleep\n"
                    "def stalled_fetch():\n"
                    "    sleep(0.3)\n"
                    "with DisplayDiagnostics(stall_seconds=0.05).mode('sports'):\n"
                    "    stalled_fetch()\n"
                    "print('RECOVERED', file=__import__('sys').stderr, flush=True)\n"
                    "sleep(0.15)\n"
                ),
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        before, after = result.stderr.split("RECOVERED\n")
        self.assertIn("Timeout", before)
        self.assertIn("stalled_fetch", before)
        self.assertNotIn("Timeout", after)
