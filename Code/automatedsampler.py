import os
import json
import time
import serial
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

class WM:
    """
    Mettler Toledo balance interface for door control, zeroing, weight, and tolerances.
    """
    def __init__(self, port='COM3', baudrate=9600, timeout=1.0):
        self.ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=timeout
        )


    def send_command(self, cmd: str) -> str:
        self.ser.write((cmd + '\r\n').encode('ascii'))
        time.sleep(0.2)
        return self.ser.readline().decode('ascii').strip()

    def wait_ready(self):
        while True:
            resp = self.send_command("I")
            if resp != "I":
                return
            print("…waiting for balance to be ready")
            time.sleep(0.5)

    def reset(self) -> str:
        resp = self.send_command("@")
        self.wait_ready()
        return resp

    def open_door(self) -> str:
        resp = self.send_command("WS 4")
        self.wait_ready()
        time.sleep(0.9)
        return resp

    def close_door(self) -> str:
        resp = self.send_command("WS 0")
        self.wait_ready()
        time.sleep(0.9)
        return resp

    def tare(self) -> str:
        resp = self.send_command("T")
        self.wait_ready()
        return resp

    def zero(self) -> str:
        resp = self.send_command("ZI")
        self.wait_ready()
        return resp

    def get_weight(self) -> float:
        while True:
            resp = self.send_command("S")
            try:
                return float(resp)
            except ValueError:
                if resp == "I":
                    time.sleep(0.5)
                    continue
                raise RuntimeError(f"Unexpected weight response: {resp}")

    def _a10_set(self, no: int, value: float, unit: str) -> str:
        """Internal: send A10_<no>_<value>_<unit> and expect 'A10_A' ack."""
        val = f"{float(value):g}"            # proper dot decimal, no trailing zeros
        cmd = f"A10 {no} {val} {unit}"
        resp = self.send_command(cmd)
        # Many models ack with exactly 'A10_A'
        if not resp.startswith("A10 A"):
            raise RuntimeError(f"A10 set failed ({cmd!r}), got: {resp!r}")
        return resp

    def set_target_weight(self, value: float, unit: str = "mg") -> str:
        """Set target weight (A10_0_<value>_<unit>), e.g., 5 mg -> A10_0_5_mg"""
        return self._a10_set(0, value, unit)

    def set_tolerance_upper(self, value: float, unit: str = "%") -> str:
        """Set +tolerance (A10_1_<value>_<unit>); use unit='%' for percentage."""
        return self._a10_set(1, value, unit)

    def set_tolerance_lower(self, value: float, unit: str = "%") -> str:
        """Set −tolerance (A10_2_<value>_<unit>); use unit='%' for percentage."""
        return self._a10_set(2, value, unit)

    def close(self):
        self.ser.close()

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


if __name__ == "__main__":
    #only use this if using json
    """system = AutomatedSampler(ur, wm)
    system.load_recipe(payload_raw)  # raw JSON text
    system.execute()"""

    #DEMO CODE
    ROBOT_IP = "192.168.0.2"
    ur = UR(ROBOT_IP)
    wm = WM(port="COM3")

    print("Connecting to robot…")
   #ur.connect()
# 0) close doors and zero
    print("Zeroing the scale...")
    wm.close_door()
    time.sleep(3)
    wm.zero()
    time.sleep(3)


# 1) Open doors and place vial on the scale
    print("Opening scale doors…")
    wm.open_door()
    print("Placing vial…")
    ur.run_program("retrievevial1.urp")


# 2) Close doors
    print("Closing scale doors…")
    wm.close_door()


# 3) Prepare target + tolerances for this powder, can be changed as necessary
    target_mg = 5.0
    tol_pct   = 2.5


    print(f"Setting target {target_mg} mg and ±{tol_pct}%…")
    wm.set_target_weight(target_mg, unit="mg")
    wm.set_tolerance_upper(tol_pct, unit="%")
    wm.set_tolerance_lower(tol_pct, unit="%")


# 4) Retrieve powder, tare, and PAUSE for manual dispensing
    print("Retrieving PowderA…")
    wait_for_continue(f"run retrieve powder program,"
   "Type 'continue' when done: ")
   #ur.run_program("retrievePowderA.urp")


    print("Taring scale…")
    time.sleep(3)
    wm.tare()


    wait_for_continue(
           f"Dispense {target_mg} mg of PowderA (±{tol_pct}%). "
           "CLICK RETURN HOME, then type 'continue' when done: "
       )


# 5) Return powder to storage
    print("Returning PowderA…")
    wait_for_continue(f"run return powder program,"
   "Type 'continue' when done: ")
   #ur.run_program("returnPowderA.urp")


# 6) Open doors and return vial
    print("Opening scale doors…")
    wm.open_door()
    print("Returning vial…")
    wait_for_continue(f"run return vial program,"
    "Type 'continue' when done: ")
    #ur.run_program("returnvial1.urp")


    print("✅ Step complete.")
   
   





