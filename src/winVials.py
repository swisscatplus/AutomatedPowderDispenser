#!/usr/bin/env python3

# BEC - November 2025
# Automated Powder Dispenser (APD) – vial selection sub-panel.
#   - Two independent groups of radiobuttons (E* and F* vial grids)
#   - Used by WinRobotArm and JSON/Auto modes to choose a vial
#-------------------------------------------------------------------------------
"""Compact vial selection panel (E*/F* grids) for the UR3."""

import tkinter as tk
import tkinter.ttk as ttk

from guiUtils import GUIFactory, ToolTip


class WinVials(tk.LabelFrame):
    """
    Sub-panel to select vials among several positions.

    There are two independent groups of Radiobuttons:
      - group E*: E1, E2, E3 (with 4,3,4 vials)
      - group F*: F1, F2, F3 (with 4,3,4 vials)

    Each group allows only one selection at a time.
    """

    def __init__(self, parent, info_win=None, title: str = "Vials"):
        super().__init__(parent, text=title)
        self.info = info_win
        self.factory = GUIFactory(self)

        # Small font to save some vertical space
        self.small_font = ("TkDefaultFont", 8)

        # Two independent index variables: one for E*, one for F*
        # -1 = no selection
        self.var_vial_index_c = tk.IntVar(value=-1)
        self.var_vial_index_f = tk.IntVar(value=-1)

        # Layout: (column_name, number_of_vials)
        self.vials_layout_c = [
            ("E1", 4),
            ("E2", 3),
            ("E3", 4),
        ]
        self.vials_layout_f = [
            ("F1", 4),
            ("F2", 3),
            ("F3", 4),
        ]

        # Storage for mapping index -> "E1-1", "F2-3", etc.
        self._vial_ids_c: list[str] = []
        self._vial_buttons_c: list[tk.Radiobutton] = []

        self._vial_ids_f: list[str] = []
        self._vial_buttons_f: list[tk.Radiobutton] = []

        self._build()

        # Important: force "no selection" state AFTER construction
        self.after(0, self._reset_selection)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_group(self, base_col: int, layout, var_index, ids_list, btn_list):
        """
        Build a staggered group of vials, starting from a base column.

        Parameters
        ----------
        base_col : int
            Starting column (0 for E*, 4 for F*, etc.)
        layout : list[tuple[str, int]]
            Example: [("E1",4), ("E2",3), ("E3",4)]
        var_index : tk.IntVar
            Index variable for this group.
        ids_list : list[str]
            List to append vial IDs ("E1-1", "E1-2", ...).
        btn_list : list[tk.Radiobutton]
            List to append the created Radiobuttons.
        """
        idx = 0  # index within this group

        for offset_col, (col_name, count) in enumerate(layout):
            col = base_col + offset_col

            # Column header
            lbl = tk.Label(self, text=col_name, font=self.small_font)
            lbl.grid(row=0, column=col, pady=(0, 1))

            for i in range(1, count + 1):
                # Compute row depending on the column to get a staggered layout
                if col_name.endswith("1") or col_name.endswith("3"):
                    # E1/E3/F1/F3: rows 1,3,5,7 (4 vials)
                    # (when count=3, only 3 rows will be used)
                    row = 1 + (i - 1) * 2      # 1,3,5,7
                elif col_name.endswith("2"):
                    # E2/F2: rows 2,4,6
                    row = 2 + (i - 1) * 2      # 2,4,6
                else:
                    row = i

                vial_id = f"{col_name}-{i}"
                ids_list.append(vial_id)

                rb = tk.Radiobutton(
                    self,
                    variable=var_index,
                    value=idx,              # each button has a unique index in ITS group
                    indicatoron=True,       # radio circle
                    font=self.small_font,
                    padx=0,
                    pady=0,
                    borderwidth=0,
                    highlightthickness=0,
                )
                rb.grid(row=row, column=col, padx=3, pady=0)

                btn_list.append(rb)
                ToolTip(rb, f"Vial {vial_id}")

                idx += 1

    def _build(self):
        """
        Build two compact staggered vial groups:

          - group E* on the left (E1, E2, E3)
          - group F* on the right (F1, F2, F3)
        """
        # Group E*: columns 0,1,2
        self._build_group(
            base_col=0,
            layout=self.vials_layout_c,
            var_index=self.var_vial_index_c,
            ids_list=self._vial_ids_c,
            btn_list=self._vial_buttons_c,
        )

        # Vertical separator in column 3
        # It goes from row=0 to row=8 (wide enough to cover all radios).
        sep = ttk.Separator(self, orient="vertical")
        sep.grid(row=0, column=3, rowspan=8, sticky="ns", padx=5)

        # Group F*: columns 4,5,6 (column 3 is just a visual gap)
        self._build_group(
            base_col=4,
            layout=self.vials_layout_f,
            var_index=self.var_vial_index_f,
            ids_list=self._vial_ids_f,
            btn_list=self._vial_buttons_f,
        )

    def _reset_selection(self):
        """
        Force the initial state: no vial selected in both groups.
        """
        self.var_vial_index_c.set(-1)
        self.var_vial_index_f.set(-1)
        for rb in self._vial_buttons_c:
            rb.deselect()
        for rb in self._vial_buttons_f:
            rb.deselect()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_selected_vial_e(self) -> str | None:
        """
        Return the selected vial in group E* (e.g. 'E2-3') or None.
        """
        idx = self.var_vial_index_c.get()
        if 0 <= idx < len(self._vial_ids_c):
            return self._vial_ids_c[idx]
        return None

    def get_selected_vial_f(self) -> str | None:
        """
        Return the selected vial in group F* (e.g. 'F1-2') or None.
        """
        idx = self.var_vial_index_f.get()
        if 0 <= idx < len(self._vial_ids_f):
            return self._vial_ids_f[idx]
        return None

    # Backward compatibility with old API: return group E by default
    def get_selected_vial(self) -> str | None:
        """Compatibility alias: same as get_selected_vial_e()."""
        return self.get_selected_vial_e()

    def set_selected_vial_c(self, vial_id: str) -> None:
        """
        Force a selection in group E* from a logical vial ID.
        """
        try:
            idx = self._vial_ids_c.index(vial_id)
        except ValueError:
            return
        self.var_vial_index_c.set(idx)

    def set_selected_vial_f(self, vial_id: str) -> None:
        """
        Force a selection in group F* from a logical vial ID.
        """
        try:
            idx = self._vial_ids_f.index(vial_id)
        except ValueError:
            return
        self.var_vial_index_f.set(idx)

    def log_selected(self):
        """
        Helper to log the current selections in the Info window (if provided).
        """
        if not self.info:
            return
        vc = self.get_selected_vial_e()
        vf = self.get_selected_vial_f()
        self.info.add(f"Vial E*: {vc if vc else 'Aucune'}")
        self.info.add(f"Vial F*: {vf if vf else 'Aucune'}")
