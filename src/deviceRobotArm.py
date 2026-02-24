#!/usr/bin/env python3

# BEC - November 2025
# Automated Powder Dispenser (APD) – UR3 backend client.
#   - Minimal Dashboard (29999), RTDE IO (30004) and SFTP program listing
#   - Exposes a thin UR3 façade class for the GUI layer
#-------------------------------------------------------------------------------
"""Low-level client for the UR3 robot (Dashboard, RTDE IO, SFTP)."""

from __future__ import annotations
from typing import Optional, List
import socket
import threading

try:
    import rtde_io  # from ur-rtde
except ImportError:
    rtde_io = None

from config import UR3_CONFIG


class UR3ConnectionError(RuntimeError):
    """Custom error type for all connection-related UR3 issues."""
    pass


class _UR3Client:
    """
    Minimal low-level UR3 client:

    - Dashboard (port 29999)
    - RTDE IO (port 30004)
    - SFTP program listing (for .urp files)

    No Script socket and no URScript helpers are implemented here.
    This class is meant to be wrapped by the higher-level `UR3` facade
    used by the GUI.
    """

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.ip: str = cfg.get("ip", "192.168.0.5")
        self.dashboard_port: int = int(cfg.get("dashboard_port", 29999))

        # SFTP listing configuration
        self.sftp_user: str = cfg.get("sftp_user", "root")
        self.sftp_password: str = cfg.get("sftp_password", "")
        self.programs_dir: str = cfg.get("programs_dir", "/programs")
        self.sftp_port: int = int(cfg.get("sftp_port", 22))

        # RTDE configuration
        self.rtde_register_default: int = int(cfg.get("rtde_input_register", 20))
        self.disp_register: int = int(cfg.get("disp_rtde_input_register", 21))

        self._dash_sock: Optional[socket.socket] = None
        self._lock = threading.Lock()
        self._rtde_io = None  # RTDEIOInterface instance

    # ------------------------------------------------------------------
    # Dashboard connection
    # ------------------------------------------------------------------
    def connect(self, timeout_s: float = 3.0) -> str:
        """
        Open the Dashboard socket connection and return the banner string.

        Parameters
        ----------
        timeout_s : float, default 3.0
            Connection timeout in seconds.

        Returns
        -------
        str
            Banner returned by the Dashboard socket (may be empty).

        Raises
        ------
        UR3ConnectionError
            If the TCP connection fails.
        """
        self.close()
        try:
            dash = socket.create_connection((self.ip, self.dashboard_port), timeout=timeout_s)
            dash.settimeout(timeout_s)
            self._dash_sock = dash
        except OSError as e:
            self.close()
            raise UR3ConnectionError(f"Erreur connexion UR3 ({self.ip}): {e}") from e

        banner = ""
        try:
            data = self._dash_sock.recv(1024)
            banner = data.decode(errors="ignore").strip()
        except OSError:
            banner = ""
        return banner

    def close(self) -> None:
        """Close the Dashboard socket if it is open."""
        s = self._dash_sock
        if s is not None:
            try:
                s.close()
            except OSError:
                pass
        self._dash_sock = None

    def is_connected(self) -> bool:
        """
        Return True if the Dashboard socket appears to be open, False otherwise.
        """
        return self._dash_sock is not None

    # ------------------------------------------------------------------
    # Dashboard command helpers
    # ------------------------------------------------------------------
    def _ensure_dash(self) -> socket.socket:
        """
        Ensure the Dashboard socket is available.

        Returns
        -------
        socket.socket
            The underlying dashboard socket.

        Raises
        ------
        UR3ConnectionError
            If the Dashboard is not connected.
        """
        if self._dash_sock is None:
            raise UR3ConnectionError("Dashboard non connecté.")
        return self._dash_sock

    def send_dashboard(self, cmd: str, expect_reply: bool = True) -> str:
        """
        Send a text command to the Dashboard and optionally read the reply.

        Parameters
        ----------
        cmd : str
            Command line to send (without trailing newline).
        expect_reply : bool, default True
            Whether a reply is expected. If False, the method will not
            attempt to read from the socket.

        Returns
        -------
        str
            Reply string from the Dashboard (may be empty).

        Raises
        ------
        UR3ConnectionError
            If send or receive fails.
        """
        with self._lock:
            s = self._ensure_dash()
            payload = (cmd.strip() + "\n").encode("ascii", errors="ignore")
            try:
                s.sendall(payload)
            except OSError as e:
                raise UR3ConnectionError(f"Erreur envoi Dashboard: {e}") from e

            if not expect_reply:
                return ""
            try:
                data = s.recv(4096)
            except OSError as e:
                raise UR3ConnectionError(f"Erreur lecture Dashboard: {e}") from e
        return data.decode(errors="ignore").strip()

    def ping(self) -> bool:
        """
        Lightweight health check on the Dashboard connection.

        Returns
        -------
        bool
            True if a non-empty reply is received, False otherwise.
        """
        try:
            return bool(self.send_dashboard("robotmode", expect_reply=True))
        except UR3ConnectionError:
            return False

    # Simple one-liner Dashboard helpers
    def get_robot_mode(self) -> str:      return self.send_dashboard("robotmode")
    def get_safety_mode(self) -> str:     return self.send_dashboard("safetymode")
    def power_on(self) -> str:            return self.send_dashboard("power on")
    def power_off(self) -> str:           return self.send_dashboard("power off")
    def brake_release(self) -> str:       return self.send_dashboard("brake release")
    def play(self) -> str:                return self.send_dashboard("play")
    def pause(self) -> str:               return self.send_dashboard("pause")
    def stop(self) -> str:                return self.send_dashboard("stop")
    def get_loaded_program(self) -> str:  return self.send_dashboard("get loaded program")
    def get_program_state(self) -> str:   return self.send_dashboard("programState")
    def load_program(self, name: str) -> str:  return self.send_dashboard(f"load {name}")

    # ------------------------------------------------------------------
    # SFTP program listing
    # ------------------------------------------------------------------
    def list_programs(self, recursive: bool = True) -> List[str]:
        """
        List all `.urp` programs found under the configured programs directory.

        Parameters
        ----------
        recursive : bool, default True
            If True, walk subdirectories recursively.

        Returns
        -------
        list[str]
            Sorted list of absolute paths (as seen from the robot) to `.urp` files.

        Raises
        ------
        UR3ConnectionError
            If `paramiko` is not installed or if SFTP connection/listing fails.
        """
        try:
            import paramiko, stat
        except Exception as e:
            raise UR3ConnectionError(
                "Le listing des programmes nécessite 'paramiko' (pip install paramiko)."
            ) from e

        host = self.ip
        port = int(self.sftp_port or 22)
        user = self.sftp_user or "ur"
        pwd = self.sftp_password or ""
        base = (self.programs_dir or "/programs").rstrip("/") or "/programs"

        transport = None
        sftp = None
        results: List[str] = []

        try:
            transport = paramiko.Transport((host, port))
            transport.connect(username=user, password=pwd)
            sftp = paramiko.SFTPClient.from_transport(transport)

            def _walk(dir_path: str):
                """Recursive SFTP walk collecting .urp files."""
                for attr in sftp.listdir_attr(dir_path):
                    name = attr.filename
                    full = f"{dir_path}/{name}".replace("//", "/")
                    if stat.S_ISDIR(attr.st_mode):
                        if recursive:
                            _walk(full)
                    else:
                        if name.lower().endswith(".urp"):
                            results.append(full)

            _walk(base)
            results.sort()
            return results
        except Exception as e:
            raise UR3ConnectionError(
                f"Echec SFTP vers {host}:{port} (user={user}): {e}"
            ) from e
        finally:
            try:
                if sftp:
                    sftp.close()
            finally:
                if transport:
                    transport.close()

    # ------------------------------------------------------------------
    # RTDE IO helpers
    # ------------------------------------------------------------------
    def _ensure_rtde_io(self):
        """
        Lazily create and return the RTDEIOInterface instance.

        Returns
        -------
        RTDEIOInterface

        Raises
        ------
        UR3ConnectionError
            If `ur-rtde` is not installed or connection fails.
        """
        if rtde_io is None:
            raise UR3ConnectionError(
                "rtde_io non disponible. Installe 'ur-rtde' (pip install ur-rtde)."
            )
        if self._rtde_io is None:
            try:
                self._rtde_io = rtde_io.RTDEIOInterface(self.ip)
            except Exception as e:
                raise UR3ConnectionError(f"Echec connexion RTDE IO ({self.ip}): {e}") from e
        return self._rtde_io

    def set_input_int_register_rtde(self, index: int, value: int) -> None:
        """
        Write an integer value to an RTDE input_int_register.

        Parameters
        ----------
        index : int
            Register index (0..23).
        value : int
            Value to write.

        Raises
        ------
        UR3ConnectionError
            If index is out of range or RTDE IO fails.
        """
        idx = int(index)
        if not (0 <= idx <= 23):
            raise UR3ConnectionError("index input_int_register hors bornes (0..23).")
        io = self._ensure_rtde_io()
        io.setInputIntRegister(idx, int(value))

    def set_vials_nb(self, vnum: int, register: Optional[int] = None) -> None:
        """
        Convenience: write vial number to the configured RTDE input register.

        Parameters
        ----------
        vnum : int
            Logical vial number expected by the UR program.
        register : int, optional
            Override input register index. If None, the default
            `rtde_input_register` from config is used.
        """
        reg = self.rtde_register_default if register is None else int(register)
        self.set_input_int_register_rtde(reg, int(vnum))

    def set_disp_nb(self, dnum: int, register: Optional[int] = None) -> None:
        """
        Convenience: write dispenser number to the configured RTDE input register.

        Parameters
        ----------
        dnum : int
            Logical dispenser number expected by the UR program.
        register : int, optional
            Override input register index. If None, the default
            `disp_rtde_input_register` from config is used.
        """
        reg = self.disp_register if register is None else int(register)
        self.set_input_int_register_rtde(reg, int(dnum))


# ----------------------------------------------------------------------
# Thin facade used by the GUI
# ----------------------------------------------------------------------
class UR3:
    """
    Thin facade around `_UR3Client` used by the GUI.

    This class keeps a stable, simple API for the UI layer while allowing
    the low-level implementation to evolve if needed.
    """

    def __init__(self, **override):
        cfg = dict(UR3_CONFIG)
        cfg.update(override)
        self._impl = _UR3Client(cfg)

    # Connection / state
    def connect(self, *a, **k):        return self._impl.connect(*a, **k)
    def close(self):                   return self._impl.close()
    def is_connected(self):            return self._impl.is_connected()
    def ping(self):                    return self._impl.ping()

    # Dashboard
    def get_robot_mode(self):          return self._impl.get_robot_mode()
    def get_safety_mode(self):         return self._impl.get_safety_mode()
    def power_on(self):                return self._impl.power_on()
    def power_off(self):               return self._impl.power_off()
    def brake_release(self):           return self._impl.brake_release()
    def play(self):                    return self._impl.play()
    def pause(self):                   return self._impl.pause()
    def stop(self):                    return self._impl.stop()
    def get_loaded_program(self):      return self._impl.get_loaded_program()
    def get_program_state(self):       return self._impl.get_program_state()
    def load_program(self, name: str): return self._impl.load_program(name)

    # SFTP
    def list_programs(self, *a, **k):  return self._impl.list_programs(*a, **k)

    # RTDE
    def set_input_int_register_rtde(self, *a, **k): return self._impl.set_input_int_register_rtde(*a, **k)
    def set_vials_nb(self, *a, **k):                return self._impl.set_vials_nb(*a, **k)
    def set_disp_nb(self, *a, **k):                 return self._impl.set_disp_nb(*a, **k)
