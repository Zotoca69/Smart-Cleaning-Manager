"""Offline review GUI (Tkinter). Synthetic transport only; no HA connection exists here."""
import asyncio
import queue
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

import config
from collector import capture
from export import export_capture
from synthetic import demo_connect_factory

SYNTHETIC_URL = "wss://synthetic.invalid/api/websocket"


class CollectorApp:
    """GUI shell; dialogs and transport factory are injectable for automated smoke tests."""

    def __init__(self, root, choose_folder=None, choose_target=None, show_error=None, connect_factory=demo_connect_factory):
        self.root = root
        self.choose_folder = choose_folder or (lambda: filedialog.askdirectory(title="Choose private local folder"))
        self.choose_target = choose_target or (lambda: filedialog.asksaveasfilename(defaultextension=".zip"))
        self.show_error = show_error or messagebox.showerror
        self.connect_factory = connect_factory
        self.events = queue.Queue()
        self.stop = threading.Event()
        self.active = False
        self.last_capture = None
        self.last_export = None
        self._build()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self._poll()

    def _build(self):
        root = self.root
        root.title("HA Event Collector — offline review")
        tk.Label(root, text="Synthetic test mode — live HA disabled").pack(padx=20, pady=12)
        tk.Label(root, text="Exact entity IDs, one per line").pack()
        self.entities = tk.Text(root, height=5, width=55)
        self.entities.pack()
        self.entities.insert("1.0", "sensor.example")
        tk.Label(root, text=f"Duration in seconds ({config.MIN_DURATION_S}–{config.MAX_DURATION_S})").pack()
        self.duration = tk.Entry(root)
        self.duration.insert(0, "10")
        self.duration.pack()
        self.status = tk.StringVar(value="Ready")
        tk.Label(root, textvariable=self.status, wraplength=420, justify="left").pack(pady=8)
        self.start_button = tk.Button(root, text="Start synthetic capture", command=self.start)
        self.start_button.pack(pady=4)
        self.stop_button = tk.Button(root, text="Stop", command=self.stop.set, state="disabled")
        self.stop_button.pack(pady=4)
        self.export_button = tk.Button(root, text="Export capture", command=self.export, state="disabled")
        self.export_button.pack(pady=4)

    def _set_running(self, running):
        self.active = running
        self.start_button.config(state="disabled" if running else "normal")
        self.stop_button.config(state="normal" if running else "disabled")
        self.export_button.config(state="disabled" if running or self.last_capture is None else "normal")

    def start(self):
        try:
            ids = config.validate_entity_ids(self.entities.get("1.0", "end").split())
            seconds = config.validate_duration(self.duration.get())
        except ValueError as exc:
            self.show_error("Invalid input", str(exc))
            return
        parent = self.choose_folder()
        if not parent:
            return
        self.last_capture = Path(parent) / f"capture-{time.strftime('%Y%m%d-%H%M%S')}-{time.time_ns() % 1_000_000:06d}"
        self.stop.clear()
        self._set_running(True)
        self.status.set("Collecting synthetic messages")
        connect_fn = self.connect_factory(ids)
        target = self.last_capture

        def run():
            try:
                manifest = asyncio.run(capture(SYNTHETIC_URL, "synthetic-only", ids, target, seconds, self.stop,
                                               connect_fn, lambda n: self.events.put(("count", n)), synthetic=True))
            except Exception as exc:  # reported in GUI; manifest holds the incomplete status
                self.events.put(("done", f"INCOMPLETE — {type(exc).__name__}: {exc}"))
            else:
                label = "Complete" if manifest["complete"] else "INCOMPLETE"
                self.events.put(("done", f"{label} — {manifest['reason']} ({manifest['messages']} messages)"))

        threading.Thread(target=run, daemon=True).start()

    def export(self):
        if self.last_capture is None:
            return
        target = self.choose_target()
        if not target:
            return
        try:
            result = export_capture(self.last_capture, target)
        except Exception as exc:
            self.show_error("Export failed", str(exc))
            return
        self.last_export = result
        state = "complete" if result["complete"] else "INCOMPLETE"
        self.status.set(f"Archive created ({state}).\nManifest SHA-256: {result['manifest_sha256']}\nArchive SHA-256: {result['archive_sha256']}")

    def _poll(self):
        while not self.events.empty():
            kind, value = self.events.get_nowait()
            if kind == "count":
                self.status.set(f"{value} messages")
            else:
                self.status.set(value)
                self._set_running(False)
        self.root.after(100, self._poll)

    def close(self):
        if self.active:
            self.stop.set()
            self.root.after(200, self.close)
        else:
            self.root.destroy()


def main():
    root = tk.Tk()
    CollectorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
