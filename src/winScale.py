#!/usr/bin/env python3

# BEC - November 2025
# Automated Powder Dispenser (APD) – Mettler balance UI (WebService only).
#   - Connects to the XPR/XSR/Q3 balance via SOAP WebService
#   - Controls doors, zero/tare, reading, and DosingAutomation jobs
#-------------------------------------------------------------------------------
"""Tkinter panel used to drive the Mettler balance via WebService."""

import tkinter as tk
import tkinter.ttk as ttk
import threading

from config import SCALE_CONFIG
from guiUtils import GUIFactory, ToolTip
from deviceScale import WM

# Periodic heartbeat for connection check (in ms)
WATCH_PERIOD_MS = SCALE_CONFIG.get("watch_period_ms", 5000)  # check connection every 5 s


class WinBalance(tk.LabelFrame):
    """
    UI frame to control the Mettler balance via WebService:
    doors, zero/tare, weight, and dosing automation.
    """
    def __init__(self, parent, info_win, devices):
        super().__init__(parent, text="Scale Mettler")
        self.info = info_win
        self.devices = devices
        self.factory = GUIFactory(self)

        # Weight display
        self.var_weight = tk.StringVar(value="— mg")

        # Active method (as in the balance "Methods" menu)
        self.var_method = tk.StringVar(value="DOSING")

        # Parameters for a dosing job
        self.var_d_vial      = tk.StringVar(value="Vessel1")
        self.var_d_substance = tk.StringVar(value="")   # substance used for the job
        self.var_d_target    = tk.DoubleVar(value=5.0)
        self.var_d_tu        = tk.StringVar(value="mg")
        self.var_d_tol_lo    = tk.DoubleVar(value=0.0)
        self.var_d_tol_up    = tk.DoubleVar(value=0.0)
        self.var_d_tol_u     = tk.StringVar(value="mg")

        # Dosing head (dispenser name currently mounted)
        self.var_dosing_head = tk.StringVar(value="")   # substance read from the head

        self.btn_connect = None
        self.btn_dosing_start = None

        # Thread used to poll dosing notifications
        self._dosing_thread: threading.Thread | None = None
        self._dosing_stop: threading.Event | None = None  # used to stop polling

        self._build()

        # Auto-connect if requested by config
        if SCALE_CONFIG.get('autoconnect', True):
            self.after(200, self._auto_connect)

        # Heartbeat: re-enable connect button if connection is lost
        self.after(WATCH_PERIOD_MS, self._watch_period)

    # ---------------------------------------------------------
    def _build(self):
        """Build all widgets for the balance UI."""
        # --- Row 0 ---
        self.btn_connect = self.factory.create_btn("Connect", self.on_connect, 0, 0)
        ToolTip(self.btn_connect, "Se connecter au WebService de la balance")

        b_open = self.factory.create_btn("Open door", self.on_open_door, 0, 2)
        ToolTip(b_open, "Ouvrir porte via DraftShieldsService.SetPosition")

        b_close = self.factory.create_btn("Close door", self.on_close_door, 0, 3)
        ToolTip(b_close, "Fermer porte via DraftShieldsService.SetPosition")

        b_check = self.factory.create_btn("Check door", self.on_check_door, 0, 4)
        ToolTip(b_check, "Lire la position des portes via DraftShieldsService.GetPosition")

        b_zero = self.factory.create_btn("Zero", self.on_zero, 0, 5)
        b_tare = self.factory.create_btn("Tare", self.on_tare, 0, 6)

        b_empty = self.factory.create_btn("Is empty ?", self.on_is_empty, 0, 7)
        ToolTip(b_empty, "Détecte si le plateau est vide via GrossWeight")

        # --- Row 1 ---
        b_read = self.factory.create_btn("Get weight", self.on_read, 1, 2)

        self.factory.create_label("Weight:", 1, 3)
        lbl_w = self.factory.create_label("", 1, 4, sticky=tk.W)
        lbl_w.configure(textvariable=self.var_weight)

        # --- Row 2 ---
        self.factory.create_label("Method", 2, 0)
        cb_method = ttk.Combobox(
            self,
            textvariable=self.var_method,
            width=18,
            values=("DOSING", "General Weighing"),
            state="readonly",
        )
        cb_method.grid(row=2, column=1, padx=5, pady=5, columnspan=2, sticky=tk.W)

        b_set_method = self.factory.create_btn("Start method", self.on_start_method, 2, 3)
        ToolTip(b_set_method, "Sélectionner la méthode de pesée (menu 'Methods' de la balance)")

        # --- Row 3 ---
        self.factory.create_label("Dosing vial", 3, 0)
        self.factory.create_entry(self.var_d_vial, 3, 1, width=12)

        self.factory.create_label("Substance", 3, 2)
        self.factory.create_entry(self.var_d_substance, 3, 3, width=12)

        # --- Row 4 ---
        self.factory.create_label("Target", 4, 0)
        self.factory.create_entry(self.var_d_target, 4, 1, width=8)
        cb_dt = ttk.Combobox(
            self,
            textvariable=self.var_d_tu,
            width=6,
            values=("mg", "g"),
            state="readonly",
        )
        cb_dt.grid(row=4, column=2, padx=5, pady=5)

        self.factory.create_label("−Tol", 4, 3)
        self.factory.create_entry(self.var_d_tol_lo, 4, 4, width=8)
        self.factory.create_label("+Tol", 4, 5)
        self.factory.create_entry(self.var_d_tol_up, 4, 6, width=8)
        cb_dtu = ttk.Combobox(
            self,
            textvariable=self.var_d_tol_u,
            width=6,
            values=("mg", "g"),
            state="readonly",
        )
        cb_dtu.grid(row=4, column=7, padx=5, pady=5)

        self.btn_dosing_start = self.factory.create_btn(
            "Start dosing job", self.on_start_dosing_job, 4, 8
        )
        ToolTip(self.btn_dosing_start, "Lancer un job de dosage (DosingAutomation) avec 1 job")

        self.btn_dosing_cancel = self.factory.create_btn(
            "Cancel job", self.on_cancel_dosing_job, 4, 9
        )
        self.btn_dosing_cancel.configure(state="disabled")
        ToolTip(self.btn_dosing_cancel, "Arrêter le polling des notifications et annuler côté UI")

        # --- Row 5 ---
        self.factory.create_label("Dosing head", 5, 0)
        self.factory.create_entry(self.var_dosing_head, 5, 1, width=16)

        btn_read_head = self.factory.create_btn("Read", self.on_read_dosing_head, 5, 2)
        ToolTip(btn_read_head, "Lire le dosing head en place (ReadDosingHead)")

        btn_write_head = self.factory.create_btn("Write", self.on_write_dosing_head, 5, 3)
        ToolTip(btn_write_head, "Écrire le nom sur le dosing head en place (WriteDosingHead)")

        # Layout: mostly fixed-width columns, with a "buffer" column to the right
        for c in range(0, 11):
            self.grid_columnconfigure(c, weight=0)
        self.grid_columnconfigure(10, weight=1)  # buffer/stretch column on the right

    # ---------------------------------------------------------
    # Helpers
    def _get_wm(self) -> WM:
        """Return the connected WM instance or raise if not connected."""
        sc = self.devices.get('scale')
        if sc is None:
            raise RuntimeError("Balance non connectée")
        return sc

    def _make_wm(self) -> WM:
        """
        Create a new WM instance using endpoints directly from SCALE_CONFIG
        (no more UI editing of endpoints).
        """
        return WM(
            scheme=SCALE_CONFIG.get("scheme", "http"),
            ip=SCALE_CONFIG.get("ip", "192.168.0.50"),
            port=int(SCALE_CONFIG.get("port", 81)),
            wsdl_path=SCALE_CONFIG.get("wsdl_path"),
            password=SCALE_CONFIG.get("password"),
            verify=SCALE_CONFIG.get("verify", False),
            timeout_s=SCALE_CONFIG.get("timeout_s", 8),
            door_ids=SCALE_CONFIG.get("door_ids", ["LeftOuter", "RightOuter"]),
            open_width=SCALE_CONFIG.get("open_width", 100),
            close_width=SCALE_CONFIG.get("close_width", 0),
        )

    # ---------------------------------------------------------
    # Connection / Heartbeat
    def on_connect(self):
        """
        Connect to the WebService of the balance, wake it up if needed,
        auto-select the configured method (e.g. DOSING), and update UI state.
        """
        # Disable the button during connection attempt
        if self.btn_connect:
            self.btn_connect.configure(state="disabled", text="Connecting…")
        try:
            wm = self._make_wm()
            wm.connect()  # OpenSession + internal SessionId
            self.devices['scale'] = wm
            self.info.add("Balance connectée (WebService).")
            
            # Try to wake the balance immediately on connect
            try:
                if wm.wakeup_from_standby():
                    self.info.add("Balance réveillée (WakeupFromStandby).")
                else:
                    self.info.add("WakeupFromStandby → déjà réveillée ou état inchangé.")
            except Exception as e:
                # Small harmless 'nudge' that often wakes the SOAP UI
                try:
                    _ = wm.get_door_positions()
                    self.info.add("WakeupFromStandby a échoué → nudge GetPosition effectué.")
                except Exception:
                    self.info.add(f"WakeupFromStandby a échoué: {e}", level="warning")
                    
            # Auto-start the selected method (default: DOSING)
            method_ui = (self.var_method.get() or "").strip()
            if method_ui:
                try:
                    wm.set_method(method_ui)
                    self.info.add(f"Auto-start method '{method_ui}' → OK")
                except Exception as e1:
                    if method_ui.upper() == "DOSING":
                        try:
                            wm.set_method("Dosing")
                            self.info.add("Auto-start method fallback 'Dosing' → OK")
                            self.var_method.set("DOSING")
                        except Exception as e2:
                            self.info.add(f"Auto-start method '{method_ui}' échouée: {e2}", level="warning")
                    else:
                        self.info.add(f"Auto-start method '{method_ui}' échouée: {e1}", level="warning")

            if self.btn_connect:
                self.btn_connect.configure(state="disabled", text="Connected")
            # Reset dosing buttons to a consistent state
            self._reset_dosing_buttons()
        except Exception as e:
            if self.btn_connect:
                self.btn_connect.configure(state="normal", text="Connect")
            self.info.add(f"Connexion WS échouée — {e}", level="error")

    def on_is_empty(self):
        """Check if the pan is empty using GrossWeight and log a detailed summary."""
        try:
            ok, stats = self._get_wm().is_pan_empty(
                threshold_mg=SCALE_CONFIG.get("empty_threshold_mg", 9.0),
                samples=SCALE_CONFIG.get("empty_samples", 10),
                sleep_s=SCALE_CONFIG.get("empty_sleep_s", 0.05),
            )            
            if ok:
                self.info.add(
                    f"Plateau VIDE (Gross mean={stats['mean_gross_g']*1000:.1f} mg, "
                    f"σ={stats['std_gross_g']*1000:.1f} mg, seuil={stats['threshold_g']*1000:.1f} mg, n={stats['n']})"
                )
            else:
                self.info.add(
                    f"Plateau OCCUPÉ (Gross mean={stats['mean_gross_g']*1000:.1f} mg, "
                    f"σ={stats['std_gross_g']*1000:.1f} mg, seuil={stats['threshold_g']*1000:.1f} mg, n={stats['n']})",
                    level="warning"
                )
        except Exception as e:
            self.info.add(f"Is empty ?: {e}", level="error")

    def _auto_connect(self):
        """Try to auto-connect at startup if enabled in SCALE_CONFIG."""
        try:
            self.on_connect()
        except Exception as e:
            self.info.add(f"Auto-connect échoué: {e}", level="warning")

    def _watch_period(self):
        """
        Periodically check the WebService/connection state.
        If the connection is lost, re-enable the 'Connect' button.
        """
        wm = self.devices.get('scale')
        ok = False
        if wm and wm.is_connected():
            try:
                _ = wm.get_door_positions()
                ok = True
            except Exception:
                ok = False

        if ok:
            if self.btn_connect:
                self.btn_connect.configure(state="disabled", text="Connected")
        else:
            if self.btn_connect:
                self.btn_connect.configure(state="normal", text="Connect")

        self.after(WATCH_PERIOD_MS, self._watch_period)

    # ---------------------------------------------------------
    # Basic UI actions
    def on_open_door(self):
        """Open the draft shield door(s)."""
        try:
            resp = self._get_wm().open_door()
            self.info.add(f"Open door → {resp}")
        except Exception as e:
            self.info.add(f"Open door: {e}", level="error")

    def on_close_door(self):
        """Close the draft shield door(s)."""
        try:
            resp = self._get_wm().close_door()
            self.info.add(f"Close door → {resp}")
        except Exception as e:
            self.info.add(f"Close door: {e}", level="error")

    def on_check_door(self):
        """Read and log the current door positions."""
        try:
            pos = self._get_wm().get_door_positions()
            self.info.add(f"Door positions: {pos}")
        except Exception as e:
            self.info.add(f"Check door: {e}", level="error")

    def on_zero(self):
        """Send a Zero command to the balance."""
        try:
            resp = self._get_wm().zero()
            self.info.add(f"Zero → {resp}")
        except Exception as e:
            self.info.add(f"Zero: {e}", level="error")

    def on_tare(self):
        """Send a Tare command to the balance."""
        try:
            resp = self._get_wm().tare()
            self.info.add(f"Tare → {resp}")
        except Exception as e:
            self.info.add(f"Tare: {e}", level="error")

    def on_read(self):
        """Read the current weight from the balance and display it in mg."""
        try:
            w_g = self._get_wm().get_weight()   # always returns grams in deviceScale
            w_mg = w_g * 1000.0
            self.var_weight.set(f"{w_mg:.3f} mg")
            self.info.add(f"Poids: {w_mg:.3f} mg")
        except Exception as e:
            self.info.add(f"Lecture: {e}", level="error")

    def on_start_method(self):
        """Start the selected weighing method on the balance."""
        try:
            method = self.var_method.get().strip()
            resp = self._get_wm().set_method(method)
            self.info.add(f"Start method '{method}' → {resp}")
        except Exception as e:
            self.info.add(f"Start method: {e}", level="error")

    # ---------------------------------------------------------
    # Dosing Automation: start job + notification thread
    def _start_dosing_notifications_thread(self):
        """
        Start the background thread that automatically confirms
        dosing notifications and logs them.
        """
        if self._dosing_thread and self._dosing_thread.is_alive():
            return

        # (Re)initialise the stop event
        self._dosing_stop = threading.Event()

        # UI: disable Start, enable Cancel
        if self.btn_dosing_start:
            self.btn_dosing_start.configure(state="disabled")
        if hasattr(self, "btn_dosing_cancel") and self.btn_dosing_cancel:
            self.btn_dosing_cancel.configure(state="normal")

        def _worker():
            def log_cb(msg: str):
                self.after(0, lambda m=msg: self.info.add(m))
            try:
                self._get_wm().auto_confirm_dosing_notifications(
                    log_cb=log_cb,
                    verbose=True,
                    long_poll_s=10,
                    stop_event=self._dosing_stop,  # pass the stop event
                )
                self.after(0, lambda: self.info.add("DosingAutomation terminé (auto-confirm)."))
            except Exception as e:
                self.after(0, lambda: self.info.add(f"Erreur auto-confirm dosing: {e}", level="error"))
            finally:
                # UI: re-enable Start, disable Cancel
                self.after(0, self._reset_dosing_buttons)

        self._dosing_thread = threading.Thread(target=_worker, daemon=True)
        self._dosing_thread.start()

    def _reset_dosing_buttons(self):
        """Reset dosing Start/Cancel buttons to a safe default state."""
        if self.btn_dosing_start:
            self.btn_dosing_start.configure(state="normal")
        if hasattr(self, "btn_dosing_cancel") and self.btn_dosing_cancel:
            self.btn_dosing_cancel.configure(state="disabled")

    def on_start_dosing_job(self):
        """
        Start a dosing job on the balance:
        - ensure doors are closed
        - ensure a dosing head is present
        - ensure a vial is present on the pan
        - ensure the 'Dosing' method is active
        - send a single dosing job and, on success, start the notification thread.
        """
        try:
            # --- A) Close the door(s) BEFORE anything else ---
            try:
                resp = self._get_wm().close_door()  # robust door-driving policy
                self.info.add(f"Close door → {resp}")
            except Exception as e_close:
                self.info.add(f"Impossible de fermer la porte: {e_close}", level="error")
                return  # do not start job if we cannot close the door

            # --- 0) Is a dispenser present? ---
            head_name = (self._get_wm().get_dosing_head_name() or "").strip()
            if not head_name:
                self.info.add(
                    "Aucun dispenser détecté (ReadDosingHead vide). "
                    "Place un dosing head puis relance.",
                    level="warning"
                )
                return

            # --- 1) Is a vial present? ---
            min_present_mg = float(SCALE_CONFIG.get("vial_presence_min_mg", 1000.0))
            has_vial, stats = self._get_wm().is_pan_present(
                min_present_mg=min_present_mg, samples=8, sleep_s=0.04
            )
            if not has_vial:
                self.info.add(
                    "Aucune vial détectée sur le plateau — je ne lance pas le job. "
                    f"(Gross≈{(stats['mean_gross_g'] or 0)*1000:.1f} mg, "
                    f"seuil≈{stats['threshold_g']*1000:.1f} mg)",
                    level="warning"
                )
                return

            # Pre-checks OK: update UI state
            if self.btn_dosing_start:
                self.btn_dosing_start.configure(state="disabled")
            if hasattr(self, "btn_dosing_cancel") and self.btn_dosing_cancel:
                self.btn_dosing_cancel.configure(state="normal")

            # (Optional) sync substance field if empty
            if not (self.var_d_substance.get() or "").strip():
                self.var_d_substance.set(head_name)

            # --- 2) Ensure 'Dosing' method is active ---
            method = self.var_method.get().strip().lower()
            if method != "dosing":
                self.info.add("La méthode active n'est pas 'Dosing' → je la démarre avant le job.")
                self._get_wm().set_method("Dosing")
                self.var_method.set("DOSING")

            # --- 3) Collect parameters and send job ---
            vial   = self.var_d_vial.get().strip()
            sub    = self.var_d_substance.get().strip()
            tgt    = float(self.var_d_target.get())
            t_unit = self.var_d_tu.get()
            tol_lo = float(self.var_d_tol_lo.get())
            tol_up = float(self.var_d_tol_up.get())
            tol_u  = self.var_d_tol_u.get()

            resp = self._get_wm().start_dosing_job(
                vial_name=vial,
                substance_name=sub,
                target_value=tgt,
                target_unit=t_unit,
                lower_tol_value=tol_lo,
                upper_tol_value=tol_up,
                tol_unit=tol_u,
            )

            out   = resp.get("Outcome")
            cmd   = resp.get("CommandId")
            err   = resp.get("ErrorMessage")
            s_err = resp.get("StartDosingJobListError")
            jerr  = resp.get("JobErrors")

            msg = f"Dosing job '{vial}' / '{sub}' {tgt:g}{t_unit} (−{tol_lo:g}{tol_u}/+{tol_up:g}{tol_u})"
            if out:  msg += f" → Outcome={out}"
            if cmd:  msg += f", CommandId={cmd}"
            if s_err: msg += f", StartError={s_err}"
            if err:   msg += f", Error={err}"
            if jerr:  msg += f", JobErrors={jerr}"
            self.info.add(msg)

            if out == "Success" and not s_err:
                self._start_dosing_notifications_thread()

        except Exception as e:
            self.info.add(f"Start dosing job: {e}", level="error")
            self._reset_dosing_buttons()
    
    def on_cancel_dosing_job(self):
        """
        Cancel the current dosing job:
        - request cancellation via WebService (several fallbacks)
        - signal the local worker thread to stop
        - join the thread briefly and reset the UI.
        """
        # 1) Request cancellation on WS side (priority: Dosing → Task → CommandId)
        try:
            r = self._get_wm().cancel_dosing_job_list()
            self.info.add(f"CancelCurrentDosingJobListAsync → Outcome={r.get('Outcome')} CmdId={r.get('CommandId')}")
            if r.get("Outcome") not in (None, "Success"):
                # fallback #1: cancel current task
                r2 = self._get_wm().cancel_current_task()
                self.info.add(f"CancelCurrentTask → Outcome={r2.get('Outcome')}")
                if r2.get("Outcome") not in (None, "Success"):
                    # fallback #2: cancel by CommandId if available
                    r3 = self._get_wm().cancel_command()
                    self.info.add(f"Session.Cancel(CommandId) → Outcome={r3.get('Outcome')}")
        except Exception as e:
            self.info.add(f"Annulation WS a échoué: {e}", level="warning")

        # 2) Signal the local worker (notification polling) to stop
        if self._dosing_stop:
            self._dosing_stop.set()

        # 3) Join the thread briefly to reduce log noise
        if self._dosing_thread and self._dosing_thread.is_alive():
            try:
                self._dosing_thread.join(timeout=0.5)
            except Exception:
                pass

        self.info.add("Cancel demandé → envoi de l'annulation et arrêt du polling en cours.")
        self._reset_dosing_buttons()

    # ---------------------------------------------------------
    # Dosing Head: read / write
    def on_read_dosing_head(self):
        """
        Read the name of the dosing head currently mounted via ReadDosingHead,
        update the dedicated field and also the substance of the dosing job.
        """
        try:
            name = self._get_wm().get_dosing_head_name().strip()
            self.var_dosing_head.set(name)
            self.var_d_substance.set(name)
            self.info.add(f"Dosing head lu: {name or '—'}")
        except Exception as e:
            self.info.add(f"Read dosing head: {e}", level="error")

    def on_write_dosing_head(self):
        """
        Write the specified name into the dosing head via WriteDosingHead,
        and keep the dosing job substance in sync with that name.
        """
        try:
            name = self.var_dosing_head.get().strip()
            if not name:
                self.info.add("Nom de dosing head vide → rien à écrire.", level="warning")
                return

            resp = self._get_wm().set_dosing_head_name(name)
            self.var_d_substance.set(name)
            self.info.add(f"Dosing head écrit: '{name}' → {resp}")
        except Exception as e:
            self.info.add(f"Write dosing head: {e}", level="error")
