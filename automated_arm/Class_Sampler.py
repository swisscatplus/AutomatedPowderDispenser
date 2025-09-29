import os
import json
import time
import serial
from typing import Optional, Dict, Any, List
import sys
from dashboard_client import DashboardClient



class AutomatedSampler:
    """
    Orchestrates the UR3eController and WeighingMachine for manual powder dispensing.

    Recipe-driven workflow:
      - Zero at the start of each vial (doors closed)
      - For each powder: set target/tolerance from JSON → retrieve → tare → manual dispense → return
      - Then return the vial
    """
    def __init__(self, ur: UR, wm: WM):
        self.robot = ur
        self.scale = wm
        for method in (
            'open_door', 'close_door', 'zero', 'tare',
            'set_target_weight', 'set_tolerance_upper', 'set_tolerance_lower'
        ):
            assert hasattr(self.scale, method), f"WM must implement {method}()"
        self.vials: List[Dict[str, Any]] = []  # default; will be set by load_recipe()

    def load_recipe(self, recipe_json: str):
        data = json.loads(recipe_json)
        self.vials = data.get('vials', [])

    def execute(self) -> None:
        print("Connecting to robot…")
        self.robot.connect()
        try:
            for vidx, vial in enumerate(self.vials, start=1):
                slot = int(vial.get("slot", vidx))

                # 0) close doors and zero
                print("Zeroing the scale...")
                self.scale.close_door()
                time.sleep(3)
                self.scale.zero()
                time.sleep(3)

                # 1) open doors and place vial
                print("Opening scale doors…")
                self.scale.open_door()
                print("Placing vial…")
                self.robot.run_program(f"retrievevial{slot}.urp")

                # 2) close doors
                print("Closing scale doors…")
                self.scale.close_door()

                # 3) per powder
                for mat in vial.get("materials", []):
                    name = mat["name"]

                    # target (mg) from JSON
                    if "target_mg" not in mat:
                        raise ValueError(f"Material {name} missing 'target_mg'")
                    target_mg = float(mat["target_mg"])
                    self.scale.set_target_weight(target_mg, unit="mg")

                    # tolerance from JSON (supports tol_pct or upper/lower(/unit) or nested tolerance)
                    tol_obj = mat.get("tolerance", {})
                    pct = mat.get("tol_pct", tol_obj.get("pct", None))
                    if pct is not None:
                        pct = float(pct)
                        self.scale.set_tolerance_upper(pct, unit="%")
                        self.scale.set_tolerance_lower(pct, unit="%")
                        tol_desc = f"±{pct}%"
                    else:
                        upper = mat.get("tol_upper", tol_obj.get("upper", 0.0))
                        lower = mat.get("tol_lower", tol_obj.get("lower", 0.0))
                        unit = mat.get("tol_unit", tol_obj.get("unit", "mg"))
                        upper = float(upper)
                        lower = float(lower)
                        self.scale.set_tolerance_upper(upper, unit=unit)
                        self.scale.set_tolerance_lower(lower, unit=unit)
                        tol_desc = (f"+{upper}{unit} / -{lower}{unit}" if unit != "%"
                                    else f"+{upper}% / -{lower}%")

                    # retrieve powder
                    print(f"Retrieving {name}…")
                    self.robot.run_program(f"retrieve{name}.urp")

                    # tare AFTER retrieving powder
                    print("Taring scale…")
                    time.sleep(3)
                    self.scale.tare()

                    # manual dispense
                    wait_for_continue(
                        f"Dispense {target_mg} mg of {name} ({tol_desc}). "
                        "CLICK RETURN HOME, then type 'continue' when done: "
                    )

                    # return powder
                    print(f"Returning {name}…")
                    self.robot.run_program(f"return{name}.urp")

                # 4) open doors and return vial
                print("Opening scale doors…")
                self.scale.open_door()
                print("Returning vial…")
                self.robot.run_program(f"returnvial{slot}.urp")

                print("✅ Vial complete.")
        finally:
            self.robot.disconnect()


def wait_for_continue(msg: str = "Type 'continue' when done: ") -> None:
    """Block until user types 'continue' (case-insensitive)."""
    while True:
        ans = input(msg).strip().lower()
        if ans == "continue":
            return
        print("…please type exactly 'continue' to proceed.")
