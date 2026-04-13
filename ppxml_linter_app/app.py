"""
Pipeline Pilot PPXML Linter - Desktop GUI
Entry point: run with  python app.py  from this directory.
"""

import sys
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Allow importing the linter from the parent directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ppxml_linter

from ui.drop_zone import DropZone
from ui.results_view import ResultsView


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Pipeline Pilot PPXML Linter")
        self.geometry("900x700")
        self.minsize(640, 480)
        self.configure(bg="#f0f0f0")

        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        # ---- top toolbar ----
        toolbar = tk.Frame(self, bg="#2d2d2d", pady=6)
        toolbar.pack(fill=tk.X)

        tk.Label(
            toolbar, text="PPXML Linter", fg="white", bg="#2d2d2d",
            font=("Segoe UI", 14, "bold"), padx=12
        ).pack(side=tk.LEFT)

        browse_btn = tk.Button(
            toolbar, text="Browse…", command=self._browse,
            bg="#0078d4", fg="white", relief=tk.FLAT,
            font=("Segoe UI", 10), padx=12, pady=4, cursor="hand2",
            activebackground="#005a9e", activeforeground="white"
        )
        browse_btn.pack(side=tk.RIGHT, padx=10)

        # ---- drop zone ----
        self.drop_zone = DropZone(self, on_file=self._load_file)
        self.drop_zone.pack(fill=tk.X, padx=16, pady=(12, 0))

        # ---- protocol info bar ----
        info_frame = tk.Frame(self, bg="#e8e8e8", relief=tk.SUNKEN, bd=1)
        info_frame.pack(fill=tk.X, padx=16, pady=6)

        self.lbl_protocol = tk.Label(
            info_frame, text="No file loaded", anchor="w",
            bg="#e8e8e8", font=("Segoe UI", 9), fg="#333", padx=8, pady=4
        )
        self.lbl_protocol.pack(fill=tk.X)

        self.lbl_path = tk.Label(
            info_frame, text="", anchor="w",
            bg="#e8e8e8", font=("Segoe UI", 8), fg="#555", padx=8, pady=2
        )
        self.lbl_path.pack(fill=tk.X)

        self.lbl_stats = tk.Label(
            info_frame, text="", anchor="w",
            bg="#e8e8e8", font=("Segoe UI", 8), fg="#555", padx=8, pady=2
        )
        self.lbl_stats.pack(fill=tk.X)

        # ---- results view ----
        self.results_view = ResultsView(self)
        self.results_view.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 16))

    # ------------------------------------------------------------------
    # File handling
    # ------------------------------------------------------------------

    def _browse(self):
        path = filedialog.askopenfilename(
            title="Select PPXML file",
            filetypes=[("Pipeline Pilot XML", "*.ppxml"), ("All files", "*.*")]
        )
        if path:
            self._load_file(path)

    def _load_file(self, filepath: str):
        if not os.path.isfile(filepath):
            messagebox.showerror("File not found", f"Cannot open:\n{filepath}")
            return

        try:
            parser, findings = ppxml_linter.run_lint(filepath)
            findings = ppxml_linter.deduplicate_findings(findings)
        except Exception as exc:
            messagebox.showerror("Parse error", f"Failed to parse file:\n{exc}")
            return

        # Update info bar
        n_comp = len(parser.get_active_components())
        n_conn = len(parser.connections)
        errors   = sum(1 for f in findings if f.severity == ppxml_linter.Severity.ERROR)
        warnings = sum(1 for f in findings if f.severity == ppxml_linter.Severity.WARNING)
        infos    = sum(1 for f in findings if f.severity == ppxml_linter.Severity.INFO)

        self.lbl_protocol.config(
            text=f"Protocol: {parser.protocol_name or '(unnamed)'}"
        )
        self.lbl_path.config(
            text=f"Path: {parser.protocol_path or '(not set)'}"
        )
        self.lbl_stats.config(
            text=(
                f"Components: {n_comp}   Connections: {n_conn}   "
                f"Findings: {len(findings)}  "
                f"(\u274c {errors}  \u26a0\ufe0f {warnings}  \u2139\ufe0f {infos})"
            )
        )

        self.results_view.show(findings)
        self.drop_zone.set_filename(os.path.basename(filepath))


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
