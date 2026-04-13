"""
DropZone widget.

Phase 1: visual placeholder only — drag-and-drop is not wired yet.
The Browse button in app.py is the working file-load path.
"""

import tkinter as tk


class DropZone(tk.Frame):
    """
    A framed area that invites the user to drop a file.
    In this first pass it acts as a status label; drag-and-drop
    will be added in a future iteration.
    """

    def __init__(self, parent, on_file=None, **kwargs):
        super().__init__(
            parent,
            bg="#dce8f5",
            relief=tk.RIDGE,
            bd=2,
            height=70,
            **kwargs
        )
        self.on_file = on_file
        self.pack_propagate(False)

        self._label = tk.Label(
            self,
            text="Drop a .ppxml file here  —  or use Browse above",
            bg="#dce8f5",
            fg="#2266aa",
            font=("Segoe UI", 11),
        )
        self._label.pack(expand=True)

    def set_filename(self, name: str):
        """Update the label after a file has been loaded."""
        self._label.config(
            text=f"Loaded: {name}",
            fg="#1a6600",
        )
        self.config(bg="#d4f0d4")
        self._label.config(bg="#d4f0d4")
