#!/usr/bin/env python3

# BEC - November 2025
# Automated Powder Dispenser (APD) – UR3 robot arm UI.
#   - Connects to the UR3 Dashboard and controls power/play/pause/stop
#   - Lists .urp programs and prepares RTDE registers for P1..P4 scenarios
#-------------------------------------------------------------------------------
"""Tkinter panel used to control the UR3 robot arm (Dashboard + RTDE)."""

import tkinter as tk
import tkinter.ttk as ttk
from contextlib import contextmanager

from config import UR3_CONFIG, STORAGE_CONFIG, SCALE_CONFIG
from guiUtils import GUIFactory, ToolTip
from deviceRobotArm import UR3, UR3ConnectionError
from winVials import WinVials
from winStorage import WinStorage

# ---------------------------------------------------------------------------
# Constants / Config
# ---------------------------------------------------------------------------
WATCH_PERIOD_MS = UR3_CONFIG.get("watch_period_ms", 3000)  # check connection every 3 s
RUN_POLL_MS = UR3_CONFIG.get("run_poll_ms", 700)       # polling period when a program is running (~0.7 s)
VIAL_ID_TO_NUMBER = UR3_CONFIG.get("vial_id_to_number", {})
RTDE_INPUT_REGISTER = int(UR3_CONFIG.get("rtde_input_register", 20))
DISP_RTDE_INPUT_REGISTER = int(UR3_CONFIG.get("disp_rtde_input_register", 21))


class WinRobotArm(tk.LabelFrame):
    """
    Control panel for UR3 (connection, state, play/pause/stop)
    with .urp autoload via a combobox.
    """

    # -----------------------------------------------------------------------
    # Construction / State
    # -----------------------------------------------------------------------
    def __init__(self, parent, info_win, devices):
        super().__init__(parent, text="UR3e Robot Arm")
        self.info = info_win
        self.devices = devices
        self.factory = GUIFactory(self)
        self._state = "idle"  # "idle" | "running" | "paused"

        # Endpoint / config
        self.var_ip = tk.StringVar(value=str(UR3_CONFIG.get("ip", "192.168.0.2")))
        self.var_script_port = tk.StringVar(value=str(UR3_CONFIG.get("script_port", 30002)))
        self.var_dashboard_port = tk.StringVar(value=str(UR3_CONFIG.get("dashboard_port", 29999)))

        # Status / modes
        self.var_status = tk.StringVar(value="Disconnected")
        self.var_robot_mode = tk.StringVar(value="-")
        self.var_safety_mode = tk.StringVar(value="-")
        self.var_program = tk.StringVar(value="-")      # dashboard line ("Loaded program: ...")
        self.var_prog_state = tk.StringVar(value="-")   # RUNNING/STOPPED/PAUSED from robot

        # Programs (.urp)
        self.var_selected_program = tk.StringVar(value="")
        self.cmb_programs: ttk.Combobox | None = None

        # UI widgets / state
        self.btn_connect: tk.Button | None = None
        self.btn_pause: tk.Button | None = None
        self.btn_stop: tk.Button | None = None
        self.btn_play: tk.Button | None = None
        self._suspend_combo_event = 0       # combobox event guard
        self._run_watch_id = None           # id of the "end-of-program" polling timer

        # Sub-windows
        self.win_vials: WinVials | None = None
        self.win_storage: WinStorage | None = None

        self._build()
        self.after(WATCH_PERIOD_MS, self._watch_period)

    # -----------------------------------------------------------------------
    # Context manager: combobox event guard
    # -----------------------------------------------------------------------
    @contextmanager
    def _combo_guard(self):
        """Temporarily disable combobox change events inside this context."""
        self._suspend_combo_event += 1
        try:
            yield
        finally:
            self._suspend_combo_event = max(0, self._suspend_combo_event - 1)

    def _combo_events_enabled(self) -> bool:
        """Return True if combobox events are currently enabled."""
        return self._suspend_combo_event == 0

    # -----------------------------------------------------------------------
    # Hardware helpers / mapping
    # -----------------------------------------------------------------------
    def _make_ur3(self) -> UR3:
        """Create a new UR3 instance using the current UI endpoint values."""
        return UR3(
            ip=self.var_ip.get().strip(),
            script_port=int(self.var_script_port.get()),
            dashboard_port=int(self.var_dashboard_port.get()),
        )

    def _get_ur3(self) -> UR3:
        """Return the connected UR3 instance or raise if not connected."""
        arm = self.devices.get("ur3")
        if not arm:
            raise RuntimeError("Bras UR3 non connecté (devices['ur3'] est vide).")
        return arm

    def _get_scale(self):
        """Return the balance instance if connected, otherwise None."""
        return self.devices.get("scale")

    def _vial_id_to_number(self, vial_id: str) -> int:
        """Map a vial logical ID (e.g. 'E1-1') to its numeric index for RTDE."""
        try:
            return int(VIAL_ID_TO_NUMBER[vial_id])
        except KeyError:
            raise ValueError(f"vial_id inconnu ou non mappé: {vial_id!r}")

    def _storage_id_to_number(self, storage_id: str) -> int:
        """Map a storage logical ID (e.g. 'S1') to its numeric index for RTDE."""
        m = (STORAGE_CONFIG.get("id_to_number") or {})
        if storage_id in m:
            return int(m[storage_id])
        if isinstance(storage_id, str) and storage_id.upper().startswith("S"):
            return int(storage_id[1:])
        raise ValueError(f"storage_id invalide: {storage_id!r}")

    # -----------------------------------------------------------------------
    # UI build / wiring
    # -----------------------------------------------------------------------
    def _build(self):
        """Build all widgets for the UR3 control UI."""
        for c in range(12):
            self.columnconfigure(c, weight=0, minsize=80)

        # Row 0: Connection + system actions
        self.btn_connect = self.factory.create_btn("Connect", self.on_connect, 0, 0, width=12, sticky=tk.EW)
        ToolTip(self.btn_connect, "Connexion Dashboard à l’UR3")

        btn_refresh_modes = self.factory.create_btn("Refresh modes", self.on_refresh_modes, 0, 1, width=14, sticky=tk.W)
        ToolTip(btn_refresh_modes, "Relit robotmode / safetymode")
        self.btn_refresh_modes = btn_refresh_modes

        btn_disconnect = self.factory.create_btn("Disconnect", self.on_disconnect, 0, 2, width=12, sticky=tk.EW)
        ToolTip(btn_disconnect, "Fermer proprement la connexion Dashboard/Script")
        btn_disconnect.configure(state="disabled")
        self.btn_disconnect = btn_disconnect

        btn_power_on  = self.factory.create_btn("Power ON",  self.on_power_on,  0, 3)
        ToolTip(btn_power_on, "Dashboard: 'power on'")
        btn_power_off = self.factory.create_btn("Power OFF", self.on_power_off, 0, 4)
        ToolTip(btn_power_off, "Dashboard: 'power off'")
        btn_brake_rel = self.factory.create_btn("Brake release", self.on_brake_release, 0, 5)
        ToolTip(btn_brake_rel, "Dashboard: 'brake release'")

        self.btn_power_on  = btn_power_on
        self.btn_power_off = btn_power_off
        self.btn_brake_rel = btn_brake_rel

        # Row 1: Status labels
        self.factory.create_label("Status", 1, 0, sticky=tk.W)
        lbl_status = self.factory.create_labelvariable(self.var_status, 1, 1, sticky=tk.W)
        lbl_rm = self.factory.create_labelvariable(self.var_robot_mode, 1, 2, sticky=tk.W); lbl_rm.grid_configure(columnspan=2)
        lbl_sm = self.factory.create_labelvariable(self.var_safety_mode, 1, 4, sticky=tk.W); lbl_sm.grid_configure(columnspan=2)
        lbl_prog = self.factory.create_labelvariable(self.var_program, 1, 6, sticky=tk.W); lbl_prog.grid_configure(columnspan=2)
        lbl_prog_state = self.factory.create_labelvariable(self.var_prog_state, 1, 8, sticky=tk.W); lbl_prog_state.grid_configure(columnspan=2)
        ToolTip(lbl_status, "État de la connexion")
        ToolTip(lbl_rm, "Robot mode")
        ToolTip(lbl_sm, "Safety mode")

        # Separator
        ttk.Separator(self, orient="horizontal").grid(row=2, column=0, columnspan=12, sticky="ew", pady=(5, 5))

        # Row 3: Program selection
        self.factory.create_label("Program (.urp)", 3, 0, sticky=tk.W)
        self.cmb_programs = ttk.Combobox(
            self,
            textvariable=self.var_selected_program,
            width=48,
            state="readonly",
            values=[],
        )
        self.cmb_programs.grid(row=3, column=1, columnspan=3, sticky="ew", padx=2)
        self.cmb_programs.bind("<<ComboboxSelected>>", self._on_program_selected)

        self.btn_play  = self.factory.create_btn("Play",  self.on_play,  3, 4); ToolTip(self.btn_play, "Dashboard: 'play'")
        self.btn_pause = self.factory.create_btn("Pause", self.on_pause, 3, 5); ToolTip(self.btn_pause, "Dashboard: 'pause'")
        self.btn_stop  = self.factory.create_btn("Stop",  self.on_stop,  3, 6); ToolTip(self.btn_stop, "Dashboard: 'stop'")

        # Row 4+: sub-panels (vials + storage)
        self.win_vials = WinVials(self, self.info, title="Vials")
        self.win_vials.grid(row=5, column=0, columnspan=2, sticky="ns", padx=5, pady=5)

        self.win_storage = WinStorage(self, self.info, title="Storage")
        self.win_storage.grid(row=5, column=4, columnspan=3, sticky="ns", padx=5, pady=5)

        self._bind_shortcuts()
        self._set_connected_ui(False, initialize=True)

    def _bind_shortcuts(self):
        """Bind global keyboard shortcuts (e.g. ESC to stop)."""
        root = self.winfo_toplevel()

        def _stop(_e=None):
            self.on_stop()
            return "break"

        root.bind_all("<Escape>", _stop, add="+")

    # -----------------------------------------------------------------------
    # Connection / Heartbeat
    # -----------------------------------------------------------------------
    def _set_connected_ui(self, connected: bool, *, initialize: bool = False):
        """
        Enable/disable UI elements according to connection state.
        If initialize=True, also reset play/pause/stop state.
        """
        if connected:
            self.btn_connect.configure(state="disabled", text="Connected")
            self.btn_disconnect.configure(state="normal")
        else:
            self.btn_connect.configure(state="normal", text="Connect")
            self.btn_disconnect.configure(state="disabled")

        generic_targets = [
            self.btn_refresh_modes, self.btn_disconnect,
            self.btn_power_on, self.btn_power_off, self.btn_brake_rel,
        ]
        if initialize:
            generic_targets += [self.btn_play, self.btn_pause, self.btn_stop]

        state = "normal" if connected else "disabled"
        for w in generic_targets:
            try:
                w.configure(state=state)
            except Exception:
                pass

        try:
            self.cmb_programs.configure(state="readonly" if connected else "disabled")
        except Exception:
            pass

        if initialize:
            if connected:
                self._set_state("idle")
            else:
                self.btn_play.configure(state="disabled")
                self.btn_pause.configure(state="disabled", text="Pause")
                self.btn_stop.configure(state="disabled")

    def _set_state(self, state: str):
        """
        Update the local UI state: 'idle', 'running', or 'paused',
        and adjust play/pause/stop button states accordingly.
        """
        self._state = state
        if state == "idle":
            self.btn_play.configure(state="normal")
            self.btn_pause.configure(text="Pause", state="disabled")
            self.btn_stop.configure(state="disabled")
        elif state == "running":
            self.btn_play.configure(state="disabled")
            self.btn_pause.configure(text="Pause", state="normal")
            self.btn_stop.configure(state="normal")
        elif state == "paused":
            self.btn_play.configure(state="disabled")
            self.btn_pause.configure(text="Continue", state="normal")
            self.btn_stop.configure(state="normal")

    def on_connect(self):
        """Connect to the UR3 Dashboard, update UI and auto-refresh modes/program list."""
        if self.btn_connect:
            self.btn_connect.configure(state="disabled", text="Connecting…")
        if getattr(self, "btn_disconnect", None):
            self.btn_disconnect.configure(state="normal")
        try:
            arm = self._make_ur3()
            banner = arm.connect()
            self.devices["ur3"] = arm
            self._set_connected_ui(True, initialize=True)
            self.var_status.set("Connected")
            self.info.add(f"UR3 connecté. Dashboard: {banner or '—'}")
            if self.btn_connect:
                self.btn_connect.configure(state="disabled", text="Connected")

            # Small post-connect bootstrap: refresh modes + program list
            def _post_connect_bootstrap():
                try:
                    self.on_refresh_modes()
                except Exception as e:
                    self.info.add(f"Auto-Refresh modes après connexion → ERREUR : {e}", level="error")
                try:
                    self.on_refresh_programs()
                except Exception as e:
                    self.info.add(f"Auto-Refresh list après connexion → ERREUR : {e}", level="error")

            self.after(150, _post_connect_bootstrap)

        except Exception as e:
            if self.btn_connect:
                self.btn_connect.configure(state="normal", text="Connect")
            self.var_status.set("Error")
            self.info.add(f"Erreur connexion UR3: {e}", level="error")

    def _force_need_reconnect(self, reason: str = ""):
        """
        Force the internal state to 'need reconnect' when UR3 switches to Local/Teach
        or when the Dashboard reports a safety/permission issue.
        """
        try:
            if self.devices.get("ur3"):
                self.devices["ur3"].close()
        except Exception:
            pass
        self.devices["ur3"] = None
        self.var_status.set("Need Reconnect")
        self._set_connected_ui(False, initialize=True)
        self.btn_connect.configure(text="Reconnect")
        self.info.add(
            "UR3: mode Local/Teach détecté → reconnectez en Remote (Dashboard 29999)."
            + (f" Détail: {reason}" if reason else ""),
            level="warning",
        )

    def on_disconnect(self):
        """Cleanly close UR3 connections and reset the UI."""
        try:
            if self.devices.get("ur3"):
                self.devices["ur3"].close()
        finally:
            self.devices["ur3"] = None
        self._stop_run_watch()
        self.var_status.set("Disconnected")
        self.btn_connect.configure(state="normal", text="Connect")
        self.btn_disconnect.configure(state="disabled")
        self.info.add("UR3: déconnecté proprement.")
        self._set_connected_ui(False, initialize=True)

    def _watch_period(self):
        """
        Periodic connection check:
        - if the UR3 is responsive → keep UI as connected
        - otherwise → mark as disconnected and close the client.
        """
        try:
            arm = self.devices.get("ur3")
            ok = bool(arm and arm.is_connected() and arm.ping())
        except Exception:
            ok = False

        if ok:
            self._set_connected_ui(True, initialize=False)
            self.var_status.set("Connected")
        else:
            self._set_connected_ui(False, initialize=True)
            if self.devices.get("ur3"):
                self.info.add("UR3: connexion perdue.", level="warning")
                try:
                    self.devices["ur3"].close()
                except Exception:
                    pass
                self.devices["ur3"] = None
            self.var_status.set("Disconnected")
        self.after(WATCH_PERIOD_MS, self._watch_period)

    # ------------------------------------------------------------------
    # Run watch (end-of-program polling)
    # ------------------------------------------------------------------
    def _canon_prog_state(self, s: str) -> str:
        """
        Normalize the raw Dashboard text into:
        RUNNING / PAUSED / STOPPED / UNKNOWN.

        Handles 'PLAYING', 'PAUSE', and prefixes like 'programState:'.
        """
        up = str(s or "").strip().upper()
        if ":" in up:  # e.g. "programState: PLAYING"
            up = up.split(":", 1)[1].strip()
        if "PLAYING" in up or "RUNNING" in up:
            return "RUNNING"
        if "PAUSE" in up or "PAUSED" in up:
            return "PAUSED"
        if "STOPPED" in up or up == "IDLE" or up == "READY":
            return "STOPPED"
        return "UNKNOWN"

    def _start_run_watch(self):
        """Start program-state polling while the UI state is 'running'."""
        if self._run_watch_id:  # already active
            return
        # First tick immediately
        self._run_watch()

    def _stop_run_watch(self):
        """Stop program-state polling if active."""
        if self._run_watch_id is not None:
            try:
                self.after_cancel(self._run_watch_id)
            except Exception:
                pass
            self._run_watch_id = None

    def _run_watch(self):
        """
        Periodically poll programState. If the UI is no longer 'running',
        stop polling. If we detect STOPPED, switch to idle.
        """
        # If UI is not 'running' anymore, stop polling
        if self._state != "running":
            self._stop_run_watch()
            return

        try:
            arm = self._get_ur3()
            raw = arm.get_program_state()            # e.g. "programState: PLAYING"
            canon = self._canon_prog_state(raw)      # RUNNING / PAUSED / STOPPED / UNKNOWN

            # (optional) reflect what we read into the label for debug
            try:
                self.var_prog_state.set(raw)
            except Exception:
                pass

            if canon == "STOPPED":
                self.info.add("UR3: programme terminé (state=STOPPED).")
                self._set_state("idle")              # → Play enabled, Pause/Stop disabled
                self._stop_run_watch()
            elif canon == "PAUSED" and self._state == "running":
                # Robot went to pause without going through the Pause button
                self.info.add("UR3: programme en pause (détecté par watcher).")
                self._set_state("paused")

        except Exception as e:
            self.info.add(f"Run watch: erreur sondage état programme → {e}", level="warning")
            self._stop_run_watch()
        finally:
            if self._state == "running":
                self._run_watch_id = self.after(RUN_POLL_MS, self._run_watch)

    # -----------------------------------------------------------------------
    # Dashboard helpers
    # -----------------------------------------------------------------------
    def _call_dash(self, label: str, func):
        """
        Call a Dashboard function and handle common error cases, including
        Local/Teach mode or safety errors that require a reconnect.
        """
        try:
            arm = self._get_ur3()
            resp = func(arm)
            txt = (resp or "").lower()
            if (
                ("remote control mode" in txt)
                or ("reconnect to port 29999" in txt)
                or ("not allowed due to safety" in txt)
            ):
                self.info.add(f"UR3 {label} → {resp}")
                self._force_need_reconnect(reason=resp)
                return
            self.info.add(f"UR3 {label} → {resp}")
        except (RuntimeError, UR3ConnectionError) as e:
            self.info.add(f"UR3 {label} → ERREUR : {e}", level="error")
            self.var_status.set("Error")

    def on_power_on(self):
        self._call_dash("power on", lambda arm: arm.power_on())

    def on_power_off(self):
        self._call_dash("power off", lambda arm: arm.power_off())

    def on_brake_release(self):
        self._call_dash("brake release", lambda arm: arm.brake_release())

    def on_refresh_modes(self):
        """Refresh robot mode, safety mode, loaded program and state, and align the UI."""
        try:
            arm = self._get_ur3()
            rm = arm.get_robot_mode()
            sm = arm.get_safety_mode()
            self.var_robot_mode.set(rm)
            self.var_safety_mode.set(sm)
            self.info.add(f"UR3 robotmode → {rm}")
            self.info.add(f"UR3 safetymode → {sm}")

            prog  = arm.get_loaded_program()
            state = arm.get_program_state()
            self.var_program.set(prog)        # "Loaded program: …"
            self.var_prog_state.set(state)    # "programState: PLAYING/PAUSE/…"
            self.info.add(f"UR3 programme → {prog}")
            self.info.add(f"UR3 state → {state}")

            # Align UI with robot state
            canon = self._canon_prog_state(state)  # RUNNING / PAUSED / STOPPED / UNKNOWN
            if canon == "RUNNING":
                self._set_state("running")
                self._start_run_watch()  # restart watcher if needed
            elif canon == "PAUSED":
                self._set_state("paused")
            elif canon == "STOPPED":
                self._set_state("idle")
                self._stop_run_watch()

        except (RuntimeError, UR3ConnectionError) as e:
            self.info.add(f"UR3 refresh modes → ERREUR : {e}", level="error")
            self.var_status.set("Error")

    # -----------------------------------------------------------------------
    # Programs: loaded state / refresh / autoload
    # -----------------------------------------------------------------------
    def _extract_loaded_path(self, s: str) -> str:
        """Extract the path part from 'Loaded program: /path/to/file.urp'."""
        s = (s or "").strip()
        if not s:
            return ""
        return s.split(":", 1)[1].strip() if ":" in s else s

    def _current_loaded_path(self) -> str:
        """Return the currently loaded program path as shown in var_program."""
        return self._extract_loaded_path(self.var_program.get())

    def _on_program_selected(self, _event=None):
        """Combobox handler: load the selected program if UR3 is connected."""
        if not self._combo_events_enabled():
            return
        try:
            self._get_ur3()
        except Exception:
            self.info.add("Sélection ignorée : UR3 non connecté.", level="warning")
            return
        self.on_load_selected_program()

    def on_refresh_programs(self):
        """Refresh the list of .urp programs from the robot and update the combobox."""
        try:
            arm = self._get_ur3()
            progs = arm.list_programs()
            if not progs:
                self.info.add("UR3: aucun programme .urp trouvé sur /programs", level="warning")

            with self._combo_guard():
                self.cmb_programs["values"] = progs
                try:
                    loaded_line = arm.get_loaded_program()
                except Exception:
                    loaded_line = self.var_program.get()
                loaded_path = self._extract_loaded_path(loaded_line)
                if loaded_path and loaded_path in progs:
                    self.var_selected_program.set(loaded_path)
                else:
                    self.var_selected_program.set(loaded_path if loaded_path else (progs[0] if progs else ""))

            self.info.add(f"UR3: {len(progs)} programme(s) trouvé(s).")
        except (RuntimeError, UR3ConnectionError) as e:
            self.info.add(f"UR3 refresh programs → ERREUR : {e}", level="error")

    def on_load_selected_program(self):
        """Send a 'load program' command for the currently selected program."""
        prog = self.var_selected_program.get().strip()
        if not prog:
            self.info.add("Load program → aucun programme sélectionné.", level="warning")
            return

        def _do(arm):
            resp = arm.load_program(prog)
            return f"load {prog} → {resp}"

        self._call_dash("load", _do)

        with self._combo_guard():
            self.var_selected_program.set(prog)

        self.after(150, self.on_refresh_modes)

    # -----------------------------------------------------------------------
    # Play / Pause / Stop
    # -----------------------------------------------------------------------
    def on_play(self):
        """
        Handle Play button:
        - run the dedicated P1/P2/P3/P4 pre-checks if the filename contains P1..P4
        - otherwise use the default 'play' helper.
        """
        try:
            arm = self._get_ur3()
            loaded_path = self._current_loaded_path()
            prog_name = loaded_path.split("/")[-1] if loaded_path else ""
            low = prog_name.lower()
            if   "p1" in low: self._play_p1(arm)
            elif "p2" in low: self._play_p2(arm)
            elif "p3" in low: self._play_p3(arm)
            elif "p4" in low: self._play_p4(arm)
            else:             self._play_default(arm)

            before = arm.get_program_state()
            resp   = arm.play()
            self._set_state("running")
            self.btn_stop.configure(state="normal")
            self._start_run_watch()
            self.after(150, self.on_refresh_modes)
            after  = arm.get_program_state()
            self.info.add(f"UR3 play → state_before={before} ; play→{resp} ; state_after={after}")
        except (RuntimeError, UR3ConnectionError, ValueError) as e:
            self.info.add(f"UR3 play → ERREUR : {e}", level="error")
            self.var_status.set("Error")

    def on_pause(self):
        """Toggle pause/continue depending on the current state."""
        try:
            arm = self._get_ur3()
            if self._state == "running":
                resp = arm.pause()
                self.info.add(f"UR3 pause → {resp}")
                self._set_state("paused")
            elif self._state == "paused":
                resp = arm.play()
                self.info.add(f"UR3 continue (play) → {resp}")
                self._set_state("running")
            else:
                self.info.add("Pause ignorée (état idle).", level="warning")
                return
            self.after(120, self.on_refresh_modes)
        except (RuntimeError, UR3ConnectionError) as e:
            self.info.add(f"UR3 pause/continue → ERREUR : {e}", level="error")
            self.var_status.set("Error")

    def on_stop(self):
        """Send a 'stop' to the robot and reset local run watcher."""
        self._call_dash("stop", lambda arm: arm.stop())
        self._stop_run_watch()
        self._set_state("idle")

    # -----------------------------------------------------------------------
    # P1 / P2 / P3 / P4 scenarios
    # -----------------------------------------------------------------------
    def _play_p1(self, arm: UR3):
        """
        P1 scenario:
        - ensure a vial is selected
        - ensure balance door is open
        - ensure pan is empty
        - set RTDE vial number (VialsNB).
        """
        vial_id, group = self._get_selected_vial_any()
        if not vial_id:
            self.info.add("Play (P1) → aucune vial E* ni F* sélectionnée.", level="warning")
            raise RuntimeError("Vial requise pour P1")

        vnum = self._vial_id_to_number(vial_id)
        self._ensure_scale_door_open()
        if not self._is_pan_empty():
            self.info.add(
                "Play (P1) → La pan n'est pas vide. Merci de vider la balance, puis relance.",
                level="warning",
            )
            raise RuntimeError("Pan non vide")
        arm.stop()
        arm.set_vials_nb(vnum)
        self.info.add(f"UR3 RTDE: VialsNB ← {vnum} ({vial_id}, groupe {group})")

    def _play_p2(self, arm: UR3):
        """
        P2 scenario:
        - ensure a storage is selected
        - ensure no dispenser is already present on the pan
        - set RTDE dispenser number (DispNB).
        """
        storage_id = self.get_selected_storage()
        if not storage_id:
            self.info.add("Play (P2) → aucun Storage sélectionné (S1..S4).", level="warning")
            raise RuntimeError("Storage requis")
        dnum = self._storage_id_to_number(storage_id)
        if self._is_dispenser_present():
            name = self._get_scale_dispenser_name()
            self.info.add(
                f"Play (P2) → Un dispenser est déjà présent sur la balance ({name or '—'})."
                " Retire-le puis relance.",
                level="warning",
            )
            raise RuntimeError("Dispenser déjà présent")
        arm.stop()
        arm.set_disp_nb(int(dnum))
        self.info.add(f"UR3 RTDE: DispNB ← {dnum} (Storage {storage_id})")

    def _play_p3(self, arm: UR3):
        """
        P3 scenario:
        - ensure a vial is selected
        - ensure balance door is open
        - ensure pan is NOT empty
        - set RTDE vial number (VialsNB).
        """
        vial_id, group = self._get_selected_vial_any()
        if not vial_id:
            self.info.add("Play (P3) → aucune vial E* ni F* sélectionnée.", level="warning")
            raise RuntimeError("Vial requise pour P3")
        vnum = self._vial_id_to_number(vial_id)
        self._ensure_scale_door_open()
        if self._is_pan_empty():
            self.info.add(
                "Play (P3) → La pan est pas vide. Le mouvement ne sert à rien.",
                level="warning",
            )
            raise RuntimeError("Pan vide → inutile")
        arm.stop()
        arm.set_vials_nb(vnum)  # GPii[20]
        self.info.add(f"UR3 RTDE: VialsNB ← {vnum} ({vial_id}, groupe {group})")

    def _play_p4(self, arm: UR3):
        """
        P4 scenario:
        - read dispenser name from the balance
        - map it to a storage position via STORAGE_CONFIG['labels']
        - set RTDE dispenser number (DispNB).
        """
        name = self._get_scale_dispenser_name()
        if not name:
            self.info.add(
                "Play (P4) → Aucun dosing head détecté (nom vide). Place un dispenser puis relance.",
                level="warning",
            )
            raise RuntimeError("Pas de dispenser")
        storage_id, dnum = self._find_storage_by_substance_label(name)
        if not storage_id or dnum is None:
            self.info.add(
                f"Play (P4) → Substance '{name}' introuvable dans STORAGE_CONFIG['labels'].",
                level="warning",
            )
            raise RuntimeError("Label inconnu")
        arm.stop()
        arm.set_disp_nb(int(dnum))  # GPii[21]
        self.info.add(f"UR3 RTDE: DispNB ← {dnum} (via label '{name}', storage {storage_id})")

    def _play_default(self, arm: UR3):
        """
        Default scenario (non P1..P4):
        - if a vial is selected, set VialsNB accordingly.
        """
        vial_id, group = self._get_selected_vial_any()
        arm.stop()
        if vial_id:
            vnum = self._vial_id_to_number(vial_id)
            arm.set_vials_nb(vnum)
            self.info.add(f"UR3 RTDE: VialsNB ← {vnum} ({vial_id}, groupe {group})")

    # -----------------------------------------------------------------------
    # Vials / Storage access (UI)
    # -----------------------------------------------------------------------
    def get_selected_vial_e(self) -> str | None:
        """Return selected vial ID in group E, or None."""
        return self.win_vials.get_selected_vial_e() if self.win_vials else None

    def get_selected_vial_f(self) -> str | None:
        """Return selected vial ID in group F, or None."""
        return self.win_vials.get_selected_vial_f() if self.win_vials else None

    def _get_selected_vial_any(self) -> tuple[str | None, str]:
        """Return (vial_id, group) where group is 'E', 'F', or '' if nothing is selected."""
        v = self.get_selected_vial_e()
        if v:
            return v, "E"
        v = self.get_selected_vial_f()
        if v:
            return v, "F"
        return None, ""

    def get_selected_storage(self) -> str | None:
        """Return selected storage ID (S1..), or None."""
        return self.win_storage.get_selected_storage() if self.win_storage else None

    # -----------------------------------------------------------------------
    # Balance helpers (door / pan / dispenser)
    # -----------------------------------------------------------------------
    def _is_scale_door_open(self) -> bool:
        """Return True if at least one door is reported as open (width > 0)."""
        wm = self._get_scale()
        if not wm:
            return False
        try:
            pos = wm.get_door_positions() or {}
            if not isinstance(pos, dict):
                return False

            def _to_int(v):
                try:
                    return int(v) if str(v).isdigit() else int(float(v))
                except Exception:
                    return 0

            return any(_to_int(v) > 0 for v in pos.values())
        except Exception:
            return False

    def _ensure_scale_door_open(self):
        """
        Ensure the balance door is open.
        If the balance is not connected, only log a warning.
        """
        wm = self._get_scale()
        if not wm:
            self.info.add("Balance non connectée → je ne peux pas ouvrir la porte.", level="warning")
            return
        try:
            if self._is_scale_door_open():
                self.info.add("Porte balance déjà ouverte.")
                return
            resp = wm.open_door()
            self.info.add(f"Open door (balance) → {resp}")
        except Exception as e:
            self.info.add(f"Open door (balance) a échoué: {e}", level="error")

    def _is_pan_empty(self) -> bool:
        """
        Use is_pan_present() to determine if the pan is empty
        and log detailed statistics.
        """
        wm = self._get_scale()
        if not wm:
            self.info.add(
                "Balance non connectée → impossible de vérifier que la pan est vide.",
                level="warning",
            )
            return False  # be conservative and block
        try:
            min_mg = float(SCALE_CONFIG.get("vial_presence_min_mg", 1000.0))
            present, stats = wm.is_pan_present(min_present_mg=min_mg, samples=8, sleep_s=0.04)
            mean_mg   = (stats.get("mean_gross_g") or 0.0) * 1000.0
            thr_mg    = (stats.get("threshold_g") or (min_mg / 1000.0)) * 1000.0
            std_mg    = (stats.get("std_gross_g") or 0.0) * 1000.0
            n_samples = int(stats.get("n") or 0)
            if present:
                self.info.add(
                    f"Plateau OCCUPÉ (Gross mean={mean_mg:.1f} mg, σ={std_mg:.1f} mg, "
                    f"seuil={thr_mg:.1f} mg, n={n_samples})",
                    level="warning",
                )
                return False
            else:
                self.info.add(
                    f"Plateau VIDE (Gross mean={mean_mg:.1f} mg, σ={std_mg:.1f} mg, "
                    f"seuil={thr_mg:.1f} mg, n={n_samples})"
                )
                return True
        except Exception as e:
            self.info.add(f"Balance: is_pan_present() a échoué → {e}", level="error")
            return False

    def _get_scale_dispenser_name(self) -> str:
        """Return the current dosing head name from the balance, or an empty string."""
        wm = self._get_scale()
        if not wm:
            return ""
        try:
            return (wm.get_dosing_head_name() or "").strip()
        except Exception:
            return ""

    def _is_dispenser_present(self) -> bool:
        """Return True iff a dosing head name is reported by the balance."""
        return bool(self._get_scale_dispenser_name())

    def _norm_label(self, s: str) -> str:
        """Normalize a label: lowercased, extra spaces removed."""
        return " ".join(str(s or "").strip().lower().split())

    def _find_storage_by_substance_label(self, substance_name: str) -> tuple[str | None, int | None]:
        """
        Given a substance label (from dosing head / JSON / config),
        find the matching storage ID and its numeric index.
        """
        labels = STORAGE_CONFIG.get("labels", {}) or {}
        id_to_number = STORAGE_CONFIG.get("id_to_number", {}) or {}
        target = self._norm_label(substance_name)
        if not target or not isinstance(labels, dict):
            return None, None
        for sid, lab in labels.items():
            if self._norm_label(lab) == target:
                try:
                    num = int(
                        id_to_number.get(
                            sid,
                            sid[1:] if isinstance(sid, str) and sid.upper().startswith("S") else sid,
                        )
                    )
                    return str(sid), num
                except Exception:
                    pass
        return None, None
