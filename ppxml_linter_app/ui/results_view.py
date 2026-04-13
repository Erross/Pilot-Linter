"""
ResultsView widget — structured, collapsible findings display.
"""

import tkinter as tk
from tkinter import ttk
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import ppxml_linter

# ---------------------------------------------------------------------------
# Theme constants
# ---------------------------------------------------------------------------

_BG        = "#f5f5f5"   # outer / canvas background
_CARD_BG   = "#ffffff"   # card face
_CARD_EDGE = "#e2e2e2"   # card border
_CODE_BG   = "#f0f2f4"   # evidence box background
_CODE_FG   = "#24292e"   # evidence box text

_SEV = {
    ppxml_linter.Severity.ERROR: {
        "strip":   "#d73a49",   # left strip / pill
        "pill_fg": "#ffffff",
        "hdr_bg":  "#ffeef0",   # section header background
        "hdr_fg":  "#86181d",   # section header text
        "label":   "Critical Errors",
        "pill_text": "error",
    },
    ppxml_linter.Severity.WARNING: {
        "strip":   "#e36209",
        "pill_fg": "#ffffff",
        "hdr_bg":  "#fff8f0",
        "hdr_fg":  "#7d4a00",
        "label":   "Warnings",
        "pill_text": "warning",
    },
    ppxml_linter.Severity.INFO: {
        "strip":   "#6a737d",
        "pill_fg": "#ffffff",
        "hdr_bg":  "#f6f8fa",
        "hdr_fg":  "#444444",
        "label":   "Observations",
        "pill_text": "observation",
    },
}

_SECTION_ORDER = [
    ppxml_linter.Severity.ERROR,
    ppxml_linter.Severity.WARNING,
    ppxml_linter.Severity.INFO,
]

# Sections expanded by default (Info collapses)
_DEFAULT_EXPANDED = {
    ppxml_linter.Severity.ERROR:   True,
    ppxml_linter.Severity.WARNING: True,
    ppxml_linter.Severity.INFO:    False,
}


# ---------------------------------------------------------------------------
# ResultsView
# ---------------------------------------------------------------------------

class ResultsView(tk.Frame):
    """Scrollable, collapsible findings display."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=_BG, **kwargs)
        self._wrap_labels: list[tk.Label] = []   # labels needing dynamic wraplength
        self._build_shell()

    # ------------------------------------------------------------------
    # Shell (built once)
    # ------------------------------------------------------------------

    def _build_shell(self):
        # ---- summary bar ----
        self._summary_bar = tk.Frame(self, bg=_BG)
        self._summary_bar.pack(fill=tk.X, pady=(0, 6))

        self._summary_label = tk.Label(
            self._summary_bar, text="", bg=_BG,
            font=("Segoe UI", 9), fg="#555555", anchor="w"
        )
        self._summary_label.pack(side=tk.LEFT)

        # pill container (individual colored labels)
        self._pill_frame = tk.Frame(self._summary_bar, bg=_BG)
        self._pill_frame.pack(side=tk.LEFT, padx=(6, 0))

        # ---- scrollable canvas ----
        container = tk.Frame(self, bg=_BG)
        container.pack(fill=tk.BOTH, expand=True)

        self._canvas = tk.Canvas(container, bg=_CARD_BG, highlightthickness=0)
        self._vsb = ttk.Scrollbar(container, orient=tk.VERTICAL, command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._vsb.set)

        self._vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._inner = tk.Frame(self._canvas, bg=_CARD_BG)
        self._win_id = self._canvas.create_window((0, 0), window=self._inner, anchor="nw")

        self._inner.bind("<Configure>", self._on_inner_configure)
        self._canvas.bind("<Configure>", self._on_canvas_resize)
        self._canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        # placeholder shown before any file is loaded
        self._placeholder = tk.Label(
            self._inner,
            text="Load a .ppxml file to see findings.",
            fg="#aaaaaa", bg=_CARD_BG,
            font=("Segoe UI", 11), pady=60
        )
        self._placeholder.pack()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show(self, findings: list):
        """Render a new set of Finding objects, replacing any previous results."""
        self._wrap_labels.clear()

        # Clear inner frame
        for w in self._inner.winfo_children():
            w.destroy()
        for w in self._pill_frame.winfo_children():
            w.destroy()

        errors   = [f for f in findings if f.severity == ppxml_linter.Severity.ERROR]
        warnings = [f for f in findings if f.severity == ppxml_linter.Severity.WARNING]
        infos    = [f for f in findings if f.severity == ppxml_linter.Severity.INFO]

        if not findings:
            tk.Label(
                self._inner, text="\u2714  No findings — looks good!",
                fg="#1a7a1a", bg=_CARD_BG,
                font=("Segoe UI", 12), pady=60
            ).pack()
            self._summary_label.config(text="No findings.")
            self._canvas.yview_moveto(0)
            return

        # ---- summary pills ----
        self._summary_label.config(text="")
        counts = [
            (ppxml_linter.Severity.ERROR,   errors),
            (ppxml_linter.Severity.WARNING, warnings),
            (ppxml_linter.Severity.INFO,    infos),
        ]
        pill_parts = []
        for sev, group in counts:
            if not group:
                continue
            cfg = _SEV[sev]
            n = len(group)
            word = cfg["pill_text"] + ("s" if n != 1 else "")
            pill_parts.append((f" {n} {word} ", cfg["strip"], cfg["pill_fg"]))

        for i, (text, bg, fg) in enumerate(pill_parts):
            tk.Label(
                self._pill_frame, text=text,
                bg=bg, fg=fg,
                font=("Segoe UI", 8, "bold"),
                padx=4, pady=2, relief=tk.FLAT
            ).pack(side=tk.LEFT, padx=(0, 4))

        # ---- sections ----
        groups = [
            (ppxml_linter.Severity.ERROR,   errors),
            (ppxml_linter.Severity.WARNING, warnings),
            (ppxml_linter.Severity.INFO,    infos),
        ]
        for sev, group in groups:
            if group:
                self._render_section(sev, group)

        self._canvas.yview_moveto(0)
        # Apply wraplength now that we know widget widths
        self.after(50, self._reflow_wrap)

    # ------------------------------------------------------------------
    # Section rendering
    # ------------------------------------------------------------------

    def _render_section(self, severity: ppxml_linter.Severity, findings: list):
        cfg = _SEV[severity]
        expanded = _DEFAULT_EXPANDED[severity]

        outer = tk.Frame(self._inner, bg=_CARD_BG)
        outer.pack(fill=tk.X, pady=(6, 0))

        # ---- section header (clickable) ----
        hdr = tk.Frame(outer, bg=cfg["hdr_bg"], cursor="hand2")
        hdr.pack(fill=tk.X)

        arrow_var = tk.StringVar(value="\u25bc" if expanded else "\u25b6")

        arrow_lbl = tk.Label(
            hdr, textvariable=arrow_var,
            bg=cfg["hdr_bg"], fg=cfg["hdr_fg"],
            font=("Segoe UI", 9), padx=6, pady=6
        )
        arrow_lbl.pack(side=tk.LEFT)

        # coloured strip on header left edge
        tk.Frame(hdr, bg=cfg["strip"], width=4).place(x=0, y=0, relheight=1)

        tk.Label(
            hdr,
            text=f"  {cfg['label']}",
            bg=cfg["hdr_bg"], fg=cfg["hdr_fg"],
            font=("Segoe UI", 10, "bold"), pady=6, anchor="w"
        ).pack(side=tk.LEFT)

        count_lbl = tk.Label(
            hdr,
            text=f"  {len(findings)}",
            bg=cfg["strip"], fg=cfg["pill_fg"],
            font=("Segoe UI", 8, "bold"),
            padx=6, pady=2
        )
        count_lbl.pack(side=tk.LEFT, padx=6)

        # ---- body frame (cards live here) ----
        body = tk.Frame(outer, bg=_CARD_BG)
        if expanded:
            body.pack(fill=tk.X)

        for finding in findings:
            self._render_card(body, finding, cfg)
            self._render_separator(body)

        # Toggle behaviour
        def toggle(_event=None):
            if body.winfo_ismapped():
                body.pack_forget()
                arrow_var.set("\u25b6")
            else:
                body.pack(fill=tk.X)
                arrow_var.set("\u25bc")
            # Force scroll region recalc
            self._inner.update_idletasks()
            self._canvas.configure(scrollregion=self._canvas.bbox("all"))

        for widget in (hdr, arrow_lbl, count_lbl):
            widget.bind("<Button-1>", toggle)
        # Also bind all static labels in the header
        for child in hdr.winfo_children():
            child.bind("<Button-1>", toggle)

    # ------------------------------------------------------------------
    # Card rendering
    # ------------------------------------------------------------------

    def _render_card(self, parent: tk.Frame, finding, cfg: dict):
        card = tk.Frame(parent, bg=_CARD_BG, pady=0)
        card.pack(fill=tk.X)

        # Left severity strip
        strip = tk.Frame(card, bg=cfg["strip"], width=5)
        strip.pack(side=tk.LEFT, fill=tk.Y)
        strip.pack_propagate(False)

        body = tk.Frame(card, bg=_CARD_BG, padx=10, pady=8)
        body.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # ---- title row: rule badge + title ----
        title_row = tk.Frame(body, bg=_CARD_BG)
        title_row.pack(fill=tk.X)

        rule_lbl = tk.Label(
            title_row,
            text=f"[{finding.rule_id}]",
            bg=_CODE_BG, fg=cfg["strip"],
            font=("Consolas", 8, "bold"),
            padx=4, pady=2
        )
        rule_lbl.pack(side=tk.LEFT)

        title_lbl = tk.Label(
            title_row,
            text=f"  {finding.title}",
            bg=_CARD_BG, fg="#24292e",
            font=("Segoe UI", 9, "bold"),
            anchor="w"
        )
        title_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # ---- location ----
        location = finding.location_str()
        if location:
            loc_lbl = tk.Label(
                body,
                text=f"\U0001f4cd  {location}",
                bg=_CARD_BG, fg="#586069",
                font=("Segoe UI", 8),
                anchor="w"
            )
            loc_lbl.pack(fill=tk.X, pady=(3, 0))

        # ---- description ----
        desc_lbl = tk.Label(
            body,
            text=finding.description,
            bg=_CARD_BG, fg="#444444",
            font=("Segoe UI", 9),
            anchor="nw", justify=tk.LEFT,
            wraplength=700
        )
        desc_lbl.pack(fill=tk.X, pady=(4, 0))
        self._wrap_labels.append(desc_lbl)

        # ---- evidence (code box) ----
        if finding.evidence:
            ev_outer = tk.Frame(body, bg=_CODE_BG, relief=tk.FLAT, bd=0)
            ev_outer.pack(fill=tk.X, pady=(5, 0))

            # thin left accent inside code box
            tk.Frame(ev_outer, bg=cfg["strip"], width=3).pack(side=tk.LEFT, fill=tk.Y)

            ev_lbl = tk.Label(
                ev_outer,
                text=finding.evidence,
                bg=_CODE_BG, fg=_CODE_FG,
                font=("Consolas", 8),
                anchor="w", justify=tk.LEFT,
                wraplength=680, padx=6, pady=4
            )
            ev_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self._wrap_labels.append(ev_lbl)

    def _render_separator(self, parent: tk.Frame):
        tk.Frame(parent, bg=_CARD_EDGE, height=1).pack(fill=tk.X, padx=14)

    # ------------------------------------------------------------------
    # Layout / scroll helpers
    # ------------------------------------------------------------------

    def _on_inner_configure(self, _event=None):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_resize(self, event):
        self._canvas.itemconfig(self._win_id, width=event.width)
        self._reflow_wrap(event.width)

    def _on_mousewheel(self, event):
        self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _reflow_wrap(self, canvas_width: int = 0):
        """Recalculate wraplength for all text labels based on current canvas width."""
        if not canvas_width:
            canvas_width = self._canvas.winfo_width()
        if canvas_width < 100:
            return
        # strip ~ left strip (5) + body padx (10*2) + evidence left-bar (3) + evidence padx (6) + scrollbar margin
        desc_wrap = max(200, canvas_width - 60)
        ev_wrap   = max(200, canvas_width - 80)

        for lbl in self._wrap_labels:
            try:
                current = lbl.cget("font")
                # evidence labels use Consolas, desc labels use Segoe UI
                if "Consolas" in str(current):
                    lbl.config(wraplength=ev_wrap)
                else:
                    lbl.config(wraplength=desc_wrap)
            except tk.TclError:
                pass  # widget was destroyed
