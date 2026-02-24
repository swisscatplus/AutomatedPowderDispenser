#!/usr/bin/env python3

# BEC - November 2025
# Automated Powder Dispenser (APD) – application entry point.
#   - Creates the shared devices registry (UR3 + Mettler scale)
#   - Instantiates WinMain and starts the Tkinter main loop
#-------------------------------------------------------------------------------
"""Entry point for the Tkinter GUI of the Automated Powder Dispenser (APD)."""

from config import APP_CONFIG
import win
import tkinter as tk  # noqa: F401 (may be used indirectly by win.*)

#-------------------------------------------------------------------------------
# MAIN
#-------------------------------------------------------------------------------


def main():
    """
    Main entry point for the APD application.

    - Creates the shared `devices` dictionary used to store live connections
      (UR3 robot arm and Mettler balance).
    - Instantiates the main window (WinMain).
    - Starts the Tkinter event loop via `app.start()`.
    """
    # Shared hardware registry between windows.
    # Each entry is filled when the corresponding UI connects the device.
    devices = {
        "ur3": None,    # UR3 client (connected from the UI)
        "scale": None,  # Mettler balance (connected from the UI)
    }

    try:
        # Create the main application window.
        app = win.WinMain(devices)
        app.title(APP_CONFIG.get("window_title", "Automated Powder Dispenser"))

        # Start Tkinter mainloop (wrapped by WinMain.start()).
        app.start()
    finally:
        # Placeholder for future cleanup if needed (e.g. closing devices).
        # Currently no explicit cleanup is required here.
        pass


if __name__ == "__main__":
    main()
