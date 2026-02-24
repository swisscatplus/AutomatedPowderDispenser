#!/usr/bin/env python3

# BEC - November 2025
# Automated Powder Dispenser (APD) – manual mode panel.
#   - Embeds WinBalance (Mettler scale) and WinRobotArm (UR3)
#   - Provides shared manual controls reused by the automatic modes
#-------------------------------------------------------------------------------

import tkinter as tk
from winScale import WinBalance
from winRobotArm import WinRobotArm

class WinMan(tk.Frame):
    def __init__(self, parent, info_win, devices):
        super().__init__(parent)
        self.parent = parent
        self.win_info = info_win
        self.devices = devices

        # Allow the grid to stretch a bit
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # ---- Balance (scale) ----
        self.win_balance = WinBalance(self, self.win_info, self.devices)
        self.win_balance.grid(row=0, column=0, padx=5, pady=5, sticky=tk.NSEW)

        # ---- UR3 arm ----
        self.win_robot = WinRobotArm(self, self.win_info, self.devices)
        self.win_robot.grid(row=1, column=0, padx=5, pady=5, sticky=tk.NSEW)
        self.win_robot.grid_configure(columnspan=2)
