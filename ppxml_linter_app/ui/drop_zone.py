"""
DropZone widget — drag-and-drop target for .ppxml files.

Requires tkinterdnd2 for DnD support (pip install tkinterdnd2).
If the library is not installed the widget degrades gracefully to a
static label; the Browse button in app.py remains the fallback.
"""

import os
import tkinter as tk

try:
    from tkinterdnd2 import DND_FILES
    _DND_AVAILABLE = True
except ImportError:
    _DND_AVAILABLE = False
    DND_FILES = None

# Colours
_BG_IDLE    = "#dce8f5"
_BG_HOVER   = "#b8d4f0"   # highlight while a file is dragged over
_BG_LOADED  = "#d4f0d4"
_FG_IDLE    = "#2266aa"
_FG_LOADED  = "#1a6600"
_FG_NOTICE  = "#888888"


def _parse_drop_data(data: str) -> str:
    """
    Extract the first file path from a DnD drop-data string.

    Windows wraps paths that contain spaces in curly braces:
      {C:/path with spaces/file.ppxml}
    Multiple files are space-separated (possibly with braces):
      {C:/file one.ppxml} C:/filetwo.ppxml
    We only want the first file.
    """
    data = data.strip()
    if data.startswith("{"):
        end = data.find("}")
        if end != -1:
            return data[1:end]
    # No braces — take the first whitespace-delimited token
    return data.split()[0] if data else ""


class DropZone(tk.Frame):
    """
    A framed drop target that accepts .ppxml files.

    Parameters
    ----------
    on_file : callable
        Called with the resolved file path when a valid file is dropped
        or otherwise accepted.
    dnd_available : bool
        Set by app.py based on whether tkinterdnd2 loaded successfully.
        When False the widget shows a notice instead of a drop invitation.
    """

    def __init__(self, parent, on_file=None, dnd_available=True, **kwargs):
        super().__init__(
            parent,
            bg=_BG_IDLE,
            relief=tk.RIDGE,
            bd=2,
            height=70,
            **kwargs,
        )
        self.on_file = on_file
        self.pack_propagate(False)

        self._dnd_live = dnd_available and _DND_AVAILABLE

        if self._dnd_live:
            label_text = "Drop a .ppxml file here  —  or use Browse above"
            label_fg   = _FG_IDLE
        else:
            label_text = "Use Browse above to open a .ppxml file  (install tkinterdnd2 to enable drag-and-drop)"
            label_fg   = _FG_NOTICE

        self._label = tk.Label(
            self,
            text=label_text,
            bg=_BG_IDLE,
            fg=label_fg,
            font=("Segoe UI", 11),
        )
        self._label.pack(expand=True)

        if self._dnd_live:
            self._register_dnd()

    # ------------------------------------------------------------------
    # DnD registration
    # ------------------------------------------------------------------

    def _register_dnd(self):
        """Register this frame and its label as a drop target."""
        for widget in (self, self._label):
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind("<<DropEnter>>", self._on_enter)
            widget.dnd_bind("<<DropLeave>>", self._on_leave)
            widget.dnd_bind("<<Drop>>",      self._on_drop)

    # ------------------------------------------------------------------
    # DnD event handlers
    # ------------------------------------------------------------------

    def _on_enter(self, event):
        self.config(bg=_BG_HOVER)
        self._label.config(bg=_BG_HOVER)
        return event.action   # required by tkinterdnd2

    def _on_leave(self, event):
        # Revert to whichever idle colour is current
        current = self.cget("bg")
        if current == _BG_HOVER:
            self.config(bg=_BG_IDLE)
            self._label.config(bg=_BG_IDLE)

    def _on_drop(self, event):
        """Handle the drop: parse path, validate extension, invoke callback."""
        self._on_leave(event)   # revert hover colour first

        path = _parse_drop_data(event.data)
        if not path:
            return

        # Normalise to OS-native separators
        path = os.path.normpath(path)

        if not path.lower().endswith(".ppxml"):
            self._flash_error("Only .ppxml files are supported")
            return

        if self.on_file:
            self.on_file(path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_filename(self, name: str):
        """Update the label after a file has been loaded (Browse or drop)."""
        self._label.config(text=f"Loaded: {name}", fg=_FG_LOADED)
        self.config(bg=_BG_LOADED)
        self._label.config(bg=_BG_LOADED)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _flash_error(self, msg: str):
        """Briefly show an error message in the drop zone then revert."""
        original_text = self._label.cget("text")
        original_fg   = self._label.cget("fg")
        self._label.config(text=msg, fg="#cc0000")
        self.after(2000, lambda: self._label.config(text=original_text, fg=original_fg))
