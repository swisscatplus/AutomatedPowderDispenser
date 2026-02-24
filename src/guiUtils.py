#!/usr/bin/env python3

# BEC - November 2025
# Automated Powder Dispenser (APD) – shared GUI helper utilities.
#   - GUIFactory: helper class to create and grid common Tk widgets
#   - ToolTip: simple tooltip behaviour for arbitrary widgets
#-------------------------------------------------------------------------------
"""GUI helper utilities for the APD Tkinter application."""

import tkinter as tk
from tkinter import ttk  # kept for potential future usage
#-------------------------------------------------------------------------------


class GUIFactory:
    """
    Small helper/factory to create common Tkinter widgets with a consistent
    style and grid configuration.

    The idea is to reduce repetitive boilerplate in the different windows and
    centralize small layout decisions (padding, default width, etc.).
    """

    def __init__(self, parent: tk.Misc):
        """
        Parameters
        ----------
        parent : tk.Misc
            Parent container (Frame, LabelFrame, Toplevel, ...).
        """
        self.parent = parent

    def create_btn(
        self,
        label,
        command,
        row,
        column,
        state=tk.NORMAL,
        width=10,
        padx=5,
        pady=5,
        sticky=None,
        **kwargs,
    ) -> tk.Button:
        """
        Create a Button widget and grid it in one call.

        Parameters
        ----------
        label : str
            Text displayed on the button.
        command : callable
            Callback executed when the button is clicked.
        row, column : int
            Grid position.
        state : str, optional
            Tkinter state, e.g. tk.NORMAL or tk.DISABLED.
        width : int, optional
            Button width in characters.
        padx, pady : int, optional
            Grid padding (x/y).
        sticky : str or None, optional
            Grid sticky option; if None, no sticky is set.
        kwargs :
            Additional keyword arguments passed to tk.Button.

        Returns
        -------
        tk.Button
            The created button instance.
        """
        button = tk.Button(
            self.parent,
            text=label,
            command=command,
            width=width,
            state=state,
            **kwargs,
        )
        button.grid(
            row=row,
            column=column,
            padx=padx,
            pady=pady,
            sticky=sticky if sticky else "",
        )
        return button

    def create_label(
        self,
        text,
        row,
        column,
        padx=5,
        pady=5,
        sticky=tk.W,
        bg=None,
        fg=None,
        **kwargs,
    ) -> tk.Label:
        """
        Create a Label widget and grid it in one call.

        Color parameters (bg/fg) are only applied if explicitly provided,
        to avoid accidental default overrides.

        Parameters
        ----------
        text : str
            Label text.
        row, column : int
            Grid position.
        padx, pady : int, optional
            Grid padding.
        sticky : str, optional
            Grid sticky option (default: tk.W).
        bg, fg : str or None, optional
            Background / foreground colors. Ignored if None.
        kwargs :
            Additional keyword arguments passed to tk.Label.

        Returns
        -------
        tk.Label
            The created label instance.
        """
        label = tk.Label(self.parent, text=text, **kwargs)
        if bg is not None:
            label.configure(bg=bg)
        if fg is not None:
            label.configure(fg=fg)
        label.grid(row=row, column=column, padx=padx, pady=pady, sticky=sticky)
        return label

    def create_labelvariable(
        self,
        textvariable,
        row,
        column,
        padx=5,
        pady=5,
        sticky=tk.W,
        bg=None,
        fg=None,
        **kwargs,
    ) -> tk.Label:
        """
        Create a Label bound to a Tk variable (StringVar, DoubleVar, etc.).

        This is the variable-based counterpart of `create_label`.

        Parameters
        ----------
        textvariable : tk.Variable
            Tkinter variable to be displayed.
        row, column : int
            Grid position.
        padx, pady : int, optional
            Grid padding.
        sticky : str, optional
            Grid sticky option (default: tk.W).
        bg, fg : str or None, optional
            Background / foreground colors. Ignored if None.
        kwargs :
            Additional keyword arguments passed to tk.Label.

        Returns
        -------
        tk.Label
            The created label instance.
        """
        label = tk.Label(self.parent, textvariable=textvariable, **kwargs)
        if bg is not None:
            label.configure(bg=bg)
        if fg is not None:
            label.configure(fg=fg)
        label.grid(row=row, column=column, padx=padx, pady=pady, sticky=sticky)
        return label

    def create_entry(
        self,
        textvariable,
        row,
        column,
        width=10,
        padx=5,
        pady=5,
        sticky=tk.EW,
        **kwargs,
    ) -> tk.Entry:
        """
        Create an Entry widget and grid it in one call.

        Parameters
        ----------
        textvariable : tk.Variable
            Tkinter variable bound to the entry.
        row, column : int
            Grid position.
        width : int, optional
            Entry width in characters.
        padx, pady : int, optional
            Grid padding.
        sticky : str, optional
            Grid sticky option (default: tk.EW).
        kwargs :
            Additional keyword arguments passed to tk.Entry.

        Returns
        -------
        tk.Entry
            The created entry instance.
        """
        entry = tk.Entry(self.parent, textvariable=textvariable, width=width, **kwargs)
        entry.grid(row=row, column=column, padx=padx, pady=pady, sticky=sticky)
        return entry


class ToolTip:
    """
    Simple tooltip class that displays a small text message when the user
    hovers over a widget.

    The tooltip appears after a short delay and is destroyed when the mouse
    leaves the widget.
    """

    def __init__(self, widget: tk.Widget, text: str):
        """
        Parameters
        ----------
        widget : tk.Widget
            Widget for which the tooltip must be shown.
        text : str
            Tooltip text to display (user-facing; keep it in French where
            appropriate in the calling code).
        """
        self.widget = widget
        self.text = text
        self.tipwindow = None
        self.id = None

        # Delay before the tooltip appears (in milliseconds).
        self.delay = 500

        # Pixel offsets relative to the widget.
        self.x_offset = 20
        self.y_offset = 10

        # Bind mouse events.
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def enter(self, event=None):
        """Mouse entered the widget: schedule tooltip display."""
        self.schedule()

    def leave(self, event=None):
        """Mouse left the widget: cancel / hide tooltip."""
        self.unschedule()
        self.hidetip()

    # ------------------------------------------------------------------
    # Scheduling helpers
    # ------------------------------------------------------------------
    def schedule(self):
        """
        Schedule the tooltip display after `self.delay` ms.
        Any existing pending schedule is first canceled.
        """
        self.unschedule()
        self.id = self.widget.after(self.delay, self.showtip)

    def unschedule(self):
        """Cancel a pending tooltip display if there is one."""
        if self.id:
            self.widget.after_cancel(self.id)
            self.id = None

    # ------------------------------------------------------------------
    # Tooltip window management
    # ------------------------------------------------------------------
    def showtip(self, event=None):
        """
        Create and show the tooltip window near the widget.

        This uses a borderless Toplevel window containing a small Label
        with a light background.
        """
        x = self.widget.winfo_rootx() + self.x_offset
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + self.y_offset

        # Create a borderless Toplevel window.
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")

        label = tk.Label(
            tw,
            text=self.text,
            justify=tk.LEFT,
            background="#ffffe0",
            relief=tk.SOLID,
            borderwidth=1,
            font=("tahoma", "8", "normal"),
        )
        label.pack(ipadx=1)

    def hidetip(self):
        """Destroy the tooltip window if it exists."""
        if self.tipwindow:
            self.tipwindow.destroy()
            self.tipwindow = None
