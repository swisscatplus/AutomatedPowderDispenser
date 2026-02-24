#!/usr/bin/env python3

# BEC - November 2025
# Automated Powder Dispenser (APD) – JSON Auto Mode.
#   - Execute a vial/powder dispensing plan loaded from a JSON file
#   - For each vial: P1 (fetch vial) then, for each powder:
#       P2 (fetch dispenser) → dosing job → P4 (return dispenser)
#   - At the end of all powders for this vial: P3 (return vial)
#-------------------------------------------------------------------------------

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json

AUTO_POLL_MS = 800  # polling period (ms) for UR3 / dosing


class WinJsonAuto(tk.Frame):
    def __init__(
        self,
        parent,
        info_win,
        devices,
        robot_win=None,
        balance_win=None,
        on_select_vial=None,
        on_select_powder=None,
        on_prepare_dosing=None,
    ):
        super().__init__(parent)
        self.parent = parent
        self.win_info = info_win
        self.devices = devices

        # References to "manual" views
        self.robot_win = robot_win
        self.balance_win = balance_win

        # Callbacks provided by winMode (see win.py)
        self.cb_select_vial = on_select_vial
        self.cb_select_powder = on_select_powder
        self.cb_prepare_dosing = on_prepare_dosing

        # Current JSON plan
        # list of dicts: {"vial_id": str, "powders":[{"name":str,"qty_mg":float}, ...]}
        self.plan = []
        self.plan_path = None

        # Current indices in the plan
        self.cur_vial_idx = 0
        self.cur_powder_idx = 0

        # Sequence state
        self._running = False
        self._waiting_for = None      # None / "program" / "dosing"
        self._current_phase = None    # for logs: "P1" / "P2" / "DOSING" / "P3" / "P4"
        self._after_id = None

        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)

        title = tk.Label(
            self,
            text="JSON Auto Mode: execute vial/powder plans from a .json file",
            font=("TkDefaultFont", 10, "bold"),
            anchor="w",
        )
        title.grid(row=0, column=0, columnspan=2, sticky="ew", padx=5, pady=(5, 2))

        # Row 1: load button + plan summary
        btn_load = tk.Button(
            self,
            text="Load JSON…",
            width=18,
            command=self.on_load_json,
        )
        btn_load.grid(row=1, column=0, sticky="w", padx=5, pady=5)

        self.lbl_plan = tk.Label(self, text="No plan loaded.", anchor="w", justify="left")
        self.lbl_plan.grid(row=1, column=1, sticky="ew", padx=5, pady=5)

        # Row 2: run button
        self.btn_run = tk.Button(
            self,
            text="Run JSON plan",
            width=18,
            command=self.on_start_plan,
            state="disabled",
        )
        self.btn_run.grid(row=2, column=0, sticky="w", padx=5, pady=(0, 5))

        self.lbl_status = tk.Label(self, text="", anchor="w", justify="left")
        self.lbl_status.grid(row=2, column=1, sticky="ew", padx=5, pady=(0, 5))

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

    # ------------------------------------------------------------------
    # JSON loading
    # ------------------------------------------------------------------
    def on_load_json(self):
        path = filedialog.askopenfilename(
            parent=self,
            title="Choose a JSON plan",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            messagebox.showerror("JSON error", f"Unable to read file:\n{e}")
            return

        plan = self._parse_plan(data)
        if not plan:
            messagebox.showerror("Empty plan", "The JSON file does not contain any valid vial/powder entry.")
            return

        self.plan = plan
        self.plan_path = path
        self.cur_vial_idx = 0
        self.cur_powder_idx = 0

        # Text summary
        lines = [f"Plan: {len(plan)} vial(s)"]
        for v in plan:
            powders_desc = ", ".join(f"{p['name']} {p['qty_mg']} mg" for p in v["powders"])
            lines.append(f"  - {v['vial_id']}: {powders_desc}")
        self.lbl_plan.configure(text="\n".join(lines))

        self._log(f"JSON mode: plan loaded from {path}.")
        self.btn_run.configure(state="normal")

    def _parse_plan(self, data):
        """Convert raw JSON dict into a normalized list usable by the state machine."""
        vials_src = data.get("vials") if isinstance(data, dict) else None
        if not isinstance(vials_src, list):
            return []

        plan = []
        for v in vials_src:
            if not isinstance(v, dict):
                continue
            vial_id = (v.get("vial_id") or v.get("name") or v.get("vial") or "").strip()
            if not vial_id:
                continue
            powders_src = v.get("powders") or []
            powders = []
            for p in powders_src:
                if not isinstance(p, dict):
                    continue
                name = (p.get("name") or "").strip()
                try:
                    qty = float(p.get("qty_mg", 0.0))
                except Exception:
                    continue
                if not name or qty <= 0:
                    continue
                powders.append({"name": name, "qty_mg": qty})
            if not powders:
                continue
            plan.append({"vial_id": vial_id, "powders": powders})
        return plan

    # ------------------------------------------------------------------
    # Auto-connect helpers for UR3 / balance
    # ------------------------------------------------------------------
    def _ensure_ur3_connected(self):
        arm = self.devices.get("ur3")
        if arm and getattr(arm, "is_connected", lambda: False)():
            return True

        if not self.robot_win:
            self._log("JSON mode: WinRobotArm not available (robot_win=None).", level="error")
            return False

        self._log("JSON mode: trying to auto-connect UR3…", level="info")
        try:
            self.robot_win.on_connect()
        except Exception as e:
            self._log(f"JSON mode: on_connect() UR3 failed: {e}", level="error")
            return False

        arm = self.devices.get("ur3")
        if not (arm and getattr(arm, "is_connected", lambda: False)()):
            self._log("JSON mode: UR3 still not connected after on_connect().", level="error")
            return False

        self._log("JSON mode: UR3 auto-connected.", level="info")
        return True

    def _ensure_scale_connected(self):
        wm = self.devices.get("scale")
        if wm and getattr(wm, "is_connected", lambda: False)():
            return True

        if not self.balance_win:
            self._log("JSON mode: WinBalance not available (balance_win=None).", level="error")
            return False

        self._log("JSON mode: trying to auto-connect balance…", level="info")
        try:
            self.balance_win.on_connect()
        except Exception as e:
            self._log(f"JSON mode: on_connect() balance failed: {e}", level="error")
            return False

        wm = self.devices.get("scale")
        if not (wm and getattr(wm, "is_connected", lambda: False)()):
            self._log("JSON mode: balance still not connected after on_connect().", level="error")
            return False

        self._log("JSON mode: balance auto-connected.", level="info")
        return True

    # ------------------------------------------------------------------
    # Entry point for JSON sequence
    # ------------------------------------------------------------------
    def on_start_plan(self):
        if self._running:
            self._log("JSON mode: a plan is already running.", level="warning")
            return
        if not self.plan:
            self._log("JSON mode: no plan loaded.", level="warning")
            return

        if not self._ensure_ur3_connected():
            return
        if not self._ensure_scale_connected():
            return
        if not self.robot_win or not self.balance_win:
            self._log("JSON mode: manual robot/balance views are missing.", level="error")
            return

        self._running = True
        self._waiting_for = None
        self._current_phase = None
        self.cur_vial_idx = 0
        self.cur_powder_idx = 0

        self.btn_run.configure(state="disabled")
        self._log("JSON mode: starting JSON plan.")
        self._start_vial_p1()

    # ------------------------------------------------------------------
    # Stop / finish management
    # ------------------------------------------------------------------
    def _abort(self, reason):
        if not self._running:
            return
        self._running = False
        self._waiting_for = None
        self._current_phase = None
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        self.btn_run.configure(state="normal")
        self._log(f"JSON mode: sequence aborted. {reason}", level="error")

    def _finish(self):
        if not self._running:
            return
        self._running = False
        self._waiting_for = None
        self._current_phase = None
        self._after_id = None
        self.btn_run.configure(state="normal")
        self._log("JSON mode: plan completed for all vials.", level="info")

    # ------------------------------------------------------------------
    # Plan steps: P1 (vial) / P2+dosing+P4 (dispenser) / P3 (end of vial)
    # ------------------------------------------------------------------
    def _get_current_vial(self):
        if 0 <= self.cur_vial_idx < len(self.plan):
            return self.plan[self.cur_vial_idx]
        return None

    def _get_current_powder(self):
        vial = self._get_current_vial()
        if not vial:
            return None
        powders = vial.get("powders") or []
        if 0 <= self.cur_powder_idx < len(powders):
            return powders[self.cur_powder_idx]
        return None

    # --- P1: bring vial to the balance (once per vial) ---
    def _start_vial_p1(self):
        if not self._running:
            return
        vial = self._get_current_vial()
        if not vial:
            self._finish()
            return

        vial_id = vial["vial_id"]
        # 1) select the vial in the manual UI
        if self.cb_select_vial:
            try:
                self.cb_select_vial(vial_id)
            except Exception as e:
                self._abort(f"Unable to select vial {vial_id}: {e}")
                return

        self._log(f"JSON mode: P1 for vial {vial_id}.", level="info")
        self._start_program_with_helper(
            "P1Bastien.urp",
            "P1",
            getattr(self.robot_win, "_play_p1", None),
            on_done=self._after_p1,
        )

    def _after_p1(self):
        """Called when P1 has finished for the current vial."""
        if not self._running:
            return
        self.cur_powder_idx = 0
        self._start_powder_cycle()

    # --- For each powder: P2 → dosing → P4 (dispenser) ---
    def _start_powder_cycle(self):
        if not self._running:
            return
        vial = self._get_current_vial()
        powder = self._get_current_powder()
        if not vial or not powder:
            # no more powders for this vial → final step for this vial (P3)
            self._start_vial_p4()
            return

        vial_id = vial["vial_id"]
        powder_name = powder["name"]
        qty_mg = powder["qty_mg"]

        # 1) select the dispenser (storage) for this powder
        if self.cb_select_powder:
            try:
                self.cb_select_powder(vial_id, powder_name)
            except Exception as e:
                self._abort(f"Unable to select dispenser for {powder_name}: {e}")
                return

        self._log(f"JSON mode: P2 for vial {vial_id}, powder {powder_name}.", level="info")
        self._start_program_with_helper(
            "P2Bastien.urp",
            "P2",
            getattr(self.robot_win, "_play_p2", None),
            on_done=self._after_p2_for_powder,
        )

    def _after_p2_for_powder(self):
        if not self._running:
            return
        vial = self._get_current_vial()
        powder = self._get_current_powder()
        if not vial or not powder:
            self._start_vial_p4()
            return

        vial_id = vial["vial_id"]
        powder_name = powder["name"]
        qty_mg = powder["qty_mg"]

        # Prepare dosing job (target, substance, etc.)
        if self.cb_prepare_dosing:
            try:
                self.cb_prepare_dosing(vial_id, powder_name, qty_mg)
            except Exception as e:
                self._abort(f"Dosing preparation failed ({powder_name} {qty_mg} mg): {e}")
                return

        # Start dosing
        self._log(f"JSON mode: dosing {powder_name} ({qty_mg} mg) into {vial_id}.", level="info")
        self._start_dosing(on_done=self._after_dosing_for_powder)

    def _after_dosing_for_powder(self):
        if not self._running:
            return
        vial = self._get_current_vial()
        powder = self._get_current_powder()
        if not vial or not powder:
            # no more powder / inconsistent state → continue to vial finalization
            self._start_vial_p4()
            return

        vial_id = vial["vial_id"]
        powder_name = powder["name"]

        # After dosing, return the DISPENSER → P4
        self._log(f"JSON mode: P4 for vial {vial_id}, powder {powder_name}.", level="info")
        self._start_program_with_helper(
            "P4Bastien.urp",
            "P4",
            getattr(self.robot_win, "_play_p4", None),
            on_done=self._after_p4_for_powder,  # callback after dispenser return
        )

    def _after_p4_for_powder(self):
        """Called after P4 (dispenser return) for the current powder."""
        if not self._running:
            return
        vial = self._get_current_vial()
        if not vial:
            self._finish()
            return

        # Next powder for this vial?
        self.cur_powder_idx += 1
        if self._get_current_powder() is not None:
            self._start_powder_cycle()
        else:
            # no more powders for this vial → final step on vial (P3)
            self._start_vial_p4()

    # --- Final step per vial: P3 (return vial to storage) ---
    def _start_vial_p4(self):
        """
        Final step for a vial:
        use P3 to return the VIAL to its storage position.
        (Function name kept as _start_vial_p4 to avoid breaking existing calls.)
        """
        if not self._running:
            return
        vial = self._get_current_vial()
        if not vial:
            self._finish()
            return

        vial_id = vial["vial_id"]
        self._log(f"JSON mode: P3 for vial {vial_id}.", level="info")
        self._start_program_with_helper(
            "P3Bastien.urp",
            "P3",
            getattr(self.robot_win, "_play_p3", None),
            on_done=self._after_p4,  # callback "after end of vial"
        )

    def _after_p4(self):
        if not self._running:
            return

        # Next vial?
        self.cur_vial_idx += 1
        self.cur_powder_idx = 0
        if self._get_current_vial() is not None:
            self._start_vial_p1()
        else:
            self._finish()

    # ------------------------------------------------------------------
    # Generic helpers: program loading + STOPPED polling
    # ------------------------------------------------------------------
    def _start_program_with_helper(self, short_name, phase_label, helper, on_done):
        """Factorize common logic for P1..P4."""
        if not self._running:
            return

        if not self._ensure_ur3_connected():
            self._abort("UR3 not connected.")
            return

        arm = self.devices.get("ur3")
        if not arm or not getattr(arm, "is_connected", lambda: False)():
            self._abort("UR3 not connected.")
            return

        try:
            # 1) refresh UR programs and select short_name in the combo, like in manual mode
            self.robot_win.on_refresh_programs()
            values = list(self.robot_win.cmb_programs["values"] or [])
            if not values:
                raise RuntimeError("no .urp program available on the robot.")

            short_low = short_name.lower()
            target = None
            for p in values:
                p_str = str(p)
                p_low = p_str.lower()
                if (
                    p_low.endswith("/" + short_low)
                    or p_low.endswith("\\" + short_low)
                    or p_low == short_low
                ):
                    target = p_str
                    break

            if not target:
                raise RuntimeError(f"program {short_name!r} not found on the robot.")

            self.robot_win.var_selected_program.set(target)
            self.robot_win.on_load_selected_program()
            self._log(f"JSON mode: loading program {short_name} ({phase_label}).")
        except Exception as e:
            self._abort(f"Unable to load program {short_name}: {e}")
            return

        # 2) Call WinRobotArm helper (pre-checks)
        if not callable(helper):
            self._abort(f"No helper _play_{phase_label.lower()} available in WinRobotArm.")
            return

        try:
            helper(arm)
        except Exception as e:
            self._abort(f"Error in _play_{phase_label.lower()}(): {e}")
            return

        # 3) Start UR program
        try:
            before = arm.get_program_state()
            play_resp = arm.play()
            self._log(
                f"JSON mode: starting program {phase_label} "
                f"(state_before={before} ; play→{play_resp})",
                level="info",
            )
        except Exception as e:
            self._abort(f"Error calling play() on UR3: {e}")
            return

        # 4) Put robot UI in 'running' and let its own watcher run
        try:
            self.robot_win._set_state("running")
            self.robot_win._start_run_watch()
        except Exception:
            pass

        # 5) Wait for STOPPED
        self._current_phase = phase_label
        self._waiting_for = "program"
        self._schedule_poll(on_done)

    def _schedule_poll(self, on_done):
        if not self._running:
            return
        # remember callback to call when the phase is done
        self._on_done_program = on_done
        self._after_id = self.after(AUTO_POLL_MS, self._poll_program_state)

    def _poll_program_state(self):
        """Poll UR program state until STOPPED, then chain the next step."""
        self._after_id = None
        if not self._running:
            return

        if self._waiting_for != "program":
            # inconsistent internal state
            self._abort("Unexpected internal state (_waiting_for != 'program').")
            return

        arm = self.devices.get("ur3")
        if not arm or not getattr(arm, "is_connected", lambda: False)():
            self._abort("UR3 connection lost.")
            return

        try:
            raw = arm.get_program_state()
        except Exception as e:
            self._abort(f"Error reading programState: {e}")
            return

        # Normalization, same approach as in WinRobotArm / WinAuto
        try:
            canon = self.robot_win._canon_prog_state(raw)
        except Exception:
            up = str(raw or "").strip().upper()
            if "RUNNING" in up or "PLAYING" in up:
                canon = "RUNNING"
            elif "PAUSE" in up:
                canon = "PAUSED"
            elif "STOP" in up:
                canon = "STOPPED"
            else:
                canon = "UNKNOWN"

        if canon in ("RUNNING", "PAUSED", "UNKNOWN"):
            # still running → re-schedule polling
            self._after_id = self.after(AUTO_POLL_MS, self._poll_program_state)
            return

        if canon == "STOPPED":
            self._log(f"JSON mode: program {self._current_phase} finished (STOPPED).", level="info")
            try:
                self.robot_win._set_state("idle")
            except Exception:
                pass

            cb = getattr(self, "_on_done_program", None)
            self._on_done_program = None
            self._waiting_for = None
            if callable(cb):
                cb()
            return

        # other unexpected state → keep polling cautiously
        self._after_id = self.after(AUTO_POLL_MS, self._poll_program_state)

    # ------------------------------------------------------------------
    # Dosing: same logic as manual, but with a completion callback
    # ------------------------------------------------------------------
    def _start_dosing(self, on_done):
        if not self._running:
            return
        if not self._ensure_scale_connected():
            self._abort("Balance not connected.")
            return

        # Trigger the same logic as the manual "Start dosing job" button
        try:
            self.balance_win.on_start_dosing_job()
        except Exception as e:
            self._abort(f"Error when starting dosing job: {e}")
            return

        # Give WinBalance a short delay to spawn its dosing thread
        self._waiting_for = "dosing"
        self._on_done_dosing = on_done
        self._after_id = self.after(300, self._poll_dosing_state)

    def _poll_dosing_state(self):
        self._after_id = None
        if not self._running:
            return
        if self._waiting_for != "dosing":
            self._abort("Unexpected internal state (_waiting_for != 'dosing').")
            return

        t = getattr(self.balance_win, "_dosing_thread", None)
        if t is None:
            # no thread → job considered finished
            self._log("JSON mode: dosing job finished (thread missing).", level="info")
            cb = getattr(self, "_on_done_dosing", None)
            self._on_done_dosing = None
            self._waiting_for = None
            if callable(cb):
                cb()
            return

        if t.is_alive():
            # still running → re-schedule check
            self._after_id = self.after(1000, self._poll_dosing_state)
            return

        # thread finished
        self._log("JSON mode: dosing job finished.", level="info")
        cb = getattr(self, "_on_done_dosing", None)
        self._on_done_dosing = None
        self._waiting_for = None
        if callable(cb):
            cb()
