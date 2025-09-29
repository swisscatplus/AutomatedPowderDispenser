import os
import json
import time
import serial
from typing import Optional, Dict, Any, List
import sys
from dashboard_client import DashboardClient


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