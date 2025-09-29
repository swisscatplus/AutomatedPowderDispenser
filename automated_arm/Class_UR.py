import os
import json
import time
from typing import Optional, Dict, Any, List
import sys
from dashboard_client import DashboardClient


class UR:
    def __init__(self, ip_address, timeout_ms=5000, verbose=True):
        self.ip = ip_address
        self.dash = DashboardClient(ip_address, verbose=verbose)
        self.timeout_ms = timeout_ms
        self.connected = False

    def connect(self):
        print(f"Connecting to UR dashboard server at {self.ip}:29999…")
        ok = self.dash.connect()

        # Some versions return a bool, others don’t—so also check isConnected()
        if hasattr(self.dash, "isConnected"):
            ok = bool(ok) and self.dash.isConnected()
        if not ok:
            raise RuntimeError(f"Dashboard connect failed to {self.ip}:29999")
        self.connected = True
        print("✅ Dashboard connected")

    def disconnect(self):
        if self.connected:
            self.dash.disconnect()
            print("🔌 Disconnected from Dashboard")
            self.connected = False

    def run_program(self, program_name: str):
        """
        Load and play a URP program, blocking until completion.
        """
        if not self.connected:
            raise RuntimeError("UR3eController not connected")
        print(f"→ Loading {program_name} …")
        self.dash.loadURP(program_name)
        self.dash.play()
        while self.dash.running():
            time.sleep(0.2)
        print(f"✔ {program_name} complete")
