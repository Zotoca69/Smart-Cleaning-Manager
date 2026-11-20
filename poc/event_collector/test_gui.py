"""Automated GUI smoke test: synthetic capture and export through the real Tk window.

Skipped when Tkinter or a display is unavailable, unless SCM_REQUIRE_GUI=1
(used by the Windows test package), in which case unavailability fails.
"""
import os
import tempfile
import time
import unittest
from pathlib import Path

REQUIRE_GUI = os.environ.get("SCM_REQUIRE_GUI") == "1"

try:
    import tkinter as tk
    _root = tk.Tk()
    _root.destroy()
    GUI_AVAILABLE, GUI_REASON = True, ""
except Exception as exc:  # ImportError or TclError (no display)
    GUI_AVAILABLE, GUI_REASON = False, f"{type(exc).__name__}: {exc}"


@unittest.skipUnless(GUI_AVAILABLE or REQUIRE_GUI, f"GUI unavailable ({GUI_REASON})")
class GuiSmokeTests(unittest.TestCase):
    def test_synthetic_capture_and_export_via_gui(self):
        self.assertTrue(GUI_AVAILABLE, f"GUI required but unavailable: {GUI_REASON}")
        from app import CollectorApp
        from export import verify_capture

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        errors = []
        root = tk.Tk()
        app = CollectorApp(root, choose_folder=lambda: tmp.name,
                           choose_target=lambda: str(Path(tmp.name) / "gui.zip"),
                           show_error=lambda *a: errors.append(a))
        app.entities.delete("1.0", "end")
        app.entities.insert("1.0", "vacuum.synthetic_robot\nsensor.synthetic_status")
        app.duration.delete(0, "end")
        app.duration.insert(0, "2")

        def pump(seconds, until=lambda: False):
            end = time.monotonic() + seconds
            while time.monotonic() < end and not until():
                root.update()
                time.sleep(0.02)

        pump(0.2)
        app.start()
        self.assertTrue(app.active)
        pump(10, lambda: not app.active)
        self.assertFalse(app.active, "capture did not finish")
        self.assertTrue(app.status.get().startswith("Complete"), app.status.get())
        verify_capture(app.last_capture)
        app.export()
        self.assertEqual(errors, [])
        self.assertIn("Archive SHA-256", app.status.get())
        self.assertTrue((Path(tmp.name) / "gui.zip").exists())

        app.duration.delete(0, "end")
        app.duration.insert(0, "0")
        app.start()
        self.assertEqual(errors[-1][0], "Invalid input")
        root.destroy()


if __name__ == "__main__":
    unittest.main()
