#!/usr/bin/env python3

# BEC - November 2025
# Automated Powder Dispenser (APD) – storage selection sub-panel.
#   - 2x2 radiobutton grid for S1..S4, configurable via STORAGE_CONFIG
#   - Used by WinRobotArm and JSON/Auto modes to select a dispenser location
#-------------------------------------------------------------------------------
"""2x2 storage selection panel (S1..S4) with configurable mapping."""

import tkinter as tk
import tkinter.ttk as ttk

from guiUtils import GUIFactory, ToolTip

try:
    from config import STORAGE_CONFIG
except Exception:
    # Fallback minimal configuration if config import fails
    STORAGE_CONFIG = {
        "ids": ["S1", "S2", "S3", "S4"],
        "order": ["S1", "S2", "S3", "S4"],  # TL, TR, BL, BR
        "labels": {"S1": "S1", "S2": "S2", "S3": "S3", "S4": "S4"},
    }


class WinStorage(tk.LabelFrame):
    """
    2x2 "Storage" sub-panel with configurable visual mapping.

    Only one cell can be selected at a time (single Radiobutton group).
    """

    def __init__(self, parent, info_win=None, title: str = "Storage"):
        super().__init__(parent, text=title)
        self.info = info_win
        self.factory = GUIFactory(self)

        # Configuration
        ids = list(STORAGE_CONFIG.get("ids", ["S1", "S2", "S3", "S4"]))
        order = list(STORAGE_CONFIG.get("order", ids))
        labels = dict(STORAGE_CONFIG.get("labels", {i: i for i in ids}))

        # Sanity: keep 4 elements and silently pad if needed
        def _take4(seq, fill=None):
            s = list(seq)[:4]
            while len(s) < 4:
                s.append(fill)
            return s

        ids = _take4(ids)
        order = _take4(order, ids[0])
        labels = {k: labels.get(k, k) for k in ids}

        # Members: visual order TL, TR, BL, BR
        self._order_visual = order           # e.g. ["S1","S2","S3","S4"]
        self._labels = labels                # e.g. {"S1":"S1", ...}

        # Single selection → IntVar (index 0..3 in order)
        self.var_storage_index = tk.IntVar(value=-1)

        self._storage_buttons: list[tk.Radiobutton] = []

        self._build()
        self.after(0, self._reset_selection)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build(self):
        """
        2x2 grid. Positions (indices var_storage_index):
          0: Top-Left
          1: Top-Right
          2: Bottom-Left
          3: Bottom-Right

        The logical ID returned corresponds to self._order_visual[index].
        """
        positions = [
            (0, 0),  # TL
            (0, 1),  # TR
            (1, 0),  # BL
            (1, 1),  # BR
        ]

        for idx, (r, c) in enumerate(positions):
            slot_id = self._order_visual[idx]
            text = self._labels.get(slot_id, slot_id)

            rb = tk.Radiobutton(
                self,
                text=text,
                variable=self.var_storage_index,
                value=idx,
                indicatoron=True,
                padx=6,
                pady=4,
                borderwidth=0,
                highlightthickness=0,
            )
            rb.grid(row=r, column=c, padx=8, pady=6, sticky="w")
            self._storage_buttons.append(rb)
            ToolTip(rb, f"Storage {slot_id}")

        # Optional: clean column layout
        for c in range(2):
            self.grid_columnconfigure(c, weight=0)

    def _reset_selection(self):
        """Ensure no selection at startup."""
        self.var_storage_index.set(-1)
        for rb in self._storage_buttons:
            try:
                rb.deselect()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_selected_storage(self) -> str | None:
        """
        Return the logical storage ID according to the visual mapping,
        e.g. 'S3', or None if nothing is selected.
        """
        idx = self.var_storage_index.get()
        if 0 <= idx < len(self._order_visual):
            return self._order_visual[idx]
        return None

    def set_selected_storage(self, storage_id: str) -> None:
        """
        Force a selection from a logical storage ID (S1..S4).
        If the ID is unknown, reset selection.
        """
        try:
            idx = self._order_visual.index(storage_id)
        except ValueError:
            self._reset_selection()
            return
        self.var_storage_index.set(idx)

    def log_selected(self):
        """Log the current selection if an Info window is provided."""
        if not self.info:
            return
        v = self.get_selected_storage()
        if v:
            self.info.add(f"Storage sélectionné: {v}")
        else:
            self.info.add("Aucun storage sélectionné.")
