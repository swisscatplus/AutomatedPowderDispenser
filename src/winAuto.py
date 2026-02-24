#!/usr/bin/env python3

# BEC - November 2025
# Automated Powder Dispenser (APD) – simple automatic test sequence.
#   - Runs a full P1 → P4 loop with one dosing job
#   - Uses the same UR3 / balance checks as manual mode
#-------------------------------------------------------------------------------

import tkinter as tk
import time

from config import UR3_CONFIG

# .urp paths 
P1_PROGRAM = UR3_CONFIG["programs"]["P1"]
P2_PROGRAM = UR3_CONFIG["programs"]["P2"]
P3_PROGRAM = UR3_CONFIG["programs"]["P3"]
P4_PROGRAM = UR3_CONFIG["programs"]["P4"]


class WinAuto(tk.Frame):
    def __init__(self, parent, info_win, devices):
        super().__init__(parent)
        self.parent = parent
        self.win_info = info_win
        self.devices = devices

        # References to Manual Mode widgets
        self.win_robot = None     # WinRobotArm (for P1..P4)
        self.win_balance = None   # WinBalance (for the dosing job)

        # Auto sequence state
        self._seq_running = False
        self._seq_after_id = None

        self._build()

    # ------------------------------------------------------------------
    # Wiring with Manual Mode (called from winMode in win.py)
    # ------------------------------------------------------------------
    def attach_manual_views(self, robot_window, balance_window):
        """
        robot_window : instance of WinRobotArm (Manual Mode tab)
        balance_window : instance of WinBalance (Manual Mode tab)
        """
        self.win_robot = robot_window
        self.win_balance = balance_window

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build(self):
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)

        lbl = tk.Label(
            self,
            text="Mode automatique : test boucle complète P1 → P4 avec dosing",
            font=("TkDefaultFont", 10, "bold"),
        )
        lbl.grid(row=0, column=0, columnspan=2, sticky="w", padx=5, pady=(5, 2))

        self.btn_full_loop = tk.Button(
            self,
            text="Test boucle complète",
            width=22,
            command=self.on_test_full_loop,
        )
        self.btn_full_loop.grid(row=1, column=0, padx=5, pady=5, sticky="w")

        self.lbl_status = tk.Label(self, text="", anchor="w")
        self.lbl_status.grid(row=1, column=1, padx=5, pady=5, sticky="w")

    # ------------------------------------------------------------------
    # Log / status helpers
    # ------------------------------------------------------------------
    def _log(self, msg, level="info"):
        try:
            self.win_info.add(msg, level=level)
        except Exception:
            print(msg)
        try:
            self.lbl_status.configure(text=msg)
        except Exception:
            pass

    def _set_status(self, msg):
        try:
            self.lbl_status.configure(text=msg)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Auto-connect helpers for UR3 / balance
    # ------------------------------------------------------------------
    def _ensure_ur3_connected(self):
        """Make sure UR3 is connected. Use exactly the same logic as WinRobotArm 'Connect' button."""
        # If the key does not exist, create it with None to be safe
        if "ur3" not in self.devices:
            self.devices["ur3"] = None

        arm = self.devices.get("ur3")

        # Already connected → OK
        if arm and getattr(arm, "is_connected", lambda: False)():
            return True

        if not self.win_robot:
            self._log(
                "Mode Auto: WinRobotArm non initialisé, impossible de connecter automatiquement l'UR3.",
                level="error",
            )
            return False

        self._log("Mode Auto: UR3 non connecté, je lance 'Connect' dans le Mode Man…", level="info")

        # Use EXACTLY the same logic as the "Connect" button
        try:
            # This method does: _make_ur3() + arm.connect() + devices['ur3'] = arm + refresh
            self.win_robot.on_connect()
        except Exception as e:
            self._log(f"Mode Auto: erreur en appelant win_robot.on_connect(): {e}", level="error")
            return False

        # Re-read after connection
        arm = self.devices.get("ur3")
        if arm and getattr(arm, "is_connected", lambda: False)():
            self._log("Mode Auto: UR3 connecté automatiquement.", level="info")
            return True

        self._log(
            "Mode Auto: impossible de connecter automatiquement l'UR3. "
            "Connecte-le manuellement dans l'onglet 'Mode Man'.",
            level="error",
        )
        return False

    def _ensure_scale_connected(self):
        """Make sure the balance is connected. Use the same logic as WinBalance 'Connect' button."""
        if "scale" not in self.devices:
            self.devices["scale"] = None

        wm = self.devices.get("scale")

        # Already connected → OK
        if wm and getattr(wm, "is_connected", lambda: False)():
            return True

        if not self.win_balance:
            self._log(
                "Mode Auto: WinBalance non initialisé, impossible de connecter automatiquement la balance.",
                level="error",
            )
            return False

        self._log("Mode Auto: balance non connectée, je lance 'Connect' dans le Mode Man…", level="info")

        try:
            # WinBalance.on_connect() creates WM(), calls connect(), and sets devices['scale'] = wm
            self.win_balance.on_connect()
        except Exception as e:
            self._log(f"Mode Auto: erreur en appelant win_balance.on_connect(): {e}", level="error")
            return False

        wm = self.devices.get("scale")
        if wm and getattr(wm, "is_connected", lambda: False)():
            self._log("Mode Auto: balance connectée automatiquement.", level="info")
            return True

        self._log(
            "Mode Auto: impossible de connecter automatiquement la balance. "
            "Connecte-la manuellement dans l'onglet 'Mode Man'.",
            level="error",
        )
        return False

    # ------------------------------------------------------------------
    # Sequence entry point
    # ------------------------------------------------------------------
    def on_test_full_loop(self):
        if self._seq_running:
            self._log("Mode Auto: une séquence est déjà en cours.", level="warning")
            return
        
        if not self.win_robot or not self.win_balance:
            self._log(
                "Mode Auto: références win_robot / win_balance manquantes (wiring winMode).",
                level="error",
            )
            return

        # Auto-connect UR3 + balance
        if not self._ensure_ur3_connected():
            return
        if not self._ensure_scale_connected():
            return

        if not self.win_robot or not self.win_balance:
            self._log(
                "Mode Auto: références win_robot / win_balance manquantes (wiring winMode).",
                level="error",
            )
            return

        self._seq_running = True
        self._seq_after_id = None
        self._seq_seen_running = False

        self._set_status("Séquence P1→P4 en cours…")
        self._log("Mode Auto: démarrage de la séquence complète P1 → P4 avec dosing.", level="info")

        self._start_p1()

    # ------------------------------------------------------------------
    # End / abort management
    # ------------------------------------------------------------------
    def _abort_sequence(self, reason):
        if not self._seq_running:
            return
        self._seq_running = False
        if self._seq_after_id is not None:
            try:
                self.after_cancel(self._seq_after_id)
            except Exception:
                pass
            self._seq_after_id = None
        self._set_status("Séquence interrompue.")
        self._log(f"Mode Auto: séquence interrompue. {reason}", level="error")

    def _finish_sequence(self):
        if not self._seq_running:
            return
        self._seq_running = False
        self._seq_after_id = None
        self._set_status("Séquence complète terminée.")
        self._log("Mode Auto: séquence complète terminée (P1→P4 + dosing).", level="info")

    # ------------------------------------------------------------------
    # Robot steps: P1 / P2 / P3 / P4
    # ------------------------------------------------------------------
    def _check_load_ok(self, resp, step_name, program_path, human_name=None):
        """
        Check the response of load_program().
        - Standardized logging
        - If 'File not found' is detected → ABORT and return False.
        """
        label = human_name or program_path
        self._log(f"Mode Auto: lancement programme {label} ({step_name}).")
        self._log(f"UR3 load → {resp}", level="info")

        if isinstance(resp, str) and "FILE NOT FOUND" in resp.upper():
            self._abort_sequence(
                f"Programme {step_name} introuvable sur le robot ({program_path}). "
                "Vérifie le chemin / le nom du .urp."
            )
            return False

        return True
    
    def _start_p1(self):
        """Load P1Bastien.urp, run the same checks as manual mode, then start the program."""
        if not self._seq_running:
            return
        arm = self.devices.get("ur3")
        if not (arm and arm.is_connected()):
            self._abort_sequence("UR3 non connecté au lancement de P1.")
            return
        try:
            resp = arm.load_program(P1_PROGRAM)
            if not self._check_load_ok(resp, "P1", P1_PROGRAM, "P1Bastien.urp"):
                return  # do not call play() if the file is missing
            self._log("Mode Auto: lancement programme P1Bastien.urp (P1).")
            self._log(f"UR3 load → {resp}", level="info")

            # Align the robot UI with the loaded program
            try:
                self.win_robot.on_refresh_programs()
            except Exception:
                pass

            # Pre-checks for P1 (selected vial, door, empty pan, RTDE…)
            self.win_robot._play_p1(arm)

            # Start UR program
            before = arm.get_program_state()
            play_resp = arm.play()
            self._log(
                f"Mode Auto: démarrage programme P1 (state_before={before} ; play→{play_resp})",
                level="info",
            )

            # Put robot UI in 'running' and let its own watcher run
            try:
                self.win_robot._set_state("running")
                self.win_robot._start_run_watch()
            except Exception:
                pass

            # Wait for P1 completion before starting P2
            self._wait_robot_stopped(step_name="P1", next_step="P2")

        except Exception as e:
            self._abort_sequence(f"erreur lancement programme P1: {e}")

    def _start_p2(self):
        """Load P2Bastien.urp, run P2 checks, start, then wait for STOPPED → dosing."""
        if not self._seq_running:
            return
        arm = self.devices.get("ur3")
        if not (arm and arm.is_connected()):
            self._abort_sequence("UR3 non connecté au lancement de P2.")
            return
        try:
            resp = arm.load_program(P2_PROGRAM)
            if not self._check_load_ok(resp, "P2", P2_PROGRAM, "P2Bastien.urp"):
                return
            self._log("Mode Auto: lancement programme P2Bastien.urp (P2).")
            self._log(f"UR3 load → {resp}", level="info")

            try:
                self.win_robot.on_refresh_programs()
            except Exception:
                pass

            # Pre-checks for P2 (selected storage, no dispenser on pan, RTDE…)
            self.win_robot._play_p2(arm)

            before = arm.get_program_state()
            play_resp = arm.play()
            self._log(
                f"Mode Auto: démarrage programme P2 (state_before={before} ; play→{play_resp})",
                level="info",
            )

            try:
                self.win_robot._set_state("running")
                self.win_robot._start_run_watch()
            except Exception:
                pass

            self._wait_robot_stopped(step_name="P2", next_step="DOSING")

        except Exception as e:
            self._abort_sequence(f"erreur lancement programme P2: {e}")

    def _start_p3(self):
        """Load P3Bastien.urp, run P3 checks, start, then wait for STOPPED → P4."""
        if not self._seq_running:
            return
        arm = self.devices.get("ur3")
        if not (arm and arm.is_connected()):
            self._abort_sequence("UR3 non connecté au lancement de P3.")
            return
        try:
            resp = arm.load_program(P3_PROGRAM)
            if not self._check_load_ok(resp, "P3", P3_PROGRAM, "P3Bastien.urp"):
                return
            self._log("Mode Auto: lancement programme P3Bastien.urp (P3).")
            self._log(f"UR3 load → {resp}", level="info")

            try:
                self.win_robot.on_refresh_programs()
            except Exception:
                pass

            # Pre-checks for P3 (selected vial, open door, pan NOT empty…)
            self.win_robot._play_p3(arm)

            before = arm.get_program_state()
            play_resp = arm.play()
            self._log(
                f"Mode Auto: démarrage programme P3 (state_before={before} ; play→{play_resp})",
                level="info",
            )

            try:
                self.win_robot._set_state("running")
                self.win_robot._start_run_watch()
            except Exception:
                pass

            self._wait_robot_stopped(step_name="P3", next_step="P4")

        except Exception as e:
            self._abort_sequence(f"erreur lancement programme P3: {e}")

    def _start_p4(self):
        """Load P4Bastien.urp, run P4 checks, start, then wait for STOPPED → end of sequence."""
        if not self._seq_running:
            return
        arm = self.devices.get("ur3")
        if not (arm and arm.is_connected()):
            self._abort_sequence("UR3 non connecté au lancement de P4.")
            return
        try:
            resp = arm.load_program(P4_PROGRAM)
            if not self._check_load_ok(resp, "P4", P4_PROGRAM, "P4Bastien.urp"):
                return
            self._log("Mode Auto: lancement programme P4Bastien.urp (P4).")
            self._log(f"UR3 load → {resp}", level="info")

            try:
                self.win_robot.on_refresh_programs()
            except Exception:
                pass

            # Pre-checks for P4 (dosing head present and recognized…)
            self.win_robot._play_p4(arm)

            before = arm.get_program_state()
            play_resp = arm.play()
            self._log(
                f"Mode Auto: démarrage programme P4 (state_before={before} ; play→{play_resp})",
                level="info",
            )

            try:
                self.win_robot._set_state("running")
                self.win_robot._start_run_watch()
            except Exception:
                pass

            self._wait_robot_stopped(step_name="P4", next_step=None)

        except Exception as e:
            self._abort_sequence(f"erreur lancement programme P4: {e}")

    # ------------------------------------------------------------------
    # Wait for UR program end (STOPPED) by polling programState
    # ------------------------------------------------------------------
    def _wait_robot_stopped(self, step_name, next_step):
        """
        Monitor programState until we see STOPPED *after* having seen RUNNING/PAUSED,
        or after a short timeout (for very short programs).
        """
        if not self._seq_running:
            return

        start_ts = time.monotonic()
        seen_active = False   # have we already seen RUNNING or PAUSED for this program?

        def _poll():
            nonlocal seen_active

            if not self._seq_running:
                return

            arm = self.devices.get("ur3")
            if not (arm and arm.is_connected()):
                self._abort_sequence("UR3 déconnecté en cours de programme.")
                return

            try:
                raw = arm.get_program_state()  # e.g. "programState: PLAYING", "STOPPED P1Bastien.urp", ...
            except Exception as e:
                self._abort_sequence(f"Erreur lecture état programme ({step_name}): {e}")
                return

            # Normalize via the same function as WinRobotArm
            try:
                canon = self.win_robot._canon_prog_state(raw)
            except Exception:
                canon = str(raw or "").strip().upper()

            # Reflect raw state into WinRobotArm label (debug)
            try:
                self.win_robot.var_prog_state.set(raw)
            except Exception:
                pass

            # If we see RUNNING or PAUSED, we know the program really started
            if canon in ("RUNNING", "PAUSED"):
                seen_active = True

            if canon == "STOPPED":
                now = time.monotonic()

                # Case 1: STOPPED too early, without ever seeing RUNNING/PAUSED
                # → give a small window (~2 s) for the program to actually start.
                if not seen_active and (now - start_ts) < 2.0:
                    self._seq_after_id = self.after(200, _poll)
                    return

                # Case 2: either we have already seen RUNNING, or the timeout has passed
                # → consider the program finished.
                self._log(f"Mode Auto: programme {step_name} terminé (STOPPED).", level="info")
                try:
                    self.win_robot._set_state("idle")
                except Exception:
                    pass

                # Chain the next step
                if next_step == "P2":
                    self._start_p2()
                elif next_step == "DOSING":
                    self._start_dosing()
                elif next_step == "P3":
                    self._start_p3()
                elif next_step == "P4":
                    self._start_p4()
                else:
                    self._finish_sequence()
                return

            # Otherwise (still RUNNING/PAUSED/UNKNOWN) → poll again later
            self._seq_after_id = self.after(700, _poll)

        # First poll slightly delayed to avoid reading 'STOPPED' just before start
        self._seq_after_id = self.after(300, _poll)

    # ------------------------------------------------------------------
    # Dosing step: start job + wait for notification thread to finish
    # ------------------------------------------------------------------
    def _start_dosing(self):
        """Start the dosing job (like the 'Start dosing job' button) and wait for completion."""
        if not self._seq_running:
            return
        wm = self.devices.get("scale")
        if not (wm and wm.is_connected()):
            self._abort_sequence("Balance non connectée au lancement du dosing job.")
            return

        self._log("Mode Auto: démarrage du dosing job.", level="info")

        # Use exactly the same logic as the manual button
        try:
            self.win_balance.on_start_dosing_job()
        except Exception as e:
            self._abort_sequence(f"erreur lancement dosing job: {e}")
            return

        # Give WinBalance a short delay to create the thread
        self.after(300, self._check_dosing_started)

    def _check_dosing_started(self):
        """Check that the dosing notification thread really started."""
        if not self._seq_running:
            return
        t = getattr(self.win_balance, "_dosing_thread", None)
        if t is None or not t.is_alive():
            # No thread → job probably did not start
            self._abort_sequence(
                "dosing job non démarré (vérifie la présence de la vial et du dosing head)."
            )
            return

        self._log("Mode Auto: dosing job en cours… attente de fin avant P3.", level="info")
        self._wait_dosing_finished()

    def _wait_dosing_finished(self):
        """Poll _dosing_thread state until it finishes."""
        if not self._seq_running:
            return

        t = getattr(self.win_balance, "_dosing_thread", None)
        if t is None:
            # No more thread → consider it finished
            self._on_dosing_done()
            return

        if t.is_alive():
            # Still running → schedule another check
            self._seq_after_id = self.after(1000, self._wait_dosing_finished)
            return

        self._on_dosing_done()

    def _on_dosing_done(self):
        """Called when the dosing notification thread has finished (job completed)."""
        self._log("Mode Auto: dosing job terminé (Fin DosingAutomation détecté).", level="info")

        # Small safety delay before opening the door / starting P3
        self.after(1000, self._start_p3)
