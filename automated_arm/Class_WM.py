import os
import json
import time
import serial
from typing import Optional, Dict, Any, List
import sys


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
        while True:
            resp = self.send_command("T")

            if resp.startswith("T I"): #scale not ready
                time.sleep(0.5)
                continue

            elif resp.startswith("T L"):
                raise RuntimeError("Incorrect parameters")
            elif resp.startswith("T +"):
                raise RuntimeError("Scale overload")
            elif resp.startswith("T -"):
                raise RuntimeError("Scale overload")
            elif resp.startswith("T S"): #good response
                value_str = resp[4:].strip()
                # keep only numerical value before dimensionality
                number_str = value_str.split()[0]
                try:
                    taring = str(number_str)
                    print(f"Tare successfully: {taring}")
                    return taring
                except ValueError:
                    raise RuntimeError(f"Unexpected tare value: {value_str}")

            else:  # unexpected answer
                raise RuntimeError(f"Unexpected tare response: {resp}")


    def zero(self) -> str:
        resp = self.send_command("ZI")
        self.wait_ready()
        return resp

    def get_weight(self) -> float:
        while True:
            resp = self.send_command("S")

            if resp.startswith("S I"):  # scale not ready
                time.sleep(0.5)
                continue

            elif resp.startswith("S L"):  # incorrect parameters
                raise RuntimeError("Unexpected weight response: incorrect parameter")

            elif resp.startswith("S +"):  # overload
                raise RuntimeError("Unexpected weight response: overload range")

            elif resp.startswith("S -"):  # underload
                raise RuntimeError("Unexpected weight response: underload range")

            elif resp.startswith("S S"):  # good response
                # erase "S S"
                value_str = resp[4:].strip()
                # keep only numerical value before dimensionality
                number_str = value_str.split()[0]
                try:
                    weight = float(number_str)
                    print(f"✅ Weight measured successfully: {weight}")
                    return weight
                except ValueError:
                    raise RuntimeError(f"Unexpected weight value: {value_str}")

            else:  # unexpected answer
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