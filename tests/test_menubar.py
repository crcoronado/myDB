"""Regression tests for the macOS menu-bar crash (Settings click aborted the app with
'Fatal Python error: PyEval_RestoreThread ... GIL is released').

AppKit itself is not available here, so we test the parts that decide safety:
the Objective-C callbacks must never call tkinter, and the Tk-side poller must
run the queued commands.
"""
import ast
import faulthandler
import io
import os
import queue
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from mydb import menubar  # noqa: E402


class TestObjCCallbacksNeverTouchTk(unittest.TestCase):
    def test_target_methods_only_queue(self):
        with open(os.path.join(ROOT, "mydb", "menubar.py"), encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        cls = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == "MyDBMenuTarget")
        for fn in (n for n in cls.body if isinstance(n, ast.FunctionDef)):
            src = ast.unparse(fn)
            for forbidden in ("root", "open_search", "open_settings", ".quit(", "bring_to_front", "after("):
                self.assertNotIn(forbidden, src, f"{fn.name} must not call tkinter ({forbidden})")


class FakeRoot:
    def __init__(self):
        self.scheduled = []

    def after(self, ms, fn):
        self.scheduled.append(fn)


class FakeWindow:
    def lift(self):
        pass

    def focus_force(self):
        pass


class FakeApp:
    def __init__(self):
        self.root = FakeRoot()
        self.calls = []
        self.settings = FakeWindow()

    def open_search(self):
        self.calls.append("search")

    def open_settings(self):
        self.calls.append("settings")

    def quit(self):
        self.calls.append("quit")


class TestPoller(unittest.TestCase):
    def make_bar(self):
        bar = menubar.MenuBar.__new__(menubar.MenuBar)  # skip AppKit __init__
        bar.app = FakeApp()
        bar.commands = queue.Queue()
        return bar

    def test_runs_commands_and_reschedules(self):
        bar = self.make_bar()
        bar.commands.put("search")
        bar.commands.put("settings")
        bar._poll()
        self.assertEqual(bar.app.calls, ["search", "settings"])
        self.assertEqual(len(bar.app.root.scheduled), 1)  # keeps polling

    def test_quit_stops_polling(self):
        bar = self.make_bar()
        bar.commands.put("quit")
        bar._poll()
        self.assertEqual(bar.app.calls, ["quit"])
        self.assertEqual(bar.app.root.scheduled, [])

    def test_failing_command_does_not_kill_poller(self):
        bar = self.make_bar()
        bar.app.open_settings = lambda: 1 / 0
        bar.commands.put("settings")
        old = sys.stderr
        sys.stderr = io.StringIO()
        try:
            bar._poll()
        finally:
            sys.stderr = old
        self.assertEqual(len(bar.app.root.scheduled), 1)


class TestLogging(unittest.TestCase):
    def test_log_file_when_not_in_terminal(self):
        old_out, old_err = sys.stdout, sys.stderr
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["XDG_CONFIG_HOME"] = tmp
            sys.stderr = io.StringIO()  # not a TTY, like a Finder launch
            try:
                path = menubar.setup_logging()
                print("hello-log", file=sys.stderr)
                sys.stderr.flush()
            finally:
                fh = sys.stderr
                faulthandler.disable()
                sys.stdout, sys.stderr = old_out, old_err
                fh.close()
                del os.environ["XDG_CONFIG_HOME"]
            self.assertIsNotNone(path)
            with open(path, encoding="utf-8") as fh:
                content = fh.read()
            self.assertIn("myDB", content)
            self.assertIn("hello-log", content)


if __name__ == "__main__":
    unittest.main()
